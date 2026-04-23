"""Unit tests for simulator.workload generators.

These tests verify that arrival pattern generators produce the correct
count of intervals with expected statistical properties, and that
request generators produce the right read/write mix.
"""

from __future__ import annotations

import statistics

from simulator.workload import Request, generate_arrivals, generate_requests


# ------------------------------------------------------------------
# generate_requests
# ------------------------------------------------------------------

def test_request_count() -> None:
    reqs = generate_requests(50, read_fraction=0.7)
    assert len(reqs) == 50


def test_request_ids_unique() -> None:
    reqs = generate_requests(100, read_fraction=0.5)
    ids = [r.id for r in reqs]
    assert len(set(ids)) == 100


def test_request_ids_start_at_one() -> None:
    reqs = generate_requests(5, read_fraction=0.5)
    assert reqs[0].id == 1
    assert reqs[-1].id == 5


def test_request_types_are_valid() -> None:
    reqs = generate_requests(100, read_fraction=0.6)
    for r in reqs:
        assert r.type in ("read", "write")


def test_all_reads_when_fraction_one() -> None:
    reqs = generate_requests(50, read_fraction=1.0)
    assert all(r.type == "read" for r in reqs)


def test_all_writes_when_fraction_zero() -> None:
    reqs = generate_requests(50, read_fraction=0.0)
    assert all(r.type == "write" for r in reqs)


def test_read_fraction_approximate() -> None:
    """With enough requests the observed fraction should be close."""
    reqs = generate_requests(1000, read_fraction=0.7)
    reads = sum(1 for r in reqs if r.type == "read")
    assert 0.60 <= reads / 1000 <= 0.80


# ------------------------------------------------------------------
# generate_arrivals
# ------------------------------------------------------------------

def test_arrival_count_poisson() -> None:
    intervals = generate_arrivals(50, "poisson", mean_interval_ms=5.0)
    assert len(intervals) == 49


def test_arrival_count_bursty() -> None:
    intervals = generate_arrivals(50, "bursty", mean_interval_ms=5.0)
    assert len(intervals) == 49


def test_arrival_count_regular() -> None:
    intervals = generate_arrivals(50, "regular", mean_interval_ms=5.0)
    assert len(intervals) == 49


def test_arrival_single_request() -> None:
    intervals = generate_arrivals(1, "poisson", mean_interval_ms=5.0)
    assert intervals == []


def test_arrival_unknown_pattern_raises() -> None:
    import pytest
    with pytest.raises(ValueError, match="Unknown arrival pattern"):
        generate_arrivals(10, "unknown", mean_interval_ms=5.0)


def test_poisson_cv_near_one() -> None:
    """Exponential inter-arrivals should have CV ≈ 1."""
    intervals = generate_arrivals(2000, "poisson", mean_interval_ms=10.0)
    mu = statistics.mean(intervals)
    sigma = statistics.stdev(intervals)
    cv = sigma / mu
    assert 0.8 <= cv <= 1.3


def test_bursty_cv_near_target() -> None:
    """Log-normal inter-arrivals with burst_cv=2 should have CV ≈ 2."""
    intervals = generate_arrivals(5000, "bursty", mean_interval_ms=10.0, burst_cv=2.0)
    mu = statistics.mean(intervals)
    sigma = statistics.stdev(intervals)
    cv = sigma / mu
    assert 1.4 <= cv <= 2.8


def test_regular_cv_low() -> None:
    """Regular arrivals should have CV ≈ 0.1."""
    intervals = generate_arrivals(2000, "regular", mean_interval_ms=10.0)
    mu = statistics.mean(intervals)
    sigma = statistics.stdev(intervals)
    cv = sigma / mu
    assert cv < 0.3


def test_all_intervals_positive() -> None:
    for pattern in ("poisson", "bursty", "regular"):
        intervals = generate_arrivals(100, pattern, mean_interval_ms=5.0)
        assert all(v > 0 for v in intervals), f"{pattern} produced non-positive interval"
