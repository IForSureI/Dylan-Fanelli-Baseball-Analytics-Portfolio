"""Benchmark the expected-whiff model against FanGraphs' Stuff+ by pitch type.

  uv run python -m baseball.edge.stuffplus_benchmark 2026

The Stuff+ tables: the FanGraphs Major League pitching leaderboard, Stuff+ tab, single seasons 2024, 2025
and 2026, as shown on the public page on Nov. 15, 2026. They sit in data/fangraphs/ with a SOURCE.txt and
are never committed. Nothing here contacts FanGraphs.

Innings: the 2024 and 2026 tables hold pitchers with 15+ innings. The 2025 table also holds pitchers under
15 innings, but only those in the first 708 rows by Pitching+, so its short-innings rows lean toward good
ones. The held-out test below keeps 15+ innings in every season so the fit and the scoring see the same
kind of pitcher.

Two things to keep in mind when reading the results:

- Stuff+ is built to predict run value. My expected whiff is built to predict swings and misses. So the
  same-season section shows each one against Savant's run value per 100 as well as against whiffs.
- Next season's whiff rate is scored two ways. Held out, the strict way the Savant benchmark uses: every
  model's weights are fit on 2024 into 2025 and scored on 2025 into 2026. And by cross-validation by
  pitcher inside 2025 into 2026 (the pitchers are split into five groups, weights are fit on four and
  scored on the fifth), which was the only option before the 2024 table existed and is kept beside it.

Ids: FanGraphs player id to MLBAM id through the Chadwick register (data/people/people.parquet).
Players the register does not link are left out. No names are matched.

Pitch types: see `fg_column()`; `mapping_evidence()` counts what the rule rests on.

Output: reports/outputs/edge-stuffplus-benchmark-<season>.json (aggregates only).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from baseball.edge import savant_benchmark as sb

ROOT = Path(__file__).resolve().parents[2]
FG_DIR = ROOT / "data" / "fangraphs"
FG_FILES = ("stuff_plus_by_pitch_2024.csv", "stuff_plus_by_pitch_2025_2026.csv")
MIN_IP = 15.0        # the innings floor every season's table shares
OUT = ROOT / "reports" / "outputs"

FG_COLUMNS = ("FA", "SI", "FC", "FS", "SL", "CU", "CH", "KC", "FO")
# Statcast code -> FanGraphs Stuff+ column. Sweepers share the slider column and slurves the curveball
# column; `mapping_evidence()` shows why.
FG_OF = {"FF": "FA", "SI": "SI", "FC": "FC", "FS": "FS", "FO": "FO", "CH": "CH", "KC": "KC",
         "SL": "SL", "ST": "SL", "CU": "CU", "SV": "CU"}
SHARED = {"SL": ("SL", "ST"), "CU": ("CU", "SV")}   # FanGraphs columns that two Statcast types land in
MIN_SHARE = 0.90     # a pitch owns a shared column when it is 90% of the pitcher's pitches in that column
THROWS = 100         # "throws the pitch" in the evidence counts: 100+ pitches in the season


# ---------------------------------------------------------------------------------------------
# Load and map
# ---------------------------------------------------------------------------------------------

def load_fangraphs(paths=None) -> pd.DataFrame:
    """Every season's table stacked. One row per pitcher and season."""
    return pd.concat([pd.read_csv(p) for p in (paths or [FG_DIR / f for f in FG_FILES])], ignore_index=True)


