"""Retry utilities with exponential backoff."""

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryError(Exception):
    """Raised when all retry attempts are exhausted."""

    def __init__(self, message: str, last_exception: Exception | None = None):
        super().__init__(message)
        self.last_exception = last_exception


async def retry_async(
    func: Callable[..., Awaitable[T]],
    *args,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    on_retry: Callable[[int, Exception, float], None] | None = None,
    **kwargs,
) -> T:
    """Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        *args: Positional arguments for func
        max_attempts: Maximum retry attempts (default: 3)
        base_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay between retries (default: 60.0)
        exponential_base: Base for exponential backoff (default: 2.0)
        jitter: Add random jitter to delays (default: True)
        exceptions: Tuple of exceptions to catch and retry
        on_retry: Optional callback(attempt, exception, delay) called before each retry
        **kwargs: Keyword arguments for func

    Returns:
        Result of func

    Raises:
        RetryError: If all attempts fail
    """
    last_exception: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_exception = e

            if attempt >= max_attempts:
                break

            # Calculate delay with exponential backoff
            delay = min(base_delay * (exponential_base ** (attempt - 1)), max_delay)

            # Add jitter (0-25% of delay)
            if jitter:
                delay = delay * (1 + random.uniform(0, 0.25))

            logger.warning(
                f"Attempt {attempt}/{max_attempts} failed: {e}. Retrying in {delay:.1f}s..."
            )

            if on_retry:
                on_retry(attempt, e, delay)

            await asyncio.sleep(delay)

    raise RetryError(
        f"All {max_attempts} attempts failed",
        last_exception=last_exception,
    )


def retry_sync(
    func: Callable[..., T],
    *args,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    on_retry: Callable[[int, Exception, float], None] | None = None,
    **kwargs,
) -> T:
    """Retry a sync function with exponential backoff.

    Same parameters as retry_async but for synchronous functions.
    """
    import time

    last_exception: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except exceptions as e:
            last_exception = e

            if attempt >= max_attempts:
                break

            delay = min(base_delay * (exponential_base ** (attempt - 1)), max_delay)

            if jitter:
                delay = delay * (1 + random.uniform(0, 0.25))

            logger.warning(
                f"Attempt {attempt}/{max_attempts} failed: {e}. Retrying in {delay:.1f}s..."
            )

            if on_retry:
                on_retry(attempt, e, delay)

            time.sleep(delay)

    raise RetryError(
        f"All {max_attempts} attempts failed",
        last_exception=last_exception,
    )


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """Decorator for async functions with retry logic.

    Args:
        max_attempts: Maximum retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        exceptions: Tuple of exceptions to catch and retry

    Example:
        @with_retry(max_attempts=3, exceptions=(httpx.TimeoutException,))
        async def fetch_data(url: str):
            ...
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await retry_async(
                func,
                *args,
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                exceptions=exceptions,
                **kwargs,
            )

        return wrapper

    return decorator


def with_retry_sync(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """Decorator for sync functions with retry logic.

    Same parameters as with_retry but for synchronous functions.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return retry_sync(
                func,
                *args,
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                exceptions=exceptions,
                **kwargs,
            )

        return wrapper

    return decorator


class CircuitBreaker:
    """Simple circuit breaker for protecting against cascading failures.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failing, requests are rejected immediately
    - HALF_OPEN: Testing if service recovered

    Example:
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30)

        async def call_api():
            if not breaker.allow_request():
                raise CircuitBreakerOpen("Service unavailable")
            try:
                result = await api_call()
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying half-open
            half_open_max_calls: Max calls allowed in half-open state
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._half_open_calls = 0

    @property
    def state(self) -> str:
        """Get current circuit state."""
        return self._state

    def allow_request(self) -> bool:
        """Check if request should be allowed.

        Returns:
            True if request can proceed, False if circuit is open
        """
        import time

        if self._state == self.CLOSED:
            return True

        if self._state == self.OPEN:
            # Check if recovery timeout has passed
            if self._last_failure_time:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = self.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info("Circuit breaker entering half-open state")
                    return True
            return False

        if self._state == self.HALF_OPEN:
            # Allow limited calls in half-open state
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False

        return True

    def record_success(self):
        """Record a successful call."""
        if self._state == self.HALF_OPEN:
            # Success in half-open state closes the circuit
            self._state = self.CLOSED
            self._failure_count = 0
            logger.info("Circuit breaker closed after successful call")
        elif self._state == self.CLOSED:
            # Reset failure count on success
            self._failure_count = 0

    def record_failure(self):
        """Record a failed call."""
        import time

        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == self.HALF_OPEN:
            # Failure in half-open state opens the circuit again
            self._state = self.OPEN
            logger.warning("Circuit breaker reopened after failure in half-open state")
        elif self._state == self.CLOSED:
            if self._failure_count >= self.failure_threshold:
                self._state = self.OPEN
                logger.warning(f"Circuit breaker opened after {self._failure_count} failures")

    def reset(self):
        """Reset circuit breaker to closed state."""
        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open and rejecting requests."""

    pass
