"""Benchmark the expected-whiff model against Baseball Savant's public pitch leaderboards.

  uv run python -m baseball.edge.savant_benchmark 2026            (uses 2024 and 2025 as well)
  uv run python -m baseball.edge.savant_benchmark 2026 --pull     (download the leaderboard files first)
  uv run python -m baseball.edge.savant_benchmark 2026 --refit    (also repeat it on a fresh fit of the model)

What this is: a check against two public Savant tables, matched on MLBAM pitcher id and pitch type.
What this is not: a comparison with Stuff+. Savant publishes no stuff grade. The comparison with
FanGraphs' Stuff+ by pitch type is in `stuffplus_benchmark.py`.

The two Savant tables (each page's own "Download CSV" link):

- Pitch Arsenal Stats: whiff%, put-away%, xwOBA and run value per 100 pitches, by pitcher and pitch type.
  Savant's note on the page: run value and whiff% are per pitch, everything else is per plate appearance.
- Swing Timing + Miss Distance (bat tracking, added June 2026, data from the second half of 2023):
  miss distance is the gap in inches, at closest approach, between the ball and the barrel half of
  the bat. The pitch files carry it only on swings and misses, so the leaderboard figure is an
  average over misses. It says how far bats missed, given that they missed. It is a result, like
  whiff rate, and not a physics model.

Three questions, each answered on the same pitches:

1. Pipeline: does my whiff rate per pitcher-pitch match Savant's published whiff%?
2. Same season: how well does my expected whiff track Savant's miss distance and run value per 100?
3. Next season: which predicts next season's whiff rate better, my expected whiff, Savant's miss
   distance, or last season's whiff rate, alone and combined? Weights are fit on one pair of
   seasons and scored on the other, the way `stuff.validate_holdout()` does it, with the same
   weighting (sqrt of the smaller swing count) and intervals that resample pitchers.

Output: reports/outputs/edge-savant-benchmark-<season>.json (aggregates only). The downloaded files
stay in data/savant/ and are never committed.
"""
from __future__ import annotations

import io
import json
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from baseball.evaluation.arsenal import SWINGS, WHIFFS

ROOT = Path(__file__).resolve().parents[2]
SAVANT_DIR = ROOT / "data" / "savant"
EDGE_DIR = ROOT / "data" / "edge"
OUT = ROOT / "reports" / "outputs"

MIN_PITCHES_ARSENAL = 50     # Savant's "Min. Pitches" filter on Pitch Arsenal Stats
MIN_SWINGS_MISS = 50         # Savant's "Min. Total Swings" and "Min. Split Swings" on the miss-distance page
MIN_SWINGS = 60              # my floor in each season, the same one validate_holdout() uses

URLS = {
    "arsenal": ("https://baseballsavant.mlb.com/leaderboard/pitch-arsenal-stats"
                "?type=pitcher&pitchType=&year={season}&team=&min=1&minPitches=" + str(MIN_PITCHES_ARSENAL) + "&csv=true"),
    "miss": ("https://baseballsavant.mlb.com/leaderboard/bat-tracking/swing-timing-miss-distance"
             "?type=pitcher&season%5B%5D={season}&split%5B%5D=api_pitch_type_group03"
             "&min=" + str(MIN_SWINGS_MISS) + "&minSplit=" + str(MIN_SWINGS_MISS) + "&csv=true"),
}
PAGES = {
    "arsenal": "https://baseballsavant.mlb.com/leaderboard/pitch-arsenal-stats",
    "miss": "https://baseballsavant.mlb.com/leaderboard/bat-tracking/swing-timing-miss-distance",
}

# Savant's pitch-type codes are the Statcast codes my tables already use, so the mapping is the identity
# on these. Anything else (eephus, pitchouts, unclassified) is left out on both sides.
PITCH_TYPES = ("FF", "SI", "FC", "SL", "ST", "SV", "CU", "KC", "CH", "FS", "FO", "SC", "KN")


