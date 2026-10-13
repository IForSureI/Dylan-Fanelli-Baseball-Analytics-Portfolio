"""Reliever evaluation: one comparison table for any list of pitchers, and 20-80 grades from data.

The question a club asks every winter: of the relievers it could acquire, which one is best for the role,
how sure is that, and what could change? This module puts every tool in the repo on one table:

- performance, regressed (`reliability.regress`): whiff, chase, CSW, zone, xwOBA on contact, hard-hit,
  ground-ball and run value, each with its 95% interval for his true level this season (and next season
  where year-to-year persistence is measured);
- stuff vs results (the edge engine's expected whiff, cross-fitted by pitcher): the gap by season and the
  engine's validated next-season whiff projection;
- velocity: the primary fastball's season-over-season change against the league's own change, regressed
  by games, and early-season vs late-season against the league's relievers;
- workload: appearances, back-to-backs, multi-inning outings, pitches per outing, fastball velocity on
  zero days' rest, and a leverage proxy;
- platoon: results by batter hand, with n;
- familiarity (`edge.familiarity`): how many same-type pitches his hitters had already seen, priced with
  the league study's per-pitch costs;
- pitch design (`development.levers`): 2025->26 shape changes beyond noise, with the levers study's
  evidence label;
- 20-80 grades per pitch (present, 2027, and a stuff-only grade), control, and a reliever OFP and role.

The 20-80 mapping (documented and tested; `grade_from_percentile`):
  The scouting scale is centered on 50 with about one standard deviation per 10 points among major leaguers
  (the 20-80 scouting convention: 10 grade points per standard deviation). So a pitch's grade is 50 + 10 z, where z is the
  normal quantile of the pitch's percentile among MLB pitches of the same Statcast type that season
  (pitcher-pitch rows with 50+ swings), rounded to the nearest 5 and clamped to 20-80:
      percentile  2.3  15.9  30.9  50  69.1  84.1  93.3  97.7  99.4  99.9
      grade        30    40    45  50    55    60    65    70    75    80
  Inputs: present = the pitch's 2026 whiff per swing regressed toward its type's league mean
  (`regress`, pitch-type M); 2027 = the edge engine's validated next-season whiff projection; stuff = the
  expected whiff from physics alone. Every reference pitch gets the same treatment, so like is compared
  with like.
  Limits: whiff per swing is one job of a pitch. It misses called strikes, weak contact and location, so it
  undergrades sinkers and strike-throwing cutters (they're graded only against their own type, which
  helps but doesn't fix it). It is a data-informed grade, not a live look: no delivery, deception, command
  within the zone or makeup. Control is graded separately from the unintentional walk rate (`control_grade`);
  it stands in for command, which the scouting formula asks for and public data can't measure.

Grain: input rows are pitches (the sequence copy, regular season). Output tables say their grain.
Conventions: flags once, rates after aggregation, every rate with its n, regular season only.
"""
from __future__ import annotations

from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

from baseball.evaluation.arsenal import SWINGS, WHIFFS

DATA = Path(__file__).resolve().parents[2] / "data"
EDGE = DATA / "edge"

FASTBALLS = ("FF", "SI", "FC")
PARAM_TYPE = {"KC": "CU"}           # knuckle-curves use the curveball constants (as the levers study pools them)
MAIN_TYPES = ("FF", "SI", "FC", "SL", "ST", "CU", "CH", "FS")
NON_PA_PREFIXES = ("caught_stealing", "pickoff", "stolen_base", "wild_pitch", "passed_ball", "other_advance", "truncated_pa")
OUTS = {"strikeout": 1, "strikeout_double_play": 2, "field_out": 1, "force_out": 1, "grounded_into_double_play": 2,
        "double_play": 2, "triple_play": 3, "fielders_choice_out": 1, "sac_fly": 1, "sac_bunt": 1,
        "sac_fly_double_play": 2, "sac_bunt_double_play": 2, "other_out": 1}

# ------------------------------------------------------------------ the 20-80 mapping

def percentile(reference, x: float) -> float:
    """Mid-rank percentile (0-100) of x in a reference sample: share below plus half the ties.
    Never exactly 0 or 100 for a value inside the sample, so the normal quantile stays finite."""
    ref = np.asarray(reference, float)
    ref = ref[np.isfinite(ref)]
    if len(ref) == 0 or x is None or not np.isfinite(x):
        return float("nan")
    below = np.sum(ref < x)
    ties = np.sum(ref == x)
    return float(100 * (below + 0.5 * ties + 0.5) / (len(ref) + 1))


def to_scale(raw: float) -> int:
    """Round to the nearest 5 and clamp to 20-80 (scouting-report grades.py convention)."""
    return int(max(20, min(80, 5 * np.floor(raw / 5 + 0.5))))


def grade_from_percentile(pct: float) -> int | None:
    """20-80 grade = 50 + 10 z, z = normal quantile of the percentile (one SD per 10 points), to the nearest 5."""
    if pct is None or not np.isfinite(pct):
        return None
    p = min(max(pct / 100, 1e-6), 1 - 1e-6)
    return to_scale(50 + 10 * NormalDist().inv_cdf(p))


# Walk-rate anchors (BB% of PA -> grade), from my scouting grading notes:
# under ~5% = 70-80, ~5-6.5% = 60, ~7.5-8.5% = 50, ~10-11% = 40, 12%+ = 30. Interpolated between the
# midpoints below; 20 at 15%+.
CONTROL_ANCHORS = [(4.0, 75), (5.75, 60), (8.0, 50), (10.5, 40), (12.0, 30), (15.0, 20)]


def control_grade(bb_pct: float) -> int | None:
    """Control grade from walk rate (percent of PA), interpolated between the anchors, to the nearest 5."""
    if bb_pct is None or not np.isfinite(bb_pct):
        return None
    xs, gs = zip(*CONTROL_ANCHORS)
    return to_scale(float(np.interp(bb_pct, xs, gs)))


