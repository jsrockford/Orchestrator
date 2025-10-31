#!/usr/bin/env python3
"""
Test OutputParser with real Claude Code output
"""

from src.utils.output_parser import OutputParser
from src.utils.path_helpers import get_tmux_worktree_path

# Sample output from our actual tests
WORKDIR_DISPLAY = str(get_tmux_worktree_path())

SAMPLE_OUTPUT = f"""
 ▐▛███▜▌   Claude Code v2.0.8
▝▜█████▛▘  Sonnet 4.5 · Claude Pro
  ▘▘ ▝▝    {WORKDIR_DISPLAY}

> What is 2 + 2?

● 4

> What is Python?

● Python is a high-level, interpreted programming language known for its simple syntax, readability, and
  versatility. It's widely used for web development, data science, automation, AI/ML, and scripting.

> List 3 programming languages

● 1. Python
  2. JavaScript
  3. Java

────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
>
────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  ? for shortcuts                                                                         Thinking off (tab to toggle)
"""


def main():
    print("=== Output Parser Test ===\n")

    parser = OutputParser()

    # Test 1: Strip ANSI codes
    print("1. Testing ANSI stripping (no ANSI in sample):")
    cleaned_ansi = parser.strip_ansi(SAMPLE_OUTPUT)
    print(f"   ✓ ANSI codes removed (length: {len(cleaned_ansi)})\n")

    # Test 2: Clean output
    print("2. Testing output cleaning:")
    cleaned = parser.clean_output(SAMPLE_OUTPUT)
    print("   --- Cleaned Output ---")
    print(cleaned)
    print("   --- End ---\n")

    # Test 3: Extract Q&A pairs
    print("3. Testing Q&A extraction:")
    pairs = parser.extract_responses(SAMPLE_OUTPUT)
    print(f"   Found {len(pairs)} question/answer pairs:\n")

    for i, pair in enumerate(pairs, 1):
        print(f"   Pair {i}:")
        print(f"     Q: {pair['question']}")
        print(f"     A: {pair['response'][:50]}..." if len(pair['response']) > 50 else f"     A: {pair['response']}")
        print()

    # Test 4: Get last response
    print("4. Testing last response extraction:")
    last_response = parser.get_last_response(SAMPLE_OUTPUT)
    print(f"   Last response: {last_response}\n")

    # Test 5: Get last question
    print("5. Testing last question extraction:")
    last_question = parser.get_last_question(SAMPLE_OUTPUT)
    print(f"   Last question: {last_question}\n")

    # Test 6: Format conversation
    print("6. Testing conversation formatting:")
    formatted = parser.format_conversation(SAMPLE_OUTPUT)
    print("   --- Formatted Conversation ---")
    print(formatted)
    print("   --- End ---\n")

    # Test 7: Error detection
    print("7. Testing error detection:")
    error_responses = [
        "Error: File not found",
        "Failed to connect",
        "This is a normal response",
    ]

    for response in error_responses:
        is_error = parser.is_error_response(response)
        status = "ERROR" if is_error else "OK"
        print(f"   '{response}' -> {status}")

    print("\n=== Test Complete ===")


if __name__ == "__main__":
    main()
