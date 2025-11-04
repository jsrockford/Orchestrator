"""
Conversation management layer that sits above the orchestrator.

The conversation manager owns turn-taking logic between controllers, captures
lightweight transcripts, and detects simple consensus/conflict signals so
higher-level workflows can decide when to stop or escalate a dialogue.
"""

from __future__ import annotations

import logging
import re
import time
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Sequence, Set, Tuple

from ..utils.logger import get_logger
from ..utils.output_parser import OutputParser, ParsedOutput, ValidationResult
from ..utils.config_loader import get_config
from .control_channel import ControlChannel, ControlCommand


_TOOL_LINE_PATTERN = re.compile(
    r"^[\t ]*[\u2713\u2717][\t ]+(?P<tool>[A-Za-z0-9_]+)\s+(?P<args>.+)$",
    re.MULTILINE,
)

_ANSI_RESET = "\033[0m"
_ANSI_GREEN = "\033[32m"
_ANSI_YELLOW = "\033[33m"
_ANSI_RED = "\033[31m"
_ANSI_CYAN = "\033[36m"


class ConversationManager:
    """
    Coordinate turn-taking between registered controllers via the orchestrator.

    The manager keeps a rolling history of the conversation, selects the next
    speaker (round-robin by default), and dispatches prompts through the
    DevelopmentTeamOrchestrator. Responses are captured when controllers expose
    a ``get_last_output`` helper – fallbacks keep the scaffold safe even if the
    integration is not yet complete.
    """

    def __init__(
        self,
        orchestrator,
        participants: Sequence[str],
        *,
        context_manager: Any | None = None,
        message_router: Any | None = None,
        participant_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
        max_history: int = 200,
        include_history: bool = True,
    ) -> None:
        if not participants:
            raise ValueError("ConversationManager requires at least one participant")

        self.logger = get_logger("orchestrator.conversation")
        self.orchestrator = orchestrator
        self.participants: List[str] = list(participants)
        self.context_manager = context_manager
        self.message_router = message_router
        metadata_source = participant_metadata or {}
        self.participant_metadata: Dict[str, Dict[str, Any]] = {}
        self._max_history = max(1, int(max_history))
        self._include_history = bool(include_history)
        self._turn_counter: int = 0
        self.history: Deque[Dict[str, Any]] = deque(maxlen=self._max_history)
        self._output_parsers: Dict[str, OutputParser] = {}
        self._conflict_code_pattern = re.compile(r"```.*?```", re.DOTALL)
        self._conflict_inline_code_pattern = re.compile(r"`[^`]*`")
        self._conflict_quoted_pattern = re.compile(r"\"[^\"]*\"|'[^']*'")
        tmux_cfg = get_config().get_section("tmux") or {}
        self._capture_tail_limit: int = int(tmux_cfg.get("capture_lines", 500) or 500)
        self._fallback_notices: Set[str] = set()
        self._delimiter_warnings: Set[str] = set()
        self._pending_interrupt: bool = False
        self._manual_pause_context: Optional[Dict[str, Any]] = None
        self._run_started_at: Optional[float] = None
        self._last_activity_at: Optional[float] = None
        self._active_max_turns: Optional[int] = None
        self._last_completed_agent: Optional[str] = None
        self._agent_activity: Dict[str, Dict[str, Any]] = {
            name: {"last_turn": None, "last_timestamp": None} for name in self.participants
        }
        self._status_error: Optional[str] = None

        completion_cfg = get_config().get_section("completion_detection") or {}
        self._completion_enabled: bool = bool(completion_cfg.get("enabled", False))
        self._completion_debug_enabled: bool = bool(completion_cfg.get("debug_logging", False))
        self._completion_mode: str = str(completion_cfg.get("mode") or "disabled").strip().lower()
        self._completion_signal: str = str(completion_cfg.get("explicit_signal") or "").strip()
        fallback_phrases = completion_cfg.get("fallback_phrases") or []
        self._completion_fallback_phrases: List[str] = [
            phrase.lower() for phrase in fallback_phrases if isinstance(phrase, str) and phrase.strip()
        ]
        consensus_cfg = completion_cfg.get("consensus") or {}
        try:
            threshold = float(consensus_cfg.get("threshold", 1.0))
        except (TypeError, ValueError):
            threshold = 1.0
        self._completion_threshold: float = max(0.0, min(1.0, threshold))
        try:
            recency_window = int(consensus_cfg.get("recency_window", 1))
        except (TypeError, ValueError):
            recency_window = 1
        self._completion_recency_window: int = max(1, recency_window)
        self._completion_require_consecutive: bool = bool(consensus_cfg.get("require_consecutive", False))
        self._completion_require_all_explicit: bool = bool(
            completion_cfg.get("require_explicit_from_all", False)
        )
        try:
            cooldown_turns = int(completion_cfg.get("cooldown_turns", 0))
        except (TypeError, ValueError):
            cooldown_turns = 0
        self._completion_cooldown_turns: int = max(0, cooldown_turns)
        self._completion_reset_on_disagreement: bool = bool(
            completion_cfg.get("reset_on_disagreement", True)
        )
        disagreement_phrases = completion_cfg.get("disagreement_phrases") or []
        self._completion_disagreement_phrases: List[str] = [
            phrase.lower() for phrase in disagreement_phrases if isinstance(phrase, str) and phrase.strip()
        ]
        self._completion_signals: Dict[str, Optional[int]] = {name: None for name in self.participants}
        self._completion_last_detected_turn: Optional[int] = None
        self._completion_last_reason: Optional[str] = None
        self._completion_explicit_signals: Set[str] = set()

        if self._completion_debug_enabled:
            self.logger.debug(
                "Completion debug logging enabled (mode=%s, require_all_explicit=%s, threshold=%.2f)",
                self._completion_mode,
                self._completion_require_all_explicit,
                self._completion_threshold,
            )

        loop_cfg = get_config().get_section("loop_detection") or {}
        self._loop_detection_enabled: bool = bool(loop_cfg.get("enabled", False))
        tool_loop_cfg = loop_cfg.get("tool_loops") or {}
        self._loop_tool_enabled: bool = bool(tool_loop_cfg.get("enabled", False))
        try:
            repeat_threshold = int(tool_loop_cfg.get("repeat_threshold", 4))
        except (TypeError, ValueError):
            repeat_threshold = 4
        self._loop_tool_threshold: int = max(2, repeat_threshold)
        try:
            history_window = int(tool_loop_cfg.get("history_window", self._loop_tool_threshold))
        except (TypeError, ValueError):
            history_window = self._loop_tool_threshold
        self._loop_tool_history_window: int = max(self._loop_tool_threshold, history_window)
        self._loop_tool_escalate: bool = bool(tool_loop_cfg.get("escalate_on_repeat", False))
        ignore_tools = tool_loop_cfg.get("ignore_tools") or []
        self._loop_tool_ignore: Set[str] = {
            str(tool).strip().lower() for tool in ignore_tools if isinstance(tool, str) and tool.strip()
        }
        self._loop_tool_state: Dict[str, Dict[str, Any]] = {}

        if self.message_router is not None:
            for name in self.participants:
                register = getattr(self.message_router, "register_participant", None)
                if callable(register):
                    try:
                        register(name)
                    except Exception as exc:  # noqa: BLE001
                        self.logger.debug("Message router registration failed for '%s': %s", name, exc)

        # Prepare metadata for participants and forward to context manager when available.
        for name in self.participants:
            merged: Dict[str, Any] = {"name": name, "type": "cli"}
            candidate = metadata_source.get(name)
            if isinstance(candidate, dict):
                merged.update(candidate)
            merged.setdefault("type", "cli")
            self.participant_metadata[name] = merged

        control_cfg = get_config().get_section("control_channel") or {}
        self._control_enabled: bool = bool(control_cfg.get("enabled", False))
        pipe_path = control_cfg.get("pipe_path")
        self.control_channel: Optional[ControlChannel] = None
        if self._control_enabled:
            try:
                self.control_channel = ControlChannel(pipe_path=pipe_path)
                self.control_channel.setup_pipe()
                self.logger.info(
                    "Control channel active at %s",
                    self.control_channel.pipe_path,
                )
            except Exception as exc:  # noqa: BLE001
                self.logger.error("Failed to initialize control channel: %s", exc)
                self.control_channel = None
                self._control_enabled = False

        status_cfg = control_cfg.get("status") or {}
        self._status_colorize: bool = bool(status_cfg.get("colorize", True))
        self._status_file_colorize: bool = bool(status_cfg.get("file_colorize", False))
        try:
            refresh_interval = float(status_cfg.get("refresh_seconds", 5.0))
        except (TypeError, ValueError):
            refresh_interval = 5.0
        self._status_refresh_interval: float = max(0.5, refresh_interval)
        try:
            progress_width = int(status_cfg.get("progress_bar_width", 20) or 20)
        except (TypeError, ValueError):
            progress_width = 20
        self._status_progress_width: int = max(5, progress_width)
        self._status_file_enabled: bool = bool(status_cfg.get("write_file", False))
        if self._status_file_enabled:
            status_path = status_cfg.get("file_path") or "/tmp/orchestrator_status.txt"
            self._status_file_path: Optional[Path] = Path(status_path)
        else:
            self._status_file_path = None
        self._status_last_written_at: Optional[float] = None

        self.human_control_mode: bool = False
        self._current_agent: Optional[str] = None

        if self.context_manager is not None:
            registrar = getattr(self.context_manager, "register_participant", None)
            if callable(registrar):
                for name, payload in self.participant_metadata.items():
                    try:
                        registrar(name, payload)
                    except TypeError:
                        registrar(name)
                    except Exception as exc:  # noqa: BLE001
                        self.logger.debug("Context manager registration failed for '%s': %s", name, exc)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def facilitate_discussion(self, topic: str, max_turns: int = 10) -> List[Dict[str, Any]]:
        """
        Run a short turn-based discussion around ``topic``.

        Returns:
            Ordered list of turn dictionaries. Each entry includes:
                - turn (int): Absolute turn index.
                - speaker (str): Controller name.
                - prompt (str): Command submitted to the controller.
                - dispatch (dict): Orchestrator dispatch summary.
                - response (str|None): Captured controller output, when available.
        """
        self._active_max_turns = max_turns
        for name in self.participants:
            self._agent_activity.setdefault(name, {"last_turn": None, "last_timestamp": None})
        if self._run_started_at is None:
            baseline = time.time()
            self._run_started_at = baseline
            self._last_activity_at = baseline
        self._refresh_status_snapshot(force=True)

        conversation: List[Dict[str, Any]] = []
        for _ in range(max_turns):
            self._refresh_status_snapshot()
            self._check_control_commands()
            while self.human_control_mode:
                self._refresh_status_snapshot()
                time.sleep(0.5)
                self._check_control_commands()

            if not self.human_control_mode and self._manual_pause_context:
                manual_result = self._complete_manual_pause(conversation)
                self._refresh_status_snapshot(force=True)
                if manual_result:
                    turn_record = manual_result.get("turn_record")
                    topic = manual_result.get("topic") or (turn_record.get("topic") if turn_record else "")
                    if manual_result.get("is_queued") and turn_record:
                        self.logger.info(
                            "Turn %s queued because controller '%s' is paused; awaiting resume",
                            turn_record.get("turn"),
                            turn_record.get("speaker"),
                        )
                        continue
                    if manual_result.get("consensus") and turn_record:
                        reason = turn_record.get("metadata", {}).get("consensus_reason")
                        if reason:
                            self.logger.info(
                                "Consensus detected after turn %s on '%s': %s",
                                turn_record.get("turn"),
                                topic,
                                reason,
                            )
                        else:
                            self.logger.info(
                                "Consensus detected after turn %s on '%s'",
                                turn_record.get("turn"),
                                topic,
                            )
                        self._notify_context_manager("consensus", turn_record)
                        continue
                    if manual_result.get("conflict") and turn_record:
                        conflict_reason = manual_result.get("conflict_reason")
                        self.logger.warning(
                            "Conflict detected after turn %s on '%s': %s",
                            turn_record.get("turn"),
                            topic,
                            conflict_reason,
                        )
                        self._notify_context_manager(
                            "conflict",
                            turn_record,
                            reason=conflict_reason,
                        )
                        continue

            speaker = self.determine_next_speaker(conversation)
            if speaker is None:
                self.logger.debug("No eligible speaker; stopping discussion on '%s'", topic)
                break

            self._current_agent = speaker
            try:
                prompt = self._build_prompt(speaker, topic, conversation)
                validation_cfg = get_config().get_section("response_validation") or {}
                max_retries = max(0, int(validation_cfg.get("max_retries", 2)))
                backoff_sequence = validation_cfg.get("retry_backoff_seconds") or []

                attempt = 1
                retries_used = 0
                dispatch_summary: Dict[str, Any] = {}
                parsed_output: Optional[ParsedOutput] = None
                validation_result = None
                is_queued = False

                while True:
                    self._check_control_commands()
                    if self.human_control_mode:
                        break

                    pre_snapshot = self._capture_snapshot(speaker)
                    dispatch_summary = self.orchestrator.dispatch_command(speaker, prompt)
                    is_queued = bool(dispatch_summary.get("queued"))
                    if is_queued:
                        parsed_output = None
                        validation_result = None
                        break

                    parsed_output = self._read_last_output(speaker, pre_snapshot)
                    parser = self._output_parsers.setdefault(speaker, OutputParser())
                    validation_result = parser.validate_response(parsed_output, speaker)
                    self._log_filtered_patterns(validation_cfg, speaker, validation_result)

                    if validation_result.valid:
                        break

                    self._log_validation_error(
                        validation_cfg,
                        speaker,
                        prompt,
                        validation_result,
                        attempt,
                    )

                    if not validation_result.should_retry or retries_used >= max_retries:
                        break

                    delay = self._select_retry_delay(backoff_sequence, retries_used)
                    retries_used += 1
                    attempt += 1
                    if delay > 0:
                        time.sleep(delay)
                    continue

                if self.human_control_mode:
                    if speaker:
                        context = self._ensure_manual_pause_context(speaker)
                        if pre_snapshot is not None:
                            context.setdefault("pre_snapshot", pre_snapshot)
                        context["prompt"] = prompt
                        context["topic"] = topic
                        context["dispatch_summary"] = dispatch_summary
                        context["retries_used"] = retries_used
                        context["max_retries"] = max_retries
                        context["queued"] = is_queued
                    # Paused during dispatch; restart loop after resume.
                    self.logger.info(
                        "Control channel pause activated during dispatch; deferring turn for '%s'",
                        speaker,
                    )
                    continue

                response = None
                if validation_result and validation_result.response_text is not None:
                    response = validation_result.response_text
                elif parsed_output:
                    response = parsed_output.response

                turn_record = {
                    "turn": self._turn_counter,
                    "speaker": speaker,
                    "topic": topic,
                    "prompt": prompt,
                    "dispatch": dispatch_summary,
                    "response": response,
                }
                if parsed_output:
                    turn_record["response_prompt"] = parsed_output.prompt
                    if validation_result:
                        turn_record["response_transcript"] = validation_result.cleaned_output
                    else:
                        turn_record["response_transcript"] = parsed_output.cleaned_output

                if validation_result:
                    turn_record["validation"] = {
                        "valid": validation_result.valid,
                        "issues": list(validation_result.issues),
                        "attempts": attempt,
                        "retries_used": retries_used,
                    }
                    if validation_result.ignored_patterns:
                        turn_record["validation"]["ignored_patterns"] = list(validation_result.ignored_patterns)
                conversation.append(turn_record)
                self._turn_counter += 1

                self._store_turn(turn_record)
                self._record_turn_activity(speaker, turn_record)

                metadata = turn_record.setdefault("metadata", {})
                loop_info = self._update_loop_state(conversation)
                if loop_info:
                    metadata["loop_detected"] = True
                    metadata["loop_detection"] = loop_info
                    if loop_info.get("escalate"):
                        metadata["loop_escalated"] = True
                    if loop_info.get("stage"):
                        metadata.setdefault("loop_stage", loop_info["stage"])

                completion_reached = self._update_completion_state(conversation)
                detect_fallback = False
                is_queued = bool(dispatch_summary.get("queued"))
                if not completion_reached:
                    detect_fallback = self.detect_consensus(conversation)
                consensus = completion_reached or detect_fallback
                if self._completion_debug_enabled:
                    self._log_completion_debug(
                        "consensus evaluation: turn=%s completion=%s detect=%s final=%s",
                        turn_record.get("turn"),
                        completion_reached,
                        detect_fallback,
                        consensus,
                    )
                conflict, reason = self.detect_conflict(conversation)

                if is_queued:
                    metadata["queued"] = True
                if validation_result and not validation_result.valid:
                    metadata["validation_failed"] = True
                    metadata["validation_issues"] = list(validation_result.issues)
                    metadata["retries_exhausted"] = bool(
                        validation_result.should_retry and retries_used >= max_retries
                    )
                if loop_info:
                    self._notify_context_manager(
                        "loop",
                        turn_record,
                        reason=loop_info.get("command_text") or loop_info.get("normalized_command"),
                    )
                if consensus:
                    metadata["consensus"] = True
                    if self._completion_last_reason:
                        metadata.setdefault("consensus_reason", self._completion_last_reason)
                if conflict:
                    metadata["conflict"] = True
                    if reason:
                        metadata["conflict_reason"] = reason

                self._record_with_context_manager(turn_record)
                self._route_message(turn_record, topic, dispatched=not is_queued)

                # Give the orchestrator a chance to drain any newly runnable work.
                try:
                    self.orchestrator.tick()
                except AttributeError:
                    self.logger.debug("Orchestrator tick unavailable; skipping background flush")

                if is_queued:
                    self.logger.info(
                        "Turn %s queued because controller '%s' is paused; awaiting resume",
                        turn_record["turn"],
                        speaker,
                    )
                    break

                if consensus:
                    log_reason = metadata.get("consensus_reason")
                    if log_reason:
                        self.logger.info(
                            "Consensus detected after turn %s on '%s': %s",
                            turn_record["turn"],
                            topic,
                            log_reason,
                        )
                    else:
                        self.logger.info("Consensus detected after turn %s on '%s'", turn_record["turn"], topic)
                    self._notify_context_manager("consensus", turn_record)
                    break

                if conflict:
                    self.logger.warning(
                        "Conflict detected after turn %s on '%s': %s",
                        turn_record["turn"],
                        topic,
                        reason,
                    )
                    self._notify_context_manager("conflict", turn_record, reason=reason)
                    break
            finally:
                self._current_agent = None
                self._refresh_status_snapshot()

        return conversation

    def determine_next_speaker(self, context: Sequence[Dict[str, Any]]) -> Optional[str]:
        """
        Pick the next controller to speak (round-robin by default).

        Context should be the running conversation log for the current session.
        If automation removed a controller mid-discussion, the manager skips it
        until it re-registers with the orchestrator.
        """
        active_participants = [
            name for name in self.participants if name in getattr(self.orchestrator, "controllers", {})
        ]
        if not active_participants:
            return None

        if not context:
            # Resume from the participant after the last global speaker, unless the last turn was queued.
            if self.history:
                last_turn = self.history[-1]
                last_speaker = last_turn.get("speaker")
                if last_speaker in active_participants:
                    last_metadata = last_turn.get("metadata") or {}
                    if last_metadata.get("queued"):
                        return last_speaker
                    idx = active_participants.index(last_speaker)
                    return active_participants[(idx + 1) % len(active_participants)]
            return active_participants[0]

        last_turn = context[-1]
        last_speaker = last_turn.get("speaker")
        last_metadata = last_turn.get("metadata") or {}
        if last_metadata.get("queued") and isinstance(last_speaker, str):
            return last_speaker if last_speaker in active_participants else active_participants[0]

        if last_speaker not in active_participants:
            return active_participants[0]

        idx = active_participants.index(last_speaker)
        return active_participants[(idx + 1) % len(active_participants)]

    def detect_consensus(self, conversation: Sequence[Dict[str, Any]]) -> bool:
        """
        Return True when the latest exchange signals consensus.

        Heuristics (subject to refinement):
            - Response text includes 'consensus' or 'agreement reached'.
            - Metadata flag ``consensus`` set truthy on the most recent turn.
        """
        if not conversation:
            return False

        latest = conversation[-1]
        turn_index = latest.get("turn")
        self._log_completion_debug(
            "detect_consensus entry: turn=%s completion_enabled=%s require_all=%s mode=%s",
            turn_index,
            self._completion_enabled,
            self._completion_require_all_explicit,
            self._completion_mode,
        )
        metadata = latest.get("metadata", {})
        if metadata and metadata.get("consensus"):
            self._log_completion_debug(
                "detect_consensus metadata flag present on turn=%s",
                turn_index,
            )
            return True

        if (
            self._completion_last_detected_turn is not None
            and latest.get("turn") == self._completion_last_detected_turn
        ):
            self._log_completion_debug(
                "detect_consensus short-circuit: last_detected_turn=%s",
                self._completion_last_detected_turn,
            )
            return True

        if self._completion_enabled:
            if self._completion_require_all_explicit:
                self._log_completion_debug(
                    "detect_consensus skipped: require_all_explicit active",
                )
                return False
            if self._completion_mode in {"explicit", "hybrid"} and self._completion_signal:
                self._log_completion_debug(
                    "detect_consensus skipped: explicit mode active",
                )
                return False

        response_text = (latest.get("response") or "")
        response = response_text.lower()
        keywords = ("consensus", "agreement reached", "we agree", "aligned")
        for keyword in keywords:
            if keyword in response:
                self._log_completion_debug(
                    "detect_consensus keyword '%s' matched on turn=%s", keyword, turn_index
                )
                return True

        self._log_completion_debug(
            "detect_consensus no match on turn=%s", turn_index
        )
        return False

    def detect_conflict(self, conversation: Sequence[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        Return (conflict_detected, reason).

        Conflict triggers when:
            - The most recent message contains negative keywords (disagree, block).
            - Two consecutive turns expose diverging stances in their metadata.
        """
        if len(conversation) < 2:
            return False, ""

        latest = conversation[-1]
        previous = conversation[-2]

        response_normalized = self._normalize_for_conflict_text(latest.get("response") or "")
        conflict_keywords = ("disagree", "blocker", "conflict", "reject")
        conflict_phrases = ("cannot agree", "cannot accept", "cannot support", "cannot proceed", "cannot endorse")

        for keyword in conflict_keywords:
            if keyword in response_normalized:
                return True, f"Keyword '{keyword}' indicates disagreement"

        for phrase in conflict_phrases:
            if phrase in response_normalized:
                return True, f"Phrase '{phrase}' indicates disagreement"

        stance_latest = self._extract_stance(latest)
        stance_previous = self._extract_stance(previous)
        if stance_latest and stance_previous and stance_latest != stance_previous:
            return True, f"Stance mismatch: {stance_previous!r} vs {stance_latest!r}"

        return False, ""

    def _update_loop_state(self, conversation: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not (self._loop_detection_enabled and self._loop_tool_enabled):
            return None

        if not conversation:
            return None

        latest = conversation[-1]
        speaker = latest.get("speaker")
        if not isinstance(speaker, str):
            return None

        current_turn = latest.get("turn")
        transcript = latest.get("response_transcript") or latest.get("response") or ""
        invocations = self._extract_tool_invocations(transcript)

        state = self._get_loop_tool_state(speaker)

        if not invocations:
            self._reset_loop_tool_state(speaker)
            return None

        invocation = invocations[-1]
        normalized_command = invocation["normalized"]

        if normalized_command == state["last_command"]:
            state["streak"] += 1
        else:
            state["last_command"] = normalized_command
            state["streak"] = 1
            state["warned_command"] = None
            state["warn_turn"] = None
            state["escalated"] = False

        state["last_raw"] = invocation["raw"]

        if state["streak"] < self._loop_tool_threshold:
            return None

        first_detection = (
            state["streak"] == self._loop_tool_threshold
            and state["warned_command"] != normalized_command
        )
        escalate = False
        stage = "warning"

        if first_detection:
            state["warned_command"] = normalized_command
            state["warn_turn"] = current_turn
            state["escalated"] = False
        else:
            stage = "continuing"
            can_escalate = (
                self._loop_tool_escalate
                and state["warned_command"] == normalized_command
                and not state["escalated"]
                and state["streak"] >= self._loop_tool_threshold + 1
            )
            if can_escalate:
                escalate = True
                stage = "escalation"
                state["escalated"] = True
            else:
                return None

        info = {
            "type": "tool_repeat",
            "tool": invocation["tool_original"],
            "tool_lower": invocation["tool"],
            "arguments": invocation["args"],
            "command_text": invocation["raw"],
            "normalized_command": normalized_command,
            "streak": state["streak"],
            "threshold": self._loop_tool_threshold,
            "stage": stage,
            "escalate": escalate,
            "commands_in_turn": [item["raw"] for item in invocations],
            "turn": current_turn,
            "speaker": speaker,
        }

        log_message = (
            "Tool loop detected for '%s': %s (streak %s, threshold %s)"
            % (speaker, invocation["raw"], state["streak"], self._loop_tool_threshold)
        )
        if escalate:
            self.logger.error("%s — escalation triggered", log_message)
        else:
            self.logger.warning("%s", log_message)

        return info

    def _extract_tool_invocations(self, transcript: str) -> List[Dict[str, str]]:
        if not transcript:
            return []

        invocations: List[Dict[str, str]] = []
        for match in _TOOL_LINE_PATTERN.finditer(transcript):
            tool_original = match.group("tool")
            if not tool_original:
                continue
            tool_lower = tool_original.strip().lower()
            if tool_lower in self._loop_tool_ignore:
                # Treat ignored tools as a break in the loop streak.
                invocations.clear()
                continue
            args = (match.group("args") or "").strip()
            raw = f"{tool_original.strip()} {args}".strip()
            normalized_args = args.lower()
            normalized_command = f"{tool_lower} {normalized_args}".strip()
            invocations.append(
                {
                    "tool_original": tool_original.strip(),
                    "tool": tool_lower,
                    "args": args,
                    "raw": raw,
                    "normalized": normalized_command,
                }
            )

        return invocations

    def _get_loop_tool_state(self, speaker: str) -> Dict[str, Any]:
        state = self._loop_tool_state.get(speaker)
        if state is None:
            state = {
                "last_command": None,
                "last_raw": None,
                "streak": 0,
                "warned_command": None,
                "warn_turn": None,
                "escalated": False,
            }
            self._loop_tool_state[speaker] = state
        return state

    def _reset_loop_tool_state(self, speaker: str) -> None:
        state = self._loop_tool_state.get(speaker)
        if state is None:
            return
        state["last_command"] = None
        state["last_raw"] = None
        state["streak"] = 0
        state["warned_command"] = None
        state["warn_turn"] = None
        state["escalated"] = False

    def _update_completion_state(self, conversation: Sequence[Dict[str, Any]]) -> bool:
        if not self._completion_enabled or self._completion_mode == "disabled":
            return False

        if not conversation:
            return False

        latest = conversation[-1]
        current_turn = latest.get("turn")
        if not isinstance(current_turn, int):
            self._log_completion_debug(
                "update_state abort: missing turn index (value=%r)",
                current_turn,
            )
            return False

        if current_turn < self._completion_cooldown_turns:
            self._log_completion_state(
                current_turn,
                speaker=latest.get("speaker"),
                note="cooldown active",
            )
            self._log_completion_debug(
                "update_state cooldown: turn=%s < cooldown=%s",
                current_turn,
                self._completion_cooldown_turns,
            )
            return False

        speaker = latest.get("speaker")
        if not isinstance(speaker, str):
            self._log_completion_debug(
                "update_state abort: missing speaker for turn=%s",
                current_turn,
            )
            return False

        response_text = (latest.get("response") or "").strip()
        normalized = response_text.lower()
        signal_sources: List[str] = []
        signal_detected = False

        self._log_completion_debug(
            "update_state entry: turn=%s speaker=%s enabled=%s mode=%s require_all=%s response_snippet=%r",
            current_turn,
            speaker,
            self._completion_enabled,
            self._completion_mode,
            self._completion_require_all_explicit,
            response_text[:160],
        )

        if self._completion_mode in {"explicit", "hybrid"} and self._completion_signal:
            if self._completion_signal.lower() in normalized:
                signal_detected = True
                signal_sources.append("explicit")
                self._log_completion_debug(
                    "explicit signal detected for %s on turn=%s",
                    speaker,
                    current_turn,
                )

        if not signal_detected and self._completion_mode in {"passive", "hybrid"}:
            for phrase in self._completion_fallback_phrases:
                if phrase and phrase in normalized:
                    signal_detected = True
                    signal_sources.append("passive")
                    self._log_completion_debug(
                        "passive phrase '%s' detected for %s turn=%s",
                        phrase,
                        speaker,
                        current_turn,
                    )
                    break

        disagreement_phrase: Optional[str] = None
        if self._completion_disagreement_phrases:
            for phrase in self._completion_disagreement_phrases:
                if phrase and phrase in normalized:
                    disagreement_phrase = phrase
                    break

        if disagreement_phrase and self._completion_reset_on_disagreement:
            self._reset_completion_state(
                f"{speaker} indicated additional work ('{disagreement_phrase}')"
            )
            metadata = latest.setdefault("metadata", {})
            metadata["completion_reset"] = {
                "speaker": speaker,
                "phrase": disagreement_phrase,
                "turn": current_turn,
            }
            metadata["completion_tracking"] = {
                "agreeing_participants": [],
                "ratio": 0.0,
                "threshold": self._completion_threshold,
                "consecutive_ok": True,
                "recency_window": self._completion_recency_window,
            }
            self._log_completion_state(
                current_turn,
                speaker=speaker,
                signal_detected=False,
                agreeing=[],
                ratio=0.0,
                consecutive_ok=True,
                consensus_reached=False,
                note="reset on disagreement",
            )
            self._log_completion_debug(
                "disagreement phrase '%s' triggered reset (turn=%s speaker=%s)",
                disagreement_phrase,
                current_turn,
                speaker,
            )
            return False

        self._completion_signals.setdefault(speaker, None)
        advisory_only = False
        is_explicit = "explicit" in signal_sources

        if signal_detected:
            if is_explicit:
                self._completion_explicit_signals.add(speaker)

            if self._completion_require_all_explicit and not is_explicit:
                advisory_only = True
            else:
                self._completion_signals[speaker] = current_turn
        elif is_explicit:
            # Record explicit acknowledgement even if we did not surface a
            # corresponding signal this turn (e.g., scrollback fragment).
            self._completion_explicit_signals.add(speaker)

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(
                "Completion raw: turn=%s speaker=%s detected=%s sources=%s explicit=%s advisory=%s "
                "signals=%s explicit_signals=%s",
                current_turn,
                speaker,
                signal_detected,
                list(signal_sources),
                is_explicit,
                advisory_only,
                {name: self._completion_signals.get(name) for name in self.participants},
                sorted(self._completion_explicit_signals),
            )

        for name, turn in list(self._completion_signals.items()):
            if turn is None:
                continue
            if current_turn - turn > self._completion_recency_window:
                self._completion_signals[name] = None

        active_participants = self._get_active_participants()
        if not active_participants:
            self._log_completion_state(
                current_turn,
                speaker=speaker,
                signal_detected=signal_detected,
                agreeing=[],
                ratio=0.0,
                consecutive_ok=True,
                consensus_reached=False,
                note="no active participants",
            )
            self._log_completion_debug(
                "update_state no active participants on turn=%s speaker=%s",
                current_turn,
                speaker,
            )
            return False

        agreeing = [
            name
            for name in active_participants
            if self._completion_signals.get(name) is not None
            and current_turn - self._completion_signals[name] <= self._completion_recency_window
        ]
        ratio = len(agreeing) / len(active_participants) if active_participants else 0.0

        consecutive_ok = True
        if self._completion_require_consecutive and agreeing:
            needed = len(agreeing)
            if len(conversation) < needed:
                consecutive_ok = False
            else:
                tail = conversation[-needed:]
                consecutive_ok = all(
                    entry.get("speaker") in agreeing
                    and self._completion_signals.get(entry.get("speaker")) == entry.get("turn")
                    for entry in tail
                )

        missing_explicit: List[str] = []
        if self._completion_require_all_explicit:
            for participant in active_participants:
                signal_turn = self._completion_signals.get(participant)
                has_recent_signal = (
                    signal_turn is not None
                    and current_turn - signal_turn <= self._completion_recency_window
                )
                has_explicit = participant in self._completion_explicit_signals
                if not (has_recent_signal and has_explicit):
                    missing_explicit.append(participant)
            all_explicit_met = not missing_explicit
        else:
            all_explicit_met = True

        speaker_signaled = self._completion_signals.get(speaker) == current_turn
        consensus_reached = (
            speaker_signaled
            and ratio >= self._completion_threshold
            and len(agreeing) > 0
            and consecutive_ok
            and all_explicit_met
        )

        if consensus_reached and self._completion_require_all_explicit:
            not_explicit = [
                participant for participant in active_participants if participant not in self._completion_explicit_signals
            ]
            if not_explicit:
                consensus_reached = False
                missing_explicit.extend(name for name in not_explicit if name not in missing_explicit)

        metadata = latest.setdefault("metadata", {})
        metadata["completion_tracking"] = {
            "agreeing_participants": list(agreeing),
            "ratio": ratio,
            "threshold": self._completion_threshold,
            "consecutive_ok": consecutive_ok,
            "recency_window": self._completion_recency_window,
        }
        if self._completion_require_all_explicit:
            metadata["completion_tracking"]["all_explicit_met"] = all_explicit_met
        if missing_explicit:
            metadata["completion_missing_explicit"] = list(dict.fromkeys(missing_explicit))
        else:
            metadata.pop("completion_missing_explicit", None)
        if signal_detected:
            metadata["completion_signal"] = True
            if signal_sources:
                metadata["completion_signal_type"] = signal_sources[0]
            if advisory_only:
                metadata["completion_signal_effective"] = False
                metadata["completion_signal_advisory"] = True
            else:
                metadata["completion_signal_effective"] = True
                metadata.pop("completion_signal_advisory", None)
        else:
            metadata.pop("completion_signal", None)
            metadata.pop("completion_signal_type", None)
            metadata.pop("completion_signal_effective", None)
            metadata.pop("completion_signal_advisory", None)

        log_notes: List[str] = []
        if advisory_only:
            log_notes.append("ignored (explicit required)")
        if missing_explicit:
            log_notes.append(f"missing explicit: {missing_explicit}")
        log_note = " | ".join(log_notes) if log_notes else None
        self._log_completion_state(
            current_turn,
            speaker=speaker,
            signal_detected=signal_detected,
            agreeing=agreeing,
            ratio=ratio,
            consecutive_ok=consecutive_ok,
            consensus_reached=consensus_reached,
            note=log_note,
        )

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(
                "Completion evaluation: turn=%s speaker=%s speaker_signaled=%s ratio=%.2f threshold=%.2f "
                "agreeing=%s consecutive_ok=%s all_explicit_met=%s missing_explicit=%s consensus=%s",
                current_turn,
                speaker,
                speaker_signaled,
                ratio,
                self._completion_threshold,
                list(agreeing),
                consecutive_ok,
                all_explicit_met,
                missing_explicit,
                consensus_reached,
            )

        self._log_completion_debug(
            "update_state summary: turn=%s speaker=%s detected=%s sources=%s ratio=%.2f "
            "agreeing=%s consecutive_ok=%s all_explicit_met=%s missing=%s consensus=%s",
            current_turn,
            speaker,
            signal_detected,
            tuple(signal_sources),
            ratio,
            tuple(agreeing),
            consecutive_ok,
            all_explicit_met,
            tuple(missing_explicit),
            consensus_reached,
        )

        if consensus_reached:
            reason = (
                f"Hybrid completion: {len(agreeing)}/{len(active_participants)} participants signaled "
                f"(threshold {self._completion_threshold:.2f})"
            )
            metadata.setdefault("consensus_reason", reason)
            self._completion_last_detected_turn = current_turn
            self._completion_last_reason = reason
            return True

        return False

    def _get_active_participants(self) -> List[str]:
        controllers = getattr(self.orchestrator, "controllers", None)
        if isinstance(controllers, dict) and controllers:
            return [name for name in self.participants if name in controllers]
        return list(self.participants)

    def _reset_completion_state(self, reason: Optional[str] = None) -> None:
        for name in list(self._completion_signals.keys()):
            self._completion_signals[name] = None
        self._completion_last_detected_turn = None
        self._completion_last_reason = None
        self._completion_explicit_signals.clear()
        if reason:
            self.logger.debug("Completion tracking reset: %s", reason)

    def _log_completion_state(
        self,
        current_turn: int,
        *,
        speaker: Optional[str] = None,
        signal_detected: bool = False,
        agreeing: Sequence[str] | None = None,
        ratio: float = 0.0,
        consecutive_ok: bool = True,
        consensus_reached: bool = False,
        note: Optional[str] = None,
    ) -> None:
        if not self.logger.isEnabledFor(logging.DEBUG):
            return

        agreeing_list = list(agreeing or [])
        summary = (
            f"turn={current_turn} speaker={speaker or '?'} signal={signal_detected} "
            f"agreeing={agreeing_list} ratio={ratio:.2f}/{self._completion_threshold:.2f} "
            f"consecutive_ok={consecutive_ok} consensus={consensus_reached}"
        )
        if note:
            summary = f"{summary} note={note}"
        self.logger.debug("Completion tracking: %s", summary)

    def _log_completion_debug(self, message: str, *args: Any) -> None:
        if not self._completion_debug_enabled:
            return
        if args:
            self.logger.debug("[completion-debug] " + message, *args)
        else:
            self.logger.debug("[completion-debug] %s", message)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _build_prompt(
        self,
        speaker: str,
        topic: str,
        conversation: Sequence[Dict[str, Any]],
    ) -> str:
        """
        Construct a lightweight prompt for the next speaker.

        If a context manager exposes ``build_prompt`` the conversation manager
        defers to it, otherwise a pragmatic default string is used.
        """
        if self.context_manager is not None:
            builder = getattr(self.context_manager, "build_prompt", None)
            if callable(builder):
                try:
                    return builder(
                        speaker,
                        topic,
                        include_history=self._include_history,
                        current_turn=self._turn_counter,
                    )
                except Exception as exc:  # noqa: BLE001
                    self.logger.warning("Context builder failed for '%s': %s", speaker, exc)

        turn_number = len(conversation)
        if not self._include_history:
            prompt = (
                f"[Turn {turn_number}] {speaker}, acknowledge the request '{topic}' "
                "and briefly confirm you can see it."
            )
        else:
            prompt = (
                f"[Turn {turn_number}] {speaker}, share your perspective on '{topic}'. "
                "Highlight progress, concerns, or next actions."
            )

        if self.message_router is not None:
            self._ensure_router_registration(speaker)
            formatter = getattr(self.message_router, "prepare_prompt", None)
            if callable(formatter):
                try:
                    prompt = formatter(
                        recipient=speaker,
                        topic=topic,
                        base_prompt=prompt,
                        include_history=self._include_history,
                    )
                except Exception as exc:  # noqa: BLE001
                    self.logger.debug("Message router prompt preparation failed: %s", exc)

        return prompt

    def _read_last_output(
        self,
        controller_name: str,
        pre_snapshot: Optional[List[str]],
    ) -> Optional[ParsedOutput]:
        controller = getattr(self.orchestrator, "controllers", {}).get(controller_name)
        if controller is None:
            return None

        self._wait_for_controller(controller_name, controller)

        capture = getattr(controller, "capture_scrollback", None)
        if callable(capture):
            try:
                post_snapshot = capture().splitlines()
            except Exception:  # noqa: BLE001
                self.logger.debug(
                    "Controller '%s' capture_scrollback failed; falling back to legacy output cache",
                    controller_name,
                    exc_info=True,
                )
            else:
                parser = self._output_parsers.setdefault(controller_name, OutputParser())
                if pre_snapshot is not None:
                    delta = self._compute_delta(pre_snapshot, post_snapshot, self._capture_tail_limit)
                else:
                    delta = post_snapshot[-self._capture_tail_limit :]
                if delta:
                    raw_text = "\n".join(delta)
                    parsed = parser.split_prompt_and_response(raw_text)
                    if parsed.response or parsed.cleaned_output.strip():
                        self._note_delimiter_usage(controller_name, parsed)
                        return parsed
                    return None
                return None

        reader = getattr(controller, "get_last_output", None)
        if callable(reader):
            if controller_name not in self._fallback_notices:
                self.logger.warning(
                    "Controller '%s' lacks scrollback capture support; falling back to get_last_output().",
                    controller_name,
                )
                self._fallback_notices.add(controller_name)
            try:
                raw_output = reader()
            except Exception:  # noqa: BLE001
                self.logger.debug(
                    "Controller '%s' get_last_output fallback failed",
                    controller_name,
                    exc_info=True,
                )
                return None
            if not raw_output:
                return None
            parser = self._output_parsers.setdefault(controller_name, OutputParser())
            parsed = parser.split_prompt_and_response(raw_output)
            if parsed.response or parsed.cleaned_output.strip():
                self._note_delimiter_usage(controller_name, parsed)
                return parsed
            return None

        if controller_name not in self._fallback_notices:
            self.logger.warning(
                "Controller '%s' exposes neither capture_scrollback nor get_last_output; no response captured.",
                controller_name,
            )
            self._fallback_notices.add(controller_name)
        return None

    def _note_delimiter_usage(self, controller_name: str, parsed: ParsedOutput) -> None:
        if parsed.used_response_delimiter:
            return
        if controller_name in self._delimiter_warnings:
            return
        self.logger.warning(
            "Controller '%s' response lacked <<<RESPONSE_START>>> delimiters; using heuristic fallback parsing.",
            controller_name,
        )
        self._delimiter_warnings.add(controller_name)

    def _ensure_manual_pause_context(self, agent_name: str) -> Dict[str, Any]:
        context = self._manual_pause_context or {}
        if context.get("agent") != agent_name:
            context = {"agent": agent_name, "turn": self._turn_counter}

        if "pre_snapshot" not in context or context.get("pre_snapshot") is None:
            snapshot = self._capture_snapshot(agent_name)
            if snapshot is not None:
                context["pre_snapshot"] = snapshot

        self._manual_pause_context = context
        return context

    def _complete_manual_pause(self, conversation: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        context = self._manual_pause_context
        if not context:
            return None

        agent_name = context.get("agent")
        if not agent_name:
            self._manual_pause_context = None
            return None

        controllers = getattr(self.orchestrator, "controllers", {})
        controller = controllers.get(agent_name) if isinstance(controllers, dict) else None
        if controller is None:
            self.logger.warning(
                "Manual resume skipped; controller '%s' unavailable for captured output",
                agent_name,
            )
            self._manual_pause_context = None
            return None

        pre_snapshot = context.get("pre_snapshot") or []
        post_snapshot_lines: List[str] = []
        snapshot = self._capture_snapshot(agent_name)
        if snapshot is not None:
            post_snapshot_lines = snapshot

        delta = self._compute_delta(pre_snapshot, post_snapshot_lines, self._capture_tail_limit)
        raw_text = "\n".join(delta) if delta else ""
        parser = self._output_parsers.setdefault(agent_name, OutputParser())
        parsed_output = parser.split_prompt_and_response(raw_text)
        self._note_delimiter_usage(agent_name, parsed_output)
        validation_result = parser.validate_response(parsed_output, agent_name)
        response_text = None
        if validation_result and validation_result.response_text is not None:
            response_text = validation_result.response_text
        elif parsed_output:
            response_text = parsed_output.response

        topic = context.get("topic") or "manual-intervention"
        prompt = context.get("prompt")
        dispatch_summary = context.get("dispatch_summary") or {}
        retries_used = context.get("retries_used", 0)
        max_retries = context.get("max_retries", 0)
        is_queued = bool(dispatch_summary.get("queued"))

        turn_index = context.get("turn", self._turn_counter)
        self._turn_counter = turn_index

        turn_record = {
            "turn": self._turn_counter,
            "speaker": agent_name,
            "topic": topic,
            "prompt": prompt,
            "dispatch": dispatch_summary,
            "response": response_text,
        }
        if parsed_output:
            turn_record["response_prompt"] = parsed_output.prompt
            if validation_result:
                turn_record["response_transcript"] = validation_result.cleaned_output
            else:
                turn_record["response_transcript"] = parsed_output.cleaned_output

        if validation_result:
            turn_record["validation"] = {
                "valid": validation_result.valid,
                "issues": list(validation_result.issues),
                "attempts": 1,
                "retries_used": retries_used,
            }
            if validation_result.ignored_patterns:
                turn_record["validation"]["ignored_patterns"] = list(validation_result.ignored_patterns)

        conversation.append(turn_record)
        self._turn_counter += 1

        self._store_turn(turn_record)
        self._record_turn_activity(agent_name, turn_record)

        metadata = turn_record.setdefault("metadata", {})
        loop_info = self._update_loop_state(conversation)
        if loop_info:
            metadata["loop_detected"] = True
            metadata["loop_detection"] = loop_info
            if loop_info.get("escalate"):
                metadata["loop_escalated"] = True
            if loop_info.get("stage"):
                metadata.setdefault("loop_stage", loop_info["stage"])

        completion_reached = self._update_completion_state(conversation)
        detect_fallback = False
        if not completion_reached:
            detect_fallback = self.detect_consensus(conversation)
        consensus = completion_reached or detect_fallback
        if self._completion_debug_enabled:
            self._log_completion_debug(
                "consensus evaluation: turn=%s completion=%s detect=%s final=%s",
                turn_record.get("turn"),
                completion_reached,
                detect_fallback,
                consensus,
            )
        conflict, reason = self.detect_conflict(conversation)

        if is_queued:
            metadata["queued"] = True
        if validation_result and not validation_result.valid:
            metadata["validation_failed"] = True
            metadata["validation_issues"] = list(validation_result.issues)
            metadata["retries_exhausted"] = bool(
                validation_result.should_retry and retries_used >= max_retries
            )

        if loop_info:
            self._notify_context_manager(
                "loop",
                turn_record,
                reason=loop_info.get("command_text") or loop_info.get("normalized_command"),
            )
        if consensus:
            metadata["consensus"] = True
            if self._completion_last_reason:
                metadata.setdefault("consensus_reason", self._completion_last_reason)
        if conflict:
            metadata["conflict"] = True
            if reason:
                metadata["conflict_reason"] = reason

        self._record_with_context_manager(turn_record)
        self._route_message(turn_record, topic, dispatched=not is_queued)

        try:
            self.orchestrator.tick()
        except AttributeError:
            self.logger.debug("Orchestrator tick unavailable; skipping background flush")

        self._manual_pause_context = None
        self._pending_interrupt = False
        self.logger.info(
            "Manual response captured for '%s'; automation resuming with next participant",
            agent_name,
        )
        return {
            "turn_record": turn_record,
            "consensus": consensus,
            "conflict": conflict,
            "conflict_reason": reason,
            "is_queued": is_queued,
            "topic": topic,
        }

    # ------------------------------------------------------------------ #
    # Control channel helpers
    # ------------------------------------------------------------------ #

    def _record_turn_activity(self, speaker: str, turn_record: Dict[str, Any]) -> None:
        now = time.time()
        self._last_activity_at = now
        self._last_completed_agent = speaker
        activity = self._agent_activity.setdefault(speaker, {"last_turn": None, "last_timestamp": None})
        activity["last_turn"] = turn_record.get("turn")
        activity["last_timestamp"] = now
        for name in self.participants:
            self._agent_activity.setdefault(name, {"last_turn": None, "last_timestamp": None})

    def _set_status_error(self, message: Optional[str]) -> None:
        if message and message.strip():
            self._status_error = message.strip()
        else:
            self._status_error = None

    def _check_control_commands(self) -> None:
        self._drain_control_commands(during_wait=False)

    def _control_interrupt_requested(self) -> bool:
        if self._pending_interrupt:
            return True

        interrupted = self._drain_control_commands(during_wait=True)
        if interrupted:
            self._pending_interrupt = True
            self.logger.debug(
                "Control channel interrupt acknowledged during wait (agent=%s)",
                self._current_agent,
            )
        return interrupted

    def _drain_control_commands(self, *, during_wait: bool) -> bool:
        if not self._control_enabled or self.control_channel is None:
            return False

        commands = self.control_channel.check_for_commands()
        if not commands:
            return False

        interrupt_requested = False

        for command in commands:
            verb = (command.name or "").upper()
            self._handle_control_command(command)
            if during_wait and self._should_interrupt_for_command(command, verb):
                interrupt_requested = True

        if during_wait and self.human_control_mode:
            interrupt_requested = True

        return interrupt_requested

    def _should_interrupt_for_command(self, command: ControlCommand, verb: str) -> bool:
        if verb == "PAUSE":
            return True
        if verb == "TEXT":
            return True
        if verb == "KEY":
            args = list(command.args or [])
            if len(args) < 2:
                return False
            keys = [arg.strip().lower() for arg in args[1:] if arg]
            if "escape" not in keys:
                return False
            if self._current_agent is None:
                return False
            targets = self._resolve_targets(args[0])
            return bool(targets and self._current_agent in targets)
        return False

    def _handle_control_command(self, command: ControlCommand) -> None:
        # Each verb maps to a dedicated handler; validation errors are fed back into STATUS output.
        verb = command.name.upper()
        if verb == "PAUSE":
            if self.human_control_mode:
                self.logger.debug("Control channel: PAUSE requested but already paused")
                self._set_status_error("Already paused")
                self._refresh_status_snapshot(force=True)
                return
            self.human_control_mode = True
            target = self._current_agent or "<none>"
            self.logger.info("Control channel: PAUSE acknowledged (current agent=%s)", target)
            if self._current_agent:
                self._send_escape(self._current_agent)
            self._set_status_error(None)
            self._refresh_status_snapshot(force=True)
            return

        if verb == "RESUME":
            if not self.human_control_mode:
                self.logger.debug("Control channel: RESUME requested but already running")
                self._set_status_error("Already running")
                self._refresh_status_snapshot(force=True)
                return
            self.human_control_mode = False
            self.logger.info("Control channel: RESUME acknowledged; resuming discussion")
            self._set_status_error(None)
            self._refresh_status_snapshot(force=True)
            return

        if verb == "STATUS":
            formatted = self._format_control_status()
            self.logger.info("Control channel status:\n%s", formatted)
            return

        if verb == "TEXT":
            # Inject a prompt mid-discussion (e.g., human guidance or clarification).
            self._handle_text_command(command)
            self._refresh_status_snapshot(force=True)
            return

        if verb == "KEY":
            # Send navigation/confirmation keys to resolve CLI dialogs without attaching manually.
            self._handle_key_command(command)
            self._refresh_status_snapshot(force=True)
            return

        self._set_status_error(f"Unknown command '{command.raw}'")
        self.logger.warning("Control channel: unknown command '%s'", command.raw)
        self._refresh_status_snapshot(force=True)

    def _format_control_status(self) -> str:
        timestamp = time.time()
        payload = self._gather_status_payload(timestamp)
        display = self._render_status_payload(payload, colorize=self._status_colorize)
        self._write_status_file_from_payload(payload, timestamp, force=True)
        return display

    def _gather_status_payload(self, timestamp: float) -> Dict[str, Any]:
        turn_current = self._turn_counter
        turn_total = self._active_max_turns if isinstance(self._active_max_turns, int) else None
        if turn_total is not None and turn_total <= 0:
            turn_total = None
        if turn_total is not None and turn_current > turn_total:
            # Clamp but preserve actual number of completed turns for display.
            ratio = 1.0
        elif turn_total:
            ratio = max(0.0, min(1.0, turn_current / turn_total))
        else:
            ratio = None

        if self._run_started_at is None:
            elapsed_seconds = None
        else:
            elapsed_seconds = max(0.0, timestamp - self._run_started_at)

        if self._last_activity_at is None:
            idle_seconds = None
        else:
            idle_seconds = max(0.0, timestamp - self._last_activity_at)

        status_level = "error" if self._status_error else ("paused" if self.human_control_mode else "running")
        participants: List[Dict[str, Any]] = []
        for name in self.participants:
            activity = self._agent_activity.get(name, {})
            last_turn = activity.get("last_turn")
            last_timestamp = activity.get("last_timestamp")
            since_seconds = None
            if isinstance(last_timestamp, (int, float)):
                since_seconds = max(0.0, timestamp - last_timestamp)
            state_key = "idle"
            if name in self._fallback_notices:
                state_key = "error"
            if self._current_agent == name:
                state_key = "active"
            elif state_key != "error" and self._last_completed_agent == name:
                state_key = "recent"
            participants.append(
                {
                    "name": name,
                    "state": state_key,
                    "label": {
                        "active": "ACTIVE",
                        "recent": "RECENT",
                        "error": "ERROR",
                    }.get(state_key, "IDLE"),
                    "last_turn": last_turn if isinstance(last_turn, int) else None,
                    "idle_seconds": since_seconds,
                    "is_last": name == self._last_completed_agent,
                }
            )

        return {
            "mode": "PAUSED" if self.human_control_mode else "RUNNING",
            "status_level": status_level,
            "turn_current": turn_current,
            "turn_total": turn_total,
            "progress_ratio": ratio,
            "active_agent": self._current_agent or "-",
            "last_agent": self._last_completed_agent or "-",
            "elapsed_seconds": elapsed_seconds,
            "idle_seconds": idle_seconds,
            "participants": participants,
            "error_message": self._status_error,
        }

    def _render_status_payload(self, payload: Dict[str, Any], *, colorize: bool) -> str:
        lines: List[str] = []
        status_color_map = {
            "running": _ANSI_GREEN,
            "paused": _ANSI_YELLOW,
            "error": _ANSI_RED,
        }
        mode_colored = self._apply_color(
            payload["mode"],
            status_color_map.get(payload["status_level"], _ANSI_GREEN),
            colorize=colorize,
        )

        turn_total = payload.get("turn_total")
        turn_current = payload.get("turn_current", 0)
        if turn_total is not None:
            status_line = f"Status: {mode_colored}  Turn {turn_current}/{turn_total}"
        else:
            status_line = f"Status: {mode_colored}  Turn {turn_current}"
        lines.append(status_line)

        progress_bar = self._build_progress_bar(
            payload.get("progress_ratio"),
            width=self._status_progress_width,
            colorize=colorize,
        )
        lines.append(f"Progress: {progress_bar}")

        active_agent = payload.get("active_agent") or "-"
        last_agent = payload.get("last_agent") or "-"
        lines.append(f"Active: {active_agent}  Last completed: {last_agent}")

        elapsed = self._format_duration(payload.get("elapsed_seconds"))
        idle = self._format_duration(payload.get("idle_seconds"))
        lines.append(f"Timing: elapsed={elapsed}  since_activity={idle}")

        if payload.get("error_message"):
            error_line = f"Last error: {payload['error_message']}"
            lines.append(self._apply_color(error_line, _ANSI_RED, colorize=colorize))

        lines.append("Participants:")
        status_colors = {
            "active": _ANSI_GREEN,
            "recent": _ANSI_CYAN,
            "error": _ANSI_RED,
        }
        for row in payload.get("participants", []):
            name = row.get("name", "?")
            state = row.get("state", "idle")
            label = row.get("label", "IDLE")
            status_text = f"{label:<7}"
            status_color = status_colors.get(state)
            status_text = self._apply_color(status_text, status_color, colorize=colorize)
            last_turn = row.get("last_turn")
            turn_text = "-" if last_turn is None else str(last_turn)
            idle_seconds = row.get("idle_seconds")
            idle_text = self._format_duration(idle_seconds)
            marker = "*" if row.get("is_last") else " "
            lines.append(f"  {marker} {name:<10} {status_text} last_turn={turn_text:<3} idle={idle_text}")

        return "\n".join(lines)

    def _build_progress_bar(self, ratio: Optional[float], *, width: int, colorize: bool) -> str:
        width = max(5, int(width))
        if ratio is None:
            bar = "-" * width
            return f"[{bar}]"
        ratio_clamped = max(0.0, min(1.0, float(ratio)))
        filled = int(round(ratio_clamped * width))
        filled = min(width, max(0, filled))
        bar = "#" * filled + "-" * (width - filled)
        percent = int(round(ratio_clamped * 100))
        text = f"[{bar}] {percent:3d}%"
        return self._apply_color(text, _ANSI_CYAN, colorize=colorize)

    @staticmethod
    def _format_duration(seconds: Optional[float]) -> str:
        if seconds is None or seconds < 0:
            return "--:--"
        total_seconds = int(round(seconds))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _apply_color(self, text: str, color_code: Optional[str], *, colorize: bool) -> str:
        if not colorize or not color_code:
            return text
        return f"{color_code}{text}{_ANSI_RESET}"

    def _write_status_file_from_payload(
        self,
        payload: Dict[str, Any],
        timestamp: float,
        *,
        force: bool = False,
    ) -> None:
        if not self._status_file_enabled or self._status_file_path is None:
            return
        if not force and self._status_last_written_at is not None:
            if timestamp - self._status_last_written_at < self._status_refresh_interval:
                return
        content = self._render_status_payload(payload, colorize=self._status_file_colorize)
        self._write_status_file(content)
        self._status_last_written_at = timestamp

    def _write_status_file(self, content: str) -> None:
        if self._status_file_path is None:
            return
        try:
            self._status_file_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            # Parent creation best-effort; ignore errors (likely /tmp).
            pass
        try:
            text = content if content.endswith("\n") else f"{content}\n"
            self._status_file_path.write_text(text, encoding="utf-8")
        except OSError as exc:  # noqa: BLE001
            self.logger.debug(
                "Control channel: failed to write status file %s: %s",
                self._status_file_path,
                exc,
            )

    def _refresh_status_snapshot(self, *, force: bool = False) -> None:
        if not self._status_file_enabled:
            return
        timestamp = time.time()
        payload = self._gather_status_payload(timestamp)
        self._write_status_file_from_payload(payload, timestamp, force=force)

    def _send_escape(self, agent_name: str) -> None:
        controllers = getattr(self.orchestrator, "controllers", {})
        if not isinstance(controllers, dict):
            self.logger.debug("Control channel: orchestrator controllers unavailable; cannot send Escape")
            return

        controller = controllers.get(agent_name)
        if controller is None:
            self.logger.debug("Control channel: controller '%s' not attached; cannot send Escape", agent_name)
            return

        sender = getattr(controller, "send_key", None)
        if callable(sender):
            try:
                sender("Escape")
                self.logger.debug("Control channel: sent Escape to '%s' via send_key", agent_name)
                return
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("Control channel: send_key Escape failed for '%s': %s", agent_name, exc)

        fallback = getattr(controller, "send_keys", None)
        if callable(fallback):
            try:
                fallback("Escape")
                self.logger.debug("Control channel: sent Escape to '%s' via send_keys fallback", agent_name)
                return
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("Control channel: send_keys Escape failed for '%s': %s", agent_name, exc)

        self.logger.debug(
            "Control channel: controller '%s' lacks send_key/send_keys for Escape; unable to interrupt",
            agent_name,
        )

    def _handle_text_command(self, command: ControlCommand) -> None:
        raw = command.raw or ""
        parts = raw.split(None, 1)
        if len(parts) < 2:
            self.logger.warning("Control channel: TEXT command missing target and prompt")
            self._set_status_error("TEXT command missing target and prompt")
            return

        payload = parts[1]
        if ":" not in payload:
            self.logger.warning("Control channel: TEXT command missing ':' separator: %s", raw)
            self._set_status_error("TEXT command missing ':' separator")
            return

        target_part, prompt_part = payload.split(":", 1)
        target = target_part.strip()
        prompt = prompt_part.lstrip()

        if not target:
            self.logger.warning("Control channel: TEXT command missing target participant")
            self._set_status_error("TEXT command missing target participant")
            return
        if not prompt:
            self.logger.warning("Control channel: TEXT command missing prompt text")
            self._set_status_error("TEXT command missing prompt text")
            return

        targets = self._resolve_targets(target)
        if not targets:
            self.logger.warning("Control channel: TEXT command target '%s' not recognized", target)
            self._set_status_error(f"TEXT target '{target}' not recognized")
            return

        self.logger.info(
            "Control channel: injecting prompt for %s (len=%d, paused=%s)",
            ", ".join(targets),
            len(prompt),
            self.human_control_mode,
        )

        failures: List[str] = []
        for resolved in targets:
            if not self._send_text_to_agent(resolved, prompt):
                failures.append(resolved)

        if failures:
            joined = ", ".join(failures)
            self.logger.warning(
                "Control channel: TEXT dispatch failures for %s",
                joined,
            )
            self._set_status_error(f"TEXT dispatch failed for: {joined}")
        else:
            self._set_status_error(None)

    def _resolve_targets(self, target: str) -> List[str]:
        normalized = target.strip().lower()
        if not normalized:
            return []

        active = self._get_active_participants()

        if normalized == "all":
            return list(active)

        if normalized == "both":
            return list(active[:2]) if active else []

        for participant in active:
            if participant.lower() == normalized:
                return [participant]

        return []

    def _send_text_to_agent(self, agent_name: str, prompt: str) -> bool:
        orchestrator_dispatch = getattr(self.orchestrator, "dispatch_command", None)
        controllers = getattr(self.orchestrator, "controllers", {})
        controller = controllers.get(agent_name) if isinstance(controllers, dict) else None

        if orchestrator_dispatch is None and controller is None:
            self.logger.warning(
                "Control channel: unable to inject prompt for '%s' (controller not registered)",
                agent_name,
            )
            return False

        if orchestrator_dispatch is not None:
            try:
                summary = orchestrator_dispatch(agent_name, prompt, submit=True)
            except Exception as exc:  # noqa: BLE001
                self.logger.error(
                    "Control channel: dispatch failed for '%s': %s",
                    agent_name,
                    exc,
                )
                return False
            summary = summary or {}
            dispatched = summary.get("dispatched")
            queued = summary.get("queued")
            self.logger.debug(
                "Control channel: prompt for '%s' dispatched=%s queued=%s",
                agent_name,
                dispatched,
                queued,
            )
            return bool(dispatched or queued or not summary)

        sender = getattr(controller, "send_command", None)
        if callable(sender):
            try:
                sender(prompt, submit=True)
                self.logger.debug(
                    "Control channel: prompt for '%s' sent via controller.send_command",
                    agent_name,
                )
            except Exception as exc:  # noqa: BLE001
                self.logger.error(
                    "Control channel: direct send failed for '%s': %s",
                    agent_name,
                    exc,
                )
                return False
            return True

        self.logger.warning(
            "Control channel: controller '%s' lacks send_command; unable to inject prompt",
            agent_name,
        )
        return False

    def _handle_key_command(self, command: ControlCommand) -> None:
        args = list(command.args or [])
        if len(args) < 2:
            self.logger.warning(
                "Control channel: KEY command requires target and at least one key (raw=%s)",
                command.raw,
            )
            self._set_status_error("KEY command requires target and at least one key")
            return

        target = args[0]
        keys = [key for key in args[1:] if key]
        if not keys:
            self.logger.warning("Control channel: KEY command missing key arguments")
            self._set_status_error("KEY command missing key arguments")
            return

        targets = self._resolve_targets(target)
        if not targets:
            self.logger.warning("Control channel: KEY command target '%s' not recognized", target)
            self._set_status_error(f"KEY target '{target}' not recognized")
            return

        self.logger.info(
            "Control channel: sending keys %s to %s",
            tuple(keys),
            ", ".join(targets),
        )
        normalized_keys = [key.strip().lower() for key in keys if key]
        failures: List[str] = []
        for resolved in targets:
            if not self._send_keys_to_agent(resolved, keys):
                failures.append(resolved)

        if failures:
            joined = ", ".join(failures)
            self.logger.warning(
                "Control channel: KEY dispatch failures for %s",
                joined,
            )
            self._set_status_error(f"KEY dispatch failed for: {joined}")
        else:
            should_pause = (
                "escape" in normalized_keys
                and self._current_agent is not None
                and self._current_agent in targets
            )
            if should_pause:
                pause_context = self._ensure_manual_pause_context(self._current_agent)
                pause_context.setdefault("topic", None)
                if not self.human_control_mode:
                    self.human_control_mode = True
                    self.logger.info(
                        "Control channel: KEY Escape triggered manual pause (active agent=%s)",
                        self._current_agent,
                    )
                self._pending_interrupt = True
                self._set_status_error("Manual control active (Escape); send RESUME to continue")
            else:
                self._set_status_error(None)

    def _send_keys_to_agent(self, agent_name: str, keys: Sequence[str]) -> bool:
        if not keys:
            return False

        controllers = getattr(self.orchestrator, "controllers", {})
        if not isinstance(controllers, dict):
            self.logger.warning(
                "Control channel: orchestrator controllers unavailable; cannot send keys"
            )
            return False

        controller = controllers.get(agent_name)
        if controller is None:
            self.logger.warning(
                "Control channel: controller '%s' not attached; cannot send keys",
                agent_name,
            )
            return False

        sender = getattr(controller, "send_key", None)
        fallback = getattr(controller, "send_keys", None)

        if callable(sender):
            success = True
            for key in keys:
                try:
                    sender(key)
                    self.logger.debug("Control channel: sent key '%s' to '%s'", key, agent_name)
                except Exception as exc:  # noqa: BLE001
                    self.logger.error(
                        "Control channel: send_key failed for '%s' (%s): %s",
                        agent_name,
                        key,
                        exc,
                    )
                    success = False
            return success

        if callable(fallback):
            success = True
            for key in keys:
                try:
                    fallback(key)
                    self.logger.debug(
                        "Control channel: sent key '%s' to '%s' via send_keys fallback",
                        key,
                        agent_name,
                    )
                except Exception as exc:  # noqa: BLE001
                    self.logger.error(
                        "Control channel: send_keys failed for '%s' (%s): %s",
                        agent_name,
                        key,
                        exc,
                    )
                    success = False
            return success

        self.logger.warning(
            "Control channel: controller '%s' lacks send_key/send_keys; cannot send keys",
            agent_name,
        )
        return False

    def _capture_snapshot(self, controller_name: str) -> Optional[List[str]]:
        controller = getattr(self.orchestrator, "controllers", {}).get(controller_name)
        if controller is None:
            return None

        capture = getattr(controller, "capture_scrollback", None)
        if not callable(capture):
            return None

        try:
            snapshot = capture()
        except Exception:  # noqa: BLE001
            self.logger.debug(
                "Controller '%s' pre-dispatch capture failed",
                controller_name,
                exc_info=True,
            )
            return None
        return snapshot.splitlines()

    def _wait_for_controller(self, controller_name: str, controller: Any) -> None:
        waiter = getattr(controller, "wait_for_ready", None)
        if callable(waiter):
            ready = None
            interrupt_triggered = False
            try:
                if self._control_enabled and self.control_channel is not None:
                    try:
                        ready = waiter(interrupt_callback=self._control_interrupt_requested)
                    except TypeError:
                        ready = waiter()
                else:
                    ready = waiter()
            except Exception:  # noqa: BLE001
                self.logger.debug(
                    "Controller '%s' wait_for_ready failed",
                    controller_name,
                    exc_info=True,
                )
            finally:
                interrupt_triggered = bool(self._pending_interrupt)
                self._pending_interrupt = False

            if ready is False and interrupt_triggered:
                self.logger.info(
                    "Controller '%s' wait_for_ready interrupted via control channel",
                    controller_name,
                )
        else:
            self._pending_interrupt = False

    @staticmethod
    def _compute_delta(
        previous: List[str],
        current: List[str],
        tail_limit: Optional[int],
    ) -> List[str]:
        if previous and len(current) >= len(previous):
            limit = min(len(previous), len(current))
            prefix = 0
            while prefix < limit and previous[prefix] == current[prefix]:
                prefix += 1
            delta = current[prefix:]
        else:
            delta = current

        if tail_limit is not None and len(delta) > tail_limit:
            delta = delta[-tail_limit:]
        return delta

    def _store_turn(self, turn: Dict[str, Any]) -> None:
        """Persist the turn in the rolling history buffer."""
        structured: Dict[str, Any] = {
            "turn": turn.get("turn"),
            "speaker": turn.get("speaker"),
            "topic": turn.get("topic"),
            "prompt": turn.get("prompt"),
            "response": turn.get("response"),
        }

        response_prompt = turn.get("response_prompt")
        if response_prompt is not None:
            structured["response_prompt"] = response_prompt

        response_transcript = turn.get("response_transcript")
        if response_transcript:
            structured["response_transcript"] = response_transcript

        metadata = turn.get("metadata")
        if isinstance(metadata, dict):
            structured["metadata"] = metadata.copy()
        elif metadata is not None:
            structured["metadata"] = metadata

        dispatch = turn.get("dispatch")
        if isinstance(dispatch, dict):
            structured["dispatch"] = dispatch.copy()
        elif dispatch is not None:
            structured["dispatch"] = dispatch

        self.history.append(structured)

    @staticmethod
    def _select_retry_delay(sequence: Any, ordinal: int) -> float:
        """Return the retry delay for the given ordinal (0-indexed)."""
        if sequence is None:
            return 0.0

        try:
            if isinstance(sequence, (list, tuple)):
                if not sequence:
                    return 0.0
                index = min(max(ordinal, 0), len(sequence) - 1)
                candidate = sequence[index]
            else:
                candidate = sequence
            return max(0.0, float(candidate))
        except (TypeError, ValueError):
            return 0.0

    def _log_filtered_patterns(
        self,
        validation_cfg: Dict[str, Any],
        speaker: str,
        result: Optional[ValidationResult],
    ) -> None:
        """Append filtered noise patterns to the configured log."""
        if not validation_cfg or result is None:
            return

        if not result.ignored_patterns:
            return

        path_str = validation_cfg.get("noise_log")
        if not path_str:
            return

        try:
            path = Path(path_str)
            path.parent.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            with path.open("a", encoding="utf-8") as handle:
                for pattern in result.ignored_patterns:
                    handle.write(f"{timestamp} {speaker}: filtered '{pattern}'\n")
        except Exception:  # noqa: BLE001
            self.logger.debug("Failed to write noise log '%s'", path_str, exc_info=True)

    def _log_validation_error(
        self,
        validation_cfg: Dict[str, Any],
        speaker: str,
        prompt: str,
        result: Optional[ValidationResult],
        attempt: int,
    ) -> None:
        """Append validation failures to the configured log file."""
        if not validation_cfg or result is None:
            return

        if not result.issues:
            return

        path_str = validation_cfg.get("error_log")
        if not path_str:
            return

        try:
            path = Path(path_str)
            path.parent.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            issues = ", ".join(result.issues)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(f"{timestamp} {speaker} attempt={attempt} issues={issues}\n")
                handle.write(f"Prompt: {prompt}\n")
                if result.cleaned_output:
                    handle.write("Output:\n")
                    handle.write(f"{result.cleaned_output}\n")
                handle.write("----\n")
        except Exception:  # noqa: BLE001
            self.logger.debug("Failed to write validation log '%s'", path_str, exc_info=True)

    def _record_with_context_manager(self, turn: Dict[str, Any]) -> None:
        """Forward the turn to the context manager if it exposes a compatible hook."""
        if self.context_manager is None:
            return

        for attr in ("record_turn", "append_turn", "save_turn"):
            handler = getattr(self.context_manager, attr, None)
            if callable(handler):
                try:
                    handler(turn)
                except Exception as exc:  # noqa: BLE001
                    self.logger.debug("Context manager hook '%s' failed: %s", attr, exc)
                return

    def _route_message(self, turn: Dict[str, Any], topic: str, *, dispatched: bool) -> None:
        if self.message_router is None or not dispatched:
            return

        deliver = getattr(self.message_router, "deliver", None)
        if not callable(deliver):
            return

        sender = turn.get("speaker")
        if not isinstance(sender, str):
            return

        response = turn.get("response") or ""
        metadata = turn.get("metadata")
        try:
            deliver(
                sender=sender,
                message=response,
                topic=topic,
                turn=turn.get("turn", 0),
                metadata=metadata if isinstance(metadata, dict) else None,
            )
        except Exception:  # noqa: BLE001
            self.logger.debug("Message routing failed for sender '%s'", sender, exc_info=True)

    def _normalize_for_conflict_text(self, text: str) -> str:
        if not text:
            return ""

        scrubbed = self._conflict_code_pattern.sub(" ", text)
        scrubbed = self._conflict_inline_code_pattern.sub(" ", scrubbed)
        scrubbed = self._conflict_quoted_pattern.sub(" ", scrubbed)
        return scrubbed.lower()

    def _ensure_router_registration(self, participant: str) -> None:
        if self.message_router is None:
            return

        register = getattr(self.message_router, "register_participant", None)
        if callable(register):
            try:
                register(participant)
            except Exception:  # noqa: BLE001
                self.logger.debug("Message router register failed for '%s'", participant, exc_info=True)

    def _notify_context_manager(self, event: str, turn: Dict[str, Any], *, reason: Optional[str] = None) -> None:
        if self.context_manager is None:
            return

        callbacks = []
        if event == "consensus":
            callbacks = ["record_consensus", "note_consensus", "log_consensus"]
        elif event == "conflict":
            callbacks = ["record_conflict", "note_conflict", "log_conflict"]
        elif event == "loop":
            callbacks = ["record_loop", "note_loop", "log_loop"]

        for attr in callbacks:
            handler = getattr(self.context_manager, attr, None)
            if callable(handler):
                try:
                    if event in {"conflict", "loop"}:
                        handler(turn, reason or "")
                    else:
                        handler(turn)
                except Exception as exc:  # noqa: BLE001
                    self.logger.debug("Context manager event '%s' failed via '%s': %s", event, attr, exc)
                break

    @staticmethod
    def _extract_stance(turn: Dict[str, Any]) -> Optional[str]:
        """Best-effort extraction of a stance label from turn metadata."""
        metadata = turn.get("metadata") or {}
        if isinstance(metadata, dict):
            stance = metadata.get("stance")
            if isinstance(stance, str):
                return stance.lower()
        stance = turn.get("stance")
        if isinstance(stance, str):
            return stance.lower()
        return None


__all__ = ["ConversationManager"]
