"""Smoke tests for simulator.runner.

These tests verify that the runner correctly loads config, produces
output with the expected fields, and respects CLI overrides.
"""

from __future__ import annotations

from pathlib import Path

from simulator.runner import load_config, run_benchmark


def test_runner_loads_config(tmp_config: Path) -> None:
    cfg = load_config(tmp_config)
    assert cfg["service_time_ms"] == 5
    assert cfg["write_service_time_ms"] == 8
    assert cfg["workers"] == 2
    assert cfg["io_workers"] == 1
    assert cfg["arrival_pattern"] == "poisson"
    assert cfg["read_fraction"] == 0.7


def test_runner_output_structure(tmp_config: Path) -> None:
    results = run_benchmark(tmp_config)
    assert len(results) == 1

    r = results[0]
    assert r["count"] > 0
    assert "mean_ms" in r
    assert "p95_ms" in r
    assert "throughput_rps" in r
    assert "read_count" in r
    assert "write_count" in r
    assert "rejected" in r
    assert "conn_pool_util" in r
    assert "io_util" in r
    assert "bottleneck_resource" in r
    assert "inter_arrival_mean_ms" in r
    assert "cv" in r


def test_arrival_pattern_override(tmp_config: Path) -> None:
    results = run_benchmark(tmp_config, arrival_pattern="bursty")
    assert results[0]["arrival_pattern"] == "bursty"


def test_read_fraction_override(tmp_config: Path) -> None:
    results = run_benchmark(tmp_config, read_fraction=1.0)
    r = results[0]
    assert r["write_count"] == 0
    assert r["read_count"] == r["count"]


def test_all_requests_processed(tmp_config: Path) -> None:
    results = run_benchmark(tmp_config)
    r = results[0]
    assert r["count"] == 20
