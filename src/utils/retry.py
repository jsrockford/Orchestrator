"""
Retry utilities with exponential backoff for handling transient failures.
"""
import time
import logging
from functools import wraps
from typing import Callable, Type, Tuple, Optional

from .exceptions import SessionError, CommandError, CommandTimeout

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 10.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (SessionError, CommandError, CommandTimeout)
):
    """
    Decorator that retries a function with exponential backoff on specified exceptions.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds before first retry (default: 1.0)
        max_delay: Maximum delay between retries in seconds (default: 10.0)
        backoff_factor: Multiplier for delay after each retry (default: 2.0)
        exceptions: Tuple of exception types to catch and retry (default: Session/Command/Timeout)

    Returns:
        Decorated function that implements retry logic

    Example:
        @retry_with_backoff(max_attempts=3, initial_delay=2.0)
        def unstable_operation():
            # May fail transiently
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts. "
                            f"Last error: {str(e)}"
                        )
                        raise

                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt}/{max_attempts}). "
                        f"Retrying in {delay:.2f}s. Error: {str(e)}"
                    )

                    time.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


class RetryStrategy:
    """
    Configurable retry strategy for more complex retry scenarios.
    """

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 10.0,
        backoff_factor: float = 2.0,
        exceptions: Optional[Tuple[Type[Exception], ...]] = None
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.exceptions = exceptions or (SessionError, CommandError, CommandTimeout)

    def execute(self, func: Callable, *args, **kwargs):
        """
        Execute a function with retry logic.

        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result of the function execution

        Raises:
            Last exception encountered if all retries fail
        """
        delay = self.initial_delay
        last_exception = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except self.exceptions as e:
                last_exception = e

                if attempt == self.max_attempts:
                    logger.error(
                        f"Function {func.__name__} failed after {self.max_attempts} attempts. "
                        f"Last error: {str(e)}"
                    )
                    raise

                logger.warning(
                    f"Function {func.__name__} failed (attempt {attempt}/{self.max_attempts}). "
                    f"Retrying in {delay:.2f}s. Error: {str(e)}"
                )

                time.sleep(delay)
                delay = min(delay * self.backoff_factor, self.max_delay)

        if last_exception:
            raise last_exception


# Predefined retry strategies for common scenarios
QUICK_RETRY = RetryStrategy(max_attempts=2, initial_delay=0.5, max_delay=2.0)
STANDARD_RETRY = RetryStrategy(max_attempts=3, initial_delay=1.0, max_delay=10.0)
PERSISTENT_RETRY = RetryStrategy(max_attempts=5, initial_delay=2.0, max_delay=30.0)
