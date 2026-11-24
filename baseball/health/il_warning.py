"""Velocity and stuff decline as an injured-list early warning.

The question: after a pitcher's outing, does a drop in his fastball velocity, spin, shape or release, measured
against his own regressed baseline, say he is more likely to go on the injured list (IL) in the next N days than
what a club already knows without tracking data? Fit on 2024-25, scored on 2026.

Grain
- `appearances()`: one row per pitcher outing (pitcher, game_pk), regular season. Fastball physics are kept per
  fastball type (FF, SI, FC) in `type_games()`: one row per (pitcher, game_pk, type) with that type's pitch count
  and game means.
- `il_placements()`: one row per IL placement (person, effective date) from MLB Stats API transactions.
  Transfers (15-day to 60-day) and activations are not placements and are dropped.

The baseline (per pitcher, season and fastball type, for each metric m)
- Each game mean x_g is first adjusted by the league's month-of-season curve for that type and metric
  (`season_curve()`, fit on the training seasons), so the normal spring-to-summer velocity rise is not a "change".
- Each game carries noise v_g = gamma2 + sigma2 / n_g, the two-level physics model of the Reliability Atlas
  (day-to-day plus pitch-to-pitch), re-estimated here on the training seasons only (`noise_params()`).
- Prior: his last-season mean for the type (precision-weighted), with variance (its own noise + delta2, the
  year-to-year change in true level). With no last season, the league mean for the type with variance tau2.
- Baseline before a window of his last k outings = the normal-normal posterior from the prior and every earlier
  game of that type this season:  mean = (mu0/s0 + sum x_g/v_g) / (1/s0 + sum 1/v_g),  var = 1 / (...).
- Window k (k = 1: this outing; k = 3: his last three outings with the type): the precision-weighted mean of
  those games and its variance.
- drop_m_k = baseline - window (positive = below his baseline), z_m_k = drop / sqrt(var_baseline + var_window).
- Outing-level features combine FF, SI and FC by the window's pitch count of each type.

Labels
- y = 1 if the pitcher has an IL placement of the chosen injury category with an effective date in (t, t + H],
  t = the outing's date. Effective dates are the retroactive dates the club chose, so an alert after an outing on
  day t is information before the placement took effect.

Models (logistic, fit on 2024-25 outings, scored on 2026 outings)
- Naive: what a club knows without tracking data: role, age, an IL placement in the last 365 days, pitches this
  outing, this outing's pitches against his recent norm, days of rest, month.
- Tracking: the naive model plus the velocity, spin, ride and release drops.
"""
from __future__ import annotations

import json
import math
import re
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from baseball.edge.familiarity import DATA, seq_parts
from baseball.stats import benjamini_hochberg, wilson

OUT_DIR = DATA / "edge" / "il_warning"
TX_DIR = DATA / "raw" / "transactions"
REPORT_OUT = Path(__file__).resolve().parents[2] / "reports" / "outputs" / "il-warning-2026.json"
FB_TYPES = ("FF", "SI", "FC")
METRICS = {               # name -> (column, scale): game means are of column * scale
    "velo": ("release_speed", 1.0),
    "spin": ("release_spin_rate", 1.0),
    "ivb": ("pfx_z", 12.0),
    "ext": ("release_extension", 1.0),
    "relz": ("release_pos_z", 12.0),
    "arm": ("arm_angle", 1.0),
}
UNITS = {"velo": "mph", "spin": "rpm", "ivb": "in", "ext": "ft", "relz": "in", "arm": "deg"}
PITCH_COLUMNS = ["game_pk", "game_date", "game_year", "at_bat_number", "pitch_number", "pitcher", "inning_topbot",
                 "home_team", "away_team", "pitch_type", "age_pit", "description"] + [c for c, _ in METRICS.values()]
NO_PITCH = ("automatic_ball", "automatic_strike")     # pitch-clock violations: no pitch was thrown
NAIVE = ["starter", "age", "il_365", "pitches100", "pitch_ratio", "log_rest", "m5", "m6", "m7", "m8", "m9"]
TRACK_VELO = ["z_velo_1", "z_velo_3"]
TRACK = TRACK_VELO + ["z_spin_1", "z_spin_3", "z_ivb_3", "z_ext_3", "z_relz_3", "z_arm_3"]
MIN_FB_BASELINE = 85.0    # outings whose fastball baseline is below this are position players pitching: dropped
TEAMS = 30


# ---------------------------------------------------------------- injuries

ARM = re.compile(r"elbow|\bucl\b|ulnar|tommy john|forearm|flexor|pronator|extensor|shoulder|\bshould\b|rotator|"
                 r"labrum|labral|capsul|\blat\b|lats\b|latissimus|teres|triceps|biceps|\barm\b|thoracic outlet|"
                 r"scapul|median nerve|radial nerve|subscap|\bulna\b|brachial|\bac joint\b|acromio|"
                 r"\belnow\b|\bunar\b")   # the last two are misspellings that appear in MLB's own transaction text
HAND = re.compile(r"finger|blister|\bnail|thumb|wrist|\bhand\b")
TRUNK = re.compile(r"oblique|back|lumbar|spine|\brib|intercostal|abdom|neck|\bside\b|pectoral|trapez|\bcore\b")
LOWER = re.compile(r"hamstring|groin|adductor|\bhip\b|knee|ankle|calf|\bfoot|\btoe|quad|glute|achilles|plantar|"
                   r"\bleg\b|\bacl\b|patell|meniscus|shin|heel")
ILLNESS = re.compile(r"illness|viral|infection|concussion|appendic|covid|flu\b|undisclosed")


def classify_injury(reason: str) -> str:
    """One category per placement from its reason text: arm, hand, trunk, lower, illness, other, or unspecified.
    Arm comes first, except that a hip labrum is lower body."""
    r = (reason or "").strip().lower()
    if not r:
        return "unspecified"
    if LOWER.search(r) and re.search(r"\bhip\b", r) and re.search(r"labr", r):
        return "lower"
    for name, pat in (("arm", ARM), ("hand", HAND), ("trunk", TRUNK), ("lower", LOWER), ("illness", ILLNESS)):
        if pat.search(r):
            return name
    return "other"


PLACED = re.compile(r"placed (?:[A-Z0-9]+ )?(?P<who>.+?) on the (?P<days>\d+)-day injured list"
                    r"(?: retroactive to [^.]*)?\.?\s*(?P<reason>.*)$")


