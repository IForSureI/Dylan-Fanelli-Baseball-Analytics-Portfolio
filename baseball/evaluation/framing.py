"""Catcher framing on public Statcast data: how many strikes a catcher adds, whether it repeats, and what
it is worth.

The question a club pays for: how much of a catcher's value is framing, is it a skill (does it repeat), and
can a public model reproduce what MLB's own leaderboard says?

Method (regular seasons 2024-26, every take: called strikes, balls and blocked balls):
1. A called-strike model per season: gradient-boosted trees on the pitch's horizontal location, its height
   as a share of the batter's strike zone (Statcast's sz_bot to sz_top), the batter's side, the pitcher's
   hand and the count. It is fit out of fold by game (5 folds), so no pitch's own call, and none of its
   game's calls, are in the model that scores it.
2. Extra strikes on a take = called strike (1 or 0) minus the model's strike probability.
3. A strike's value by count: on takes, the mean change in run expectancy (Statcast's delta_run_exp) after
   a ball minus after a called strike, by count, from the same season. A ball at 3-2 costs much more than a
   ball at 0-0, so the value is count by count, not one number.
4. Framing runs = sum over the catcher's takes of extra strikes x that count's value.
5. A pitcher-and-park adjustment: a ridge regression of each take's framing runs on catcher, pitcher and
   home park (the umpire isn't in the public data; the park stands in for some of the crew and camera
   effects). The catcher's coefficient times his takes is his adjusted framing.

Checks: the model's calibration by decile; split-half reliability (odd vs even games) and year-to-year
correlation for catchers with enough takes; and agreement with Baseball Savant's catcher framing
leaderboard (runs), pulled for each season.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SEQ = ROOT / "data" / "seq"
RAW = ROOT / "data" / "raw" / "savant"
OUT = ROOT / "reports" / "outputs"
FIG = ROOT / "reports" / "figures"
SEASONS = (2024, 2025, 2026)
TAKES = {"called_strike": 1, "ball": 0, "blocked_ball": 0}
COLS = ["game_pk", "game_type", "home_team", "pitcher", "fielder_2", "stand", "p_throws", "balls", "strikes",
        "plate_x", "plate_z", "sz_top", "sz_bot", "description", "delta_run_exp"]
FOLDS = 5
RIDGE_ALPHA = 400.0          # takes-equivalent shrinkage for the catcher, pitcher and park terms
MIN_TAKES_SPLIT = 1500       # catchers with this many takes in a season enter the split-half check
MIN_TAKES_YOY = 2000         # ... and this many in both seasons enter the year-to-year check
RUNS_PER_WIN = 10.0
# The season must go in seasonStart/seasonEnd: the older `year=` form returns the current season for any year.
SAVANT_URL = ("https://baseballsavant.mlb.com/leaderboard/catcher-framing?type=catcher&seasonStart={y}&seasonEnd={y}"
              "&team=&min=q&sortColumn=rv_tot&sortDirection=desc&csv=true")


def takes(season: int) -> pd.DataFrame:
    parts = sorted(SEQ.glob(f"seq_{season}_*.parquet"))
    if not parts:
        raise FileNotFoundError(f"no sequence files for {season} in {SEQ}: run `bb pull-league {season}` and `bb seq {season}`")
    d = pd.concat([pd.read_parquet(p, columns=COLS) for p in parts], ignore_index=True)
    d = d[(d.game_type == "R") & d.description.isin(TAKES) & d.fielder_2.notna()]
    d = d.dropna(subset=["plate_x", "plate_z", "sz_top", "sz_bot", "balls", "strikes"])
    d = d[(d.sz_top - d.sz_bot) > 0.5].copy()
    d["strike"] = d.description.map(TAKES).astype(int)
    d["pz"] = (d.plate_z - d.sz_bot) / (d.sz_top - d.sz_bot)
    d["count"] = d.balls.astype(int).astype(str) + "-" + d.strikes.astype(int).astype(str)
    d["season"] = season
    d["fielder_2"] = d.fielder_2.astype(int)
    return d.reset_index(drop=True)


def _X(d: pd.DataFrame) -> np.ndarray:
    return np.column_stack([d.plate_x, d.pz, (d.stand == "L").astype(float), (d.p_throws == "L").astype(float),
                            d.balls.astype(float), d.strikes.astype(float)])


def call_model(d: pd.DataFrame, folds: int = FOLDS, seed: int = 7) -> np.ndarray:
    """Out-of-fold called-strike probability for every take (folds are whole games)."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    games = d.game_pk.unique()
    rng = np.random.default_rng(seed)
    fold_of = dict(zip(games, rng.integers(0, folds, len(games))))
    f = d.game_pk.map(fold_of).to_numpy()
    X, y, p = _X(d), d.strike.to_numpy(), np.empty(len(d))
    for k in range(folds):
        m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, max_leaf_nodes=63,
                                           categorical_features=[2, 3], random_state=seed)
        m.fit(X[f != k], y[f != k])
        p[f == k] = m.predict_proba(X[f == k])[:, 1]
    return p


