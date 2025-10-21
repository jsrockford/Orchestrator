# Timing and Synchronization Guide

This guide explains how timing works in the AI CLI orchestration system and how to configure timeouts for different use cases.

## Overview

The system uses **observation-based synchronization** rather than arbitrary delays wherever possible. This ensures reliable operation regardless of system performance, network latency, or model response times.

## Three Types of Waiting

### 1. Startup Detection (`start_session()`)

**What it does:** Waits for AI to fully initialize and be ready for first input.

**How it works:**
- Detects ready indicators (e.g., "Type your message", "? for shortcuts")
- Checks for absence of loading indicators
- Adds brief stabilization delay for input buffer initialization

**Configuration:**
```yaml
claude:
  startup_timeout: 20  # Max seconds to wait for startup
  ready_indicators:
    - "? for shortcuts"

gemini:
  startup_timeout: 20  # Max seconds to wait for startup
  ready_indicators:
    - "Type your message or @path/to/file"
  loading_indicators:  # Must NOT be present when ready
    - "⠦"
    - "⠼"
    - "Enhancing..."
```

**Usage:**
```python
# Happens automatically in start_session()
controller.start_session(auto_confirm_trust=True)
# Session is ready for first command
```

### 2. Response Completion (`wait_for_ready()`)

**What it does:** Waits for model to finish responding to a command.

**How it works:**
- Repeatedly captures output every 0.5s
- Detects when output stabilizes (no changes for 3 consecutive checks)
- Returns True when model is ready for next input

**Key insight:** This is **observation-based**, not time-based. If the model takes 10 seconds or 60 seconds to respond, `wait_for_ready()` will wait until it's actually done (up to the timeout).

**Configuration:**
```yaml
claude:
  response_timeout: 30      # Max seconds to wait for response
  ready_check_interval: 0.5 # Seconds between stability checks
  ready_stable_checks: 3    # Consecutive stable checks required
```

**Usage Examples:**

```python
# Simple question (30s timeout is fine)
controller.send_command("What is 2 + 2?")
controller.wait_for_ready(timeout=30)

# Complex analysis (needs longer timeout)
controller.send_command("Analyze this 1000-line codebase and suggest refactorings")
controller.wait_for_ready(timeout=120)

# Tool execution (file operations, code generation)
controller.send_command("Create 5 test files with comprehensive test cases")
controller.wait_for_ready(timeout=300)

# Use config default
controller.send_command("List 3 colors")
controller.wait_for_ready()  # Uses response_timeout from config
```

**Handling Timeouts:**

```python
if not controller.wait_for_ready(timeout=60):
    logger.warning("Response timeout - model may still be processing")
    # Options:
    # 1. Capture partial output
    partial = controller.capture_output()
    # 2. Wait longer
    if not controller.wait_for_ready(timeout=60):
        # Give up or handle error
        pass
```

### 3. Command Input (`send_command()`)

**What it does:** Sends text to the AI and submits with Enter.

**How it works:**
- Sends command text via tmux
- **0.1s delay** (required for tmux to process text)
- Sends Enter key

**Configuration:**
```yaml
tmux:
  text_enter_delay: 0.1  # Delay between text and Enter (seconds)
```

**Why the delay?** This is a tmux limitation - we can't detect when tmux has processed the text, so a small fixed delay is necessary.

## Real-World Timing Recommendations

### Interactive Q&A
```python
timeout = 30  # Most responses complete in 5-15s
```

### Code Generation
```python
timeout = 60  # Writing code can take 20-40s
```

### File Operations
```python
timeout = 120  # Reading/writing files, especially large ones
```

### Complex Analysis
```python
timeout = 180  # Deep analysis, multiple files, refactoring
```

### Tool Execution (Gemini)
```python
timeout = 300  # External tools can be slow
```

## Configuration Best Practices

### 1. Set Generous Timeouts

```yaml
claude:
  startup_timeout: 20       # Was 10s, increased for reliability
  response_timeout: 30      # Adjust based on typical use case
```

**Why?** Network latency, system load, cold starts, and credential loading all add variability. Better to wait longer than fail prematurely.

### 2. Adjust Per Use Case

Don't use the same timeout for everything:

```python
# Create a helper function
def send_and_wait(controller, command, timeout=None):
    """Send command with appropriate timeout"""
    # Estimate complexity
    if len(command) < 50:
        timeout = timeout or 30
    elif "create" in command.lower() or "generate" in command.lower():
        timeout = timeout or 120
    else:
        timeout = timeout or 60

    controller.send_command(command)
    return controller.wait_for_ready(timeout=timeout)
```

### 3. Monitor and Log

```python
import time

start = time.time()
controller.send_command("Complex analysis task")
success = controller.wait_for_ready(timeout=120)
elapsed = time.time() - start

if success:
    logger.info(f"Response completed in {elapsed:.1f}s")
else:
    logger.warning(f"Timeout after {elapsed:.1f}s")
```

## Understanding Output Stabilization

`wait_for_ready()` considers output "stable" when:

1. Captures output at T=0
2. Waits 0.5s
3. Captures output at T=0.5
4. Compares: if identical, increment stable_count
5. Repeats until stable_count >= 3 (or timeout)

**Why 3 checks?** Prevents false positives from brief pauses in streaming output.

**Configuration:**
```yaml
ready_stable_checks: 3     # More = stricter, fewer = faster (but risky)
ready_check_interval: 0.5  # More frequent = faster detection, more CPU
```

## Common Pitfalls

### ❌ Don't do this:
```python
controller.send_command("Question 1")
time.sleep(10)  # Arbitrary delay - might be too short or too long
controller.send_command("Question 2")
```

### ✅ Do this instead:
```python
controller.send_command("Question 1")
controller.wait_for_ready(timeout=30)  # Observation-based
controller.send_command("Question 2")
```

### ❌ Don't assume fixed response times:
```python
# BAD: Assumes all responses take same time
for question in questions:
    controller.send_command(question)
    controller.wait_for_ready(timeout=30)  # Same timeout for all
```

### ✅ Adjust based on complexity:
```python
# GOOD: Different timeouts for different complexity
for question, expected_time in questions_with_estimates:
    controller.send_command(question)
    controller.wait_for_ready(timeout=expected_time * 2)  # 2x safety margin
```

## Debugging Timing Issues

### Enable Debug Logging

```yaml
logging:
  level: "DEBUG"
```

Look for:
- `"Waiting for startup ready indicators"`
- `"Checking for indicators in X chars of output"`
- `"Startup ready indicator found"`
- `"Ready indicator found but loading indicator still present"`

### Check What's Happening

```python
# Before command
before = controller.capture_output()
print(f"Before: {before[-200:]}")

# After command (before wait)
controller.send_command("Test")
time.sleep(1)
after_send = controller.capture_output()
print(f"After send: {after_send[-200:]}")

# After wait
controller.wait_for_ready()
after_ready = controller.capture_output()
print(f"After ready: {after_ready[-200:]}")
```

## Summary

✅ **Observation-based:** System detects actual ready states, not guessing with delays
✅ **Configurable:** All timeouts adjustable per use case
✅ **Safe defaults:** 20s startup, 30s response - works for most scenarios
✅ **Extensible:** Easy to add longer timeouts for complex operations
⚠️ **One unavoidable delay:** 0.1s between text and Enter (tmux limitation)
⚠️ **Stabilization delays:** 1-2s after startup (empirically necessary for input buffer)
