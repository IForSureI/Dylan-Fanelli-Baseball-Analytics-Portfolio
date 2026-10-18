"""Advance-scouting packet on an opponent's hitters, from the sequence copy of Statcast (data/seq/).

The question a pitching staff asks before a series: for each hitter in their lineup, where does he swing,
what does he miss, what does he hurt, and what does he do early and with two strikes? This module answers
it with one table per question and draft plan lines, every rate carrying its n and its regressed value.

Grain: one row per pitch (regular season, automatic balls and strikes removed). The batting team on each
pitch is the away team in the top of the inning and the home team in the bottom. A hitter's tendencies use
all of his pitches that season (with any club); the lineup is chosen by plate appearances with the club.

Locations are in the hitter's frame. Statcast's zones 1-9 (the strike zone in thirds) and 11-14 (the four
chase quadrants) are relabeled "in" and "away" by the side the hitter stood on, so a switch-hitter's two
sides add up. Pitches outside the zone are also given a direction (above, below, in, away): the side on
which the pitch is furthest outside the zone, with the plate edge at 0.83 ft (8.5 in plus a ball radius).

Small samples: every rate is shrunk toward the league rate for the same cell with the Reliability Atlas
constants (`baseball/evaluation/reliability_params.json`): estimate = (n x observed + M x league) / (n + M),
M in the metric's own events (swings for whiff, balls in play for xwOBA on contact, pitches outside the
zone for chase). The atlas measured M on whole-season rates, so using it inside a cell (say, breaking balls
below the zone) treats the cell's true-talent spread as the same as the overall one: an approximation.
Platoon splits are regressed toward the league split for the hitter's side with The Book's constants
(2,200 PA against left-handed pitchers for right-handed hitters, 1,000 for left-handed hitters; switch
hitters get the larger figure).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from baseball.edge.familiarity import GROUP, seq_parts
from baseball.evaluation.arsenal import SWINGS, WHIFFS
from baseball.evaluation.reliability import BUNTS, NO_PITCH, competitive_swings, load_params

COLUMNS = [
    "game_pk", "game_date", "game_year", "home_team", "away_team", "inning_topbot", "at_bat_number", "pitch_number",
    "pitcher", "batter", "p_throws", "stand", "pitch_type", "description", "type", "events", "balls", "strikes",
    "release_speed", "release_spin_rate", "plate_x", "plate_z", "sz_top", "sz_bot", "zone", "woba_value",
    "woba_denom", "estimated_woba_using_speedangle", "launch_speed", "bat_speed", "swing_length", "attack_angle",
    "attack_direction", "swing_path_tilt",
]
FAMILIES = ["fastball", "cutter", "breaking", "offspeed"]
FAMILY_LABEL = {"fastball": "fastballs (four-seam, sinker)", "cutter": "cutters",
                "breaking": "breaking balls", "offspeed": "changeups and splitters"}
EDGE_FT = 0.83                     # half the plate (8.5 in) plus a ball radius, in feet
ROWS = ["up", "mid", "down"]
COLS = ["in", "mid", "away"]
RING = ["up-in", "up-away", "down-in", "down-away"]
CELLS = [f"{r}-{c}" for r in ROWS for c in COLS] + [f"chase {q}" for q in RING]
OUT_DIRS = ["above", "below", "in", "away"]
VELO_BANDS = ["under 93", "93-95.9", "96+"]
SPIN_BANDS = ["low third", "middle third", "top third"]
STRIKEOUTS = ("strikeout", "strikeout_double_play")
WALKS = ("walk", "intent_walk")
# Display minimums: below these a rate is shown in parentheses and never drives a plan line.
MIN_SWINGS, MIN_PITCHES, MIN_BIP, MIN_PA = 10, 20, 8, 25
# The Book (Tango, Lichtman, Dolphin 2007): PA vs left-handed pitchers of league-average split to add.
PLATOON_M = {"R": 2200.0, "L": 1000.0, "S": 2200.0}
# Which constant regresses which rate (atlas metric ids).
M_IDS = {"whiff": "hitter/whiff", "chase": "hitter/chase", "zone_swing": "hitter/zone_swing",
         "swing": "hitter/swing", "xwcon": "hitter/xwoba_con", "hard": "hitter/hard_hit",
         "zone_contact": "hitter/zone_contact", "bat_speed": "hitter/bat_speed",
         "swing_length": "hitter/swing_length", "attack_angle": "hitter/attack_angle",
         "attack_dir": "hitter/attack_direction", "tilt": "hitter/swing_path_tilt"}


# ---------------------------------------------------------------- data

def load_season(season: int, columns: list[str] | None = None) -> pd.DataFrame:
    """One regular season from data/seq/, only the columns asked for (memory: ~100 MB per 10 columns)."""
    import pyarrow.parquet as pq

    parts = seq_parts(season)
    if not parts:
        raise FileNotFoundError(f"No sequence data for {season} in data/seq/. Run `bb seq {season}` on the Mac.")
    columns = columns or COLUMNS
    have = set(pq.ParquetFile(parts[0]).schema_arrow.names)
    cols = [c for c in columns if c in have]
    return pd.concat([pd.read_parquet(p, columns=cols) for p in parts], ignore_index=True)


def _side(stand: pd.Series, catcher_left: pd.Series) -> np.ndarray:
    """'in' when the location is on the hitter's side of the plate. A right-handed hitter stands on the
    catcher's left (third-base side), so the catcher's-left column is inside to him."""
    return np.where(catcher_left.to_numpy() == stand.eq("R").to_numpy(), "in", "away")


def prepare(p: pd.DataFrame) -> pd.DataFrame:
    """Flags once, on every pitch of the frame. The frame should be the whole league season: spin bands
    are thirds of the league's spin for each breaking-ball type, computed here."""
    d = p.copy()
    # Automatic balls and strikes (pitch-clock violations) end plate appearances but are not pitches:
    # they count toward PA, K and BB and toward nothing else.
    d["thrown"] = ~d["description"].isin(NO_PITCH)
    d["season"] = d["game_year"].astype(int)
    top = d["inning_topbot"].eq("Top")
    d["bat_team"] = np.where(top, d["away_team"], d["home_team"])
    d["swing"] = d["description"].isin(SWINGS)
    d["whiff"] = d["description"].isin(WHIFFS)
    d["contact"] = d["swing"] & ~d["whiff"]
    d["bip"] = d["type"].eq("X")
    d["in_zone"] = d["zone"].between(1, 9) & d["thrown"]
    d["out_zone"] = d["zone"].notna() & ~d["zone"].between(1, 9) & d["thrown"]
    d["family"] = d["pitch_type"].map(GROUP)
    d["xwcon"] = d["estimated_woba_using_speedangle"].where(d["bip"])
    d["hard_n"] = d["bip"] & d["launch_speed"].notna()
    d["hard"] = d["hard_n"] & d["launch_speed"].ge(95)
    d["first_pitch"] = d["balls"].eq(0) & d["strikes"].eq(0)
    d["two_k"] = d["strikes"].eq(2)
    ev = d["events"]
    d["pa"] = ev.notna() & ev.ne("truncated_pa")
    d["k"] = ev.isin(STRIKEOUTS)
    d["bb"] = ev.isin(WALKS)
    d["woba_n"] = d["woba_denom"].fillna(0).eq(1)
    d["woba_v"] = d["woba_value"].where(d["woba_n"], 0.0).fillna(0.0)
    d["xwoba_v"] = np.where(d["woba_n"], np.where(d["bip"] & d["xwcon"].notna(), d["xwcon"], d["woba_value"]), 0.0)
    d["xwoba_v"] = d["xwoba_v"].fillna(0.0)
    # Bat tracking: Statcast's competitive swings (the batter's fastest 90%, plus hard contact)
    d["comp"] = competitive_swings(d, "bat_speed") if d["bat_speed"].notna().any() else False
    d["attack_dir"] = -d["attack_direction"]          # pull positive for both sides (see reliability.prepare)
    d["tilt"] = d["swing_path_tilt"]
    # Locations in the hitter's frame
    z = d["zone"]
    col_cl = z.isin([1, 4, 7, 11, 13])                # catcher's left
    col_mid = z.isin([2, 5, 8])
    row = np.select([z.isin([1, 2, 3]), z.isin([4, 5, 6]), z.isin([7, 8, 9])], ROWS, "")
    col = np.where(col_mid, "mid", _side(d["stand"], col_cl))
    ring_v = np.where(z.isin([11, 12]), "up", "down")
    d["cell"] = np.where(d["in_zone"], pd.Series(row, index=d.index) + "-" + pd.Series(col, index=d.index),
                         np.where(d["out_zone"], "chase " + pd.Series(ring_v, index=d.index) + "-"
                                  + pd.Series(_side(d["stand"], col_cl), index=d.index), ""))
    d["zrow"] = np.where(d["in_zone"], row, "")
    d["zcol"] = np.where(d["in_zone"], col, "")
    up = d["plate_z"] - d["sz_top"]
    down = d["sz_bot"] - d["plate_z"]
    side = d["plate_x"].abs() - EDGE_FT
    ex = np.vstack([up.to_numpy(float), down.to_numpy(float), side.to_numpy(float)])
    which = np.nanargmax(np.where(np.isnan(ex), -np.inf, ex), axis=0)
    inside = (d["plate_x"] < 0).to_numpy() == d["stand"].eq("R").to_numpy()
    odir = np.select([which == 0, which == 1, inside], ["above", "below", "in"], "away")
    d["odir"] = np.where(d["out_zone"] & d["plate_x"].notna() & d["plate_z"].notna(), odir, "")
    # Velocity and spin bands
    fb = d["pitch_type"].isin(["FF", "SI"])
    v = d["release_speed"]
    d["velo_band"] = np.where(fb & v.notna(), np.select([v < 93, v < 96], VELO_BANDS[:2], VELO_BANDS[2]), "")
    br = d["family"].eq("breaking") & d["release_spin_rate"].notna()
    pct = d.loc[br].groupby("pitch_type")["release_spin_rate"].rank(pct=True)
    band = pd.Series("", index=d.index, dtype=object)
    band.loc[pct.index] = np.select([pct <= 1 / 3, pct <= 2 / 3], SPIN_BANDS[:2], SPIN_BANDS[2])
    d["spin_band"] = band
    d["count_state"] = np.select([d["first_pitch"], d["two_k"]], ["first pitch", "two strikes"], "other")
    keep = ["thrown", "game_pk", "batter", "pitcher", "stand", "p_throws", "bat_team", "pitch_type", "family", "swing", "whiff",
            "contact", "bip", "in_zone", "out_zone", "xwcon", "hard", "hard_n", "first_pitch", "two_k", "pa", "k",
            "bb", "woba_n", "woba_v", "xwoba_v", "comp", "bat_speed", "swing_length", "attack_angle", "attack_dir",
            "tilt", "cell", "zrow", "zcol", "odir", "velo_band", "spin_band", "count_state", "description"]
    d = d[keep].reset_index(drop=True)
    for c in ("cell", "zrow", "zcol", "odir", "velo_band", "spin_band", "count_state", "family", "pitch_type",
              "bat_team", "stand", "p_throws"):
        d[c] = d[c].astype("category")
    return d


