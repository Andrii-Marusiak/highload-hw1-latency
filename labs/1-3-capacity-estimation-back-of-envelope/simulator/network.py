"""Bandwidth model.

Three classes of traffic dominate the bandwidth bill for a typical
high-load read-heavy service:

* **Ingress** -- request payloads coming in (write payloads + read
  request bodies; we approximate as ``peak_total_qps * payload_bytes``).
* **Egress** -- response payloads going out, dominated by reads
  (``peak_read_qps * payload_bytes``).
* **Replication egress** -- copies of every write shipped to ``RF - 1``
  replica nodes.
* **Fan-out egress** -- async change events emitted per write
  (search indexer, audit log, cache invalidator, ...).
"""

from __future__ import annotations

from dataclasses import dataclass

from simulator.config import Config
from simulator.workload import WorkloadProfile


MB = 1024 ** 2


@dataclass(frozen=True)
class BandwidthProfile:
    ingress_bytes_per_second: float
    egress_bytes_per_second: float
    replication_egress_bytes_per_second: float
    fan_out_egress_bytes_per_second: float
    total_egress_bytes_per_second: float


def derive_bandwidth(config: Config, workload: WorkloadProfile) -> BandwidthProfile:
    i = config.infra
    payload = float(config.workload.payload_bytes)

    ingress = workload.peak_total_qps * payload
    egress = workload.peak_read_qps * payload
    replication = workload.peak_write_qps * payload * max(0, i.replication_factor - 1)
    fan_out = workload.peak_write_qps * payload * i.fan_out_per_write

    return BandwidthProfile(
        ingress_bytes_per_second=ingress,
        egress_bytes_per_second=egress,
        replication_egress_bytes_per_second=replication,
        fan_out_egress_bytes_per_second=fan_out,
        total_egress_bytes_per_second=egress + replication + fan_out,
    )