# ---------------------------------------------------------------------------------------------
# Download (one request per file) and load
# ---------------------------------------------------------------------------------------------

def csv_path(kind: str, season: int) -> Path:
    return SAVANT_DIR / f"savant_{kind}_{season}.csv"


def pull(seasons, refresh: bool = False, pause: float = 5.0, log=print) -> dict:
    """Download each leaderboard file once. A file already on disk is kept unless `refresh`.
    Any answer other than a CSV with rows stops the pull with the URL and the status; nothing is retried."""
    import requests

    SAVANT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = SAVANT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for season in seasons:
        for kind, template in URLS.items():
            path, url = csv_path(kind, season), template.format(season=season)
            if path.exists() and not refresh:
                continue
            r = requests.get(url, timeout=120, headers={"User-Agent": "baseball-research-script (one request per file)"})
            text = r.text.lstrip("﻿")
            if r.status_code != 200 or text.lstrip().startswith("<") or "," not in text.split("\n", 1)[0]:
                raise RuntimeError(f"Savant did not return a CSV: status {r.status_code} for {url}")
            rows = len(pd.read_csv(io.StringIO(text)))
            if rows == 0:
                raise RuntimeError(f"Savant returned an empty CSV: status {r.status_code} for {url}")
            path.write_text(text, encoding="utf-8")
            manifest[path.name] = {"url": url, "pulled": date.today().isoformat(), "rows": rows, "status": r.status_code}
            manifest_path.write_text(json.dumps(manifest, indent=1))
            log(f"{path.name}: {rows:,} rows")
            time.sleep(pause)
    return manifest


def load_savant(season: int) -> pd.DataFrame:
    """Both Savant files for a season as one frame keyed by pitcher and pitch type (Savant's codes).
    Columns: sv_whiff_pct, sv_rv100 (positive is good for the pitcher), sv_put_away, sv_xwoba, sv_pitches,
    sv_miss_in (inches), sv_swings (swings on the miss-distance page)."""
    a = pd.read_csv(csv_path("arsenal", season))
    a = a.rename(columns={"player_id": "pitcher", "whiff_percent": "sv_whiff_pct", "run_value_per_100": "sv_rv100",
                          "put_away": "sv_put_away", "est_woba": "sv_xwoba", "pitches": "sv_pitches"})
    a = a[["pitcher", "pitch_type", "sv_whiff_pct", "sv_rv100", "sv_put_away", "sv_xwoba", "sv_pitches"]]
    m = pd.read_csv(csv_path("miss", season))
    m = m.rename(columns={"id": "pitcher", "api_pitch_type": "pitch_type", "miss_distance": "sv_miss_in", "n_swings": "sv_swings"})
    m = m[["pitcher", "pitch_type", "sv_miss_in", "sv_swings"]]
    out = a.merge(m, on=["pitcher", "pitch_type"], how="outer")
    for c in out.columns.drop("pitch_type"):
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out[out["pitch_type"].isin(PITCH_TYPES)].drop_duplicates(["pitcher", "pitch_type"])
    return out.assign(pitcher=out["pitcher"].astype("int64")).reset_index(drop=True)


def savant_type(table: pd.DataFrame) -> pd.DataFrame:
    """Add `sv_type`, the code Savant files the pitch under. Savant's two leaderboards have no knuckle
    curve: it is filed under curveball, so KC maps to CU. A pitcher with both a KC and a CU row in one
    season cannot be matched to Savant's single curveball row, so both rows are dropped. Types Savant
    does not list are dropped."""
    t = table[table["pitch_type"].isin(PITCH_TYPES)].copy()
    t["sv_type"] = t["pitch_type"].replace({"KC": "CU"})
    clash = t.duplicated(["pitcher", "sv_type"], keep=False)
    return t[~clash]