# ---------------------------------------------------------------- sums and rates

def sums(d: pd.DataFrame, keys: list[str] | None = None) -> pd.DataFrame:
    """Numerators and denominators by keys (rates come after aggregation)."""
    x = pd.DataFrame({
        "pitches": d["thrown"].astype(int), "swings": d["swing"].astype(int), "whiffs": d["whiff"].astype(int),
        "in_pitches": d["in_zone"].astype(int), "in_swings": (d["swing"] & d["in_zone"]).astype(int),
        "in_contact": (d["contact"] & d["in_zone"]).astype(int),
        "out_pitches": d["out_zone"].astype(int), "out_swings": (d["swing"] & d["out_zone"]).astype(int),
        "bip": d["bip"].astype(int), "xw_sum": d["xwcon"].fillna(0.0), "xw_n": d["xwcon"].notna().astype(int),
        "hard": d["hard"].astype(int), "hard_n": d["hard_n"].astype(int),
        "pa": d["pa"].astype(int), "k": d["k"].astype(int), "bb": d["bb"].astype(int),
        "woba_n": d["woba_n"].astype(int), "woba_sum": d["woba_v"], "xwoba_sum": d["xwoba_v"],
    }, index=d.index)
    if not keys:
        return x.sum().to_frame().T
    for k in keys:
        x[k] = d[k]
    return x.groupby(keys, observed=True).sum().reset_index()


def rates(s: pd.DataFrame) -> pd.DataFrame:
    """Raw rates from summed counts (NaN where the denominator is 0)."""
    s = s.copy()
    div = lambda a, b: np.where(s[b] > 0, s[a] / s[b].where(s[b] > 0, 1), np.nan)  # noqa: E731
    s["swing"] = div("swings", "pitches")
    s["whiff"] = div("whiffs", "swings")
    s["swstr"] = div("whiffs", "pitches")
    s["zone_swing"] = div("in_swings", "in_pitches")
    s["zone_contact"] = div("in_contact", "in_swings")
    s["chase"] = div("out_swings", "out_pitches")
    s["xwcon"] = div("xw_sum", "xw_n")
    s["hard_rate"] = div("hard", "hard_n")
    s["k_rate"] = div("k", "pa")
    s["bb_rate"] = div("bb", "pa")
    s["woba"] = div("woba_sum", "woba_n")
    s["xwoba"] = div("xwoba_sum", "woba_n")
    return s


def shrink(metric: str, observed, n, league) -> np.ndarray:
    """(n x observed + M x league) / (n + M) with the atlas M for `metric` (a key of M_IDS)."""
    M = float(load_params().loc[M_IDS[metric], "M"])
    obs = np.nan_to_num(np.asarray(observed, float))
    n = np.asarray(n, float)
    league = np.asarray(league, float)
    return np.where(n > 0, (n * obs + M * league) / (n + M), league)


