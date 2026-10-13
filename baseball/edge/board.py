"""Build the Edge Board: one self-contained HTML page from the engine's outputs.

  uv run bb board 2026        -> data/edge/2026/edge-board.html

The page template lives in baseball/edge/board_template.html; this module computes the data it shows
and injects it as JSON. Public Statcast data only.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from baseball.edge.run import COLUMNS, OUT_DIR
from baseball.ingest.league import load_season
from baseball.phases import phase

TEMPLATE = Path(__file__).with_name("board_template.html")
MIN_SWINGS_LIST = 75


def _r(x, n=1):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    return round(float(x), n)


def _name(s: str) -> str:
    """'Skubal, Tarik' -> 'Tarik Skubal'."""
    if not isinstance(s, str) or ", " not in s:
        return s
    last, first = s.split(", ", 1)
    return f"{first} {last}"


def build(season: int) -> Path:
    d = OUT_DIR / str(season)
    summary = json.loads((d / "summary.json").read_text())
    seasons = summary["seasons"]
    stuff = {s: pd.read_parquet(d / f"stuff_{s}.parquet") for s in seasons}
    tells = {s: pd.read_parquet(d / f"tells_{s}.parquet") for s in seasons}
    shifts = pd.read_parquet(d / "shifts.parquet")
    proj = pd.read_parquet(d / "projection.parquet")
    pg = pd.read_parquet(d / "persistent_gaps.parquet")
    bl = pd.read_parquet(d / "baselines.parquet")

    cur = phase(load_season(season, COLUMNS))
    cur["ivb"] = cur["pfx_z"] * 12
    cur["hb"] = np.where(cur["p_throws"].eq("R"), -cur["pfx_x"], cur["pfx_x"]) * 12
    usage = (
        cur.dropna(subset=["pitch_type"])
        .groupby(["pitcher", "pitch_type"])
        .agg(n=("pitch_type", "size"), velo=("release_speed", "mean"), ivb=("ivb", "mean"), hb=("hb", "mean"),
             spin=("release_spin_rate", "mean"), name=("pitch_name", "first"))
        .reset_index()
    )
    usage["usage"] = 100 * usage["n"] / usage.groupby("pitcher")["n"].transform("sum")
    people = cur.groupby("pitcher").agg(name=("player_name", "first"), throws=("p_throws", "first"), pitches=("pitch_type", "size"),
                                        games=("game_pk", "nunique")).reset_index()

    # ---- Finding 1: beating your stuff is a skill (gap scatter, last pair) ----
    a, b = seasons[-2], seasons[-1]
    m = stuff[a].merge(stuff[b], on=["pitcher", "pitch_type"], suffixes=("_a", "_b"))
    m = m[(m["swings_a"] >= 60) & (m["swings_b"] >= 60)]
    scatter = [[_r(r.gap_a), _r(r.gap_b), _name(r.player_name_b), r.pitch_name_b] for r in m.itertuples()]

    # ---- Finding 2: release tells and whiffs ----
    tc = summary["tell_cost"]
    pooled = summary["tell_cost_pooled"]
    league_auc = tells[season]["tell_auc"]

    # ---- Finding 3: projection accuracy ----
    ty = summary.get("projection_two_year") or {}

    # ---- Lists ----
    keep = pg[(pg["seasons"] == len(seasons)) & pg["same_sign"] & (pg["swings"] >= MIN_SWINGS_LIST * len(seasons))]
    def gap_row(r):
        return {"id": int(r.pitcher), "name": _name(r.player_name), "pitch": r.pitch_name, "swings": int(r.swings),
                "gaps": [_r(getattr(r, f"gap_{s}")) for s in seasons], "mean": _r(r.mean_gap)}
    beats = [gap_row(r) for r in keep.sort_values("mean_gap", ascending=False).head(30).itertuples()]
    trails = [gap_row(r) for r in keep.sort_values("mean_gap").head(30).itertuples()]

    pr = proj[proj["swings"] >= MIN_SWINGS_LIST].copy()
    def proj_row(r):
        return {"id": int(r.pitcher), "name": _name(r.player_name), "pitch": r.pitch_name, "swings": int(r.swings),
                "whiff": _r(r.whiff_pct), "x": _r(r.x_whiff_pct), "prior": _r(getattr(r, "whiff_pct_prior", np.nan)),
                "proj": _r(r.proj_whiff_pct), "chg": _r(r.proj_change), "basis": r.proj_basis}
    risers = [proj_row(r) for r in pr.sort_values("proj_change", ascending=False).head(30).itertuples()]
    fallers = [proj_row(r) for r in pr.sort_values("proj_change").head(30).itertuples()]

    ch = shifts[(shifts["scope"] == "this pitch only") & (shifts["label_check"] == "ok") & (shifts["metric"] != "arm angle (deg)")
                & (shifts["swings_before"] >= 40) & (shifts["swings_after"] >= 40)].copy()
    metric_short = {"velocity (mph)": "velo", "induced vertical break (in)": "rise", "arm-side break (in)": "arm-side run", "spin (rpm)": "spin"}
    # one row per pitch: the same change often trips several metrics a few days apart. Keep the strongest
    # signal as the headline and list every metric that moved.
    moved = ch.groupby(["pitcher", "pitch_type"])["metric"].agg(lambda x: ", ".join(sorted({metric_short.get(v, v) for v in x})))
    ch = ch.sort_values("t", key=np.abs, ascending=False).drop_duplicates(["pitcher", "pitch_type"])
    changes_found = int(len(ch))
    ch = ch.join(moved.rename("moved"), on=["pitcher", "pitch_type"])
    ch = ch.reindex(ch["x_whiff_change"].abs().sort_values(ascending=False).index).head(40)
    changes = []
    for r in ch.itertuples():
        changes.append({
            "id": int(r.pitcher), "name": _name(r.player_name), "pitch": r.pitch_name, "date": r.split_date,
            "metric": metric_short.get(r.metric, r.metric), "moved": r.moved, "before": _r(r.before, 1 if r.metric != "spin (rpm)" else 0),
            "after": _r(r.after, 1 if r.metric != "spin (rpm)" else 0), "x_before": _r(r.x_whiff_before), "x_after": _r(r.x_whiff_after),
            "x_chg": _r(r.x_whiff_change), "u_before": _r(r.usage_before_pct), "u_after": _r(r.usage_after_pct),
            "w_before": _r(r.whiff_before_pct), "w_after": _r(r.whiff_after_pct), "sw_before": int(r.swings_before), "sw_after": int(r.swings_after),
        })

    # ---- Pitcher lookup ----
    tell_pct = {}
    for pt, g in tells[season].groupby("pitch_type"):
        ranks = g["tell_auc"].rank(pct=True) * 100
        for (pid, auc), pc in zip(zip(g["pitcher"], g["tell_auc"]), ranks):
            tell_pct[(int(pid), pt)] = (_r(auc, 3), _r(pc, 0))
    st_cur = stuff[season].set_index(["pitcher", "pitch_type"])
    pj = proj.set_index(["pitcher", "pitch_type"])
    pg_i = pg.set_index(["pitcher", "pitch_type"])
    pitchers = {}
    for p in people[people["pitches"] >= 300].itertuples():
        arsenal = []
        for u in usage[(usage["pitcher"] == p.pitcher) & (usage["n"] >= 20)].sort_values("n", ascending=False).itertuples():
            k = (p.pitcher, u.pitch_type)
            row = {"code": u.pitch_type, "pitch": u.name, "usage": _r(u.usage), "velo": _r(u.velo), "ivb": _r(u.ivb), "hb": _r(u.hb),
                   "spin": _r(u.spin, 0)}
            if k in st_cur.index:
                s_ = st_cur.loc[k]
                row.update({"swings": int(s_["swings"]), "whiff": _r(s_["whiff_pct"]), "x": _r(s_["x_whiff_pct"]), "gap": _r(s_["gap"])})
            if k in pj.index:
                row["proj"] = _r(pj.loc[k, "proj_whiff_pct"])
            if k in pg_i.index and pg_i.loc[k, "seasons"] >= 2:
                row["gaps"] = [_r(pg_i.loc[k].get(f"gap_{s}", np.nan)) for s in seasons]
            if k in tell_pct:
                row["tell"], row["tell_pct"] = tell_pct[k]
            arsenal.append(row)
        if not arsenal:
            continue
        pch = shifts[(shifts["pitcher"] == p.pitcher) & (shifts["metric"] != "arm angle (deg)")]
        pch = pch.sort_values("t", key=np.abs, ascending=False).drop_duplicates(["pitch_type", "split_date"]).head(6)
        pchanges = [{"pitch": r.pitch_name, "date": r.split_date, "metric": metric_short.get(r.metric, r.metric),
                     "before": _r(r.before, 0 if r.metric == "spin (rpm)" else 1), "after": _r(r.after, 0 if r.metric == "spin (rpm)" else 1),
                     "scope": r.scope, "label": r.label_check, "x_chg": _r(r.x_whiff_change)} for r in pch.itertuples()]
        pb = bl[(bl["pitcher"] == p.pitcher) & bl["metric"].isin(["velo", "spin", "ext_ft", "arm_angle"])]
        deltas = [{"metric": r.metric, "pitch": r.pitch_type, "chg": _r(r.change, 2), "league": _r(r.league_median_change, 2), "pct": _r(r.pctile, 0)}
                  for r in pb.itertuples()]
        pitchers[int(p.pitcher)] = {"name": _name(p.name), "throws": p.throws, "pitches": int(p.pitches), "games": int(p.games),
                                    "arsenal": arsenal, "changes": pchanges, "deltas": deltas}

    data = {
        "meta": {"built": date.today().isoformat(), "season": season, "seasons": seasons,
                 "pitches": summary["pitches"], "total": int(sum(summary["pitches"].values())), "pitchers": len(pitchers),
                 "changes_found": changes_found},
        "gap": {"pairs": summary["gap_persistence"], "controlled": summary["gap_persistence_controlled"], "scatter": scatter, "a": a, "b": b,
                "same_sign_share": _r(100 * pg.loc[pg["seasons"] == len(seasons), "same_sign"].mean(), 0)},
        "tells": {"by_season": [{"season": s, "slope": _r(tc[str(s)]["slope_per_0.1_auc"], 2), "se": _r(tc[str(s)]["slope_se"], 2),
                                  "n": tc[str(s)]["pitches"]} for s in seasons],
                  "pooled": {k: ({kk: _r(vv, 2) for kk, vv in v.items()} if isinstance(v, dict) and "slope" in v else v)
                             for k, v in pooled.items() if k != "by_group"},
                  "by_group": {g: {"slope": _r(v["slope"], 2), "se": _r(v["se"], 2), "rows": v["rows"]} for g, v in pooled["by_group"].items()},
                  "median_auc": _r(league_auc.median(), 3),
                  "share_over_80": _r(100 * (league_auc > 0.8).mean(), 0)},
        "proj": {"validation": {k: {"r_actual": _r(v["r_actual_prev"], 3), "r_x": _r(v["r_xwhiff_prev"], 3), "r_blend": _r(v["r_blend"], 3),
                                    "rmse_actual": _r(v["rmse_actual_prev"], 2), "rmse_blend": _r(v["rmse_blend"], 2), "n": v["matched_pitches"]}
                                for k, v in summary["validation"].items()},
                 "two_year": {"matched_pitches": ty.get("matched_pitches"), "raw_last": _r(ty.get("rmse_raw_last_season"), 2),
                              "loo": {k: _r(v, 2) for k, v in (ty.get("loo_rmse") or {}).items()},
                              "gain_total": _r(ty.get("gain_vs_last_season_pct"), 1), "gain_from_expected": _r(ty.get("gain_from_expected_pct"), 1)},
                 "weights": {k: _r(v, 3) for k, v in (ty.get("weights") or {}).items()}},
        "lists": {"beats": beats, "trails": trails, "risers": risers, "fallers": fallers, "changes": changes},
        "pitchers": pitchers,
    }
    payload = json.dumps(data, separators=(",", ":"), default=lambda o: None).replace("</", "<\\/")
    html = TEMPLATE.read_text().replace("/*__EDGE_DATA__*/null", payload)
    out = d / "edge-board.html"
    out.write_text(html)
    return out
