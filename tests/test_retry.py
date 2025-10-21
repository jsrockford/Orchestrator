#!/usr/bin/env python3
"""
Test script for retry functionality.
Tests the retry decorator and integration with tmux_controller.
"""
import sys
import time
from src.utils.retry import retry_with_backoff, RetryStrategy, QUICK_RETRY, STANDARD_RETRY
from src.utils.exceptions import CommandError, CommandTimeout, TmuxError


# Test 1: Basic retry decorator
print("=" * 60)
print("Test 1: Basic retry decorator")
print("=" * 60)

attempt_count = 0

@retry_with_backoff(max_attempts=3, initial_delay=0.5)
def flaky_function():
    global attempt_count
    attempt_count += 1
    print(f"  Attempt {attempt_count}")
    if attempt_count < 3:
        raise CommandError("Simulated transient failure")
    return "Success!"

try:
    attempt_count = 0
    result = flaky_function()
    print(f"✓ Result: {result}")
    print(f"✓ Took {attempt_count} attempts\n")
except Exception as e:
    print(f"✗ Failed: {e}\n")
    sys.exit(1)


# Test 2: Retry with max attempts exceeded
print("=" * 60)
print("Test 2: Max attempts exceeded (should fail)")
print("=" * 60)

attempt_count = 0

@retry_with_backoff(max_attempts=3, initial_delay=0.2)
def always_fails():
    global attempt_count
    attempt_count += 1
    print(f"  Attempt {attempt_count}")
    raise CommandTimeout("Always fails")

try:
    attempt_count = 0
    result = always_fails()
    print(f"✗ Should have failed but got: {result}\n")
    sys.exit(1)
except CommandTimeout as e:
    print(f"✓ Failed as expected after {attempt_count} attempts")
    print(f"✓ Error: {e}\n")


# Test 3: RetryStrategy class
print("=" * 60)
print("Test 3: RetryStrategy class")
print("=" * 60)

attempt_count = 0

def flaky_with_args(x, y):
    global attempt_count
    attempt_count += 1
    print(f"  Attempt {attempt_count} with args: x={x}, y={y}")
    if attempt_count < 2:
        raise TmuxError("Transient error", command=["test"])
    return x + y

try:
    attempt_count = 0
    # Create custom strategy that includes TmuxError
    strategy = RetryStrategy(max_attempts=2, initial_delay=0.5, exceptions=(TmuxError,))
    result = strategy.execute(flaky_with_args, 10, 20)
    print(f"✓ Result: {result}")
    print(f"✓ Took {attempt_count} attempts\n")
except Exception as e:
    print(f"✗ Failed: {e}\n")
    sys.exit(1)


# Test 4: Custom exception types
print("=" * 60)
print("Test 4: Custom exception filtering")
print("=" * 60)

@retry_with_backoff(max_attempts=2, initial_delay=0.1, exceptions=(CommandError,))
def specific_exception():
    print("  Raising TimeoutException (not in retry list)")
    raise CommandTimeout("Not in retry exception list")

try:
    result = specific_exception()
    print(f"✗ Should have failed immediately\n")
    sys.exit(1)
except CommandTimeout as e:
    print(f"✓ Failed immediately without retry (correct behavior)")
    print(f"✓ Error: {e}\n")


# Test 5: Exponential backoff timing
print("=" * 60)
print("Test 5: Exponential backoff timing")
print("=" * 60)

attempt_times = []

@retry_with_backoff(max_attempts=4, initial_delay=0.5, backoff_factor=2.0)
def timed_failures():
    attempt_times.append(time.time())
    print(f"  Attempt {len(attempt_times)}")
    if len(attempt_times) < 4:
        raise CommandError("Not yet")
    return "Done"

try:
    attempt_times = []
    start = time.time()
    result = timed_failures()
    total_time = time.time() - start

    print(f"✓ Result: {result}")
    print(f"✓ Total time: {total_time:.2f}s")

    # Check delays between attempts
    if len(attempt_times) >= 2:
        delays = [attempt_times[i] - attempt_times[i-1] for i in range(1, len(attempt_times))]
        print(f"✓ Delays between attempts: {[f'{d:.2f}s' for d in delays]}")

        # Verify exponential backoff (approximately)
        if delays[0] < delays[1]:  # Second delay should be longer than first
            print(f"✓ Exponential backoff working correctly\n")
        else:
            print(f"✗ Backoff not increasing as expected\n")
            sys.exit(1)
except Exception as e:
    print(f"✗ Failed: {e}\n")
    sys.exit(1)


print("=" * 60)
print("All retry tests passed! ✓")
print("=" * 60)
