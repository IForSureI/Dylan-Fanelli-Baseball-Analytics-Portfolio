"""Why the expected-whiff model is weak on sweepers, whether a principled change fixes it, and how much a
refit moves the numbers.

  uv run python -m baseball.edge.stuff_checks 2026

The Stuff+ benchmark found that my expected whiff barely tracks the actual whiff rate on sweepers. This
module asks why, from the pitch data alone. Nothing here looks at Stuff+.

1. Where the model is weak: for each pitch type, the correlation between expected and actual whiff rate
   across pitchers, how well it ranks single swings (AUC inside the type), and the split by hitter side.
2. What sweeper whiffs follow: correlations across sweeper pitchers between the actual whiff rate and
   (a) every physical input the model has and (b) how the pitch is used (chase share, two-strike share,
   same-side share), which the model leaves out on purpose.
3. Candidate fixes, each a change with a baseball reason, each judged out of sample. The rule was set
   before scoring: a change is adopted only if it lowers the held-out error on sweepers (weights fit on
   one pair of seasons, scored on the next; interval from resampling pitchers must exclude zero) and makes
   no other pitch type worse by the same test.
     - pitch type as an input (is the sweeper being read as a slider?)
     - the primary fastball's velocity as an input (a harder fastball makes a breaking ball play up)
     - the primary fastball's velocity and shape as inputs
     - a model fit on sweepers only (is the pooled model drowning them out?)
4. Refit noise: the same swings in a different row order. The cross-fit folds and the model's binning both
   depend on row order, so two fits of the same data differ a little.

Every fit here is made fresh from the pitch files, so its numbers sit within refit noise of the saved
pitch tables, not exactly on them.

Output: reports/outputs/edge-stuff-checks-<season>.json (aggregates only).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from baseball.edge import savant_benchmark as sb
from baseball.edge import stuff

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "outputs"
MIN_SWINGS = 60
MIN_ROWS = 40          # a pitch type is reported when it has 40+ pitcher rows
PHYSICS = ["velo", "ivb_in", "hb_arm_in", "spin", "ext_ft", "rel_z_ft", "rel_x_arm_ft", "arm_angle", "d_velo", "d_ivb", "d_hb", "fb_velo"]
USAGE = ["chase_share", "two_strike_share", "same_side_share"]
VARIANTS = {
    "base": stuff.FEATURES,
    "pitch_type": stuff.FEATURES + ["type_code"],
    "fastball_velocity": stuff.FEATURES + ["fb_velo"],
    "fastball_velocity_and_shape": stuff.FEATURES + ["fb_velo", "fb_ivb", "fb_hb"],
}


def add_inputs(swings: pd.DataFrame) -> pd.DataFrame:
    """The extra columns the candidate models and the usage read need. The primary fastball's own velocity
    and shape are the pitch's value minus its difference from that fastball."""
    s = swings.copy()
    s["fb_velo"] = s["velo"] - s["d_velo"]
    s["fb_ivb"] = s["ivb_in"] - s["d_ivb"]
    s["fb_hb"] = s["hb_arm_in"] - s["d_hb"]
    codes = {t: i for i, t in enumerate(sorted(stuff.FASTBALL_TYPES + ("SL", "ST", "SV", "CU", "KC", "CH", "FS", "FO", "SC", "KN")))}
    s["type_code"] = s["pitch_type"].map(codes).fillna(len(codes)).astype(float)
    s["chase"] = (s["zone"] > 9).astype(float)
    s["two_strikes"] = (s["strikes"] == 2).astype(float)
    return s


def pitch_rows(swings: pd.DataFrame, x: pd.Series, min_swings: int = MIN_SWINGS) -> pd.DataFrame:
    """One row per pitcher and pitch type with 60+ swings: actual and expected whiff%, the model's physical
    inputs averaged over his swings, and how the pitch was used."""
    s = swings.assign(x=x)
    agg = {"swings": ("whiff", "size"), "whiff_pct": ("whiff", "mean"), "x_whiff_pct": ("x", "mean"),
           "chase_share": ("chase", "mean"), "two_strike_share": ("two_strikes", "mean"), "same_side_share": ("same_hand", "mean")}
    agg |= {c: (c, "mean") for c in PHYSICS}
    t = s.groupby(["pitcher", "pitch_type"]).agg(**agg).reset_index()
    t[["whiff_pct", "x_whiff_pct"]] *= 100
    return t[t["swings"] >= min_swings].reset_index(drop=True)


