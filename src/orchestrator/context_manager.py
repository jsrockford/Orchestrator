"""
Lightweight context manager for orchestrated AI collaborations.

The context manager maintains recent conversation history, decisions, and
observations so higher-level orchestration layers can construct prompts and
summaries without re-implementing bookkeeping logic in every workflow.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Deque, Dict, List, Sequence

from ..utils.logger import get_logger


class ContextManager:
    """
    Track conversation context, decisions, and conflict signals.

    The manager keeps a bounded turn history to minimize memory pressure while
    still offering recent context for prompt construction. Consumers can record
    decisions and query consolidated project state snapshots.
    """

    def __init__(self, *, history_size: int = 200) -> None:
        if history_size < 1:
            raise ValueError("history_size must be positive")

        self.logger = get_logger("orchestrator.context")
        self._history: Deque[Dict[str, Any]] = deque(maxlen=history_size)
        self._decisions: List[Dict[str, Any]] = []
        self._conflicts: List[Dict[str, Any]] = []
        self._consensus_events: List[Dict[str, Any]] = []
        self._project_state: Dict[str, Any] = {}

    # ------------------------------------------------------------------ #
    # Turn and decision management
    # ------------------------------------------------------------------ #

    def record_turn(self, turn: Dict[str, Any]) -> None:
        """Store a sanitized copy of the latest conversation turn."""
        self._history.append(self._sanitize_turn(turn))

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
        """
        return {
            "history": self.history,
            "decisions": self.decisions,
            "conflicts": self.conflicts,
            "consensus": self.consensus_events,
            "state": self._project_state.copy(),
        }

    def update_project_state(self, **state: Any) -> None:
        """Merge keyword updates into the project state payload."""
        self._project_state.update(state)

    # ------------------------------------------------------------------ #
    # Prompt and summary helpers
    # ------------------------------------------------------------------ #

    def build_prompt(self, ai_name: str, task: str, *, include_history: bool = True) -> str:
        """
        Construct a prompt for the requested AI participant.

        Args:
            ai_name: Controller identifier (e.g., "claude").
            task: The current topic or objective.
            include_history: Whether to embed a short context summary.
        """
        lines = [
            f"{ai_name}, we're collaborating on: {task}.",
            "Provide your next contribution focusing on actionable steps.",
        ]

        if include_history:
            blurb = self._format_recent_history()
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

    def _format_recent_history(self, max_turns: int = 3) -> str:
        """Return a compact description of the most recent turns."""
        if not self._history:
            return ""

        recent = list(self._history)[-max_turns:]
        fragments = []
        for turn in recent:
            speaker = turn.get("speaker", "unknown")
            response = turn.get("response")
            if response:
                fragments.append(f"{speaker}: {response}")
            else:
                fragments.append(f"{speaker} queued a prompt")
        return "; ".join(fragments)

    @staticmethod
    def _sanitize_turn(turn: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a shallow copy of the supplied turn.

        The function avoids mutating caller-owned dictionaries and ensures
        metadata dictionaries are shallow-copied as well.
        """
        sanitized = turn.copy()
        metadata = sanitized.get("metadata")
        if isinstance(metadata, dict):
            sanitized["metadata"] = metadata.copy()
        return sanitized


__all__ = ["ContextManager"]
