#!/usr/bin/env python3
"""
Test script for health check functionality.
Tests the HealthChecker and integration with tmux_controller.
"""
import sys
import time
from src.utils.health_check import HealthChecker, HealthCheckResult


# Test 1: Basic session exists check
print("=" * 60)
print("Test 1: Basic session exists check")
print("=" * 60)

checker = HealthChecker(check_interval=5.0, max_failed_checks=3)

# Simulate healthy session
def mock_session_exists_healthy():
    return True

result = checker.check_session_exists(mock_session_exists_healthy)
print(f"Check type: {result.check_type}")
print(f"Healthy: {result.healthy}")
print(f"Consecutive failures: {checker.consecutive_failures}")
print(f"Is healthy: {checker.is_healthy()}")

if result.healthy and checker.is_healthy():
    print("✓ Session exists check passed\n")
else:
    print("✗ Session exists check failed\n")
    sys.exit(1)


# Test 2: Failed session check
print("=" * 60)
print("Test 2: Failed session check")
print("=" * 60)

def mock_session_exists_dead():
    return False

result = checker.check_session_exists(mock_session_exists_dead)
print(f"Healthy: {result.healthy}")
print(f"Error: {result.error_message}")
print(f"Consecutive failures: {checker.consecutive_failures}")
print(f"Is healthy: {checker.is_healthy()}")

if not result.healthy and result.error_message == "Session does not exist":
    print("✓ Failed session detected correctly\n")
else:
    print("✗ Failed session not detected\n")
    sys.exit(1)


# Test 3: Consecutive failure threshold
print("=" * 60)
print("Test 3: Consecutive failure threshold")
print("=" * 60)

checker2 = HealthChecker(max_failed_checks=3)

print("Failing 3 consecutive checks...")
for i in range(3):
    result = checker2.check_session_exists(mock_session_exists_dead)
    print(f"  Check {i+1}: failures={checker2.consecutive_failures}, healthy={checker2.is_healthy()}")

if not checker2.is_healthy():
    print("✓ Unhealthy status after threshold exceeded\n")
else:
    print("✗ Should be unhealthy after 3 failures\n")
    sys.exit(1)


# Test 4: Recovery after failure
print("=" * 60)
print("Test 4: Recovery after failure")
print("=" * 60)

checker3 = HealthChecker(max_failed_checks=3)

# Fail twice
for i in range(2):
    checker3.check_session_exists(mock_session_exists_dead)
print(f"After 2 failures: consecutive={checker3.consecutive_failures}, healthy={checker3.is_healthy()}")

# Then succeed
result = checker3.check_session_exists(mock_session_exists_healthy)
print(f"After recovery: consecutive={checker3.consecutive_failures}, healthy={checker3.is_healthy()}")

if checker3.consecutive_failures == 0 and checker3.is_healthy():
    print("✓ Recovery from failures works correctly\n")
else:
    print("✗ Recovery failed\n")
    sys.exit(1)


# Test 5: Output responsive check
print("=" * 60)
print("Test 5: Output responsive check")
print("=" * 60)

checker4 = HealthChecker()

def mock_capture_good_output():
    return "This is sufficient output for the health check"

def mock_capture_insufficient_output():
    return "Short"

result = checker4.check_output_responsive(mock_capture_good_output, min_output_length=10)
print(f"Good output - Healthy: {result.healthy}, length: {result.details['output_length']}")

result = checker4.check_output_responsive(mock_capture_insufficient_output, min_output_length=10)
print(f"Insufficient output - Healthy: {result.healthy}, length: {result.details['output_length']}")
print(f"Error: {result.error_message}")

if result.error_message and "Insufficient output" in result.error_message:
    print("✓ Output responsive check works correctly\n")
else:
    print("✗ Output responsive check failed\n")
    sys.exit(1)


# Test 6: Command echo check
print("=" * 60)
print("Test 6: Command echo check")
print("=" * 60)

checker5 = HealthChecker(response_timeout=2.0)

def mock_send_command(cmd):
    return True

def mock_wait_ready(timeout):
    time.sleep(0.1)  # Simulate brief processing
    return True

def mock_capture_with_echo():
    return "Previous output\n# health_check\nMore output"

result = checker5.check_command_echo(
    send_command_func=mock_send_command,
    wait_func=mock_wait_ready,
    capture_func=mock_capture_with_echo,
    test_command="# health_check"
)

print(f"Healthy: {result.healthy}")
print(f"Command found: {result.details.get('command_found')}")
print(f"Elapsed: {result.details.get('elapsed_time'):.3f}s")

if result.healthy and result.details.get('command_found'):
    print("✓ Command echo check works correctly\n")
else:
    print("✗ Command echo check failed\n")
    sys.exit(1)


# Test 7: Health check statistics
print("=" * 60)
print("Test 7: Health check statistics")
print("=" * 60)

checker6 = HealthChecker()

# Perform mix of checks
checker6.check_session_exists(mock_session_exists_healthy)
checker6.check_session_exists(mock_session_exists_healthy)
checker6.check_session_exists(mock_session_exists_dead)
checker6.check_session_exists(mock_session_exists_healthy)

stats = checker6.get_stats()
print(f"Total checks: {stats['total_checks']}")
print(f"Total failures: {stats['total_failures']}")
print(f"Success rate: {stats['success_rate']:.2%}")
print(f"Consecutive failures: {stats['consecutive_failures']}")
print(f"Is healthy: {stats['is_healthy']}")

if stats['total_checks'] == 4 and stats['total_failures'] == 1 and stats['success_rate'] == 0.75:
    print("✓ Statistics tracking works correctly\n")
else:
    print("✗ Statistics tracking failed\n")
    sys.exit(1)


# Test 8: Should check interval
print("=" * 60)
print("Test 8: Should check interval")
print("=" * 60)

checker7 = HealthChecker(check_interval=1.0)

# First check should always run
should_check1 = checker7.should_check()
print(f"Before any check: should_check={should_check1}")

# Run a check
checker7.check_session_exists(mock_session_exists_healthy)

# Immediately after, should not check
should_check2 = checker7.should_check()
print(f"Immediately after check: should_check={should_check2}")

# Wait for interval
time.sleep(1.1)
should_check3 = checker7.should_check()
print(f"After interval: should_check={should_check3}")

if should_check1 and not should_check2 and should_check3:
    print("✓ Check interval logic works correctly\n")
else:
    print("✗ Check interval logic failed\n")
    sys.exit(1)


print("=" * 60)
print("All health check tests passed! ✓")
print("=" * 60)
