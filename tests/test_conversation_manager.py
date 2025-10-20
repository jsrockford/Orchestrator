#!/usr/bin/env python3
"""
Tests for the conversation manager scaffold.
"""

from collections import deque
from typing import Deque, Dict, List, Tuple

from src.orchestrator.conversation_manager import ConversationManager
from src.orchestrator.message_router import MessageRouter
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
        self._paused: bool = False
        self._pause_reason: str | None = None
        self._manual_clients: List[str] = []
        self._internal_queue: Deque[Tuple[str, bool]] = deque()

    # --- Controller contract -------------------------------------------------

    def get_status(self) -> Dict[str, Dict[str, object]]:
        return {
            "automation": {
                "paused": self._paused,
                "reason": self._pause_reason,
                "pending_commands": len(self._internal_queue),
                "manual_clients": list(self._manual_clients),
            }
        }

    def send_command(self, command: str, submit: bool = True) -> bool:
        if self._paused:
            self._internal_queue.append((command, submit))
            return False

        self.sent.append(command)
        self._last_output = self._outputs.popleft() if self._outputs else ""
        return True

    # --- Helpers -------------------------------------------------------------

    def get_last_output(self) -> str | None:
        return self._last_output

    def wait_for_ready(self, timeout: float | None = None, check_interval: float | None = None) -> bool:
        return True

    def set_paused(self, paused: bool, *, reason: str | None = None, manual_clients: List[str] | None = None) -> None:
        self._paused = paused
        self._pause_reason = reason
        self._manual_clients = manual_clients or []
        if not paused:
            self._flush_internal_queue()

    def _flush_internal_queue(self) -> None:
        while self._internal_queue:
            command, submit = self._internal_queue.popleft()
            # Emulate normal send behaviour on resume
            self.send_command(command, submit=submit)


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


def test_message_router_adds_partner_updates_to_prompt() -> None:
    claude_controller = FakeConversationalController(
        ["Initial proposal.", "Consensus reached."]
    )
    gemini_controller = FakeConversationalController(
        ["Follow-up analysis."]
    )

    orchestrator = DevelopmentTeamOrchestrator(
        {"claude": claude_controller, "gemini": gemini_controller}
    )
    router = MessageRouter(["claude", "gemini"])
    manager = ConversationManager(
        orchestrator,
        ["claude", "gemini"],
        message_router=router,
    )

    conversation = manager.facilitate_discussion("Evaluate design trade-offs", max_turns=4)

    assert len(conversation) == 3
    assert "Initial proposal." in gemini_controller.sent[0]
    assert "Follow-up analysis." in claude_controller.sent[-1]


def test_message_router_skips_delivery_when_turn_is_queued() -> None:
    claude_controller = FakeConversationalController(
        ["Draft solution."]
    )
    gemini_controller = FakeConversationalController(
        ["Queued response that should not route."]
    )
    # Gemini starts paused to force orchestrator queueing.
    gemini_controller.set_paused(True, reason="manual-attach", manual_clients=["tmux-client"])

    orchestrator = DevelopmentTeamOrchestrator(
        {"claude": claude_controller, "gemini": gemini_controller}
    )
    router = MessageRouter(["claude", "gemini"])
    manager = ConversationManager(
        orchestrator,
        ["claude", "gemini"],
        message_router=router,
    )

    conversation = manager.facilitate_discussion("Queued delivery check", max_turns=3)

    assert len(conversation) == 2
    assert conversation[1]["dispatch"]["queued"] is True
    base_prompt = "[Base]"
    prompt_for_claude = router.prepare_prompt(
        recipient="claude",
        topic="Queued delivery check",
        base_prompt=base_prompt,
    )
    assert prompt_for_claude == base_prompt, "No routed message should reach Claude"


def test_determine_next_speaker_retry_after_queue() -> None:
    claude_controller = FakeConversationalController(["Initial idea."])
    gemini_controller = FakeConversationalController(["Queued response."])
    gemini_controller.set_paused(True, reason="manual-attach")

    orchestrator = DevelopmentTeamOrchestrator(
        {"claude": claude_controller, "gemini": gemini_controller}
    )
    router = MessageRouter(["claude", "gemini"])
    manager = ConversationManager(
        orchestrator,
        ["claude", "gemini"],
        message_router=router,
    )

    conversation = manager.facilitate_discussion("Retry speaker", max_turns=2)

    assert conversation[-1]["metadata"]["queued"] is True
    next_speaker = manager.determine_next_speaker(conversation)
    assert next_speaker == "gemini"


def test_orchestrator_start_discussion_with_router() -> None:
    claude_controller = FakeConversationalController(
        ["Draft outline.", "Consensus achieved."]
    )
    gemini_controller = FakeConversationalController(
        ["Refined analysis."]
    )

    orchestrator = DevelopmentTeamOrchestrator(
        {"claude": claude_controller, "gemini": gemini_controller}
    )

    result = orchestrator.start_discussion(
        "Plan implementation",
        max_turns=4,
    )

    conversation = result["conversation"]
    context_manager = result["context_manager"]
    message_router = result["message_router"]

    assert len(conversation) == 3
    assert conversation[-1]["metadata"]["consensus"] is True
    assert len(context_manager.history) == 3
    prompt = message_router.prepare_prompt(
        recipient="gemini",
        topic="Plan implementation",
        base_prompt="[Reminder]",
    )
    assert "[Reminder]" in prompt
