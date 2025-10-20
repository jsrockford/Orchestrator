#!/usr/bin/env python3
"""
Smoke tests for the manual takeover lease/queue logic.
"""

from collections import deque
from typing import Sequence

from src.controllers.tmux_controller import TmuxController


class FakeResult:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeTmuxController(TmuxController):
    """
    Minimal stand-in that skips real tmux interactions so we can exercise the
    automation gating logic deterministically.
    """

    def __init__(self):
        self._fake_clients: Sequence[str] = []
        self.sent_commands = deque()
        super().__init__(
            session_name="fake-session",
            executable="fake-cli",
            working_dir="/tmp"
        )

    # --- overrides ----------------------------------------------------- #

    def _verify_environment(self):
        """Skip environment verification for tests."""
        return

    def session_exists(self) -> bool:
        return True

    def _run_tmux_command(self, args):
        """
        Simulate tmux behavior for send-keys and capture commands.
        """
        if not args:
            return FakeResult(returncode=1, stderr="invalid command")

        cmd = args[0]
        if cmd == "send-keys":
            target = args[2] if len(args) > 2 else ""
            payload = args[3] if len(args) > 3 else ""
            if payload and payload != "Enter":
                self.sent_commands.append(payload)
            return FakeResult()
        if cmd == "capture-pane":
            return FakeResult(stdout="fake output")
        if cmd == "has-session":
            return FakeResult(returncode=0)
        if cmd == "list-clients":
            if self._fake_clients:
                return FakeResult(stdout="\n".join(self._fake_clients))
            return FakeResult(stdout="")
        if cmd == "kill-session":
            return FakeResult(returncode=0)

        return FakeResult()

    def list_clients(self) -> Sequence[str]:
        return list(self._fake_clients)

    # --- helpers ------------------------------------------------------- #

    def set_clients(self, clients):
        self._fake_clients = list(clients)


def main() -> int:
    print("=== Manual Takeover Lease Smoke Test ===")

    controller = FakeTmuxController()
    assert not controller.automation_paused
    assert controller.pending_command_count == 0

    print("1. Sending command with automation active...")
    assert controller.send_command("First command")
    assert list(controller.sent_commands) == ["First command"]

    print("2. Simulating manual client attachment...")
    controller.set_clients(["/dev/pts/1: user"])
    result = controller.send_command("Queued while manual")
    assert result is False, "Command should be queued, not executed"
    assert controller.pending_command_count == 1
    assert list(controller.sent_commands) == ["First command"]
    assert controller.automation_paused
    assert controller.automation_pause_reason == "manual-attach"

    print("3. Manual client detaches; new command should flush queue...")
    controller.set_clients([])
    assert controller.send_command("After manual detach")
    assert controller.pending_command_count == 0
    assert list(controller.sent_commands) == [
        "First command",
        "Queued while manual",
        "After manual detach",
    ]
    assert not controller.automation_paused

    print("=== All manual takeover lease checks passed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
