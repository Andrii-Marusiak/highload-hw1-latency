"""Config loading and validation."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from simulator.config import load_config


def test_loads_valid_config(tmp_config_path: Path) -> None:
    cfg = load_config(tmp_config_path)
    assert cfg.workload.dau == 100_000
    assert cfg.infra.replication_factor == 3
    assert 0 <= cfg.infra.cache_hit_ratio <= 1
    assert cfg.benchmark.sample_requests == 200


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(textwrap.dedent(body))
    return path


def test_rejects_replication_factor_below_one(tmp_path: Path) -> None:
    cfg_text = """\
        workload:
          dau: 1000
          sessions_per_user: 1
          requests_per_session: 1
          payload_bytes: 100
          read_write_ratio: 1
          burst_factor: 2.0
          retention_months: 1
        infra:
          replication_factor: 0
          cache_hit_ratio: 0.5
          index_overhead: 0.1
          fan_out_per_write: 0
          write_amplification: 1.0
          instance_qps_capacity: 100
          per_request_service_time_ms: 1
          cache_hit_service_time_ms: 0.1
          hot_data_fraction: 1.0
        capacity:
          target_buffer_pct: 20
          cost_per_node_per_month_usd: 100
          cold_tier_cost_multiplier: 0.1
          replication_lag_budget_s: 1.0
        benchmark:
          sample_requests: 10
          sample_workers: 1
          rng_seed: 1
    """
    with pytest.raises(ValueError, match="replication_factor"):
        load_config(_write(tmp_path, cfg_text))


def test_rejects_cache_hit_above_one(tmp_path: Path) -> None:
    cfg_text = """\
        workload:
          dau: 1000
          sessions_per_user: 1
          requests_per_session: 1
          payload_bytes: 100
          read_write_ratio: 1
          burst_factor: 2.0
          retention_months: 1
        infra:
          replication_factor: 1
          cache_hit_ratio: 1.5
          index_overhead: 0.1
          fan_out_per_write: 0
          write_amplification: 1.0
          instance_qps_capacity: 100
          per_request_service_time_ms: 1
          cache_hit_service_time_ms: 0.1
          hot_data_fraction: 1.0
        capacity:
          target_buffer_pct: 20
          cost_per_node_per_month_usd: 100
          cold_tier_cost_multiplier: 0.1
          replication_lag_budget_s: 1.0
        benchmark:
          sample_requests: 10
          sample_workers: 1
          rng_seed: 1
    """
    with pytest.raises(ValueError, match="cache_hit_ratio"):
        load_config(_write(tmp_path, cfg_text))


def test_rejects_burst_factor_below_one(tmp_path: Path) -> None:
    cfg_text = """\
        workload:
          dau: 1000
          sessions_per_user: 1
          requests_per_session: 1
          payload_bytes: 100
          read_write_ratio: 1
          burst_factor: 0.5
          retention_months: 1
        infra:
          replication_factor: 1
          cache_hit_ratio: 0.5
          index_overhead: 0.0
          fan_out_per_write: 0
          write_amplification: 1.0
          instance_qps_capacity: 100
          per_request_service_time_ms: 1
          cache_hit_service_time_ms: 0.1
          hot_data_fraction: 1.0
        capacity:
          target_buffer_pct: 20
          cost_per_node_per_month_usd: 100
          cold_tier_cost_multiplier: 0.1
          replication_lag_budget_s: 1.0
        benchmark:
          sample_requests: 10
          sample_workers: 1
          rng_seed: 1
    """
    with pytest.raises(ValueError, match="burst_factor"):
        load_config(_write(tmp_path, cfg_text))
