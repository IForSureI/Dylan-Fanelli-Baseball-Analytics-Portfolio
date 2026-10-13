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


def benjamini_hochberg(p_values) -> list[float]:
    """False-discovery-rate q-values for a list of p-values (NaN stays NaN).

    When hundreds of changes are each tested, about 5% clear p < 0.05 by chance alone. A q-value is
    the expected share of false findings among everything at least that significant, so q < 0.10
    means about 1 in 10 of those findings is noise.
    """
    import numpy as np

    p = np.asarray(p_values, dtype=float)
    q = np.full_like(p, np.nan)
    ok = ~np.isnan(p)
    if not ok.any():
        return q.tolist()
    pv = p[ok]
    order = np.argsort(pv)
    ranked = pv[order] * len(pv) / np.arange(1, len(pv) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty_like(pv)
    out[order] = np.minimum(ranked, 1.0)
    q[ok] = out
    return q.tolist()


def clustered_wls(y, X, w, clusters):
    """Weighted least squares with standard errors clustered by group (e.g. pitcher).

    Use when rows aren't independent: the same pitcher's pitches, or the same pitch across seasons.
    Returns (beta, se). Small-sample factor G/(G-1) * (n-1)/(n-k).
    """
    import numpy as np

    y, X, w = np.asarray(y, float), np.asarray(X, float), np.asarray(w, float)
    Xw = X * w[:, None]
    bread = np.linalg.pinv(X.T @ Xw)
    beta = bread @ (Xw.T @ y)
    e = y - X @ beta
    meat = np.zeros((X.shape[1], X.shape[1]))
    clusters = np.asarray(clusters)
    groups = np.unique(clusters)
    for g in groups:
        m = clusters == g
        s = (Xw[m] * e[m][:, None]).sum(axis=0)
        meat += np.outer(s, s)
    n, k, G = len(y), X.shape[1], len(groups)
    adj = (G / max(G - 1, 1)) * ((n - 1) / max(n - k, 1))
    cov = adj * bread @ meat @ bread
    return beta, np.sqrt(np.diag(cov))


def wls_loo_rmse(y, X, w):
    """Leave-one-out RMSE of a weighted least-squares fit (closed form via leverage), weighted by w."""
    import numpy as np

    y, X, w = np.asarray(y, float), np.asarray(X, float), np.asarray(w, float)
    Xw = X * np.sqrt(w)[:, None]
    H = Xw @ np.linalg.pinv(Xw.T @ Xw) @ Xw.T
    beta = np.linalg.pinv(X.T @ (X * w[:, None])) @ (X.T @ (w * y))
    e = (y - X @ beta) / (1 - np.diag(H))
    return float(np.sqrt(np.average(e**2, weights=w)))
