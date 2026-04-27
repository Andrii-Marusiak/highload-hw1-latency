"""Orchestrator: load config, derive every profile, print the report.

Output is grouped into seven sections so it maps 1:1 onto the homework
grading dimensions:

    INPUTS / THROUGHPUT / LATENCY / STORAGE / BANDWIDTH / CAPACITY / COST

``run_benchmark`` returns a flat dictionary of all metrics so tests can
assert on values without re-parsing stdout.
"""

from __future__ import annotations

import time
from pathlib import Path

from simulator.capacity import derive_capacity
from simulator.config import Config, load_config
from simulator.cost import derive_cost
from simulator.network import derive_bandwidth
from simulator.service import run_benchmark_sample
from simulator.storage import derive_storage, GB, TB
from simulator.workload import derive_workload


_SEPARATOR = "=" * 72
_SECTION = "-" * 72
MB = 1024 ** 2


def _fmt_bytes(n: float) -> str:
    if n >= TB:
        return f"{n / TB:>8.2f} TB"
    if n >= GB:
        return f"{n / GB:>8.2f} GB"
    if n >= MB:
        return f"{n / MB:>8.2f} MB"
    return f"{n:>8.0f}  B"


def _fmt_bw(bytes_per_second: float) -> str:
    return f"{bytes_per_second / MB:>8.2f} MB/s"


def _fmt_qps(qps: float) -> str:
    if qps >= 1_000_000:
        return f"{qps / 1_000_000:>8.2f} M req/s"
    if qps >= 1_000:
        return f"{qps / 1_000:>8.2f} k req/s"
    return f"{qps:>10.2f} req/s"


def _print_report(
    config: Config,
    metrics: dict,
) -> None:
    w = config.workload
    i = config.infra
    cap = config.capacity

    print(_SEPARATOR)
    print("LAB 1-3 BENCHMARK: Capacity Estimation (Back of Envelope)")
    print(_SEPARATOR)
    print()

    print("INPUTS")
    print(_SECTION)
    print(
        f"  DAU: {w.dau:,}   sessions/user: {w.sessions_per_user}   "
        f"req/session: {w.requests_per_session}"
    )
    print(
        f"  payload: {w.payload_bytes} B   R:W = {w.read_write_ratio}:1   "
        f"burst x{w.burst_factor}   retention: {w.retention_months} mo"
    )
    print(
        f"  RF: {i.replication_factor}   cache hit (cfg): {i.cache_hit_ratio:.2f}   "
        f"index overhead: {i.index_overhead:.0%}   "
        f"write amp: {i.write_amplification}"
    )
    print(
        f"  fan-out/write: {i.fan_out_per_write}   "
        f"instance QPS cap: {i.instance_qps_capacity:,.0f}   "
        f"hot fraction: {i.hot_data_fraction:.0%}"
    )
    print(
        f"  service time: storage {i.per_request_service_time_ms} ms / "
        f"cache {i.cache_hit_service_time_ms} ms   "
        f"target buffer: {cap.target_buffer_pct:.0f}%"
    )
    print()

    print("THROUGHPUT")
    print(_SECTION)
    print(f"  Daily requests:           {metrics['daily_requests']:>14,}")
    print(f"  Avg total QPS:           {_fmt_qps(metrics['avg_total_qps'])}")
    print(f"  Peak total QPS:          {_fmt_qps(metrics['peak_total_qps'])}")
    print(f"  Peak read QPS:           {_fmt_qps(metrics['peak_read_qps'])}")
    print(f"  Peak write QPS:          {_fmt_qps(metrics['peak_write_qps'])}")
    print(
        f"  Effective storage QPS:   {_fmt_qps(metrics['effective_storage_read_qps'] + metrics['effective_storage_write_qps'])}    "
        f"(after cache + write amp)"
    )
    print()

    print(f"LATENCY ({metrics['latency_count']:,}-sample benchmark, {metrics['latency_duration_s']:.2f} s wall)")
    print(_SECTION)
    print(f"  p50:                          {metrics['p50_ms']:>8.2f} ms")
    print(f"  p95:                          {metrics['p95_ms']:>8.2f} ms")
    print(f"  p99:                          {metrics['p99_ms']:>8.2f} ms")
    print(f"  mean:                         {metrics['mean_ms']:>8.2f} ms")
    print(
        f"  cache hit rate (observed):    {metrics['observed_hit_rate']:>8.3f}   "
        f"(cfg: {i.cache_hit_ratio:.3f})"
    )
    print()

    print("STORAGE (with replication, indexes, write amplification)")
    print(_SECTION)
    print(f"  Daily writes:             {metrics['daily_write_count']:>14,}")
    print(f"  Daily raw growth:         {_fmt_bytes(metrics['daily_raw_growth_bytes'])}")
    print(f"  Daily replicated growth:  {_fmt_bytes(metrics['daily_replicated_growth_bytes'])}")
    print(f"  Storage at {w.retention_months} mo:           {_fmt_bytes(metrics['storage_at_retention_bytes'])}")
    if i.hot_data_fraction < 1.0:
        print(f"  Hot tier  ({i.hot_data_fraction:.0%}):           {_fmt_bytes(metrics['hot_storage_at_retention_bytes'])}")
        print(f"  Cold tier ({1 - i.hot_data_fraction:.0%}):           {_fmt_bytes(metrics['cold_storage_at_retention_bytes'])}")
    print()

    print("BANDWIDTH (peak)")
    print(_SECTION)
    print(f"  Ingress (writes + reads in):  {_fmt_bw(metrics['ingress_bytes_per_second'])}")
    print(f"  Egress (reads out):           {_fmt_bw(metrics['egress_bytes_per_second'])}")
    print(f"  Replication egress:           {_fmt_bw(metrics['replication_egress_bytes_per_second'])}")
    print(f"  Fan-out egress:               {_fmt_bw(metrics['fan_out_egress_bytes_per_second'])}")
    print(f"  Total egress:                 {_fmt_bw(metrics['total_egress_bytes_per_second'])}")
    print()

    print("CAPACITY")
    print(_SECTION)
    print(f"  Nodes required:               {metrics['nodes_required']:>4d}")
    print(f"  Provisioned QPS:           {_fmt_qps(metrics['provisioned_qps_capacity'])}")
    print(f"  Utilisation at peak:          {metrics['utilisation_pct_at_peak']:>8.2f} %")
    print(f"  Headroom at peak:             {metrics['headroom_pct_at_peak']:>8.2f} %    (target: >= {cap.target_buffer_pct:.0f}%)")
    lag_s = metrics['replication_lag_estimate_s']
    lag_marker = " (within budget)" if lag_s <= cap.replication_lag_budget_s else " (OVER BUDGET)"
    print(f"  Replication lag (est):        {lag_s:>8.2f} s    (budget: {cap.replication_lag_budget_s:.1f} s){lag_marker}")
    print()

    print("COST")
    print(_SECTION)
    print(f"  Monthly compute:           ${metrics['monthly_compute_usd']:>12,.2f}")
    print(f"  Monthly hot storage:       ${metrics['monthly_hot_storage_usd']:>12,.2f}")
    if i.hot_data_fraction < 1.0:
        print(f"  Monthly cold storage:      ${metrics['monthly_cold_storage_usd']:>12,.2f}")
    print(f"  Monthly TOTAL:             ${metrics['monthly_total_usd']:>12,.2f}")
    print(f"  Cost per 1k QPS:           ${metrics['cost_per_1k_qps_usd']:>12,.4f}")
    print()
    print(_SEPARATOR)


