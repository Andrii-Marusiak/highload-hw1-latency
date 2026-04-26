# Environment

* Python 3.14.4
* masOs Darwin Kernel Version 24.3.0
* CPU count: 12 (Apple M3 Pro)

---

# Workload Shape Analysis
| Profile  | CV    | Mean latency (ms) | p95 latency (ms) | Throughput (r/s) | Bottleneck util %      |
|----------|-------|-------------------|------------------|------------------|------------------------|
| Poisson  | 1.08  | 13.54             | 20.38            | 204.86           | 58.6 (connection_pool) |
| Bursty   | 2.50  | 13.87             | 20.38            | 190.73           | 55.7 (connection_pool) |

Explain why bursty p95 is higher despite identical average load?
В моєму кейсі вони однакові, через те, що система не довантажена, менше 70%, тому Queue Saturation в нормі.
В теорії, при Bursty Bottleneck util % в моменті може наближатись до 100%, що спричинить стрибки p95 latency. 

# Improvement Impact (Bursty Condition)

| Metric               | Baseline (bursty) | Improved (bursty) | Delta   |
|----------------------|-------------------|-------------------|---------|
| Mean latency (ms)    | 13.87             | 14.54             | +0.67   |
| p95 latency (ms)     | 20.38             | 20.01             | -0.37   |
| Throughput (r/s)     | 190.73            | 220.41            | +29.68  |
| Rejected requests    | 0                 | 0                 | 0       |
| Bottleneck util %    | 55.7              | 64.1              | +8.4    |

---


# Read/Write Ratio Sweep

| read_fraction | Bottleneck resource | Util % | Mean (ms) | p95 (ms) | Replica lag (ms) |
|---------------|---------------------|--------|-----------|----------|------------------|
| 0.50          | io_subsystem        | 56.1   | 14.63     | 21.03    | 5 (reads only)   |
| 0.80          | connection_pool     | 63.7   | 12.99     | 19.46    | 5 (reads only)   |
| 0.95          | connection_pool     | 62.2   | 12.13     | 14.97    | 5 (reads only)   |

## Baseline vs Improved

| read_fraction | Variant  | Bottleneck     | Util % | Mean (ms) | p95 (ms) | Throughput (r/s) |
|---------------|----------|----------------|--------|-----------|----------|------------------|
| 0.50          | baseline | io_subsystem   | 56.1   | 14.63     | 21.03    | 151.99           |
| 0.50          | improved | io_subsystem   | 66.5   | 15.46     | 21.05    | 180.87           |
| 0.80          | baseline | connection_pool| 63.7   | 12.99     | 19.46    | 232.36           |
| 0.80          | improved | connection_pool| 58.8   | 13.86     | 19.72    | 213.96           |
| 0.95          | baseline | connection_pool| 62.2   | 12.13     | 14.97    | 241.99           |
| 0.95          | improved | connection_pool| 60.2   | 13.38     | 15.72    | 234.51           |

Після імплементації CQRS bottleneck для `read_fraction=0.50` не змінився — `io_subsystem` залишився вузьким місцем, однак його утилізація зросла з 56.1% до 66.5%, що залишається в межах норми (<70%), а throughput виріс на +28.88 r/s. У read-heavy сценаріях (`read_fraction=0.80` та `0.95`) `connection_pool` був незначно розвантажений (з 63.7% до 58.8% і з 62.2% до 60.2% відповідно) — reads перейшли на репліку і більше не займають worker-слоти primary.

---

# New Risk Introduced

Впровадження опції B (CQRS replica routing) переносить усі читання на репліку, що породжує новий клас відмов — **replica lag**. Якщо репліка відстає від primary (через мережеву затримку, важкий write-потік або failover), клієнти читатимуть застарілі дані, а не отримають помилку — тобто проблема буде невидима на рівні latency або throughput метрик. 
На PROD це може призвести до порушення варіантів бізнес-логіки (наприклад, читання балансу одразу після списання). 
Щоб виявляти це рано, на дашборд необхідно додати метрику **`replica_lag_ms` p95**: якщо вона перевищує допустимий поріг (наприклад, 100 ms), система має або перемикати читання назад на primary, або підіймати alert — до того як клієнти побачать stale reads.
Також на Лекції 3 стало зрозуміло, що кількість реплік прямов впливатиме на ресурси системи. Тому потенційно я би додав ще дашборд для розуміння того, як швидко система впиратиметься в hardware і коли ініціювати scale. Наприклад для storage

---

# Bottleneck Migration and Next Step

Після впровадження CQRS (read replica routing) наступним вузьким місцем залишається **connection pool** у read-heavy сценаріях і зміщується до **I/O subsystem** у збалансованих навантаженнях (`read_fraction = 0.50`).
Насичення вузького місця можна відстежувати через **utilisation ресурсу (%)**, зокрема:
- `connection_pool utilisation` для read-heavy сценаріїв  
- `io_subsystem utilisation` для write-heavy або збалансованих сценаріїв  
Наступним кроком варто **збільшити паралелізм I/O (`io_workers`)** або оптимізувати шлях запису (наприклад, batching), щоб зменшити навантаження на I/O subsystem.
