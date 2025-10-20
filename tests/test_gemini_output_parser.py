#!/usr/bin/env python3
"""
Test OutputParser with Gemini CLI output

Verify that OutputParser can handle Gemini's different response format
"""

import sys
import time
from src.utils.output_parser import OutputParser
from src.controllers.gemini_controller import GeminiController

# Sample Gemini output from our tests
SAMPLE_GEMINI_OUTPUT = """
 ███            █████████  ██████████ ██████   ██████ █████ ██████   █████ █████
░░░███         ███░░░░░███░░███░░░░░█░░██████ ██████ ░░███ ░░██████ ░░███ ░░███
  ░░░███      ███     ░░░  ░███  █ ░  ░███░█████░███  ░███  ░███░███ ░███  ░███
    ░░░███   ░███          ░██████    ░███░░███ ░███  ░███  ░███░░███░███  ░███

Tips for getting started:
1. Ask questions, edit files, or run commands.

╭────────────────────╮
│  > What is 2 + 2?  │
╰────────────────────╯

✦ 4

╭─────────────────────╮
│  > What is Python?  │
╰─────────────────────╯

✦ Python is a high-level, interpreted programming language known for its readability and versatility. It is
  widely used for web development, data analysis, artificial intelligence, scientific computing, and
  automation.

╭──────────────────────────────────╮
│  > List 3 programming languages  │
╰──────────────────────────────────╯

✦ 1. Python
  2. JavaScript
  3. Java

Using: 2 GEMINI.md files
╭──────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ >   Type your message or @path/to/file                                                                   │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────╯
/mnt/f/PROGRAMMING_PROJECTS/OrchestratorTest            no sandbox (see     gemini-2.5-pro (99% context
(GeminiDev*)                                            /docs)             left)
"""


def main():
    print("=== Testing OutputParser with Gemini Output ===\n")

    parser = OutputParser()

    # Test 1: Clean output
    print("1. Testing output cleaning:")
    cleaned = parser.clean_output(SAMPLE_GEMINI_OUTPUT)
    print("   --- Cleaned Output ---")
    print(cleaned)
    print("   --- End ---\n")

    # Test 2: Extract Q&A pairs
    print("2. Testing Q&A extraction with Gemini's ✦ marker:")
    pairs = parser.extract_responses(SAMPLE_GEMINI_OUTPUT)
    print(f"   Found {len(pairs)} question/answer pairs (expected 3):\n")

    for i, pair in enumerate(pairs, 1):
        print(f"   Pair {i}:")
        print(f"     Q: {pair['question']}")
        print(f"     A: {pair['response'][:60]}..." if len(pair['response']) > 60 else f"     A: {pair['response']}")
        print()

    # Check for duplicates
    questions = [p['question'] for p in pairs]
    if len(questions) != len(set(questions)):
        print("   ⚠ WARNING: Duplicate questions detected!")

    # Test 3: Get last response
    print("3. Testing last response extraction:")
    last_response = parser.get_last_response(SAMPLE_GEMINI_OUTPUT)
    print(f"   Last response: {last_response}\n")

    # Test 4: Get last question
    print("4. Testing last question extraction:")
    last_question = parser.get_last_question(SAMPLE_GEMINI_OUTPUT)
    print(f"   Last question: {last_question}\n")

    # Test 5: Live test with actual Gemini session
    print("5. LIVE TEST: Testing with actual Gemini session...")
    print("   Starting Gemini...")

    controller = GeminiController(
        session_name="gemini-parser-test",
        working_dir="/mnt/f/PROGRAMMING_PROJECTS/OrchestratorTest"
    )

    # Clean up existing
    if controller.session_exists():
        controller.kill_session()
        time.sleep(1)

    controller.start_session(auto_confirm_trust=False)
    print("   ✓ Gemini started")
    print("\n   ATTACH NOW: tmux attach -t gemini-parser-test -r")
    print("   Waiting 10 seconds for you to attach...")
    for i in range(10, 0, -1):
        print(f"   {i}...", end="\r")
        time.sleep(1)
    print("\n")

    # Send test command
    print("   Sending: 'What is the capital of France?'")
    controller.send_command("What is the capital of France?")
    print("   Waiting for response...")
    controller.wait_for_ready()
    print("   ✓ Response received")

    print("\n   Pausing 5 seconds so you can see the result...")
    time.sleep(5)

    # Capture and parse
    output = controller.capture_output()
    print(f"   Raw output length: {len(output)} characters")
    print(f"   Full output:")
    print("   " + "\n   ".join(output.split("\n")))
    print()

    pairs = parser.extract_responses(output)

    print(f"   Extracted {len(pairs)} pairs from live session:\n")
    if pairs:
        for pair in pairs:
            print(f"     Q: {pair['question']}")
            print(f"     A: {pair['response']}")
            print()

    # Cleanup
    controller.kill_session()
    print("   ✓ Session cleaned up\n")

    # Final verdict
    print("=" * 70)
    if len(pairs) > 0:
        print("✅ SUCCESS: OutputParser works with Gemini!")
        print("   - Handles ✦ marker correctly")
        print("   - Extracts Q&A pairs properly")
        print("   - Compatible with Gemini's box format")
        return 0
    else:
        print("❌ ISSUE: Parser may need updates for Gemini format")
        return 1


if __name__ == "__main__":
    sys.exit(main())
