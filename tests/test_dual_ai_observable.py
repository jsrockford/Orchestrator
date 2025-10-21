#!/usr/bin/env python3
"""
Dual AI test with pauses for observation

Run this, then attach to both sessions to watch them work!
"""

import sys
import time
from src.controllers.claude_controller import ClaudeController
from src.controllers.gemini_controller import GeminiController


def main():
    print("=" * 70)
    print("DUAL AI OBSERVABLE TEST - Claude Code + Gemini CLI")
    print("=" * 70)
    print()

    # Create both controllers
    claude = ClaudeController(
        session_name="claude-dual-test",
        working_dir="/mnt/f/PROGRAMMING_PROJECTS/OrchestratorTest-tmux"
    )

    gemini = GeminiController(
        session_name="gemini-dual-test",
        working_dir="/mnt/f/PROGRAMMING_PROJECTS/OrchestratorTest"
    )

    print("1. Cleaning up any existing sessions...")
    for ai in [claude, gemini]:
        if ai.session_exists():
            ai.kill_session()
            time.sleep(1)
    print("   ✓ Clean\n")

    # Start both AIs
    print("2. Starting both AIs...")
    claude.start_session()
    gemini.start_session(auto_confirm_trust=False)
    print("   ✓ Both started\n")

    print("=" * 70)
    print("ATTACH NOW!")
    print("Terminal 1: tmux attach -t claude-dual-test -r")
    print("Terminal 2: tmux attach -t gemini-dual-test -r")
    print("=" * 70)
    print("\nWaiting 15 seconds for you to attach...")
    for i in range(15, 0, -1):
        print(f"  {i}...", end="\r")
        time.sleep(1)
    print("\n")

    # Test 1: Same question to both
    print("TEST 1: Asking both: 'What is 2 + 2?'")
    claude.send_command("What is 2 + 2?")
    gemini.send_command("What is 2 + 2?")
    print("  Commands sent. Waiting for responses...")
    claude.wait_for_ready()
    gemini.wait_for_ready()
    print("  ✓ Both responded\n")
    time.sleep(3)

    # Test 2: Different questions
    print("TEST 2: Different questions")
    print("  Claude: 'What is Python?'")
    claude.send_command("What is Python?")
    claude.wait_for_ready()
    print("  ✓ Claude responded\n")
    time.sleep(2)

    print("  Gemini: 'What is JavaScript?'")
    gemini.send_command("What is JavaScript?")
    gemini.wait_for_ready()
    print("  ✓ Gemini responded\n")
    time.sleep(3)

    # Test 3: Quick succession
    print("TEST 3: Quick succession on both")
    print("  Claude: 'List 3 colors'")
    claude.send_command("List 3 colors")
    time.sleep(1)

    print("  Gemini: 'List 3 animals'")
    gemini.send_command("List 3 animals")
    time.sleep(1)

    print("  Waiting for both...")
    claude.wait_for_ready()
    gemini.wait_for_ready()
    print("  ✓ Both completed\n")

    print("=" * 70)
    print("Tests complete! Sessions still running for your inspection.")
    print("=" * 70)
    print("\nTo kill sessions:")
    print("  tmux kill-session -t claude-dual-test")
    print("  tmux kill-session -t gemini-dual-test")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
