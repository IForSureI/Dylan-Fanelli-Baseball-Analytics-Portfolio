"""The Reliability Atlas: which numbers to trust, and when.

The question a club pays for: when is a pitcher's or hitter's number signal rather than noise, and how
far should it be regressed before anyone acts on it?

Three measurements per metric, all from public Statcast data (regular seasons only):

1. Within-season reliability r(n). For every player-season, the player's games are split at random into
   two halves (halves never share a game), each half is cut to exactly n events of the metric's own
   denominator (n swings, n balls in play, n pitches of the type), and the halves are correlated
   across players. Because each half holds exactly n, that correlation IS the reliability of an
   n-event sample: no Spearman-Brown step is needed. (Splitting a season of N into halves of N/2 and
   calling the correlation the reliability of N is the classic mistake; the right step-up is
   spearman_brown(r_half, 2).) The curve is fit to r(n) = n / (n + M). M is the sample at which
   r = 0.5 (signal and noise variance equal; the regression constant), and r = 0.7 needs 7M/3.
2. Year-to-year persistence. Same players, same n, both seasons: the between-season correlation of
   n-samples divided by the within-season reliability at that n is rho, the correlation of true talent
   from one season to the next. rho near 1 is a stable skill; rho well below 1 means the skill changes
   or depends on context (team, park, role, health), which is itself a finding.
3. The club deliverable, regress(): shrink an observed value toward a mean with weight n / (n + M)
   (times rho for next season), with an interval from the fitted true-talent spread tau. Validated out
   of sample: parameters fit on 2024-25 only, then 2026 first half -> second half and 2025 -> 2026.

Grain: one row per pitch. Events per metric are its denominator (swings for whiff%, balls in play for
xwOBA on contact, and so on). Every number carries its season, phase (regular season) and sample.
Standard errors and intervals come from repeated random splits with a bootstrap of players (clustered
by player across seasons, because the same players recur every year).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Callable

import numpy as np
import pandas as pd

from baseball.evaluation.arsenal import SWINGS, WHIFFS
from baseball.stats import fit_reliability_constant, shrink

DATA = Path(__file__).resolve().parents[2] / "data"
OUT_DIR = DATA / "edge" / "reliability"
PARAMS_PATH = Path(__file__).with_name("reliability_params.json")

MAIN_TYPES = ("FF", "SI", "FC", "SL", "ST", "CU", "CH", "FS")
NO_PITCH = ("automatic_ball", "automatic_strike")     # pitch-clock violations: no pitch was thrown
BUNTS = ("foul_bunt", "missed_bunt", "bunt_foul_tip")
GRID = (1, 2, 3, 4, 6, 8, 11, 16, 23, 32, 45, 64, 90, 128, 181, 256, 362, 512, 724, 1024, 1448, 2048, 2896)
MIN_ENTITIES = 50        # a point on the curve needs at least this many player-seasons (pooled)
MIN_PAIRS = 100          # a year-to-year estimate needs at least this many matched players (both pairs)
HOME_X, HOME_Y = 125.42, 198.27   # Statcast hit-coordinate origin (home plate)


# ---------------------------------------------------------------- metrics

@dataclass(frozen=True)
class Metric:
    """One metric: per event, a value and whether the event is in the denominator."""
    key: str
    label: str
    role: str                 # "pitcher" or "hitter"
    kind: str                 # "rate" (value is 0/1, shown in %) or "mean" (shown in its unit)
    unit: str                 # the denominator: what one event is
    value: Callable[[pd.DataFrame], np.ndarray]
    den: Callable[[pd.DataFrame], np.ndarray]
    by_type: bool = False     # computed per pitch type (pitchers)
    overall: bool = True      # computed over all pitches (pitchers)
    fmt: str = "%"            # display: "%" (x100), or a unit like "mph"


def _f(col):
    return lambda d: d[col].to_numpy(float)


def _b(col):
    return lambda d: d[col].to_numpy(bool)


def _has(col, also=None):
    if also is None:
        return lambda d: d[col].notna().to_numpy()
    return lambda d: (d[col].notna() & d[also]).to_numpy()


_PITCH = lambda d: np.ones(len(d), bool)  # noqa: E731

PITCHER_METRICS = [
    Metric("whiff", "Whiff per swing", "pitcher", "rate", "swings", _b("whiff"), _b("swing"), True),
    Metric("csw", "CSW (called + swinging strikes)", "pitcher", "rate", "pitches", _b("csw"), _PITCH, True),
    Metric("chase", "Chase (swings at pitches outside the zone)", "pitcher", "rate", "pitches outside the zone", _b("swing"), _b("out_zone"), True),
    Metric("zone", "Zone%", "pitcher", "rate", "pitches with a zone", _b("in_zone"), _b("has_zone"), True),
    Metric("cstr", "Called-strike %", "pitcher", "rate", "pitches", _b("called"), _PITCH, True),
    Metric("xwoba_con", "xwOBA on contact", "pitcher", "mean", "balls in play", _f("xwoba"), _has("xwoba"), True, fmt=".3f"),
    Metric("hard_hit", "Hard-hit % (95+ mph)", "pitcher", "rate", "balls in play", _b("hard"), _has("ls", "bip"), True),
    Metric("barrel", "Barrel %", "pitcher", "rate", "balls in play", _b("barrel"), _has("lsa", "bip"), True),
    Metric("gb", "Ground-ball %", "pitcher", "rate", "balls in play", _b("gb"), _b("has_bbt"), True),
    Metric("rv100", "Run value per 100 pitches", "pitcher", "mean", "pitches", lambda d: -100 * d["rv"].to_numpy(float), _has("rv"), True, fmt="runs"),
    Metric("velo", "Velocity", "pitcher", "mean", "pitches", _f("velo"), _has("velo"), True, overall=False, fmt="mph"),
    Metric("spin", "Spin rate", "pitcher", "mean", "pitches", _f("spin"), _has("spin"), True, overall=False, fmt="rpm"),
    Metric("ivb", "Induced vertical break", "pitcher", "mean", "pitches", _f("ivb"), _has("ivb"), True, overall=False, fmt="in"),
    Metric("hb", "Horizontal break (arm side +)", "pitcher", "mean", "pitches", _f("hb"), _has("hb"), True, overall=False, fmt="in"),
    Metric("arm_angle", "Arm angle", "pitcher", "mean", "pitches", _f("arm"), _has("arm"), True, overall=False, fmt="deg"),
    Metric("extension", "Extension", "pitcher", "mean", "pitches", _f("ext"), _has("ext"), True, overall=False, fmt="ft"),
]

HITTER_METRICS = [
    Metric("swing", "Swing %", "hitter", "rate", "pitches", _b("swing"), _PITCH),
    Metric("chase", "Chase (swing % outside the zone)", "hitter", "rate", "pitches outside the zone", _b("swing"), _b("out_zone")),
    Metric("zone_swing", "Zone swing %", "hitter", "rate", "pitches in the zone", _b("swing"), _b("in_zone")),
    Metric("zone_contact", "Zone contact % (per zone swing)", "hitter", "rate", "swings in the zone", _b("contact"), _b("zone_swing")),
    Metric("whiff", "Whiff per swing", "hitter", "rate", "swings", _b("whiff"), _b("swing")),
    Metric("xwoba_con", "xwOBA on contact", "hitter", "mean", "balls in play", _f("xwoba"), _has("xwoba"), fmt=".3f"),
    Metric("woba", "wOBA", "hitter", "mean", "plate appearances (wOBA denominator)", _f("woba_value"), _b("woba_pa"), fmt=".3f"),
    Metric("hard_hit", "Hard-hit % (95+ mph)", "hitter", "rate", "balls in play", _b("hard"), _has("ls", "bip")),
    Metric("barrel", "Barrel %", "hitter", "rate", "balls in play", _b("barrel"), _has("lsa", "bip")),
    Metric("ev", "Average exit velocity", "hitter", "mean", "balls in play", _f("ls"), _has("ls", "bip"), fmt="mph"),
    Metric("la", "Average launch angle", "hitter", "mean", "balls in play", _f("la"), _has("la", "bip"), fmt="deg"),
    Metric("pull", "Pull %", "hitter", "rate", "balls in play with a spray angle", _f("pulled"), _has("pulled")),
    Metric("bat_speed", "Bat speed", "hitter", "mean", "competitive swings", _f("bat_speed"), _b("comp_bs"), fmt="mph"),
    Metric("swing_length", "Swing length", "hitter", "mean", "competitive swings", _f("swing_length"), _b("comp_sl"), fmt="ft"),
    Metric("fast_swing", "Fast-swing rate (75+ mph)", "hitter", "rate", "competitive swings", _f("fast"), _b("comp_bs")),
    Metric("attack_angle", "Attack angle", "hitter", "mean", "competitive swings", _f("attack_angle"), _b("comp_aa"), fmt="deg"),
    Metric("attack_direction", "Attack direction (pull +)", "hitter", "mean", "competitive swings", _f("attack_dir_pull"), _b("comp_ad"), fmt="deg"),
    Metric("swing_path_tilt", "Swing path tilt", "hitter", "mean", "competitive swings", _f("swing_path_tilt"), _b("comp_tilt"), fmt="deg"),
    Metric("rv100", "Run value per 100 pitches", "hitter", "mean", "pitches", lambda d: 100 * d["rv"].to_numpy(float), _has("rv"), fmt="runs"),
]

METRICS = {("pitcher", m.key): m for m in PITCHER_METRICS} | {("hitter", m.key): m for m in HITTER_METRICS}


def metric_id(role: str, key: str, group: str = "ALL") -> str:
    """The name regress() takes: 'hitter/bat_speed', 'pitcher/whiff', 'pitcher/FF/velo'."""
    return f"{role}/{key}" if group == "ALL" else f"{role}/{group}/{key}"


# ---------------------------------------------------------------- data

def spray_angle(hc_x, hc_y) -> np.ndarray:
    """Horizontal spray angle in degrees from Statcast hit coordinates: 0 = straight away center,
    negative = toward the left-field line, about +/-45 at the foul lines."""
    return np.degrees(np.arctan2(np.asarray(hc_x, float) - HOME_X, HOME_Y - np.asarray(hc_y, float)))


def pulled(angle, stand) -> np.ndarray:
    """1.0 if the ball went to the batter's pull third (more than 15 degrees to his pull side), else 0.0;
    NaN without an angle. A right-handed batter pulls to left field (negative angle)."""
    angle = np.asarray(angle, float)
    pull_side = np.where(np.asarray(stand) == "R", -angle, angle)
    return np.where(np.isnan(angle), np.nan, (pull_side > 15).astype(float))


def competitive_swings(d: pd.DataFrame, col: str = "bat_speed") -> np.ndarray:
    """Statcast's competitive swings: the fastest 90% of a batter's tracked swings in the season, plus any
    swing of 60+ mph with a 90+ mph exit velocity. Bunts are never competitive. Needs a tracked value
    in `col`. (The 90% cut uses the batter's whole season, so it is shared by both halves of a split and
    by both halves of the within-season validation; add_prior_cut() builds the leak-free version.)"""
    tracked = d["bat_speed"].notna() & d[col].notna() & d["swing"] & ~d["description"].isin(BUNTS)
    q10 = d["bat_speed"].where(tracked).groupby([d["batter"], d["season"]]).transform(lambda s: s.quantile(0.10))
    fast_enough = d["bat_speed"] >= q10
    hard_contact = (d["bat_speed"] >= 60) & (d["launch_speed"] >= 90)
    return (tracked & (fast_enough | hard_contact)).to_numpy()


SOURCE_COLUMNS = [
    "game_pk", "game_date", "game_year", "at_bat_number", "pitch_number", "pitcher", "batter", "p_throws", "stand",
    "pitch_type", "description", "type", "zone", "bb_type", "estimated_woba_using_speedangle", "launch_speed",
    "launch_angle", "launch_speed_angle", "hc_x", "hc_y", "delta_run_exp", "woba_value", "woba_denom", "release_speed",
    "release_spin_rate", "pfx_x", "pfx_z", "arm_angle", "release_extension", "bat_speed", "swing_length",
    "attack_angle", "attack_direction", "swing_path_tilt",
]
KEEP = [
    "game_pk", "game_date", "season", "at_bat_number", "pitch_number", "pitcher", "batter", "stand", "pitch_type",
    "description", "swing", "whiff", "called", "csw", "has_zone", "in_zone", "out_zone", "contact", "zone_swing", "bip",
    "xwoba", "ls", "la", "lsa", "hard", "barrel", "gb", "has_bbt", "pulled", "rv", "woba_value", "woba_pa", "velo", "spin",
    "ivb", "hb", "arm", "ext", "bat_speed", "swing_length", "attack_angle", "attack_dir_pull", "swing_path_tilt", "fast",
    "comp_bs", "comp_sl", "comp_aa", "comp_ad", "comp_tilt", "tracked_swing", "hard_contact_swing",
]
PHYSICS = ("velo", "spin", "ivb", "hb", "arm_angle", "extension")   # two-level noise model (see day_components)


def prepare(p: pd.DataFrame) -> pd.DataFrame:
    """Flags once, on every pitch (regular season frames from familiarity.load_seq). Returns only the
    columns the atlas uses, floats as float32 (a three-season frame fits in memory)."""
    d = p[~p["description"].isin(NO_PITCH)].copy()
    d["season"] = d["game_year"].astype(int)
    d["swing"] = d["description"].isin(SWINGS)
    d["whiff"] = d["description"].isin(WHIFFS)
    d["called"] = d["description"].eq("called_strike")
    d["csw"] = d["called"] | d["whiff"]
    d["has_zone"] = d["zone"].notna()
    d["in_zone"] = d["zone"].between(1, 9)
    d["out_zone"] = d["has_zone"] & ~d["in_zone"]
    d["contact"] = d["swing"] & ~d["whiff"]
    d["zone_swing"] = d["swing"] & d["in_zone"]
    d["bip"] = d["type"].eq("X")
    d["xwoba"] = d["estimated_woba_using_speedangle"].where(d["bip"])
    d["ls"] = d["launch_speed"].where(d["bip"])
    d["la"] = d["launch_angle"].where(d["bip"])
    d["lsa"] = d["launch_speed_angle"].where(d["bip"])
    d["bbt"] = d["bb_type"].where(d["bip"])
    d["hard"] = d["ls"].ge(95)
    d["barrel"] = d["lsa"].eq(6)
    d["gb"] = d["bbt"].eq("ground_ball")
    d["has_bbt"] = d["bbt"].notna()
    d["pulled"] = pulled(np.where(d["bip"], spray_angle(d["hc_x"], d["hc_y"]), np.nan), d["stand"])
    d["rv"] = d["delta_run_exp"]
    d["woba_pa"] = d["woba_denom"].fillna(0) > 0
    d["velo"] = d["release_speed"]
    d["spin"] = d["release_spin_rate"]
    d["ivb"] = d["pfx_z"] * 12
    d["hb"] = np.where(d["p_throws"].eq("R"), -d["pfx_x"], d["pfx_x"]) * 12
    d["arm"] = d["arm_angle"]
    d["ext"] = d["release_extension"]
    # Bat tracking: competitive swings (per metric, since a swing can carry bat speed but not tilt)
    d["comp_bs"] = competitive_swings(d, "bat_speed")
    d["comp_sl"] = d["comp_bs"] & d["swing_length"].notna()
    d["comp_aa"] = d["comp_bs"] & d["attack_angle"].notna()
    d["comp_ad"] = d["comp_bs"] & d["attack_direction"].notna()
    d["comp_tilt"] = d["comp_bs"] & d["swing_path_tilt"].notna()
    d["fast"] = (d["bat_speed"] >= 75).astype(float)
    d["tracked_swing"] = d["bat_speed"].notna() & d["swing"] & ~d["description"].isin(BUNTS)
    d["hard_contact_swing"] = (d["bat_speed"] >= 60) & (d["launch_speed"] >= 90)
    # Statcast's attack direction is batter-relative with pull negative for both sides (checked on 2025:
    # it correlates with spray angle +0.32 for righties and -0.29 for lefties), so flip it: pull +.
    d["attack_dir_pull"] = -d["attack_direction"]
    d = d[KEEP].reset_index(drop=True)
    for c in d.columns:
        if d[c].dtype == "float64":
            d[c] = d[c].astype("float32")
    return d


def load(seasons: list[int]) -> pd.DataFrame:
    """Prepared pitches of the given regular seasons, read from the sequence copy (data/seq/)."""
    from baseball.edge.familiarity import seq_parts

    frames = []
    for s in seasons:
        parts = seq_parts(s)
        if not parts:
            raise FileNotFoundError(f"No sequence data for {s} in data/seq/ (bb seq {s} writes it on the Mac).")
        frames.append(prepare(pd.concat([pd.read_parquet(x, columns=SOURCE_COLUMNS) for x in parts], ignore_index=True)))
    return pd.concat(frames, ignore_index=True)


def add_prior_cut(d: pd.DataFrame) -> pd.DataFrame:
    """comp_bs_prior: competitive swings with the fastest-90% cut taken from the batter's PREVIOUS season, so
    nothing in a season's own swings decides which of them count (no leak between halves). Batters without a
    previous season in d get no competitive swings under this rule. Also comp_bs_known: Statcast's rule,
    restricted to the same batter-seasons, for a like-for-like comparison."""
    d = d.copy()
    q10 = d.loc[d["tracked_swing"]].groupby(["batter", "season"])["bat_speed"].quantile(0.10)
    prev = q10.rename("q10_prior").reset_index()
    prev["season"] += 1
    cut = d[["batter", "season"]].merge(prev, on=["batter", "season"], how="left")["q10_prior"].to_numpy()
    has = np.isfinite(cut)
    bs = d["bat_speed"].to_numpy(float)
    with np.errstate(invalid="ignore"):
        d["comp_bs_prior"] = d["tracked_swing"].to_numpy() & has & ((bs >= cut) | d["hard_contact_swing"].to_numpy())
    d["comp_bs_known"] = d["comp_bs"].to_numpy() & has
    return d


# ---------------------------------------------------------------- families: who is split, and how

@dataclass
class Family:
    """The events of one kind of entity, sorted so each (entity, unit) row is contiguous.

    entity = player-season (hitters, pitchers overall) or pitcher-season-pitch type.
    unit   = what is assigned to a half: a game (the default) or a single event (for comparison).
    owner  = whose units are split: the player-season. A pitcher's games go to the same half for all
             of his pitch types, so every type is split the same way.
    """
    name: str
    role: str
    events: pd.DataFrame          # sorted
    event_row: np.ndarray         # row id per event
    row_entity: np.ndarray
    row_og: np.ndarray            # owner-unit id per row
    og_owner: np.ndarray
    n_owner: int
    entity_season: np.ndarray
    entity_player: np.ndarray
    entity_group: np.ndarray      # "ALL" or the pitch type
    row_date: np.ndarray          # game date of each row (for the calendar halves: drift and validation)

    @property
    def n_entity(self) -> int:
        return len(self.entity_season)

    @property
    def n_row(self) -> int:
        return len(self.row_entity)


def _change(cols: list[np.ndarray]) -> np.ndarray:
    ch = np.zeros(len(cols[0]), bool)
    ch[0] = True
    for c in cols:
        ch[1:] |= c[1:] != c[:-1]
    return ch


def build_family(d: pd.DataFrame, role: str, by_type: bool = False, unit: str = "game") -> Family:
    """Group events into entities and split units. d is a prepared frame."""
    player = "pitcher" if role == "pitcher" else "batter"
    e = d
    if by_type:
        e = e[e["pitch_type"].isin(MAIN_TYPES)]
    order = np.lexsort([e[c].to_numpy() for c in ("pitch_number", "at_bat_number", "game_pk", "game_date")]
                       + ([e["pitch_type"].to_numpy()] if by_type else []) + [e["season"].to_numpy(), e[player].to_numpy()])
    e = e.iloc[order].reset_index(drop=True)
    e["_group"] = e["pitch_type"].to_numpy() if by_type else "ALL"
    pl, se, gr = e[player].to_numpy(), e["season"].to_numpy(), e["_group"].to_numpy()
    u = e["game_pk"].to_numpy() if unit == "game" else np.arange(len(e))
    ent_change = _change([pl, se, gr])
    entity = np.cumsum(ent_change) - 1
    row_change = ent_change | _change([u])
    row = np.cumsum(row_change) - 1
    first = np.flatnonzero(row_change)
    row_entity = entity[first]
    owner = np.cumsum(_change([pl, se])) - 1
    og_key = owner[first].astype(np.int64) * (len(e) + 1) + pd.factorize(u[first])[0]
    row_og, og_uniques = pd.factorize(og_key)
    og_owner = (og_uniques // (len(e) + 1)).astype(np.int64)
    ef = np.flatnonzero(ent_change)
    row_date = pd.to_datetime(e["game_date"].to_numpy()[first]).to_numpy()
    return Family(name=f"{role}{'-type' if by_type else ''}{'' if unit == 'game' else '-event'}", role=role,
                  events=e, event_row=row, row_entity=row_entity, row_og=row_og.astype(np.int64), og_owner=og_owner,
                  n_owner=int(owner.max()) + 1, entity_season=se[ef], entity_player=pl[ef], entity_group=gr[ef],
                  row_date=row_date)


@dataclass
class Arrays:
    """One metric on one family: per row the denominator count c and value sum s, plus the events'
    running value sum so the first k events of any row can be added exactly."""
    c: np.ndarray
    s: np.ndarray
    off: np.ndarray
    cs: np.ndarray
    ss: np.ndarray | None = None      # sum of squared values per row (within-game spread, two-level model)


def metric_arrays(fam: Family, m: Metric) -> Arrays:
    den = np.array(m.den(fam.events), bool)
    val = np.asarray(m.value(fam.events), float)
    den &= np.isfinite(val)
    v, r = val[den], fam.event_row[den]
    c = np.bincount(r, minlength=fam.n_row).astype(np.int64)
    s = np.bincount(r, weights=v, minlength=fam.n_row)
    ss = np.bincount(r, weights=v * v, minlength=fam.n_row)
    return Arrays(c=c, s=s, off=np.cumsum(c) - c, cs=np.r_[0.0, np.cumsum(v)], ss=ss)


@dataclass
class Split:
    order: np.ndarray        # rows in (entity, half, random unit order)
    seg: np.ndarray          # entity * 2 + half, per ordered row
    first: np.ndarray        # first ordered position of each present segment
    length: np.ndarray


def random_split(fam: Family, rng: np.random.Generator) -> Split:
    """Shuffle each owner's units, deal them alternately into two halves (a coin decides which half gets
    the first), and order every entity's rows by half, then by the shuffled order."""
    n_og = len(fam.og_owner)
    key = rng.random(n_og)
    o = np.lexsort((key, fam.og_owner))
    own = fam.og_owner[o]
    starts = np.flatnonzero(_change([own]))
    rank = np.arange(n_og) - np.repeat(starts, np.diff(np.r_[starts, n_og]))
    flip = rng.integers(0, 2, fam.n_owner)
    half = np.empty(n_og, np.int64)
    half[o] = (rank + flip[own]) % 2
    rh, rk = half[fam.row_og], key[fam.row_og]
    order = np.lexsort((rk, rh, fam.row_entity))
    seg = fam.row_entity[order] * 2 + rh[order]
    first = np.flatnonzero(_change([seg]))
    return Split(order=order, seg=seg, first=first, length=np.diff(np.r_[first, len(seg)]))


