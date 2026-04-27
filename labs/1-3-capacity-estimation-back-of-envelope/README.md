# Lab 1-3: Capacity Estimation (Back of Envelope)

A back-of-envelope capacity simulator for studying how DAU, payload
size, replication, caching, fan-out, and retention combine into the
QPS / storage / bandwidth / cost numbers that drive infrastructure
decisions. The benchmark reports observed metrics across all six
homework grading dimensions; you compare them with the estimate you
committed in `capacity-estimate.md` and explain any discrepancies in
`results.md`.

## Prerequisites

- Python 3.12 or newer
- pip

## Setup

```bash
cd labs/1-3-capacity-estimation-back-of-envelope/
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Verify the environment:

```bash
python3 -c "import simulator; print('simulator OK')"
```

## Workflow

The homework explicitly requires you to **commit `capacity-estimate.md`
before running the benchmark**. This is the whole point of the lab:
build the model first, then test it against measurement, and document
which multipliers were missing from your initial estimate.

```bash
# 1. Read config.yaml and write capacity-estimate.md (six dimensions: QPS,
#    storage, bandwidth, working set / nodes, buffer, cost). Commit it.

# 2. Run the benchmark and capture the output:
bash scripts/run-benchmark.sh 2>&1 | tee results/baseline.txt

# 3. Build the discrepancy table in results.md (estimate vs measured
#    for every dimension), implement one improvement option (A-D),
#    re-run, and finish results.md.

# 4. Run the test suite:
pytest tests/ -v
```

You can pass a custom config file:

```bash
python3 -m simulator path/to/my-config.yaml
```

## Configuration (`config.yaml`)

### `workload` — what the system has to handle

| Key                    | Default     | Description                                              |
|------------------------|-------------|----------------------------------------------------------|
| `dau`                  | `1000000`   | Daily active users                                       |
| `sessions_per_user`    | `5`         | Sessions per DAU per day                                 |
| `requests_per_session` | `30`        | API requests per session (read + write combined)         |
| `payload_bytes`        | `4096`      | Average request/response payload size (bytes)            |
| `read_write_ratio`     | `9`         | Reads per write (9 = 90% reads / 10% writes)             |
| `burst_factor`         | `4.0`       | Peak QPS / average QPS                                   |
| `retention_months`     | `12`        | How long write data is retained                          |

### `infra` — how the system is built

| Key                            | Default | Description                                                |
|--------------------------------|---------|------------------------------------------------------------|
| `replication_factor`           | `3`     | Storage replicas (>=1)                                     |
| `cache_hit_ratio`              | `0.80`  | Assumed read-cache hit rate (0..1)                         |
| `index_overhead`               | `0.30`  | Extra storage from secondary indexes (0.30 = +30%)         |
| `fan_out_per_write`            | `2.0`   | Async change-events emitted per write                      |
| `write_amplification`          | `1.4`   | Journal / compaction multiplier on disk writes             |
| `instance_qps_capacity`        | `5000`  | Sustainable QPS per node (read-equivalent)                 |
| `per_request_service_time_ms`  | `4.0`   | Storage-path service time                                  |
| `cache_hit_service_time_ms`    | `0.5`   | Cache-hit-path service time                                |
| `hot_data_fraction`            | `1.0`   | Fraction of dataset on hot tier (1.0 = no tiering)         |

### `capacity` — sizing & cost knobs

| Key                            | Default | Description                                                |
|--------------------------------|---------|------------------------------------------------------------|
| `target_buffer_pct`            | `40`    | Provision so peak uses (100 - buffer)% of capacity         |
| `cost_per_node_per_month_usd`  | `350`   | Compute price per node per month                           |
| `cold_tier_cost_multiplier`    | `0.10`  | Cold-tier $/GB relative to hot-tier                        |
| `replication_lag_budget_s`     | `5.0`   | Acceptable lag at peak (informational)                     |

### `benchmark` — sampling controls

| Key                | Default | Description                                                            |
|--------------------|---------|------------------------------------------------------------------------|
| `sample_requests`  | `5000`  | Number of requests in the short real-time benchmark                    |
| `sample_workers`   | `8`     | Concurrency of the sampling thread pool                                |
| `rng_seed`         | `42`    | Seed for cache hit/miss decisions and request-kind selection           |

## Expected Output

Running the default config produces a 7-section ASCII report covering
every homework grading dimension. An abbreviated example:

```
========================================================================
LAB 1-3 BENCHMARK: Capacity Estimation (Back of Envelope)
========================================================================

INPUTS
------------------------------------------------------------------------
  DAU: 1,000,000   sessions/user: 5.0   req/session: 30.0
  payload: 4096 B   R:W = 9.0:1   burst x4.0   retention: 12 mo
  RF: 3   cache hit (cfg): 0.80   index overhead: 30%   write amp: 1.4
  ...

