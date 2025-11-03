from collections import deque
from types import SimpleNamespace

import pytest

from src.orchestrator.conversation_manager import ConversationManager
from src.orchestrator.control_channel import ControlCommand


class DummyController:
    def __init__(self):
        self.keys = []

    def send_key(self, key):
        allowed = {
            "Escape",
            "Enter",
            "Up",
            "Down",
            "Left",
            "Right",
            "Tab",
            "Space",
            "Spacebar",
        }
        if key not in allowed and not key.startswith("C-"):
            from src.controllers.session_backend import SessionBackendError

            raise SessionBackendError(f"Unsupported key {key}")
        self.keys.append(key)

    def send_keys(self, key):
        self.keys.append(f"seq:{key}")


class DummyOrchestrator:
    def __init__(self):
        self.controllers = {
            "gemini": DummyController(),
            "qwen": DummyController(),
        }
        self.dispatch_calls = []

    def dispatch_command(self, speaker, prompt, *, submit=True):
        self.dispatch_calls.append((speaker, prompt))
        return {"queued": False, "dispatched": True}

    def tick(self):
        return None


class ControlStub:
    def __init__(self, command_batches):
        self._commands = deque(command_batches)

    def check_for_commands(self):
        if not self._commands:
            return []
        batch = self._commands.popleft()
        commands = []
        for item in batch:
            if isinstance(item, ControlCommand):
                commands.append(item)
                continue
            raw = str(item).strip()
            if not raw:
                continue
            tokens = raw.split()
            name = tokens[0].upper()
            args = tokens[1:]
            commands.append(ControlCommand(name=name, args=args, raw=raw))
        return commands


def _fake_parser():
    class Parser:
        def validate_response(self, parsed_output, speaker):
            return SimpleNamespace(
                valid=True,
                response_text="ok",
                issues=[],
                should_retry=False,
                ignored_patterns=[],
                cleaned_output="ok",
            )

    return Parser()


@pytest.fixture
def patched_manager(monkeypatch):
    orchestrator = DummyOrchestrator()
    manager = ConversationManager(orchestrator, ["gemini", "qwen"])

    if getattr(manager, "control_channel", None) is not None:
        try:
            manager.control_channel.cleanup()
        except Exception:  # noqa: BLE001
            pass
    manager.control_channel = None
    manager._control_enabled = False  # noqa: SLF001
    manager._status_file_enabled = False  # noqa: SLF001

    monkeypatch.setattr(
        "src.orchestrator.conversation_manager.OutputParser",
        lambda: _fake_parser(),
    )
    monkeypatch.setattr(
        ConversationManager,
        "_capture_snapshot",
        lambda self, speaker: None,
    )
    monkeypatch.setattr(
        ConversationManager,
        "_read_last_output",
        lambda self, speaker, snapshot: SimpleNamespace(
            response="ok", cleaned_output="ok", prompt="prompt"
        ),
    )
    monkeypatch.setattr(
        ConversationManager,
        "_update_completion_state",
        lambda self, convo: False,
    )
    monkeypatch.setattr(
        ConversationManager,
        "detect_conflict",
        lambda self, convo: (False, None),
    )
    monkeypatch.setattr(
        ConversationManager,
        "detect_consensus",
        lambda self, convo: False,
    )

    return manager, orchestrator


def test_pause_and_resume_toggle_flags(monkeypatch, patched_manager):
    manager, orchestrator = patched_manager

    control_stub = ControlStub([["pause"], ["resume"]])
    manager.control_channel = control_stub
    manager._control_enabled = True  # noqa: SLF001
    manager._current_agent = "gemini"  # noqa: SLF001

    fake_sleep_calls = []

    def fake_sleep(duration):
        fake_sleep_calls.append(duration)

    monkeypatch.setattr("src.orchestrator.conversation_manager.time.sleep", fake_sleep)

    manager._check_control_commands()  # noqa: SLF001
    assert manager.human_control_mode is True
    assert orchestrator.controllers["gemini"].keys == ["Escape"]

    manager._check_control_commands()  # noqa: SLF001
    assert manager.human_control_mode is False
    assert fake_sleep_calls == []


