"""In-memory sliding-window rate limiter for authentication endpoints."""

import threading
import time
from collections import defaultdict, deque


class InMemoryRateLimiter:
    """Thread-safe sliding-window rate limiter keyed by client/account."""

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check_and_record(self, key: str) -> tuple[bool, int]:
        """Record an attempt and return (allowed, retry_after_seconds)."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._attempts[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self.max_attempts:
                retry_after = max(1, int(bucket[0] + self.window_seconds - now) + 1)
                return False, retry_after

            bucket.append(now)
            return True, 0

    def reset(self) -> None:
        """Clear all recorded attempts (for isolated testing)."""
        with self._lock:
            self._attempts.clear()


_login_limiter: InMemoryRateLimiter | None = None


def get_login_rate_limiter(
    max_attempts: int,
    window_seconds: int,
) -> InMemoryRateLimiter:
    """Return singleton login rate limiter configured from settings."""
    global _login_limiter
    if (
        _login_limiter is None
        or _login_limiter.max_attempts != max_attempts
        or _login_limiter.window_seconds != window_seconds
    ):
        _login_limiter = InMemoryRateLimiter(max_attempts, window_seconds)
    return _login_limiter
