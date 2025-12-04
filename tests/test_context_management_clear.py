import time
from typing import Any, Dict

import pytest

from src.orchestrator.conversation_manager import ConversationManager
from src.utils.config_loader import reload_config
from tests.test_conversation_manager import FakeConversationalController


class StubOrchestrator:
    def __init__(self, controllers: Dict[str, Any]) -> None:
        self.controllers = controllers
        self.discussion_state = "RUNNING"
        self.should_stop_discussion = False
        self.dispatched = []

    def dispatch_command(self, controller_name: str, command: str, submit: bool = True) -> Dict[str, Any]:
        self.dispatched.append((controller_name, command, submit))
        controller = self.controllers.get(controller_name)
        if controller:
            controller.send_command(command, submit=submit)
        return {"dispatched": True, "queued": False}

    def tick(self) -> Dict[str, Dict[str, Any]]:
        return {}

    def get_controller_status(self, controller_name: str) -> Dict[str, Any]:
        controller = self.controllers.get(controller_name)
        return controller.get_status() if controller else {}


@pytest.fixture(autouse=True)
def _reload_config() -> None:
    reload_config()


def test_clear_signal_dispatches_command_and_injects_prompt() -> None:
    claude_controller = FakeConversationalController(["Ready to clear."])
    orchestrator = StubOrchestrator({"claude": claude_controller})
    manager = ConversationManager(orchestrator, ["claude"])

    result = manager._process_clear_signals(
        speaker="claude",
        response="Need a reset [[CLEAR]] before next task.",
        topic="context-trim",
        source="orchestrated_turn",
        turn_index=0,
    )

    assert result and result["targets"] == ["claude"]
    assert orchestrator.dispatched == [("claude", "/clear", True)]
    # Injection is queued for the cleared agent
    assert len(manager._injected_messages) == 1
    injected = manager._injected_messages[0]
    assert injected["role"] == "claude"
    assert "Context cleared. Re-read PRD.md" in injected["content"]
    assert injected["metadata"].get("targets") == ["claude"]
    stats = manager.get_status_snapshot()["clear_stats"]
    assert stats["per_agent"]["claude"] == 1
    assert stats["total"] == 1


def test_clear_signal_sets_resume_and_unpauses_discussion() -> None:
    claude_controller = FakeConversationalController(["Ready to resume"])
    orchestrator = StubOrchestrator({"claude": claude_controller})
    orchestrator.discussion_state = "PAUSED"
    manager = ConversationManager(orchestrator, ["claude", "gemini"])

    manager._process_clear_signals(
        speaker="claude",
        response="Need a reset [[CLEAR:claude]] before next task.",
        topic="context-trim",
        source="orchestrated_turn",
        turn_index=0,
    )

    assert manager._resume_speaker == "claude"
    assert orchestrator.discussion_state == "RUNNING"
    # Resume target takes precedence over normal round-robin ordering.
    next_speaker = manager.determine_next_speaker([{"speaker": "gemini"}])
    assert next_speaker == "claude"
    assert manager._resume_speaker is None


def test_clear_signal_respects_cooldown() -> None:
    claude_controller = FakeConversationalController(["Cooldown run"])
    orchestrator = StubOrchestrator({"claude": claude_controller})
    manager = ConversationManager(orchestrator, ["claude"])
    manager._clear_last_ts["claude"] = time.time()

    result = manager._process_clear_signals(
        speaker="claude",
        response="[[CLEAR]] hitting cooldown guard",
        topic="cooldown",
        source="orchestrated_turn",
        turn_index=1,
    )

    assert result is not None
    assert not result["targets"]
    assert orchestrator.dispatched == []
    stats = manager.get_status_snapshot()["clear_stats"]
    assert stats["per_agent"].get("claude") is None
    assert stats["total"] == 0


def test_clear_signal_targets_all_participants() -> None:
    claude_controller = FakeConversationalController(["claude cleared"])
    codex_controller = FakeConversationalController(["codex cleared"])
    orchestrator = StubOrchestrator({"claude": claude_controller, "codex": codex_controller})
    manager = ConversationManager(orchestrator, ["claude", "codex"])
    manager._clear_debounce_seconds = 0  # Ensure broadcast is not throttled

    result = manager._process_clear_signals(
        speaker="claude",
        response="Checkpoint reached [[CLEAR:all]]",
        topic="broadcast",
        source="orchestrated_turn",
        turn_index=2,
    )

    assert result and set(result["targets"]) == {"claude", "codex"}
    assert orchestrator.dispatched == [("claude", "/clear", True), ("codex", "/new", True)]
    assert len(manager._injected_messages) == 2
    targets = {payload["metadata"].get("targets")[0] for payload in manager._injected_messages}
    assert targets == {"claude", "codex"}
    stats = manager.get_status_snapshot()["clear_stats"]
    assert stats["per_agent"]["claude"] == 1
    assert stats["per_agent"]["codex"] == 1
    assert stats["total"] == 2
