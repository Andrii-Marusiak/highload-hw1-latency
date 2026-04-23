# Tests

Automated test suite for the workload characterization and bottleneck
analysis simulator.

## Running Tests

From the lab directory (`labs/1-2-workload-characterization-bottleneck-analysis/`):

```bash
pytest tests/ -v
```

## What Each Test File Covers

| File                   | Scope       | What it verifies |
|------------------------|-------------|------------------|
| `test_metrics.py`      | Unit        | MetricsCollector: per-type latencies, inter-arrival stats, utilisation, thread safety, reset |
| `test_worker_pool.py`  | Unit        | WorkerPool: read/write differentiation, jitter, arrival spacing, no dropped requests |
| `test_workload.py`     | Unit        | Arrival generators: CV for poisson/bursty/regular; request mix: counts, types, fractions |
| `test_runner.py`       | Smoke       | Runner loads config, produces output with correct fields, respects CLI overrides |
| `test_benchmark_e2e.py`| Integration | Full benchmark output, CLI entry point, CLI flags, bottleneck util positive |

## Test Configuration

Tests use small parameters (5ms service time, 2 workers, 20 requests)
via the `tmp_config` fixture in `conftest.py`. The full suite runs in
under 2 seconds.

## Adding Your Own Tests

After implementing your improvement, add tests to verify its behaviour.
Examples:

**Token-bucket rate limiter (Option A):**
```python
def test_token_bucket_rejects_bursts(tmp_config):
    """Under bursty load the rate limiter should reject excess requests."""
    results = run_benchmark(tmp_config, arrival_pattern="bursty")
    assert results[0]["rejected"] > 0
```

**Read replica routing / CQRS (Option B):**
```python
def test_cqrs_reduces_primary_util(tmp_config):
    """Routing reads to a replica should lower connection_pool util."""
    base = run_benchmark(tmp_config, read_fraction=0.95)
    # After your CQRS change, primary conn_pool_util should drop
    assert base[0]["conn_pool_util"] < 90
```

**Adaptive concurrency limit (Option C):**
```python
def test_adaptive_limit_bounds_queue(tmp_config):
    """During bursts, the adaptive limiter should keep p95 bounded."""
    results = run_benchmark(tmp_config, arrival_pattern="bursty")
    assert results[0]["p95_ms"] < 100  # your target ceiling
```

Place your test files in this `tests/` directory and run `pytest tests/ -v`.