def match(table: pd.DataFrame, savant: pd.DataFrame, min_swings: int = MIN_SWINGS) -> pd.DataFrame:
    """My pitch table (60+ swings) joined to Savant's rows on MLBAM pitcher id and pitch type."""
    t = savant_type(table[table["swings"] >= min_swings])
    t = t.assign(pitcher=t["pitcher"].astype("int64"))
    return t.merge(savant.rename(columns={"pitch_type": "sv_type"}), on=["pitcher", "sv_type"], how="inner")


def load_tables(seasons, edge_season: int, tables_dir: Path | None = None) -> dict[int, pd.DataFrame]:
    """The pitch tables `bb edge <edge_season>` saved (stuff_<season>.parquet): actual and expected whiff per pitch."""
    base = tables_dir or EDGE_DIR / str(edge_season)
    return {s: pd.read_parquet(base / f"stuff_{s}.parquet") for s in seasons}


def build_tables(seasons, out_dir: Path, log=print) -> dict[int, pd.DataFrame]:
    """Refit the expected-whiff model from the pitch files, the way `bb edge` does, and save the tables."""
    from baseball.edge import stuff
    from baseball.edge.run import COLUMNS
    from baseball.ingest.league import load_season
    from baseball.phases import phase

    out_dir.mkdir(parents=True, exist_ok=True)
    tables = {}
    for s in seasons:
        swings = stuff.prepare(phase(load_season(s, COLUMNS)))
        x, diag = stuff.fit_crossfit(swings)
        tables[s] = stuff.pitch_table(swings, x)
        tables[s].to_parquet(out_dir / f"stuff_{s}.parquet")
        log(f"{s}: {len(tables[s]):,} pitches, cross-fitted AUC {diag['auc']:.4f}")
    return tables


# ---------------------------------------------------------------------------------------------
# Statistics: correlations and intervals that resample pitchers
# ---------------------------------------------------------------------------------------------

def _r(u, v) -> float:
    u, v = np.asarray(u, float), np.asarray(v, float)
    if len(u) < 3 or np.std(u) == 0 or np.std(v) == 0:
        return float("nan")
    return float(np.corrcoef(u, v)[0, 1])


def pitcher_draws(pitchers, n_boot: int, seed: int):
    """Row positions for `n_boot` resamples of pitchers (all of a pitcher's rows travel together)."""
    pitchers = np.asarray(pitchers)
    ids, inverse = np.unique(pitchers, return_inverse=True)
    order = np.argsort(inverse, kind="stable")
    rows = np.split(order, np.cumsum(np.bincount(inverse))[:-1])
    rng = np.random.default_rng(seed)
    for _ in range(n_boot):
        yield np.concatenate([rows[i] for i in rng.integers(0, len(ids), len(ids))])


def interval(values) -> tuple[float, float]:
    v = np.asarray([x for x in values if np.isfinite(x)], float)
    if not len(v):
        return float("nan"), float("nan")
    return float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))


def center(values: np.ndarray, codes: np.ndarray) -> np.ndarray:
    """Values with their group mean removed (pitch type within season), so a correlation compares
    like with like: four-seamers with four-seamers, sliders with sliders."""
    sums = np.bincount(codes, weights=values, minlength=codes.max() + 1)
    counts = np.bincount(codes, minlength=codes.max() + 1)
    return values - (sums / np.maximum(counts, 1))[codes]


def corr_row(frame: pd.DataFrame, a: str, b: str, by=None, n_boot: int = 2000, seed: int = 7) -> dict:
    """Pearson r between two columns with a 95% interval from resampling pitchers. With `by`, both
    columns are centered within those groups first (and again inside every resample)."""
    f = frame.dropna(subset=[a, b]).reset_index(drop=True)
    u, v = f[a].to_numpy(float), f[b].to_numpy(float)
    codes = f.groupby(by).ngroup().to_numpy() if by else None

    def stat(idx):
        if codes is None:
            return _r(u[idx], v[idx])
        return _r(center(u[idx], codes[idx]), center(v[idx], codes[idx]))

    lo, hi = interval(stat(idx) for idx in pitcher_draws(f["pitcher"], n_boot, seed))
    return {"n": int(len(f)), "pitchers": int(f["pitcher"].nunique()), "r": stat(np.arange(len(f))), "lo": lo, "hi": hi}


