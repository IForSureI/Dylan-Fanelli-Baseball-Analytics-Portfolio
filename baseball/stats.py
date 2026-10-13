"""Small, dependency-free statistics used across the library.

- wilson()          : 95% interval for a rate (whiff%, chase%, ...). Better than the plain normal
                      interval when the sample is small or the rate is near 0% or 100%.
- two_proportion()  : is the change in a rate between two samples bigger than chance would give?
                      Two-sided z-test with a pooled proportion.
- spearman_brown()  : reliability of a k-times-larger sample (steps a split-half r up to the whole).
- fit_reliability_constant(): the M in r(n) = n / (n + M), the regression constant.
- shrink()          : regress an observed average toward a prior with constant M.
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
    # Sum the score (x * w * e) within each cluster in one pass (fast on millions of rows)
    groups, inv = np.unique(np.asarray(clusters), return_inverse=True)
    S = np.zeros((len(groups), X.shape[1]))
    np.add.at(S, inv, Xw * e[:, None])
    meat = S.T @ S
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


def spearman_brown(r, k):
    """Reliability of a sample k times as large as the one with reliability r: k r / (1 + (k - 1) r).

    Use it to step a split-half correlation up to the full sample: two halves of n/2 that correlate
    at r give the reliability of n as 2r / (1 + r). It is exact under r(n) = n / (n + M), the model
    the Reliability Atlas fits: spearman_brown(n / (n + M), k) == k n / (k n + M).
    """
    import numpy as np

    r = np.asarray(r, dtype=float)
    out = k * r / (1 + (k - 1) * r)
    return float(out) if out.ndim == 0 else out


def fit_reliability_constant(n, r, w=None, lo: float = 1e-3, hi: float = 1e7) -> float:
    """The M in r(n) = n / (n + M) that best fits observed reliabilities (weighted least squares).

    M is the sample at which reliability is 0.5: the regression constant, the number of league-average
    observations to add before averaging (Tango's "regress halfway" point). The fit is a golden-section
    search on log M, so it needs no extra dependency. Points with NaN are ignored.
    """
    import numpy as np

    n, r = np.asarray(n, float), np.asarray(r, float)
    w = np.ones_like(n) if w is None else np.asarray(w, float)
    ok = np.isfinite(n) & np.isfinite(r) & np.isfinite(w) & (w > 0)
    n, r, w = n[ok], r[ok], w[ok]
    if len(n) == 0:
        return float("nan")

    def loss(log_m: float) -> float:
        return float(np.sum(w * (r - n / (n + np.exp(log_m))) ** 2))

    a, b = np.log(lo), np.log(hi)
    g = (np.sqrt(5) - 1) / 2
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = loss(c), loss(d)
    for _ in range(200):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = loss(c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = loss(d)
        if b - a < 1e-10:
            break
    return float(np.exp((a + b) / 2))


def shrink(observed, n, prior_mean, m):
    """Regress an observed average toward a prior mean: (n * observed + m * prior) / (n + m).

    m is the regression constant (sample at which reliability is 0.5). The weight on the observation
    is n / (n + m), which is also its reliability. Works on scalars or arrays; n = 0 returns the prior.
    """
    import numpy as np

    observed, n = np.asarray(observed, float), np.asarray(n, float)
    w = n / (n + m)
    out = np.where(n > 0, w * np.nan_to_num(observed) + (1 - w) * prior_mean, prior_mean)
    return float(out) if out.ndim == 0 else out


def absorb(df, cols, fe, iters: int = 50, tol: float = 1e-9):
    """Remove several sets of fixed effects at once (alternating projections, unweighted).

    df: DataFrame; cols: columns to demean; fe: list of column names or lists of names, one per set of
    fixed effects (e.g. ["pitch_key", "batter_key"]). Returns a float frame of the residualized columns.
    Regressing residualized y on residualized X gives the same slopes as including every dummy
    (Frisch-Waugh-Lovell), without building millions of dummy columns.
    """
    import numpy as np
    import pandas as pd

    codes = [pd.factorize(df[k] if isinstance(k, str) else df[list(k)].astype(str).agg("|".join, axis=1))[0] for k in fe]
    counts = [np.bincount(c) for c in codes]
    out = {}
    for col in cols:
        v = df[col].to_numpy(float).copy()
        for _ in range(iters):
            change = 0.0
            for c, n in zip(codes, counts):
                means = np.bincount(c, weights=v) / n
                v -= means[c]
                change = max(change, float(np.abs(means).max()))
            if change < tol:
                break
        out[col] = v
    return pd.DataFrame(out, index=df.index)
