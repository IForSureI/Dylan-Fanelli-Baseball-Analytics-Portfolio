"""Swing decisions: the run value of a hitter's choice to swing or take, net of what an average hitter
would have chosen on the same pitch, plus the bat-tracking profile that goes with it.

The question a club pays for: how much of a hitter's offense comes from choosing well, separately from
how hard and how often he hits the ball, and is that a skill that carries into next season?

Grain: one row per pitch a hitter could decide on (regular season; automatic balls and strikes,
pitchouts and bunts removed). Every pitch gets three league-wide estimates, fit on 2024-25 only:

* es : expected run value if an average hitter swings at this pitch, E[delta_run_exp | swing, context]
* et : expected run value if he takes it,                          E[delta_run_exp | take, context]
* p  : the probability an average hitter swings,                   P(swing | context)

Context is location in the batter's own zone (inches off the middle of the plate, mirrored so that
positive is away from him, and height as a fraction of his zone, 0 = bottom, 1 = top, from
sz_bot/sz_top), the count, and the pitch family (fastball, cutter, breaking, offspeed).
delta_run_exp is the offense's run value of the pitch (Statcast), so es and et value the swing at
league-average execution: the hitter's own contact quality is left out on purpose.

Decision value of one pitch = (swing - p) x (es - et), where swing is 1 or 0.
* Zero on average by construction: an average decision-maker scores 0 on every kind of pitch.
* A swing at a pitch worth swinging at (es > et) earns (1 - p)(es - et): little for the obvious
  middle-middle 3-1 heater that everyone swings at, a lot for the borderline pitch most hitters take.
* The raw "value of the choice minus the value of the alternative", (2 swing - 1)(es - et),
  equals 2 x (decision value) + (2p - 1)(es - et). The last term depends only on the pitches he
  was thrown (how many easy decisions he got), so it's reported separately as the pitch-mix term.

Per hitter: decision value per 100 pitches (DV100), regressed toward the league with weight
n / (n + M), where M is the split-half constant measured here (games split at random, as in the
Reliability Atlas). Validation: year-to-year correlation, and whether 2025 DV100 adds to 2025 wOBA and
xwOBA (and to chase, zone-swing and whiff rates) in predicting 2026 wOBA, with bootstrap intervals.

Bat tracking per hitter (competitive swings, Statcast's definition): bat speed, swing length, attack
angle, attack direction, swing path tilt, ideal attack angle rate (5-20 degrees), squared-up and blast
rates, and contact point depth.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from baseball.edge.familiarity import GROUP
from baseball.evaluation.arsenal import SWINGS, WHIFFS
from baseball.stats import fit_reliability_constant, wls_loo_rmse

DATA = Path(__file__).resolve().parents[2] / "data"
OUT_DIR = DATA / "edge" / "swing_decisions"

NO_PITCH = ("automatic_ball", "automatic_strike", "pitchout")
BUNTS = ("foul_bunt", "missed_bunt", "bunt_foul_tip")
BUNT_EVENTS = ("sac_bunt", "sac_bunt_double_play")
FAMILIES = ("fastball", "cutter", "breaking", "offspeed")
FAMILY = dict(GROUP) | {"FA": "fastball"}
HALF_PLATE_IN = 17 / 2 + 1.45          # the zone's half-width in inches: half the plate plus a ball's radius
ABS_FIRST_SEASON = 2026                 # Statcast's sz_top / sz_bot became the fixed challenge-system zone
ABS_TOP, ABS_BOTTOM = 0.535, 0.27       # ABS zone: top and bottom as shares of the batter's height
FEATURES = ["x_in", "z_rel", "balls", "strikes", "fam"]

COLUMNS = [
    "game_pk", "game_year", "at_bat_number", "pitch_number", "batter", "stand", "pitch_type", "description",
    "events", "type", "balls", "strikes", "plate_x", "plate_z", "sz_top", "sz_bot", "zone", "delta_run_exp",
    "woba_value", "woba_denom", "estimated_woba_using_speedangle", "launch_speed", "launch_angle",
    "release_speed", "bat_speed", "swing_length", "attack_angle", "attack_direction", "swing_path_tilt",
    "intercept_ball_minus_batter_pos_y_inches", "game_date",
]
DROP_AFTER_PREPARE = ["game_year", "at_bat_number", "pitch_number", "pitch_type", "description", "events", "type",
                      "plate_x", "plate_z", "sz_top", "sz_bot", "zone", "delta_run_exp", "launch_angle"]
RESULT_COLUMNS = ["game_year", "batter", "stand", "events", "description", "type", "woba_denom",
                  "estimated_ba_using_speedangle", "launch_speed", "launch_angle", "launch_speed_angle", "bb_type",
                  "hc_x", "hc_y"]


# ---------------------------------------------------------------- data

def fixed_zones(p: pd.DataFrame) -> pd.DataFrame:
    """One strike zone per batter, the same in every season: top and bottom in feet.

    From 2026 Statcast's sz_top and sz_bot behave as the challenge-system (ABS) zone, which MLB defines as
    53.5% and 27% of the batter's height (MLB press release, Sept. 23, 2025). The switch in the Statcast
    fields is observed in the data, not announced: in 2026 bottom / top equals 27 / 53.5 to within rounding
    for every batter, with essentially no pitch-to-pitch variation (600 of 662 batters have a single sz_top;
    the rest vary by hundredths of a foot). Before 2026 they were set from the batter's stance on each pitch. A model trained on one
    and applied to the other would misplace pitches, so every season uses the fixed zone:
    * batters seen in 2026 (or later): their ABS zone;
    * the rest: their median stance top, mapped to an ABS top by a line fit on batters seen in both
      eras, with the bottom at 27 / 53.5 of the top.
    Without any ABS-era season (the fictional tests), each batter's median stance zone is used."""
    z = p.groupby(["batter", "game_year"])[["sz_top", "sz_bot"]].median().reset_index()
    abs_era = z[z["game_year"] >= ABS_FIRST_SEASON].groupby("batter")[["sz_top", "sz_bot"]].median()
    stance = z[z["game_year"] < ABS_FIRST_SEASON].groupby("batter")[["sz_top", "sz_bot"]].median()
    if abs_era.empty:
        out = stance.copy()
        out["zone_source"] = "stance"
        return out
    both = stance.join(abs_era, lsuffix="_stance", how="inner")
    slope, icpt = np.polyfit(both["sz_top_stance"], both["sz_top"], 1) if len(both) >= 30 else (0.0, abs_era["sz_top"].mean())
    rest = stance.loc[stance.index.difference(abs_era.index)].copy()
    rest["sz_top"] = icpt + slope * rest["sz_top"]
    rest["sz_bot"] = rest["sz_top"] * ABS_BOTTOM / ABS_TOP
    out = pd.concat([abs_era.assign(zone_source="abs"), rest.assign(zone_source="mapped")])
    out.attrs["map"] = {"slope": float(slope), "intercept": float(icpt), "batters_both": int(len(both))}
    return out


def prepare(p: pd.DataFrame, zones: pd.DataFrame | None = None) -> pd.DataFrame:
    """Flags once, on every pitch. Keeps pitches a hitter could decide on and adds the decision context.

    zones : fixed_zones() output; when given, sz_top and sz_bot are replaced by the batter's fixed zone
            (always the case in load(); see fixed_zones for why).
    x_in  : inches from the middle of the plate, positive = away from the batter (plate_x mirrored for
            left-handed batters, since Statcast's plate_x is from the catcher's view, positive to first base).
    z_rel : height as a fraction of the batter's zone (0 = bottom, 1 = top).
    region: Savant's attack-region layout in the batter's zone: heart (inner two-thirds), shadow (a
            third of the half-zone either side of the edge), chase (out to two-thirds beyond), waste.
    in_zone: Statcast's own zone (1-9) for that season, used only for the chase and zone-swing rates.
    """
    d = p[~p["description"].isin(NO_PITCH + BUNTS) & ~p["events"].isin(BUNT_EVENTS)].copy()
    if zones is not None:
        d["sz_top"] = d["batter"].map(zones["sz_top"]).astype(float)
        d["sz_bot"] = d["batter"].map(zones["sz_bot"]).astype(float)
    d["fam"] = d["pitch_type"].map(FAMILY)
    d = d[d["fam"].notna() & d["plate_x"].notna() & d["plate_z"].notna() & d["sz_top"].notna()
          & d["sz_bot"].notna() & (d["sz_top"] > d["sz_bot"])].copy()
    d["season"] = d["game_year"].astype(int)
    d["swing"] = d["description"].isin(SWINGS)
    d["whiff"] = d["description"].isin(WHIFFS)
    d["in_zone"] = d["zone"].between(1, 9)
    d["x_in"] = np.where(d["stand"].eq("L"), -d["plate_x"], d["plate_x"]) * 12
    d["z_rel"] = (d["plate_z"] - d["sz_bot"]) / (d["sz_top"] - d["sz_bot"])
    d["region"] = attack_region(d["x_in"].to_numpy(float), d["z_rel"].to_numpy(float))
    d["fam"] = pd.Categorical(d["fam"], categories=FAMILIES)
    d["rv"] = d["delta_run_exp"].astype(float)
    for c in d.columns:
        if d[c].dtype == "float64":
            d[c] = d[c].astype("float32")
    return d.reset_index(drop=True)