def parse_placements(transactions: list[dict]) -> pd.DataFrame:
    """IL placements from Stats API transaction records. One row per (person, effective date)."""
    rows = []
    for t in transactions:
        d = t.get("description", "") or ""
        m = PLACED.search(d)
        if not m or "person" not in t:
            continue
        rows.append({"person": int(t["person"]["id"]), "name": t["person"].get("fullName", ""),
                     "team": (t.get("toTeam") or {}).get("name", ""),
                     "announced": pd.Timestamp(t.get("date")),
                     "effective": pd.Timestamp(t.get("effectiveDate") or t.get("date")),
                     "il_days": int(m.group("days")), "reason": m.group("reason").strip(),
                     "category": classify_injury(m.group("reason"))})
    out = pd.DataFrame(rows, columns=["person", "name", "team", "announced", "effective", "il_days", "reason", "category"])
    return out.sort_values(["person", "effective", "announced"]).drop_duplicates(["person", "effective"]).reset_index(drop=True)


def pull_transactions(seasons, raw: Path = TX_DIR, refresh: bool = False) -> None:
    """Every MLB transaction of each calendar year (Stats API), cached as tx_<year>.json."""
    raw.mkdir(parents=True, exist_ok=True)
    for y in seasons:
        f = raw / f"tx_{y}.json"
        if f.exists() and not refresh:
            continue
        url = f"https://statsapi.mlb.com/api/v1/transactions?startDate={y}-01-01&endDate={y}-12-31&sportId=1"
        for i in range(4):
            try:
                with urllib.request.urlopen(url, timeout=120) as r:
                    f.write_bytes(r.read())
                break
            except Exception:
                if i == 3:
                    raise
                time.sleep(3)


def il_placements(seasons, raw: Path = TX_DIR) -> pd.DataFrame:
    frames = []
    for y in seasons:
        frames.append(parse_placements(json.loads((raw / f"tx_{y}.json").read_text())["transactions"]))
    out = pd.concat(frames, ignore_index=True)
    return out.sort_values(["person", "effective"]).drop_duplicates(["person", "effective"]).reset_index(drop=True)


# ---------------------------------------------------------------- outings

def load_pitches(season: int) -> pd.DataFrame:
    parts = seq_parts(season)
    if not parts:
        raise FileNotFoundError(f"No sequence data for {season} in data/seq/. Run `bb seq {season}` first; it builds data/seq/ from the league files.")
    cols = PITCH_COLUMNS
    return pd.concat([pd.read_parquet(p, columns=cols) for p in parts], ignore_index=True)


def appearances(p: pd.DataFrame) -> pd.DataFrame:
    """One row per pitcher outing: season, date, team (the fielding side), starter (threw his team's first pitch),
    pitches thrown and age."""
    p = p.copy()
    p["thrown"] = ~p["description"].isin(NO_PITCH) if "description" in p else True
    p["team"] = np.where(p["inning_topbot"].eq("Top"), p["home_team"], p["away_team"])
    p = p.sort_values(["game_pk", "at_bat_number", "pitch_number"])
    first = p.drop_duplicates(["game_pk", "team"])[["game_pk", "team", "pitcher"]].rename(columns={"pitcher": "first_p"})
    a = (p.groupby(["pitcher", "game_pk"], as_index=False)
         .agg(game_date=("game_date", "first"), season=("game_year", "first"), team=("team", "first"),
              pitches=("thrown", "sum"), age=("age_pit", "first")))
    a = a.merge(first, on=["game_pk", "team"], how="left")
    a["starter"] = (a["pitcher"] == a["first_p"]).astype(int)
    a["game_date"] = pd.to_datetime(a["game_date"])
    a["season"] = a["season"].astype(int)
    return a.drop(columns="first_p").sort_values(["pitcher", "game_date", "game_pk"]).reset_index(drop=True)


def type_games(p: pd.DataFrame) -> pd.DataFrame:
    """One row per (pitcher, game_pk, fastball type): pitch count and the game mean of each metric, plus the
    within-game sum of squares (for the pitch-to-pitch variance)."""
    f = p[p["pitch_type"].isin(FB_TYPES)].copy()
    for m, (col, scale) in METRICS.items():
        f[m] = f[col].astype(float) * scale
    g = f.groupby(["pitcher", "game_pk", "pitch_type"])
    out = g.agg(game_date=("game_date", "first"), season=("game_year", "first"), n=("release_speed", "count"))
    for m in METRICS:
        out[m] = g[m].mean()
        out[f"{m}_n"] = g[m].count()
        out[f"{m}_ss"] = g[m].var(ddof=1) * (out[f"{m}_n"] - 1)
    out = out.reset_index().rename(columns={"pitch_type": "ptype"})
    out["game_date"] = pd.to_datetime(out["game_date"])
    out["season"] = out["season"].astype(int)
    return out[out["n"] > 0].sort_values(["pitcher", "ptype", "game_date", "game_pk"]).reset_index(drop=True)


# ---------------------------------------------------------------- training-season parameters

def season_curve(tg: pd.DataFrame) -> pd.DataFrame:
    """League month-of-season curve per type and metric: the mean of (game mean - his season mean for the type),
    by calendar month (March folded into April). Fit on the seasons passed in."""
    d = tg.copy()
    d["month"] = d["game_date"].dt.month.clip(4, 9)
    rows = []
    for m in METRICS:
        x = d.dropna(subset=[m])
        dev = x[m] - x.groupby(["pitcher", "season", "ptype"])[m].transform("mean")
        c = dev.groupby([x["ptype"], x["month"]]).mean().rename("shift").reset_index()
        c["metric"] = m
        rows.append(c)
    return pd.concat(rows, ignore_index=True)


def _adjust(tg: pd.DataFrame, curve: pd.DataFrame) -> pd.DataFrame:
    d = tg.copy()
    d["month"] = d["game_date"].dt.month.clip(4, 9)
    for m in METRICS:
        s = curve[curve["metric"].eq(m)].set_index(["ptype", "month"])["shift"]
        key = pd.MultiIndex.from_arrays([d["ptype"], d["month"]])
        d[m] = d[m].astype(float) - s.reindex(key).astype(float).fillna(0.0).to_numpy()
    return d


