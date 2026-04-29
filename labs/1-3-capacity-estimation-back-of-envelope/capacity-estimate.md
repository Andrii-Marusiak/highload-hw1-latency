## QPS Chain

DAU → sessions/day → requests/day → average QPS → × burst factor → **peak QPS**

- Split into:
  - **Read peak QPS**
  - **Write peak QPS**
- Internal write load:
  - `write peak QPS × replication factor = internal write QPS`


- Total requests per day: 150_000_000
dau: 1_000_000 * sessions_per_user: 5 * requests_per_session: 30 = 150_000_000

- Average QPS: 1736
Total requests per day: 150_000_000 / seconds in a day: 86_400 = 1736

- Read peak QPS: 6250
Average QPS: 1736 * read_write_ratio: 9 (0.9) * burst_factor: 4.0 = 6250 

- Write peak QPS: 695
Average QPS: 1736 * read_write_ratio: 9 (0.1) * burst_factor: 4.0 = 695

- Total peak QPS: 6_945

- Internal write load: 2085
Write peak QPS: 695 * replication factor = 2085

---

## Storage Projection

- Raw data per day:
  - `write QPS × payload bytes × 86,400 s = raw bytes/day`
- Add overhead:
  - `+30%` for index/metadata
- Project:
  - 12 months
  - 24 months
- Physical storage:
  - `× replication factor`
- Add headroom:
  - `+30%` for compaction, hotspots, reindexing

- Raw data/day =
695 * 4096 * 86_400 =
245_975_040_000 bytes
≈ 246 GB/day

- Raw data per day with index overhead: 319_767_552_000 bytes (~320 GB/day)
Raw data per day: 245_975_040_000 * overhead: 1.30 = 319_767_552_000 bytes/day

**used AI to calculate bytes**
- 12 months logical =
319_767_552_000 * 30 * 12 =
115_116_318_720_000 bytes
≈ 115.1 TB

- 24 months logical =
319_767_552_000 * 30 * 24 =
230_232_637_440_000 bytes
≈ 230.2 TB

- 12 months physical =
115_116_318_720_000 * replication_factor: 3 =
345_348_956_160_000 bytes
≈ 345.3 TB

- 24 months physical =
230_232_637_440_000 * replication_factor: 3 =
690_697_912_320_000 bytes
≈ 690.7 TB

- 12 months physical storage with headroom = 
12 months physical storage: 345.3 TB * headroom: 1.30 ≈ 449.0 TB

- 24 months physical with headroom =
690_697_912_320_000 * 1.30 =
897_907_286_016_000 bytes
≈ 897.9 TB

---

## Bandwidth Budget

Components:
- **Ingress** (client writes)
- **Egress** (responses to clients)
- **Replication egress** (`× RF`)
- **Change-event fan-out**:
  - search index
  - cache invalidation
  - audit log

Total:
- Sum all traffic
- Compare against NIC capacity at **70% utilisation**

- Ingress =
695 * 4096 =
2_846_720 bytes/s
≈ 2.85 MB/s

- Egress =
6250 * 4096 =
25_600_000 bytes/s
≈ 25.6 MB/s

- Replication egress =
2_846_720 * 3 =
8_540_160 bytes/s
≈ 8.54 MB/s

- Change-event fan-out =
2_846_720 * 2.0 =
5_693_440 bytes/s
≈ 5.69 MB/s

**use AI to calculate**
- Total bandwidth: 42.7 MB/s
Ingress: 2_846_720 + Egress: 25_600_000 + Replication egress: 8_540_160 + Change-event fan-out: 5_693_440 = 42_680_320 bytes/s

- NIC capacity: ≈ 1.25 GB/s
network_bandwidth_gbps: 10 * 1_000_000_000 bits/s / bits_per_byte: 8 = 1_250_000_000 bytes/s

- NIC capacity at target utilisation: 875 MB/s
NIC capacity: 1_250_000_000 * target_utilisation: 0.70 = 875_000_000 bytes/s

- NIC utilisation: ~4.9%
Total bandwidth: 42_680_320 / NIC capacity at target utilisation: 875_000_000 = 0.0488

---

## Working-Set Memory

- Hot data per node
- Per-connection working set:
  - `× peak concurrent connections`
- Cache size:
  - based on assumed hit ratio

- Usable QPS per node =
instance_qps_capacity: 5_000 * target_buffer_pct (1 - 0.40) =
3_000 QPS/node

- Required nodes =
ceil(write peak and read peak: 6_944 / 3_000 QPS/node) =
3 nodes

**Using 12-month physical storage with headroom**
- Hot data total =
449 TB * hot_data_fraction 1.0 =
449 TB

- Hot data per node =
449 TB / 3 =
150 TB/node

- Weighted service time (average latency per request): 1.2 ms
0.80 (cache hit ratio) * 0.5 ms (cache hit latency)
+ 0.20 (cache miss ratio) * 4.0 ms (storage latency)
= 0.4 ms + 0.8 ms
= 1.2 ms

- Peak concurrent requests =
6_945 * 0.0012 =
8.33 concurrent requests

- Peak concurrent connections per node =
8.33 / 3 =
2.78
≈ 3 connections/node

- Cache size/node =
Hot data per node: 150 TB * cache_hit_ratio: 0.80 =
120 TB/node

- Working-set memory

Memory for node ≈
150 TB (data) + 120 TB (cache) + connection overhead (30%) = 350 TB

### Total cluster memory (3 nodes)

Total ≈
350 TB × 3 = 1050 TB

---

## Capacity Buffer

- Formula:
  - `slowest_tier_time_to_scale × max projected growth rate + safety margin`
- Target utilisation:
  - **Kubernetes (≈2 min scale):** 70–80%
  - **Storage (≈2 weeks):** 60–70%
  - **Bare metal (≈4 weeks):** 40–50%

slowest_tier_time_to_scale = 4 weeks (bare metal)
max_projected_growth_rate = not provided  
→ assumption: 5% per week
safety_margin = (50–60% buffer)
target utilisation = 40%
target_buffer_pct = 60%
---

## Cost Line

- Metrics:
  - **Cost per 1000 QPS**
  - **Cost per TB stored**
- Based on:
  - per-tier unit prices from `config.yaml`

Nodes = 3  
Cost per node = 350 USD/month

- Total monthly cost = 3 * 350 = 1_050 USD/month

- Cost per 1000 QPS =
1_050 / (6_945 / 1000) =
1_050 / 6.945 =
151 USD per 1000 QPS

- Cost per TB =
1_050 / 449 =
2.34 USD per TB/month