def strike_values(d: pd.DataFrame) -> pd.Series:
    """Runs a called strike saves vs a ball, by count: mean delta_run_exp after a ball minus after a called
    strike (batting team's view, so positive = good for the defense)."""
    g = d.groupby(["count", "strike"]).delta_run_exp.mean().unstack()
    return (g[0] - g[1]).rename("strike_value")


def score(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["p_strike"] = call_model(d)
    vals = strike_values(d)
    d["value"] = d["count"].map(vals)
    d["extra"] = d.strike - d.p_strike
    d["runs"] = d.extra * d.value
    return d


def adjusted(d: pd.DataFrame, alpha: float = RIDGE_ALPHA) -> pd.DataFrame:
    """Ridge of each take's framing runs on catcher, pitcher and home-park indicators; a catcher's adjusted
    runs = his coefficient x his takes."""
    from scipy import sparse
    from sklearn.linear_model import Ridge
    blocks, names = [], []
    for col in ("fielder_2", "pitcher", "home_team"):
        codes, uniq = pd.factorize(d[col])
        blocks.append(sparse.csr_matrix((np.ones(len(d)), (np.arange(len(d)), codes)), shape=(len(d), len(uniq))))
        names.append((col, uniq))
    X = sparse.hstack(blocks).tocsr()
    m = Ridge(alpha=alpha, fit_intercept=True).fit(X, d.runs.to_numpy())
    n_c = len(names[0][1])
    coef = pd.Series(m.coef_[:n_c], index=names[0][1])
    n = d.groupby("fielder_2").size()
    return pd.DataFrame({"takes": n, "adj_runs": coef.reindex(n.index) * n})


def catcher_table(d: pd.DataFrame) -> pd.DataFrame:
    raw = d.groupby("fielder_2").agg(takes=("runs", "size"), extra_strikes=("extra", "sum"), raw_runs=("runs", "sum"))
    adj = adjusted(d)
    t = raw.join(adj[["adj_runs"]])
    t["season"] = int(d.season.iloc[0])
    return t.reset_index().rename(columns={"fielder_2": "catcher"})


def calibration(d: pd.DataFrame, bins: int = 10) -> pd.DataFrame:
    q = pd.qcut(d.p_strike, bins, labels=False, duplicates="drop")
    return d.groupby(q).agg(predicted=("p_strike", "mean"), called=("strike", "mean"), n=("strike", "size")).reset_index(drop=True)


def split_half(d: pd.DataFrame, min_takes: int = MIN_TAKES_SPLIT) -> dict:
    """Odd vs even games within a season: correlation of framing runs per take across catchers, and the
    Spearman-Brown step-up to the full season."""
    d = d.assign(half=(d.game_pk % 2))
    g = d.groupby(["fielder_2", "half"]).agg(n=("runs", "size"), r=("runs", "sum")).unstack()
    g = g[(g["n"].sum(axis=1) >= min_takes)]
    a, b = g["r"][0] / g["n"][0], g["r"][1] / g["n"][1]
    r = float(np.corrcoef(a, b)[0, 1])
    return dict(catchers=int(len(g)), r_half=r, r_season=2 * r / (1 + r))


def year_to_year(tables: pd.DataFrame, min_takes: int = MIN_TAKES_YOY, col: str = "adj_runs") -> dict:
    t = tables[tables.takes >= min_takes].assign(rate=lambda x: x[col] / x.takes * 1000)
    out = {}
    for y in sorted(t.season.unique())[:-1]:
        a = t[t.season == y].set_index("catcher").rate
        b = t[t.season == y + 1].set_index("catcher").rate
        both = a.index.intersection(b.index)
        if len(both) >= 8:
            out[f"{y}->{y + 1}"] = dict(catchers=int(len(both)), r=float(np.corrcoef(a[both], b[both])[0, 1]))
    return out


def savant(season: int, raw: Path = RAW) -> pd.DataFrame:
    raw.mkdir(parents=True, exist_ok=True)
    p = raw / f"catcher_framing_{season}.csv"
    if not p.exists():
        req = urllib.request.Request(SAVANT_URL.format(y=season), headers={"User-Agent": "Mozilla/5.0"})
        p.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    s = pd.read_csv(p, encoding="utf-8-sig")
    return s.rename(columns={"id": "catcher", "rv_tot": "savant_runs", "pitches": "savant_pitches"})[["catcher", "name", "savant_pitches", "savant_runs"]]


def agreement(table: pd.DataFrame, sv: pd.DataFrame) -> dict:
    j = table.merge(sv, on="catcher")
    return dict(catchers=int(len(j)), r_raw=float(np.corrcoef(j.raw_runs, j.savant_runs)[0, 1]),
                r_adj=float(np.corrcoef(j.adj_runs, j.savant_runs)[0, 1]),
                slope_raw=float(np.polyfit(j.savant_runs, j.raw_runs, 1)[0]))


HALF_PLATE_FT = 17 / 24        # half of the 17-inch plate, in feet
DEEP_FT = 3 / 12               # "well inside / outside": 3 inches past the plate's edge, either way
DEEP_PZ = (0.2, 0.8)           # well inside vertically: the middle 60% of the batter's zone height
OUT_PZ = (-0.15, 1.15)         # well outside vertically: more than 15% of the zone height above or below it
FULL_TIME_TAKES = 7000         # about a full-time catcher's season of takes (the 2025 leaders caught 8,000-9,000)
DOLLARS_PER_WIN = 11.23        # FanGraphs, Clemens, Feb. 24, 2026 (overall rate)


def zone_sharpness(d: pd.DataFrame) -> dict:
    """How predictable the calls were from location: the share of takes in the uncertain band (model strike
    probability 10-90%), called balls on pitches well inside the zone, and called strikes well outside it."""
    inside = (d.plate_x.abs() < HALF_PLATE_FT - DEEP_FT) & d.pz.between(*DEEP_PZ)
    outside = (d.plate_x.abs() > HALF_PLATE_FT + DEEP_FT) | (d.pz < OUT_PZ[0]) | (d.pz > OUT_PZ[1])
    return dict(uncertain_share=float(d.p_strike.between(0.1, 0.9).mean()),
                balls_well_inside=float(1 - d[inside].strike.mean()), n_inside=int(inside.sum()),
                strikes_well_outside=float(d[outside].strike.mean()), n_outside=int(outside.sum()))


def fisher_diff(r1: float, n1: int, r2: float, n2: int) -> dict:
    """Two correlations compared with Fisher's z, as if independent (the two year pairs share a season, so the
    true p-value is somewhat smaller; this is the textbook check)."""
    from statistics import NormalDist
    z = (np.arctanh(r1) - np.arctanh(r2)) / np.sqrt(1 / (n1 - 3) + 1 / (n2 - 3))
    return dict(z=float(z), p=float(2 * (1 - NormalDist().cdf(abs(z)))))


def paired_yoy(T: pd.DataFrame, min_takes: int = MIN_TAKES_YOY, boot: int = 4000, seed: int = 5) -> dict:
    """The two year-to-year correlations on the same catchers (2,000+ takes in all three seasons), and a bootstrap
    over catchers of their difference, so the shared 2025 season is accounted for."""
    t = T[T.takes >= min_takes].assign(rate=lambda x: x.adj_runs / x.takes * 1000).pivot_table(index="catcher", columns="season", values="rate")
    t = t.dropna()
    if len(t) < 10:
        return dict(catchers=int(len(t)))
    a, b, c = t[2024].to_numpy(), t[2025].to_numpy(), t[2026].to_numpy()
    r1, r2 = np.corrcoef(a, b)[0, 1], np.corrcoef(b, c)[0, 1]
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(boot):
        i = rng.integers(0, len(t), len(t))
        diffs.append(np.corrcoef(a[i], b[i])[0, 1] - np.corrcoef(b[i], c[i])[0, 1])
    diffs = np.array(diffs)
    return dict(catchers=int(len(t)), r_24_25=float(r1), r_25_26=float(r2), diff_lo=float(np.percentile(diffs, 2.5)),
                diff_hi=float(np.percentile(diffs, 97.5)), share_diff_le_0=float((diffs <= 0).mean()))


def bref_catcher_term(T: pd.DataFrame, war_file: Path = ROOT / "data" / "raw" / "market" / "war_daily_bat.txt") -> dict:
    """How much framing Baseball-Reference's catcher term (runs_catcher) carries: its correlation with my framing
    runs, unadjusted and adjusted, catchers with 1,500+ takes."""
    if not war_file.exists():
        return {}
    b = pd.read_csv(war_file, na_values="NULL", low_memory=False, usecols=["mlb_ID", "year_ID", "runs_catcher"])
    g = b[b.year_ID.isin(list(SEASONS))].groupby(["mlb_ID", "year_ID"]).runs_catcher.sum().reset_index()
    j = T[T.takes >= MIN_TAKES_SPLIT].merge(g, left_on=["catcher", "season"], right_on=["mlb_ID", "year_ID"])
    return {str(s): dict(catchers=int(len(x)), r_unadjusted=float(np.corrcoef(x.runs_catcher, x.raw_runs)[0, 1]),
                         r_adjusted=float(np.corrcoef(x.runs_catcher, x.adj_runs)[0, 1])) for s, x in j.groupby("season")}


def run(seasons=SEASONS) -> dict:
    tables, out = [], {"seasons": {}}
    for s in seasons:
        d = score(takes(s))
        t = catcher_table(d)
        sv = savant(s)
        cal = calibration(d)
        vals = strike_values(d)
        out["seasons"][str(s)] = dict(takes=int(len(d)), called_strike_rate=float(d.strike.mean()),
                                      brier=float(((d.p_strike - d.strike) ** 2).mean()),
                                      calibration_max_gap=float((cal.predicted - cal.called).abs().max()),
                                      strike_value_0_0=float(vals.get("0-0")), strike_value_3_2=float(vals.get("3-2")),
                                      mean_strike_value=float((d.value).mean()),
                                      split_half=split_half(d), savant=agreement(t, sv), zone=zone_sharpness(d))
        tables.append(t.merge(sv[["catcher", "name", "savant_runs", "savant_pitches"]], on="catcher", how="left"))
    T = pd.concat(tables, ignore_index=True)
    out["year_to_year_adj"] = year_to_year(T, col="adj_runs")
    out["year_to_year_raw"] = year_to_year(T, col="raw_runs")
    q = T[T.takes >= MIN_TAKES_SPLIT]
    per = q.adj_runs / q.takes * 1000
    sv_all = T[T.savant_runs.notna() & T.savant_pitches.notna()] if "savant_pitches" in T else T.iloc[:0]
    out["spread"] = {str(s): dict(catchers=int((q.season == s).sum()), sd_adj=float(q[q.season == s].adj_runs.std()),
                                  sd_per_1000=float(per[q.season == s].std()), mean_takes=float(q[q.season == s].takes.mean()),
                                  sd_savant=float(T[(T.season == s) & T.savant_runs.notna()].savant_runs.std()),
                                  sd_savant_per_1000=float((sv_all[sv_all.season == s].savant_runs / sv_all[sv_all.season == s].savant_pitches * 1000).std()) if len(sv_all) else None,
                                  full_time_sd_runs=float(per[q.season == s].std() * FULL_TIME_TAKES / 1000),
                                  full_time_sd_dollars=float(per[q.season == s].std() * FULL_TIME_TAKES / 1000 / RUNS_PER_WIN * DOLLARS_PER_WIN),
                                  best=float(q[q.season == s].adj_runs.max()), worst=float(q[q.season == s].adj_runs.min()))
                     for s in seasons}
    y = out["year_to_year_adj"]
    if "2024->2025" in y and "2025->2026" in y:
        out["year_to_year_test"] = fisher_diff(y["2024->2025"]["r"], y["2024->2025"]["catchers"], y["2025->2026"]["r"], y["2025->2026"]["catchers"])
        out["year_to_year_paired"] = paired_yoy(T)
    out["bref_catcher_term"] = bref_catcher_term(T)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "framing_summary.json").write_text(json.dumps(out, indent=1) + "\n")
    T.round(3).to_json(OUT / "framing_catchers.json", orient="records", indent=0)
    return out