def noise_params(tg: pd.DataFrame, min_games: int = 3) -> pd.DataFrame:
    """Two-level noise per (type, metric), from the seasons passed in (already curve-adjusted):
    - sigma2: pooled within-game variance (pitch to pitch);
    - gamma2: variance of a pitcher's game means around his season mean for the type, net of sigma2 / n,
      with the G / (G - 1) correction for estimating the mean (pitcher-seasons with min_games games or more);
    - tau2: variance of pitcher-season means across pitchers (games >= 10), net of their own noise;
    - delta2: variance of the change in a pitcher's season mean from one season to the next (10+ games in both),
      net of both seasons' noise: the year-to-year move in true level;
    - league: the mean of pitcher-season means."""
    rows = []
    for (pt, m), _ in [((pt, m), None) for pt in FB_TYPES for m in METRICS]:
        x = tg[tg["ptype"].eq(pt)].dropna(subset=[m])
        n = x[f"{m}_n"]
        ok = n > 1
        sigma2 = float(x.loc[ok, f"{m}_ss"].sum() / (n[ok] - 1).sum()) if ok.any() else math.nan
        key = [x["pitcher"], x["season"]]
        G = x.groupby(key)[m].transform("size")
        dev = x[m] - x.groupby(key)[m].transform("mean")
        use = G >= min_games
        raw = float((dev[use] ** 2 * G[use] / (G[use] - 1)).mean())
        gamma2 = max(raw - float((sigma2 / n[use]).mean()), 1e-6)
        x = x.assign(v=gamma2 + sigma2 / n)
        ps = x.groupby(["pitcher", "season"]).agg(mean=(m, "mean"), G=(m, "size"),
                                                   vmean=("v", lambda v: 1.0 / (1.0 / v).sum()))
        big = ps[ps["G"] >= 10]
        tau2 = max(float(big["mean"].var() - big["vmean"].mean()), 1e-6)
        league = float(big["mean"].mean())
        b = big.reset_index()
        b2 = b.assign(season=b["season"] + 1).merge(b, on=["pitcher", "season"], suffixes=("_prev", ""))
        if len(b2) >= 20:
            delta2 = max(float((b2["mean"] - b2["mean_prev"]).var() - (b2["vmean"] + b2["vmean_prev"]).mean()), 1e-6)
        else:
            delta2 = math.nan
        rows.append({"ptype": pt, "metric": m, "sigma2": sigma2, "gamma2": gamma2, "tau2": tau2, "delta2": delta2,
                     "league": league, "n_pitcher_seasons": int(len(big)), "n_pairs": int(len(b2))})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- baselines and drops

def _par(d: pd.DataFrame, P: pd.DataFrame, m: str, col: str) -> np.ndarray:
    """One noise parameter of metric m for every row, by its fastball type."""
    return d["ptype"].map(P.xs(m, level="metric")[col]).to_numpy(float)


def _priors(tg_adj: pd.DataFrame, params: pd.DataFrame, m: str) -> pd.DataFrame:
    """Prior mean and variance per (pitcher, season, type) for metric m: last season's precision-weighted mean
    (variance = its noise + delta2), else the league mean for the type (variance tau2)."""
    P = params.set_index(["ptype", "metric"])
    x = tg_adj.dropna(subset=[m]).copy()
    x["v"] = _par(x, P, m, "gamma2") + _par(x, P, m, "sigma2") / np.maximum(x[f"{m}_n"].to_numpy(), 1)
    x["w"] = 1.0 / x["v"]
    x["wx"] = x["w"] * x[m]
    s = x.groupby(["pitcher", "season", "ptype"]).agg(W=("w", "sum"), WX=("wx", "sum")).reset_index()
    s["mu_prev"] = s["WX"] / s["W"]
    s["var_prev"] = 1.0 / s["W"]
    s["season"] += 1
    return s[["pitcher", "season", "ptype", "mu_prev", "var_prev"]]


def add_drops(tg: pd.DataFrame, params: pd.DataFrame, curve: pd.DataFrame, windows=(1, 3)) -> pd.DataFrame:
    """For every (pitcher, game, type): the baseline before each window, the window mean, the drop and its z.
    Columns: drop_<m>_<k>, z_<m>_<k>, base_<m>_<k>, win_<m>_<k>, prior_<m> ("last" or "league")."""
    d = _adjust(tg, curve).sort_values(["pitcher", "season", "ptype", "game_date", "game_pk"]).reset_index(drop=True)
    P = params.set_index(["ptype", "metric"])
    for m in METRICS:
        pri = _priors(d, params, m)
        e = d[["pitcher", "season", "ptype"]].merge(pri, on=["pitcher", "season", "ptype"], how="left")
        delta2, tau2, league = _par(d, P, m, "delta2"), _par(d, P, m, "tau2"), _par(d, P, m, "league")
        has = e["mu_prev"].notna().to_numpy()
        mu0 = np.where(has, e["mu_prev"].to_numpy(), league)
        s0 = np.where(has, e["var_prev"].to_numpy() + delta2, tau2)
        d[f"prior_{m}"] = np.where(has, "last", "league")
        v = _par(d, P, m, "gamma2") + _par(d, P, m, "sigma2") / np.maximum(d[f"{m}_n"].to_numpy(), 1)
        ok = d[m].notna().to_numpy()
        w = np.where(ok, 1.0 / v, 0.0)
        wx = np.where(ok, w * d[m].fillna(0.0).to_numpy(), 0.0)
        grp = d.groupby(["pitcher", "season", "ptype"]).ngroup().to_numpy()
        W = pd.Series(w).groupby(grp).cumsum().to_numpy()
        WX = pd.Series(wx).groupby(grp).cumsum().to_numpy()
        cnt = pd.Series(ok.astype(int)).groupby(grp).cumsum().to_numpy()
        for k in windows:
            Wk = pd.Series(W).groupby(grp).shift(k).fillna(0.0).to_numpy()      # through the game before the window
            WXk = pd.Series(WX).groupby(grp).shift(k).fillna(0.0).to_numpy()
            ck = pd.Series(cnt).groupby(grp).shift(k).fillna(0).to_numpy()
            pos = pd.Series(np.ones(len(d))).groupby(grp).cumsum().to_numpy()   # 1-based game index within the group
            A = 1.0 / s0 + Wk
            base = (mu0 / s0 + WXk) / A
            ww, wxw = W - Wk, WX - WXk
            full = (pos >= k) & (cnt - ck == k) & ok
            win = np.where(full & (ww > 0), wxw / np.where(ww > 0, ww, 1.0), np.nan)
            var_w = np.where(full & (ww > 0), 1.0 / np.where(ww > 0, ww, 1.0), np.nan)
            d[f"base_{m}_{k}"] = base
            d[f"bvar_{m}_{k}"] = 1.0 / A
            d[f"win_{m}_{k}"] = win
            d[f"drop_{m}_{k}"] = base - win
            d[f"z_{m}_{k}"] = (base - win) / np.sqrt(1.0 / A + var_w)
            d[f"games_before_{k}"] = ck
    return d


