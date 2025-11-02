#!/usr/bin/env python3
"""
Tests for the conversation manager scaffold.
"""

from collections import deque
from typing import Any, Deque, Dict, List, Tuple

from src.orchestrator.conversation_manager import ConversationManager
from src.orchestrator.message_router import MessageRouter
from src.orchestrator.context_manager import ContextManager
from src.orchestrator.orchestrator import DevelopmentTeamOrchestrator
from src.utils.config_loader import reload_config


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
        ["Here's an approach.", "[[PROJECT_COMPLETE]] Consensus: adopt plan A."]
    )
    gemini_controller = FakeConversationalController(
        ["Let's explore plan B to cover edge cases.", "[[PROJECT_COMPLETE]] Confirm plan A handles the edge cases."]
    )

    orchestrator = DevelopmentTeamOrchestrator(
        {"claude": claude_controller, "gemini": gemini_controller}
    )
    manager = ConversationManager(orchestrator, ["claude", "gemini"])

    conversation = manager.facilitate_discussion("Design the API", max_turns=6)

    # Expect alternating turns until both explicit signals arrive.
    assert [turn["speaker"] for turn in conversation] == ["claude", "gemini", "claude", "gemini"]
    assert manager.detect_consensus(conversation) is True
    assert conversation[-1]["metadata"]["consensus"] is True

    # Confirm prompts made it to the controllers.
    assert len(claude_controller.sent) == 2
    assert len(gemini_controller.sent) == 2


def test_hybrid_completion_detection_with_explicit_signal() -> None:
    reload_config()
    claude_controller = FakeConversationalController(
        [
            "Initial proposal for the project.",
            "[[PROJECT_COMPLETE]] All deliverables satisfied.",
        ]
    )
    gemini_controller = FakeConversationalController(
        [
            "Acknowledged. Verifying remaining items.",
            "[[PROJECT_COMPLETE]] Confirming the project is complete.",
        ]
    )

    orchestrator = DevelopmentTeamOrchestrator(
        {"claude": claude_controller, "gemini": gemini_controller}
    )
    manager = ConversationManager(orchestrator, ["claude", "gemini"])

    conversation = manager.facilitate_discussion("Ship the feature", max_turns=6)

    assert len(conversation) == 4
    last_turn = conversation[-1]
    assert last_turn["speaker"] == "gemini"
    assert last_turn["metadata"]["consensus"] is True
    assert "Hybrid completion" in last_turn["metadata"]["consensus_reason"]
    tracking = last_turn["metadata"]["completion_tracking"]
    assert tracking["agreeing_participants"] == ["claude", "gemini"]
    assert tracking["consecutive_ok"] is True
    assert tracking.get("all_explicit_met") is True


def test_completion_reset_on_disagreement_phrase() -> None:
    reload_config()
    claude_controller = FakeConversationalController(
        [
            "[[PROJECT_COMPLETE]] Implementation is ready.",
            "[[PROJECT_COMPLETE]] Final review complete.",
        ]
    )
    gemini_controller = FakeConversationalController(
        [
            "We still need to update the documentation.",
            "[[PROJECT_COMPLETE]] Documentation finished and verified.",
        ]
    )

    orchestrator = DevelopmentTeamOrchestrator(
        {"claude": claude_controller, "gemini": gemini_controller}
    )
    manager = ConversationManager(orchestrator, ["claude", "gemini"])

    conversation = manager.facilitate_discussion("Finalize docs", max_turns=6)

    assert len(conversation) == 4
    reset_turn = conversation[1]
    assert "completion_reset" in reset_turn["metadata"]
    assert reset_turn["metadata"]["completion_tracking"]["agreeing_participants"] == []
    last_turn = conversation[-1]
    assert last_turn["metadata"]["consensus"] is True
    assert last_turn["metadata"]["completion_tracking"]["agreeing_participants"] == ["claude", "gemini"]


