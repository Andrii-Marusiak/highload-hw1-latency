#!/usr/bin/env python3

import sys
import time
import random
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

BASE_URL = "http://localhost:8080"

ENDPOINTS = [
    ("GET", "/api/health"),
    ("GET", "/api/users/{id}"),
    ("POST", "/api/orders"),
    ("GET", "/api/slow"),
]

PHASES = [
    {"name": "warm-up", "duration_s": 15, "rps": 5, "workers": 4},
    {"name": "steady-state", "duration_s": 30, "rps": 20, "workers": 10},
    {"name": "saturation", "duration_s": 45, "rps": 80, "workers": 40},
    {"name": "cool-down", "duration_s": 15, "rps": 5, "workers": 4},
]


def make_request(method, path):
    url = BASE_URL + path
    start = time.perf_counter()
    try:
        if method == "GET":
            resp = requests.get(url, timeout=10)
        else:
            resp = requests.post(url, json={"item": "test"}, timeout=10)
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
    if phase_name == "saturation":
        weights = [0.05, 0.20, 0.35, 0.40]
    else:
        weights = [0.20, 0.30, 0.30, 0.20]
    method, path = random.choices(ENDPOINTS, weights=weights, k=1)[0]
    if "{id}" in path:
        path = path.replace("{id}", str(random.randint(1, 100)))
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
    start_time = time.time()
    end_time = start_time + duration

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = []
        while time.time() < end_time:
            method, path = pick_endpoint(name)
            futures.append(executor.submit(make_request, method, path))
            time.sleep(interval)

        for future in as_completed(futures):
            results.append(future.result())

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
