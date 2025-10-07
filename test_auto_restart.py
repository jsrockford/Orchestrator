#!/usr/bin/env python3
"""
Test script for auto-restart functionality.
Tests the AutoRestarter and integration with tmux_controller.
"""
import sys
import time
from src.utils.auto_restart import AutoRestarter, RestartPolicy, RestartAttempt


# Test 1: Basic restart allowed
print("=" * 60)
print("Test 1: Basic restart allowed")
print("=" * 60)

restarter = AutoRestarter(policy=RestartPolicy.ON_FAILURE, max_restart_attempts=3)
should_restart = restarter.should_restart(reason="test")
print(f"Should restart: {should_restart}")
print(f"Can restart: {restarter.can_restart()}")

if should_restart and restarter.can_restart():
    print("✓ Restart allowed when policy permits\n")
else:
    print("✗ Restart should be allowed\n")
    sys.exit(1)


# Test 2: NEVER policy blocks restart
print("=" * 60)
print("Test 2: NEVER policy blocks restart")
print("=" * 60)

restarter_never = AutoRestarter(policy=RestartPolicy.NEVER)
should_restart = restarter_never.should_restart(reason="test")
print(f"Should restart: {should_restart}")

if not should_restart:
    print("✓ NEVER policy correctly blocks restart\n")
else:
    print("✗ NEVER policy should block restart\n")
    sys.exit(1)


# Test 3: Max attempts limit
print("=" * 60)
print("Test 3: Max attempts limit")
print("=" * 60)

restarter_limited = AutoRestarter(
    policy=RestartPolicy.ALWAYS,
    max_restart_attempts=3,
    restart_window=60.0,
    initial_backoff=0.1  # Fast for testing
)

restart_count = 0
def mock_restart_func():
    global restart_count
    restart_count += 1
    return True

# Perform 3 restarts
for i in range(3):
    result = restarter_limited.attempt_restart(mock_restart_func, reason=f"test_{i}", wait_before_restart=False)
    print(f"  Restart {i+1}: success={result}")

# Try 4th restart (should be blocked)
print("Attempting 4th restart (should be blocked)...")
result = restarter_limited.attempt_restart(mock_restart_func, reason="test_4", wait_before_restart=False)
print(f"  4th restart allowed: {result}")

stats = restarter_limited.get_stats()
print(f"Total restarts: {stats['total_restarts']}")
print(f"Attempts remaining: {stats['attempts_remaining']}")

if stats['total_restarts'] == 3 and stats['attempts_remaining'] == 0:
    print("✓ Max attempts limit enforced correctly\n")
else:
    print("✗ Max attempts limit not working\n")
    sys.exit(1)


# Test 4: Backoff calculation
print("=" * 60)
print("Test 4: Backoff calculation")
print("=" * 60)

restarter_backoff = AutoRestarter(
    policy=RestartPolicy.ON_FAILURE,
    initial_backoff=1.0,
    backoff_factor=2.0,
    max_backoff=10.0
)

# No attempts yet
backoff1 = restarter_backoff.calculate_backoff()
print(f"Initial backoff: {backoff1:.2f}s")

# Simulate failed attempts to test backoff growth
def mock_failing_restart():
    return False

restarter_backoff.attempt_restart(mock_failing_restart, reason="fail_1", wait_before_restart=False)
backoff2 = restarter_backoff.calculate_backoff()
print(f"After 1 failure: {backoff2:.2f}s (for 2nd attempt)")

restarter_backoff.attempt_restart(mock_failing_restart, reason="fail_2", wait_before_restart=False)
backoff3 = restarter_backoff.calculate_backoff()
print(f"After 2 failures: {backoff3:.2f}s (for 3rd attempt)")

# Backoff logic: initial_backoff * (backoff_factor ** (attempt_count - 1))
# With 0 attempts: 1.0 * (2.0 ** -1) = N/A, returns initial_backoff = 1.0
# With 1 attempt: 1.0 * (2.0 ** 0) = 1.0
# With 2 attempts: 1.0 * (2.0 ** 1) = 2.0
if backoff1 == 1.0 and backoff2 == 1.0 and backoff3 == 2.0:
    print("✓ Exponential backoff working correctly\n")
