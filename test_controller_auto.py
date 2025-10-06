#!/usr/bin/env python3
"""
Automated test script for TmuxController (no user input required)
"""

import sys
import time
from src.controllers.tmux_controller import TmuxController


def main():
    # Use the worktree directory for testing
    worktree_dir = "/mnt/f/PROGRAMMING_PROJECTS/OrchestratorTest-tmux"

    # Create controller
    controller = TmuxController(
        session_name="claude-test-auto",
        working_dir=worktree_dir
    )

    print("=== Automated Tmux Controller Test ===\n")

    # Clean up any existing session
    print("1. Cleaning up any existing session...")
    if controller.session_exists():
        controller.kill_session()
        time.sleep(1)
    print("   ✓ Clean state\n")

    # Start session
    print("2. Starting Claude Code session...")
    if controller.start_session(auto_confirm_trust=True):
        print("   ✓ Session started successfully\n")
    else:
        print("   ✗ Failed to start session")
        return 1

    # Check status
    print("3. Session status:")
    status = controller.get_status()
    for key, value in status.items():
        print(f"   {key}: {value}")
    print()

    # Test command sequence with proper timing
    print("4. Sending command: 'What is 2 + 2?'")
    controller.send_command("What is 2 + 2?")
    print("   ✓ Command sent\n")

    print("5. Waiting for response (5 seconds)...")
    time.sleep(5)

    print("6. Capturing output:")
    output = controller.capture_output()
    print("   " + "\n   ".join(output.split("\n")))
    print()

    # Second command with longer wait
    print("7. Sending command: 'What is Python?'")
    controller.send_command("What is Python?")
    print("   ✓ Command sent\n")

    print("8. Waiting for response (5 seconds)...")
    time.sleep(5)

    print("9. Capturing output:")
    output = controller.capture_output()
    print("   " + "\n   ".join(output.split("\n")))
    print()

    # Test Ctrl+C
    print("10. Testing Ctrl+C (cancel operation)...")
    controller.send_ctrl_c()
    time.sleep(1)
    print("    ✓ Ctrl+C sent\n")

    print("11. Capturing output after cancel:")
    output = controller.capture_output()
    print("   " + "\n   ".join(output.split("\n")))
    print()

    # Cleanup
    print("12. Killing session...")
    if controller.kill_session():
        print("    ✓ Session killed successfully\n")
    else:
        print("    ✗ Failed to kill session\n")

    print("=== Test Complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
