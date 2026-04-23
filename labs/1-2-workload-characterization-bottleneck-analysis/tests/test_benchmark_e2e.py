"""End-to-end integration tests.

These tests run the full benchmark (via subprocess or direct call)
and verify the output structure and key invariants.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from simulator.runner import run_benchmark


def test_full_benchmark_completes(tmp_config: Path) -> None:
    results = run_benchmark(tmp_config)
    assert len(results) == 1
    r = results[0]
    assert r["count"] > 0
    assert r["mean_ms"] > 0
    assert r["throughput_rps"] > 0


def test_output_parseable(tmp_config: Path, capsys) -> None:
    run_benchmark(tmp_config)
    captured = capsys.readouterr().out

    assert "BENCHMARK RESULTS" in captured
    assert "r/s" in captured
    assert "Resource utilisation:" in captured
    assert "connection_pool:" in captured
    assert "io_subsystem:" in captured
    assert "bottleneck:" in captured
    assert "Arrival statistics:" in captured
    assert "CV:" in captured


def test_bottleneck_util_positive(tmp_config: Path) -> None:
    results = run_benchmark(tmp_config)
    r = results[0]
    assert r["bottleneck_util"] > 0


def test_cli_entry_point(tmp_config: Path) -> None:
    """``python -m simulator <config>`` exits with code 0."""
    lab_dir = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "-m", "simulator", str(tmp_config)],
        capture_output=True,
        text=True,
        cwd=str(lab_dir),
        timeout=60,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "BENCHMARK RESULTS" in result.stdout


def test_cli_arrival_pattern_flag(tmp_config: Path) -> None:
    """``--arrival-pattern bursty`` is accepted."""
    lab_dir = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [
            sys.executable, "-m", "simulator",
            str(tmp_config),
            "--arrival-pattern", "bursty",
        ],
        capture_output=True,
        text=True,
        cwd=str(lab_dir),
        timeout=60,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "arrival=bursty" in result.stdout


def test_cli_read_fraction_flag(tmp_config: Path) -> None:
    """``--read-fraction 0.95`` is accepted."""
    lab_dir = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [
            sys.executable, "-m", "simulator",
            str(tmp_config),
            "--read-fraction", "0.95",
        ],
        capture_output=True,
        text=True,
        cwd=str(lab_dir),
        timeout=60,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "read_fraction=0.95" in result.stdout
