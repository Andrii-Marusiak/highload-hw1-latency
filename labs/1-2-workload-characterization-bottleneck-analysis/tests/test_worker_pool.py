"""Unit tests for simulator.worker_pool.WorkerPool.

These tests verify read/write service time differentiation, jitter,
arrival rate spacing, and that no requests are dropped.
"""

from __future__ import annotations

import time

from simulator.metrics import MetricsCollector
from simulator.worker_pool import WorkerPool
from simulator.workload import Request


def _make_requests(n: int, req_type: str = "read") -> list[Request]:
    return [Request(id=i, type=req_type) for i in range(1, n + 1)]


def test_single_worker_serial() -> None:
    """With 1 worker, requests run sequentially."""
    pool = WorkerPool(workers=1, service_time_ms=5)
    collector = MetricsCollector()
    reqs = _make_requests(5)

    start = time.monotonic()
    pool.run(reqs, collector)
    elapsed = time.monotonic() - start

    assert collector.count == 5
    assert elapsed >= 0.020


def test_parallel_workers() -> None:
    """With N workers processing N requests, total time ≈ 1 × service_time."""
    n = 4
    pool = WorkerPool(workers=n, service_time_ms=10)
    collector = MetricsCollector()
    reqs = _make_requests(n)

    start = time.monotonic()
    pool.run(reqs, collector)
    elapsed = time.monotonic() - start

    assert collector.count == n
    assert elapsed < 0.030


def test_write_requests_take_longer() -> None:
    """Write service time is higher, so write mean latency > read mean."""
    pool = WorkerPool(workers=4, service_time_ms=5, write_service_time_ms=15)
    collector = MetricsCollector()

    reads = _make_requests(20, "read")
    writes = [Request(id=100 + i, type="write") for i in range(1, 21)]
    pool.run(reads + writes, collector)

    s = collector.summary(duration_s=1.0)
    assert s["write_mean_ms"] > s["read_mean_ms"]


def test_latency_has_jitter() -> None:
    """Latencies should not be identical due to +/-20% jitter."""
    pool = WorkerPool(workers=4, service_time_ms=10)
    collector = MetricsCollector()
    reqs = _make_requests(20)

    pool.run(reqs, collector)
    s = collector.summary(duration_s=1.0)
    assert s["p95_ms"] != s["mean_ms"] or collector.count < 2


def test_all_requests_completed() -> None:
    """Every submitted request must produce a recorded latency."""
    pool = WorkerPool(workers=2, service_time_ms=3)
    collector = MetricsCollector()
    reqs = _make_requests(30)

    pool.run(reqs, collector)
    assert collector.count == 30


def test_run_with_inter_arrival_times() -> None:
    """Requests with inter-arrival spacing still complete all."""
    pool = WorkerPool(workers=2, service_time_ms=5)
    collector = MetricsCollector()
    reqs = _make_requests(10)
    intervals = [1.0] * 9

    pool.run(reqs, collector, inter_arrival_times=intervals)
    assert collector.count == 10


def test_read_write_counts_tracked() -> None:
    """Collector tracks read and write counts separately."""
    pool = WorkerPool(workers=4, service_time_ms=3, write_service_time_ms=5)
    collector = MetricsCollector()

    reads = _make_requests(6, "read")
    writes = [Request(id=100 + i, type="write") for i in range(1, 5)]
    pool.run(reads + writes, collector)

    assert collector.read_count == 6
    assert collector.write_count == 4