ROLE_BY_OFP_RELIEVER = {60: "Elite closer", 55: "Closer / high-leverage reliever", 50: "Setup / high-leverage reliever",
                        45: "Middle reliever", 40: "Up-and-down reliever", 30: "Organizational arm"}


def reliever_ofp(pitch_grades: dict[str, int], control: int) -> dict:
    """Reliever OFP from my scouting grading notes: min(60, 0.55 best + 0.35 second
    + 0.10 control), to the nearest 5. Relief OFPs top out at 60 (grading-scale §5.2). Needs two graded pitches."""
    g = sorted((v for v in pitch_grades.values() if v is not None), reverse=True)
    if len(g) < 2 or control is None:
        return {"ofp": None, "role": None, "raw": None}
    raw = min(60.0, 0.55 * g[0] + 0.35 * g[1] + 0.10 * control)
    ofp = to_scale(raw)
    role = ROLE_BY_OFP_RELIEVER[max(k for k in ROLE_BY_OFP_RELIEVER if k <= ofp)] if ofp >= 30 else "Organizational arm"
    return {"ofp": ofp, "role": role, "raw": raw}


# ------------------------------------------------------------------ flags and roles

def flag(p: pd.DataFrame) -> pd.DataFrame:
    """Flags once on every row (regular season only). Adds the pitching team and whether the pitcher was in
    relief (not his team's first pitcher of the game; position players pitching count as relief, a negligible
    share of relief pitches).

    Rows with no pitch thrown (description automatic_ball / automatic_strike: intentional walks and pitch-clock
    violations) are kept, because they end plate appearances (every intentional walk is one), but `pitch` is
    False on them, so pitch counts, swings, zone and run value ignore them."""
    d = p[p["game_type"].eq("R")].copy() if "game_type" in p else p.copy()
    d["pitch"] = ~d["description"].isin(("automatic_ball", "automatic_strike"))
    d["season"] = d["game_year"].astype(int)
    d["swing"] = d["description"].isin(SWINGS)
    d["whiff"] = d["description"].isin(WHIFFS)
    d["called"] = d["description"].eq("called_strike")
    d["csw"] = d["called"] | d["whiff"]
    d["in_zone"] = d["zone"].between(1, 9)
    d["out_zone"] = d["zone"].notna() & ~d["in_zone"]
    d["chase"] = d["swing"] & d["out_zone"]
    d["bip"] = d["type"].eq("X")
    d["xwoba_bip"] = d["estimated_woba_using_speedangle"].where(d["bip"])
    d["hard"] = d["bip"] & d["launch_speed"].ge(95)
    d["has_ev"] = d["bip"] & d["launch_speed"].notna()
    d["gb"] = d["bip"] & d["bb_type"].eq("ground_ball") if "bb_type" in d else False
    d["has_bbt"] = d["bip"] & d["bb_type"].notna() if "bb_type" in d else False
    ev = d["events"].fillna("")
    d["pa"] = ev.ne("") & ~ev.str.startswith(NON_PA_PREFIXES)
    d["k"] = ev.isin(("strikeout", "strikeout_double_play"))
    d["bb"] = ev.isin(("walk", "intent_walk"))
    d["ubb"] = ev.eq("walk")                          # unintentional walks: the control input
    d["outs"] = ev.map(OUTS).fillna(0) + ev.str.startswith(("caught_stealing", "pickoff_caught")).astype(int)
    # xwOBA per PA: the expected value on balls in play, the actual wOBA value otherwise (walks, strikeouts)
    d["xwoba_pa"] = np.where(d["bip"], d["estimated_woba_using_speedangle"], d["woba_value"]).astype(float)
    d["xwoba_den"] = d["woba_denom"].fillna(0).astype(float)
    d["rv"] = -d["delta_run_exp"]                     # pitcher's view
    d["team"] = np.where(d["inning_topbot"].eq("Top"), d["home_team"], d["away_team"])
    d = d.sort_values(["game_pk", "at_bat_number", "pitch_number"])
    first = d.groupby(["game_pk", "team"])["pitcher"].transform("first")
    d["relief"] = d["pitcher"].ne(first)
    return d.reset_index(drop=True)


def primary_fastball(d: pd.DataFrame) -> pd.Series:
    """Each pitcher-season's most-thrown of FF/SI/FC (index: pitcher, season)."""
    fb = d[d["pitch_type"].isin(FASTBALLS)]
    n = fb.groupby(["pitcher", "season", "pitch_type"]).size().rename("n").reset_index()
    return n.sort_values("n").groupby(["pitcher", "season"]).tail(1).set_index(["pitcher", "season"])["pitch_type"]


# ------------------------------------------------------------------ the season line

