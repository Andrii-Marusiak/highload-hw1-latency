#!/usr/bin/env python3

import sys
import time
import random
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

BASE_URL = "http://localhost:8080"

ENDPOINTS = [
    ("GET",  "/api/health"),
    ("GET",  "/api/users/{id}"),
    ("POST", "/api/orders"),
    ("GET",  "/api/slow"),
]

PHASES = [
    {"name": "warm-up",      "duration_s": 15,  "rps": 15,   "workers": 10},
    {"name": "steady-state", "duration_s": 30,  "rps": 80,   "workers": 40},
    {"name": "ramp-up",      "duration_s": 20,  "rps": 500,  "workers": 250},
    {"name": "saturation",   "duration_s": 60,  "rps": 2000, "workers": 1000},
    {"name": "error-flood",  "duration_s": 30,  "rps": 1200, "workers": 600},
    {"name": "cool-down",    "duration_s": 15,  "rps": 15,   "workers": 10},
]

ENDPOINT_WEIGHTS = {
    "warm-up":      [0.20, 0.30, 0.30, 0.20],
    "steady-state": [0.15, 0.25, 0.30, 0.30],
    "ramp-up":      [0.05, 0.10, 0.30, 0.55],
    "saturation":   [0.02, 0.05, 0.33, 0.60],
    "error-flood":  [0.02, 0.03, 0.90, 0.05],
    "cool-down":    [0.20, 0.30, 0.30, 0.20],
}


def make_request(method, path):
    url = BASE_URL + path
    start = time.perf_counter()
    try:
        if method == "GET":
            resp = requests.get(url, timeout=15)
        else:
            resp = requests.post(url, json={"item": "test"}, timeout=15)
        elapsed = time.perf_counter() - start
        return {
            "method": method,
            "path": path,
            "status": resp.status_code,
            "latency": elapsed,
            "error": resp.status_code >= 500,
        }
    except requests.exceptions.RequestException as exc:
        elapsed = time.perf_counter() - start
        return {
            "method": method,
            "path": path,
            "status": 0,
            "latency": elapsed,
            "error": True,
            "exception": str(exc),
        }


def pick_endpoint(phase_name):
    weights = ENDPOINT_WEIGHTS.get(phase_name, [0.25, 0.25, 0.25, 0.25])
    method, path = random.choices(ENDPOINTS, weights=weights, k=1)[0]
    if "{id}" in path:
        path = path.replace("{id}", str(random.randint(1, 1000)))
    return method, path


def run_phase(phase):
    name = phase["name"]
    duration = phase["duration_s"]
    rps = phase["rps"]
    workers = phase["workers"]
    interval = 1.0 / rps

    print(f"\n{'='*60}")
    print(f"  Phase: {name.upper()}")
    print(f"  Duration: {duration}s | Target RPS: {rps} | Workers: {workers}")
    print(f"{'='*60}")

    results = []
    submitted = 0
    start_time = time.time()
    end_time = start_time + duration
    last_progress = start_time

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = []
        while time.time() < end_time:
            method, path = pick_endpoint(name)
            futures.append(executor.submit(make_request, method, path))
            submitted += 1

            now = time.time()
            if now - last_progress >= 10:
                elapsed = now - start_time
                actual_rps = submitted / elapsed if elapsed > 0 else 0
                print(f"  [{name}] {elapsed:.0f}s elapsed | submitted: {submitted} | actual RPS: {actual_rps:.0f}")
                last_progress = now

            sleep_until = start_time + submitted * interval
            remaining = sleep_until - time.time()
            if remaining > 0:
                time.sleep(remaining)

        for future in as_completed(futures):
            results.append(future.result())

    elapsed_total = time.time() - start_time
    actual_rps = len(results) / elapsed_total if elapsed_total > 0 else 0
    print(f"  [{name}] Done: {len(results)} requests in {elapsed_total:.1f}s → {actual_rps:.0f} actual RPS")

    return results


def percentile(data, p):
    if not data:
        return 0
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * p / 100)
    idx = min(idx, len(sorted_data) - 1)
    return sorted_data[idx]


def print_phase_summary(name, results):
    total = len(results)
    errors = sum(1 for r in results if r["error"])
    latencies = [r["latency"] for r in results]

    error_rate = (errors / total * 100) if total > 0 else 0
    p50 = percentile(latencies, 50)
    p95 = percentile(latencies, 95)
    p99 = percentile(latencies, 99)
    avg = statistics.mean(latencies) if latencies else 0

    print(f"\n  [{name.upper()}] Summary:")
    print(f"    Total requests: {total}")
    print(f"    Errors:         {errors} ({error_rate:.1f}%)")
    print(f"    Latency avg:    {avg*1000:.1f}ms")
    print(f"    Latency p50:    {p50*1000:.1f}ms")
    print(f"    Latency p95:    {p95*1000:.1f}ms")
    print(f"    Latency p99:    {p99*1000:.1f}ms")

    return {
        "total": total,
        "errors": errors,
        "error_rate": error_rate,
        "p50": p50,
        "p95": p95,
        "p99": p99,
    }


def print_final_summary(all_results):
    total = len(all_results)
    errors = sum(1 for r in all_results if r["error"])
    latencies = [r["latency"] for r in all_results]

    error_rate = (errors / total * 100) if total > 0 else 0
    p50 = percentile(latencies, 50)
    p95 = percentile(latencies, 95)
    p99 = percentile(latencies, 99)
    avg = statistics.mean(latencies) if latencies else 0

    print(f"\n{'='*60}")
    print(f"  FINAL SUMMARY")
    print(f"{'='*60}")
    print(f"    Total requests: {total}")
    print(f"    Total errors:   {errors} ({error_rate:.1f}%)")
    print(f"    Latency avg:    {avg*1000:.1f}ms")
    print(f"    Latency p50:    {p50*1000:.1f}ms")
    print(f"    Latency p95:    {p95*1000:.1f}ms")
    print(f"    Latency p99:    {p99*1000:.1f}ms")
    print(f"{'='*60}")

    by_endpoint = {}
    for r in all_results:
        key = f"{r['method']} {r['path']}"
        if key not in by_endpoint:
            by_endpoint[key] = {"total": 0, "errors": 0, "latencies": []}
        by_endpoint[key]["total"] += 1
        by_endpoint[key]["latencies"].append(r["latency"])
        if r["error"]:
            by_endpoint[key]["errors"] += 1

    print(f"\n  Per-Endpoint Breakdown:")
    for endpoint, data in sorted(by_endpoint.items()):
        ep_error_rate = (data["errors"] / data["total"] * 100) if data["total"] > 0 else 0
        ep_p95 = percentile(data["latencies"], 95)
        print(f"    {endpoint}")
        print(f"      Requests: {data['total']} | Errors: {data['errors']} ({ep_error_rate:.1f}%) | p95: {ep_p95*1000:.1f}ms")


def main():
    print("Observability Stack Load Test")
    print(f"Target: {BASE_URL}")
    print(f"Phases: {' -> '.join(p['name'] for p in PHASES)}")

    try:
        resp = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if resp.status_code != 200:
            print(f"Health check failed with status {resp.status_code}")
            sys.exit(1)
    except requests.exceptions.RequestException as exc:
        print(f"Cannot reach service: {exc}")
        sys.exit(1)

    print("\nService is healthy. Starting load test...\n")

    all_results = []

    for phase in PHASES:
        phase_results = run_phase(phase)
        print_phase_summary(phase["name"], phase_results)
        all_results.extend(phase_results)

    print_final_summary(all_results)


if __name__ == "__main__":
    main()
