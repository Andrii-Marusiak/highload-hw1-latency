"""Shared fixtures for the lab 1-3 simulator tests.

The fixtures use small workloads and a tiny sample_requests count so
the full suite runs in well under 2 seconds.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from simulator.config import Config, load_config


_SMALL_CONFIG = """\
workload:
  dau: 100000
  sessions_per_user: 4
  requests_per_session: 20
  payload_bytes: 1024
  read_write_ratio: 9
  burst_factor: 3.0
  retention_months: 6

infra:
  replication_factor: 3
  cache_hit_ratio: 0.8
  index_overhead: 0.3
  fan_out_per_write: 2.0
  write_amplification: 1.4
  instance_qps_capacity: 1000
  per_request_service_time_ms: 2.0
  cache_hit_service_time_ms: 0.2
  hot_data_fraction: 1.0

capacity:
  target_buffer_pct: 40
  cost_per_node_per_month_usd: 200
  cold_tier_cost_multiplier: 0.10
  replication_lag_budget_s: 5.0

benchmark:
  sample_requests: 200
  sample_workers: 4
  rng_seed: 7
"""


@pytest.fixture()
def tmp_config_path(tmp_path: Path) -> Path:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(textwrap.dedent(_SMALL_CONFIG))
    return cfg_path


@pytest.fixture()
def tmp_config(tmp_config_path: Path) -> Config:
    return load_config(tmp_config_path)