def season_line(d: pd.DataFrame) -> pd.DataFrame:
    """Grain: pitcher x season. Counts and rates from summed numerators and denominators."""
    g = d.groupby(["pitcher", "season"])
    out = g.agg(player_name=("player_name", "last"), p_throws=("p_throws", "last"), games=("game_pk", "nunique"),
                relief_games=("game_pk", lambda s: s[d.loc[s.index, "relief"]].nunique()),
                pitches=("pitch", "sum"), pa=("pa", "sum"), outs=("outs", "sum"), k=("k", "sum"), bb=("bb", "sum"),
                ubb=("ubb", "sum"),
                swings=("swing", "sum"), whiffs=("whiff", "sum"), csw=("csw", "sum"), in_zone=("in_zone", "sum"),
                zone_n=("zone", "count"), out_zone=("out_zone", "sum"), chases=("chase", "sum"), bip=("bip", "sum"),
                xwoba_sum=("xwoba_bip", "sum"), xwoba_n=("xwoba_bip", "count"), hard=("hard", "sum"),
                ev_n=("has_ev", "sum"), gb=("gb", "sum"), bbt_n=("has_bbt", "sum"), rv=("rv", "sum"),
                rv_n=("rv", "count"), xwoba_pa_sum=("xwoba_pa", lambda s: np.nansum(s * d.loc[s.index, "xwoba_den"])),
                xwoba_den=("xwoba_den", "sum"))
    out["ip"] = out["outs"] // 3 + (out["outs"] % 3) / 10          # baseball notation (approximate: event outs)
    out["k_pct"] = 100 * out["k"] / out["pa"]
    out["bb_pct"] = 100 * out["bb"] / out["pa"]
    out["ubb_pct"] = 100 * out["ubb"] / out["pa"]
    out["k_bb_pct"] = out["k_pct"] - out["bb_pct"]
    out["whiff"] = out["whiffs"] / out["swings"]
    out["csw_rate"] = out["csw"] / out["pitches"]
    out["zone"] = out["in_zone"] / out["zone_n"]
    out["chase"] = out["chases"] / out["out_zone"]
    out["xwoba_con"] = out["xwoba_sum"] / out["xwoba_n"]
    out["hard_hit"] = out["hard"] / out["ev_n"]
    out["gb_rate"] = out["gb"] / out["bbt_n"]
    out["rv100"] = 100 * out["rv"] / out["rv_n"]
    out["xwoba"] = out["xwoba_pa_sum"] / out["xwoba_den"]
    return out.reset_index()


# metric id in reliability_params.json -> (rate column, denominator column)
REGRESS = {"whiff": ("whiff", "swings"), "chase": ("chase", "out_zone"), "csw": ("csw_rate", "pitches"),
           "zone": ("zone", "zone_n"), "xwoba_con": ("xwoba_con", "xwoba_n"), "hard_hit": ("hard_hit", "ev_n"),
           "gb": ("gb_rate", "bbt_n"), "rv100": ("rv100", "rv_n")}


def regressed(line: pd.DataFrame, league: dict[str, float], params: pd.DataFrame | None = None) -> pd.DataFrame:
    """Every REGRESS metric for every row of a season line: observed, n, estimate and 95% interval for his true
    level over the sample's season, and next season where year-to-year persistence is measured (else NaN).
    league: metric -> league mean (e.g. from data/edge/reliability/league_means.parquet). Grain: pitcher x
    season x metric."""
    from baseball.evaluation.reliability import load_params, regress

    params = load_params() if params is None else params
    rows = []
    for metric, (col, den) in REGRESS.items():
        mid = f"pitcher/{metric}"
        obs, n = line[col].to_numpy(float), line[den].to_numpy(float)
        cur = regress(mid, obs, n, league[metric], params=params)
        try:
            nxt = regress(mid, obs, n, league[metric], horizon="next_season", params=params)
        except ValueError:
            nxt = pd.DataFrame({"estimate": np.nan, "lo": np.nan, "hi": np.nan}, index=range(len(line)))
        rows.append(pd.DataFrame({"pitcher": line["pitcher"].to_numpy(), "season": line["season"].to_numpy(), "metric": metric,
                                  "observed": obs, "n": n, "league": league[metric], "M": float(params.loc[mid, "M"]),
                                  "weight": cur["weight"].to_numpy(), "estimate": cur["estimate"].to_numpy(),
                                  "lo": cur["lo"].to_numpy(), "hi": cur["hi"].to_numpy(),
                                  "next_estimate": nxt["estimate"].to_numpy(), "next_lo": nxt["lo"].to_numpy(),
                                  "next_hi": nxt["hi"].to_numpy()}))
    return pd.concat(rows, ignore_index=True)


def league_means(season: int, path: Path | None = None) -> dict[str, float]:
    """League means (all pitchers) for the regressed metrics, from the Reliability Atlas tables."""
    lm = pd.read_parquet(path or EDGE / "reliability" / "league_means.parquet")
    lm = lm[lm["season"].eq(season)].set_index("metric")["mean"]
    out = {m: float(lm[f"pitcher/{m}"]) for m in REGRESS if f"pitcher/{m}" in lm}
    for pt in MAIN_TYPES:
        key = f"pitcher/{pt}/whiff"
        if key in lm:
            out[f"{pt}/whiff"] = float(lm[key])
        if f"pitcher/{pt}/velo" in lm:
            out[f"{pt}/velo"] = float(lm[f"pitcher/{pt}/velo"])
    return out


# ------------------------------------------------------------------ pitch grades

def _ptype(pt: str) -> str:
    return PARAM_TYPE.get(pt, pt)


def regress_pitch_whiff(table: pd.DataFrame, league: dict[str, float], params: pd.DataFrame | None = None) -> pd.Series:
    """Regressed whiff% (0-100) for every pitcher-pitch row of a stuff table (pitch-type constants)."""
    from baseball.evaluation.reliability import load_params, regress

    params = load_params() if params is None else params
    out = pd.Series(np.nan, index=table.index)
    for pt, g in table.groupby(table["pitch_type"].map(_ptype)):
        mid = f"pitcher/{pt}/whiff"
        if mid not in params.index or f"{pt}/whiff" not in league:
            mid, mean = "pitcher/whiff", league["whiff"]
        else:
            mean = league[f"{pt}/whiff"]
        r = regress(mid, g["whiffs"] / g["swings"], g["swings"], mean, params=params)
        out.loc[g.index] = 100 * r["estimate"].to_numpy()
    return out