# The rate, its denominator column and the atlas constant used to regress it.
RATE_SPECS = {
    "swing": ("pitches", "swing"), "whiff": ("swings", "whiff"), "chase": ("out_pitches", "chase"),
    "zone_swing": ("in_pitches", "zone_swing"), "zone_contact": ("in_swings", "zone_contact"),
    "xwcon": ("xw_n", "xwcon"), "hard_rate": ("hard_n", "hard"),
}


def compare(h: pd.DataFrame, lg: pd.DataFrame, keys: list[str], swing_metric: str = "swing") -> pd.DataFrame:
    """Join a hitter's rates to the league's on keys, with regressed versions (`r_<rate>`) and the league
    rate (`lg_<rate>`). `swing_metric` picks the constant for swing rate in out-of-zone or in-zone cells."""
    h, lg = rates(h), rates(lg)
    cols = list(RATE_SPECS) + ["swstr", "k_rate", "bb_rate", "woba", "xwoba"]
    m = h.merge(lg[keys + cols].rename(columns={c: f"lg_{c}" for c in cols}), on=keys, how="left") if keys else \
        h.assign(**{f"lg_{c}": lg[c].iloc[0] for c in cols})
    for rate, (den, metric) in RATE_SPECS.items():
        metric = swing_metric if rate == "swing" else metric
        m[f"r_{rate}"] = shrink(metric, m[rate], m[den], m[f"lg_{rate}"])
    m["r_swstr"] = m["r_swing"] * m["r_whiff"]
    return m


def _swing_metric_for(loc_kind: str) -> str:
    return {"out": "chase", "in": "zone_swing"}.get(loc_kind, "swing")


# ---------------------------------------------------------------- league and hitter tables

def _loc_views(d: pd.DataFrame) -> list[tuple[str, str, pd.DataFrame]]:
    """Three overlapping location views: zone rows, zone columns, out-of-zone directions."""
    zr = d[d["zrow"].astype(str) != ""].assign(loc=lambda x: "zone " + x["zrow"].astype(str))
    zc = d[d["zcol"].astype(str) != ""].assign(loc=lambda x: "zone " + x["zcol"].astype(str).replace({"mid": "middle"}))
    od = d[d["odir"].astype(str) != ""].assign(loc=lambda x: "chase " + x["odir"].astype(str))
    return [("in", "row", zr), ("in", "col", zc), ("out", "dir", od)]


def famloc_sums(d: pd.DataFrame) -> pd.DataFrame:
    """Sums by pitch family x location (zone up/mid/down, zone in/middle/away, chase above/below/in/away)."""
    frames = []
    for kind, view, x in _loc_views(d):
        s = sums(x, ["family", "loc"])
        s["loc_kind"], s["view"] = kind, view
        frames.append(s)
    return pd.concat(frames, ignore_index=True)