def half_means(a: Arrays, sp: Split, n_entity: int, grid) -> np.ndarray:
    """Mean of exactly n events in each half, for every n in grid: shape (len(grid), n_entity, 2).

    Whole units are added in shuffled order until the next would pass n; that unit contributes its first
    k events (in game order) so the half holds exactly n. NaN where a half has fewer than n events.
    """
    c, s, off = a.c[sp.order], a.s[sp.order], a.off[sp.order]
    t = np.cumsum(c)
    base = t[sp.first] - c[sp.first]
    cum = t - np.repeat(base, sp.length)
    prev = cum - c
    n_seg = 2 * n_entity
    tot = np.bincount(sp.seg, weights=c, minlength=n_seg)
    out = np.full((len(grid), n_seg), np.nan)
    for i, n in enumerate(grid):
        ok = tot >= n
        if not ok.any():
            continue
        contrib = np.where(cum <= n, s, 0.0)
        b = np.flatnonzero((prev < n) & (cum > n))
        k = n - prev[b]
        contrib[b] = a.cs[off[b] + k] - a.cs[off[b]]
        sums = np.bincount(sp.seg, weights=contrib, minlength=n_seg)
        out[i, ok] = sums[ok] / n
    return out.reshape(len(grid), n_entity, 2)


# ---------------------------------------------------------------- reliability from split halves

