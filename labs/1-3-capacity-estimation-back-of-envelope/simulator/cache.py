"""Tiny seeded cache stub used by the latency benchmark.

We don't simulate a real LRU; the goal is just to drive the per-request
latency model with a Bernoulli hit/miss decision whose long-run rate
matches ``infra.cache_hit_ratio``.  A seeded RNG keeps results
reproducible across runs (important when comparing baseline vs
improvement results in ``results.md``).
"""

from __future__ import annotations

import random


class SeededCache:
    """Bernoulli-style cache: ``is_hit`` returns True with probability p."""

    def __init__(self, hit_ratio: float, seed: int) -> None:
        if not 0.0 <= hit_ratio <= 1.0:
            raise ValueError("hit_ratio must be in [0, 1]")
        self._hit_ratio = hit_ratio
        self._rng = random.Random(seed)
        self._lock_seed = seed

    def is_hit(self) -> bool:
        return self._rng.random() < self._hit_ratio
