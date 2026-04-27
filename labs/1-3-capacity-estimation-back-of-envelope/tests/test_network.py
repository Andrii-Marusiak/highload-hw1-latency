"""Bandwidth math: ingress, egress, replication, fan-out."""

from __future__ import annotations

from dataclasses import replace

from simulator.config import Config
from simulator.network import derive_bandwidth
from simulator.workload import derive_workload


def test_ingress_matches_payload_times_peak_total(tmp_config: Config) -> None:
    workload = derive_workload(tmp_config)
    bw = derive_bandwidth(tmp_config, workload)
    expected = workload.peak_total_qps * tmp_config.workload.payload_bytes
    assert abs(bw.ingress_bytes_per_second - expected) < 1e-6


def test_egress_matches_payload_times_peak_read(tmp_config: Config) -> None:
    workload = derive_workload(tmp_config)
    bw = derive_bandwidth(tmp_config, workload)
    expected = workload.peak_read_qps * tmp_config.workload.payload_bytes
    assert abs(bw.egress_bytes_per_second - expected) < 1e-6


def test_replication_egress_uses_rf_minus_one(tmp_config: Config) -> None:
    rf3 = tmp_config
    rf2 = replace(tmp_config, infra=replace(tmp_config.infra, replication_factor=2))

    a = derive_bandwidth(rf3, derive_workload(rf3))
    b = derive_bandwidth(rf2, derive_workload(rf2))

    assert abs(a.replication_egress_bytes_per_second / b.replication_egress_bytes_per_second - 2.0) < 1e-6


def test_fan_out_egress_scales_linearly(tmp_config: Config) -> None:
    cfg1 = replace(tmp_config, infra=replace(tmp_config.infra, fan_out_per_write=1.0))
    cfg4 = replace(tmp_config, infra=replace(tmp_config.infra, fan_out_per_write=4.0))

    a = derive_bandwidth(cfg1, derive_workload(cfg1))
    b = derive_bandwidth(cfg4, derive_workload(cfg4))

    assert abs(b.fan_out_egress_bytes_per_second / a.fan_out_egress_bytes_per_second - 4.0) < 1e-6


def test_total_egress_is_sum(tmp_config: Config) -> None:
    workload = derive_workload(tmp_config)
    bw = derive_bandwidth(tmp_config, workload)
    expected = bw.egress_bytes_per_second + bw.replication_egress_bytes_per_second + bw.fan_out_egress_bytes_per_second
    assert abs(bw.total_egress_bytes_per_second - expected) < 1e-6


def test_rf_one_yields_zero_replication(tmp_config: Config) -> None:
    cfg = replace(tmp_config, infra=replace(tmp_config.infra, replication_factor=1))
    bw = derive_bandwidth(cfg, derive_workload(cfg))
    assert bw.replication_egress_bytes_per_second == 0.0
