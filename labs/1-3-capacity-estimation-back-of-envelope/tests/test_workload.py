"""Workload derivation: avg/peak QPS, R/W split, post-cache storage QPS."""

from __future__ import annotations

from dataclasses import replace

from simulator.config import Config
from simulator.workload import derive_workload


def test_daily_requests(tmp_config: Config) -> None:
    profile = derive_workload(tmp_config)
    expected = 100_000 * 4 * 20
    assert profile.daily_requests == expected


def test_avg_qps(tmp_config: Config) -> None:
    profile = derive_workload(tmp_config)
    expected_avg = (100_000 * 4 * 20) / 86_400
    assert abs(profile.avg_total_qps - expected_avg) < 1e-6


def test_peak_is_burst_x_avg(tmp_config: Config) -> None:
    profile = derive_workload(tmp_config)
    assert abs(profile.peak_total_qps - profile.avg_total_qps * 3.0) < 1e-6


def test_read_write_split(tmp_config: Config) -> None:
    profile = derive_workload(tmp_config)
    assert abs(profile.peak_read_qps + profile.peak_write_qps - profile.peak_total_qps) < 1e-6
    assert abs(profile.peak_read_qps / profile.peak_write_qps - 9.0) < 1e-3


def test_cache_lowers_effective_storage_read_qps(tmp_config: Config) -> None:
    no_cache = replace(tmp_config, infra=replace(tmp_config.infra, cache_hit_ratio=0.0))
    big_cache = replace(tmp_config, infra=replace(tmp_config.infra, cache_hit_ratio=0.95))

    no_cache_profile = derive_workload(no_cache)
    big_cache_profile = derive_workload(big_cache)

    assert big_cache_profile.effective_storage_read_qps < no_cache_profile.effective_storage_read_qps
    assert abs(big_cache_profile.effective_storage_read_qps - no_cache_profile.peak_read_qps * 0.05) < 1e-6


def test_write_amplification_raises_storage_write_qps(tmp_config: Config) -> None:
    no_amp = replace(tmp_config, infra=replace(tmp_config.infra, write_amplification=1.0))
    high_amp = replace(tmp_config, infra=replace(tmp_config.infra, write_amplification=2.5))

    a = derive_workload(no_amp)
    b = derive_workload(high_amp)
    assert b.effective_storage_write_qps > a.effective_storage_write_qps
    assert abs(b.effective_storage_write_qps / a.effective_storage_write_qps - 2.5) < 1e-3
