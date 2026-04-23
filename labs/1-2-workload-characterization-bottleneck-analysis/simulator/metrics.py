"""Thread-safe metrics collector with per-type latency tracking,
inter-arrival statistics, and resource utilisation reporting."""

from __future__ import annotations

import statistics
import threading


class MetricsCollector:
    """Collects per-request latencies (split by type), inter-arrival
    intervals, and computes summary statistics including resource
    utilisation and bottleneck identification."""

    def __init__(self) -> None:
        self._latencies: list[float] = []
        self._read_latencies: list[float] = []
        self._write_latencies: list[float] = []
        self._inter_arrivals: list[float] = []
        self._lock = threading.Lock()
        self._rejected = 0

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(self, latency_ms: float, request_type: str = "read") -> None:
        with self._lock:
            self._latencies.append(latency_ms)
            if request_type == "read":
                self._read_latencies.append(latency_ms)
            else:
                self._write_latencies.append(latency_ms)

    def record_rejection(self) -> None:
        with self._lock:
            self._rejected += 1

    def record_inter_arrival(self, interval_ms: float) -> None:
        with self._lock:
            self._inter_arrivals.append(interval_ms)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._latencies)

    @property
    def read_count(self) -> int:
        with self._lock:
            return len(self._read_latencies)

    @property
    def write_count(self) -> int:
        with self._lock:
            return len(self._write_latencies)

    @property
    def rejected(self) -> int:
        with self._lock:
            return self._rejected

    # ------------------------------------------------------------------
    # Statistics helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _mean(values: list[float]) -> float:
        return statistics.mean(values) if values else 0.0

    @staticmethod
    def _p95(values: list[float]) -> float:
        if not values:
            return 0.0
        s = sorted(values)
        idx = min(int(len(s) * 0.95), len(s) - 1)
        return s[idx]

    @staticmethod
    def _stdev(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        return statistics.stdev(values)

    def mean(self) -> float:
        with self._lock:
            return self._mean(self._latencies)

    def p95(self) -> float:
        with self._lock:
            return self._p95(self._latencies)

    def throughput(self, duration_s: float) -> float:
        with self._lock:
            if duration_s <= 0:
                return 0.0
            return len(self._latencies) / duration_s

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(
        self,
        duration_s: float,
        *,
        workers: int = 1,
        io_workers: int = 1,
        read_fraction: float = 1.0,
        service_time_ms: float = 10.0,
        write_service_time_ms: float = 15.0,
    ) -> dict:
        """Return a dict with all benchmark metrics.

        Resource utilisation is computed analytically from the observed
        throughput so that the numbers map cleanly to M/M/1 theory.
        """
        with self._lock:
            if not self._latencies:
                return {
                    "mean_ms": 0.0,
                    "p95_ms": 0.0,
                    "count": 0,
                    "read_count": 0,
                    "write_count": 0,
                    "rejected": self._rejected,
                    "throughput_rps": 0.0,
                    "read_mean_ms": 0.0,
                    "read_p95_ms": 0.0,
                    "write_mean_ms": 0.0,
                    "write_p95_ms": 0.0,
                    "inter_arrival_mean_ms": 0.0,
                    "inter_arrival_std_ms": 0.0,
                    "cv": 0.0,
                    "conn_pool_util": 0.0,
                    "io_util": 0.0,
                    "bottleneck_resource": "connection_pool",
                    "bottleneck_util": 0.0,
                }

            total = len(self._latencies)
            rps = total / max(duration_s, 1e-9)

            # Per-type stats
            read_mean = self._mean(self._read_latencies)
            read_p95 = self._p95(self._read_latencies)
            write_mean = self._mean(self._write_latencies)
            write_p95 = self._p95(self._write_latencies)

            # Inter-arrival stats
            ia_mean = self._mean(self._inter_arrivals)
            ia_std = self._stdev(self._inter_arrivals)
            cv = (ia_std / ia_mean) if ia_mean > 0 else 0.0

            # Analytical resource utilisation
            actual_read_frac = len(self._read_latencies) / total if total else read_fraction
            avg_svc_s = (
                actual_read_frac * service_time_ms
                + (1.0 - actual_read_frac) * write_service_time_ms
            ) / 1000.0
            conn_util = rps * avg_svc_s / max(workers, 1)

            write_rps = rps * (1.0 - actual_read_frac)
            io_util = write_rps * (write_service_time_ms / 1000.0) / max(io_workers, 1)

            if io_util >= conn_util:
                bottleneck_resource = "io_subsystem"
                bottleneck_util = io_util
            else:
                bottleneck_resource = "connection_pool"
                bottleneck_util = conn_util

            sorted_lat = sorted(self._latencies)
            p95_idx = min(int(len(sorted_lat) * 0.95), len(sorted_lat) - 1)

            return {
                "mean_ms": round(statistics.mean(self._latencies), 2),
                "p95_ms": round(sorted_lat[p95_idx], 2),
                "count": total,
                "read_count": len(self._read_latencies),
                "write_count": len(self._write_latencies),
                "rejected": self._rejected,
                "throughput_rps": round(rps, 2),
                "read_mean_ms": round(read_mean, 2),
                "read_p95_ms": round(read_p95, 2),
                "write_mean_ms": round(write_mean, 2),
                "write_p95_ms": round(write_p95, 2),
                "inter_arrival_mean_ms": round(ia_mean, 2),
                "inter_arrival_std_ms": round(ia_std, 2),
                "cv": round(cv, 2),
                "conn_pool_util": round(conn_util * 100, 1),
                "io_util": round(io_util * 100, 1),
                "bottleneck_resource": bottleneck_resource,
                "bottleneck_util": round(bottleneck_util * 100, 1),
            }

    def reset(self) -> None:
        with self._lock:
            self._latencies.clear()
            self._read_latencies.clear()
            self._write_latencies.clear()
            self._inter_arrivals.clear()
            self._rejected = 0
