"""What pitch-design changes stick and pay: season-over-season shape changes, their payoff and persistence.

The question a player-development department pays for: when a pitcher changes a pitch's shape from one
season to the next, which changes go with real gains in whiffs and run value, how much per unit of change,
and do the gains last?

Grain
- pitch-season: one row per pitcher x season x pitch type (Statcast's label; CU and KC pooled as "CU"),
  regular season only. Shape means, outcome counts, the fixed-hand expected whiff, and the shape of the
  first and second half of the season (for the noise threshold).
- pair: one row per pitcher x pitch type x (season s, season s+1), both seasons over the sample floors.

Pipeline
1. `load()` reads the sequence copy (only the columns needed).
2. `expected_whiff()` scores every pitch with ONE expected-whiff model trained on all seasons pooled,
   cross-fitted by pitcher (a pitcher's pitches in every season are scored by a model that never saw him),
   at a fixed batter-hand mix. So a change in expected whiff is a change in the pitch's physics only:
   not a different model year, not a different mix of hitters.
3. `pitch_seasons()` aggregates to the pitch-season grain.
4. `pairs()` builds season-over-season changes and removes the league's own shift: each change is net of
   the median change of every returning pitch of that type in the same season pair (measurement drift, the
   ball, league-wide training trends).
5. `thresholds()` defines a "deliberate change" from noise: the 90th percentile of how far a pitch's shape
   moves between the first and second half of ONE season (net of the league's half-to-half shift). A
   season-over-season change beyond it is bigger than nine in ten pitches move within a season.
6. `lever_effects()` estimates payoff per unit of change (dose-response), regression-to-the-mean handled by
   controlling for the prior season's actual and expected whiff and run value, sample, role and age;
   standard errors clustered by pitcher; Benjamini-Hochberg across every lever x pitch type x outcome.
7. `matched_effects()` compares deliberate changers with matched non-changers (coarsened exact matching on
   pitch type, season pair, role, prior actual and expected whiff), regression-adjusted, clustered SEs.
8. `placebo()` asks whether NEXT season's change predicts LAST season's results (it can't cause them; a
   non-zero coefficient is selection the controls missed).
9. `validate()` fits the levers on 2024->25 and predicts 2025->26 out of sample against a controls-only
   baseline (regression to the mean alone).
10. `persistence()` follows 2024->25 deliberate changers into 2026: shape kept, results kept.

Conventions: flags once, rates after aggregation; run value is the pitcher's view (minus Statcast's
delta_run_exp) per 100 pitches; whiff% is per swing.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from baseball.evaluation.arsenal import SWINGS, WHIFFS
from baseball.stats import benjamini_hochberg, clustered_wls

DATA = Path(__file__).resolve().parents[2] / "data"
OUT_DIR = DATA / "edge" / "levers"

COLUMNS = [
    "game_pk", "game_date", "game_year", "at_bat_number", "pitch_number", "inning", "inning_topbot", "pitcher",
    "player_name", "p_throws", "stand", "pitch_type", "description", "zone", "release_speed", "release_spin_rate",
    "release_extension", "release_pos_x", "release_pos_z", "arm_angle", "pfx_x", "pfx_z", "delta_run_exp", "age_pit",
]

FASTBALLS = ("FF", "SI", "FC")
TYPES = ["FF", "SI", "FC", "SL", "ST", "CU", "CH", "FS"]
TYPE_NAMES = {"FF": "Four-seamer", "SI": "Sinker", "FC": "Cutter", "SL": "Slider", "ST": "Sweeper",
              "CU": "Curveball (incl. knuckle-curve)", "CH": "Changeup", "FS": "Splitter"}
# Horizontal break is reported in each pitch's own direction: arm side for these, glove side for the rest
ARM_SIDE_TYPES = ("FF", "SI", "CH", "FS")

# Lever: (pitch-season column, unit of change reported, label)
LEVERS = {
    "velo": ("velo", 1.0, "velocity, +1 mph"),
    "ivb": ("ivb_in", 2.0, "induced vertical break, +2 in"),
    "hb": ("hb_own_in", 2.0, "horizontal break in its own direction, +2 in"),
    "spin": ("spin", 100.0, "spin, +100 rpm"),
    "gap": ("speed_gap", 1.0, "speed gap below the primary fastball, +1 mph"),
    "sep": ("separation_in", 2.0, "movement separation from the primary fastball, +2 in"),
    "rel_z": ("rel_z_in", 3.0, "release height, +3 in"),
    "rel_x": ("rel_x_arm_in", 3.0, "release side toward the arm side, +3 in"),
    "ext": ("ext_in", 3.0, "extension, +3 in"),
    "arm": ("arm_angle", 3.0, "arm angle, +3 degrees (higher slot)"),
}
SECONDARY_ONLY = ("gap", "sep")


def levers_for(pitch_type: str) -> list[str]:
    """Levers that apply to a pitch type. Speed gap and separation are measured from the primary fastball, so
    they are not levers for four-seamers and sinkers (nearly always the primary fastball, and the few that
    aren't would be a different question)."""
    return [lv for lv in LEVERS if not (lv in SECONDARY_ONLY and pitch_type in ("FF", "SI", "all"))]

MIN_PITCHES = 150          # per pitch-season (each half then has ~75+)
MIN_SWINGS = 50            # per pitch-season, the repo's whiff floor
NOISE_QUANTILE = 0.90


# ---------------------------------------------------------------- data

def load(seasons: list[int]) -> pd.DataFrame:
    """Regular-season pitches of the seasons, only the columns this study needs."""
    from baseball.edge.familiarity import seq_parts

    frames = []
    for s in seasons:
        parts = seq_parts(s)
        if not parts:
            raise FileNotFoundError(f"No sequence data for {s} in data/seq/. The monthly update writes it on the Mac.")
        frames += [pd.read_parquet(p, columns=COLUMNS) for p in parts]
    p = pd.concat(frames, ignore_index=True)
    p["pitcher"] = p["pitcher"].astype("int64")
    p["game_year"] = p["game_year"].astype(int)
    return p


def shape_columns(p: pd.DataFrame) -> pd.DataFrame:
    """Per-pitch shape in readable units. Statcast pfx and release are in feet from the catcher's view."""
    p = p.copy()
    p["pitch_type"] = p["pitch_type"].replace({"KC": "CU"})
    arm = np.where(p["p_throws"].eq("R"), -1.0, 1.0)
    p["velo"] = p["release_speed"]
    p["ivb_in"] = p["pfx_z"] * 12
    p["hb_arm_in"] = p["pfx_x"] * 12 * arm
    p["spin"] = p["release_spin_rate"]
    p["rel_z_in"] = p["release_pos_z"] * 12
    p["rel_x_arm_in"] = p["release_pos_x"] * 12 * arm
    p["ext_in"] = p["release_extension"] * 12
    return p


def roles(p: pd.DataFrame, starter_share: float = 0.5) -> pd.DataFrame:
    """Starter or reliever per pitcher-season: SP if he threw his team's first pitch in at least half his games.

    The first pitch of the top of the first is the home starter's; of the bottom, the away starter's.
    Grain: pitcher x season.
    """
    first = (p[p["inning"].eq(1)].sort_values(["game_pk", "inning_topbot", "at_bat_number", "pitch_number"])
             .groupby(["game_pk", "inning_topbot"]).head(1))
    starts = first.groupby(["pitcher", "game_year"]).size().rename("starts")
    games = p.groupby(["pitcher", "game_year"])["game_pk"].nunique().rename("games")
    out = pd.concat([games, starts], axis=1).fillna({"starts": 0}).reset_index().rename(columns={"game_year": "season"})
    out["starts"] = out["starts"].astype(int)
    out["role"] = np.where(out["starts"] >= starter_share * out["games"], "SP", "RP")
    return out


# ---------------------------------------------------------------- expected whiff (one model, all seasons)

def expected_whiff(p: pd.DataFrame, n_splits: int = 5, seed: int = 11) -> pd.DataFrame:
    """x_same / x_opp: whiff probability per swing from physics alone, scored against a same-handed and an
    opposite-handed hitter, for every pitch (swing or not).

    One model on all seasons pooled; folds grouped by pitcher, so each pitcher's pitches in every season come
    from a model trained without him. Features are the edge engine's (velocity, movement, spin, release,
    extension, arm angle, and differences from his own primary fastball in that season).
    Returns frame keyed like p's index with x_same, x_opp.
    """
    from sklearn.model_selection import GroupKFold

    from baseball.edge.stuff import FEATURES, _model, features

    # Features per season, so "difference from his primary fastball" uses that season's fastball
    feats = []
    for s, g in p.groupby("game_year"):
        f = features(g.assign(pitch_type=g["pitch_type"].replace({"KC": "CU"})))
        feats.append(f)
    f = pd.concat(feats)
    is_swing = f["description"].isin(SWINGS).to_numpy()
    y = f["description"].isin(WHIFFS).to_numpy().astype(int)
    X = f[FEATURES].to_numpy(float)
    groups = f["pitcher"].to_numpy()
    j_same = FEATURES.index("same_hand")
    x_same = np.zeros(len(f))
    x_opp = np.zeros(len(f))
    for train, test in GroupKFold(n_splits=n_splits).split(X, y, groups):
        tr = train[is_swing[train]]
        m = _model(seed).fit(X[tr], y[tr])
        Xt = X[test].copy()
        Xt[:, j_same] = 1
        x_same[test] = m.predict_proba(Xt)[:, 1]
        Xt[:, j_same] = 0
        x_opp[test] = m.predict_proba(Xt)[:, 1]
    return pd.DataFrame({"x_same": x_same, "x_opp": x_opp}, index=f.index)


# ---------------------------------------------------------------- pitch-season table

SHAPE = ["velo", "ivb_in", "hb_arm_in", "spin", "rel_z_in", "rel_x_arm_in", "ext_in", "arm_angle"]


def _halves(p: pd.DataFrame) -> pd.Series:
    """1 for pitches in the first half of a pitch-season (by game order, split where half the pitches are
    thrown), 2 for the second half."""
    g = p.groupby(["pitcher", "game_year", "pitch_type", "game_date", "game_pk"]).size().rename("k").reset_index()
    g = g.sort_values(["pitcher", "game_year", "pitch_type", "game_date", "game_pk"])
    key = ["pitcher", "game_year", "pitch_type"]
    before = g.groupby(key)["k"].cumsum() - g["k"]          # pitches thrown in earlier games
    total = g.groupby(key)["k"].transform("sum")
    g["half"] = np.where(before < total / 2, 1, 2)
    return p.merge(g[[*key, "game_pk", "half"]], on=[*key, "game_pk"], how="left")["half"].to_numpy()


def pitch_seasons(p: pd.DataFrame, xw: pd.DataFrame | None = None) -> pd.DataFrame:
    """Aggregate to pitcher x season x pitch type. p: shape_columns() output (all of a pitcher's pitches,
    so usage shares are right). xw: expected_whiff() output aligned on p's index (optional).

    Columns: n, games, swings, whiffs, whiff_pct, rv100, usage_pct, shape means (SHAPE), shape means by half
    (<metric>_h1, <metric>_h2), x_same, x_opp, same_share (share of pitches to same-handed hitters), age.
    """
    p = p.dropna(subset=["pitch_type"]).copy()
    p["is_swing"] = p["description"].isin(SWINGS)
    p["is_whiff"] = p["description"].isin(WHIFFS)
    p["rv_pitcher"] = -p["delta_run_exp"]
    p["same"] = p["p_throws"].eq(p["stand"]).astype(float)
    if xw is not None:
        p = p.join(xw)
    p["half"] = _halves(p)
    key = ["pitcher", "game_year", "pitch_type"]
    g = p.groupby(key)
    out = g.agg(player_name=("player_name", "last"), p_throws=("p_throws", "first"), n=("pitch_type", "size"),
                games=("game_pk", "nunique"), swings=("is_swing", "sum"), whiffs=("is_whiff", "sum"),
                rv=("rv_pitcher", "sum"), rv_n=("rv_pitcher", "count"), same_share=("same", "mean"),
                age=("age_pit", "median"), **{m: (m, "mean") for m in SHAPE})
    if xw is not None:
        out = out.join(g[["x_same", "x_opp"]].mean())
    halves = p.groupby([*key, "half"])[SHAPE].mean().unstack("half")
    halves.columns = [f"{m}_h{h}" for m, h in halves.columns]
    out = out.join(halves).reset_index().rename(columns={"game_year": "season"})
    tot = p.groupby(["pitcher", "game_year"]).size()
    out["usage_pct"] = 100 * out["n"] / tot.reindex(pd.MultiIndex.from_frame(out[["pitcher", "season"]])).to_numpy()
    out["whiff_pct"] = 100 * out["whiffs"] / out["swings"].where(out["swings"] > 0)
    out["rv100"] = 100 * out["rv"] / out["rv_n"].where(out["rv_n"] > 0)
    return out


# ---------------------------------------------------------------- season-over-season pairs

def _primary_fastball(ps: pd.DataFrame, seasons: list[int]) -> pd.Series:
    """Each pitcher's primary fastball over the seasons compared: his most-thrown FF/SI/FC (pooled)."""
    fb = ps[ps["season"].isin(seasons) & ps["pitch_type"].isin(FASTBALLS)]
    tot = fb.groupby(["pitcher", "pitch_type"])["n"].sum().reset_index()
    return tot.sort_values("n").groupby("pitcher").tail(1).set_index("pitcher")["pitch_type"]


def add_relative(ps: pd.DataFrame, seasons: list[int]) -> pd.DataFrame:
    """Speed gap and movement separation from the pitcher's primary fastball (defined over `seasons`), plus
    horizontal break in the pitch's own direction and the fixed-hand expected whiff.

    The primary fastball is the same pitch type in every season compared, so its gap is measured against
    a like-for-like reference. The primary fastball itself gets NaN for gap and separation.
    """
    ps = ps[ps["season"].isin(seasons)].copy()
    prim = _primary_fastball(ps, seasons)
    ps["primary_fb"] = ps["pitcher"].map(prim)
    ref = ps[ps["pitch_type"].eq(ps["primary_fb"])].set_index(["pitcher", "season"])[["velo", "ivb_in", "hb_arm_in"]]
    r = ref.reindex(pd.MultiIndex.from_frame(ps[["pitcher", "season"]]))
    is_primary = ps["pitch_type"].eq(ps["primary_fb"]).to_numpy()
    ps["speed_gap"] = np.where(is_primary, np.nan, r["velo"].to_numpy() - ps["velo"].to_numpy())
    sep = np.hypot(ps["ivb_in"].to_numpy() - r["ivb_in"].to_numpy(), ps["hb_arm_in"].to_numpy() - r["hb_arm_in"].to_numpy())
    ps["separation_in"] = np.where(is_primary, np.nan, sep)
    ps["hb_own_in"] = np.where(ps["pitch_type"].isin(ARM_SIDE_TYPES), 1.0, -1.0) * ps["hb_arm_in"]
    for h in ("h1", "h2"):
        ps[f"hb_own_in_{h}"] = np.where(ps["pitch_type"].isin(ARM_SIDE_TYPES), 1.0, -1.0) * ps[f"hb_arm_in_{h}"]
    if "x_same" in ps:
        # Batter-hand mix fixed at the pitch's pooled share across the seasons compared
        w = ps.groupby(["pitcher", "pitch_type"])["same_share"].transform(
            lambda s: np.average(s, weights=ps.loc[s.index, "n"]))
        ps["x_whiff_pct"] = 100 * (w * ps["x_same"] + (1 - w) * ps["x_opp"])
    return ps


def league_net(d: pd.DataFrame, change_col: str, by: list[str]) -> pd.Series:
    """Change net of the league's own shift: minus the median change of every pitch in the same group."""
    return d[change_col] - d.groupby(by)[change_col].transform("median")


def pairs(ps: pd.DataFrame, rl: pd.DataFrame, s0: int, s1: int, min_pitches: int = MIN_PITCHES,
          min_swings: int = MIN_SWINGS) -> pd.DataFrame:
    """Season-over-season changes for every pitch thrown above the floors in both seasons.

    Each lever's change d_<lever> is raw; net_<lever> subtracts the league median change for that pitch type
    and season pair. Outcomes: d_whiff (pts per swing), d_rv100, d_xwhiff (fixed hand mix). Priors: the
    first season's levels. Weight w = harmonic sample of the two seasons' swings (the inverse variance of a
    difference of two rates is proportional to it).
    """
    t = add_relative(ps, [s0, s1])
    t = t[t["pitch_type"].isin(TYPES)]
    ok = t[(t["n"] >= min_pitches) & (t["swings"] >= min_swings)]
    a, b = ok[ok["season"].eq(s0)], ok[ok["season"].eq(s1)]
    m = a.merge(b, on=["pitcher", "pitch_type"], suffixes=("_0", "_1"))
    m["pair"] = f"{s0}-{s1}"
    m["player_name"] = m["player_name_1"]
    m["p_throws"] = m["p_throws_1"]
    for lever, (col, unit, _) in LEVERS.items():
        m[f"d_{lever}"] = m[f"{col}_1"] - m[f"{col}_0"]
        m[f"net_{lever}"] = league_net(m, f"d_{lever}", ["pitch_type"])
    m["d_whiff"] = m["whiff_pct_1"] - m["whiff_pct_0"]
    m["d_rv100"] = m["rv100_1"] - m["rv100_0"]
    m["d_usage"] = m["usage_pct_1"] - m["usage_pct_0"]
    if "x_whiff_pct_0" in m:
        m["d_xwhiff"] = m["x_whiff_pct_1"] - m["x_whiff_pct_0"]
    r = rl.set_index(["pitcher", "season"])["role"]
    m["role_0"] = r.reindex(pd.MultiIndex.from_arrays([m["pitcher"], np.full(len(m), s0)])).fillna("RP").to_numpy()
    m["role_1"] = r.reindex(pd.MultiIndex.from_arrays([m["pitcher"], np.full(len(m), s1)])).fillna("RP").to_numpy()
    m["role_change"] = m["role_0"].ne(m["role_1"]).astype(int)
    m["w"] = 1 / (1 / m["swings_0"] + 1 / m["swings_1"])
    m["log_swings"] = np.log(m["swings_0"])
    return m.reset_index(drop=True)


# ---------------------------------------------------------------- the noise threshold

def half_noise(ps: pd.DataFrame, min_pitches: int = MIN_PITCHES) -> pd.DataFrame:
    """How far each shape metric moves between the first and second half of one season, per pitch-season,
    net of the league's median half-to-half shift for that pitch type and season. Relative levers (speed gap,
    separation) use the primary fastball's halves. Grain: pitch-season x lever."""
    rows = []
    for s in sorted(ps["season"].unique()):
        t = add_relative(ps, [s])
        t = t[t["pitch_type"].isin(TYPES) & (t["n"] >= min_pitches)].copy()
        prim = t[t["pitch_type"].eq(t["primary_fb"])].set_index("pitcher")
        for lever, (col, unit, _) in LEVERS.items():
            if lever in SECONDARY_ONLY:
                f = {h: prim.reindex(t["pitcher"]) for h in ("h1", "h2")}
                if lever == "gap":
                    v = {h: f[h][f"velo_{h}"].to_numpy() - t[f"velo_{h}"].to_numpy() for h in ("h1", "h2")}
                else:
                    v = {h: np.hypot(t[f"ivb_in_{h}"].to_numpy() - f[h][f"ivb_in_{h}"].to_numpy(),
                                     t[f"hb_arm_in_{h}"].to_numpy() - f[h][f"hb_arm_in_{h}"].to_numpy()) for h in ("h1", "h2")}
                diff = np.where(t["pitch_type"].eq(t["primary_fb"]), np.nan, v["h2"] - v["h1"])
            else:
                diff = (t[f"{col}_h2"] - t[f"{col}_h1"]).to_numpy()
            d = t[["pitcher", "season", "pitch_type"]].assign(lever=lever, diff=diff).dropna(subset=["diff"])
            d["net"] = league_net(d, "diff", ["pitch_type"])
            rows.append(d)
    return pd.concat(rows, ignore_index=True)


def thresholds(noise: pd.DataFrame, q: float = NOISE_QUANTILE) -> pd.DataFrame:
    """Deliberate-change threshold per pitch type x lever: the q quantile of |net half-to-half change|.

    Conservative on purpose: a half-season mean has twice the sampling variance of a full-season mean, and
    the halves also carry in-season drift (fatigue, weather, mid-season tweaks). A season-over-season change
    beyond it moved more than q of pitches move within a season."""
    return (noise.assign(abs_net=noise["net"].abs()).groupby(["pitch_type", "lever"])["abs_net"]
            .agg(threshold=lambda x: x.quantile(q), noise_sd=lambda x: float(np.sqrt(np.mean(x**2))), pitch_seasons="size")
            .reset_index())


def flag_changes(pr: pd.DataFrame, th: pd.DataFrame) -> pd.DataFrame:
    """Add chg_<lever> = +1 (deliberate increase), -1 (deliberate decrease), 0 (within noise: |net| < half the
    threshold) or NaN (in between, or the lever doesn't apply)."""
    pr = pr.copy()
    t = th.set_index(["pitch_type", "lever"])["threshold"]
    for lever in LEVERS:
        thr = pr["pitch_type"].map(lambda pt, lv=lever: t.get((pt, lv), np.nan))
        net = pr[f"net_{lever}"]
        c = pd.Series(np.nan, index=pr.index)
        c[net.abs() < thr / 2] = 0
        c[net >= thr] = 1
        c[net <= -thr] = -1
        pr[f"thr_{lever}"] = thr
        pr[f"chg_{lever}"] = c
    return pr


# ---------------------------------------------------------------- payoff per unit of change

CONTROLS = ["prior_whiff", "prior_xwhiff", "prior_rv100", "log_swings", "age", "role_SP0", "role_change"]


def _design(d: pd.DataFrame, terms: list[str], controls: list[str] = CONTROLS) -> tuple[np.ndarray, list[str]]:
    """Intercept per season pair + terms + controls."""
    X = pd.DataFrame(index=d.index)
    for pr in sorted(d["pair"].unique()):
        X[f"pair_{pr}"] = d["pair"].eq(pr).astype(float)
    c = pd.DataFrame({
        "prior_whiff": d["whiff_pct_0"], "prior_xwhiff": d.get("x_whiff_pct_0", np.nan), "prior_rv100": d["rv100_0"],
        "log_swings": d["log_swings"], "age": d["age_0"], "role_SP0": d["role_0"].eq("SP").astype(float),
        "role_change": d["role_change"].astype(float),
    }, index=d.index)
    for t in terms:
        X[t] = d[t]
    for k in controls:
        X[k] = c[k] if k in c else d[k]
    return X.to_numpy(float), list(X.columns)


def ols_clustered(d: pd.DataFrame, y: str, terms: list[str], controls: list[str] = CONTROLS, weight: str = "w") -> pd.DataFrame:
    """Weighted least squares of y on terms + controls + season-pair intercepts; SEs clustered by pitcher.
    Returns one row per term in `terms`: coef, se, t, p, n, pitchers."""
    from scipy.stats import norm

    need = [y, *terms, weight, "pitcher"]
    d = d.dropna(subset=need)
    X, names = _design(d, terms, controls)
    ok = ~np.isnan(X).any(axis=1)
    d, X = d[ok], X[ok]
    if len(d) < len(names) + 5:
        return pd.DataFrame(columns=["term", "coef", "se", "t", "p", "n", "pitchers"])
    beta, se = clustered_wls(d[y].to_numpy(), X, d[weight].to_numpy(), d["pitcher"].to_numpy())
    out = pd.DataFrame({"term": names, "coef": beta, "se": se})
    out = out[out["term"].isin(terms)].copy()
    out["t"] = out["coef"] / out["se"]
    out["p"] = 2 * norm.sf(out["t"].abs())
    out["n"] = len(d)
    out["pitchers"] = d["pitcher"].nunique()
    return out.reset_index(drop=True)


OUTCOMES = {"whiff": "d_whiff", "rv100": "d_rv100", "xwhiff": "d_xwhiff"}


def lever_effects(pr: pd.DataFrame, types: list[str] = TYPES, joint: bool = False, extra: list[str] | None = None,
                  controls: list[str] = CONTROLS) -> pd.DataFrame:
    """Payoff per unit of league-net change, per pitch type x lever x outcome.

    One lever at a time (the default): the total association of a change in that lever, including what
    usually changes with it. joint=True puts every lever in one model per pitch type (each lever net of the
    others). extra: more controls; "{lv}" in a name is replaced by the lever (e.g. "early_net_{lv}").
    Coefficients are scaled to the lever's reporting unit. q: Benjamini-Hochberg across every row of the
    whiff and run-value outcomes (expected whiff is the physics model's own answer, not a test).
    """
    rows = []
    for pt in types:
        d = pr[pr["pitch_type"].eq(pt)]
        levers = levers_for(pt)
        for oname, ycol in OUTCOMES.items():
            if ycol not in d:
                continue
            if joint:
                dd = d.dropna(subset=[f"net_{lv}" for lv in levers])
                tab = ols_clustered(dd, ycol, [f"net_{lv}" for lv in levers], controls + list(extra or []))
            else:
                tab = pd.concat([ols_clustered(d, ycol, [f"net_{lv}"], controls + [e.format(lv=lv) for e in extra or []])
                                 for lv in levers], ignore_index=True)
            for _, r in tab.iterrows():
                lv = r["term"].removeprefix("net_")
                unit = LEVERS[lv][1]
                rows.append({"pitch_type": pt, "lever": lv, "outcome": oname, "per": LEVERS[lv][2],
                             "coef": r["coef"] * unit, "se": r["se"] * unit, "p": r["p"], "n": int(r["n"]),
                             "pitchers": int(r["pitchers"])})
    out = pd.DataFrame(rows)
    tested = out["outcome"].isin(["whiff", "rv100"])
    out["q"] = np.nan
    out.loc[tested, "q"] = benjamini_hochberg(out.loc[tested, "p"])
    return out


def by_sign(pr: pd.DataFrame, types: list[str] = TYPES, outcome: str = "d_whiff") -> pd.DataFrame:
    """Are gains and losses symmetric? One model per pitch type x lever with the net change split into its
    positive part (increases) and negative part (decreases). gain = effect of a one-unit increase;
    loss = effect of a one-unit decrease (so a symmetric linear lever has loss = -gain)."""
    rows = []
    for pt in types:
        d = pr[pr["pitch_type"].eq(pt)].copy()
        for lv in levers_for(pt):
            unit = LEVERS[lv][1]
            d["up"] = d[f"net_{lv}"].clip(lower=0)
            d["down"] = d[f"net_{lv}"].clip(upper=0)
            tab = ols_clustered(d.dropna(subset=[f"net_{lv}"]), outcome, ["up", "down"]).set_index("term")
            if len(tab) < 2:
                continue
            rows.append({"pitch_type": pt, "lever": lv, "outcome": outcome,
                         "gain": tab.loc["up", "coef"] * unit, "gain_se": tab.loc["up", "se"] * unit, "gain_p": tab.loc["up", "p"],
                         "loss": -tab.loc["down", "coef"] * unit, "loss_se": tab.loc["down", "se"] * unit, "loss_p": tab.loc["down", "p"],
                         "n_up": int((d[f"net_{lv}"] > 0).sum()), "n_down": int((d[f"net_{lv}"] < 0).sum())})
    return pd.DataFrame(rows)


def robustness(pr: pd.DataFrame, rows: list[tuple[str, str]], outcome: str = "d_whiff") -> pd.DataFrame:
    """The payoff per unit for chosen (pitch type, lever) rows under alternative specifications:
    main; + usage change and + same-handed-batter share change (both partly the club's response, so they can
    absorb some of the effect); role changers dropped; 100+ swings in both seasons; each season pair alone."""
    pr = pr.assign(d_same=pr["same_share_1"] - pr["same_share_0"])
    specs = {
        "main": (pr, []),
        "+ usage and platoon-mix change": (pr, ["d_usage", "d_same"]),
        "no role changers": (pr[pr["role_change"].eq(0)], []),
        "100+ swings each season": (pr[(pr["swings_0"] >= 100) & (pr["swings_1"] >= 100)], []),
        **{f"{pair} only": (pr[pr["pair"].eq(pair)], []) for pair in sorted(pr["pair"].unique())},
    }
    out = []
    for pt, lv in rows:
        label, sign = display(pt, lv)
        unit = LEVERS[lv][1]
        for name, (d, extra) in specs.items():
            t = ols_clustered(d[d["pitch_type"].eq(pt)], outcome, [f"net_{lv}"], CONTROLS + extra)
            if len(t):
                out.append({"pitch_type": pt, "lever": lv, "change": label, "spec": name, "coef": sign * t["coef"].iloc[0] * unit,
                            "se": t["se"].iloc[0] * unit, "p": t["p"].iloc[0], "n": int(t["n"].iloc[0])})
    return pd.DataFrame(out)


def realization(pr: pd.DataFrame, types: list[str] = TYPES, treat: str = "d_xwhiff") -> pd.DataFrame:
    """How much of a physics-predicted whiff change shows up: d_whiff on the expected-whiff change `treat` (same
    controls), per pitch type and pooled. A slope of 1 means the stuff model's predicted gain arrives in full."""
    rows = []
    for pt in [*types, "all"]:
        d = pr if pt == "all" else pr[pr["pitch_type"].eq(pt)]
        tab = ols_clustered(d, "d_whiff", [treat])
        if len(tab):
            r = tab.iloc[0]
            rows.append({"pitch_type": pt, "slope": r["coef"], "se": r["se"], "p": r["p"], "n": int(r["n"]),
                         "sd_d_xwhiff": float(d[treat].std())})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- matched changers

def cem_weights(d: pd.DataFrame, treat: str, strata: list[str]) -> pd.Series:
    """Coarsened exact matching weights. Strata without both a treated and a control row are dropped (weight
    0). Treated rows weigh 1; controls weigh (treated in stratum / controls in stratum) x (total matched
    controls / total matched treated), so the controls stand in for the treated rows' covariate mix."""
    key = d[strata].astype(str).agg("|".join, axis=1)
    t = d[treat].astype(bool)
    nt = t.groupby(key).transform("sum")
    nc = (~t).groupby(key).transform("sum")
    matched = (nt > 0) & (nc > 0)
    mt = int((t & matched).sum())
    mc = int((~t & matched).sum())
    w = pd.Series(0.0, index=d.index)
    w[t & matched] = 1.0
    if mt and mc:
        w[~t & matched] = (nt / nc)[~t & matched] * (mc / mt)
    return w


def _terciles(d: pd.DataFrame, col: str, by: str) -> pd.Series:
    return d.groupby(by)[col].transform(lambda x: pd.qcut(x.rank(method="first"), 3, labels=False)).astype("Int64")


def smd(x_t: pd.Series, x_c: pd.Series, w_c: pd.Series | None = None) -> float:
    """Standardized mean difference (treated minus control), pooled SD of the unweighted groups."""
    mc = np.average(x_c, weights=w_c) if w_c is not None else x_c.mean()
    sd = np.sqrt((x_t.var() + x_c.var()) / 2)
    return float((x_t.mean() - mc) / sd) if sd > 0 else 0.0


def matched_effects(pr: pd.DataFrame, types: list[str] = TYPES, min_treated: int = 15) -> pd.DataFrame:
    """Deliberate changers vs matched non-changers, per pitch type x lever x direction.

    Treated: a deliberate change in that direction (chg_<lever> = +1 or -1). Controls: the same pitch type with
    the lever within noise (chg = 0). Strata: season pair, prior role, role change, terciles of prior actual
    whiff% and prior expected whiff% (within pitch type). Then a weighted regression of the outcome change on
    the treatment with the continuous controls (doubly robust to residual imbalance), SEs clustered by pitcher.
    Balance: SMD of prior whiff before and after matching.
    """
    rows = []
    for pt in types:
        d0 = pr[pr["pitch_type"].eq(pt)].copy()
        if len(d0) < 30:
            continue
        d0["t_whiff"] = _terciles(d0, "whiff_pct_0", "pitch_type")
        d0["t_x"] = _terciles(d0, "x_whiff_pct_0", "pitch_type")
        for lever in levers_for(pt):
            for direction in (1, -1):
                d = d0[d0[f"chg_{lever}"].isin([0, direction])].copy()
                d["treat"] = d[f"chg_{lever}"].eq(direction).astype(int)
                if d["treat"].sum() < min_treated:
                    continue
                cw = cem_weights(d, "treat", ["pair", "role_0", "role_change", "t_whiff", "t_x"])
                d = d.assign(cw=cw)[cw > 0]
                n_t = int(d["treat"].sum())
                if n_t < min_treated:
                    continue
                t_rows, c_rows = d[d["treat"].eq(1)], d[d["treat"].eq(0)]
                rec = {"pitch_type": pt, "lever": lever, "direction": "up" if direction > 0 else "down",
                       "treated": n_t, "controls": int(len(c_rows)),
                       "mean_net_change": float(t_rows[f"net_{lever}"].mean()),
                       "smd_prior_whiff_before": smd(d0.loc[d0[f"chg_{lever}"].eq(direction), "whiff_pct_0"],
                                                     d0.loc[d0[f"chg_{lever}"].eq(0), "whiff_pct_0"]),
                       "smd_prior_whiff_after": smd(t_rows["whiff_pct_0"], c_rows["whiff_pct_0"], c_rows["cw"])}
                for oname, ycol in OUTCOMES.items():
                    if ycol not in d:
                        continue
                    raw = float(t_rows[ycol].mean() - np.average(c_rows[ycol], weights=c_rows["cw"]))
                    d["wt"] = d["cw"]
                    tab = ols_clustered(d, ycol, ["treat"], weight="wt")
                    r = tab.iloc[0] if len(tab) else {"coef": np.nan, "se": np.nan, "p": np.nan}
                    rec[f"{oname}_raw_diff"] = raw
                    rec[f"{oname}_effect"] = float(r["coef"])
                    rec[f"{oname}_se"] = float(r["se"])
                    rec[f"{oname}_p"] = float(r["p"])
                    rec[f"{oname}_naive"] = float(d0.loc[d0[f"chg_{lever}"].eq(direction), ycol].mean())
                rows.append(rec)
    out = pd.DataFrame(rows)
    if len(out):
        ps = pd.concat([out["whiff_p"], out["rv100_p"]]).to_numpy()
        q = benjamini_hochberg(ps)
        out["whiff_q"], out["rv100_q"] = q[: len(out)], q[len(out):]
    return out


# ---------------------------------------------------------------- selection check and out-of-sample test

def placebo(pr_early: pd.DataFrame, pr_late: pd.DataFrame, types: list[str] = TYPES) -> pd.DataFrame:
    """Does the change a pitcher makes NEXT (late pair, e.g. 2025->26) predict the results change he had
    BEFORE it (early pair, 2024->25)? It can't have caused them.

    The early pair's own change in the same lever is controlled: a velocity dip in 2025 lowers 2025 whiffs AND
    is followed by a rebound in 2026, which is mechanics, not selection. With it (and the early priors)
    controlled, a coefficient near zero says the study's controls handle selection into changing; a non-zero
    one measures selection they miss (e.g. pitchers redesign pitches that just had a bad year)."""
    k = ["pitcher", "pitch_type"]
    late = pr_late[k + [f"net_{lv}" for lv in LEVERS]]
    early = pr_early.rename(columns={f"net_{lv}": f"early_net_{lv}" for lv in LEVERS}).merge(late, on=k)
    return lever_effects(early, types, extra=["early_net_{lv}"]).query("outcome != 'xwhiff'").rename(columns={"q": "q_placebo"})


def _wrmse(y, yhat, w) -> float:
    return float(np.sqrt(np.average((np.asarray(y) - np.asarray(yhat)) ** 2, weights=w)))


def validate(pr_train: pd.DataFrame, pr_test: pd.DataFrame, types: list[str] = TYPES, outcome: str = "d_whiff",
             boot: int = 1000, seed: int = 7) -> pd.DataFrame:
    """Out-of-sample: fit on one season pair, predict the next pair's results change.

    Models (each fitted by weighted least squares on the training pair only):
    - baseline: controls only (regression to the mean, role, age, sample)
    - levers: baseline + every league-net lever change
    - physics: baseline + the expected-whiff change (the stuff model's summary of the same shape change)
    Score: weighted RMSE on the test pair and the share of the baseline's squared error removed, with a 95%
    interval from resampling the test pair's pitchers (a pitcher's pitches move together).
    """
    rows = []
    for pt in [*types, "all"]:
        tr = pr_train if pt == "all" else pr_train[pr_train["pitch_type"].eq(pt)]
        te = pr_test if pt == "all" else pr_test[pr_test["pitch_type"].eq(pt)]
        levers = [f"net_{lv}" for lv in levers_for(pt)]
        need = [outcome, "d_xwhiff", *levers, "whiff_pct_0", "x_whiff_pct_0", "rv100_0", "age_0", "w"]
        tr, te = tr.dropna(subset=need), te.dropna(subset=need)
        if len(tr) < 40 or len(te) < 40:
            continue
        rec = {"pitch_type": pt, "train_n": len(tr), "test_n": len(te)}
        y, w = te[outcome].to_numpy(), te["w"].to_numpy()
        se2 = {}
        for name, terms in (("baseline", []), ("levers", levers), ("physics", ["d_xwhiff"])):
            Xtr, _ = _design(tr.assign(pair="x"), terms)
            Xte, _ = _design(te.assign(pair="x"), terms)
            sw = np.sqrt(tr["w"].to_numpy())
            beta, *_ = np.linalg.lstsq(Xtr * sw[:, None], tr[outcome].to_numpy() * sw, rcond=None)
            se2[name] = w * (y - Xte @ beta) ** 2
            rec[f"rmse_{name}"] = float(np.sqrt(se2[name].sum() / w.sum()))
        rec["rmse_no_change"] = _wrmse(y, np.zeros(len(te)), w)
        # Uncertainty of the out-of-sample gain: resample test-pair pitchers (clusters) with replacement
        codes, inv = np.unique(te["pitcher"].to_numpy(), return_inverse=True)
        sums = {k: np.bincount(inv, weights=v) for k, v in se2.items()}
        rng = np.random.default_rng(seed)
        draws = rng.integers(0, len(codes), size=(boot, len(codes)))
        counts = np.stack([np.bincount(dr, minlength=len(codes)) for dr in draws])
        for name in ("levers", "physics"):
            rec[f"gain_{name}_pct"] = 100 * (1 - se2[name].sum() / se2["baseline"].sum())
            g = 100 * (1 - (counts @ sums[name]) / (counts @ sums["baseline"]))
            rec[f"gain_{name}_lo"], rec[f"gain_{name}_hi"] = (float(x) for x in np.percentile(g, [2.5, 97.5]))
        rows.append(rec)
    return pd.DataFrame(rows)


def plan_target(pr_train: pd.DataFrame, prior: dict, pitch_type: str, lever: str, planned_change: float,
                outcome: str = "d_whiff") -> dict:
    """What a planned change should be worth, from training pairs only (e.g. 2024->25 when planning 2026).

    Fits the one-lever model (controls + the lever's net change) on the training pairs of that pitch type and
    predicts the outcome change for a pitch with the given priors. prior: whiff_pct_0, x_whiff_pct_0, rv100_0,
    swings_0, age_0, role_0 (role_change is assumed 0; the latest training pair's intercept is used).
    Returns the predicted change without the plan ("drift": regression to the mean, age, role), the lever's
    part (coefficient x planned change) and their sum, plus the coefficient and its clustered SE.
    """
    d = pr_train[pr_train["pitch_type"].eq(pitch_type)].dropna(subset=[outcome, f"net_{lever}", "w"])
    X, names = _design(d, [f"net_{lever}"])
    ok = ~np.isnan(X).any(axis=1)
    beta, se = clustered_wls(d.loc[ok, outcome].to_numpy(), X[ok], d.loc[ok, "w"].to_numpy(), d.loc[ok, "pitcher"].to_numpy())
    row = pd.DataFrame([{**prior, "pair": sorted(d["pair"].unique())[-1], "log_swings": np.log(prior["swings_0"]),
                         "role_change": 0, f"net_{lever}": 0.0}])
    Xr, names_r = _design(pd.concat([d[row.columns], row], ignore_index=True), [f"net_{lever}"])
    assert names_r == names
    j = names.index(f"net_{lever}")
    drift = float(Xr[-1] @ beta)
    part = float(beta[j] * planned_change)
    return {"drift": drift, "lever_part": part, "with_change": drift + part, "coef_per_unit": float(beta[j]),
            "se_per_unit": float(se[j]), "train_n": int(ok.sum())}


# ---------------------------------------------------------------- persistence

def retention(x0, x1, x2, league01: float = 0.0, league02: float = 0.0) -> float:
    """Share of a season-1 change still there in season 2, both net of the league's shift:
    (x2 - x0 - league02) / (x1 - x0 - league01). 1 = all of it kept, 0 = back to where it started."""
    first = (x1 - x0) - league01
    return float(((x2 - x0) - league02) / first) if first != 0 else float("nan")


def persistence(ps: pd.DataFrame, rl: pd.DataFrame, th: pd.DataFrame, seasons: tuple[int, int, int] = (2024, 2025, 2026),
                min_pitches: int = MIN_PITCHES, min_swings: int = MIN_SWINGS) -> dict:
    """Follow s0->s1 changes into s2. Shape and results separately.

    shape (one row per lever, pitch types pooled): for deliberate s0->s1 changers, how many were still thrown
      above the floors in s2 (and the same share for within-noise pitches, to see whether changers drop out
      more), the median retention (share of the s0->s1 net change still present in s2, net of the league's
      s0->s2 shift; `retention()`), the share keeping half or more, the share that reversed past the start,
      and the slope of the s0->s2 net change on the s0->s1 net change across every pitch.
    results (one row per pitch type x lever x outcome): on pitches thrown in all three seasons, the payoff
      per unit of the s0->s1 change measured over one season (s0->s1) and over two (s0->s2), and the
      s1->s2 change in results on the same s0->s1 change ("fade": negative = the gain shrank in year two),
      each with the usual controls and SEs clustered by pitcher.
    """
    s0, s1, s2 = seasons
    p01 = flag_changes(pairs(ps, rl, s0, s1, min_pitches, min_swings), th)
    p02 = pairs(ps, rl, s0, s2, min_pitches, min_swings)
    k = ["pitcher", "pitch_type"]
    shape_rows = []
    for lever, (col, unit, label) in LEVERS.items():
        m = p01[k + [f"net_{lever}", f"chg_{lever}"]].merge(p02[k + [f"net_{lever}"]].rename(columns={f"net_{lever}": "net02"}),
                                                          on=k, how="left")
        m["ret"] = m["net02"] / m[f"net_{lever}"]
        delib = m[m[f"chg_{lever}"].abs().eq(1)]
        quiet = m[m[f"chg_{lever}"].eq(0)]
        have = delib.dropna(subset=["ret"])
        allm = m.dropna(subset=["net02", f"net_{lever}"])
        shape_rows.append({
            "lever": lever, "deliberate_changes": int(len(delib)), "still_thrown": int(len(have)),
            "still_thrown_pct": 100 * len(have) / max(len(delib), 1),
            "still_thrown_pct_within_noise": 100 * quiet["net02"].notna().mean() if len(quiet) else np.nan,
            "median_retention": float(have["ret"].median()) if len(have) else np.nan,
            "kept_half_pct": 100 * float((have["ret"] >= 0.5).mean()) if len(have) else np.nan,
            "reversed_pct": 100 * float((have["ret"] < 0).mean()) if len(have) else np.nan,
            "slope_all": float(np.polyfit(allm[f"net_{lever}"], allm["net02"], 1)[0]) if len(allm) >= 10 else np.nan,
            "pitches_all": int(len(allm))})
    shape = pd.DataFrame(shape_rows)

    keep = p02[k + ["d_whiff", "d_rv100", "d_xwhiff"]].rename(columns={"d_whiff": "d_whiff_02", "d_rv100": "d_rv100_02",
                                                                      "d_xwhiff": "d_xwhiff_02"})
    both = p01.merge(keep, on=k)
    both["dx01"] = both["d_xwhiff"]          # the s0->s1 expected-whiff change stays the treatment at every horizon
    horizons = {
        f"{s0}->{s1}": both,
        f"{s0}->{s2}": both.drop(columns=["d_whiff", "d_rv100", "d_xwhiff"]).rename(
            columns={"d_whiff_02": "d_whiff", "d_rv100_02": "d_rv100", "d_xwhiff_02": "d_xwhiff"}),
        f"{s1}->{s2} (fade)": both.assign(d_whiff=both["d_whiff_02"] - both["d_whiff"],
                                          d_rv100=both["d_rv100_02"] - both["d_rv100"],
                                          d_xwhiff=both["d_xwhiff_02"] - both["d_xwhiff"]),
    }
    res = []
    for h, b in horizons.items():
        e = lever_effects(b)
        e["horizon"] = h
        res.append(e.drop(columns=["q"]))
        r = realization(b, treat="dx01").assign(horizon=h)
        res.append(r.rename(columns={"slope": "coef"}).assign(lever="expected-whiff change", outcome="whiff",
                                                              per="+1 pt of expected whiff")[["pitch_type", "lever", "outcome", "per", "coef", "se", "p", "n", "horizon"]])
    results = pd.concat(res, ignore_index=True)
    return {"shape": shape, "results": results, "pairs01": p01}


# ---------------------------------------------------------------- run everything

def run(seasons: tuple[int, int, int] = (2024, 2025, 2026), out_dir: Path | None = None, log=print,
        xwhiff_cache: bool = True) -> dict:
    """The whole study. Writes tables to data/edge/levers/ and returns them."""
    out = Path(out_dir or OUT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    log("loading pitches")
    p = shape_columns(load(list(seasons)))
    cache = out / f"xwhiff_{len(p)}.parquet"           # keyed by the row count of the pitches it scored
    if xwhiff_cache and cache.exists():
        xw = pd.read_parquet(cache)
    else:
        log("fitting the pooled expected-whiff model (cross-fitted by pitcher)")
        xw = expected_whiff(p)
        xw.to_parquet(cache)
    ps = pitch_seasons(p, xw)
    rl = roles(p)
    del p
    ps.to_parquet(out / "pitch_seasons.parquet")
    rl.to_parquet(out / "roles.parquet")
    noise = half_noise(ps)
    th = thresholds(noise)
    s0, s1, s2 = seasons
    pr_a = flag_changes(pairs(ps, rl, s0, s1), th)
    pr_b = flag_changes(pairs(ps, rl, s1, s2), th)
    pr = pd.concat([pr_a, pr_b], ignore_index=True)
    log(f"{len(pr):,} pitch pairs ({len(pr_a):,} {s0}->{s1}, {len(pr_b):,} {s1}->{s2})")
    res = {
        "thresholds": th,
        "pairs": pr,
        "levers": lever_effects(pr),
        "levers_joint": lever_effects(pr, joint=True),
        "by_sign": by_sign(pr),
        "realization": realization(pr),
        "matched": matched_effects(pr),
        "placebo": placebo(pr_a, pr_b),
        "validation": validate(pr_a, pr_b),
        # the same levers with no prior-season controls: how much regression to the mean would have misled
        "levers_unadjusted": lever_effects(pr, controls=[]),
    }
    per = persistence(ps, rl, th, seasons)
    res["persistence_shape"], res["persistence_results"] = per["shape"], per["results"]
    res["answer"] = answer_table(res)
    top = res["answer"].query("verdict == 'confirmed'")
    res["robustness"] = pd.concat([
        robustness(pr, [(a, b) for a, b, k in zip(top["pitch_type"], top["lever"], top["basis"]) if k != "run value"]
                   ).assign(outcome="whiff"),
        robustness(pr, [(a, b) for a, b, k in zip(top["pitch_type"], top["lever"], top["basis"]) if k == "run value"],
                   outcome="d_rv100").assign(outcome="rv100"),
    ], ignore_index=True)
    for name, t in res.items():
        t.to_parquet(out / f"{name}.parquet")
    summary = {"seasons": list(seasons), "pairs": int(len(pr)), "pairs_by_season_pair": pr["pair"].value_counts().to_dict(),
               "pitchers": int(pr["pitcher"].nunique()), "pitch_seasons": int(len(ps)),
               "pitches_per_season_floor": MIN_PITCHES, "swings_per_season_floor": MIN_SWINGS, "noise_quantile": NOISE_QUANTILE}
    (out / "summary.json").write_text(__import__("json").dumps(summary, indent=2))
    return res


# ---------------------------------------------------------------- the answer table and the figure

# Vertical break on pitches that work by dropping reads better as "more drop" (the sign is flipped for display)
DROP_TYPES = ("SL", "ST", "CU", "CH", "FS")


def display(pitch_type: str, lever: str) -> tuple[str, float]:
    """(label, sign) for reporting a lever: sign -1 flips the coefficient so the label reads in the pitch's
    natural direction (e.g. slider vertical break as '+2 in more drop')."""
    if lever == "ivb" and pitch_type in DROP_TYPES:
        return "drop, +2 in (less induced vertical break)", -1.0
    if lever == "hb":
        return ("arm-side run, +2 in" if pitch_type in ARM_SIDE_TYPES else "glove-side sweep, +2 in"), 1.0
    if lever == "ivb":
        return "ride (induced vertical break), +2 in", 1.0
    return LEVERS[lever][2], 1.0


def answer_table(res: dict) -> pd.DataFrame:
    """One row per pitch type x lever: whiff and run-value payoff per unit (one lever at a time), the physics
    model's payoff, the joint-model whiff payoff, gains and losses separately, the placebo, the out-of-sample
    status of the pitch type, and a wording that follows the evidence:
      confirmed      whiff or run-value q < 0.05
      lean           q < 0.10
      not confirmed  p < 0.05 on its own, but it doesn't survive the multiple-testing correction
      no sign        none of the above, and the 95% interval for whiffs excludes effects larger than 2 points per unit
      can't tell     none of the above, and the interval is too wide to rule out a 2-point effect
    """
    from scipy.stats import norm

    lv = res["levers"].pivot_table(index=["pitch_type", "lever"], columns="outcome", values=["coef", "se", "q", "n"])
    lv.columns = [f"{o}_{s}" for s, o in lv.columns]
    j = res["levers_joint"].query("outcome == 'whiff'").set_index(["pitch_type", "lever"])[["coef", "se", "p"]].add_prefix("joint_")
    bs = res["by_sign"].set_index(["pitch_type", "lever"])[["gain", "gain_se", "loss", "loss_se"]]
    pl = res["placebo"].query("outcome == 'whiff'").set_index(["pitch_type", "lever"])[["coef", "p"]].add_prefix("placebo_")
    t = lv.join(j).join(bs).join(pl).reset_index()
    rows = []
    for _, r in t.iterrows():
        label, sign = display(r["pitch_type"], r["lever"])
        q = np.nanmin([r["whiff_q"], r["rv100_q"]])
        hi = abs(r["whiff_coef"]) + 1.96 * r["whiff_se"]
        raw_p = min(2 * norm.sf(abs(r["whiff_coef"] / r["whiff_se"])), 2 * norm.sf(abs(r["rv100_coef"] / r["rv100_se"])))
        verdict = ("confirmed" if q < 0.05 else "lean" if q < 0.10 else "not confirmed" if raw_p < 0.05
                   else "no sign" if hi < 2.0 else "can't tell")
        rows.append({"pitch_type": r["pitch_type"], "lever": r["lever"], "change": label,
                     "whiff": sign * r["whiff_coef"], "whiff_se": r["whiff_se"], "whiff_q": r["whiff_q"],
                     "rv100": sign * r["rv100_coef"], "rv100_se": r["rv100_se"], "rv100_q": r["rv100_q"],
                     "xwhiff": sign * r["xwhiff_coef"], "xwhiff_se": r["xwhiff_se"],
                     "joint_whiff": sign * r["joint_coef"], "joint_se": r["joint_se"],
                     # for a flipped lever, "gain" (an increase in the raw metric) is a loss of the displayed quantity
                     "gain": r["gain"] if sign > 0 else r["loss"], "gain_se": r["gain_se"] if sign > 0 else r["loss_se"],
                     "loss": r["loss"] if sign > 0 else r["gain"], "loss_se": r["loss_se"] if sign > 0 else r["gain_se"],
                     "placebo_whiff": sign * r["placebo_coef"], "placebo_p": r["placebo_p"],
                     "n": int(r["whiff_n"]), "verdict": verdict,
                     # which outcome carries the label: whiffs, run value, or both (q < 0.10)
                     "basis": ("both" if max(r["whiff_q"], r["rv100_q"]) < 0.10 else "whiff" if r["whiff_q"] < 0.10
                               else "run value" if r["rv100_q"] < 0.10 else "")})
    out = pd.DataFrame(rows)
    order = {v: i for i, v in enumerate(["confirmed", "lean", "not confirmed", "no sign", "can't tell"])}
    return out.sort_values(["verdict", "pitch_type"], key=lambda s: s.map(order) if s.name == "verdict" else s.map(TYPES.index)).reset_index(drop=True)


def figure(out_path: Path | None = None, tables_dir: Path | None = None,
           extra_rows: tuple = (("CH", "gap"), ("CH", "sep"), ("FF", "hb"), ("FF", "ext"))) -> Path:
    """Report figure. Left: whiff payoff per unit of change (actual, with 95% interval; physics model as an open
    diamond) for every confirmed or lean lever plus named nulls. Right: did the payoff last? One-season vs
    two-season payoff of 2024->25 changes."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from baseball.viz import INK, MUTED, PITCH_COLORS, _style

    D = Path(tables_dir or OUT_DIR)
    out_path = Path(out_path or D / "levers.png")
    ans = pd.read_parquet(D / "answer.parquet")
    named = np.array([(a_, b_) in extra_rows for a_, b_ in zip(ans["pitch_type"], ans["lever"])])
    keep = ans[ans["verdict"].isin(["confirmed", "lean"]).to_numpy() | named]
    keep = keep.assign(o=keep["pitch_type"].map(TYPES.index)).sort_values(["o", "whiff"], ascending=[False, True])
    fig, (a, b) = plt.subplots(1, 2, figsize=(13, 0.34 * len(keep) + 2.2), gridspec_kw={"width_ratios": [1.35, 1]})
    y = np.arange(len(keep))
    for yi, (_, r) in zip(y, keep.iterrows()):
        c = PITCH_COLORS.get(r["pitch_type"], "#888")
        a.errorbar(r["whiff"], yi, xerr=1.96 * r["whiff_se"], fmt="o", color=c, ms=7, capsize=3, lw=1.6, zorder=3)
        a.plot(r["xwhiff"], yi, marker="D", ms=7, mfc="white", mec=INK, mew=1.2, ls="none", zorder=4)
    a.set_yticks(y)
    tag = {"run value": ", on run value"}
    a.set_yticklabels([f"{TYPE_NAMES[r['pitch_type']].split(' (')[0]}: {r['change']}  [{r['verdict']}{tag.get(r['basis'], '')}]"
                       for _, r in keep.iterrows()], fontsize=8.5, color=INK)
    a.axvline(0, color=MUTED, lw=0.8)
    a.plot([], [], "o", color=MUTED, label="Actual whiff change (95% interval)")
    a.plot([], [], "D", mfc="white", mec=INK, color=INK, label="What the physics model expected")
    a.legend(frameon=False, fontsize=8.5, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=1)
    a.set_xlabel("Whiff% per swing, points per unit of league-net change", color=MUTED, fontsize=9)
    a.set_title("What a shape change is worth", loc="left", fontsize=12, fontweight="bold", color=INK, pad=44)
    _style(a)

    pr = pd.read_parquet(D / "persistence_results.parquet")
    show = [("FF", "velo"), ("FF", "ivb"), ("FF", "spin"), ("SL", "ivb"), ("all", "expected-whiff change")]
    hz = sorted(pr["horizon"].unique())
    one, two = [h for h in hz if "fade" not in h][:2]
    yy = np.arange(len(show))
    for k, (pt, lv) in enumerate(show):
        sign = display(pt, lv)[1] if lv in LEVERS else 1.0
        for h, off, mk in ((one, -0.13, "o"), (two, 0.13, "s")):
            r = pr[(pr["pitch_type"] == pt) & (pr["lever"] == lv) & (pr["outcome"] == "whiff") & (pr["horizon"] == h)].iloc[0]
            c = PITCH_COLORS.get(pt, MUTED)
            b.errorbar(sign * r["coef"], k + off, xerr=1.96 * r["se"], fmt=mk, color=c, ms=7, capsize=3, lw=1.6,
                       mfc=c if h == one else "white", mew=1.5)
    b.set_yticks(yy)
    b.set_yticklabels(["Four-seamer: +1 mph", "Four-seamer: +2 in ride", "Four-seamer: +100 rpm", "Slider: +2 in drop",
                       "Any pitch: +1 pt expected whiff"], fontsize=8.5, color=INK)
    b.invert_yaxis()
    b.axvline(0, color=MUTED, lw=0.8)
    b.plot([], [], "o", color=MUTED, label=f"First season ({one})")
    b.plot([], [], "s", mfc="white", mec=MUTED, color=MUTED, label=f"Two seasons on ({two})")
    b.legend(frameon=False, fontsize=8.5, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=1)
    b.set_xlabel("Whiff% per swing, points per unit", color=MUTED, fontsize=9)
    b.set_title("Did the payoff last?", loc="left", fontsize=12, fontweight="bold", color=INK, pad=44)
    _style(b)
    n_tests = int(pd.read_parquet(D / "levers.parquet")["outcome"].isin(["whiff", "rv100"]).sum())
    fig.text(0.01, 0.005, "MLB regular seasons 2024-26, Statcast via Baseball Savant. Observational: pitchers chose these changes. Each change is "
             "net of the league's median change for the pitch type; prior-season actual and expected whiff%,\nrun value, swings, age and "
             f"role held fixed; 95% intervals clustered by pitcher. Bracket: evidence label (q = Benjamini-Hochberg across all {n_tests} lever tests). "
             "Right panel: 2024->25 changes on pitches thrown in all three seasons.", fontsize=7.3, color=MUTED)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    return out_path
