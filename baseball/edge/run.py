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
from baseball.stats import clustered_wls

OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "edge"

COLUMNS = [
    "game_pk", "game_date", "game_year", "game_type", "at_bat_number", "pitch_number",
    "pitcher", "player_name", "p_throws", "stand", "pitch_type", "pitch_name", "description", "type",
    "release_speed", "release_spin_rate", "release_extension", "release_pos_x", "release_pos_z", "arm_angle",
    "pfx_x", "pfx_z", "estimated_woba_using_speedangle", "launch_speed", "zone", "balls", "strikes",
]

PITCH_GROUP = {"CH": "offspeed", "FS": "offspeed", "SL": "breaking", "ST": "breaking", "CU": "breaking",
               "KC": "breaking", "SV": "breaking", "FC": "cutter"}


def pitch_context(p: pd.DataFrame) -> pd.DataFrame:
    """What the stuff model can't see, per pitcher x pitch type: how the pitch is used.

    - chase_share  : share of its swings that came on pitches outside the zone (location)
    - two_k_share  : share of its swings that came with two strikes (count)
    - zone_pct     : share of the pitch thrown in the zone
    - reliever     : the pitcher averaged under 40 pitches per appearance (role)
    """
    from baseball.evaluation.arsenal import SWINGS

    p = p.dropna(subset=["pitch_type"])
    sw = p[p["description"].isin(SWINGS)].assign(out_zone=lambda d: d["zone"] > 9, two_k=lambda d: d["strikes"] == 2)
    ctx = sw.groupby(["pitcher", "pitch_type"]).agg(chase_share=("out_zone", "mean"), two_k_share=("two_k", "mean"))
    ctx["zone_pct"] = p.assign(inz=p["zone"] <= 9).groupby(["pitcher", "pitch_type"])["inz"].mean()
    per_game = p.groupby("pitcher").size() / p.groupby("pitcher")["game_pk"].nunique()
    ctx = ctx.reset_index()
    ctx["reliever"] = ctx["pitcher"].map(per_game < 40).astype(float)
    return ctx


def _tell_frame(tells_df: pd.DataFrame, stuff_df: pd.DataFrame, ctx: pd.DataFrame | None = None) -> pd.DataFrame:
    m = tells_df.merge(stuff_df, on=["pitcher", "pitch_type"], suffixes=("", "_s"))
    m = m[m["pitch_type"].isin(PITCH_GROUP)].copy()
    m["group"] = m["pitch_type"].map(PITCH_GROUP)
    if ctx is not None:
        m = m.merge(ctx, on=["pitcher", "pitch_type"], how="left").dropna(subset=["chase_share", "two_k_share", "reliever"])
    return m


def tell_cost(tells_df: pd.DataFrame, stuff_df: pd.DataFrame) -> dict:
    """One season: do pitches with stronger release tells get fewer whiffs than their stuff predicts?

    Regress (actual - expected whiff%) on tell AUC with pitch-group controls, weighted by swings, standard
    errors clustered by pitcher. Slope is in whiff-percentage points per 0.1 of tell AUC.
    """
    m = _tell_frame(tells_df, stuff_df)
    if len(m) < 30:
        return {"pitches": int(len(m))}
    dummies = pd.get_dummies(m["group"], drop_first=True, dtype=float)
    X = np.column_stack([np.ones(len(m)), m["tell_auc"].to_numpy() * 10, dummies.to_numpy()])
    beta, se = clustered_wls(m["gap"], X, m["swings"].astype(float), m["pitcher"])
    return {
        "pitches": int(len(m)),
        "slope_per_0.1_auc": float(beta[1]),
        "slope_se": float(se[1]),
        "t": float(beta[1] / se[1]) if se[1] else float("nan"),
        "median_tell_auc": float(m["tell_auc"].median()),
    }


