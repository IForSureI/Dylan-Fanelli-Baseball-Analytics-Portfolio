"""Does a pitch wear out? Pitch-type familiarity within a game (and across a season).

The question: when a hitter has already seen more of a pitch type from this pitcher today, is that
pitch type less effective against him, beyond the general times-through-the-order effect?

The design separates two kinds of familiarity:
- generic: he has seen this pitcher more (more plate appearances, more pitches of any kind)
- type-specific: of the pitches he has seen, more were this pitch type

The estimate of interest is the contrast `same - other`: the effect of one earlier pitch having been this
type rather than a different type, with total pitches seen, prior plate appearances, count, location,
the pitch's own physics and the pitcher's fatigue held fixed.

Grain: one row per pitch (regular season). Exposure columns count pitches this pitcher threw this
batter earlier in the same game, before the current pitch:
- prev_same / prev_other   in earlier plate appearances today, same pitch type / any other type
- pa_same / pa_other       earlier in this plate appearance
- game_same / game_other   in earlier games this season (same pitcher and batter)
- next_same / next_other   in LATER plate appearances today. A placebo: the future can't change this
                           pitch, so a non-zero coefficient measures selection (pitchers keep throwing
                           what works), and tells which way the main estimate is biased.

Fixed effects: pitcher x pitch type x season (the pitch's own quality and usage) and
batter x pitch group x season (how well this hitter handles, say, breaking balls).
Standard errors are clustered by pitcher.
"""
from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

from baseball.evaluation.arsenal import SWINGS, WHIFFS
from baseball.stats import absorb, clustered_wls

DATA = Path(__file__).resolve().parents[2] / "data"
SEQ_DIR = DATA / "seq"

GROUP = {"FF": "fastball", "SI": "fastball", "FC": "cutter",
         "SL": "breaking", "ST": "breaking", "CU": "breaking", "KC": "breaking", "SV": "breaking", "CS": "breaking",
         "CH": "offspeed", "FS": "offspeed", "FO": "offspeed", "SC": "offspeed"}
GROUPS = ["fastball", "cutter", "breaking", "offspeed"]

SEQ_COLUMNS = [
    "game_pk", "game_date", "game_year", "game_type", "at_bat_number", "pitch_number", "pitcher", "batter",
    "player_name", "p_throws", "stand", "pitch_type", "description", "type", "events", "release_speed",
    "release_spin_rate", "release_extension", "release_pos_x", "release_pos_z", "arm_angle", "pfx_x", "pfx_z",
    "plate_x", "plate_z", "sz_top", "sz_bot", "zone", "balls", "strikes", "inning", "outs_when_up",
    "n_thruorder_pitcher", "delta_run_exp", "estimated_woba_using_speedangle", "launch_speed", "bat_speed",
    "swing_length",
]

EXPOSURE = ["prev_same", "prev_other", "pa_same", "pa_other"]


# ---------------------------------------------------------------- data

def seq_parts(season: int) -> list[Path]:
    """The sequence copy of a season: regular-season pitches with batter ids and location, ~3 MB parts."""
    return sorted(Path(p) for p in glob.glob(str(SEQ_DIR / f"seq_{season}_*.parquet")))


def load_seq(season: int) -> pd.DataFrame:
    parts = seq_parts(season)
    if not parts:
        raise FileNotFoundError(f"No sequence data for {season} in {SEQ_DIR}. The monthly update writes it on the Mac.")
    return pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)


def write_seq(season: int, raw_files: list[Path], out_dir: Path = SEQ_DIR, rows_per_part: int = 72_000) -> list[Path]:
    """Write the sequence copy from the monthly league files (regular season only, float32, zstd)."""
    d = pd.concat([pd.read_parquet(f) for f in raw_files], ignore_index=True)
    d = d[d["game_type"].eq("R")][[c for c in SEQ_COLUMNS if c in d.columns]]
    d = d.drop_duplicates(["game_pk", "at_bat_number", "pitch_number"]).sort_values(["game_pk", "at_bat_number", "pitch_number"])
    for c in d.columns:
        if pd.api.types.is_extension_array_dtype(d[c]) and pd.api.types.is_numeric_dtype(d[c]):
            d[c] = d[c].astype("float32")
        elif d[c].dtype == "float64":
            d[c] = d[c].astype("float32")
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob(f"seq_{season}_*.parquet"):
        old.unlink()
    paths = []
    for i, start in enumerate(range(0, len(d), rows_per_part)):
        path = out_dir / f"seq_{season}_{i}.parquet"
        d.iloc[start:start + rows_per_part].to_parquet(path, index=False, compression="zstd")
        paths.append(path)
    return paths


# ---------------------------------------------------------------- exposures

def _excl_cumsum(ind: pd.Series, keys: list[pd.Series]) -> np.ndarray:
    """How many earlier rows in the group had the indicator (rows must already be in time order)."""
    return (ind.groupby(keys).cumsum() - ind).to_numpy()


