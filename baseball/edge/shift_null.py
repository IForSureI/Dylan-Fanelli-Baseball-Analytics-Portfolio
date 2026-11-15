"""How often does the pitch-change detector fire when nothing changed? A permutation null.

  uv run python -m baseball.edge.shift_null 2026 --n 200 --seed 20261114

The detector (shifts.py) tries every split date and keeps the best one, so its |t| >= 6 bar has no
textbook false-positive rate. This module measures it on the real season:

1. For each pitcher, shuffle the order of his games. Every pitch stays in its game, so the spread
   inside a game and the link between his pitch types on the same day are kept. All of his pitch
   types move together, because the detector's "this pitch only" check compares them across one date.
2. Rerun the detector and the Edge Board's candidate filter on the shuffled season. Count candidates.
3. Repeat. The average count is what the detector returns on a season with no time order at all.

What the null covers: chance alone, given each pitcher's real game-to-game and pitch-to-pitch spread
and the search over split dates.
What it does not cover: anything real that moves with the calendar. A slow drift (velocity building
through the summer, a pitch fading with fatigue), a run of games in one park, or a tracking change
is destroyed by the shuffle along with deliberate changes. So the real count beating the null says
"this pitch's shape depended on the date", not "the pitcher made a change on that date".
`step_or_trend()` is a first read on that: does a step fit a candidate's game averages better than a
straight line through the season?

Speed: a shuffled series is first screened on per-game sums with the detector's own split search
(`shifts._best_split_arrays`). Only pitchers with a series that passes are sent through the full
`shifts.pitcher_shifts`, which makes every final call. `tests/test_edge_shift_null.py` checks the
screened path against the plain detector.
"""
from __future__ import annotations

import json
from multiprocessing import get_context
from pathlib import Path

import numpy as np
import pandas as pd

from baseball.edge import shifts

GATE_COLS = [c for c in shifts.METRICS if c != "arm_angle"]   # the candidate list leaves arm angle out
_SLACK = 1e-6   # screen a hair looser than the detector; pitcher_shifts decides
OUT = Path(__file__).resolve().parents[2] / "reports" / "outputs"


def prepare(pitches: pd.DataFrame) -> list[dict]:
    """One entry per pitcher: his rows, his game slots in date order, and per-game sums for the screen."""
    out = []
    pitches = pitches.assign(game_date=pd.to_datetime(pitches["game_date"]))
    for pid, g in sorted(pitches.groupby("pitcher", sort=False), key=lambda kv: kv[0]):
        slots = g[["game_date", "game_pk"]].drop_duplicates().sort_values(["game_date", "game_pk"]).reset_index(drop=True)
        key = pd.MultiIndex.from_frame(slots)
        code = key.get_indexer(pd.MultiIndex.from_frame(g[["game_date", "game_pk"]]))
        p = shifts._prepare(g.assign(_code=code))
        series = []
        for pt, q in p.groupby("pitch_type"):
            for col in GATE_COLS:
                v = q[col].to_numpy(float)
                ok = ~np.isnan(v)
                c, v = q["_code"].to_numpy()[ok], v[ok]
                n = np.bincount(c, minlength=len(slots)).astype(float)
                keep = np.flatnonzero(n >= shifts.MIN_PITCHES_PER_GAME)
                if len(keep) < shifts.MIN_GAMES:
                    continue
                s = np.bincount(c, weights=v, minlength=len(slots))
                ss = np.bincount(c, weights=v * v, minlength=len(slots))
                series.append({"pitch_type": pt, "col": col, "games": keep, "n": n[keep], "s": s[keep], "ss": ss[keep]})
        out.append({"pitcher": pid, "rows": g, "code": code, "dates": slots["game_date"].to_numpy(),
                    "pks": slots["game_pk"].to_numpy(), "series": series})
    return out


def _passes_screen(series: dict, perm: np.ndarray) -> bool:
    order = np.argsort(perm[series["games"]], kind="stable")
    k, shift, t, persistence = shifts._best_split_arrays(series["n"][order], series["s"][order], series["ss"][order])
    min_shift = shifts.METRICS[series["col"]][1]
    return (k >= 0 and abs(shift) >= min_shift * (1 - _SLACK) and abs(t) >= shifts.MIN_T * (1 - _SLACK)
            and persistence >= shifts.MIN_PERSISTENCE - _SLACK)


