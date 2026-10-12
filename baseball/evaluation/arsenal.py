"""Pitcher arsenal tables from Statcast pitch-level data.

The same table is built two ways, in pandas and in DuckDB SQL, so you can practice
both and check that they agree (tests/test_arsenal.py does exactly that).

Grain of the input: one row per pitch.
Grain of the output: one row per pitch type for one pitcher.

Definitions
- usage_pct : share of the pitcher's pitches, computed BEFORE the sample floor is applied
- velo      : mean release_speed (mph)
- spin      : mean release_spin_rate (rpm)
- ivb_in    : induced vertical break in inches (Statcast pfx_z is in feet, so x 12)
- hb_arm_in : horizontal break toward the pitcher's arm side, in inches. Statcast pfx_x is from the
              catcher's view, so a right-hander's arm-side run is negative pfx_x and gets flipped.
- whiff_pct : whiffs / swings
- csw_pct   : (called strikes + whiffs) / all pitches
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

SWINGS = (
    "swinging_strike", "swinging_strike_blocked", "foul", "foul_tip", "foul_bunt", "missed_bunt",
    "hit_into_play", "hit_into_play_no_out", "hit_into_play_score",
)
WHIFFS = ("swinging_strike", "swinging_strike_blocked", "foul_tip", "missed_bunt")

COLUMNS = ["pitch_type", "pitch_name", "n", "usage_pct", "velo", "spin", "ivb_in", "hb_arm_in", "whiff_pct", "csw_pct"]


def arsenal_counts(pitches: pd.DataFrame) -> pd.DataFrame:
    """The arsenal before rounding and floors, keeping the counts behind every rate (swings, whiffs,
    called strikes). Other tools (comparisons, intervals) build on this."""
    p = pitches.dropna(subset=["pitch_type"]).copy()
    if p["pitcher"].nunique() != 1:
        raise ValueError("arsenal() expects exactly one pitcher; filter first.")

    # Flags, derived once
    p["is_swing"] = p["description"].isin(SWINGS)
    p["is_whiff"] = p["description"].isin(WHIFFS)
    p["is_called"] = p["description"].eq("called_strike")
    p["ivb_in"] = p["pfx_z"] * 12
    p["hb_arm_in"] = np.where(p["p_throws"].eq("R"), -p["pfx_x"], p["pfx_x"]) * 12

    out = (
        p.groupby(["pitch_type", "pitch_name"], dropna=False)
        .agg(
            n=("pitch_type", "size"),
            velo=("release_speed", "mean"),
            spin=("release_spin_rate", "mean"),
            ivb_in=("ivb_in", "mean"),
            hb_arm_in=("hb_arm_in", "mean"),
            swings=("is_swing", "sum"),
            whiffs=("is_whiff", "sum"),
            called=("is_called", "sum"),
        )
        .reset_index()
    )
    # Rates after aggregation, from summed numerators and denominators
    out["usage_pct"] = 100 * out["n"] / out["n"].sum()
    out["whiff_pct"] = 100 * out["whiffs"] / out["swings"].replace(0, np.nan)
    out["csw_pct"] = 100 * (out["called"] + out["whiffs"]) / out["n"]
    return out.sort_values("n", ascending=False).reset_index(drop=True)


def arsenal(pitches: pd.DataFrame, min_n: int = 20) -> pd.DataFrame:
    """Arsenal table in pandas. `pitches` must hold one pitcher's pitches."""
    out = arsenal_counts(pitches)
    out = out[out["n"] >= min_n]
    # Round last
    out = out[COLUMNS].round({"usage_pct": 1, "velo": 1, "spin": 0, "ivb_in": 1, "hb_arm_in": 1, "whiff_pct": 1, "csw_pct": 1})
    return out.reset_index(drop=True)


ARSENAL_SQL = """
WITH flagged AS (
    SELECT
        pitch_type,
        pitch_name,
        release_speed,
        release_spin_rate,
        pfx_z * 12                                                          AS ivb_in,
        CASE WHEN p_throws = 'R' THEN -pfx_x ELSE pfx_x END * 12            AS hb_arm_in,
        description IN {swings}                                             AS is_swing,
        description IN {whiffs}                                             AS is_whiff,
        description = 'called_strike'                                       AS is_called
    FROM pitches
    WHERE pitch_type IS NOT NULL
),
by_type AS (
    SELECT
        pitch_type,
        pitch_name,
        COUNT(*)                                AS n,
        AVG(release_speed)                      AS velo,
        AVG(release_spin_rate)                  AS spin,
        AVG(ivb_in)                             AS ivb_in,
        AVG(hb_arm_in)                          AS hb_arm_in,
        SUM(is_swing::INT)                      AS swings,
        SUM(is_whiff::INT)                      AS whiffs,
        SUM(is_called::INT)                     AS called
    FROM flagged
    GROUP BY pitch_type, pitch_name
)
SELECT
    pitch_type,
    pitch_name,
    n,
    ROUND(100.0 * n / SUM(n) OVER (), 1)                    AS usage_pct,
    ROUND(velo, 1)                                          AS velo,
    ROUND(spin, 0)                                          AS spin,
    ROUND(ivb_in, 1)                                        AS ivb_in,
    ROUND(hb_arm_in, 1)                                     AS hb_arm_in,
    ROUND(100.0 * whiffs / NULLIF(swings, 0), 1)            AS whiff_pct,
    ROUND(100.0 * (called + whiffs) / n, 1)                 AS csw_pct
FROM by_type
QUALIFY n >= $min_n
ORDER BY n DESC
""".format(swings=SWINGS, whiffs=WHIFFS)


