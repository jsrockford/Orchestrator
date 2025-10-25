#!/usr/bin/env python3
"""
Simple alternating counting smoke test for Claude and Gemini.

Each turn instructs the active AI to respond with the next integer in the
sequence. Keeping the transcript minimal makes it easy to spot desynchronisation.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from src.controllers.tmux_controller import (
    TmuxController,
    SessionBackendError,
    SessionNotFoundError,
)
from src.utils.config_loader import get_config
from src.utils.output_parser import OutputParser


def build_controller(
    *,
    name: str,
    session_name: str,
    executable: str,
    working_dir: Optional[str],
    auto_start: bool,
    startup_timeout: int,
    init_wait: Optional[float],
    kill_existing: bool,
) -> TmuxController:
    config = dict(get_config().get_section(name.lower()) or {})
    config["startup_timeout"] = startup_timeout
    if init_wait is not None:
        config["init_wait"] = init_wait

    parts = executable.split()
    controller = TmuxController(
        session_name=session_name,
        executable=parts[0],
        working_dir=working_dir,
        ai_config=config,
        executable_args=tuple(parts[1:]),
    )

    controller.reset_output_cache()

    if kill_existing and controller.session_exists():
        controller.kill()
        time.sleep(1)

    if controller.session_exists():
        controller.resume_automation(flush_pending=True)
        return controller

    if not auto_start:
        raise SessionNotFoundError(
            f"Session '{session_name}' not found for {name}. Start manually or pass --auto-start."
        )

    controller.start()
    controller.wait_for_ready(timeout=startup_timeout)
    return controller


def parse_args(argv: list[str]) -> argparse.Namespace:
    cfg = get_config()
    tmux_cfg = cfg.get_section("tmux")

    parser = argparse.ArgumentParser(
        description="Minimal alternating counting smoke test for Claude and Gemini."
    )
    parser.add_argument("--count-to", type=int, default=20)
    parser.add_argument("--auto-start", action="store_true")
    parser.add_argument("--kill-existing", action="store_true")
    parser.add_argument("--claude-session", default=tmux_cfg.get("claude_session", "claude"))
    parser.add_argument("--gemini-session", default=tmux_cfg.get("gemini_session", "gemini"))
    parser.add_argument(
        "--claude-executable",
        default="claude --dangerously-skip-permissions",
    )
    parser.add_argument(
        "--gemini-executable",
        default="gemini --yolo",
    )
    parser.add_argument("--claude-startup-timeout", type=int, default=20)
    parser.add_argument("--gemini-startup-timeout", type=int, default=60)
    parser.add_argument("--claude-init-wait", type=float, default=None)
    parser.add_argument("--gemini-init-wait", type=float, default=None)
    parser.add_argument("--claude-cwd", default=None)
    parser.add_argument("--gemini-cwd", default=None)
    parser.add_argument("--log-file", default=None)
    parser.add_argument(
        "--initial-delay",
        type=float,
        default=2.0,
        help="Seconds to wait before the first prompt (default: 2.0).",
    )
    parser.add_argument(
        "--turn-delay",
        type=float,
        default=1.0,
        help="Seconds to wait before each subsequent prompt (default: 1.0).",
    )
    return parser.parse_args(argv)


def capture_scrollback_lines(controller: TmuxController) -> List[str]:
    try:
        snapshot = controller.capture_scrollback()
    except (SessionBackendError, SessionNotFoundError):
        return []
    return snapshot.splitlines()


def compute_delta(previous: List[str], current: List[str], tail_limit: int) -> List[str]:
    if previous and len(current) >= len(previous):
        limit = min(len(previous), len(current))
        prefix = 0
        while prefix < limit and previous[prefix] == current[prefix]:
            prefix += 1
        delta = current[prefix:]
    else:
        delta = current

    if tail_limit and len(delta) > tail_limit:
        delta = delta[-tail_limit:]
    return delta


def send_number(controller: TmuxController, number: int, turn_delay: float) -> str:
    prompt = f"Respond ONLY with the number {number}."
    if turn_delay > 0:
        time.sleep(turn_delay)
    before_lines = capture_scrollback_lines(controller)
    controller.send_command(prompt, submit=True)
    controller.wait_for_ready()
    after_lines = capture_scrollback_lines(controller)
    delta_lines = compute_delta(before_lines, after_lines, tail_limit=120)
    if delta_lines:
        raw_output = "\n".join(delta_lines)
    else:
        raw_output = controller.get_last_output(tail_lines=120) or ""
    parser = OutputParser()
    cleaned = parser.clean_output(raw_output, strip_trailing_prompts=True)
    return cleaned or raw_output


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    transcript_path = Path(args.log_file) if args.log_file else None
    transcript_lines: list[str] = []

    try:
        claude = build_controller(
            name="Claude",
            session_name=args.claude_session,
            executable=args.claude_executable,
            working_dir=args.claude_cwd,
            auto_start=args.auto_start,
            startup_timeout=args.claude_startup_timeout,
            init_wait=args.claude_init_wait,
            kill_existing=args.kill_existing,
        )
        gemini = build_controller(
            name="Gemini",
            session_name=args.gemini_session,
            executable=args.gemini_executable,
            working_dir=args.gemini_cwd,
            auto_start=args.auto_start,
            startup_timeout=args.gemini_startup_timeout,
            init_wait=args.gemini_init_wait,
            kill_existing=args.kill_existing,
        )
    except (SessionBackendError, SessionNotFoundError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    controllers: Dict[str, TmuxController] = {"gemini": gemini, "claude": claude}
    order = ["gemini", "claude"]

    if args.initial_delay > 0:
        print(f"[info] Waiting {args.initial_delay:.1f}s before starting the count...")
        time.sleep(args.initial_delay)

    print("=== Counting Smoke Test ===")
    for number in range(1, args.count_to + 1):
        speaker = order[(number - 1) % len(order)]
        controller = controllers[speaker]
        print(f"[turn {number}] {speaker} → {number}")
        output = send_number(controller, number, args.turn_delay).strip()
        print(f"    output: {output or '(no output)'}")
        transcript_lines.append(f"{number}: {speaker}: {output}")

    if transcript_path:
        transcript_path.write_text("\n".join(transcript_lines), encoding="utf-8")
        print(f"\nTranscript written to {transcript_path}")

    print("=== Done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