def detect(prepared: list[dict], rng: np.random.Generator | None = None, screen: bool = True) -> pd.DataFrame:
    """The detector's rows (arm angle left out) for the season with each pitcher's games reordered.

    rng None keeps the real order. With rng, game i takes the date and game number of slot perm[i].
    """
    parts = []
    for P in prepared:
        G = len(P["dates"])
        perm = np.arange(G) if rng is None else rng.permutation(G)
        if screen and not any(_passes_screen(s, perm) for s in P["series"]):
            continue
        slot = perm[P["code"]]
        found = shifts.pitcher_shifts(P["rows"].assign(game_date=P["dates"][slot], game_pk=P["pks"][slot]))
        if not found.empty:
            parts.append(found[found["metric"].isin(shifts.CANDIDATE_METRICS)])
    parts = [p for p in parts if len(p)]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _count(rows: pd.DataFrame, real_keys: frozenset = frozenset()) -> dict:
    """Counts for one season. real_keys: (pitcher, pitch_type) of the real-order candidates, so a shuffled
    season's hits can be split into pitches that are on the real list and pitches that are not."""
    c = shifts.candidates(rows)
    by = c["metric"].value_counts().to_dict() if len(c) else {}
    on_real = sum((int(a), b) in real_keys for a, b in zip(c["pitcher"], c["pitch_type"])) if len(c) else 0
    return {"detector_rows": int(len(rows)), "candidates": int(len(c)),
            "pitchers": int(c["pitcher"].nunique()) if len(c) else 0,
            "candidates_on_real_list": int(on_real), "candidates_off_real_list": int(len(c) - on_real),
            **{f"candidates: {m}": int(by.get(m, 0)) for m in shifts.CANDIDATE_METRICS}}


_PREPARED: list[dict] = []
_REAL_KEYS: frozenset = frozenset()


def _init(prepared: list[dict], real_keys: frozenset) -> None:
    global _PREPARED, _REAL_KEYS
    _PREPARED, _REAL_KEYS = prepared, real_keys


def _one(args: tuple[int, int]) -> dict:
    seed, i = args
    return _count(detect(_PREPARED, np.random.default_rng([seed, i])), _REAL_KEYS)


def permutation_null(prepared: list[dict], n: int, seed: int, workers: int = 1, real: pd.DataFrame | None = None) -> pd.DataFrame:
    """Counts from n shuffled seasons. Shuffle i uses default_rng([seed, i]), so a run can be repeated
    or extended and the worker count does not change the answer. `real`: the real-order candidates."""
    keys = frozenset() if real is None or real.empty else frozenset(zip(real["pitcher"].astype(int), real["pitch_type"]))
    jobs = [(seed, i) for i in range(n)]
    if workers > 1:
        with get_context("spawn").Pool(workers, initializer=_init, initargs=(prepared, keys)) as pool:
            rows = pool.map(_one, jobs, chunksize=1)
    else:
        _init(prepared, keys)
        rows = [_one(j) for j in jobs]
    return pd.DataFrame(rows)


def step_or_trend(pitches: pd.DataFrame, cands: pd.DataFrame) -> pd.DataFrame:
    """For each candidate: does a step at its date fit the game averages better than a straight line?

    Both are weighted by pitches per game. The step's date was chosen to fit, the line has no such
    choice, so a line that still fits as well is a candidate that reads like drift.
    """
    label_to_col = {label: col for col, (label, _) in shifts.METRICS.items()}
    p = shifts._prepare(pitches)
    groups = {k: g for k, g in p.groupby(["pitcher", "pitch_type"])}
    rows = []
    for r in cands.itertuples():
        col = label_to_col[r.metric]
        games = shifts._game_stats(groups[(r.pitcher, r.pitch_type)], col)
        y, w = (games["s"] / games["n"]).to_numpy(), games["n"].to_numpy(float)
        x = (games["game_date"] - games["game_date"].min()).dt.days.to_numpy(float)
        after = (games["game_date"] >= pd.Timestamp(r.split_date)).to_numpy()
        sse_step = sum(float(np.sum(w[m] * (y[m] - np.average(y[m], weights=w[m])) ** 2)) for m in (~after, after))
        X = np.column_stack([np.ones(len(x)), x])
        beta = np.linalg.lstsq(X * np.sqrt(w)[:, None], y * np.sqrt(w), rcond=None)[0]
        sse_line = float(np.sum(w * (y - X @ beta) ** 2))
        rows.append({"pitcher": r.pitcher, "pitch_type": r.pitch_type, "metric": r.metric,
                     "sse_step": sse_step, "sse_line": sse_line, "line_fits_as_well": bool(sse_line <= sse_step)})
    return pd.DataFrame(rows)


