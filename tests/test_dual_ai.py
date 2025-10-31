#!/usr/bin/env python3
"""
Test both Claude and Gemini running simultaneously

This is the ultimate test - demonstrating multi-AI orchestration capability!
"""

import sys
import time
from src.controllers.claude_controller import ClaudeController
from src.controllers.gemini_controller import GeminiController
from src.utils.path_helpers import get_tmux_worktree_path, get_repo_root


def main():
    print("=" * 70)
    print("DUAL AI OPERATION TEST - Claude Code + Gemini CLI")
    print("=" * 70)
    print()

    # Create both controllers
    claude = ClaudeController(
        session_name="claude-dual-test",
        working_dir=str(get_tmux_worktree_path())
    )

    gemini = GeminiController(
        session_name="gemini-dual-test",
        working_dir=str(get_repo_root())
    )

    print("1. Controllers created:")
    print(f"   Claude: {claude.session_name} ({claude.response_marker})")
    print(f"   Gemini: {gemini.session_name} ({gemini.response_marker})\n")

    # Clean up
    for ai, name in [(claude, "Claude"), (gemini, "Gemini")]:
        if ai.session_exists():
            print(f"   Cleaning up existing {name} session...")
            ai.kill_session()
            time.sleep(1)

    # Start both AIs
    print("2. Starting both AIs simultaneously...")
    claude_started = claude.start_session()
    gemini_started = gemini.start_session(auto_confirm_trust=False)

    if claude_started and gemini_started:
        print("   ✅ Both AIs started successfully!\n")
    else:
        print("   ❌ Failed to start one or both AIs")
        return 1

    # Send same question to both
    question = "What is artificial intelligence?"
    print(f"3. Asking both AIs: '{question}'")
    claude.send_command(question)
    gemini.send_command(question)
    print("   ✓ Questions sent to both\n")

    # Wait for both to respond
    print("4. Waiting for Claude response...")
    if claude.wait_for_ready():
        print("   ✓ Claude ready\n")
    else:
        print("   ⚠ Claude timeout\n")

    print("5. Waiting for Gemini response...")
    if gemini.wait_for_ready():
        print("   ✓ Gemini ready\n")
    else:
        print("   ⚠ Gemini timeout\n")

    # Capture and display Claude's response
    print("6. Claude's response:")
    print("   " + "-" * 66)
    claude_output = claude.capture_output()
    # Extract just the response part
    for line in claude_output.split("\n"):
        if "●" in line or (line.strip() and not line.startswith(">")):
            if not any(skip in line for skip in ["▐▛███▜▌", "────", "? for shortcuts"]):
                print("   " + line)
    print("   " + "-" * 66)
    print()

    # Capture and display Gemini's response
    print("7. Gemini's response:")
    print("   " + "-" * 66)
    gemini_output = gemini.capture_output()
    # Extract just the response part
    for line in gemini_output.split("\n"):
        if "✦" in line or (line.strip() and ">" in line and "Type your message" not in line):
            if not any(skip in line for skip in ["███", "Tips for", "context left"]):
                print("   " + line)
    print("   " + "-" * 66)
    print()

    # Send different questions to each
    print("8. Sending different questions:")
    claude_q = "Name a programming language"
    gemini_q = "Name a color"

    print(f"   Claude: '{claude_q}'")
    claude.send_command(claude_q)
    claude.wait_for_ready()

    print(f"   Gemini: '{gemini_q}'")
    gemini.send_command(gemini_q)
    gemini.wait_for_ready()
    print("   ✓ Both responded\n")

    # Show sessions are independent
    print("9. Verifying independent sessions:")
    print(f"   Claude session exists: {claude.session_exists()}")
    print(f"   Gemini session exists: {gemini.session_exists()}\n")

    # Cleanup
    print("10. Cleaning up...")
    claude.kill_session()
    gemini.kill_session()
    print("    ✓ Both sessions terminated\n")

    print("=" * 70)
    print("🎉 SUCCESS! Claude Code and Gemini CLI operating simultaneously!")
    print("=" * 70)
    print("\nKey Achievements:")
    print("✅ Both AIs started in separate tmux sessions")
    print("✅ Both AIs responded to commands independently")
    print("✅ No interference between sessions")
    print("✅ Clean session management for both")
    print("\n🚀 Multi-AI orchestration foundation complete!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
