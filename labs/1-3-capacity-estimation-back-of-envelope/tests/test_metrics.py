"""MetricsCollector: percentile computation, thread safety, hit-rate."""

from __future__ import annotations

import threading

from simulator.metrics import MetricsCollector


def test_empty_summary() -> None:
    c = MetricsCollector()
    s = c.summary()
    assert s.count == 0
    assert s.p50_ms == 0.0
    assert s.p95_ms == 0.0
    assert s.p99_ms == 0.0
    assert s.observed_hit_rate == 0.0


def test_percentiles_known_distribution() -> None:
    c = MetricsCollector()
    for v in range(1, 101):
        c.record(float(v), cache_hit=None)
    s = c.summary()
    assert 49.0 <= s.p50_ms <= 51.0
    assert 94.0 <= s.p95_ms <= 96.0
    assert 98.0 <= s.p99_ms <= 100.0


def test_hit_rate_tracking() -> None:
    c = MetricsCollector()
    for _ in range(80):
        c.record(1.0, cache_hit=True)
    for _ in range(20):
        c.record(5.0, cache_hit=False)
    s = c.summary()
    assert abs(s.observed_hit_rate - 0.8) < 1e-6
    assert s.cache_hits == 80
    assert s.cache_misses == 20


def test_thread_safety_record() -> None:
    c = MetricsCollector()
    per_thread = 200
    threads = [
        threading.Thread(target=lambda: [c.record(1.0, cache_hit=True) for _ in range(per_thread)])
        for _ in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert c.count == per_thread * 8


def test_reset_clears() -> None:
    c = MetricsCollector()
    c.record(1.0, cache_hit=True)
    c.record(2.0, cache_hit=False)
    c.reset()
    s = c.summary()
    assert s.count == 0
    assert s.cache_hits == 0
    assert s.cache_misses == 0
