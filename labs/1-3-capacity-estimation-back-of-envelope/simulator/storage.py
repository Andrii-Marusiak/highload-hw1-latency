"""Storage growth math: replication, indexing, retention, tiering.

The mistake students typically make in their first estimate is to
multiply ``daily_writes * payload_bytes`` and stop there.  This module
encodes the multipliers that almost always appear in real systems:

* Index overhead (B-tree / inverted-index / vector-index bloat).
* Replication factor (full copies for durability and read scaling).
* Write amplification (journals, compaction, WAL).
* Retention window (how long writes are kept on hot storage).
* Optional hot/cold tiering (only ``hot_data_fraction`` lives on hot disks).
"""

from __future__ import annotations

from dataclasses import dataclass

from simulator.config import Config
from simulator.workload import WorkloadProfile


GB = 1024 ** 3
TB = 1024 ** 4
DAYS_PER_MONTH = 30


@dataclass(frozen=True)
class StorageProfile:
    daily_write_count: int
    daily_raw_growth_bytes: float
    daily_replicated_growth_bytes: float
    storage_at_retention_bytes: float
    hot_storage_at_retention_bytes: float
    cold_storage_at_retention_bytes: float


def derive_storage(config: Config, workload: WorkloadProfile) -> StorageProfile:
    i = config.infra
    w = config.workload

    avg_writes_per_second = workload.avg_write_qps
    daily_write_count = int(avg_writes_per_second * 86_400)

    record_size_bytes = float(w.payload_bytes) * (1.0 + i.index_overhead)
    daily_raw = avg_writes_per_second * 86_400 * record_size_bytes * i.write_amplification
    daily_replicated = daily_raw * i.replication_factor

    retention_days = w.retention_months * DAYS_PER_MONTH
    total = daily_replicated * retention_days

    hot = total * i.hot_data_fraction
    cold = total - hot

    return StorageProfile(
        daily_write_count=daily_write_count,
        daily_raw_growth_bytes=daily_raw,
        daily_replicated_growth_bytes=daily_replicated,
        storage_at_retention_bytes=total,
        hot_storage_at_retention_bytes=hot,
        cold_storage_at_retention_bytes=cold,
    )