def attack_region(x_in, z_rel) -> np.ndarray:
    """heart / shadow / chase / waste from location in the batter's zone (Savant's layout, scaled to it).

    Horizontal units are the zone's half-width h (about 9.95 in); vertical units are zone heights.
    heart  : |x| < 2h/3 and 1/6 < z < 5/6
    shadow : inside |x| < 4h/3 and -1/6 < z < 7/6, outside the heart
    chase  : inside |x| < 2h and -1/2 < z < 3/2, outside the shadow
    waste  : everything else
    """
    ax = np.abs(np.asarray(x_in, float)) / HALF_PLATE_IN
    z = np.asarray(z_rel, float)
    zc = np.abs(z - 0.5) * 2                # 0 at the middle of the zone, 1 at its top or bottom edge
    heart = (ax < 2 / 3) & (zc < 2 / 3)
    shadow = (ax < 4 / 3) & (zc < 4 / 3)
    chase = (ax < 2) & (zc < 2)
    return np.select([heart, shadow, chase], ["heart", "shadow", "chase"], "waste")


def load(seasons: list[int], extra: list[str] | None = None, return_zones: bool = False):
    """Prepared pitches of the given regular seasons from the sequence copy (data/seq/), needed columns only,
    with every batter's fixed zone (fixed_zones) taken from all the seasons loaded. With return_zones,
    returns (pitches, zones)."""
    from baseball.edge.familiarity import seq_parts

    cols = COLUMNS + [c for c in (extra or []) if c not in COLUMNS]
    parts = {}
    for s in seasons:
        parts[s] = seq_parts(s)
        if not parts[s]:
            raise FileNotFoundError(f"No sequence data for {s} in data/seq/.")
    zcols = ["batter", "game_year", "sz_top", "sz_bot"]
    zones = fixed_zones(pd.concat([pd.read_parquet(x, columns=zcols) for s in seasons for x in parts[s]],
                                  ignore_index=True))
    out = []
    for s in seasons:      # one season at a time, trimmed as it goes, to keep memory low
        d = prepare(_read(parts[s], cols), zones)
        out.append(compact(d.drop(columns=[c for c in DROP_AFTER_PREPARE if c in d and c not in (extra or [])])))
    out = compact(pd.concat(out, ignore_index=True))
    return (out, zones) if return_zones else out


