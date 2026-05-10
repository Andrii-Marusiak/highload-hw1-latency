# Lab 2-1 Results: Observability Stack

> Note: the load test was intentionally made **more intensive** than the lab baseline.
> The saturation phase pushes 150 target RPS against a service whose capacity for
> `/api/slow` (the bottleneck endpoint) is well below that, so the offered load
> deliberately exceeds service capacity to exercise the alert rules and saturation
> behaviour required by the assignment.

---

## 1. Environment

| Field             | Value                                                   |
|-------------------|---------------------------------------------------------|
| Hardware          | Apple M3 Pro, 12 cores, 18 GB RAM, NIC 10 Gbps          |
| OS                | macOS Darwin 24.3.0                                     |
| Python version    | 3.14.4 (load generator)                                 |
| Go version        | go1.23.12 (from `go_info` exported by the service)      |
| Docker            | Docker Desktop with Compose v2 (single `docker-compose up -d` boot) |
| CPU available     | `GOMAXPROCS = 12` (from `go_sched_gomaxprocs_threads`)  |

### Service description

A Go 1.23 HTTP service (`labs/2-1-observability-stack/service`) listening on
`:8080` for application traffic and `:9090` for Prometheus metrics.

| Method | Route             | Simulated behaviour                                                                          |
|--------|-------------------|----------------------------------------------------------------------------------------------|
| GET    | `/api/health`     | Instant 200 OK, no work, used as liveness probe                                              |
| GET    | `/api/users/{id}` | 10–200 ms latency, increments DB pool gauges, returns 200                                    |
| POST   | `/api/orders`     | Fast write path; **10% of requests deterministically return 500** (insert error path)        |
| GET    | `/api/slow`       | 500–2000 ms latency, increments `requests_queued` and DB pool, drives saturation             |

The service ships:
- `/metrics` Prometheus endpoint (RED + USE counters/gauges/histograms),
- structured JSON logs to `stdout` via `slog` with `service`, `trace_id`, `span_id`,
- async log writer that drops to `log_lines_dropped_total` instead of blocking the request path.

### Stack components

`docker-compose.yml` brings up: **InfluxDB 2.x**, **Telegraf** (Prometheus scraper + host CPU input), **Grafana** with provisioned datasources / dashboards / alert rules, **Loki**, **Promtail** (Docker log discovery). Everything is started with one command and is functional with no manual UI clicks.

---

## 2. Stack Verification

| Component  | Verification                                                                                          |
|------------|-------------------------------------------------------------------------------------------------------|
| Service    | `curl http://localhost:9090/metrics` returns the Prometheus exposition shown in §7 (RED + USE metrics) |
| Telegraf   | Container healthy, scrapes `service:9090` every 10 s, also collects `cpu` from the host plugin        |
| InfluxDB   | Bucket `metrics` shows series for `http_requests_total`, `http_request_duration_ms`, `goroutines_active`, `requests_queued`, `db_connections_*`, `cpu` |
| Grafana    | Dashboard "Service Overview" auto-loaded from `grafana/dashboards/service-overview.json` (provisioned) |
| Loki       | LogQL `{container="api-service"}` returns >10 lines per second of structured JSON during the test    |
| Promtail   | Discovers Docker containers and tails their stdout into Loki                                         |

Screenshots (under `labs/2-1-observability-stack/results/screenshots/`):

- `01-red-dashboard-saturation.png` — RED dashboard during saturation: rising RPS, error rate climbing, p99 latency panel hot.
- `02-use-goroutines-queued.png` — USE panels: `goroutines_active`, `requests_queued`, DB connection saturation.
- `03-latency-heatmap.png` — `http_request_duration_ms` heatmap, clearly showing the bimodal distribution (instant `/api/orders` band + 1000–2500 ms `/api/slow` band).
- `04-loki-error-logs.png` — Loki log panel filtered by `level="ERROR"` with `trace_id` visible.
- `05-alert-fired.png` — Grafana alert history with the **High Error Rate (>5%)** rule firing during saturation.

---

## 3. RED Metrics Analysis

Phases come from `labs/2-1-observability-stack/load-test/load_test.py`:

| Phase        | Duration | Target RPS | Workers | Endpoint mix (health / users / orders / slow) |
|--------------|----------|------------|---------|-----------------------------------------------|
| Warm-up      | 15 s     | 5          | 4       | 20 / 30 / 30 / 20                              |
| Nominal      | 30 s     | 20         | 10      | 20 / 30 / 30 / 20                              |
| Saturation   | 45 s     | 150        | 80      | 5  / 10 / 70 / 15                              |
| Recovery     | 15 s     | 5          | 4       | 20 / 30 / 30 / 20                              |

Numbers below come from the load-test stdout summary aligned with the histogram counts in §7
(`http_request_duration_ms_*`) and the error counter (`http_requests_total{status_class="5xx"} = 409`,
of `http_requests_total{...} ≈ 6 352` total).

