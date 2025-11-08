"""Manual probe for the WebSocket streaming helper.

Run inside the repository root with the virtual environment activated:

    python tests/manual_ws_stream_probe.py
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import sys
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(level=logging.DEBUG)

from fastapi import WebSocketDisconnect  # noqa: E402

from src.orchestrator.orchestrator import DevelopmentTeamOrchestrator  # noqa: E402
from src.orchestrator import web_api  # noqa: E402


class ProbeController:
    """Controller stub that returns a predictable stream of scrollback snapshots."""

    def __init__(self) -> None:
        self.snapshots = ["line1\n", "line1\nline2\n"]
        self.calls = 0

    def get_status(self):  # noqa: D401
        """Provide minimal status payload used by the API."""
        return {"automation": {"paused": False}}

    def capture_scrollback(self) -> str:  # type: ignore[override]
        index = min(self.calls, len(self.snapshots) - 1)
        value = self.snapshots[index]
        self.calls += 1
        return value


class FakeWebSocket:
    """Minimal WebSocket stub capturing payloads."""

    def __init__(self, disconnect_after: int = 1) -> None:
        self.disconnect_after = disconnect_after
        self.messages = []
        self.accepted = False
        self.closed = False
        self.close_code = None
        self._send_count = 0

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload) -> None:  # noqa: ANN001
        self._send_count += 1
        self.messages.append(payload)
        print(f"[FakeWebSocket] send_json count={self._send_count}", flush=True)
        if self._send_count >= self.disconnect_after:
            print("[FakeWebSocket] raising WebSocketDisconnect", flush=True)
            raise WebSocketDisconnect(code=1000)

    async def close(self, code: int = 1000) -> None:
        self.closed = True
        self.close_code = code


async def async_main() -> None:
    orchestrator = DevelopmentTeamOrchestrator(controllers={"claude": ProbeController()})
    web_api.STREAM_POLL_INTERVAL_SECONDS = 0.05
    web_api.logger.setLevel("DEBUG")

    async def immediate_to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    original_to_thread = web_api.asyncio.to_thread
    web_api.asyncio.to_thread = immediate_to_thread  # type: ignore[attr-defined]

    fake_ws = FakeWebSocket()
    try:
        await web_api.stream_controller_output(fake_ws, orchestrator, "claude")
    finally:
        web_api.asyncio.to_thread = original_to_thread  # type: ignore[attr-defined]

    print("accepted:", fake_ws.accepted, flush=True)
    for idx, payload in enumerate(fake_ws.messages):
        print(f"message[{idx}]: {payload}", flush=True)
    print("closed:", fake_ws.closed, "code:", fake_ws.close_code, flush=True)
    print("async_main complete", flush=True)


def main() -> None:
    asyncio.run(async_main())
    sys.exit(0)


if __name__ == "__main__":
    main()
