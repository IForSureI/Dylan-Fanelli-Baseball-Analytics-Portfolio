"""The Python side of the R check: run the repo's own Reliability Atlas code on the same swings.

Reads the DuckDB file that reports/r/pull_swings.R builds, runs baseball/evaluation/reliability.py
(build_family -> _job -> run_splits -> summarize) for hitter whiff per swing on that season only,
and writes two things for reports/r/check_against_python.R:

  reports/r/output/python_whiff.json   M with its 95% interval, tau, sigma2, the r(n) curve, league mean,
                                        and regress() on a fixed set of examples
  data/r/shared_splits_<season>.csv     the first K random game splits, so R can score the very same
                                        splits and must agree to rounding error (not committed)

Usage (repo root):  uv run python reports/r/python_reference.py 2026 data/r/swings_2026.duckdb
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from baseball.evaluation import reliability as R  # noqa: E402
from baseball.evaluation.arsenal import SWINGS, WHIFFS  # noqa: E402

SEASON = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
DB = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / f"data/r/swings_{SEASON}.duckdb"
REPS, BOOT, SEED = 200, 100, 2026          # the atlas's settings: 200 splits, 100 bootstrap draws
SHARED_K, SHARED_SEED = 20, 7              # splits handed to R for the exact check
OUT = ROOT / "reports/r/output"
SHARED = ROOT / f"data/r/shared_splits_{SEASON}.csv"

# Example hitters for regress(): (observed whiff rate, swings). The first is the atlas's worked example.
EXAMPLES = [(0.400, 50), (0.150, 50), (0.300, 100), (0.350, 200), (0.200, 400), (0.250, 10)]


def load_swings() -> pd.DataFrame:
    con = duckdb.connect(str(DB), read_only=True)
    d = con.execute(f"SELECT * FROM swings WHERE game_year = {SEASON} AND game_type = 'R'").df()
    con.close()
    d = d[d["description"].isin(SWINGS)].copy()        # the repo's swing list (drops bunt_foul_tip)
    d["season"] = d["game_year"].astype(int)
    d["swing"] = True
    d["whiff"] = d["description"].isin(WHIFFS)
    return d.reset_index(drop=True)


def main() -> None:
    d = load_swings()
    metric = R.METRICS[("hitter", "whiff")]
    league_mean = float(d["whiff"].mean())

    # 1. The shared splits (before _job frees the events frame)
    fam = R.build_family(d, "hitter")
    first = np.flatnonzero(np.r_[True, fam.event_row[1:] != fam.event_row[:-1]])
    row_game = fam.events["game_pk"].to_numpy()[first]
    row_batter = fam.entity_player[fam.row_entity]
    a = R.metric_arrays(fam, metric)
    grid = [n for n in R.GRID if (np.bincount(fam.row_entity, weights=a.c, minlength=fam.n_entity) >= 2 * n).sum() >= R.MIN_ENTITIES]
    rng = np.random.default_rng(SHARED_SEED)
    W1 = np.ones((1, fam.n_entity))
    sums = 0.0
    rows = []
    for k in range(SHARED_K):
        sp = R.random_split(fam, rng)
        sums = sums + R.within_sums(R.half_means(a, sp, fam.n_entity, grid), np.zeros(fam.n_entity, np.int64), 1, W1)
        rows.append(pd.DataFrame({"split": k + 1, "batter": row_batter[sp.order], "game_pk": row_game[sp.order],
                                  "half": sp.seg % 2, "pos": np.arange(len(sp.order))}))
    SHARED.parent.mkdir(parents=True, exist_ok=True)
    pd.concat(rows).to_csv(SHARED, index=False)
    n_, c_, v_ = R.centered(sums[0, :, 0, :])
    shared = [{"n": int(g), "players": float(n_[i] / SHARED_K), "r": float(c_[i] / v_[i])} for i, g in enumerate(grid)]

    # 2. The full run, exactly as the atlas does it (one season, no year-to-year pairs)
    fam = R.build_family(d, "hitter")
    job = R._job(fam, [metric], [SEASON], boot=BOOT, y2y=False)
    R.run_splits([job], REPS, seed=SEED, log=None)
    curve, params = R.summarize(job)
    p = params.iloc[0]

    # 3. regress() on the examples: with the shipped atlas constants, and with this season's fitted ones
    shipped = R.load_params().loc["hitter/whiff"]
    obs = np.array([x for x, _ in EXAMPLES]); n = np.array([y for _, y in EXAMPLES])
    reg_shipped = R.regress("hitter/whiff", obs, n, 0.251)                       # atlas: league 25.1%
    reg_fitted = R.regress("hitter/whiff", obs, n, league_mean, M=float(p["M"]), tau=float(p["tau"]), params=None)

    out = {
        "season": SEASON, "reps": REPS, "boot": BOOT, "seed": SEED,
        "swings": int(len(d)), "batters": int(d["batter"].nunique()), "games": int(d["game_pk"].nunique()),
        "league_mean": league_mean, "per_game": float(p["per_game"]),
        "M": float(p["M"]), "M_lo": float(p["M_lo"]), "M_hi": float(p["M_hi"]),
        "tau": float(p["tau"]), "sigma2": float(p["sigma2"]), "n_fit_min": int(p["n_fit_min"]),
        "curve": curve[["n", "r", "r_lo", "r_hi", "entities", "r_model", "in_fit"]].to_dict("records"),
        "shared_splits": {"k": SHARED_K, "seed": SHARED_SEED, "grid": grid, "curve": shared},
        "examples": [{"observed": float(o), "n": int(m)} for o, m in EXAMPLES],
        "regress_shipped": {"M": float(shipped["M"]), "tau": float(shipped["tau"]), "league_mean": 0.251,
                             **reg_shipped.to_dict("list")},
        "regress_fitted": {"league_mean": league_mean, **reg_fitted.to_dict("list")},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "python_whiff.json").write_text(json.dumps(out, indent=1, default=float))
    print(f"Python: M = {p['M']:.2f} ({p['M_lo']:.2f}-{p['M_hi']:.2f}), tau = {p['tau']:.4f}, "
          f"league {league_mean:.4f}, {len(d):,} swings, {d['batter'].nunique()} batters")


if __name__ == "__main__":
    main()
