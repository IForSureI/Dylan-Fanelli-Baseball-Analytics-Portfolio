"""Stuff vs results: how many whiffs a pitch should get from its physics alone, and where results disagree.

The model sees only what the ball does and where it comes from: velocity, movement, spin, release
height and side, extension, arm angle, and how the pitch differs from the pitcher's own primary
fastball, plus whether the hitter is same-handed. It does not see location, count or sequence. So:

- x_whiff  = whiff rate the pitch's physics earn against an average hitter
- gap      = actual whiff% - x_whiff. Positive: results beat the stuff (location, sequencing, deception,
             or luck). Negative: the stuff is better than the results (location, predictability,
             tipping, or bad luck).

Honesty rules:
- Cross-fitted by pitcher: every pitcher's x_whiff comes from a model that never saw him.
- `validate()` checks the model is worth listening to: does last season's x_whiff predict this
  season's actual whiff% better than last season's actual whiff% does?

Grain: model rows are swings; output rows are pitcher x season x pitch type.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold

from baseball.evaluation.arsenal import SWINGS, WHIFFS
from baseball.stats import wilson

FASTBALL_TYPES = ("FF", "SI", "FC")
FEATURES = [
    "velo", "ivb_in", "hb_arm_in", "spin", "ext_ft", "rel_z_ft", "rel_x_arm_ft", "arm_angle",
    "d_velo", "d_ivb", "d_hb", "same_hand",
]
MIN_SWINGS = 50


def prepare(pitches: pd.DataFrame) -> pd.DataFrame:
    """Swing rows with model features. Expects one season of regular-season pitches (any number of pitchers)."""
    p = pitches.dropna(subset=["pitch_type", "release_speed", "pfx_x", "pfx_z", "release_spin_rate",
                               "release_extension", "release_pos_z", "release_pos_x", "arm_angle"]).copy()
    arm = np.where(p["p_throws"].eq("R"), -1.0, 1.0)
    p["velo"] = p["release_speed"]
    p["ivb_in"] = p["pfx_z"] * 12
    p["hb_arm_in"] = p["pfx_x"] * 12 * arm
    p["spin"] = p["release_spin_rate"]
    p["ext_ft"] = p["release_extension"]
    p["rel_z_ft"] = p["release_pos_z"]
    p["rel_x_arm_ft"] = p["release_pos_x"] * arm
    p["same_hand"] = p["p_throws"].eq(p["stand"]).astype(int)

    # Each pitcher's primary fastball: his most-thrown of FF/SI/FC (his most-thrown pitch if none)
    counts = p.groupby(["pitcher", "pitch_type"]).size().rename("n").reset_index()
    fb = counts[counts["pitch_type"].isin(FASTBALL_TYPES)]
    primary = (fb if len(fb) else counts).sort_values("n").groupby("pitcher").tail(1).set_index("pitcher")["pitch_type"]
    missing = counts.loc[~counts["pitcher"].isin(primary.index)].sort_values("n").groupby("pitcher").tail(1)
    primary = pd.concat([primary, missing.set_index("pitcher")["pitch_type"]])
    p["primary_fb"] = p["pitcher"].map(primary)
    ref = p[p["pitch_type"].eq(p["primary_fb"])].groupby("pitcher")[["velo", "ivb_in", "hb_arm_in"]].mean()
    p["d_velo"] = p["velo"] - p["pitcher"].map(ref["velo"])
    p["d_ivb"] = p["ivb_in"] - p["pitcher"].map(ref["ivb_in"])
    p["d_hb"] = p["hb_arm_in"] - p["pitcher"].map(ref["hb_arm_in"])

    swings = p[p["description"].isin(SWINGS)].copy()
    swings["whiff"] = swings["description"].isin(WHIFFS).astype(int)
    return swings


def fit_crossfit(swings: pd.DataFrame, n_splits: int = 5, seed: int = 11) -> tuple[pd.Series, dict]:
    """Out-of-fold whiff probability for every swing, folds grouped by pitcher. Returns (x_whiff, diagnostics)."""
    X, y, groups = swings[FEATURES].to_numpy(), swings["whiff"].to_numpy(), swings["pitcher"].to_numpy()
    oof = np.zeros(len(swings))
    for train, test in GroupKFold(n_splits=n_splits).split(X, y, groups):
        model = HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.06, max_leaf_nodes=31, min_samples_leaf=200,
            l2_regularization=1.0, random_state=seed,
        )
        model.fit(X[train], y[train])
        oof[test] = model.predict_proba(X[test])[:, 1]
    base = np.full_like(oof, y.mean())
    diag = {
        "swings": int(len(y)),
        "auc": float(roc_auc_score(y, oof)),
        "log_loss": float(log_loss(y, oof)),
        "log_loss_baseline": float(log_loss(y, base)),
        "calibration": (
            pd.DataFrame({"pred": oof, "actual": y})
            .assign(decile=lambda d: pd.qcut(d["pred"], 10, labels=False, duplicates="drop"))
            .groupby("decile")[["pred", "actual"]].mean().round(3).to_dict("records")
        ),
    }
    return pd.Series(oof, index=swings.index, name="x_whiff"), diag


def pitch_table(swings: pd.DataFrame, x_whiff: pd.Series, min_swings: int = MIN_SWINGS) -> pd.DataFrame:
    """Actual vs expected whiff% per pitcher x pitch type."""
    s = swings.assign(x_whiff=x_whiff)
    out = (
        s.groupby(["pitcher", "player_name", "p_throws", "game_year", "pitch_type"])
        .agg(pitch_name=("pitch_name", "first"), swings=("whiff", "size"), whiffs=("whiff", "sum"),
             x_whiff=("x_whiff", "mean"), velo=("velo", "mean"), ivb_in=("ivb_in", "mean"),
             hb_arm_in=("hb_arm_in", "mean"), d_velo=("d_velo", "mean"))
        .reset_index()
        .rename(columns={"game_year": "season"})
    )
    out = out[out["swings"] >= min_swings].copy()
    out["whiff_pct"] = 100 * out["whiffs"] / out["swings"]
    out["x_whiff_pct"] = 100 * out["x_whiff"]
    out["gap"] = out["whiff_pct"] - out["x_whiff_pct"]
    ci = [wilson(int(k), int(n)) for k, n in zip(out["whiffs"], out["swings"])]
    out["whiff_lo"] = [100 * c[0] for c in ci]
    out["whiff_hi"] = [100 * c[1] for c in ci]
    # Is the gap bigger than chance? x_whiff sits outside the 95% interval of the actual rate
    out["gap_clear"] = (out["x_whiff_pct"] < out["whiff_lo"]) | (out["x_whiff_pct"] > out["whiff_hi"])
    return out.drop(columns=["x_whiff"]).sort_values("gap").reset_index(drop=True)


def validate(prev: pd.DataFrame, curr: pd.DataFrame, min_swings: int = 60) -> dict:
    """Does last season's x_whiff predict this season's actual whiff% better than last season's actual?

    prev, curr: pitch_table() outputs for consecutive seasons. Matched on pitcher x pitch type.
    Returns correlations, the best blend (least squares), and the matched frame.
    """
    keys = ["pitcher", "pitch_type"]
    m = prev[prev["swings"] >= min_swings].merge(curr[curr["swings"] >= min_swings], on=keys, suffixes=("_prev", "_curr"))
    y = m["whiff_pct_curr"].to_numpy()
    a, x = m["whiff_pct_prev"].to_numpy(), m["x_whiff_pct_prev"].to_numpy()
    w = np.sqrt(np.minimum(m["swings_prev"], m["swings_curr"]).to_numpy())  # weight by sample
    A = np.column_stack([np.ones_like(a), a, x])
    coef, *_ = np.linalg.lstsq(A * w[:, None], y * w, rcond=None)
    pred = A @ coef

    def r(u, v):
        return float(np.corrcoef(u, v)[0, 1])

    def rmse(u):
        return float(np.sqrt(np.average((y - u) ** 2, weights=w)))

    return {
        "matched_pitches": int(len(m)),
        "r_actual_prev": r(a, y),
        "r_xwhiff_prev": r(x, y),
        "r_blend": r(pred, y),
        "rmse_actual_prev": rmse(a),
        "rmse_xwhiff_prev": rmse(x),
        "rmse_blend": rmse(pred),
        "blend": {"intercept": float(coef[0]), "actual": float(coef[1]), "x_whiff": float(coef[2])},
        "matched": m,
    }


def project(curr: pd.DataFrame, blend: dict) -> pd.DataFrame:
    """Next-season whiff% projection from this season's actual and expected, using validated blend weights."""
    out = curr.copy()
    out["proj_whiff_pct"] = blend["intercept"] + blend["actual"] * out["whiff_pct"] + blend["x_whiff"] * out["x_whiff_pct"]
    out["proj_change"] = out["proj_whiff_pct"] - out["whiff_pct"]
    return out


