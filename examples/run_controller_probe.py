#!/usr/bin/env python3
"""
Manual controller probe utility.

Launches a tmux-backed AI controller (Claude, Gemini, or Codex), sends one or
more prompts, and prints both raw and cleaned responses. Intended for manual
testing to determine whether additional controller tweaks are needed (e.g.,
submit key, timing delays, ready indicators).
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Callable, Dict, List, Optional, Type

from src.controllers.claude_controller import ClaudeController
from src.controllers.codex_controller import CodexController
from src.controllers.gemini_controller import GeminiController
from src.utils.output_parser import OutputParser


ControllerFactory = Callable[..., object]


CONTROLLERS: Dict[str, Type] = {
    "claude": ClaudeController,
    "gemini": GeminiController,
    "codex": CodexController,
}


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "prompts",
        nargs="*",
        default=["What is 2 + 2?", "Give a one-sentence project status update."],
        help="Prompts to send in order (defaults to two simple checks).",
    )
    parser.add_argument(
        "--controller",
        choices=CONTROLLERS.keys(),
        required=True,
        help="Controller to exercise.",
    )
    parser.add_argument(
        "--session-name",
        help="Override tmux session name (defaults to controller config).",
    )
    parser.add_argument(
        "--working-dir",
        help="Working directory for the CLI process.",
    )
    parser.add_argument(
        "--no-start",
        action="store_true",
        help="Assume the session is already running; do not call start_session().",
    )
    parser.add_argument(
        "--keep-session",
        action="store_true",
        help="Leave the tmux session running when finished.",
    )
    parser.add_argument(
        "--response-timeout",
        type=float,
        default=None,
        help="Override wait_for_ready timeout (seconds).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="Delay between prompts to allow buffer stabilization (seconds).",
    )
    parser.add_argument(
        "--tail-lines",
        type=int,
        default=120,
        help="Maximum lines to print from the delta capture.",
    )
    return parser.parse_args(argv)


def capture_scrollback_lines(controller: object) -> List[str]:
    capture = getattr(controller, "capture_scrollback", None)
    if callable(capture):
        try:
            return capture().splitlines()
        except Exception:  # noqa: BLE001
            return []
    return []


def compute_delta(previous: List[str], current: List[str], tail_limit: Optional[int]) -> List[str]:
    if previous and len(current) >= len(previous):
        limit = min(len(previous), len(current))
        prefix = 0
        while prefix < limit and previous[prefix] == current[prefix]:
            prefix += 1
        delta = current[prefix:]
    else:
        delta = current

    if tail_limit is not None and len(delta) > tail_limit:
        delta = delta[-tail_limit:]
    return delta


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    controller_cls = CONTROLLERS[args.controller]

    controller = controller_cls(
        session_name=args.session_name,
        working_dir=args.working_dir,
    )

    print(f"[info] Controller: {args.controller}")
    print(f"[info] tmux session: {controller.session_name}")
    print(f"[info] executable: {controller.executable}")
    print("")

    if not args.no_start:
        if controller.session_exists():
            print("[info] Session already running; reusing existing instance.")
        else:
            print("[info] Starting session...")
            controller.start_session()
            time.sleep(1.0)

    controller.reset_output_cache()
    parser = OutputParser()

    for idx, prompt in enumerate(args.prompts, start=1):
        print(f"[turn {idx}] prompt: {prompt}")
        before_lines = capture_scrollback_lines(controller)
        controller.send_command(prompt)
        if controller.wait_for_ready(timeout=args.response_timeout):
            print("  [status] response complete")
        else:
            print("  [status] timeout waiting for response")

        after_lines = capture_scrollback_lines(controller)
        delta_lines = compute_delta(before_lines, after_lines, args.tail_lines)
        if delta_lines:
            raw_delta = "\n".join(delta_lines)
        else:
            getter = getattr(controller, "get_last_output", None)
            raw_delta = getter(tail_lines=args.tail_lines) if callable(getter) else ""
        cleaned = parser.clean_output(raw_delta, strip_trailing_prompts=True)
        print("  [raw delta]")
        print("    " + "\n    ".join(raw_delta.splitlines() or ["<empty>"]))
        print("  [clean]")
        print("    " + "\n    ".join(cleaned.splitlines() or ["<empty>"]))
        print("")

        if idx < len(args.prompts) and args.sleep:
            time.sleep(args.sleep)

    if not args.keep_session:
        print("[info] Killing session (use --keep-session to leave running).")
        try:
            controller.kill_session()
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] Failed to kill session cleanly: {exc}")

    print("[done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
