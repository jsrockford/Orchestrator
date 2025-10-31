"""
Lightweight context manager for orchestrated AI collaborations.

The context manager maintains recent conversation history, decisions, and
observations so higher-level orchestration layers can construct prompts and
summaries without re-implementing bookkeeping logic in every workflow.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Deque, Dict, List, Optional, Sequence

from ..utils.logger import get_logger


class ContextManager:
    """
    Track conversation context, decisions, and conflict signals.

    The manager keeps a bounded turn history to minimize memory pressure while
    still offering recent context for prompt construction. Consumers can record
    decisions and query consolidated project state snapshots.
    """

    def __init__(
        self,
        *,
        history_size: int = 200,
        participant_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        if history_size < 1:
            raise ValueError("history_size must be positive")

        self.logger = get_logger("orchestrator.context")
        self._history: Deque[Dict[str, Any]] = deque(maxlen=history_size)
        self._decisions: List[Dict[str, Any]] = []
        self._conflicts: List[Dict[str, Any]] = []
        self._consensus_events: List[Dict[str, Any]] = []
        self._project_state: Dict[str, Any] = {}
        self._participants: Dict[str, Dict[str, Any]] = {}
        self._last_turn_by_participant: Dict[str, int] = {}

        if participant_metadata:
            for name, metadata in participant_metadata.items():
                self.register_participant(name, metadata)

    # ------------------------------------------------------------------ #
    # Turn and decision management
    # ------------------------------------------------------------------ #

    def record_turn(self, turn: Dict[str, Any]) -> None:
        """Store a sanitized copy of the latest conversation turn."""
        sanitized = self._sanitize_turn(turn)
        self._history.append(sanitized)

        speaker = sanitized.get("speaker")
        turn_index = sanitized.get("turn")
        if isinstance(speaker, str) and isinstance(turn_index, int):
            self._last_turn_by_participant[speaker] = turn_index

    # Backwards-compatible aliases for other naming conventions
    append_turn = record_turn
    save_turn = record_turn

    def record_conflict(self, turn: Dict[str, Any], reason: str) -> None:
        """Track conflicts for later review or escalation."""
        payload = self._sanitize_turn(turn)
        payload["reason"] = reason
        self._conflicts.append(payload)

    def record_consensus(self, turn: Dict[str, Any]) -> None:
        """Track consensus outcomes so we can summarize decisions later."""
        self._consensus_events.append(self._sanitize_turn(turn))

    def save_decision(self, decision: Dict[str, Any]) -> None:
        """Persist key decisions reached by the team."""
        if not isinstance(decision, dict):
            self.logger.warning("Ignoring non-dict decision payload: %r", decision)
            return

        self._decisions.append(decision.copy())

    # ------------------------------------------------------------------ #
    # Context inspection helpers
    # ------------------------------------------------------------------ #

    @property
    def history(self) -> List[Dict[str, Any]]:
        """Return a snapshot of the stored conversation history."""
        return list(self._history)

    @property
    def decisions(self) -> List[Dict[str, Any]]:
        """Return recorded decisions."""
        return list(self._decisions)

    @property
    def conflicts(self) -> List[Dict[str, Any]]:
        """Return historical conflict events."""
        return list(self._conflicts)

    @property
    def consensus_events(self) -> List[Dict[str, Any]]:
        """Return turns where consensus was detected."""
        return list(self._consensus_events)

    def get_project_context(self) -> Dict[str, Any]:
        """
        Consolidated view of recent history and decisions.

        Returns:
            Dict with keys:
                - history: list of turn dicts
                - decisions: list of decisions
                - conflicts: recorded conflict events
                - consensus: recorded consensus events
                - state: current project state payload
                - participants: participant metadata (if registered)
        """
        return {
            "history": self.history,
            "decisions": self.decisions,
            "conflicts": self.conflicts,
            "consensus": self.consensus_events,
            "state": self._project_state.copy(),
            "participants": self.participants,
        }

    def update_project_state(self, **state: Any) -> None:
        """Merge keyword updates into the project state payload."""
        self._project_state.update(state)

    # ------------------------------------------------------------------ #
    # Prompt and summary helpers
    # ------------------------------------------------------------------ #

    def build_prompt(
        self,
        ai_name: str,
        task: str,
        *,
        include_history: bool = True,
        current_turn: Optional[int] = None,
    ) -> str:
        """
        Construct a prompt for the requested AI participant.

        Args:
            ai_name: Controller identifier (e.g., "claude").
            task: The current topic or objective.
            include_history: Whether to embed a short context summary.
            current_turn: Upcoming turn index for the speaker (unused but accepted for API parity).
        """
        metadata = self._participants.get(ai_name, {})
        participant_type = metadata.get("type", "cli")
        role = metadata.get("role") or metadata.get("persona")
        host = metadata.get("host")
        guidance = metadata.get("guidance")

        if not include_history:
            return (
                f"{ai_name}, respond only with: 'Hello from {ai_name} — message received.'\n"
                "Do not run tools or reference previous steps. Confirm you saw this message and stop."
            )

        if participant_type == "agent":
            host_blurb = f" hosted via {host}" if host else ""
            performer = role or "implementation"
            lines = [
                f"{ai_name}, you're operating as the {performer} agent{host_blurb}.",
                f"Address the topic: {task}. Focus on concrete actions, code, or fixes.",
            ]
        else:
            qualifier = f" ({role})" if role else ""
            lines = [
                f"{ai_name}{qualifier}, we're collaborating on: {task}.",
                "Provide your next contribution focusing on actionable steps.",
            ]

        if guidance:
            lines.append(str(guidance))

        if include_history:
            blurb = self._format_recent_history(speaker=ai_name)
            if blurb:
                lines.append(f"Recent context: {blurb}")

        return "\n".join(lines)

    def summarize_conversation(
        self,
        messages: Sequence[Dict[str, Any]],
        *,
        max_length: int = 400,
    ) -> str:
        """
        Return a truncated summary of the supplied messages.

        The summary favours responses when available, falling back to prompts.
        """
        fragments: List[str] = []
        for turn in messages:
            speaker = turn.get("speaker", "unknown")
            body = turn.get("response") or turn.get("prompt") or ""
            snippet = f"{speaker}: {body}".strip()
            if snippet:
                fragments.append(snippet)

        summary = " | ".join(fragments)
        if len(summary) > max_length:
            return summary[: max_length - 3] + "..."
        return summary

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _format_recent_history(
        self,
        *,
        speaker: Optional[str] = None,
        max_turns: int = 3,
    ) -> str:
        """Return a compact description of the most recent turns."""
        if not self._history:
            return ""

        recent = list(self._history)
        if speaker is not None:
            last_seen = self._last_turn_by_participant.get(speaker, -1)
            filtered: List[Dict[str, Any]] = []
            for turn in recent:
                turn_index = turn.get("turn")
                if isinstance(turn_index, int) and turn_index <= last_seen:
                    continue
                filtered.append(turn)
            recent = filtered

        if max_turns > 0:
            recent = recent[-max_turns:]

        if not recent:
            return ""

        fragments = []
        for turn in recent:
            speaker_name = turn.get("speaker", "unknown")
            response = turn.get("response")
            if response:
                fragments.append(f"{speaker_name}: {response}")
            else:
                fragments.append(f"{speaker_name} queued a prompt")
        return "; ".join(fragments)

    @staticmethod
    def _sanitize_turn(turn: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a shallow copy of the supplied turn.

        The function avoids mutating caller-owned dictionaries and ensures
        metadata dictionaries are shallow-copied as well.
        """
        sanitized = turn.copy()
        sanitized.pop("response_raw", None)

        response = sanitized.get("response")
        if isinstance(response, str):
            sanitized["response"] = response.strip()

        metadata = sanitized.get("metadata")
        if isinstance(metadata, dict):
            sanitized["metadata"] = metadata.copy()
        return sanitized


    # ------------------------------------------------------------------ #
    # Participant metadata helpers
    # ------------------------------------------------------------------ #

    def register_participant(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Register or update metadata for a participant."""
        if not isinstance(name, str) or not name:
            return

        merged: Dict[str, Any] = {"name": name}
        if isinstance(metadata, dict):
            merged.update(metadata)
        merged.setdefault("type", "cli")
        self._participants[name] = merged

    def get_participant_metadata(self, name: str) -> Dict[str, Any]:
        """Return stored metadata for ``name``."""
        payload = self._participants.get(name, {})
        return payload.copy() if isinstance(payload, dict) else {}

    @property
    def participants(self) -> Dict[str, Dict[str, Any]]:
        """Return a copy of registered participant metadata."""
        return {name: meta.copy() for name, meta in self._participants.items()}


__all__ = ["ContextManager"]
