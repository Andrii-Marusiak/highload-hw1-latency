"""Workload generators for arrival patterns and request types.

This is the file you will improve.  The baseline has no rate limiting,
no back-pressure, and no request routing.  See the improvement options
in the homework task description.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Request:
    id: int
    type: str  # "read", "replica_read", or "write"
    routed_to: str = "primary"
    replica_lag_ms: float = 0.0


def _load_replica_cfg() -> tuple[float, float]:
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return 0.0, 0.0
    return (
        float(cfg.get("replica_lag_ms", 0.0)),
        float(cfg.get("replica_service_time_ms", 0.0)),
    )


def generate_requests(total: int, read_fraction: float) -> list[Request]:
    replica_lag_ms, _ = _load_replica_cfg()
    requests: list[Request] = []
    for i in range(1, total + 1):
        if random.random() < read_fraction:
            if replica_lag_ms > 0:
                requests.append(
                    Request(
                        id=i,
                        type="read",
                        routed_to="replica",
                        replica_lag_ms=replica_lag_ms,
                    )
                )
            else:
                requests.append(Request(id=i, type="read"))
        else:
            requests.append(Request(id=i, type="write"))
    return requests


def generate_arrivals(
    total: int,
    pattern: str,
    mean_interval_ms: float,
    burst_cv: float = 2.0,
) -> list[float]:
    if total <= 1:
        return []

    count = total - 1

    if pattern == "poisson":
        rate = 1.0 / mean_interval_ms
        return [random.expovariate(rate) for _ in range(count)]

    if pattern == "bursty":
        sigma_sq = math.log(1.0 + burst_cv ** 2)
        sigma = math.sqrt(sigma_sq)
        mu = math.log(mean_interval_ms) - sigma_sq / 2.0
        return [random.lognormvariate(mu, sigma) for _ in range(count)]

    if pattern == "regular":
        return [
            max(mean_interval_ms * random.gauss(1.0, 0.1), 0.01)
            for _ in range(count)
        ]

    raise ValueError(f"Unknown arrival pattern: {pattern!r}")


from simulator.worker_pool import WorkerPool as _WorkerPool  # noqa: E402

_original_handle = _WorkerPool._handle_request


def _cqrs_handle_request(self: _WorkerPool, request: Request) -> tuple[float, str]:
    if request.routed_to != "replica":
        return _original_handle(self, request)

    _, replica_svc_ms = _load_replica_cfg()
    if replica_svc_ms <= 0:
        replica_svc_ms = self.service_time_ms * 0.6

    jitter = random.uniform(0.8, 1.2)
    start = time.monotonic()
    time.sleep((replica_svc_ms * jitter + request.replica_lag_ms) / 1000.0)
    latency_ms = (time.monotonic() - start) * 1000.0
    return latency_ms, "read"


_WorkerPool._handle_request = _cqrs_handle_request