# ---------------------------------------------------------------------------------------------
# 1. Pipeline check
# ---------------------------------------------------------------------------------------------

def raw_counts(pitches: pd.DataFrame) -> pd.DataFrame:
    """Swing and whiff counts per pitcher and pitch type straight from regular-season pitch rows, under
    my definition (foul tips and missed bunts are whiffs, bunt attempts are swings) and with foul tips
    taken out of the whiffs, plus the average miss distance on the rows that carry one."""
    p = pitches.dropna(subset=["pitch_type"])
    d = p["description"]
    p = p.assign(swing=d.isin(SWINGS), whiff=d.isin(WHIFFS), foul_tip=d.eq("foul_tip"),
                 miss=p["miss_distance"] if "miss_distance" in p else np.nan)
    g = p.groupby(["pitcher", "pitch_type"])
    out = g.agg(pitches=("swing", "size"), swings=("swing", "sum"), whiffs=("whiff", "sum"), foul_tips=("foul_tip", "sum"),
                miss_in=("miss", "mean"), misses_measured=("miss", "count")).reset_index()
    out["whiff_pct"] = 100 * out["whiffs"] / out["swings"]
    out["whiff_pct_no_foul_tips"] = 100 * (out["whiffs"] - out["foul_tips"]) / out["swings"]
    return out


def agreement(mine, theirs, tol: float) -> dict:
    """How closely two columns agree: mean and largest absolute difference, the share within `tol`, and r."""
    mine, theirs = np.asarray(mine, float), np.asarray(theirs, float)
    keep = np.isfinite(mine) & np.isfinite(theirs)
    e = np.abs(mine[keep] - theirs[keep])
    if not len(e):
        return {"n": 0, "tol": tol}
    return {"n": int(keep.sum()), "mean_abs_diff": float(e.mean()), "max_abs_diff": float(e.max()),
            "share_within_tol": float((e <= tol).mean()), "tol": tol, "mean_diff": float((mine[keep] - theirs[keep]).mean()),
            "r": _r(mine[keep], theirs[keep])}


def pipeline_check(table: pd.DataFrame, savant: pd.DataFrame, raw: pd.DataFrame | None = None) -> dict:
    """Savant prints whiff% to one decimal, so a perfect match still differs by up to 0.05."""
    tol = 0.0501
    m = match(table, savant).dropna(subset=["sv_whiff_pct"])
    out = {"model_table_vs_savant": agreement(m["whiff_pct"], m["sv_whiff_pct"], tol),
           "off_by_more_than_1_point": int((np.abs(m["whiff_pct"] - m["sv_whiff_pct"]) > 1).sum())}
    if raw is not None:
        r = match(raw, savant).dropna(subset=["sv_whiff_pct"])
        out["pitch_files_vs_savant"] = agreement(r["whiff_pct"], r["sv_whiff_pct"], tol)
        out["pitch_files_without_foul_tips_vs_savant"] = agreement(r["whiff_pct_no_foul_tips"], r["sv_whiff_pct"], tol)
        out["pitch_count_equal_share"] = float((r["pitches"] == r["sv_pitches"]).mean())
        d = r[r["misses_measured"] >= 10].dropna(subset=["sv_miss_in"])
        out["miss_distance_pitch_files_vs_savant"] = agreement(d["miss_in"], d["sv_miss_in"], 0.1)
    return out


# ---------------------------------------------------------------------------------------------
# 2. Same-season benchmark
# ---------------------------------------------------------------------------------------------

SAME_SEASON_PAIRS = [("x_whiff_pct", "sv_miss_in"), ("x_whiff_pct", "sv_rv100"), ("x_whiff_pct", "sv_whiff_pct"),
                     ("whiff_pct", "sv_miss_in"), ("whiff_pct", "sv_rv100"), ("sv_miss_in", "sv_rv100")]