def exposures(p: pd.DataFrame) -> pd.DataFrame:
    """Add exposure counts to every pitch. Input: pitches of one or more seasons, any order.

    A pitch with no recorded type still counts as a pitch the hitter saw (it lands in *_other).
    """
    p = p.copy()
    p["pitch_type"] = p["pitch_type"].fillna("UN")
    p["group"] = p["pitch_type"].map(GROUP).fillna("other")
    p = p.sort_values(["game_date", "game_pk", "at_bat_number", "pitch_number"]).reset_index(drop=True)

    g, pi, b, ab, t = p["game_pk"], p["pitcher"], p["batter"], p["at_bat_number"], p["pitch_type"]
    one = pd.Series(1, index=p.index)
    seen_game = _excl_cumsum(one, [g, pi, b])                     # all pitches earlier today from him
    seen_game_type = _excl_cumsum(one, [g, pi, b, t])             # same type earlier today
    seen_pa = _excl_cumsum(one, [g, ab, pi, b])                      # earlier in this PA
    seen_pa_type = _excl_cumsum(one, [g, ab, pi, b, t])
    p["pa_same"] = seen_pa_type
    p["pa_other"] = seen_pa - seen_pa_type
    p["prev_same"] = seen_game_type - seen_pa_type
    p["prev_other"] = (seen_game - seen_pa) - p["prev_same"]

    # Earlier plate appearances against this pitcher today (batter-specific times through the order)
    p["prior_pa"] = p.groupby([g, pi, b])["at_bat_number"].rank(method="dense").astype(int) - 1

    # Earlier games this season (same pitcher and batter)
    season = p["game_year"]
    p["game_same"] = _excl_cumsum(one, [season, pi, b, t]) - seen_game_type
    p["game_other"] = (_excl_cumsum(one, [season, pi, b]) - seen_game) - p["game_same"]

    # Cross-type exposure by group (earlier PAs today and earlier in this PA)
    for grp in GROUPS:
        ind = p["group"].eq(grp).astype(int)
        game_g = _excl_cumsum(ind, [g, pi, b])
        pa_g = _excl_cumsum(ind, [g, ab, pi, b])
        p[f"pa_{grp}"] = pa_g
        p[f"prev_{grp}"] = game_g - pa_g

    # Placebo: the same type thrown to him in LATER plate appearances today
    tot_type = p.groupby([g, pi, b, t])["pitch_number"].transform("size").to_numpy()
    tot = p.groupby([g, pi, b])["pitch_number"].transform("size").to_numpy()
    pa_tot_type = p.groupby([g, ab, pi, b, t])["pitch_number"].transform("size").to_numpy()
    pa_tot = p.groupby([g, ab, pi, b])["pitch_number"].transform("size").to_numpy()
    p["next_same"] = tot_type - p["prev_same"].to_numpy() - pa_tot_type
    p["next_other"] = (tot - (seen_game - seen_pa) - pa_tot) - p["next_same"]
    p["has_later_pa"] = (p.groupby([g, pi, b])["prior_pa"].transform("max") > p["prior_pa"]).astype(int)

    # From OTHER pitchers earlier today (e.g. the starter's changeups when a reliever throws his):
    # same type, same group but another type (a splitter before a changeup), and any pitch.
    # Same type is also split by whether that earlier pitcher threw with the same hand.
    gr = p["group"]
    me_any = seen_game
    me_type = seen_game_type
    me_grp = _excl_cumsum(one, [g, pi, b, gr])
    p["xp_same"] = _excl_cumsum(one, [g, b, t]) - me_type
    p["xp_total"] = _excl_cumsum(one, [g, b]) - me_any
    p["xp_group_other_type"] = (_excl_cumsum(one, [g, b, gr]) - me_grp) - p["xp_same"]
    same_hand_type = np.zeros(len(p), dtype=int)
    for h in ("L", "R"):
        ind = p["p_throws"].eq(h).astype(int)
        same_hand_type = np.where(p["p_throws"].eq(h), _excl_cumsum(ind, [g, b, t]), same_hand_type)
    p["xp_same_samehand"] = same_hand_type - me_type
    p["xp_same_otherhand"] = p["xp_same"] - p["xp_same_samehand"]

    # Totals (for the same-minus-other parameterization)
    for w in ("prev", "pa", "game"):
        p[f"{w}_total"] = p[f"{w}_same"] + p[f"{w}_other"]

    # Pitcher fatigue, role, and the previous pitch
    p["pitch_count"] = p.groupby([g, pi]).cumcount()
    outing = p.groupby([g, pi])
    p["starter"] = outing["inning"].transform("min").eq(1) & outing["pitch_count"].transform("max").ge(60)
    prev_type = p.groupby([g, ab, pi, b])["pitch_type"].shift(1)
    p["repeat"] = prev_type.eq(p["pitch_type"]).astype(int)
    return p


# ---------------------------------------------------------------- outcomes and controls

def outcomes(p: pd.DataFrame) -> pd.DataFrame:
    """Flags once, on every pitch: swing, whiff, out-of-zone, chase, run value (pitcher's view)."""
    p = p.copy()
    p["swing"] = p["description"].isin(SWINGS).astype(int)
    p["whiff"] = p["description"].isin(WHIFFS).astype(int)
    p["out_zone"] = (p["zone"] > 9).astype(int)
    p["rv_pitcher"] = -p["delta_run_exp"]                      # Statcast's run value is the offense's
    p["xwoba_con"] = p["estimated_woba_using_speedangle"].where(p["type"].eq("X"))
    return p