def run_benchmark(config_path: str | Path | None = None) -> dict:
    """Run the lab 1-3 benchmark suite and return a flat metrics dict."""
    config = load_config(config_path)
    workload = derive_workload(config)
    storage = derive_storage(config, workload)
    bandwidth = derive_bandwidth(config, workload)
    capacity = derive_capacity(config, workload)
    cost = derive_cost(config, workload, storage, capacity)

    bench_start = time.monotonic()
    latency = run_benchmark_sample(config, workload)
    bench_duration = time.monotonic() - bench_start

    metrics = {
        # workload
        "daily_requests": workload.daily_requests,
        "avg_total_qps": workload.avg_total_qps,
        "peak_total_qps": workload.peak_total_qps,
        "avg_read_qps": workload.avg_read_qps,
        "avg_write_qps": workload.avg_write_qps,
        "peak_read_qps": workload.peak_read_qps,
        "peak_write_qps": workload.peak_write_qps,
        "effective_storage_read_qps": workload.effective_storage_read_qps,
        "effective_storage_write_qps": workload.effective_storage_write_qps,
        # storage
        "daily_write_count": storage.daily_write_count,
        "daily_raw_growth_bytes": storage.daily_raw_growth_bytes,
        "daily_replicated_growth_bytes": storage.daily_replicated_growth_bytes,
        "storage_at_retention_bytes": storage.storage_at_retention_bytes,
        "hot_storage_at_retention_bytes": storage.hot_storage_at_retention_bytes,
        "cold_storage_at_retention_bytes": storage.cold_storage_at_retention_bytes,
        # bandwidth
        "ingress_bytes_per_second": bandwidth.ingress_bytes_per_second,
        "egress_bytes_per_second": bandwidth.egress_bytes_per_second,
        "replication_egress_bytes_per_second": bandwidth.replication_egress_bytes_per_second,
        "fan_out_egress_bytes_per_second": bandwidth.fan_out_egress_bytes_per_second,
        "total_egress_bytes_per_second": bandwidth.total_egress_bytes_per_second,
        # capacity
        "target_node_qps_at_buffer": capacity.target_node_qps_at_buffer,
        "nodes_required": capacity.nodes_required,
        "provisioned_qps_capacity": capacity.provisioned_qps_capacity,
        "utilisation_pct_at_peak": capacity.utilisation_pct_at_peak,
        "headroom_pct_at_peak": capacity.headroom_pct_at_peak,
        "replication_lag_estimate_s": capacity.replication_lag_estimate_s,
        # cost
        "monthly_compute_usd": cost.monthly_compute_usd,
        "monthly_hot_storage_usd": cost.monthly_hot_storage_usd,
        "monthly_cold_storage_usd": cost.monthly_cold_storage_usd,
        "monthly_total_usd": cost.monthly_total_usd,
        "cost_per_1k_qps_usd": cost.cost_per_1k_qps_usd,
        # latency benchmark
        "latency_count": latency.count,
        "mean_ms": latency.mean_ms,
        "p50_ms": latency.p50_ms,
        "p95_ms": latency.p95_ms,
        "p99_ms": latency.p99_ms,
        "observed_hit_rate": latency.observed_hit_rate,
        "cache_hits": latency.cache_hits,
        "cache_misses": latency.cache_misses,
        "latency_duration_s": bench_duration,
    }

    _print_report(config, metrics)
    return metrics
