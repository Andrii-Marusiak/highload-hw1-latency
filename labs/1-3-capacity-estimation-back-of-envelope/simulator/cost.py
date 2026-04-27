"""Cost-per-unit calculations.

Two figures matter for the homework's cost reasoning:

* **Monthly infra cost** -- ``nodes * cost_per_node_per_month`` plus a
  storage cost line that splits hot vs cold tiers.  Storage cost is
  computed as a fraction of the node cost so that the model stays
  self-contained (no separate ``$/GB`` knob), while still rewarding
  tiering.
* **Cost per 1k QPS** -- normalises the monthly bill against the peak
  served QPS so that adding caching, reducing RF, or vertical-scaling
  shows up as a clear directional change.
"""

from __future__ import annotations

from dataclasses import dataclass

from simulator.capacity import CapacityProfile
from simulator.config import Config
from simulator.storage import StorageProfile, GB
from simulator.workload import WorkloadProfile


SECONDS_PER_MONTH = 30 * 86_400
HOT_STORAGE_USD_PER_GB_MONTH = 0.10


@dataclass(frozen=True)
class CostProfile:
    monthly_compute_usd: float
    monthly_hot_storage_usd: float
    monthly_cold_storage_usd: float
    monthly_total_usd: float
    cost_per_1k_qps_usd: float


def derive_cost(
    config: Config,
    workload: WorkloadProfile,
    storage: StorageProfile,
    capacity: CapacityProfile,
) -> CostProfile:
    c = config.capacity

    monthly_compute = capacity.nodes_required * c.cost_per_node_per_month_usd

    hot_gb = storage.hot_storage_at_retention_bytes / GB
    cold_gb = storage.cold_storage_at_retention_bytes / GB
    monthly_hot_storage = hot_gb * HOT_STORAGE_USD_PER_GB_MONTH
    monthly_cold_storage = cold_gb * HOT_STORAGE_USD_PER_GB_MONTH * c.cold_tier_cost_multiplier

    monthly_total = monthly_compute + monthly_hot_storage + monthly_cold_storage

    served_qps_per_month = workload.peak_total_qps
    cost_per_1k_qps = (
        monthly_total / (served_qps_per_month / 1000.0) if served_qps_per_month > 0 else 0.0
    )

    return CostProfile(
        monthly_compute_usd=monthly_compute,
        monthly_hot_storage_usd=monthly_hot_storage,
        monthly_cold_storage_usd=monthly_cold_storage,
        monthly_total_usd=monthly_total,
        cost_per_1k_qps_usd=cost_per_1k_qps,
    )
