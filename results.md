# Lab 1-3: Capacity Estimation — Results

---

## Section 1 — Environment

| Field               | Value                                                                                    |
|---------------------|------------------------------------------------------------------------------------------|
| Hardware            | Apple M3 Pro, 12 cores, RAM 18 GB, NIC 10 Gbps                                          |
| Python version      | 3.14.4                                                                                   |
| OS                  | macOS Darwin 24.3.0                                                                      |

---

## Section 2 — Initial Capacity Estimate

| Dimension                             | Estimated value        |
|---------------------------------------|------------------------|
| Peak read QPS                         | 6,250                  |
| Peak write QPS                        | 695                    |
| Internal write QPS (× RF)             | 2,085                  |
| Ingress bandwidth                     | 2.85 MB/s              |
| Egress bandwidth                      | 25.60 MB/s             |
| Replication egress                    | 8.54 MB/s              |
| Storage at 12 months (physical + headroom) | 449 TB            |
| Working-set memory                    | 350 TB/node            |
| p99 latency                           | 1.2 ms (mean only, no tail model) |
| Cost per 1,000 QPS                    | $151.00                |

---

## Section 3 — Estimate vs. Measured Discrepancies

### Comparison Table

| Dimension                     | Estimated       | Measured (bench avg) | Ratio (M / E) | Missing multiplier                                                                 |
|-------------------------------|-----------------|----------------------|----------------|------------------------------------------------------------------------------------|
| Peak read QPS                 | 6,250           | 6,250                | 1.00           | —                                                                                  |
| Peak write QPS                | 695             | 694                  | 1.00           | —                                                                                  |
| Internal write QPS (× RF)    | 2,085           | 2,917 (derived¹)     | 1.40           | write amplification (1.4×) excluded from estimate                                  |
| Ingress bandwidth (MB/s)     | 2.85            | 27.13                | 9.52           | read-request payload excluded — benchmark counts (reads + writes) × payload        |
| Egress bandwidth (MB/s)      | 25.60           | 24.41                | 0.95           | within model accuracy                                                              |
| Replication egress (MB/s)    | 8.54            | 5.43                 | 0.64           | used × RF (3) instead of × (RF − 1) = 2; primary holds one copy locally           |
| Storage growth (GB/day)      | 320             | 104.14               | 0.33           | burst factor (4×) applied to daily volume instead of average QPS; write amp missed |
| Working-set memory (GB/node) | 350,000 (350 TB)| N/A                  | —              | on-disk storage confused with in-RAM working set; benchmark does not report memory |
| p99 latency (ms)             | 1.2 (mean only) | 8.52                 | 7.10           | no tail-latency model — only weighted-mean service time was computed               |

> ¹ Benchmark does not output internal write QPS directly. Derived as `write_peak × RF × write_amp = 694 × 3 × 1.4 = 2,917`.
> Benchmark reports "Effective storage QPS" = 2,220, which is a different concept: `read_miss_QPS + write_QPS × write_amp`.

### Ingress bandwidth — ratio 9.52×

The estimate only counted write payload (`695 × 4096 = 2.85 MB/s`). The benchmark counts all requests (reads + writes) at full payload size: `6,944 × 4096 = 27.13 MiB/s`. In a real system read requests are much smaller than responses (just a key/query), so the benchmark's definition is a worst-case model. Fix: add a read-request size parameter and include `read_QPS × read_request_bytes` in ingress.

### Storage growth — ratio 0.33× (estimate 3× too high)

Two compounding errors: first, the estimate multiplied peak write QPS (695) × 86,400 s for daily volume, but daily volume should use average write QPS (174), overestimating by the burst factor (4×); second, write amplification (1.4×) was omitted from the estimate. Net effect: `4.0 / 1.4 = 2.86×` overestimate, matching the observed ratio of `320 / 104.14 ≈ 3.07`. Fix: use `daily_writes = avg_write_QPS × 86,400`, then multiply by `(1 + index_overhead) × write_amplification`.