def arsenal_sql(pitches: pd.DataFrame, min_n: int = 20) -> pd.DataFrame:
    """The same arsenal table in DuckDB SQL. Usage is computed over all pitch types before the floor."""
    con = duckdb.connect()
    con.register("pitches", pitches)
    return con.execute(ARSENAL_SQL, {"min_n": min_n}).df()


OUTCOME_COLUMNS = ["pitch_type", "n", "ext_ft", "zone_pct", "chase_pct", "bip", "xwoba_con", "hard_hit_pct", "rv_per100"]


def outcomes(pitches: pd.DataFrame, min_n: int = 20) -> pd.DataFrame:
    """What happens when he throws each pitch: location, chase, contact quality and run value.

    - ext_ft       : mean release extension (ft)
    - zone_pct     : pitches in Statcast zones 1-9 / all pitches
    - chase_pct    : swings at pitches outside the zone / pitches outside the zone
    - bip          : balls in play (the sample behind the next two columns)
    - xwoba_con    : mean expected wOBA on balls in play (a model from exit velocity and launch angle)
    - hard_hit_pct : balls in play at 95+ mph / balls in play
    - rv_per100    : runs saved per 100 pitches, from Statcast delta_run_exp (positive = good for the pitcher)
    """
    p = pitches.dropna(subset=["pitch_type"]).copy()
    p["in_zone"] = p["zone"].between(1, 9)
    p["out_zone"] = p["zone"].notna() & ~p["in_zone"]
    p["is_swing"] = p["description"].isin(SWINGS)
    p["chase"] = p["out_zone"] & p["is_swing"]
    p["is_bip"] = p["type"].eq("X")
    p["hard"] = p["is_bip"] & p["launch_speed"].ge(95)
    p["xwoba_bip"] = p["estimated_woba_using_speedangle"].where(p["is_bip"])

    out = (
        p.groupby("pitch_type")
        .agg(
            n=("pitch_type", "size"),
            ext_ft=("release_extension", "mean"),
            in_zone=("in_zone", "sum"),
            out_zone=("out_zone", "sum"),
            chases=("chase", "sum"),
            bip=("is_bip", "sum"),
            hard=("hard", "sum"),
            xwoba_con=("xwoba_bip", "mean"),
            rv=("delta_run_exp", "sum"),
        )
        .reset_index()
    )
    out["zone_pct"] = 100 * out["in_zone"] / out["n"]
    out["chase_pct"] = 100 * out["chases"] / out["out_zone"].replace(0, np.nan)
    out["hard_hit_pct"] = 100 * out["hard"] / out["bip"].replace(0, np.nan)
    out["rv_per100"] = -100 * out["rv"] / out["n"]  # delta_run_exp is from the offense's side, so flip it

    out = out[out["n"] >= min_n].sort_values("n", ascending=False)
    return out[OUTCOME_COLUMNS].round({"ext_ft": 2, "zone_pct": 1, "chase_pct": 1, "xwoba_con": 3, "hard_hit_pct": 1, "rv_per100": 2}).reset_index(drop=True)


def usage_by_hand(pitches: pd.DataFrame, min_n: int = 20) -> pd.DataFrame:
    """Usage % of each pitch type against left-handed (L) and right-handed (R) hitters."""
    p = pitches.dropna(subset=["pitch_type"])
    keep = p["pitch_type"].value_counts().loc[lambda s: s >= min_n].index
    table = pd.crosstab(p["pitch_type"], p["stand"], normalize="columns").mul(100).round(1)
    table = table.loc[table.index.isin(keep)]
    table.columns = [f"vs_{c}HH_pct" for c in table.columns]
    counts = p["stand"].value_counts()
    table.attrs["pitches_vs"] = counts.to_dict()
    return table.sort_values(table.columns[-1], ascending=False).reset_index()
