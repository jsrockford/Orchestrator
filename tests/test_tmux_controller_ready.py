import time
import shutil
from typing import List

import pytest

from src.controllers.tmux_controller import TmuxController


def _make_controller(monkeypatch, outputs: List[str]) -> TmuxController:
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/fake")
    monkeypatch.setattr(time, "sleep", lambda _: None)

    config = {
        "response_timeout": 1,
        "ready_check_interval": 0.0,
        "ready_stable_checks": 2,
        "ready_indicators": ["context left"],
        "loading_indicators": ["◦"],
        "response_complete_markers": ["› "],
    }

    controller = TmuxController(
        session_name="test",
        executable="claude",
        ai_config=config,
        executable_args=[],
    )

    controller.session_exists = lambda: True

    sequence = iter(outputs)
    last_value = {"value": ""}

    def fake_capture() -> str:
        try:
            last_value["value"] = next(sequence)
        except StopIteration:
            pass
        return last_value["value"]

    controller.capture_output = fake_capture  # type: ignore[assignment]
    return controller


def test_wait_for_ready_reacts_to_completion(monkeypatch):
    controller = _make_controller(
        monkeypatch,
        [
            "◦ Working for 10s\n",
            "◦ Working for 10s\n",
            "› Write tests for @filename\n98% context left · ? for shortcuts\n",
            "› Write tests for @filename\n98% context left · ? for shortcuts\n",
        ],
    )

    assert controller.wait_for_ready(timeout=0.2, check_interval=0.0)


def test_wait_for_ready_times_out_when_loading_persists(monkeypatch):
    controller = _make_controller(
        monkeypatch,
        [
            "◦ Working for 10s\n",
        ],
    )

    # Ensure the capture continues returning the loading indicator.
    assert controller.wait_for_ready(timeout=0.05, check_interval=0.0) is False


def test_wait_for_ready_ignores_old_marker(monkeypatch):
    controller = _make_controller(
        monkeypatch,
        [
            "› Write tests for @filename\n98% context left · ? for shortcuts\n",
            "◦ Working for 3s\n",
            "◦ Working for 3s\n",
        ],
    )

    assert controller.wait_for_ready(timeout=0.1, check_interval=0.0) is False
