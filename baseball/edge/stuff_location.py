"""Location-aware expected whiff: a second measure beside the stuff model, for pitches whose whiffs follow
where they are thrown.

  uv run python -m baseball.edge.stuff_location 2026

What it is. The stuff model (stuff.py) reads a swing from physics alone, and its grade means that and nothing
more. `stuff_checks.py` showed that sweeper whiffs follow location and count, which the stuff model leaves
out on purpose. This module fits a second model, the same way (same learner, cross-fit by pitcher within the
season), with four more inputs for each swing:

- where the pitch crossed the plate: sideways, signed so that positive is toward the hitter (`px_in`), and
  height as a share of that hitter's strike zone (`pz_rel`, 0 at the bottom, 1 at the top)
- the count when it was thrown (`balls`, `strikes`)

A pitch's location-aware expected whiff is the average over the swings it drew. It is NOT pure stuff.
Location is partly the pitcher's command, partly the catcher and the plan, and, because only swings are
counted, partly what hitters chose to swing at. The stuff grade keeps its meaning; this is a different number
with a different name.

Leakage. In the same season each pitcher's number comes from a model that never saw his swings. When it
predicts next season, every input comes from the earlier season: last year's physics and last year's
locations, never next year's.

The test. Weights fit on one pair of seasons and scored on the next (and the other way round as a second
look), for every pitch type, with intervals from resampling pitchers. The rule, set before scoring, is the
one `stuff_checks.py` uses: the measure is adopted for a pitch type only if it lowers held-out error there
with an interval that excludes zero, and it makes no pitch type clearly worse.

Outputs: reports/outputs/edge-stuff-location-<season>.json (aggregates only), and the pitch tables with both
measures in data/edge/<season>/stuff_loc_<season>.parquet (never committed).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from baseball.edge import savant_benchmark as sb
from baseball.edge import stuff

ROOT = Path(__file__).resolve().parents[2]
EDGE_DIR = ROOT / "data" / "edge"
OUT = ROOT / "reports" / "outputs"
MIN_SWINGS = 60
MIN_ROWS = 40
LOCATION = ["px_in", "pz_rel", "balls", "strikes"]
EXTRA_COLUMNS = ["plate_x", "plate_z", "sz_top", "sz_bot"]


def add_location(swings: pd.DataFrame) -> pd.DataFrame:
    """The four location and count inputs. Swings with no tracked location or strike zone are dropped."""
    s = swings.dropna(subset=["plate_x", "plate_z", "sz_top", "sz_bot", "balls", "strikes", "stand"]).copy()
    s = s[(s["sz_top"] - s["sz_bot"]) > 0.5]
    s["px_in"] = s["plate_x"] * np.where(s["stand"].eq("L"), 1.0, -1.0)     # catcher's view: a right-handed hitter stands on the negative side
    s["pz_rel"] = (s["plate_z"] - s["sz_bot"]) / (s["sz_top"] - s["sz_bot"])
    s["balls"], s["strikes"] = s["balls"].astype(float), s["strikes"].astype(float)
    return s


def both_tables(swings: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """One pitch table with both measures from the same swings: `x_whiff_pct` (physics) and `x_loc_pct`
    (physics, location and count). Each is cross-fit by pitcher."""
    x, d0 = stuff.fit_crossfit(swings)
    xl, d1 = stuff.fit_crossfit(swings, feature_list=stuff.FEATURES + LOCATION)
    t = stuff.pitch_table(swings, x)
    tl = stuff.pitch_table(swings, xl)[["pitcher", "pitch_type", "x_whiff_pct"]].rename(columns={"x_whiff_pct": "x_loc_pct"})
    return t.merge(tl, on=["pitcher", "pitch_type"]), {"auc_physics": d0["auc"], "auc_location": d1["auc"], "swings": d0["swings"]}


def same_season(table: pd.DataFrame, n_boot: int = 2000, seed: int = 7) -> dict:
    """Per pitch type, across pitchers with 60+ swings: r between each measure and the actual whiff rate."""
    t = table[table["swings"] >= MIN_SWINGS]
    return {pt: {"physics": sb.corr_row(g, "x_whiff_pct", "whiff_pct", None, n_boot, seed),
                 "location": sb.corr_row(g, "x_loc_pct", "whiff_pct", None, n_boot, seed)}
            for pt, g in t.groupby("pitch_type") if len(g) >= MIN_ROWS}


def pair(prev: pd.DataFrame, curr: pd.DataFrame) -> pd.DataFrame:
    """Pitches with 60+ swings in both seasons. Every predictor is the earlier season's; the outcome is the later one's."""
    keep = ["pitcher", "pitch_type", "swings", "whiff_pct", "x_whiff_pct", "x_loc_pct"]
    m = prev[prev["swings"] >= MIN_SWINGS][keep].merge(curr[curr["swings"] >= MIN_SWINGS][["pitcher", "pitch_type", "swings", "whiff_pct"]],
                                                       on=["pitcher", "pitch_type"], suffixes=("_prev", "_curr"))
    m = m.rename(columns={"x_whiff_pct": "x_whiff_pct_prev", "x_loc_pct": "x_loc_pct_prev"})
    return m.sort_values(["pitcher", "pitch_type"]).reset_index(drop=True)


MODELS = {"last_whiff": ["whiff_pct_prev"], "physics": ["x_whiff_pct_prev"], "location": ["x_loc_pct_prev"],
          "last+physics": ["whiff_pct_prev", "x_whiff_pct_prev"], "last+location": ["whiff_pct_prev", "x_loc_pct_prev"],
          "last+physics+location": ["whiff_pct_prev", "x_whiff_pct_prev", "x_loc_pct_prev"]}
CONTRASTS = [("location", "physics"), ("last+location", "last+physics"), ("last+physics+location", "last+physics"), ("last+location", "last_whiff")]


def errors(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """Squared held-out error of every model on every test pitch (weights fit on `train`), with the weight
    stuff.validate_holdout() uses."""
    def design(m, cols):
        return np.column_stack([np.ones(len(m))] + [m[c].to_numpy(float) for c in cols])

    out = test[["pitcher", "pitch_type"]].copy()
    out["w"] = sb.weights(test)
    wt = sb.weights(train)
    for name, cols in MODELS.items():
        c, *_ = np.linalg.lstsq(design(train, cols) * wt[:, None], train["whiff_pct_curr"].to_numpy(float) * wt, rcond=None)
        out[name] = (test["whiff_pct_curr"].to_numpy(float) - design(test, cols) @ c) ** 2
    return out


def by_type(err: pd.DataFrame, a: str, b: str, n_boot: int = 2000, seed: int = 7) -> dict:
    """Held-out RMSE of model `a` minus model `b`, on all pitches and by pitch type, with intervals from
    resampling pitchers. Negative means `a` is better."""
    def one(e):
        w, ea, eb = e["w"].to_numpy(), e[a].to_numpy(), e[b].to_numpy()
        rm = lambda v, i: float(np.sqrt(np.average(v[i], weights=w[i])))
        every = np.arange(len(e))
        lo, hi = sb.interval(rm(ea, i) - rm(eb, i) for i in sb.pitcher_draws(e["pitcher"], n_boot, seed))
        return {"pitches": int(len(e)), "rmse_first": rm(ea, every), "rmse_second": rm(eb, every), "diff": rm(ea, every) - rm(eb, every), "lo": lo, "hi": hi}

    out = {"all": one(err)}
    for pt, n in err["pitch_type"].value_counts().items():
        if n >= MIN_ROWS:
            out[pt] = one(err[err["pitch_type"] == pt].reset_index(drop=True))
    return out


def decide(comparison: dict) -> dict:
    """The rule: adopted for a pitch type only where its interval is below zero, and only if no pitch type is clearly worse."""
    types = {k: v for k, v in comparison.items() if k != "all"}
    better = sorted(k for k, v in types.items() if v["hi"] < 0)
    worse = sorted(k for k, v in types.items() if v["lo"] > 0)
    return {"clearly_better_on": better, "clearly_worse_on": worse, "adopted_for": [] if worse else better}


def held_out(train: pd.DataFrame, test: pd.DataFrame, n_boot: int = 2000, seed: int = 7) -> dict:
    err = errors(train, test)
    w = err["w"].to_numpy()
    out = {"train_pitches": int(len(train)), "test_pitches": int(len(test)), "test_pitchers": int(test["pitcher"].nunique()),
           "rmse": {m: float(np.sqrt(np.average(err[m], weights=w))) for m in MODELS},
           "contrasts": {f"{a} minus {b}": by_type(err, a, b, n_boot, seed) for a, b in CONTRASTS}}
    out["rule_alone"] = decide(out["contrasts"]["location minus physics"])
    out["rule_with_last_season"] = decide(out["contrasts"]["last+location minus last+physics"])
    out["r_with_next_season_whiff"] = {pt: {"pitches": int(len(g)), "physics": sb._r(g["x_whiff_pct_prev"], g["whiff_pct_curr"]),
                                            "location": sb._r(g["x_loc_pct_prev"], g["whiff_pct_curr"]), "last_whiff": sb._r(g["whiff_pct_prev"], g["whiff_pct_curr"])}
                                       for pt, g in test.groupby("pitch_type") if len(g) >= MIN_ROWS}
    return out


def run(season: int = 2026, n_boot: int = 2000, seed: int = 7, log=print) -> dict:
    from baseball.edge.run import COLUMNS
    from baseball.ingest.league import load_season
    from baseball.phases import phase

    seasons = [season - 2, season - 1, season]
    tables, diags, dropped = {}, {}, {}
    out_dir = EDGE_DIR / str(season)
    out_dir.mkdir(parents=True, exist_ok=True)
    for s in seasons:
        sw = stuff.prepare(phase(load_season(s, COLUMNS + EXTRA_COLUMNS)))
        loc = add_location(sw)
        dropped[str(s)] = int(len(sw) - len(loc))
        tables[s], diags[str(s)] = both_tables(loc)
        tables[s].to_parquet(out_dir / f"stuff_loc_{s}.parquet")
        log(f"{s}: AUC physics {diags[str(s)]['auc_physics']:.4f}, with location {diags[str(s)]['auc_location']:.4f}")
    a, b, c = seasons
    first, second = pair(tables[a], tables[b]), pair(tables[b], tables[c])
    carry = {}
    for (p, q), m in (((a, b), first), ((b, c), second)):
        full = tables[p][tables[p]["swings"] >= MIN_SWINGS].merge(tables[q][tables[q]["swings"] >= MIN_SWINGS], on=["pitcher", "pitch_type"], suffixes=("_p", "_q"))
        carry[f"{p}->{q}"] = {pt: {"pitches": int(len(g)), "physics": sb._r(g["x_whiff_pct_p"], g["x_whiff_pct_q"]), "location": sb._r(g["x_loc_pct_p"], g["x_loc_pct_q"]),
                                   "actual": sb._r(g["whiff_pct_p"], g["whiff_pct_q"])} for pt, g in full.groupby("pitch_type") if len(g) >= MIN_ROWS}
    result = {
        "source": f"python -m baseball.edge.stuff_location {season}, fresh fits on the regular-season pitch files.",
        "what_this_is": "A second measure beside the stuff model: expected whiff from physics plus where the pitch crossed the plate and the count. "
                        "It is not pure stuff. Location is partly command, partly the catcher and the plan, and partly which pitches hitters swung at.",
        "inputs_added": {"px_in": "plate_x signed so positive is toward the hitter", "pz_rel": "height as a share of the hitter's strike zone",
                         "balls": "balls in the count", "strikes": "strikes in the count"},
        "leakage": "Same season: cross-fit by pitcher. Next season: every predictor is the earlier season's.",
        "adoption_rule": "Adopted for a pitch type only if held-out RMSE drops there with a 95% interval (resampling pitchers) that excludes zero, "
                         "and no pitch type is clearly worse. Applied to the test fit on the first pair and scored on the second.",
        "bootstrap": {"resamples": n_boot, "seed": seed, "unit": "pitcher"},
        "fit": diags, "swings_dropped_for_missing_location": dropped,
        "same_season": {str(s): same_season(tables[s], n_boot, seed) for s in seasons},
        "measure_carry_over": carry,
        "held_out": {f"fit {a}->{b}, scored {b}->{c}": held_out(first, second, n_boot, seed),
                     f"fit {b}->{c}, scored {a}->{b}": held_out(second, first, n_boot, seed)},
    }
    main = result["held_out"][f"fit {a}->{b}, scored {b}->{c}"]
    result["decision"] = {"alone": main["rule_alone"], "with_last_season": main["rule_with_last_season"]}
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"edge-stuff-location-{season}.json"
    path.write_text(json.dumps(result, indent=1, default=float))
    log(f"saved {path}")
    return result


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Location-aware expected whiff: fit, same-season read and held-out test")
    ap.add_argument("season", type=int)
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    run(a.season, a.n, a.seed)
