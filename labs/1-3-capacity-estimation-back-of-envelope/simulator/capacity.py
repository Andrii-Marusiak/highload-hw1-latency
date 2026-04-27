"""Capacity sizing: nodes, headroom, replication-lag estimate.

The two-scenario rule (Day 1 vs Month 12) and the buffer rule are
the headline outputs.  ``replication_lag_estimate_s`` uses a simple
M/M/1-flavoured queueing approximation:

    lag ~ (write_pressure / spare_capacity) * RF

where ``write_pressure`` is per-replica write QPS, ``spare_capacity``
is per-replica idle QPS, and the leading factor is clamped so the
estimate behaves sensibly when the system is highly under- or
over-utilised.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from simulator.config import Config
from simulator.workload import WorkloadProfile


@dataclass(frozen=True)
class CapacityProfile:
    target_node_qps_at_buffer: float
    nodes_required: int
    provisioned_qps_capacity: float
    utilisation_pct_at_peak: float
    headroom_pct_at_peak: float
    replication_lag_estimate_s: float


def derive_capacity(config: Config, workload: WorkloadProfile) -> CapacityProfile:
    i = config.infra
    c = config.capacity

    effective_node_qps = i.instance_qps_capacity * (1.0 - c.target_buffer_pct / 100.0)

    storage_qps = workload.effective_storage_read_qps + workload.effective_storage_write_qps
    nodes_for_storage = math.ceil(storage_qps / effective_node_qps) if effective_node_qps > 0 else 0
    nodes_for_durability = i.replication_factor
    nodes_required = max(nodes_for_storage, nodes_for_durability)

    provisioned = nodes_required * i.instance_qps_capacity
    utilisation = (storage_qps / provisioned * 100.0) if provisioned > 0 else 0.0
    headroom = max(0.0, 100.0 - utilisation)

    per_replica_write = workload.effective_storage_write_qps / max(1, i.replication_factor)
    per_replica_capacity = i.instance_qps_capacity
    rho = per_replica_write / per_replica_capacity if per_replica_capacity > 0 else 1.0
    rho = min(rho, 0.99)
    base_service_s = i.per_request_service_time_ms / 1000.0
    queue_factor = rho / (1.0 - rho) if rho < 1 else 100.0
    replication_lag = base_service_s * queue_factor * i.replication_factor
    replication_lag = max(0.0, replication_lag)

    return CapacityProfile(
        target_node_qps_at_buffer=effective_node_qps,
        nodes_required=int(nodes_required),
        provisioned_qps_capacity=provisioned,
        utilisation_pct_at_peak=utilisation,
        headroom_pct_at_peak=headroom,
        replication_lag_estimate_s=replication_lag,
    )