def controls(p: pd.DataFrame, location: bool = True) -> pd.DataFrame:
    """Control columns (numeric). Fixed effects are absorbed separately."""
    arm = np.where(p["p_throws"].eq("R"), -1.0, 1.0)
    side = np.where(p["stand"].eq("L"), -1.0, 1.0)
    c = pd.DataFrame(index=p.index)
    count = p["balls"].astype(int).astype(str) + "-" + p["strikes"].astype(int).astype(str)
    c = c.join(pd.get_dummies(count, prefix="c", drop_first=True, dtype=float))
    c = c.join(pd.get_dummies(p["prior_pa"].clip(upper=3), prefix="tto", drop_first=True, dtype=float))
    c["pitch_count"] = p["pitch_count"] / 100
    c["pitch_count2"] = c["pitch_count"] ** 2
    c["same_hand"] = p["p_throws"].eq(p["stand"]).astype(float)
    # The pitch's own physics on this throw (its season mean is absorbed by the fixed effect)
    c["velo"] = p["release_speed"]
    c["ivb"] = p["pfx_z"] * 12
    c["hb_arm"] = p["pfx_x"] * 12 * arm
    c["spin"] = p["release_spin_rate"] / 1000
    if location:
        h = (p["sz_top"] - p["sz_bot"]).where(lambda s: s > 0.5)
        pz = (p["plate_z"] - (p["sz_top"] + p["sz_bot"]) / 2) / h
        px = p["plate_x"] * side
        c["px"], c["pz"], c["px2"], c["pz2"], c["pxz"] = px, pz, px**2, pz**2, px * pz
        c = c.join(pd.get_dummies(p["zone"].astype("Int64").astype(str), prefix="z", drop_first=True, dtype=float))
    return c


# ---------------------------------------------------------------- estimation

def fit(p: pd.DataFrame, y: str, terms: list[str], location: bool = True,
        fe: tuple = ("pkey", "bkey"), cluster: str = "pitcher", all_terms: bool = False) -> pd.DataFrame:
    """y on the exposure terms + controls, fixed effects absorbed, SEs clustered by pitcher.

    Returns one row per term: coef, se, t, p, plus n and the number of clusters. Rows with any
    missing input are dropped first (complete cases).
    """
    from scipy.stats import norm

    c = controls(p, location)
    d = pd.concat([p[[y, *terms, *fe, cluster]], c], axis=1).dropna()
    # Fixed-effect groups with one row carry no within-group information
    for k in fe:
        d = d[d.groupby(k)[y].transform("size") > 1]
    xcols = [*terms, *c.columns]
    r = absorb(d, [y, *xcols], list(fe))
    keep = [col for col in xcols if r[col].abs().max() > 1e-9]          # drop columns the FE swallowed
    beta, se = clustered_wls(r[y].to_numpy(), r[keep].to_numpy(), np.ones(len(r)), d[cluster].to_numpy())
    out = pd.DataFrame({"term": keep, "coef": beta, "se": se})
    out["t"] = out["coef"] / out["se"]
    out["p"] = 2 * norm.sf(out["t"].abs())
    out["n"] = len(d)
    out["clusters"] = d[cluster].nunique()
    out["y_mean"] = d[y].mean()
    return (out if all_terms else out[out["term"].isin(terms)]).reset_index(drop=True)


def keys(p: pd.DataFrame) -> pd.DataFrame:
    """Fixed-effect keys: pitcher x pitch type x season, and batter x pitch group x season."""
    p = p.copy()
    p["pkey"] = p["pitcher"].astype(str) + "|" + p["pitch_type"] + "|" + p["game_year"].astype(str)
    p["bkey"] = p["batter"].astype(str) + "|" + p["group"] + "|" + p["game_year"].astype(str)
    # Finer: pitcher x type x season x month, for in-season trends (April and October fold into neighbors)
    month = pd.to_datetime(p["game_date"]).dt.month.clip(4, 9)
    p["pkey_m"] = p["pkey"] + "|" + month.astype(str)
    return p


PAIRS = [("prev_same", "prev_other"), ("pa_same", "pa_other"), ("game_same", "game_other")]
LABELS = {"prev": "earlier PAs today", "pa": "earlier in this PA", "game": "earlier games this season",
          "next": "later PAs today (placebo)"}


def fit_pairs(p: pd.DataFrame, y: str, pairs: list[tuple[str, str]] = PAIRS, extra: list[str] | None = None,
              location: bool = True, fe: tuple = ("pkey", "bkey")) -> pd.DataFrame:
    """Reparameterize each (same, other) pair so the contrast is one coefficient with its own clustered SE.

    a*same + b*other = (a - b)*same + b*(same + other). The coefficient on `same` is the contrast (one earlier
    pitch having been this type instead of another type); the coefficient on the sum is the effect of one
    more earlier pitch of another type. Returns rows labelled "<window>: same - other" and "<window>: other type".
    """
    q = p.copy()
    terms, names = [], {}
    for same, other in pairs:
        win = same.split("_")[0]
        tot = f"{win}_total"
        q[tot] = q[same] + q[other]
        terms += [same, tot]
        names[same] = f"{win}: same - other"
        names[tot] = f"{win}: other type"
    tab = fit(q, y, terms + list(extra or []), location, fe)
    tab["term"] = tab["term"].replace(names)
    return tab


# ---------------------------------------------------------------- the analyses

OUTCOMES = {  # name: (rows, y, scale for reporting)
    "whiff per swing (pts)": ("swing", "whiff", 100),
    "chase per out-of-zone pitch (pts)": ("out_zone", "swing", 100),
    "run value per 100 pitches": ("all", "rv100", 1),
    "xwOBA on contact (points)": ("contact", "xwoba_con", 1000),
}


def _rows(d: pd.DataFrame, which: str) -> pd.DataFrame:
    if which == "swing":
        return d[d["swing"].eq(1)]
    if which == "out_zone":
        return d[d["out_zone"].eq(1)]
    if which == "contact":
        return d.dropna(subset=["xwoba_con"])
    return d.dropna(subset=["rv100"])


