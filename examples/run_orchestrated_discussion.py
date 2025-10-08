#!/usr/bin/env python3
"""
Kick off a multi-AI discussion using the DevelopmentTeamOrchestrator.

This script expects Claude and Gemini CLI sessions to be available (either
already running inside tmux, or launchable via the configured executables).
It wires the controllers into the orchestrator, runs a short discussion on
the supplied topic, and prints a concise turn-by-turn summary.
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from typing import Dict

from src.controllers.tmux_controller import SessionBackendError, SessionNotFoundError, TmuxController
from src.orchestrator import ContextManager, DevelopmentTeamOrchestrator, MessageRouter


def build_controller(
    *,
    name: str,
    session_name: str,
    executable: str,
    working_dir: str | None,
    auto_start: bool,
    startup_timeout: int,
    init_wait: float | None,
) -> TmuxController:
    ai_config: Dict[str, object] = {"startup_timeout": startup_timeout}
    if init_wait is not None:
        ai_config["init_wait"] = init_wait

    controller = TmuxController(
        session_name=session_name,
        executable=executable,
        working_dir=working_dir,
        ai_config=ai_config,
    )

    controller.reset_output_cache()

    if controller.session_exists():
        controller.resume_automation(flush_pending=True)
        return controller

    if not auto_start:
        raise SessionNotFoundError(
            f"Tmux session '{session_name}' not found for {name}. "
            "Start the CLI manually or pass --auto-start."
        )

    controller.start()
    controller.wait_for_ready()
    return controller


def run_discussion(
    *,
    claude: TmuxController,
    gemini: TmuxController,
    topic: str,
    max_turns: int,
    history_size: int,
) -> Dict[str, object]:
    orchestrator = DevelopmentTeamOrchestrator(
        {"claude": claude, "gemini": gemini}
    )
    context_manager = ContextManager(history_size=history_size)
    router = MessageRouter(["claude", "gemini"], context_manager=context_manager)

    result = orchestrator.start_discussion(
        topic,
        max_turns=max_turns,
        context_manager=context_manager,
        message_router=router,
    )
    return {
        "conversation": result["conversation"],
        "context_manager": context_manager,
        "message_router": router,
    }


def format_turn(turn: Dict[str, object]) -> str:
    speaker = turn.get("speaker", "unknown")
    prompt = (turn.get("prompt") or "").strip()
    response = (turn.get("response") or "").strip()
    metadata = turn.get("metadata") or {}
    status_bits = []
    if metadata.get("queued"):
        status_bits.append("queued")
    if metadata.get("consensus"):
        status_bits.append("consensus")
    if metadata.get("conflict"):
        status_bits.append("conflict")
    status_suffix = f" [{' '.join(status_bits)}]" if status_bits else ""

    prompt_block = textwrap.indent(prompt, "    ")
    response_block = textwrap.indent(response, "    ") if response else "    (no response captured yet)"

    return "\n".join(
        [
            f"{turn.get('turn')}: {speaker}{status_suffix}",
            "  Prompt:",
            prompt_block,
            "  Response:",
            response_block,
        ]
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a coordinated discussion between Claude and Gemini."
    )
    parser.add_argument("topic", help="Topic for the discussion.")
    parser.add_argument(
        "--max-turns",
        type=int,
        default=6,
        help="Maximum number of turns to run (default: 6).",
    )
    parser.add_argument(
        "--history-size",
        type=int,
        default=20,
        help="Number of turns to retain in the shared context (default: 20).",
    )
    parser.add_argument(
        "--auto-start",
        action="store_true",
        help="Launch tmux sessions automatically if they are not running.",
    )
    parser.add_argument(
        "--claude-session",
        default="claude",
        help="Tmux session name for Claude (default: claude).",
    )
    parser.add_argument(
        "--claude-executable",
        default="claude",
        help="Executable used to start Claude (default: claude).",
    )
    parser.add_argument(
        "--claude-startup-timeout",
        type=int,
        default=10,
        help="Seconds to wait for Claude session readiness when auto-starting (default: 10).",
    )
    parser.add_argument(
        "--claude-init-wait",
        type=float,
        default=None,
        help="Seconds to pause after spawning Claude before sending the first input.",
    )
    parser.add_argument(
        "--claude-cwd",
        default=None,
        help="Working directory for the Claude session (defaults to current directory).",
    )
    parser.add_argument(
        "--gemini-session",
        default="gemini",
        help="Tmux session name for Gemini (default: gemini).",
    )
    parser.add_argument(
        "--gemini-executable",
        default="gemini",
        help="Executable used to start Gemini (default: gemini).",
    )
    parser.add_argument(
        "--gemini-startup-timeout",
        type=int,
        default=20,
        help="Seconds to wait for Gemini session readiness when auto-starting (default: 20).",
    )
    parser.add_argument(
        "--gemini-init-wait",
        type=float,
        default=None,
        help="Seconds to pause after spawning Gemini before sending the first input.",
    )
    parser.add_argument(
        "--gemini-cwd",
        default=None,
        help="Working directory for the Gemini session (defaults to current directory).",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    try:
        claude = build_controller(
            name="Claude",
            session_name=args.claude_session,
            executable=args.claude_executable,
            working_dir=args.claude_cwd,
            auto_start=args.auto_start,
            startup_timeout=args.claude_startup_timeout,
            init_wait=args.claude_init_wait,
        )
        gemini = build_controller(
            name="Gemini",
            session_name=args.gemini_session,
            executable=args.gemini_executable,
            working_dir=args.gemini_cwd,
            auto_start=args.auto_start,
            startup_timeout=args.gemini_startup_timeout,
            init_wait=args.gemini_init_wait,
        )
    except (SessionNotFoundError, SessionBackendError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    result = run_discussion(
        claude=claude,
        gemini=gemini,
        topic=args.topic,
        max_turns=args.max_turns,
        history_size=args.history_size,
    )

    conversation = result["conversation"]
    context_manager: ContextManager = result["context_manager"]

    print("\n=== Conversation Transcript ===")
    for turn in conversation:
        print(format_turn(turn))
        print("-")

    print("\n=== Shared Context Summary ===")
    summary = context_manager.summarize_conversation(context_manager.history)
    print(summary or "(no summary available)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
