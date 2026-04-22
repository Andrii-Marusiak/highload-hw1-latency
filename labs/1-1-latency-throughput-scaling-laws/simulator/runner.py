"""Benchmark runner -- loads config, runs all three workload conditions,
and prints a formatted report to stdout."""

from __future__ import annotations

import os
import time
from pathlib import Path

import yaml

from simulator.metrics import MetricsCollector
from simulator.worker_pool import WorkerPool
from simulator.workload import generate_parallel, generate_saturated, generate_serial

_SEPARATOR = "=" * 60


def load_config(config_path: str | Path | None = None) -> dict:
    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    config_path = Path(config_path)
    with open(config_path) as f:
        return yaml.safe_load(f)


def _run_condition(
    label: str,
    workers: int,
    request_ids: list[int],
    service_time_ms: float,
    inter_arrival_ms: float | None = None,
) -> dict:
    pool = WorkerPool(workers=workers, service_time_ms=service_time_ms)
    collector = MetricsCollector()

    start = time.monotonic()
    if inter_arrival_ms is not None:
        pool.run_with_arrival_rate(request_ids, collector, inter_arrival_ms)
    else:
        pool.run(request_ids, collector)
    duration_s = time.monotonic() - start

    summary = collector.summary(duration_s)
    summary["condition"] = label
    summary["workers"] = workers
    summary["duration_s"] = round(duration_s, 3)
    return summary


def _worker_counts_for_sweep(max_workers: int) -> list[int]:
    out: list[int] = []
    w = 2
    while w <= max_workers:
        out.append(w)
        w *= 2
    return out


def _find_optimal_workers(
    service_time_ms: float,
    serial_mean_ms: float,
    probe_requests: int,
    max_workers: int,
    fallback_workers: int,
) -> tuple[int, list[dict]]:
    p95_threshold = 2.0 * serial_mean_ms
    counts = _worker_counts_for_sweep(max_workers)
    if not counts:
        return max(2, min(fallback_workers, max(1, max_workers))), []

    sweep_results: list[dict] = []
    best_workers = max(2, min(fallback_workers, max_workers))
    prev_throughput: float | None = None

    for w in counts:
        n = max(probe_requests, w, 10)
        probe_ids = list(range(1, n + 1))
        r = _run_condition("Probe", w, probe_ids, service_time_ms)

        if r["p95_ms"] > p95_threshold:
            sweep_results.append(
                {
                    "workers": w,
                    "throughput_rps": r["throughput_rps"],
                    "p95_ms": r["p95_ms"],
                    "status": "OVER THRESHOLD",
                }
            )
            break

        if prev_throughput is not None and r["throughput_rps"] < prev_throughput:
            sweep_results.append(
                {
                    "workers": w,
                    "throughput_rps": r["throughput_rps"],
                    "p95_ms": r["p95_ms"],
                    "status": "THROUGHPUT REGRESSION",
                }
            )
            break

        sweep_results.append(
            {
                "workers": w,
                "throughput_rps": r["throughput_rps"],
                "p95_ms": r["p95_ms"],
                "status": "ok",
            }
        )
        best_workers = w
        prev_throughput = r["throughput_rps"]

    return best_workers, sweep_results


def _print_worker_sweep(
    sweep_results: list[dict],
    p95_threshold: float,
    optimal_workers: int,
) -> None:
    print("WORKER SWEEP")
    print(f"(threshold p95 <= {p95_threshold:.2f} ms)")
    print()

    header = f"{'Workers':>7} {'Throughput':>12} {'p95(ms)':>9} {'Status':<20}"
    print(header)
    print("-" * len(header))

    for row in sweep_results:
        print(
            f"{row['workers']:>7} {row['throughput_rps']:>10.2f} r/s "
            f"{row['p95_ms']:>9.2f} {row['status']:<20}"
        )

    print()
    print(f"=> Optimal workers: {optimal_workers}")
    print()


def _print_report(results: list[dict]) -> None:
    print(_SEPARATOR)
    print("BENCHMARK RESULTS")
    print(_SEPARATOR)
    print()

    header = (
        f"{'Condition':<12} {'Workers':>7} {'Requests':>8} {'Rejected':>8} "
        f"{'Mean(ms)':>9} {'p95(ms)':>9} {'Throughput':>12} {'Duration':>10}"
    )
    print(header)
    print("-" * len(header))

    for r in results:
        print(
            f"{r['condition']:<12} {r['workers']:>7} {r['count']:>8} "
            f"{r['rejected']:>8} {r['mean_ms']:>9.2f} {r['p95_ms']:>9.2f} "
            f"{r['throughput_rps']:>10.2f} r/s {r['duration_s']:>8.3f} s"
        )

    print()
    print(_SEPARATOR)


def run_benchmark(config_path: str | Path | None = None) -> list[dict]:
    """Run the full benchmark suite and return results."""
    cfg = load_config(config_path)

    service_time_ms: float = cfg.get("service_time_ms", 10)
    fallback_workers: int = cfg.get("workers", os.cpu_count() or 4)
    total_requests: int = cfg.get("total_requests", 500)
    saturated_multiplier: int = cfg.get("saturated_multiplier", 3)
    max_workers: int = int(cfg.get("max_workers", 64))
    probe_requests: int = int(cfg.get("probe_requests", 100))

    print(
        f"Config: service_time={service_time_ms}ms, workers=auto(max={max_workers}), "
        f"probe={probe_requests}, requests={total_requests}, "
        f"saturated_multiplier={saturated_multiplier}"
    )
    print()

    results: list[dict] = []

    serial_ids = generate_serial(total_requests)
    results.append(
        _run_condition("Serial", 1, serial_ids, service_time_ms)
    )

    serial_mean = results[0]["mean_ms"]
    p95_threshold = 2.0 * serial_mean
    optimal_workers, sweep_rows = _find_optimal_workers(
        service_time_ms,
        serial_mean,
        probe_requests,
        max_workers,
        fallback_workers,
    )
    _print_worker_sweep(sweep_rows, p95_threshold, optimal_workers)

    parallel_ids = generate_parallel(total_requests)
    results.append(
        _run_condition("Parallel", optimal_workers, parallel_ids, service_time_ms)
    )

    saturated_ids = generate_saturated(total_requests, saturated_multiplier)
    capacity_rps = optimal_workers / (service_time_ms / 1000.0)
    overload_rps = capacity_rps * 1.5
    inter_arrival_ms = 1000.0 / overload_rps
    results.append(
        _run_condition(
            "Saturated",
            optimal_workers,
            saturated_ids,
            service_time_ms,
            inter_arrival_ms=inter_arrival_ms,
        )
    )

    _print_report(results)
    return results