def within_sums(means: np.ndarray, cell: np.ndarray, n_cell: int, W: np.ndarray) -> np.ndarray:
    """Sufficient sums per (weight row, n, cell) for the double-entry (intraclass) split-half correlation.

    means: (len(grid), n_entity, 2) from half_means. cell = group x season per entity. W: (rows, n_entity)
    weights, row 0 all ones (the estimate) and the rest bootstrap draws of players. Returns
    (rows, len(grid), n_cell, 4): N = sum w, Sa = sum w(a + b), Sq = sum w(a^2 + b^2), Sab = sum w a b.
    The sums are linear in w, so every bootstrap draw costs one matrix product. Centering comes later.
    """
    g, e = means.shape[0], means.shape[1]
    a, b = means[..., 0], means[..., 1]
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = np.where(ok, a, 0.0), np.where(ok, b, 0.0)
    X = np.stack([ok.astype(float), a + b, a * a + b * b, a * b], -1).transpose(1, 0, 2).reshape(e, g * 4)
    out = np.zeros((W.shape[0], g, n_cell, 4))
    for c in range(n_cell):
        idx = np.flatnonzero(cell == c)
        if len(idx):
            out[:, :, c, :] = (W[:, idx] @ X[idx]).reshape(W.shape[0], g, 4)
    return out


def centered(sums: np.ndarray):
    """(N, C, V) from within_sums, centered per cell: C = covariance of the halves x N (true-talent
    variance), V = double-entry variance x N. r = C / V. Sum C and V over cells to pool seasons."""
    n, sa, sq, sab = sums[..., 0], sums[..., 1], sums[..., 2], sums[..., 3]
    with np.errstate(invalid="ignore", divide="ignore"):
        nm2 = np.where(n > 0, sa * sa / (4 * n), 0.0)
    return n, sab - nm2, sq / 2 - nm2


