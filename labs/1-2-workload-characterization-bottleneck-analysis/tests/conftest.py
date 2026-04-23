"""Shared fixtures for the simulator test suite.

All fixtures use small request counts and short service times so that
the full suite completes in under 2 seconds.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from simulator.metrics import MetricsCollector


@pytest.fixture()
def tmp_config(tmp_path: Path) -> Path:
    """Write a small config.yaml for fast test runs and return its path."""
    config = tmp_path / "config.yaml"
    config.write_text(textwrap.dedent("""\
        service_time_ms: 5
        write_service_time_ms: 8
        workers: 2
        io_workers: 1
        total_requests: 20
        arrival_pattern: poisson
        burst_cv: 2.0
        read_fraction: 0.7
        target_utilization: 0.5
        replica_lag_ms: 3
    """))
    return config


@pytest.fixture()
def small_collector() -> MetricsCollector:
    """Return a MetricsCollector pre-loaded with known latency values."""
    c = MetricsCollector()
    for v in [10.0, 12.0, 11.0, 15.0, 9.0]:
        c.record(v, "read")
    for v in [13.0, 14.0, 10.5, 11.5, 12.5]:
        c.record(v, "write")
    return c