def test_completion_requires_explicit_signal_when_configured() -> None:
    reload_config()
    gemini_controller = FakeConversationalController(
        [
            "Coordinating next steps while Qwen wraps up.",
        ]
    )
    qwen_controller = FakeConversationalController(
        [
            "The project is complete and ready for review; handing off deliverables now.",
        ]
    )

    orchestrator = DevelopmentTeamOrchestrator(
        {"gemini": gemini_controller, "qwen": qwen_controller}
    )
    manager = ConversationManager(orchestrator, ["gemini", "qwen"])

    conversation = manager.facilitate_discussion("Finalize delivery", max_turns=2)

    # Consensus should not trigger without explicit [[PROJECT_COMPLETE]] markers.
    assert len(conversation) == 2
    assert all(not turn.get("metadata", {}).get("consensus") for turn in conversation)

    final_turn = conversation[-1]
    metadata = final_turn.get("metadata", {})
    tracking = metadata.get("completion_tracking") or {}
    assert tracking.get("agreeing_participants") == []
    assert tracking.get("all_explicit_met") is False
    # Passive acknowledgment should be marked advisory and ignored for consensus math.
    assert metadata.get("completion_signal") is True
    assert metadata.get("completion_signal_type") == "passive"
    assert metadata.get("completion_signal_advisory") is True
    assert metadata.get("completion_signal_effective") is False
    missing = metadata.get("completion_missing_explicit") or []
    assert set(missing) == {"gemini", "qwen"}


def test_keyword_alignment_does_not_trigger_consensus_when_explicit_required() -> None:
    reload_config()
    gemini_controller = FakeConversationalController(
        [
            "Spec drafted; awaiting implementation.",
            "Code review indicates components remain aligned with the spec; additional changes needed.",
        ]
    )
    qwen_controller = FakeConversationalController(
        [
            "Implementation ready for review; tests executed; all modules aligned with expectations.",
        ]
    )

    orchestrator = DevelopmentTeamOrchestrator(
        {"gemini": gemini_controller, "qwen": qwen_controller}
    )
    manager = ConversationManager(orchestrator, ["gemini", "qwen"])

    conversation = manager.facilitate_discussion("Ship aligned feature", max_turns=3)

    assert len(conversation) == 3
    assert all(not turn.get("metadata", {}).get("consensus") for turn in conversation)
    final_metadata = conversation[-1].get("metadata", {})
    missing = final_metadata.get("completion_missing_explicit") or []
    assert set(missing) == {"gemini", "qwen"}


def test_tool_loop_detection_triggers_warning_after_threshold() -> None:
    reload_config()
    claude_outputs = [
        "\u2713  ReadFolder project/src\nListing complete.",
        "\u2713  ReadFolder project/src\nStill listing.",
        "\u2713  ReadFolder project/src\nReviewing contents.",
        "\u2713  ReadFolder project/src\nNo changes detected.",
    ]
    gemini_outputs = [
        "Acknowledged progress.",
        "Continuing coordination.",
        "Awaiting next update.",
        "Ready for additional guidance.",
    ]

    claude_controller = FakeConversationalController(claude_outputs)
    gemini_controller = FakeConversationalController(gemini_outputs)

    orchestrator = DevelopmentTeamOrchestrator(
        {"claude": claude_controller, "gemini": gemini_controller}
    )
    context_manager = ContextManager(history_size=10)
    manager = ConversationManager(
        orchestrator,
        ["claude", "gemini"],
        context_manager=context_manager,
    )

    conversation = manager.facilitate_discussion("Audit project directory", max_turns=8)

    claude_turns = [turn for turn in conversation if turn["speaker"] == "claude"]
    assert len(claude_turns) == 4
    final_turn = claude_turns[-1]
    metadata = final_turn["metadata"]
    assert metadata["loop_detected"] is True
    loop_details = metadata["loop_detection"]
    assert loop_details["stage"] == "warning"
    assert loop_details["tool"] == "ReadFolder"
    assert loop_details["threshold"] == 4
    assert loop_details["streak"] == 4
    assert loop_details["escalate"] is False
    assert context_manager.loops, "Loop event should be recorded in context manager"
    assert context_manager.loops[-1]["reason"].startswith("ReadFolder")