def same_season(matched: pd.DataFrame, n_boot: int = 2000, seed: int = 7) -> dict:
    """Correlations on one frame of matched pitches (one season, or seasons stacked with a `season` column).
    `raw` pools every pitch type; `within_pitch_type` centers both columns by pitch type and season."""
    by = ["season", "sv_type"] if "season" in matched else ["sv_type"]
    return {f"{a} ~ {b}": {"raw": corr_row(matched, a, b, None, n_boot, seed),
                           "within_pitch_type": corr_row(matched, a, b, by, n_boot, seed)}
            for a, b in SAME_SEASON_PAIRS}


# ---------------------------------------------------------------------------------------------
# 3. Next season's whiff rate
# ---------------------------------------------------------------------------------------------

TYPE_GROUPS = ("FF", "SI", "FC", "SL", "ST", "CU", "CH", "FS")   # everything else shares the base intercept

MODELS = {
    "last_whiff": ["whiff_pct_prev"],                                   # the regressed baseline
    "expected": ["x_whiff_pct_prev"],
    "miss": ["sv_miss_in_prev"],
    "expected+type": ["x_whiff_pct_prev", "TYPE"],
    "miss+type": ["sv_miss_in_prev", "TYPE"],
    "expected+miss": ["x_whiff_pct_prev", "sv_miss_in_prev"],
    "last+expected": ["whiff_pct_prev", "x_whiff_pct_prev"],           # the published blend
    "last+miss": ["whiff_pct_prev", "sv_miss_in_prev"],
    "last+expected+type": ["whiff_pct_prev", "x_whiff_pct_prev", "TYPE"],
    "last+miss+type": ["whiff_pct_prev", "sv_miss_in_prev", "TYPE"],
    "last+expected+miss": ["whiff_pct_prev", "x_whiff_pct_prev", "sv_miss_in_prev"],
}
CONTRASTS = [("expected", "miss"), ("expected+type", "miss+type"), ("last+expected", "last+miss"),
             ("last+expected+type", "last+miss+type"), ("last+expected+miss", "last+expected"), ("last+expected+miss", "last+miss")]

# "+type" gives a model one intercept per pitch type. Miss distance has no idea what pitch it is looking at
# (a four-seamer misses by about an inch, a breaking ball by several), and MLB's own explainer says to read
# it within pitch type, so the "+type" rows are the fair read of miss distance. Expected whiff already
# knows the pitch's shape, so "+type" changes it less.
VERDICTS = {"alone": ("expected", "miss"), "alone_given_pitch_type": ("expected+type", "miss+type"),
            "with_last_season": ("last+expected", "last+miss"), "with_last_season_given_pitch_type": ("last+expected+type", "last+miss+type")}


def pair(prev: pd.DataFrame, curr: pd.DataFrame, savant_prev: pd.DataFrame, min_swings: int = MIN_SWINGS) -> pd.DataFrame:
    """Pitches with 60+ swings in both seasons and a Savant miss distance in the earlier one. Every
    model is fit and scored on this one set."""
    p = match(prev, savant_prev, min_swings).dropna(subset=["sv_miss_in"])
    c = savant_type(curr[curr["swings"] >= min_swings]).assign(pitcher=lambda d: d["pitcher"].astype("int64"))
    keep = ["pitcher", "sv_type", "swings", "whiff_pct", "x_whiff_pct", "sv_miss_in"]
    m = p[keep].merge(c[["pitcher", "sv_type", "swings", "whiff_pct"]], on=["pitcher", "sv_type"], suffixes=("_prev", "_curr"))
    return m.rename(columns={"x_whiff_pct": "x_whiff_pct_prev", "sv_miss_in": "sv_miss_in_prev"}).reset_index(drop=True)


def design(m: pd.DataFrame, cols) -> np.ndarray:
    parts = [np.ones(len(m))]
    for c in cols:
        if c == "TYPE":
            parts += [m["sv_type"].eq(t).to_numpy(float) for t in TYPE_GROUPS]
        else:
            parts.append(m[c].to_numpy(float))
    return np.column_stack(parts)