def league_tables(d: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """League sums for every table a hitter is compared on (the whole prepared season)."""
    lg = {
        "all": sums(d),
        "cell": sums(d[d["cell"].astype(str) != ""], ["cell"]),
        "family": sums(d[d["family"].notna()], ["family"]),
        "famloc": famloc_sums(d[d["family"].notna()]),
        "velo": sums(d[d["velo_band"].astype(str) != ""], ["velo_band"]),
        "spin": sums(d[d["spin_band"].astype(str) != ""], ["spin_band"]),
        "count": sums(d, ["count_state"]),
        "hand": sums(d, ["p_throws"]),
    }
    lg["platoon"] = league_platoon(d)
    lg["bat"] = bat_tracking_league(d)
    lg["two_k_bat"] = _two_k_bat(d)
    return lg


def hitter_side(d: pd.DataFrame) -> pd.Series:
    """'R', 'L', or 'S' (switch: at least 20% of plate appearances from the other side)."""
    pa = d[d["pa"]].groupby(["batter", "stand"], observed=True).size().unstack(fill_value=0)
    for c in ("R", "L"):
        if c not in pa:
            pa[c] = 0
    minor = pa[["R", "L"]].min(axis=1) / pa[["R", "L"]].sum(axis=1).clip(lower=1)
    return pd.Series(np.where(minor >= 0.2, "S", np.where(pa["R"] >= pa["L"], "R", "L")), index=pa.index)


def league_platoon(d: pd.DataFrame) -> pd.DataFrame:
    """League xwOBA per PA by hitter side x pitcher hand, and the split (vs LHP minus vs RHP)."""
    side = hitter_side(d)
    x = d.assign(side=d["batter"].map(side))
    s = rates(sums(x, ["side", "p_throws"]))
    t = s.pivot(index="side", columns="p_throws", values="xwoba")
    t["split"] = t["L"] - t["R"]
    return t.reset_index()


def bat_tracking_league(d: pd.DataFrame, min_comp: int = 100) -> pd.DataFrame:
    """Per-hitter means on competitive swings, hitters with min_comp+ (the reference for percentiles)."""
    c = d[d["comp"]]
    g = c.groupby("batter").agg(n=("bat_speed", "size"), bat_speed=("bat_speed", "mean"),
                                swing_length=("swing_length", "mean"), attack_angle=("attack_angle", "mean"),
                                attack_dir=("attack_dir", "mean"), tilt=("tilt", "mean"))
    return g[g["n"] >= min_comp]


def _two_k_bat(d: pd.DataFrame) -> pd.DataFrame:
    """Bat speed on competitive swings with two strikes vs fewer, per hitter."""
    c = d[d["comp"]]
    return c.pivot_table(index="batter", columns="two_k", values="bat_speed", aggfunc=["mean", "size"])


def hitter_profile(d: pd.DataFrame, batter: int, lg: dict, name: str = "", team: str = "") -> dict:
    """Every table for one hitter (d: the prepared league season; lg: league_tables(d))."""
    h = d[d["batter"] == batter]
    side = hitter_side(h).iloc[0] if h["pa"].any() else h["stand"].mode().iloc[0]
    stands = h.loc[h["pa"], "stand"].astype(str).value_counts()
    main_side = stands.index[0] if len(stands) else str(h["stand"].mode().iloc[0])
    prof = {"batter": int(batter), "name": name or str(batter), "side": side, "main_side": main_side,
            "pa_team": int(h.loc[h["bat_team"] == team, "pa"].sum()) if team else int(h["pa"].sum()),
            "pa": int(h["pa"].sum())}
    prof["overview"] = compare(sums(h), lg["all"], [])
    prof["cell"] = _cell_table(h, lg)
    prof["family"] = compare(sums(h[h["family"].notna()], ["family"]), lg["family"], ["family"])
    prof["famloc"] = _famloc_table(h, lg)
    prof["velo"] = compare(sums(h[h["velo_band"].astype(str) != ""], ["velo_band"]), lg["velo"], ["velo_band"])
    prof["spin"] = compare(sums(h[h["spin_band"].astype(str) != ""], ["spin_band"]), lg["spin"], ["spin_band"])
    prof["count"] = compare(sums(h, ["count_state"]), lg["count"], ["count_state"])
    prof["hand"] = compare(sums(h, ["p_throws"]), lg["hand"], ["p_throws"])
    prof["platoon"] = _platoon(prof["hand"], side, lg["platoon"])
    prof["bat"] = _bat(h, lg)
    return prof


def _cell_table(h: pd.DataFrame, lg: dict) -> pd.DataFrame:
    x = h[h["cell"].astype(str) != ""]
    s = sums(x, ["cell"])
    s = pd.DataFrame({"cell": CELLS}).merge(s, on="cell", how="left").fillna(0)
    inz = compare(s, lg["cell"], ["cell"], "zone_swing")
    outz = compare(s, lg["cell"], ["cell"], "chase")
    is_out = inz["cell"].str.startswith("chase")
    for c in ("r_swing", "r_swstr"):
        inz.loc[is_out, c] = outz.loc[is_out, c]
    return inz


def _famloc_table(h: pd.DataFrame, lg: dict) -> pd.DataFrame:
    hs = famloc_sums(h[h["family"].notna()])
    keys = ["family", "loc"]
    base = lg["famloc"][keys + ["loc_kind", "view"]]
    hs = base.merge(hs.drop(columns=["loc_kind", "view"]), on=keys, how="left").fillna(
        {c: 0 for c in hs.columns if c not in keys + ["loc_kind", "view"]})
    out = []
    for kind in ("in", "out"):
        part = hs[hs["loc_kind"] == kind]
        out.append(compare(part, lg["famloc"][lg["famloc"]["loc_kind"] == kind].drop(columns=["loc_kind", "view"]),
                           keys, _swing_metric_for(kind)))
    return pd.concat(out, ignore_index=True)


def _platoon(hand: pd.DataFrame, side: str, lgp: pd.DataFrame) -> dict:
    """Observed and regressed platoon split (xwOBA vs LHP minus vs RHP), The Book's method."""
    t = hand.set_index("p_throws")
    pa_l = float(t["pa"].get("L", 0))
    x_l, x_r = t["xwoba"].get("L", np.nan), t["xwoba"].get("R", np.nan)
    lg_split = float(lgp.set_index("side").loc[side, "split"]) if side in set(lgp["side"]) else 0.0
    obs = x_l - x_r if np.isfinite(x_l) and np.isfinite(x_r) else np.nan
    M = PLATOON_M[side]
    reg = lg_split + pa_l / (pa_l + M) * (obs - lg_split) if np.isfinite(obs) else lg_split
    return {"pa_vs_l": int(pa_l), "pa_vs_r": int(t["pa"].get("R", 0)), "xwoba_vs_l": x_l, "xwoba_vs_r": x_r,
            "observed_split": obs, "league_split": lg_split, "regressed_split": reg, "M": M}


def _bat(h: pd.DataFrame, lg: dict) -> dict:
    c = h[h["comp"]]
    ref = lg["bat"]
    out = {"n": int(len(c))}
    for col in ("bat_speed", "swing_length", "attack_angle", "attack_dir", "tilt"):
        obs = float(c[col].mean()) if len(c) else np.nan
        n_col = int(c[col].notna().sum())
        league = float(ref[col].mean()) if len(ref) else np.nan
        reg = float(shrink(col, obs, n_col, league)) if np.isfinite(league) else obs
        pctl = float(np.clip((ref[col] < reg).mean() * 100, 1, 99)) if len(ref) else np.nan
        out[col] = {"observed": obs, "n": n_col, "regressed": reg, "league": league, "pctl": pctl}
    two = c[c["two_k"]]["bat_speed"]
    rest = c[~c["two_k"]]["bat_speed"]
    tk = lg["two_k_bat"]
    lg_drop = float((tk[("mean", True)] - tk[("mean", False)]).dropna().mean()) if len(tk) else np.nan
    out["two_k"] = {"bat_speed_2k": float(two.mean()) if len(two) else np.nan, "n_2k": int(len(two)),
                    "bat_speed_other": float(rest.mean()) if len(rest) else np.nan, "n_other": int(len(rest)),
                    "league_drop": lg_drop}
    return out


# ---------------------------------------------------------------- lineup

def lineup(d: pd.DataFrame, team: str, n: int = 9) -> pd.DataFrame:
    """The team's n hitters with the most plate appearances while batting for it (the batting team on each
    pitch), with their total plate appearances that season."""
    pa = d[d["pa"]]
    t = pa[pa["bat_team"] == team].groupby("batter").size().rename("pa_team")
    tot = pa.groupby("batter").size().rename("pa_total")
    out = pd.concat([t, tot], axis=1, join="inner").sort_values("pa_team", ascending=False).head(n)
    return out.reset_index().rename(columns={"index": "batter"})


# ---------------------------------------------------------------- draft plan lines

LOC_WORDS = {"zone up": "up in the zone", "zone mid": "at the belt", "zone down": "down in the zone",
             "zone in": "in off the inner third", "zone middle": "over the middle", "zone away": "on the outer third",
             "chase above": "above the zone", "chase below": "below the zone", "chase in": "in off the plate",
             "chase away": "off the plate away"}
FAM_WORDS = {"fastball": "fastball", "cutter": "cutter", "breaking": "breaking ball", "offspeed": "changeup/splitter"}


def pct(x, d: int = 0) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{100 * x:.{d}f}%"


def woba3(x) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:.3f}".replace("0.", ".", 1)


STRIKE_GAP = 0.03     # an in-zone miss spot must beat the league's whiff rate there by 3 points (regressed)
AVOID_GAP = 0.020     # a damage spot must beat the league's xwOBA on contact there by .020 (regressed)