def outing_features(app: pd.DataFrame, drops: pd.DataFrame, windows=(1, 3)) -> pd.DataFrame:
    """Combine the per-type drops into one row per outing, weighting each fastball type by its pitches in the
    window. Adds the fastball baseline (velocity, k = 1), how many earlier fastball games the baseline has seen,
    and whether its prior is last season."""
    d = drops.copy()
    for k in windows:
        d[f"wt_{k}"] = d.groupby(["pitcher", "season", "ptype"])["n"].transform(
            lambda s: s.rolling(k, min_periods=k).sum())
    cols = {}
    for k in windows:
        wk = d[f"wt_{k}"]
        for m in METRICS:
            for kind in ("drop", "z"):
                c = f"{kind}_{m}_{k}"
                ok = d[c].notna() & wk.notna()
                d[f"_w_{c}"] = np.where(ok, wk, 0.0)
                d[f"_wx_{c}"] = np.where(ok, wk * d[c].fillna(0.0), 0.0)
                cols[c] = (f"_wx_{c}", f"_w_{c}")
    d["_bw"] = d["n"]
    d["_bx"] = d["n"] * d["base_velo_1"]
    d["_last"] = d["n"] * d["prior_velo"].eq("last")
    d["_gb"] = d["n"] * d["games_before_1"]
    agg = d.groupby(["pitcher", "game_pk"])[[x for pair in cols.values() for x in pair] + ["_bw", "_bx", "_last", "_gb", "n"]].sum()
    out = pd.DataFrame(index=agg.index)
    for c, (wx, w) in cols.items():
        out[c] = np.where(agg[w] > 0, agg[wx] / agg[w].where(agg[w] > 0, 1.0), np.nan)
    out["fb_pitches"] = agg["n"]
    out["fb_base_velo"] = agg["_bx"] / agg["_bw"]
    out["prior_last_share"] = agg["_last"] / agg["_bw"]
    out["fb_games_before"] = agg["_gb"] / agg["_bw"]
    return app.merge(out.reset_index(), on=["pitcher", "game_pk"], how="left")


# ---------------------------------------------------------------- context and labels

def add_context(a: pd.DataFrame, il: pd.DataFrame) -> pd.DataFrame:
    """The naive model's inputs: days of rest (log), pitches (per 100), pitches against the mean of his previous
    five outings this season in the same role (1 when there are none), an IL placement effective in the 365 days
    up to the outing, and month dummies (March folded into April)."""
    a = a.sort_values(["pitcher", "game_date", "game_pk"]).copy()
    g = a.groupby(["pitcher", "season"])
    rest = (a["game_date"] - g["game_date"].shift(1)).dt.days
    a["rest"] = rest
    a["log_rest"] = np.log1p(rest.fillna(rest.median()).clip(0, 60))
    a["pitches100"] = a["pitches"] / 100.0
    prev = a.groupby(["pitcher", "season", "starter"])["pitches"].transform(
        lambda s: s.shift(1).rolling(5, min_periods=1).mean())
    a["pitch_ratio"] = (a["pitches"] / prev).fillna(1.0).clip(0, 3)
    a["age"] = a["age"].astype(float)
    month = a["game_date"].dt.month.clip(4, 9)
    for mth in range(4, 10):
        a[f"m{mth}"] = (month == mth).astype(int)
    eff = il.groupby("person")["effective"].apply(lambda s: np.sort(s.to_numpy()))
    flag = np.zeros(len(a), dtype=int)
    for i, (pid, t) in enumerate(zip(a["pitcher"].to_numpy(), a["game_date"].to_numpy())):
        e = eff.get(pid)
        if e is None:
            continue
        j = np.searchsorted(e, t, side="right")          # placements effective on or before the outing
        flag[i] = int(j > 0 and (t - e[j - 1]) <= np.timedelta64(365, "D"))
    a["il_365"] = flag
    return a


def label(a: pd.DataFrame, il: pd.DataFrame, horizon: int, categories=None, col: str = "y") -> pd.DataFrame:
    """y = 1 if an IL placement (in the categories, or any) takes effect in (t, t + horizon] days.
    Also: `days_to_il` (to that placement's effective date), `il_effective` and `last_before` (no other outing by
    him between this one and that placement)."""
    a = a.sort_values(["pitcher", "game_date", "game_pk"]).copy()
    x = il if categories is None else il[il["category"].isin(categories)]
    eff = x.groupby("person")["effective"].apply(lambda s: np.sort(s.to_numpy()))
    ann = {(int(p), np.datetime64(e, "ns")): np.datetime64(n, "ns") for p, e, n in zip(x["person"], x["effective"], x["announced"])}
    y = np.zeros(len(a), dtype=int)
    days = np.full(len(a), np.nan)
    eff_out = np.full(len(a), np.datetime64("NaT", "ns"), dtype="datetime64[ns]")
    lead_ann = np.full(len(a), np.nan)
    for i, (pid, t) in enumerate(zip(a["pitcher"].to_numpy(), a["game_date"].to_numpy())):
        e = eff.get(pid)
        if e is None:
            continue
        j = np.searchsorted(e, t, side="right")          # first placement strictly after the outing's date
        if j < len(e) and (e[j] - t) <= np.timedelta64(horizon, "D"):
            y[i] = 1
            days[i] = (e[j] - t) / np.timedelta64(1, "D")
            eff_out[i] = e[j]
            lead_ann[i] = (ann[(int(pid), np.datetime64(e[j], "ns"))] - t) / np.timedelta64(1, "D")
    a[col] = y
    a[f"{col}_days"] = days
    a[f"{col}_effective"] = eff_out
    a[f"{col}_lead_announced"] = lead_ann
    nxt = a.groupby("pitcher")["game_date"].shift(-1)
    a[f"{col}_last_before"] = (a[col].eq(1) & (nxt.isna() | (nxt > a[f"{col}_effective"]))).astype(int)
    return a