def test_facilitate_discussion_pauses_and_resumes(monkeypatch, patched_manager):
    manager, orchestrator = patched_manager

    command_batches = [
        [],  # initial check before turn 0
        [],  # inner loop before dispatch
        ["pause"],  # before turn 1 begins
        [],  # pause loop first check (stay paused)
        ["resume"],  # pause loop second check (resume)
        [],  # inner loop after resume
    ]
    control_stub = ControlStub(command_batches)
    manager.control_channel = control_stub
    manager._control_enabled = True  # noqa: SLF001

    sleep_calls = []

    def fake_sleep(duration):
        sleep_calls.append(duration)

    monkeypatch.setattr("src.orchestrator.conversation_manager.time.sleep", fake_sleep)

    # Ensure determinism: always alternate gemini -> qwen
    sequence = deque(["gemini", "qwen", None])

    def determine_next_speaker(self, context):
        return sequence.popleft()

    monkeypatch.setattr(ConversationManager, "determine_next_speaker", determine_next_speaker)

    conversation = manager.facilitate_discussion("test-topic", max_turns=2)

    assert len(orchestrator.dispatch_calls) == 2
    assert orchestrator.dispatch_calls[0][0] == "gemini"
    assert orchestrator.dispatch_calls[1][0] == "qwen"
    assert manager.human_control_mode is False
    assert sleep_calls  # pause loop should have slept at least once
    assert len(conversation) == 2


def test_text_command_dispatches_to_single_agent(monkeypatch, patched_manager):
    manager, orchestrator = patched_manager
    manager.human_control_mode = True
    manager._control_enabled = True  # noqa: SLF001

    text_command = ControlCommand(
        name="TEXT",
        args=[],
        raw="TEXT gemini: Please summarize progress",
    )
    manager.control_channel = ControlStub([[text_command]])

    manager._check_control_commands()  # noqa: SLF001

    assert orchestrator.dispatch_calls == [("gemini", "Please summarize progress")]
    assert manager.human_control_mode is True  # remains paused


def test_text_command_all_targets(monkeypatch, patched_manager):
    manager, orchestrator = patched_manager
    manager.human_control_mode = True
    manager._control_enabled = True  # noqa: SLF001

    text_command = ControlCommand(
        name="TEXT",
        args=[],
        raw="TEXT all: Focus on debugging",
    )
    manager.control_channel = ControlStub([[text_command]])

    manager._check_control_commands()  # noqa: SLF001

    assert ("gemini", "Focus on debugging") in orchestrator.dispatch_calls
    assert ("qwen", "Focus on debugging") in orchestrator.dispatch_calls
    assert len(orchestrator.dispatch_calls) == 2


def test_text_command_invalid_target(monkeypatch, patched_manager):
    manager, orchestrator = patched_manager
    manager.human_control_mode = True
    manager._control_enabled = True  # noqa: SLF001

    text_command = ControlCommand(
        name="TEXT",
        args=[],
        raw="TEXT unknown: Hello there",
    )
    manager.control_channel = ControlStub([[text_command]])

    manager._check_control_commands()  # noqa: SLF001

    assert orchestrator.dispatch_calls == []


def test_text_command_preserves_pause_until_resume(monkeypatch, patched_manager):
    manager, orchestrator = patched_manager
    manager.human_control_mode = True
    manager._control_enabled = True  # noqa: SLF001

    command_batches = [
        [
            ControlCommand(
                name="TEXT",
                args=[],
                raw="TEXT gemini: First prompt",
            )
        ],
        ["resume"],
    ]
    manager.control_channel = ControlStub(command_batches)

    manager._check_control_commands()  # TEXT
    assert manager.human_control_mode is True
    assert orchestrator.dispatch_calls == [("gemini", "First prompt")]

    manager._check_control_commands()  # RESUME
    assert manager.human_control_mode is False


def test_text_command_multi_line_prompt(monkeypatch, patched_manager):
    manager, orchestrator = patched_manager
    manager.human_control_mode = True
    manager._control_enabled = True  # noqa: SLF001

    multi_line = "TEXT qwen: Line one\nLine two with \"quotes\" and --special-- chars"
    manager.control_channel = ControlStub([[ControlCommand(name="TEXT", args=[], raw=multi_line)]])

    manager._check_control_commands()  # noqa: SLF001

    assert orchestrator.dispatch_calls == [
        ("qwen", 'Line one\nLine two with "quotes" and --special-- chars')
    ]


def test_key_command_single_agent(monkeypatch, patched_manager):
    manager, orchestrator = patched_manager
    manager.human_control_mode = True
    manager._control_enabled = True  # noqa: SLF001

    manager.control_channel = ControlStub([["KEY gemini Escape Enter"]])
    manager._check_control_commands()  # noqa: SLF001

    assert orchestrator.controllers["gemini"].keys == ["Escape", "Enter"]
    assert orchestrator.controllers["qwen"].keys == []
    assert manager.human_control_mode is True


def test_key_command_multiple_targets(monkeypatch, patched_manager):
    manager, orchestrator = patched_manager
    manager.human_control_mode = True
    manager._control_enabled = True  # noqa: SLF001

    manager.control_channel = ControlStub([["KEY both Up Down"]])
    manager._check_control_commands()  # noqa: SLF001

    assert orchestrator.controllers["gemini"].keys == ["Up", "Down"]
    assert orchestrator.controllers["qwen"].keys == ["Up", "Down"]