def test_tool_loop_detection_escalates_on_next_turn() -> None:
    reload_config()
    claude_outputs = [
        "\u2713  ReadFolder project/src\nListing complete.",
        "\u2713  ReadFolder project/src\nStill listing.",
        "\u2713  ReadFolder project/src\nReviewing contents.",
        "\u2713  ReadFolder project/src\nNo changes detected.",
        "\u2713  ReadFolder project/src\nRepeating inspection.",
    ]
    gemini_outputs = [
        "Acknowledged progress.",
        "Continuing coordination.",
        "Awaiting next update.",
        "Ready for additional guidance.",
        "Preparing follow-up.",
    ]

    claude_controller = FakeConversationalController(claude_outputs)
    gemini_controller = FakeConversationalController(gemini_outputs)

    orchestrator = DevelopmentTeamOrchestrator(
        {"claude": claude_controller, "gemini": gemini_controller}
    )
    context_manager = ContextManager(history_size=10)
    manager = ConversationManager(
        orchestrator,
        ["claude", "gemini"],
        context_manager=context_manager,
    )

    conversation = manager.facilitate_discussion("Audit project directory", max_turns=10)

    claude_turns = [turn for turn in conversation if turn["speaker"] == "claude"]
    assert len(claude_turns) == 5
    final_turn = claude_turns[-1]
    metadata = final_turn["metadata"]
    assert metadata["loop_detected"] is True
    loop_details = metadata["loop_detection"]
    assert loop_details["stage"] == "escalation"
    assert loop_details["escalate"] is True
    assert loop_details["streak"] == 5
    assert len(context_manager.loops) >= 2


def test_tool_loop_detection_not_triggered_below_threshold() -> None:
    reload_config()
    claude_outputs = [
        "\u2713  ReadFolder project/src\nListing complete.",
        "\u2713  ReadFolder project/src\nStill listing.",
        "\u2713  ReadFolder project/src\nReviewing contents.",
    ]
    gemini_outputs = [
        "Acknowledged progress.",
        "Continuing coordination.",
        "Awaiting next update.",
    ]

    claude_controller = FakeConversationalController(claude_outputs)
    gemini_controller = FakeConversationalController(gemini_outputs)

    orchestrator = DevelopmentTeamOrchestrator(
        {"claude": claude_controller, "gemini": gemini_controller}
    )
    manager = ConversationManager(orchestrator, ["claude", "gemini"])

    conversation = manager.facilitate_discussion("Audit project directory", max_turns=6)

    for turn in conversation:
        metadata = turn.get("metadata") or {}
        assert "loop_detected" not in metadata


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


def test_detect_conflict_ignores_code_block_keywords() -> None:
    orchestrator = DevelopmentTeamOrchestrator({})
    manager = ConversationManager(orchestrator, ["claude"])

    conversation = [
        {"speaker": "claude", "response": "Initial analysis."},
        {
            "speaker": "gemini",
            "response": "```python\nraise ValueError('Input cannot be empty')\n```",
        },
    ]

    conflict, reason = manager.detect_conflict(conversation)

    assert conflict is False
    assert reason == ""


