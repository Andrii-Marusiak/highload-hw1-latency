At which workload condition does latency first rise significantly? Is that consistent with the saturation knee described in the theory?

Latency не зростає значущо в жодному з режимів. 
Saturation knee не спостерігається, оскільки ні середня, ні p95 latency не демонструють росту.
Згідно з Little’s Law, середня кількість запитів у системі відповідає кількості воркерів. Тому запити оброблялись без видимого росту черги.


Apply Little's Law: L = λ × W. Using the throughput (λ) and mean latency (W) from the parallel baseline, calculate the implied in-flight concurrency (L). Does this match the worker count you configured?

Згідно з Little’s Law, середня кількість запитів у системі (~4 для Parallel та Saturated і 1 для Serial) відповідає кількості воркерів

What is the ratio of p95 to mean latency in the saturated run? What does a high ratio (e.g., >3×) tell you about queue depth?

Співвідношення p95 to mean становить 1.22, це означає, що черга ще не почала накопичуватись і більшість часу запит виконується воркером
Якщо співвідношення росте і становить, наприклад 3, це означає, що часттина запитів проводить час в черзі, а не виконується воркером
В бенчмарку середній saturation більше 80%, отже черги може не бути, або вона не значна. Однак 80% це вже значення, на яке треба мати алерт
