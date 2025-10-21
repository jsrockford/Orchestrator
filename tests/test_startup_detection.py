#!/usr/bin/env python3
"""
Quick test to verify wait_for_startup() works correctly.
"""
import sys
import yaml
from src.controllers.tmux_controller import TmuxController

def load_config():
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

print("="*60)
print("Testing Startup Detection")
print("="*60)

config = load_config()

# Test Claude
print("\n1. Testing Claude startup detection...")
claude = TmuxController(
    session_name="claude-startup-test",
    executable="claude",
    working_dir="/mnt/f/PROGRAMMING_PROJECTS/OrchestratorTest-tmux",
    ai_config=config['claude']
)

if claude.session_exists():
    claude.kill_session()

print("   Starting Claude session...")
try:
    claude.start_session(auto_confirm_trust=True)
    print("   ✓ Claude started and ready!")

    # Show what output was detected
    output = claude.capture_output()
    print(f"   Output length: {len(output)} chars")
    if "? for shortcuts" in output:
        print("   ✓ Found 'for shortcuts' indicator")

    claude.kill_session()
except Exception as e:
    print(f"   ✗ Failed: {e}")
    if claude.session_exists():
        claude.kill_session()
    sys.exit(1)

# Test Gemini
print("\n2. Testing Gemini startup detection...")
gemini = TmuxController(
    session_name="gemini-startup-test",
    executable="gemini",
    working_dir="/mnt/f/PROGRAMMING_PROJECTS/OrchestratorTest-tmux",
    ai_config=config['gemini']
)

if gemini.session_exists():
    gemini.kill_session()

print("   Starting Gemini session...")
try:
    gemini.start_session(auto_confirm_trust=False)
    print("   ✓ Gemini started and ready!")

    # Show what output was detected
    output = gemini.capture_output()
    print(f"   Output length: {len(output)} chars")
    if "Type your message" in output:
        print("   ✓ Found 'Type your message' indicator")

    gemini.kill_session()
except Exception as e:
    print(f"   ✗ Failed: {e}")
    if gemini.session_exists():
        gemini.kill_session()
    sys.exit(1)

print("\n" + "="*60)
print("✓ Startup detection working correctly!")
print("="*60)
