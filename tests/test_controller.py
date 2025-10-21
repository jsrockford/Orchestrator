#!/usr/bin/env python3
"""
Simple test script for TmuxController

Tests basic functionality of the TmuxController class.
"""

import sys
import time
from src.controllers.tmux_controller import TmuxController


def main():
    # Use the worktree directory for testing
    worktree_dir = "/mnt/f/PROGRAMMING_PROJECTS/OrchestratorTest-tmux"

    # Create controller
    controller = TmuxController(
        session_name="claude-test",
        working_dir=worktree_dir
    )

    print("=== Tmux Controller Test ===\n")

    # Test 1: Check if session already exists
    print("1. Checking for existing session...")
    if controller.session_exists():
        print("   ⚠️  Session already exists. Killing it first...")
        controller.kill_session()
        time.sleep(1)
    print("   ✓ No existing session\n")

    # Test 2: Start session
    print("2. Starting Claude Code session...")
    if controller.start_session(auto_confirm_trust=True):
        print("   ✓ Session started successfully\n")
    else:
        print("   ✗ Failed to start session")
        return 1

    # Test 3: Check status
    print("3. Checking session status...")
    status = controller.get_status()
    for key, value in status.items():
        print(f"   {key}: {value}")
    print()

    # Test 4: Send a simple command
    print("4. Sending test command: 'What is 2 + 2?'")
    if controller.send_command("What is 2 + 2?"):
        print("   ✓ Command sent successfully\n")
    else:
        print("   ✗ Failed to send command")
        return 1

    # Test 5: Wait and capture output
    print("5. Waiting for response (3 seconds)...")
    time.sleep(3)

    print("6. Capturing output...")
    output = controller.capture_output()
    print("   --- Output Start ---")
    print(output)
    print("   --- Output End ---\n")

    # Test 6: Send another command
    print("7. Sending second command: 'What is Python?'")
    if controller.send_command("What is Python?"):
        print("   ✓ Command sent successfully\n")
    else:
        print("   ✗ Failed to send command")
        return 1

    print("8. Waiting for response (3 seconds)...")
    time.sleep(3)

    print("9. Capturing output...")
    output = controller.capture_output()
    print("   --- Output Start ---")
    print(output)
    print("   --- Output End ---\n")

    # Test 7: Keep session alive or kill
    print("10. Session control options:")
    print("    - Press 'k' to kill the session")
    print("    - Press 'a' to attach to the session (read-only)")
    print("    - Press any other key to keep session alive and exit")

    choice = input("\n    Your choice: ").lower()

    if choice == 'k':
        print("\n    Killing session...")
        if controller.kill_session():
            print("    ✓ Session killed\n")
        else:
            print("    ✗ Failed to kill session\n")
    elif choice == 'a':
        print("\n    Attaching in read-only mode...")
        print("    (Press Ctrl+b, then d to detach)")
        controller.attach_for_manual(read_only=True)
        print("\n    Detached from session\n")
    else:
        print(f"\n    Session '{controller.session_name}' is still running")
        print(f"    To attach: tmux attach -t {controller.session_name}")
        print(f"    To kill: tmux kill-session -t {controller.session_name}\n")

    print("=== Test Complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
