"""
Development team orchestrator that coordinates multiple AI controllers.

The orchestrator monitors each controller's automation state, defers command
dispatch while a human is attached, and flushes queued work once automation
resumes. This module intentionally keeps the orchestration surface minimal so
additional subsystems (conversation manager, task planner, etc.) can build on
top of a stable contract.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Deque, Dict, Iterable, List, Optional, Sequence, Tuple

from ..utils.logger import get_logger


ControllerType = Any  # Protocol-like duck typing (send_command, get_status)


class DevelopmentTeamOrchestrator:
    """
    Coordinates collaborative workflows across multiple AI controllers.

    The class tracks automation pauses reported by controllers (e.g., when a
    human attaches to a tmux session) and ensures commands are only dispatched
    once the session is safe for automation again.
    """

    def __init__(
        self,
        controllers: Optional[Dict[str, ControllerType]] = None,
    ) -> None:
        """
        Args:
            controllers: Optional mapping of controller name -> controller object.
        """
        self.logger = get_logger("orchestrator.development_team")
        self.controllers: Dict[str, ControllerType] = {}
        self._pending: Dict[str, Deque[Tuple[str, bool]]] = {}
        self._debug_prompts: bool = False
        self._debug_prompt_chars: int = 200

        if controllers:
            for name, controller in controllers.items():
                self.register_controller(name, controller)

    # ------------------------------------------------------------------ #
    # Controller registration & status helpers
    # ------------------------------------------------------------------ #

    def register_controller(self, name: str, controller: ControllerType) -> None:
        """Register (or replace) a controller instance."""
        self.controllers[name] = controller
        self._pending.setdefault(name, deque())
        self.logger.debug("Registered controller '%s'", name)

    def unregister_controller(self, name: str) -> None:
        """Remove a controller from orchestration (noop if unknown)."""
        self.controllers.pop(name, None)
        self._pending.pop(name, None)
        self.logger.debug("Unregistered controller '%s'", name)

    def get_controller_status(self, name: str) -> Dict[str, Any]:
        """Return the latest status dictionary reported by the controller."""
        controller = self._get_controller(name)
        try:
            status = controller.get_status()
            return status if isinstance(status, dict) else {}
        except Exception as exc:  # noqa: BLE001 - propagate minimal info
            self.logger.warning(
                "Failed to fetch status from controller '%s': %s", name, exc
            )
            return {}

    def get_pending_command_count(self, name: Optional[str] = None) -> int:
        """Return the number of queued commands (for one or all controllers)."""
        if name is not None:
            return len(self._pending.get(name, ()))
        return sum(len(queue) for queue in self._pending.values())

    def get_pending_commands(self, name: str) -> List[Tuple[str, bool]]:
        """Return a copy of queued commands for the requested controller."""
        return list(self._pending.get(name, ()))

    # ------------------------------------------------------------------ #
    # Command dispatch / automation awareness
    # ------------------------------------------------------------------ #

    def set_prompt_debug(
        self,
        enabled: bool,
        *,
        preview_chars: int = 200,
    ) -> None:
        """Enable or disable prompt debugging output."""
        self._debug_prompts = enabled
        if preview_chars is not None and preview_chars >= 0:
            self._debug_prompt_chars = int(preview_chars)

    def dispatch_command(
        self,
        controller_name: str,
        command: str,
        *,
        submit: bool = True,
    ) -> Dict[str, Any]:
        """
        Dispatch a command to the requested controller, respecting automation pauses.

        Returns:
            A dictionary describing the result. Keys include:
                - dispatched (bool): True if the controller executed the command.
                - queued (bool): True if the command was queued instead of sent.
                - queue_source (str): "orchestrator", "controller", or None.
                - reason (str|None): Pause reason reported by the controller.
                - manual_clients (list): Attached clients (if reported).
                - pending (int): Commands waiting in the orchestrator queue.
                - controller_pending (int|None): Pending count reported by controller.
        """
        if self._debug_prompts:
            preview_len = self._debug_prompt_chars or 0
            preview = command[:preview_len] if command else ""
            self.logger.info(
                "[prompt-debug] %s len=%d preview=%r",
                controller_name,
                len(command or ""),
                preview,
            )

        controller = self._get_controller(controller_name)
        status = self.get_controller_status(controller_name)
        paused, reason, manual_clients, controller_pending = self._extract_automation(status)

        if paused:
            summary = self._queue_command(
                controller_name,
                command,
                submit,
                reason=reason,
                manual_clients=manual_clients,
                controller_pending=controller_pending,
            )
            summary["queue_source"] = "orchestrator"
            return summary

        result = controller.send_command(command, submit=submit)
        if result:
            return {
                "dispatched": True,
                "queued": False,
                "queue_source": None,
                "reason": reason,
                "manual_clients": manual_clients,
                "pending": len(self._pending.get(controller_name, ())),
                "controller_pending": controller_pending,
            }

        # Command was not dispatched (e.g., automation paused between poll & send)
        status_after = self.get_controller_status(controller_name)
        paused_after, reason_after, manual_after, controller_pending_after = (
            self._extract_automation(status_after)
        )
        if paused_after:
            self.logger.info(
                "Controller '%s' paused during dispatch; relying on controller queue",
                controller_name,
            )
            return {
                "dispatched": False,
                "queued": True,
                "queue_source": "controller",
                "reason": reason_after,
                "manual_clients": manual_after,
                "pending": len(self._pending.get(controller_name, ())),
                "controller_pending": controller_pending_after,
            }

        return {
            "dispatched": False,
            "queued": False,
            "queue_source": None,
            "reason": reason_after,
            "manual_clients": manual_after,
            "pending": len(self._pending.get(controller_name, ())),
            "controller_pending": controller_pending_after,
        }

    # ------------------------------------------------------------------ #
    # Pending queue management
    # ------------------------------------------------------------------ #

    def process_pending(self, controller_name: str) -> Dict[str, Any]:
        """
        Attempt to flush queued commands for the specified controller.

        Returns:
            Dict describing the flush results:
                - flushed (int): Number of orchestrator-queued commands executed.
                - remaining (int): Commands still queued.
                - paused (bool): Whether automation remains paused.
                - reason (str|None): Pause reason, if paused.
        """
        controller = self._get_controller(controller_name)
        queue = self._pending.get(controller_name)
        if not queue:
            return {"flushed": 0, "remaining": 0, "paused": False, "reason": None}

        status = self.get_controller_status(controller_name)
        paused, reason, manual_clients, _ = self._extract_automation(status)

        if paused:
            self.logger.debug(
                "Controller '%s' still paused (%s); skipping flush",
                controller_name,
                reason or "unknown",
            )
            return {
                "flushed": 0,
                "remaining": len(queue),
                "paused": True,
                "reason": reason,
                "manual_clients": manual_clients,
            }

        flushed = 0
        while queue:
            command, submit = queue[0]
            result = controller.send_command(command, submit=submit)
            if not result:
                # Controller paused again or hit an error; stop flushing
                break
            queue.popleft()
            flushed += 1

        return {
            "flushed": flushed,
            "remaining": len(queue),
            "paused": False,
            "reason": None,
        }

    def process_all_pending(self) -> Dict[str, Dict[str, Any]]:
        """Flush queued commands for every controller and return per-controller summaries."""
        return {
            name: self.process_pending(name)
            for name in self.controllers.keys()
        }

    def tick(self) -> Dict[str, Dict[str, Any]]:
        """
        Convenience helper for external loops: process pending commands once.

        Returns the same payload as process_all_pending().
        """
        return self.process_all_pending()

    # ------------------------------------------------------------------ #
    # Higher-level helpers
    # ------------------------------------------------------------------ #

    def start_discussion(
        self,
        topic: str,
        *,
        participants: Optional[Sequence[str]] = None,
        max_turns: int = 10,
        context_manager: Any | None = None,
        message_router: Any | None = None,
        include_history: bool = True,
    ) -> Dict[str, Any]:
        """
        Run a facilitated discussion between registered controllers.

        Args:
            topic: Subject for the conversation.
            participants: Optional ordered list of controller names to include.
                Defaults to all registered controllers.
            max_turns: Maximum number of turns before stopping.
            context_manager: Optional context manager instance. If omitted a new
                ContextManager is created.
            message_router: Optional message router instance. A default router
                is created when not provided.

        Returns:
            Dict containing:
                - conversation: List of turn dictionaries.
                - manager: ConversationManager used for the exchange.
                - context_manager: Context manager instance (created or provided).
                - message_router: Message router instance (created or provided).
        """
        from .conversation_manager import ConversationManager  # local import to avoid cycles
        from .context_manager import ContextManager
        from .message_router import MessageRouter

        participant_list = list(participants or self.controllers.keys())
        if not participant_list:
            raise ValueError("start_discussion requires at least one participant")

        ctx_manager = context_manager or ContextManager()
        msg_router = message_router or MessageRouter(participant_list, context_manager=ctx_manager)

        manager = ConversationManager(
            self,
            participant_list,
            context_manager=ctx_manager,
            message_router=msg_router,
            include_history=include_history,
        )
        conversation = manager.facilitate_discussion(topic, max_turns=max_turns)
        return {
            "conversation": conversation,
            "manager": manager,
            "context_manager": ctx_manager,
            "message_router": msg_router,
        }

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _get_controller(self, name: str) -> ControllerType:
        if name not in self.controllers:
            raise KeyError(f"Unknown controller '{name}'")
        return self.controllers[name]

    def _queue_command(
        self,
        controller_name: str,
        command: str,
        submit: bool,
        *,
        reason: Optional[str],
        manual_clients: Iterable[str],
        controller_pending: Optional[int],
    ) -> Dict[str, Any]:
        queue = self._pending.setdefault(controller_name, deque())
        queue.append((command, submit))
        self.logger.info(
            "Controller '%s' paused (%s); queued command. pending=%d controller_pending=%s",
            controller_name,
            reason or "unknown",
            len(queue),
            controller_pending,
        )
        return {
            "dispatched": False,
            "queued": True,
            "queue_source": "orchestrator",
            "reason": reason,
            "manual_clients": list(manual_clients),
            "pending": len(queue),
            "controller_pending": controller_pending,
        }

    @staticmethod
    def _extract_automation(status: Dict[str, Any]) -> Tuple[bool, Optional[str], List[str], Optional[int]]:
        """Return (paused, reason, manual_clients, controller_pending) tuple."""
        automation = status.get("automation") if isinstance(status, dict) else None
        if not isinstance(automation, dict):
            return False, None, [], None

        paused = bool(automation.get("paused"))
        reason = automation.get("reason")
        manual_clients_raw = automation.get("manual_clients") or []
        manual_clients = list(manual_clients_raw) if isinstance(manual_clients_raw, Iterable) else []
        controller_pending = automation.get("pending_commands")
        if isinstance(controller_pending, bool):
            controller_pending = int(controller_pending)  # guard misuse
        elif not isinstance(controller_pending, int):
            controller_pending = None

        return paused, reason, manual_clients, controller_pending
