"""Is it the pitcher or the cameras? League-wide season-over-season baselines.

When a pitcher's spin, extension or velocity changes from one season to the next, the first
question is whether everyone's did. This compares each returning pitcher's change on each pitch
type with the same change for every other returning pitcher.

- league_change(): for pitchers who threw the pitch type in both seasons (min pitches each),
  the distribution of their within-pitcher changes. The median is the league-wide shift.
- percentile(): where one pitcher's change sits in that distribution, raw and after removing
  the league median ("excess change").

Grain of the output: one row per pitcher x pitch type x metric.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

METRICS = {
    "velo": "release_speed",
    "spin": "release_spin_rate",
    "ext_ft": "release_extension",
    "arm_angle": "arm_angle",
}
MIN_PITCHES = 100


def _pitch_means(p: pd.DataFrame) -> pd.DataFrame:
    p = p.dropna(subset=["pitch_type"]).copy()
    for name, col in METRICS.items():
        p[name] = p[col]
    p["spin_per_mph"] = p["release_spin_rate"] / p["release_speed"]
    g = p.groupby(["pitcher", "player_name", "pitch_type"])
    out = g[list(METRICS) + ["spin_per_mph"]].mean()
    out["n"] = g.size()
    return out[out["n"] >= MIN_PITCHES].reset_index()


def changes(prev: pd.DataFrame, curr: pd.DataFrame) -> pd.DataFrame:
    """Within-pitcher change per pitch type and metric, for pitchers in both seasons."""
    a, b = _pitch_means(prev), _pitch_means(curr)
    m = a.merge(b, on=["pitcher", "pitch_type"], suffixes=("_prev", "_curr"))
    rows = []
    for metric in list(METRICS) + ["spin_per_mph"]:
        d = m[["pitcher", "player_name_curr", "pitch_type", f"{metric}_prev", f"{metric}_curr"]].copy()
        d.columns = ["pitcher", "player_name", "pitch_type", "prev", "curr"]
        d["metric"] = metric
        d["change"] = d["curr"] - d["prev"]
        if metric == "spin_per_mph":
            d["change_pct"] = 100 * d["change"] / d["prev"]
        rows.append(d)
    out = pd.concat(rows, ignore_index=True)
    league = out.groupby(["metric", "pitch_type"])["change"].median().rename("league_median_change")
    out = out.join(league, on=["metric", "pitch_type"])
    out["excess_change"] = out["change"] - out["league_median_change"]
    out["pctile"] = out.groupby(["metric", "pitch_type"])["change"].rank(pct=True) * 100
    return out


def league_change(ch: pd.DataFrame) -> pd.DataFrame:
    """Summary: the league-wide median change and its spread, per metric x pitch type."""
    return (
        ch.groupby(["metric", "pitch_type"])["change"]
        .agg(pitchers="size", median="median", p25=lambda x: x.quantile(0.25), p75=lambda x: x.quantile(0.75),
             share_up=lambda x: (x > 0).mean() * 100)
        .reset_index()
    )
