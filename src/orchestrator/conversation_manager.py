"""
Conversation management layer that sits above the orchestrator.

The conversation manager owns turn-taking logic between controllers, captures
lightweight transcripts, and detects simple consensus/conflict signals so
higher-level workflows can decide when to stop or escalate a dialogue.
"""

from __future__ import annotations

import logging
import os
import re
import time
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Sequence, Set, Tuple

from ..controllers.session_backend import TurnCancelledByUser
from ..utils.logger import get_logger
from ..utils.output_parser import OutputParser, ParsedOutput, ValidationResult
from ..utils.config_loader import get_config
from .control_channel import ControlChannel, ControlCommand


# Phase 4: HitL - Import broadcast function for WebSocket events
def _get_broadcast_function() -> Any:
    """
    Lazy import of broadcast_event_sync to avoid circular import.

    The web_api module imports conversation_manager (via orchestrator),
    so we can't import web_api at module level.
    """
    try:
        from .web_api import broadcast_event_sync
        return broadcast_event_sync
    except ImportError:
        # web_api may not be available in some contexts (tests, CLI-only usage)
        return None


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
        self._conflict_doc_reference_pattern = re.compile(r"@[A-Za-z0-9_\-/\.]*\.md")
        self._conflict_marker_pattern = re.compile(r"\[\[[A-Z0-9_]+\]\]")
        conflict_cfg = get_config().get_section("conflict_detection") or {}
        self._conflict_keyword_detection_enabled = bool(
            conflict_cfg.get("keyword_detection_enabled", False)
        )
        self._conflict_blocker_detection_enabled = bool(
            conflict_cfg.get("blocker_detection_enabled", False)
        )
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
        self._awaiting_turn_extension: bool = False
        self._paused_for_turn_limit: bool = False

        # Human participant state (Phase 1: HitL feature)
        self._waiting_on_human: bool = False
        self._bypass_human: bool = False
        self._pending_turn_participant: Optional[str] = None
        self._human_turn_started_at: Optional[float] = None
        # Track the live conversation list for external submissions (e.g., human submit/skip)
        self._conversation_ref: List[Dict[str, Any]] = []
        # Cache discussion configuration for turn records (may be None)
        self.discussion_config = getattr(self.orchestrator, "discussion_config", None)

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
            # Phase 1: HitL - Detect human participant (case-insensitive)
            is_human = name.lower() == "human"
            merged: Dict[str, Any] = {"name": name, "type": "human" if is_human else "cli"}
            candidate = metadata_source.get(name)
            if isinstance(candidate, dict):
                merged.update(candidate)
            # Ensure type is set correctly for human vs AI participants
            if is_human:
                merged["type"] = "human"
                merged["has_controller"] = False
            else:
                merged.setdefault("type", "cli")
                merged.setdefault("has_controller", True)
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

        context_cfg = get_config().get_section("context_management") or {}
        self._clear_enabled: bool = bool(context_cfg.get("enabled", False))
        raw_pattern = context_cfg.get("clear_signal")
        if raw_pattern and "(" in str(raw_pattern):
            pattern = str(raw_pattern)
        else:
            pattern = r"\[\[CLEAR(?::(\w+|all))?\]\]"
        try:
            self._clear_pattern = re.compile(pattern)
        except re.error:
            self.logger.error("Invalid CLEAR pattern '%s'; disabling context clears", pattern)
            self._clear_enabled = False
            self._clear_pattern = re.compile(r"$^")
        contexts = context_cfg.get("valid_contexts") or []
        self._clear_valid_contexts: Set[str] = {
            str(ctx).strip().lower() for ctx in contexts if isinstance(ctx, str) and ctx.strip()
        }
        if not self._clear_valid_contexts:
            self._clear_valid_contexts = {"orchestrated_turn", "messageboard.md"}
        try:
            debounce_seconds = int(context_cfg.get("debounce_seconds", 30))
        except (TypeError, ValueError):
            debounce_seconds = 30
        self._clear_debounce_seconds: int = max(0, debounce_seconds)
        default_clear_commands = {
            "claude": "/clear",
            "gemini": "/clear",
            "qwen": "/clear",
            "codex": "/new",
        }
        agents_cfg = context_cfg.get("agents") or {}
        for name, payload in agents_cfg.items():
            if not isinstance(payload, dict):
                continue
            command = payload.get("clear_command")
            if isinstance(command, str) and command.strip():
                default_clear_commands[name.strip().lower()] = command.strip()
        self._clear_commands = default_clear_commands
        self._clear_post_prompt: str = (
            context_cfg.get("post_clear_prompt")
            or "Context cleared. Re-read PRD.md, ARCHITECTURE.md, and the next section of PROJECT_TASKS.md before continuing."
        )
        self._clear_required_rereads: List[str] = [
            item for item in context_cfg.get("required_rereads", []) if isinstance(item, str) and item.strip()
        ]
        log_level_name = str(context_cfg.get("log_level", "INFO")).upper()
        self._clear_log_level = getattr(logging, log_level_name, logging.INFO)
        self._clear_log_path = Path(context_cfg.get("log_file") or "logs/context_clears.log")
        self._clear_logger = self._build_clear_logger()
        self._clear_last_ts: Dict[str, float] = {}
        self._clear_stats: Dict[str, Any] = {
            "total": 0,
            "per_agent": {},
            "last_clear_ts": {},
            "last_failure": None,
        }

        self.human_control_mode: bool = False
        self._current_agent: Optional[str] = None
        self._injected_messages: Deque[Dict[str, Any]] = deque()
        self._resume_speaker: Optional[str] = None
        self._awaiting_resume_after_cancel: bool = False
        self._pending_cancelled_turn: Optional[Dict[str, Any]] = None
        self._pending_injection_payloads: List[Dict[str, Any]] = []

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
        # Keep a reference so external human submit/skip can append turns to the active log
        self._conversation_ref = conversation
        while True:
            if getattr(self.orchestrator, "should_stop_discussion", False):
                self.logger.info("Stop requested; ending discussion on '%s'", topic)
                break

            if (
                self._active_max_turns is not None
                and self._turn_counter >= self._active_max_turns
            ):
                if getattr(self.orchestrator, "should_stop_discussion", False):
                    self.logger.info("Stop requested while awaiting turn extension on '%s'", topic)
                    break
                self._handle_turn_limit_reached(topic)
                time.sleep(0.5)
                self._refresh_status_snapshot()
                self._check_control_commands()
                continue

            if not self._wait_for_discussion_resumption():
                self.logger.info("Discussion paused indefinitely; stopping '%s'", topic)
                break

            self._flush_injected_messages(conversation, topic)
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
                resume_context = self._claim_pending_cancelled_turn(speaker)
                prompt_source: Optional[str] = None
                if resume_context:
                    topic = resume_context.get("topic") or topic
                    prompt_source = resume_context.get("prompt")

                if prompt_source is None:
                    prompt = self._build_prompt(speaker, topic, conversation)
                else:
                    prompt = prompt_source

                prompt, injected_into_prompt = self._apply_injected_prompts(speaker, prompt)
                validation_cfg = get_config().get_section("response_validation") or {}
                max_retries = max(0, int(validation_cfg.get("max_retries", 2)))
                backoff_sequence = validation_cfg.get("retry_backoff_seconds") or []

                attempt = 1
                retries_used = 0
                dispatch_summary: Dict[str, Any] = {}
                parsed_output: Optional[ParsedOutput] = None
                validation_result = None
                is_queued = False
                turn_cancelled = False

                # Phase 2: HitL - Check if speaker is human
                speaker_meta = self.participant_metadata.get(speaker, {})
                is_human_speaker = speaker_meta.get("type") == "human"

                if is_human_speaker:
                    # Human turn: set waiting state and wait for submit/skip
                    self._waiting_on_human = True
                    self._pending_turn_participant = speaker
                    self._human_turn_started_at = time.time()
                    timeout_seconds = self._get_human_timeout()
                    self.logger.info(
                        "Human turn started for '%s'. Waiting for human input (timeout: %s seconds)",
                        speaker,
                        timeout_seconds if timeout_seconds > 0 else "disabled",
                    )

                    # Phase 4: HitL - Emit human_turn_started event
                    broadcast_fn = _get_broadcast_function()
                    if broadcast_fn:
                        broadcast_fn({
                            "type": "human_turn_started",
                            "speaker": speaker,
                            "turn": self._turn_counter,
                            "timeout_seconds": timeout_seconds if timeout_seconds > 0 else None,
                            "timestamp": self._human_turn_started_at,
                        })

                    # Wait loop: pause discussion until human submits, skips, or times out
                    while self._waiting_on_human:
                        # Check for stop signal
                        if getattr(self.orchestrator, "should_stop_discussion", False):
                            self.logger.info("Stop requested during human turn; ending discussion")
                            break

                        # Check for timeout (if enabled)
                        if timeout_seconds > 0:
                            elapsed = time.time() - self._human_turn_started_at
                            if elapsed >= timeout_seconds:
                                self.logger.warning(
                                    "Human turn timeout after %.1f seconds; auto-skipping '%s'",
                                    elapsed,
                                    speaker,
                                )

                                # Phase 4: HitL - Emit human_turn_timeout event
                                broadcast_fn = _get_broadcast_function()
                                if broadcast_fn:
                                    broadcast_fn({
                                        "type": "human_turn_timeout",
                                        "speaker": speaker,
                                        "turn": self._turn_counter,
                                        "elapsed_seconds": elapsed,
                                        "timestamp": time.time(),
                                    })

                                # Record timeout as a skipped turn
                                self._record_human_skip(speaker, timeout=True, elapsed_time=elapsed)
                                break

                        # Poll for control commands and refresh status
                        self._refresh_status_snapshot()
                        self._check_control_commands()

                        # Sleep briefly to avoid busy-waiting
                        time.sleep(0.5)

                    # After human turn completes (submit/skip/timeout), continue to next turn
                    continue

                parser: Optional[OutputParser] = None
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

                    try:
                        parsed_output = self._read_last_output(speaker, pre_snapshot)
                    except TurnCancelledByUser:
                        turn_cancelled = True
                        self._handle_turn_cancelled(speaker, topic, prompt)
                        break
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

                if turn_cancelled:
                    self.logger.info(
                        "Turn for '%s' cancelled; waiting for resume before retrying",
                        speaker,
                    )
                    continue
                response = None
                if validation_result and validation_result.response_text is not None:
                    response = validation_result.response_text
                elif parsed_output:
                    response = parsed_output.response

                clear_result = self._process_clear_signals(
                    speaker=speaker,
                    response=response,
                    topic=topic,
                    source="orchestrated_turn",
                    turn_index=self._turn_counter,
                )

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

                # Recover richer responses from the transcript when the parsed
                # response is missing or truncated (e.g., when CLI UI glyphs
                # confuse the primary extractor).
                self._maybe_enrich_response(turn_record, parser)

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
                if clear_result:
                    metadata["clear_signal"] = clear_result
                if injected_into_prompt:
                    metadata["injection_applied"] = True
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

    def extend_turn_limit(self, extend_by: int) -> int:
        """Increase the active turn limit by ``extend_by`` turns."""
        try:
            delta = int(extend_by)
        except (TypeError, ValueError) as exc:  # noqa: BLE001
            raise ValueError("extend_by must be an integer") from exc

        if delta <= 0:
            raise ValueError("extend_by must be >= 1")

        if self._active_max_turns is None:
            self._active_max_turns = delta
        else:
            self._active_max_turns += delta

        new_total = self._active_max_turns
        self.logger.info("Turn limit extended by %s; new max_turns=%s", delta, new_total)

        if self._awaiting_turn_extension:
            self._awaiting_turn_extension = False
            if self._paused_for_turn_limit and self.human_control_mode:
                self.human_control_mode = False
            self._paused_for_turn_limit = False

            if getattr(self.orchestrator, "discussion_state", "").upper() == "PAUSED":
                setattr(self.orchestrator, "discussion_state", "RUNNING")

            self._refresh_status_snapshot(force=True)
        else:
            self._refresh_status_snapshot()

        return new_total

    def _handle_turn_limit_reached(self, topic: str) -> None:
        """Pause automation when the configured turn budget has been exhausted."""
        if self._awaiting_turn_extension:
            return

        self._awaiting_turn_extension = True
        self._paused_for_turn_limit = True
        if not self.human_control_mode:
            self.human_control_mode = True

        if getattr(self.orchestrator, "discussion_state", "").upper() == "RUNNING":
            setattr(self.orchestrator, "discussion_state", "PAUSED")

        self.logger.info(
            "Max turns (%s) reached for '%s'; awaiting extension or stop",
            self._active_max_turns,
            topic,
        )
        self._refresh_status_snapshot(force=True)

    def inject_message(
        self,
        role: str,
        content: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Queue a human (or system) message to be inserted into the conversation.

        The queue is processed at the start of each turn so injections are
        preserved in the transcript before the next participant speaks.
        """
        normalized_role = role.strip() if role else "human"
        payload = {
            "role": normalized_role,
            "content": content or "",
            "metadata": metadata.copy() if isinstance(metadata, dict) else {},
        }
        self._injected_messages.append(payload)
        self.logger.info(
            "Queued injected message from '%s' (len=%d, pending=%d)",
            normalized_role,
            len(payload["content"]),
            len(self._injected_messages),
        )

    def process_key_command(self, target: str, keys: Sequence[str] | str) -> bool:
        """
        Invoke the control-channel KEY handler without writing to the FIFO.

        Args:
            target: Controller name or alias (e.g., ``gemini``, ``all``).
            keys: Iterable of keys to send. A single string is accepted for convenience.

        Returns:
            True if the keys were dispatched successfully, False otherwise.
        """
        if not isinstance(target, str) or not target.strip():
            raise ValueError("KEY command requires a target controller name")

        if isinstance(keys, str):
            key_list = [keys]
        else:
            key_list = [
                str(key).strip()
                for key in keys
                if isinstance(key, str) and str(key).strip()
            ]

        if not key_list:
            raise ValueError("KEY command requires at least one key")

        args = [target.strip()]
        args.extend(key_list)
        raw = "KEY " + " ".join(args)
        command = ControlCommand(name="KEY", args=args, raw=raw)
        return self._handle_key_command(command)

    def _queue_pending_injection(self, payload: Dict[str, Any]) -> None:
        """Track injected text so it can be merged into the next prompt."""
        content = (payload.get("content") or "").strip()
        if not content:
            return

        metadata = payload.get("metadata") or {}
        targets_raw = metadata.get("targets")
        normalized_targets: Optional[Set[str]] = None
        if isinstance(targets_raw, (list, tuple, set)):
            normalized_targets = {
                str(item).strip().lower()
                for item in targets_raw
                if isinstance(item, str) and item.strip()
            }
            if not normalized_targets:
                normalized_targets = None

        entry = {
            "content": content,
            "role": payload.get("role") or "human",
            "metadata": metadata,
            "targets": normalized_targets,
        }
        self._pending_injection_payloads.append(entry)

    def _collect_injections_for_speaker(self, speaker: str) -> List[Dict[str, Any]]:
        """Return any queued injections that apply to ``speaker``."""
        if not self._pending_injection_payloads:
            return []

        speaker_key = (speaker or "").strip().lower()
        matched: List[Dict[str, Any]] = []
        remaining: List[Dict[str, Any]] = []

        for entry in self._pending_injection_payloads:
            targets = entry.get("targets")
            if targets and speaker_key not in targets:
                remaining.append(entry)
                continue

            matched.append(
                {
                    "content": entry.get("content"),
                    "role": entry.get("role"),
                    "metadata": entry.get("metadata"),
                }
            )

            if targets:
                residual = set(targets)
                residual.discard(speaker_key)
                if residual:
                    entry = entry.copy()
                    entry["targets"] = residual
                    remaining.append(entry)
            # Broadcast injections (no targets) are consumed once.

        self._pending_injection_payloads = remaining
        return matched

    def _apply_injected_prompts(self, speaker: str, prompt: str) -> Tuple[str, bool]:
        """Prepend any applicable injected text to ``prompt``."""
        payloads = self._collect_injections_for_speaker(speaker)
        if not payloads:
            return prompt, False

        directives = [
            (payload.get("content") or "").strip() for payload in payloads if payload.get("content")
        ]
        directives = [text for text in directives if text]
        if not directives:
            return prompt, False

        injected_text = "\n\n".join(directives)
        updated_prompt = f"{injected_text}\n\n{prompt}" if prompt else injected_text
        self.logger.info(
            "Applied %d injected message(s) to prompt for '%s'",
            len(directives),
            speaker,
        )
        return updated_prompt, True

    def _process_clear_signals(
        self,
        *,
        speaker: str,
        response: Optional[str],
        topic: str,
        source: str,
        turn_index: int,
    ) -> Optional[Dict[str, Any]]:
        if not self._clear_enabled or not response:
            return None

        normalized_source = (source or "").strip().lower()
        if normalized_source not in self._clear_valid_contexts:
            self.logger.debug(
                "Ignoring [[CLEAR]] from disallowed source '%s' (turn=%s)",
                source,
                turn_index,
            )
            return None

        matches = list(self._clear_pattern.finditer(response))
        if not matches:
            return None

        now = time.time()
        requested_targets: Set[str] = set()
        for match in matches:
            target_token = match.group(1) if match.lastindex else None
            targets = self._resolve_clear_targets_for_signal(target_token, speaker)
            requested_targets.update(targets)

        if not requested_targets:
            return None

        allowed_targets, skipped = self._filter_clear_targets_by_cooldown(requested_targets, now)
        for skipped_target in skipped:
            self._log_clear_event(
                status="cooldown_skipped",
                targets=[skipped_target],
                source=normalized_source,
                topic=topic,
                turn_index=turn_index,
                reason=f"Debounce {self._clear_debounce_seconds}s active",
            )

        if not allowed_targets:
            return {"source": source, "targets": [], "skipped": list(skipped)}

        self._handle_clear_signal(
            emitting_agent=speaker,
            targets=allowed_targets,
            source=normalized_source,
            topic=topic,
            turn_index=turn_index,
        )

        return {"source": source, "targets": list(allowed_targets)}

    def _resolve_clear_targets_for_signal(self, target_token: Optional[str], emitting_agent: str) -> Set[str]:
        if not target_token:
            return {emitting_agent} if emitting_agent else set()

        token = target_token.strip().lower()
        if token == "all":
            return set(self._get_active_participants())

        active = self._get_active_participants()
        for participant in active:
            if participant.lower() == token:
                return {participant}

        self.logger.debug(
            "CLEAR signal ignored for unknown target '%s' (emitter=%s)",
            target_token,
            emitting_agent,
        )
        return set()

    def _filter_clear_targets_by_cooldown(
        self,
        targets: Set[str],
        now: float,
    ) -> Tuple[Set[str], Set[str]]:
        if self._clear_debounce_seconds <= 0:
            return set(targets), set()

        allowed: Set[str] = set()
        skipped: Set[str] = set()
        for target in targets:
            last_ts = self._clear_last_ts.get(target)
            if last_ts is not None and now - last_ts < self._clear_debounce_seconds:
                skipped.add(target)
            else:
                allowed.add(target)
        return allowed, skipped

    def _handle_clear_signal(
        self,
        *,
        emitting_agent: str,
        targets: Set[str],
        source: str,
        topic: str,
        turn_index: int,
    ) -> None:
        timestamp = time.time()
        succeeded: List[str] = []
        failures: List[Tuple[str, str]] = []
        for target in sorted(targets):
            success, error_reason = self._dispatch_clear_for_target(target)
            if success:
                succeeded.append(target)
                self._clear_last_ts[target] = timestamp
                self._clear_stats["last_clear_ts"][target] = timestamp
                self._clear_stats["per_agent"][target] = (
                    self._clear_stats["per_agent"].get(target, 0) + 1
                )
            else:
                failures.append((target, error_reason or "dispatch_failed"))

        if succeeded:
            self._clear_stats["total"] += len(succeeded)
            self._log_clear_event(
                status="cleared",
                targets=succeeded,
                source=source,
                topic=topic,
                turn_index=turn_index,
                reason=f"emitter={emitting_agent}",
            )
            for target in succeeded:
                self._inject_post_clear_prompt(target, topic)

        if failures:
            reason = "; ".join(f"{name}:{msg}" for name, msg in failures)
            self._record_clear_failure(reason, targets=[name for name, _ in failures])
            self._log_clear_event(
                status="clear_failed",
                targets=[name for name, _ in failures],
                source=source,
                topic=topic,
                turn_index=turn_index,
                reason=reason,
            )

    def _dispatch_clear_for_target(self, target: str) -> Tuple[bool, Optional[str]]:
        command = self._clear_commands.get(target.lower())
        if not command:
            return False, "no_clear_command"

        dispatch_fn = getattr(self.orchestrator, "dispatch_command", None)
        if not callable(dispatch_fn):
            return False, "dispatch_unavailable"

        try:
            summary = dispatch_fn(target, command)
        except Exception as exc:  # noqa: BLE001
            self.logger.error("Clear dispatch failed for '%s': %s", target, exc)
            return False, str(exc)

        summary = summary or {}
        dispatched = summary.get("dispatched")
        queued = summary.get("queued")
        if dispatched or queued or not summary:
            controller = getattr(self.orchestrator, "controllers", {}).get(target, None)
            if controller:
                try:
                    self._wait_for_controller(target, controller)
                except Exception:  # noqa: BLE001
                    self.logger.debug("wait_for_ready after clear failed for '%s'", target, exc_info=True)
            return True, None

        return False, "dispatch_not_sent"

    def _inject_post_clear_prompt(self, target: str, topic: str) -> None:
        metadata = {"source": "context_clear", "targets": [target], "topic": topic}
        # Treat post-clear instructions as system-level so they are not attributed to an agent.
        self.inject_message("system", self._clear_post_prompt, metadata=metadata)

    def _log_clear_event(
        self,
        *,
        status: str,
        targets: Sequence[str],
        source: str,
        topic: str,
        turn_index: int,
        reason: Optional[str] = None,
    ) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        target_list = ", ".join(targets)
        message = (
            f"{timestamp} status={status} targets={target_list} source={source} "
            f"turn={turn_index} topic={topic or '-'}"
        )
        if reason:
            message = f"{message} reason={reason}"
        if self._clear_logger:
            self._clear_logger.info(message)
        else:
            self.logger.info("[context-clear] %s", message)

    def _record_clear_failure(self, reason: str, *, targets: Optional[Sequence[str]] = None) -> None:
        failure = {
            "timestamp": time.time(),
            "reason": reason,
        }
        if targets:
            failure["targets"] = list(targets)
        self._clear_stats["last_failure"] = failure

    def _get_clear_stats_snapshot(self) -> Dict[str, Any]:
        return {
            "enabled": self._clear_enabled,
            "total": self._clear_stats.get("total", 0),
            "per_agent": dict(self._clear_stats.get("per_agent", {})),
            "last_clear_ts": dict(self._clear_stats.get("last_clear_ts", {})),
            "last_failure": (
                dict(self._clear_stats["last_failure"]) if self._clear_stats.get("last_failure") else None
            ),
            "cooldown_seconds": self._clear_debounce_seconds,
        }

    def _build_clear_logger(self) -> Optional[logging.Logger]:
        try:
            self._clear_log_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:  # noqa: BLE001
            self.logger.debug("Failed to ensure context clear log directory: %s", self._clear_log_path, exc_info=True)

        logger = logging.getLogger("orchestrator.context_clear")
        logger.setLevel(self._clear_log_level)
        logger.propagate = False
        existing_files = {
            getattr(handler, "baseFilename", None) for handler in logger.handlers if hasattr(handler, "baseFilename")
        }
        log_path_str = str(self._clear_log_path)
        if log_path_str not in existing_files:
            try:
                handler = logging.FileHandler(log_path_str)
                handler.setLevel(self._clear_log_level)
                formatter = logging.Formatter("%(message)s")
                handler.setFormatter(formatter)
                logger.addHandler(handler)
            except Exception:  # noqa: BLE001
                self.logger.debug("Failed to configure context clear logger at %s", log_path_str, exc_info=True)
                return None
        return logger

    def get_status_snapshot(self) -> Dict[str, Any]:
        """
        Return a lightweight snapshot describing the current discussion.

        Phase 3: HitL - Includes human turn state for UI rendering.
        """
        # Check if human is in participants
        human_enabled = any(
            self.participant_metadata.get(p, {}).get("type") == "human"
            for p in self.participants
        )

        return {
            "turn_counter": self._turn_counter,
            "current_agent": self._current_agent,
            "participants": list(self.participants),
            "human_control_mode": self.human_control_mode,
            "pending_injections": len(self._injected_messages),
            "max_turns": self._active_max_turns,
            "awaiting_turn_extension": self._awaiting_turn_extension,
            "last_activity_at": self._last_activity_at,
            "run_started_at": self._run_started_at,
            "clear_stats": self._get_clear_stats_snapshot(),
            # Phase 3: HitL - Human turn state
            "waiting_on_human": self._waiting_on_human,
            "bypass_human": self._bypass_human,
            "pending_turn_participant": self._pending_turn_participant,
            "human_enabled": human_enabled,
        }

    def determine_next_speaker(self, context: Sequence[Dict[str, Any]]) -> Optional[str]:
        """
        Pick the next controller to speak (round-robin by default).

        Context should be the running conversation log for the current session.
        If automation removed a controller mid-discussion, the manager skips it
        until it re-registers with the orchestrator.

        Phase 2: HitL - Human participants are included in rotation. If bypass_human
        is True, human turns are skipped in favor of the next AI participant.
        """
        # Phase 2: HitL - Include all participants (both AI and human)
        # Human participants may have controller=None, so check metadata instead
        active_participants = []
        for name in self.participants:
            meta = self.participant_metadata.get(name, {})
            is_human = meta.get("type") == "human"

            if is_human:
                # Human participants are always "active" (no controller check needed)
                # Skip if bypass_human is enabled
                if not self._bypass_human:
                    active_participants.append(name)
            else:
                # AI participants must have a registered controller
                if name in getattr(self.orchestrator, "controllers", {}):
                    active_participants.append(name)

        if not active_participants:
            return None

        if self._resume_speaker:
            pending = self._resume_speaker
            if pending in active_participants:
                self.logger.debug("Resuming cancelled turn with '%s'", pending)
                self._resume_speaker = None
                return pending
            self.logger.debug(
                "Resume target '%s' unavailable; clearing pending resume",
                pending,
            )
            self._resume_speaker = None

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

    def _maybe_enrich_response(
        self,
        turn_record: Dict[str, Any],
        parser: Optional[OutputParser] = None,
    ) -> None:
        """
        Fill in or upgrade ``turn_record['response']`` using the transcript.

        Some CLI outputs include UI glyphs (e.g., block characters) that can
        confuse the primary response extractor, yielding an empty or
        truncated message. When we have a transcript, attempt to pull a more
        complete response (preferring explicit delimiters) and replace the
        stored response if it is currently missing or clearly shorter.
        """
        transcript = turn_record.get("response_transcript")
        if not transcript:
            return

        response = turn_record.get("response")
        cleaned_existing = str(response).strip() if response is not None else ""

        parser_obj = parser or self._output_parsers.get(turn_record.get("speaker"))
        if parser_obj is None:
            parser_obj = OutputParser()

        recovered: Optional[str] = None
        try:
            recovered = parser_obj.extract_delimited_response(transcript)
            if not recovered:
                recovered = parser_obj.get_last_response(transcript)
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("Response recovery from transcript failed: %s", exc)
            return

        candidate = (recovered or "").strip()
        if not candidate:
            return

        if not cleaned_existing or len(candidate) > len(cleaned_existing):
            turn_record["response"] = candidate

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

        response_raw = latest.get("response") or ""
        response_normalized = self._normalize_for_conflict_text(response_raw)
        conflict_keywords = ("disagree", "conflict", "reject")
        conflict_phrases = ("cannot agree", "cannot accept", "cannot support", "cannot proceed", "cannot endorse")

        if self._conflict_keyword_detection_enabled:
            for keyword in conflict_keywords:
                idx = response_normalized.find(keyword)
                if idx != -1:
                    snippet = self._extract_conflict_snippet(response_normalized, idx, idx + len(keyword))
                    return True, f"Keyword '{keyword}' indicates disagreement (context: {snippet})"

            for phrase in conflict_phrases:
                idx = response_normalized.find(phrase)
                if idx != -1:
                    snippet = self._extract_conflict_snippet(response_normalized, idx, idx + len(phrase))
                    return True, f"Phrase '{phrase}' indicates disagreement (context: {snippet})"

        if self._conflict_blocker_detection_enabled:
            blocker_patterns = (
                re.compile(r"\b(?:is|are|remains|became|becomes)\s+(?:a\s+)?blocker(?:s)?\b"),
                re.compile(r"\b(?:blocker|blocking|blocks?)\b.*\b(can(?:not|'t)|unable|stuck|blocked)\b"),
                re.compile(r"\b(can(?:not|'t)|unable|stuck|blocked)\b.*\b(?:blocker|blocking|blocks?)\b"),
                re.compile(r"\b(blocks?|blocking)\s+(?:my|our|the)\s+(?:progress|work|ability|plan)\b"),
            )
            for pattern in blocker_patterns:
                match = pattern.search(response_normalized)
                if match:
                    snippet = self._extract_conflict_snippet(response_normalized, match.start(), match.end())
                    return True, f"Phrase '{match.group(0)}' indicates disagreement (context: {snippet})"

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

        # Phase 2: HitL - Exclude human turns from loop detection
        speaker_meta = self.participant_metadata.get(speaker, {})
        if speaker_meta.get("type") == "human":
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
        """
        Update completion detection state based on the latest turn.

        Phase 2: HitL - Human completion signals count toward consensus just like AI signals.
        No special handling needed - the generic logic works for both human and AI participants.
        """
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
        prompt: Optional[str] = None
        if self.context_manager is not None:
            builder = getattr(self.context_manager, "build_prompt", None)
            if callable(builder):
                try:
                    prompt = builder(
                        speaker,
                        topic,
                        include_history=self._include_history,
                        current_turn=self._turn_counter,
                    )
                except Exception as exc:  # noqa: BLE001
                    self.logger.warning("Context builder failed for '%s': %s", speaker, exc)

        if prompt is None:
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
            "Controller '%s' response lacked [[RESPONSE_START]] delimiters; using heuristic fallback parsing.",
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

        clear_result = self._process_clear_signals(
            speaker=agent_name,
            response=response_text,
            topic=context.get("topic") or "manual-intervention",
            source="orchestrated_turn",
            turn_index=self._turn_counter,
        )

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
        if clear_result:
            metadata["clear_signal"] = clear_result
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

    def _claim_pending_cancelled_turn(self, speaker: str) -> Optional[Dict[str, Any]]:
        """
        Return the stored cancelled turn context for ``speaker``, if any.

        The stored context is cleared once claimed so we don't replay it twice.
        """
        context = self._pending_cancelled_turn
        if not context:
            return None
        pending_speaker = context.get("speaker")
        if pending_speaker and pending_speaker != speaker:
            return None
        self._pending_cancelled_turn = None
        return context.copy()

    def _handle_turn_cancelled(self, speaker: str, topic: str, prompt: str) -> None:
        self._resume_speaker = speaker
        self._awaiting_resume_after_cancel = True
        self._pending_cancelled_turn = {
            "speaker": speaker,
            "topic": topic,
            "prompt": prompt or "",
        }
        state = getattr(self.orchestrator, "discussion_state", None)
        if isinstance(state, str) and state.upper() == "RUNNING":
            self.logger.info("Marking discussion paused after cancellation on '%s'", speaker)
            setattr(self.orchestrator, "discussion_state", "PAUSED")
        self._set_status_error(f"Turn cancelled for {speaker}; awaiting resume")
        self._refresh_status_snapshot(force=True)
        self.logger.info(
            "Cancellation detected for '%s' (topic='%s'); prompt len=%d",
            speaker,
            topic,
            len(prompt or ""),
        )

    def _wait_for_discussion_resumption(self) -> bool:
        orchestrator_state = getattr(self.orchestrator, "discussion_state", "RUNNING")
        if orchestrator_state != "PAUSED":
            if self._awaiting_resume_after_cancel:
                self._awaiting_resume_after_cancel = False
                self._set_status_error(None)
            return True

        self.logger.info("Discussion state is PAUSED; waiting for resume signal")
        while True:
            if getattr(self.orchestrator, "should_stop_discussion", False):
                self.logger.info("Stop requested while waiting for resume; exiting discussion wait")
                return False
            orchestrator_state = getattr(self.orchestrator, "discussion_state", "RUNNING")
            if orchestrator_state != "PAUSED":
                self._awaiting_resume_after_cancel = False
                self._set_status_error(None)
                self._refresh_status_snapshot(force=True)
                return True
            self._refresh_status_snapshot()
            self._check_control_commands()
            time.sleep(0.3)

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

    def _get_human_timeout(self) -> int:
        """
        Get the configured timeout for human turns (in seconds).

        Phase 2: HitL - Returns the turn_timeout from human config, or 0 if disabled.
        """
        from ..utils.config_loader import get_config
        human_cfg = get_config().get_section("human") or {}
        return int(human_cfg.get("turn_timeout", 300))

    def _record_human_skip(
        self,
        speaker: str,
        *,
        timeout: bool = False,
        elapsed_time: Optional[float] = None,
    ) -> None:
        """
        Record a human turn skip in conversation history.

        Phase 3: HitL - Creates a turn record for skipped human turns,
        either manual skip or timeout auto-skip.

        Args:
            speaker: Name of the human participant
            timeout: True if this is a timeout auto-skip, False for manual skip
            elapsed_time: Time elapsed before timeout (for logging)
        """
        from ..utils.config_loader import get_config

        # Build turn record
        turn_record = {
            "turn": self._turn_counter,
            "speaker": speaker,
            "topic": self.discussion_config.get("discussion_topic") if self.discussion_config else "",
            "prompt": "",
            "response": "[Human turn skipped - timeout]" if timeout else "[Human turn skipped]",
            "metadata": {
                "human_turn": True,
                "skipped": True,
                "skipped_at": time.time(),
            },
        }

        if timeout:
            turn_record["metadata"]["timeout"] = True
            if elapsed_time is not None:
                turn_record["metadata"]["elapsed_seconds"] = elapsed_time

        # Get response marker from config
        human_cfg = get_config().get_section("human") or {}
        response_marker = human_cfg.get("response_marker", "👤")
        turn_record["response_marker"] = response_marker

        # Phase 7: Keep the active conversation log in sync for human turns
        conversation_ref = getattr(self, "_conversation_ref", None)
        if isinstance(conversation_ref, list):
            conversation_ref.append(turn_record)

        # Add to conversation history
        self.history.append(turn_record)
        self._turn_counter += 1

        # Store turn and record activity
        self._store_turn(turn_record)
        self._record_turn_activity(speaker, turn_record)
        # Keep context manager history aligned for skipped/timeout human turns
        self._record_with_context_manager(turn_record)

        # Deliver the skipped (or timed out) human turn so other participants are aware
        router = getattr(self, "message_router", None)
        if router is not None and hasattr(router, "deliver"):
            try:
                router.deliver(
                    sender=speaker,
                    message=turn_record.get("response") or "",
                    topic=turn_record.get("topic") or "",
                    turn=turn_record.get("turn") or self._turn_counter,
                    metadata=turn_record.get("metadata"),
                )
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("Failed to route skipped human turn: %s", exc)

        # Clear waiting state
        self._waiting_on_human = False
        self._pending_turn_participant = None
        self._human_turn_started_at = None

        self.logger.info(
            "Human turn %s for '%s' (turn %d)%s",
            "timed out" if timeout else "skipped",
            speaker,
            turn_record["turn"],
            f" after {elapsed_time:.1f}s" if elapsed_time else "",
        )

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

        if verb == "MACRO":
            self._handle_macro_command(command)
            self._refresh_status_snapshot(force=True)
            return

        # Phase 5: HitL - Control channel commands for human turns
        if verb == "HUMAN_SUBMIT":
            self._handle_human_submit_command(command)
            self._refresh_status_snapshot(force=True)
            return

        if verb == "HUMAN_SKIP":
            self._handle_human_skip_command(command)
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

        clear_stats = self._get_clear_stats_snapshot()

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
            "clear_stats": clear_stats,
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

    def _handle_key_command(self, command: ControlCommand) -> bool:
        args = list(command.args or [])
        if len(args) < 2:
            self.logger.warning(
                "Control channel: KEY command requires target and at least one key (raw=%s)",
                command.raw,
            )
            self._set_status_error("KEY command requires target and at least one key")
            return False

        target = args[0]
        keys = [key for key in args[1:] if key]
        if not keys:
            self.logger.warning("Control channel: KEY command missing key arguments")
            self._set_status_error("KEY command missing key arguments")
            return False

        targets = self._resolve_targets(target)
        if not targets:
            self.logger.warning("Control channel: KEY command target '%s' not recognized", target)
            self._set_status_error(f"KEY target '{target}' not recognized")
            return False

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
            return False
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
        return True

    def _handle_macro_command(self, command: ControlCommand) -> bool:
        args = list(command.args or [])
        if len(args) < 2:
            self.logger.warning(
                "Control channel: MACRO command requires target and macro name (raw=%s)",
                command.raw,
            )
            self._set_status_error("MACRO command requires target and macro name")
            return False

        target = args[0].strip()
        macro_name = args[1].strip()
        if not target or not macro_name:
            self.logger.warning("Control channel: MACRO command missing target or macro name")
            self._set_status_error("MACRO command missing target or macro name")
            return False

        macro_config_root = get_config().get_section("interactive_macros") or {}
        if not macro_config_root:
            self.logger.warning("Control channel: no interactive_macros configured")
            self._set_status_error("No interactive_macros configured")
            return False

        targets = self._resolve_targets(target)
        if not targets:
            self.logger.warning("Control channel: MACRO target '%s' not recognized", target)
            self._set_status_error(f"MACRO target '{target}' not recognized")
            return False

        failures: List[str] = []
        successes: List[str] = []
        for resolved in targets:
            macro_config = self._find_macro_definition(
                macro_config_root.get(resolved.lower(), {}),
                macro_name,
            )
            if macro_config is None:
                self.logger.warning(
                    "Control channel: macro '%s' not found for agent '%s'",
                    macro_name,
                    resolved,
                )
                failures.append(resolved)
                continue

            dispatched = self._send_macro_to_agent(resolved, macro_name, macro_config)
            if dispatched:
                successes.append(resolved)
            else:
                failures.append(resolved)

        if failures and successes:
            self._set_status_error(f"MACRO dispatched with partial failures: {', '.join(failures)}")
        elif failures:
            self._set_status_error(f"MACRO dispatch failed for: {', '.join(failures)}")
        else:
            self._set_status_error(None)

        return not failures

    @staticmethod
    def _find_macro_definition(agent_macros: Dict[str, Any], macro_name: str) -> Optional[Dict[str, Any]]:
        if not agent_macros or not macro_name:
            return None

        normalized = macro_name.strip().lower()
        if normalized in agent_macros:
            macro_config = agent_macros[normalized]
            return macro_config if isinstance(macro_config, dict) else None

        for name, macro_config in agent_macros.items():
            if name.lower() == normalized and isinstance(macro_config, dict):
                return macro_config

        return None

    def _send_macro_to_agent(
        self,
        agent_name: str,
        macro_name: str,
        macro_config: Dict[str, Any],
    ) -> bool:
        controllers = getattr(self.orchestrator, "controllers", {})
        if not isinstance(controllers, dict):
            self.logger.warning(
                "Control channel: orchestrator controllers unavailable; cannot send macro"
            )
            return False

        controller = controllers.get(agent_name)
        if controller is None:
            self.logger.warning(
                "Control channel: controller '%s' not attached; cannot send macro",
                agent_name,
            )
            return False

        sender = getattr(controller, "send_macro", None)
        if not callable(sender):
            self.logger.warning(
                "Control channel: controller '%s' lacks send_macro; cannot send macro '%s'",
                agent_name,
                macro_name,
            )
            return False

        keys = macro_config.get("keys")
        command_text = macro_config.get("command")
        log_detail = ""
        if keys:
            log_detail = f"keys={keys}"
        elif command_text:
            log_detail = f"command={command_text}"

        try:
            sender(macro_config)
        except Exception as exc:  # noqa: BLE001
            self.logger.error(
                "Control channel: send_macro failed for '%s' (%s): %s",
                agent_name,
                macro_name,
                exc,
            )
            return False

        self.logger.info(
            "Control channel: sent macro '%s' to '%s'%s",
            macro_name,
            agent_name,
            f" ({log_detail})" if log_detail else "",
        )
        self._append_control_history(
            f"[MACRO] agent={agent_name} macro={macro_name} {log_detail}".strip()
        )
        return True

    def _append_control_history(self, line: str) -> None:
        path = os.environ.get("ORCHESTRATOR_CONTROL_HISTORY", "logs/control_channel_history.log")
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(f"{timestamp} | {line}\n")
        except Exception:  # noqa: BLE001
            self.logger.debug("Unable to append to control history at %s", path, exc_info=True)

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

            if interrupt_triggered and ready is not True:
                self.logger.info(
                    "Controller '%s' wait_for_ready interrupted via control channel",
                    controller_name,
                )
                raise TurnCancelledByUser(f"Turn interrupted for {controller_name}")
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

    def _flush_injected_messages(
        self,
        conversation: List[Dict[str, Any]],
        topic: str,
    ) -> None:
        """Drain queued injected messages into the conversation history."""
        while self._injected_messages:
            payload = self._injected_messages.popleft()
            metadata = payload.get("metadata") or {}
            metadata = metadata.copy()
            metadata["injected"] = True
            content = payload.get("content") or ""

            turn_record = {
                "turn": self._turn_counter,
                "speaker": payload.get("role") or "human",
                "topic": topic,
                "prompt": content,
                "dispatch": {"injected": True},
                "response": content,
                "metadata": metadata,
            }

            self._queue_pending_injection(payload)
            conversation.append(turn_record)
            self._turn_counter += 1
            self._store_turn(turn_record)
            self._record_turn_activity(turn_record["speaker"], turn_record)
            self._record_with_context_manager(turn_record)
            self._route_message(turn_record, topic, dispatched=True)

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
        scrubbed = self._conflict_doc_reference_pattern.sub(" ", scrubbed)
        scrubbed = self._conflict_marker_pattern.sub(" ", scrubbed)
        scrubbed = scrubbed.lower()
        return " ".join(scrubbed.split())

    def _extract_conflict_snippet(self, text: str, start: int, end: int, *, max_length: int = 80) -> str:
        """
        Return a trimmed snippet around the matched keyword so logs explain the trigger.
        """
        if not text:
            return ""

        prefix = "…" if start > 0 else ""
        suffix = "…" if end < len(text) else ""
        window_start = max(0, start - 30)
        window_end = min(len(text), end + 30)
        snippet = text[window_start:window_end].strip()
        if len(snippet) > max_length:
            snippet = snippet[: max_length - 1].rstrip() + "…"
            suffix = ""
        return f"{prefix}{snippet}{suffix}"

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

    # Phase 5: HitL - Control channel handlers for human turns
    def _handle_human_submit_command(self, command: ControlCommand) -> None:
        """
        Handle HUMAN_SUBMIT control channel command.

        Format: HUMAN_SUBMIT <response text>

        Submits the human's response for the current pending turn, reusing
        the same logic as the API endpoint.
        """
        if not self._waiting_on_human:
            self.logger.warning("Control channel: HUMAN_SUBMIT ignored - not waiting for human input")
            self._set_status_error("Not currently waiting for human input")
            return

        # Extract response text from args (everything after HUMAN_SUBMIT)
        args = list(command.args or [])
        if not args:
            response_text = ""
        else:
            # Reconstruct full response from args (space-separated tokens)
            response_text = " ".join(args)

        # Validate empty submission if configured
        human_cfg = get_config().get_section("human") or {}
        allow_empty = human_cfg.get("allow_empty_submissions", False)
        if not allow_empty and not response_text.strip():
            self.logger.warning("Control channel: HUMAN_SUBMIT rejected - empty responses not allowed")
            self._set_status_error("Empty responses are not allowed")
            return

        speaker = self._pending_turn_participant
        if not speaker:
            self.logger.error("Control channel: HUMAN_SUBMIT failed - no pending participant")
            self._set_status_error("Human turn state is inconsistent (no pending participant)")
            return

        # Create turn record
        turn_record = {
            "turn": self._turn_counter,
            "speaker": speaker,
            "topic": self.discussion_config.get("discussion_topic") if self.discussion_config else "",
            "prompt": "",
            "response": response_text.strip(),
            "metadata": {
                "human_turn": True,
                "submitted_at": time.time(),
                "via_control_channel": True,
            },
        }

        # Get response marker from config
        response_marker = human_cfg.get("response_marker", "👤")
        turn_record["response_marker"] = response_marker

        # Add to conversation history
        self.history.append(turn_record)
        self._turn_counter += 1

        # Store turn and record activity
        self._store_turn(turn_record)
        self._record_turn_activity(speaker, turn_record)

        # Clear waiting state
        self._waiting_on_human = False
        self._pending_turn_participant = None
        self._human_turn_started_at = None

        self.logger.info(
            "Control channel: HUMAN_SUBMIT processed for '%s' (turn %d, %d chars)",
            speaker,
            turn_record["turn"],
            len(response_text.strip()),
        )
        self._set_status_error(None)

        # Emit WebSocket event
        broadcast_fn = _get_broadcast_function()
        if broadcast_fn:
            broadcast_fn({
                "type": "human_turn_completed",
                "speaker": speaker,
                "turn": turn_record["turn"],
                "response_length": len(response_text.strip()),
                "timestamp": time.time(),
                "via_control_channel": True,
            })

    def _handle_human_skip_command(self, command: ControlCommand) -> None:
        """
        Handle HUMAN_SKIP control channel command.

        Format: HUMAN_SKIP

        Skips the current human turn, reusing the same logic as the API endpoint.
        """
        if not self._waiting_on_human:
            self.logger.warning("Control channel: HUMAN_SKIP ignored - not waiting for human input")
            self._set_status_error("Not currently waiting for human input")
            return

        speaker = self._pending_turn_participant
        if not speaker:
            self.logger.error("Control channel: HUMAN_SKIP failed - no pending participant")
            self._set_status_error("Human turn state is inconsistent (no pending participant)")
            return

        # Record the turn before getting turn number (counter increments inside)
        turn_before = self._turn_counter
        self._record_human_skip(speaker, timeout=False)

        self.logger.info(
            "Control channel: HUMAN_SKIP processed for '%s' (turn %d)",
            speaker,
            turn_before,
        )
        self._set_status_error(None)

        # Emit WebSocket event
        broadcast_fn = _get_broadcast_function()
        if broadcast_fn:
            broadcast_fn({
                "type": "human_turn_skipped",
                "speaker": speaker,
                "turn": turn_before,
                "timestamp": time.time(),
                "via_control_channel": True,
            })


__all__ = ["ConversationManager"]