def plan(prof: dict) -> dict:
    """Draft plan lines with their evidence. Each is a hypothesis for the video check, never the scout's
    conclusion on its own. Picks:
    - put-away: the out-of-zone family x direction with the most regressed whiffs per pitch (25+ pitches)
    - strike: the in-zone family x region where his regressed whiff rate is furthest above the league's
      (15+ swings), if at least STRIKE_GAP above; otherwise the region where his regressed xwOBA on contact
      is furthest below the league's (10+ balls in play)
    - avoid: the in-zone family x region where his regressed xwOBA on contact is furthest above the
      league's (10+ balls in play); `clear` says whether it beats the league by AVOID_GAP
    - first pitch and two strikes: his regressed swing (chase) rate against the league's in that count."""
    fl = prof["famloc"]
    fl = fl[fl["family"] != "cutter"]                       # the plan speaks fastball / breaking / offspeed
    out = fl[(fl["loc_kind"] == "out") & (fl["pitches"] >= 25)]
    inz = fl[fl["loc_kind"] == "in"]
    lines = {}
    if len(out):
        r = out.loc[out["r_swstr"].idxmax()]
        lines["put_away"] = dict(family=r["family"], loc=r["loc"], r_swstr=r["r_swstr"], lg_swstr=r["lg_swstr"],
                                 r_chase=r["r_swing"], r_whiff=r["r_whiff"], pitches=int(r["pitches"]),
                                 swings=int(r["swings"]))
    s = inz[inz["swings"] >= 15]
    b = inz[inz["xw_n"] >= 10]
    if len(s):
        r = s.loc[(s["r_whiff"] - s["lg_whiff"]).idxmax()]
        if r["r_whiff"] - r["lg_whiff"] >= STRIKE_GAP or not len(b):
            lines["strike"] = dict(kind="whiff", family=r["family"], loc=r["loc"], r_whiff=r["r_whiff"],
                                   lg_whiff=r["lg_whiff"], swings=int(r["swings"]), r_xwcon=r["r_xwcon"],
                                   lg_xwcon=r["lg_xwcon"], bip=int(r["xw_n"]))
        else:                                               # no in-zone miss spot: his weakest contact instead
            r = b.loc[(b["r_xwcon"] - b["lg_xwcon"]).idxmin()]
            lines["strike"] = dict(kind="contact", family=r["family"], loc=r["loc"], r_whiff=r["r_whiff"],
                                   lg_whiff=r["lg_whiff"], swings=int(r["swings"]), r_xwcon=r["r_xwcon"],
                                   lg_xwcon=r["lg_xwcon"], bip=int(r["xw_n"]))
    if len(b):
        r = b.loc[(b["r_xwcon"] - b["lg_xwcon"]).idxmax()]
        lines["avoid"] = dict(family=r["family"], loc=r["loc"], r_xwcon=r["r_xwcon"], lg_xwcon=r["lg_xwcon"],
                              bip=int(r["xw_n"]), pitches=int(r["pitches"]),
                              clear=bool(r["r_xwcon"] - r["lg_xwcon"] >= AVOID_GAP))
    c = prof["count"].set_index("count_state")
    if "first pitch" in c.index:
        r = c.loc["first pitch"]
        lines["first_pitch"] = dict(r_swing=float(shrink("swing", r["swing"], r["pitches"], r["lg_swing"])),
                                    swing=r["swing"], lg_swing=r["lg_swing"], pitches=int(r["pitches"]),
                                    r_zone_swing=r["r_zone_swing"], lg_zone_swing=r["lg_zone_swing"])
    if "two strikes" in c.index:
        r = c.loc["two strikes"]
        lines["two_strikes"] = dict(r_chase=r["r_chase"], lg_chase=r["lg_chase"], out_pitches=int(r["out_pitches"]),
                                    r_whiff=r["r_whiff"], lg_whiff=r["lg_whiff"], swings=int(r["swings"]))
    return lines


def plan_text(prof: dict, lines: dict) -> list[str]:
    """The draft lines in words, each with its number and n (analyst wording)."""
    t = []
    fp = lines.get("first_pitch")
    if fp:
        gap = fp["r_swing"] - fp["lg_swing"]
        verdict = ("aggressive early: don't give in on 0-0" if gap >= 0.06 else
                   "takes early: steal strike one in the zone" if gap <= -0.06 else "average on 0-0")
        t.append(f"**First pitch:** swings {pct(fp['swing'])} (regressed {pct(fp['r_swing'])}, league "
                 f"{pct(fp['lg_swing'])}, n = {fp['pitches']} first pitches), {pct(fp['r_zone_swing'])} at strikes "
                 f"(league {pct(fp['lg_zone_swing'])}); {verdict}.")
    s = lines.get("strike")
    if s and s["kind"] == "whiff":
        t.append(f"**Get strikes:** {FAM_WORDS[s['family']]} {LOC_WORDS[s['loc']]}: misses on {pct(s['r_whiff'])} of "
                 f"swings regressed (league {pct(s['lg_whiff'])}, n = {s['swings']} swings), xwOBA on contact "
                 f"{woba3(s['r_xwcon'])} (league {woba3(s['lg_xwcon'])}, n = {s['bip']}).")
    elif s:
        t.append(f"**Get strikes:** no in-zone spot where he misses 3+ points more than the league; his weakest contact "
                 f"is on the {FAM_WORDS[s['family']]} {LOC_WORDS[s['loc']]}: xwOBA on contact {woba3(s['r_xwcon'])} "
                 f"regressed (league {woba3(s['lg_xwcon'])}, n = {s['bip']} balls in play).")
    p = lines.get("put_away")
    if p:
        rel = "more than" if p["r_swstr"] > p["lg_swstr"] + 0.01 else "fewer than" if p["r_swstr"] < p["lg_swstr"] - 0.01 \
            else "about as many as"
        t.append(f"**Put-away:** {FAM_WORDS[p['family']]} {LOC_WORDS[p['loc']]}: {pct(p['r_swstr'], 1)} swinging "
                 f"strikes per pitch regressed, {rel} the league's {pct(p['lg_swstr'], 1)} (chases {pct(p['r_chase'])}, "
                 f"misses {pct(p['r_whiff'])} of those swings; n = {p['pitches']} pitches, {p['swings']} swings).")
    a = lines.get("avoid")
    if a and a["clear"]:
        t.append(f"**Avoid:** {FAM_WORDS[a['family']]} {LOC_WORDS[a['loc']]}: xwOBA on contact {woba3(a['r_xwcon'])} "
                 f"regressed (league {woba3(a['lg_xwcon'])}, n = {a['bip']} balls in play).")
    elif a:
        t.append(f"**Avoid:** no in-zone spot where he beats the league's contact by .020; his closest is the "
                 f"{FAM_WORDS[a['family']]} {LOC_WORDS[a['loc']]} ({woba3(a['r_xwcon'])} regressed, league "
                 f"{woba3(a['lg_xwcon'])}, n = {a['bip']}).")
    k = lines.get("two_strikes")
    if k:
        gap = k["r_chase"] - k["lg_chase"]
        verdict = ("expands: bury the put-away pitch" if gap >= 0.04 else
                   "won't expand: finish him in or near the zone" if gap <= -0.04 else "league-average expansion")
        t.append(f"**Two strikes:** chases {pct(k['r_chase'])} regressed (league {pct(k['lg_chase'])}, "
                 f"n = {k['out_pitches']} pitches outside); misses {pct(k['r_whiff'])} of swings (league "
                 f"{pct(k['lg_whiff'])}, n = {k['swings']}); {verdict}.")
    return t


# ---------------------------------------------------------------- tables in markdown

def _cell(v, n, minimum, fmt) -> str:
    s = fmt(v)
    return s if n >= minimum else f"({s})"


