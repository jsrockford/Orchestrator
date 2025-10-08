#!/usr/bin/env python3
"""
Integration-flavoured tests for orchestrator-driven conversations with pauses.
"""

from collections import deque
from typing import Deque, Dict, List, Tuple

from src.orchestrator.conversation_manager import ConversationManager
from src.orchestrator.context_manager import ContextManager
from src.orchestrator.message_router import MessageRouter
from src.orchestrator.orchestrator import DevelopmentTeamOrchestrator


class PauseAwareController:
    """
    Test double that mimics TmuxController automation behaviour.

    - Exposes automation pause metadata.
    - Returns False from send_command while paused (forcing orchestrator queueing).
    - Produces deterministic outputs in FIFO order when commands execute.
    """

    def __init__(self, responses: List[str]) -> None:
        self.sent: List[str] = []
        self._responses: Deque[str] = deque(responses)
        self._last_output: str | None = None
        self._paused: bool = False
        self._pause_reason: str | None = None
        self._manual_clients: List[str] = []

    def get_status(self) -> Dict[str, Dict[str, object]]:
        return {
            "automation": {
                "paused": self._paused,
                "reason": self._pause_reason,
                "pending_commands": 0,
                "manual_clients": list(self._manual_clients),
            }
        }

    def send_command(self, command: str, submit: bool = True) -> bool:
        if self._paused:
            return False
        self.sent.append(command)
        self._last_output = self._responses.popleft() if self._responses else ""
        return True

    def get_last_output(self) -> str | None:
        return self._last_output

    def set_paused(
        self,
        paused: bool,
        *,
        reason: str | None = None,
        manual_clients: List[str] | None = None,
    ) -> None:
        self._paused = paused
        self._pause_reason = reason
        self._manual_clients = manual_clients or []


def test_discussion_pause_and_resume_flow() -> None:
    claude_controller = PauseAwareController(
        ["Claude initial proposal.", "Claude acknowledges Gemini."]
    )
    gemini_controller = PauseAwareController(
        ["Gemini flush response after resume.", "Gemini detailed follow-up."]
    )
    gemini_controller.set_paused(True, reason="manual-attach", manual_clients=["tmux-client"])

    orchestrator = DevelopmentTeamOrchestrator(
        {"claude": claude_controller, "gemini": gemini_controller}
    )
    context_manager = ContextManager(history_size=10)
    router = MessageRouter(["claude", "gemini"], context_manager=context_manager)
    manager = ConversationManager(
        orchestrator,
        ["claude", "gemini"],
        context_manager=context_manager,
        message_router=router,
    )

    # Phase 1: Gemini is paused, so her turn should be queued and conversation halts.
    phase_one = manager.facilitate_discussion("Coordinate rollout", max_turns=3)
    assert [turn["speaker"] for turn in phase_one] == ["claude", "gemini"]
    assert phase_one[-1]["metadata"]["queued"] is True
    assert orchestrator.get_pending_command_count("gemini") == 1

    # Resume automation and allow orchestrator to flush the queued command.
    gemini_controller.set_paused(False)
    flush_summary = orchestrator.process_pending("gemini")
    assert flush_summary["flushed"] == 1
    assert orchestrator.get_pending_command_count("gemini") == 0
    assert gemini_controller.get_last_output() == "Gemini flush response after resume."

    # Phase 2: Conversation resumes; Gemini speaks first, then Claude responds using routed context.
    phase_two = manager.facilitate_discussion("Coordinate rollout", max_turns=2)
    assert [turn["speaker"] for turn in phase_two] == ["gemini", "claude"]
    assert phase_two[0]["response"] == "Gemini detailed follow-up."

    # Router should have injected Gemini's follow-up into Claude's prompt.
    assert "Gemini detailed follow-up." in claude_controller.sent[-1]

    # Context manager tracks the full history.
    assert len(context_manager.history) == 4
    assert context_manager.history[-1]["speaker"] == "claude"
