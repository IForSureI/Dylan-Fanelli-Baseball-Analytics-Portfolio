"""Shape exposure: does a pitch shape lose value as a hitter sees more of it from *other* pitchers?

The analysis plan was fixed before any outcome was fit (reports/2026-shape-exposure-plan.md). This module implements
it as written:

  uv run bb shape-exposure build      # exposures for every 2024-26 pitch -> data/edge/shape_exposure/exposures.parquet
  uv run bb shape-exposure fit dev    # development fit, 2024-25
  uv run bb shape-exposure fit 2026   # confirmation, 2026 (run once, after the development run is committed)

Definitions (from the plan):
- Family: fastball (FF, SI), cutter (FC), breaking (SL, ST, SV, CU, KC, CS), offspeed (CH, FS, FO, SC).
- Shape: release speed, pfx_x, pfx_z, release side and height, extension; standardized within family x pitcher hand
  on 2024-25.
- A hitter's diet for a target pitch: every pitch he saw with the same family, pitcher hand and batter side, from
  pitchers other than today's, in a window of earlier dates (the current game is never in it).
- N = how many; K = sum of exp(-d^2 / 2h^2) over them (d = distance in standardized shape space, h = bandwidth);
  S = K / N, the share of the diet that looks like this pitch.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from baseball.edge.familiarity import GROUP, load_seq

SHAPE = ["release_speed", "pfx_x", "pfx_z", "release_pos_x", "release_pos_z", "release_extension"]
SEASONS = (2024, 2025, 2026)
DEV = (2024, 2025)
OUT = Path(__file__).resolve().parents[2] / "data" / "edge" / "shape_exposure"
SWINGS = {"swinging_strike", "swinging_strike_blocked", "foul", "foul_tip", "hit_into_play"}   # bunt attempts excluded
WHIFFS = {"swinging_strike", "swinging_strike_blocked", "foul_tip"}
MIN_N30 = 25

# (name, first day back, last day back); negative = days ahead (the lead placebo)
WINDOWS = {"30": (1, 30), "7": (1, 7), "8_30": (8, 30), "31_90": (31, 90), "lead30": (-30, -1)}
BANDWIDTHS = {"30": (0.5, 1.0, 2.0), "7": (1.0,), "8_30": (1.0,), "31_90": (1.0,), "lead30": (1.0,)}


# ---------------------------------------------------------------- data

def load(seasons=SEASONS) -> pd.DataFrame:
    cols = ["game_pk", "game_date", "game_year", "at_bat_number", "pitch_number", "pitcher", "batter", "p_throws", "stand",
            "pitch_type", "description", "zone", "balls", "strikes", "delta_run_exp", *SHAPE]
    d = pd.concat([load_seq(s)[cols] for s in seasons], ignore_index=True)
    d["family"] = d["pitch_type"].map(GROUP)
    d = d[d["family"].notna() & d[SHAPE].notna().all(axis=1)].copy()
    d["day"] = (pd.to_datetime(d["game_date"]) - pd.Timestamp("2024-01-01")).dt.days.astype(int)
    d["season"] = d["game_year"].astype(int)
    d = d.sort_values(["day", "game_pk", "at_bat_number", "pitch_number"]).reset_index(drop=True)
    return d


def standardize(d: pd.DataFrame) -> pd.DataFrame:
    """z-scores within family x pitcher hand, means and SDs from the development seasons only."""
    dev = d[d["season"].isin(DEV)]
    stats = dev.groupby(["family", "p_throws"])[SHAPE].agg(["mean", "std"])
    z = np.empty((len(d), len(SHAPE)), dtype=np.float32)
    for (fam, hand), idx in d.groupby(["family", "p_throws"]).groups.items():
        m = stats.loc[(fam, hand)]
        z[d.index.get_indexer(idx)] = ((d.loc[idx, SHAPE] - m.xs("mean", level=1).values) / m.xs("std", level=1).values).to_numpy()
    for i, c in enumerate(SHAPE):
        d[f"z_{c}"] = z[:, i]
    return d


# ---------------------------------------------------------------- exposures

def _group_exposure(day, pitcher, Z, chunk: int = 400) -> dict[str, np.ndarray]:
    """Every window and bandwidth for one batter x family x pitcher hand x batter side (rows in date order)."""
    n = len(day)
    out = {}
    for w in WINDOWS:
        out[f"N{w}"] = np.zeros(n, np.float32)
        for h in BANDWIDTHS[w]:
            out[f"K{w}_h{h}"] = np.zeros(n, np.float32)
    sq = (Z * Z).sum(1)
    for a in range(0, n, chunk):
        b = min(n, a + chunk)
        lo = np.searchsorted(day, day[a] - 90, "left")
        hi = np.searchsorted(day, day[b - 1] + 30, "right")
        dd = day[a:b, None] - day[None, lo:hi]                       # days back (positive = earlier)
        other = pitcher[a:b, None] != pitcher[None, lo:hi]
        d2 = np.maximum(sq[a:b, None] + sq[None, lo:hi] - 2 * Z[a:b] @ Z[lo:hi].T, 0)
        for w, (first, last) in WINDOWS.items():
            m = other & (dd >= first) & (dd <= last)
            out[f"N{w}"][a:b] = m.sum(1)
            for h in BANDWIDTHS[w]:
                out[f"K{w}_h{h}"][a:b] = (np.exp(-d2 / (2 * h * h)) * m).sum(1)
    return out


def build(d: pd.DataFrame | None = None) -> pd.DataFrame:
    """Exposure columns for every pitch with a complete shape (2024-26)."""
    d = standardize(load() if d is None else d)
    zc = [f"z_{c}" for c in SHAPE]
    cols = {}
    keys = ["batter", "family", "p_throws", "stand"]
    for k, idx in d.groupby(keys, sort=False).groups.items():
        g = d.loc[idx]                                                # already in time order
        e = _group_exposure(g["day"].to_numpy(), g["pitcher"].to_numpy(), g[zc].to_numpy(np.float32))
        for c, v in e.items():
            cols.setdefault(c, []).append(pd.Series(v, index=idx))
    for c, parts in cols.items():
        d[c] = pd.concat(parts).reindex(d.index).astype(np.float32)
    keep = ["game_pk", "game_date", "season", "day", "at_bat_number", "pitch_number", "pitcher", "batter", "p_throws",
            "stand", "pitch_type", "family", "description", "zone", "balls", "strikes", "delta_run_exp", *cols]
    OUT.mkdir(parents=True, exist_ok=True)
    d[keep].to_parquet(OUT / "exposures.parquet", index=False)
    return d[keep]


# ---------------------------------------------------------------- the model

def add_shares(d: pd.DataFrame) -> pd.DataFrame:
    """S{window}_h{bandwidth} = K / N (NaN when the window is empty)."""
    for w, hs in BANDWIDTHS.items():
        n = d[f"N{w}"].where(d[f"N{w}"] > 0)
        for h in hs:
            d[f"S{w}_h{h}"] = d[f"K{w}_h{h}"] / n
    return d


def frame(e: pd.DataFrame, outcome: str) -> pd.DataFrame:
    """Targets for a fit: swings (whiff) or all pitches (run value), N30 >= 25."""
    d = e[e["N30"] >= MIN_N30].copy()
    if outcome == "whiff":
        d = d[d["description"].isin(SWINGS)].copy()
        d["y"] = 100.0 * d["description"].isin(WHIFFS)
    else:
        d = d[d["delta_run_exp"].notna()].copy()
        d["y"] = -100.0 * d["delta_run_exp"]                         # pitcher's side, runs per 100 pitches
    d["week"] = d["season"].astype(str) + "-" + (d["day"] // 7).astype(str)
    d["bfam"] = d["batter"].astype(str) + "|" + d["season"].astype(str) + "|" + d["family"]
    d["pkey"] = d["pitcher"].astype(str) + "|" + d["pitch_type"] + "|" + d["season"].astype(str)
    d["fzone"] = d["family"] + "|" + d["zone"].astype("Int64").astype(str)
    d["fcount"] = d["family"] + "|" + d["balls"].astype(int).astype(str) + "-" + d["strikes"].astype(int).astype(str)
    return d


def standardizer(dev: pd.DataFrame, cols: list[str]) -> dict:
    """Family-level means and SDs of each share on the development targets (frozen for 2026)."""
    return {c: dev.groupby("family")[c].agg(["mean", "std"]) for c in cols}


def fit(d: pd.DataFrame, specs: list[tuple[str, str]], std: dict) -> pd.DataFrame:
    """y on standardized shares (each with the log of its window's count), five sets of fixed effects absorbed,
    standard errors clustered by batter. specs: [(share column, count column), ...]."""
    from scipy.stats import norm

    from baseball.stats import absorb, clustered_wls

    d = d.copy()
    names, controls = [], []
    for share, count in specs:
        s = std[share]
        d[f"s_{share}"] = (d[share] - d["family"].map(s["mean"])) / d["family"].map(s["std"])
        d[f"log{count}"] = np.log(d[count].clip(lower=1))
        names.append(f"s_{share}")
        controls.append(f"log{count}")
    controls = list(dict.fromkeys(controls))
    d = d.dropna(subset=names + controls + ["y"])
    for k in ("bfam", "pkey"):                       # groups with one row carry no within information
        d = d[d.groupby(k)[k].transform("size") > 1]
    r = absorb(d, ["y", *names, *controls], ["bfam", "pkey", "fzone", "fcount", "week"])
    beta, se = clustered_wls(r["y"], r[names + controls].to_numpy(), np.ones(len(r)), d["batter"].to_numpy())
    res = pd.DataFrame({"term": names + controls, "coef": beta, "se": se})
    res["lo"], res["hi"] = res["coef"] - 1.96 * res["se"], res["coef"] + 1.96 * res["se"]
    res["p"] = 2 * norm.sf(np.abs(res["coef"] / res["se"]))
    res["n"], res["batters"] = len(d), d["batter"].nunique()
    return res


SPECS = {
    "H1": [("S30_h1.0", "N30")],
    "H2_narrow": [("S30_h0.5", "N30")],
    "H2_wide": [("S30_h2.0", "N30")],
    "H3": [("S30_h1.0", "N30"), ("Slead30_h1.0", "Nlead30")],
    "H4": [("S7_h1.0", "N7"), ("S8_30_h1.0", "N8_30"), ("S31_90_h1.0", "N31_90")],
}


def run(which: str, e: pd.DataFrame | None = None) -> pd.DataFrame:
    """which = 'dev' (2024-25) or '2026'. Standardizers always come from the development targets."""
    e = add_shares(pd.read_parquet(OUT / "exposures.parquet") if e is None else e)
    rows = []
    for outcome in ("whiff", "rv"):
        fr = frame(e, outcome)
        dev = fr[fr["season"].isin(DEV)]
        allshares = sorted({s for sp in SPECS.values() for s, _ in sp})
        std = standardizer(dev, allshares)
        target = dev if which == "dev" else fr[fr["season"].eq(2026)]
        tests = SPECS if outcome == "whiff" else {"H5": SPECS["H1"]}
        for name, spec in tests.items():
            res = fit(target, spec, std)
            res.insert(0, "test", name)
            res.insert(1, "outcome", outcome)
            rows.append(res)
            print(res.round(4).to_string(index=False), flush=True)
    out = pd.concat(rows, ignore_index=True)
    out.to_csv(OUT / f"results_{which}.csv", index=False)
    return out


# ---------------------------------------------------------------- follow-up designs (exploratory; see the follow-up plan)

def _season_exposure(day, season, pitcher, Z, chunk: int = 400) -> tuple[np.ndarray, np.ndarray]:
    """Design B: N and K (h = 1) over all of the hitter's other same-season dates, before and after."""
    n = len(day)
    N, K = np.zeros(n, np.float32), np.zeros(n, np.float32)
    sq = (Z * Z).sum(1)
    for a in range(0, n, chunk):
        b = min(n, a + chunk)
        lo = np.searchsorted(day, day[a] - 250, "left")
        hi = np.searchsorted(day, day[b - 1] + 250, "right")
        m = (season[a:b, None] == season[None, lo:hi]) & (day[a:b, None] != day[None, lo:hi]) \
            & (pitcher[a:b, None] != pitcher[None, lo:hi])
        d2 = np.maximum(sq[a:b, None] + sq[None, lo:hi] - 2 * Z[a:b] @ Z[lo:hi].T, 0)
        N[a:b] = m.sum(1)
        K[a:b] = (np.exp(-d2 / 2) * m).sum(1)
    return N, K


def series_opponents(g: pd.DataFrame) -> pd.DataFrame:
    """For every (team, game): the opponent of the team's previous and next series (consecutive games against one
    opponent form a series, off days included). g: one row per team-game with team, season, day, game_pk, opp."""
    g = g.sort_values(["team", "season", "day", "game_pk"]).copy()
    new = (g["opp"] != g.groupby(["team", "season"])["opp"].shift()).astype(int)
    g["series"] = new.groupby([g["team"], g["season"]]).cumsum()
    s = g.groupby(["team", "season", "series"])["opp"].first().reset_index()
    s["prev_opp"] = s.groupby(["team", "season"])["opp"].shift(1)
    s["next_opp"] = s.groupby(["team", "season"])["opp"].shift(-1)
    return g.merge(s[["team", "season", "series", "prev_opp", "next_opp"]], on=["team", "season", "series"])


def _staff_share(Zt, pool, chunk: int = 2000) -> np.ndarray:
    """Mean kernel (h = 1) between each target shape and a staff's pitches."""
    out = np.empty(len(Zt), np.float32)
    sp = (pool * pool).sum(1)
    for a in range(0, len(Zt), chunk):
        z = Zt[a:a + chunk]
        d2 = np.maximum((z * z).sum(1)[:, None] + sp[None, :] - 2 * z @ pool.T, 0)
        out[a:a + chunk] = np.exp(-d2 / 2).mean(1)
    return out


def build_followup(pool_size: int = 800, seed: int = 0) -> pd.DataFrame:
    """Both follow-up designs' variables for every pitch, merged onto exposures.parquet -> followup.parquet."""
    cols_extra = ["home_team", "away_team", "inning_topbot"]
    d = pd.concat([load_seq(s)[["game_pk", "at_bat_number", "pitch_number", *cols_extra]] for s in SEASONS], ignore_index=True)
    base = standardize(load())
    base = base.merge(d, on=["game_pk", "at_bat_number", "pitch_number"], how="left")
    base["bat_team"] = np.where(base["inning_topbot"].eq("Top"), base["away_team"], base["home_team"])
    base["fld_team"] = np.where(base["inning_topbot"].eq("Top"), base["home_team"], base["away_team"])
    zc = [f"z_{c}" for c in SHAPE]
    # Design B: season-long diet
    NS = np.zeros(len(base), np.float32); KS = np.zeros(len(base), np.float32)
    for _, idx in base.groupby(["batter", "family", "p_throws", "stand"], sort=False).groups.items():
        g = base.loc[idx]
        n_, k_ = _season_exposure(g["day"].to_numpy(), g["season"].to_numpy(), g["pitcher"].to_numpy(),
                                  g[zc].to_numpy(np.float32))
        pos = base.index.get_indexer(idx)
        NS[pos], KS[pos] = n_, k_
    base["Nseason"], base["Kseason_h1.0"] = NS, KS
    # Design A: previous- and next-series opponent staffs
    games = base.groupby(["game_pk", "bat_team"]).agg(season=("season", "first"), day=("day", "first"),
                                                      opp=("fld_team", "first")).reset_index().rename(columns={"bat_team": "team"})
    so = series_opponents(games)
    base = base.merge(so[["game_pk", "team", "prev_opp", "next_opp"]].rename(columns={"team": "bat_team"}),
                      on=["game_pk", "bat_team"], how="left")
    rng = np.random.default_rng(seed)
    pools = {}
    for key, idx in base.groupby(["fld_team", "season", "family", "p_throws", "stand"]).groups.items():
        z = base.loc[idx, zc].to_numpy(np.float32)
        pools[key] = z if len(z) <= pool_size else z[rng.choice(len(z), pool_size, replace=False)]
    for which in ("prev", "next"):
        out = np.full(len(base), np.nan, np.float32)
        for key, idx in base.groupby([f"{which}_opp", "season", "family", "p_throws", "stand"]).groups.items():
            pool = pools.get(key)
            if pool is None or len(pool) < 50:
                continue
            pos = base.index.get_indexer(idx)
            out[pos] = _staff_share(base.loc[idx, zc].to_numpy(np.float32), pool)
        base[f"SS_{which}"] = out
    keep = ["game_pk", "at_bat_number", "pitch_number", "Nseason", "Kseason_h1.0", "prev_opp", "next_opp", "SS_prev", "SS_next"]
    base[keep].to_parquet(OUT / "followup.parquet", index=False)
    return base[keep]


FOLLOWUP_SPECS = {
    "A_schedule": [("SS_prev", None), ("SS_next", None)],
    "B_timing": [("S30_h1.0", "N30"), ("Slead30_h1.0", "Nlead30"), ("Sseason_h1.0", "Nseason")],
}


def fit_followup(seasons=SEASONS) -> pd.DataFrame:
    """Both designs, pooled and by season, on whiff per swing. Standardizers: development targets, as in the plan."""
    from scipy.stats import norm

    from baseball.stats import absorb, clustered_wls

    e = add_shares(pd.read_parquet(OUT / "exposures.parquet"))
    f = pd.read_parquet(OUT / "followup.parquet")
    e = e.merge(f, on=["game_pk", "at_bat_number", "pitch_number"], how="left")
    e["Sseason_h1.0"] = e["Kseason_h1.0"] / e["Nseason"].where(e["Nseason"] > 0)
    fr = frame(e, "whiff")
    dev = fr[fr["season"].isin(DEV)]
    std = standardizer(dev, ["SS_prev", "SS_next", "S30_h1.0", "Slead30_h1.0", "Sseason_h1.0"])
    rows = []
    for design, spec in FOLLOWUP_SPECS.items():
        for label, ss in [("pooled", list(seasons))] + [(str(s), [s]) for s in seasons]:
            d = fr[fr["season"].isin(ss)].copy()
            names, controls = [], []
            for share, count in spec:
                d[f"s_{share}"] = (d[share] - d["family"].map(std[share]["mean"])) / d["family"].map(std[share]["std"])
                names.append(f"s_{share}")
                if count:
                    d[f"log{count}"] = np.log(d[count].clip(lower=1))
                    controls.append(f"log{count}")
            d = d.dropna(subset=names + controls + ["y"])
            for k in ("bfam", "pkey"):
                d = d[d.groupby(k)[k].transform("size") > 1]
            r = absorb(d, ["y", *names, *controls], ["bfam", "pkey", "fzone", "fcount", "week"])
            X = r[names + controls].to_numpy()
            beta, se = clustered_wls(r["y"], X, np.ones(len(r)), d["batter"].to_numpy())
            res = pd.DataFrame({"design": design, "sample": label, "term": names + controls, "coef": beta, "se": se})
            if design == "A_schedule":
                # previous minus next, with the covariance from the same clustered fit
                cov = _clustered_cov(r["y"].to_numpy(), X, d["batter"].to_numpy())
                diff = beta[0] - beta[1]
                sd = float(np.sqrt(cov[0, 0] + cov[1, 1] - 2 * cov[0, 1]))
                res = pd.concat([res, pd.DataFrame([{"design": design, "sample": label, "term": "prev minus next",
                                                     "coef": diff, "se": sd}])], ignore_index=True)
            res["lo"], res["hi"] = res["coef"] - 1.96 * res["se"], res["coef"] + 1.96 * res["se"]
            res["p"] = 2 * norm.sf(np.abs(res["coef"] / res["se"]))
            res["n"], res["batters"] = len(d), d["batter"].nunique()
            rows.append(res)
            print(res.round(4).to_string(index=False), flush=True)
    out = pd.concat(rows, ignore_index=True)
    out.to_csv(OUT / "results_followup.csv", index=False)
    return out


def _clustered_cov(y, X, clusters):
    """The clustered covariance matrix (same small-sample factor as baseball.stats.clustered_wls)."""
    bread = np.linalg.pinv(X.T @ X)
    e = y - X @ (bread @ (X.T @ y))
    groups, inv = np.unique(clusters, return_inverse=True)
    S = np.zeros((len(groups), X.shape[1]))
    np.add.at(S, inv, X * e[:, None])
    n, k, G = len(y), X.shape[1], len(groups)
    adj = (G / max(G - 1, 1)) * ((n - 1) / max(n - k, 1))
    return adj * bread @ (S.T @ S) @ bread


# ---------------------------------------------------------------- figure

def figure(out_path: Path | None = None) -> Path:
    """Three panels: the planned test and its placebo, the timing design, the schedule design."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from baseball.viz import _style

    dev = pd.read_csv(OUT / "results_dev.csv")
    conf = pd.read_csv(OUT / "results_2026.csv")
    fu = pd.read_csv(OUT / "results_followup.csv")
    out_path = Path(out_path or OUT / "shape_exposure.png")
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6), gridspec_kw={"width_ratios": [1, 1.1, 0.9]})
    BLUE, ORANGE, GREY = "#2f5d8a", "#c8692e", "#8a8a8a"

    def bars(ax, labels, rows, colors):
        y = np.arange(len(rows))[::-1]
        for yi, r, c in zip(y, rows, colors):
            ax.errorbar(r["coef"], yi, xerr=1.96 * r["se"], fmt="o", color=c, capsize=3, lw=2)
        ax.set_yticks(y); ax.set_yticklabels(labels); ax.axvline(0, color="#999", lw=0.8); _style(ax)

    pick = lambda t, test, term: t[(t["test"] == test) & (t["term"] == term) & (t["outcome"] == "whiff")].iloc[0]  # noqa: E731
    a = axes[0]
    bars(a, ["Seen, 2024-25", "Seen, 2026", "About to see, 2024-25", "About to see, 2026"],
         [pick(dev, "H3", "s_S30_h1.0"), pick(conf, "H3", "s_S30_h1.0"), pick(dev, "H3", "s_Slead30_h1.0"),
          pick(conf, "H3", "s_Slead30_h1.0")], [BLUE, BLUE, ORANGE, ORANGE])
    a.set_title("The planned test fails its placebo", loc="left", fontsize=12, fontweight="bold")
    a.set_xlabel("Whiff points per SD of similar-shape share")

    b = axes[1]
    pf = fu[(fu["design"] == "B_timing") & (fu["sample"] == "pooled")].set_index("term")
    bars(b, ["Last 30 days", "Next 30 days (placebo)", "His whole season"],
         [pf.loc["s_S30_h1.0"], pf.loc["s_Slead30_h1.0"], pf.loc["s_Sseason_h1.0"]], [BLUE, ORANGE, GREY])
    b.set_title("Recent exposure, beyond his season's diet", loc="left", fontsize=12, fontweight="bold")
    b.set_xlabel("Whiff points per SD, all three in one model (2024-26)")

    c = axes[2]
    sf = fu[(fu["design"] == "A_schedule") & (fu["sample"] == "pooled")].set_index("term")
    bars(c, ["Last series' staff", "Next series' staff (placebo)", "Last minus next"],
         [sf.loc["s_SS_prev"], sf.loc["s_SS_next"], sf.loc["prev minus next"]], [BLUE, ORANGE, GREY])
    c.set_title("The schedule shows none", loc="left", fontsize=12, fontweight="bold")
    c.set_xlabel("Whiff points per SD (2024-26)")

    fig.text(0.01, 0.005,
             "MLB regular seasons 2024-26, Statcast via Baseball Savant. Swings on pitches whose hitter saw 25+ same-family pitches from other pitchers in the last 30 days. "
             "Fixed effects: batter x season x family, pitcher x pitch type x season,\nfamily x zone, family x count, season x week. "
             "95% intervals clustered by batter. Left panel: the plan's H3 model. Middle and right: follow-up designs specified after the placebo failed, before they were fit.",
             fontsize=7.5, color="#555")
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    return out_path