THROUGHPUT
------------------------------------------------------------------------
  Daily requests:              150,000,000
  Avg total QPS:               1.74 k req/s
  Peak total QPS:              6.94 k req/s
  Peak read QPS:               6.25 k req/s
  Peak write QPS:              694.44 req/s
  Effective storage QPS:       2.22 k req/s    (after cache + write amp)

LATENCY (5,000-sample benchmark, 1.55 s wall)
------------------------------------------------------------------------
  p50:                              0.73 ms
  p95:                              7.58 ms
  p99:                              9.30 ms
  ...

STORAGE (with replication, indexes, write amplification)
------------------------------------------------------------------------
  Daily writes:                 14,999,999
  Daily replicated growth:    312.42 GB
  Storage at 12 mo:             109.84 TB
  ...

BANDWIDTH (peak)
------------------------------------------------------------------------
  Ingress (writes + reads in):     27.13 MB/s
  Egress (reads out):              24.41 MB/s
  Replication egress:               5.43 MB/s
  Fan-out egress:                   5.43 MB/s
  ...

CAPACITY
------------------------------------------------------------------------
  Nodes required:                  3
  Headroom at peak:                85.19 %    (target: >= 40%)
  Replication lag (est):            0.00 s    (budget: 5.0 s)
  ...

COST
------------------------------------------------------------------------
  Monthly compute:           $    1,050.00
  Monthly hot storage:       $   11,247.25
  Monthly TOTAL:             $   12,297.25
  Cost per 1k QPS:           $  1,770.8045
========================================================================
```

A full sample is committed at [results/baseline.txt](results/baseline.txt).

## Improvement Options

Pick one and apply it as a focused commit. All four are reachable
through `config.yaml` edits — no simulator code changes required —
but you are welcome to extend the simulator if your option requires it.

### Option A — Add a caching tier

Raise `infra.cache_hit_ratio` (e.g. `0.80` -> `0.95`). What should move:

- `effective_storage_read_qps` falls (less load reaches the storage tier)
- `mean_ms` and the latency distribution shift toward the cache fast-path
- `cost_per_1k_qps_usd` drops because the read tier needs fewer nodes

What to discuss in `results.md`: cache invalidation cost, cold-start
risk, the assumption that the working set fits in memory.

### Option B — Reduce the replication factor

Lower `infra.replication_factor` (e.g. `3` -> `2`). What should move:

- `storage_at_retention_bytes` drops by ~33%
- `replication_egress_bytes_per_second` halves
- Hot-storage cost line in `monthly_total_usd` drops by ~33%

What to discuss in `results.md`: durability trade-off, blast radius if
a node dies during a rebalance, read-fan-out / quorum implications.

### Option C — Vertical scale

Lower `infra.per_request_service_time_ms` (e.g. `4.0` -> `2.0`) and
raise `infra.instance_qps_capacity` (e.g. `5000` -> `9000`) to model
moving to a larger instance class. What should move:

- `mean_ms` drops (faster service path)
- `nodes_required` drops, `headroom_pct_at_peak` rises
- `cost_per_node_per_month_usd` should also rise (raise it to reflect the
  larger instance) — `cost_per_1k_qps_usd` may net-fall thanks to density

What to discuss in `results.md`: vertical-scaling cliff, blast radius
of losing one large node, NUMA / memory-bandwidth assumptions.

### Option D — Tiered storage

Set `infra.hot_data_fraction` to `0.2` (only 20% of data on hot tier).
What should move:

- `hot_storage_at_retention_bytes` shrinks; `cold_storage_at_retention_bytes` appears
- Total storage cost drops because cold storage is `cold_tier_cost_multiplier`x cheaper
- `monthly_total_usd` and `cost_per_1k_qps_usd` drop

What to discuss in `results.md`: cold-read latency penalty, how you'd
choose the partition key, lifecycle policy.

## Project Structure

```
simulator/
  __init__.py       Public API
  __main__.py       python -m simulator entry point
  config.py         Typed Config dataclass + YAML loader + validation
  workload.py       avg/peak QPS, R/W split, post-cache storage QPS
  storage.py        RF, index, write amp, retention, hot/cold split
  network.py        Ingress, egress, replication, fan-out bandwidth
  capacity.py       Nodes, headroom, replication-lag estimate
  cost.py           Monthly compute + storage cost; cost per 1k QPS
  cache.py          Seeded Bernoulli cache (drives the latency mix)
  metrics.py        Latency collector (p50/p95/p99, observed hit rate)
  service.py        Short real-time benchmark (ThreadPoolExecutor + sleep)
  runner.py         Orchestrator: load config, derive every profile, print report
scripts/
  run-benchmark.sh  Shell wrapper (activates venv, calls python -m simulator)
tests/              Automated tests (see tests/README.md)
results/            Save your benchmark output here (baseline.txt, etc.)
config.yaml         Tunable benchmark parameters
```

## What to Do Next

See the homework task description for the full assignment: build the
back-of-envelope estimate first, commit it as `capacity-estimate.md`,
benchmark, build the discrepancy table, implement one improvement
option, re-benchmark, and write `results.md`.
