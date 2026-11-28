"""One hitter's approach and contact, split the way a hitting coach asks about it.

The season line says what happened; these splits say where. For one batter-season of Statcast pitches (regular
season only) it returns:
- the plate-discipline line: chase rate, zone swing, contact in and out of the zone, whiff per swing;
- two strikes: how often at-bats got there, how often they ended in a strikeout once there, and what his swing and
  contact looked like with two strikes against the rest of the count;
- batted balls: ground ball, line drive, fly ball and popup shares, hard-hit rate, how many hard-hit balls went
  into the ground, wOBA and expected wOBA on contact;
- two locations clubs attack him with: fastballs above 3.0 ft and soft stuff (breaking balls and offspeed) low and
  away;
- swing and take run value by Savant's attack regions (heart, shadow, chase, waste);
- whiff rate and expected wOBA on contact for each of the 13 Statcast zones (the hole map).

Two seasons compare with `compare`, which adds a two-proportion z-test for rates and Welch's t-test for means, so a
report can say which changes are bigger than the noise. Nothing here is fitted, so there is no out-of-sample step;
the report says which differences pass and which don't.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as st

from baseball.stats import benjamini_hochberg, two_proportion, wilson

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "outputs"

SWINGS = {"swinging_strike", "swinging_strike_blocked", "foul", "foul_tip", "hit_into_play"}
WHIFFS = {"swinging_strike", "swinging_strike_blocked", "foul_tip"}
STRIKEOUTS = {"strikeout", "strikeout_double_play"}
WALKS = {"walk", "intent_walk"}
FASTBALLS = {"FF", "SI", "FC"}
SOFT = {"SL", "ST", "CU", "KC", "SV", "CS", "CH", "FS", "FO", "SC"}
HIGH_FB_FT = 3.0
HARD_HIT = 95.0
ZONE_HALF_WIDTH_FT = 10 / 12        # half the plate (8.5 in) plus a ball's radius, rounded as Savant does
INTERCEPT = "intercept_ball_minus_batter_pos_y_inches"


def _away_low_zones(stand: str) -> set[int]:
    """Statcast zones are drawn from the catcher's view: a right-handed hitter's outside edge is the right side."""
    return {9, 14} if stand == "R" else {7, 13}


def prepare(d: pd.DataFrame) -> pd.DataFrame:
    """Regular season only, with the flags the splits use."""
    d = d[d["game_type"] == "R"].copy() if "game_type" in d else d.copy()
    d["swing"] = d["description"].isin(SWINGS)
    d["whiff"] = d["description"].isin(WHIFFS)
    d["in_zone"] = d["zone"].between(1, 9)
    d["bip"] = d["description"] == "hit_into_play"
    d["pa_end"] = d["events"].notna() & (d["events"] != "truncated_pa")
    return d


def attack_region(d: pd.DataFrame) -> pd.Series:
    """Savant's attack regions from location, as a fraction of the hitter's own zone: heart inside 67%, shadow to
    133%, chase to 200%, waste beyond."""
    mid = (d["sz_top"] + d["sz_bot"]) / 2
    half_h = (d["sz_top"] - d["sz_bot"]) / 2
    r = np.maximum(d["plate_x"].abs() / ZONE_HALF_WIDTH_FT, (d["plate_z"] - mid).abs() / half_h)
    return pd.cut(r, [-np.inf, 0.67, 1.33, 2.0, np.inf], labels=["heart", "shadow", "chase", "waste"], right=False)


def _rate(k: int, n: int) -> dict:
    lo, hi = wilson(int(k), int(n))
    return {"k": int(k), "n": int(n), "pct": round(100 * k / n, 1) if n else None,
            "lo": round(100 * lo, 1) if n else None, "hi": round(100 * hi, 1) if n else None}


def _mean(s: pd.Series, nd: int = 1) -> dict:
    s = s.dropna()
    return {"mean": round(float(s.mean()), nd) if len(s) else None, "n": len(s),
            "sd": round(float(s.std(ddof=1)), nd + 1) if len(s) > 1 else None}


def _contact(sw: pd.DataFrame) -> dict:
    """Contact per swing (a foul tip is a whiff, as Statcast counts it)."""
    return _rate((~sw["whiff"]).sum(), len(sw))


def _batted(b: pd.DataFrame) -> dict:
    bt = b["bb_type"]
    hard = b[b["launch_speed"] >= HARD_HIT]
    return {
        "n": len(b),
        "ground_ball": _rate((bt == "ground_ball").sum(), len(b)),
        "line_drive": _rate((bt == "line_drive").sum(), len(b)),
        "fly_ball": _rate((bt == "fly_ball").sum(), len(b)),
        "popup": _rate((bt == "popup").sum(), len(b)),
        "hard_hit": _rate(len(hard), b["launch_speed"].notna().sum()),
        "hard_hit_on_ground": _rate((hard["bb_type"] == "ground_ball").sum(), len(hard)),
        "launch_angle": _mean(b["launch_angle"]),
        "launch_angle_hard_hit": _mean(hard["launch_angle"]),
        "exit_velo": _mean(b["launch_speed"]),
        "ev90": round(float(b["launch_speed"].dropna().quantile(0.9)), 1) if b["launch_speed"].notna().any() else None,
        "xwoba_con": round(float(b["estimated_woba_using_speedangle"].mean()), 3) if len(b) else None,
        "woba_con": round(float(b["woba_value"].mean()), 3) if len(b) else None,
        # results against expected results by batted-ball type: where a gap between wOBA and xwOBA came from
        "by_type": {t: {"n": len(g), "woba": round(float(g["woba_value"].mean()), 3),
                        "xwoba": round(float(g["estimated_woba_using_speedangle"].mean()), 3)}
                    for t, g in b.groupby("bb_type")},
    }


def _swing_shape(sw: pd.DataFrame) -> dict:
    return {"bat_speed": _mean(sw["bat_speed"]), "swing_length": _mean(sw["swing_length"], 2),
            "attack_angle": _mean(sw["attack_angle"]),
            "contact_depth_in": _mean(sw[INTERCEPT]) if INTERCEPT in sw else None}


def season_splits(d: pd.DataFrame) -> dict:
    """All the splits for one batter-season. `d` is that hitter's pitches; `prepare` is applied here."""
    d = prepare(d)
    stand = d["stand"].mode().iloc[0]
    pa = d[d["pa_end"]]
    sw = d[d["swing"]]
    oz, iz = d[~d["in_zone"]], d[d["in_zone"]]

    two = d[d["strikes"] == 2]
    pa2 = pa[pa["strikes"] == 2]
    sw2, sw01 = sw[sw["strikes"] == 2], sw[sw["strikes"] < 2]

    hi = d[d["pitch_type"].isin(FASTBALLS) & (d["plate_z"] > HIGH_FB_FT)]
    la = d[d["pitch_type"].isin(SOFT) & d["zone"].isin(_away_low_zones(stand))]

    reg = attack_region(d)
    regions = {}
    for name in ["heart", "shadow", "chase", "waste"]:
        g = d[reg == name]
        regions[name] = {"n": len(g), "swing": _rate(g["swing"].sum(), len(g)),
                         "rv_swing": round(float(g.loc[g["swing"], "delta_run_exp"].sum()), 1),
                         "rv_take": round(float(g.loc[~g["swing"], "delta_run_exp"].sum()), 1)}

    zones = {}
    for z, g in d.groupby("zone"):
        gs = g[g["swing"]]
        zones[str(int(z))] = {"n": len(g), "swings": len(gs), "whiff": _rate(gs["whiff"].sum(), len(gs)),
                              "xwoba_con": round(float(g.loc[g["bip"], "estimated_woba_using_speedangle"].mean()), 3)
                              if g["bip"].any() else None, "bip": int(g["bip"].sum())}

    return {
        "stand": stand,
        "pitches": len(d),
        "pa": len(pa),
        "strikeout": _rate(pa["events"].isin(STRIKEOUTS).sum(), len(pa)),
        "walk": _rate(pa["events"].isin(WALKS).sum(), len(pa)),
        "discipline": {
            "chase": _rate(oz["swing"].sum(), len(oz)),
            "zone_swing": _rate(iz["swing"].sum(), len(iz)),
            "zone_contact": _contact(sw[sw["in_zone"]]),
            "chase_contact": _contact(sw[~sw["in_zone"]]),
            "whiff_per_swing": _rate(sw["whiff"].sum(), len(sw)),
            "first_pitch_swing": _rate(d.loc[(d["balls"] == 0) & (d["strikes"] == 0), "swing"].sum(),
                                       ((d["balls"] == 0) & (d["strikes"] == 0)).sum()),
        },
        "two_strikes": {
            "pa_reaching": _rate(len(pa2), len(pa)),
            "strikeout_once_there": _rate(pa2["events"].isin(STRIKEOUTS).sum(), len(pa2)),
            "chase": _rate(two.loc[~two["in_zone"], "swing"].sum(), (~two["in_zone"]).sum()),
            "zone_swing": _rate(two.loc[two["in_zone"], "swing"].sum(), two["in_zone"].sum()),
            "chase_contact": _contact(sw2[~sw2["in_zone"]]),
            "zone_contact": _contact(sw2[sw2["in_zone"]]),
            "swing_two_strikes": _swing_shape(sw2),
            "swing_fewer_strikes": _swing_shape(sw01),
            "batted": _batted(two[two["bip"]]),
            "batted_chase": _batted(two[two["bip"] & ~two["in_zone"]]),
        },
        "batted": _batted(d[d["bip"]]),
        "swing": _swing_shape(sw),
        "high_fastball": {"pitches": len(hi), "swing": _rate(hi["swing"].sum(), len(hi)),
                          "whiff": _rate(hi.loc[hi["swing"], "whiff"].sum(), hi["swing"].sum()),
                          "swing_shape": _swing_shape(hi[hi["swing"]]), "batted": _batted(hi[hi["bip"]])},
        "low_away_soft": {"pitches": len(la), "swing": _rate(la["swing"].sum(), len(la)),
                          "whiff": _rate(la.loc[la["swing"], "whiff"].sum(), la["swing"].sum()),
                          "swing_shape": _swing_shape(la[la["swing"]]), "batted": _batted(la[la["bip"]])},
        "regions": regions,
        "zones": zones,
    }


