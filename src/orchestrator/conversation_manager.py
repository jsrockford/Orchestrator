"""
Conversation management layer that sits above the orchestrator.

The conversation manager owns turn-taking logic between controllers, captures
lightweight transcripts, and detects simple consensus/conflict signals so
higher-level workflows can decide when to stop or escalate a dialogue.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Deque, Dict, List, Optional, Sequence, Tuple

from ..utils.logger import get_logger


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
        max_history: int = 200,
    ) -> None:
        if not participants:
            raise ValueError("ConversationManager requires at least one participant")

        self.logger = get_logger("orchestrator.conversation")
        self.orchestrator = orchestrator
        self.participants: List[str] = list(participants)
        self.context_manager = context_manager
        self.message_router = message_router
        self._max_history = max(1, int(max_history))
        self._turn_counter: int = 0
        self.history: Deque[Dict[str, Any]] = deque(maxlen=self._max_history)

        if self.message_router is not None:
            for name in self.participants:
                register = getattr(self.message_router, "register_participant", None)
                if callable(register):
                    try:
                        register(name)
                    except Exception as exc:  # noqa: BLE001
                        self.logger.debug("Message router registration failed for '%s': %s", name, exc)

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
        conversation: List[Dict[str, Any]] = []
        for _ in range(max_turns):
            speaker = self.determine_next_speaker(conversation)
            if speaker is None:
                self.logger.debug("No eligible speaker; stopping discussion on '%s'", topic)
                break

            prompt = self._build_prompt(speaker, topic, conversation)
            dispatch_summary = self.orchestrator.dispatch_command(speaker, prompt)
            response = self._read_last_output(speaker)

            turn_record = {
                "turn": self._turn_counter,
                "speaker": speaker,
                "topic": topic,
                "prompt": prompt,
                "dispatch": dispatch_summary,
                "response": response,
            }
            conversation.append(turn_record)
            self._turn_counter += 1

            self._store_turn(turn_record)

            is_queued = bool(dispatch_summary.get("queued"))
            consensus = self.detect_consensus(conversation)
            conflict, reason = self.detect_conflict(conversation)

            metadata = turn_record.setdefault("metadata", {})
            if is_queued:
                metadata["queued"] = True
            if consensus:
                metadata["consensus"] = True
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
        metadata = latest.get("metadata", {})
        if metadata and metadata.get("consensus"):
            return True

        response = (latest.get("response") or "").lower()
        keywords = ("consensus", "agreement reached", "we agree", "aligned")
        return any(keyword in response for keyword in keywords)

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

        response = (latest.get("response") or "").lower()
        for keyword in ("disagree", "blocker", "conflict", "cannot", "reject"):
            if keyword in response:
                return True, f"Keyword '{keyword}' indicates disagreement"

        stance_latest = self._extract_stance(latest)
        stance_previous = self._extract_stance(previous)
        if stance_latest and stance_previous and stance_latest != stance_previous:
            return True, f"Stance mismatch: {stance_previous!r} vs {stance_latest!r}"

        return False, ""

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
                    return builder(speaker, topic, include_history=True)
                except Exception as exc:  # noqa: BLE001
                    self.logger.warning("Context builder failed for '%s': %s", speaker, exc)

        turn_number = len(conversation)
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
                        include_history=True,
                    )
                except Exception as exc:  # noqa: BLE001
                    self.logger.debug("Message router prompt preparation failed: %s", exc)

        return prompt

    def _read_last_output(self, controller_name: str) -> Optional[str]:
        controller = getattr(self.orchestrator, "controllers", {}).get(controller_name)
        if controller is None:
            return None

        waiter = getattr(controller, "wait_for_ready", None)
        if callable(waiter):
            try:
                waiter()
            except Exception:  # noqa: BLE001
                self.logger.debug(
                    "Controller '%s' wait_for_ready failed",
                    controller_name,
                    exc_info=True,
                )

        reader = getattr(controller, "get_last_output", None)
        if callable(reader):
            try:
                return reader()
            except Exception:  # noqa: BLE001 - avoid breaking the discussion loop
                self.logger.debug("Controller '%s' get_last_output failed", controller_name, exc_info=True)
        return None

    def _store_turn(self, turn: Dict[str, Any]) -> None:
        """Persist the turn in the rolling history buffer."""
        self.history.append(turn)

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

        for attr in callbacks:
            handler = getattr(self.context_manager, attr, None)
            if callable(handler):
                try:
                    if event == "conflict":
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