def tell_cost_pooled(tells_by: dict, stuff_by: dict, ctx_by: dict) -> dict:
    """All seasons in one regression, with season and pitch-group effects and SEs clustered by pitcher
    (the same pitchers appear every season, so seasons can't be pooled as independent samples).
    Reported raw and with usage controls (location, count, role) the stuff model can't see."""
    frames = [_tell_frame(tells_by[s], stuff_by[s], ctx_by[s]).assign(season=s) for s in tells_by]
    m = pd.concat(frames, ignore_index=True)
    fx = pd.get_dummies(m[["group", "season"]].astype(str), drop_first=True, dtype=float).to_numpy()
    w, y, cl = m["swings"].astype(float), m["gap"], m["pitcher"]
    out = {"rows": int(len(m)), "pitchers": int(m["pitcher"].nunique())}
    for label, extra in [("raw", []), ("controlled", ["chase_share", "two_k_share", "reliever"])]:
        X = np.column_stack([np.ones(len(m)), m["tell_auc"].to_numpy() * 10, fx] + [m[c].to_numpy() for c in extra])
        b, se = clustered_wls(y, X, w, cl)
        out[label] = {"slope": float(b[1]), "se": float(se[1]), "lo": float(b[1] - 1.96 * se[1]), "hi": float(b[1] + 1.96 * se[1])}
    out["by_group"] = {}
    for grp, g in m.groupby("group"):
        fxg = pd.get_dummies(g[["season"]].astype(str), drop_first=True, dtype=float).to_numpy()
        X = np.column_stack([np.ones(len(g)), g["tell_auc"].to_numpy() * 10, fxg])
        b, se = clustered_wls(g["gap"], X, g["swings"].astype(float), g["pitcher"])
        out["by_group"][grp] = {"rows": int(len(g)), "slope": float(b[1]), "se": float(se[1])}
    return out


def gap_persistence_controlled(stuff_by: dict, ctx_by: dict, seasons: list[int]) -> dict:
    """Year-to-year correlation of the stuff gap after removing what usage explains within each season
    (pitch type, chase share, two-strike share, zone%, role). What's left is less likely to be usage."""
    resid = {}
    for s_ in seasons:
        m = stuff_by[s_].merge(ctx_by[s_], on=["pitcher", "pitch_type"]).dropna(subset=["chase_share", "two_k_share", "zone_pct"])
        pt = pd.get_dummies(m["pitch_type"], drop_first=True, dtype=float).to_numpy()
        X = np.column_stack([np.ones(len(m)), pt, m[["chase_share", "two_k_share", "zone_pct", "reliever"]].to_numpy()])
        w = m["swings"].to_numpy(float)
        beta = np.linalg.pinv(X.T @ (X * w[:, None])) @ (X.T @ (w * m["gap"].to_numpy()))
        resid[s_] = m.assign(resid=m["gap"].to_numpy() - X @ beta)[["pitcher", "pitch_type", "swings", "resid"]]
    out = {}
    for a, b in zip(seasons, seasons[1:]):
        j = resid[a].merge(resid[b], on=["pitcher", "pitch_type"], suffixes=("_a", "_b"))
        j = j[(j["swings_a"] >= 60) & (j["swings_b"] >= 60)]
        out[f"{a}->{b}"] = {"pitches": int(len(j)), "r_resid": float(np.corrcoef(j["resid_a"], j["resid_b"])[0, 1])}
    return out


def _available(season: int) -> bool:
    try:
        load_season(season, ["game_pk"])
        return True
    except FileNotFoundError:
        return False


