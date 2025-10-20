#!/usr/bin/env python3
"""
Test configuration loader
"""

from src.utils.config_loader import ConfigLoader, get_config


def main():
    print("=== Configuration Loader Test ===\n")

    # Test loading config
    print("1. Loading configuration...")
    config = get_config()
    print(f"   ✓ Config loaded from: {config.config_path}\n")

    # Test getting values with dot notation
    print("2. Testing dot notation access:")
    test_cases = [
        ("claude.startup_timeout", "Startup timeout"),
        ("claude.response_timeout", "Response timeout"),
        ("tmux.capture_lines", "Capture lines"),
        ("tmux.session_prefix", "Session prefix"),
        ("logging.level", "Log level"),
        ("worktree.main_path", "Main worktree path"),
    ]

    for key_path, description in test_cases:
        value = config.get(key_path)
        print(f"   {description:20} ({key_path}): {value}")

    print()

    # Test getting sections
    print("3. Testing section access:")
    claude_config = config.get_section("claude")
    print(f"   Claude section keys: {list(claude_config.keys())}")

    tmux_config = config.get_section("tmux")
    print(f"   Tmux section keys: {list(tmux_config.keys())}\n")

    # Test default values
    print("4. Testing default values:")
    nonexistent = config.get("nonexistent.key", "DEFAULT_VALUE")
    print(f"   Nonexistent key with default: {nonexistent}\n")

    # Display test commands
    print("5. Available test commands:")
    simple_commands = config.get("test_commands.simple", [])
    for i, cmd in enumerate(simple_commands, 1):
        print(f"   {i}. {cmd}")

    print("\n=== Test Complete ===")


if __name__ == "__main__":
    main()