def _contrasts(tab: pd.DataFrame, scale: float) -> pd.DataFrame:
    t = tab.copy()
    t[["coef", "se"]] *= scale
    return t


def prepare(seasons: list[int]) -> pd.DataFrame:
    """Every regular-season pitch of the seasons with exposures, outcomes and fixed-effect keys."""
    p = pd.concat([exposures(load_seq(s)) for s in seasons], ignore_index=True)
    p = keys(outcomes(p))
    p["rv100"] = 100 * p["rv_pitcher"]
    return p


def main_effects(p: pd.DataFrame) -> pd.DataFrame:
    """Same-minus-other contrasts for every window, outcome and pitch group (pooled seasons)."""
    out = []
    for grp in ["fastball", "breaking", "offspeed", "cutter"]:
        d = p[p["group"].eq(grp)]
        for name, (rows, y, scale) in OUTCOMES.items():
            t = _contrasts(fit_pairs(_rows(d, rows), y), scale)
            t.insert(0, "outcome", name)
            t.insert(0, "group", grp)
            out.append(t)
    return pd.concat(out, ignore_index=True)


def robustness(p: pd.DataFrame) -> pd.DataFrame:
    """The whiff contrast under other specifications, plus the future-exposure placebo."""
    out = []
    for grp in ["fastball", "breaking", "offspeed", "cutter"]:
        sw = p[p["group"].eq(grp) & p["swing"].eq(1)]
        specs = {
            "main": lambda d: fit_pairs(d, "whiff"),
            "same sample as the placebo, without it (batters who come up again)":
                lambda d: fit_pairs(d[d["has_later_pa"].eq(1)], "whiff"),
            "placebo: + later PAs today (batters who come up again)":
                lambda d: fit_pairs(d[d["has_later_pa"].eq(1)], "whiff", PAIRS + [("next_same", "next_other")]),
            "pitcher x type x month fixed effects": lambda d: fit_pairs(d, "whiff", fe=("pkey_m", "bkey")),
            "starters only": lambda d: fit_pairs(d[d["starter"]], "whiff"),
            "+ back-to-back control": lambda d: fit_pairs(d, "whiff", extra=["repeat"]),
            "pitcher x type x season x batter side fixed effects (platoon)":
                lambda d: fit_pairs(d.assign(pkey_s=d["pkey"] + "|" + d["stand"]), "whiff", fe=("pkey_s", "bkey")),
            "no location controls": lambda d: fit_pairs(d, "whiff", location=False),
            **{f"season {s}": (lambda d, s=s: fit_pairs(d[d["game_year"].eq(s)], "whiff")) for s in sorted(p["game_year"].unique())},
        }
        for name, fn in specs.items():
            t = _contrasts(fn(sw), 100)
            t = t[t["term"].str.endswith("same - other")]
            t.insert(0, "spec", name)
            t.insert(0, "group", grp)
            out.append(t)
    return pd.concat(out, ignore_index=True)


def dose_response(p: pd.DataFrame) -> pd.DataFrame:
    """Whiff change by how many of the same type he saw in earlier PAs today (1, 2, 3, 4+) and in earlier
    games this season (1-3, 4-7, 8-15, 16+), with total pitches seen held fixed."""
    out = []
    for grp in ["fastball", "breaking", "offspeed"]:
        sw = p[p["group"].eq(grp) & p["swing"].eq(1)].copy()
        today = {"1": (1, 1), "2": (2, 2), "3": (3, 3), "4+": (4, 999)}
        season = {"1-3": (1, 3), "4-7": (4, 7), "8-15": (8, 15), "16+": (16, 999)}
        for lab, (lo, hi) in today.items():
            sw[f"today {lab}"] = sw["prev_same"].between(lo, hi).astype(float)
        for lab, (lo, hi) in season.items():
            sw[f"season {lab}"] = sw["game_same"].between(lo, hi).astype(float)
        terms = [f"today {k}" for k in today] + [f"season {k}" for k in season]
        t = _contrasts(fit(sw, "whiff", terms + ["prev_total", "pa_same", "pa_total", "game_total"]), 100)
        t = t[t["term"].isin(terms)]
        t["share_of_swings"] = [sw[c].mean() for c in t["term"]]
        t.insert(0, "group", grp)
        out.append(t)
    return pd.concat(out, ignore_index=True)


def by_pitch_type(p: pd.DataFrame, types=("FF", "SI", "FC", "SL", "ST", "CU", "KC", "CH", "FS")) -> pd.DataFrame:
    """Earlier-PA contrast per pitch type: whiff per swing (pts) and run value per 100 pitches."""
    out = []
    for pt in types:
        d = p[p["pitch_type"].eq(pt)]
        w = _contrasts(fit_pairs(_rows(d, "swing"), "whiff"), 100)
        r = fit_pairs(_rows(d, "all"), "rv100")
        w = w[w["term"].eq("prev: same - other")].copy()
        r = r[r["term"].eq("prev: same - other")]
        w["rv_coef"], w["rv_se"] = r["coef"].to_numpy(), r["se"].to_numpy()
        w["whiff_pct"] = 100 * w["y_mean"]
        w.insert(0, "pitch_type", pt)
        out.append(w)
    return pd.concat(out, ignore_index=True)