def weights(m: pd.DataFrame) -> np.ndarray:
    """Same weighting as stuff.validate_holdout(): sqrt of the smaller of the two seasons' swing counts."""
    return np.sqrt(np.minimum(m["swings_prev"], m["swings_curr"]).to_numpy(float))


def fit(m: pd.DataFrame, cols) -> np.ndarray:
    w = weights(m)
    c, *_ = np.linalg.lstsq(design(m, cols) * w[:, None], m["whiff_pct_curr"].to_numpy(float) * w, rcond=None)
    return c


def rmse(y, pred, w) -> float:
    return float(np.sqrt(np.average((np.asarray(y, float) - np.asarray(pred, float)) ** 2, weights=w)))


def next_season(train: pd.DataFrame, test: pd.DataFrame, n_boot: int = 2000, seed: int = 7) -> dict:
    """Fit every model's weights on `train` (one pair of seasons) and score them on `test` (another pair),
    so no weight has seen the outcomes it is scored on. Gains are against the regressed last-season
    baseline. Intervals resample pitchers in the test pair with the weights held fixed."""
    y, w = test["whiff_pct_curr"].to_numpy(float), weights(test)
    coefs = {name: fit(train, cols) for name, cols in MODELS.items()}
    preds = {name: design(test, cols) @ coefs[name] for name, cols in MODELS.items()}
    scores = {name: rmse(y, p, w) for name, p in preds.items()}
    base = scores["last_whiff"]

    boot = {name: [] for name in MODELS}
    for idx in pitcher_draws(test["pitcher"], n_boot, seed):
        for name in MODELS:
            boot[name].append(rmse(y[idx], preds[name][idx], w[idx]))
    boot = {k: np.asarray(v) for k, v in boot.items()}

    models = {}
    for name, cols in MODELS.items():
        gain = 100 * (1 - boot[name] / boot["last_whiff"])
        lo, hi = interval(gain)
        models[name] = {"rmse": scores[name], "r": _r(preds[name], y), "gain_vs_baseline_pct": 100 * (1 - scores[name] / base),
                        "gain_lo": lo, "gain_hi": hi,
                        "weights": {k: float(v) for k, v in zip(["intercept"] + [c for c in cols if c != "TYPE"], coefs[name])}}
    contrasts = {}
    for a, b in CONTRASTS:
        lo, hi = interval(boot[a] - boot[b])
        contrasts[f"{a} minus {b}"] = {"rmse_diff": scores[a] - scores[b], "lo": lo, "hi": hi,
                                        "share_of_resamples_first_is_better": float((boot[a] < boot[b]).mean())}
    alone = {c: corr_row(test.assign(y=y), c, "y", None, n_boot, seed) for c in ("x_whiff_pct_prev", "sv_miss_in_prev", "whiff_pct_prev")}
    alone["sv_miss_in_prev, within pitch type"] = corr_row(test.assign(y=y), "sv_miss_in_prev", "y", ["sv_type"], n_boot, seed)
    alone["x_whiff_pct_prev, within pitch type"] = corr_row(test.assign(y=y), "x_whiff_pct_prev", "y", ["sv_type"], n_boot, seed)
    return {"train_pitches": int(len(train)), "test_pitches": int(len(test)), "test_pitchers": int(test["pitcher"].nunique()),
            "rmse_raw_last_season": rmse(y, test["whiff_pct_prev"], w), "models": models, "contrasts": contrasts,
            "r_with_next_season_whiff": alone}


def verdict(result: dict, a: str = "expected", b: str = "miss") -> str:
    """Which of two models won on the test pair: the interval on the RMSE difference has to exclude zero."""
    c = result["contrasts"][f"{a} minus {b}"]
    if c["hi"] < 0:
        return a
    if c["lo"] > 0:
        return b
    return "tie"


# ---------------------------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------------------------