def eligible(a: pd.DataFrame) -> pd.Series:
    """Outings that can be scored: a fastball in this outing and the last three, a baseline with last season as
    prior or 3+ earlier fastball games this season, and a fastball baseline of 85 mph or more."""
    return (a["z_velo_1"].notna() & a["z_velo_3"].notna()
            & ((a["prior_last_share"] > 0.5) | (a["fb_games_before"] >= 3))
            & (a["fb_base_velo"] >= MIN_FB_BASELINE))


# ---------------------------------------------------------------- models

Z_CLIP = 5.0


def model_frame(a: pd.DataFrame) -> pd.DataFrame:
    """Eligible outings with model-ready tracking inputs: each z clipped to +/-5 (a handful of tracking glitches
    reach 15+), and a missing z (no spin or arm-angle reading) set to 0, i.e. at his baseline."""
    d = a[eligible(a)].copy()
    for c in TRACK:
        d[c] = d[c].clip(-Z_CLIP, Z_CLIP).fillna(0.0)
    return d


def logit_fit(X: np.ndarray, y: np.ndarray, clusters=None, iters: int = 50, tol: float = 1e-10) -> dict:
    """Logistic regression by Newton-Raphson (X includes the intercept column). Standard errors clustered by
    group, with the G / (G - 1) small-sample factor, or the plain inverse information when clusters is None."""
    X, y = np.asarray(X, float), np.asarray(y, float)
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        eta = np.clip(X @ b, -30, 30)
        p = 1.0 / (1.0 + np.exp(-eta))
        H = X.T @ (X * (p * (1 - p))[:, None])
        step = np.linalg.solve(H, X.T @ (y - p))
        b += step
        if np.max(np.abs(step)) < tol:
            break
    eta = np.clip(X @ b, -30, 30)
    p = 1.0 / (1.0 + np.exp(-eta))
    H = X.T @ (X * (p * (1 - p))[:, None])
    Hi = np.linalg.inv(H)
    if clusters is None:
        V = Hi
    else:
        groups, inv = np.unique(np.asarray(clusters), return_inverse=True)
        S = np.zeros((len(groups), X.shape[1]))
        np.add.at(S, inv, X * (y - p)[:, None])
        G = len(groups)
        V = Hi @ (S.T @ S) @ Hi * G / (G - 1)
    return {"coef": b, "se": np.sqrt(np.diag(V)), "cov": V}


def design(d: pd.DataFrame, cols: list[str]) -> np.ndarray:
    return np.column_stack([np.ones(len(d))] + [d[c].to_numpy(float) for c in cols])


def predict(fit: dict, X: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(X @ fit["coef"], -30, 30)))


def auc(y, p) -> float:
    """Area under the ROC curve by the rank-sum formula (ties get the average rank)."""
    y, p = np.asarray(y), np.asarray(p, float)
    n1, n0 = int(y.sum()), int(len(y) - y.sum())
    if n1 == 0 or n0 == 0:
        return math.nan
    r = pd.Series(p).rank().to_numpy()
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def log_loss(y, p) -> float:
    y, p = np.asarray(y, float), np.clip(np.asarray(p, float), 1e-12, 1 - 1e-12)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def brier(y, p) -> float:
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def recalibration(y, p) -> dict:
    """Calibration on new data: logit(P(y)) = a + b logit(p). Calibrated: a = 0, b = 1."""
    p = np.clip(np.asarray(p, float), 1e-9, 1 - 1e-9)
    lp = np.log(p / (1 - p))
    f = logit_fit(np.column_stack([np.ones(len(lp)), lp]), y)
    # calibration-in-the-large: the intercept with the slope fixed at 1 (offset logistic, one parameter)
    a = 0.0
    for _ in range(50):
        q = 1 / (1 + np.exp(-(a + lp)))
        step = (np.asarray(y, float) - q).sum() / (q * (1 - q)).sum()
        a += step
        if abs(step) < 1e-12:
            break
    return {"slope": float(f["coef"][1]), "slope_se": float(f["se"][1]), "intercept_at_slope_1": float(a),
            "mean_predicted": float(p.mean()), "observed": float(np.mean(y))}


def deciles(y, p, q: int = 10) -> pd.DataFrame:
    d = pd.DataFrame({"y": np.asarray(y), "p": np.asarray(p)})
    d["bin"] = pd.qcut(d["p"].rank(method="first"), q, labels=False)
    out = d.groupby("bin").agg(n=("y", "size"), events=("y", "sum"), predicted=("p", "mean"), observed=("y", "mean")).reset_index()
    lo, hi = zip(*[wilson(int(k), int(n)) for k, n in zip(out["events"], out["n"])])
    out["lo"], out["hi"] = lo, hi
    return out


def bootstrap_compare(y, p0, p1, clusters, reps: int = 1000, seed: int = 0) -> dict:
    """Model 1 against model 0 on the same rows: differences in AUC, log loss and Brier, with a bootstrap that
    resamples clusters (pitchers). p is the two-sided share of resampled differences on the other side of 0."""
    y, p0, p1 = np.asarray(y), np.asarray(p0, float), np.asarray(p1, float)
    groups, inv = np.unique(np.asarray(clusters), return_inverse=True)
    idx = [np.flatnonzero(inv == g) for g in range(len(groups))]
    rng = np.random.default_rng(seed)
    point = {"auc": auc(y, p1) - auc(y, p0), "log_loss": log_loss(y, p1) - log_loss(y, p0),
             "brier": brier(y, p1) - brier(y, p0)}
    draws = {k: [] for k in point}
    for _ in range(reps):
        take = np.concatenate([idx[g] for g in rng.integers(0, len(groups), len(groups))])
        yy, a0, a1 = y[take], p0[take], p1[take]
        if yy.sum() == 0:
            continue
        draws["auc"].append(auc(yy, a1) - auc(yy, a0))
        draws["log_loss"].append(log_loss(yy, a1) - log_loss(yy, a0))
        draws["brier"].append(brier(yy, a1) - brier(yy, a0))
    out = {}
    for k, v in draws.items():
        v = np.asarray(v)
        better = v > 0 if k == "auc" else v < 0          # higher AUC, lower loss is better
        p = 2 * min(better.mean(), 1 - better.mean())
        out[k] = {"diff": float(point[k]), "lo": float(np.quantile(v, 0.025)), "hi": float(np.quantile(v, 0.975)),
                  "p": float(max(p, 1 / len(v)))}
    return out


# ---------------------------------------------------------------- alert rules

