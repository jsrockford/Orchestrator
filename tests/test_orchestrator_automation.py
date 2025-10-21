#!/usr/bin/env python3
"""
Smoke test for DevelopmentTeamOrchestrator automation awareness.
"""

from collections import deque
from typing import Deque, List, Tuple

from src.orchestrator.orchestrator import DevelopmentTeamOrchestrator


class FakeController:
    """
    Minimal controller stub that exposes the orchestrator-facing surface.
    """

    def __init__(self) -> None:
        self.sent: List[Tuple[str, bool]] = []
        self._paused: bool = False
        self._manual_clients: List[str] = []
        self._reason: str | None = None
        self._internal_queue: Deque[Tuple[str, bool]] = deque()
        self.pause_on_send: bool = False

    # --- Controller contract -------------------------------------------------

    def get_status(self):
        return {
            "automation": {
                "paused": self._paused,
                "reason": self._reason,
                "pending_commands": len(self._internal_queue),
                "manual_clients": list(self._manual_clients),
            }
        }

    def send_command(self, command: str, submit: bool = True) -> bool:
        if self.pause_on_send:
            # Simulate a pause being detected while sending
            self.pause_on_send = False
            self._paused = True
            self._reason = "manual-attach"
            self._manual_clients = ["tmux-client"]
            self._internal_queue.append((command, submit))
            return False

        if self._paused:
            # Mirror TmuxController behaviour: queue internally and return False
            self._internal_queue.append((command, submit))
            return False

        self.sent.append((command, submit))
        return True

    # --- Helpers -------------------------------------------------------------

    def set_manual_pause(self, paused: bool, reason: str | None = None, client: str | None = None) -> None:
        self._paused = paused
        self._reason = reason
        self._manual_clients = [client] if paused and client else []
        if not paused:
            self.flush_internal_queue()

    def flush_internal_queue(self) -> None:
        while self._internal_queue and not self._paused:
            command, submit = self._internal_queue.popleft()
            self.sent.append((command, submit))


def main() -> int:
    print("=== Orchestrator Automation Awareness Smoke Test ===")

    controller = FakeController()
    orchestrator = DevelopmentTeamOrchestrator({"claude": controller})

    # Command should dispatch immediately when automation is active
    result = orchestrator.dispatch_command("claude", "Initial command")
    assert result["dispatched"] and not result["queued"]
    assert controller.sent == [("Initial command", True)]
    assert orchestrator.get_pending_command_count("claude") == 0

    # When paused, commands should be queued by the orchestrator
    controller.set_manual_pause(True, reason="manual-attach", client="tmux-client")
    result = orchestrator.dispatch_command("claude", "Queued command 1")
    assert not result["dispatched"] and result["queued"]
    assert result["queue_source"] == "orchestrator"
    assert orchestrator.get_pending_command_count("claude") == 1

    orchestrator.dispatch_command("claude", "Queued command 2")
    assert orchestrator.get_pending_command_count("claude") == 2

    # Automation resumes; orchestrator should flush its queue
    controller.set_manual_pause(False)
    summary = orchestrator.process_pending("claude")
    assert summary["flushed"] == 2
    assert orchestrator.get_pending_command_count("claude") == 0
    assert controller.sent[-2:] == [("Queued command 1", True), ("Queued command 2", True)]

    # Pause occurs during dispatch (controller queues internally)
    controller.pause_on_send = True
    result = orchestrator.dispatch_command("claude", "Controller queued command")
    assert not result["dispatched"] and result["queued"]
    assert result["queue_source"] == "controller"
    assert len(controller.sent) == 3  # no new send recorded yet
    assert len(controller._internal_queue) == 1

    # Automation resumes; controller flushes internally
    controller.set_manual_pause(False)
    assert len(controller.sent) == 4
    assert controller.sent[-1] == ("Controller queued command", True)

    print("=== All orchestrator automation checks passed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
