"""Fixed-window counter keyed by API-key fingerprint.

`limit <= 0` disables the limiter. The window clock is injectable so tests
do not sleep.
"""

import time
from collections import deque
from threading import Lock


class RateLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: float = 60.0,
        max_buckets: int = 4096,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_buckets = max_buckets
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def allow(self, bucket: str, *, now: float | None = None) -> bool:
        if self.limit <= 0:
            return True
        moment = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits.get(bucket)
            if hits is None:
                if len(self._hits) >= self.max_buckets:
                    oldest = next(iter(self._hits))
                    self._hits.pop(oldest, None)
                hits = deque()
                self._hits[bucket] = hits
            cutoff = moment - self.window_seconds
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(moment)
            return True
