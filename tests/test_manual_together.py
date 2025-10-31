#!/usr/bin/env python3
"""
Manual interactive test - works together with user observation

This script will:
1. Start a Claude Code session
2. Pause so you can attach and observe
3. Send commands one at a time with pauses between
4. Keep session alive at the end for inspection
"""

import sys
import time
from src.controllers.tmux_controller import TmuxController
from src.utils.path_helpers import get_tmux_worktree_path


def main():
    worktree_dir = str(get_tmux_worktree_path())

    controller = TmuxController(
        session_name="claude-manual-test",
        working_dir=worktree_dir
    )

    print("=== Manual Interactive Test ===\n")

    # Clean up
    if controller.session_exists():
        print("Cleaning up existing session...")
        controller.kill_session()
        time.sleep(1)

    # Start session
    print("Starting Claude Code session...")
    if not controller.start_session(auto_confirm_trust=True):
        print("Failed to start session!")
        return 1

    print(f"✓ Session '{controller.session_name}' started!\n")
    print("=" * 60)
    print("ATTACH NOW to observe:")
    print(f"  tmux attach -t {controller.session_name} -r")
    print("=" * 60)
    print("\nWaiting 10 seconds for you to attach...")

    for i in range(10, 0, -1):
        print(f"  {i}...", end="\r")
        time.sleep(1)
    print("\n")

    # Test 1
    print("TEST 1: Sending 'What is 2 + 2?'")
    controller.send_command("What is 2 + 2?")
    print("  Waiting for response to complete...")
    if controller.wait_for_ready(timeout=30):
        print("  ✓ Response complete and ready for next command\n")
    else:
        print("  ⚠ Timeout waiting for ready state\n")

    # Test 2
    print("TEST 2: Sending 'What is Python?'")
    controller.send_command("What is Python?")
    print("  Waiting for response to complete...")
    if controller.wait_for_ready(timeout=30):
        print("  ✓ Response complete and ready for next command\n")
    else:
        print("  ⚠ Timeout waiting for ready state\n")

    # Test 3
    print("TEST 3: Sending 'List 3 programming languages'")
    controller.send_command("List 3 programming languages")
    print("  Waiting for response to complete...")
    if controller.wait_for_ready(timeout=30):
        print("  ✓ Response complete and ready for next command\n")
    else:
        print("  ⚠ Timeout waiting for ready state\n")

    # Capture final state
    print("Capturing final output:")
    print("-" * 60)
    output = controller.capture_scrollback()
    # Show last 30 lines
    lines = output.split("\n")
    for line in lines[-30:]:
        print(line)
    print("-" * 60)
    print()

    # Keep alive
    print("=" * 60)
    print(f"Session '{controller.session_name}' is still running!")
    print(f"  To attach: tmux attach -t {controller.session_name} -r")
    print(f"  To kill: tmux kill-session -t {controller.session_name}")
    print("=" * 60)
    print("\nTest complete. Session kept alive for your inspection.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