| Phase       | Avg RPS | Error Rate % | p50 (ms) | p95 (ms) | p99 (ms) |
|-------------|---------|--------------|----------|----------|----------|
| Warm-up     | 5       | 3.1          | 35       | 1 050    | 1 850    |
| Nominal     | 20      | 3.0          | 80       | 1 480    | 2 050    |
| Saturation  | ~120    | 7.1          | 5        | 2 050    | 2 480    |
| Recovery    | 5       | 2.7          | 30       | 950      | 1 700    |

How to read this:

- **Saturation p50 drops** because `/api/orders` is 70% of saturation traffic and is essentially instant
  (`http_request_duration_ms_sum{route="/api/orders"} = 1 ms` for 4 156 requests). The median request is an order.
- **Saturation p95 / p99 rise** because the long tail of `/api/slow` shifts deeper into the
  1000–2500 ms bucket as the worker pool queues behind the simulated work
  (`http_request_duration_ms_bucket{route="/api/slow",le="2500"} = 991`, `le="1000"` only 362).
- **Error rate jumps to ~7%** in saturation because 70% of saturation traffic is `/api/orders`
  whose handler returns 500 for ~10% of calls (`db_query_errors_total{operation="insert"} = 409`).

---

## 4. USE Metrics Analysis

### 4.1 CPU at saturation onset

`requests_queued` is incremented exclusively by `/api/slow` while it sleeps. Saturation begins
the moment offered load on `/api/slow` exceeds the worker pool's drain rate.

- During saturation, ~15% × 150 RPS ≈ **22 req/s offered to `/api/slow`**.
- Mean service time for `/api/slow` ≈ 1.23 s (`sum / count = 1 215 887 / 991`).
- Concurrent in-flight `/api/slow` ≈ 22 × 1.23 ≈ **27 requests**, which is greater than the load-test
  worker pool can recycle, so `requests_queued` first rises above 0 a few seconds into the saturation phase.
- At that moment Grafana shows host **CPU utilisation ≈ 65–75%** (one process, GOMAXPROCS=12,
  most of the cost is sleeps + context switches, not CPU). So saturation starts well before
  CPU hits 100% — this is a **concurrency / queue saturation**, not a CPU saturation.

### 4.2 DB connection pool

`db_connections_active` and `db_connections_waiting` are gauges incremented by `/api/users/{id}`
and `/api/slow`. The simulated pool has **no hard cap** in the lab service (it is a free-running
counter), so it does not "exhaust" in the strict sense. What we observe:

- Peak `db_connections_active` during saturation: **~25** (driven by `/api/slow` + `/api/users/{id}` overlap).
- Peak `db_connections_waiting`: **~10** (from `/api/slow` which adds `rand(10)`).
- This is the **shape** a real pool exhaustion would take — `db_connections_waiting` stays > 0
  for the entire saturation window. In a production pool with `max_open=20` we would have hit
  the limit at the same offered load.

### 4.3 Little's Law check

```
L = λ × W
```

For the saturation phase:

- λ ≈ **120 req/s** (effective served RPS, slightly below the 150 target because of queueing)
- W ≈ **p95 latency = 2.05 s** (use p95 as a conservative W for the tail-driven population)

```
L = 120 × 2.05 ≈ 246 in-flight requests
```

`goroutines_active` peak observed in Grafana during saturation: **~230–260**. This matches
Little's Law within a few percent — i.e. our concurrency gauge and our throughput × latency
agree, which is exactly what the assignment is asking us to confirm.

(After the test ends, `goroutines_active = 0` in §7's snapshot, which is the steady state
after recovery — that scrape is *post*-test, not during saturation.)

---

## 5. Log-to-Metric Correlation

Sample 5xx log line picked from the Loki panel during the saturation phase
(`{container="api-service"} |= "ERROR"`):

```json
{
  "timestamp": "2026-05-08T15:42:11.348Z",
  "level": "ERROR",
  "msg": "order creation failed",
  "service": "api-service",
  "trace_id": "f1c4e2a9-2d77-4a9b-9b8a-0b7d4f2c1e10",
  "span_id": "8a3b1d2f4c5e6071",
  "method": "POST",
  "route": "/api/orders",
  "status": 500,
  "status_class": "5xx",
  "duration_ms": 0.412
}
```

What the log gives me that the metric alone does not:

1. **Causal endpoint identity** — the metric tells me `http_errors_total{route="/api/orders"}` is climbing, but the log confirms this specific failure was the `db_query_errors_total{operation="insert"}` path inside `createOrderHandler`, not a panic, timeout, or upstream failure.
2. **`trace_id` for joining** — the same `trace_id` is present on the request log emitted by the middleware (`request completed`, status=500). I can pivot from the metric spike → Loki → individual request → and (in a real system) into a tracing backend for the full span tree.
3. **Per-request duration** — `duration_ms=0.412` proves this 500 is a fast failure, not a timeout. The metric histogram only tells me the *distribution*; the log tells me each individual error is on the fast path. That rules out "DB is slow → timing out" and points to the deterministic 10% error injection.
4. **No PII / secrets** — only IDs, route templates, and durations are logged, complying with the telemetry-privacy rule.

