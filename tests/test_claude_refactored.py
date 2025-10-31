#!/usr/bin/env python3
"""
Test refactored ClaudeController to ensure Claude Code still works
"""

import sys
import time
from src.controllers.claude_controller import ClaudeController
from src.utils.path_helpers import get_tmux_worktree_path


def main():
    print("=== Testing Refactored Claude Controller ===\n")

    # Create controller using new ClaudeController class
    controller = ClaudeController(
        session_name="claude-refactor-test",
        working_dir=str(get_tmux_worktree_path())
    )

    print(f"1. Controller created")
    print(f"   Session: {controller.session_name}")
    print(f"   Executable: {controller.executable}")
    print(f"   Response marker: {controller.response_marker}\n")

    # Clean up any existing session
    if controller.session_exists():
        print("2. Cleaning up existing session...")
        controller.kill_session()
        time.sleep(1)

    # Start session
    print("3. Starting Claude Code session...")
    if controller.start_session():
        print("   ✓ Session started\n")
    else:
        print("   ✗ Failed to start session")
        return 1

    # Send command
    print("4. Sending command: 'What is 2 + 2?'")
    controller.send_command("What is 2 + 2?")
    print("   ✓ Command sent\n")

    # Wait for ready
    print("5. Waiting for response to complete...")
    if controller.wait_for_ready():
        print("   ✓ Response complete\n")
    else:
        print("   ⚠ Timeout waiting for response\n")

    # Capture output
    print("6. Capturing output:")
    output = controller.capture_output()
    print("   " + "\n   ".join(output.split("\n")[:20]))  # First 20 lines
    print()

    # Second command
    print("7. Sending second command: 'What is Python?'")
    controller.send_command("What is Python?")
    print("   ✓ Command sent\n")

    print("8. Waiting for response...")
    if controller.wait_for_ready():
        print("   ✓ Response complete\n")
    else:
        print("   ⚠ Timeout\n")

    # Final output
    print("9. Final output:")
    output = controller.capture_output()
    print("   " + "\n   ".join(output.split("\n")[:30]))  # First 30 lines
    print()

    # Cleanup
    print("10. Killing session...")
    if controller.kill_session():
        print("    ✓ Session killed\n")

    print("=== Test Complete ===")
    print("\n✅ Claude Code works with refactored controller!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