### p99 latency — ratio 7.1×

The estimate only computed weighted-mean service time: `0.80 × 0.5 ms + 0.20 × 4.0 ms = 1.2 ms`. It did not model tail latency at all. The benchmark's p99 (8.52 ms) reflects the fact that ~20% of requests hit the storage path (4 ms base), and at the 99th percentile nearly all sampled requests are storage-path hits. Typical p99/mean ratio for mixed cache+storage workloads is 5–10×. Fix: model p99 as `storage_service_time × (1 + queueing_factor)` or use Little's Law to estimate queue depth at peak. A simple heuristic — `p99 ≈ 2 × storage_service_time = 8 ms` — would have been within 6% of the measured value.

### Working-set memory — fundamentally wrong

The estimate computed `hot_data_per_node (150 TB) + cache (120 TB) + 30% overhead = 350 TB/node`, conflating total on-disk storage with in-RAM working set. No server has 350 TB of RAM. Working-set memory should be: `cache_size + per_connection_buffers + OS/runtime overhead`. The benchmark does not output a memory metric, so no measured value is available.

---

## Section 4 — Improvement Before / After

Option A raised `cache_hit_ratio` from 0.80 → 0.90, targeting a reduction in storage-tier read QPS and mean latency.

| Metric                       | Baseline | Improved | Delta                  |
|------------------------------|----------|----------|------------------------|
| Peak read QPS observed       | 6,250    | 6,250    | 0                      |
| Peak write QPS observed      | 694      | 694      | 0                      |
| Storage at 12 months (TB)    | 109.84   | 109.84   | 0                      |
| Total bandwidth (MB/s)       | 35.26    | 35.26    | 0                      |
| p99 latency (ms)             | 8.41     | 8.55     | +0.14 (within noise)   |
| Mean latency (ms)            | 1.98     | 1.62     | −0.36 (−18%)           |
| Effective storage QPS        | 2,220    | 1,600    | −620 (−28%)            |
| Cost per 1,000 QPS ($)       | 1,770.80 | 1,770.80 | 0                      |

p99 did not improve because the tail is dominated by the storage-path service time (4 ms), which is unchanged; Option A reduced the fraction of requests hitting that path (20% → 10%) but not the path's own latency. The primary wins are mean latency (−18%) and effective storage QPS (−28%), which increases headroom on the storage tier before it saturates.

---

## Section 5 — New Risk + Monitoring Metric

Raising the cache hit ratio to 0.90 creates a cache stampede risk: if the hot key set shifts suddenly (e.g. a viral event) or a cold-start occurs after a node restart, the hit ratio drops sharply and all cache-miss reads simultaneously flood the storage tier, potentially saturating it faster than auto-scaling can respond. The exact metric that would catch this early is `cache_hit_ratio` — a drop of more than 10 points from the configured value (i.e. below 0.80 when target is 0.90) should trigger an on-call alert before storage tier saturation occurs.

---

## Section 6 — Next Bottleneck Forecast

**Compute nodes** will saturate first as load doubles. At current load 3 nodes provide 15,000 QPS capacity at 14.81% peak utilisation. Doubling write QPS doubles the total workload to 13,888 peak QPS, pushing utilisation to **92.6%** — far above the 60% ceiling implied by the 40% headroom target (`utilisation_at_peak = 13,888 / 15,000 = 92.6%`). The model multiplier that shows this: `nodes_required = ⌈peak_QPS / (instance_qps_capacity × (1 − buffer))⌉ = ⌈13,888 / 3,000⌉ = 5 nodes` — two more nodes are needed before load doubles. The metric to monitor is `utilisation_at_peak` crossing 60%. The single next change is to scale the cluster from 3 to 5 nodes, or vertically increase `instance_qps_capacity` per node before utilisation breaches the buffer threshold.