def persistent_gaps(tables: dict[int, pd.DataFrame], min_swings: int = MIN_SWINGS) -> pd.DataFrame:
    """Pitches that beat (or trail) their stuff season after season.

    The gap between actual and expected whiff% is a stable trait (it carries over from one season to
    the next), so a pitch that beats its physics two or three years running is showing deception,
    command or sequencing, not luck. Grain: pitcher x pitch type, across every season given.
    """
    rows = []
    for season, t in tables.items():
        t = t[t["swings"] >= min_swings]
        rows.append(t[["pitcher", "player_name", "pitch_type", "pitch_name", "swings", "whiff_pct", "x_whiff_pct", "gap"]].assign(season=season))
    allr = pd.concat(rows, ignore_index=True)
    g = allr.groupby(["pitcher", "pitch_type"])
    out = g.agg(player_name=("player_name", "last"), pitch_name=("pitch_name", "last"), seasons=("season", "nunique"),
                swings=("swings", "sum"), min_gap=("gap", "min"), max_gap=("gap", "max")).reset_index()
    out["mean_gap"] = g.apply(lambda d: np.average(d["gap"], weights=d["swings"]), include_groups=False).to_numpy()
    out["same_sign"] = (np.sign(out["min_gap"]) == np.sign(out["max_gap"]))
    by_season = allr.pivot_table(index=["pitcher", "pitch_type"], columns="season", values="gap").add_prefix("gap_")
    out = out.merge(by_season.reset_index(), on=["pitcher", "pitch_type"], how="left")
    return out.sort_values("mean_gap", ascending=False).reset_index(drop=True)