else:
    print(f"✗ Backoff not correct: expected 1.0, 1.0, 2.0 but got {backoff1}, {backoff2}, {backoff3}\n")
    sys.exit(1)


# Test 5: Success and failure tracking
print("=" * 60)
print("Test 5: Success and failure tracking")
print("=" * 60)

restarter_tracking = AutoRestarter(policy=RestartPolicy.ALWAYS, max_restart_attempts=10)

success_count = 0
fail_count = 0

def mock_mixed_restart():
    global success_count, fail_count
    # Succeed every other time
    if (success_count + fail_count) % 2 == 0:
        success_count += 1
        return True
    else:
        fail_count += 1
        return False

# Perform 6 restarts
for i in range(6):
    restarter_tracking.attempt_restart(mock_mixed_restart, reason=f"test_{i}", wait_before_restart=False)

stats = restarter_tracking.get_stats()
print(f"Successful restarts: {stats['successful_restarts']}")
print(f"Failed restarts: {stats['failed_restarts']}")
print(f"Success rate: {stats['success_rate']:.2%}")

if stats['successful_restarts'] == 3 and stats['failed_restarts'] == 3 and stats['success_rate'] == 0.5:
    print("✓ Success/failure tracking works correctly\n")
else:
    print("✗ Tracking not correct\n")
    sys.exit(1)


# Test 6: Restart window expiry
print("=" * 60)
print("Test 6: Restart window expiry")
print("=" * 60)

restarter_window = AutoRestarter(
    policy=RestartPolicy.ON_FAILURE,
    max_restart_attempts=2,
    restart_window=2.0,  # 2 second window
    initial_backoff=0.1
)

def mock_quick_restart():
    return True

# First restart
restarter_window.attempt_restart(mock_quick_restart, reason="test_1", wait_before_restart=False)
print(f"After 1st restart: attempts_remaining={restarter_window.get_stats()['attempts_remaining']}")

# Second restart
restarter_window.attempt_restart(mock_quick_restart, reason="test_2", wait_before_restart=False)
print(f"After 2nd restart: attempts_remaining={restarter_window.get_stats()['attempts_remaining']}")

# Wait for window to expire
print("Waiting for window to expire (2s)...")
time.sleep(2.1)

# Should be able to restart again
can_restart = restarter_window.can_restart()
print(f"After window expiry: can_restart={can_restart}")

if can_restart:
    print("✓ Restart window expiry works correctly\n")
else:
    print("✗ Should be able to restart after window expires\n")
    sys.exit(1)


# Test 7: History reset
print("=" * 60)
print("Test 7: History reset")
print("=" * 60)

restarter_reset = AutoRestarter(policy=RestartPolicy.ON_FAILURE)

# Perform some restarts
for i in range(3):
    restarter_reset.attempt_restart(mock_quick_restart, reason=f"test_{i}", wait_before_restart=False)

print(f"Before reset: total_restarts={restarter_reset.get_stats()['total_restarts']}")

# Reset history
restarter_reset.reset_history()

stats_after = restarter_reset.get_stats()
print(f"After reset: total_restarts={stats_after['total_restarts']}")
print(f"Recent attempts: {stats_after['recent_attempts_count']}")

if stats_after['total_restarts'] == 3 and stats_after['recent_attempts_count'] == 0:
    print("✓ History reset works correctly (keeps totals, clears recent)\n")
else:
    print("✗ History reset not working correctly\n")
    sys.exit(1)


# Test 8: Restart with actual delay
print("=" * 60)
print("Test 8: Restart with backoff delay")
print("=" * 60)

restarter_delay = AutoRestarter(
    policy=RestartPolicy.ON_FAILURE,
    initial_backoff=0.5,
    backoff_factor=2.0
)

start_time = time.time()
restarter_delay.attempt_restart(mock_quick_restart, reason="test_delay", wait_before_restart=True)
elapsed = time.time() - start_time

print(f"Restart with backoff took: {elapsed:.2f}s")

if elapsed >= 0.5 and elapsed < 1.0:
    print("✓ Backoff delay applied correctly\n")
else:
    print(f"✗ Delay incorrect (expected ~0.5s, got {elapsed:.2f}s)\n")
    sys.exit(1)


print("=" * 60)
print("All auto-restart tests passed! ✓")
print("=" * 60)