def alert_table(d: pd.DataFrame, flag: np.ndarray, col: str = "y", teams: int = TEAMS, seasons: int = 1) -> dict:
    """What a staff would see from an alert rule on these outings: alerts, alerts and false alarms per club-season,
    precision (share of alerts followed by an IL placement within the horizon) with a Wilson interval, lift over
    the base rate (and an exact binomial p against it, the base rate taken as known), the share of IL stints with an alert in the horizon before them, and the median lead time to the
    effective date and to the announcement."""
    flag = np.asarray(flag, bool)
    y = d[col].to_numpy()
    n_alert, hits = int(flag.sum()), int((flag & (y == 1)).sum())
    base = float(y.mean())
    lo, hi = wilson(hits, n_alert) if n_alert else (math.nan, math.nan)
    st = d[y == 1].assign(flag=flag[y == 1])
    stints = st.groupby(["pitcher", f"{col}_effective"])["flag"].max()
    caught = int(stints.sum())
    lead = d.loc[flag & (y == 1), f"{col}_days"]
    lead_ann = d.loc[flag & (y == 1), f"{col}_lead_announced"]
    first = st[st["flag"]].sort_values("game_date").groupby(["pitcher", f"{col}_effective"]).head(1)
    from scipy.stats import binomtest
    p_vs_base = float(binomtest(hits, n_alert, base, alternative="two-sided").pvalue) if n_alert and 0 < base < 1 else math.nan
    return {"p_vs_base_rate": p_vs_base, "alerts": n_alert, "true_alerts": hits, "alerts_per_club_season": n_alert / (teams * seasons),
            "false_alarms_per_club_season": (n_alert - hits) / (teams * seasons),
            "precision": hits / n_alert if n_alert else math.nan, "precision_lo": lo, "precision_hi": hi,
            "base_rate": base, "lift": (hits / n_alert) / base if n_alert and base else math.nan,
            "stints": int(len(stints)), "stints_caught": caught,
            "share_caught": caught / len(stints) if len(stints) else math.nan,
            "median_days_to_effective": float(lead.median()) if len(lead) else math.nan,
            "median_days_first_alert_to_effective": float(first[f"{col}_days"].median()) if len(first) else math.nan,
            "median_days_to_announced": float(lead_ann.median()) if len(lead_ann) else math.nan}


def pick_threshold(train: pd.DataFrame, grid=(0.5, 1.0, 1.5, 2.0, 2.5, 3.0), max_false: float = 10.0,
                   col: str = "y", seasons: int = 2) -> float:
    """The alert threshold for the outing's velocity drop (mph), chosen on the training seasons only: the lowest
    value on the grid whose false alarms per club-season are at most max_false."""
    for t in grid:
        r = alert_table(train, train["drop_velo_1"].to_numpy() >= t, col=col, seasons=seasons)
        if r["false_alarms_per_club_season"] <= max_false:
            return float(t)
    return float(grid[-1])


# ---------------------------------------------------------------- the study

def build(seasons=(2024, 2025, 2026), train=(2024, 2025), log=print) -> dict:
    """Outings with every feature, the IL placements, and the training-season parameters."""
    pitches = {s: load_pitches(s) for s in seasons}
    app = pd.concat([appearances(pitches[s]) for s in seasons], ignore_index=True)
    tg = pd.concat([type_games(pitches[s]) for s in seasons], ignore_index=True)
    log(f"{len(app):,} outings, {len(tg):,} fastball type-games, {sum(len(p) for p in pitches.values()):,} pitches")
    tr = tg[tg["season"].isin(train)]
    curve = season_curve(tr)
    params = noise_params(_adjust(tr, curve))
    drops = add_drops(tg, params, curve)
    a = outing_features(app, drops)
    tx_years = range(min(seasons) - 1, max(seasons) + 1)
    pull_transactions(tx_years)
    il = il_placements(tx_years)
    a = add_context(a, il)
    return {"outings": a, "il": il, "params": params, "curve": curve,
            "pitches": int(sum(len(p) for p in pitches.values())), "games": int(app["game_pk"].nunique())}


SPECS = {   # name -> (categories, horizon, early only)
    "arm_14": (["arm"], 14, False),
    "arm_7": (["arm"], 7, False),
    "arm_30": (["arm"], 30, False),
    "arm_14_early": (["arm"], 14, True),
    "any_14": (None, 14, False),
    "lower_illness_14": (["lower", "illness"], 14, False),
}


def evaluate(a: pd.DataFrame, il: pd.DataFrame, spec: str, train=(2024, 2025), test: int = 2026,
             reps: int = 1000) -> dict:
    cats, H, early = SPECS[spec]
    d = label(model_frame(a), il, H, cats)
    if early:   # drop each stint's last outing: the alert must come with at least one more outing before the IL
        d = d[d["y_last_before"].eq(0)]
    tr, te = d[d["season"].isin(train)], d[d["season"].eq(test)]
    f0 = logit_fit(design(tr, NAIVE), tr["y"], tr["pitcher"])
    f1 = logit_fit(design(tr, NAIVE + TRACK), tr["y"], tr["pitcher"])
    fv = logit_fit(design(tr, NAIVE + TRACK_VELO), tr["y"], tr["pitcher"])
    p0, p1, pv = predict(f0, design(te, NAIVE)), predict(f1, design(te, NAIVE + TRACK)), predict(fv, design(te, NAIVE + TRACK_VELO))
    coefs = []
    for name, cols, f in (("naive", NAIVE, f0), ("tracking", NAIVE + TRACK, f1), ("velocity", NAIVE + TRACK_VELO, fv)):
        for i, c in enumerate(["const"] + cols):
            z = f["coef"][i] / f["se"][i]
            coefs.append({"model": name, "term": c, "coef": float(f["coef"][i]), "se": float(f["se"][i]),
                          "odds_ratio": float(np.exp(f["coef"][i])), "p": float(math.erfc(abs(z) / math.sqrt(2)))})
    track = [r for r in coefs if r["model"] == "tracking" and r["term"] in TRACK]
    for r, qq in zip(track, benjamini_hochberg([r["p"] for r in track])):
        r["q_bh_tracking_terms"] = qq
    fr = logit_fit(design(te, NAIVE + TRACK_VELO), te["y"], te["pitcher"])     # the association, refit on the test season
    i1 = 1 + len(NAIVE)
    replication = {"term": "z_velo_1", "coef": float(fr["coef"][i1]), "se": float(fr["se"][i1]),
                   "odds_ratio": float(np.exp(fr["coef"][i1])),
                   "or_lo": float(np.exp(fr["coef"][i1] - 1.96 * fr["se"][i1])),
                   "or_hi": float(np.exp(fr["coef"][i1] + 1.96 * fr["se"][i1])),
                   "p": float(math.erfc(abs(fr["coef"][i1] / fr["se"][i1]) / math.sqrt(2)))}
    out = {"spec": spec, "categories": cats, "horizon": H, "early": early, "replication_in_test": replication,
           "train": {"outings": int(len(tr)), "events": int(tr["y"].sum()), "pitchers": int(tr["pitcher"].nunique()),
                     "stints": int(tr[tr["y"].eq(1)].groupby(["pitcher", "y_effective"]).ngroups)},
           "test": {"outings": int(len(te)), "events": int(te["y"].sum()), "pitchers": int(te["pitcher"].nunique()),
                    "stints": int(te[te["y"].eq(1)].groupby(["pitcher", "y_effective"]).ngroups),
                    "base_rate": float(te["y"].mean())},
           "auc": {"naive": auc(te["y"], p0), "tracking": auc(te["y"], p1), "velocity": auc(te["y"], pv)},
           "log_loss": {"naive": log_loss(te["y"], p0), "tracking": log_loss(te["y"], p1), "velocity": log_loss(te["y"], pv),
                        "base_rate_only": log_loss(te["y"], np.full(len(te), tr["y"].mean()))},
           "brier": {"naive": brier(te["y"], p0), "tracking": brier(te["y"], p1), "velocity": brier(te["y"], pv)},
           "tracking_vs_naive": bootstrap_compare(te["y"], p0, p1, te["pitcher"], reps=reps),
           "velocity_vs_naive": bootstrap_compare(te["y"], p0, pv, te["pitcher"], reps=reps, seed=1),
           "calibration": {"naive": recalibration(te["y"], p0), "tracking": recalibration(te["y"], p1)},
           "coefficients": coefs}
    out["_frames"] = {"train": tr, "test": te, "p0": p0, "p1": p1, "pv": pv, "f1": f1, "f0": f0}
    return out


