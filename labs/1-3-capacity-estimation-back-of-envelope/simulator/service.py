"""Short real-time benchmark.

Runs ``benchmark.sample_requests`` requests through a thread pool with
``time.sleep``-based service times that depend on whether the request
is a read with a cache hit, a read with a cache miss (storage path),
or a write (storage path with extra cost).  This gives the lab real
p50 / p95 / p99 numbers that move when students change the cache hit
ratio or service-time-related parameters.

The sleeps include +/-25% jitter so the latency distribution has a
realistic tail rather than collapsing onto a single value.
"""

from __future__ import annotations

import random
import time
from concurrent.futures import ThreadPoolExecutor

from simulator.cache import SeededCache
from simulator.config import Config
from simulator.metrics import LatencySummary, MetricsCollector
from simulator.workload import WorkloadProfile


WRITE_PATH_MULTIPLIER = 1.5
JITTER_MIN = 0.75
JITTER_MAX = 1.25


def _request_kind(rng: random.Random, write_share: float) -> str:
    return "write" if rng.random() < write_share else "read"


def _service_time_seconds(
    kind: str,
    cache_hit: bool,
    config: Config,
    rng: random.Random,
) -> tuple[float, bool | None]:
    i = config.infra
    if kind == "read":
        if cache_hit:
            base_ms = i.cache_hit_service_time_ms
            hit_recorded: bool | None = True
        else:
            base_ms = i.per_request_service_time_ms
            hit_recorded = False
    else:
        base_ms = i.per_request_service_time_ms * WRITE_PATH_MULTIPLIER
        hit_recorded = None

    jittered_ms = base_ms * rng.uniform(JITTER_MIN, JITTER_MAX)
    return jittered_ms / 1000.0, hit_recorded


def run_benchmark_sample(
    config: Config,
    workload: WorkloadProfile,
) -> LatencySummary:
    """Run the short sampling benchmark and return a LatencySummary."""
    b = config.benchmark
    rng = random.Random(b.rng_seed)
    cache = SeededCache(config.infra.cache_hit_ratio, seed=b.rng_seed + 1)

    write_share = (
        workload.avg_write_qps / workload.avg_total_qps
        if workload.avg_total_qps > 0
        else 0.0
    )

    collector = MetricsCollector()

    plan: list[tuple[str, bool, float, bool | None]] = []
    for _ in range(b.sample_requests):
        kind = _request_kind(rng, write_share)
        cache_hit = cache.is_hit() if kind == "read" else False
        sleep_s, hit_recorded = _service_time_seconds(kind, cache_hit, config, rng)
        plan.append((kind, cache_hit, sleep_s, hit_recorded))

    def handle(item: tuple[str, bool, float, bool | None]) -> None:
        _kind, _hit, sleep_s, hit_recorded = item
        start = time.monotonic()
        time.sleep(sleep_s)
        latency_ms = (time.monotonic() - start) * 1000.0
        collector.record(latency_ms, cache_hit=hit_recorded)

    with ThreadPoolExecutor(max_workers=max(1, b.sample_workers)) as pool:
        for _ in pool.map(handle, plan):
            pass

    return collector.summary()
