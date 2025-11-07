"""Tests for the embedded orchestrator FastAPI application."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Dict, List

import pytest
from fastapi import HTTPException, WebSocketDisconnect, status

from src.orchestrator.orchestrator import DevelopmentTeamOrchestrator
from src.orchestrator import web_api
from src.orchestrator.web_api import create_app


class DummyController:
    """Minimal controller stub for API tests."""

    def __init__(self, name: str) -> None:
        self._name = name
        self.paused = False
        self.pause_reason = None
        self.resume_calls = 0
        self.sent_keys: List[str] = []

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

    def pause_automation(self, reason: str = "manual") -> None:
        self.paused = True
        self.pause_reason = reason

    def resume_automation(self, flush_pending: bool = True) -> None:
        self.paused = False
        self.resume_calls += 1

    def send_key(self, key_name: str) -> None:
        self.sent_keys.append(key_name)


class StreamingDummyController(DummyController):
    """Controller stub that exposes deterministic scrollback snapshots."""

    def __init__(self, name: str, snapshots: List[str]) -> None:
        super().__init__(name)
        self._snapshots = snapshots
        self._calls = 0

    def capture_scrollback(self) -> str:  # type: ignore[override]
        index = min(self._calls, len(self._snapshots) - 1)
        snapshot = self._snapshots[index]
        self._calls += 1
        return snapshot


@pytest.fixture()
def orchestrator() -> DevelopmentTeamOrchestrator:
    controllers = {"claude": DummyController("claude")}
    return DevelopmentTeamOrchestrator(controllers=controllers)


@pytest.fixture()
def api_app(
    orchestrator: DevelopmentTeamOrchestrator,
):
    app = create_app(orchestrator)

    def get_endpoint(path: str, method: str) -> Any:
        for route in app.router.routes:
            if getattr(route, "path", None) == path and method in getattr(route, "methods", []):
                return route.endpoint
        raise RuntimeError(f"Endpoint {method} {path} not found")

    return app, get_endpoint


def run(async_fn: Awaitable[Any]) -> Any:
    """Helper to execute async HTTP requests in synchronous tests."""
    return asyncio.run(async_fn)


def test_health_endpoint(api_app) -> None:
    app, get_endpoint = api_app
    health = get_endpoint("/api/health", "GET")
    response = run(health())
    assert response == {"status": "ok"}


def test_pause_endpoint_pauses_controllers(api_app, orchestrator) -> None:
    app, get_endpoint = api_app
    pause = get_endpoint("/api/control/pause", "POST")
    response = run(pause(app.state.orchestrator))
    assert response["status"] == "paused"
    controller = orchestrator.controllers["claude"]
    assert controller.paused is True
    assert controller.pause_reason == "api-request"


def test_resume_endpoint(api_app, orchestrator) -> None:
    app, get_endpoint = api_app
    # first pause to avoid noop
    controller = orchestrator.controllers["claude"]
    controller.paused = True
    resume = get_endpoint("/api/control/resume", "POST")
    response = run(resume(app.state.orchestrator))
    assert response["status"] == "resumed"
    assert controller.paused is False
    assert controller.resume_calls == 1


def test_key_endpoint_validates_model(api_app) -> None:
    app, get_endpoint = api_app
    send_key = get_endpoint("/api/control/{model_name}/key/{key_name}", "POST")
    with pytest.raises(HTTPException) as exc:
        run(send_key("unknown", "Up", app.state.orchestrator))
    assert exc.value.status_code == 404


def test_key_endpoint_sends_command(api_app, orchestrator) -> None:
    app, get_endpoint = api_app
    send_key = get_endpoint("/api/control/{model_name}/key/{key_name}", "POST")
    response = run(send_key("claude", "ArrowUp", app.state.orchestrator))
    assert response["status"] == "sent"
    assert orchestrator.controllers["claude"].sent_keys == ["Up"]


def test_key_endpoint_validates_key(api_app) -> None:
    app, get_endpoint = api_app
    send_key = get_endpoint("/api/control/{model_name}/key/{key_name}", "POST")
    with pytest.raises(HTTPException) as exc:
        run(send_key("claude", "InvalidKey", app.state.orchestrator))
    assert exc.value.status_code == 400


def test_status_endpoint_returns_controller_state(api_app) -> None:
    app, get_endpoint = api_app
    status = get_endpoint("/api/control/status", "GET")
    payload = run(status(app.state.orchestrator))
    assert "controllers" in payload
    assert payload["controllers"]["claude"]["automation"]["paused"] is False
    assert payload["pending"]["claude"] == 0


def test_pause_endpoint_requires_controller_support() -> None:
    class NoPauseController:
        def __init__(self, name: str) -> None:
            self._name = name

        def get_status(self) -> Dict[str, Any]:
            return {"name": self._name}

    orchestrator = DevelopmentTeamOrchestrator(controllers={"claude": NoPauseController("claude")})
    app = create_app(orchestrator)

    def get_endpoint(path: str, method: str) -> Any:
        for route in app.router.routes:
            if getattr(route, "path", None) == path and method in getattr(route, "methods", []):
                return route.endpoint
        raise RuntimeError("not found")

    pause = get_endpoint("/api/control/pause", "POST")
    with pytest.raises(HTTPException) as exc:
        run(pause(app.state.orchestrator))
    assert exc.value.status_code == status.HTTP_501_NOT_IMPLEMENTED


def test_send_key_requires_controller_support() -> None:
    class NoKeyController:
        def __init__(self, name: str) -> None:
            self._name = name

        def get_status(self) -> Dict[str, Any]:
            return {"name": self._name}

    orchestrator = DevelopmentTeamOrchestrator(controllers={"claude": NoKeyController("claude")})
    app = create_app(orchestrator)

    def get_endpoint(path: str, method: str) -> Any:
        for route in app.router.routes:
            if getattr(route, "path", None) == path and method in getattr(route, "methods", []):
                return route.endpoint
        raise RuntimeError("not found")

    send_key = get_endpoint("/api/control/{model_name}/key/{key_name}", "POST")
    with pytest.raises(HTTPException) as exc:
        run(send_key("claude", "Enter", app.state.orchestrator))
    assert exc.value.status_code == status.HTTP_501_NOT_IMPLEMENTED


def test_normalize_scrollback_text_trims_trailing_blank_lines() -> None:
    raw = "line1\nline2\n   \n\n"
    assert web_api.normalize_scrollback_text(raw) == "line1\nline2\n"
    assert web_api.normalize_scrollback_text("   \n\n ") == ""
    assert web_api.normalize_scrollback_text("") == ""


def test_websocket_streams_snapshot_and_append(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshots = ["line1\n\n   \n", "line1\nline2\n   \n\n"]
    controllers = {"claude": StreamingDummyController("claude", snapshots)}
    orchestrator = DevelopmentTeamOrchestrator(controllers=controllers)

    class FakeWebSocket:
        def __init__(self, disconnect_after: int = 2) -> None:
            self.disconnect_after = disconnect_after
            self.messages: List[Dict[str, Any]] = []
            self.accepted = False
            self.closed = False
            self.close_code = None
            self._send_count = 0

        async def accept(self) -> None:
            self.accepted = True

        async def send_json(self, payload: Dict[str, Any]) -> None:
            self._send_count += 1
            self.messages.append(payload)
            if self._send_count >= self.disconnect_after:
                raise WebSocketDisconnect(code=1000)

        async def close(self, code: int = 1000) -> None:
            self.closed = True
            self.close_code = code

    async def immediate_to_thread(func, /, *args, **kwargs):  # noqa: ANN001
        return func(*args, **kwargs)

    monkeypatch.setattr(web_api.asyncio, "to_thread", immediate_to_thread)  # type: ignore[attr-defined]
    monkeypatch.setattr(web_api, "STREAM_POLL_INTERVAL_SECONDS", 0.0)

    fake_ws = FakeWebSocket()

    async def run_stream() -> None:
        try:
            await web_api.stream_controller_output(fake_ws, orchestrator, "claude")
        except WebSocketDisconnect:
            pass

    asyncio.run(run_stream())

    assert fake_ws.accepted is True
    assert len(fake_ws.messages) >= 2
    first, second = fake_ws.messages[0], fake_ws.messages[1]
    assert first["type"] == "snapshot"
    assert first["model"] == "claude"
    assert first["content"] == "line1\n"
    assert second["type"] == "append"
    assert second["model"] == "claude"
    assert second["content"] == "line2\n"
