"""Typed configuration for the capacity-estimation simulator.

The YAML file groups settings into ``workload``, ``infra``, ``capacity``,
and ``benchmark``.  ``load_config`` parses and validates the file and
returns a frozen ``Config`` dataclass that the rest of the simulator
consumes.

Validation is intentionally strict (rather than silently defaulting) so
that students get a clear error when an estimate input is out of range.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


SECONDS_PER_DAY = 86_400


@dataclass(frozen=True)
class WorkloadConfig:
    dau: int
    sessions_per_user: float
    requests_per_session: float
    payload_bytes: int
    read_write_ratio: float
    burst_factor: float
    retention_months: int


@dataclass(frozen=True)
class InfraConfig:
    replication_factor: int
    cache_hit_ratio: float
    index_overhead: float
    fan_out_per_write: float
    write_amplification: float
    instance_qps_capacity: float
    per_request_service_time_ms: float
    cache_hit_service_time_ms: float
    hot_data_fraction: float


@dataclass(frozen=True)
class CapacityConfig:
    target_buffer_pct: float
    cost_per_node_per_month_usd: float
    cold_tier_cost_multiplier: float
    replication_lag_budget_s: float


@dataclass(frozen=True)
class BenchmarkConfig:
    sample_requests: int
    sample_workers: int
    rng_seed: int


@dataclass(frozen=True)
class Config:
    workload: WorkloadConfig
    infra: InfraConfig
    capacity: CapacityConfig
    benchmark: BenchmarkConfig


def _require(section: dict, key: str, section_name: str):
    if key not in section:
        raise ValueError(f"config.{section_name}: missing required key '{key}'")
    return section[key]


def _validate(cfg: Config) -> None:
    w, i, c, b = cfg.workload, cfg.infra, cfg.capacity, cfg.benchmark

    if w.dau <= 0:
        raise ValueError("workload.dau must be > 0")
    if w.sessions_per_user <= 0:
        raise ValueError("workload.sessions_per_user must be > 0")
    if w.requests_per_session <= 0:
        raise ValueError("workload.requests_per_session must be > 0")
    if w.payload_bytes <= 0:
        raise ValueError("workload.payload_bytes must be > 0")
    if w.read_write_ratio < 0:
        raise ValueError("workload.read_write_ratio must be >= 0")
    if w.burst_factor < 1.0:
        raise ValueError("workload.burst_factor must be >= 1.0 (peak >= avg)")
    if w.retention_months <= 0:
        raise ValueError("workload.retention_months must be > 0")

    if i.replication_factor < 1:
        raise ValueError("infra.replication_factor must be >= 1")
    if not 0.0 <= i.cache_hit_ratio <= 1.0:
        raise ValueError("infra.cache_hit_ratio must be in [0, 1]")
    if i.index_overhead < 0:
        raise ValueError("infra.index_overhead must be >= 0")
    if i.fan_out_per_write < 0:
        raise ValueError("infra.fan_out_per_write must be >= 0")
    if i.write_amplification < 1.0:
        raise ValueError("infra.write_amplification must be >= 1.0")
    if i.instance_qps_capacity <= 0:
        raise ValueError("infra.instance_qps_capacity must be > 0")
    if i.per_request_service_time_ms <= 0:
        raise ValueError("infra.per_request_service_time_ms must be > 0")
    if i.cache_hit_service_time_ms < 0:
        raise ValueError("infra.cache_hit_service_time_ms must be >= 0")
    if not 0.0 < i.hot_data_fraction <= 1.0:
        raise ValueError("infra.hot_data_fraction must be in (0, 1]")

    if not 0.0 <= c.target_buffer_pct < 100.0:
        raise ValueError("capacity.target_buffer_pct must be in [0, 100)")
    if c.cost_per_node_per_month_usd < 0:
        raise ValueError("capacity.cost_per_node_per_month_usd must be >= 0")
    if c.cold_tier_cost_multiplier < 0:
        raise ValueError("capacity.cold_tier_cost_multiplier must be >= 0")
    if c.replication_lag_budget_s <= 0:
        raise ValueError("capacity.replication_lag_budget_s must be > 0")

    if b.sample_requests <= 0:
        raise ValueError("benchmark.sample_requests must be > 0")
    if b.sample_workers <= 0:
        raise ValueError("benchmark.sample_workers must be > 0")


def load_config(config_path: str | Path | None = None) -> Config:
    """Load and validate a Lab 1-3 config file.

    If ``config_path`` is ``None``, the lab-root ``config.yaml`` is used.
    Raises :class:`ValueError` with a section.key prefix on bad input,
    so the failure message tells students exactly which line to fix.
    """
    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    path = Path(config_path)

    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top-level YAML must be a mapping")

    workload = _require(raw, "workload", "")
    infra = _require(raw, "infra", "")
    capacity = _require(raw, "capacity", "")
    benchmark = _require(raw, "benchmark", "")

    cfg = Config(
        workload=WorkloadConfig(
            dau=int(_require(workload, "dau", "workload")),
            sessions_per_user=float(_require(workload, "sessions_per_user", "workload")),
            requests_per_session=float(_require(workload, "requests_per_session", "workload")),
            payload_bytes=int(_require(workload, "payload_bytes", "workload")),
            read_write_ratio=float(_require(workload, "read_write_ratio", "workload")),
            burst_factor=float(_require(workload, "burst_factor", "workload")),
            retention_months=int(_require(workload, "retention_months", "workload")),
        ),
        infra=InfraConfig(
            replication_factor=int(_require(infra, "replication_factor", "infra")),
            cache_hit_ratio=float(_require(infra, "cache_hit_ratio", "infra")),
            index_overhead=float(_require(infra, "index_overhead", "infra")),
            fan_out_per_write=float(_require(infra, "fan_out_per_write", "infra")),
            write_amplification=float(_require(infra, "write_amplification", "infra")),
            instance_qps_capacity=float(_require(infra, "instance_qps_capacity", "infra")),
            per_request_service_time_ms=float(
                _require(infra, "per_request_service_time_ms", "infra")
            ),
            cache_hit_service_time_ms=float(
                _require(infra, "cache_hit_service_time_ms", "infra")
            ),
            hot_data_fraction=float(infra.get("hot_data_fraction", 1.0)),
        ),
        capacity=CapacityConfig(
            target_buffer_pct=float(_require(capacity, "target_buffer_pct", "capacity")),
            cost_per_node_per_month_usd=float(
                _require(capacity, "cost_per_node_per_month_usd", "capacity")
            ),
            cold_tier_cost_multiplier=float(
                capacity.get("cold_tier_cost_multiplier", 0.10)
            ),
            replication_lag_budget_s=float(
                _require(capacity, "replication_lag_budget_s", "capacity")
            ),
        ),
        benchmark=BenchmarkConfig(
            sample_requests=int(_require(benchmark, "sample_requests", "benchmark")),
            sample_workers=int(_require(benchmark, "sample_workers", "benchmark")),
            rng_seed=int(benchmark.get("rng_seed", 42)),
        ),
    )

    _validate(cfg)
    return cfg
