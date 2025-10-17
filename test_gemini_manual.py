#!/usr/bin/env python3
"""
Manual Gemini test - similar to Claude manual test

Allows user to attach and observe Gemini CLI interaction
"""

import subprocess
import time
import sys


def run_tmux(args):
    """Run tmux command"""
    cmd = ["tmux"] + args
    return subprocess.run(cmd, capture_output=True, text=True)


def main():
    session_name = "gemini-manual-test"

    print("=== Gemini Manual Interactive Test ===\n")

    # Clean up existing session
    print("Cleaning up any existing session...")
    run_tmux(["kill-session", "-t", session_name])
    time.sleep(1)

    # Start Gemini session
    print(f"Starting Gemini CLI session '{session_name}'...")
    result = run_tmux([
        "new-session", "-d",
        "-s", session_name,
        "-c", "/mnt/f/PROGRAMMING_PROJECTS/OrchestratorTest",
        "gemini", "--screenReader"
    ])

    if result.returncode != 0:
        print(f"Failed to start session: {result.stderr}")
        return 1

    print(f"✓ Session '{session_name}' started!\n")
    print("=" * 60)
    print("ATTACH NOW to observe:")
    print(f"  tmux attach -t {session_name} -r")
    print("=" * 60)
    print("\nWaiting 10 seconds for you to attach...")

    for i in range(10, 0, -1):
        print(f"  {i}...", end="\r")
        time.sleep(1)
    print("\n")

    # Test 1
    print("TEST 1: Sending 'What is 2 + 2?'")
    run_tmux(["send-keys", "-t", session_name, "What is 2 + 2?"])
    time.sleep(0.2)
    run_tmux(["send-keys", "-t", session_name, "Enter"])
    print("  Waiting 5 seconds for response...")
    time.sleep(5)
    print("  ✓ Done\n")

    # Test 2
    print("TEST 2: Sending 'What is Python?'")
    run_tmux(["send-keys", "-t", session_name, "What is Python?"])
    time.sleep(0.2)
    run_tmux(["send-keys", "-t", session_name, "Enter"])
    print("  Waiting 5 seconds for response...")
    time.sleep(5)
    print("  ✓ Done\n")

    # Test 3
    print("TEST 3: Sending 'List 3 programming languages'")
    run_tmux(["send-keys", "-t", session_name, "List 3 programming languages"])
    time.sleep(0.2)
    run_tmux(["send-keys", "-t", session_name, "Enter"])
    print("  Waiting 5 seconds for response...")
    time.sleep(5)
    print("  ✓ Done\n")

    # Capture final output
    print("Capturing final output:")
    print("-" * 60)
    result = run_tmux(["capture-pane", "-t", session_name, "-p", "-S", "-30"])
    print(result.stdout)
    print("-" * 60)
    print()

    # Keep alive
    print("=" * 60)
    print(f"Session '{session_name}' is still running!")
    print(f"  To attach: tmux attach -t {session_name} -r")
    print(f"  To kill: tmux kill-session -t {session_name}")
    print("=" * 60)
    print("\nTest complete. Session kept alive for your inspection.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
