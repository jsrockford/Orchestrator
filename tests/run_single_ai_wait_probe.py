#!/usr/bin/env python3
"""
Single-AI wait_for_ready probe.

Launch or attach to a single AI controller, send a prompt, and rely on the
augmented wait_for_ready() instrumentation to gather detailed readiness logs.
"""

from __future__ import annotations

import argparse
import logging
import shlex
import sys
import time
from typing import Dict, Sequence

from src.controllers.tmux_controller import (
    SessionBackendError,
    SessionNotFoundError,
    TmuxController,
)
from src.utils.config_loader import get_config


AI_CHOICES = ("claude", "gemini", "codex")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Probe a single AI session to collect wait_for_ready() diagnostics. "
            "Runs inside the active tmux worktree."
        )
    )
    parser.add_argument(
        "--ai",
        choices=AI_CHOICES,
        required=True,
        help="Which AI controller to exercise.",
    )
    parser.add_argument(
        "--prompt",
        default="Summarize the current status of the output end-marker investigation.",
        help="Prompt to send to the AI once the session is ready.",
    )
    parser.add_argument(
        "--session",
        help="Override tmux session name (defaults to config tmux.<ai>_session).",
    )
    parser.add_argument(
        "--working-dir",
        help="Working directory for the AI process (defaults to controller behaviour).",
    )
    parser.add_argument(
        "--auto-start",
        action="store_true",
        help="Launch the tmux session automatically if it is not already running.",
    )
    parser.add_argument(
        "--kill-existing",
        action="store_true",
        help="Kill any existing tmux session before starting a fresh instance.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        help=(
            "Override response timeout (seconds) used for wait_for_ready() "
            "(defaults to the value in config.yaml; Claude now uses 500s)."
        ),
    )
    parser.add_argument(
        "--check-interval",
        type=float,
        help="Override ready check interval (seconds).",
    )
    parser.add_argument(
        "--tail-lines",
        type=int,
        default=60,
        help="Number of trailing lines to print from the pane after completion.",
    )
    parser.add_argument(
        "--bootstrap",
        help="Shell command to run before launching the executable (safe worktree activation).",
    )
    parser.add_argument(
        "--enable-debug-wait",
        action="store_true",
        help="Force debug_wait_logging on for this run (overrides config setting).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only validate setup; do not send the prompt.",
    )
    return parser.parse_args(argv)


def build_controller(
    *,
    ai: str,
    session_name: str,
    working_dir: str | None,
    auto_start: bool,
    kill_existing: bool,
    bootstrap: str | None,
    enable_debug_wait: bool,
) -> TmuxController:
    config_loader = get_config()
    ai_section: Dict[str, object] = dict(config_loader.get_section(ai))
    if not ai_section:
        raise ValueError(f"No configuration section found for '{ai}'.")

    executable_value = ai_section.pop("executable", ai)
    exec_args_value = ai_section.pop("executable_args", [])
    if isinstance(exec_args_value, str):
        exec_args_value = shlex.split(exec_args_value)
    launch_executable = executable_value
    launch_args = list(exec_args_value)
    if enable_debug_wait:
        ai_section["debug_wait_logging"] = True

    if bootstrap:
        quoted_executable = shlex.quote(executable_value)
        quoted_args = " ".join(shlex.quote(arg) for arg in exec_args_value)
        command_tail = f"{quoted_executable} {quoted_args}".strip()
        shell_command = f"{bootstrap} && {command_tail}" if command_tail else f"{bootstrap} && {quoted_executable}"
        launch_executable = "bash"
        launch_args = ["-lc", shell_command]

    controller = TmuxController(
        session_name=session_name,
        executable=launch_executable,
        working_dir=working_dir,
        ai_config=ai_section,
        executable_args=launch_args,
    )
    controller.reset_output_cache()

    exists = controller.session_exists()
    if exists and kill_existing:
        if not controller.kill_session():
            raise SessionBackendError(f"Failed to kill existing session '{session_name}'.")
        exists = False

    if not exists:
        if not auto_start:
            raise SessionNotFoundError(
                f"Session '{session_name}' not found for {ai}. "
                "Start it manually or pass --auto-start."
            )
        controller.start()
        controller.reset_output_cache()
    else:
        controller.resume_automation(flush_pending=True)

    return controller


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    config_loader = get_config()
    tmux_section = config_loader.get_section("tmux")
    default_session = tmux_section.get(f"{args.ai}_session", args.ai)
    session_name = args.session or default_session

    try:
        controller = build_controller(
            ai=args.ai,
            session_name=session_name,
            working_dir=args.working_dir,
            auto_start=args.auto_start,
            kill_existing=args.kill_existing,
            bootstrap=args.bootstrap,
            enable_debug_wait=args.enable_debug_wait,
        )
    except (ValueError, SessionBackendError, SessionNotFoundError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    timeout = args.timeout or float(controller.config.get("response_timeout", 60.0))
    check_interval = args.check_interval or float(controller.config.get("ready_check_interval", 0.5))

    print(f"[INFO] Using wait_for_ready timeout: {timeout:.1f}s (interval {check_interval:.2f}s)")

    if args.dry_run:
        print(
            f"[DRY-RUN] Controller initialised for {args.ai} in session '{session_name}'. "
            "Skipping command dispatch."
        )
        return 0

    prompt = args.prompt.strip()
    if not prompt:
        print("[ERROR] Prompt is empty after stripping whitespace.", file=sys.stderr)
        return 1

    print(f"[INFO] Sending prompt to {args.ai} (session '{session_name}').")
    controller.reset_output_cache()
    start = time.time()
    try:
        controller.send_command(prompt, submit=True)
    except SessionBackendError as exc:
        print(f"[ERROR] Failed to send command: {exc}", file=sys.stderr)
        return 1

    ready = controller.wait_for_ready(timeout=timeout, check_interval=check_interval)
    elapsed = time.time() - start
    status = "ready" if ready else "timeout"
    print(f"[INFO] wait_for_ready result: {status} after {elapsed:.2f}s")

    try:
        pane_contents = controller.capture_output()
    except SessionBackendError as exc:
        print(f"[WARN] Unable to capture pane output: {exc}", file=sys.stderr)
        pane_contents = ""

    if pane_contents:
        lines = pane_contents.splitlines()
        tail = lines[-args.tail_lines :] if args.tail_lines else lines
        print("\n[INFO] Tail of pane output:")
        print("\n".join(tail))
    else:
        print("[INFO] No pane output captured.")

    return 0 if ready else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
