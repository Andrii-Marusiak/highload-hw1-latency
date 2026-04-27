"""Storage growth math: replication, indexes, retention, tiering."""

from __future__ import annotations

from dataclasses import replace

from simulator.config import Config
from simulator.storage import derive_storage, GB
from simulator.workload import derive_workload


def test_replication_factor_multiplies_growth(tmp_config: Config) -> None:
    rf1 = replace(tmp_config, infra=replace(tmp_config.infra, replication_factor=1))
    rf3 = replace(tmp_config, infra=replace(tmp_config.infra, replication_factor=3))

    s1 = derive_storage(rf1, derive_workload(rf1))
    s3 = derive_storage(rf3, derive_workload(rf3))

    assert abs(s3.daily_replicated_growth_bytes / s1.daily_replicated_growth_bytes - 3.0) < 1e-6


def test_index_overhead_inflates_growth(tmp_config: Config) -> None:
    no_idx = replace(tmp_config, infra=replace(tmp_config.infra, index_overhead=0.0))
    with_idx = replace(tmp_config, infra=replace(tmp_config.infra, index_overhead=0.5))

    a = derive_storage(no_idx, derive_workload(no_idx))
    b = derive_storage(with_idx, derive_workload(with_idx))

    assert abs(b.daily_raw_growth_bytes / a.daily_raw_growth_bytes - 1.5) < 1e-6


def test_retention_scales_total(tmp_config: Config) -> None:
    cfg6 = tmp_config
    cfg12 = replace(cfg6, workload=replace(cfg6.workload, retention_months=12))
    s6 = derive_storage(cfg6, derive_workload(cfg6))
    s12 = derive_storage(cfg12, derive_workload(cfg12))

    assert abs(s12.storage_at_retention_bytes / s6.storage_at_retention_bytes - 2.0) < 1e-6


def test_hot_cold_split(tmp_config: Config) -> None:
    cfg = replace(tmp_config, infra=replace(tmp_config.infra, hot_data_fraction=0.2))
    storage = derive_storage(cfg, derive_workload(cfg))

    total = storage.storage_at_retention_bytes
    assert abs(storage.hot_storage_at_retention_bytes - 0.2 * total) < 1e-6
    assert abs(storage.cold_storage_at_retention_bytes - 0.8 * total) < 1e-6


def test_daily_writes_match_workload(tmp_config: Config) -> None:
    workload = derive_workload(tmp_config)
    storage = derive_storage(tmp_config, workload)
    expected = int(workload.avg_write_qps * 86_400)
    assert storage.daily_write_count == expected


def test_storage_in_realistic_units(tmp_config: Config) -> None:
    workload = derive_workload(tmp_config)
    storage = derive_storage(tmp_config, workload)
    assert storage.daily_raw_growth_bytes > 0
    assert storage.daily_replicated_growth_bytes >= storage.daily_raw_growth_bytes
    assert storage.storage_at_retention_bytes >= 0.5 * GB