def split_half_r(a: np.ndarray, b: np.ndarray) -> float:
    """Double-entry (intraclass) correlation of two equal-size halves: 2 cov / (var a + var b) with a
    common mean. Halves are exchangeable, so this uses both orderings (the plain Pearson r of a and b
    would depend on which half is called A)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    m = (a.mean() + b.mean()) / 2
    return float(np.mean((a - m) * (b - m)) / np.mean(((a - m) ** 2 + (b - m) ** 2) / 2))


@dataclass
class Pairs:
    """Entities matched across consecutive seasons (same player, same group)."""
    e1: np.ndarray
    e2: np.ndarray
    cell: np.ndarray        # group x pair
    labels: list            # (group, (s1, s2)) per cell


def season_pairs(fam: Family, groups: list[str], seasons: list[int]) -> Pairs:
    key = pd.DataFrame({"player": fam.entity_player, "group": fam.entity_group, "season": fam.entity_season,
                        "e": np.arange(fam.n_entity)})
    pairs = [(a, b) for a, b in zip(seasons[:-1], seasons[1:]) if b == a + 1]
    e1, e2, cells, labels = [], [], [], []
    for gi, g in enumerate(groups):
        for pi, (s1, s2) in enumerate(pairs):
            x = key[(key["group"] == g) & (key["season"] == s1)].merge(
                key[(key["group"] == g) & (key["season"] == s2)], on=["player", "group"])
            e1.append(x["e_x"].to_numpy()); e2.append(x["e_y"].to_numpy())
            cells.append(np.full(len(x), gi * len(pairs) + pi)); labels.append((g, (s1, s2)))
    cat = lambda v: np.concatenate(v) if v else np.array([], np.int64)  # noqa: E731
    return Pairs(cat(e1).astype(np.int64), cat(e2).astype(np.int64), cat(cells).astype(np.int64), labels)


def y2y_sums(means: np.ndarray, pr: Pairs, n_cell: int, W: np.ndarray) -> np.ndarray:
    """Raw sums per (weight row, n, cell = group x season pair) for year-to-year comparisons at equal n:
    N, S1 = sum w(a1 + b1), S2, Sab1 = sum w a1 b1, Sab2, S12 = sum w (a1 + b1)(a2 + b2), Sq1, Sq2.
    W: (rows, n_pairs) weights per matched player. y2y_centered() turns them into covariances."""
    g, p = means.shape[0], len(pr.e1)
    a1, b1 = means[:, pr.e1, 0], means[:, pr.e1, 1]
    a2, b2 = means[:, pr.e2, 0], means[:, pr.e2, 1]
    ok = np.isfinite(a1) & np.isfinite(b1) & np.isfinite(a2) & np.isfinite(b2)
    a1, b1, a2, b2 = (np.where(ok, x, 0.0) for x in (a1, b1, a2, b2))
    X = np.stack([ok.astype(float), a1 + b1, a2 + b2, a1 * b1, a2 * b2, (a1 + b1) * (a2 + b2),
                  a1 * a1 + b1 * b1, a2 * a2 + b2 * b2], -1).transpose(1, 0, 2).reshape(p, g * 8)
    out = np.zeros((W.shape[0], g, n_cell, 8))
    for c in range(n_cell):
        idx = np.flatnonzero(pr.cell == c)
        if len(idx):
            out[:, :, c, :] = (W[:, idx] @ X[idx]).reshape(W.shape[0], g, 8)
    return out


def y2y_centered(raw: np.ndarray):
    """(N, C11, C22, C12, V1, V2) from y2y_sums, centered within each cell (x N). C11, C22: within-season
    half covariances; C12: covariance of a season-1 half with a season-2 half (all four pairings, same n)."""
    n, s1, s2, sab1, sab2, s12, sq1, sq2 = (raw[..., k] for k in range(8))
    with np.errstate(invalid="ignore", divide="ignore"):
        m1, m2 = np.where(n > 0, s1 / (2 * n), 0.0), np.where(n > 0, s2 / (2 * n), 0.0)
    return n, sab1 - n * m1 * m1, sab2 - n * m2 * m2, s12 / 4 - n * m1 * m2, sq1 / 2 - n * m1 * m1, sq2 / 2 - n * m2 * m2


@dataclass
class Job:
    """Everything one family and its metrics need across replicates. Sums are accumulated over splits:
    row 0 with every player once (the estimate), rows 1..B with bootstrap draws of players."""
    fam: Family
    metrics: list
    arrays: dict
    grids: dict
    groups: list
    seasons: list
    cell: np.ndarray
    pairs: Pairs
    within: dict            # key -> array (B + 1, grid, groups*seasons, 4)
    y2y: dict               # key -> array (B + 1, grid, groups*pairs, 8)
    per_unit: dict          # key -> median denominator events per unit (game) with any, by group
    reps: int = 0           # splits accumulated so far


def _job(fam: Family, metrics: list, seasons: list[int], boot: int = 100, y2y: bool = True) -> Job:
    groups = sorted(set(fam.entity_group))
    gi = {g: i for i, g in enumerate(groups)}
    si = {s: i for i, s in enumerate(seasons)}
    cell = np.array([gi[g] * len(seasons) + si[s] for g, s in zip(fam.entity_group, fam.entity_season)], np.int64)
    pairs = season_pairs(fam, groups, seasons) if y2y else Pairs(np.array([], np.int64), np.array([], np.int64), np.array([], np.int64), [])
    arrays, grids, within, yy, per_unit = {}, {}, {}, {}, {}
    for m in metrics:
        a = metric_arrays(fam, m)
        tot = np.bincount(fam.row_entity, weights=a.c, minlength=fam.n_entity)
        grid = [n for n in GRID if (tot >= 2 * n).sum() >= MIN_ENTITIES]
        if not grid:
            continue
        arrays[m.key], grids[m.key] = a, grid
        within[m.key] = np.zeros((boot + 1, len(grid), len(groups) * len(seasons), 4))
        yy[m.key] = np.zeros((boot + 1, len(grid), max(len(pairs.labels), 1), 8))
        rows_g = fam.entity_group[fam.row_entity]
        per_unit[m.key] = {g: float(np.median(a.c[(rows_g == g) & (a.c > 0)])) if ((rows_g == g) & (a.c > 0)).any() else np.nan
                           for g in groups}
    fam.events = None          # the arrays hold everything the splits need; free the frame
    return Job(fam, [m for m in metrics if m.key in arrays], arrays, grids, groups, seasons, cell, pairs, within, yy, per_unit)


def run_splits(jobs: list[Job], reps: int, seed: int = 2026, log=print) -> None:
    """Accumulate every job's within and y2y sums over `reps` random game splits.

    Uncertainty: B bootstrap draws of players (multinomial counts per player id, shared across seasons,
    so a player's seasons stay together, and across families of the same role) are fixed up front, and
    every split is scored under every draw. Each draw's estimate is therefore pooled over all splits, and
    the spread across draws reflects which players we happened to observe, not which split was drawn.
    (Checked on fictional players with known truth: see tests/test_reliability.py.)
    """
    rng = np.random.default_rng(seed)
    B = next(iter(jobs[0].within.values())).shape[0] - 1 if jobs and jobs[0].within else 0
    weights = {}
    for role in {j.fam.role for j in jobs}:
        players = np.unique(np.concatenate([j.fam.entity_player for j in jobs if j.fam.role == role]))
        draws = rng.multinomial(len(players), np.full(len(players), 1 / len(players)), size=B).astype(float)
        weights[role] = (players, np.vstack([np.ones(len(players)), draws]))
    W_ent = {}
    for j in jobs:
        players, Wr = weights[j.fam.role]
        W_ent[id(j)] = Wr[:, np.searchsorted(players, j.fam.entity_player)]
    t0 = time.time()
    for r in range(reps):
        for j in jobs:
            sp = random_split(j.fam, rng)
            W = W_ent[id(j)]
            n_cell = len(j.groups) * len(j.seasons)
            for m in j.metrics:
                means = half_means(j.arrays[m.key], sp, j.fam.n_entity, j.grids[m.key])
                j.within[m.key] += within_sums(means, j.cell, n_cell, W)
                if len(j.pairs.e1):
                    j.y2y[m.key] += y2y_sums(means, j.pairs, len(j.pairs.labels), W[:, j.pairs.e1])
            j.reps += 1
        if log and (r + 1) % max(1, reps // 10) == 0:
            log(f"  split {r + 1}/{reps} ({time.time() - t0:.0f}s)")


def save_sums(jobs: list[Job], path: Path) -> None:
    """The split sums are the expensive part (about 15 minutes); keep them so summaries can be refit."""
    import pickle

    path.write_bytes(pickle.dumps([{"name": j.fam.name, "within": j.within, "y2y": j.y2y,
                                    "reps": j.reps} for j in jobs]))


def load_sums(jobs: list[Job], path: Path) -> None:
    import pickle

    saved = {x["name"]: x for x in pickle.loads(path.read_bytes())}
    for j in jobs:
        x = saved[j.fam.name]
        j.within, j.y2y, j.reps = x["within"], x["y2y"], x["reps"]


# ---------------------------------------------------------------- summaries

def _q(x, q):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(np.quantile(x, q)) if len(x) else np.nan


def _sd(x) -> float:
    """Spread of the bootstrap draws (the standard error of the estimate)."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(np.std(x, ddof=1)) if len(x) >= 3 else np.nan


def _ratio(num, den):
    with np.errstate(invalid="ignore", divide="ignore"):
        return num / den


def summarize(job: Job, seasons: list[int] | None = None, pairs: list[tuple] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Curve (one row per metric x group x n) and parameters (one row per metric x group).

    seasons / pairs restrict which seasons feed the within-season fit and which season pairs feed rho
    (the validation fits on 2024-25 only). Intervals are 95%, normal on the scale noted (log for M),
    with standard errors from the spread of the bootstrap draws.
    """
    seasons = seasons or job.seasons
    s_idx = [job.seasons.index(s) for s in seasons]
    curve_rows, param_rows = [], []
    z = 1.959964
    reps = max(job.reps, 1)
    for m in job.metrics:
        grid = np.array(job.grids[m.key], float)
        for gi, g in enumerate(job.groups):
            cells = [gi * len(job.seasons) + k for k in s_idx]
            n, c, v = centered(job.within[m.key][:, :, cells, :])     # rows, grid, cells
            N, C, V = n.sum(-1), c.sum(-1), v.sum(-1)                 # pool seasons -> rows, grid
            n_ent = N[0] / reps                                       # player-seasons per point
            keep = n_ent >= MIN_ENTITIES
            if keep.sum() < 2:
                continue
            r_all = _ratio(C, V)
            r_point, r_b = r_all[0], r_all[1:]
            tau2_n = _ratio(C[0], N[0])
            kidx = np.flatnonzero(keep)
            gk, rp, nk = grid[keep], r_point[keep], n_ent[keep]
            # Fit in the multi-game regime: halves of at least one typical game's worth of events. Below
            # that a half sits inside one game and the curve has a different shape (the day's conditions
            # don't average out), so those points are kept only as a diagnostic.
            per_game = job.per_unit[m.key].get(g, np.nan)
            fit = gk >= max(per_game, 1.0) if np.isfinite(per_game) else np.ones(len(gk), bool)
            if fit.sum() < 3:
                fit = np.ones(len(gk), bool)
            fidx = kidx[fit]
            M = fit_reliability_constant(gk[fit], rp[fit], nk[fit])
            Mb = np.array([fit_reliability_constant(gk[fit], r_b[b, fidx], nk[fit]) for b in range(len(r_b))])
            se_logM = _sd(np.log(Mb))
            # Noise variance of one event, measured directly: at each n, (variance of a half - covariance of
            # the halves) is the noise in an n-event mean, times n is the noise per event. It is the stable
            # quantity (Finding 3 of the report); talent spread tau^2 = sigma2 / M then makes the model
            # internally consistent: r(n) = tau^2 / (tau^2 + sigma2 / n) = n / (n + M).
            sigma2_n = _ratio(V[0] - C[0], N[0]) * grid
            sigma2 = float(np.average(sigma2_n[fidx], weights=nk[fit]))
            tau2 = sigma2 / M if M > 0 else np.nan
            tau2_cov = float(np.average(np.maximum(tau2_n[fidx], 0), weights=nk[fit]))
            # Diagnostics: M inside one game, and M among full-time players (the three largest n)
            inside = ~(gk >= max(per_game, 1.0)) if np.isfinite(per_game) else np.zeros(len(gk), bool)
            M_small = fit_reliability_constant(gk[inside], rp[inside], nk[inside]) if inside.sum() >= 2 else np.nan
            top = np.flatnonzero(fit)[-3:]
            M_large = fit_reliability_constant(gk[top], rp[top], nk[top]) if len(top) >= 2 else np.nan
            tau2_top = float(np.average(np.maximum(tau2_n[kidx[top]], 0), weights=nk[top])) if len(top) else np.nan
            # Where the observed curve crosses 0.5 and 0.7 (log-n interpolation), if it does
            cross = {}
            for t in (0.5, 0.7):
                above = np.flatnonzero(rp >= t)
                if len(above) == 0:
                    cross[t] = np.nan
                elif above[0] == 0:
                    cross[t] = float(gk[0])
                else:
                    i = above[0]
                    x0, x1, y0, y1 = np.log(gk[i - 1]), np.log(gk[i]), rp[i - 1], rp[i]
                    cross[t] = float(np.exp(x0 + (t - y0) * (x1 - x0) / (y1 - y0)))
            for i in kidx:
                se = _sd(r_b[:, i])
                curve_rows.append({"metric": metric_id(m.role, m.key, g), "role": m.role, "key": m.key, "group": g,
                                   "n": int(grid[i]), "r": r_point[i], "r_lo": r_point[i] - z * se, "r_hi": r_point[i] + z * se,
                                   "entities": float(n_ent[i]), "r_model": grid[i] / (grid[i] + M), "tau2": tau2_n[i], "sigma2_event": sigma2_n[i],
                                   "in_fit": bool(i in set(fidx))})
            # Year to year: at every n with enough matched players and signal, then keep the most precise
            yy = {}
            if len(job.pairs.labels):
                want = [pi for pi, (gg, pp) in enumerate(job.pairs.labels) if gg == g and (pairs is None or pp in pairs)]
                if want:
                    Np, C11, C22, C12, V1, V2 = (x.sum(-1) for x in y2y_centered(job.y2y[m.key][:, :, want, :]))  # rows, grid
                    npairs = Np[0] / reps
                    rw = _ratio(C11 + C22, V1 + V2)
                    rho_all = _ratio(C12, np.sqrt(np.maximum(C11 * C22, 0)))
                    ryy_all = _ratio(C12, np.sqrt(np.maximum(V1 * V2, 0)))
                    cand = [i for i in range(len(grid)) if npairs[i] >= MIN_PAIRS and rw[0, i] >= 0.2]
                    ses = {i: _sd(rho_all[1:, i]) for i in cand}
                    cand = [i for i in cand if np.isfinite(ses[i])]
                    if cand:
                        i = min(cand, key=lambda k: ses[k])   # the most precise sample size
                        se_r, se_ryy = ses[i], _sd(ryy_all[1:, i])
                        rho_pt, ryy_pt = float(rho_all[0, i]), float(ryy_all[0, i])
                        yy = {"n_match": int(grid[i]), "pairs": float(npairs[i]), "r_within_match": float(rw[0, i]),
                              "r_y2y": ryy_pt, "r_y2y_lo": ryy_pt - z * se_ryy, "r_y2y_hi": ryy_pt + z * se_ryy,
                              "rho": rho_pt, "rho_se": se_r, "rho_lo": rho_pt - z * se_r, "rho_hi": rho_pt + z * se_r,
                              "rho_range_n": f"{min(rho_all[0, k] for k in cand):.2f} to {max(rho_all[0, k] for k in cand):.2f}",
                              "rho_n_tested": len(cand)}
                        for pi_ in want:                       # each season pair on its own, same n
                            gg, pp = job.pairs.labels[pi_]
                            q = [x[0, i] for x in y2y_centered(job.y2y[m.key][:, :, [pi_], :].sum(2))]
                            yy[f"rho_{pp[0]}_{pp[1]}"] = _ratio(q[3], np.sqrt(q[1] * q[2]))
                            yy[f"r_y2y_{pp[0]}_{pp[1]}"] = _ratio(q[3], np.sqrt(q[4] * q[5]))
                        # What regress() uses next season: a correlation can't pass 1; an imprecise one isn't used
                        yy["rho_use"] = float(np.clip(rho_pt, 0, 1)) if se_r <= 0.15 else np.nan
            n70 = 7 * M / 3
            param_rows.append({"metric": metric_id(m.role, m.key, g), "role": m.role, "key": m.key, "group": g,
                               "label": m.label, "kind": m.kind, "unit": m.unit, "fmt": m.fmt,
                               "M": M, "M_lo": M * np.exp(-z * se_logM), "M_hi": M * np.exp(z * se_logM), "n70": n70,
                               "n_max": int(gk[-1]), "n70_observed": bool(n70 <= gk[-1]), "r_at_max": float(rp[-1]),
                               "n50_curve": cross[0.5], "n70_curve": cross[0.7], "n_fit_min": int(gk[fit][0]),
                               "M_in_game": M_small, "M_fulltime": M_large, "n_fulltime": int(gk[top][0]) if len(top) else np.nan,
                               "tau": float(np.sqrt(tau2)), "tau_cov": float(np.sqrt(tau2_cov)),
                               "tau_fulltime": float(np.sqrt(tau2_top)) if np.isfinite(tau2_top) else np.nan,
                               "sigma2": sigma2, "sigma2_small_n": float(sigma2_n[fidx][0]), "sigma2_large_n": float(sigma2_n[fidx][-1]),
                               "per_game": per_game,
                               "entities_at_M": float(np.interp(np.log(max(M, 1)), np.log(gk), nk)),
                               "seasons": ",".join(map(str, seasons)), **yy})
    return pd.DataFrame(curve_rows), pd.DataFrame(param_rows)


# ---------------------------------------------------------------- in-season drift

def season_halves(fam: Family, seasons: list[int]) -> np.ndarray:
    """0 / 1 per row: on or before / after the league's median pitch date of that season; -1 otherwise.
    The same calendar split the within-season validation uses."""
    size = np.bincount(fam.event_row, minlength=fam.n_row)          # pitches per row
    row_season = fam.entity_season[fam.row_entity]
    half = np.full(fam.n_row, -1, np.int64)
    for s in seasons:
        t = row_season == s
        dates, wts = fam.row_date[t], size[t]
        o = np.argsort(dates)
        cutoff = dates[o][np.searchsorted(np.cumsum(wts[o]), wts.sum() / 2)]
        half[t] = (fam.row_date[t] > cutoff).astype(np.int64)
    return half


def drift(fam: Family, a: Arrays, half: np.ndarray, reps: int = 40, min_games: int = 4, boot: int = 200,
          seed: int = 0) -> pd.DataFrame:
    """In-season drift per group: the spread of players' true change from the first calendar half of a
    season to the second, var(T2 - T1), net of sampling noise and of the league-wide shift.

    For each player-season with at least min_games games in each half:
      d     = (second-half mean) - (first-half mean)
      noise = each half's sampling variance, measured inside that half by dealing its games at random
              into X and Y: (mean_X - mean_Y)^2 n_X n_Y / (n_X + n_Y)^2 (averaged over `reps` deals). Games
              are the unit, so day-to-day swings count as noise, as they should.
      drift variance = mean(d^2 - noise_1 - noise_2) - mean(d)^2.
    Standard error from a bootstrap of player-seasons. Rows with half = -1 are ignored.
    """
    rng = np.random.default_rng(seed)
    use = (half >= 0) & (a.c > 0)
    rows = np.flatnonzero(use)
    ent, h = fam.row_entity[rows], half[rows]
    key = ent * 2 + h
    nseg = 2 * fam.n_entity
    C = np.bincount(key, weights=a.c[rows], minlength=nseg)
    S = np.bincount(key, weights=a.s[rows], minlength=nseg)
    G = np.bincount(key, minlength=nseg)
    noise = np.zeros(nseg)
    for _ in range(reps):
        r = rng.random(len(rows))
        o = np.lexsort((r, key))
        k = key[o]
        starts = np.flatnonzero(_change([k]))
        rank = np.arange(len(k)) - np.repeat(starts, np.diff(np.r_[starts, len(k)]))
        x = np.empty(len(rows), bool)
        x[o] = rank % 2 == 0
        cx = np.bincount(key[x], weights=a.c[rows][x], minlength=nseg)
        sx = np.bincount(key[x], weights=a.s[rows][x], minlength=nseg)
        cy, sy = C - cx, S - sx
        with np.errstate(invalid="ignore", divide="ignore"):
            noise += (sx / cx - sy / cy) ** 2 * cx * cy / (cx + cy) ** 2
    noise /= reps
    G2, C2, S2, N2 = G.reshape(-1, 2), C.reshape(-1, 2), S.reshape(-1, 2), noise.reshape(-1, 2)
    ok = (G2 >= min_games).all(1)
    rows_out = []
    for g in sorted(set(fam.entity_group)):
        e = np.flatnonzero(ok & (fam.entity_group == g))
        if len(e) < 30:
            continue
        d = S2[e, 1] / C2[e, 1] - S2[e, 0] / C2[e, 0]
        q = d * d - N2[e, 0] - N2[e, 1]
        est = lambda idx: float(np.mean(q[idx]) - np.mean(d[idx]) ** 2)  # noqa: E731
        point = est(np.arange(len(e)))
        draws = np.array([est(rng.integers(0, len(e), len(e))) for _ in range(boot)])
        se = float(np.std(draws, ddof=1))
        rows_out.append({"group": g, "drift_var": point, "drift_var_se": se, "drift_sd": float(np.sqrt(max(point, 0))),
                         "drift_sd_lo": float(np.sqrt(max(point - 1.959964 * se, 0))),
                         "drift_sd_hi": float(np.sqrt(max(point + 1.959964 * se, 0))),
                         "drift_players": int(len(e)), "league_shift_mean": float(np.mean(d)),
                         "raw_change_sd": float(np.std(d, ddof=1))})
    return pd.DataFrame(rows_out)


def drift_table(job: Job, seasons: list[int], reps: int = 40, seed: int = 0) -> pd.DataFrame:
    half = season_halves(job.fam, seasons)
    out = []
    for m in job.metrics:
        t = drift(job.fam, job.arrays[m.key], half, reps=reps, seed=seed)
        if len(t):
            t.insert(0, "metric", [metric_id(m.role, m.key, g) for g in t["group"]])
            out.append(t.drop(columns="group"))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def with_drift(params: pd.DataFrame, drift_tab: pd.DataFrame) -> pd.DataFrame:
    """Merge drift into the parameters. Drift is used (drift_sd_use) only when its 95% interval excludes 0,
    the report's own evidence standard; otherwise rest-of-season intervals aren't widened. drift_over_tau
    uses the talent spread measured directly by the half covariances (tau_cov)."""
    p = params.drop(columns=[c for c in drift_tab.columns if c != "metric" and c in params]
                    + [c for c in ("drift_sig", "drift_sd_use", "drift_var_use", "drift_over_tau") if c in params], errors="ignore")
    p = p.merge(drift_tab, on="metric", how="left")
    p["drift_sig"] = p["drift_sd_lo"].fillna(0) > 0
    p["drift_sd_use"] = np.where(p["drift_sig"], p["drift_sd"], 0.0)
    p["drift_var_use"] = p["drift_sd_use"] ** 2
    p["drift_over_tau"] = p["drift_sd"] / p["tau_cov"]
    return p


# ---------------------------------------------------------------- pitch physics: a two-level noise model

def day_components(fam: Family, a: Arrays, seasons: list[int] | None = None, min_games: int = 3) -> pd.DataFrame:
    """For pitch physics, noise has two levels: pitch to pitch within a game (sigma_pitch^2) and game to game
    around the player's season level (gamma^2, the day effect, which also absorbs in-season trend). A
    sample of n pitches over g games then has noise gamma^2 / g + sigma_pitch^2 / n, so pitches are not
    the unit of information: games are.

    sigma_pitch^2: pooled within-game variance, sum over games of (ss - s^2/c) / sum of (c - 1).
    gamma^2      : per player-season with min_games+ games, the variance of his game means minus the part
                   pitch noise explains (sigma_pitch^2 x mean(1/c)), pooled with weights games - 1.
    Also k_median, the median events per game (what regress() assumes when told only a pitch count).
    """
    use = a.c > 0
    if seasons is not None:
        use &= np.isin(fam.entity_season[fam.row_entity], seasons)
    rows = []
    rg_all = fam.entity_group[fam.row_entity]
    for g in sorted(set(fam.entity_group)):
        r = np.flatnonzero(use & (rg_all == g))
        if len(r) == 0:
            continue
        c, sm, sq = a.c[r].astype(float), a.s[r], a.ss[r]
        dev = sq - sm * sm / c
        two = c >= 2
        sig2 = float(dev[two].sum() / (c[two] - 1).sum()) if two.any() else np.nan
        t = pd.DataFrame({"e": fam.row_entity[r], "m": sm / c, "inv": 1 / c})
        agg = t.groupby("e").agg(G=("m", "size"), v=("m", "var"), inv=("inv", "mean"))
        agg = agg[agg["G"] >= min_games]
        gam = agg["v"] - sig2 * agg["inv"]
        gamma2 = float(np.average(gam, weights=agg["G"] - 1)) if len(agg) else np.nan
        game_sd = float(np.sqrt(np.average(agg["v"], weights=agg["G"] - 1))) if len(agg) else np.nan
        rows.append({"group": g, "sigma_pitch2": sig2, "gamma2": gamma2, "game_mean_sd": game_sd,
                     "k_median": float(np.median(c)), "day_players": int(len(agg))})
    return pd.DataFrame(rows)


def day_table(job: Job, seasons: list[int]) -> pd.DataFrame:
    out = []
    for m in job.metrics:
        if m.key not in PHYSICS:
            continue
        t = day_components(job.fam, job.arrays[m.key], seasons)
        if len(t):
            t.insert(0, "metric", [metric_id(m.role, m.key, g) for g in t["group"]])
            out.append(t.drop(columns="group"))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["metric"])


def with_day(params: pd.DataFrame, day: pd.DataFrame, curve: pd.DataFrame | None = None) -> pd.DataFrame:
    """Physics rows switch to the two-level model: tau = the talent SD measured by the half covariances,
    sigma2 = pitch-to-pitch noise, gamma2 = day-to-day noise. Adds the model's reliability for one pitch,
    one game of k_median pitches and five such games, and games needed for r = 0.5 and 0.7."""
    p = params.drop(columns=[c for c in day.columns if c != "metric" and c in params], errors="ignore")
    p = p.merge(day, on="metric", how="left")
    two = p["key"].isin(PHYSICS) & p["gamma2"].notna()
    p["model"] = np.where(two, "two-level", "one-level")
    p.loc[two, "tau"] = p.loc[two, "tau_cov"]
    p.loc[two, "sigma2"] = p.loc[two, "sigma_pitch2"]
    t2, g2, s2, k = p["tau_cov"] ** 2, p["gamma2"].clip(lower=0), p["sigma_pitch2"], p["k_median"]
    p["r_one_pitch"] = np.where(two, t2 / (t2 + g2 + s2), np.nan)
    p["r_one_game"] = np.where(two, t2 / (t2 + g2 + s2 / k), np.nan)
    p["r_five_games"] = np.where(two, t2 / (t2 + g2 / 5 + s2 / (5 * k)), np.nan)
    p["games_r50"] = np.where(two, (g2 + s2 / k) / t2, np.nan)
    p["games_r70"] = 7 / 3 * p["games_r50"]
    if curve is not None:
        r1 = curve[curve["n"].eq(1)].set_index("metric")["r"]
        p["r_one_pitch_measured"] = p["metric"].map(r1)
    return p


# ---------------------------------------------------------------- the club deliverable

_PARAMS_CACHE: dict = {}


def load_params(path: Path | None = None) -> pd.DataFrame:
    """The shipped constants (pooled 2024-26), one row per metric id."""
    path = Path(path or PARAMS_PATH)
    if path not in _PARAMS_CACHE:
        _PARAMS_CACHE[path] = pd.DataFrame(json.loads(path.read_text())["metrics"]).set_index("metric")
    return _PARAMS_CACHE[path]


def regress(metric: str, observed, n, league_mean: float, horizon: str = "season", params: pd.DataFrame | None = None,
            level: float = 0.95, M: float | None = None, tau: float | None = None, rho: float | None = None,
            drift_sd: float | None = None, games=None) -> pd.DataFrame:
    """Shrink an observed value toward the league mean, with an interval for the player's true level.

    metric       : an id like 'pitcher/whiff', 'pitcher/FF/velo', 'hitter/bat_speed' (see load_params()).
                   Rates are proportions (0.31, not 31); run value is runs per 100 pitches.
    observed, n  : the player's value and its sample in the metric's own denominator (scalars or arrays).
    games        : pitch physics only (velocity, spin, IVB, HB, arm angle, extension): the number of games the
                   n pitches came from. For these the day-to-day swing dominates, so the weight is
                   tau^2 / (tau^2 + gamma^2 / games + sigma^2 / n), not n / (n + M). Without games it assumes
                   n / k_median games and warns: one 100-pitch outing is one game, not ten.
    league_mean  : the mean to regress toward (the league, or a better prior if you have one).
    horizon      : "season": his true level over the period the sample covers (weight w = n / (n + M)).
                   "rest_of_season": his level over the rest of this season. Same estimate as "season"
                   (in-season change behaves like drift, not a pull back to the mean: tested), with the
                   interval widened by the measured drift (sd drift_sd from first half to second) when
                   that drift is distinguishable from 0.
                   "next_season": his level next season (weight rho * w; rho is year-to-year persistence).
    M, tau, rho  : override the shipped constants (rho: year-to-year persistence; drift_sd: in-season drift).

    Returns estimate, sd, lo, hi and the weight put on the observation. The sd is the posterior
    standard deviation of true talent under a normal model: tau * sqrt(1 - w) for the sample's own
    period, sqrt(tau^2 (1 - w) + drift_sd^2) for the rest of the season, tau * sqrt(1 - rho^2 w) next season.
    It describes his level, not the noise of a future sample: to bracket a future observed value of n2 events,
    add M tau^2 / n2 to the variance (that predictive interval is what the validation checked).
    Rates are clipped to [0, 1].
    """
    if params is None and (M is None or tau is None):
        params = load_params()
    row = params.loc[metric] if params is not None else {}
    two_level = M is None and params is not None and row.get("model") == "two-level"
    M = float(row["M"]) if M is None else float(M)
    tau = float(row["tau"]) if tau is None else float(tau)
    if horizon == "next_season":
        rho = float(row["rho_use"]) if rho is None else float(rho)
        if not np.isfinite(rho):
            raise ValueError(f"{metric}: no precise year-to-year estimate; use horizon='season'")
    elif horizon == "rest_of_season":
        drift_sd = float(row.get("drift_sd_use", row.get("drift_sd"))) if drift_sd is None else float(drift_sd)
        if not np.isfinite(drift_sd):
            raise ValueError(f"{metric}: no in-season drift estimate; use horizon='season'")
    elif horizon != "season":
        raise ValueError("horizon must be 'season', 'rest_of_season' or 'next_season'")
    obs, n = np.atleast_1d(np.asarray(observed, float)), np.atleast_1d(np.asarray(n, float))
    if two_level:
        if games is None:
            import warnings

            games = np.maximum(1.0, n / float(row["k_median"]))
            warnings.warn(f"{metric} is a pitch-physics metric: its noise is mostly day to day. Assuming "
                          f"{float(row['k_median']):g} pitches per game; pass games= for the real count.", stacklevel=2)
        g = np.maximum(np.atleast_1d(np.asarray(games, float)), 1.0)
        V = float(row["gamma2"]) / g + float(row["sigma2"]) / np.maximum(n, 1)
        w = np.where(n > 0, tau ** 2 / (tau ** 2 + V), 0.0)
    else:
        w = n / (n + M)
    if horizon in ("season", "rest_of_season"):
        est = np.where(n > 0, league_mean + w * (np.nan_to_num(obs) - league_mean), league_mean)
        sd = tau * np.sqrt(1 - w) if horizon == "season" else np.sqrt(tau ** 2 * (1 - w) + drift_sd ** 2)
        weight = w
    else:
        weight = rho * w
        est = league_mean + weight * (np.nan_to_num(obs) - league_mean)
        sd = tau * np.sqrt(1 - rho ** 2 * w)
    z = NormalDist().inv_cdf(0.5 + level / 2)
    lo, hi = est - z * sd, est + z * sd
    kind = row["kind"] if params is not None and "kind" in row else None
    if kind == "rate":
        lo, hi = np.clip(lo, 0, 1), np.clip(hi, 0, 1)
    return pd.DataFrame({"estimate": np.atleast_1d(est), "sd": sd, "lo": lo, "hi": hi, "weight": weight})


# ---------------------------------------------------------------- out-of-sample validation

def period_sums(fam: Family, a: Arrays, period: np.ndarray, n_period: int) -> tuple[np.ndarray, np.ndarray]:
    """Per entity and period (e.g. first/second half of a season): denominator count and value sum.
    period is per row of the family (-1 = not used)."""
    use = period >= 0
    idx = fam.row_entity[use] * n_period + period[use]
    cnt = np.bincount(idx, weights=a.c[use], minlength=fam.n_entity * n_period).reshape(-1, n_period)
    tot = np.bincount(idx, weights=a.s[use], minlength=fam.n_entity * n_period).reshape(-1, n_period)
    return cnt, tot


def period_games(fam: Family, a: Arrays, period: np.ndarray, n_period: int) -> np.ndarray:
    """Games with at least one event, per entity and period."""
    use = (period >= 0) & (a.c > 0)
    idx = fam.row_entity[use] * n_period + period[use]
    return np.bincount(idx, minlength=fam.n_entity * n_period).reshape(-1, n_period).astype(float)


VALIDATION_COLUMNS = ("rmse_raw", "rmse_shrunk", "rmse_mean", "cut_pct", "cut_lo", "cut_hi", "p_cut")
# Buckets by the weight on the first sample, w = n / (n + M): the same as n under M/4, M/4 to M, M to 3M, 3M +
BUCKETS = ((0, 0.2), (0.2, 0.5), (0.5, 0.75), (0.75, 1.01))
BUCKET_LABELS = ("< M/4", "M/4 to M", "M to 3M", "3M +")


def _golden(f, lo: float, hi: float, iters: int = 80) -> float:
    a, b = np.log(lo), np.log(hi)
    g = (np.sqrt(5) - 1) / 2
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = f(np.exp(c)), f(np.exp(d))
    for _ in range(iters):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a); fc = f(np.exp(c))
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a); fd = f(np.exp(d))
    return float(np.exp((a + b) / 2))


def score_forecast(obs1, n1, obs2, n2, prior, M, tau, rho=1.0, min_target: float | None = None, shift: float = 0.0,
                   extra_var: float = 0.0, boot: int = 400, seed: int = 0, V1=None, V2=None) -> tuple[pd.DataFrame, dict]:
    """Compare raw, regressed and league-mean forecasts of a later sample (out of sample).

    obs1/n1: the earlier sample (n1 >= 1); obs2/n2: the later one. V1, V2: the samples' noise variances
    (default M tau^2 / n, the one-level model; pitch physics pass the two-level values). Forecasts: raw = obs1;
    shrunk = prior + rho w (obs1 - prior) with w = tau^2 / (tau^2 + V1), which is n1 / (n1 + M) by default;
    mean = prior. Targets are kept when their own reliability tau^2 / (tau^2 + V2) is at least 1/6 (n2 >= M/5).
    Errors are against obs2 - shift, every player counting once. shift is the league's own change between
    the periods (the later period's ACTUAL league mean - prior, so it uses information a forecaster wouldn't
    have yet), so scores are relative to league: a league-wide move isn't anyone's error.

    Returns a table by bucket of w (equivalently n1 / M: under 1/4, 1/4-1, 1-3, 3+) with each forecast's RMSE,
    the % RMSE cut from raw, its bootstrap 95% interval and two-sided bootstrap p, and a dict with the overall
    result, the noise multiplier that would have minimized the error on this test set (best_over_M; with the
    default noise it is the best M over ours: a calibration check, in-sample by construction), and the coverage
    of 80% and 95% predictive intervals for obs2 (talent uncertainty + drift + obs2's own noise).
    """
    obs1, n1, obs2, n2 = (np.asarray(x, float) for x in (obs1, n1, obs2, n2))
    with np.errstate(invalid="ignore", divide="ignore"):
        V1 = M * tau ** 2 / n1 if V1 is None else np.asarray(V1, float)
        V2 = M * tau ** 2 / n2 if V2 is None else np.asarray(V2, float)
    if min_target is not None:
        keep_t = n2 >= min_target
    else:
        keep_t = (n2 >= 1) & (V2 <= 5 * tau ** 2)
    ok = (n1 >= 1) & keep_t & np.isfinite(obs1) & np.isfinite(obs2) & np.isfinite(V1) & np.isfinite(V2)
    obs1, n1, obs2, n2, V1, V2 = obs1[ok], n1[ok], obs2[ok] - shift, n2[ok], V1[ok], V2[ok]
    wk = lambda k: tau ** 2 / (tau ** 2 + k * V1)  # noqa: E731
    w = wk(1.0)
    f_shr = prior + rho * w * (obs1 - prior)
    e_raw, e_shr, e_mean = obs1 - obs2, f_shr - obs2, prior - obs2
    rng = np.random.default_rng(seed)
    rows = []
    for (lo, hi), lab in zip(BUCKETS + ((0, 1.01),), BUCKET_LABELS + ("all",)):
        b = (w >= lo) & (w < hi)
        k = int(b.sum())
        row = {"bucket": lab, "players": k}
        if k >= 10:
            r_raw, r_shr, r_mean = (float(np.sqrt(np.mean(e[b] ** 2))) for e in (e_raw, e_shr, e_mean))
            idx = np.flatnonzero(b)
            draws = rng.integers(0, k, (boot, k))
            cut = 1 - np.sqrt((e_shr[idx][draws] ** 2).mean(1)) / np.sqrt((e_raw[idx][draws] ** 2).mean(1))
            p_cut = min(1.0, 2 * min((np.sum(cut <= 0) + 1) / (boot + 1), (np.sum(cut >= 0) + 1) / (boot + 1)))
            row |= {"n1_median": float(np.median(n1[b])), "rmse_raw": r_raw, "rmse_shrunk": r_shr, "rmse_mean": r_mean,
                    "cut_pct": 100 * (1 - r_shr / r_raw), "cut_lo": 100 * _q(cut, 0.025), "cut_hi": 100 * _q(cut, 0.975),
                    "p_cut": p_cut}
        rows.append(row)
    table = pd.DataFrame(rows)
    sse = lambda k: float(np.mean((prior + rho * wk(k) * (obs1 - prior) - obs2) ** 2))  # noqa: E731
    best = _golden(sse, 1e-3, 1e3) if len(obs1) >= 20 else np.nan
    sd = np.sqrt(tau ** 2 * (1 - rho ** 2 * w) + V2 + extra_var)
    zc = np.abs(e_shr) / sd
    info = {"players": int(len(obs1)), "best_M": best * M if np.isfinite(best) else np.nan, "M": M, "best_over_M": best,
            "rmse_at_best_M": float(np.sqrt(sse(best))) if np.isfinite(best) else np.nan,
            "cover80": float(np.mean(zc <= 1.2816)) if len(zc) else np.nan,
            "cover95": float(np.mean(zc <= 1.96)) if len(zc) else np.nan}
    return table, info


def _params_dict(params: pd.DataFrame) -> dict:
    return {r["metric"]: r for r in params.to_dict("records")}


def validate(jobs: list[Job], train_params: pd.DataFrame, test_season: int, prev_season: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Out-of-sample checks with parameters fit without the test data.

    within: test season, games on or before the league's median game date -> games after.
            Prior = the test season's first-half league mean (known at the midpoint). The forecast is the
            regressed first half; its interval adds the in-season drift ("within, no drift" leaves it out).
    next  : prev season (full) -> test season (full), same player (and pitch type).
            Prior = the previous season's league mean. Shrunk uses rho * w; 'season-only' uses w.
    """
    P = _params_dict(train_params)
    by_bucket, overall = [], []
    for j in jobs:
        fam = j.fam
        row_season = fam.entity_season[fam.row_entity]
        # The league's median pitch date in the test season (each row weighted by its pitches)
        size = np.bincount(fam.event_row, minlength=fam.n_row)
        t = row_season == test_season
        dates, wts = fam.row_date[t], size[t]
        o = np.argsort(dates)
        cutoff = dates[o][np.searchsorted(np.cumsum(wts[o]), wts.sum() / 2)]
        first = fam.row_date <= cutoff
        half = np.where(row_season == test_season, np.where(first, 0, 1), -1)
        whole = np.where(row_season == prev_season, 0, np.where(row_season == test_season, 1, -1))
        key = pd.DataFrame({"player": fam.entity_player, "group": fam.entity_group, "season": fam.entity_season})
        for m in j.metrics:
            a = j.arrays[m.key]
            cnt_h, tot_h = period_sums(fam, a, half, 2)
            cnt_w, tot_w = period_sums(fam, a, whole, 2)
            gam_h, gam_w = period_games(fam, a, half, 2), period_games(fam, a, whole, 2)
            for g in j.groups:
                mid = metric_id(m.role, m.key, g)
                if mid not in P:
                    continue
                p = P[mid]
                M, tau, rho = p["M"], p["tau"], p.get("rho_use", np.nan)
                dv = p.get("drift_var_use", np.nan)
                drift_var = float(dv) if dv is not None and np.isfinite(dv) else 0.0
                two = p.get("model") == "two-level"

                def noise(n_, g_):
                    if not two:
                        return None
                    with np.errstate(invalid="ignore", divide="ignore"):
                        return p["gamma2"] / np.maximum(g_, 1) + p["sigma2"] / n_
                ent = np.flatnonzero((key["group"].to_numpy() == g) & (key["season"].to_numpy() == test_season))
                n1, s1, n2, s2 = cnt_h[ent, 0], tot_h[ent, 0], cnt_h[ent, 1], tot_h[ent, 1]
                with np.errstate(invalid="ignore", divide="ignore"):
                    prior = s1.sum() / n1.sum()
                    shift = s2.sum() / n2.sum() - prior
                    for label, xv in (("within", drift_var), ("within, no drift", 0.0)):
                        tab, info = score_forecast(s1 / n1, n1, s2 / n2, n2, prior, M, tau, shift=shift, extra_var=xv,
                                                   V1=noise(n1, gam_h[ent, 0]), V2=noise(n2, gam_h[ent, 1]))
                        tab.insert(0, "test", label); tab.insert(0, "metric", mid)
                        by_bucket.append(tab)
                        overall.append({"metric": mid, "test": label, "drift_var_used": xv, "league_shift": shift, **info,
                                        **{k: tab.loc[tab["bucket"].eq("all"), k].iloc[0] for k in VALIDATION_COLUMNS if k in tab}})
                # next season
                if not np.isfinite(rho):
                    continue
                kp = key.assign(e=np.arange(fam.n_entity))
                x = kp[(kp["group"] == g) & (kp["season"] == prev_season)].merge(
                    kp[(kp["group"] == g) & (kp["season"] == test_season)], on=["player", "group"])
                e1, e2 = x["e_x"].to_numpy(), x["e_y"].to_numpy()
                prev_ent = np.flatnonzero((key["group"].to_numpy() == g) & (key["season"].to_numpy() == prev_season))
                test_ent = np.flatnonzero((key["group"].to_numpy() == g) & (key["season"].to_numpy() == test_season))
                with np.errstate(invalid="ignore", divide="ignore"):
                    prior = tot_w[prev_ent, 0].sum() / cnt_w[prev_ent, 0].sum()
                    shift = tot_w[test_ent, 1].sum() / cnt_w[test_ent, 1].sum() - prior
                    o1, k1 = tot_w[e1, 0] / cnt_w[e1, 0], cnt_w[e1, 0]
                    o2, k2 = tot_w[e2, 1] / cnt_w[e2, 1], cnt_w[e2, 1]
                for label, r_use in (("next", rho), ("next, season weight only", 1.0)):
                    tab, info = score_forecast(o1, k1, o2, k2, prior, M, tau, rho=r_use, shift=shift,
                                               V1=noise(k1, gam_w[e1, 0]), V2=noise(k2, gam_w[e2, 1]))
                    tab.insert(0, "test", label); tab.insert(0, "metric", mid)
                    by_bucket.append(tab)
                    overall.append({"metric": mid, "test": label, "rho_used": r_use, "league_shift": shift, **info,
                                    **{k: tab.loc[tab["bucket"].eq("all"), k].iloc[0] for k in VALIDATION_COLUMNS if k in tab}})
    return pd.concat(by_bucket, ignore_index=True), pd.DataFrame(overall)


# ---------------------------------------------------------------- game vs. pitch-level splits

EVENT_SPLIT_CHECK = {("hitter", None): ["bat_speed", "swing_length", "attack_angle", "swing_path_tilt", "ev", "whiff", "chase"],
                     ("pitcher", "type"): ["velo", "spin", "ivb", "arm_angle", "whiff"]}


def event_split_check(d: pd.DataFrame, seasons: list[int], reps: int = 40, seed: int = 7, log=print) -> pd.DataFrame:
    """M from a split by game against M from a split by single events (what a random pitch-level split
    does). Days differ (opponent, park, weather, how the player feels), so a split that puts events from
    the same game in both halves shares that day's conditions and overstates reliability."""
    rows = []
    for (role, kind), keys in EVENT_SPLIT_CHECK.items():
        metrics = [m for m in (PITCHER_METRICS if role == "pitcher" else HITTER_METRICS) if m.key in keys]
        res = {}
        for unit in ("game", "event"):
            fam = build_family(d, role, by_type=kind == "type", unit=unit)
            job = _job(fam, metrics, seasons, boot=40, y2y=False)
            run_splits([job], reps, seed=seed, log=None)
            res[unit] = summarize(job)[1].set_index("metric")
            log(f"  event check {role} {unit}: done")
        for mid in res["game"].index.intersection(res["event"].index):
            if kind == "type" and not mid.split("/")[1] in ("FF", "SI", "SL", "CH"):
                continue
            g, e = res["game"].loc[mid], res["event"].loc[mid]
            rows.append({"metric": mid, "M_game": g["M"], "M_game_lo": g["M_lo"], "M_game_hi": g["M_hi"],
                         "M_event": e["M"], "M_event_lo": e["M_lo"], "M_event_hi": e["M_hi"], "ratio": g["M"] / e["M"]})
    return pd.DataFrame(rows)


def bat_speed_floor_check(d: pd.DataFrame, seasons: list[int], reps: int = 40, seed: int = 11) -> pd.DataFrame:
    """Bat speed with a fixed competitive-swing rule (50+ mph, no bunts) instead of Statcast's
    season-based fastest-90% rule, which both halves share."""
    d = d.copy()
    d["comp_fixed"] = d["swing"] & ~d["description"].isin(BUNTS) & (d["bat_speed"] >= 50)
    m = Metric("bat_speed_fixed", "Bat speed (50+ mph floor)", "hitter", "mean", "swings of 50+ mph", _f("bat_speed"), _b("comp_fixed"), fmt="mph")
    fam = build_family(d, "hitter")
    job = _job(fam, [m], seasons, boot=40, y2y=False)
    run_splits([job], reps, seed=seed, log=None)
    return summarize(job)[1]


def bat_speed_cut_check(d: pd.DataFrame, seasons: list[int], reps: int = 60, boot: int = 40, seed: int = 13) -> pd.DataFrame:
    """Does Statcast's season-based competitive-swing cut leak information between halves? Compare, on the
    same batter-seasons (those with a previous season in the data), bat speed under Statcast's rule against
    bat speed with the fastest-90% cut taken from the previous season. Reliability (pooled seasons) and the
    within-season validation on the last season, with parameters fit on the seasons before it."""
    d = add_prior_cut(d)
    metrics = [Metric("bat_speed_known", "Bat speed (Statcast's cut, same batters)", "hitter", "mean", "competitive swings",
                      _f("bat_speed"), _b("comp_bs_known"), fmt="mph"),
               Metric("bat_speed_prior", "Bat speed (previous season's cut)", "hitter", "mean", "competitive swings",
                      _f("bat_speed"), _b("comp_bs_prior"), fmt="mph")]
    job = _job(build_family(d, "hitter"), metrics, seasons, boot=boot, y2y=False)
    run_splits([job], reps, seed=seed, log=None)
    params = summarize(job, seasons=seasons[1:])[1]
    train = summarize(job, seasons=seasons[1:-1], pairs=[])[1]
    train = with_drift(train, drift_table(job, seasons[1:-1]))
    _, val = validate([job], train, test_season=seasons[-1], prev_season=seasons[-2])
    val = val[val["test"].eq("within")].set_index("metric")
    out = params[["metric", "label", "M", "M_lo", "M_hi", "tau_cov", "sigma2"]].copy()
    for c in ("players", "cut_pct", "cut_lo", "cut_hi", "cover80", "cover95"):
        out[f"within_{c}"] = out["metric"].map(val[c])
    return out


COHORTS = [("hitter", "woba", "ALL", 256), ("hitter", "whiff", "ALL", 256), ("hitter", "hard_hit", "ALL", 90),
           ("pitcher", "whiff", "ALL", 256), ("pitcher", "csw", "ALL", 512), ("pitcher", "chase", "ALL", 362),
           ("pitcher", "hard_hit", "ALL", 90), ("pitcher", "hard_hit", "CH", 45), ("pitcher", "hard_hit", "CU", 23),
           ("pitcher", "hard_hit", "SI", 64), ("pitcher", "xwoba_con", "SI", 64)]


def cohort_curves(jobs: list[Job], specs=COHORTS, reps: int = 60, boot: int = 40, seed: int = 5, log=print):
    """The reliability curve on a FIXED cohort: only player-seasons with at least 2 x n_cohort events, at
    every n up to n_cohort. With the open population, who is measured changes with n (only regulars reach
    large n); here it doesn't, so a curve whose M stays flat and sits near the open population's large-n
    value says the open curve's drift with n came from who was measured. Returns (curve, summary)."""
    rng = np.random.default_rng(seed)
    curves, summ = [], []
    for role, key, group, n_c in specs:
        job = next(j for j in jobs if j.fam.role == role and key in j.arrays and group in j.groups
                   and (group == "ALL") == (j.fam.name == role))
        fam, a = job.fam, job.arrays[key]
        tot = np.bincount(fam.row_entity, weights=a.c, minlength=fam.n_entity)
        mask = (fam.entity_group == group) & (tot >= 2 * n_c)
        players = np.unique(fam.entity_player[mask])
        draws = rng.multinomial(len(players), np.full(len(players), 1 / len(players)), size=boot).astype(float)
        Wp = np.vstack([np.ones(len(players)), draws])
        idx = np.searchsorted(players, fam.entity_player)
        idx = np.clip(idx, 0, len(players) - 1)
        W = Wp[:, idx] * mask[None, :]
        grid = [n for n in GRID if n <= n_c]
        n_cell = len(job.groups) * len(job.seasons)
        acc = np.zeros((boot + 1, len(grid), n_cell, 4))
        for _ in range(reps):
            acc += within_sums(half_means(a, random_split(fam, rng), fam.n_entity, grid), job.cell, n_cell, W)
        gi = job.groups.index(group)
        cells = [gi * len(job.seasons) + k for k in range(len(job.seasons))]
        nn, cc, vv = (x.sum(-1) for x in centered(acc[:, :, cells, :]))
        r = _ratio(cc, vv)
        g = np.array(grid, float)
        per_game = job.per_unit[key].get(group, 1.0)
        fit = g >= max(per_game, 1.0)
        if fit.sum() < 3:
            fit = np.ones(len(g), bool)
        Mc = fit_reliability_constant(g[fit], r[0, fit], nn[0, fit])
        Mb = np.array([fit_reliability_constant(g[fit], r[b, fit], nn[0, fit]) for b in range(1, boot + 1)])
        se = _sd(np.log(Mb))
        mid = metric_id(role, key, group)
        with np.errstate(invalid="ignore", divide="ignore"):
            Mn = g * (1 - r[0]) / r[0]
            sig2 = _ratio(vv[0] - cc[0], nn[0]) * g
            tau2 = _ratio(cc[0], nn[0])
        for i, n in enumerate(grid):
            curves.append({"metric": mid, "n_cohort": n_c, "n": n, "r": r[0, i], "r_lo": r[0, i] - 1.96 * _sd(r[1:, i]),
                           "r_hi": r[0, i] + 1.96 * _sd(r[1:, i]), "M_n": Mn[i], "sigma2_event": sig2[i], "tau2": tau2[i]})
        summ.append({"metric": mid, "n_cohort": n_c, "cohort": int(mask.sum()), "M_cohort": Mc,
                     "M_cohort_lo": Mc * np.exp(-1.96 * se), "M_cohort_hi": Mc * np.exp(1.96 * se),
                     "M_n_first_fit": float(Mn[fit][0]), "M_n_last": float(Mn[-1]),
                     "tau_cohort": float(np.sqrt(max(np.average(tau2[fit], weights=nn[0, fit]), 0)))})
        if log:
            log(f"  cohort {mid} (n <= {n_c}, {int(mask.sum())} player-seasons): M = {Mc:.1f}")
    return pd.DataFrame(curves), pd.DataFrame(summ)


# ---------------------------------------------------------------- fictional leagues (simulation checks)

def fictional_league(players=300, games=40, per_game=10, tau=1.0, sigma_g=0.0, sigma_e=1.0, seasons=(2026,), rho=1.0,
                     rho_half=1.0, binary=False, p_mean=0.25, seed=0) -> pd.DataFrame:
    """FICTIONAL players for checking the machinery against a known answer. Value = talent + game effect +
    event noise (or a Bernoulli draw at p = p_mean + talent). Talent correlates rho across seasons and
    rho_half between the first and second half of a season's games. Only the columns families need."""
    import math

    rng = np.random.default_rng(seed)
    P, G, K = players, games, per_game
    base = rng.normal(0, tau, P)
    frames = []
    for si, season in enumerate(seasons):
        if si:
            base = rho * base + math.sqrt(1 - rho ** 2) * rng.normal(0, tau, P)
        later = rho_half * base + math.sqrt(1 - rho_half ** 2) * rng.normal(0, tau, P)
        talent = np.where(np.arange(G)[None, :] < G // 2, base[:, None], later[:, None])
        value = talent[:, :, None] + rng.normal(0, sigma_g, (P, G))[:, :, None] * (sigma_g > 0) \
            + rng.normal(0, sigma_e, (P, G, K))
        if binary:
            value = (rng.random((P, G, K)) < np.clip(p_mean + talent, 0.01, 0.99)[:, :, None]).astype(float)
        pl, gm, ev = (x.ravel() for x in np.meshgrid(np.arange(P), np.arange(G), np.arange(K), indexing="ij"))
        dates = np.array([str(pd.Timestamp(f"{season}-04-01") + pd.Timedelta(days=int(g)))[:10] for g in range(G)])
        frames.append(pd.DataFrame({"batter": pl, "season": season, "game_pk": season * 100_000 + pl * 100 + gm,
                                    "game_date": dates[gm], "at_bat_number": ev // 4 + 1, "pitch_number": ev % 4 + 1,
                                    "pitch_type": "FF", "x": value.ravel()}))
    return pd.concat(frames, ignore_index=True)


FICTIONAL_X = Metric("x", "Fictional metric", "hitter", "mean", "events", lambda d: d["x"].to_numpy(float),
                     lambda d: np.ones(len(d), bool))


def fictional_summary(d: pd.DataFrame, seasons, reps: int = 12, unit: str = "game", seed: int = 3, boot: int = 60) -> pd.Series:
    """The atlas parameters of a fictional league (one metric, x)."""
    fam = build_family(d, "hitter", unit=unit)
    job = _job(fam, [FICTIONAL_X], list(seasons), boot)
    run_splits([job], reps, seed=seed, log=None)
    return summarize(job)[1].iloc[0]


def simulation_checks(leagues: int = 30, log=print) -> dict:
    """Saved evidence for two method claims, on FICTIONAL leagues with known truth.
    1. Day effects: talent sd 1, a day effect sd 0.5 shared by a game's 10 events, event noise sd 1. By game,
       M should be (1 + 10 x 0.25) / 1 = 3.5 for halves spanning many games; a pitch-level split shares days.
    2. Calibration: `leagues` leagues of 300 players, two seasons, rho = 0.6, M = 4. Do the bootstrap
       standard errors match the spread of the estimates across leagues, and do intervals cover the truth?"""
    d = fictional_league(players=300, games=40, per_game=10, tau=1.0, sigma_g=0.5, sigma_e=1.0, seed=4)
    by_game, by_event = fictional_summary(d, [2026], reps=10), fictional_summary(d, [2026], reps=10, unit="event")
    out = {"day_effect": {"theory_M_by_game": 3.5, "M_by_game": float(by_game["M"]), "M_by_event": float(by_event["M"])}}
    rows = []
    for k in range(leagues):
        d = fictional_league(players=300, games=30, per_game=6, tau=1.0, sigma_e=2.0, seasons=(2025, 2026), rho=0.6, seed=500 + k)
        sm = fictional_summary(d, [2025, 2026], reps=8, seed=k)
        rows.append((sm["rho"], sm["rho_se"], np.log(sm["M"]), np.log(sm["M_hi"] / sm["M"]) / 1.959964))
        if log and (k + 1) % 10 == 0:
            log(f"  calibration league {k + 1}/{leagues}")
    r = np.array(rows)
    out["calibration"] = {"leagues": leagues, "true_rho": 0.6, "true_M": 4.0,
                          "rho_sd_across_leagues": float(r[:, 0].std(ddof=1)), "rho_mean_se": float(r[:, 1].mean()),
                          "rho_cover95": float(np.mean(np.abs(r[:, 0] - 0.6) <= 1.959964 * r[:, 1])),
                          "logM_sd_across_leagues": float(r[:, 2].std(ddof=1)), "logM_mean_se": float(r[:, 3].mean()),
                          "logM_cover95": float(np.mean(np.abs(r[:, 2] - np.log(4)) <= 1.959964 * r[:, 3]))}
    return out


# ---------------------------------------------------------------- the whole study

def make_jobs(d: pd.DataFrame, seasons: list[int], boot: int = 100) -> list[Job]:
    return [
        _job(build_family(d, "hitter"), HITTER_METRICS, seasons, boot),
        _job(build_family(d, "pitcher"), [m for m in PITCHER_METRICS if m.overall], seasons, boot),
        _job(build_family(d, "pitcher", by_type=True), [m for m in PITCHER_METRICS if m.by_type], seasons, boot),
    ]


def league_means(d: pd.DataFrame) -> pd.DataFrame:
    """Event-weighted league mean of every metric by season (and pitch type), and its events per plate
    appearance (wOBA-denominator PAs), the rate that turns any M into a common currency."""
    pa = d.groupby("season")["woba_pa"].sum()
    rows = []
    for (role, key), m in METRICS.items():
        groups = (["ALL"] if m.overall or role == "hitter" else []) + (list(MAIN_TYPES) if m.by_type else [])
        for g in groups:
            e = d if g == "ALL" else d[d["pitch_type"].eq(g)]
            den = np.array(m.den(e), bool)
            val = np.asarray(m.value(e), float)
            den &= np.isfinite(val)
            s = pd.Series(val[den]).groupby(e["season"].to_numpy()[den]).agg(["mean", "size"])
            for season, r in s.iterrows():
                rows.append({"metric": metric_id(role, key, g), "season": int(season), "mean": r["mean"], "events": int(r["size"]),
                             "per_pa": r["size"] / pa.loc[season]})
    return pd.DataFrame(rows)


def run(seasons: list[int] = (2024, 2025, 2026), reps: int = 200, out_dir: Path | None = None,
        ship: bool = False, checks: bool = True, check_reps: int = 40, reuse_sums: bool = False, boot: int = 100,
        log=print) -> dict:
    """The atlas: split-half curves, parameters, year-to-year persistence, in-season drift, out-of-sample
    validation and the game-vs-event split check. Tables and a constants file -> data/edge/reliability/.
    ship=True also replaces the constants shipped with the code (baseball/evaluation/reliability_params.json,
    what regress() reads by default); do that only for a reviewed run, as with a report's figure."""
    seasons = list(seasons)
    out_dir = Path(out_dir or OUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    d = load(seasons)
    log(f"{len(d):,} pitches ({time.time() - t0:.0f}s)")
    jobs = make_jobs(d, seasons, boot)
    sums = out_dir / "split_sums.pkl"
    if reuse_sums and sums.exists():
        load_sums(jobs, sums)
        log("  reusing saved split sums")
    else:
        run_splits(jobs, reps, log=log)
        save_sums(jobs, sums)
    curve, params = (pd.concat(x, ignore_index=True) for x in zip(*[summarize(j) for j in jobs]))
    train = pd.concat([summarize(j, seasons=seasons[:-1], pairs=[(seasons[-3], seasons[-2])] if len(seasons) >= 3 else [])[1] for j in jobs], ignore_index=True)
    params = with_drift(params, pd.concat([drift_table(j, seasons) for j in jobs], ignore_index=True))
    train = with_drift(train, pd.concat([drift_table(j, seasons[:-1]) for j in jobs], ignore_index=True))
    params = with_day(params, pd.concat([day_table(j, seasons) for j in jobs], ignore_index=True), curve)
    train = with_day(train, pd.concat([day_table(j, seasons[:-1]) for j in jobs], ignore_index=True))
    log(f"  drift and day effects done ({time.time() - t0:.0f}s)")
    means = league_means(d)
    by_bucket, overall = validate(jobs, train, test_season=seasons[-1], prev_season=seasons[-2])
    # A replication on data never looked at while choosing the design: fit on the first season alone, test the
    # second season's halves (within-season only: there's no season pair before it to fit rho on).
    first = [seasons[0]]
    train1 = with_drift(pd.concat([summarize(j, seasons=first, pairs=[])[1] for j in jobs], ignore_index=True),
                        pd.concat([drift_table(j, first) for j in jobs], ignore_index=True))
    train1 = with_day(train1, pd.concat([day_table(j, first) for j in jobs], ignore_index=True))
    rep_bucket, rep_overall = validate(jobs, train1, test_season=seasons[1], prev_season=seasons[0])
    from baseball.stats import benjamini_hochberg

    for t in (overall, by_bucket, rep_overall, rep_bucket):
        t["q_cut"] = np.nan
        for test, idx in t.groupby("test").groups.items():
            t.loc[idx, "q_cut"] = benjamini_hochberg(t.loc[idx, "p_cut"].to_numpy())
    tables = {"curve": curve, "params": params, "params_train": train, "league_means": means,
              "validation_buckets": by_bucket, "validation": overall,
              "validation_replication": rep_overall, "validation_replication_buckets": rep_bucket}
    if checks and not (reuse_sums and (out_dir / "event_split.parquet").exists()):
        tables["event_split"] = event_split_check(d, seasons, reps=check_reps, log=log)
        tables["bat_speed_floor"] = bat_speed_floor_check(d, seasons, reps=check_reps)
    if checks and not (reuse_sums and (out_dir / "cohort_summary.parquet").exists()):
        tables["cohort_curve"], tables["cohort_summary"] = cohort_curves(jobs, log=log)
        tables["bat_speed_cut"] = bat_speed_cut_check(d, seasons)
        (out_dir / "simulation_checks.json").write_text(json.dumps(simulation_checks(log=log), indent=2))
    for name, t in tables.items():
        t.to_parquet(out_dir / f"{name}.parquet", index=False)
    summary = {"seasons": seasons, "reps": max(j.reps for j in jobs), "bootstrap_draws": boot, "pitches": int(len(d)), "games": int(d["game_pk"].nunique()),
               "pitchers": int(d["pitcher"].nunique()), "batters": int(d["batter"].nunique()),
               "source": "Baseball Savant Statcast, regular season", "built": time.strftime("%Y-%m-%d"),
               "minutes": round((time.time() - t0) / 60, 1)}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    write_param_file(params, means, summary, out_dir / "reliability_params.json")
    if ship:
        write_param_file(params, means, summary)
    log(f"done in {summary['minutes']} min")
    return {"summary": summary, **tables}


PARAM_FIELDS = ["metric", "label", "kind", "unit", "fmt", "model", "M", "M_lo", "M_hi", "tau", "tau_cov", "sigma2", "gamma2",
                "k_median", "drift_sd", "drift_sd_lo", "drift_sd_hi", "drift_sig", "drift_sd_use", "rho", "rho_lo", "rho_hi",
                "rho_use", "per_game", "r_at_max", "n_max"]


def write_param_file(params: pd.DataFrame, means: pd.DataFrame, summary: dict, path: Path | None = None) -> Path:
    """Ship the constants with the code (dated), so regress() works without the data."""
    p = params.copy()
    for c in PARAM_FIELDS:
        if c not in p:
            p[c] = np.nan
    last = means[means["season"].eq(max(summary["seasons"]))].set_index("metric")["mean"]
    p["league_mean_last"] = p["metric"].map(last)
    rec = json.loads(p[PARAM_FIELDS + ["league_mean_last"]].to_json(orient="records", double_precision=6))
    path = Path(path or PARAMS_PATH)
    path.write_text(json.dumps({"built": summary["built"], "seasons": summary["seasons"], "reps": summary["reps"],
                                "source": summary["source"],
                                "note": "Rates are proportions; run value is runs per 100 pitches. league_mean_last is the "
                                        "last season's event-weighted league mean. model 'two-level' (pitch physics): "
                                        "weight tau^2 / (tau^2 + gamma2 / games + sigma2 / n); pass games= to regress(). "
                                        "drift_sd_use is drift_sd when its 95% interval excludes 0, else 0.",
                                "metrics": rec}, indent=1))
    _PARAMS_CACHE.pop(path, None)
    return path


# ---------------------------------------------------------------- the report figure

SHORT = {"whiff": "whiff", "csw": "CSW", "chase": "chase", "zone": "zone%", "cstr": "called strike", "xwoba_con": "xwOBAcon",
         "hard_hit": "hard-hit", "barrel": "barrel", "gb": "GB%", "rv100": "RV/100", "swing": "swing%", "zone_swing": "zone swing",
         "zone_contact": "zone contact", "woba": "wOBA", "ev": "avg EV", "la": "avg LA", "pull": "pull%", "bat_speed": "bat speed",
         "swing_length": "swing length", "fast_swing": "fast-swing", "attack_angle": "attack angle",
         "attack_direction": "attack dir.", "swing_path_tilt": "tilt"}
FIGURE_CURVES = ["bat_speed", "swing_path_tilt", "attack_angle", "ev", "whiff", "chase", "barrel", "woba"]
LABEL_INSIDE = {"attack_angle": 0.85}


def _repel(ax, xs, ys, labels, dx: float = 6, step: float = 9.5, color: str = "#1f1f1f", size: float = 7.5) -> None:
    """Direct labels beside points, nudged up or down (in points, nearest first) until no two overlap."""
    fig = ax.figure
    fig.canvas.draw()
    placed = []
    order = np.argsort(-np.asarray(ys, float))
    offsets = [2.0] + [2.0 + sgn * step * k for k in range(1, 20) for sgn in (-1, 1)]
    for i in order:
        for off in offsets:
            t = ax.annotate(labels[i], (xs[i], ys[i]), xytext=(dx, off), textcoords="offset points", fontsize=size,
                            color=color, va="center")
            bb = t.get_window_extent(renderer=fig.canvas.get_renderer()).expanded(1.02, 1.1)
            if not any(bb.overlaps(p) for p in placed):
                placed.append(bb)
                break
            t.remove()
        else:
            placed.append(bb)


def figure(out_path: Path | None = None, tables_dir: Path | None = None) -> Path:
    """Three panels. Left and middle: the atlas maps, M (sample to r = 0.5, in plate appearances or batters
    faced) against year-to-year persistence rho, for hitters and for pitchers (all pitches). Right: hitter
    reliability curves with their fitted r = n/(n+M)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    from baseball.viz import INK, MUTED, PITCH_COLORS, _style

    D = Path(tables_dir or OUT_DIR)
    out_path = Path(out_path or D / "reliability-atlas.png")
    params, curve = pd.read_parquet(D / "params.parquet"), pd.read_parquet(D / "curve.parquet")
    per_pa = pd.read_parquet(D / "league_means.parquet").groupby("metric")["per_pa"].mean()
    summary = json.loads((D / "summary.json").read_text())
    p = params[params["group"].eq("ALL")].copy()
    p["M_pa"] = p["M"] / p["metric"].map(per_pa)
    p = p[p["rho_use"].notna()]
    colors = {"hitter": PITCH_COLORS["FF"], "pitcher": PITCH_COLORS["SI"]}
    fig, axes = plt.subplots(1, 3, figsize=(18, 6.2), gridspec_kw={"width_ratios": [1.1, 0.8, 1]}, dpi=160)
    titles = {"hitter": "Hitters: fast and sticky to slow", "pitcher": "Pitchers (all pitches): slower, less sticky"}
    xlab = {"hitter": "Plate appearances to r = 0.5 (M, log scale)", "pitcher": "Batters faced to r = 0.5 (M, log scale)"}
    for ax, role in zip(axes[:2], ("hitter", "pitcher")):
        g = p[p["role"].eq(role)].reset_index(drop=True)
        for beyond, gg in g.groupby(g["M"] > g["n_max"]):    # hollow: M extrapolated beyond the largest sample
            ax.errorbar(gg["M_pa"], gg["rho"], yerr=[(gg["rho"] - gg["rho_lo"]).clip(0), (gg["rho_hi"] - gg["rho"]).clip(0)],
                        fmt="o", ms=7, color=colors[role], ecolor=colors[role], elinewidth=1, alpha=0.9,
                        mec=colors[role] if beyond else "white", mfc="white" if beyond else colors[role], mew=1.2)
        ax.set_xscale("log")
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
        ax.xaxis.set_minor_formatter(FuncFormatter(lambda v, _: f"{v:g}" if str(int(round(v)))[0] in "25" and v >= 2 else ""))
        ax.set_ylim(0.7, 1.1)
        ax.axhline(1.0, color=MUTED, lw=0.8, ls=":")
        ax.set_xlabel(xlab[role], color=MUTED, fontsize=9)
        ax.set_title(titles[role], loc="left", fontsize=11.5, fontweight="bold", color=INK)
        _style(ax)
        _repel(ax, g["M_pa"].to_numpy(), g["rho"].to_numpy(), [SHORT.get(k, k) for k in g["key"]], color=INK)
    axes[0].set_ylabel("Year-to-year correlation of true talent (rho)", color=MUTED, fontsize=9)
    b = axes[2]
    line_color = ["#2a78d6", "#1baf7a", "#008300", "#eb6834", "#c98500", "#e87ba4", "#d55181", "#8a8a8a"]
    ends = []
    for k, col in zip(FIGURE_CURVES, line_color):
        mid = metric_id("hitter", k)
        c = curve[curve["metric"].eq(mid)].sort_values("n")
        if c.empty:
            continue
        M = float(params.loc[params["metric"].eq(mid), "M"].iloc[0])
        x = (c["n"] / per_pa[mid]).to_numpy()
        b.plot(x, c["r"], marker="o", ms=3.5, lw=0, color=col)
        x_fit = float(x[c["in_fit"].to_numpy()].min()) if c["in_fit"].any() else x.min()
        for lo, hi, ls in ((x.min(), x_fit, ":"), (x_fit, x.max(), "-")):   # solid where the curve was fit
            if hi > lo:
                xx = np.geomspace(lo, hi, 60)
                b.plot(xx, xx * per_pa[mid] / (xx * per_pa[mid] + M), color=col, lw=1.6, alpha=0.85, ls=ls)
        if k in LABEL_INSIDE:      # crowded at the top right: label it where the curve crosses this r instead
            i = int(np.argmax(c["r"].to_numpy() >= LABEL_INSIDE[k]))
            b.annotate(SHORT[k], (x[i], float(c["r"].iloc[i])), xytext=(8, -6), textcoords="offset points", fontsize=7.5,
                       color=INK, ha="left", va="top")
        else:
            ends.append((x[-1], float(c["r"].iloc[-1]), SHORT[k]))
    b.axhline(0.5, color=MUTED, lw=0.8, ls="--")
    b.axhline(0.7, color=MUTED, lw=0.8, ls=":")
    b.set_xscale("log")
    b.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    b.set_ylim(0, 1.03)
    b.set_xlabel("Sample, in plate appearances (log scale)", color=MUTED, fontsize=9)
    b.set_ylabel("Split-half reliability r(n)", color=MUTED, fontsize=9)
    b.set_title("Hitters: swing shape reads in days, results take seasons", loc="left", fontsize=11.5,
                fontweight="bold", color=INK)
    _style(b)
    b.set_xlim(right=b.get_xlim()[1] * 4)
    _repel(b, [e[0] for e in ends], [e[1] for e in ends], [e[2] for e in ends], color=INK)
    s = summary["seasons"]
    fig.text(0.01, 0.005,
             f"MLB regular seasons {s[0]}-{str(s[-1])[2:]}, Statcast via Baseball Savant. Reliability: each player's games split at random into halves of exactly n "
             f"events ({summary['reps']} splits, seasons pooled); dots are measured; lines are r = n/(n+M), solid over the fitted range (halves of at least one game's worth), dotted below it.\n"
             "rho: between-season correlation at matched samples divided by within-season reliability at that sample (2024-25 and 2025-26 pooled); bars are 95% "
             f"intervals ({summary.get('bootstrap_draws', '')} bootstrap draws of players).\nPlate appearances convert each metric's own events (swings, balls in play, "
             "pitches) at league rates per wOBA plate appearance. Hollow points: M lies beyond the largest sample measured (extrapolated). Metrics whose "
             "year-to-year correlation can't be estimated within +/-0.3 (wOBA, run value, pitchers' xwOBA on contact and barrels) are left off the maps.",
             fontsize=7.2, color="#555")
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    return out_path
