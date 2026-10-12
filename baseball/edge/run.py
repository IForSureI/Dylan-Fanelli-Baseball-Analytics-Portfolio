"""Run the edge engine on two consecutive seasons of league data and save every output.

  uv run bb edge 2025            (uses 2024 as the prior season)

Outputs in data/edge/<season>/:
  tells.parquet, tells_prev.parquet     release tells, both seasons
  shifts.parquet                        hidden in-season changes, current season
  stuff.parquet, stuff_prev.parquet     actual vs expected whiff per pitch
  projection.parquet                    next-season whiff projection per pitch
  baselines.parquet                     within-pitcher season-over-season changes vs the league
  summary.json                          model diagnostics, validation, and the tell-cost test
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from baseball.edge import baselines, shifts, stuff, tells
from baseball.ingest.league import load_season
from baseball.phases import phase

OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "edge"

COLUMNS = [
    "game_pk", "game_date", "game_year", "game_type", "at_bat_number", "pitch_number",
    "pitcher", "player_name", "p_throws", "stand", "pitch_type", "pitch_name", "description", "type",
    "release_speed", "release_spin_rate", "release_extension", "release_pos_x", "release_pos_z", "arm_angle",
    "pfx_x", "pfx_z", "estimated_woba_using_speedangle", "launch_speed", "zone", "balls", "strikes",
]

PITCH_GROUP = {"CH": "offspeed", "FS": "offspeed", "SL": "breaking", "ST": "breaking", "CU": "breaking",
               "KC": "breaking", "SV": "breaking", "FC": "cutter"}


def _wls(y: np.ndarray, X: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Weighted least squares coefficients and standard errors."""
    W = np.sqrt(w)[:, None]
    Xw, yw = X * W, y * W[:, 0]
    beta, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
    resid = yw - Xw @ beta
    dof = max(len(y) - X.shape[1], 1)
    sigma2 = float(resid @ resid) / dof
    cov = sigma2 * np.linalg.pinv(Xw.T @ Xw)
    return beta, np.sqrt(np.diag(cov))


def tell_cost(tells_df: pd.DataFrame, stuff_df: pd.DataFrame) -> dict:
    """Do pitches with stronger release tells get fewer whiffs than their stuff predicts?

    Regress (actual - expected whiff%) on tell AUC, with pitch-group controls, weighted by swings.
    Slope is in whiff-percentage points per 0.1 of tell AUC.
    """
    m = tells_df.merge(stuff_df, on=["pitcher", "pitch_type"], suffixes=("", "_s"))
    m = m[m["pitch_type"].isin(PITCH_GROUP)].copy()
    if len(m) < 30:
        return {"pitches": int(len(m))}
    m["group"] = m["pitch_type"].map(PITCH_GROUP)
    dummies = pd.get_dummies(m["group"], drop_first=True, dtype=float)
    X = np.column_stack([np.ones(len(m)), m["tell_auc"].to_numpy() * 10, dummies.to_numpy()])
    beta, se = _wls(m["gap"].to_numpy(), X, m["swings"].to_numpy().astype(float))
    out = {
        "pitches": int(len(m)),
        "slope_per_0.1_auc": float(beta[1]),
        "slope_se": float(se[1]),
        "t": float(beta[1] / se[1]) if se[1] else float("nan"),
        "median_tell_auc": float(m["tell_auc"].median()),
        "by_group": {},
    }
    for grp, g in m.groupby("group"):
        if len(g) >= 30:
            b, s = _wls(g["gap"].to_numpy(), np.column_stack([np.ones(len(g)), g["tell_auc"].to_numpy() * 10]),
                        g["swings"].to_numpy().astype(float))
            out["by_group"][grp] = {"pitches": int(len(g)), "slope": float(b[1]), "se": float(s[1])}
    return out


def run(season: int, log=print) -> dict:
    prev_season = season - 1
    out_dir = OUT_DIR / str(season)
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    def step(msg):
        log(f"[{time.time() - t0:6.0f}s] {msg}")

    step(f"Loading {prev_season} and {season} league data")
    prev = phase(load_season(prev_season, COLUMNS))
    curr = phase(load_season(season, COLUMNS))
    step(f"  {len(prev):,} and {len(curr):,} regular-season pitches")

    step("Release tells")
    t_prev, t_curr = tells.league_tells(prev), tells.league_tells(curr)
    t_prev.to_parquet(out_dir / "tells_prev.parquet"); t_curr.to_parquet(out_dir / "tells.parquet")

    step("Hidden in-season changes")
    sh = shifts.league_shifts(curr)
    sh.to_parquet(out_dir / "shifts.parquet")

    step("Stuff model (cross-fitted by pitcher), both seasons")
    sw_prev, sw_curr = stuff.prepare(prev), stuff.prepare(curr)
    x_prev, diag_prev = stuff.fit_crossfit(sw_prev)
    x_curr, diag_curr = stuff.fit_crossfit(sw_curr)
    st_prev, st_curr = stuff.pitch_table(sw_prev, x_prev), stuff.pitch_table(sw_curr, x_curr)
    st_prev.to_parquet(out_dir / "stuff_prev.parquet"); st_curr.to_parquet(out_dir / "stuff.parquet")
    val = stuff.validate(st_prev, st_curr)
    proj = stuff.project(st_curr, val["blend"])
    proj.to_parquet(out_dir / "projection.parquet")

    step("League baselines")
    bl = baselines.changes(prev, curr)
    bl.to_parquet(out_dir / "baselines.parquet")

    step("Do release tells cost whiffs? (both seasons, must replicate)")
    cost = {str(prev_season): tell_cost(t_prev, st_prev), str(season): tell_cost(t_curr, st_curr)}

    summary = {
        "season": season,
        "prev_season": prev_season,
        "pitches": {str(prev_season): int(len(prev)), str(season): int(len(curr))},
        "stuff_model": {str(prev_season): diag_prev, str(season): diag_curr},
        "validation": {k: v for k, v in val.items() if k != "matched"},
        "tell_cost": cost,
        "counts": {"tells": int(len(t_curr)), "shifts": int(len(sh)), "stuff_pitches": int(len(st_curr))},
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    step(f"Done. Outputs in {out_dir}")
    return summary
