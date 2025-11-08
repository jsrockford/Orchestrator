#!/usr/bin/env python3
"""
Launch the embedded orchestrator FastAPI server for web UI integration.

This script bootstraps the DevelopmentTeamOrchestrator with the requested
controllers, starts the in-process uvicorn server, and keeps it alive until the
user interrupts (Ctrl+C). The HTTP API exposes control endpoints used by the
React frontend to send pause/resume/key commands and inspect controller status.
"""

from __future__ import annotations

import argparse
import signal
import sys
import threading
from typing import Dict, Iterable

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.controllers import (  # noqa: E402
    ClaudeController,
    CodexController,
    GeminiController,
    QwenController,
)
from src.orchestrator.orchestrator import DevelopmentTeamOrchestrator  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402

logger = get_logger("scripts.run_api_server")

CONTROLLER_FACTORIES = {
    "claude": ClaudeController,
    "codex": CodexController,
    "gemini": GeminiController,
    "qwen": QwenController,
}


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the orchestrator FastAPI server.")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host interface for uvicorn (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="TCP port for uvicorn (default: 8000)",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=sorted(CONTROLLER_FACTORIES.keys()),
        metavar="MODEL",
        help="Subset of controllers to register (default: all)",
    )
    parser.add_argument(
        "--start-sessions",
        action="store_true",
        help="Start tmux sessions immediately after registering controllers.",
    )
    return parser.parse_args(argv)


def build_controllers(model_names: Iterable[str]) -> Dict[str, object]:
    controllers: Dict[str, object] = {}
    for name in model_names:
        factory = CONTROLLER_FACTORIES[name]
        controllers[name] = factory()
        logger.info("Registered %s controller", name)
    return controllers


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)

    orchestrator = DevelopmentTeamOrchestrator()

    if args.start_sessions:
        models = args.models or list(CONTROLLER_FACTORIES.keys())
        controllers = build_controllers(models)
        for name, controller in controllers.items():
            orchestrator.register_controller(name, controller)

        for name, controller in controllers.items():
            start = getattr(controller, "start_session", None)
            if callable(start):
                logger.info("Starting tmux session for %s", name)
                start()
        logger.info(
            "Preloaded %s controller(s) via --start-sessions flag; UI Start Project not required.",
            len(controllers),
        )
    else:
        logger.info(
            "API server starting with no preloaded controllers; use the web UI Start Project button to launch sessions."
        )

    orchestrator.start_api_server(host=args.host, port=args.port)
    logger.info("API server listening on http://%s:%s", args.host, args.port)

    stop_event = threading.Event()

    def handle_signal(signum, frame):  # noqa: ANN001
        logger.info("Received signal %s; shutting down API server.", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        stop_event.wait()
    finally:
        orchestrator.stop_api_server()
        logger.info("API server stopped.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