def pitch_grades(stuff: pd.DataFrame, projection: pd.DataFrame | None, ids, league: dict[str, float],
                 params: pd.DataFrame | None = None) -> pd.DataFrame:
    """20-80 grades per pitch for the pitchers in `ids`, against every MLB pitch of the same type in `stuff`.

    stuff      : an edge-engine stuff table for one season (pitcher x pitch type, 50+ swings: whiffs, swings,
                 whiff_pct, x_whiff_pct).
    projection : the engine's projection table for the next season (proj_whiff_pct), or None.
    Grain: pitcher x pitch type. Columns: present / 2027 / stuff grades with the percentiles behind them.
    """
    s = stuff.copy()
    s["group"] = s["pitch_type"].map(_ptype)
    s["reg_whiff"] = regress_pitch_whiff(s, league, params)
    if projection is not None:
        s = s.merge(projection[["pitcher", "pitch_type", "proj_whiff_pct"]], on=["pitcher", "pitch_type"], how="left")
    else:
        s["proj_whiff_pct"] = np.nan
    rows = []
    for _, r in s[s["pitcher"].isin(list(ids))].iterrows():
        ref = s[s["group"].eq(r["group"])]
        pct_now = percentile(ref["reg_whiff"], r["reg_whiff"])
        pct_next = percentile(ref["proj_whiff_pct"], r["proj_whiff_pct"])
        pct_stuff = percentile(ref["x_whiff_pct"], r["x_whiff_pct"])
        rows.append({"pitcher": r["pitcher"], "pitch_type": r["pitch_type"], "swings": int(r["swings"]),
                     "whiff_pct": r["whiff_pct"], "reg_whiff_pct": r["reg_whiff"], "x_whiff_pct": r["x_whiff_pct"],
                     "proj_whiff_pct": r["proj_whiff_pct"], "reference_pitches": int(len(ref)),
                     "pct_present": pct_now, "grade_present": grade_from_percentile(pct_now),
                     "pct_2027": pct_next, "grade_2027": grade_from_percentile(pct_next),
                     "pct_stuff": pct_stuff, "grade_stuff": grade_from_percentile(pct_stuff)})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ velocity

def velocity_read(d: pd.DataFrame, ids, season: int, min_pitches: int = 100, params: pd.DataFrame | None = None,
                  early=(3, 4, 5), late=(8, 9), min_games: int = 5) -> pd.DataFrame:
    """Primary-fastball velocity for each pitcher in `ids`: this season (regressed by games), last season on the
    same pitch type, the change, the league's median change for that type (pitchers with min_pitches of it in
    both seasons) and his change net of it; then early season (months `early`) vs late (`late`), against the
    median of the same change for every reliever with min_games outings in each window.
    d: flagged pitches covering `season` and `season - 1`. Grain: pitcher."""
    from baseball.evaluation.reliability import load_params, regress

    params = load_params() if params is None else params
    prim = primary_fastball(d[d["season"].eq(season)])
    means = d.groupby(["pitcher", "season", "pitch_type"]).agg(velo=("release_speed", "mean"), n=("release_speed", "count"),
                                                                 games=("game_pk", "nunique"))
    both = means[means["n"] >= min_pitches].reset_index()
    wide = both.pivot_table(index=["pitcher", "pitch_type"], columns="season", values="velo")
    league = {}
    if season - 1 in wide and season in wide:
        ch = (wide[season] - wide[season - 1]).dropna()
        league = ch.groupby(level="pitch_type").median().to_dict()
    # early vs late, per game means (velocity's noise is mostly day to day), relievers only
    cur = d[d["season"].eq(season) & d["relief"]].copy()
    cur["month"] = pd.to_datetime(cur["game_date"]).dt.month
    cur = cur.join(prim.rename("prim"), on=["pitcher", "season"])
    fb = cur[cur["pitch_type"].eq(cur["prim"])]
    gm = fb.groupby(["pitcher", "game_pk"]).agg(velo=("release_speed", "mean"), month=("month", "first"))
    gm["window"] = np.where(gm["month"].isin(early), "early", np.where(gm["month"].isin(late), "late", None))
    win = gm.dropna(subset=["window"]).groupby(["pitcher", "window"])["velo"].agg(["mean", "size"]).unstack()
    win = win.reindex(columns=pd.MultiIndex.from_product([["mean", "size"], ["early", "late"]]))
    win[[("size", "early"), ("size", "late")]] = win[[("size", "early"), ("size", "late")]].fillna(0)
    ok = (win[("size", "early")] >= min_games) & (win[("size", "late")] >= min_games)
    late_change = (win[("mean", "late")] - win[("mean", "early")])
    league_late = float(late_change[ok].median()) if ok.any() else np.nan
    rows = []
    for pid in ids:
        if (pid, season) not in prim.index:
            continue
        pt = prim.loc[(pid, season)]
        m = means.loc[(pid, season, pt)]
        prev = means.loc[(pid, season - 1, pt)] if (pid, season - 1, pt) in means.index else None
        mid = f"pitcher/{_ptype(pt)}/velo"
        lm = float(d.loc[d["season"].eq(season) & d["pitch_type"].eq(pt), "release_speed"].mean())
        r = regress(mid, m["velo"], m["n"], lm, games=m["games"], params=params)
        change = (m["velo"] - prev["velo"]) if prev is not None else np.nan
        rows.append({"pitcher": pid, "pitch_type": pt, "velo": m["velo"], "pitches": int(m["n"]), "games": int(m["games"]),
                     "velo_reg": float(r["estimate"].iloc[0]), "velo_lo": float(r["lo"].iloc[0]), "velo_hi": float(r["hi"].iloc[0]),
                     "velo_prev": prev["velo"] if prev is not None else np.nan, "change": change,
                     "league_change": league.get(pt, np.nan), "net_change": change - league.get(pt, np.nan),
                     "early": win.loc[pid, ("mean", "early")] if pid in win.index else np.nan,
                     "late": win.loc[pid, ("mean", "late")] if pid in win.index else np.nan,
                     "early_games": win.loc[pid, ("size", "early")] if pid in win.index else 0,
                     "late_games": win.loc[pid, ("size", "late")] if pid in win.index else 0,
                     "late_minus_early": late_change.get(pid, np.nan), "league_late_minus_early": league_late,
                     "relievers_in_baseline": int(ok.sum())})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ workload

