"""Tests for the embedded orchestrator FastAPI application."""

from __future__ import annotations

import asyncio
import pathlib
from typing import Any, Awaitable, Dict, List

import pytest
from fastapi import HTTPException

from src.orchestrator.orchestrator import DevelopmentTeamOrchestrator
from src.orchestrator.web_api import create_app, write_fifo_message


class DummyController:
    """Minimal controller stub for API tests."""

    def __init__(self, name: str) -> None:
        self._name = name

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self._name,
            "automation": {
                "paused": False,
                "reason": None,
                "manual_clients": [],
                "pending": 0,
            },
        }


@pytest.fixture()
def orchestrator() -> DevelopmentTeamOrchestrator:
    controllers = {"claude": DummyController("claude")}
    return DevelopmentTeamOrchestrator(controllers=controllers)


@pytest.fixture()
def api_app(
    orchestrator: DevelopmentTeamOrchestrator,
    monkeypatch: pytest.MonkeyPatch,
):
    messages: List[str] = []

    async def fake_write(message: str, **_: Any) -> None:
        messages.append(message)

    monkeypatch.setattr("src.orchestrator.web_api.write_fifo_message", fake_write)
    app = create_app(orchestrator)

    def get_endpoint(path: str, method: str) -> Any:
        for route in app.router.routes:
            if getattr(route, "path", None) == path and method in getattr(route, "methods", []):
                return route.endpoint
        raise RuntimeError(f"Endpoint {method} {path} not found")

    return app, messages, get_endpoint


def run(async_fn: Awaitable[Any]) -> Any:
    """Helper to execute async HTTP requests in synchronous tests."""
    return asyncio.run(async_fn)


def test_health_endpoint(api_app) -> None:
    app, _, get_endpoint = api_app
    health = get_endpoint("/api/health", "GET")
    response = run(health())
    assert response == {"status": "ok"}


def test_pause_endpoint_writes_fifo(api_app) -> None:
    app, messages, get_endpoint = api_app
    pause = get_endpoint("/api/control/pause", "POST")
    response = run(pause(app.state.orchestrator))
    assert response["status"] == "paused"
    assert messages == ["PAUSE"]


def test_resume_endpoint(api_app) -> None:
    app, messages, get_endpoint = api_app
    resume = get_endpoint("/api/control/resume", "POST")
    response = run(resume(app.state.orchestrator))
    assert response["status"] == "resumed"
    assert messages == ["RESUME"]


def test_key_endpoint_validates_model(api_app) -> None:
    app, _, get_endpoint = api_app
    send_key = get_endpoint("/api/control/{model_name}/key/{key_name}", "POST")
    with pytest.raises(HTTPException) as exc:
        run(send_key("unknown", "Up", app.state.orchestrator))
    assert exc.value.status_code == 404


def test_key_endpoint_sends_command(api_app) -> None:
    app, messages, get_endpoint = api_app
    send_key = get_endpoint("/api/control/{model_name}/key/{key_name}", "POST")
    response = run(send_key("claude", "ArrowUp", app.state.orchestrator))
    assert response["status"] == "sent"
    assert messages == ["KEY claude Up"]


def test_key_endpoint_validates_key(api_app) -> None:
    app, _, get_endpoint = api_app
    send_key = get_endpoint("/api/control/{model_name}/key/{key_name}", "POST")
    with pytest.raises(HTTPException) as exc:
        run(send_key("claude", "InvalidKey", app.state.orchestrator))
    assert exc.value.status_code == 400


def test_status_endpoint_returns_controller_state(api_app) -> None:
    app, _, get_endpoint = api_app
    status = get_endpoint("/api/control/status", "GET")
    payload = run(status(app.state.orchestrator))
    assert "controllers" in payload
    assert payload["controllers"]["claude"]["automation"]["paused"] is False
    assert payload["pending"]["claude"] == 0


def test_fifo_failure_propagates(api_app, monkeypatch: pytest.MonkeyPatch) -> None:
    app, _, get_endpoint = api_app

    async def boom(*_: Any, **__: Any) -> None:  # noqa: ANN003, ANN401
        raise HTTPException(status_code=503, detail="fifo down")

    monkeypatch.setattr("src.orchestrator.web_api.write_fifo_message", boom)

    pause = get_endpoint("/api/control/pause", "POST")
    with pytest.raises(HTTPException) as exc:
        run(pause(app.state.orchestrator))
    assert exc.value.status_code == 503


def test_write_fifo_message_appends_history(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    fifo_path = tmp_path / "fifo"
    history_path = tmp_path / "history.log"
    writes: List[str] = []

    class DummyWriter:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def write(self, data: str) -> None:
            writes.append(data)

        def flush(self) -> None:
            return

    original_open = pathlib.Path.open

    def fake_open(self, mode="r", *args, **kwargs):  # noqa: ANN001
        if self == fifo_path:
            return DummyWriter()
        return original_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "open", fake_open)

    asyncio.run(write_fifo_message("PAUSE", fifo_path=fifo_path, history_path=history_path))

    assert writes == ["PAUSE\n"]
    history_contents = history_path.read_text(encoding="utf-8").strip().splitlines()
    assert history_contents
    assert history_contents[-1].endswith("PAUSE")