def velocity_bins(d: pd.DataFrame, col: str = "drop_velo_1", edges=(-np.inf, -1.0, 0.0, 1.0, 2.0, 3.0, np.inf)) -> pd.DataFrame:
    """IL rate by the outing's fastball velocity drop (mph below his baseline), with Wilson intervals."""
    labels = ["up 1+", "up 0-1", "down 0-1", "down 1-2", "down 2-3", "down 3+"]
    b = pd.cut(d[col], list(edges), labels=labels, right=False)
    g = d.groupby(b, observed=False)["y"].agg(["size", "sum"]).reset_index().rename(columns={col: "bin", "size": "n", "sum": "events"})
    g["rate"] = g["events"] / g["n"]
    lo, hi = zip(*[wilson(int(k), int(n)) for k, n in zip(g["events"], g["n"])])
    g["lo"], g["hi"] = lo, hi
    g["bin"] = g["bin"].astype(str)
    return g


def run(test: int = 2026, train=(2024, 2025), out_dir: Path | None = None, reps: int = 1000, log=print,
        write_report_table: bool = True) -> dict:
    D = Path(out_dir or OUT_DIR)
    D.mkdir(parents=True, exist_ok=True)
    seasons = tuple(sorted(set(train) | {test}))
    B = build(seasons, train, log=log)
    a, il = B["outings"], B["il"]
    B["params"].to_csv(D / "noise_params.csv", index=False)
    B["curve"].to_csv(D / "season_curve.csv", index=False)
    il.to_csv(D / "il_placements.csv", index=False)

    res = {}
    for spec in SPECS:
        log(f"evaluating {spec} ...")
        res[spec] = evaluate(a, il, spec, train, test, reps=reps)
    q = benjamini_hochberg([res[s]["tracking_vs_naive"]["log_loss"]["p"] for s in SPECS])
    for s, qq in zip(SPECS, q):
        res[s]["tracking_vs_naive"]["log_loss"]["q_bh"] = qq

    M = res["arm_14"]["_frames"]
    tr, te = M["train"], M["test"]
    thr = pick_threshold(tr)
    rules = {}
    for t in (1.0, 1.5, 2.0, 2.5, 3.0):
        rules[f"velo_drop_{t:.1f}"] = {"train": alert_table(tr, tr["drop_velo_1"].to_numpy() >= t, seasons=len(train)),
                                       "test": alert_table(te, te["drop_velo_1"].to_numpy() >= t)}
    p_tr1 = predict(M["f1"], design(tr, NAIVE + TRACK))
    p_tr0 = predict(M["f0"], design(tr, NAIVE))
    for share in (0.01, 0.02, 0.05):
        for name, ptr, pte in (("tracking", p_tr1, M["p1"]), ("naive", p_tr0, M["p0"])):
            cut = float(np.quantile(ptr, 1 - share))
            rules[f"{name}_top_{int(share * 100)}pct"] = {"cut": cut,
                                                         "train": alert_table(tr, ptr >= cut, seasons=len(train)),
                                                         "test": alert_table(te, pte >= cut)}
    full_tr, full_te = tr["pitch_ratio"].to_numpy() >= 0.75, te["pitch_ratio"].to_numpy() >= 0.75
    rules["chosen_full_outing"] = {"train": alert_table(tr, (tr["drop_velo_1"].to_numpy() >= thr) & full_tr, seasons=len(train)),
                                   "test": alert_table(te, (te["drop_velo_1"].to_numpy() >= thr) & full_te)}
    rules["chosen_short_outing"] = {"train": alert_table(tr, (tr["drop_velo_1"].to_numpy() >= thr) & ~full_tr, seasons=len(train)),
                                    "test": alert_table(te, (te["drop_velo_1"].to_numpy() >= thr) & ~full_te)}
    E = res["arm_14_early"]["_frames"]
    rules["chosen_early"] = {"train": alert_table(E["train"], E["train"]["drop_velo_1"].to_numpy() >= thr, seasons=len(train)),
                             "test": alert_table(E["test"], E["test"]["drop_velo_1"].to_numpy() >= thr)}
    for k in ("starter", "reliever"):
        mtr, mte = tr["starter"].eq(k == "starter").to_numpy(), te["starter"].eq(k == "starter").to_numpy()
        rules[f"chosen_{k}"] = {"train": alert_table(tr[mtr], tr.loc[mtr, "drop_velo_1"].to_numpy() >= thr, seasons=len(train)),
                                "test": alert_table(te[mte], te.loc[mte, "drop_velo_1"].to_numpy() >= thr)}
    # false alarms per club in 2026 under the chosen velocity rule
    flag = te["drop_velo_1"].to_numpy() >= thr
    fa = te.assign(fa=flag & te["y"].eq(0).to_numpy()).groupby("team")["fa"].sum()
    clubs = {"median": float(fa.median()), "min": int(fa.min()), "max": int(fa.max()), "clubs": int(len(fa))}

    bins_tr, bins_te = velocity_bins(tr), velocity_bins(te)
    dec = {"naive": deciles(te["y"], M["p0"]), "tracking": deciles(te["y"], M["p1"])}
    sample = {"pitches": B["pitches"], "games": B["games"], "outings": int(len(a)),
              "outings_by_season": {int(k): int(v) for k, v in a.groupby("season").size().items()},
              "eligible_by_season": {int(k): int(v) for k, v in a[eligible(a)].groupby("season").size().items()},
              "pitchers": int(a["pitcher"].nunique())}
    il_counts = {}
    for s in seasons:      # placements effective in the calendar year, by pitchers who pitched in the majors that season
        g = il[(il["effective"].dt.year == s) & il["person"].isin(set(a.loc[a["season"].eq(s), "pitcher"]))]
        il_counts[int(s)] = {c: int(v) for c, v in g["category"].value_counts().items()}
    # coverage: arm placements effective from the season's first game to its last, by pitchers who pitched in the
    # majors that season, and how many of them had an eligible outing in the 14 days before
    cov = {}
    e = label(model_frame(a), il, 14, ["arm"])
    for s in seasons:
        sa = a[a["season"].eq(s)]
        arm_s = il[il["category"].eq("arm") & il["person"].isin(set(sa["pitcher"]))
                   & (il["effective"] > sa["game_date"].min()) & (il["effective"] <= sa["game_date"].max())]
        hit = e[e["season"].eq(s) & e["y"].eq(1)].groupby(["pitcher", "y_effective"]).ngroups
        cov[int(s)] = {"arm_placements_in_season": int(len(arm_s)), "with_eligible_outing_14d": int(hit)}

    summary = {"built": pd.Timestamp.now().strftime("%Y-%m-%d"), "train": list(train), "test": test,
               "sample": sample, "il_by_category": il_counts, "coverage": cov, "chosen_threshold_mph": thr,
               "false_alarms_by_club_test": clubs,
               "noise": B["params"].to_dict("records"),
               "specs": {s: {k: v for k, v in r.items() if k != "_frames"} for s, r in res.items()},
               "rules": rules,
               "velocity_bins": {"train": bins_tr.to_dict("records"), "test": bins_te.to_dict("records")},
               "deciles": {k: v.to_dict("records") for k, v in dec.items()}}
    (D / "summary.json").write_text(json.dumps(summary, indent=1, default=float))
    pd.DataFrame(res["arm_14"]["coefficients"]).to_csv(D / "coefficients_arm_14.csv", index=False)
    if write_report_table:
        REPORT_OUT.write_text(json.dumps(summary, indent=1, default=float))
    figure(summary, D / "il-warning.png")
    log(f"wrote {D / 'summary.json'}")
    return summary


