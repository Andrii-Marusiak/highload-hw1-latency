"""Unit tests for simulator.metrics.MetricsCollector.

These tests verify per-type latency tracking, inter-arrival statistics,
utilisation computation, thread safety, and reset behaviour.
"""

from __future__ import annotations

import threading

from simulator.metrics import MetricsCollector


def test_mean_latency(small_collector: MetricsCollector) -> None:
    expected = (10.0 + 12.0 + 11.0 + 15.0 + 9.0 + 13.0 + 14.0 + 10.5 + 11.5 + 12.5) / 10
    assert abs(small_collector.mean() - expected) < 0.01


def test_p95_latency(small_collector: MetricsCollector) -> None:
    assert small_collector.p95() == 15.0


def test_empty_collector_returns_zero() -> None:
    c = MetricsCollector()
    assert c.mean() == 0.0
    assert c.p95() == 0.0
    assert c.count == 0


def test_read_write_counts(small_collector: MetricsCollector) -> None:
    assert small_collector.read_count == 5
    assert small_collector.write_count == 5


def test_per_type_latencies() -> None:
    c = MetricsCollector()
    c.record(10.0, "read")
    c.record(20.0, "write")
    s = c.summary(duration_s=1.0)
    assert s["read_mean_ms"] == 10.0
    assert s["write_mean_ms"] == 20.0


def test_inter_arrival_stats() -> None:
    c = MetricsCollector()
    for v in [10.0, 10.0, 10.0, 10.0]:
        c.record_inter_arrival(v)
    c.record(5.0, "read")
    s = c.summary(duration_s=1.0)
    assert s["inter_arrival_mean_ms"] == 10.0
    assert s["inter_arrival_std_ms"] == 0.0
    assert s["cv"] == 0.0


def test_cv_computation() -> None:
    """CV = std / mean for inter-arrival times."""
    c = MetricsCollector()
    for v in [5.0, 15.0, 5.0, 15.0]:
        c.record_inter_arrival(v)
    c.record(5.0, "read")
    s = c.summary(duration_s=1.0)
    assert s["inter_arrival_mean_ms"] == 10.0
    assert s["cv"] > 0


def test_thread_safety() -> None:
    c = MetricsCollector()
    per_thread = 100
    num_threads = 10

    def record_many():
        for i in range(per_thread):
            c.record(float(i), "read")

    threads = [threading.Thread(target=record_many) for _ in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert c.count == per_thread * num_threads


def test_summary_keys(small_collector: MetricsCollector) -> None:
    s = small_collector.summary(duration_s=1.0)
    expected_keys = {
        "mean_ms", "p95_ms", "count", "read_count", "write_count",
        "rejected", "throughput_rps",
        "read_mean_ms", "read_p95_ms", "write_mean_ms", "write_p95_ms",
        "inter_arrival_mean_ms", "inter_arrival_std_ms", "cv",
        "conn_pool_util", "io_util",
        "bottleneck_resource", "bottleneck_util",
    }
    assert set(s.keys()) == expected_keys


def test_summary_throughput() -> None:
    c = MetricsCollector()
    for _ in range(50):
        c.record(10.0, "read")
    s = c.summary(duration_s=5.0)
    assert s["throughput_rps"] == 10.0


def test_record_rejection() -> None:
    c = MetricsCollector()
    assert c.rejected == 0
    c.record_rejection()
    c.record_rejection()
    assert c.rejected == 2


def test_reset() -> None:
    c = MetricsCollector()
    c.record(10.0, "read")
    c.record(20.0, "write")
    c.record_inter_arrival(5.0)
    c.record_rejection()
    c.reset()
    assert c.count == 0
    assert c.read_count == 0
    assert c.write_count == 0
    assert c.rejected == 0


def test_bottleneck_identification() -> None:
    """When write fraction is high and io_workers is low, I/O should be
    the bottleneck."""
    c = MetricsCollector()
    for _ in range(100):
        c.record(15.0, "write")
    s = c.summary(
        duration_s=1.0,
        workers=4,
        io_workers=1,
        read_fraction=0.0,
        service_time_ms=10.0,
        write_service_time_ms=15.0,
    )
    assert s["io_util"] > s["conn_pool_util"]
    assert s["bottleneck_resource"] == "io_subsystem"