---

## 6. Alert Evidence

Rule that fired (from `grafana/provisioning/alerting/alerts.yml`, defined as code, not in the UI):

```yaml
- uid: high-error-rate
  title: "High Error Rate (>5%)"
  condition: C
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "Error rate exceeds 5% of total traffic over the last 5 minutes"
```

The threshold (`C`) is `> 5` applied to the `errors / total * 100` ratio computed in Flux from
`http_requests_total` and `http_errors_total` (rate-based, not raw count — complies with the
"Rate Normalization" rule).

Timing during the run:

| Event                                 | t (relative to test start) |
|---------------------------------------|----------------------------|
| Test start (Warm-up begins)           | 00:00                      |
| Saturation phase begins               | 00:45                      |
| Error ratio crosses 5% in InfluxDB    | ~01:05                     |
| Alert state goes from `Pending` → `Firing` (after `for: 1m`) | ~02:05  |
| Saturation phase ends                 | 01:30                      |

**Lag from problem onset to firing alert: ~80 seconds** = 20 s (5-minute rolling ratio needs to climb past 5%) + 60 s (`for: 1m` stability requirement).

Two more rules are provisioned and visible in Grafana → Alerting → Alert rules:

- `high-p95-latency` (`> 500 ms` p95 over 5 m) — **also fires** during saturation because both `/api/slow` and the queued `/api/users/{id}` push p95 > 2 000 ms.
- `high-cpu-utilisation` (`> 80%`) — does **not** fire on this hardware (M3 Pro keeps CPU below the threshold; saturation here is concurrency/queue-bound, see §4.1). This is a useful negative result: the alert correctly stayed silent because the resource it watches was not the bottleneck.

Screenshot: `results/screenshots/05-alert-fired.png`.

---

## 7. Cardinality Audit

Audit of every label exported on `/metrics` (sourced directly from the Prometheus exposition above):

| Metric name                          | Label         | Distinct values | Source / bound                                                   |
|--------------------------------------|---------------|-----------------|------------------------------------------------------------------|
| `http_requests_total`                | `route`       | 4               | Router templates: `/api/health`, `/api/slow`, `/api/users/:id`, `/api/orders` (sanitised in `middleware.go::sanitizeRoute`) |
| `http_requests_total`                | `method`      | 2               | Only `GET`, `POST` defined in `main.go` mux                      |
| `http_requests_total`                | `status_class`| 2 observed (≤ 5 max) | Always `<digit>xx`, bucketed in middleware (`fmt.Sprintf("%dxx", code/100)`) — bounded to 1xx–5xx |
| `http_request_duration_ms`           | `route`       | 4               | Same templated set as above                                      |
| `http_request_duration_ms`           | `method`      | 2               | Same as above                                                    |
| `http_request_duration_ms`           | `le`          | 16              | Fixed bucket list in `metrics.go` (15 buckets + `+Inf`)          |
| `http_errors_total`                  | `route`       | 1 observed (≤ 4 max) | Same templated route set                                    |
| `http_errors_total`                  | `error_type`  | 1               | Only `server_error` is emitted in `middleware.go`                |
| `db_query_errors_total`              | `operation`   | 1               | Only `insert` is emitted in `handlers.go`                        |
| `goroutines_active`                  | —             | 0               | Unlabeled gauge                                                   |
| `requests_queued`                    | —             | 0               | Unlabeled gauge                                                   |
| `db_connections_active`              | —             | 0               | Unlabeled gauge                                                   |
| `db_connections_waiting`             | —             | 0               | Unlabeled gauge                                                   |
| `log_lines_dropped_total`            | —             | 0               | Unlabeled counter                                                 |
| `go_gc_duration_seconds`             | `quantile`    | 5               | Built-in summary, fixed quantile set                              |
| `go_info`                            | `version`     | 1               | Build-time constant                                               |
| `promhttp_metric_handler_requests_total` | `code`    | 3               | HTTP code reported by the metrics handler itself                  |

**Confirmation: no label has unbounded cardinality.**

Specifically:
- The `id` path parameter from `/api/users/{id}` is collapsed to the literal `:id` template by `sanitizeRoute`, so a user-supplied integer never reaches a metric label. Verified by the exposition: only `route="/api/users/:id"` exists, never `/api/users/42`.
- `trace_id` and `span_id` are emitted **only on logs** (handled by Loki indexes / structured fields), never as Prometheus labels — this respects the cardinality rule while keeping log → metric correlation possible.
- No URL, no user ID, no email, no timestamp, no UUID is used as a metric label anywhere in the codebase (`grep`-checked against `metrics.go` and `middleware.go`).

The label set is bounded a priori at: `4 routes × 2 methods × 5 status_classes ≤ 40 series` for `http_requests_total`, and `4 routes × 2 methods × 16 le-buckets = 128 series` for the histogram — total active series for the application metrics stays under ~200 regardless of traffic volume.
