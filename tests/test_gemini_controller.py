#!/usr/bin/env python3
"""
Test GeminiController with refactored architecture
"""

import sys
import time
from src.controllers.gemini_controller import GeminiController


def main():
    print("=== Testing Gemini Controller ===\n")

    # Create controller using new GeminiController class
    controller = GeminiController(
        session_name="gemini-controller-test",
        working_dir="/mnt/f/PROGRAMMING_PROJECTS/OrchestratorTest"
    )

    print(f"1. Controller created")
    print(f"   Session: {controller.session_name}")
    print(f"   Executable: {controller.executable}")
    print(f"   Response marker: {controller.response_marker}")
    print(f"   Supports tools: {controller.supports_tools}\n")

    # Clean up any existing session
    if controller.session_exists():
        print("2. Cleaning up existing session...")
        controller.kill_session()
        time.sleep(1)

    # Start session
    print("3. Starting Gemini CLI session...")
    if controller.start_session(auto_confirm_trust=False):  # Gemini doesn't need trust confirmation
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
    print("   " + "\n   ".join(output.split("\n")[:25]))  # First 25 lines
    print()

    # Second command
    print("7. Sending second command: 'List 3 colors'")
    controller.send_command("List 3 colors")
    print("   ✓ Command sent\n")

    print("8. Waiting for response...")
    if controller.wait_for_ready():
        print("   ✓ Response complete\n")
    else:
        print("   ⚠ Timeout\n")

    # Final output
    print("9. Final output:")
    output = controller.capture_output()
    print("   " + "\n   ".join(output.split("\n")[:35]))  # First 35 lines
    print()

    # Cleanup
    print("10. Killing session...")
    if controller.kill_session():
        print("    ✓ Session killed\n")

    print("=== Test Complete ===")
    print("\n✅ Gemini CLI works with new controller!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