def figure(path: Path = FIG / "2026-catcher-framing.png") -> Path:
    """Left: framing runs per catcher by season (1,500+ takes), Patrick Bailey marked. Right: my runs vs
    Baseball Savant's, all three seasons."""
    import matplotlib.pyplot as plt
    from baseball import house
    from baseball.ingest import people
    house.apply()
    T = pd.read_json(OUT / "framing_catchers.json")
    T["nm"] = T.catcher.map(people.names(T.catcher))
    q = T[T.takes >= MIN_TAKES_SPLIT]
    fig, (a, b) = plt.subplots(1, 2, figsize=(11.5, 4.8), gridspec_kw=dict(width_ratios=[1.1, 1]))
    rng = np.random.default_rng(3)
    for i, s in enumerate(SEASONS):
        y = q[(q.season == s) & (q.nm != "Patrick Bailey")].adj_runs.to_numpy()
        a.scatter(i + rng.uniform(-0.16, 0.16, len(y)), y, s=18, color=house.SERIES[0], alpha=0.55, lw=0)
        a.hlines(np.percentile(y, [10, 90]), i - 0.28, i + 0.28, color=house.MUTED, lw=1)
        bp = q[(q.season == s) & (q.nm == "Patrick Bailey")]
        if len(bp):
            a.scatter([i], bp.adj_runs, s=46, color=house.SERIES[1], zorder=3)
            a.annotate(f"Bailey {bp.adj_runs.iloc[0]:+.1f}", (i, bp.adj_runs.iloc[0]), xytext=(10, 0), textcoords="offset points",
                       va="center", fontsize=9, color=house.SERIES[1])
    a.axhline(0, color=house.SOFT, lw=0.8)
    a.set_xticks(range(len(SEASONS)), [f"{s}{' (ABS challenges)' if s == 2026 else ''}" for s in SEASONS])
    a.set_ylabel("Framing runs, pitcher- and park-adjusted")
    a.set_title("The spread of framing shrank in 2026")
    a.text(0, -0.16, "Each dot is a catcher with 1,500+ takes; lines mark the 10th and 90th percentiles. Statcast 2024-26.",
           transform=a.transAxes, fontsize=8.5, color=house.MUTED)
    cols = dict(zip(SEASONS, house.SERIES[:3]))
    for s in SEASONS:
        j = T[(T.season == s) & T.savant_runs.notna()]
        b.scatter(j.savant_runs, j.raw_runs, s=16, alpha=0.7, lw=0, color=cols[s], label=str(s))
    lim = [min(T.raw_runs.min(), T.savant_runs.min()) - 2, max(T.raw_runs.max(), T.savant_runs.max()) + 2]
    b.plot(lim, lim, color=house.SOFT, lw=0.8)
    b.set_xlabel("Baseball Savant framing runs")
    b.set_ylabel("My framing runs (location model)")
    b.set_title("My model against MLB's leaderboard")
    b.legend(loc="upper left", fontsize=9)
    for ax in (a, b):
        ax.grid(True, axis="y", lw=0.6)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path