def cross_pitcher(p: pd.DataFrame) -> pd.DataFrame:
    """Does it carry over from one pitcher to the next? Exposure from other pitchers earlier today."""
    base = ["prev_same", "prev_total", "pa_same", "pa_total", "game_same", "game_total"]
    out = []
    for grp in ["fastball", "breaking", "offspeed", "cutter"]:
        sw = p[p["group"].eq(grp) & p["swing"].eq(1)]
        for spec, xs in [("pooled", ["xp_same", "xp_group_other_type", "xp_total"]),
                         ("by hand", ["xp_same_samehand", "xp_same_otherhand", "xp_group_other_type", "xp_total"])]:
            t = _contrasts(fit(sw, "whiff", base + xs), 100)
            t = t[t["term"].isin(["prev_same"] + xs)]
            t.insert(0, "spec", spec)
            t.insert(0, "group", grp)
            out.append(t)
    return pd.concat(out, ignore_index=True)


def tto_decomposition(p: pd.DataFrame) -> pd.DataFrame:
    """How much of the times-through-the-order whiff decline is type-specific exposure.

    Model A: TTO dummies + controls (count, location, pitch physics, fatigue): the controlled decline. Model C adds prev_same and prev_total. The
    type-specific part at TTO k = (same - other contrast) x mean prev_same at k; the general part =
    (effect of any earlier pitch) x mean of ALL pitches seen at k; net exposure = the two together; the rest
    stays on the TTO dummy. The parts come from model C, so they need not sum to model A's decline.
    """
    out = []
    for grp in ["fastball", "breaking", "offspeed", "cutter"]:
        sw = p[p["group"].eq(grp) & p["swing"].eq(1)]
        a = fit(sw, "whiff", [], all_terms=True).set_index("term")
        c = fit(sw, "whiff", ["prev_same", "prev_total"], all_terms=True).set_index("term")
        means = sw[sw["prior_pa"].isin([1, 2])].groupby("prior_pa")[["prev_same", "prev_total"]].mean()
        for k in (1, 2):
            out.append({
                "group": grp, "times_through": k + 1,
                "raw_decline": 100 * a.loc[f"tto_{k}", "coef"], "raw_se": 100 * a.loc[f"tto_{k}", "se"],
                "mean_prev_same": means.loc[k, "prev_same"], "mean_prev_total": means.loc[k, "prev_total"],
                "type_specific": 100 * c.loc["prev_same", "coef"] * means.loc[k, "prev_same"],
                "general_per_pitch_seen": 100 * c.loc["prev_total", "coef"] * means.loc[k, "prev_total"],
                "left_on_tto": 100 * c.loc[f"tto_{k}", "coef"],
            })
    return pd.DataFrame(out)


def moderators(p: pd.DataFrame, pitch_traits: pd.DataFrame) -> pd.DataFrame:
    """Does wear-out speed depend on the pitch? prev_same x z(trait), traits per pitcher x type x season.

    pitch_traits: columns pitcher, game_year, pitch_type + trait columns. Each trait is standardized across
    pitches (one value per pitcher x type x season). P-values get a Benjamini-Hochberg adjustment across all
    tests run here.
    """
    from baseball.stats import benjamini_hochberg

    d0 = p.merge(pitch_traits, on=["pitcher", "game_year", "pitch_type"], how="left")
    plan = {"offspeed": ["tell_auc", "x_whiff_pct", "d_velo", "sep_in", "usage"],
            "breaking": ["tell_auc", "x_whiff_pct", "d_velo", "sep_in", "usage"],
            "fastball": ["x_whiff_pct", "velo", "usage"]}
    out = []
    for grp, traits in plan.items():
        sw = d0[d0["group"].eq(grp) & d0["swing"].eq(1)]
        for m in traits:
            d = sw.dropna(subset=[m]).copy()
            per = d.drop_duplicates("pkey")[m]
            z = (d[m] - per.mean()) / per.std()
            d["prev_same_x"], d["prev_total_x"] = d["prev_same"] * z, d["prev_total"] * z
            t = _contrasts(fit(d, "whiff", ["prev_same", "prev_total", "prev_same_x", "prev_total_x",
                                            "pa_same", "pa_total", "game_same", "game_total"]), 100)
            at_mean = float(t.loc[t["term"].eq("prev_same"), "coef"].iloc[0])
            t = t[t["term"].eq("prev_same_x")].copy()
            t["cost_at_mean"] = at_mean
            t["base_whiff_pct"] = 100 * d["whiff"].mean()
            t.insert(0, "trait", m)
            t.insert(0, "group", grp)
            t["trait_sd"] = per.std()
            t["pitches"] = d["pkey"].nunique()
            out.append(t)
    r = pd.concat(out, ignore_index=True)
    r["p_bh"] = benjamini_hochberg(r["p"].tolist())
    return r