def hitter_markdown(prof: dict) -> str:
    """The analyst card: overview, families, velocity, spin, counts, hands, bat tracking, draft lines."""
    o = prof["overview"].iloc[0]
    L = [f"### {prof['name']} ({prof['side']}), {prof['pa_team']} PA for the club, {prof['pa']} PA in all", ""]
    L += [f"- {x}" for x in plan_text(prof, plan(prof))]
    L += ["", "| Overall | Raw | Regressed | League | n |", "|---|---|---|---|---|"]
    rows = [("Swing %", "swing", "swing", "pitches"), ("Chase %", "chase", "chase", "out_pitches"),
            ("Zone swing %", "zone_swing", "zone_swing", "in_pitches"), ("Whiff per swing", "whiff", "whiff", "swings"),
            ("Zone contact %", "zone_contact", "zone_contact", "in_swings")]
    for lab, raw, reg, den in rows:
        L.append(f"| {lab} | {pct(o[raw])} | {pct(o['r_' + reg])} | {pct(o['lg_' + reg])} | {int(o[den]):,} |")
    L.append(f"| xwOBA on contact | {woba3(o['xwcon'])} | {woba3(o['r_xwcon'])} | {woba3(o['lg_xwcon'])} | {int(o['xw_n'])} |")
    L.append(f"| Hard-hit % | {pct(o['hard_rate'])} | {pct(o['r_hard_rate'])} | {pct(o['lg_hard_rate'])} | {int(o['hard_n'])} |")
    L.append(f"| K % / BB % | {pct(o['k_rate'])} / {pct(o['bb_rate'])} | | | {int(o['pa'])} PA |")
    L.append(f"| wOBA / xwOBA | {woba3(o['woba'])} / {woba3(o['xwoba'])} | | | {int(o['woba_n'])} |")
    L += ["", "| Pitch family | Pitches | Swings | Whiff (reg.) | Chase (reg.) | BIP | xwOBA con (reg.) |", "|---|---|---|---|---|---|---|"]
    for _, r in prof["family"].set_index("family").reindex(FAMILIES).dropna(subset=["pitches"]).iterrows():
        L.append(f"| {r.name} | {int(r['pitches'])} | {int(r['swings'])} | "
                 f"{_cell(r['r_whiff'], r['swings'], MIN_SWINGS, pct)} (lg {pct(r['lg_whiff'])}) | "
                 f"{_cell(r['r_chase'], r['out_pitches'], MIN_PITCHES, pct)} (lg {pct(r['lg_chase'])}) | {int(r['xw_n'])} | "
                 f"{_cell(r['r_xwcon'], r['xw_n'], MIN_BIP, woba3)} (lg {woba3(r['lg_xwcon'])}) |")
    L += ["", "| Location (regressed whiff / xwOBA con; n swings, BIP) | Fastball | Breaking | Changeup/splitter |",
          "|---|---|---|---|"]
    fl = prof["famloc"].set_index(["loc", "family"])
    for loc in ["zone up", "zone mid", "zone down", "zone in", "zone middle", "zone away",
                "chase above", "chase below", "chase in", "chase away"]:
        cells = []
        for fam in ("fastball", "breaking", "offspeed"):
            if (loc, fam) not in fl.index:
                cells.append("")
                continue
            r = fl.loc[(loc, fam)]
            cells.append(f"{_cell(r['r_whiff'], r['swings'], MIN_SWINGS, pct)} / {_cell(r['r_xwcon'], r['xw_n'], MIN_BIP, woba3)} "
                         f"({int(r['swings'])}, {int(r['xw_n'])})")
        L.append(f"| {LOC_WORDS[loc]} | " + " | ".join(cells) + " |")
    L += ["", "| Fastball velocity | Pitches | Swings | Whiff (reg.) | BIP | xwOBA con (reg.) |", "|---|---|---|---|---|---|"]
    for _, r in prof["velo"].set_index("velo_band").reindex(VELO_BANDS).dropna(subset=["pitches"]).iterrows():
        L.append(f"| {r.name} mph | {int(r['pitches'])} | {int(r['swings'])} | "
                 f"{_cell(r['r_whiff'], r['swings'], MIN_SWINGS, pct)} (lg {pct(r['lg_whiff'])}) | {int(r['xw_n'])} | "
                 f"{_cell(r['r_xwcon'], r['xw_n'], MIN_BIP, woba3)} (lg {woba3(r['lg_xwcon'])}) |")
    L += ["", "| Breaking-ball spin (third of its type) | Pitches | Swings | Whiff (reg.) | Chase (reg.) | BIP | xwOBA con (reg.) |",
          "|---|---|---|---|---|---|---|"]
    for _, r in prof["spin"].set_index("spin_band").reindex(SPIN_BANDS).dropna(subset=["pitches"]).iterrows():
        L.append(f"| {r.name} | {int(r['pitches'])} | {int(r['swings'])} | "
                 f"{_cell(r['r_whiff'], r['swings'], MIN_SWINGS, pct)} (lg {pct(r['lg_whiff'])}) | "
                 f"{_cell(r['r_chase'], r['out_pitches'], MIN_PITCHES, pct)} (lg {pct(r['lg_chase'])}) | {int(r['xw_n'])} | "
                 f"{_cell(r['r_xwcon'], r['xw_n'], MIN_BIP, woba3)} (lg {woba3(r['lg_xwcon'])}) |")
    L += ["", "| Pitcher hand | PA | xwOBA | K % | Whiff (reg.) | Chase (reg.) |", "|---|---|---|---|---|---|"]
    for _, r in prof["hand"].set_index("p_throws").reindex(["R", "L"]).dropna(subset=["pitches"]).iterrows():
        L.append(f"| vs {r.name}HP | {int(r['pa'])} | {woba3(r['xwoba'])} | {pct(r['k_rate'])} | "
                 f"{pct(r['r_whiff'])} | {pct(r['r_chase'])} |")
    pl = prof["platoon"]
    L.append(f"\nPlatoon split (xwOBA vs LHP minus vs RHP): observed {pl['observed_split']:+.3f}, league for his side "
             f"{pl['league_split']:+.3f}, regressed {pl['regressed_split']:+.3f} ({pl['pa_vs_l']} PA vs LHP, M = {pl['M']:,.0f}).")
    b = prof["bat"]
    L += ["", "| Bat tracking (competitive swings) | Value | League | Percentile | n |", "|---|---|---|---|---|"]
    lab = {"bat_speed": ("Bat speed", "mph"), "swing_length": ("Swing length", "ft"), "attack_angle": ("Attack angle", "deg"),
           "attack_dir": ("Attack direction (pull +)", "deg"), "tilt": ("Swing path tilt", "deg")}
    for k, (nm, u) in lab.items():
        x = b[k]
        L.append(f"| {nm} | {x['regressed']:.1f} {u} | {x['league']:.1f} | {x['pctl']:.0f} | {x['n']} |")
    tk = b["two_k"]
    L.append(f"\nTwo-strike bat speed {tk['bat_speed_2k']:.1f} mph (n = {tk['n_2k']}) vs {tk['bat_speed_other']:.1f} "
             f"otherwise (n = {tk['n_other']}); the league's hitters average a {tk['league_drop']:+.1f} mph change.")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- team summary

