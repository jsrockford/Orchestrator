"""Tests for the embedded orchestrator FastAPI application."""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

try:
    from fastapi.testclient import TestClient
except (RuntimeError, ModuleNotFoundError):
    TestClient = None  # type: ignore[assignment]

from fastapi import HTTPException

from src.orchestrator.orchestrator import DevelopmentTeamOrchestrator
from src.orchestrator.web_api import create_app

pytestmark = pytest.mark.skipif(
    TestClient is None,
    reason="httpx is required for FastAPI TestClient",
)


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
def api_app(orchestrator: DevelopmentTeamOrchestrator, monkeypatch: pytest.MonkeyPatch):
    messages: List[str] = []

    async def fake_write(message: str, **_: Any) -> None:
        messages.append(message)

    monkeypatch.setattr("src.orchestrator.web_api.write_fifo_message", fake_write)
    app = create_app(orchestrator)
    return app, messages


def test_health_endpoint(api_app) -> None:
    app, _ = api_app
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_pause_endpoint_writes_fifo(api_app) -> None:
    app, messages = api_app
    client = TestClient(app)
    response = client.post("/api/control/pause")
    assert response.status_code == 200
    assert response.json()["status"] == "paused"
    assert messages == ["PAUSE"]


def test_resume_endpoint(api_app) -> None:
    app, messages = api_app
    client = TestClient(app)
    response = client.post("/api/control/resume")
    assert response.status_code == 200
    assert response.json()["status"] == "resumed"
    assert messages == ["RESUME"]


def test_key_endpoint_validates_model(api_app) -> None:
    app, _ = api_app
    client = TestClient(app)
    response = client.post("/api/control/unknown/key/Up")
    assert response.status_code == 404


def test_key_endpoint_sends_command(api_app) -> None:
    app, messages = api_app
    client = TestClient(app)
    response = client.post("/api/control/claude/key/ArrowUp")
    assert response.status_code == 200
    assert messages == ["KEY claude Up"]


def test_key_endpoint_validates_key(api_app) -> None:
    app, _ = api_app
    client = TestClient(app)
    response = client.post("/api/control/claude/key/InvalidKey")
    assert response.status_code == 400


def test_status_endpoint_returns_controller_state(api_app) -> None:
    app, _ = api_app
    client = TestClient(app)
    response = client.get("/api/control/status")
    assert response.status_code == 200
    payload = response.json()
    assert "controllers" in payload
    assert payload["controllers"]["claude"]["automation"]["paused"] is False
    assert payload["pending"]["claude"] == 0


def test_fifo_failure_propagates(api_app, monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = api_app

    async def boom(*_: Any, **__: Any) -> None:  # noqa: ANN003, ANN401
        raise HTTPException(status_code=503, detail="fifo down")

    monkeypatch.setattr("src.orchestrator.web_api.write_fifo_message", boom)

    client = TestClient(app)
    response = client.post("/api/control/pause")
    assert response.status_code == 503