def fit_by_type(rows: pd.DataFrame, swings: pd.DataFrame, x: pd.Series) -> dict:
    """Per pitch type: r between expected and actual whiff% across pitchers, and the AUC of the swing-level
    prediction inside the type (can it tell a whiff from contact on that pitch at all?)."""
    out = {}
    s = swings.assign(x=x)
    for pt, g in rows.groupby("pitch_type"):
        if len(g) < MIN_ROWS:
            continue
        sw = s[s["pitch_type"] == pt]
        out[pt] = {"pitchers": int(len(g)), "r_expected_actual": sb._r(g["x_whiff_pct"], g["whiff_pct"]),
                   "sd_expected": float(g["x_whiff_pct"].std()), "sd_actual": float(g["whiff_pct"].std()),
                   "mean_expected": float(g["x_whiff_pct"].mean()), "mean_actual": float(g["whiff_pct"].mean()),
                   "swing_auc": float(roc_auc_score(sw["whiff"], sw["x"]))}
    return out


def by_hitter_side(swings: pd.DataFrame, x: pd.Series, pitch_type: str, min_swings: int = 40) -> dict:
    """The same pitcher-level correlation with the swings split by hitter side (40+ swings on that side)."""
    s = swings.assign(x=x)
    s = s[s["pitch_type"] == pitch_type]
    out = {}
    for label, flag in (("same_side", 1), ("opposite_side", 0)):
        d = s[s["same_hand"] == flag]
        t = d.groupby("pitcher").agg(n=("whiff", "size"), w=("whiff", "mean"), x=("x", "mean"))
        t = t[t["n"] >= min_swings]
        out[label] = {"pitchers": int(len(t)), "r_expected_actual": sb._r(t["x"], t["w"]),
                      "mean_actual": float(100 * d["whiff"].mean()), "mean_expected": float(100 * d["x"].mean())}
    return out


def correlates(rows: pd.DataFrame, pitch_type: str, n_boot: int = 2000, seed: int = 7) -> dict:
    """Across pitchers who throw `pitch_type` (rows from several seasons stacked, centered by season): r between
    the actual whiff rate and each physical input, each usage measure, and the model's expected whiff."""
    g = rows[rows["pitch_type"] == pitch_type]
    by = ["season"] if "season" in g else None
    out = {c: sb.corr_row(g, c, "whiff_pct", by, n_boot, seed) for c in ["x_whiff_pct", *PHYSICS, *USAGE]}
    out["strongest_physical_input"] = max(PHYSICS, key=lambda c: abs(out[c]["r"]))
    out["what_expected_whiff_follows"] = {c: sb.corr_row(g, c, "x_whiff_pct", by, 0, seed)["r"] for c in PHYSICS}
    return out


def carry_over(prev: pd.DataFrame, curr: pd.DataFrame) -> dict:
    """Per pitch type, on pitches with 60+ swings in both seasons: does the actual whiff rate carry over, and
    does last season's expected whiff see next season's actual?"""
    m = prev.merge(curr, on=["pitcher", "pitch_type"], suffixes=("_prev", "_curr"))
    return {pt: {"pitches": int(len(g)), "r_actual_actual": sb._r(g["whiff_pct_prev"], g["whiff_pct_curr"]),
                 "r_expected_next_actual": sb._r(g["x_whiff_pct_prev"], g["whiff_pct_curr"])}
            for pt, g in m.groupby("pitch_type") if len(g) >= MIN_ROWS}


