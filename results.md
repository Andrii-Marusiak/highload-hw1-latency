# Environment

* Python 3.14.4
* masOs Darwin Kernel Version 24.3.0
* CPU count: 12 (Apple M3 Pro)

---

# Benchmark Results

| Condition | Version  | Mean Latency (ms) | p95 Latency (ms) | Throughput (req/s) | Workers |
| --------- | -------- | ----------------- | ---------------- | ------------------ | ------- |
| Serial    | Baseline | 12.05             | 14.59            | 82.66 r/s          | 1       |
| Serial    | Improved | 12.02             | 14.79            | 82.80 r/s          | 1       |
| Parallel  | Baseline | 12.04             | 14.52            | 330.50 r/s         | 4       |
| Parallel  | Improved | 11.70             | 14.21            | 4765.34 r/s        | 64      |
| Saturated | Baseline | 11.81             | 14.45            | 337.30 r/s         | 4       |
| Saturated | Improved | 11.33             | 13.99            | 5324.54 r/s        | 64      |

---

## Observations

1. **Serial Improved L** = залишається однаковим, рішення не стосувалось даного сценарію.
   L тяжіє до 1, що відповідає кількості задіяних workers

2. **Parallel Improved L** = 55

3. **Saturated Improved L** = 60

Отже система майже повністю завантажена, але черга мінімальна, оскільки p95 не перевищує Mean Latency (ms), а L майже дорівнює Workers

---

# Questions

## 1) What changed between baseline and improved, and in which direction (better or worse) for each metric?

Ще в початковому бенчмарку було помічено лінійне зростання Throughput під час додавання Workers.
При тому що p95 та Mean залишались у межах похибки.

Тому я обрав Worker count tuning із заготовкою на дотримання The Universal Scalability Law, щоб система перевіряла, чи при додаванні нових Workers не збільшуєтсья p95.

В середньому Throughput виріс в 15 разів, лінійно до кількості Workers.

---

## 2) Which condition showed the largest improvement? Is this consistent with your theory-based prediction?

Parallel виграла від додавання Workers.
Відповідало спостереженню про лінійне зростання при невеликій або відсутній черзі.

---

## 3) Did the improvement affect the serial workload? Why or why not?

Ні, покращення не вплинуло на serial workload, оскільки його суть полягала у виборі достатньої кількості workers.

Latency не свідчили про зростання черги, отже я мав оперувати кількістю ресурсів.

---

## 4) At what point (if any) did the improvement reach diminishing returns?

Я не досяг такої точки, оскільки захардкодив максимум 64 Workers.

Припускаю, що метод пошуку кількості Workers при ще адекватній p95 міг би дійти до певної межі:
* фізичної, коли система не могла би підтримувати себе з великою кількістю нод, або за Amdahl's Law
* ресурсної, коли додаткові workers були би фінансово невиправданими, або впираються в hardware

---

# New Risk Introduced

Значна кількість воркерів підвищує споживання ресурсів CPU.
Тому потрібна метрика **CPU utilization (%)**

---

# What You Would Do Next

Я би знайшов межу, до якої можна розвивати паралелізм, коли система зламає The Knee та перейде в The Cliff.
Оскільки я збільшував кількість Workers, це підвищило CPU utilization (%), викликало ризик context switches.
Дотримуючись теорії щодо Gunther's Universal Scalability Law я би заміряв β і дізнався, як довго можна скейлити дану систему.

---

# Початкові питання завдання

## 1) At which workload condition does latency first rise significantly? Is that consistent with the saturation knee described in the theory?

Latency не зростає значущо в жодному з режимів.

Saturation knee не спостерігається, оскільки ні середня, ні p95 latency не демонструють росту.

Згідно з Little’s Law, середня кількість запитів у системі відповідає кількості воркерів.
Тому запити оброблялись без видимого росту черги.

---

## 2) Apply Little's Law: L = λ × W. Using the throughput (λ) and mean latency (W) from the parallel baseline, calculate the implied in-flight concurrency (L). Does this match the worker count you configured?

Згідно з Little’s Law, середня кількість запитів у системі (~4 для Parallel та Saturated і 1 для Serial) відповідає кількості воркерів

---

## 3) What is the ratio of p95 to mean latency in the saturated run? What does a high ratio (e.g., >3×) tell you about queue depth?

Співвідношення p95 to mean становить **1.22**, це означає, що черга ще не почала накопичуватись і більшість часу запит виконується воркером

Якщо співвідношення росте і становить, наприклад **3**, це означає, що частина запитів проводить час в черзі, а не виконується воркером

В бенчмарку середній saturation більше **80%**, отже черги може не бути, або вона не значна.
Однак **80%** це вже значення, на яке треба мати алерт

p.s. останнє твердження вже мною переглянуто, після лекції #2

---
