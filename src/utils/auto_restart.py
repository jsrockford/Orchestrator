"""
Auto-restart utilities for session recovery.

Provides mechanisms to automatically restart failed sessions with
configurable policies and backoff strategies.
"""
import time
import logging
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class RestartPolicy(Enum):
    """Restart policy options."""
    NEVER = "never"  # Never auto-restart
    ON_FAILURE = "on_failure"  # Restart only on unexpected failures
    ALWAYS = "always"  # Always attempt restart regardless of reason


@dataclass
class RestartAttempt:
    """Record of a restart attempt."""
    timestamp: datetime
    success: bool
    reason: str
    error_message: Optional[str] = None
    elapsed_time: float = 0.0


class AutoRestarter:
    """
    Manages automatic session restart with configurable policies.

    Tracks restart attempts, implements backoff strategies, and
    enforces restart limits to prevent infinite loops.
    """

    def __init__(
        self,
        policy: RestartPolicy = RestartPolicy.ON_FAILURE,
        max_restart_attempts: int = 3,
        restart_window: float = 300.0,  # 5 minutes
        initial_backoff: float = 5.0,
        max_backoff: float = 60.0,
        backoff_factor: float = 2.0
    ):
        """
        Initialize AutoRestarter.

        Args:
            policy: When to restart (NEVER, ON_FAILURE, ALWAYS)
            max_restart_attempts: Max restarts within window (default: 3)
            restart_window: Time window in seconds for counting attempts (default: 300)
            initial_backoff: Initial delay before first restart (default: 5.0s)
            max_backoff: Maximum delay between restarts (default: 60.0s)
            backoff_factor: Backoff multiplier (default: 2.0)
        """
        self.policy = policy
        self.max_restart_attempts = max_restart_attempts
        self.restart_window = restart_window
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.backoff_factor = backoff_factor

        # Track restart history
        self.restart_history: list[RestartAttempt] = []
        self.total_restarts = 0
        self.successful_restarts = 0
        self.failed_restarts = 0

    def should_restart(self, reason: str = "unknown") -> bool:
        """
        Determine if restart should be attempted based on policy and limits.

        Args:
            reason: Reason for potential restart

        Returns:
            True if restart should be attempted, False otherwise
        """
        if self.policy == RestartPolicy.NEVER:
            logger.info("Restart policy is NEVER - skipping restart")
            return False

        # Check if we've exceeded restart attempts within the window
        recent_attempts = self._get_recent_attempts()
        if len(recent_attempts) >= self.max_restart_attempts:
            logger.warning(
                f"Max restart attempts ({self.max_restart_attempts}) reached "
                f"within {self.restart_window}s window. Not restarting."
            )
            return False

        logger.info(f"Restart permitted: {len(recent_attempts)}/{self.max_restart_attempts} attempts used")
        return True

    def calculate_backoff(self) -> float:
        """
        Calculate backoff delay based on recent restart attempts.

        Returns:
            Delay in seconds before next restart attempt
        """
        recent_attempts = self._get_recent_attempts()

        if not recent_attempts:
            return self.initial_backoff

        # Exponential backoff based on number of recent attempts
        attempt_count = len(recent_attempts)
        delay = self.initial_backoff * (self.backoff_factor ** (attempt_count - 1))
        delay = min(delay, self.max_backoff)

        logger.debug(f"Calculated backoff delay: {delay:.2f}s (attempt {attempt_count})")
        return delay

    def attempt_restart(
        self,
        restart_func: Callable[[], bool],
        reason: str = "unknown",
        wait_before_restart: bool = True
    ) -> bool:
        """
        Attempt to restart session with backoff and tracking.

        Args:
            restart_func: Function that performs the restart (should return bool)
            reason: Reason for restart (for logging)
            wait_before_restart: If True, apply backoff delay before restart

        Returns:
            True if restart succeeded, False otherwise
        """
        if not self.should_restart(reason):
            return False

        # Apply backoff if requested
        if wait_before_restart:
            delay = self.calculate_backoff()
            logger.info(f"Waiting {delay:.2f}s before restart attempt (reason: {reason})")
            time.sleep(delay)

        # Attempt restart
        logger.info(f"Attempting restart (reason: {reason})")
        start_time = time.time()

        try:
            success = restart_func()
            elapsed = time.time() - start_time

            # Record attempt
            attempt = RestartAttempt(
                timestamp=datetime.now(),
                success=success,
                reason=reason,
                error_message=None if success else "Restart function returned False",
                elapsed_time=elapsed
            )

            self._record_attempt(attempt)

            if success:
                logger.info(f"Restart succeeded in {elapsed:.2f}s")
            else:
                logger.error(f"Restart failed after {elapsed:.2f}s")

            return success

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Restart failed with exception after {elapsed:.2f}s: {e}")

            # Record failed attempt
            attempt = RestartAttempt(
                timestamp=datetime.now(),
                success=False,
                reason=reason,
                error_message=str(e),
                elapsed_time=elapsed
            )

            self._record_attempt(attempt)
            return False

    def _get_recent_attempts(self) -> list[RestartAttempt]:
        """
        Get restart attempts within the configured time window.

        Returns:
            List of recent RestartAttempt objects
        """
        cutoff_time = datetime.now() - timedelta(seconds=self.restart_window)
        return [
            attempt for attempt in self.restart_history
            if attempt.timestamp >= cutoff_time
        ]

    def _record_attempt(self, attempt: RestartAttempt):
        """Record a restart attempt and update statistics."""
        self.restart_history.append(attempt)
        self.total_restarts += 1

        if attempt.success:
            self.successful_restarts += 1
        else:
            self.failed_restarts += 1

        # Keep only recent history (last 100 attempts)
        if len(self.restart_history) > 100:
            self.restart_history = self.restart_history[-100:]

    def get_stats(self) -> Dict[str, Any]:
        """
        Get restart statistics.

        Returns:
            Dictionary with restart metrics
        """
        recent_attempts = self._get_recent_attempts()

        success_rate = 0.0
        if self.total_restarts > 0:
            success_rate = self.successful_restarts / self.total_restarts

        return {
            "policy": self.policy.value,
            "total_restarts": self.total_restarts,
            "successful_restarts": self.successful_restarts,
            "failed_restarts": self.failed_restarts,
            "success_rate": success_rate,
            "recent_attempts_count": len(recent_attempts),
            "attempts_remaining": max(0, self.max_restart_attempts - len(recent_attempts)),
            "last_attempt": {
                "timestamp": self.restart_history[-1].timestamp.isoformat(),
                "success": self.restart_history[-1].success,
                "reason": self.restart_history[-1].reason,
                "elapsed_time": self.restart_history[-1].elapsed_time
            } if self.restart_history else None
        }

    def reset_history(self):
        """Reset restart history (useful after successful manual intervention)."""
        logger.info("Resetting restart history")
        self.restart_history.clear()

    def can_restart(self) -> bool:
        """
        Check if restart is currently allowed without attempting.

        Returns:
            True if restart would be allowed, False otherwise
        """
        if self.policy == RestartPolicy.NEVER:
            return False

        recent_attempts = self._get_recent_attempts()
        return len(recent_attempts) < self.max_restart_attempts