def blend_errors(train_prev, train_curr, test_prev, test_curr) -> pd.DataFrame:
    """The published projection (last season's whiff% plus expected whiff%), weights fit on the train pair,
    with its squared error on every pitch of the test pair. Same weighting as stuff.validate_holdout()."""
    def pair(a, b):
        m = a.merge(b, on=["pitcher", "pitch_type"], suffixes=("_prev", "_curr"))
        return m.sort_values(["pitcher", "pitch_type"]).reset_index(drop=True)

    def design(m):
        return np.column_stack([np.ones(len(m)), m["whiff_pct_prev"], m["x_whiff_pct_prev"]])

    tr, te = pair(train_prev, train_curr), pair(test_prev, test_curr)
    w = np.sqrt(np.minimum(tr["swings_prev"], tr["swings_curr"]).to_numpy(float))
    c, *_ = np.linalg.lstsq(design(tr) * w[:, None], tr["whiff_pct_curr"].to_numpy(float) * w, rcond=None)
    te["w"] = np.sqrt(np.minimum(te["swings_prev"], te["swings_curr"]).to_numpy(float))
    te["sq_err"] = (te["whiff_pct_curr"] - design(te) @ c) ** 2
    return te[["pitcher", "pitch_type", "w", "sq_err"]]


def compare_errors(base: pd.DataFrame, other: pd.DataFrame, n_boot: int = 2000, seed: int = 7) -> dict:
    """Held-out RMSE of a candidate minus the base model's, on all pitches and by pitch type, with a 95%
    interval from resampling pitchers. Negative means the candidate is better. `verdict` applies the rule."""
    assert (base["pitcher"].to_numpy() == other["pitcher"].to_numpy()).all() and (base["pitch_type"].to_numpy() == other["pitch_type"].to_numpy()).all()

    def one(mask):
        b, o = base[mask], other[mask]
        w, eb, eo = b["w"].to_numpy(), b["sq_err"].to_numpy(), o["sq_err"].to_numpy()
        rm = lambda e, i: float(np.sqrt(np.average(e[i], weights=w[i])))
        every = np.arange(len(b))
        lo, hi = sb.interval(rm(eo, i) - rm(eb, i) for i in sb.pitcher_draws(b["pitcher"], n_boot, seed))
        return {"pitches": int(len(b)), "rmse_base": rm(eb, every), "rmse_candidate": rm(eo, every),
                "diff": rm(eo, every) - rm(eb, every), "lo": lo, "hi": hi}

    out = {"all": one(np.ones(len(base), bool))}
    for pt, n in base["pitch_type"].value_counts().items():
        if n >= MIN_ROWS:
            out[pt] = one((base["pitch_type"] == pt).to_numpy())
    return out


def verdict(comparison: dict, target: str = "ST") -> dict:
    """The adoption rule: better on the target type with an interval that excludes zero, and no type clearly worse."""
    helps = comparison[target]["hi"] < 0
    hurts = sorted(k for k, v in comparison.items() if v["lo"] > 0)
    return {"helps_target": bool(helps), "clearly_worse_on": hurts, "adopt": bool(helps and not hurts)}


def row_order_check(swings: pd.DataFrame, base_x: pd.Series, seed: int = 1) -> dict:
    """Fit the same swings again in other row orders and measure how far each pitch's expected whiff% moves."""
    t0 = stuff.pitch_table(swings, base_x).set_index(["pitcher", "pitch_type"])["x_whiff_pct"]
    orders = {"shuffled": swings.sample(frac=1, random_state=seed), "reversed": swings.iloc[::-1],
              "by_game_and_pitch": swings.sort_values(["game_pk", "at_bat_number", "pitch_number"])}
    out = {}
    for name, s in orders.items():
        x, diag = stuff.fit_crossfit(s)
        t = stuff.pitch_table(s, x).set_index(["pitcher", "pitch_type"])["x_whiff_pct"].reindex(t0.index)
        out[name] = {"auc": diag["auc"], "mean_abs_move": float((t - t0).abs().mean()), "max_abs_move": float((t - t0).abs().max()), "r": sb._r(t, t0)}
    return out


