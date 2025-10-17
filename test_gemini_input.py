#!/usr/bin/env python3
"""
Focused Gemini CLI input probe.

Launches (or attaches to) the Gemini tmux session, injects a single prompt,
and prints pane snapshots so we can verify whether text and the submit key
are being delivered as expected.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

from src.controllers.gemini_controller import GeminiController
from src.controllers.tmux_controller import (
    SessionBackendError,
    SessionNotFoundError,
)
from src.utils.config_loader import get_config


def capture_tail(controller: GeminiController, max_lines: int) -> str:
    """Return the last ``max_lines`` from the pane for quick inspection."""
    try:
        snapshot = controller.capture_output()
    except (SessionNotFoundError, SessionBackendError):
        return "<capture failed>"
    lines = snapshot.splitlines()
    tail = lines[-max_lines:] if max_lines else lines
    return "\n".join(tail)


def build_controller(session_name: str, working_dir: Optional[str]) -> GeminiController:
    """Create a GeminiController with config defaults."""
    controller = GeminiController(
        session_name=session_name,
        working_dir=working_dir,
    )
    controller.reset_output_cache()
    return controller


def parse_args(argv: list[str]) -> argparse.Namespace:
    cfg = get_config()
    tmux_cfg = cfg.get_section("tmux")
    default_session = tmux_cfg.get("gemini_session", "gemini")
    default_cwd = Path.cwd()

    parser = argparse.ArgumentParser(
        description="Send a single prompt to Gemini and inspect tmux behaviour."
    )
    parser.add_argument(
        "--session",
        default=default_session,
        help=f"Tmux session name for Gemini (default: {default_session}).",
    )
    parser.add_argument(
        "--working-dir",
        default=str(default_cwd),
        help="Working directory for the session (default: current directory).",
    )
    parser.add_argument(
        "--prompt",
        default="Gemini, please confirm you received this test input.",
        help="Prompt text to send to Gemini.",
    )
    parser.add_argument(
        "--auto-start",
        action="store_true",
        help="Launch the Gemini session automatically if it is not running.",
    )
    parser.add_argument(
        "--kill-existing",
        action="store_true",
        help="Kill any existing session with the chosen name before starting.",
    )
    parser.add_argument(
        "--startup-timeout",
        type=int,
        default=20,
        help="Seconds to wait for session startup readiness checks.",
    )
    parser.add_argument(
        "--response-timeout",
        type=int,
        default=60,
        help="Seconds to wait for Gemini to finish responding.",
    )
    parser.add_argument(
        "--wait-before-send",
        type=float,
        default=0.0,
        help="Seconds to sleep after ensuring the session is ready but before sending the prompt (attach window).",
    )
    parser.add_argument(
        "--tail-lines",
        type=int,
        default=40,
        help="Number of pane lines to show for snapshots (default: 40).",
    )
    parser.add_argument(
        "--preview-only",
        action="store_true",
        help="Do not send Enter after injecting text; useful for observing the buffer before submission.",
    )
    parser.add_argument(
        "--skip-wait",
        action="store_true",
        help="Do not call wait_for_ready() after sending the command.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    controller = build_controller(args.session, args.working_dir)
    controller.startup_timeout = args.startup_timeout
    controller.response_timeout = args.response_timeout

    if args.kill_existing and controller.session_exists():
        print(f"[info] Killing existing session '{args.session}'...")
        try:
            controller.kill()
        except SessionBackendError as exc:
            print(f"[error] Failed to kill existing session: {exc}", file=sys.stderr)
            return 1
        time.sleep(1)

    if not controller.session_exists():
        if not args.auto_start:
            print(
                f"[error] Session '{args.session}' not found. "
                "Start it manually or pass --auto-start.",
                file=sys.stderr,
            )
            return 1
        print(f"[info] Starting Gemini session '{args.session}'...")
        try:
            controller.start()
        except SessionBackendError as exc:
            print(f"[error] Failed to start session: {exc}", file=sys.stderr)
            return 1
        if not controller.wait_for_ready(timeout=args.startup_timeout):
            print("[warn] Startup ready check timed out; continuing anyway.")

    controller.resume_automation(flush_pending=True)

    if args.wait_before_send > 0:
        print(
            f"[info] Waiting {args.wait_before_send:.1f}s before sending prompt "
            "so you can attach with 'tmux attach -t {session} -r'."
        )
        time.sleep(args.wait_before_send)

    print("[snapshot] Pane tail BEFORE send:")
    print(capture_tail(controller, args.tail_lines))
    print("-" * 60)

    if args.preview_only:
        print("[action] Injecting text without Enter (preview-only mode).")
        controller.send_text(args.prompt)
        print("[snapshot] Pane tail AFTER text injection:")
        print(capture_tail(controller, args.tail_lines))
        print(
            "[note] Prompt inserted without submitting. Inspect the session and "
            "press Enter manually if desired."
        )
        return 0

    print(f"[action] Sending prompt (length {len(args.prompt)} chars)...")
    sent = controller.send_command(args.prompt)
    print(f"[action] controller.send_command returned {sent}")

    print("[snapshot] Pane tail AFTER send_command:")
    print(capture_tail(controller, args.tail_lines))
    print("-" * 60)

    if not args.skip_wait:
        print("[info] Waiting for Gemini to finish responding...")
        ready = controller.wait_for_ready(timeout=args.response_timeout)
        print(f"[info] wait_for_ready returned {ready}")
    else:
        ready = False

    output = controller.get_last_output(tail_lines=args.tail_lines)
    print("[delta] Output since send_command:")
    print(output or "<no new output captured>")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
