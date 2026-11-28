"""Follow-up to the IL early-warning study (Nov. 28, 2026): three questions the first run left open.

Written before any of these numbers were computed. The 2026 results of the first study were already known, so
none of this is a clean held-out test the way the first study was; each part says what it can and can't show.

1. The run-up (`run_up`): for every arm IL stint with scored outings in the 30 days before it, his velocity drop in
   each of his last six outings before the placement (1 = the last one), against outings that were not followed by
   an arm stint within 30 days. Descriptive: it shows when the drop shows up, not whether it predicts.
2. In-game fade (`fade_features`): his fastball velocity over the last 10 fastballs of an outing minus the first 10
   (outings with 20+ fastballs), against his own fade in earlier outings this season (league mean by role when he
   has fewer than three). A pitcher who is fine early and loses velocity late may be getting hurt during the game.
3. Secondary pitches (`secondary_features`): breaking-ball and offspeed velocity in the outing against his mean in
   earlier outings this season (3+ games of that pitch class), as a z-score over the pooled game-to-game spread.

Parts 2 and 3 are scored exactly like the first study: logistic models fit on 2024-25 with the velocity-only model
as the base, scored on 2026 by AUC with a pitcher bootstrap, and the term refit on 2026 alone for the association.
The two new terms get a Benjamini-Hochberg correction across themselves.

4. Repeat flags (`streak_rules`), added after the broadcast coding showed one pitcher flagged in four straight starts
   before his stint: does a drop that repeats beat a single flag? Three rules, set before scoring: this outing and
   his previous scored outing both 2.0+ mph down; both 1.5+ down; and 1.5+ down in at least two of his last three.
   Scored on 2024-25 and 2026 with the first study's alert table.

`video_sample` lists the 2026 outings flagged by the 2 mph rule that were followed by an arm stint, and the same
number of false alarms matched on role, in shuffled order without the outcome, so the broadcast can be coded blind.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from baseball.health import il_warning as W
from baseball.stats import benjamini_hochberg, wilson

ROOT = Path(__file__).resolve().parents[2]
REPORT_OUT = ROOT / "reports" / "outputs" / "il-followup-2026.json"
BREAKING = ("SL", "ST", "CU", "KC", "SV", "CS")
OFFSPEED = ("CH", "FS", "FO", "SC")
FADE_N = 10


def _pitches(seasons) -> pd.DataFrame:
    cols = ["game_pk", "game_date", "game_year", "at_bat_number", "pitch_number", "pitcher", "player_name",
            "pitch_type", "release_speed", "inning", "description", "home_team", "away_team", "inning_topbot"]
    out = []
    for s in seasons:
        out.append(pd.concat([pd.read_parquet(p, columns=cols) for p in W.seq_parts(s)], ignore_index=True))
    p = pd.concat(out, ignore_index=True)
    p = p[~p["description"].isin(W.NO_PITCH)]
    p["game_date"] = pd.to_datetime(p["game_date"])
    return p.sort_values(["pitcher", "game_pk", "at_bat_number", "pitch_number"])


def fade_features(p: pd.DataFrame, a: pd.DataFrame) -> pd.DataFrame:
    """Last-10 minus first-10 fastball velocity per outing (20+ fastballs), and that fade against his own."""
    f = p[p["pitch_type"].isin(W.FB_TYPES) & p["release_speed"].notna()]
    g = f.groupby(["pitcher", "game_pk"])["release_speed"]
    n = g.size()
    first = g.apply(lambda s: s.iloc[:FADE_N].mean())
    last = g.apply(lambda s: s.iloc[-FADE_N:].mean())
    o = pd.DataFrame({"fb_n": n, "fade": last - first}).reset_index()
    o.loc[o["fb_n"] < 2 * FADE_N, "fade"] = np.nan
    o = a[["pitcher", "game_pk", "game_date", "season", "starter"]].merge(o, on=["pitcher", "game_pk"], how="left")
    o = o.sort_values(["pitcher", "game_date", "game_pk"])
    grp = o.groupby(["pitcher", "season"])["fade"]
    prev_mean = grp.transform(lambda s: s.shift(1).expanding().mean())
    prev_n = grp.transform(lambda s: s.shift(1).expanding().count())
    league = o.groupby(["season", "starter"])["fade"].transform("mean")
    o["fade_base"] = np.where(prev_n >= 3, prev_mean, league)
    o["fade_drop"] = o["fade_base"] - o["fade"]            # positive = he lost more velocity late than usual
    sd = o["fade_drop"].std()
    o["z_fade"] = (o["fade_drop"] / sd).clip(-W.Z_CLIP, W.Z_CLIP)
    return o[["pitcher", "game_pk", "fb_n", "fade", "fade_base", "fade_drop", "z_fade"]]


def secondary_features(p: pd.DataFrame, a: pd.DataFrame) -> pd.DataFrame:
    """Breaking-ball and offspeed velocity against his earlier outings this season (3+ games of the class)."""
    rows = []
    for cls, types in (("brk", BREAKING), ("off", OFFSPEED)):
        s = p[p["pitch_type"].isin(types) & p["release_speed"].notna()]
        g = (s.groupby(["pitcher", "game_pk"]).agg(game_date=("game_date", "first"), season=("game_year", "first"),
                                                    v=("release_speed", "mean"), n=("release_speed", "size"))
             .reset_index().sort_values(["pitcher", "game_date", "game_pk"]))
        gg = g.groupby(["pitcher", "season"])["v"]
        g["base"] = gg.transform(lambda x: x.shift(1).expanding().mean())
        g["games_before"] = gg.transform(lambda x: x.shift(1).expanding().count())
        g["drop"] = np.where(g["games_before"] >= 3, g["base"] - g["v"], np.nan)
        sd = (g["v"] - g["base"]).where(g["games_before"] >= 3).std()
        g[f"z_{cls}"] = (g["drop"] / sd).clip(-W.Z_CLIP, W.Z_CLIP)
        rows.append(g[["pitcher", "game_pk", f"z_{cls}"]].assign(**{f"drop_{cls}": g["drop"], f"n_{cls}": g["n"]}))
    out = a[["pitcher", "game_pk"]].copy()
    for r in rows:
        out = out.merge(r, on=["pitcher", "game_pk"], how="left")
    # one secondary term: the pitch-count-weighted mean of the two classes he threw
    w_b, w_o = out["n_brk"].where(out["drop_brk"].notna(), 0).fillna(0), out["n_off"].where(out["drop_off"].notna(), 0).fillna(0)
    tot = w_b + w_o
    out["z_secondary"] = np.where(tot > 0, (out["z_brk"].fillna(0) * w_b + out["z_off"].fillna(0) * w_o) / tot.where(tot > 0, 1), np.nan)
    out["drop_secondary"] = np.where(tot > 0, (out["drop_brk"].fillna(0) * w_b + out["drop_off"].fillna(0) * w_o) / tot.where(tot > 0, 1), np.nan)
    return out[["pitcher", "game_pk", "z_secondary", "drop_secondary", "z_brk", "z_off"]]


def run_up(d: pd.DataFrame, il: pd.DataFrame, k_max: int = 6, horizon: int = 30) -> dict:
    """Velocity drop by outing before each arm stint (scored outings within `horizon` days of the placement)."""
    e = W.label(d, il, horizon, ["arm"], col="r")
    e = e.sort_values(["pitcher", "game_date", "game_pk"])
    s = e[e["r"].eq(1)].copy()
    s["k"] = s.groupby(["pitcher", "r_effective"]).cumcount(ascending=False) + 1
    ctrl = e[e["r"].eq(0)]
    out = {"control": {}, "by_k": {}}
    for split, seasons in (("train", (2024, 2025)), ("test", (2026,))):
        c = ctrl[ctrl["season"].isin(seasons)]["drop_velo_1"].dropna()
        flag_c = (c >= 2.0)
        out["control"][split] = {"n": int(len(c)), "mean_drop": float(c.mean()), "se": float(c.std(ddof=1) / math.sqrt(len(c))),
                                 "flag_share": float(flag_c.mean())}
        rows = []
        for k in range(1, k_max + 1):
            x = s[s["season"].isin(seasons) & s["k"].eq(k)]["drop_velo_1"].dropna()
            fl = int((x >= 2.0).sum())
            lo, hi = wilson(fl, len(x))
            rows.append({"k": k, "n": int(len(x)), "mean_drop": float(x.mean()),
                         "se": float(x.std(ddof=1) / math.sqrt(len(x))) if len(x) > 1 else None,
                         "median_days_before": float(s[s["season"].isin(seasons) & s["k"].eq(k)]["r_days"].median()),
                         "flagged": fl, "flag_share": fl / len(x) if len(x) else None, "flag_lo": lo, "flag_hi": hi})
        out["by_k"][split] = rows
    return out


def _evaluate_term(d: pd.DataFrame, term: str, reps: int, keep=None) -> dict:
    """Velocity-only model vs velocity-only plus `term`, fit on 2024-25, scored on 2026."""
    if keep is not None:
        d = d[keep(d)]
    d = d[d[term].notna()]
    tr, te = d[d["season"].isin((2024, 2025))], d[d["season"].eq(2026)]
    base = W.NAIVE + W.TRACK_VELO
    f0 = W.logit_fit(W.design(tr, base), tr["y"], tr["pitcher"])
    f1 = W.logit_fit(W.design(tr, base + [term]), tr["y"], tr["pitcher"])
    p0, p1 = W.predict(f0, W.design(te, base)), W.predict(f1, W.design(te, base + [term]))
    i = 1 + len(base)
    fr = W.logit_fit(W.design(te, base + [term]), te["y"], te["pitcher"])

    def ortab(f):
        b, se = f["coef"][i], f["se"][i]
        return {"odds_ratio": float(np.exp(b)), "lo": float(np.exp(b - 1.96 * se)), "hi": float(np.exp(b + 1.96 * se)),
                "p": float(math.erfc(abs(b / se) / math.sqrt(2)))}
    return {"term": term, "train": {"outings": int(len(tr)), "events": int(tr["y"].sum())},
            "test": {"outings": int(len(te)), "events": int(te["y"].sum())},
            "fit_2024_25": ortab(f1), "refit_2026": ortab(fr),
            "auc": {"velocity": W.auc(te["y"], p0), "with_term": W.auc(te["y"], p1)},
            "vs_velocity": W.bootstrap_compare(te["y"], p0, p1, te["pitcher"], reps=reps, seed=7)}


def streak_rules(d: pd.DataFrame) -> dict:
    """Repeat-flag rules on the scored outings (see the module note), on 2024-25 and on 2026."""
    d = d.sort_values(["pitcher", "season", "game_date", "game_pk"]).copy()
    g = d.groupby(["pitcher", "season"])["drop_velo_1"]
    prev1, prev2 = g.shift(1), g.shift(2)
    rules = {"streak_2.0": (d["drop_velo_1"] >= 2.0) & (prev1 >= 2.0),
             "streak_1.5": (d["drop_velo_1"] >= 1.5) & (prev1 >= 1.5),
             "two_of_three_1.5": ((d["drop_velo_1"] >= 1.5).astype(int) + (prev1 >= 1.5).astype(int)
                                  + (prev2 >= 1.5).astype(int)) >= 2,
             "single_2.0": d["drop_velo_1"] >= 2.0}
    out = {}
    for name, f in rules.items():
        tr, te = d["season"].isin((2024, 2025)).to_numpy(), d["season"].eq(2026).to_numpy()
        f = f.to_numpy()
        out[name] = {"train": W.alert_table(d[tr], f[tr], seasons=2), "test": W.alert_table(d[te], f[te])}
    return out


def video_sample(d: pd.DataFrame, names: pd.DataFrame, seed: int = 11) -> pd.DataFrame:
    """2026 flags (2.0+ mph) followed by an arm stint, plus as many false alarms matched on role, shuffled."""
    te = d[d["season"].eq(2026) & (d["drop_velo_1"] >= 2.0)].copy()
    true = te[te["y"].eq(1)]
    rng = np.random.default_rng(seed)
    false = []
    for st, n in true.groupby("starter").size().items():
        pool = te[te["y"].eq(0) & te["starter"].eq(st)]
        false.append(pool.iloc[rng.choice(len(pool), size=min(n, len(pool)), replace=False)])
    v = pd.concat([true, *false]).sample(frac=1, random_state=seed).reset_index(drop=True)
    v = v.merge(names, on=["pitcher", "game_pk"], how="left")
    v["case"] = np.arange(1, len(v) + 1)
    return v


def run(reps: int = 1000, log=print, out: Path = REPORT_OUT) -> dict:
    B = W.build(log=log)
    a, il = B["outings"], B["il"]
    p = _pitches((2024, 2025, 2026))
    a = a.merge(fade_features(p, a), on=["pitcher", "game_pk"], how="left")
    a = a.merge(secondary_features(p, a), on=["pitcher", "game_pk"], how="left")
    d = W.label(W.model_frame(a), il, 14, ["arm"])
    res = {"run_up": run_up(W.model_frame(a), il)}
    terms = {"fade": _evaluate_term(d, "z_fade", reps), "secondary": _evaluate_term(d, "z_secondary", reps)}
    q = benjamini_hochberg([terms[k]["fit_2024_25"]["p"] for k in terms])
    for k, qq in zip(terms, q):
        terms[k]["fit_2024_25"]["q_bh"] = qq
    res["terms"] = terms
    res["streak_rules"] = streak_rules(d)
    c = d[d["y"].eq(0)]["drop_velo_1"]
    res["outing_drop_sd_no_il"] = float(c.std())      # how much one outing's drop moves around with no injury
    # how the fade and the outing's drop relate, and the flag split by whether he faded late
    te = d[d["season"].eq(2026)]
    res["fade_corr_with_drop_2026"] = float(te[["z_fade", "z_velo_1"]].dropna().corr().iloc[0, 1])
    names = (p.groupby(["pitcher", "game_pk"]).agg(name=("player_name", "first"), home=("home_team", "first"),
                                                   away=("away_team", "first"), first_inning=("inning", "min"),
                                                   last_inning=("inning", "max"))
             .reset_index())
    v = video_sample(d, names)
    keep = ["case", "game_pk", "game_date", "name", "pitcher", "team", "home", "away", "starter", "first_inning",
            "last_inning", "pitches", "fb_base_velo", "drop_velo_1", "fade", "y", "y_days", "y_effective"]
    res["video_sample"] = json.loads(v[keep].to_json(orient="records", date_format="iso"))
    out.write_text(json.dumps(res, indent=1, default=float))
    log(f"wrote {out}")
    return res


if __name__ == "__main__":
    run()
