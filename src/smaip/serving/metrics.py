"""In-process serving counters."""

from threading import Lock


class Metrics:
    def __init__(self) -> None:
        self.requests_total = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.latency_ms_sum = 0.0
        self.completions_by_engine: dict[str, int] = {}
        self._lock = Lock()

    def record(self, *, engine: str, cache_status: str, latency_ms: float) -> None:
        with self._lock:
            self.requests_total += 1
            self.latency_ms_sum += latency_ms
            self.completions_by_engine[engine] = self.completions_by_engine.get(engine, 0) + 1
            if cache_status == "hit":
                self.cache_hits += 1
            else:
                self.cache_misses += 1

    def snapshot(self) -> dict:
        with self._lock:
            looked = self.cache_hits + self.cache_misses
            rate = (self.cache_hits / looked) if looked else 0.0
            return {
                "requests_total": self.requests_total,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "cache_hit_rate": rate,
                "latency_ms_sum": self.latency_ms_sum,
                "completions_by_engine": dict(self.completions_by_engine),
                "engine_default": "mock",
                "gpu": False,
            }

    def prometheus(self) -> str:
        snap = self.snapshot()
        lines = [
            "# TYPE smaip_requests_total counter",
            f"smaip_requests_total {snap['requests_total']}",
            "# TYPE smaip_cache_hits counter",
            f"smaip_cache_hits {snap['cache_hits']}",
            "# TYPE smaip_cache_misses counter",
            f"smaip_cache_misses {snap['cache_misses']}",
            "# TYPE smaip_cache_hit_rate gauge",
            f"smaip_cache_hit_rate {snap['cache_hit_rate']}",
        ]
        return "\n".join(lines) + "\n"
