"""The exposure-aware hook: when should a starter face the next hitter, and do managers price what each
hitter has already seen?

Builds on the pitch-type familiarity study (`familiarity.py`): a pitch type loses run value the more of it a
hitter has seen from the pitcher in earlier plate appearances today. Here that per-pitch finding becomes a
per-hitter number a dugout can use before each plate appearance, and two questions are tested on a season the
costs never saw (2026):

1. Does the number predict? PA run value on the exposure index with times through the order, pitch count,
   in-game form, platoon, base-out state, score and pitcher-season / batter-season fixed effects.
2. Do managers price it? Starter removal at each between-PA decision point on the next hitters' index, with the
   same state held fixed.

Grain
- `plate_appearances()`: one row per plate appearance (game_pk, at_bat_number). The pitcher is the one who threw
  its first pitch. Run value is the sum of Statcast's delta_run_exp over every pitch of the PA (offense's view:
  positive = runs for the batting team).
- `decisions()`: one row per between-PA decision point of a starter, i.e. after each PA he completed, when the
  manager either lets him face the next hitter or brings in a reliever.

The exposure index (runs per PA, offense's view), built from information available BEFORE the PA:

    index = PPA x sum over pitch types T of  usage_T x seen_T x cost_T

- usage_T: the pitcher's share of type T to batters of this hitter's side in his earlier games this season,
  blended with last season's share at a weight of K_USAGE pitches (so early-season usage leans on last season
  and fades as this season's pitches accumulate). With no earlier games and no last season (a debut), his
  pitches earlier in this game.
- seen_T: pitches of type T this hitter saw from this pitcher in earlier PAs today.
- cost_T: runs per pitch lost by type T per earlier same-type pitch (the familiarity contrast, `rv_coef`),
  re-estimated on 2024-25 only so the 2026 test is out of sample. Types without an estimate cost 0.
- PPA: average pitches per PA in starters' later-time-through PAs (2024-25), turning a per-pitch cost into a
  per-PA one.

If the index means what it says, the coefficient of PA run value on it is 1.0 (the calibration slope).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from baseball.edge.familiarity import DATA, seq_parts
from baseball.evaluation.arsenal import SWINGS, WHIFFS
from baseball.stats import absorb, clustered_wls

OUT_DIR = DATA / "edge" / "hook"
COST_TYPES = ("FF", "SI", "FC", "SL", "ST", "CU", "KC", "CH", "FS")
FASTBALLS = ("FF", "SI")
K_USAGE = 150          # last season's usage counts as this many pitches of this season's
PITCH_COLUMNS = [
    "game_pk", "game_date", "game_year", "at_bat_number", "pitch_number", "pitcher", "batter", "p_throws",
    "stand", "pitch_type", "release_speed", "description", "events", "inning", "inning_topbot", "outs_when_up",
    "on_1b", "on_2b", "on_3b", "bat_score", "fld_score", "home_team", "away_team", "delta_run_exp",
    "delta_home_win_exp", "woba_value", "woba_denom",
]


# ---------------------------------------------------------------- data

def load_pitches(season: int, columns: list[str] = PITCH_COLUMNS) -> pd.DataFrame:
    """Regular-season pitches of a season from the sequence copy (data/seq/), only the columns used here."""
    parts = seq_parts(season)
    if not parts:
        raise FileNotFoundError(f"No sequence data for {season}. Run `bb seq {season}` on the Mac.")
    return pd.concat([pd.read_parquet(p, columns=columns) for p in parts], ignore_index=True)


def _cum_before(df: pd.DataFrame, keys: list[str], cols: list[str]) -> pd.DataFrame:
    """Running total within the group, excluding the current row (rows must be in time order)."""
    return df.groupby(keys, sort=False)[cols].cumsum() - df[cols]


def estimate_costs(seasons=(2024, 2025)) -> pd.DataFrame:
    """Per-pitch-type familiarity costs re-estimated on the given seasons only (familiarity.by_pitch_type)."""
    from baseball.edge import familiarity as f

    return f.by_pitch_type(f.prepare(list(seasons)))


def cost_per_pitch(costs: pd.DataFrame) -> dict[str, float]:
    """runs (offense's view) per pitch of type T, per earlier same-type pitch seen: -rv_coef / 100.

    rv_coef is in runs per 100 pitches from the pitcher's view (negative = the pitcher loses), so the
    offense gains -rv_coef / 100 runs per pitch.
    """
    return {t: -float(v) / 100 for t, v in zip(costs["pitch_type"], costs["rv_coef"])}


# ---------------------------------------------------------------- plate appearances

def plate_appearances(p: pd.DataFrame) -> pd.DataFrame:
    """One row per plate appearance, with everything known before it (and, for decision points, after it).

    Input: pitches (any number of games, any order). Columns added per PA:
    - outcome: rv (sum of delta_run_exp, offense's view), woba_value, woba_denom, dwe (sum of delta_home_win_exp),
      pitches, pa_swings, pa_whiffs, sw_<T> (swings by pitch type), mid_pa_change (another pitcher threw part of it)
    - state at the first pitch: inning, half, outs, base (1st=1, 2nd=2, 3rd=4), lead (fielding team's), same_hand
    - roles: fld_team, bat_team, starter (pitcher threw his team's first pitch of the game), bat_idx (the
      batting team's PA number in the game, 0-based; lineup slot = bat_idx % 9)
    - pitcher before the PA: bf, pitch_count, rv_so_far, whiffs_so_far, swings_so_far, velo_drop (mean FF/SI
      velocity over his last three PAs minus his first inning; 0 with velo_missing = 1 when either is missing)
    - the same five after the PA (suffix _after), for decision points
    - hitter vs this pitcher: prior_pa (earlier PAs today), seen_<T> and seen_total (pitches seen in earlier PAs
      today), and seen_after_<T> (including this PA)
    - today_<T>, today_total: the pitcher's pitches earlier today (usage fallback for a debut)
    """
    p = p.sort_values(["game_pk", "at_bat_number", "pitch_number"]).reset_index(drop=True)
    p["pt"] = p["pitch_type"].where(p["pitch_type"].isin(COST_TYPES), "OT")
    p["swing"] = p["description"].isin(SWINGS).astype(int)
    p["whiff"] = p["description"].isin(WHIFFS).astype(int)
    p["fbv"] = p["release_speed"].where(p["pitch_type"].isin(FASTBALLS))
    p["delta_run_exp"] = p["delta_run_exp"].fillna(0.0)

    # pitcher x PA level (a PA can have two pitchers)
    k3 = ["game_pk", "at_bat_number", "pitcher"]
    g = p.groupby(k3, sort=False)
    pp = g.agg(batter=("batter", "first"), inning=("inning", "first"), n=("pitch_number", "size"),
               rv_p=("delta_run_exp", "sum"), whiffs=("whiff", "sum"), swings=("swing", "sum"),
               fb_sum=("fbv", "sum"), fb_n=("fbv", "count"))
    cnt = p.groupby(k3 + ["pt"], sort=False).size().unstack(fill_value=0)
    types = list(COST_TYPES) + ["OT"]
    cnt = cnt.reindex(columns=types, fill_value=0).add_prefix("n_")
    pp = pp.join(cnt).reset_index().sort_values(["game_pk", "at_bat_number"]).reset_index(drop=True)
    ncols = [f"n_{t}" for t in types]

    gp = ["game_pk", "pitcher"]
    before = _cum_before(pp, gp, ["n", "rv_p", "whiffs", "swings"])
    pp["bf"] = pp.groupby(gp, sort=False).cumcount()
    pp["pitch_count"], pp["rv_so_far"] = before["n"], before["rv_p"]
    pp["whiffs_so_far"], pp["swings_so_far"] = before["whiffs"], before["swings"]
    pp["pitch_count_after"] = pp["pitch_count"] + pp["n"]
    pp["rv_so_far_after"] = pp["rv_so_far"] + pp["rv_p"]
    pp["whiffs_so_far_after"] = pp["whiffs_so_far"] + pp["whiffs"]
    pp["swings_so_far_after"] = pp["swings_so_far"] + pp["swings"]

    # velocity: last three PAs vs his first inning of work
    first_inn = pp.groupby(gp, sort=False)["inning"].transform("min")
    in1 = pp["inning"].eq(first_inn)
    pp["fb_sum1"], pp["fb_n1"] = pp["fb_sum"].where(in1, 0.0), pp["fb_n"].where(in1, 0)
    c1 = _cum_before(pp, gp, ["fb_sum1", "fb_n1"])
    roll = pp.groupby(gp, sort=False)[["fb_sum", "fb_n"]].rolling(3, min_periods=1).sum().reset_index(level=[0, 1], drop=True)
    roll = roll.sort_index()
    prev_roll = roll.groupby([pp["game_pk"], pp["pitcher"]]).shift(1)

    def drop(v1s, v1n, rs, rn):
        v = rs / rn.where(rn > 0) - v1s / v1n.where(v1n > 0)
        return v.fillna(0.0), v.isna().astype(int)

    pp["velo_drop"], pp["velo_missing"] = drop(c1["fb_sum1"], c1["fb_n1"], prev_roll["fb_sum"], prev_roll["fb_n"])
    pp["velo_drop_after"], pp["velo_missing_after"] = drop(c1["fb_sum1"] + pp["fb_sum1"], c1["fb_n1"] + pp["fb_n1"],
                                                           roll["fb_sum"], roll["fb_n"])

    # what the hitter has seen from this pitcher in earlier PAs today, and the pitcher's pitches today
    gpb = ["game_pk", "pitcher", "batter"]
    seen = _cum_before(pp, gpb, ncols)
    pp["prior_pa"] = pp.groupby(gpb, sort=False).cumcount()
    today = _cum_before(pp, gp, ncols)
    for t in types:
        pp[f"seen_{t}"] = seen[f"n_{t}"]
        pp[f"seen_after_{t}"] = seen[f"n_{t}"] + pp[f"n_{t}"]
        pp[f"today_{t}"] = today[f"n_{t}"]
        pp[f"today_after_{t}"] = today[f"n_{t}"] + pp[f"n_{t}"]
    pp["seen_total"] = seen[ncols].sum(axis=1)
    pp["seen_after_total"] = pp["seen_total"] + pp["n"]
    pp["today_total"] = today[ncols].sum(axis=1)
    pp["today_after_total"] = pp["today_total"] + pp["n"]

    # PA level
    k2 = ["game_pk", "at_bat_number"]
    g = p.groupby(k2, sort=False)
    pa = g.agg(game_date=("game_date", "first"), game_year=("game_year", "first"), pitcher=("pitcher", "first"),
               batter=("batter", "first"), stand=("stand", "first"), p_throws=("p_throws", "first"),
               inning=("inning", "first"), half=("inning_topbot", "first"), outs=("outs_when_up", "first"),
               on_1b=("on_1b", "first"), on_2b=("on_2b", "first"), on_3b=("on_3b", "first"),
               bat_score=("bat_score", "first"), fld_score=("fld_score", "first"),
               home_team=("home_team", "first"), away_team=("away_team", "first"),
               rv=("delta_run_exp", "sum"), woba_value=("woba_value", "sum"), woba_denom=("woba_denom", "sum"),
               dwe=("delta_home_win_exp", "sum"), pitches=("pitch_number", "size"),
               pa_swings=("swing", "sum"), pa_whiffs=("whiff", "sum"),
               n_pitchers=("pitcher", "nunique"), events=("events", "last")).reset_index()
    sw = p[p["swing"].eq(1)].groupby(k2 + ["pt"], sort=False).size().unstack(fill_value=0)
    sw = sw.reindex(columns=types, fill_value=0).add_prefix("sw_").reset_index()
    pa = pa.merge(sw, on=k2, how="left")
    pa[[f"sw_{t}" for t in types]] = pa[[f"sw_{t}" for t in types]].fillna(0).astype(int)
    pa["mid_pa_change"] = (pa.pop("n_pitchers") > 1).astype(int)
    occ = lambda c: (pa[c].fillna(0) > 0).astype(int)  # noqa: E731
    pa["base"] = occ("on_1b") + 2 * occ("on_2b") + 4 * occ("on_3b")
    pa["lead"] = (pa["fld_score"] - pa["bat_score"]).astype(float)
    pa["same_hand"] = pa["stand"].eq(pa["p_throws"]).astype(int)
    top = pa["half"].eq("Top")
    pa["fld_team"] = np.where(top, pa["home_team"], pa["away_team"])
    pa["bat_team"] = np.where(top, pa["away_team"], pa["home_team"])
    pa = pa.sort_values(["game_pk", "at_bat_number"]).reset_index(drop=True)
    first = pa.groupby(["game_pk", "half"], sort=False)["pitcher"].transform("first")
    pa["starter"] = pa["pitcher"].eq(first).astype(int)
    pa["bat_idx"] = pa.groupby(["game_pk", "half"], sort=False).cumcount()

    keep = ["game_pk", "at_bat_number", "pitcher", "bf", "prior_pa", "pitch_count", "rv_so_far", "whiffs_so_far",
            "swings_so_far", "velo_drop", "velo_missing", "pitch_count_after", "rv_so_far_after",
            "whiffs_so_far_after", "swings_so_far_after", "velo_drop_after", "velo_missing_after", "seen_total",
            "seen_after_total", "today_total", "today_after_total",
            *[f"{w}_{t}" for w in ("seen", "seen_after", "today", "today_after") for t in types]]
    return pa.merge(pp[keep], on=["game_pk", "at_bat_number", "pitcher"], how="left")


# ---------------------------------------------------------------- usage and the index

def usage_table(p: pd.DataFrame, k: float = K_USAGE) -> pd.DataFrame:
    """The pitcher's pitch-type shares to each batter side BEFORE each game (no current-game information).

    One row per (pitcher, game_pk, stand) where he faced that side. use_<T> =
        (this season's earlier pitches of T + k x last season's share of T) / (this season's earlier pitches + k)
    when he pitched last season (to that side); this season's earlier share alone when he didn't; NaN when
    neither exists (the caller falls back to his pitches earlier today). use_src says which applied.
    """
    q = p.copy()
    q["pt"] = q["pitch_type"].where(q["pitch_type"].isin(COST_TYPES), "OT")
    types = list(COST_TYPES) + ["OT"]
    keys = ["pitcher", "game_year", "stand", "game_date", "game_pk"]
    g = q.groupby(keys + ["pt"]).size().unstack(fill_value=0).reindex(columns=types, fill_value=0)
    g = g.reset_index().sort_values(keys).reset_index(drop=True)
    g["tot"] = g[types].sum(axis=1)
    cur = _cum_before(g, ["pitcher", "game_year", "stand"], types + ["tot"])
    last = q.groupby(["pitcher", "game_year", "stand", "pt"]).size().unstack(fill_value=0).reindex(columns=types, fill_value=0)
    last_tot = last.sum(axis=1)
    share = last.div(last_tot, axis=0).add_prefix("u_").assign(n_last=last_tot).reset_index()
    share["game_year"] = share["game_year"] + 1
    out = g[["pitcher", "game_year", "stand", "game_pk"]].join(cur).merge(share, on=["pitcher", "game_year", "stand"], how="left")
    has_last = out["n_last"].fillna(0) > 0
    for t in types:
        blend = (out[t] + k * out[f"u_{t}"]) / (out["tot"] + k)
        alone = out[t] / out["tot"].where(out["tot"] > 0)
        out[f"use_{t}"] = np.where(has_last, blend, alone)
    out["use_n"] = out["tot"]
    out["use_src"] = np.select([has_last & out["tot"].gt(0), has_last, out["tot"].gt(0)],
                               ["season+last", "last season", "season"], "none")
    return out[["pitcher", "game_pk", "stand", "use_n", "use_src", *[f"use_{t}" for t in types]]]


def exposure_index(seen: pd.DataFrame, use: pd.DataFrame, cost: dict[str, float], ppa: float) -> np.ndarray:
    """PPA x sum_T use_T x seen_T x cost_T, row by row. seen has seen_<T>, use has use_<T> (same index)."""
    total = np.zeros(len(seen))
    for t, c in cost.items():
        if f"seen_{t}" in seen and f"use_{t}" in use:
            total += use[f"use_{t}"].to_numpy(float) * seen[f"seen_{t}"].to_numpy(float) * c
    return ppa * total


def _fallback_use(df: pd.DataFrame, prefix: str = "today") -> pd.DataFrame:
    """Fill missing usage from the pitcher's pitches earlier today (columns <prefix>_<T>, <prefix>_total)."""
    df = df.copy()
    miss = df["use_FF"].isna()
    tot = df[f"{prefix}_total"].where(df[f"{prefix}_total"] > 0)
    for t in [*COST_TYPES, "OT"]:
        df.loc[miss, f"use_{t}"] = (df[f"{prefix}_{t}"] / tot)[miss]
    df.loc[miss & tot.notna(), "use_src"] = "today"
    return df


def pitches_per_pa(pa: pd.DataFrame) -> float:
    """Average pitches per PA in starters' PAs against hitters facing them for the second time or later."""
    d = pa[pa["starter"].eq(1) & pa["prior_pa"].ge(1) & pa["mid_pa_change"].eq(0)]
    return float(d["pitches"].mean())


def add_index(pa: pd.DataFrame, use: pd.DataFrame, cost: dict[str, float], ppa: float) -> pd.DataFrame:
    """Attach usage (with the today fallback) and the exposure index (idx, runs per PA) to every PA."""
    d = pa.merge(use, on=["pitcher", "game_pk", "stand"], how="left")
    d = _fallback_use(d, "today")
    d["idx"] = exposure_index(d, d, cost, ppa)
    # same index with one average cost for every type (does the type-specific weighting matter?)
    cbar = float(np.mean(list(cost.values())))
    d["idx_flat"] = exposure_index(d, d, {t: cbar for t in cost}, ppa)
    nothing_seen = d["seen_total"].eq(0)              # 0 whatever the usage (a debut's first batters)
    d.loc[nothing_seen, ["idx", "idx_flat"]] = 0.0
    return d


# ---------------------------------------------------------------- leverage, bullpen, quality

def _lev_keys(d: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"inn": d["inning"].clip(1, 9).astype(int), "half": d["half"], "outs": d["outs"].astype(int),
                         "base": d["base"].astype(int), "lead": d["lead"].clip(-4, 4).astype(int)}, index=d.index)


def leverage_table(pa: pd.DataFrame, k: float = 50.0) -> pd.DataFrame:
    """A leverage index from the data (Tango's definition, approximately): the average absolute swing in home
    win expectancy over a PA in this state, divided by the average over all PAs.

    State = inning (9+ pooled) x half x outs x base state x fielding team's lead (clipped at +-4). Each cell is
    shrunk toward its inning x half x lead cell with a weight of k PAs.
    """
    s = _lev_keys(pa).assign(sw=pa["dwe"].abs())
    s = s[s["sw"].notna()]
    overall = s["sw"].mean()
    parent = s.groupby(["inn", "half", "lead"])["sw"].mean().rename("parent")
    c = s.groupby(["inn", "half", "outs", "base", "lead"])["sw"].agg(["sum", "size"]).reset_index()
    c = c.merge(parent.reset_index(), on=["inn", "half", "lead"], how="left")
    c["li"] = (c["sum"] + k * c["parent"]) / (c["size"] + k) / overall
    return c[["inn", "half", "outs", "base", "lead", "li"]]


def add_leverage(d: pd.DataFrame, lev: pd.DataFrame) -> pd.Series:
    """Leverage for each row's state (1.0 where the state never occurred)."""
    k = _lev_keys(d).reset_index().merge(lev, on=["inn", "half", "outs", "base", "lead"], how="left").set_index("index")
    return k["li"].reindex(d.index).fillna(1.0)


def bullpen_load(pa: pd.DataFrame, days: int = 3) -> pd.DataFrame:
    """Pitches thrown by each team's relievers (non-starters) on the `days` calendar days before each game."""
    r = pa[pa["starter"].eq(0)]
    daily = r.groupby(["fld_team", "game_date"])["pitches"].sum().reset_index()
    daily["game_date"] = pd.to_datetime(daily["game_date"])
    out = []
    for team, d in daily.groupby("fld_team"):
        s = d.set_index("game_date")["pitches"].asfreq("D", fill_value=0)
        prev = s.rolling(days, min_periods=1).sum().shift(1).fillna(0)
        out.append(pd.DataFrame({"fld_team": team, "game_date": prev.index.strftime("%Y-%m-%d"), "pen_load": prev.to_numpy()}))
    return pd.concat(out, ignore_index=True)


def shrinkage_k(y: pd.Series, groups: pd.Series) -> float:
    """Method-of-moments shrinkage constant k = noise variance / true-talent variance, so a group's mean is
    regressed by n / (n + k). Noise variance = pooled within-group variance; true-talent variance = variance of
    group means minus their average sampling variance (floored at a tiny positive number)."""
    d = pd.DataFrame({"y": y.to_numpy(float), "g": groups.to_numpy()})
    s = d.groupby("g")["y"].agg(["mean", "var", "size"])
    s = s[s["size"] > 1]
    within = float((s["var"] * (s["size"] - 1)).sum() / (s["size"] - 1).sum())
    between = float(s["mean"].var(ddof=1) - (within / s["size"]).mean())
    return within / max(between, 1e-12)


# ---------------------------------------------------------------- estimation helpers

def pa_controls(d: pd.DataFrame, seen_total: bool = True, prefix: str = "") -> pd.DataFrame:
    """Controls for a PA (prefix '' = before the PA; for decisions the caller passes post-PA values)."""
    c = pd.DataFrame(index=d.index)
    tto = d["prior_pa"].clip(upper=3).astype(int)
    for k in (1, 2, 3):
        c[f"tto_{k + 1}"] = tto.eq(k).astype(float)
    c["pitch_count"] = d["pitch_count"] / 100
    c["pitch_count2"] = c["pitch_count"] ** 2
    for col in ("rv_so_far", "whiffs_so_far", "swings_so_far", "velo_drop", "velo_missing", "same_hand"):
        c[col] = d[col].astype(float)
    bo = (d["base"].astype(int) * 3 + d["outs"].astype(int)).astype(str)
    c = c.join(pd.get_dummies(bo, prefix="bo", dtype=float).drop(columns="bo_0", errors="ignore"))
    lead = d["lead"].clip(-5, 5).astype(int).astype(str)
    c = c.join(pd.get_dummies(lead, prefix="lead", dtype=float).drop(columns="lead_0", errors="ignore"))
    inn = d["inning"].clip(1, 9).astype(int).astype(str)
    c = c.join(pd.get_dummies(inn, prefix="inn", dtype=float).drop(columns="inn_1", errors="ignore"))
    if seen_total:
        c["seen_total"] = d["seen_total"].astype(float)
    return c


def _drop_singletons(d: pd.DataFrame, fe: list[str]) -> pd.DataFrame:
    for _ in range(5):
        n = len(d)
        for k in fe:
            d = d[d.groupby(k)[k].transform("size") > 1]
        if len(d) == n:
            break
    return d


def fe_ols(d: pd.DataFrame, y: str, xcols: list[str], fe: list[str], cluster: str = "pitcher",
           report: list[str] | None = None) -> pd.DataFrame:
    """OLS of y on xcols with fixed effects absorbed, SEs clustered. Complete cases; FE singletons dropped."""
    from scipy.stats import norm

    d = _drop_singletons(d.dropna(subset=[y, *xcols]), fe)
    r = absorb(d, [y, *xcols], fe)
    keep = [c for c in xcols if r[c].abs().max() > 1e-9]
    beta, se = clustered_wls(r[y].to_numpy(), r[keep].to_numpy(), np.ones(len(r)), d[cluster].to_numpy())
    out = pd.DataFrame({"term": keep, "coef": beta, "se": se})
    out["t"] = out["coef"] / out["se"]
    out["p"] = 2 * norm.sf(out["t"].abs())
    out["n"], out["clusters"], out["y_mean"] = len(d), d[cluster].nunique(), d[y].mean()
    return (out if report is None else out[out["term"].isin(report)]).reset_index(drop=True)


def fe_fit_predict(train: pd.DataFrame, test: pd.DataFrame, y: str, xcols: list[str], fe: list[str],
                   lam: float | list = 0.0, iters: int = 100, offset: str | None = None) -> np.ndarray:
    """Fit y ~ xcols + fixed effects on train, predict test. Fixed effects are recovered by alternating
    (ridge-shrunk) group means of the residual: a group's effect = sum of its residuals / (n + lam), with lam
    one number or one per fixed effect. Groups
    unseen in training get 0 (the grand mean). `offset`: a column added to the prediction with slope 1 and
    subtracted from y before fitting (a forecast that takes the index at face value)."""
    tr = _drop_singletons(train.dropna(subset=[y, *xcols]), fe).copy()
    if offset:
        tr[y] = tr[y] - tr[offset]
    if xcols:
        r = absorb(tr, [y, *xcols], fe)
        keep = [c for c in xcols if r[c].abs().max() > 1e-9]
        beta = np.linalg.lstsq(r[keep].to_numpy(), r[y].to_numpy(), rcond=None)[0]
        u = tr[y].to_numpy(float) - tr[keep].to_numpy(float) @ beta
    else:
        keep, beta, u = [], np.zeros(0), tr[y].to_numpy(float)
    mu = u.mean()
    v = u - mu
    codes = [pd.factorize(tr[k]) for k in fe]
    effects = [np.zeros(len(c[1])) for c in codes]
    for _ in range(iters):
        delta = 0.0
        for j, (c, _lev) in enumerate(codes):
            other = sum(effects[i][codes[i][0]] for i in range(len(fe)) if i != j) if len(fe) > 1 else 0.0
            lj = lam[j] if isinstance(lam, (list, tuple)) else lam
            new = np.bincount(c, weights=v - other, minlength=len(_lev)) / (np.bincount(c, minlength=len(_lev)) + lj)
            delta = max(delta, float(np.abs(new - effects[j]).max()))
            effects[j] = new
        if delta < 1e-10:
            break
    pred = mu + (test[keep].to_numpy(float) @ beta if keep else np.zeros(len(test)))
    for k, (c, lev), eff in zip(fe, codes, effects):
        pred = pred + test[k].map(pd.Series(eff, index=lev)).fillna(0.0).to_numpy()
    if offset:
        pred = pred + test[offset].to_numpy(float)
    return np.asarray(pred, float)


def paired_mse_test(e0, e1, clusters) -> dict:
    """Is model 1's squared error lower than model 0's? d_i = e0_i^2 - e1_i^2 (positive = model 1 better).
    Returns the mean of d, its cluster-robust SE (sum within clusters, G/(G-1) factor), t, and the % MSE change."""
    e0, e1 = np.asarray(e0, float), np.asarray(e1, float)
    d = e0 ** 2 - e1 ** 2
    n = len(d)
    groups, inv = np.unique(np.asarray(clusters), return_inverse=True)
    G = len(groups)
    s = np.bincount(inv, weights=d - d.mean())
    se = float(np.sqrt((G / (G - 1)) * (s ** 2).sum()) / n)
    mse0 = float((e0 ** 2).mean())
    return {"d_mean": float(d.mean()), "se": se, "t": float(d.mean() / se) if se > 0 else np.nan,
            "mse0": mse0, "mse1": float((e1 ** 2).mean()), "pct_reduction": 100 * float(d.mean()) / mse0, "n": n,
            "clusters": G}


def decile_table(d: pd.DataFrame, x: str, y: str, cluster: str = "pitcher", q: int = 10) -> tuple[pd.DataFrame, dict]:
    """Mean x and y by quantile bin of x, and the top-minus-bottom difference in y with a clustered SE
    (y on a top-bin dummy within the top and bottom bins). Ties in x go to the lower bin."""
    from scipy.stats import norm

    d = d[[x, y, cluster]].dropna().copy()
    d["bin"] = pd.qcut(d[x].rank(method="first"), q, labels=False)
    tab = d.groupby("bin").agg(x_mean=(x, "mean"), y_mean=(y, "mean"), n=(y, "size")).reset_index()
    tb = d[d["bin"].isin([0, q - 1])]
    X = np.column_stack([np.ones(len(tb)), tb["bin"].eq(q - 1).astype(float)])
    beta, se = clustered_wls(tb[y].to_numpy(), X, np.ones(len(tb)), tb[cluster].to_numpy())
    xb, xs = clustered_wls(tb[x].to_numpy(), X, np.ones(len(tb)), tb[cluster].to_numpy())
    diff = {"y_diff": float(beta[1]), "y_se": float(se[1]), "p": float(2 * norm.sf(abs(beta[1] / se[1]))),
            "x_diff": float(xb[1]), "n": len(tb)}
    return tab, diff


# ---------------------------------------------------------------- decision points

DECISION_STATE = ("pitch_count", "rv_so_far", "whiffs_so_far", "swings_so_far", "velo_drop", "velo_missing")


def decisions(pa: pd.DataFrame, use: pd.DataFrame, cost: dict[str, float], ppa: float, ahead: int = 3) -> pd.DataFrame:
    """One row per between-PA decision point of a starter.

    A decision point follows each PA the starter completed (no mid-PA change) when his team's defense has
    another PA in the game. removed = 1 when someone else threw the first pitch of that next PA (between
    innings or mid-inning). The state is the next PA's starting state (inning, outs, bases, lead), fixed before
    the choice. The pitcher's form is as of the end of his last PA (pitch_count = pitches thrown so far).

    The upcoming hitters come from the lineup, not from who actually batted next (a pinch hitter can be a
    response to the pitching change): hitter j (j = 0, 1, 2) is whoever batted in that lineup slot last time,
    i.e. the batting team's PA nine before. His exposure is what he had seen from the starter through that PA,
    priced with the starter's usage to his side: idx_0, idx_1, idx_2, and idx_next3 = their mean. A hitter who
    hasn't batted yet against him (first time through) has idx 0 and times 0.
    """
    pa = pa.sort_values(["game_pk", "at_bat_number"]).reset_index(drop=True)
    grp = pa.groupby(["game_pk", "half"], sort=False)
    nxt = pd.DataFrame({c: grp[c].shift(-1) for c in ("pitcher", "inning", "outs", "base", "lead", "bat_idx", "at_bat_number")})
    d = pa[pa["starter"].eq(1) & pa["mid_pa_change"].eq(0) & nxt["pitcher"].notna()].copy()
    nx = nxt.loc[d.index]
    d["removed"] = nx["pitcher"].ne(d["pitcher"]).astype(int)
    d["new_inning"] = nx["inning"].ne(d["inning"]).astype(int)
    d["next_ab"] = nx["at_bat_number"].astype(int)
    for c in ("inning", "outs", "base"):
        d[c] = nx[c].astype(int)
    d["lead"] = nx["lead"].astype(float)
    d["next_bat_idx"] = nx["bat_idx"].astype(int)
    for c in DECISION_STATE:
        d[c] = d[f"{c}_after"]
    d["bf"] = d["bf"] + 1
    types = [*COST_TYPES, "OT"]
    today_after = d[[f"today_after_{t}" for t in types] + ["today_after_total"]].copy()
    today_after.columns = [c.replace("today_after", "today") for c in today_after.columns]

    slot = pa.set_index(["game_pk", "half", "bat_idx"])
    new = {}
    for j in range(ahead):
        pos = d["next_bat_idx"].to_numpy() + j - 9
        s = slot.reindex(pd.MultiIndex.from_arrays([d["game_pk"].to_numpy(), d["half"].to_numpy(), pos]))
        ok = (pos >= 0) & (s["pitcher"].to_numpy(dtype=float) == d["pitcher"].to_numpy(dtype=float))
        h = pd.DataFrame(index=d.index)
        h["pitcher"], h["game_pk"] = d["pitcher"].to_numpy(), d["game_pk"].to_numpy()
        h["batter"] = np.where(ok, s["batter"].to_numpy(dtype=float), np.nan)
        h["stand"] = np.where(ok, s["stand"].to_numpy(dtype=object), None)
        h["times"] = np.where(ok, s["prior_pa"].to_numpy(dtype=float) + 1, 0)
        for t in types:
            h[f"seen_{t}"] = np.where(ok, s[f"seen_after_{t}"].to_numpy(dtype=float), 0.0)
        h["seen_total"] = np.where(ok, s["seen_after_total"].to_numpy(dtype=float), 0.0)
        u = h[["pitcher", "game_pk", "stand"]].merge(use, on=["pitcher", "game_pk", "stand"], how="left")
        u.index = h.index
        u = _fallback_use(pd.concat([u, today_after], axis=1), "today")
        new[f"idx_{j}"] = np.where(ok, exposure_index(h, u, cost, ppa), 0.0)
        new[f"batter_{j}"], new[f"stand_{j}"], new[f"times_{j}"] = h["batter"], h["stand"], h["times"]
        new[f"seen_total_{j}"] = h["seen_total"]
        new[f"same_hand_{j}"] = (h["stand"] == d["p_throws"]).astype(int)
        if j == 0:
            new["seen_total"] = h["seen_total"]
            new["same_hand"] = (h["stand"] == d["p_throws"]).astype(int)
            new["prior_pa"] = h["times"].astype(int)
            new["next_batter"] = h["batter"]
            new["next_ok"] = ok.astype(int)
    drop = [c for c in d.columns if c.startswith(("seen_", "today_")) or c.endswith("_after")
            or c in new or c.startswith("use_") or c in ("idx", "idx_flat")]
    d = pd.concat([d.drop(columns=drop), pd.DataFrame(new, index=d.index)], axis=1)
    d["idx_next3"] = d[[f"idx_{j}" for j in range(ahead)]].mean(axis=1)
    d["seen_next3"] = d[[f"seen_total_{j}" for j in range(ahead)]].mean(axis=1)
    d["same_next3"] = d[[f"same_hand_{j}" for j in range(ahead)]].mean(axis=1)
    d["slot"] = d["next_bat_idx"] % 9
    return d.reset_index(drop=True)


def decision_controls(d: pd.DataFrame) -> pd.DataFrame:
    """Controls for the removal model at a decision point (second time through or later).

    Times through for the next hitter (2nd = reference), pitch-count bins (removal is sharply non-linear in
    pitch count), inning, outs x bases, lead, leverage, start of an inning, in-game form, the next hitter's
    platoon and pitches seen, the next three hitters' average pitches seen and platoon share, the lineup slot
    due up, and the bullpen's pitches over the previous three days.
    """
    c = pd.DataFrame(index=d.index)
    times = d["prior_pa"].clip(upper=3).astype(int)
    c["tto_3"], c["tto_4"] = times.eq(2).astype(float), times.eq(3).astype(float)
    pc = pd.cut(d["pitch_count"], [-1, 59, 69, 79, 89, 99, 109, 999],
                labels=["<60", "60s", "70s", "80s", "90s", "100s", "110+"]).astype(str)
    c = c.join(pd.get_dummies(pc, prefix="pc", dtype=float).drop(columns="pc_<60", errors="ignore"))
    for col in ("rv_so_far", "whiffs_so_far", "swings_so_far", "velo_drop", "velo_missing", "same_hand", "seen_total",
                "seen_next3", "same_next3", "li", "new_inning", "pen_load"):
        c[col] = d[col].astype(float)
    bo = (d["base"].astype(int) * 3 + d["outs"].astype(int)).astype(str)
    c = c.join(pd.get_dummies(bo, prefix="bo", dtype=float).drop(columns="bo_0", errors="ignore"))
    lead = d["lead"].clip(-5, 5).astype(int).astype(str)
    c = c.join(pd.get_dummies(lead, prefix="lead", dtype=float).drop(columns="lead_0", errors="ignore"))
    inn = d["inning"].clip(1, 9).astype(int).astype(str)
    c = c.join(pd.get_dummies(inn, prefix="inn", dtype=float).drop(columns="inn_1", errors="ignore"))
    c = c.join(pd.get_dummies(d["slot"].astype(int).astype(str), prefix="slot", dtype=float).drop(columns="slot_0", errors="ignore"))
    return c


def matchup(p: pd.DataFrame, pa: pd.DataFrame, k: float = 200.0, ppa: float = 1.0) -> np.ndarray:
    """How well this hitter does against this pitcher's mix, from his season: sum over pitch groups g of the
    pitcher's usage of g x the hitter's run value per pitch against g this season (offense's view, shrunk
    toward 0 with k pitches), times ppa. A PA-level stand-in for the familiarity study's batter x pitch group x
    season fixed effect. It uses the whole season, as that fixed effect does."""
    from baseball.edge.familiarity import GROUP, GROUPS

    q = p[["batter", "game_year", "pitch_type", "delta_run_exp"]].copy()
    q["g"] = q["pitch_type"].map(GROUP)
    s = q.dropna(subset=["g"]).groupby(["batter", "game_year", "g"])["delta_run_exp"].agg(["sum", "size"])
    bv = (s["sum"] / (s["size"] + k)).unstack(fill_value=0.0)
    bv = bv.reindex(columns=GROUPS, fill_value=0.0)
    key = pd.MultiIndex.from_arrays([pa["batter"], pa["game_year"]])
    b = bv.reindex(key).fillna(0.0).to_numpy()
    use = np.column_stack([sum(pa[f"use_{t}"].fillna(0).to_numpy(float) for t in COST_TYPES if GROUP[t] == g) for g in GROUPS])
    return ppa * (use * b).sum(axis=1)


# ---------------------------------------------------------------- the card's model

def starter_cells(pa: pd.DataFrame) -> pd.DataFrame:
    """League starter run value per PA (offense's view) and mean exposure index by times through (1-4+,
    from prior_pa) and platoon (same_hand). Starters' PAs without a mid-PA change."""
    d = pa[pa["starter"].eq(1) & pa["mid_pa_change"].eq(0)].copy()
    d["times"] = d["prior_pa"].clip(upper=3).astype(int) + 1
    return d.groupby(["times", "same_hand"]).agg(rv=("rv", "mean"), idx=("idx", "mean"), n=("rv", "size")).reset_index()


def reliever_baseline(pa: pd.DataFrame) -> pd.DataFrame:
    """The reliever baseline: league run value per PA (offense's view) allowed by relievers (not the team's
    first pitcher) in innings 5-9 facing a hitter for the first time that game. Row same_hand = -1 pools both
    platoons (the card uses it: which reliever comes in, and his hand, isn't known at the decision); rows 0 and 1
    are the platoon splits for reference. Batter quality and the base-out state are averaged over, so the card
    compares a starter and a reliever against the same hitter in the same state by assuming both shift by the
    same amount."""
    d = pa[pa["starter"].eq(0) & pa["prior_pa"].eq(0) & pa["inning"].between(5, 9) & pa["mid_pa_change"].eq(0)]
    split = d.groupby("same_hand").agg(rv=("rv", "mean"), n=("rv", "size")).reset_index()
    pooled = pd.DataFrame({"same_hand": [-1], "rv": [d["rv"].mean()], "n": [len(d)]})
    return pd.concat([pooled, split], ignore_index=True)


def pitcher_quality(pa_prev: pd.DataFrame, pa_cur: pd.DataFrame, league: float, k: float) -> pd.DataFrame:
    """A starter's run value per PA allowed before each game: his starter PAs last season plus this season's
    earlier games, as a deviation from the league starter mean, shrunk by n / (n + k).
    One row per (pitcher, game_pk) of pa_cur's starters: q (runs per PA, offense's view), q_n (PAs used)."""
    def per_game(pa):
        d = pa[pa["starter"].eq(1) & pa["mid_pa_change"].eq(0)]
        return d.groupby(["pitcher", "game_date", "game_pk"])["rv"].agg(["sum", "size"]).reset_index()

    prev = per_game(pa_prev).groupby("pitcher")[["sum", "size"]].sum().rename(columns={"sum": "s0", "size": "n0"})
    cur = per_game(pa_cur).sort_values(["pitcher", "game_date", "game_pk"]).reset_index(drop=True)
    before = _cum_before(cur, ["pitcher"], ["sum", "size"])
    cur = cur[["pitcher", "game_pk"]].join(before).join(prev, on="pitcher")
    s = cur["sum"] + cur["s0"].fillna(0)
    n = cur["size"] + cur["n0"].fillna(0)
    dev = (s / n.where(n > 0) - league).fillna(0.0)
    cur["q"] = dev * n / (n + k)
    cur["q_n"] = n
    return cur[["pitcher", "game_pk", "q", "q_n"]]


def fit_quality_k(pa_prev: pd.DataFrame, pa_cur: pd.DataFrame, league: float,
                  grid=(50, 100, 200, 300, 400, 500, 600, 800, 1000, 1200, 1600, 2000, 3000)) -> tuple[float, pd.DataFrame]:
    """Choose the pitcher-quality shrinkage out of sample: build q for pa_cur's starts from pa_prev plus pa_cur's
    earlier games, regress pa_cur's starter PA run value on it (batter-season fixed effects), and keep the k
    whose slope is closest to 1 (q then means what it says, one season ahead)."""
    d = pa_cur[pa_cur["starter"].eq(1) & pa_cur["mid_pa_change"].eq(0)].copy()
    d["y"] = 100 * d["rv"]
    d["bkey"] = d["batter"].astype(str) + "|" + d["game_year"].astype(str)
    rows = []
    for k in grid:
        q = pitcher_quality(pa_prev, pa_cur, league, k)
        z = d.merge(q, on=["pitcher", "game_pk"], how="left")
        z["xq"] = 100 * z["q"].fillna(0.0)
        r = fe_ols(z, "y", ["xq"], ["bkey"]).iloc[0]
        rows.append({"k": k, "slope": r["coef"], "se": r["se"]})
    t = pd.DataFrame(rows)
    return float(t.loc[(t["slope"] - 1).abs().idxmin(), "k"]), t


def card_model(pa_train: pd.DataFrame, k_pitcher: float) -> dict:
    """Everything the card needs from the training seasons (the PA table with idx): starter cells, the
    reliever baseline, the league starter mean and the pitcher shrinkage constant."""
    st = pa_train[pa_train["starter"].eq(1) & pa_train["mid_pa_change"].eq(0)]
    return {"cells": starter_cells(pa_train), "reliever": reliever_baseline(pa_train),
            "league_starter": float(st["rv"].mean()), "k_pitcher": float(k_pitcher)}


def expected_vs_reliever(times, same_hand, idx, q, model: dict) -> pd.DataFrame:
    """For upcoming hitters: the starter's expected run value per PA (offense's view) and the reliever
    baseline, both in runs per PA.

    starter_base  = league starter mean at his times through and platoon + the starter's quality deviation q
    starter_index = starter_base + (idx - that cell's mean idx)    (the index at face value)
    reliever      = the pooled reliever baseline (same_hand = -1 row)
    cost_base / cost_index = starter - reliever (positive: the average reliever is expected to be better)
    """
    cells = model["cells"].set_index(["times", "same_hand"])
    rel = float(model["reliever"].set_index("same_hand").loc[-1, "rv"])
    t = np.clip(np.asarray(times, int), 1, 4)
    sh = np.asarray(same_hand, int)
    key = pd.MultiIndex.from_arrays([t, sh])
    cell_rv = cells["rv"].reindex(key).to_numpy()
    cell_idx = cells["idx"].reindex(key).to_numpy()
    out = pd.DataFrame({"starter_base": cell_rv + np.asarray(q, float)})
    out["starter_index"] = out["starter_base"] + (np.asarray(idx, float) - cell_idx)
    out["reliever"] = rel
    out["cost_base"] = out["starter_base"] - out["reliever"]
    out["cost_index"] = out["starter_index"] - out["reliever"]
    return out


def hook_card(game_pk: int, pitcher: int, ctx: dict | None = None, season: int = 2026, names: dict | None = None,
              from_times: int = 2) -> pd.DataFrame:
    """The exposure-aware hook card for one start: at each decision point from the `from_times` time through,
    the next three hitters (by lineup slot), each one's exposure index and expected run cost against the
    reliever baseline, with and without the index, and what the manager did.

    ctx: {"pa": PA table with usage and idx for the season, "use": usage table, "cost", "ppa", "model",
    "quality": pitcher_quality table}; `load_context(season)` builds it from the saved study outputs.
    Run values are per 100 PAs (offense's view: positive = runs for the hitters).
    """
    ctx = ctx or load_context(season)
    g = ctx["pa"][ctx["pa"]["game_pk"].eq(game_pk)]
    d = decisions(g, ctx["use"], ctx["cost"], ctx["ppa"])
    d = d[d["pitcher"].eq(pitcher) & d["prior_pa"].ge(from_times - 1)]
    q = ctx["quality"].set_index(["pitcher", "game_pk"])["q"].get((pitcher, game_pk), 0.0)
    rows = []
    for _, r in d.iterrows():
        e = expected_vs_reliever([r[f"times_{j}"] + 1 for j in range(3)], [r[f"same_hand_{j}"] for j in range(3)],
                                 [r[f"idx_{j}"] for j in range(3)], [q] * 3, ctx["model"])
        row = {"after_bf": int(r["bf"]), "inning": int(r["inning"]), "outs": int(r["outs"]), "base": int(r["base"]),
               "lead": int(r["lead"]), "pitches": int(r["pitch_count"]), "removed": int(r["removed"])}
        for j in range(3):
            b = r[f"batter_{j}"]
            row[f"hitter_{j + 1}"] = (names or {}).get(int(b), str(int(b))) if pd.notna(b) else ""
            row[f"times_{j + 1}"] = int(r[f"times_{j}"]) + 1
            row[f"idx_{j + 1}"] = 100 * r[f"idx_{j}"]
            row[f"cost_base_{j + 1}"] = 100 * e["cost_base"].iloc[j]
            row[f"cost_index_{j + 1}"] = 100 * e["cost_index"].iloc[j]
        row["next3_cost_base"] = sum(row[f"cost_base_{j + 1}"] for j in range(3)) / 100
        row["next3_cost_index"] = sum(row[f"cost_index_{j + 1}"] for j in range(3)) / 100
        rows.append(row)
    return pd.DataFrame(rows)


def load_context(season: int = 2026, out_dir: Path | None = None) -> dict:
    """The card's inputs from a finished `run()` (data/edge/hook/)."""
    import json

    D = Path(out_dir or OUT_DIR)
    meta = json.loads((D / "summary.json").read_text())
    model = {"cells": pd.read_parquet(D / "card_cells.parquet"), "reliever": pd.read_parquet(D / "card_reliever.parquet"),
             "league_starter": meta["league_starter"], "k_pitcher": meta["k_pitcher"]}
    return {"pa": pd.read_parquet(D / f"pai_{season}.parquet"), "use": pd.read_parquet(D / f"use_{season}.parquet"),
            "cost": meta["cost"], "ppa": meta["ppa"], "model": model,
            "quality": pd.read_parquet(D / f"quality_{season}.parquet")}


# ---------------------------------------------------------------- the study

def _keys(d: pd.DataFrame, batter: str = "batter") -> pd.DataFrame:
    d = d.copy()
    yr = d["game_year"].astype(str)
    d["pkey"] = d["pitcher"].astype(str) + "|" + yr
    d["bkey"] = d[batter].astype("Int64").astype(str) + "|" + yr
    tto = d["prior_pa"].clip(upper=3).astype(str)
    d["pkey_t"] = d["pkey"] + "|" + tto
    d["pkey_ts"] = d["pkey_t"] + "|" + d["stand"].astype(str)
    return d


def outcome_frame(pai: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Starter PAs (no mid-PA change, usage known) with y = 100 x run value (runs per 100 PAs), x = 100 x idx,
    xf = 100 x the flat-cost index, fixed-effect keys and the PA controls. Returns (frame, control names)."""
    d = pai[pai["starter"].eq(1) & pai["mid_pa_change"].eq(0) & pai["use_src"].ne("none")].copy()
    d["y"], d["x"], d["xf"] = 100 * d["rv"], 100 * d["idx"], 100 * d["idx_flat"]
    d = _keys(d)
    c = pa_controls(d)
    d = d.drop(columns=[k for k in c.columns if k in d.columns])
    return pd.concat([d, c], axis=1), list(c.columns)


def _slope_row(t: pd.DataFrame, term: str, spec: str, season: int) -> dict:
    from scipy.stats import norm

    r = t.set_index("term").loc[term]
    return {"season": season, "spec": spec, "coef": r["coef"], "se": r["se"], "p": r["p"],
            "p_vs_1": float(2 * norm.sf(abs((r["coef"] - 1) / r["se"]))), "n": int(r["n"]), "clusters": int(r["clusters"])}


def calibration(D: pd.DataFrame, cols: list[str], season: int, matchup_col: str | None = None) -> pd.DataFrame:
    """The calibration slope (PA run value per 100 PAs on the index in the same units) under each spec."""
    no_seen = [c for c in cols if c != "seen_total"]
    fe = ["pkey", "bkey"]
    rows = [_slope_row(fe_ols(D, "y", ["x"] + cols, fe), "x", "main", season),
            _slope_row(fe_ols(D, "y", ["x"] + no_seen, fe), "x", "without pitches-seen control", season),
            _slope_row(fe_ols(D, "y", ["x"] + cols, ["pkey_t", "bkey"]), "x", "pitcher-season x times-through FE", season),
            _slope_row(fe_ols(D, "y", ["x"] + cols, ["pkey_ts", "bkey"]), "x", "pitcher-season x times-through x batter side FE", season),
            _slope_row(fe_ols(D, "y", ["xf"] + cols, fe), "xf", "one average cost for every pitch type", season)]
    if matchup_col:
        rows.append(_slope_row(fe_ols(D, "y", ["x", matchup_col] + cols, fe), "x", "+ hitter vs this pitcher's mix (season)", season))
    late = D[pd.to_datetime(D["game_date"]) >= pd.to_datetime(D["game_date"]).min() + pd.Timedelta(days=30)]
    rows.append(_slope_row(fe_ols(late, "y", ["x"] + cols, fe), "x", "after the season's first 30 days", season))
    for k, lab in ((1, "second time through only"), (2, "third time through only")):
        sub = D[D["prior_pa"].isin([0, k])]
        rows.append(_slope_row(fe_ols(sub, "y", ["x"] + cols, fe), "x", lab, season))
    return pd.DataFrame(rows)


def woba_calibration(D: pd.DataFrame, cols: list[str], runs_per_woba: float, season: int) -> dict:
    """The same test on wOBA (PAs with a wOBA denominator). A calibrated index moves wOBA by
    (index in runs) / runs_per_woba, so the slope is reported relative to that (1.0 = calibrated)."""
    W = D[D["woba_denom"].eq(1)].copy()
    W["yw"] = 1000 * W["woba_value"]
    t = fe_ols(W, "yw", ["x"] + cols, ["pkey", "bkey"], report=["x"])
    expected = 10 / runs_per_woba              # wOBA points per 1 run / 100 PAs
    r = t.iloc[0]
    return {"season": season, "coef_woba_pts": r["coef"], "se": r["se"], "expected_woba_pts": expected,
            "slope": r["coef"] / expected, "slope_se": r["se"] / expected, "p": r["p"], "n": int(r["n"])}


def runs_per_woba(pa: pd.DataFrame) -> float:
    """Runs per unit of wOBA at the PA level (OLS slope of run value on woba_value, PAs with a denominator)."""
    d = pa[pa["woba_denom"].eq(1)]
    x, y = d["woba_value"].to_numpy(float), d["rv"].to_numpy(float)
    return float(np.cov(x, y)[0, 1] / np.var(x, ddof=1))


def mechanism(D: pd.DataFrame, cols: list[str], cost: dict, wcost: dict, ppa: float, p_mix: pd.DataFrame,
              season: int) -> pd.DataFrame:
    """Why might the index not aggregate? (1) Does the mechanism (whiffs) show up at the PA level? Whiff rate per
    swing in the PA on the same index built with the per-type WHIFF costs (whiff points lost per swing; a
    calibrated index has slope -1), without and with the PA's realized swing mix held fixed. (2) Split the run
    index into the part usage predicts from pitches seen (seen_total x usage) and the hitter-specific deviation
    (which pitches he was actually shown). (3) Does the pitcher's mix in this PA move toward the types the hitter
    has seen more of than usage implies?"""
    T = list(COST_TYPES)
    rows = []
    W = D[D["pa_swings"].gt(0)].copy()
    W["wr"] = 100 * W["pa_whiffs"] / W["pa_swings"]
    W["xw"] = 100 * exposure_index(W, W, wcost, 1.0)
    W.loc[W["seen_total"].eq(0), "xw"] = 0.0
    mix = []
    for t in T[1:]:
        W[f"swmix_{t}"] = W[f"sw_{t}"] / W["pa_swings"]
        mix.append(f"swmix_{t}")
    for lab, xs in (("whiff rate per swing on the whiff index (calibrated = -1)", ["xw"]),
                    ("same, holding the PA's swing mix by pitch type fixed", ["xw"] + mix)):
        r = fe_ols(W, "wr", xs + cols, ["pkey", "bkey"], report=["xw"]).iloc[0]
        rows.append({"season": season, "test": lab, "coef": r["coef"], "se": r["se"], "p": r["p"], "n": int(r["n"]),
                     "sd": float(W.loc[W["prior_pa"].ge(1), "xw"].std())})
    exp_seen = pd.DataFrame({f"seen_{t}": D["seen_total"] * D[f"use_{t}"].fillna(0) for t in T}, index=D.index)
    D = D.copy()
    D["xe"] = 100 * exposure_index(exp_seen, D, cost, ppa)
    D["xd"] = D["x"] - D["xe"]
    t = fe_ols(D, "y", ["xe", "xd"] + cols, ["pkey", "bkey"], report=["xe", "xd"])
    rows += [{"season": season, "test": {"xe": "index: part usage predicts", "xd": "index: hitter-specific deviation"}[r.term],
              "coef": r.coef, "se": r.se, "p": r.p, "n": int(r.n), "sd": float(D.loc[D["prior_pa"].ge(1), r.term].std())}
             for r in t.itertuples()]
    q = p_mix.copy()
    q["pt"] = q["pitch_type"].where(q["pitch_type"].isin(T), "OT")
    mix = q.groupby(["game_pk", "at_bat_number", "pitcher", "pt"]).size().unstack(fill_value=0)
    mix = mix.div(mix.sum(axis=1), axis=0).reindex(columns=T, fill_value=0).add_prefix("now_").reset_index()
    M = D[D["prior_pa"].ge(1)].merge(mix, on=["game_pk", "at_bat_number", "pitcher"], how="left")
    long = []
    for t_ in T:
        z = M[["pitcher", "pkey", "bkey", "seen_total", f"use_{t_}", f"seen_{t_}", f"now_{t_}"]].copy()
        z.columns = ["pitcher", "pkey", "bkey", "seen_total", "use", "seen", "now"]
        z = z[z["use"] > 0.05]
        z["dev_share"] = z["seen"] / z["seen_total"] - z["use"]
        z["resp"] = z["now"] - z["use"]
        z["ptkey"] = z["pkey"] + "|" + t_
        long.append(z)
    L = pd.concat(long, ignore_index=True)
    r = fe_ols(L, "resp", ["dev_share"], ["ptkey", "bkey"], report=["dev_share"]).iloc[0]
    rows.append({"season": season, "test": "mix response: this PA's share on the seen-share deviation",
                 "coef": r["coef"], "se": r["se"], "p": r["p"], "n": int(r["n"]), "sd": np.nan})
    real = pd.DataFrame({f"use_{t_}": M[f"now_{t_}"] for t_ in T})
    rows.append({"season": season, "test": "mean index, usage-based vs realized mix (runs/100 PA)",
                 "coef": float(M["x"].mean()), "se": np.nan, "p": np.nan, "n": len(M),
                 "sd": float(100 * exposure_index(M, real, cost, ppa).mean())})
    return pd.DataFrame(rows)


def fe_resid(D: pd.DataFrame, y: str, xcols: list[str], fe: list[str]) -> pd.Series:
    """y net of xcols and the fixed effects (residuals on the rows used; NaN elsewhere)."""
    d = _drop_singletons(D.dropna(subset=[y, *xcols]), fe)
    r = absorb(d, [y, *xcols], fe)
    keep = [c for c in xcols if r[c].abs().max() > 1e-9]
    beta = np.linalg.lstsq(r[keep].to_numpy(), r[y].to_numpy(), rcond=None)[0] if keep else np.zeros(0)
    e = r[y].to_numpy() - (r[keep].to_numpy() @ beta if keep else 0.0)
    return pd.Series(e, index=d.index).reindex(D.index)


def binned_calibration(D: pd.DataFrame, cols: list[str], q: int = 10) -> pd.DataFrame:
    """Deciles of the residualized index (net of controls and fixed effects, second time through or later)
    against the residualized run value: a calibrated index sits on the 45-degree line."""
    D = D.copy()
    D["rx"] = fe_resid(D, "x", cols, ["pkey", "bkey"])
    D["ry"] = fe_resid(D, "y", cols, ["pkey", "bkey"])
    tab, _ = decile_table(D[D["prior_pa"].ge(1)], "rx", "ry", q=q)
    return tab


def tto3_deciles(D: pd.DataFrame, cols: list[str]) -> tuple[pd.DataFrame, dict, dict, dict]:
    """Third time through: run value by decile of the index, raw; adjusted for fixed effects and every control
    except the index and pitches seen (so whatever travels with the index stays in); and adjusted for pitches
    seen as well (only the pitch-type mix of what he saw is left to the index)."""
    D = D.copy()
    adj_cols = [c for c in cols if c != "seen_total"]
    D["y_adj"] = fe_resid(D, "y", adj_cols, ["pkey", "bkey"]) + D["y"].mean()
    D["y_adj2"] = fe_resid(D, "y", cols, ["pkey", "bkey"]) + D["y"].mean()
    t3 = D[D["prior_pa"].eq(2)]
    raw, raw_diff = decile_table(t3, "x", "y")
    adj, adj_diff = decile_table(t3, "x", "y_adj")
    adj2, adj2_diff = decile_table(t3, "x", "y_adj2")
    raw["y_adj"], raw["y_adj_seen"] = adj["y_mean"], adj2["y_mean"]
    return raw, raw_diff, adj_diff, adj2_diff


def cv_compare(D: pd.DataFrame, cols: list[str], folds: int = 5, seed: int = 0, split_date: str | None = None) -> pd.DataFrame:
    """Out-of-sample forecast of PA run value without and with the index (fitted slope, and slope fixed at 1).

    Folds are whole games (5-fold) or, with split_date, a forward split (train before, test on/after). Fixed
    effects are re-estimated in each training fold with ridge shrinkage (lam = the method-of-moments constant
    for pitchers and for batters, from the training rows). Returns the paired squared-error tests."""
    fe = ["pkey", "bkey"]
    D = D.dropna(subset=["y", "x", *cols]).copy()
    if split_date:
        splits = [(D["game_date"] < split_date, D["game_date"] >= split_date)]
    else:
        rng = np.random.default_rng(seed)
        games = D["game_pk"].unique()
        fold_of = pd.Series(rng.integers(0, folds, len(games)), index=games)
        f = D["game_pk"].map(fold_of)
        splits = [(f != k, f == k) for k in range(folds)]
    preds = {m: pd.Series(np.nan, index=D.index) for m in ("mean", "base", "fitted", "face")}
    for tr_m, te_m in splits:
        tr, te = D[tr_m], D[te_m]
        lam = [shrinkage_k(tr["y"], tr["pkey"]), shrinkage_k(tr["y"], tr["bkey"])]
        preds["mean"][te.index] = tr["y"].mean()
        preds["base"][te.index] = fe_fit_predict(tr, te, "y", cols, fe, lam)
        preds["fitted"][te.index] = fe_fit_predict(tr, te, "y", ["x"] + cols, fe, lam)
        preds["face"][te.index] = fe_fit_predict(tr, te, "y", cols, fe, lam, offset="x")
    ok = preds["base"].notna()
    y = D.loc[ok, "y"]
    e0 = y - preds["base"][ok]
    design = f"forward split at {split_date}" if split_date else f"{folds}-fold by game"
    rows = []
    for m, lab in (("fitted", "+ index (slope fitted in training)"), ("face", "+ index (slope fixed at 1)")):
        r = paired_mse_test(e0, y - preds[m][ok], D.loc[ok, "pitcher"])
        rows.append({**r, "model": lab, "comparison": "vs base model (controls + fixed effects)", "design": design})
    r = paired_mse_test(y - preds["mean"][ok], e0, D.loc[ok, "pitcher"])
    rows.append({**r, "model": "base model", "comparison": "vs the training mean (what controls + fixed effects buy)", "design": design})
    # the most adding the index could ever buy: its variance net of the controls and fixed effects, if its slope were 1
    rx = fe_resid(D, "x", cols, fe)
    out = pd.DataFrame(rows)
    out["max_pct_if_calibrated"] = 100 * float(rx.var()) / float((e0 ** 2).mean())
    return out


def removal_frame(dec: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Decision points from the second time through, with y = 100 x removed (percentage points), x0 / x3 =
    100 x the next hitter's / next three hitters' index (runs per 100 PAs), keys and controls."""
    D = dec[dec["prior_pa"].ge(1) & dec["next_ok"].eq(1)].copy()
    D["y"], D["x0"], D["x3"] = 100 * D["removed"], 100 * D["idx_0"], 100 * D["idx_next3"]
    D["stand"] = D["stand_0"]
    D = _keys(D, batter="next_batter")
    c = decision_controls(D)
    D = D.drop(columns=[k for k in c.columns if k in D.columns])
    return pd.concat([D, c], axis=1), list(c.columns)


REMOVAL_REPORT = ["x0", "x3", "tto_3", "tto_4", "rv_so_far", "whiffs_so_far", "velo_drop", "li", "pen_load",
                  "pc_80s", "pc_90s", "pc_100s", "pc_110+", "seen_total", "same_hand"]


def removal_models(D: pd.DataFrame, cols: list[str], season: int) -> pd.DataFrame:
    """Linear probability of removal on the index (pp per 1 run / 100 PAs), pitcher-season and next-batter-season
    fixed effects, SEs clustered by pitcher; the main specs and subsets."""
    fe = ["pkey", "bkey"]
    out = []
    med = D["pen_load"].median()
    specs = {
        "next hitter": (D, ["x0"]), "next three hitters": (D, ["x3"]), "both": (D, ["x0", "x3"]),
        "rested bullpen (below-median pitches in the last 3 days)": (D[D["pen_load"] <= med], ["x0", "x3"]),
        "start of an inning": (D[D["new_inning"].eq(1)], ["x0", "x3"]),
        "mid-inning": (D[D["new_inning"].eq(0)], ["x0", "x3"]),
        "third time through or later": (D[D["prior_pa"].ge(2)], ["x0", "x3"]),
    }
    for name, (d, xs) in specs.items():
        c = [k for k in cols if not (name.startswith("third") and k == "tto_3")]   # TTO3 is the reference there
        t = fe_ols(d, "y", xs + c, fe, report=REMOVAL_REPORT)
        t.insert(0, "spec", name)
        t.insert(0, "season", season)
        t["base_rate"] = d["y"].mean()
        out.append(t)
    return pd.concat(out, ignore_index=True)


def price_table(D_out: pd.DataFrame, cols_out: list[str], D_dec: pd.DataFrame, cols_dec: list[str]) -> pd.DataFrame:
    """Predictive vs priced: for each in-game signal, its association with the next PA's run value (starter PAs
    from the second time through, same controls; runs per 100 PAs) and with removal before that PA (pp).
    Both per one standard deviation of the signal at decision points, so they can be compared. Times through
    and pitch count are left out: with both in the models their separate coefficients aren't interpretable."""
    O = D_out[D_out["prior_pa"].ge(1)].copy()
    O = O.drop(columns=["tto_2"])
    oc = [c for c in cols_out if c != "tto_2"]
    sig = {"x": "x0", "rv_so_far": "rv_so_far", "whiffs_so_far": "whiffs_so_far", "velo_drop": "velo_drop"}
    to = fe_ols(O, "y", ["x"] + oc, ["pkey", "bkey"], report=list(sig)).set_index("term")
    tr = fe_ols(D_dec, "y", ["x0"] + cols_dec, ["pkey", "bkey"], report=list(sig.values())).set_index("term")
    labels = {"x": "Next hitter's exposure index (runs/100 PA)", "rv_so_far": "Run value allowed so far (runs)",
              "whiffs_so_far": "Whiffs so far", "velo_drop": "Fastball velocity vs first inning (mph)"}
    rows = []
    for o, r in sig.items():
        sd = float(D_dec[r].std())
        rows.append({"signal": labels[o], "sd": sd,
                     "runs_per100_per_sd": to.loc[o, "coef"] * sd, "runs_se": to.loc[o, "se"] * sd, "runs_p": to.loc[o, "p"],
                     "removal_pp_per_sd": tr.loc[r, "coef"] * sd, "removal_se": tr.loc[r, "se"] * sd, "removal_p": tr.loc[r, "p"]})
    return pd.DataFrame(rows)


def card_validation(pai: pd.DataFrame, quality: pd.DataFrame, model: dict) -> dict:
    """Does the card's starter expectation track 2026 PA run value? 100 x rv on 100 x starter_base (and the
    index deviation) with batter-season fixed effects only (the card assumes batter quality cancels)."""
    d = pai[pai["starter"].eq(1) & pai["mid_pa_change"].eq(0) & pai["use_src"].ne("none") & pai["prior_pa"].ge(1)].copy()
    d = d.merge(quality, on=["pitcher", "game_pk"], how="left")
    d["q"] = d["q"].fillna(0.0)
    e = expected_vs_reliever(d["prior_pa"].clip(upper=3) + 1, d["same_hand"], d["idx"], d["q"], model)
    e.index = d.index
    d["y"], d["s_base"] = 100 * d["rv"], 100 * e["starter_base"]
    d["dev"] = 100 * (e["starter_index"] - e["starter_base"])
    d = _keys(d)
    t1 = fe_ols(d, "y", ["s_base"], ["bkey"]).iloc[0]
    t2 = fe_ols(d, "y", ["s_base", "dev"], ["bkey"]).set_index("term")
    rel = model["reliever"].set_index("same_hand").loc[-1, "rv"]
    return {"slope_base": t1["coef"], "slope_base_se": t1["se"], "n": int(t1["n"]),
            "slope_dev": t2.loc["dev", "coef"], "slope_dev_se": t2.loc["dev", "se"], "slope_dev_p": t2.loc["dev", "p"],
            "reliever_baseline": float(rel)}


def season_value(D: pd.DataFrame, slope: float, slope_se: float, teams: int = 30) -> dict:
    """What the index could be worth to a rotation: third-time-through starter PAs in the top decile of the
    index, times their excess over the median, per team-season; at face value (slope 1) and at the
    out-of-sample slope with its 95% upper bound."""
    t3 = D[D["prior_pa"].ge(2)]
    cut, med = t3["x"].quantile(0.9), t3["x"].median()
    top = t3[t3["x"] >= cut]
    excess = float((top["x"] - med).sum()) / 100 / teams          # runs per team-season at face value
    return {"tto3_pas_per_team": len(t3) / teams, "top_decile_pas_per_team": len(top) / teams,
            "mean_excess_runs_per100": float((top["x"] - med).mean()), "face_value_runs": excess,
            "slope": slope, "estimate_runs": slope * excess, "upper95_runs": max(0.0, (slope + 1.96 * slope_se)) * excess}


def run(season: int = 2026, cost_seasons: tuple = (2024, 2025), out_dir: Path | None = None, log=print) -> dict:
    """The whole study. Costs from cost_seasons only; `season` is the out-of-sample test; earlier seasons in
    the sequence copy are reported as in-sample comparisons. Saves tables to data/edge/hook/."""
    import json
    import time

    from baseball.edge import familiarity as fam

    D_ = Path(out_dir or OUT_DIR)
    D_.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    seasons = sorted({*cost_seasons, season})
    cpath = D_ / f"costs_{cost_seasons[0]}_{str(cost_seasons[-1])[2:]}.parquet"
    costs = pd.read_parquet(cpath) if cpath.exists() else estimate_costs(cost_seasons)
    costs.to_parquet(cpath, index=False)
    cost = cost_per_pitch(costs)
    wcost = {t: -float(v) / 100 for t, v in zip(costs["pitch_type"], costs["coef"])}   # whiff prob per swing
    log(f"costs ({time.time() - t0:.0f}s)")

    # Does the per-pitch run-value contrast hold in each season on its own? (first: it needs the most memory)
    import gc

    pl = []
    for s in seasons:
        p = fam.prepare([s])
        for grp in ("fastball", "breaking", "offspeed", "cutter"):
            t = fam.fit_pairs(p[p["group"].eq(grp)].dropna(subset=["rv100"]), "rv100")
            pl.append(t[t["term"].eq("prev: same - other")].assign(season=s, group=grp))
        del p
        gc.collect()
    pitch_level = pd.concat(pl, ignore_index=True)
    log(f"pitch-level replication ({time.time() - t0:.0f}s)")

    mix_cols = ["game_pk", "game_date", "game_year", "at_bat_number", "pitcher", "batter", "stand", "pitch_type", "delta_run_exp"]
    P, PA = {}, {}
    for s in seasons:
        P[s] = load_pitches(s, mix_cols)
        PA[s] = plate_appearances(load_pitches(s))
    train = pd.concat([PA[s] for s in cost_seasons], ignore_index=True)
    ppa = pitches_per_pa(train)
    lev = leverage_table(train)
    rpw = runs_per_woba(train)
    log(f"PA tables, ppa {ppa:.3f}, runs per wOBA {rpw:.3f} ({time.time() - t0:.0f}s)")

    PAI, USE = {}, {}
    for s in seasons:
        prev = P.get(s - 1)
        use = usage_table(pd.concat([prev, P[s]]) if prev is not None else P[s])
        use = use[use["game_pk"].isin(PA[s]["game_pk"])]
        PAI[s], USE[s] = add_index(PA[s], use, cost, ppa), use
        PAI[s]["matchup"] = 100 * matchup(P[s], PAI[s], ppa=ppa)
    PAI[season].to_parquet(D_ / f"pai_{season}.parquet", index=False)
    USE[season].to_parquet(D_ / f"use_{season}.parquet", index=False)
    log(f"index ({time.time() - t0:.0f}s)")

    tables = {}
    cal, wob, mech, frames = [], [], [], {}
    for s in seasons:
        D, cols = outcome_frame(PAI[s])
        frames[s] = (D, cols)
        cal.append(calibration(D, cols, s, matchup_col="matchup"))
        wob.append(woba_calibration(D, cols, rpw, s))
        mech.append(mechanism(D, cols, cost, wcost, ppa, P[s], s))
        log(f"  calibration {s} ({time.time() - t0:.0f}s)")
    tables["calibration"] = pd.concat(cal, ignore_index=True)
    tables["woba"] = pd.DataFrame(wob)
    tables["mechanism"] = pd.concat(mech, ignore_index=True)

    tables["pitch_level"] = pitch_level
    D, cols = frames[season]
    tables["binned"] = pd.concat([binned_calibration(*frames[s]).assign(season=s) for s in seasons], ignore_index=True)
    dec_tab, raw_diff, adj_diff, adj2_diff = tto3_deciles(D, cols)
    tables["tto3_deciles"] = dec_tab
    tables["cv"] = pd.concat([cv_compare(D, cols), cv_compare(D, cols, split_date=f"{season}-08-01")], ignore_index=True)
    log(f"deciles and CV ({time.time() - t0:.0f}s)")

    rem, dec_frames = [], {}
    for s in seasons:
        dec = decisions(PAI[s], USE[s], cost, ppa)
        dec["li"] = add_leverage(dec, lev)
        dec = dec.merge(bullpen_load(PA[s]), on=["fld_team", "game_date"], how="left")
        dec["pen_load"] = dec["pen_load"].fillna(0) / 100
        Dd, cd = removal_frame(dec)
        dec_frames[s] = (Dd, cd)
        rem.append(removal_models(Dd, cd, s))
        log(f"  removal {s} ({time.time() - t0:.0f}s)")
    tables["removal"] = pd.concat(rem, ignore_index=True)
    tables["price"] = price_table(D, cols, *dec_frames[season])

    st_last = PA[cost_seasons[-1]].query("starter == 1 and mid_pa_change == 0")
    k_mom = shrinkage_k(st_last["rv"], st_last["pitcher"])
    train_i = pd.concat([PAI[s] for s in cost_seasons], ignore_index=True)
    league_st = float(train_i.query("starter == 1 and mid_pa_change == 0")["rv"].mean())
    k_p, k_grid = fit_quality_k(PA[cost_seasons[0]], PA[cost_seasons[1]], league_st)
    tables["quality_k"] = k_grid
    model = card_model(train_i, k_p)
    quality = pitcher_quality(PA[season - 1], PA[season], model["league_starter"], k_p)
    quality.to_parquet(D_ / f"quality_{season}.parquet", index=False)
    model["cells"].to_parquet(D_ / "card_cells.parquet", index=False)
    model["reliever"].to_parquet(D_ / "card_reliever.parquet", index=False)
    cv = card_validation(PAI[season], quality, model)
    rel_now = reliever_baseline(PA[season]).set_index("same_hand").loc[-1]
    cv.update({"reliever_actual_oos": float(rel_now["rv"]), "reliever_actual_n": int(rel_now["n"])})
    main = tables["calibration"].query("season == @season and spec == 'main'").iloc[0]
    value = season_value(D, float(main["coef"]), float(main["se"]))

    # how often the index (at face value) flips the card's call for the next hitter, and removal by the card's cost
    Dd, _ = dec_frames[season]
    Dd = Dd.merge(quality, on=["pitcher", "game_pk"], how="left")
    e = expected_vs_reliever(Dd["prior_pa"].clip(upper=3) + 1, Dd["same_hand"], Dd["idx_0"], Dd["q"].fillna(0), model)
    e.index = Dd.index
    flips = float((np.sign(e["cost_base"]) != np.sign(e["cost_index"])).mean())
    Dd["cost_base"] = 100 * e["cost_base"]
    Dd["cost_bin"] = pd.cut(Dd["cost_base"], [-99, 0, 1, 2, 3, 4, 99], labels=["<0", "0-1", "1-2", "2-3", "3-4", "4+"])
    tables["removal_by_cost"] = Dd.groupby("cost_bin", observed=True).agg(removed_pct=("y", "mean"), n=("y", "size")).reset_index()
    tables["removal_by_cost"]["cost_bin"] = tables["removal_by_cost"]["cost_bin"].astype(str)
    tables["costs"] = costs

    # every season's main slope, pooled by inverse variance, with Cochran's Q for heterogeneity
    from scipy.stats import chi2, norm

    m = tables["calibration"].query("spec == 'main'")
    w = 1 / m["se"] ** 2
    pooled = float((w * m["coef"]).sum() / w.sum())
    pooled_se = float(np.sqrt(1 / w.sum()))
    q_stat = float((w * (m["coef"] - pooled) ** 2).sum())
    pooled_cal = {"slope": pooled, "se": pooled_se, "p_vs_1": float(2 * norm.sf(abs(pooled - 1) / pooled_se)),
                  "Q": q_stat, "Q_p": float(chi2.sf(q_stat, len(m) - 1)), "seasons": m["season"].tolist()}

    for name, t in tables.items():
        t.to_parquet(D_ / f"{name}.parquet", index=False)
    summary = {
        "season": season, "cost_seasons": list(cost_seasons), "cost": cost, "whiff_cost": wcost, "ppa": ppa,
        "runs_per_woba": rpw, "k_usage": K_USAGE, "k_pitcher": k_p, "k_pitcher_moments": k_mom,
        "league_starter": model["league_starter"], "pooled_calibration": pooled_cal,
        "tto3_decile_adjusted_with_seen": adj2_diff,
        "starter_pas": {str(s): int(len(frames[s][0])) for s in seasons},
        "decisions": {str(s): int(len(dec_frames[s][0])) for s in seasons},
        "use_src": {str(s): PAI[s].loc[PAI[s]["starter"].eq(1), "use_src"].value_counts().to_dict() for s in seasons},
        "index_by_times": {str(k): v for k, v in D.groupby(D["prior_pa"].clip(upper=3))["x"].agg(["mean", "std"]).round(4).to_dict("index").items()},
        "tto3_decile_raw": raw_diff, "tto3_decile_adjusted": adj_diff, "card_validation": cv, "season_value": value,
        "call_flips_next_hitter": flips, "games": int(PA[season]["game_pk"].nunique()),
        "source": "Baseball Savant Statcast, regular season",
    }
    (D_ / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    log(f"done ({time.time() - t0:.0f}s)")
    return {"summary": summary, **tables}


def figure(out_path: Path | None = None, tables_dir: Path | None = None) -> Path:
    """The report figure. Left: binned calibration of the index by season (the out-of-sample season in ink).
    Right: for four in-game signals, the association with the next PA's run value against the association with
    removal before it, both per standard deviation, with 95% intervals clustered by pitcher."""
    import json

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from baseball.viz import GRID, INK, MUTED, _style

    D = Path(tables_dir or OUT_DIR)
    out_path = Path(out_path or D / "hook.png")
    S = json.loads((D / "summary.json").read_text())
    cal, pr = pd.read_parquet(D / "calibration.parquet"), pd.read_parquet(D / "price.parquet")
    wob, mech = pd.read_parquet(D / "woba.parquet"), pd.read_parquet(D / "mechanism.parquet")
    oos = S["season"]

    def cal_row(season, spec):
        r = cal[(cal["season"] == season) & (cal["spec"] == spec)].iloc[0]
        return r["coef"], r["se"]

    rows = []   # (label, slope, se, is_out_of_sample, group)
    for s in sorted(cal["season"].unique()):
        rows.append((f"Run value, {s}" + (" (out of sample)" if s == oos else " (in sample)"), *cal_row(s, "main"), s == oos, "rv"))
    rows.append((f"Run value, {oos}, pitcher x times-through x side FE", *cal_row(oos, "pitcher-season x times-through x batter side FE"), True, "rv"))
    w = wob[wob["season"] == oos].iloc[0]
    rows.append((f"wOBA, {oos}", w["slope"], w["slope_se"], True, "rv"))
    pc = S["pooled_calibration"]
    rows.append((f"Run value, pooled {min(pc['seasons'])}-{str(max(pc['seasons']))[2:]}", pc["slope"], pc["se"], False, "rv"))
    for test, lab in (("whiff rate per swing on the whiff index (calibrated = -1)", "Whiffs per swing"),
                      ("same, holding the PA's swing mix by pitch type fixed", "Whiffs per swing, swing mix held")):
        m = mech[(mech["season"] == oos) & (mech["test"] == test)].iloc[0]
        rows.append((f"{lab}, {oos}", -m["coef"], m["se"], True, "whiff"))    # sign flipped: 1 = calibrated

    fig, (a, c) = plt.subplots(1, 2, figsize=(14, 5.6), gridspec_kw={"width_ratios": [1, 1]})
    yy = np.arange(len(rows))[::-1]
    a.axvline(0, color=GRID, lw=1.2)
    a.axvline(1, color=MUTED, lw=1, ls="--")
    a.text(1.03, yy[-1] - 0.75, "calibrated", color=MUTED, fontsize=8.5)
    a.text(0.03, yy[-1] - 0.75, "no signal", color=MUTED, fontsize=8.5)
    a.set_ylim(yy[-1] - 1, yy[0] + 0.6)
    for y, (lab, b, se, is_oos, grp) in zip(yy, rows):
        col = INK if is_oos else "#9a9a9a"
        a.errorbar(b, y, xerr=1.96 * se, fmt="s" if grp == "whiff" else "o", color=col, ms=6, capsize=3, lw=1.6)
    a.set_yticks(yy)
    a.set_yticklabels([r[0] for r in rows], fontsize=8.5)
    a.axhline(yy[-2] + 0.5, color=MUTED, lw=0.8)
    a.set_xlabel("Calibration slope (1 = the index means what it says), 95% interval")
    a.set_title("Out of sample the index predicts whiffs, not runs", loc="left", fontsize=12, fontweight="bold")
    _style(a)

    short = {"Next hitter's exposure index (runs/100 PA)": ("Exposure index\n(next hitter)", (10, 10)),
             "Run value allowed so far (runs)": ("Run value allowed\nso far", (10, 4)),
             "Whiffs so far": ("Whiffs so far", (-20, 12)),
             "Fastball velocity vs first inning (mph)": ("Fastball velocity\nup vs first inning", (10, -30))}
    c.axhline(0, color=GRID, lw=1)
    c.axvline(0, color=GRID, lw=1)
    for r in pr.itertuples():
        is_idx = r.signal.startswith("Next hitter")
        col = INK if is_idx else MUTED
        c.errorbar(r.runs_per100_per_sd, r.removal_pp_per_sd, xerr=1.96 * r.runs_se, yerr=1.96 * r.removal_se,
                   fmt="o", color=col, ms=7 if is_idx else 6, capsize=3, lw=1.4)
        lab, off = short.get(r.signal, (r.signal, (8, 6)))
        c.annotate(lab, (r.runs_per100_per_sd, r.removal_pp_per_sd), xytext=off, textcoords="offset points",
                   fontsize=8.5, color=INK, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85))
    c.set_xlabel("Next PA's run value per 1 SD of the signal (runs per 100 PAs)")
    c.set_ylabel("Chance the starter is removed before it, per 1 SD (points)")
    c.set_title("Managers act on runs allowed, not exposure", loc="left", fontsize=12, fontweight="bold")
    _style(c)
    n_pa, n_dec = S["starter_pas"][str(oos)], S["decisions"][str(oos)]
    first = min(int(s) for s in S["starter_pas"])
    fig.text(0.01, 0.005,
             f"MLB regular seasons {first}-{str(oos)[2:]}, Statcast via Baseball Savant. Index costs estimated on "
             f"{S['cost_seasons'][0]}-{str(S['cost_seasons'][-1])[2:]} only, so {oos} is out of sample. Left: {n_pa:,} starter PAs in "
             f"{oos}; pitcher-season and batter-season fixed effects, times through, pitch count, in-game form,\nplatoon, base-out "
             "state, score and pitches seen held fixed; whiff slopes sign-flipped so 1 = calibrated. Right: "
             f"{oos}; {n_dec:,} decisions from the second time through (removal) and the matching starter PAs (run value); same "
             "controls\nplus leverage, bullpen workload and lineup slot. Associations, not causal effects. 95% intervals "
             "clustered by pitcher.", fontsize=7.3, color="#555")
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    return out_path