def map_ids(fg: pd.DataFrame, register: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Add the MLBAM id (`pitcher`) from the register's FanGraphs key. Rows with no link are dropped and counted."""
    reg = register.dropna(subset=["key_fangraphs", "key_mlbam"])
    reg = reg.assign(fgid=pd.to_numeric(reg["key_fangraphs"], errors="coerce")).dropna(subset=["fgid"]).drop_duplicates("fgid")
    m = fg.merge(reg[["fgid", "key_mlbam"]], on="fgid", how="left")
    counts = {str(s): {"rows": int(len(g)), "mapped": int(g["key_mlbam"].notna().sum()), "unmapped": int(g["key_mlbam"].isna().sum())}
              for s, g in m.groupby("season")}
    m = m.dropna(subset=["key_mlbam"])
    return m.assign(pitcher=m["key_mlbam"].astype("int64")).drop(columns="key_mlbam"), counts


def long_stuff(fg: pd.DataFrame) -> pd.DataFrame:
    """One row per pitcher, season and FanGraphs column that holds a Stuff+ value."""
    out = fg.melt(id_vars=["season", "pitcher", "ip"], value_vars=list(FG_COLUMNS), var_name="fg_col", value_name="stuff_plus")
    return out.dropna(subset=["stuff_plus"]).reset_index(drop=True)


def fg_column(table: pd.DataFrame, counts: pd.DataFrame) -> pd.DataFrame:
    """Add `fg_col`, the FanGraphs Stuff+ column each of my pitches is compared with. The rule:

    - Four-seamer to FA. SI, FC, FS, FO, CH and KC to the column of the same name.
    - FanGraphs has no sweeper or slurve column. Sweepers go in its SL column and slurves in its CU column.
      (The slurve evidence is thin and, in 2024, mixed. Slurves are a handful of rows, so the choice moves nothing.)
    - A pitcher who throws both pitches of a shared column (slider and sweeper, or curveball and slurve) has
      one Stuff+ number for the two. My pitch is matched only when it is at least 90% of his pitches in
      that column for the season; otherwise the row is dropped.

    `counts` has pitcher, pitch_type and pitches (every regular-season pitch, no floor)."""
    t = table[table["pitch_type"].isin(FG_OF)].copy()
    t["pitcher"] = t["pitcher"].astype("int64")
    t["fg_col"] = t["pitch_type"].map(FG_OF)
    c = counts[counts["pitch_type"].isin(FG_OF)].assign(pitcher=lambda d: d["pitcher"].astype("int64"), fg_col=lambda d: d["pitch_type"].map(FG_OF))
    total = c.groupby(["pitcher", "fg_col"])["pitches"].sum().rename("col_pitches").reset_index()
    own = c[["pitcher", "pitch_type", "pitches"]].rename(columns={"pitches": "own_pitches"})
    t = t.merge(own, on=["pitcher", "pitch_type"], how="left").merge(total, on=["pitcher", "fg_col"], how="left")
    t["col_share"] = t["own_pitches"] / t["col_pitches"]
    return t[t["col_share"] >= MIN_SHARE].drop(columns=["own_pitches", "col_pitches"])


def mapping_evidence(counts: pd.DataFrame, fg: pd.DataFrame) -> dict:
    """What the pitch-type rule rests on, for one season. `counts`: pitcher, pitch_type, pitches. `fg`: that
    season's mapped FanGraphs rows. For each Statcast type: of the pitchers who threw 100+, how many have a
    value in each candidate column. Then the cases that decide sweepers and slurves."""
    n = counts.assign(pitcher=counts["pitcher"].astype("int64")).pivot_table(index="pitcher", columns="pitch_type", values="pitches", aggfunc="sum")
    n = n.reindex(columns=sorted(set(n.columns) | set(FG_OF))).fillna(0)
    j = n.join(fg.set_index("pitcher")[list(FG_COLUMNS)].add_prefix("fg_"), how="inner")

    def filled(rows, col):
        return int(rows[f"fg_{col}"].notna().sum())

    by_type = {}
    for code in FG_OF:
        rows = j[j[code] >= THROWS]
        by_type[code] = {"pitchers": int(len(rows))} | {f"with_{c}": filled(rows, c) for c in FG_COLUMNS if filled(rows, c) > len(rows) / 4
                                                         or c == FG_OF[code]}
    st_only = j[(j["ST"] >= THROWS) & (j["SL"] == 0)]
    none = j[(j["ST"] == 0) & (j["SL"] == 0) & (j["SV"] == 0)]
    sv_only = j[(j["SV"] >= THROWS) & (j["SL"] == 0) & (j["ST"] == 0)]
    sv_alone = sv_only[(sv_only["CU"] == 0) & (sv_only["KC"] == 0)]
    kc_only = j[(j["KC"] >= THROWS) & (j["CU"] == 0)]
    both = j[(j["ST"] >= THROWS) & (j["SL"] >= THROWS)]
    return {
        "pitchers_joined": int(len(j)),
        "throws_100_pitches": by_type,
        "sweeper_no_slider": {"pitchers": int(len(st_only)), "with_SL": filled(st_only, "SL")},
        "no_slider_sweeper_or_slurve": {"pitchers": int(len(none)), "with_SL": filled(none, "SL")},
        "slurve_no_slider_or_sweeper": {"pitchers": int(len(sv_only)), "with_SL": filled(sv_only, "SL"), "with_CU": filled(sv_only, "CU")},
        "slurve_and_no_other_breaking_ball": {"pitchers": int(len(sv_alone)), "with_SL": filled(sv_alone, "SL"), "with_CU": filled(sv_alone, "CU")},
        "knuckle_curve_no_curveball": {"pitchers": int(len(kc_only)), "with_KC": filled(kc_only, "KC"), "with_CU": filled(kc_only, "CU")},
        "slider_and_sweeper_100_each": {"pitchers": int(len(both)), "with_SL": filled(both, "SL")},
    }


def season_frame(table: pd.DataFrame, counts: pd.DataFrame, stuff: pd.DataFrame, savant: pd.DataFrame, min_swings: int = sb.MIN_SWINGS) -> pd.DataFrame:
    """My pitches with 60+ swings, each with its Stuff+ (FanGraphs column by the rule above) and, where Savant
    has the row, its miss distance and run value per 100."""
    t = fg_column(table[table["swings"] >= min_swings], counts)
    t = t.merge(stuff[["pitcher", "fg_col", "stuff_plus", "ip"]], on=["pitcher", "fg_col"], how="inner")
    sv = sb.savant_type(t).merge(savant.rename(columns={"pitch_type": "sv_type"}), on=["pitcher", "sv_type"], how="left")
    return sv.reset_index(drop=True)


# ---------------------------------------------------------------------------------------------
# 1. Same season, pitch level   2. Pitcher level
# ---------------------------------------------------------------------------------------------

PITCH_PAIRS = [("x_whiff_pct", "stuff_plus"), ("x_whiff_pct", "sv_miss_in"), ("stuff_plus", "sv_miss_in"),
               ("x_whiff_pct", "whiff_pct"), ("stuff_plus", "whiff_pct"), ("sv_miss_in", "whiff_pct"),
               ("x_whiff_pct", "sv_rv100"), ("stuff_plus", "sv_rv100"), ("sv_miss_in", "sv_rv100"), ("whiff_pct", "sv_rv100")]


def same_season(frame: pd.DataFrame, n_boot: int = 2000, seed: int = 7) -> dict:
    """Correlations on pitches that have all three measures and a Savant run value, so every pair is on the
    same rows. `raw` pools pitch types; `within_pitch_type` centers by my pitch type and season."""
    f = frame.dropna(subset=["stuff_plus", "sv_miss_in", "sv_rv100", "x_whiff_pct", "whiff_pct"])
    by = ["season", "pitch_type"] if "season" in f else ["pitch_type"]
    return {f"{a} ~ {b}": {"raw": sb.corr_row(f, a, b, None, n_boot, seed), "within_pitch_type": sb.corr_row(f, a, b, by, n_boot, seed)}
            for a, b in PITCH_PAIRS}


def by_pitch_type(frame: pd.DataFrame, a: str = "x_whiff_pct", b: str = "stuff_plus", min_n: int = 40, n_boot: int = 2000, seed: int = 7) -> dict:
    """The same correlation one pitch type at a time (centered by season), for types with 40+ rows."""
    out = {}
    for pt, g in frame.dropna(subset=[a, b]).groupby("pitch_type"):
        if len(g) >= min_n:
            out[pt] = sb.corr_row(g, a, b, ["season"] if "season" in g else None, n_boot, seed)
    return out


def roll_up(frame: pd.DataFrame) -> pd.DataFrame:
    """One row per pitcher and season: expected and actual whiff weighted by swings over his 60-swing pitches,
    and Savant run value per 100 weighted by pitches (blank if any of his pitches has none)."""
    def roll(g):
        w, p = g["swings"].to_numpy(float), g["sv_pitches"].fillna(0).to_numpy(float)
        rv = np.average(g["sv_rv100"], weights=p) if p.sum() > 0 and g["sv_rv100"].notna().all() else np.nan
        return pd.Series({"x_whiff_pct": np.average(g["x_whiff_pct"], weights=w), "whiff_pct": np.average(g["whiff_pct"], weights=w),
                          "sv_rv100": rv, "swings": w.sum(), "pitch_types": len(g)})

    return frame.groupby(["season", "pitcher"]).apply(roll, include_groups=False).reset_index()


def pitcher_level(frame: pd.DataFrame, overall: pd.DataFrame, n_boot: int = 2000, seed: int = 7) -> dict:
    """`roll_up()` of every 60-swing pitch joined to Savant (whether or not it has a by-pitch Stuff+), against
    FanGraphs' overall Stuff+ (the `stuff` column). Correlations are centered by season."""
    p = roll_up(frame)
    p = p.merge(overall[["season", "pitcher", "stuff"]], on=["season", "pitcher"], how="inner").rename(columns={"stuff": "stuff_plus"})
    pairs = [("x_whiff_pct", "stuff_plus"), ("whiff_pct", "stuff_plus"), ("x_whiff_pct", "whiff_pct"), ("stuff_plus", "sv_rv100"),
             ("x_whiff_pct", "sv_rv100"), ("whiff_pct", "sv_rv100")]
    out = {"pitcher_seasons": int(len(p)), "pitchers": int(p["pitcher"].nunique()), "median_swings": float(p["swings"].median())}
    for a, b in pairs:
        out[f"{a} ~ {b}"] = sb.corr_row(p, a, b, ["season"], n_boot, seed)
    return out


# ---------------------------------------------------------------------------------------------
# 3. Next season's whiff rate
# ---------------------------------------------------------------------------------------------

MEASURES = {"expected": "x_whiff_pct_prev", "stuff": "stuff_plus_prev", "miss": "sv_miss_in_prev"}
MODELS = {"last_whiff": ["whiff_pct_prev"], "type": ["TYPE"]}
for _name, _col in MEASURES.items():
    MODELS[_name] = [_col]
    MODELS[f"{_name}+type"] = [_col, "TYPE"]
    MODELS[f"last+{_name}"] = ["whiff_pct_prev", _col]
    MODELS[f"last+{_name}+type"] = ["whiff_pct_prev", _col, "TYPE"]
MODELS["last+expected+stuff"] = ["whiff_pct_prev", "x_whiff_pct_prev", "stuff_plus_prev"]
MODELS["last+expected+stuff+miss"] = ["whiff_pct_prev", "x_whiff_pct_prev", "stuff_plus_prev", "sv_miss_in_prev"]
MODELS["last+expected+stuff+type"] = ["whiff_pct_prev", "x_whiff_pct_prev", "stuff_plus_prev", "TYPE"]
MODELS["last+expected+stuff+miss+type"] = ["whiff_pct_prev", "x_whiff_pct_prev", "stuff_plus_prev", "sv_miss_in_prev", "TYPE"]
NEEDS_STUFF = [k for k, v in MODELS.items() if "stuff_plus_prev" in v]

CONTRASTS = [("expected", "stuff"), ("expected+type", "stuff+type"), ("last+expected", "last+stuff"), ("last+expected+type", "last+stuff+type"),
             ("stuff", "miss"), ("stuff+type", "miss+type"), ("last+stuff", "last+miss"), ("last+stuff+type", "last+miss+type"),
             ("last+expected+stuff", "last+expected"), ("last+expected+stuff", "last+stuff"),
             ("last+expected+stuff+miss", "last+expected+stuff"),
             ("last+expected+stuff+type", "last+expected+type"), ("last+expected+stuff+type", "last+stuff+type"),
             ("last+expected+stuff+miss+type", "last+expected+stuff+type")]

# Stuff+ is scaled inside each pitch type (100 is an average pitch of that type), so on its own it says
# nothing about whether the pitch is a sinker or a slider, and whiff rates differ a lot by type. The rows
# with "+type" (one intercept per pitch type) are the fair read of Stuff+, as they are of miss distance.
VERDICTS = {"alone": ("expected", "stuff"), "alone_given_pitch_type": ("expected+type", "stuff+type"),
            "with_last_season": ("last+expected", "last+stuff"), "with_last_season_given_pitch_type": ("last+expected+type", "last+stuff+type")}


def pair(prev_frame: pd.DataFrame, curr_table: pd.DataFrame, min_swings: int = sb.MIN_SWINGS) -> pd.DataFrame:
    """Pitches with 60+ swings in both seasons, and a Stuff+ and a Savant miss distance in the earlier one.
    `prev_frame` is season_frame() for the earlier season. Seasons are joined on pitcher and Savant's pitch
    type, as in the Savant benchmark."""
    p = prev_frame.dropna(subset=["stuff_plus", "sv_miss_in"])
    c = sb.savant_type(curr_table[curr_table["swings"] >= min_swings]).assign(pitcher=lambda d: d["pitcher"].astype("int64"))
    keep = ["pitcher", "sv_type", "pitch_type", "swings", "whiff_pct", "x_whiff_pct", "sv_miss_in", "stuff_plus", "ip"]
    m = p[keep].merge(c[["pitcher", "sv_type", "swings", "whiff_pct"]], on=["pitcher", "sv_type"], suffixes=("_prev", "_curr"))
    return m.rename(columns={"x_whiff_pct": "x_whiff_pct_prev", "sv_miss_in": "sv_miss_in_prev", "stuff_plus": "stuff_plus_prev",
                             "ip": "ip_prev"}).reset_index(drop=True)


def folds(pitchers, k: int = 5, seed: int = 7) -> np.ndarray:
    """A fold number for every row. All of a pitcher's rows share a fold."""
    ids = np.unique(np.asarray(pitchers))
    order = np.random.default_rng(seed).permutation(len(ids))
    fold_of = dict(zip(ids[order], np.arange(len(ids)) % k))
    return np.array([fold_of[p] for p in np.asarray(pitchers)])


def cv_predictions(frame: pd.DataFrame, models: dict, k: int = 5, seed: int = 7) -> dict[str, np.ndarray]:
    """Out-of-fold predictions for every model: each pitcher's rows are predicted by weights fit without him."""
    fold = folds(frame["pitcher"], k, seed)
    preds = {name: np.full(len(frame), np.nan) for name in models}
    for i in range(k):
        train, test = frame[fold != i], frame[fold == i]
        for name, cols in models.items():
            preds[name][fold == i] = sb.design(test, cols) @ sb.fit(train, cols)
    return preds


def holdout_predictions(train: pd.DataFrame, test: pd.DataFrame, models: dict) -> dict[str, np.ndarray]:
    """Predictions for `test` from weights fit on another pair of seasons."""
    return {name: sb.design(test, cols) @ sb.fit(train, cols) for name, cols in models.items()}


def score(frame: pd.DataFrame, preds: dict[str, np.ndarray], contrasts, n_boot: int = 2000, seed: int = 7) -> dict:
    """Weighted RMSE of each model's predictions, the gain against the last-season baseline, and the RMSE
    difference for each contrast, all with 95% intervals from resampling pitchers (predictions held fixed)."""
    y, w = frame["whiff_pct_curr"].to_numpy(float), sb.weights(frame)
    scores = {name: sb.rmse(y, p, w) for name, p in preds.items()}
    boot = {name: [] for name in preds}
    for idx in sb.pitcher_draws(frame["pitcher"], n_boot, seed):
        for name, p in preds.items():
            boot[name].append(sb.rmse(y[idx], p[idx], w[idx]))
    boot = {name: np.asarray(v) for name, v in boot.items()}
    base = "last_whiff"
    models = {}
    for name in preds:
        lo, hi = sb.interval(100 * (1 - boot[name] / boot[base]))
        models[name] = {"rmse": scores[name], "r": sb._r(preds[name], y), "gain_vs_baseline_pct": 100 * (1 - scores[name] / scores[base]),
                        "gain_lo": lo, "gain_hi": hi}
    out = {}
    for a, b in contrasts:
        if a in preds and b in preds:
            lo, hi = sb.interval(boot[a] - boot[b])
            out[f"{a} minus {b}"] = {"rmse_diff": scores[a] - scores[b], "lo": lo, "hi": hi,
                                     "share_of_resamples_first_is_better": float((boot[a] < boot[b]).mean())}
    return {"pitches": int(len(frame)), "pitchers": int(frame["pitcher"].nunique()),
            "rmse_raw_last_season": sb.rmse(y, frame["whiff_pct_prev"], w), "models": models, "contrasts": out}


def verdict(scored: dict, a: str, b: str) -> str:
    """Which of two models won: the interval on the RMSE difference has to exclude zero."""
    c = scored["contrasts"][f"{a} minus {b}"]
    return a if c["hi"] < 0 else b if c["lo"] > 0 else "tie"


def winners(scored: dict) -> dict:
    out = {name: verdict(scored, a, b) for name, (a, b) in VERDICTS.items()}
    out["stuff_vs_miss_alone_given_pitch_type"] = verdict(scored, "stuff+type", "miss+type")
    out["stuff_vs_miss_with_last_season"] = verdict(scored, "last+stuff", "last+miss")
    return out


def held_out(train: pd.DataFrame, test: pd.DataFrame, n_boot: int = 2000, seed: int = 7) -> dict:
    """Every model, Stuff+ ones included: weights fit on `train` (an earlier pair of seasons) and scored on
    `test`, whose outcomes no weight has seen."""
    out = score(test, holdout_predictions(train, test, MODELS), CONTRASTS, n_boot, seed)
    out["train_pitches"], out["train_pitchers"] = int(len(train)), int(train["pitcher"].nunique())
    out["winner"] = winners(out)
    return out


def next_season(test: pd.DataFrame, train_earlier: pd.DataFrame | None = None, k: int = 5, n_boot: int = 2000, seed: int = 7) -> dict:
    """Score every model on `test` (the one pair with Stuff+).

    - `cross_validated_by_pitcher`: every model, weights fit inside the pair on other pitchers.
    - `weights_from_earlier_pair`: the models that need no Stuff+, weights fit on `train_earlier`."""
    cv = score(test, cv_predictions(test, MODELS, k, seed), CONTRASTS, n_boot, seed)
    cv["winner"] = winners(cv)
    cv["folds"], cv["fold_seed"] = k, seed
    y = test["whiff_pct_curr"].to_numpy(float)
    alone = {c: sb.corr_row(test.assign(y=y), c, "y", None, n_boot, seed) for c in ("whiff_pct_prev", *MEASURES.values())}
    alone |= {f"{c}, within pitch type": sb.corr_row(test.assign(y=y), c, "y", ["sv_type"], n_boot, seed) for c in MEASURES.values()}
    out = {"cross_validated_by_pitcher": cv, "r_with_next_season_whiff": alone}
    if train_earlier is not None:
        free = {name: cols for name, cols in MODELS.items() if name not in NEEDS_STUFF}
        ho = score(test, holdout_predictions(train_earlier, test, free), CONTRASTS, n_boot, seed)
        ho["train_pitches"] = int(len(train_earlier))
        out["weights_from_earlier_pair"] = ho
    return out


# ---------------------------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------------------------

def run(season: int = 2026, n_boot: int = 2000, seed: int = 7, log=print) -> dict:
    from baseball.ingest import people
    from baseball.ingest.league import load_season
    from baseball.phases import phase

    seasons = [season - 2, season - 1, season]
    tables = sb.load_tables(seasons, season)
    savant = {s: sb.load_savant(s) for s in seasons}
    fg_all = load_fangraphs()
    fg, id_counts = map_ids(fg_all, people.load())
    stuff = long_stuff(fg)
    counts = {s: sb.raw_counts(phase(load_season(s, ["pitcher", "pitch_type", "description", "game_type"]))) for s in seasons}
    log("tables loaded")

    frames, all_pitches, coverage, evidence = {}, {}, {}, {}
    for s in seasons:
        frames[s] = season_frame(tables[s], counts[s], stuff[stuff["season"] == s], savant[s]).assign(season=s)
        floor = tables[s][tables[s]["swings"] >= sb.MIN_SWINGS]
        mapped_types = floor[floor["pitch_type"].isin(FG_OF)]
        with_col = fg_column(mapped_types, counts[s])
        all_pitches[s] = sb.match(tables[s], savant[s]).assign(season=s)
        coverage[str(s)] = {"my_pitches_60_swings": int(len(floor)), "in_a_type_fangraphs_lists": int(len(mapped_types)),
                            "after_shared_column_rule": int(len(with_col)), "dropped_by_shared_column_rule": int(len(mapped_types) - len(with_col)),
                            "with_stuff_plus": int(len(frames[s])), "slurves_with_stuff_plus": int(frames[s]["pitch_type"].eq("SV").sum()), "with_stuff_plus_and_savant": int(frames[s][["sv_miss_in", "sv_rv100"]].notna().all(axis=1).sum())}
        evidence[str(s)] = mapping_evidence(counts[s], fg[fg["season"] == s])
    pooled = pd.concat([frames[season - 1], frames[season]], ignore_index=True)   # the two seasons the first benchmark had

    test = pair(frames[season - 1], tables[season])
    train_stuff = pair(frames[season - 2], tables[season - 1])
    ip15 = lambda f: f[f["ip_prev"] >= MIN_IP].reset_index(drop=True)
    short = test[test["ip_prev"] < MIN_IP]
    train = sb.pair(tables[season - 2], tables[season - 1], savant[season - 2])
    plain = sb.pair(tables[season - 1], tables[season], savant[season - 1])
    log(f"next-season set: {len(test):,} pitches")

    source = (FG_DIR / "SOURCE.txt").read_text().strip().splitlines()
    result = {
        "source": f"python -m baseball.edge.stuffplus_benchmark {season}, on the bb edge {season} pitch tables, the regular-season pitch files, "
                  "the Savant leaderboard files of the Savant benchmark, and the FanGraphs Stuff+ table described below.",
        "what_this_is": "Expected whiff against FanGraphs Stuff+ by pitch type, 2025 and 2026. Stuff+ is built to predict run value; "
                        "expected whiff is built to predict swings and misses.",
        "fangraphs_table": {"description": source, "rows": {str(s): int((fg_all["season"] == s).sum()) for s in seasons},
                            "rows_15_ip": {str(s): int(((fg_all["season"] == s) & (fg_all["ip"] >= MIN_IP)).sum()) for s in seasons}},
        "limits": ["One held-out test: weights fit on 2024 into 2025, scored on 2025 into 2026. There is no second scoring year.",
                   "Stuff+ by pitch type exists only for the columns FanGraphs lists: FA SI FC FS SL CU CH KC FO.",
                   "The 2024 and 2026 tables are pitchers with 15+ innings. The 2025 table leaves out 139 pitchers who threw under 15 "
                   "innings and keeps the under-15 pitchers only from its first 708 rows by Pitching+.",
                   "FanGraphs ids with no link in the Chadwick register are left out; no names are matched."],
        "id_mapping": {"how": "FanGraphs player id to MLBAM id through the Chadwick register (key_fangraphs to key_mlbam)", "by_season": id_counts},
        "pitch_type_rule": {"map": FG_OF, "shared_columns": {k: list(v) for k, v in SHARED.items()}, "min_share_of_shared_column": MIN_SHARE,
                            "in_words": "FF to FA; SI, FC, FS, FO, CH, KC to the same name; sweepers (ST) to SL and slurves (SV) to CU. "
                                        "Where a pitcher throws both pitches of a shared column, my pitch is matched only if it is at least "
                                        "90% of his pitches in that column; otherwise it is dropped.",
                            "evidence": evidence},
        "floors": {"mine": f"{sb.MIN_SWINGS} swings with complete tracking in each season used", "fangraphs": "whatever the table holds (see limits)",
                   "savant": "as in the Savant benchmark"},
        "bootstrap": {"resamples": n_boot, "seed": seed, "unit": "pitcher", "interval": "2.5th to 97.5th percentile"},
        "weighting": "RMSE and fits weighted by sqrt(min swings in the two seasons), as in stuff.validate_holdout()",
        "coverage": coverage,
        "same_season": {str(s): same_season(frames[s], n_boot, seed) for s in seasons} | {"pooled": same_season(pooled, n_boot, seed)},
        "same_season_pooled_is": f"{season - 1} and {season}",
        "expected_vs_stuff_by_pitch_type": by_pitch_type(pooled, n_boot=n_boot, seed=seed),
        "stuff_vs_run_value_by_pitch_type": by_pitch_type(pooled, "stuff_plus", "sv_rv100", n_boot=n_boot, seed=seed),
        "expected_vs_whiff_by_pitch_type": by_pitch_type(pooled, "x_whiff_pct", "whiff_pct", n_boot=n_boot, seed=seed),
        "stuff_vs_whiff_by_pitch_type": by_pitch_type(pooled, "stuff_plus", "whiff_pct", n_boot=n_boot, seed=seed),
        "pitcher_level": pitcher_level(pd.concat([all_pitches[season - 1], all_pitches[season]], ignore_index=True), fg, n_boot, seed),
        "next_season": {"pair": f"{season - 1}->{season}", "pitches_in_savant_benchmark_test_set": int(len(plain)),
                        "pitches_with_stuff_plus": int(len(test)), "earlier_pair": f"{season - 2}->{season - 1}"}
                       | next_season(test, train, n_boot=n_boot, seed=seed)
                       | {"held_out": {
                           "fit": f"{season - 2}->{season - 1}", "scored": f"{season - 1}->{season}",
                           "test_pitches_from_pitchers_under_15_ip": int(len(short)),
                           "test_pitchers_under_15_ip": int(short["pitcher"].nunique()),
                           "15_ip_every_season": held_out(ip15(train_stuff), ip15(test), n_boot, seed),
                           "all_rows_in_the_tables": held_out(train_stuff, test, n_boot, seed)},
                          "cross_validated_by_pitcher_15_ip": {k: v for k, v in next_season(ip15(test), None, n_boot=n_boot, seed=seed)
                                                               ["cross_validated_by_pitcher"].items()}},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"edge-stuffplus-benchmark-{season}.json"
    path.write_text(json.dumps(result, indent=1, default=float))
    log(f"saved {path}")
    return result


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Benchmark expected whiff against FanGraphs Stuff+ by pitch type")
    ap.add_argument("season", type=int)
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    run(a.season, a.n, a.seed)
