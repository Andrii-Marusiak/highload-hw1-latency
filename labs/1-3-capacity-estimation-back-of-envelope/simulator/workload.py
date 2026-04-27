"""Derive QPS profile (avg, peak, R/W split, post-cache storage QPS).

This is the deterministic part of the back-of-envelope:

    daily_requests = DAU * sessions_per_user * requests_per_session
    avg_total_qps  = daily_requests / 86400
    peak_total_qps = avg_total_qps * burst_factor
    read_share     = read_write_ratio / (read_write_ratio + 1)
    write_share    = 1 - read_share

The cache hit ratio is applied to derive the *effective* storage read
QPS, i.e. the load the storage tier actually has to serve.
"""

from __future__ import annotations

from dataclasses import dataclass

from simulator.config import SECONDS_PER_DAY, Config


@dataclass(frozen=True)
class WorkloadProfile:
    daily_requests: int
    avg_total_qps: float
    peak_total_qps: float
    avg_read_qps: float
    avg_write_qps: float
    peak_read_qps: float
    peak_write_qps: float
    effective_storage_read_qps: float
    effective_storage_write_qps: float


def derive_workload(config: Config) -> WorkloadProfile:
    w = config.workload
    i = config.infra

    daily_requests = int(w.dau * w.sessions_per_user * w.requests_per_session)
    avg_total = daily_requests / SECONDS_PER_DAY
    peak_total = avg_total * w.burst_factor

    read_share = w.read_write_ratio / (w.read_write_ratio + 1.0)
    write_share = 1.0 - read_share

    avg_read = avg_total * read_share
    avg_write = avg_total * write_share
    peak_read = peak_total * read_share
    peak_write = peak_total * write_share

    effective_storage_read = peak_read * (1.0 - i.cache_hit_ratio)
    effective_storage_write = peak_write * i.write_amplification

    return WorkloadProfile(
        daily_requests=daily_requests,
        avg_total_qps=avg_total,
        peak_total_qps=peak_total,
        avg_read_qps=avg_read,
        avg_write_qps=avg_write,
        peak_read_qps=peak_read,
        peak_write_qps=peak_write,
        effective_storage_read_qps=effective_storage_read,
        effective_storage_write_qps=effective_storage_write,
    )
