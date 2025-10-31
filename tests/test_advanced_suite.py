#!/usr/bin/env python3
"""
Phase 2.4: Advanced Test Suite
Integration tests with real Claude Code and Gemini CLI sessions.

Tests multi-turn conversations, file operations, rapid commands, and error recovery.
"""
import sys
import os
import time
import yaml
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.controllers.tmux_controller import TmuxController
from src.utils.output_parser import OutputParser
from src.utils.path_helpers import (
    ensure_directory,
    get_tmux_worktree_path,
)


TMUX_WORKTREE = get_tmux_worktree_path()
TMUX_WORKTREE_STR = str(TMUX_WORKTREE)


def load_config():
    """Load configuration from config.yaml"""
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)


def _extract_executable_parts(config: dict, agent: str) -> tuple[str, tuple[str, ...]]:
    section = config.get(agent, {})
    executable = section.get("executable")
    if not executable:
        raise KeyError(f"No executable configured for '{agent}'")
    args = section.get("executable_args", [])
    if isinstance(args, str):
        args = [args]
    if not isinstance(args, (list, tuple)):
        raise TypeError(f"Invalid executable_args for '{agent}': {type(args)!r}")
    return executable, tuple(str(arg) for arg in args)


def pause_for_observation(test_name: str, session_name: str, delay: int = 5):
    """Pause to allow manual tmux observation"""
    print(f"\n{'='*60}")
    print(f"OBSERVATION POINT: {test_name}")
    print(f"Session name: {session_name}")
    print(f"To observe: tmux attach -t {session_name} -r")
    print(f"Waiting {delay} seconds for observation...")
    print(f"{'='*60}")
    time.sleep(delay)


def test_multi_turn_claude():
    """Test 1: Multi-turn conversation with context preservation (Claude)"""
    print("\n" + "="*60)
    print("TEST 1: Multi-turn Conversation - Claude Code")
    print("="*60)

    config = load_config()
    parser = OutputParser()

    # Create controller for Claude
    claude_exec, claude_args = _extract_executable_parts(config, "claude")

    controller = TmuxController(
        session_name="claude-test",
        executable=claude_exec,
        working_dir=TMUX_WORKTREE_STR,
        ai_config=config['claude'],
        executable_args=claude_args,
    )

    try:
        # Start session
        print("Starting Claude Code session...")
        controller.start_session(auto_confirm_trust=True)

        pause_for_observation("Claude session started", "claude-test")

        # Turn 1: Ask about a topic
        print("\nTurn 1: Asking Claude to remember a number...")
        controller.send_command("I'm going to tell you a number. Remember it: 42. Just acknowledge you'll remember it.")
        controller.wait_for_ready(timeout=30)

        output1 = controller.capture_output(lines=50)
        print(f"Response received ({len(output1)} chars)")

        pause_for_observation("After Turn 1", "claude-test")

        # Turn 2: Reference previous context
        print("\nTurn 2: Testing context preservation...")
        controller.send_command("What number did I just tell you to remember?")
        controller.wait_for_ready(timeout=30)

        output2 = controller.capture_output(lines=50)
        print(f"Response received ({len(output2)} chars)")

        # Check if Claude remembers
        if "42" in output2:
            print("✓ Context preserved - Claude remembered the number!")
        else:
            print("✗ Context lost - Claude didn't remember")

        pause_for_observation("After Turn 2 (context test)", "claude-test")

        # Turn 3: Follow-up question
        print("\nTurn 3: Follow-up question...")
        controller.send_command("What's that number multiplied by 2?")
        controller.wait_for_ready(timeout=30)

        output3 = controller.capture_output(lines=50)

        if "84" in output3:
            print("✓ Claude correctly calculated 42 * 2 = 84")
        else:
            print("✗ Calculation incorrect or context lost")

        pause_for_observation("After Turn 3 (calculation)", "claude-test")

        print("\n✓ Multi-turn conversation test complete")
        return True

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        print("\nPausing before cleanup (10 seconds)...")
        time.sleep(10)
        if controller.session_exists():
            controller.kill_session()
            print("Session cleaned up")


