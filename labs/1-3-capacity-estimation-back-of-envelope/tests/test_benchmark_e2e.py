"""End-to-end test: stdout includes every grading-dimension headline."""

from __future__ import annotations

from pathlib import Path

import pytest

from simulator.runner import run_benchmark


_REQUIRED_HEADLINES = [
    "INPUTS",
    "THROUGHPUT",
    "LATENCY",
    "STORAGE",
    "BANDWIDTH",
    "CAPACITY",
    "COST",
    "Peak total QPS",
    "Storage at",
    "Replication egress",
    "Fan-out egress",
    "Headroom at peak",
    "Cost per 1k QPS",
    "p50:",
    "p95:",
    "p99:",
]


def test_report_contains_every_grading_dimension(
    tmp_config_path: Path, capsys: pytest.CaptureFixture
) -> None:
    run_benchmark(tmp_config_path)
    out = capsys.readouterr().out
    for needle in _REQUIRED_HEADLINES:
        assert needle in out, f"expected '{needle}' in benchmark output"


def test_improvement_a_moves_the_right_metrics(
    tmp_config_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Improvement A: raising the cache hit ratio should:

    * raise the *observed* cache hit rate,
    * shrink the *analytical* effective storage read QPS, and
    * lower the *mean* latency of the short benchmark.

    Mean (rather than p99) is asserted because p99 of a 200-sample
    real-time benchmark is dominated by OS scheduling jitter, not the
    service-time model.  Students running the full 5,000-sample
    benchmark via ``scripts/run-benchmark.sh`` will see the p99 drop
    too; that's exercised in the README's expected output.
    """
    baseline = run_benchmark(tmp_config_path)
    capsys.readouterr()

    raised = tmp_path / "improved.yaml"
    raised.write_text(tmp_config_path.read_text().replace(
        "cache_hit_ratio: 0.8", "cache_hit_ratio: 0.99"
    ))
    improved = run_benchmark(raised)
    capsys.readouterr()

    assert improved["observed_hit_rate"] > baseline["observed_hit_rate"]
    assert improved["effective_storage_read_qps"] < baseline["effective_storage_read_qps"]
    assert improved["mean_ms"] <= baseline["mean_ms"], (
        f"mean latency should drop with higher cache hit: "
        f"baseline={baseline['mean_ms']:.2f}, improved={improved['mean_ms']:.2f}"
    )