def compare_rate(a: dict, b: dict) -> dict:
    _, p = two_proportion(a["k"], a["n"], b["k"], b["n"])
    return {"from": a["pct"], "to": b["pct"], "diff": round(b["pct"] - a["pct"], 1), "p": round(p, 4)}


def compare_mean(a: pd.Series, b: pd.Series, nd: int = 1) -> dict:
    a, b = a.dropna(), b.dropna()
    _, p = st.ttest_ind(a, b, equal_var=False)
    return {"from": round(float(a.mean()), nd), "to": round(float(b.mean()), nd),
            "diff": round(float(b.mean() - a.mean()), nd), "p": round(float(p), 4), "n": [len(a), len(b)]}


def compare(d1: pd.DataFrame, d2: pd.DataFrame) -> dict:
    """The season-over-season tests a report quotes: each is (first season, second season, difference, p)."""
    s1, s2 = season_splits(d1), season_splits(d2)
    p1, p2 = prepare(d1), prepare(d2)
    stand = s1["stand"]

    def hi(d):
        return d[d["pitch_type"].isin(FASTBALLS) & (d["plate_z"] > HIGH_FB_FT)]

    def la(d):
        return d[d["pitch_type"].isin(SOFT) & d["zone"].isin(_away_low_zones(stand))]

    t1, t2 = s1["two_strikes"], s2["two_strikes"]
    tests = {
        "strikeout": compare_rate(s1["strikeout"], s2["strikeout"]),
        "chase": compare_rate(s1["discipline"]["chase"], s2["discipline"]["chase"]),
        "two_strike_chase": compare_rate(t1["chase"], t2["chase"]),
        "two_strike_chase_contact": compare_rate(t1["chase_contact"], t2["chase_contact"]),
        "two_strike_zone_contact": compare_rate(t1["zone_contact"], t2["zone_contact"]),
        "strikeout_once_at_two_strikes": compare_rate(t1["strikeout_once_there"], t2["strikeout_once_there"]),
        "ground_ball": compare_rate(s1["batted"]["ground_ball"], s2["batted"]["ground_ball"]),
        "popup": compare_rate(s1["batted"]["popup"], s2["batted"]["popup"]),
        "hard_hit": compare_rate(s1["batted"]["hard_hit"], s2["batted"]["hard_hit"]),
        "hard_hit_on_ground": compare_rate(s1["batted"]["hard_hit_on_ground"], s2["batted"]["hard_hit_on_ground"]),
        "high_fb_whiff": compare_rate(s1["high_fastball"]["whiff"], s2["high_fastball"]["whiff"]),
        "high_fb_bat_speed": compare_mean(hi(p1).loc[lambda x: x["swing"], "bat_speed"],
                                          hi(p2).loc[lambda x: x["swing"], "bat_speed"]),
        "high_fb_contact_depth": compare_mean(hi(p1).loc[lambda x: x["swing"], INTERCEPT],
                                              hi(p2).loc[lambda x: x["swing"], INTERCEPT]),
        "high_fb_launch_angle": compare_mean(hi(p1).loc[lambda x: x["bip"], "launch_angle"],
                                             hi(p2).loc[lambda x: x["bip"], "launch_angle"]),
        "low_away_soft_whiff": compare_rate(s1["low_away_soft"]["whiff"], s2["low_away_soft"]["whiff"]),
        "bat_speed_all_swings": compare_mean(p1.loc[p1["swing"], "bat_speed"], p2.loc[p2["swing"], "bat_speed"]),
        "contact_depth_all_swings": compare_mean(p1.loc[p1["swing"], INTERCEPT], p2.loc[p2["swing"], INTERCEPT]),
    }
    # many tests on one pair of seasons: report Benjamini-Hochberg q-values next to the raw p-values
    for t, q in zip(tests.values(), benjamini_hochberg([t["p"] for t in tests.values()])):
        t["q"] = round(float(q), 4)
    return {"first": s1, "second": s2, "tests": tests}


def main(first_csv: str, second_csv: str, out_name: str, years=(2025, 2026)) -> dict:
    """Write the comparison for two Savant statcast_search exports of one hitter."""
    res = compare(pd.read_csv(first_csv), pd.read_csv(second_csv))
    res = {"seasons": list(years), **res}
    (OUT / out_name).write_text(json.dumps(res, indent=1, allow_nan=False, default=lambda x: None))
    return res


if __name__ == "__main__":   # python -m baseball.evaluation.approach_splits sc2025.csv sc2026.csv arozarena_approach.json
    import sys

    main(*sys.argv[1:4])
