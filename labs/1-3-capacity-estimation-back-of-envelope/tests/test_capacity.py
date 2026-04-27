"""Capacity sizing: nodes, headroom, replication-lag estimate."""

from __future__ import annotations

from dataclasses import replace

from simulator.capacity import derive_capacity
from simulator.config import Config
from simulator.workload import derive_workload


def test_at_least_rf_nodes(tmp_config: Config) -> None:
    cap = derive_capacity(tmp_config, derive_workload(tmp_config))
    assert cap.nodes_required >= tmp_config.infra.replication_factor


def test_buffer_lowers_effective_node_qps(tmp_config: Config) -> None:
    no_buffer = replace(tmp_config, capacity=replace(tmp_config.capacity, target_buffer_pct=0.0))
    half_buffer = replace(tmp_config, capacity=replace(tmp_config.capacity, target_buffer_pct=50.0))

    a = derive_capacity(no_buffer, derive_workload(no_buffer))
    b = derive_capacity(half_buffer, derive_workload(half_buffer))

    assert b.target_node_qps_at_buffer < a.target_node_qps_at_buffer
    assert abs(b.target_node_qps_at_buffer - tmp_config.infra.instance_qps_capacity * 0.5) < 1e-6


def test_headroom_in_range(tmp_config: Config) -> None:
    cap = derive_capacity(tmp_config, derive_workload(tmp_config))
    assert 0.0 <= cap.headroom_pct_at_peak <= 100.0
    assert abs(cap.headroom_pct_at_peak + cap.utilisation_pct_at_peak - 100.0) < 1e-6


def test_replication_lag_non_negative(tmp_config: Config) -> None:
    cap = derive_capacity(tmp_config, derive_workload(tmp_config))
    assert cap.replication_lag_estimate_s >= 0.0


def test_higher_burst_increases_nodes(tmp_config: Config) -> None:
    low_burst = replace(tmp_config, workload=replace(tmp_config.workload, burst_factor=1.0))
    high_burst = replace(tmp_config, workload=replace(tmp_config.workload, burst_factor=20.0))

    a = derive_capacity(low_burst, derive_workload(low_burst))
    b = derive_capacity(high_burst, derive_workload(high_burst))

    assert b.nodes_required >= a.nodes_required


def test_provisioned_qps_at_least_storage_qps(tmp_config: Config) -> None:
    """At target buffer the provisioned capacity must comfortably exceed
    the effective storage QPS that needs to be served at peak."""
    workload = derive_workload(tmp_config)
    cap = derive_capacity(tmp_config, workload)
    storage_qps = workload.effective_storage_read_qps + workload.effective_storage_write_qps
    assert cap.provisioned_qps_capacity >= storage_qps