def _read(files, cols) -> pd.DataFrame:
    """One season's parts as a single frame, strings read straight into categories (saves memory)."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pq.ParquetDataset([str(f) for f in files]).read(columns=cols)
    out = table.to_pandas(strings_to_categorical=True, split_blocks=True, self_destruct=True)
    del table
    pa.default_memory_pool().release_unused()
    return out


def compact(d: pd.DataFrame) -> pd.DataFrame:
    """Strings to categories, game_date to a date, 64-bit integers to 32: a three-season frame in ~0.4 GB."""
    for c in d.columns:
        if d[c].dtype == object:
            if c == "game_date":
                d[c] = pd.to_datetime(d[c])
            else:
                d[c] = d[c].astype("category")
        elif d[c].dtype == "int64" and c not in ("game_pk", "batter"):
            d[c] = d[c].astype("int32")
    return d


# ---------------------------------------------------------------- the league value model

def _X(d: pd.DataFrame) -> np.ndarray:
    return np.column_stack([d["x_in"].to_numpy(float), d["z_rel"].to_numpy(float), d["balls"].to_numpy(float),
                            d["strikes"].to_numpy(float), d["fam"].cat.codes.to_numpy(float)])


@dataclass
class DecisionModel:
    """Three smoothers fit on the training seasons: swing value, take value, swing probability.

    Gradient-boosted trees (scikit-learn's histogram GBM) on location, count and family. Trees fit the
    count and family interactions without a hand-built grid; min_samples_leaf keeps every leaf to at
    least a few hundred pitches, so no estimate rests on a thin cell.
    """
    swing: object
    take: object
    prob: object
    seasons: list[int] = field(default_factory=list)
    n_train: dict = field(default_factory=dict)

    def predict(self, d: pd.DataFrame) -> pd.DataFrame:
        X = _X(d)
        return pd.DataFrame({"es": self.swing.predict(X), "et": self.take.predict(X),
                             "p": self.prob.predict_proba(X)[:, 1]}, index=d.index)


def fit_model(d: pd.DataFrame, seasons: list[int] | None = None, min_leaf: int = 400, iters: int = 250,
              seed: int = 2026) -> DecisionModel:
    """Fit the league model on `seasons` (default: every season in d)."""
    from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

    cols = FEATURES + ["swing", "rv", "season"]
    t = d[cols] if seasons is None else d.loc[d["season"].isin(seasons).to_numpy(), cols]
    X, sw = _X(t), t["swing"].to_numpy(bool)
    y = t["rv"].to_numpy(float)
    has = np.isfinite(y)                     # a few pitches carry no run value; they still count for P(swing)
    kw = dict(max_iter=iters, learning_rate=0.08, max_leaf_nodes=31, min_samples_leaf=min_leaf,
              categorical_features=[4], random_state=seed)
    swing = HistGradientBoostingRegressor(**kw).fit(X[sw & has], y[sw & has])
    take = HistGradientBoostingRegressor(**kw).fit(X[~sw & has], y[~sw & has])
    prob = HistGradientBoostingClassifier(**kw).fit(X, sw)
    return DecisionModel(swing, take, prob, sorted(t["season"].unique().tolist()),
                         {"swings": int(sw.sum()), "takes": int((~sw).sum())})


def score(d: pd.DataFrame, model: DecisionModel, inplace: bool = False) -> pd.DataFrame:
    """Adds es, et, p, gap = es - et, dv = (swing - p) * gap, and mix = (2p - 1) * gap to every pitch."""
    out = d if inplace else d.copy()
    pr = model.predict(d)
    out["es"], out["et"], out["p"] = pr["es"].astype("float32"), pr["et"].astype("float32"), pr["p"].astype("float32")
    out["gap"] = out["es"] - out["et"]
    out["dv"] = (out["swing"].astype("float32") - out["p"]) * out["gap"]
    out["mix"] = (2 * out["p"] - 1) * out["gap"]
    return out


def score_by_era(d: pd.DataFrame, base: list[int], refit: list[int], **kw) -> tuple[pd.DataFrame, dict]:
    """Score `base` seasons with one model fit on them and each `refit` season with its own model.
    Scores d in place (no copy) and returns it with the models.

    Why: the 2026 challenge system changed which takes are strikes (more low strikes, fewer high ones,
    measured in the report), so a take's value in 2026 isn't the 2024-25 value. Each 2026 pitch is
    judged against the 2026 league. A season's own model contains the hitter's own pitches, about 0.4%
    of a full season's league sample, which is negligible for a league average."""
    models = {"base": fit_model(d, base, **kw)}
    for season in refit:
        models[season] = fit_model(d, [season], **kw)
    for c in ("es", "et", "p"):
        d[c] = np.float32(np.nan)
    for key, ss in [("base", base)] + [(y, [y]) for y in refit]:
        m = d["season"].isin(ss).to_numpy()
        pr = models[key].predict(d.loc[m, FEATURES])
        for c in ("es", "et", "p"):
            d.loc[m, c] = pr[c].to_numpy(np.float32)
    d["gap"] = d["es"] - d["et"]
    d["dv"] = (d["swing"].astype("float32") - d["p"]) * d["gap"]
    d["mix"] = (2 * d["p"] - 1) * d["gap"]
    return d, models


def calibration(d: pd.DataFrame, bins: int = 10) -> dict[str, pd.DataFrame]:
    """Out-of-sample check on scored pitches: predicted vs actual by decile of the prediction.
    Swings: es vs rv; takes: et vs rv; all pitches: p vs swing."""
    out = {}
    for name, mask, pred, actual in (("swing value", d["swing"], "es", "rv"), ("take value", ~d["swing"], "et", "rv"),
                                     ("swing probability", np.ones(len(d), bool), "p", "swing")):
        t = d.loc[np.asarray(mask, bool), [pred, actual]].astype(float)
        t["bin"] = pd.qcut(t[pred].rank(method="first"), bins, labels=False)
        out[name] = t.groupby("bin").agg(n=(pred, "size"), predicted=(pred, "mean"), actual=(actual, "mean")).reset_index()
    return out


# ---------------------------------------------------------------- hitter seasons

def _woba_cols(d: pd.DataFrame) -> pd.DataFrame:
    pa = d["woba_denom"].fillna(0).astype(float)
    x = d["estimated_woba_using_speedangle"].astype(float)
    xw = np.where(pa > 0, np.where(x.notna(), x, d["woba_value"].astype(float)), 0.0)
    return pd.DataFrame({"pa": pa, "woba_num": d["woba_value"].fillna(0).astype(float) * (pa > 0),
                         "xwoba_num": np.nan_to_num(xw)}, index=d.index)


def hitter_seasons(s: pd.DataFrame) -> pd.DataFrame:
    """One row per batter-season from scored pitches: pitches, DV100 and its parts, results, discipline.

    dv100       : decision value per 100 pitches (runs above an average decision-maker on the same pitches)
    dv100_zone  : the part earned on pitches in Statcast's zone (1-9), per 100 of all his pitches
    dv100_out   : the part earned outside it; dv100 = dv100_zone + dv100_out
    raw100      : the raw choice-minus-alternative sum per 100, = 2 dv100 + mix100
    """
    w = _woba_cols(s)
    f = np.float32
    dv = s["dv"].to_numpy(f)
    zone, swing = s["in_zone"].to_numpy(bool), s["swing"].to_numpy(bool)
    g = pd.DataFrame({
        "batter": s["batter"].to_numpy(), "season": s["season"].to_numpy(), "n": np.ones(len(s), f), "dv": dv,
        "dv_zone": dv * zone, "dv_out": dv * ~zone, "mix": s["mix"].to_numpy(f), "swing": swing.astype(f),
        "whiff": s["whiff"].to_numpy(f), "in_zone": zone.astype(f), "out_zone": (~zone).astype(f),
        "z_swing": (swing & zone).astype(f), "o_swing": (swing & ~zone).astype(f), "rv": s["rv"].to_numpy(f),
        "pa": w["pa"].to_numpy(f), "woba_num": w["woba_num"].to_numpy(f), "xwoba_num": w["xwoba_num"].to_numpy(f),
    }).groupby(["batter", "season"]).sum().astype(float)
    h = pd.DataFrame(index=g.index)
    h["pitches"] = g["n"].astype(int)
    h["pa"] = g["pa"].astype(int)
    h["dv100"] = 100 * g["dv"] / g["n"]
    h["dv100_zone"] = 100 * g["dv_zone"] / g["n"]
    h["dv100_out"] = 100 * g["dv_out"] / g["n"]
    h["mix100"] = 100 * g["mix"] / g["n"]
    h["raw100"] = 2 * h["dv100"] + h["mix100"]
    h["rv100"] = 100 * g["rv"] / g["n"]
    h["woba"] = g["woba_num"] / g["pa"].where(g["pa"] > 0)
    h["xwoba"] = g["xwoba_num"] / g["pa"].where(g["pa"] > 0)
    h["chase"] = g["o_swing"] / g["out_zone"]
    h["zone_swing"] = g["z_swing"] / g["in_zone"]
    h["whiff"] = g["whiff"] / g["swing"]
    return h.reset_index()


def by_region(s: pd.DataFrame, batter: int, season: int) -> pd.DataFrame:
    """A hitter's swing rate against the league's expected rate, and the decision runs, by attack region."""
    t = s[(s["batter"] == batter) & (s["season"] == season)]
    g = t.groupby("region").agg(pitches=("swing", "size"), swing=("swing", "mean"), expected=("p", "mean"),
                                dv=("dv", "sum"), gap=("gap", "mean"))
    g["swing_minus_expected"] = g["swing"] - g["expected"]
    g["dv_runs"] = g.pop("dv")
    return g.reindex(["heart", "shadow", "chase", "waste"]).reset_index()


def by_count_group(s: pd.DataFrame, batter: int, season: int) -> pd.DataFrame:
    """Decision runs by count group: ahead (more balls than strikes), even, behind, two strikes."""
    t = s[(s["batter"] == batter) & (s["season"] == season)]
    grp = np.select([t["strikes"].eq(2), t["balls"] > t["strikes"], t["balls"] == t["strikes"]],
                    ["two strikes", "ahead", "even"], "behind")
    g = t.groupby(grp).agg(pitches=("swing", "size"), swing=("swing", "mean"), expected=("p", "mean"),
                           dv_runs=("dv", "sum"))
    g["dv100"] = 100 * g["dv_runs"] / g["pitches"]
    return g.reindex(["ahead", "even", "behind", "two strikes"]).reset_index(names="count")


# ---------------------------------------------------------------- reliability and regression

def split_half(s: pd.DataFrame, grid=(50, 100, 200, 300, 450, 600, 800, 1000, 1200), reps: int = 20,
               col: str = "dv", seed: int = 7) -> pd.DataFrame:
    """Within-season reliability of the per-pitch mean of `col` at n pitches, as in the Reliability Atlas:
    each hitter-season's games go to two halves at random, each half is cut to exactly n pitches (a random
    n), and the half means are correlated across hitters. Returns n, r, hitters (mean over reps)."""
    rng = np.random.default_rng(seed)
    base = s[["batter", "season", "game_pk", col]].copy()
    base["hs"] = base.groupby(["batter", "season"]).ngroup()
    games = base[["hs", "game_pk"]].drop_duplicates()
    rows = []
    for _ in range(reps):
        games["half"] = rng.integers(0, 2, len(games))
        t = base.merge(games, on=["hs", "game_pk"], how="left")
        t["u"] = rng.random(len(t))
        t = t.sort_values(["hs", "half", "u"])
        t["k"] = t.groupby(["hs", "half"]).cumcount()
        size = t.groupby(["hs", "half"]).size().unstack(fill_value=0)
        for n in grid:
            ok = size.index[(size.min(axis=1) >= n)]
            if len(ok) < 30:
                continue
            m = t[(t["k"] < n) & t["hs"].isin(ok)].groupby(["hs", "half"])[col].mean().unstack()
            rows.append({"n": n, "r": float(np.corrcoef(m[0], m[1])[0, 1]), "hitters": len(ok)})
    return pd.DataFrame(rows).groupby("n", as_index=False).mean()


def reliability_constant(curve: pd.DataFrame, per_pitch_var: float) -> dict:
    """M from r(n) = n / (n + M) (weighted by hitters at each n), and the true-talent SD tau, per pitch
    and per 100 pitches: tau^2 = sigma^2 / M, where sigma^2 is the within-hitter per-pitch variance."""
    M = fit_reliability_constant(curve["n"], curve["r"], w=curve["hitters"])
    tau = float(np.sqrt(per_pitch_var / M))
    return {"M": M, "tau_per_pitch": tau, "tau100": 100 * tau}


def within_variance(s: pd.DataFrame, col: str = "dv") -> float:
    """Pooled within hitter-season variance of the per-pitch value."""
    g = s.groupby(["batter", "season"])[col]
    return float((g.transform(lambda x: x - x.mean()) ** 2).mean())


def regress_dv(dv100, n, M: float, tau100: float, league: float = 0.0, rho: float | None = None) -> pd.DataFrame:
    """Shrink observed DV100 toward the league: estimate = league + w (observed - league), w = n / (n + M)
    (times rho for next season). Interval: the normal-model posterior, as in reliability.regress()."""
    from baseball.evaluation.reliability import regress

    horizon = "season" if rho is None else "next_season"
    return regress("hitter/dv100", dv100, n, league, horizon=horizon, M=M, tau=tau100, rho=rho)


# ---------------------------------------------------------------- validation

def fisher_ci(r: float, n: int, level: float = 0.95) -> tuple[float, float]:
    from statistics import NormalDist

    z, se = np.arctanh(r), 1 / np.sqrt(n - 3)
    q = NormalDist().inv_cdf(0.5 + level / 2)
    return float(np.tanh(z - q * se)), float(np.tanh(z + q * se))


def pairs(h: pd.DataFrame, a: int, b: int, min_pitches: int = 1000) -> pd.DataFrame:
    """Hitters with min_pitches in both seasons, season-a columns suffixed _a, season-b _b."""
    x = h[(h["season"] == a) & (h["pitches"] >= min_pitches)].set_index("batter")
    y = h[(h["season"] == b) & (h["pitches"] >= min_pitches)].set_index("batter")
    return x.join(y, lsuffix="_a", rsuffix="_b", how="inner").reset_index()


def year_to_year(pr: pd.DataFrame, cols=("dv100", "chase", "zone_swing", "whiff", "woba", "xwoba"),
                 M: float | None = None) -> pd.DataFrame:
    """Pearson r between seasons with a Fisher 95% interval; for dv100 also the disattenuated true-talent
    correlation rho = r / sqrt(rel_a rel_b), rel = mean of n / (n + M)."""
    rows = []
    for c in cols:
        r = float(np.corrcoef(pr[f"{c}_a"], pr[f"{c}_b"])[0, 1])
        lo, hi = fisher_ci(r, len(pr))
        row = {"metric": c, "n": len(pr), "r": r, "lo": lo, "hi": hi}
        if c == "dv100" and M:
            rel_a = float(np.mean(pr["pitches_a"] / (pr["pitches_a"] + M)))
            rel_b = float(np.mean(pr["pitches_b"] / (pr["pitches_b"] + M)))
            row |= {"rel_a": rel_a, "rel_b": rel_b, "rho": r / np.sqrt(rel_a * rel_b),
                    "rho_lo": lo / np.sqrt(rel_a * rel_b), "rho_hi": hi / np.sqrt(rel_a * rel_b)}
        rows.append(row)
    return pd.DataFrame(rows)


def _wls(y, X, w):
    Xw = X * w[:, None]
    beta = np.linalg.pinv(X.T @ Xw) @ (Xw.T @ y)
    e = y - X @ beta
    ybar = np.average(y, weights=w)
    r2 = 1 - np.sum(w * e ** 2) / np.sum(w * (y - ybar) ** 2)
    return beta, r2


def incremental(pr: pd.DataFrame, base: list[str], add: str = "dv100", target: str = "woba_b",
                boot: int = 2000, seed: int = 11) -> dict:
    """Does `add` (season a) help predict `target` beyond `base` (season a)? Weighted by season-b PA.

    Reports the coefficient on `add` per 1 SD of it, the R^2 gain, the leave-one-out RMSE of both fits,
    and hitter-bootstrap 95% intervals for the coefficient and the R^2 gain."""
    cols = [f"{c}_a" for c in base]
    y, w = pr[target].to_numpy(float), pr["pa_b"].to_numpy(float)
    sd = float(pr[f"{add}_a"].std())
    X0 = np.column_stack([np.ones(len(pr))] + [pr[c].to_numpy(float) for c in cols])
    X1 = np.column_stack([X0, pr[f"{add}_a"].to_numpy(float) / sd])

    def stats(idx):
        b0, r0 = _wls(y[idx], X0[idx], w[idx])
        b1, r1 = _wls(y[idx], X1[idx], w[idx])
        return b1[-1], r1 - r0

    coef, dr2 = stats(np.arange(len(pr)))
    rng = np.random.default_rng(seed)
    bs = np.array([stats(rng.integers(0, len(pr), len(pr))) for _ in range(boot)])
    return {"n": len(pr), "base": "+".join(base), "add": add, "coef_per_sd": float(coef),
            "coef_lo": float(np.quantile(bs[:, 0], 0.025)), "coef_hi": float(np.quantile(bs[:, 0], 0.975)),
            "p_le_0": float(np.mean(bs[:, 0] <= 0)), "dr2": float(dr2),
            "dr2_lo": float(np.quantile(bs[:, 1], 0.025)), "dr2_hi": float(np.quantile(bs[:, 1], 0.975)),
            "loo_rmse_base": wls_loo_rmse(y, X0, w), "loo_rmse_with": wls_loo_rmse(y, X1, w), "add_sd": sd}


# ---------------------------------------------------------------- bat tracking

def competitive(d: pd.DataFrame) -> np.ndarray:
    """Statcast's competitive swings: the fastest 90% of a batter's tracked swings in the season, plus any
    swing of 60+ mph that produced a 90+ mph exit velocity (as in reliability.competitive_swings)."""
    tracked = d["bat_speed"].notna() & d["swing"]
    q10 = d["bat_speed"].where(tracked).groupby([d["batter"], d["season"]]).transform(lambda x: x.quantile(0.10))
    return (tracked & ((d["bat_speed"] >= q10) | ((d["bat_speed"] >= 60) & (d["launch_speed"] >= 90)))).to_numpy()


def squared_up(launch_speed, bat_speed, pitch_speed_plate) -> np.ndarray:
    """Exit velocity as a share of the most this bat and pitch speed allow (Savant's squared-up idea):
    max EV = 1.23 bat speed + 0.23 pitch speed at the plate. Squared up = 80%+ of it."""
    mx = 1.23 * np.asarray(bat_speed, float) + 0.23 * np.asarray(pitch_speed_plate, float)
    return np.asarray(launch_speed, float) / mx


def bat_profile(d: pd.DataFrame) -> pd.DataFrame:
    """Bat-tracking profile per batter-season on competitive swings.

    Pitch speed at the plate is approximated as 0.92 x release speed (about 8% is lost on the way).
    Squared-up and blast rates are per contact with a measured exit velocity (fair or foul).
    Blast: squared-up share x 100 + bat speed >= 164 (Savant's definition).
    contact_depth: inches the contact point sits in front of the batter's position (intercept y)."""
    t = d.copy()
    t["comp"] = competitive(t)
    c = t[t["comp"]].copy()
    c["attack_dir_pull"] = -c["attack_direction"]          # Statcast: pull negative for both sides; flip it
    c["ideal_aa"] = c["attack_angle"].between(5, 20).astype(float).where(c["attack_angle"].notna())
    c["fast"] = (c["bat_speed"] >= 75).astype(float)
    contact = c["launch_speed"].notna()
    sq = squared_up(c["launch_speed"], c["bat_speed"], 0.92 * c["release_speed"].astype(float))
    c["sq"] = np.where(contact, (sq >= 0.8).astype(float), np.nan)
    c["blast"] = np.where(contact, ((sq * 100 + c["bat_speed"]) >= 164).astype(float), np.nan)
    g = c.groupby(["batter", "season"]).agg(
        comp_swings=("bat_speed", "size"), bat_speed=("bat_speed", "mean"), fast_swing=("fast", "mean"),
        swing_length=("swing_length", "mean"), attack_angle=("attack_angle", "mean"),
        ideal_aa=("ideal_aa", "mean"), attack_dir_pull=("attack_dir_pull", "mean"),
        swing_path_tilt=("swing_path_tilt", "mean"), squared_up=("sq", "mean"), blast=("blast", "mean"),
        contact_depth=("intercept_ball_minus_batter_pos_y_inches", "mean"))
    return g.reset_index()


def percentile(values: pd.Series, x: float) -> float:
    """Share of values at or below x, in percent."""
    v = pd.Series(values).dropna().to_numpy(float)
    return float(100 * np.mean(v <= x)) if len(v) else float("nan")


# ---------------------------------------------------------------- fictional data (tests)

def fictional_pitches(hitters: int = 60, per_hitter: int = 600, seasons=(2024, 2025), skill_sd: float = 0.15,
                      seed: int = 1) -> pd.DataFrame:
    """FICTIONAL pitches in the Statcast columns prepare() reads. Each fictional hitter has a decision
    skill: he swings more often than the league when a swing is worth more than a take, and less when it
    isn't. The run values follow a simple rule (strikes cost, balls help, swings in the middle of the
    zone pay), so a model can be checked against a known answer."""
    rng = np.random.default_rng(seed)
    skill = rng.normal(0, skill_sd, hitters)
    rows = []
    for season in seasons:
        n = hitters * per_hitter
        b = np.repeat(np.arange(hitters), per_hitter)
        plate_x = rng.normal(0, 0.9, n)
        plate_z = rng.normal(2.5, 0.9, n)
        balls, strikes = rng.integers(0, 4, n), rng.integers(0, 3, n)
        stand = np.where(b % 3 == 0, "L", "R")
        x_in = np.where(stand == "L", -plate_x, plate_x) * 12
        z_rel = (plate_z - 1.6) / (3.4 - 1.6)
        in_zone = (np.abs(x_in) < HALF_PLATE_IN) & (z_rel > 0) & (z_rel < 1)
        dist = np.hypot(x_in / HALF_PLATE_IN, (z_rel - 0.5) * 2)          # 0 middle, ~1 at the edge
        gap = 0.06 * (1 - dist) - 0.01 * strikes                          # swing minus take value
        logit = 2.5 * (1 - dist) + 0.4 * strikes - 0.2 * balls + skill[b] * np.sign(gap) * 4
        swing = rng.random(n) < 1 / (1 + np.exp(-logit))
        take_val = np.where(in_zone, -0.05 - 0.02 * strikes, 0.04 + 0.03 * balls)
        rv = np.where(swing, take_val + gap, take_val) + rng.normal(0, 0.05, n)
        desc = np.where(swing, np.where(rng.random(n) < 0.25, "swinging_strike", "foul"),
                        np.where(in_zone, "called_strike", "ball"))
        rows.append(pd.DataFrame({
            "game_pk": season * 10_000 + (np.tile(np.arange(per_hitter), hitters) // 15), "game_year": season,
            "at_bat_number": 1, "pitch_number": 1, "batter": 1000 + b, "stand": stand,
            "pitch_type": rng.choice(["FF", "SI", "SL", "CH", "FC", "CU"], n), "description": desc, "events": None,
            "type": np.where(swing, "S", np.where(in_zone, "S", "B")), "balls": balls, "strikes": strikes,
            "plate_x": plate_x, "plate_z": plate_z, "sz_top": 3.4, "sz_bot": 1.6,
            "zone": np.where(in_zone, 5, 13), "delta_run_exp": rv, "woba_value": np.nan, "woba_denom": np.nan,
            "estimated_woba_using_speedangle": np.nan, "launch_speed": np.nan, "launch_angle": np.nan,
            "release_speed": 93.0, "bat_speed": np.where(swing, 70 + rng.normal(0, 3, n), np.nan),
            "swing_length": np.nan, "attack_angle": np.nan, "attack_direction": np.nan, "swing_path_tilt": np.nan,
            "intercept_ball_minus_batter_pos_y_inches": np.nan}))
    return pd.concat(rows, ignore_index=True), pd.Series(skill, index=1000 + np.arange(hitters), name="skill")


# ---------------------------------------------------------------- results, execution, aging

def results(p: pd.DataFrame) -> pd.DataFrame:
    """Batting line and batted-ball quality per batter-season from raw Statcast rows (RESULT_COLUMNS).

    Grain: one row per plate appearance (rows with an event), and one per ball in play for the quality
    columns. xBA = expected hits (Statcast's estimated BA on balls in play, 0 on strikeouts) per at-bat.
    EV90 = the 90th percentile exit velocity on balls in play (a raw-power reading less noisy than the max)."""
    from baseball.evaluation.reliability import pulled, spray_angle

    p = p[p["events"].notna() | p["type"].eq("X")].copy()
    for c in ("events", "type", "bb_type", "stand", "description"):
        if c in p:
            p[c] = p[c].astype(object)
    pa = p[p["events"].notna() & (p["events"] != "truncated_pa")].copy()
    ev = pa["events"]
    bases = {"single": 1, "double": 2, "triple": 3, "home_run": 4}
    not_ab = ["walk", "intent_walk", "hit_by_pitch", "sac_bunt", "sac_fly", "sac_fly_double_play", "catcher_interf",
              "sac_bunt_double_play"]
    pa = pa.assign(pa=1, h=ev.isin(list(bases)), tb=ev.map(bases).fillna(0), ab=~ev.isin(not_ab),
                   bb=ev.isin(["walk", "intent_walk"]), hbp=ev.eq("hit_by_pitch"),
                   k=ev.isin(["strikeout", "strikeout_double_play"]), sf=ev.isin(["sac_fly", "sac_fly_double_play"]),
                   hr=ev.eq("home_run"))
    pa["xh"] = np.where(pa["type"].eq("X"), pa["estimated_ba_using_speedangle"].astype(float), 0.0)
    g = pa.groupby(["batter", "game_year"]).agg(pa=("pa", "sum"), ab=("ab", "sum"), h=("h", "sum"), tb=("tb", "sum"),
                                                 bb=("bb", "sum"), hbp=("hbp", "sum"), k=("k", "sum"), sf=("sf", "sum"),
                                                 hr=("hr", "sum"), xh=("xh", "sum"))
    g["avg"] = g["h"] / g["ab"]
    g["obp"] = (g["h"] + g["bb"] + g["hbp"]) / (g["ab"] + g["bb"] + g["hbp"] + g["sf"])
    g["slg"] = g["tb"] / g["ab"]
    g["iso"] = g["slg"] - g["avg"]
    g["k_pct"], g["bb_pct"] = g["k"] / g["pa"], g["bb"] / g["pa"]
    g["xba"] = g["xh"] / g["ab"]
    bip = p[p["type"].eq("X")].copy()
    bip["barrel"] = bip["launch_speed_angle"].eq(6)
    bip["hard"] = bip["launch_speed"] >= 95
    bip["pulled"] = pulled(spray_angle(bip["hc_x"], bip["hc_y"]), bip["stand"])
    bip["pull_fly"] = ((bip["pulled"] == 1) & bip["bb_type"].eq("fly_ball")).astype(float)
    b = bip.groupby(["batter", "game_year"]).agg(bip=("barrel", "size"), barrel=("barrel", "mean"), hard=("hard", "mean"),
                                                  ev=("launch_speed", "mean"),
                                                  ev90=("launch_speed", lambda x: x.quantile(0.9)),
                                                  max_ev=("launch_speed", "max"), la=("launch_angle", "mean"),
                                                  pull=("pulled", "mean"), pull_fly=("pull_fly", "mean"))
    g = g.join(b)
    g["barrel_pa"] = g["barrel"] * g["bip"] / g["pa"]
    return g.reset_index().rename(columns={"game_year": "season"})


def execution(s: pd.DataFrame) -> pd.DataFrame:
    """The run-value decomposition per batter-season, per 100 pitches (scored pitches):

    rv100 = base100 + dv100 + swing_exec100 + take_luck100, where
    base       : what an average hitter's choice would have earned on his pitches, p es + (1 - p) et
    dv         : his decisions against that average choice
    swing_exec : his swings' actual run value minus es (contact quality against the league's on those pitches)
    take_luck  : his takes' actual run value minus et (mostly the umpire, and from 2026 the challenges)"""
    sw = s["swing"].to_numpy(bool)
    rv = s["rv"].astype(float)
    t = pd.DataFrame({"batter": s["batter"], "season": s["season"],
                      "base": s["p"] * s["es"] + (1 - s["p"]) * s["et"], "dv": s["dv"],
                      "swing_exec": np.where(sw, rv - s["es"], 0.0), "take_luck": np.where(~sw, rv - s["et"], 0.0)})
    g = 100 * t.groupby(["batter", "season"]).mean()
    return g.add_suffix("100").reset_index()


def monthly_bat_speed(s: pd.DataFrame, batter: int | None = None) -> pd.DataFrame:
    """Mean bat speed on competitive swings by calendar month (league when batter is None).
    Needs game_date. March games are folded into April."""
    comp = s["comp"].to_numpy(bool) if "comp" in s else competitive(s)
    mask = comp & ((s["batter"] == batter).to_numpy() if batter is not None else True)
    t = s[mask]
    month = pd.to_datetime(t["game_date"]).dt.month.clip(lower=4)
    g = t.groupby([t["season"], month])["bat_speed"].agg(["mean", "size"])
    g.index.names = ["season", "month"]
    return g.reset_index()


def bat_speed_change(table: pd.DataFrame, min_pitches: int = 1000) -> pd.DataFrame:
    """Season-over-season bat-speed change net of the league's change, per hitter with min_pitches in both."""
    q = table[table["pitches"] >= min_pitches]
    lg = q.groupby("season")["bat_speed"].mean()
    w = q.pivot(index="batter", columns="season", values="bat_speed").sub(lg, axis=1)
    rows = []
    seasons = sorted(w.columns)
    for a, b in zip(seasons, seasons[1:]):
        d = (w[b] - w[a]).dropna()
        rows.append(pd.DataFrame({"batter": d.index, "season_a": a, "season_b": b, "change": d.values}))
    return pd.concat(rows, ignore_index=True)


def drop_follow_up(change: pd.DataFrame, threshold: float = -1.5) -> dict:
    """Hitters whose bat speed fell by `threshold` or more (net of league) one year: what happened the next.
    Also the slope of next change on this change over everyone (the share of any change that comes back)."""
    a = change.set_index(["batter", "season_b"])["change"]
    nxt = change.assign(season_b=change["season_a"]).set_index(["batter", "season_b"])["change"]
    j = pd.DataFrame({"drop": a, "next": nxt}).dropna()
    big = j[j["drop"] <= threshold]
    slope = float(np.polyfit(j["drop"], j["next"], 1)[0]) if len(j) > 2 else float("nan")
    se = float(big["next"].std() / np.sqrt(len(big))) if len(big) > 1 else float("nan")
    return {"n_pairs": int(len(j)), "slope_next_on_this": slope, "n_drops": int(len(big)),
            "drops_mean": float(big["drop"].mean()) if len(big) else float("nan"),
            "next_mean": float(big["next"].mean()) if len(big) else float("nan"),
            "next_lo": float(big["next"].mean() - 1.96 * se), "next_hi": float(big["next"].mean() + 1.96 * se),
            "share_back_half": float(np.mean(big["next"] >= -big["drop"] / 2)) if len(big) else float("nan")}


def tool_grade(value: float, mean: float, sd: float, higher_is_better: bool = True) -> dict:
    """A 20-80 reading of a measurement against a population: 50 + 10 z, rounded to the 5-point scale
    (grades.to_scale). The population here is MLB hitters with 1,000+ pitches in the season."""
    from baseball.evaluation.grades import to_scale

    z = (value - mean) / sd * (1 if higher_is_better else -1)
    return {"z": float(z), "raw": float(50 + 10 * z), "grade": to_scale(50 + 10 * z)}


def _ages(batters) -> pd.Series | None:
    """Birth years from the people table (data/people/), or None without it."""
    path = DATA / "people" / "people.parquet"
    if not path.exists():
        return None
    p = pd.read_parquet(path, columns=["key_mlbam", "birth_year"]).dropna()
    return p.drop_duplicates("key_mlbam").set_index("key_mlbam")["birth_year"].reindex(batters).astype(float)


# ---------------------------------------------------------------- projection and price (the report's contract)
# League constants, 2026: FanGraphs Guts! (read 2026-10-18).
LEAGUE_WOBA, WOBA_SCALE, RUNS_PER_WIN = 0.316, 1.238, 9.822
REPLACEMENT_RUNS_PER_PA = 570 * RUNS_PER_WIN / 183_846     # 570 position-player wins over 2026's 183,846 PA
POS_2B_PER_650 = 2.5                                       # FanGraphs positional adjustment, second base
# The price of a win (2027 dollars): the market rate I fit to 46 comparable free-agent contracts.
# A cross-check from public numbers: FanGraphs' flat 2026 rate ($11.23M, Clemens, Feb. 24, 2026) grown 3%
# is $11.57M. One rate for every player: FanGraphs' tiers describe average prices paid by WAR band, not a
# marginal price, and pricing on them puts a cliff at 2.0 WAR. The tiered version is kept as a check.
PRICE_OF_WIN_2027, PRICE_GROWTH, DISCOUNT_RATE = 11.66, 0.03, 0.10
TORRES_MLBAM = 650402


@dataclass
class HitterInputs:
    """Public inputs to a hitter's projection that the pitch data can't supply. Every number is sourced
    where it's set (see TORRES_INPUTS)."""
    bsr: dict                       # season -> (FanGraphs BsR, PA)
    fielding_runs: float            # base fielding runs a season at the position
    fielding_low: float
    fielding_high: float
    pos_per_650: float = POS_2B_PER_650
    age_2027: int = 30


# Gleyber Torres. Baserunning: FanGraphs player page, read 2026-10-18 (BsR -4.6 in 665 PA, 2024; -3.4 in 628,
# 2025; -4.9 in 420, 2026). Sprint speed (Baseball Savant sprint-speed leaderboard, 10+ competitive runs, read
# 2026-10-18): 26.6, 26.2 and 25.3 ft/s in 2024-26, the 26th, 20th and 7th percentiles of 566, 579 and 567 players.
# Fielding at second base (Baseball Savant outs-above-average leaderboard, read 2026-10-18): -5 outs above average
# in each of 2024, 2025 and 2026, and -3, -4 and -3 fielding runs prevented. Base: those runs weighted 5/4/3 like
# the bat, -3.3. Range: two runs either side (-5.3 to -1.3), wider than his own three-season spread because one
# season of fielding runs is noisy.
TORRES_INPUTS = HitterInputs(bsr={2024: (-4.6, 665), 2025: (-3.4, 628), 2026: (-4.9, 420)},
                             fielding_runs=(5 * -3 + 4 * -4 + 3 * -3) / 12, fielding_low=(5 * -3 + 4 * -4 + 3 * -3) / 12 - 2,
                             fielding_high=(5 * -3 + 4 * -4 + 3 * -3) / 12 + 2)


def blend_woba(seasons: dict, weights=(5, 4, 3), regress_pa: float = 1200, league: float = LEAGUE_WOBA,
               age_adj: float = -0.003) -> dict:
    """Projected wOBA: each season's mean of wOBA and xwOBA, weighted 5/4/3 (latest first) times PA, then
    regressed with `regress_pa` plate appearances of league average (the seasons' raw PA count against it),
    plus an aging step. `seasons`: {year: {"woba", "xwoba", "pa"}}."""
    ys = sorted(seasons, reverse=True)[:len(weights)]
    w = np.array([weights[i] * seasons[y]["pa"] for i, y in enumerate(ys)], float)
    x = np.array([(seasons[y]["woba"] + seasons[y]["xwoba"]) / 2 for y in ys], float)
    blend = float(np.sum(w * x) / np.sum(w))
    pa = float(sum(seasons[y]["pa"] for y in ys))
    regressed = (pa * blend + regress_pa * league) / (pa + regress_pa)
    return {"blend": blend, "pa": pa, "regressed": regressed, "projection": regressed + age_adj}


def bsr_rate(bsr: dict, weights=(5, 4, 3)) -> float:
    """Baserunning runs per PA, weighted 5/4/3 (latest first) by season and PA, like the wOBA blend."""
    ys = sorted(bsr, reverse=True)[:len(weights)]
    runs = sum(weights[i] * bsr[y][0] for i, y in enumerate(ys))
    pa = sum(weights[i] * bsr[y][1] for i, y in enumerate(ys))
    return runs / pa


def project_war_season(woba: float, pa: float, fielding: float, bsr_per_pa: float,
                       pos_per_650: float = POS_2B_PER_650, include_bsr: bool = True) -> dict:
    """One season's WAR from components: batting runs at the league wOBA and scale, replacement, position,
    fielding (a season's runs), baserunning (rate x PA), divided by runs per win."""
    parts = {"batting": (woba - LEAGUE_WOBA) / WOBA_SCALE * pa, "replacement": REPLACEMENT_RUNS_PER_PA * pa,
             "position": pos_per_650 * pa / 650, "fielding": fielding,
             "baserunning": bsr_per_pa * pa if include_bsr else 0.0}
    runs = sum(parts.values())
    return {"woba": woba, "pa": pa, **parts, "runs": runs, "war": runs / RUNS_PER_WIN}


def contract_value(war_2027: float, years: int = 2, age_2027: int = 30, rate_2027: float = PRICE_OF_WIN_2027,
                   growth: float = PRICE_GROWTH, discount: float = DISCOUNT_RATE) -> dict:
    """Value of `years` seasons from 2027 at one price of a win: WAR aged as baseball.roster.money.project_war
    (-0.4 a year from 29), each season at rate_2027 x (1 + growth)^t, discounted to 2027. Also the same
    WAR priced on FanGraphs' 2026 tiers (money.value_seasons) for comparison."""
    from baseball.roster.money import project_war, value_seasons

    war = project_war(war_2027, age_2027, years)
    by_year = [w * rate_2027 * (1 + growth) ** t for t, w in enumerate(war)]
    pv_ = sum(v / (1 + discount) ** t for t, v in enumerate(by_year))
    tiers = value_seasons(war, 2027, discount=discount)
    return {"war": war, "value": by_year, "pv": pv_, "first_year": by_year[0],
            "tiered_first_year": tiers.value[0], "tiered_pv": tiers.pv_value}


def torres_price(card_seasons: dict, inputs: HitterInputs = TORRES_INPUTS) -> dict:
    """The report's projection and price for Torres from the card's season lines (summary.json) and the
    public inputs above. Scenarios: base = the blended wOBA at 550 PA; the two others are judgment inputs,
    not fits: the 2026 bat stays (.312, 450 PA) and the 2025 bat comes back (.340, 600 PA)."""
    seasons = {int(y): v for y, v in card_seasons.items()}
    blend = blend_woba(seasons)
    rate = bsr_rate(inputs.bsr)
    scen = {"low": (0.312, 450), "base": (round(blend["projection"], 3), 550), "high": (0.340, 600)}
    out = {"blend": blend, "bsr_per_pa": rate, "scenarios": {}, "fielding_range": {}}
    for k, (woba, pa) in scen.items():
        p = project_war_season(woba, pa, inputs.fielding_runs, rate, inputs.pos_per_650)
        out["scenarios"][k] = p | {"value": contract_value(p["war"], 1, inputs.age_2027),
                                   "value_2y": contract_value(p["war"], 2, inputs.age_2027)}
    woba, pa = scen["base"]
    for k, f in (("low", inputs.fielding_low), ("high", inputs.fielding_high)):
        p = project_war_season(woba, pa, f, rate, inputs.pos_per_650)
        out["fielding_range"][k] = p | {"fielding_input": f, "value_2y": contract_value(p["war"], 2, inputs.age_2027)}
    # the earlier version of this report: no baserunning, priced on the tiers
    p = project_war_season(woba, pa, inputs.fielding_runs, rate, inputs.pos_per_650, include_bsr=False)
    out["without_baserunning"] = p | {"value_2y": contract_value(p["war"], 2, inputs.age_2027)}
    return out


def grade_from_percentile(pct: float) -> dict:
    """A 20-80 grade from a population percentile (normal z), for tools where only a percentile is public."""
    from scipy.stats import norm

    from baseball.evaluation.grades import to_scale

    z = float(norm.ppf(pct / 100))
    return {"z": z, "raw": 50 + 10 * z, "grade": to_scale(50 + 10 * z)}


# ---------------------------------------------------------------- figure

def figure(s: pd.DataFrame, pr: pd.DataFrame, batter: int, seasons: list[int], name: str, months: pd.DataFrame,
           league_months: pd.DataFrame, out: Path, min_swings: int = 40) -> Path:
    """Three panels: (1) the hitter's swing rate minus an average hitter's on the same pitches, in his zone;
    (2) year-to-year decision value for every hitter with 1,000+ pitches both seasons, him marked;
    (3) his bat speed by month against the league's (months with min_swings competitive swings or more)."""
    import matplotlib.pyplot as plt

    from baseball.viz import GRID, INK, MUTED, _style

    t = s[(s["batter"] == batter) & s["season"].isin(seasons)]
    months = months[months["size"] >= min_swings]
    label = "-".join(str(y)[-2:] if i else str(y) for i, y in enumerate(sorted(seasons)))
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(17, 5.4), dpi=150, gridspec_kw={"width_ratios": [1, 1.05, 1.15]})
    xb, zb = np.arange(-20, 20.1, 4), np.arange(-0.5, 1.51, 1 / 6)
    ix, iz = np.digitize(t["x_in"], xb) - 1, np.digitize(t["z_rel"], zb) - 1
    ok = (ix >= 0) & (ix < len(xb) - 1) & (iz >= 0) & (iz < len(zb) - 1)
    diff = (t["swing"].astype(float) - t["p"].astype(float)).to_numpy()
    cells = pd.DataFrame({"ix": ix[ok], "iz": iz[ok], "d": diff[ok]}).groupby(["ix", "iz"])["d"].agg(["mean", "size"])
    grid = np.full((len(zb) - 1, len(xb) - 1), np.nan)
    for (i, j), row in cells[cells["size"] >= 15].iterrows():
        grid[j, i] = row["mean"]
    _style(a1)
    a1.grid(False)
    im = a1.imshow(grid * 100, origin="lower", extent=[xb[0], xb[-1], zb[0], zb[-1]], aspect="auto",
                   cmap="RdBu_r", vmin=-30, vmax=30)
    a1.add_patch(plt.Rectangle((-HALF_PLATE_IN, 0), 2 * HALF_PLATE_IN, 1, fill=False, ec=INK, lw=1.4))
    a1.set_xlabel("Inches from the middle of the plate (right = away from him)", color=MUTED, fontsize=9)
    a1.set_ylabel("Height in his zone (0 = bottom, 1 = top)", color=MUTED, fontsize=9)
    a1.set_title(f"{name}, {label}: his swing rate minus an average\nhitter's on the same pitches (blue = takes more)",
                 fontsize=10.5, color=INK, loc="left")
    cb = fig.colorbar(im, ax=a1, fraction=0.046, pad=0.03)
    cb.set_label("percentage points (cells with 15+ pitches)", color=MUTED, fontsize=8)
    cb.ax.tick_params(labelsize=8, colors=MUTED)

    _style(a2)
    a2.scatter(pr["dv100_a"], pr["dv100_b"], s=12, color="#9db4cc", alpha=0.85, linewidths=0)
    me = pr[pr["batter"] == batter]
    if len(me):
        a2.scatter(me["dv100_a"], me["dv100_b"], s=60, color="#c0392b", zorder=3, edgecolors="white", linewidths=1.5)
        a2.annotate(name, (me["dv100_a"].iloc[0], me["dv100_b"].iloc[0]), xytext=(-8, 8), ha="right",
                    textcoords="offset points", fontsize=9, color=INK)
    r = np.corrcoef(pr["dv100_a"], pr["dv100_b"])[0, 1]
    a2.axhline(0, color=MUTED, lw=0.8)
    a2.axvline(0, color=MUTED, lw=0.8)
    ya, yb = int(pr["season_a"].iloc[0]), int(pr["season_b"].iloc[0])
    a2.set_xlabel(f"Decision runs per 100 pitches, {ya}", color=MUTED, fontsize=9)
    a2.set_ylabel(f"Decision runs per 100 pitches, {yb}", color=MUTED, fontsize=9)
    a2.set_title(f"Decisions carry over: r = {r:.2f}\n{len(pr)} hitters with 1,000+ pitches in both seasons",
                 fontsize=10.5, color=INK, loc="left")

    _style(a3)
    x_his = months["season"] + (months["month"] - 4) / 6
    x_lg = league_months["season"] + (league_months["month"] - 4) / 6
    for season_, g in league_months.groupby("season"):
        a3.plot(season_ + (g["month"] - 4) / 6, g["mean"], color=MUTED, lw=2)
    for season_, g in months.groupby("season"):
        # every month April-September, NaN where he had too few swings, so the line breaks across a gap
        g = g.set_index("month").reindex(range(4, 10))
        a3.plot(season_ + (g.index - 4) / 6, g["mean"], color="#c0392b", lw=2, marker="o", ms=5)
    a3.text(x_lg.iloc[-1] + 0.05, league_months["mean"].iloc[-1], "League", color=MUTED, fontsize=9, va="center")
    a3.text(x_his.iloc[-1] + 0.05, months["mean"].iloc[-1], name.split()[-1], color=INK, fontsize=9, va="center")
    a3.set_xticks([y + 0.42 for y in sorted(months["season"].unique())])
    a3.set_xticklabels([str(y) for y in sorted(months["season"].unique())])
    a3.set_xlim(x_his.min() - 0.1, x_his.max() + 0.45)
    a3.set_ylabel("Bat speed, competitive swings (mph)", color=MUTED, fontsize=9)
    a3.set_title(f"The bat: bat speed by month, April to September\n(months with {min_swings}+ competitive swings)",
                 fontsize=10.5, color=INK, loc="left")
    fig.text(0.01, 0.005, "Source: Statcast via Baseball Savant, regular seasons 2024-26. League swing and take values "
             "fit on 2024-25 (2026 on its own season). Each batter's zone fixed (see method).", fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


# ---------------------------------------------------------------- the whole study

def run(seasons=(2024, 2025, 2026), base=(2024, 2025), batter: int = 650402, name: str = "Gleyber Torres",
        out_dir: Path | None = None, figure_path: Path | None = None, reps: int = 20, boot: int = 2000,
        log=print) -> dict:
    """The league study and one hitter's card. Writes tables to out_dir (default data/edge/swing_decisions/)
    and returns the numbers the report quotes. About 2.5 minutes and about 1.5 GB of memory."""
    import json

    from baseball.edge.familiarity import seq_parts

    out = Path(out_dir or OUT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    seasons, base = list(seasons), list(base)
    refit = [x for x in seasons if x not in base]
    # results from the raw rows (plate appearances that pitch-level filters would drop count here)
    res = pd.concat([results(_read(seq_parts(y), RESULT_COLUMNS)) for y in seasons], ignore_index=True)
    d, zones = load(seasons, return_zones=True)
    log(f"{len(d):,} pitches; zones: {zones['zone_source'].value_counts().to_dict()}")
    s, models = score_by_era(d, base, refit)
    del d
    # what 2026 would look like judged by the 2024-25 league (the reason for the refit)
    alt = {}
    for y in refit:
        m = (s["season"] == y).to_numpy()
        pr = models["base"].predict(s.loc[m, FEATURES])
        alt[y] = {"league_dv100_with_base_model": float(100 * ((s.loc[m, "swing"] - pr["p"]) * (pr["es"] - pr["et"])).mean()),
                  "swing_rate": float(s.loc[m, "swing"].mean()), "p_base_model": float(pr["p"].mean()),
                  "p_own_model": float(s.loc[m, "p"].mean())}
    # out-of-sample check in one rule regime: a model fit on the first base season, scored on the second
    holdout = {}
    if len(base) >= 2:
        early = fit_model(s, base[:1])
        m = (s["season"] == base[1]).to_numpy()
        pr = early.predict(s.loc[m, FEATURES])
        t = pd.DataFrame({"swing": s.loc[m, "swing"].to_numpy(), "rv": s.loc[m, "rv"].to_numpy()}) \
            .assign(es=pr["es"].to_numpy(), et=pr["et"].to_numpy(), p=pr["p"].to_numpy())
        cal = {f"{base[0]} model on {base[1]}": calibration(t)}
        dv_early = pd.Series((t["swing"] - t["p"]) * (t["es"] - t["et"]), name="dv_early").to_numpy()
        holdout = pd.DataFrame({"batter": s.loc[m, "batter"].to_numpy(), "dv": dv_early}) \
            .groupby("batter")["dv"].agg(["mean", "size"])
        del early, pr, t
    log("scored")
    s["comp"] = competitive(s)
    h = hitter_seasons(s)
    bp = bat_profile(s)
    ex = execution(s)
    table = h.merge(bp, on=["batter", "season"], how="left").merge(ex.drop(columns="dv100"), on=["batter", "season"], how="left") \
             .merge(res, on=["batter", "season"], how="left", suffixes=("", "_res"))
    table.to_parquet(out / "hitter_seasons.parquet")
    robust = {}
    if len(holdout):
        hb = table[(table["season"] == base[1]) & (table["pitches"] >= 1000)].set_index("batter")
        e = 100 * holdout["mean"].reindex(hb.index)
        robust["r_with_main"] = float(np.corrcoef(e, hb["dv100"])[0, 1])
        if base[1] + 1 in seasons:
            pr = pairs(table, base[1], base[1] + 1)
            pr["dv100_a"] = 100 * holdout["mean"].reindex(pr["batter"]).to_numpy()
            robust["y2y_r"] = float(np.corrcoef(pr["dv100_a"], pr["dv100_b"])[0, 1])
            robust["incremental_woba_xwoba"] = incremental(pr, ["woba", "xwoba"], boot=boot)
    # reliability (games split at random), base seasons and each refit season
    rel = {}
    for label, ss in [("base", base)] + [(str(y), [y]) for y in refit]:
        x = s[s["season"].isin(ss)]
        curve = split_half(x, reps=reps)
        rel[label] = reliability_constant(curve, within_variance(x)) | {"curve": curve.to_dict("records")}
    M = rel["base"]["M"]
    log(f"reliability: M = {M:.0f}")
    # validation
    val = {}
    for a, b in zip(seasons, seasons[1:]):
        pr = pairs(table, a, b)
        y2y = year_to_year(pr, M=M)
        inc = [incremental(pr, base_, boot=boot) for base_ in
               (["woba"], ["woba", "xwoba"], ["woba", "xwoba", "chase", "zone_swing", "whiff"])]
        resid = {}
        for side in ("a", "b"):
            X = np.column_stack([np.ones(len(pr)), pr[f"chase_{side}"], pr[f"zone_swing_{side}"]])
            beta = np.linalg.lstsq(X, pr[f"dv100_{side}"], rcond=None)[0]
            resid[side] = pr[f"dv100_{side}"] - X @ beta
            resid[f"r2_{side}"] = 1 - np.var(resid[side]) / np.var(pr[f"dv100_{side}"])
        r_res = float(np.corrcoef(resid["a"], resid["b"])[0, 1])
        val[f"{a}-{b}"] = {"y2y": y2y.to_dict("records"), "incremental": inc,
                           "dv_r2_on_chase_zone_swing": [float(resid["r2_a"]), float(resid["r2_b"])],
                           "residual_y2y": [r_res, *fisher_ci(r_res, len(pr))]}
    rho = float(np.mean([v["y2y"][0]["rho"] for v in val.values()]))
    q = table[table["pitches"] >= 1000]
    corr = q[["dv100", "chase", "zone_swing", "whiff", "woba", "xwoba", "rv100", "swing_exec100", "bat_speed",
              "blast", "contact_depth", "pull"]].corr()
    # the hitter
    me = table[table["batter"] == batter].set_index("season")
    card = {"seasons": {}, "regions": {}, "counts": {}, "families": {}}
    for y in seasons:
        if y not in me.index:
            continue
        qy = q[q["season"] == y]
        row = me.loc[y]
        card["seasons"][y] = {c: (float(row[c]) if pd.notna(row[c]) else None) for c in me.columns if c != "batter"}
        card["seasons"][y]["pct"] = {c: percentile(qy[c], float(row[c])) for c in
                                     ["dv100", "dv100_zone", "dv100_out", "chase", "zone_swing", "whiff", "woba", "xwoba",
                                      "bat_speed", "swing_length", "attack_angle", "ideal_aa", "attack_dir_pull",
                                      "swing_path_tilt", "squared_up", "blast", "contact_depth", "swing_exec100",
                                      "avg", "obp", "slg", "iso", "k_pct", "bb_pct", "xba", "barrel", "barrel_pa", "hard",
                                      "ev", "ev90", "max_ev", "la", "pull", "pull_fly"] if pd.notna(row.get(c))}
        card["seasons"][y]["league"] = {c: [float(qy[c].mean()), float(qy[c].std())] for c in
                                        ["dv100", "xba", "avg", "ev90", "max_ev", "iso", "barrel_pa", "bat_speed"]}
        reg = regress_dv(row["dv100"], row["pitches"], M, rel["base"]["tau100"] if y in base else rel[str(y)]["tau100"],
                         league=float(qy["dv100"].mean()))
        nxt = regress_dv(row["dv100"], row["pitches"], M, rel["base"]["tau100"], league=float(qy["dv100"].mean()), rho=rho)
        card["seasons"][y]["dv100_regressed"] = reg.iloc[0].to_dict()
        card["seasons"][y]["dv100_next_season"] = nxt.iloc[0].to_dict()
        card["regions"][y] = by_region(s, batter, y).to_dict("records")
        card["counts"][y] = by_count_group(s, batter, y).to_dict("records")
        t = s[(s["batter"] == batter) & (s["season"] == y)]
        fam = t.groupby("fam", observed=True).agg(pitches=("dv", "size"), dv=("dv", "sum"), swing=("swing", "mean"),
                                                  expected=("p", "mean"))
        card["families"][y] = fam.assign(dv100=100 * fam["dv"] / fam["pitches"]).reset_index().to_dict("records")
    months = monthly_bat_speed(s, batter)
    league_months = monthly_bat_speed(s)
    change = bat_speed_change(table)
    card["bat_speed_months"] = months.to_dict("records")
    card["bat_speed_change"] = change[change["batter"] == batter].to_dict("records")
    card["change_sd"] = change.groupby("season_b")["change"].std().to_dict()
    ages = _ages(change["batter"].unique())
    if ages is not None:
        ch = change.assign(age=change["season_b"] - change["batter"].map(ages))
        card["age_change"] = ch.groupby(pd.cut(ch["age"], [20, 25, 28, 31, 34, 41]), observed=True)["change"] \
                               .agg(["mean", "size", "std"]).reset_index().astype({"age": str}).to_dict("records")
    card["drop_follow_up"] = drop_follow_up(change)
    pr_last = pairs(table, seasons[-2], seasons[-1])
    fig = figure(s, pr_last, batter, seasons[-2:], name, months, league_months,
                 Path(figure_path or out / "swing-decisions.png"))
    summary = {"pitches": {int(k): int(v) for k, v in s.groupby("season").size().items()},
               "train": {str(k): v.n_train for k, v in models.items()}, "zones_map": zones.attrs.get("map"),
               "zone_sources": zones["zone_source"].value_counts().to_dict(), "refit_check": alt,
               "calibration": {y: {k: v.to_dict("records") for k, v in c.items()} for y, c in cal.items()},
               "robustness_early_model": robust,
               "league_dv100": {int(k): float(v) for k, v in (100 * s.groupby("season")["dv"].mean()).items()},
               "regulars": {int(k): int(v) for k, v in q.groupby("season").size().items()},
               "dv100_sd_regulars": {int(k): float(v) for k, v in q.groupby("season")["dv100"].std().items()},
               "reliability": {k: {kk: vv for kk, vv in v.items() if kk != "curve"} for k, v in rel.items()},
               "curves": {k: v["curve"] for k, v in rel.items()}, "validation": val, "rho_used": rho,
               "correlations_regulars": corr.round(3).to_dict(), "card": card, "figure": str(fig)}
    if batter == TORRES_MLBAM:
        summary["price"] = torres_price(card["seasons"])
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=float))
    log(f"wrote {out / 'summary.json'} and {fig}")
    return summary


def main(argv: list[str] | None = None) -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Swing-decision value study and one hitter's card.")
    ap.add_argument("--batter", type=int, default=650402, help="MLBAM id (default: Gleyber Torres)")
    ap.add_argument("--name", default="Gleyber Torres")
    ap.add_argument("--figure", default=None, help="where to write the figure (default: the output folder)")
    ap.add_argument("--reps", type=int, default=20)
    ap.add_argument("--price-only", action="store_true",
                    help="recompute Torres's projection and price from an existing summary.json (seconds, not minutes)")
    a = ap.parse_args(argv)
    if a.price_only:
        import json

        path = OUT_DIR / "summary.json"
        summ = json.loads(path.read_text())
        summ["price"] = torres_price(summ["card"]["seasons"])
        path.write_text(json.dumps(summ, indent=1, default=float))
        print(json.dumps({k: {"war": round(v["war"], 3), "value_1y": round(v["value"]["first_year"], 2),
                              "value_2y": round(v["value_2y"]["pv"], 2)} for k, v in summ["price"]["scenarios"].items()}))
    else:
        run(batter=a.batter, name=a.name, figure_path=Path(a.figure) if a.figure else None, reps=a.reps)


if __name__ == "__main__":
    main()
