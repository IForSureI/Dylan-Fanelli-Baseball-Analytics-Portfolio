"""Small, dependency-free statistics used across the library.

- wilson()          : 95% interval for a rate (whiff%, chase%, ...). Better than the plain normal
                      interval when the sample is small or the rate is near 0% or 100%.
- two_proportion()  : is the change in a rate between two samples bigger than chance would give?
                      Two-sided z-test with a pooled proportion.
"""
from __future__ import annotations

import math


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for k successes in n trials, as proportions (0-1)."""
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, center - half), min(1.0, center + half))  # clamp float error at 0 and 1


def two_proportion(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float]:
    """Two-sided z-test for p2 - p1. Returns (z, p_value)."""
    if min(n1, n2) == 0:
        return (math.nan, math.nan)
    pooled = (k1 + k2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return (0.0, 1.0)
    z = (k2 / n2 - k1 / n1) / se
    return (z, math.erfc(abs(z) / math.sqrt(2)))