def workload(d: pd.DataFrame, ids, season: int) -> pd.DataFrame:
    """Usage and durability signals from game logs (no injury inference). Grain: pitcher.
    back_to_back: outings the day after an outing. multi_inning: outings with 4+ outs recorded.
    velo_b2b_minus_rest: primary-fastball velocity in back-to-back outings minus other outings (game means).
    leverage_proxy: his mean |win-probability swing| per PA over the league's relief mean (realized, not Tango's LI)."""
    cur = d[d["season"].eq(season)]
    prim = primary_fastball(cur)
    rel = cur[cur["relief"]]
    pa_rows = rel[rel["pa"]]
    # win-probability swing per PA, summed over its pitches (delta_home_win_exp is per pitch)
    swing = rel.groupby(["pitcher", "game_pk", "at_bat_number"])["delta_home_win_exp"].sum().abs()
    league_swing = float(swing.mean()) if len(swing) else np.nan
    rows = []
    for pid in ids:
        p = cur[cur["pitcher"].eq(pid)]
        if p.empty:
            continue
        g = p.groupby("game_pk").agg(date=("game_date", "first"), pitches=("pitch", "sum"), outs=("outs", "sum"),
                                     relief=("relief", "first"))
        g["date"] = pd.to_datetime(g["date"])
        g = g.sort_values("date")
        g["rest"] = g["date"].diff().dt.days
        g["b2b"] = g["rest"].eq(1)
        pt = prim.get((pid, season))
        fbv = p[p["pitch_type"].eq(pt)].groupby("game_pk")["release_speed"].mean()
        g = g.join(fbv.rename("fb_velo"))
        b2b_v = g.loc[g["b2b"], "fb_velo"]
        rest_v = g.loc[~g["b2b"], "fb_velo"]
        ps = swing.loc[pid] if pid in swing.index.get_level_values(0) else pd.Series(dtype=float)
        rows.append({"pitcher": pid, "games": len(g), "relief_games": int(g["relief"].sum()),
                     "pitches_per_game": g["pitches"].mean(), "max_pitches": int(g["pitches"].max()),
                     "back_to_back": int(g["b2b"].sum()), "multi_inning": int((g["outs"] >= 4).sum()),
                     "three_in_four_days": int(sum(((g["date"] > dt - pd.Timedelta(days=4)) & (g["date"] <= dt)).sum() >= 3
                                                   for dt in g["date"])),
                     "velo_b2b_minus_rest": b2b_v.mean() - rest_v.mean() if len(b2b_v) and len(rest_v) else np.nan,
                     "b2b_games_with_velo": int(b2b_v.notna().sum()),
                     "first_game": g["date"].min().date().isoformat(), "last_game": g["date"].max().date().isoformat(),
                     "longest_gap_days": int(g["rest"].max()) if g["rest"].notna().any() else 0,
                     "leverage_proxy": float(ps.mean() / league_swing) if len(ps) and league_swing > 0 else np.nan,
                     "relief_pa": int(pa_rows["pitcher"].eq(pid).sum())})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ platoon

def platoon(d: pd.DataFrame, ids, season: int, league_whiff: float, params: pd.DataFrame | None = None) -> pd.DataFrame:
    """Results by batter hand: PA, K%, BB%, xwOBA per PA, whiff% raw and regressed (pitcher whiff M). Grain:
    pitcher x batter hand."""
    from baseball.evaluation.reliability import load_params, regress

    params = load_params() if params is None else params
    cur = d[d["season"].eq(season) & d["pitcher"].isin(list(ids))]
    g = cur.groupby(["pitcher", "stand"]).agg(pa=("pa", "sum"), k=("k", "sum"), bb=("bb", "sum"), swings=("swing", "sum"),
                                             whiffs=("whiff", "sum"), xw=("xwoba_pa", lambda s: np.nansum(s * cur.loc[s.index, "xwoba_den"])),
                                             den=("xwoba_den", "sum"), pitches=("pitch_type", "size")).reset_index()
    g["k_pct"] = 100 * g["k"] / g["pa"]
    g["bb_pct"] = 100 * g["bb"] / g["pa"]
    g["xwoba"] = g["xw"] / g["den"]
    g["whiff_pct"] = 100 * g["whiffs"] / g["swings"]
    g["whiff_reg"] = 100 * regress("pitcher/whiff", g["whiffs"] / g["swings"], g["swings"], league_whiff, params=params)["estimate"].to_numpy()
    tot = g.groupby("pitcher")["pitches"].transform("sum")
    g["share_of_pitches"] = 100 * g["pitches"] / tot
    sd = cur[cur["xwoba_den"] > 0].groupby(["pitcher", "stand"])["xwoba_pa"].std()
    g["xwoba_se"] = [sd.get((r.pitcher, r.stand), np.nan) / np.sqrt(r.den) for r in g.itertuples()]
    return g.drop(columns=["xw", "den"])


def xwoba_stats(rows: pd.DataFrame) -> dict:
    """xwOBA per PA (expected value on balls in play, actual wOBA value otherwise; wOBA-denominator PAs only):
    mean, per-PA SD, n and standard error. Rows: flagged pitches."""
    r = rows[rows["xwoba_den"] > 0]
    v = r["xwoba_pa"].to_numpy(float)
    n = len(v)
    sd = float(np.std(v, ddof=1)) if n > 1 else float("nan")
    return {"mean": float(v.mean()) if n else float("nan"), "sd": sd, "n": n, "se": sd / np.sqrt(n) if n else float("nan")}


def xwoba_diff_test(a: dict, b: dict) -> dict:
    """Two-sample z-test on xwOBA per PA (a minus b), from xwoba_stats() outputs. PAs are treated as
    independent, which slightly understates the SE (the same hitters and games recur)."""
    diff = a["mean"] - b["mean"]
    se = float(np.sqrt(a["se"] ** 2 + b["se"] ** 2))
    z = diff / se
    return {"diff": diff, "se": se, "z": z, "p": 2 * (1 - NormalDist().cdf(abs(z)))}


