# Tests

Automated test suite for the capacity-estimation simulator.

## Running Tests

From the lab directory (`labs/1-3-capacity-estimation-back-of-envelope/`):

```bash
pytest tests/ -v
```

## What Each Test File Covers

| File                    | Scope       | What it verifies                                                                 |
|-------------------------|-------------|----------------------------------------------------------------------------------|
| `test_config.py`        | Unit        | Loader returns typed `Config`; rejects RF<1, cache>1, burst<1                    |
| `test_workload.py`      | Unit        | Avg vs peak QPS; R/W split; cache lowers effective storage read QPS              |
| `test_storage.py`       | Unit        | RF, index overhead, retention, hot/cold split, write amplification               |
| `test_network.py`       | Unit        | Ingress / egress / replication / fan-out math; total egress equals the sum       |
| `test_capacity.py`      | Unit        | Nodes >= RF; buffer lowers effective node QPS; headroom + utilisation = 100%    |
| `test_cost.py`          | Unit        | Caching / RF reduction / tiering each move `cost_per_1k_qps_usd` the right way   |
| `test_metrics.py`       | Unit        | p50/p95/p99 percentile correctness; observed hit rate; thread-safety             |
| `test_runner.py`        | Smoke       | All 30+ metric keys present; runs fast (<5 s); observed hit rate near config     |
| `test_benchmark_e2e.py` | Integration | Every grading-dimension headline appears in stdout; cache improvement lowers p99 |

## Test Configuration

Tests use a small fixture (DAU=100k, 200 sample requests, 4 workers) via
the `tmp_config` and `tmp_config_path` fixtures in `conftest.py`. The
full suite runs in well under 5 seconds.

## Adding Your Own Tests

After implementing your improvement option, add a test to verify it
moves the right metric. Examples:

**Option B (RF reduction):**

```python
def test_rf_reduction_shrinks_storage_at_12mo(tmp_config):
    rf3 = tmp_config
    rf2 = replace(tmp_config, infra=replace(tmp_config.infra, replication_factor=2))
    s3 = derive_storage(rf3, derive_workload(rf3))
    s2 = derive_storage(rf2, derive_workload(rf2))
    assert s2.storage_at_retention_bytes < s3.storage_at_retention_bytes
```

**Option C (vertical scale):**

```python
def test_vertical_scale_drops_p99(tmp_config_path):
    # Save tmp_config_path with lower service_time_ms / higher capacity, then re-run.
    ...
```

Place new test files in this `tests/` directory and run `pytest tests/ -v`.