def test_conversation_manager_records_history_in_context_manager() -> None:
    claude_controller = FakeConversationalController(
        ["Initial thoughts.", "[[PROJECT_COMPLETE]] Consensus reached on plan A."]
    )
    gemini_controller = FakeConversationalController(
        ["Building on that idea.", "[[PROJECT_COMPLETE]] Confirming plan A readiness."]
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

    conversation = manager.facilitate_discussion("Choose the rollout strategy", max_turns=6)

    assert len(conversation) == 4
    assert len(context_manager.history) == 4
    assert context_manager.consensus_events, "Consensus event should be recorded"

    history_responses = [turn.get("response") for turn in context_manager.history]
    assert any("Consensus reached on plan A" in (resp or "") for resp in history_responses)
    assert any("Confirming plan A readiness" in (resp or "") for resp in history_responses)

    prompt = context_manager.build_prompt("gemini", "Provide final summary", include_history=True)
    assert "gemini: Building on that idea." not in prompt

    peer_prompt = context_manager.build_prompt("claude", "Provide final summary", include_history=True)
    assert "gemini: [[PROJECT_COMPLETE]] Confirming plan A readiness." in peer_prompt


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


def test_detect_conflict_matches_stronger_phrases() -> None:
    orchestrator = DevelopmentTeamOrchestrator({})
    manager = ConversationManager(orchestrator, ["claude"])

    conversation = [
        {"speaker": "claude", "response": "Proposal summary."},
        {"speaker": "gemini", "response": "I cannot agree with this direction."},
    ]

    conflict, reason = manager.detect_conflict(conversation)

    assert conflict is True
    assert "cannot agree" in reason


def test_participant_metadata_registered_with_context_manager() -> None:
    class RecordingContext(ContextManager):
        def __init__(self) -> None:
            super().__init__()
            self.registered: Dict[str, Dict[str, Any]] = {}

        def register_participant(self, name: str, metadata: Dict[str, Any] | None = None) -> None:  # type: ignore[override]
            self.registered[name] = metadata or {}
            super().register_participant(name, metadata)

    orchestrator = DevelopmentTeamOrchestrator({})
    context = RecordingContext()
    metadata = {"codex": {"type": "cli", "role": "implementation"}}

    ConversationManager(
        orchestrator,
        ["codex"],
        context_manager=context,
        participant_metadata=metadata,
    )

    assert "codex" in context.registered
    assert context.registered["codex"]["type"] == "cli"
    stored = context.get_participant_metadata("codex")
    assert stored["role"] == "implementation"

def test_context_manager_prompt_includes_role_details() -> None:
    context = ContextManager(
        participant_metadata={"codex": {"type": "cli", "role": "implementation"}}
    )
    prompt = context.build_prompt("codex", "Implement the new endpoint", include_history=True)
    assert "implementation" in prompt.lower()


def test_orchestrator_start_discussion_with_codex_participant() -> None:
    claude_controller = FakeConversationalController(
        ["Initial assessment.", "Alignment reached."]
    )
    gemini_controller = FakeConversationalController(
        ["Architecture notes.", "No blockers identified."]
    )
    codex_controller = FakeConversationalController(
        ["Implementation plan ready.", "Pushing final changes."]
    )

    controllers = {
        "claude": claude_controller,
        "gemini": gemini_controller,
        "codex": codex_controller,
    }
    metadata = {
        "claude": {"type": "cli", "role": "review"},
        "gemini": {"type": "cli", "role": "architecture"},
        "codex": {"type": "cli", "role": "implementation"},
    }

    orchestrator = DevelopmentTeamOrchestrator(controllers, metadata=metadata)
    result = orchestrator.start_discussion("Coordinate handoff", max_turns=3)

    conversation = result["conversation"]
    assert len(conversation) == 3
    assert [turn["speaker"] for turn in conversation] == ["claude", "gemini", "codex"]

    context = result["context_manager"]
    agent_prompt = context.build_prompt("codex", "Follow-up validation", include_history=True)
    assert "implementation" in agent_prompt.lower()


def test_message_router_adds_partner_updates_to_prompt() -> None:
    claude_controller = FakeConversationalController(
        ["Initial proposal.", "[[PROJECT_COMPLETE]] Consensus reached."]
    )
    gemini_controller = FakeConversationalController(
        ["Follow-up analysis.", "[[PROJECT_COMPLETE]] Ready to proceed."]
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

    conversation = manager.facilitate_discussion("Evaluate design trade-offs", max_turns=6)

    assert len(conversation) == 4
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
        ["Draft outline.", "[[PROJECT_COMPLETE]] Consensus achieved."]
    )
    gemini_controller = FakeConversationalController(
        ["Refined analysis.", "[[PROJECT_COMPLETE]] Validated."]
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

    assert len(conversation) == 4
    assert conversation[-1]["metadata"]["consensus"] is True
    assert len(context_manager.history) == 4
    prompt = message_router.prepare_prompt(
        recipient="gemini",
        topic="Plan implementation",
        base_prompt="[Reminder]",
    )
    assert "[Reminder]" in prompt


def test_validation_warnings_do_not_trigger_retry() -> None:
    controller = FakeConversationalController(["Short reply."])
    orchestrator = DevelopmentTeamOrchestrator({"claude": controller})
    manager = ConversationManager(orchestrator, ["claude"])

    conversation = manager.facilitate_discussion("Check warning behavior", max_turns=1)

    assert len(conversation) == 1
    turn = conversation[0]
    assert "validation" in turn
    assert turn["validation"]["valid"] is True
    assert any(issue.startswith("response_too_short") for issue in turn["validation"]["issues"])
    metadata = turn.get("metadata") or {}
    assert "validation_failed" not in metadata
    # Controller should only receive a single command since we accepted the warning.
    assert len(controller.sent) == 1