def team_table(profiles: list[dict]) -> pd.DataFrame:
    """One row per hitter: the numbers the team page sorts on."""
    rows = []
    for p in profiles:
        o = p["overview"].iloc[0]
        fp = plan(p).get("first_pitch", {})
        tk = plan(p).get("two_strikes", {})
        rows.append({"batter": p["batter"], "name": p["name"], "side": p["side"], "pa_team": p["pa_team"], "pa": p["pa"],
                     "xwoba": o["xwoba"], "woba": o["woba"], "k_rate": o["k_rate"], "bb_rate": o["bb_rate"],
                     "r_chase": o["r_chase"], "r_whiff": o["r_whiff"], "r_xwcon": o["r_xwcon"],
                     "r_hard": o["r_hard_rate"], "r_first_swing": fp.get("r_swing", np.nan),
                     "r_2k_chase": tk.get("r_chase", np.nan), "bat_speed": p["bat"]["bat_speed"]["regressed"],
                     "bat_speed_pctl": p["bat"]["bat_speed"]["pctl"], "swing_length": p["bat"]["swing_length"]["regressed"],
                     "attack_angle": p["bat"]["attack_angle"]["regressed"]})
    return pd.DataFrame(rows)


def team_rates(d: pd.DataFrame, batters: list[int], lg: dict) -> dict[str, pd.DataFrame]:
    """The lineup pooled (pitch-weighted) against the league, by family, out-of-zone direction and count."""
    x = d[d["batter"].isin(batters)]
    out = {"all": compare(sums(x), lg["all"], []),
           "family": compare(sums(x[x["family"].notna()], ["family"]), lg["family"], ["family"]),
           "count": compare(sums(x, ["count_state"]), lg["count"], ["count_state"]),
           "hand": compare(sums(x, ["p_throws"]), lg["hand"], ["p_throws"])}
    od = x[x["odir"].astype(str) != ""]
    lod = d[d["odir"].astype(str) != ""]
    out["odir"] = compare(sums(od, ["odir"]), sums(lod, ["odir"]), ["odir"], "chase")
    fl = famloc_sums(x[x["family"].notna()])
    out["famloc_out"] = compare(fl[fl["loc_kind"] == "out"].drop(columns=["loc_kind", "view"]),
                                lg["famloc"][lg["famloc"]["loc_kind"] == "out"].drop(columns=["loc_kind", "view"]),
                                ["family", "loc"], "chase")
    return out


# ---------------------------------------------------------------- figures

RING_W = 0.75                       # chase-quadrant depth in the drawing, in zone thirds


def _ring_polys(w: float = RING_W):
    """L-shaped chase quadrants around a 3x3 zone drawn on [0,3]x[0,3] (catcher's view, x to the right)."""
    lo, hi = -w, 3 + w
    return {
        ("up", "left"): [(lo, 1.5), (0, 1.5), (0, 3), (1.5, 3), (1.5, hi), (lo, hi)],
        ("up", "right"): [(hi, 1.5), (3, 1.5), (3, 3), (1.5, 3), (1.5, hi), (hi, hi)],
        ("down", "left"): [(lo, 1.5), (0, 1.5), (0, 0), (1.5, 0), (1.5, lo), (lo, lo)],
        ("down", "right"): [(hi, 1.5), (3, 1.5), (3, 0), (1.5, 0), (1.5, lo), (hi, lo)],
    }


def zone_panel(ax, cells: pd.DataFrame, value: str, league: str, n_col: str, minimum: int, span: float,
               cmap, fmt, side: str, title: str) -> None:
    """One hitter's 13 zones in the catcher's view. Inside is on the left for a right-handed hitter.
    `side` is the side to draw: pass a switch-hitter's main side (the one with more plate appearances);
    his other side is mirrored in, since cells are labeled in/away from the hitter. The number is the
    regressed rate; the color is its gap from the league's rate in the same zone (full color at `span`).
    Zones under the minimum are grey, the number in parentheses."""
    from matplotlib.patches import Polygon, Rectangle

    c = cells.set_index("cell")
    in_left = side != "L"
    colmap = {"in": 0 if in_left else 2, "mid": 1, "away": 2 if in_left else 0}
    rowmap = {"up": 2, "mid": 1, "down": 0}

    def style(key):
        v, lgv, n = c.loc[key, value], c.loc[key, league], c.loc[key, n_col]
        if n < minimum or not np.isfinite(v):
            return "#ececea", "#8a8a8a", f"({fmt(v)})", "normal"
        t = float(np.clip((v - lgv) / span, -1, 1))
        return cmap(0.5 + 0.5 * t), ("white" if abs(t) > 0.62 else "#1f1f1f"), fmt(v), "bold"

    w = RING_W
    for q, poly in _ring_polys().items():
        horiz = "in" if (q[1] == "left") == in_left else "away"
        fc, tc, txt, wt = style(f"chase {q[0]}-{horiz}")
        ax.add_patch(Polygon(poly, closed=True, fc=fc, ec="white", lw=1.4))
        tx = -w / 2 if q[1] == "left" else 3 + w / 2
        ty = 3 + w / 2 if q[0] == "up" else -w / 2
        ax.text(tx, ty, txt, ha="center", va="center", fontsize=7.5, color=tc, fontweight=wt)
    for r in ROWS:
        for col in COLS:
            fc, tc, txt, wt = style(f"{r}-{col}")
            x0, y0 = colmap[col], rowmap[r]
            ax.add_patch(Rectangle((x0, y0), 1, 1, fc=fc, ec="white", lw=1.4))
            ax.text(x0 + 0.5, y0 + 0.5, txt, ha="center", va="center", fontsize=9, color=tc, fontweight=wt)
    ax.add_patch(Rectangle((0, 0), 3, 3, fill=False, ec="#1f1f1f", lw=1.5))
    lo, hi = -w, 3 + w
    ax.text(lo, lo - 0.12, "IN" if in_left else "AWAY", ha="left", va="top", fontsize=6.5, color="#6b6b6b")
    ax.text(hi, lo - 0.12, "AWAY" if in_left else "IN", ha="right", va="top", fontsize=6.5, color="#6b6b6b")
    ax.set_xlim(lo - 0.05, hi + 0.05)
    ax.set_ylim(lo - 0.5, hi + 0.05)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=9.5, color="#1f1f1f", loc="left", pad=3)