def run(season: int = 2026, n_boot: int = 2000, seed: int = 7, log=print) -> dict:
    from baseball.edge.run import COLUMNS
    from baseball.ingest.league import load_season
    from baseball.phases import phase

    seasons = [season - 2, season - 1, season]
    tables = {name: {} for name in VARIANTS}
    rows, by_type, sides, aucs, sweeper_swings = {}, {}, {}, {name: {} for name in VARIANTS}, []
    order = None
    for s in seasons:
        sw = add_inputs(stuff.prepare(phase(load_season(s, COLUMNS))))
        for name, cols in VARIANTS.items():
            x, diag = stuff.fit_crossfit(sw, feature_list=cols)
            t = stuff.pitch_table(sw, x)
            tables[name][s] = t[t["swings"] >= MIN_SWINGS]
            aucs[name][str(s)] = diag["auc"]
            if name == "base":
                rows[s] = pitch_rows(sw, x).assign(season=s)
                by_type[str(s)] = fit_by_type(rows[s], sw, x)
                sides[str(s)] = {pt: by_hitter_side(sw, x, pt) for pt in ("ST", "SL")}
                if s == season - 1:
                    order = row_order_check(sw, x)
            log(f"{s} {name}: AUC {diag['auc']:.4f}")
        sweeper_swings.append(sw[sw["pitch_type"] == "ST"])

    stacked = pd.concat(rows.values(), ignore_index=True)
    st = pd.concat(sweeper_swings, ignore_index=True)
    x_st, diag_st = stuff.fit_crossfit(st)
    st_rows = st.assign(x=x_st).groupby(["pitcher", "game_year"]).agg(n=("whiff", "size"), w=("whiff", "mean"), x=("x", "mean"))
    st_rows = st_rows[st_rows["n"] >= MIN_SWINGS]

    a, b, c = seasons
    errors = {name: blend_errors(tables[name][a], tables[name][b], tables[name][b], tables[name][c]) for name in VARIANTS}
    candidates = {}
    for name in VARIANTS:
        if name == "base":
            continue
        comp = compare_errors(errors["base"], errors[name], n_boot, seed)
        h = stuff.validate_holdout(tables[name][a], tables[name][b], tables[name][b], tables[name][c])
        st_now = [sb._r(tables[name][s].query("pitch_type == 'ST'")["x_whiff_pct"], tables[name][s].query("pitch_type == 'ST'")["whiff_pct"]) for s in seasons]
        candidates[name] = {"auc": aucs[name], "held_out_gain_pct": h["gain_pct"], "sweeper_r_expected_actual_by_season": st_now,
                            "held_out_rmse_vs_base": comp, "rule": verdict(comp)}
    base_h = stuff.validate_holdout(tables["base"][a], tables["base"][b], tables["base"][b], tables["base"][c])

    result = {
        "source": f"python -m baseball.edge.stuff_checks {season}, fresh fits on the regular-season pitch files.",
        "note": "Fresh fits sit within refit noise of the saved pitch tables (see refit_noise), not exactly on them.",
        "adoption_rule": "A change is adopted only if it lowers held-out error on sweepers (weights fit on the first pair of seasons, "
                         "scored on the second; 95% interval from resampling pitchers excludes zero) and no pitch type is clearly worse.",
        "bootstrap": {"resamples": n_boot, "seed": seed, "unit": "pitcher"},
        "base_model": {"auc": aucs["base"], "held_out_gain_pct": base_h["gain_pct"], "held_out_rmse_blend": base_h["rmse_blend"]},
        "fit_by_pitch_type": by_type,
        "carry_over": {f"{p}->{q}": carry_over(rows[p], rows[q]) for p, q in zip(seasons, seasons[1:])},
        "by_hitter_side": sides,
        "sweeper_correlates": correlates(stacked, "ST", n_boot, seed),
        "slider_correlates": correlates(stacked, "SL", n_boot, seed),
        "sweeper_only_model": {"swings": int(len(st)), "swing_auc": diag_st["auc"], "pitcher_seasons": int(len(st_rows)),
                               "r_expected_actual": sb._r(st_rows["x"], st_rows["w"])},
        "candidates": candidates,
        "model_changed": bool(any(v["rule"]["adopt"] for v in candidates.values())),
        "refit_noise": {"season": season - 1, "what": "The same swings fit again in another row order; how far a pitch's expected whiff% moves.",
                        "orders": order},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"edge-stuff-checks-{season}.json"
    path.write_text(json.dumps(result, indent=1, default=float))
    log(f"saved {path}")
    return result


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Sweeper diagnosis, candidate fixes and refit noise for the expected-whiff model")
    ap.add_argument("season", type=int)
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    run(a.season, a.n, a.seed)
