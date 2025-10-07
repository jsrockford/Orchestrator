#!/usr/bin/env python3
"""
Tests for the conversation manager scaffold.
"""

from collections import deque
from typing import Deque, Dict, List

from src.orchestrator.conversation_manager import ConversationManager
from src.orchestrator.context_manager import ContextManager
from src.orchestrator.orchestrator import DevelopmentTeamOrchestrator


class FakeConversationalController:
    """
    Minimal controller surface for conversation tests.

    The controller never pauses automation and exposes ``get_last_output`` so the
    conversation manager can capture responses.
    """

    def __init__(self, outputs: List[str]) -> None:
        self.sent: List[str] = []
        self._outputs: Deque[str] = deque(outputs)
        self._last_output: str | None = None

    # --- Controller contract -------------------------------------------------

    def get_status(self) -> Dict[str, Dict[str, object]]:
        return {
            "automation": {
                "paused": False,
                "reason": None,
                "pending_commands": 0,
                "manual_clients": [],
            }
        }

    def send_command(self, command: str, submit: bool = True) -> bool:
        self.sent.append(command)
        self._last_output = self._outputs.popleft() if self._outputs else ""
        return True

    # --- Helpers -------------------------------------------------------------

    def get_last_output(self) -> str | None:
        return self._last_output


def test_conversation_manager_round_robin_dispatch() -> None:
    claude_controller = FakeConversationalController(
        ["Here's an approach.", "Consensus: adopt plan A."]
    )
    gemini_controller = FakeConversationalController(
        ["Let's explore plan B to cover edge cases."]
    )

    orchestrator = DevelopmentTeamOrchestrator(
        {"claude": claude_controller, "gemini": gemini_controller}
    )
    manager = ConversationManager(orchestrator, ["claude", "gemini"])

    conversation = manager.facilitate_discussion("Design the API", max_turns=4)

    # Expect alternating turns until consensus is declared.
    assert [turn["speaker"] for turn in conversation] == ["claude", "gemini", "claude"]
    assert manager.detect_consensus(conversation) is True
    assert conversation[-1]["metadata"]["consensus"] is True

    # Confirm prompts made it to the controllers.
    assert len(claude_controller.sent) == 2
    assert len(gemini_controller.sent) == 1


def test_detect_conflict_on_disagreement_keyword() -> None:
    orchestrator = DevelopmentTeamOrchestrator({})
    manager = ConversationManager(orchestrator, ["claude"])

    conversation = [
        {"speaker": "claude", "response": "Proposal A looks solid."},
        {"speaker": "gemini", "response": "I disagree with that direction."},
    ]
    conflict, reason = manager.detect_conflict(conversation)

    assert conflict is True
    assert "disagree" in reason


def test_conversation_manager_records_history_in_context_manager() -> None:
    claude_controller = FakeConversationalController(
        ["Initial thoughts.", "Consensus reached on plan A."]
    )
    gemini_controller = FakeConversationalController(
        ["Building on that idea."]
    )

    orchestrator = DevelopmentTeamOrchestrator(
        {"claude": claude_controller, "gemini": gemini_controller}
    )
    context_manager = ContextManager(history_size=5)
    manager = ConversationManager(
        orchestrator,
        ["claude", "gemini"],
        context_manager=context_manager,
    )

    conversation = manager.facilitate_discussion("Choose the rollout strategy", max_turns=5)

    assert len(conversation) == 3
    assert len(context_manager.history) == 3
    assert context_manager.consensus_events, "Consensus event should be recorded"

    prompt = context_manager.build_prompt("gemini", "Provide final summary", include_history=True)
    assert "Recent context" in prompt


def test_conflict_notification_updates_context_manager() -> None:
    claude_controller = FakeConversationalController(
        ["Let's proceed with plan A."]
    )
    gemini_controller = FakeConversationalController(
        ["I disagree; plan A introduces risks."]
    )

    orchestrator = DevelopmentTeamOrchestrator(
        {"claude": claude_controller, "gemini": gemini_controller}
    )
    context_manager = ContextManager(history_size=5)
    manager = ConversationManager(
        orchestrator,
        ["claude", "gemini"],
        context_manager=context_manager,
    )

    conversation = manager.facilitate_discussion("Decide between plans", max_turns=4)

    assert len(conversation) == 2
    assert conversation[-1]["metadata"]["conflict"] is True
    assert context_manager.conflicts, "Conflict should be tracked"
    assert "disagree" in context_manager.conflicts[0]["reason"]
