"""Two checks on the pitch-familiarity estimate (`baseball.edge.familiarity`).

1. A null by shuffling. The earlier-PA exposure pair (prev_same, prev_other) is permuted between rows inside
   a stratum and the model is refit. Games, the multiset of counts, fixed effects and every control stay as
   they are; only which row carries which count changes. Three strata are run, because they cut different links:

   - WITHIN_HITTER: game x pitcher x batter, over every pitch of the matchup. Each hitter keeps his own counts
     from that game against that pitcher, in a random order. This also cuts the tie between the count and the
     time through the order.
   - WITHIN_PA: game x pitcher x batter x plate appearance, over every pitch of the plate appearance. The total
     he has seen is the same on every pitch of a plate appearance, so it stays exactly as it was. Only which
     pitch type the count belongs to is scrambled.
   - ACROSS_HITTERS: game x pitcher x time through x pitch type, over the model's rows. Hitters facing the same
     pitcher on the same day at the same time through swap counts. Only the hitter's own history is cut.

   A shuffle inside a stratum keeps whatever differs BETWEEN strata (a random reordering replaces each row's
   count, on average, with its stratum mean). So the null mean is the coefficient the between-stratum pattern
   produces alone. That pattern can hold a real effect as well as selection, so the null mean is not a
   "no effect anywhere" benchmark. The test is of the within-stratum link: the share of shuffles that reach
   the real coefficient.

2. Leave-own-game-out. Two versions.

   - Fixed effects (`fit_leave_game_out`): each row is scored against its pitcher x type x season and
     batter x group x season effects as they would be without the row's own game. With e the residuals of the
     ordinary fit, leaving game g out of a key's effect moves it by -n_g / (n - n_g) x mean(e in g), so the
     refit needs no loop over games. The slopes and the other family of effects are not re-estimated for each
     of the 7,000+ games; that part is second order.
   - Levels (`fit_levels`): no fixed effects. Two columns stand in for them: the pitcher's whiff rate on this
     pitch type this season and the hitter's against this pitch group, from every OTHER game. Simpler to read,
     but a level from a few games is a noisier control than a fixed effect.

   Why it matters: a pitcher goes back to what just worked. A whiff early in a game then raises both the
   later exposure counts and the season mean the fixed effect subtracts, which pushes the ordinary estimate
   below zero even when exposure does nothing (`tests/test_familiarity_checks.py` plants exactly this).

Run: `python -m baseball.edge.familiarity_checks` (writes reports/outputs/familiarity-checks-2024-26.json).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from baseball.edge import familiarity as fam
from baseball.stats import absorb, clustered_wls

ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = ROOT / "reports" / "outputs" / "familiarity-checks-2024-26.json"

PAIR = ("prev_same", "prev_other")
TERMS = ["prev_same", "prev_total", "pa_same", "pa_total", "game_same", "game_total"]
WITHIN_HITTER = ("game_pk", "pitcher", "batter")
WITHIN_PA = ("game_pk", "pitcher", "batter", "prior_pa")
ACROSS_HITTERS = ("game_pk", "pitcher", "prior_pa", "pitch_type")
GROUPS = ["fastball", "breaking", "offspeed", "cutter"]

# Columns the checks need (the full table with every Statcast column does not fit in 8 GB of memory)
SLIM = ["game_pk", "game_year", "pitcher", "batter", "p_throws", "stand", "pitch_type", "group", "balls", "strikes",
        "release_speed", "release_spin_rate", "pfx_x", "pfx_z", "plate_x", "plate_z", "sz_top", "sz_bot", "zone",
        "prev_same", "prev_other", "pa_same", "pa_other", "game_same", "game_other", "prior_pa", "pitch_count",
        "swing", "whiff", "pkey", "bkey"]


# ---------------------------------------------------------------- shuffling

def group_codes(d: pd.DataFrame, cols) -> np.ndarray:
    """One integer per distinct combination of the columns."""
    return d.groupby(list(cols), sort=False, dropna=False).ngroup().to_numpy()


def permute_within(codes: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """A random permutation that only moves rows inside their own group. Row i takes the values of row
    perm[i], and codes[perm[i]] == codes[i] for every i."""
    codes = np.asarray(codes)
    base = np.argsort(codes, kind="stable")
    order = np.lexsort((rng.random(len(codes)), codes))
    perm = np.empty(len(codes), dtype=np.int64)
    perm[base] = order
    return perm


# ---------------------------------------------------------------- a fast refit when only two columns change

def _absorb_codes(v: np.ndarray, codes: list, counts: list, iters: int = 50, tol: float = 1e-9) -> np.ndarray:
    """`baseball.stats.absorb` for one column, with the group codes already made."""
    v = v.astype(float).copy()
    for _ in range(iters):
        change = 0.0
        for c, n in zip(codes, counts):
            means = np.bincount(c, weights=v) / n
            v -= means[c]
            change = max(change, float(np.abs(means).max()))
        if change < tol:
            break
    return v


class Partial:
    """Refit the model many times when only some regressors change.

    The outcome and the fixed regressors are residualized on the fixed effects once. Each call residualizes
    the new columns the same way, removes the fixed regressors from them, and solves the small system that is
    left. By Frisch-Waugh-Lovell the coefficients equal those of the full fit.
    """

    def __init__(self, d: pd.DataFrame, y: str, fixed: list[str], fe: tuple):
        self.codes = [pd.factorize(d[k])[0] for k in fe]
        self.counts = [np.bincount(c) for c in self.codes]
        ry = _absorb_codes(d[y].to_numpy(float), self.codes, self.counts)
        cols = [_absorb_codes(d[c].to_numpy(float), self.codes, self.counts) for c in fixed]
        cols = [v for v in cols if np.abs(v).max() > 1e-9]                # drop columns the FE swallowed
        if cols:
            u, s, _ = np.linalg.svd(np.column_stack(cols), full_matrices=False)
            self.basis = u[:, s > s.max() * 1e-10]
        else:
            self.basis = np.zeros((len(d), 0))
        self.ty = self._clear(ry)

    def _clear(self, v: np.ndarray) -> np.ndarray:
        return v - self.basis @ (self.basis.T @ v)

    def coefs(self, columns: list[np.ndarray]) -> np.ndarray:
        x = np.column_stack([self._clear(_absorb_codes(np.asarray(c, float), self.codes, self.counts)) for c in columns])
        return np.linalg.lstsq(x, self.ty, rcond=None)[0]


# ---------------------------------------------------------------- check 1: the null

def null_shuffle(pool: pd.DataFrame, sample: pd.Series, strata=WITHIN_HITTER, y: str = "whiff",
                 n_shuffles: int = 1000, seed: int = 0, location: bool = True,
                 fe: tuple = ("pkey", "bkey")) -> dict:
    """Refit the main model with the earlier-PA exposure pair shuffled inside each stratum.

    pool: the rows the counts are shuffled over (they carry the strata columns and the exposure columns).
    sample: boolean, same index as pool: the rows the model is fit on (e.g. swings at fastballs).
    The model is `familiarity.fit_pairs`: the reported coefficient is the same-minus-other contrast for
    earlier plate appearances today. Its other terms (this PA, earlier games) keep their real values.

    Returns the real coefficient, the shuffled coefficients (`null`, one per shuffle), the share of model rows
    whose pair changed in an average shuffle (`share_moved`), the share alone in their stratum, which can
    never change (`share_alone`), and counts. Coefficients are in the outcome's own units.
    """
    pool = pool.reset_index(drop=True)
    mask = np.asarray(sample, dtype=bool)
    q = pool[mask].copy()
    for w in ("prev", "pa", "game"):
        q[f"{w}_total"] = q[f"{w}_same"] + q[f"{w}_other"]
    d, xcols = fam.design(q, y, TERMS, location, fe)
    rows = d.index.to_numpy()                                             # positions in pool
    part = Partial(d, y, [c for c in xcols if c not in ("prev_same", "prev_total")], fe)
    same, other = pool[PAIR[0]].to_numpy(float), pool[PAIR[1]].to_numpy(float)
    observed = part.coefs([same[rows], (same + other)[rows]])

    codes = group_codes(pool, strata)
    live = np.flatnonzero(np.isin(codes, codes[rows]))                    # strata with no model row can't matter
    codes_live = codes[live]
    at = np.searchsorted(live, rows)                                      # the model rows inside `live`
    rng = np.random.default_rng(seed)
    null = np.empty((n_shuffles, 2))
    moved = 0.0
    for i in range(n_shuffles):
        take = live[permute_within(codes_live, rng)[at]]
        s, o = same[take], other[take]
        null[i] = part.coefs([s, s + o])
        moved += float(((s != same[rows]) | (o != other[rows])).mean())
    return {"observed": float(observed[0]), "observed_other": float(observed[1]), "null": null[:, 0],
            "null_other": null[:, 1], "n": int(len(d)), "strata": int(len(np.unique(codes[rows]))),
            "share_moved": moved / max(n_shuffles, 1),
            "share_alone": float((np.bincount(codes)[codes[rows]] == 1).mean()), "n_shuffles": int(n_shuffles), "seed": int(seed)}


def null_summary(res: dict, scale: float = 100.0) -> dict:
    """Where the real coefficient sits in the shuffled ones.

    p_lower: share of shuffles at or below the real coefficient (one-sided; the claim is a negative effect).
    p_two_sided: share of shuffles at least as far from the null mean as the real coefficient is.
    Both count the real fit as one draw, so the smallest value is 1 / (n_shuffles + 1).
    """
    null, obs, n = np.asarray(res["null"]) * scale, res["observed"] * scale, res["n_shuffles"]
    mean, sd = float(null.mean()), float(null.std(ddof=1))
    return {
        "observed": obs, "null_mean": mean, "null_sd": sd,
        "null_lo": float(np.quantile(null, 0.025)), "null_hi": float(np.quantile(null, 0.975)),
        "null_min": float(null.min()), "null_max": float(null.max()),
        "observed_minus_null_mean": obs - mean, "z": (obs - mean) / sd if sd > 0 else float("nan"),
        "p_lower": float((1 + (null <= obs).sum()) / (n + 1)),
        "p_two_sided": float((1 + (np.abs(null - mean) >= abs(obs - mean)).sum()) / (n + 1)),
        "null_mean_se": sd / np.sqrt(n),
        "n": res["n"], "strata": res["strata"], "share_moved": res["share_moved"],
        "share_alone": res["share_alone"], "n_shuffles": n, "seed": res["seed"],
    }


# ---------------------------------------------------------------- check 2: leave-own-game-out

def _with_totals(p: pd.DataFrame) -> pd.DataFrame:
    q = p.copy()
    for w in ("prev", "pa", "game"):
        q[f"{w}_total"] = q[f"{w}_same"] + q[f"{w}_other"]
    return q


def _label(tab: pd.DataFrame) -> pd.DataFrame:
    names = {}
    for w in ("prev", "pa", "game"):
        names[f"{w}_same"], names[f"{w}_total"] = f"{w}: same - other", f"{w}: other type"
    tab["term"] = tab["term"].replace(names)
    return tab


def leave_game_out_mean(d: pd.DataFrame, y: str, key: str, game: str = "game_pk") -> pd.Series:
    """For each row, the mean of y over rows with the same key in every other game. Missing when the key
    has no other game."""
    tot = d.groupby(key)[y].transform("sum")
    n = d.groupby(key)[y].transform("size")
    own = d.groupby([key, game])[y].transform("sum")
    n_own = d.groupby([key, game])[y].transform("size")
    left = n - n_own
    return ((tot - own) / left.where(left > 0)).rename(f"{key}_level")


def fit_leave_game_out(p: pd.DataFrame, y: str = "whiff", location: bool = True, fe: tuple = ("pkey", "bkey"),
                       game: str = "game_pk", cluster: str = "pitcher") -> pd.DataFrame:
    """The main model with every row scored against fixed effects that leave its own game out.

    Rows whose pitcher key or batter key appears in one game only have no leave-out effect and are dropped.
    Returns one row per exposure term: coef, se, t, p (leave-own-game-out), and coef_in, se_in (the ordinary
    fixed-effect fit on the same rows), plus n and the number of clusters.
    """
    from scipy.stats import norm

    q = _with_totals(p)
    d, xcols = fam.design(q, y, TERMS, location, fe, cluster)
    g = q.loc[d.index, game]
    while True:                                   # a key needs two games; dropping rows can strand another key
        ok = np.ones(len(d), dtype=bool)
        for k in fe:
            ok &= g.groupby(d[k]).transform("nunique").to_numpy() > 1
        if ok.all():
            break
        d, g = d[ok], g[ok]
    r = absorb(d, [y, *xcols], list(fe))
    keep = [c for c in xcols if r[c].abs().max() > 1e-9]
    ry, X, cl = r[y].to_numpy(), r[keep].to_numpy(), d[cluster].to_numpy()
    beta_in, se_in = clustered_wls(ry, X, np.ones(len(d)), cl)
    e = pd.Series(ry - X @ beta_in, index=d.index)
    shift = np.zeros(len(d))                      # own-game share of each effect, handed back to the row
    for k in fe:
        n = e.groupby(d[k]).transform("size")
        n_own = e.groupby([d[k], g]).transform("size")
        shift += (n_own / (n - n_own) * e.groupby([d[k], g]).transform("mean")).to_numpy()
    beta, se = clustered_wls(ry + shift, X, np.ones(len(d)), cl)
    out = pd.DataFrame({"term": keep, "coef": beta, "se": se, "coef_in": beta_in, "se_in": se_in})
    out["t"] = out["coef"] / out["se"]
    out["p"] = 2 * norm.sf(out["t"].abs())
    out["n"] = len(d)
    out["clusters"] = d[cluster].nunique()
    return _label(out[out["term"].isin(TERMS)].reset_index(drop=True))


def fit_levels(p: pd.DataFrame, y: str = "whiff", own_game: bool = False, location: bool = True,
               fe: tuple = ("pkey", "bkey"), game: str = "game_pk") -> pd.DataFrame:
    """The main model with each fixed effect replaced by a level column.

    own_game=False: the level is the mean of y for the row's pitcher x type x season (and batter x group x
    season) in every other game. own_game=True: the same mean with the own game left in, as the comparison.
    The model has an intercept and no absorbed fixed effects. Rows start from the fixed-effect model's sample;
    rows whose pitcher or batter key has no other game are dropped (in both versions, so the samples match).
    Returns `familiarity.fit` rows for the exposure terms and the two levels, labelled like `fit_pairs`.
    """
    q = _with_totals(p)
    d, _ = fam.design(q, y, TERMS, location, fe)
    q = q.loc[d.index]
    levels = []
    for k in fe:
        out = leave_game_out_mean(q, y, k, game)
        q[f"{k}_level"] = q.groupby(k)[y].transform("mean").where(out.notna()) if own_game else out
        levels.append(f"{k}_level")
    q["_one"] = 1
    return _label(fam.fit(q, y, [*TERMS, *levels], location, fe=("_one",)))


# ---------------------------------------------------------------- the run

def prepare_slim(seasons: list[int]) -> pd.DataFrame:
    """`familiarity.prepare`, one season at a time and keeping only the columns the checks use."""
    parts = []
    for s in seasons:
        p = fam.keys(fam.outcomes(fam.exposures(fam.load_seq(s))))
        parts.append(p[SLIM].copy())
        del p
    return pd.concat(parts, ignore_index=True)


DESIGNS = {"within_hitter": (WITHIN_HITTER, "every pitch of the matchup"),
           "within_pa": (WITHIN_PA, "every pitch of the plate appearance"),
           "across_hitters": (ACROSS_HITTERS, "the model's rows (swings in the group)")}
_TABLE: pd.DataFrame | None = None


def _run_group(args: tuple) -> dict:
    """Both checks for one pitch group (whiff per swing, points)."""
    grp, n_shuffles, seed = args
    p = _TABLE
    r4 = lambda x: round(float(x), 4)  # noqa: E731
    sample = p["group"].eq(grp) & p["swing"].eq(1)
    sw = p[sample]
    out = {"null": [], "draws": {}, "leave_game_out": []}
    for di, (name, (strata, _)) in enumerate(DESIGNS.items()):
        pool, mask = (sw, pd.Series(True, index=sw.index)) if name == "across_hitters" else (p, sample)
        res = null_shuffle(pool, mask, strata, "whiff", n_shuffles, seed + di)
        out["null"].append({"group": grp, "design": name,
                            **{k: (r4(v) if isinstance(v, float) else v) for k, v in null_summary(res).items()}})
        out["draws"][f"{grp}|{name}"] = [r4(100 * v) for v in res["null"]]

    def add(spec, term, coef, se, n, clusters):
        k = 1 if term.endswith("_level") else 100                  # a level's slope is whiff per whiff
        z = coef / se
        from scipy.stats import norm
        out["leave_game_out"].append({"group": grp, "spec": spec, "term": term, "coef": r4(k * coef), "se": r4(k * se),
                                      "p": float(2 * norm.sf(abs(z))), "n": int(n), "clusters": int(clusters)})

    for _, r in fam.fit_pairs(sw, "whiff").iterrows():
        add("fixed effects (published)", r["term"], r["coef"], r["se"], r["n"], r["clusters"])
    for _, r in fit_leave_game_out(sw).iterrows():
        add("fixed effects, rows with another game", r["term"], r["coef_in"], r["se_in"], r["n"], r["clusters"])
        add("fixed effects, own game left out", r["term"], r["coef"], r["se"], r["n"], r["clusters"])
    for own, spec in [(True, "levels, own game included"), (False, "levels, own game left out")]:
        for _, r in fit_levels(sw, own_game=own).iterrows():
            add(spec, r["term"], r["coef"], r["se"], r["n"], r["clusters"])
    return out


def run(seasons: list[int] | None = None, n_shuffles: int = 1000, seed: int = 20261114,
        out_path: Path | None = OUT_PATH, jobs: int = 1, log=print) -> dict:
    """Both checks on whiff per swing for the four pitch groups. Writes a small JSON of the results.

    Each group and design gets its own seed (seed + 10 x group index + design index), so the result does not
    depend on `jobs`.
    """
    import json
    import time

    global _TABLE
    seasons = seasons or [2024, 2025, 2026]
    t0 = time.time()
    _TABLE = p = prepare_slim(seasons)
    log(f"{len(p):,} pitches, {p['game_pk'].nunique():,} games ({time.time() - t0:.0f}s)")
    out = {
        "source": f"python -m baseball.edge.familiarity_checks on data/seq (regular seasons {seasons[0]}-{seasons[-1]}). "
                  "Whiff per swing, points. Coefficient: one earlier pitch of the same type in place of another type, "
                  "earlier plate appearances today.",
        "sample": {"seasons": seasons, "pitches": int(len(p)), "games": int(p["game_pk"].nunique()), "swings": int(p["swing"].sum())},
        "null": {"n_shuffles": n_shuffles, "seed": seed, "shuffled": list(PAIR),
                 "designs": {k: {"strata": list(s), "pool": pool} for k, (s, pool) in DESIGNS.items()},
                 "results": [], "draws": {}},
        "leave_game_out": [],
    }
    tasks = [(grp, n_shuffles, seed + 10 * gi) for gi, grp in enumerate(GROUPS)]
    if jobs > 1:
        import multiprocessing as mp
        with mp.get_context("fork").Pool(jobs) as pool:
            parts = pool.map(_run_group, tasks, chunksize=1)
    else:
        parts = [_run_group(t) for t in tasks]
    for part in parts:
        out["null"]["results"] += part["null"]
        out["null"]["draws"].update(part["draws"])
        out["leave_game_out"] += part["leave_game_out"]
    for r in out["null"]["results"]:
        log(f"  {r['group']} {r['design']}: real {r['observed']:+.3f}, null {r['null_mean']:+.3f} (SD {r['null_sd']:.3f}), p {r['p_lower']:.4f}")
    log(f"done ({time.time() - t0:.0f}s)")
    if out_path is not None:
        Path(out_path).write_text(dump(out))
    return out


def dump(out: dict) -> str:
    """The results as JSON, with each list of 1,000 shuffled coefficients on one line."""
    import json

    draws = out["null"]["draws"]
    slim = {**out, "null": {**out["null"], "draws": {k: f"@{i}@" for i, k in enumerate(draws)}}}
    text = json.dumps(slim, indent=1)
    for i, k in enumerate(draws):
        text = text.replace(f'"@{i}@"', json.dumps(draws[k], separators=(",", ":")))
    return text + "\n"


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Null shuffle and leave-own-game-out checks on the familiarity estimate")
    ap.add_argument("--shuffles", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=20261114)
    ap.add_argument("--jobs", type=int, default=1)
    a = ap.parse_args()
    run(n_shuffles=a.shuffles, seed=a.seed, jobs=a.jobs)