def run(season: int, log=print) -> dict:
    """Engine run centered on `season`, using up to two prior seasons for validation and replication.

    - Detectors (tells, shifts, stuff, baselines) report on `season`.
    - The stuff model is validated on every consecutive pair available (e.g. 2024->2025 and 2025->2026).
    - The tell-cost test runs in every season available; a finding must hold in all of them.
    """
    seasons = [s for s in (season - 2, season - 1, season) if _available(s)]
    if season not in seasons or season - 1 not in seasons:
        raise FileNotFoundError(f"Need league data for {season - 1} and {season}. Run: uv run bb pull-league <season>")
    out_dir = OUT_DIR / str(season)
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    def step(msg):
        log(f"[{time.time() - t0:6.0f}s] {msg}")

    data, tell_tables, stuff_tables, diags, ctx = {}, {}, {}, {}, {}
    for s_ in seasons:
        step(f"{s_}: loading")
        data[s_] = phase(load_season(s_, COLUMNS))
        step(f"{s_}: {len(data[s_]):,} regular-season pitches; release tells")
        tell_tables[s_] = tells.league_tells(data[s_])
        ctx[s_] = pitch_context(data[s_])
        step(f"{s_}: stuff model (cross-fitted by pitcher)")
        sw = stuff.prepare(data[s_])
        x, diags[s_] = stuff.fit_crossfit(sw)
        stuff_tables[s_] = stuff.pitch_table(sw, x)
        if s_ == season:
            swings_curr = sw.assign(x_whiff=x)
        tell_tables[s_].to_parquet(out_dir / f"tells_{s_}.parquet")
        stuff_tables[s_].to_parquet(out_dir / f"stuff_{s_}.parquet")

    step(f"{season}: hidden in-season changes")
    sh = shifts.score_shifts(shifts.league_shifts(data[season]), swings_curr)
    sh.to_parquet(out_dir / "shifts.parquet")

    step("Pitches that beat (or trail) their stuff across seasons")
    pg = stuff.persistent_gaps(stuff_tables)
    pg.to_parquet(out_dir / "persistent_gaps.parquet")
    gap_persistence = {}
    for a_, b_ in zip(seasons, seasons[1:]):
        m = stuff_tables[a_].merge(stuff_tables[b_], on=["pitcher", "pitch_type"], suffixes=("_a", "_b"))
        m = m[(m["swings_a"] >= 60) & (m["swings_b"] >= 60)]
        gap_persistence[f"{a_}->{b_}"] = {"pitches": int(len(m)), "r_gap": float(np.corrcoef(m["gap_a"], m["gap_b"])[0, 1])}

    step("Validating the stuff model year to year")
    validations = {}
    for a, b in zip(seasons, seasons[1:]):
        v = stuff.validate(stuff_tables[a], stuff_tables[b])
        validations[f"{a}->{b}"] = {k: val for k, val in v.items() if k != "matched"}
    blend = validations[f"{season - 1}->{season}"]["blend"]
    two_year = None
    if season - 2 in seasons:
        two_year = stuff.validate_two_year(stuff_tables[season - 2], stuff_tables[season - 1], stuff_tables[season])
    if two_year and two_year["loo_rmse"]["two_seasons_plus_expected"] < two_year["loo_rmse"]["last_plus_expected"]:
        proj = stuff.project_two_year(stuff_tables[season - 1], stuff_tables[season], two_year["weights"], blend)
    else:
        proj = stuff.project(stuff_tables[season], blend).assign(proj_basis="one season")
    proj.to_parquet(out_dir / "projection.parquet")

    step(f"{season}: portable stuff model for TrackMan / Rapsodo data")
    portable = stuff.build_portable(data[season], season)
    stuff.save_portable(portable, out_dir / "stuff_portable.joblib")

    step("League baselines")
    bl = baselines.changes(data[season - 1], data[season])
    bl.to_parquet(out_dir / "baselines.parquet")

    step("Do release tells cost whiffs? (every season)")
    cost = {str(s_): tell_cost(tell_tables[s_], stuff_tables[s_]) for s_ in seasons}
    cost_pooled = tell_cost_pooled(tell_tables, stuff_tables, ctx)
    gap_ctrl = gap_persistence_controlled(stuff_tables, ctx, seasons)

    summary = {
        "season": season,
        "seasons": seasons,
        "pitches": {str(s_): int(len(data[s_])) for s_ in seasons},
        "stuff_model": {str(s_): diags[s_] for s_ in seasons},
        "validation": validations,
        "projection_blend": blend,
        "projection_two_year": two_year,
        "tell_cost": cost,
        "tell_cost_pooled": cost_pooled,
        "gap_persistence": gap_persistence,
        "gap_persistence_controlled": gap_ctrl,
        "portable_model": {k: v for k, v in portable["diagnostics"].items() if k != "calibration"},
        "counts": {"tells": int(len(tell_tables[season])), "shifts": int(len(sh)), "stuff_pitches": int(len(stuff_tables[season]))},
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    step(f"Done. Outputs in {out_dir}")
    return summary
