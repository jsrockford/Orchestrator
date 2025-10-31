#!/usr/bin/env python3
"""
Manual validation script for the Qwen controller.

Launches the Qwen CLI inside tmux, exercises a pair of commands, and verifies
that the `(esc to cancel` loading indicator clears before sending additional
input. Mirrors the existing Gemini/Codex smoke scripts so we can sanity check
the ready/wait flow before running larger orchestrations.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Optional, Sequence

from src.controllers.qwen_controller import QwenController
from src.utils.path_helpers import get_tmux_worktree_path

SESSION_NAME = "qwen-controller-test"
WORKING_DIR = str(get_tmux_worktree_path())


class TeeWriter:
    """Mirror stdout to an additional file handle when requested."""

    def __init__(self, *targets):
        self._targets = targets

    def write(self, data: str) -> None:
        for target in self._targets:
            target.write(data)

    def flush(self) -> None:
        for target in self._targets:
            target.flush()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manual Qwen controller validation probe.")
    parser.add_argument(
        "--log-file",
        help=(
            "Optional path to capture a copy of the console output. "
            "Specify a directory to create/use qwen_standalone.log inside it."
        ),
    )
    return parser.parse_args(argv)


def _prepare_log_handle(path_str: str) -> tuple[Path, object]:
    log_path = Path(path_str)
    if log_path.is_dir() or not log_path.suffix:
        log_path.mkdir(parents=True, exist_ok=True)
        log_path = log_path / "qwen_standalone.log"
    else:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    handle = log_path.open("w", encoding="utf-8")
    return log_path, handle


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    original_stdout = sys.stdout
    log_handle = None

    try:
        if args.log_file:
            log_path, log_handle = _prepare_log_handle(args.log_file)
            sys.stdout = TeeWriter(original_stdout, log_handle)
            print(f"[log] Mirroring output to {log_path}")

        print("=== Testing Qwen Controller ===\n")

        controller = QwenController(
            session_name=SESSION_NAME,
            working_dir=WORKING_DIR,
        )

        print("1. Controller created")
        print(f"   Session: {controller.session_name}")
        print(f"   Executable: {controller.executable}")
        print(f"   Ready indicators: {controller.ready_indicators}")
        print(f"   Loading indicators: {controller.loading_indicators}")
        print(f"   Ready stabilization delay: {controller.ready_stabilization_delay:.2f}s")
        print(f"   Text enter delay: {controller.text_enter_delay:.2f}s\n")

        if controller.session_exists():
            print("2. Cleaning up existing session…")
            controller.kill_session()
            time.sleep(1.0)

        print("3. Starting Qwen CLI session…")
        if controller.start_session(auto_confirm_trust=False):
            print("   ✓ Session started\n")
        else:
            print("   ✗ Failed to start session")
            return 1

        first_prompt = "Summarize the Fibonacci sequence in one sentence."
        print(f"4. Sending command: {first_prompt!r}")
        controller.send_command(first_prompt)
        print("   ✓ Command sent\n")

        print("5. Waiting for response to complete (monitoring '(esc to cancel')…")
        if controller.wait_for_ready(timeout=controller.response_timeout):
            print("   ✓ Response complete\n")
        else:
            print("   ⚠ Timeout waiting for Qwen response\n")

        output = controller.capture_output()
        tail_preview = "\n   ".join(output.splitlines()[-25:])
        print("6. Captured output tail:")
        print(f"   {tail_preview}\n")

        recent_lines = output.splitlines()[-15:]
        if any(
            indicator in line
            for indicator in controller.loading_indicators
            for line in recent_lines
        ):
            print("   ⚠ Loading indicator text still present; double-check wait timing.")
        else:
            print("   ✓ Loading indicator cleared before prompt returned.")

        second_prompt = "\n".join(
            [
                "qwen, we're collaborating on: Give a one sentence statement about quantum computing, then pass to the next.",
                "Provide your next contribution focusing on actionable steps.",
                "Recent context: claude: ● To begin exploring quantum computing, start by learning the mathematical foundations of linear algebra and quantum mechanics.",
                "Provide your next contribution focusing on actionable steps.",
            ]
        )
        print(f"\n7. Sending multiline prompt:\n{second_prompt!r}")
        controller.send_command(second_prompt)
        print("   ✓ Multiline prompt sent\n")

        print("8. Waiting for multiline response…")
        if controller.wait_for_ready(timeout=controller.response_timeout):
            print("   ✓ Multiline response complete\n")
        else:
            print("   ⚠ Timeout waiting for multiline Qwen response\n")

        final_output = controller.capture_output()
        final_tail = "\n   ".join(final_output.splitlines()[-35:])
        print("9. Final output tail:")
        print(f"   {final_tail}\n")

        print("10. Killing session…")
        if controller.kill_session():
            print("    ✓ Session killed\n")
        else:
            print("    ⚠ Session kill reported failure; verify manually.\n")

        print("=== Test Complete ===")
        return 0

    finally:
        if log_handle is not None:
            log_handle.flush()
            log_handle.close()
        sys.stdout = original_stdout


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