def persistence(p: pd.DataFrame, min_info: float = 40.0) -> pd.DataFrame:
    """Is wear-out speed a stable trait of a pitch? Per pitcher x type x season slope of whiff on prev_same
    (after the fixed effects and every control), then season-to-season correlation of the slopes."""
    from baseball.stats import absorb

    out = []
    for grp in ["fastball", "breaking", "offspeed"]:
        sw = p[p["group"].eq(grp) & p["swing"].eq(1)]
        c = controls(sw)
        d = pd.concat([sw[["whiff", "pkey", "bkey", "pitcher", "pitch_type", "game_year", "prev_same",
                           "prev_total", "pa_same", "pa_total"]], c], axis=1).dropna()
        xc = ["prev_total", "pa_same", "pa_total", *c.columns]
        r = absorb(d, ["whiff", "prev_same", *xc], ["pkey", "bkey"])
        X = r[xc].to_numpy()
        for col in ("whiff", "prev_same"):
            r[col] = r[col] - X @ np.linalg.lstsq(X, r[col].to_numpy(), rcond=None)[0]
        r[["pitcher", "pitch_type", "game_year"]] = d[["pitcher", "pitch_type", "game_year"]]
        s = (r.assign(xy=r["whiff"] * r["prev_same"], xx=r["prev_same"] ** 2)
             .groupby(["pitcher", "pitch_type", "game_year"])[["xy", "xx"]].sum())
        s = s[s["xx"] > min_info]
        s["slope"] = s["xy"] / s["xx"]
        wide = s["slope"].unstack("game_year")
        years = sorted(wide.columns)
        for a, b in zip(years, years[1:]):
            m = wide[[a, b]].dropna()
            if len(m) > 10:
                rho = float(np.corrcoef(m[a], m[b])[0, 1])
                se = (1 - rho ** 2) / np.sqrt(len(m) - 2)
                out.append({"group": grp, "seasons": f"{a}-{b}", "pitches": len(m), "r": rho, "r_se": se,
                            "slope_noise_sd": 100 * float(np.sqrt((1 / s["xx"]).mean() * r["whiff"].var()))})
    t = pd.DataFrame(out)
    pooled = []
    for grp, g in t.groupby("group", sort=False):
        w = 1 / g["r_se"] ** 2
        r_ = float((w * g["r"]).sum() / w.sum())
        se_ = float(np.sqrt(1 / w.sum()))
        pooled.append({"group": grp, "seasons": "pooled", "pitches": int(g["pitches"].sum()), "r": r_, "r_se": se_,
                       "slope_noise_sd": float(g["slope_noise_sd"].mean())})
    return pd.concat([t, pd.DataFrame(pooled)], ignore_index=True)


def exposure_base(p: pd.DataFrame) -> pd.DataFrame:
    """Average pitches a hitter has already seen from this pitcher, per pitch thrown, by role."""
    role = np.where(p["starter"], "starter", "reliever")
    return p.groupby(role)[["prev_total", "pa_total", "game_total"]].mean().rename_axis("role").reset_index()


def break_even(cost_b: float, use_b: float, cost_a: float, use_a: float, seen_today: float,
               season_cost_b: float = 0.0, season_cost_a: float = 0.0, seen_season: float = 0.0,
               pa_cost_b: float = 0.0, pa_cost_a: float = 0.0, seen_pa: float = 0.0) -> float:
    """How much better (runs per 100 pitches, observed) pitch B must be than pitch A before moving usage
    from A to B pays, once familiarity is counted.

    Each pitch of type T carries expected exposure use_T x seen (earlier pitches seen x share that were T),
    so its value is v_T - cost_T x use_T x seen. Total value N x sum(use_T x value_T); its derivative for a
    shift from A to B, written with the observed (average) values, is
        (vbar_B - vbar_A) - seen x (cost_B x use_B - cost_A x use_A).
    Costs are positive numbers: runs per 100 pitches lost per earlier pitch of the same type. Three windows:
    earlier plate appearances today (seen_today), earlier in this plate appearance (seen_pa), earlier games
    this season (seen_season); each uses that window's own cost.
    Only the hitter's in-game (and in-season, same pitcher) learning is counted; a hitter sitting on a
    pitch because he knows the pitcher's overall tendencies is not in these costs.
    """
    return (seen_today * (cost_b * use_b - cost_a * use_a)
            + seen_season * (season_cost_b * use_b - season_cost_a * use_a)
            + seen_pa * (pa_cost_b * use_b - pa_cost_a * use_a))


def pitch_traits(edge_dir: Path, seasons: list[int], p: pd.DataFrame) -> pd.DataFrame:
    """Per pitcher x type x season: release tell AUC, expected whiff, speed gap, movement separation from
    his primary fastball (inches), velocity, usage. From the edge engine's saved outputs."""
    st = pd.concat([pd.read_parquet(edge_dir / f"stuff_{s}.parquet") for s in seasons if (edge_dir / f"stuff_{s}.parquet").exists()])
    te = pd.concat([pd.read_parquet(edge_dir / f"tells_{s}.parquet") for s in seasons if (edge_dir / f"tells_{s}.parquet").exists()])
    st["pitcher"], st["season"] = st["pitcher"].astype(int), st["season"].astype(int)
    fb = (st[st["pitch_type"].isin(["FF", "SI", "FC"])].sort_values("swings").groupby(["pitcher", "season"]).tail(1)
          [["pitcher", "season", "ivb_in", "hb_arm_in"]].rename(columns={"ivb_in": "fb_ivb", "hb_arm_in": "fb_hb"}))
    st = st.merge(fb, on=["pitcher", "season"], how="left")
    st["sep_in"] = np.hypot(st["ivb_in"] - st["fb_ivb"], st["hb_arm_in"] - st["fb_hb"])
    t = st[["pitcher", "season", "pitch_type", "x_whiff_pct", "d_velo", "sep_in", "velo"]].merge(
        te[["pitcher", "season", "pitch_type", "tell_auc"]], on=["pitcher", "season", "pitch_type"], how="left")
    use = (p.groupby(["pitcher", "game_year", "pitch_type"]).size() / p.groupby(["pitcher", "game_year"]).size())
    use = use.rename("usage").reset_index()
    t = t.rename(columns={"season": "game_year"}).merge(use, on=["pitcher", "game_year", "pitch_type"], how="left")
    t["pitcher"] = t["pitcher"].astype(p["pitcher"].dtype)
    return t


