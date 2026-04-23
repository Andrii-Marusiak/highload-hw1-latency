# Lab 1-2: Workload Characterization and Bottleneck Analysis

A Python-based benchmark simulator for studying workload arrival
patterns, read/write ratio bottlenecks, and resource utilisation
in a worker-pool architecture.

## Prerequisites

- Python 3.12 or newer
- pip

## Setup

```bash
cd labs/1-2-workload-characterization-bottleneck-analysis/
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Verify the environment:

```bash
python3 -c "import simulator; print('simulator OK')"
```

## Running the Benchmark

Default run (uses `config.yaml`):

```bash
bash scripts/run-benchmark.sh 2>&1 | tee results/baseline.txt
```

Or directly:

```bash
python3 -m simulator
```

### CLI Overrides

Override arrival pattern:

```bash
python3 -m simulator --arrival-pattern poisson
python3 -m simulator --arrival-pattern bursty
```

Override read/write ratio:

```bash
python3 -m simulator --read-fraction 0.5
python3 -m simulator --read-fraction 0.8
python3 -m simulator --read-fraction 0.95
```

Override target utilisation:

```bash
python3 -m simulator --target-utilization 0.65
```

Pass a custom config file:

```bash
python3 -m simulator path/to/my-config.yaml
```

## Running Tests

```bash
pytest tests/ -v
```

See [tests/README.md](tests/README.md) for details on what each test
verifies and how to add your own.

## Configuration

Edit `config.yaml` to change benchmark parameters:

| Key                    | Default  | Description                                          |
|------------------------|----------|------------------------------------------------------|
| `service_time_ms`      | 10       | Base service time for read requests (ms)             |
| `write_service_time_ms`| 15       | Base service time for write requests (ms) — WAL/fsync|
| `workers`              | 4        | Connection pool size (thread pool)                   |
| `io_workers`           | 2        | I/O subsystem parallelism (simulated WAL writers)    |
| `total_requests`       | 500      | Total requests per benchmark run                     |
| `arrival_pattern`      | poisson  | Arrival distribution: `poisson`, `bursty`, `regular` |
| `burst_cv`             | 2.0      | Target CV for bursty arrivals                        |
| `read_fraction`        | 0.7      | Fraction of requests that are reads (0.0–1.0)        |
| `target_utilization`   | 0.75     | Arrival rate targets this util on the bottleneck     |
| `replica_lag_ms`       | 5        | Simulated replica lag (for CQRS improvement option)  |

## Benchmark Output

The simulator prints:

1. **Config summary** — all active parameters.
2. **Arrival statistics** — `inter_arrival_mean_ms`, `inter_arrival_std_ms`, `CV`.
3. **Results table** — requests, reads, writes, rejected, mean/p95 latency, throughput, duration.
4. **Resource utilisation** — connection pool %, I/O subsystem %, bottleneck name.
5. **Per-type latency** — read mean/p95, write mean/p95.

## Project Structure

```
simulator/
  __init__.py       Public API (import simulator)
  __main__.py       python -m simulator entry point (argparse CLI)
  metrics.py        Thread-safe collector with per-type and inter-arrival stats
  worker_pool.py    ThreadPoolExecutor wrapper with read/write differentiation
  workload.py       Arrival pattern generators + request type assignment (the code you improve)
  runner.py         Orchestrator: loads config, runs benchmark, computes utilisation, prints report
scripts/
  run-benchmark.sh  Shell wrapper (activates venv, calls python -m simulator)
tests/              Automated tests (see tests/README.md)
results/            Save your benchmark output here (baseline.txt, improved.txt, etc.)
config.yaml         Tunable benchmark parameters
```

## What to Do Next

See the homework task description for the full assignment: run the
baseline, analyse workload shape (Poisson vs. bursty), sweep
read/write ratios to find the bottleneck, choose one improvement
(token-bucket limiter, CQRS replica routing, adaptive concurrency
limit, or config tuning), implement it, re-benchmark, and write
`results.md`.