def usage(d: pd.DataFrame, ids, season: int, min_n: int = 20) -> pd.DataFrame:
    """Pitch mix overall and by batter hand, with velocity and shape (arsenal conventions: usage before the
    floor; arm-side horizontal break +). Grain: pitcher x pitch type."""
    cur = d[d["season"].eq(season) & d["pitcher"].isin(list(ids)) & d["pitch_type"].notna()].copy()
    cur["ivb_in"] = cur["pfx_z"] * 12
    cur["hb_arm_in"] = np.where(cur["p_throws"].eq("R"), -cur["pfx_x"], cur["pfx_x"]) * 12
    g = cur.groupby(["pitcher", "pitch_type"]).agg(n=("pitch_type", "size"), velo=("release_speed", "mean"),
                                                  spin=("release_spin_rate", "mean"), ivb_in=("ivb_in", "mean"),
                                                  hb_arm_in=("hb_arm_in", "mean"), swings=("swing", "sum"), whiffs=("whiff", "sum"))
    g["usage_pct"] = 100 * g["n"] / g.groupby(level="pitcher")["n"].transform("sum")
    hand = cur.groupby(["pitcher", "pitch_type", "stand"]).size().unstack(fill_value=0)
    for h in ("L", "R"):
        col = hand[h] if h in hand else 0
        g[f"vs_{h}HH_pct"] = 100 * col / (hand[h].groupby(level="pitcher").transform("sum") if h in hand else 1)
    g["whiff_pct"] = 100 * g["whiffs"] / g["swings"].replace(0, np.nan)
    return g[g["n"] >= min_n].reset_index()


# ------------------------------------------------------------------ stuff vs results across seasons

def gap_history(stuff_tables: dict[int, pd.DataFrame], ids, projection: pd.DataFrame | None = None) -> pd.DataFrame:
    """Swing-weighted actual vs expected whiff per pitcher and season (pitch types with 50+ swings), plus the
    engine's next-season whiff projection (swing-weighted over his current pitches). Grain: pitcher."""
    rows = []
    for season, t in stuff_tables.items():
        t = t[t["pitcher"].isin(list(ids))]
        if t.empty:
            continue
        a = t.assign(xw=t["x_whiff_pct"] * t["swings"]).groupby("pitcher").agg(swings=("swings", "sum"), whiffs=("whiffs", "sum"),
                                                                                 xw=("xw", "sum"))
        a["season"] = season
        rows.append(a.reset_index())
    h = pd.concat(rows, ignore_index=True)
    h["whiff_pct"] = 100 * h["whiffs"] / h["swings"]
    h["x_whiff_pct"] = h["xw"] / h["swings"]
    h["gap"] = h["whiff_pct"] - h["x_whiff_pct"]
    out = h.pivot_table(index="pitcher", columns="season", values=["whiff_pct", "x_whiff_pct", "gap", "swings"])
    out.columns = [f"{m}_{s}" for m, s in out.columns]
    if projection is not None:
        pr = projection[projection["pitcher"].isin(list(ids))]
        pr = pr.assign(pw=pr["proj_whiff_pct"] * pr["swings"]).groupby("pitcher").agg(pw=("pw", "sum"), sw=("swings", "sum"))
        out["proj_whiff_pct"] = pr["pw"] / pr["sw"]
    return out.reset_index()


# ------------------------------------------------------------------ familiarity

# Whiff points per swing per earlier same-type pitch, relative to an earlier pitch of another type, by group:
# earlier PAs today (Finding 1) and earlier games this season (Finding 1, "the other two windows").
# Source: reports/2026-league-pitch-familiarity.md (2024-26, two-way fixed effects, pitcher-clustered SEs).
FAMILIARITY_COST = {
    "prev_same": {"fastball": -0.70, "breaking": -0.91, "offspeed": -1.87, "cutter": -0.50},
    "game_same": {"fastball": -0.22, "breaking": -0.36, "offspeed": -0.77, "cutter": -0.37},
}


def familiarity_load(p: pd.DataFrame, ids) -> pd.DataFrame:
    """How many same-type pitches his hitters had already seen from him (earlier PAs today, earlier games this
    season), per pitch, and the whiff-point cost those exposures carry at the league study's rates. Input: the
    raw sequence rows (with batter) of the pitchers' seasons. Grain: pitcher x pitch group."""
    from baseball.edge.familiarity import GROUP, exposures

    sub = p[p["pitcher"].isin(list(ids))]
    if "game_type" in sub:
        sub = sub[sub["game_type"].eq("R")]
    e = exposures(sub)
    e["group"] = e["pitch_type"].map(GROUP)
    e = e[e["group"].notna()]
    g = e.groupby(["pitcher", "group"]).agg(pitches=("pitch_type", "size"), prev_same=("prev_same", "mean"),
                                           game_same=("game_same", "mean")).reset_index()
    g["cost_whiff_pts"] = [r.prev_same * FAMILIARITY_COST["prev_same"][r.group] + r.game_same * FAMILIARITY_COST["game_same"][r.group]
                           for r in g.itertuples()]
    g["usage_pct"] = 100 * g["pitches"] / g.groupby("pitcher")["pitches"].transform("sum")
    return g


# ------------------------------------------------------------------ pitch design

# Year-two labels from the levers study's persistence table (reports/2026-pitch-design-levers.md, "Persistence";
# 2024->25 changes followed into 2026) and its robustness note on slider spin. Levers without a row weren't followed.
LEVER_PERSISTENCE = {
    ("FF", "ivb"): "point estimate held; interval can't exclude a full fade",
    ("FF", "spin"): "whiff gain held; run value not shown to last (borderline)",
    ("FF", "velo"): "not shown to last (borderline); about half the fade is velocity reverting",
    ("SL", "ivb"): "not shown in year one in this sample; not shown to last (borderline)",
    ("SL", "gap"): "not shown to last (borderline)",
    ("SL", "arm"): "year-two gain, borderline",
    ("SL", "spin"): "unstable across season pairs (robustness)",
    ("ST", "hb"): "run value not shown to last",
}

