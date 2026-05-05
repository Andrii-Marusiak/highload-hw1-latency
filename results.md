# Environment

* Python 3.14.4
* masOs Darwin Kernel Version 24.3.0
* CPU count: 12 (Apple M3 Pro)

---

# Estimate vs. Measured — Find the Missing Multiplier

## Comparison Table

| Dimension                     | Estimated       | Measured (bench avg) | Ratio (M / E) | Missing multiplier                                                                 |
|-------------------------------|-----------------|----------------------|----------------|------------------------------------------------------------------------------------|
| Peak read QPS                 | 6,250           | 6,250                | 1.00           | —                                                                                  |
| Peak write QPS                | 695             | 694                  | 1.00           | —                                                                                  |
| Internal write QPS (× RF)    | 2,085           | 2,917 (derived¹)     | 1.40           | write amplification (1.4×) excluded from estimate                                  |
| Ingress bandwidth (MB/s)     | 2.85            | 27.13                | 9.52           | read-request payload excluded — benchmark counts (reads + writes) × payload        |
| Egress bandwidth (MB/s)      | 25.60           | 24.41                | 0.95           | —                                                                                  |
| Replication egress (MB/s)    | 8.54            | 5.43                 | 0.64           | used × RF (3) instead of × (RF − 1) = 2; primary holds one copy locally           |
| Storage growth (GB/day)      | 320             | 104.14               | 0.33           | burst factor (4×) applied to daily volume instead of average QPS; write amp missed |
| Working-set memory (GB/node) | 350,000 (350 TB)| N/A                  | —              | on-disk storage confused with in-RAM working set; benchmark does not report memory |
| p99 latency (ms)             | 1.2 (mean only) | 8.52                 | 7.10           | no tail-latency model — only weighted-mean service time was computed               |

> ¹ Benchmark does not output internal write QPS directly. Derived as `write_peak × RF × write_amp = 694 × 3 × 1.4 = 2,917`.
> Benchmark reports "Effective storage QPS" = 2,220, which is a different concept: `read_miss_QPS + write_QPS × write_amp`.

## Rows Outside 0.5 – 2.0×

### 1. Ingress bandwidth — ratio 9.52×

The estimate only counted write payload (`695 × 4096 = 2.85 MB/s`).
The benchmark counts **all** requests (reads + writes) at full payload size: `6,944 × 4096 = 27.13 MiB/s`.
In a real system read requests are much smaller than responses (just a key/query), so the benchmark's definition is a worst-case model.
**Fix:** add a read-request size parameter and include `read_QPS × read_request_bytes` in ingress.

### 2. Storage growth — ratio 0.33× (estimate 3× too high)

Two compounding errors:

- **Peak vs. average:** the estimate multiplied **peak** write QPS (695) × 86,400 s for daily volume. Daily volume should use **average** write QPS (174). This overestimated by the burst factor (4×).
- **Write amplification omitted:** the estimate included index overhead (+30%) but not write amplification (1.4×), underestimating by 1.4×.

Net effect: `4.0 / 1.4 = 2.86×` overestimate, matching the observed ratio of `320 / 104.14 ≈ 3.07`.

**Fix:** use `daily_writes = avg_write_QPS × 86,400`, then multiply by `(1 + index_overhead) × write_amplification`.

### 3. p99 latency — ratio 7.1×

The estimate only computed weighted-mean service time:
`0.80 × 0.5 ms + 0.20 × 4.0 ms = 1.2 ms`.

It did not model tail latency at all. The benchmark's p99 (8.52 ms) reflects the fact that ~20% of requests hit the storage path (4 ms base), and at the 99th percentile nearly all sampled requests are storage-path hits.
Typical p99/mean ratio for mixed cache+storage workloads is 5–10×.

**Fix:** model p99 as `storage_service_time × (1 + queueing_factor)` or use Little's Law to estimate queue depth at peak. A simple heuristic: `p99 ≈ 2 × storage_service_time = 8 ms` would have been within 6% of the measured value.

### 4. Working-set memory — fundamentally wrong

The estimate computed:
`hot_data_per_node (150 TB) + cache (120 TB) + 30% overhead = 350 TB/node`

This conflated **total on-disk storage** with **in-RAM working set**. No server has 350 TB of RAM.
Working-set memory should be: `cache_size + per_connection_buffers + OS/runtime overhead`.
A reasonable estimate: `cache_size = hit_ratio × daily_hot_reads × avg_object_size × TTL` or size it to hold the hot fraction of keys that produce 80% cache hit rate.

The benchmark does not output a memory metric, so no measured value is available.

## Rows Marginally Inside (but noteworthy)

### Replication egress — ratio 0.64×

The estimate used `× RF (3)` for replication traffic. The primary node already holds one copy; it only replicates to `RF − 1 = 2` peers. This overcounts by 1.5×.

### Internal write QPS — ratio 1.40×

The estimate computed `write_peak × RF` but excluded write amplification (1.4×). Each replica performs journal/compaction writes locally, so the true internal write IOPS is `write_peak × RF × write_amp`.

## Summary

| Status | Count | Rows |
|--------|-------|------|
| ✅ Within 0.5 – 2.0× | 5 | Peak read QPS, Peak write QPS, Internal write QPS, Egress bandwidth, Replication egress |
| ❌ Outside 0.5 – 2.0× | 3 | Ingress bandwidth, Storage growth, p99 latency |
| ⚠️ Not comparable       | 1 | Working-set memory (no benchmark metric) |

**The model is not yet useful** — 3 of 8 comparable dimensions fall outside the ±2× threshold.
The two highest-impact fixes:

1. **Storage growth:** use average QPS (not peak) for daily volume and include write amplification.
   This single fix would bring the ratio from 0.33 to ~1.0.
2. **p99 latency:** add a tail-latency multiplier (≈ 2× storage service time as a starting heuristic).
   This would bring the ratio from 7.1 to ~1.0.

After these two corrections, re-run the benchmark to verify the model predicts within 30%.
The next input to tighten after that would be **ingress bandwidth** — adding a separate `read_request_bytes` parameter to distinguish read request size from response payload size.

---

# Step 5: Improvement — Option A (Add a Caching Tier)
Root cause of the largest measured gap (p99 latency 7.1×) is the 20 % of reads that miss cache and hit the 4 ms storage path. Raising `cache_hit_ratio` from 0.80 → 0.90 halves the storage-tier read QPS and reduces the queue depth that drives tail latency — without any hardware change and in hours rather than weeks.

**New alert:** monitor `cache_hit_ratio` in real time; a drop of > 10 points from 90 % signals an eviction wave or cold-start event and should page on-call before storage tier saturation occurs.