def run(season: int, n: int = 200, seed: int = 20261114, workers: int = 2, log=print) -> dict:
    from baseball.edge.run import COLUMNS
    from baseball.ingest.league import load_season
    from baseball.phases import phase

    data = phase(load_season(season, COLUMNS))
    log(f"{season}: {len(data):,} regular-season pitches; preparing")
    prepared = prepare(data)
    real_rows = detect(prepared)
    real = shifts.candidates(real_rows)
    observed = {k: v for k, v in _count(real_rows).items() if "real_list" not in k}
    log(f"observed: {observed}")
    shape = step_or_trend(data, real)
    log(f"step or trend: line fits as well as the step in {int(shape['line_fits_as_well'].sum())} of {len(shape)}")
    null = permutation_null(prepared, n, seed, workers, real)
    c = null["candidates"]
    mean = float(c.mean())
    result = {
        "source": f"python -m baseball.edge.shift_null {season} --n {n} --seed {seed}, on data/raw Statcast files (regular season).",
        "season": season,
        "method": "Each pitcher's games reordered at random (pitches stay in their game, all his pitch types move together), "
                  "then shifts.pitcher_shifts and shifts.candidates rerun unchanged.",
        "permutations": n,
        "seed": seed,
        "pitchers": len(prepared),
        "pitch_series_tested": int(len({(P["pitcher"], s["pitch_type"]) for P in prepared for s in P["series"]})),
        "pitch_metric_series_tested": int(sum(len(P["series"]) for P in prepared)),
        "observed": observed,
        "null": {
            "candidates_mean": mean,
            "candidates_sd": float(c.std(ddof=1)),
            "candidates_min": int(c.min()),
            "candidates_median": float(c.median()),
            "candidates_p95": float(c.quantile(0.95)),
            "candidates_max": int(c.max()),
            "mean_se": float(c.std(ddof=1) / np.sqrt(n)),
            "detector_rows_mean": float(null["detector_rows"].mean()),
            "pitchers_mean": float(null["pitchers"].mean()),
            "on_real_list_mean": float(null["candidates_on_real_list"].mean()),
            "off_real_list_mean": float(null["candidates_off_real_list"].mean()),
            "by_metric_mean": {m: float(null[f"candidates: {m}"].mean()) for m in shifts.CANDIDATE_METRICS},
            "shuffles_at_or_above_observed": int((c >= observed["candidates"]).sum()),
            "counts": c.astype(int).tolist(),
        },
        "false_share_of_candidates": mean / observed["candidates"] if observed["candidates"] else None,
        "false_per_series_tested": None,
        "step_or_trend": {
            "candidates": int(len(shape)),
            "line_fits_as_well_as_step": int(shape["line_fits_as_well"].sum()),
            "note": "Weighted fit to game averages. The step's date was chosen to fit; the line had no such choice.",
        },
    }
    result["false_per_series_tested"] = mean / result["pitch_series_tested"]
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"edge-shift-null-{season}.json"
    path.write_text(json.dumps(result, indent=1))
    log(f"null mean {mean:.2f} candidates per season vs {observed['candidates']} observed -> {path}")
    return result


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Permutation null for the in-season pitch-change detector")
    ap.add_argument("season", type=int)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20261114)
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    run(a.season, a.n, a.seed, a.workers)