def run(seasons: list[int], out_dir: Path | None = None, edge_dir: Path | None = None, log=print) -> dict:
    """Every analysis on the pooled seasons. Saves tables and summary.json to data/edge/familiarity/."""
    import json
    import time

    out_dir = Path(out_dir or DATA / "edge" / "familiarity")
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    p = prepare(seasons)
    log(f"{len(p):,} pitches, {p['game_pk'].nunique():,} games ({time.time() - t0:.0f}s)")
    tables = {
        "main": main_effects(p), "robustness": robustness(p), "dose_response": dose_response(p),
        "pitch_types": by_pitch_type(p), "cross_pitcher": cross_pitcher(p), "tto": tto_decomposition(p),
        "persistence": persistence(p), "exposure_base": exposure_base(p),
    }
    edge_dir = Path(edge_dir or DATA / "edge" / str(max(seasons)))
    if (edge_dir / f"stuff_{max(seasons)}.parquet").exists():
        tables["moderators"] = moderators(p, pitch_traits(edge_dir, seasons, p))
    for name, t in tables.items():
        t.to_parquet(out_dir / f"{name}.parquet", index=False)
        log(f"  {name}: {len(t)} rows ({time.time() - t0:.0f}s)")
    summary = {"seasons": seasons, "pitches": int(len(p)), "games": int(p["game_pk"].nunique()),
               "swings": int(p["swing"].sum()), "pitchers": int(p["pitcher"].nunique()),
               "batters": int(p["batter"].nunique()), "source": "Baseball Savant Statcast, regular season"}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return {"summary": summary, **tables}


# ---------------------------------------------------------------- the page

PAGE_TEMPLATE = Path(__file__).with_name("familiarity_template.html")


def ledger(season: int, pitcher: int, game_pk: int, names: dict | None = None,
           types: tuple = ("FF", "SI", "CH", "SL", "CU"), pitch_types: pd.DataFrame | None = None) -> list[dict]:
    """The exposure ledger for one start: per hitter, pitches of each type seen in his first two plate
    appearances, the league-rate whiff penalty on his third look (count x per-pitch effect), and what he got."""
    s = outcomes(exposures(load_seq(season)))
    g = s[s["pitcher"].eq(pitcher) & s["game_pk"].eq(game_pk)]
    coef = (pitch_types if pitch_types is not None else pd.read_parquet(DATA / "edge" / "familiarity" / "pitch_types.parquet")).set_index("pitch_type")["coef"]
    rows = []
    for slot, b in enumerate(g.drop_duplicates("batter")["batter"], start=1):
        d = g[g["batter"].eq(b)]
        before = d[d["prior_pa"].lt(2)]["pitch_type"].value_counts()
        third = d[d["prior_pa"].eq(2)]
        r = {"slot": slot, "batter": int(b), "name": (names or {}).get(int(b), str(int(b))), "stand": d["stand"].iloc[0]}
        for t in types:
            r[f"seen_{t}"] = int(before.get(t, 0))
            r[f"pen_{t}"] = round(float(coef.get(t, 0.0)) * r[f"seen_{t}"], 1)
        r["pa3_pitches"] = " ".join(third["pitch_type"])
        r["pa3_result"] = str(third["events"].dropna().iloc[-1]) if third["events"].notna().any() else ""
        rows.append(r)
    return rows


def page_data(out_dir: Path | None = None) -> dict:
    """Everything the page shows, from the saved tables (rounded for display)."""
    import json
    from datetime import date

    D = Path(out_dir or DATA / "edge" / "familiarity")
    r = lambda x, n=2: round(float(x), n)  # noqa: E731
    dr = pd.read_parquet(D / "dose_response.parquet")
    pt = pd.read_parquet(D / "pitch_types.parquet")
    m = pd.read_parquet(D / "main.parquet")
    cp = pd.read_parquet(D / "cross_pitcher.parquet")
    cp = cp[cp["spec"].eq("by hand")]
    rb = pd.read_parquet(D / "robustness.parquet")
    rb = rb[rb["term"].str.startswith(("prev", "next"))]
    eb = pd.read_parquet(D / "exposure_base.parquet")
    gs = m[m["term"].eq("game: same - other") & m["outcome"].str.startswith("run")]
    ps = m[m["term"].eq("pa: same - other") & m["outcome"].str.startswith("run")]
    out = {
        "dose": {g: [{"k": t.split(" ", 1)[1], "coef": r(c), "se": r(s)} for t, c, s in zip(d["term"], d["coef"], d["se"]) if t.startswith("today")]
                 for g, d in dr.groupby("group")},
        "types": [{"t": t, "coef": r(c), "se": r(s), "rv": r(v, 4), "rvse": r(vs, 4), "whiff": r(w, 1), "pitchers": int(n)}
                  for t, c, s, v, vs, w, n in zip(pt["pitch_type"], pt["coef"], pt["se"], pt["rv_coef"], pt["rv_se"], pt["whiff_pct"], pt["clusters"])],
        "main": [{"group": g, "outcome": o, "term": t, "coef": r(c), "se": r(s), "p": float(p), "n": int(n), "base": r(y, 3)}
                 for g, o, t, c, s, p, n, y in zip(m["group"], m["outcome"], m["term"], m["coef"], m["se"], m["p"], m["n"], m["y_mean"])],
        "cross": [{"group": g, "term": t, "coef": r(c), "se": r(s), "p": float(p)} for g, t, c, s, p in zip(cp["group"], cp["term"], cp["coef"], cp["se"], cp["p"])],
        "tto": json.loads(pd.read_parquet(D / "tto.parquet").round(2).to_json(orient="records")),
        "mods": json.loads(pd.read_parquet(D / "moderators.parquet")[["group", "trait", "coef", "se", "p", "p_bh", "pitches"]].round(4).to_json(orient="records"))
        if (D / "moderators.parquet").exists() else [],
        "base": {k: {"today": r(a, 4), "pa": r(c, 4), "season": r(b, 4)} for k, a, c, b in zip(eb["role"], eb["prev_total"], eb["pa_total"], eb["game_total"])},
        "season_cost": {g: r(-c, 4) for g, c in zip(gs["group"], gs["coef"])},
        "pa_cost": {g: r(-c, 4) for g, c in zip(ps["group"], ps["coef"])},
        "robust": [{"group": g, "spec": s, "term": t, "coef": r(c), "se": r(e)} for g, s, t, c, e in zip(rb["group"], rb["spec"], rb["term"], rb["coef"], rb["se"])],
        "summary": json.loads((D / "summary.json").read_text()),
        "ledger": json.loads((D / "ledger.json").read_text()) if (D / "ledger.json").exists() else [],
        "built": date.today().isoformat(),
    }
    return out


