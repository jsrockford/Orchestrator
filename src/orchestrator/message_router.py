"""
Message routing between AI controllers orchestrated via tmux sessions.

The router propagates responses from one participant to the others, ensuring
their next prompts include relevant partner updates. It maintains lightweight
mailboxes per participant with bounded history so routing remains predictable.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Deque, Dict, Iterable, List, Optional, Sequence

from ..utils.logger import get_logger


class MessageRouter:
    """
    Route messages between orchestrated participants.

    Producers call ``deliver`` after each turn to broadcast their response.
    Consumers call ``prepare_prompt`` before speaking to pull pending updates.
    """

    def __init__(
        self,
        participants: Optional[Sequence[str]] = None,
        *,
        max_pending: int = 8,
        context_manager: Any | None = None,
    ) -> None:
        self.logger = get_logger("orchestrator.message_router")
        self.participants: List[str] = list(participants or [])
        self._max_pending = max(1, int(max_pending))
        self._mailboxes: Dict[str, Deque[Dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=self._max_pending)
        )
        self.context_manager = context_manager

        # Pre-create mailboxes for known participants so deliver() can iterate quickly.
        for name in self.participants:
            self._mailboxes[name]  # type: ignore[func-returns-value]

    # ------------------------------------------------------------------ #
    # Participant management
    # ------------------------------------------------------------------ #

    def register_participant(self, name: str) -> None:
        """Ensure a participant has an associated mailbox."""
        if name not in self.participants:
            self.participants.append(name)
        self._mailboxes[name]  # type: ignore[func-returns-value]

    # ------------------------------------------------------------------ #
    # Message routing
    # ------------------------------------------------------------------ #

    def deliver(
        self,
        *,
        sender: str,
        message: str,
        topic: str,
        turn: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Broadcast a message to all other participants.

        Args:
            sender: Name of the controller that produced the message.
            message: Text body to deliver.
            topic: Current discussion topic.
            turn: Absolute turn index captured by the conversation manager.
            metadata: Optional metadata dictionary for downstream consumers.
        """
        if not message:
            self.logger.debug("Skipping empty message delivery from '%s'", sender)
            return

        payload = {
            "sender": sender,
            "message": message,
            "topic": topic,
            "turn": turn,
            "metadata": metadata.copy() if isinstance(metadata, dict) else None,
        }

        targets = self._targets_for_sender(sender)
        for recipient in targets:
            self._mailboxes[recipient].append(payload)
            self.logger.debug(
                "Delivered message from '%s' to '%s' (pending=%d)",
                sender,
                recipient,
                len(self._mailboxes[recipient]),
            )

        if self.context_manager is not None:
            self._record_delivery(payload)

    def prepare_prompt(
        self,
        *,
        recipient: str,
        topic: str,
        base_prompt: str,
        include_history: bool = True,
    ) -> str:
        """
        Construct a prompt for ``recipient`` including routed messages.

        Args:
            recipient: Target controller name.
            topic: Current discussion topic.
            base_prompt: Default prompt constructed by the conversation manager.
            include_history: Whether to include contextual snippets for older messages.
        """
        mailbox = self._mailboxes.get(recipient)
        if not mailbox:
            return base_prompt

        updates: List[str] = []
        while mailbox:
            payload = mailbox.popleft()
            message = payload.get("message", "")
            sender = payload.get("sender", "unknown")
            snippet = self._trim_message(message)
            updates.append(f"{sender} wrote: {snippet}")

        if not updates:
            return base_prompt

        prompt_lines = [base_prompt, "", f"Topic: {topic}", "Recent partner updates:"]
        prompt_lines.extend(f"- {update}" for update in updates)

        if include_history and self.context_manager is not None:
            summary = self._context_summary()
            if summary:
                prompt_lines.extend(["", f"Shared context: {summary}"])

        return "\n".join(prompt_lines)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _targets_for_sender(self, sender: str) -> Iterable[str]:
        if not self.participants:
            # No participants registered; deliver to everyone except sender via mailboxes keys.
            return [name for name in self._mailboxes.keys() if name != sender]

        return [name for name in self.participants if name != sender]

    def _record_delivery(self, payload: Dict[str, Any]) -> None:
        """Forward delivery metadata to the context manager if it exposes a hook."""
        for attr in ("record_delivery", "note_delivery"):
            handler = getattr(self.context_manager, attr, None)
            if callable(handler):
                try:
                    handler(payload)
                except Exception as exc:  # noqa: BLE001
                    self.logger.debug("Context manager delivery hook failed: %s", exc)
                break

    @staticmethod
    def _trim_message(message: str, *, max_length: int = 400) -> str:
        text = message.strip()
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    def _context_summary(self) -> str:
        """Request a shortened summary from the context manager, if available."""
        if self.context_manager is None:
            return ""
        summarizer = getattr(self.context_manager, "summarize_conversation", None)
        history = getattr(self.context_manager, "history", None)
        if callable(summarizer) and isinstance(history, list):
            try:
                return summarizer(history[-3:], max_length=300)
            except Exception as exc:  # noqa: BLE001
                self.logger.debug("Context summary request failed: %s", exc)
        return ""


__all__ = ["MessageRouter"]
