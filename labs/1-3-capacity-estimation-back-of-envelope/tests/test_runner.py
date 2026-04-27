"""Smoke tests for the runner: returns expected metric keys, runs fast."""

from __future__ import annotations

import time
from pathlib import Path

from simulator.runner import run_benchmark


_REQUIRED_KEYS = {
    "daily_requests",
    "avg_total_qps",
    "peak_total_qps",
    "peak_read_qps",
    "peak_write_qps",
    "effective_storage_read_qps",
    "effective_storage_write_qps",
    "daily_write_count",
    "daily_raw_growth_bytes",
    "daily_replicated_growth_bytes",
    "storage_at_retention_bytes",
    "hot_storage_at_retention_bytes",
    "cold_storage_at_retention_bytes",
    "ingress_bytes_per_second",
    "egress_bytes_per_second",
    "replication_egress_bytes_per_second",
    "fan_out_egress_bytes_per_second",
    "total_egress_bytes_per_second",
    "nodes_required",
    "provisioned_qps_capacity",
    "utilisation_pct_at_peak",
    "headroom_pct_at_peak",
    "replication_lag_estimate_s",
    "monthly_compute_usd",
    "monthly_hot_storage_usd",
    "monthly_cold_storage_usd",
    "monthly_total_usd",
    "cost_per_1k_qps_usd",
    "p50_ms",
    "p95_ms",
    "p99_ms",
    "mean_ms",
    "observed_hit_rate",
    "latency_count",
    "latency_duration_s",
}


def test_run_benchmark_returns_all_keys(tmp_config_path: Path) -> None:
    metrics = run_benchmark(tmp_config_path)
    missing = _REQUIRED_KEYS - set(metrics.keys())
    assert not missing, f"missing keys: {missing}"


def test_run_benchmark_is_fast(tmp_config_path: Path) -> None:
    start = time.monotonic()
    run_benchmark(tmp_config_path)
    elapsed = time.monotonic() - start
    assert elapsed < 5.0, f"run_benchmark took {elapsed:.2f}s for sample_requests=200"


def test_observed_hit_rate_close_to_config(tmp_config_path: Path) -> None:
    metrics = run_benchmark(tmp_config_path)
    assert abs(metrics["observed_hit_rate"] - 0.8) < 0.15, (
        f"observed hit rate {metrics['observed_hit_rate']} should be near 0.8"
    )