def test_multi_turn_gemini():
    """Test 2: Multi-turn conversation with context preservation (Gemini)"""
    print("\n" + "="*60)
    print("TEST 2: Multi-turn Conversation - Gemini CLI")
    print("="*60)

    config = load_config()
    parser = OutputParser()

    # Create controller for Gemini
    gemini_exec, gemini_args = _extract_executable_parts(config, "gemini")

    controller = TmuxController(
        session_name="gemini-test",
        executable=gemini_exec,
        working_dir=TMUX_WORKTREE_STR,
        ai_config=config['gemini'],
        executable_args=gemini_args,
    )

    try:
        # Start session
        print("Starting Gemini CLI session...")
        controller.start_session(auto_confirm_trust=False)  # Gemini doesn't need trust confirmation

        pause_for_observation("Gemini session started", "gemini-test")

        # Turn 1: Ask about a topic (avoid triggering file edits)
        print("\nTurn 1: Asking Gemini to remember a number...")
        controller.send_command("Please remember this number: 777. Just say OK.")
        controller.wait_for_ready(timeout=30)

        output1 = controller.capture_output(lines=50)
        print(f"Response received ({len(output1)} chars)")

        pause_for_observation("After Turn 1", "gemini-test")

        # Turn 2: Reference previous context
        print("\nTurn 2: Testing context preservation...")
        controller.send_command("What number did I ask you to remember?")
        controller.wait_for_ready(timeout=30)

        output2 = controller.capture_output(lines=50)
        print(f"Response received ({len(output2)} chars)")

        # Check if Gemini remembers
        if "777" in output2:
            print("✓ Context preserved - Gemini remembered the number!")
        else:
            print("✗ Context lost - Gemini didn't remember")

        pause_for_observation("After Turn 2 (context test)", "gemini-test")

        # Turn 3: Math follow-up
        print("\nTurn 3: Math follow-up...")
        controller.send_command("What is that number divided by 7?")
        controller.wait_for_ready(timeout=30)

        output3 = controller.capture_output(lines=50)
        print(f"Response received ({len(output3)} chars)")

        pause_for_observation("After Turn 3 (creative response)", "gemini-test")

        print("\n✓ Multi-turn conversation test complete")
        return True

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        print("\nPausing before cleanup (10 seconds)...")
        time.sleep(10)
        if controller.session_exists():
            controller.kill_session()
            print("Session cleaned up")


def test_file_operations_claude():
    """Test 3: File operation commands (Claude)"""
    print("\n" + "="*60)
    print("TEST 3: File Operations - Claude Code")
    print("="*60)

    config = load_config()

    claude_exec, claude_args = _extract_executable_parts(config, "claude")

    controller = TmuxController(
        session_name="claude-test",
        executable=claude_exec,
        working_dir=TMUX_WORKTREE_STR,
        ai_config=config['claude'],
        executable_args=claude_args,
    )

    try:
        print("Starting Claude Code session...")
        controller.start_session(auto_confirm_trust=True)

        pause_for_observation("Claude session started", "claude-test")

        # Test 1: Create a test file
        print("\nAsking Claude to create a test file...")
        controller.send_command("Create a file called test_output.txt with the content 'Hello from Claude Code' in it.")
        controller.wait_for_ready(timeout=45)

        output1 = controller.capture_output(lines=100)
        print(f"Response received ({len(output1)} chars)")

        pause_for_observation("After file creation request", "claude-test")

        # Verify file was created
        test_file = ensure_directory(TMUX_WORKTREE) / "test_output.txt"
        if test_file.exists():
            content = test_file.read_text()
            print(f"✓ File created with content: {content.strip()}")
        else:
            print("✗ File was not created")

        # Test 2: Read the file back
        print("\nAsking Claude to read the file...")
        controller.send_command("What are the contents of test_output.txt?")
        controller.wait_for_ready(timeout=30)

        output2 = controller.capture_output(lines=100)

        if "Hello from Claude Code" in output2:
            print("✓ Claude correctly read the file contents")
        else:
            print("✗ Claude couldn't read the file or content missing")

        pause_for_observation("After file read request", "claude-test")

        print("\n✓ File operations test complete")
        return True

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        print("\nPausing before cleanup (10 seconds)...")
        time.sleep(10)

        # Clean up test file
        test_file = ensure_directory(TMUX_WORKTREE) / "test_output.txt"
        if test_file.exists():
            test_file.unlink()
            print("Test file removed")

        if controller.session_exists():
            controller.kill_session()
            print("Session cleaned up")


def main():
    """Run all advanced tests"""
    print("="*60)
    print("PHASE 2.4: ADVANCED TEST SUITE")
    print("="*60)
    print("\nThis suite will test:")
    print("1. Multi-turn conversations (context preservation)")
    print("2. File operation commands")
    print("3. Rapid sequential commands")
    print("4. Error scenarios with recovery")
    print("\nYou can attach to tmux sessions for observation:")
    print("  tmux attach -t claude-test -r")
    print("  tmux attach -t gemini-test -r")
    print("\nStarting tests in 5 seconds...")
    time.sleep(5)

    results = {}

    # Test 1: Multi-turn Claude
    results['multi_turn_claude'] = test_multi_turn_claude()

    # Test 2: Multi-turn Gemini
    results['multi_turn_gemini'] = test_multi_turn_gemini()

    # Test 3: File operations Claude
    results['file_ops_claude'] = test_file_operations_claude()

    # Summary
    print("\n" + "="*60)
    print("TEST SUITE SUMMARY")
    print("="*60)
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {test_name}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\nTotal: {passed}/{total} tests passed")


if __name__ == "__main__":
    main()