def build_page(out_dir: Path | None = None) -> Path:
    """Write the familiarity page (data/edge/familiarity/familiarity.html) from the saved tables."""
    import json

    D = Path(out_dir or DATA / "edge" / "familiarity")
    html = PAGE_TEMPLATE.read_text().replace("/*DATA*/null", json.dumps(page_data(D), ensure_ascii=False))
    path = D / "familiarity.html"
    path.write_text(html)
    return path


def figure(out_path: Path | None = None, tables_dir: Path | None = None) -> Path:
    """The report figure: dose-response (earlier PAs today) and the per-pitch-type contrast."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from baseball.viz import PITCH_COLORS, _style

    D = Path(tables_dir or DATA / "edge" / "familiarity")
    # Default: next to the tables, so the monthly run never touches the report's reviewed snapshot
    out_path = Path(out_path or D / "familiarity.png")
    dr, pt = pd.read_parquet(D / "dose_response.parquet"), pd.read_parquet(D / "pitch_types.parquet")
    summary = __import__("json").loads((D / "summary.json").read_text())
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.8), gridspec_kw={"width_ratios": [1.05, 1]})
    cols = {"fastball": PITCH_COLORS["FF"], "breaking": PITCH_COLORS["SL"], "offspeed": PITCH_COLORS["CH"]}
    labels = {"fastball": "Fastballs (FF, SI)", "breaking": "Breaking balls", "offspeed": "Changeups / splitters"}
    for g, c in cols.items():
        d = dr[(dr["group"] == g) & dr["term"].str.startswith("today")]
        y, e = np.r_[0, d["coef"].to_numpy()], np.r_[0, 1.96 * d["se"].to_numpy()]
        x = np.arange(5) + {"fastball": -0.08, "breaking": 0, "offspeed": 0.08}[g]
        a.errorbar(x, y, yerr=e, color=c, marker="o", lw=2, capsize=3, label=labels[g])
    a.set_xticks(range(5)); a.set_xticklabels(["0", "1", "2", "3", "4+"]); a.axhline(0, color="#999", lw=0.8)
    a.set_xlabel("Same-type pitches he saw from this pitcher in earlier PAs today")
    a.set_ylabel("Change in whiff% per swing (points)")
    a.set_title("The more he's seen it, the less he misses it", loc="left", fontsize=12, fontweight="bold")
    a.legend(frameon=False, fontsize=9, loc="lower left"); _style(a)
    names = {"FF": "4-seam", "SI": "Sinker", "FC": "Cutter", "SL": "Slider", "ST": "Sweeper", "CU": "Curve",
             "KC": "Knuckle-curve", "CH": "Changeup", "FS": "Splitter"}
    order = pt.sort_values("coef")
    yy = np.arange(len(order))
    b.barh(yy, order["coef"], xerr=1.96 * order["se"], color=[PITCH_COLORS.get(t, "#888") for t in order["pitch_type"]], capsize=3)
    b.set_yticks(yy); b.set_yticklabels([f"{names.get(t, t)}  ({w:.0f}%)" for t, w in zip(order["pitch_type"], order["whiff_pct"])])
    b.axvline(0, color="#999", lw=0.8); b.set_xlabel("Whiff% change per earlier same-type pitch (points)")
    b.set_title("Splitters and changeups wear out fastest", loc="left", fontsize=12, fontweight="bold"); _style(b)
    seasons = summary["seasons"]
    fig.text(0.01, 0.005,
             f"MLB regular seasons {seasons[0]}-{str(seasons[-1])[2:]}, Statcast via Baseball Savant. Associations, not a randomized test. Total pitches seen, count, location, pitch physics,\n"
             "pitcher fatigue and times through the order held fixed; fixed effects for pitcher x pitch type x season and batter x pitch group x season; 95% intervals clustered by pitcher.\n"
             "Right panel: in parentheses, the pitch type's league whiff% per swing.", fontsize=7.5, color="#555")
    fig.tight_layout(rect=(0, 0.09, 1, 1))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    return out_path