def zone_figure(profiles: list[dict], metric: str, path: Path, title: str, subtitle: str) -> Path:
    """Small multiples, one panel per hitter: regressed whiff per swing (metric='whiff') or regressed xwOBA
    on contact (metric='xwcon') in Statcast's 13 zones. Blue is the pitcher's spot (more misses, less damage
    than the league in that zone), red the hitter's."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize
    from matplotlib.cm import ScalarMappable

    if metric == "whiff":
        value, league, n_col, minimum = "r_whiff", "lg_whiff", "swings", MIN_SWINGS
        fmt = lambda v: "" if not np.isfinite(v) else f"{100 * v:.0f}"  # noqa: E731
        cmap, span, unit = plt.get_cmap("RdBu"), 0.10, "points of whiff"
    else:
        value, league, n_col, minimum = "r_xwcon", "lg_xwcon", "xw_n", MIN_BIP
        fmt = lambda v: "" if not np.isfinite(v) else f"{v:.3f}"[1:]  # noqa: E731
        cmap, span, unit = plt.get_cmap("RdBu_r"), 0.080, "xwOBA"
    n = len(profiles)
    ncol = 3
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(9, 3.05 * nrow + 1.3), dpi=160)
    axes = np.atleast_1d(axes).ravel()
    for ax, p in zip(axes, profiles):
        draw = p.get("main_side", p["side"]) if p["side"] == "S" else p["side"]
        label = f"S, drawn {draw}" if p["side"] == "S" else f"{p['side']}H"
        zone_panel(ax, p["cell"], value, league, n_col, minimum, span, cmap, fmt, draw,
                   f"{p['name']} ({label}, {p['pa']} PA)")
    for ax in axes[n:]:
        ax.axis("off")
    top = 1 - 0.95 / (3.05 * nrow + 1.3)
    fig.text(0.015, 0.995, title, ha="left", va="top", fontsize=13, fontweight="bold", color="#1f1f1f")
    fig.text(0.015, 0.995 - 0.38 / (3.05 * nrow + 1.3), subtitle, ha="left", va="top", fontsize=8.2, color="#6b6b6b",
             linespacing=1.4)
    fig.tight_layout(rect=(0, 0.045, 1, top))
    cax = fig.add_axes((0.30, 0.018, 0.40, 0.012))
    sm = ScalarMappable(norm=Normalize(-span, span), cmap=cmap)
    cb = fig.colorbar(sm, cax=cax, orientation="horizontal")
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=7, colors="#6b6b6b", length=0)
    if metric == "whiff":
        cb.set_ticks([-span, 0, span], labels=[f"{-100 * span:.0f} pts", "league in that zone", f"+{100 * span:.0f} pts"])
        cax.set_title("hitter's spot (makes contact)          pitcher's spot (misses)", fontsize=7.5, color="#1f1f1f", pad=3)
    else:
        cb.set_ticks([-span, 0, span], labels=[f"-{span:.3f}"[0] + f"{span:.3f}"[1:], "league in that zone", f"+{span:.3f}"[0] + f"{span:.3f}"[1:]])
        cax.set_title("pitcher's spot (weak contact)          hitter's spot (damage)", fontsize=7.5, color="#1f1f1f", pad=3)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path


# ---------------------------------------------------------------- build

def _jsonable(prof: dict) -> dict:
    out = {}
    for k, v in prof.items():
        out[k] = v.replace({np.nan: None}).to_dict(orient="records") if isinstance(v, pd.DataFrame) else v
    return out


def build(team: str = "TB", season: int = 2026, n: int = 9, out_dir: Path = Path("data/advance"),
          fig_dir: Path | None = None, extra: list[int] | None = None, data: pd.DataFrame | None = None,
          names: dict | None = None, team_name: str | None = None) -> dict:
    """The whole packet: lineup, profiles, team rates, the analyst tables (markdown + JSON) and figures.
    `extra`: more batter ids to profile (cards only; the figures show the n regulars).
    `team_name`: the name used in figure titles (default: the abbreviation)."""
    d = prepare(data if data is not None else load_season(season))
    lg = league_tables(d)
    lu = lineup(d, team, n)
    ids = lu["batter"].astype(int).tolist()
    more = [int(b) for b in (extra or []) if int(b) not in ids]
    if names is None:
        try:
            from baseball.ingest.people import names as _names
            names = _names(ids + more)
        except FileNotFoundError:
            names = {}
    profs = [hitter_profile(d, b, lg, names.get(b, str(b)), team) for b in ids]
    extras = [hitter_profile(d, b, lg, names.get(b, str(b)), team) for b in more]
    tr = team_rates(d, ids, lg)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    md = [f"# Advance tables: {team} hitters, {season}\n"]
    md += [hitter_markdown(p) for p in profs + extras]
    (out_dir / f"tables-{team}-{season}.md").write_text("\n".join(md))
    tt = team_table(profs + extras)
    tt.to_csv(out_dir / f"team-{team}-{season}.csv", index=False)
    (out_dir / f"profiles-{team}-{season}.json").write_text(json.dumps(
        {"lineup": lu.to_dict(orient="records"), "profiles": [_jsonable(p) | {"plan": plan(p)} for p in profs + extras],
         "team": {k: v.replace({np.nan: None}).to_dict(orient="records") for k, v in tr.items()},
         "league_platoon": lg["platoon"].replace({np.nan: None}).to_dict(orient="records")},
        default=lambda o: o.item() if hasattr(o, "item") else str(o), indent=1))
    figs = {}
    if fig_dir is not None:
        sub = (f"Statcast, {season} regular season, all of each hitter's pitches. Catcher's view: the 3x3 strike zone and "
               "the four chase quadrants around it.\nThe number is regressed toward the league rate in that zone "
               "(Reliability Atlas constants); the color is the gap from it. Grey: under {}.")
        figs["whiff"] = zone_figure(profs, "whiff", Path(fig_dir) / f"{season}-advance-{team.lower()}-whiff.png",
                                    f"Where the {team_name or team} lineup misses: whiff per swing by zone (%)",
                                    sub.format(f"{MIN_SWINGS} swings"))
        figs["xwcon"] = zone_figure(profs, "xwcon", Path(fig_dir) / f"{season}-advance-{team.lower()}-damage.png",
                                    f"Where the {team_name or team} lineup does damage: xwOBA on contact by zone",
                                    sub.format(f"{MIN_BIP} balls in play"))
    return {"data": d, "league": lg, "lineup": lu, "profiles": profs, "extras": extras, "team": tr, "figures": figs,
            "team_table": tt}


def lg_whiff(lg: dict) -> float:
    return float(rates(lg["all"])["whiff"].iloc[0])


def lg_xwcon(lg: dict) -> float:
    return float(rates(lg["all"])["xwcon"].iloc[0])


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Advance-scouting packet on an opponent's hitters (Statcast seq data).")
    ap.add_argument("team", help="club abbreviation as Statcast writes it, e.g. TB")
    ap.add_argument("season", type=int)
    ap.add_argument("--n", type=int, default=9, help="hitters with the most PA for the club")
    ap.add_argument("--extra", type=int, nargs="*", default=[], help="more batter ids to card")
    ap.add_argument("--out", default="data/advance")
    ap.add_argument("--figures", default=None, help="folder for the zone figures (e.g. reports/figures)")
    ap.add_argument("--name", default=None, help="club name for figure titles, e.g. Rays")
    a = ap.parse_args(argv)
    r = build(a.team, a.season, a.n, Path(a.out), Path(a.figures) if a.figures else None, a.extra,
              team_name=a.name)
    print(r["team_table"].to_string(index=False))
    print(f"Tables and JSON in {a.out}; figures: {', '.join(str(p) for p in r['figures'].values()) or 'none'}")


if __name__ == "__main__":
    main()