def analyse(tables: dict[int, pd.DataFrame], savant: dict[int, pd.DataFrame], raws: dict[int, pd.DataFrame] | None = None,
            n_boot: int = 2000, seed: int = 7) -> dict:
    seasons = sorted(tables)
    matched = {s: match(tables[s], savant[s]).assign(season=s) for s in seasons}
    out = {"pipeline": {}, "same_season": {}, "next_season": {}, "matched_counts": {}}
    for s in seasons:
        floor = tables[s][tables[s]["swings"] >= MIN_SWINGS]
        out["matched_counts"][str(s)] = {
            "my_pitches_60_swings": int(len(floor)), "after_type_rule": int(len(savant_type(floor))),
            "knuckle_curves_mapped_to_CU": int(savant_type(floor)["pitch_type"].eq("KC").sum()),
            "matched_to_savant": int(len(matched[s])), "with_miss_distance": int(matched[s]["sv_miss_in"].notna().sum()),
            "with_run_value": int(matched[s]["sv_rv100"].notna().sum())}
        out["pipeline"][str(s)] = pipeline_check(tables[s], savant[s], None if raws is None else raws[s])
        out["same_season"][str(s)] = same_season(matched[s], n_boot, seed)
    pooled = pd.concat(matched.values(), ignore_index=True)
    out["same_season"]["pooled"] = same_season(pooled, n_boot, seed)
    by_type = pooled.dropna(subset=["sv_miss_in"]).groupby("sv_type")["sv_miss_in"].agg(["size", "mean"])
    out["miss_distance_by_type"] = {t: {"pitches": int(r["size"]), "mean_in": float(r["mean"])} for t, r in by_type.iterrows()}
    pairs = {(a, b): pair(tables[a], tables[b], savant[a]) for a, b in zip(seasons, seasons[1:])}
    keys = list(pairs)
    if len(keys) >= 2:
        (a0, b0), (a1, b1) = keys[-2], keys[-1]
        fwd = next_season(pairs[(a0, b0)], pairs[(a1, b1)], n_boot, seed)
        rev = next_season(pairs[(a1, b1)], pairs[(a0, b0)], n_boot, seed)
        out["next_season"][f"fit {a0}->{b0}, scored {a1}->{b1}"] = fwd | {"winner": {k: verdict(fwd, *v) for k, v in VERDICTS.items()}}
        out["next_season"][f"fit {a1}->{b1}, scored {a0}->{b0}"] = rev | {"winner": {k: verdict(rev, *v) for k, v in VERDICTS.items()}}
    return out