NET = {"velo": "net_velo", "ivb": "net_ivb", "hb": "net_hb", "spin": "net_spin", "gap": "net_gap", "sep": "net_sep",
       "rel_z": "net_rel_z", "rel_x": "net_rel_x", "ext": "net_ext", "arm": "net_arm"}


def lever_read(pairs: pd.DataFrame, answer: pd.DataFrame, ids, season: int) -> pd.DataFrame:
    """Shape changes from season-1 to season beyond the levers study's noise threshold (net of the league), with
    the study's payoff per unit and evidence label, and the implied whiff change (net change / unit x payoff:
    an association from the league study, not a forecast for him). Grain: pitcher x pitch type x lever."""
    from baseball.development.levers import LEVERS, display, levers_for

    pr = pairs[pairs["pitcher"].isin(list(ids)) & pairs["season_1"].eq(season)]
    ans = answer.set_index(["pitch_type", "lever"])
    rows = []
    for _, r in pr.iterrows():
        pt = r["pitch_type"]
        for lv in levers_for(pt):
            if not bool(r.get(f"chg_{lv}", False)):
                continue
            label, sign = display(pt, lv)
            unit = LEVERS[lv][1]
            net = float(r[NET[lv]])
            row = {"pitcher": r["pitcher"], "pitch_type": pt, "lever": lv, "change": label,
                   "net_change_units": sign * net / unit, "d_whiff": r["d_whiff"], "d_xwhiff": r["d_xwhiff"]}
            if (pt, lv) in ans.index:
                a = ans.loc[(pt, lv)]
                row |= {"payoff_whiff_per_unit": a["whiff"], "verdict": a["verdict"], "caveat": a["caveat"],
                        "implied_whiff": sign * net / unit * a["whiff"],
                        "persistence": LEVER_PERSISTENCE.get((pt, lv), "not followed in the persistence study")}
            rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ club need

def team_bullpens(d: pd.DataFrame, season: int, late_inning: int = 7, close: int = 3) -> pd.DataFrame:
    """Each club's relief results: PA, K-BB%, whiff, xwOBA, run value per 100 pitches, win probability added,
    and the same in late, close spots (inning >= late_inning, score within `close`). Grain: team."""
    r = d[d["season"].eq(season) & d["relief"]].copy()
    r["wpa"] = np.where(r["inning_topbot"].eq("Top"), 1, -1) * r["delta_home_win_exp"]
    r["late_close"] = (r["inning"] >= late_inning) & ((r["bat_score"] - r["fld_score"]).abs() <= close)

    def agg(x: pd.DataFrame) -> pd.Series:
        return pd.Series({"pa": x["pa"].sum(), "k_bb_pct": 100 * (x["k"].sum() - x["bb"].sum()) / x["pa"].sum(),
                          "whiff_pct": 100 * x["whiff"].sum() / x["swing"].sum(),
                          "xwoba": np.nansum(x["xwoba_pa"] * x["xwoba_den"]) / x["xwoba_den"].sum(),
                          "rv100": 100 * x["rv"].sum() / x["rv"].count(), "wpa": x["wpa"].sum()})

    allr = r.groupby("team")[list(r.columns)].apply(agg)
    lc = r[r["late_close"]].groupby("team")[list(r.columns)].apply(agg).add_prefix("late_close_")
    out = allr.join(lc)
    for c in ("rv100", "wpa", "late_close_rv100", "late_close_wpa", "k_bb_pct", "xwoba"):
        asc = c == "xwoba"
        out[f"{c}_rank"] = out[c].rank(ascending=asc, method="min").astype(int)   # 1 = best
    return out.reset_index()


# ------------------------------------------------------------------ the comparison table

VIEW = [  # (row label, formatter of a summary row)
    ("Throws / games / IP", lambda r: f"{r['throws']} / {r['games']} / {r['ip']:.1f}"),
    ("K% / BB% (unintentional) / K-BB%", lambda r: f"{r['k_pct']:.1f} / {r['bb_pct']:.1f} ({r['ubb_pct']:.1f}) / {r['k_bb_pct']:.1f}"),
    ("Whiff%: observed, regressed (95%)", lambda r: f"{100 * r['whiff_obs']:.1f}, {100 * r['whiff_reg']:.1f} ({100 * r['whiff_lo']:.1f}-{100 * r['whiff_hi']:.1f})"),
    ("Chase%: observed, regressed", lambda r: f"{100 * r['chase_obs']:.1f}, {100 * r['chase_reg']:.1f}"),
    ("xwOBA on contact: observed, regressed", lambda r: f"{r['xwoba_con_obs']:.3f}, {r['xwoba_con_reg']:.3f}"),
    ("GB%: observed, regressed", lambda r: f"{100 * r['gb_obs']:.1f}, {100 * r['gb_reg']:.1f}"),
    ("Run value /100: observed, regressed (95%)", lambda r: f"{r['rv100_obs']:+.2f}, {r['rv100_reg']:+.2f} ({r['rv100_lo']:+.2f} to {r['rv100_hi']:+.2f})"),
    ("Expected whiff% / gap, by season", lambda r: ", ".join(f"{s}: {r.get(f'x_whiff_pct_{s}', np.nan):.1f} / {r.get(f'gap_{s}', np.nan):+.1f}"
                                                            for s in (r["season"] - 2, r["season"] - 1, r["season"]))),
    ("Next-season whiff% (edge engine)", lambda r: f"{r.get('proj_whiff_pct', np.nan):.1f}"),
    ("Fastball: velo, change net of league", lambda r: f"{r.get('fb_type')} {r.get('fb_velo', np.nan):.1f}, {r.get('fb_net_change', np.nan):+.2f}"),
    ("Late minus early velo (league)", lambda r: f"{r.get('fb_late_minus_early', np.nan):+.2f} ({r.get('league_late_minus_early', np.nan):+.2f})"),
    ("Back-to-backs / multi-inning / leverage proxy", lambda r: f"{r.get('back_to_back')} / {r.get('multi_inning')} / {r.get('leverage_proxy', np.nan):.2f}"),
    ("Control grade / OFP now / OFP 2027", lambda r: f"{r['control_grade']} / {r['ofp_present']} / {r['ofp_2027']}"),
]


