"""Cost-per-unit calculations.

These tests focus on directional correctness: improvements should make
``cost_per_1k_qps_usd`` go down (caching, RF reduction, tiering) and
the storage line should reflect the hot/cold split when tiering is on.
"""

from __future__ import annotations

from dataclasses import replace

from simulator.capacity import derive_capacity
from simulator.config import Config
from simulator.cost import derive_cost
from simulator.network import derive_bandwidth  # noqa: F401  (kept for parity)
from simulator.storage import derive_storage
from simulator.workload import derive_workload


def _full_cost(cfg: Config):
    workload = derive_workload(cfg)
    storage = derive_storage(cfg, workload)
    capacity = derive_capacity(cfg, workload)
    return derive_cost(cfg, workload, storage, capacity)


def test_monthly_total_is_sum(tmp_config: Config) -> None:
    cost = _full_cost(tmp_config)
    expected = (
        cost.monthly_compute_usd
        + cost.monthly_hot_storage_usd
        + cost.monthly_cold_storage_usd
    )
    assert abs(cost.monthly_total_usd - expected) < 1e-6


def test_caching_lowers_cost_per_1k_qps(tmp_config: Config) -> None:
    low = replace(tmp_config, infra=replace(tmp_config.infra, cache_hit_ratio=0.5))
    high = replace(tmp_config, infra=replace(tmp_config.infra, cache_hit_ratio=0.95))

    a = _full_cost(low)
    b = _full_cost(high)
    assert b.cost_per_1k_qps_usd <= a.cost_per_1k_qps_usd


def test_rf_reduction_lowers_storage_cost(tmp_config: Config) -> None:
    rf3 = tmp_config
    rf2 = replace(tmp_config, infra=replace(tmp_config.infra, replication_factor=2))

    a = _full_cost(rf3)
    b = _full_cost(rf2)
    assert b.monthly_hot_storage_usd < a.monthly_hot_storage_usd
    assert abs(b.monthly_hot_storage_usd / a.monthly_hot_storage_usd - 2 / 3) < 1e-3


def test_tiering_reduces_total_storage_cost(tmp_config: Config) -> None:
    no_tier = tmp_config
    tier = replace(tmp_config, infra=replace(tmp_config.infra, hot_data_fraction=0.2))

    a = _full_cost(no_tier)
    b = _full_cost(tier)
    a_storage = a.monthly_hot_storage_usd + a.monthly_cold_storage_usd
    b_storage = b.monthly_hot_storage_usd + b.monthly_cold_storage_usd
    assert b_storage < a_storage
