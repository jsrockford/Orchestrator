"""Unit tests for the interactive command guard on tmux controllers."""

from __future__ import annotations

from typing import List

from src.controllers.tmux_controller import _InteractiveCommandGuard


class _FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self._value = start

    def __call__(self) -> float:  # pragma: no cover - simple getter
        return self._value

    def advance(self, delta: float) -> None:
        self._value += delta


def _build_guard(clock: _FakeClock, **overrides: object) -> _InteractiveCommandGuard:
    params = {
        "timeout_seconds": 5.0,
        "require_spinner": True,
        "spinner_patterns": ["Figuring out", "⠸"],
        "allow_patterns": [],
        "cooldown_seconds": 2.0,
        "time_provider": clock,
    }
    params.update(overrides)
    return _InteractiveCommandGuard(**params)


def test_guard_interrupts_after_timeout_with_spinner() -> None:
    clock = _FakeClock()
    guard = _build_guard(clock)

    start_lines: List[str] = ["⊷  Shell cd /tmp && python snake_game.py"]
    assert guard.update(start_lines) is None

    clock.advance(3.0)
    assert guard.update(start_lines) is None, "no spinner yet; guard stays idle"

    spinner_lines = ["⠸ Figuring out how to make this more witty..."]
    clock.advance(1.0)
    assert guard.update(spinner_lines) is None

    clock.advance(2.1)
    decision = guard.update(start_lines + spinner_lines)
    assert decision is not None
    assert "shell cd /tmp" in decision.lower()


def test_guard_resets_on_completion() -> None:
    clock = _FakeClock()
    guard = _build_guard(clock)

    start_lines = ["⊷  Shell cd /tmp && python snake_game.py"]
    spinner_lines = ["⠸ Figuring out how to make this more witty..."]
    guard.update(start_lines)
    clock.advance(1.0)
    guard.update(spinner_lines)

    clock.advance(10.0)
    completion = ["✓  Shell cd /tmp && python snake_game.py (R 0.45s)"]
    assert guard.update(completion) is None

    # After completion the guard should not attempt another interrupt.
    clock.advance(10.0)
    assert guard.update(spinner_lines) is None


def test_guard_ignores_allow_listed_commands() -> None:
    clock = _FakeClock()
    guard = _build_guard(clock, allow_patterns=["pytest"])

    pytest_command = ["⊷  Shell cd /tmp && python -m pytest"]
    assert guard.update(pytest_command) is None

    clock.advance(20.0)
    spinner_lines = ["⠸ Figuring out how to make this more witty..."]
    assert guard.update(spinner_lines) is None