def summary_view(summary: pd.DataFrame) -> pd.DataFrame:
    """The summary as a readable table: one column per pitcher, one row per line of VIEW."""
    cols = {}
    for _, r in summary.iterrows():
        cols[r["name"]] = [f(r) for _, f in VIEW]
    return pd.DataFrame(cols, index=[label for label, _ in VIEW])


def load_seasons(seasons) -> pd.DataFrame:
    """Raw sequence rows (regular season) for the given seasons."""
    from baseball.edge.familiarity import load_seq

    return pd.concat([load_seq(s) for s in seasons], ignore_index=True)


def compare_relievers(ids, season: int, raw: pd.DataFrame | None = None, edge_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    """The full comparison for any list of pitcher ids and a season: every table above, plus one summary row per
    pitcher. Needs the sequence copy for `season` and `season - 1` (data/seq/) and the edge engine's outputs for
    `season` (data/edge/<season>/: stuff tables, projection) and the levers study (data/edge/levers/).
    Returns a dict of DataFrames: summary, regressed, grades, velocity, workload, platoon, usage, gaps, levers,
    familiarity, lines."""
    ids = [int(i) for i in ids]
    edge_dir = Path(edge_dir or EDGE)
    raw = load_seasons([season - 1, season]) if raw is None else raw
    d = flag(raw)
    lg = league_means(season)
    lines = season_line(d[d["pitcher"].isin(ids)])
    cur = lines[lines["season"].eq(season)]
    reg = regressed(cur, lg)
    stuff = {s: pd.read_parquet(edge_dir / str(season) / f"stuff_{s}.parquet") for s in (season - 2, season - 1, season)
             if (edge_dir / str(season) / f"stuff_{s}.parquet").exists()}
    proj = pd.read_parquet(edge_dir / str(season) / "projection.parquet")
    grades = pitch_grades(stuff[season], proj, ids, lg)
    velo = velocity_read(d, ids, season)
    work = workload(d, ids, season)
    plat = platoon(d, ids, season, lg["whiff"])
    mix = usage(d, ids, season)
    gaps = gap_history(stuff, ids, proj)
    lev_dir = edge_dir / "levers"
    levers = (lever_read(pd.read_parquet(lev_dir / "pairs.parquet"), pd.read_parquet(lev_dir / "answer.parquet"), ids, season)
              if (lev_dir / "pairs.parquet").exists() else pd.DataFrame())
    fam = familiarity_load(raw[raw["game_year"].eq(season)], ids)

    rows = []
    for pid in ids:
        ln = cur[cur["pitcher"].eq(pid)]
        if ln.empty:
            continue
        ln = ln.iloc[0]
        rg = reg[reg["pitcher"].eq(pid)].set_index("metric")
        gr = grades[grades["pitcher"].eq(pid)]
        pres = {r.pitch_type: r.grade_present for r in gr.itertuples()}
        fut = {r.pitch_type: r.grade_2027 for r in gr.itertuples()}
        ctl = control_grade(ln["ubb_pct"])
        o_now, o_next = reliever_ofp(pres, ctl), reliever_ofp(fut, ctl)
        v = velo[velo["pitcher"].eq(pid)]
        w = work[work["pitcher"].eq(pid)]
        gp = gaps[gaps["pitcher"].eq(pid)]
        row = {"pitcher": pid, "name": ln["player_name"], "throws": ln["p_throws"], "season": season,
               "games": int(ln["games"]), "ip": ln["ip"], "pa": int(ln["pa"]), "pitches": int(ln["pitches"]),
               "k_pct": ln["k_pct"], "bb_pct": ln["bb_pct"], "ubb_pct": ln["ubb_pct"], "k_bb_pct": ln["k_bb_pct"],
               "xwoba": ln["xwoba"]}
        for m in REGRESS:
            row[f"{m}_obs"] = rg.loc[m, "observed"]
            row[f"{m}_reg"] = rg.loc[m, "estimate"]
            row[f"{m}_lo"], row[f"{m}_hi"] = rg.loc[m, "lo"], rg.loc[m, "hi"]
            row[f"{m}_next"] = rg.loc[m, "next_estimate"]
        if not gp.empty:
            for c in gp.columns:
                if c != "pitcher":
                    row[c] = gp[c].iloc[0]
        if not v.empty:
            v0 = v.iloc[0]
            row |= {"fb_type": v0["pitch_type"], "fb_velo": v0["velo"], "fb_velo_reg": v0["velo_reg"], "fb_velo_change": v0["change"],
                    "fb_league_change": v0["league_change"], "fb_net_change": v0["net_change"],
                    "fb_late_minus_early": v0["late_minus_early"], "league_late_minus_early": v0["league_late_minus_early"]}
        if not w.empty:
            w0 = w.iloc[0]
            row |= {k: w0[k] for k in ("back_to_back", "multi_inning", "three_in_four_days", "pitches_per_game",
                                       "velo_b2b_minus_rest", "leverage_proxy", "longest_gap_days", "last_game")}
        row |= {"control_grade": ctl, "ofp_present": o_now["ofp"], "role_present": o_now["role"],
                "ofp_2027": o_next["ofp"], "role_2027": o_next["role"],
                "best_pitch": gr.sort_values("grade_present", ascending=False)["pitch_type"].iloc[0] if len(gr) else None}
        rows.append(row)
    return {"summary": pd.DataFrame(rows), "regressed": reg, "grades": grades, "velocity": velo, "workload": work,
            "platoon": plat, "usage": mix, "gaps": gaps, "levers": levers, "familiarity": fam, "lines": lines}
