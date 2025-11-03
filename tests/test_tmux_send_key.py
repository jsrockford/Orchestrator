import subprocess

import pytest

from src.controllers.tmux_controller import TmuxController
from src.controllers.session_backend import SessionBackendError, SessionNotFoundError
from src.utils.exceptions import TmuxError


def _make_controller(monkeypatch, run_callable, *, session_exists=True):
    monkeypatch.setattr(TmuxController, "_verify_environment", lambda self: None)
    controller = TmuxController("test-session", "python")
    monkeypatch.setattr(controller, "session_exists", lambda: session_exists)

    calls = []

    def fake_run(args):
        calls.append(args)
        return run_callable(args)

    monkeypatch.setattr(controller, "_run_tmux_command", fake_run)
    return controller, calls


def test_send_key_uses_alias(monkeypatch):
    def run_success(args):
        return subprocess.CompletedProcess(args, 0, "", "")

    controller, calls = _make_controller(monkeypatch, run_success)
    controller.send_key("esc")

    assert calls == [["send-keys", "-t", "test-session", "Escape"]]


def test_send_key_invalid_name(monkeypatch):
    def run_success(args):
        return subprocess.CompletedProcess(args, 0, "", "")

    controller, _ = _make_controller(monkeypatch, run_success)

    with pytest.raises(SessionBackendError):
        controller.send_key("INVALID_KEY")


def test_send_key_session_missing(monkeypatch):
    def run_success(args):
        return subprocess.CompletedProcess(args, 0, "", "")

    controller, _ = _make_controller(monkeypatch, run_success, session_exists=False)

    with pytest.raises(SessionNotFoundError):
        controller.send_key("Escape")


def test_send_key_tmux_failure(monkeypatch):
    def run_failure(args):
        return subprocess.CompletedProcess(args, 1, "", "boom")

    controller, _ = _make_controller(monkeypatch, run_failure)

    with pytest.raises(SessionBackendError):
        controller.send_key("Enter")


def test_send_key_tmux_raises(monkeypatch):
    def run_raise(args):
        raise TmuxError("boom")

    controller, _ = _make_controller(monkeypatch, run_raise)

    with pytest.raises(SessionBackendError):
        controller.send_key("Tab")