def test_key_command_invalid_target(monkeypatch, patched_manager):
    manager, orchestrator = patched_manager
    manager.human_control_mode = True
    manager._control_enabled = True  # noqa: SLF001

    manager.control_channel = ControlStub([["KEY unknown Escape"]])
    manager._check_control_commands()  # noqa: SLF001

    assert orchestrator.controllers["gemini"].keys == []
    assert orchestrator.controllers["qwen"].keys == []


def test_key_command_fallback_send_keys(monkeypatch, patched_manager):
    manager, orchestrator = patched_manager
    manager.human_control_mode = True
    manager._control_enabled = True  # noqa: SLF001

    fallback_controller = SimpleNamespace(keys=[], send_keys=lambda key: fallback_controller.keys.append(key))
    orchestrator.controllers["gemini"] = fallback_controller

    manager.control_channel = ControlStub([["KEY gemini Tab"]])
    manager._check_control_commands()  # noqa: SLF001

    assert fallback_controller.keys == ["Tab"]


def test_key_command_invalid_key_name(monkeypatch, patched_manager):
    manager, orchestrator = patched_manager
    manager.human_control_mode = True
    manager._control_enabled = True  # noqa: SLF001

    manager.control_channel = ControlStub([["KEY gemini INVALIDKEY"]])
    manager._check_control_commands()  # noqa: SLF001

    assert orchestrator.controllers["gemini"].keys == []


def test_key_command_rapid_sequence(monkeypatch, patched_manager):
    manager, orchestrator = patched_manager
    manager.human_control_mode = True
    manager._control_enabled = True  # noqa: SLF001

    manager.control_channel = ControlStub([["KEY gemini Up", "KEY gemini Down", "KEY gemini Enter"]])
    # Simulate control loop polling multiple times
    manager._check_control_commands()  # noqa: SLF001
    manager._check_control_commands()  # noqa: SLF001
    manager._check_control_commands()  # noqa: SLF001

    assert orchestrator.controllers["gemini"].keys == ["Up", "Down", "Enter"]


def test_key_command_pause_flow(monkeypatch, patched_manager):
    manager, orchestrator = patched_manager
    manager.human_control_mode = True
    manager._control_enabled = True  # noqa: SLF001

    control_batches = [
        ["KEY gemini Down", "KEY gemini Down", "KEY gemini Enter"],
        ["resume"],
    ]
    manager.control_channel = ControlStub(control_batches)

    manager._check_control_commands()  # handle keys
    assert orchestrator.controllers["gemini"].keys == ["Down", "Down", "Enter"]
    assert manager.human_control_mode is True

    manager._check_control_commands()  # resume
    assert manager.human_control_mode is False


def test_format_control_status_includes_agents(monkeypatch, patched_manager):
    manager, _ = patched_manager
    manager._status_colorize = False  # noqa: SLF001
    manager._status_progress_width = 10  # noqa: SLF001
    manager._active_max_turns = 10  # noqa: SLF001
    manager._turn_counter = 3  # noqa: SLF001
    manager._run_started_at = 100.0  # noqa: SLF001
    manager._last_activity_at = 195.0  # noqa: SLF001
    manager._current_agent = "qwen"  # noqa: SLF001
    manager._last_completed_agent = "gemini"  # noqa: SLF001
    manager._agent_activity["gemini"]["last_turn"] = 2  # noqa: SLF001
    manager._agent_activity["gemini"]["last_timestamp"] = 190.0  # noqa: SLF001
    manager._agent_activity["qwen"]["last_turn"] = 1  # noqa: SLF001
    manager._agent_activity["qwen"]["last_timestamp"] = 192.0  # noqa: SLF001

    monkeypatch.setattr("src.orchestrator.conversation_manager.time.time", lambda: 200.0)

    status = manager._format_control_status()

    assert "Status: RUNNING  Turn 3/10" in status
    assert "Progress: [" in status
    assert "Active: qwen  Last completed: gemini" in status
    assert "Participants:" in status
    assert "gemini" in status and "RECENT" in status
    assert "qwen" in status and "ACTIVE" in status


def test_format_control_status_reports_errors(monkeypatch, patched_manager):
    manager, _ = patched_manager
    manager._status_colorize = False  # noqa: SLF001
    manager._status_progress_width = 6  # noqa: SLF001
    manager._run_started_at = 0.0  # noqa: SLF001
    manager._last_activity_at = 5.0  # noqa: SLF001
    manager._status_error = "Unknown command 'FOO'"  # noqa: SLF001
    manager.human_control_mode = True

    monkeypatch.setattr("src.orchestrator.conversation_manager.time.time", lambda: 12.0)

    status = manager._format_control_status()

    assert "Status: PAUSED  Turn 0" in status
    assert "Progress: [" in status
    assert "Last error: Unknown command 'FOO'" in status
    assert "Timing: elapsed=00:12  since_activity=00:07" in status
