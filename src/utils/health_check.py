"""
Health check utilities for monitoring session state and responsiveness.

Provides mechanisms to periodically verify sessions are alive and responsive.
"""
import time
import logging
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Results from a health check operation."""
    healthy: bool
    timestamp: datetime
    check_type: str
    details: Dict[str, Any]
    error_message: Optional[str] = None


class HealthChecker:
    """
    Monitors session health with configurable checks and thresholds.

    Supports various health check strategies:
    - Session existence (tmux session still running)
    - Output responsiveness (session producing output)
    - Command echo (session responding to test commands)
    """

    def __init__(
        self,
        check_interval: float = 30.0,
        response_timeout: float = 5.0,
        max_failed_checks: int = 3
    ):
        """
        Initialize HealthChecker.

        Args:
            check_interval: Seconds between health checks (default: 30)
            response_timeout: Seconds to wait for health check response (default: 5)
            max_failed_checks: Number of consecutive failures before unhealthy (default: 3)
        """
        self.check_interval = check_interval
        self.response_timeout = response_timeout
        self.max_failed_checks = max_failed_checks

        # Track health check history
        self.last_check: Optional[datetime] = None
        self.last_result: Optional[HealthCheckResult] = None
        self.consecutive_failures = 0
        self.total_checks = 0
        self.total_failures = 0

    def should_check(self) -> bool:
        """
        Determine if a health check should be performed based on interval.

        Returns:
            True if enough time has passed since last check
        """
        if self.last_check is None:
            return True

        elapsed = (datetime.now() - self.last_check).total_seconds()
        return elapsed >= self.check_interval

    def check_session_exists(self, session_exists_func: Callable[[], bool]) -> HealthCheckResult:
        """
        Check if session exists (basic liveness check).

        Args:
            session_exists_func: Function that returns True if session exists

        Returns:
            HealthCheckResult with check outcome
        """
        start_time = time.time()

        try:
            exists = session_exists_func()
            elapsed = time.time() - start_time

            result = HealthCheckResult(
                healthy=exists,
                timestamp=datetime.now(),
                check_type="session_exists",
                details={
                    "elapsed_time": elapsed,
                    "exists": exists
                },
                error_message=None if exists else "Session does not exist"
            )

            self._record_result(result)
            return result

        except Exception as e:
            logger.error(f"Health check failed with exception: {e}")
            result = HealthCheckResult(
                healthy=False,
                timestamp=datetime.now(),
                check_type="session_exists",
                details={"error": str(e)},
                error_message=f"Exception during check: {e}"
            )
            self._record_result(result)
            return result

    def check_output_responsive(
        self,
        capture_func: Callable[[], str],
        min_output_length: int = 10
    ) -> HealthCheckResult:
        """
        Check if session is producing output (responsiveness check).

        Args:
            capture_func: Function that captures current output
            min_output_length: Minimum characters expected (default: 10)

        Returns:
            HealthCheckResult with check outcome
        """
        start_time = time.time()

        try:
            output = capture_func()
            elapsed = time.time() - start_time

            # Check if we got meaningful output
            has_output = len(output) >= min_output_length

            result = HealthCheckResult(
                healthy=has_output,
                timestamp=datetime.now(),
                check_type="output_responsive",
                details={
                    "elapsed_time": elapsed,
                    "output_length": len(output),
                    "min_required": min_output_length
                },
                error_message=None if has_output else f"Insufficient output: {len(output)} < {min_output_length}"
            )

            self._record_result(result)
            return result

        except Exception as e:
            logger.error(f"Output check failed with exception: {e}")
            result = HealthCheckResult(
                healthy=False,
                timestamp=datetime.now(),
                check_type="output_responsive",
                details={"error": str(e)},
                error_message=f"Exception during check: {e}"
            )
            self._record_result(result)
            return result

    def check_command_echo(
        self,
        send_command_func: Callable[[str], bool],
        wait_func: Callable[[Optional[float]], bool],
        capture_func: Callable[[], str],
        test_command: str = "# health_check"
    ) -> HealthCheckResult:
        """
        Check if session can execute a test command (full responsiveness check).

        Args:
            send_command_func: Function to send command
            wait_func: Function to wait for response
            capture_func: Function to capture output
            test_command: Safe test command to send (default: comment)

        Returns:
            HealthCheckResult with check outcome
        """
        start_time = time.time()

        try:
            # Send test command (should be harmless like a comment)
            send_success = send_command_func(test_command)
            if not send_success:
                result = HealthCheckResult(
                    healthy=False,
                    timestamp=datetime.now(),
                    check_type="command_echo",
                    details={"stage": "send_failed"},
                    error_message="Failed to send test command"
                )
                self._record_result(result)
                return result

            # Wait for response
            ready = wait_func(self.response_timeout)
            elapsed = time.time() - start_time

            if not ready:
                result = HealthCheckResult(
                    healthy=False,
                    timestamp=datetime.now(),
                    check_type="command_echo",
                    details={
                        "stage": "timeout",
                        "elapsed_time": elapsed,
                        "timeout": self.response_timeout
                    },
                    error_message=f"Timeout waiting for response ({self.response_timeout}s)"
                )
                self._record_result(result)
                return result

            # Capture output to verify command was processed
            output = capture_func()
            command_found = test_command in output

            result = HealthCheckResult(
                healthy=command_found,
                timestamp=datetime.now(),
                check_type="command_echo",
                details={
                    "elapsed_time": elapsed,
                    "test_command": test_command,
                    "command_found": command_found,
                    "output_length": len(output)
                },
                error_message=None if command_found else "Test command not found in output"
            )

            self._record_result(result)
            return result

        except Exception as e:
            logger.error(f"Command echo check failed with exception: {e}")
            result = HealthCheckResult(
                healthy=False,
                timestamp=datetime.now(),
                check_type="command_echo",
                details={"error": str(e)},
                error_message=f"Exception during check: {e}"
            )
            self._record_result(result)
            return result

    def _record_result(self, result: HealthCheckResult):
        """Record health check result and update statistics."""
        self.last_check = result.timestamp
        self.last_result = result
        self.total_checks += 1

        if not result.healthy:
            self.consecutive_failures += 1
            self.total_failures += 1
            logger.warning(
                f"Health check failed ({result.check_type}): {result.error_message}. "
                f"Consecutive failures: {self.consecutive_failures}/{self.max_failed_checks}"
            )
        else:
            if self.consecutive_failures > 0:
                logger.info(f"Health check recovered after {self.consecutive_failures} failures")
            self.consecutive_failures = 0
            logger.debug(f"Health check passed ({result.check_type})")

    def is_healthy(self) -> bool:
        """
        Determine overall health status.

        Returns:
            False if consecutive failures exceed threshold, True otherwise
        """
        return self.consecutive_failures < self.max_failed_checks

    def get_stats(self) -> Dict[str, Any]:
        """
        Get health check statistics.

        Returns:
            Dictionary with health check metrics
        """
        success_rate = 0.0
        if self.total_checks > 0:
            success_rate = (self.total_checks - self.total_failures) / self.total_checks

        return {
            "total_checks": self.total_checks,
            "total_failures": self.total_failures,
            "consecutive_failures": self.consecutive_failures,
            "success_rate": success_rate,
            "is_healthy": self.is_healthy(),
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "last_result": {
                "healthy": self.last_result.healthy,
                "check_type": self.last_result.check_type,
                "error": self.last_result.error_message
            } if self.last_result else None
        }

    def reset(self):
        """Reset health check state (useful after recovery actions)."""
        logger.info("Resetting health check state")
        self.consecutive_failures = 0
        # Keep total_checks and total_failures for historical tracking