def figure(summary: dict | None = None, out_path: Path | None = None) -> Path:
    """Left: 2026 arm-IL rate in the next 14 days by the outing's fastball velocity drop (training seasons in grey).
    Right: 2026 calibration by decile of predicted risk, naive and tracking models."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from baseball.house import SERIES
    from baseball.viz import GRID, INK, MUTED, _style

    S = summary or json.loads((OUT_DIR / "summary.json").read_text())
    out_path = Path(out_path or OUT_DIR / "il-warning.png")
    fig, (a, c) = plt.subplots(1, 2, figsize=(13.5, 5.6))
    tr, te = pd.DataFrame(S["velocity_bins"]["train"]), pd.DataFrame(S["velocity_bins"]["test"])
    x = np.arange(len(te))
    for off, d, col, lab in ((-0.14, tr, "#9a9a9a", f"{S['train'][0]}-{str(S['train'][-1])[2:]} (fit)"),
                             (0.14, te, INK, f"{S['test']} (held out)")):
        a.errorbar(x + off, 100 * d["rate"], yerr=[100 * (d["rate"] - d["lo"]), 100 * (d["hi"] - d["rate"])],
                   fmt="o", color=col, capsize=3, lw=1.5, ms=6, label=lab)
    base = 100 * S["specs"]["arm_14"]["test"]["base_rate"]
    a.axhline(base, color=MUTED, lw=1, ls="--")
    a.text(len(te) - 0.6, base, f"2026 base rate {base:.1f}%", color=MUTED, fontsize=8.5, va="bottom", ha="right")
    a.set_xticks(x)
    a.set_xticklabels([f"{b}\n(n={n:,})" for b, n in zip(te["bin"], te["n"])], fontsize=8.5)
    a.set_xlabel("This outing's fastball velocity vs his regressed baseline (mph)")
    a.set_ylabel("Arm-injury IL placement within 14 days (%)")
    a.set_title("A big velocity drop goes with arm IL soon after", loc="left", fontsize=12, fontweight="bold")
    a.legend(fontsize=8.5, loc="upper left")
    _style(a)

    for name, col in (("naive", SERIES[0]), ("tracking", SERIES[1])):
        d = pd.DataFrame(S["deciles"][name])
        c.errorbar(100 * d["predicted"], 100 * d["observed"], yerr=[100 * (d["observed"] - d["lo"]), 100 * (d["hi"] - d["observed"])],
                   fmt="o-", color=col, capsize=2, lw=1.3, ms=5,
                   label=f"{name.capitalize()} model (AUC {S['specs']['arm_14']['auc'][name]:.3f})")
    hi = 100 * max(max(pd.DataFrame(S["deciles"][k])["hi"]) for k in ("naive", "tracking"))
    c.plot([0, hi], [0, hi], color=GRID, lw=1.2)
    c.set_xlabel("Predicted risk, decile mean (%)")
    c.set_ylabel("Observed rate in 2026 (%)")
    c.set_title("2026: the tracking model ranks risk no detectably better", loc="left", fontsize=12, fontweight="bold")
    c.legend(fontsize=8.5, loc="upper left")
    _style(c)
    fig.text(0.01, 0.005, "Sources: Statcast via Baseball Savant (regular season); MLB Stats API transactions. "
             "95% Wilson intervals. Fit on 2024-25, scored on 2026.", fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path