def run(season: int = 2026, do_pull: bool = False, n_boot: int = 2000, seed: int = 7, refit: bool = False, log=print) -> dict:
    """The whole benchmark for `season` and the two before it. With `refit`, the model is also fit again
    from the pitch files into data/edge/<season>/refit/ and the analysis repeated on that fit."""
    from baseball.ingest.league import load_season
    from baseball.phases import phase

    seasons = [season - 2, season - 1, season]
    if do_pull:
        pull(seasons, log=log)
    if refit:
        build_tables(seasons, EDGE_DIR / str(season) / "refit", log)
    manifest = json.loads((SAVANT_DIR / "manifest.json").read_text())
    savant = {s: load_savant(s) for s in seasons}
    tables = load_tables(seasons, season)
    raws = {s: raw_counts(phase(load_season(s, ["pitcher", "pitch_type", "description", "miss_distance", "game_type"]))) for s in seasons}
    log("tables and Savant files loaded")
    result = {
        "source": f"python -m baseball.edge.savant_benchmark {season}, on the bb edge {season} pitch tables (stuff_<season>.parquet), "
                  "the regular-season pitch files, and Baseball Savant's leaderboard CSV downloads.",
        "what_this_is": "A benchmark against Baseball Savant's public leaderboards (Pitch Arsenal Stats, Swing Timing + Miss Distance). "
                        "It is not a comparison with Stuff+; that one is in edge-stuffplus-benchmark-<season>.json.",
        "savant_files": {name: manifest[name] for name in sorted(manifest)
                         if any(name == csv_path(k, s).name for k in URLS for s in seasons)},
        "savant_pages": PAGES,
        "matching": {"key": "MLBAM pitcher id and pitch type",
                     "pitch_types": "Statcast codes as they are (FF SI FC SL ST SV CU CH FS FO SC KN). Savant files knuckle curves under "
                                    "curveball, so my KC rows match Savant's CU row; a pitcher with both KC and CU in a season is dropped. "
                                    "Other codes are dropped.",
                     "my_floor": f"{MIN_SWINGS} swings with complete tracking in each season used",
                     "savant_floor": f"{MIN_PITCHES_ARSENAL} pitches (Pitch Arsenal Stats); {MIN_SWINGS_MISS} swings on the pitch type and "
                                     f"{MIN_SWINGS_MISS} in total (Swing Timing + Miss Distance)"},
        "definitions": {"my_whiff_pct": "swinging strikes, blocked swinging strikes, foul tips and missed bunts, over all swings (bunt attempts included)",
                        "sv_whiff_pct": "Savant whiff%, printed to one decimal",
                        "sv_miss_in": "Savant miss distance: average inches between ball and barrel half of the bat on swings and misses",
                        "sv_rv100": "Savant run value per 100 pitches; positive is good for the pitcher",
                        "x_whiff_pct": "my expected whiff rate from pitch physics, cross-fit by pitcher within the season"},
        "bootstrap": {"resamples": n_boot, "seed": seed, "unit": "pitcher", "interval": "2.5th to 97.5th percentile"},
        "weighting": "RMSE and fits weighted by sqrt(min swings in the two seasons), as in stuff.validate_holdout()",
    }
    result.update(analyse(tables, savant, raws, n_boot, seed))
    refit_dir = EDGE_DIR / str(season) / "refit"
    if all((refit_dir / f"stuff_{s}.parquet").exists() for s in seasons):
        log("repeating on a fresh refit of the model")
        refit = analyse(load_tables(seasons, season, refit_dir), savant, None, n_boot, seed)
        key = next(iter(refit["next_season"]))
        rows = pd.concat([tables[s].assign(season=s) for s in seasons]).merge(
            pd.concat([pd.read_parquet(refit_dir / f"stuff_{s}.parquet").assign(season=s) for s in seasons]),
            on=["season", "pitcher", "pitch_type"], suffixes=("", "_refit"))
        result["refit_check"] = {
            "what": "The same analysis on a second fit of the model from the same pitch files. Swing and whiff counts are identical; "
                    "expected whiff differs a little by pitch because the fit is not bit-for-bit repeatable across machines.",
            "x_whiff_r_between_fits": _r(rows["x_whiff_pct"], rows["x_whiff_pct_refit"]),
            "x_whiff_mean_abs_diff": float((rows["x_whiff_pct"] - rows["x_whiff_pct_refit"]).abs().mean()),
            "same_season_pooled": {k: v for k, v in refit["same_season"]["pooled"].items() if k.startswith("x_whiff_pct")},
            "next_season": {key: {"models": {k: {"rmse": v["rmse"], "gain_vs_baseline_pct": v["gain_vs_baseline_pct"]}
                                             for k, v in refit["next_season"][key]["models"].items()},
                                  "contrasts": refit["next_season"][key]["contrasts"],
                                  "winner": refit["next_season"][key]["winner"]}},
        }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"edge-savant-benchmark-{season}.json"
    path.write_text(json.dumps(result, indent=1, default=float))
    log(f"saved {path}")
    return result


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Benchmark expected whiff against Baseball Savant's public leaderboards")
    ap.add_argument("season", type=int)
    ap.add_argument("--pull", action="store_true", help="download the Savant leaderboard files first (one request per file)")
    ap.add_argument("--refit", action="store_true", help="also fit the model again from the pitch files and repeat the analysis on it")
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    run(a.season, a.pull, a.n, a.seed, a.refit)
