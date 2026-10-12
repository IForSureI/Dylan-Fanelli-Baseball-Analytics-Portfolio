"""Release tells: can you tell a pitch from the fastball using only how it leaves the hand?

A hitter sees the release before the ball's flight. If a pitcher releases his changeup from a
measurably different spot or arm angle than his fastball, that difference is information an
opponent can use (to sit on a pitch) and a pitching coach can fix.

Method, per pitcher and secondary pitch:
1. Reference = his fastball family (four-seamers and sinkers).
2. Within each game, subtract the mean release of that game's fastballs from every pitch.
   This removes park-to-park camera calibration and day-to-day drift, leaving only how a pitch's
   release differs from the fastballs thrown in the same game.
3. Release features: horizontal release (arm-side +), release height, extension, arm angle.
4. A logistic regression predicts "secondary vs fastball" from those features alone, scored with
   5-fold cross-validation grouped by game (never trained and tested on the same game).
5. tell_auc: 0.5 = no information in the release; 1.0 = the release gives the pitch away every time.
   tell_auc_se is the Hanley-McNeil standard error.

Grain of the output: one row per pitcher x season x secondary pitch type.

What this does not prove: that hitters actually see the difference. A 1-inch separation is
measurable by Hawk-Eye but may be invisible from the box. Use it to rank where to look on video.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

FASTBALLS = ("FF", "SI")
SECONDARIES = ("CH", "FS", "SL", "ST", "CU", "KC", "SV", "FC")
FEATURES = ["rel_x_arm_in", "rel_z_in", "ext_in", "arm_angle"]
FEATURE_LABELS = {"rel_x_arm_in": "horizontal release", "rel_z_in": "release height", "ext_in": "extension", "arm_angle": "arm angle"}

MIN_FASTBALLS_PER_GAME = 3
MIN_PITCHES = 75   # of the secondary, and of fastballs
MIN_GAMES = 5


def _prepare(p: pd.DataFrame) -> pd.DataFrame:
    """Release features in inches (degrees for arm angle), arm side positive."""
    p = p.dropna(subset=["pitch_type", "release_pos_x", "release_pos_z", "release_extension", "arm_angle"]).copy()
    arm = np.where(p["p_throws"].eq("R"), -1.0, 1.0)  # Statcast x is catcher's view; flip so arm side is +
    p["rel_x_arm_in"] = p["release_pos_x"] * 12 * arm
    p["rel_z_in"] = p["release_pos_z"] * 12
    p["ext_in"] = p["release_extension"] * 12
    return p


def _demean_by_game(p: pd.DataFrame) -> pd.DataFrame:
    """Subtract each game's fastball release mean. Drops games with too few fastballs."""
    fb = p[p["pitch_type"].isin(FASTBALLS)]
    counts = fb.groupby("game_pk").size()
    good = counts[counts >= MIN_FASTBALLS_PER_GAME].index
    ref = fb[fb["game_pk"].isin(good)].groupby("game_pk")[FEATURES].mean()
    p = p[p["game_pk"].isin(good)].copy()
    p[FEATURES] = p[FEATURES].to_numpy() - ref.loc[p["game_pk"], FEATURES].to_numpy()
    return p


def _hanley_mcneil_se(auc: float, n_pos: int, n_neg: int) -> float:
    q1 = auc / (2 - auc)
    q2 = 2 * auc**2 / (1 + auc)
    var = (auc * (1 - auc) + (n_pos - 1) * (q1 - auc**2) + (n_neg - 1) * (q2 - auc**2)) / (n_pos * n_neg)
    return math.sqrt(max(var, 0.0))


def pitcher_tells(pitches: pd.DataFrame) -> pd.DataFrame:
    """Release tells for one pitcher-season. Empty frame if he has no fastball reference."""
    p = _demean_by_game(_prepare(pitches))
    if p.empty:
        return pd.DataFrame()
    fb = p[p["pitch_type"].isin(FASTBALLS)]
    if len(fb) < MIN_PITCHES:
        return pd.DataFrame()

    rows = []
    for pt in SECONDARIES:
        sec = p[p["pitch_type"].eq(pt)]
        if len(sec) < MIN_PITCHES or sec["game_pk"].nunique() < MIN_GAMES:
            continue
        both = pd.concat([fb, sec])
        y = both["pitch_type"].eq(pt).to_numpy().astype(int)
        X = both[FEATURES].to_numpy()
        groups = both["game_pk"].to_numpy()
        n_splits = min(5, len(np.unique(groups)))
        oof = np.zeros(len(both))
        model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500))
        for train, test in GroupKFold(n_splits=n_splits).split(X, y, groups):
            if len(np.unique(y[train])) < 2:
                oof[test] = 0.5
                continue
            model.fit(X[train], y[train])
            oof[test] = model.predict_proba(X[test])[:, 1]
        auc = roc_auc_score(y, oof)

        # Plain-language separation: mean difference from the fastball, in units of his own scatter
        diff = sec[FEATURES].mean() - fb[FEATURES].mean()
        scatter = np.sqrt((sec[FEATURES].var() + fb[FEATURES].var()) / 2)
        z = (diff / scatter).abs()
        top = z.idxmax()
        rows.append(
            {
                "pitch_type": pt,
                "pitch_name": sec["pitch_name"].iloc[0] if "pitch_name" in sec else pt,
                "n_fastballs": len(fb),
                "n_pitch": len(sec),
                "games": sec["game_pk"].nunique(),
                "tell_auc": auc,
                "tell_auc_se": _hanley_mcneil_se(auc, int(y.sum()), int(len(y) - y.sum())),
                "rel_x_arm_diff_in": diff["rel_x_arm_in"],
                "rel_z_diff_in": diff["rel_z_in"],
                "ext_diff_in": diff["ext_in"],
                "arm_angle_diff_deg": diff["arm_angle"],
                "top_tell": FEATURE_LABELS[top],
                "top_tell_sd": z[top],
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    meta = pitches.iloc[0]
    out.insert(0, "pitcher", int(meta["pitcher"]))
    out.insert(1, "player_name", meta["player_name"])
    out.insert(2, "p_throws", meta["p_throws"])
    out.insert(3, "season", int(meta["game_year"]))
    return out.sort_values("tell_auc", ascending=False).reset_index(drop=True)


def league_tells(pitches: pd.DataFrame) -> pd.DataFrame:
    """Release tells for every pitcher in a season of league data."""
    parts = []
    for _, g in pitches.groupby("pitcher", sort=False):
        t = pitcher_tells(g)
        if not t.empty:
            parts.append(t)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
