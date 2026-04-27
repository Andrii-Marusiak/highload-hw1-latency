"""Latency collector and percentile summariser.

Used by the short real-time benchmark in ``simulator.service`` to
report p50/p95/p99 latency and the observed cache hit rate, which
should track ``infra.cache_hit_ratio`` from the config (a sanity check
that the cache simulator is wired correctly).
"""

from __future__ import annotations

import statistics
import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class LatencySummary:
    count: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    cache_hits: int
    cache_misses: int
    observed_hit_rate: float


class MetricsCollector:
    """Thread-safe collector for per-request latencies and cache events."""

    def __init__(self) -> None:
        self._latencies: list[float] = []
        self._cache_hits = 0
        self._cache_misses = 0
        self._lock = threading.Lock()

    def record(self, latency_ms: float, cache_hit: bool | None = None) -> None:
        with self._lock:
            self._latencies.append(latency_ms)
            if cache_hit is True:
                self._cache_hits += 1
            elif cache_hit is False:
                self._cache_misses += 1

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._latencies)

    def summary(self) -> LatencySummary:
        with self._lock:
            if not self._latencies:
                return LatencySummary(
                    count=0,
                    mean_ms=0.0,
                    p50_ms=0.0,
                    p95_ms=0.0,
                    p99_ms=0.0,
                    cache_hits=self._cache_hits,
                    cache_misses=self._cache_misses,
                    observed_hit_rate=0.0,
                )

            sorted_lat = sorted(self._latencies)
            n = len(sorted_lat)
            p50 = sorted_lat[min(int(n * 0.50), n - 1)]
            p95 = sorted_lat[min(int(n * 0.95), n - 1)]
            p99 = sorted_lat[min(int(n * 0.99), n - 1)]
            mean = statistics.mean(sorted_lat)

            total_decisions = self._cache_hits + self._cache_misses
            hit_rate = (
                self._cache_hits / total_decisions if total_decisions > 0 else 0.0
            )

            return LatencySummary(
                count=n,
                mean_ms=mean,
                p50_ms=p50,
                p95_ms=p95,
                p99_ms=p99,
                cache_hits=self._cache_hits,
                cache_misses=self._cache_misses,
                observed_hit_rate=hit_rate,
            )

    def reset(self) -> None:
        with self._lock:
            self._latencies.clear()
            self._cache_hits = 0
            self._cache_misses = 0
