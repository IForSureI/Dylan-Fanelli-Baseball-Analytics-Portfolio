"""How much a quoted pitch grade moves when the expected-whiff model is fit again.

  uv run python -m baseball.edge.grade_noise 2026 --pitchers 670970 650556 664126

The model's cross-fit folds and binning follow the order of the swings (see `stuff_checks.py`), so two fits
of the same data give slightly different expected whiffs. A report that quotes one pitch's expected whiff,
its stuff grade or its next-season grade is quoting one fit. This module fits the same swings in several
row orders (the order as loaded, then seeded shuffles), rebuilds the next-season projection the way
`bb edge` does, grades each pitch the way `reliever.pitch_grades()` does, and reports the range.

It changes nothing: `stuff.py` and the saved run are read, not written.

Output: reports/outputs/edge-grade-noise-<season>.json. One row per quoted pitch: public pitcher id and
pitch type with the range across fits (no pitch-level rows).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from baseball.edge import stuff
from baseball.evaluation.reliever import _ptype, grade_from_percentile, percentile

ROOT = Path(__file__).resolve().parents[2]
EDGE_DIR = ROOT / "data" / "edge"
OUT = ROOT / "reports" / "outputs"
N_ORDERS = 10


def reorder(swings: pd.DataFrame, k: int) -> pd.DataFrame:
    """Order 0 is the swings as loaded. Order k > 0 is a shuffle with seed k."""
    return swings if k == 0 else swings.sample(frac=1, random_state=k)


def projection(tables: dict[int, pd.DataFrame], season: int) -> pd.DataFrame:
    """Next-season whiff projection for every pitch of `season`, by the same steps as edge/run.py: the one-year
    blend fit on (season - 1, season), and the two-year weights where they score better leave-one-out."""
    blend = stuff.validate(tables[season - 1], tables[season])["blend"]
    two = stuff.validate_two_year(tables[season - 2], tables[season - 1], tables[season]) if season - 2 in tables else None
    if two and two["loo_rmse"]["two_seasons_plus_expected"] < two["loo_rmse"]["last_plus_expected"]:
        return stuff.project_two_year(tables[season - 1], tables[season], two["weights"], blend)
    return stuff.project(tables[season], blend).assign(proj_basis="one season")


def grade_rows(table: pd.DataFrame, proj: pd.DataFrame, ids) -> pd.DataFrame:
    """Stuff and next-season grades for the pitchers in `ids`, each against every pitch of its type group in
    `table`: the same percentile and 20-80 mapping as reliever.pitch_grades()."""
    s = table.merge(proj[["pitcher", "pitch_type", "proj_whiff_pct"]], on=["pitcher", "pitch_type"], how="left")
    s["group"] = s["pitch_type"].map(_ptype)
    rows = []
    for _, r in s[s["pitcher"].isin(list(ids))].iterrows():
        ref = s[s["group"].eq(r["group"])]
        pct_stuff, pct_next = percentile(ref["x_whiff_pct"], r["x_whiff_pct"]), percentile(ref["proj_whiff_pct"], r["proj_whiff_pct"])
        rows.append({"pitcher": int(r["pitcher"]), "pitch_type": r["pitch_type"], "swings": int(r["swings"]), "whiff_pct": float(r["whiff_pct"]),
                     "x_whiff_pct": float(r["x_whiff_pct"]), "gap": float(r["whiff_pct"] - r["x_whiff_pct"]),
                     "pct_stuff": pct_stuff, "grade_stuff": grade_from_percentile(pct_stuff),
                     "proj_whiff_pct": float(r["proj_whiff_pct"]), "pct_next": pct_next, "grade_next": grade_from_percentile(pct_next)})
    return pd.DataFrame(rows)


def summarize(fits: list[pd.DataFrame]) -> dict:
    """Per pitch, across fits: the low and high of each number and every grade it took, with how many fits gave each."""
    allr = pd.concat([f.assign(fit=i) for i, f in enumerate(fits)], ignore_index=True)
    out = {}
    for (pid, pt), g in allr.groupby(["pitcher", "pitch_type"]):
        row = {"pitcher": int(pid), "pitch_type": pt, "swings": int(g["swings"].iloc[0]), "whiff_pct": float(g["whiff_pct"].iloc[0]), "fits": int(len(g))}
        for c in ("x_whiff_pct", "gap", "pct_stuff", "proj_whiff_pct", "pct_next"):
            row[c] = {"lo": float(g[c].min()), "hi": float(g[c].max()), "mean": float(g[c].mean())}
        for c in ("grade_stuff", "grade_next"):
            counts = g[c].value_counts().sort_index()
            row[c] = {"lo": int(g[c].min()), "hi": int(g[c].max()), "counts": {str(int(k)): int(v) for k, v in counts.items()}}
        out[f"{pid}_{pt}"] = row
    return out


def pitcher_level(tables_by_fit: list[pd.DataFrame], ids) -> dict:
    """Swing-weighted expected whiff% per pitcher across fits (the 'stuff vs. results' line in the memo)."""
    vals = {}
    for t in tables_by_fit:
        for pid, g in t[t["pitcher"].isin(list(ids))].groupby("pitcher"):
            vals.setdefault(int(pid), []).append(float(np.average(g["x_whiff_pct"], weights=g["swings"])))
    return {str(p): {"lo": min(v), "hi": max(v)} for p, v in vals.items()}


def run(season: int, ids, n_orders: int = N_ORDERS, log=print) -> dict:
    from baseball.edge.run import COLUMNS
    from baseball.ingest.league import load_season
    from baseball.phases import phase

    seasons = [season - 2, season - 1, season]
    swings = {s: stuff.prepare(phase(load_season(s, COLUMNS))) for s in seasons}
    fits, current = [], []
    for k in range(n_orders):
        tables = {}
        for s in seasons:
            sw = reorder(swings[s], k)
            x, _ = stuff.fit_crossfit(sw)
            tables[s] = stuff.pitch_table(sw, x)
        fits.append(grade_rows(tables[season], projection(tables, season), ids))
        current.append(tables[season])
        log(f"order {k} done")
    saved_dir = EDGE_DIR / str(season)
    saved = None
    if (saved_dir / f"stuff_{season}.parquet").exists() and (saved_dir / "projection.parquet").exists():
        saved = grade_rows(pd.read_parquet(saved_dir / f"stuff_{season}.parquet"), pd.read_parquet(saved_dir / "projection.parquet"), ids)
        saved = {f"{r.pitcher}_{r.pitch_type}": {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in r._asdict().items() if k != "Index"}
                 for r in saved.itertuples()}
    result = {
        "source": f"python -m baseball.edge.grade_noise {season} --pitchers {' '.join(str(i) for i in ids)}, fresh fits on the regular-season pitch files.",
        "what": "Each quoted pitch's expected whiff, stuff grade and next-season grade across fits of the same swings in different row orders.",
        "orders": {"count": n_orders, "how": "order 0 is the swings as loaded; orders 1 and up are shuffles seeded with the order number"},
        "grading": "percentile among pitches of the same type group with 50+ tracked swings that season, grade = 50 + 10z to the nearest 5 "
                   "(reliever.grade_from_percentile); next-season grade uses the projection rebuilt from each fit as edge/run.py builds it",
        "pitches": summarize(fits),
        "pitcher_swing_weighted_expected_whiff": pitcher_level(current, ids),
        "saved_run": saved,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"edge-grade-noise-{season}.json"
    path.write_text(json.dumps(result, indent=1, default=float))
    log(f"saved {path}")
    return result


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Range of quoted pitch grades across refits in different row orders")
    ap.add_argument("season", type=int)
    ap.add_argument("--pitchers", type=int, nargs="+", required=True, help="MLBAM pitcher ids")
    ap.add_argument("--orders", type=int, default=N_ORDERS)
    a = ap.parse_args()
    run(a.season, a.pitchers, a.orders)
