"""Hitter whiff rate (whiffs per swing) as a hierarchical Bayesian model in PyMC, checked against the
Reliability Atlas's closed-form regression and tested on 2026 out of sample.

Two models, both binomial on the logit scale (logit-normal hierarchy):

  one-season   fit on 2025 only.  logit p_i = mu + sigma * z_i,  z_i ~ N(0, 1),  whiffs_i ~ Binomial(swings_i, p_i).
               Its 2026 forecast assumes talent does not change between seasons.
  two-season   fit on 2024 and 2025.  Each season has its own mu_t and sigma_t, and a hitter's standardized
               talent carries over with correlation rho:  z_2025 = rho * z_2024 + sqrt(1 - rho^2) * e.
               The 2026 forecast steps the same way once more:  z_2026 = rho * z_2025 + sqrt(1 - rho^2) * e.
               rho is learned from 2024 -> 2025 only.  No 2026 data enters any fit.

The comparison is the Atlas's regress(): estimate = league + w (obs - league), w = n / (n + M), M = 55.4 swings,
tau = 0.0618, and rho = 0.931 for next season (constants pooled over 2024-26, so the Atlas has seen 2026).

Scoring 2026 (the Atlas's own convention): the league's shift from 2025 to 2026 is removed using 2026's actual
league mean, for both methods, so a league-wide move isn't anyone's error.  Every hitter counts once.
Targets: hitters with 1+ swing in 2025 and at least M/5 = 11 swings in 2026.

Run (from the repo root):
    uv run --group bayes python reports/bayes/whiff_hierarchical.py
    uv run --group bayes python reports/bayes/whiff_hierarchical.py --sigma-sd 0.05        # exercise 1: a bad prior
    uv run --group bayes python reports/bayes/whiff_hierarchical.py --sample-hitters 25    # exercise 1: a small roster
    uv run --group bayes python reports/bayes/whiff_hierarchical.py --by-pitch-group       # exercise 2
    uv run --group bayes python reports/bayes/whiff_hierarchical.py --by-pitch-group --centered  # exercise 3
    uv run --group bayes python reports/bayes/whiff_hierarchical.py --counts my_counts.csv # skip the pitch data

Reads regular-season pitches from data/seq/ (bb seq <season>), or a counts CSV with columns
season, batter, player_name, pitch_group, swings, whiffs (written to reports/bayes/out/ on every run).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"

# The repo's definitions (baseball.evaluation.arsenal, baseball.evaluation.reliability), copied so the counts
# step also runs where the package isn't installed.  test_definitions_match_repo() checks they agree.
SWINGS = ("swinging_strike", "swinging_strike_blocked", "foul", "foul_tip", "foul_bunt", "missed_bunt",
          "hit_into_play", "hit_into_play_no_out", "hit_into_play_score")
WHIFFS = ("swinging_strike", "swinging_strike_blocked", "foul_tip", "missed_bunt")
NO_PITCH = ("automatic_ball", "automatic_strike")
PITCH_GROUP = {"FF": "fastball", "SI": "fastball", "FC": "fastball",
               "SL": "breaking", "ST": "breaking", "CU": "breaking", "KC": "breaking", "SV": "breaking",
               "CS": "breaking", "CH": "offspeed", "FS": "offspeed", "FO": "offspeed", "SC": "offspeed"}
GROUPS = ("fastball", "breaking", "offspeed", "other")

# Atlas constants for hitter/whiff (baseball/evaluation/reliability_params.json, built 2026-10-13)
TARGET_ACCEPT = 0.9
CENTERED = False
ATLAS = {"M": 55.40049, "tau": 0.061794, "rho": 0.930619}


# ---------------------------------------------------------------- data

def counts_from_pitches(p: pd.DataFrame) -> pd.DataFrame:
    """Hitter x season x pitch group swings and whiffs from pitch rows (regular season only)."""
    d = p[p["game_type"].eq("R") & ~p["description"].isin(NO_PITCH)]
    d = d.drop_duplicates(["game_pk", "at_bat_number", "pitch_number"])
    d = d.assign(season=d["game_year"].astype(int),
                 pitch_group=d["pitch_type"].map(PITCH_GROUP).fillna("other"),
                 swings=d["description"].isin(SWINGS).astype(int),
                 whiffs=d["description"].isin(WHIFFS).astype(int))
    d = d[d["swings"].eq(1)]
    names = d.groupby("batter")["player_name"].agg(lambda s: s.mode().iat[0])
    c = d.groupby(["season", "batter", "pitch_group"], as_index=False)[["swings", "whiffs"]].sum()
    return c.assign(player_name=c["batter"].map(names))[["season", "batter", "player_name", "pitch_group", "swings", "whiffs"]]


def load_counts(seasons, csv: str | None = None) -> pd.DataFrame:
    if csv:
        c = pd.read_csv(csv)
        return c[c["season"].isin(seasons)].reset_index(drop=True)
    from baseball.edge.familiarity import seq_parts

    cols = ["game_pk", "game_year", "game_type", "at_bat_number", "pitch_number", "batter", "player_name",
            "pitch_type", "description"]
    frames = []
    for s in seasons:
        parts = seq_parts(s)
        if not parts:
            raise FileNotFoundError(f"No data/seq/ files for {s}. Run `uv run bb seq {s}`, or pass --counts.")
        frames.append(pd.concat([pd.read_parquet(x, columns=cols) for x in parts], ignore_index=True))
    return counts_from_pitches(pd.concat(frames, ignore_index=True))


def hitters(c: pd.DataFrame, season: int) -> pd.DataFrame:
    h = c[c["season"].eq(season)].groupby(["batter", "player_name"], as_index=False)[["swings", "whiffs"]].sum()
    return h[h["swings"] > 0].reset_index(drop=True)


def league_mean(h: pd.DataFrame) -> float:
    return float(h["whiffs"].sum() / h["swings"].sum())


# ---------------------------------------------------------------- the closed form (the Atlas)

def atlas_season(obs, n, league, level):
    """regress(..., horizon='season'): his true 2025 level."""
    from statistics import NormalDist

    M, tau = ATLAS["M"], ATLAS["tau"]
    w = n / (n + M)
    est = league + w * (obs - league)
    sd = tau * np.sqrt(1 - w)
    z = NormalDist().inv_cdf(0.5 + level / 2)
    return est, np.clip(est - z * sd, 0, 1), np.clip(est + z * sd, 0, 1), w


def atlas_next(obs, n, league, n2, level):
    """regress(..., horizon='next_season') plus the 2026 sample's own noise, M tau^2 / n2 (the predictive
    interval the Atlas validated)."""
    from statistics import NormalDist

    M, tau, rho = ATLAS["M"], ATLAS["tau"], ATLAS["rho"]
    w = n / (n + M)
    est = league + rho * w * (obs - league)
    sd = np.sqrt(tau ** 2 * (1 - rho ** 2 * w) + M * tau ** 2 / n2)
    z = NormalDist().inv_cdf(0.5 + level / 2)
    return est, est - z * sd, est + z * sd


# ---------------------------------------------------------------- the PyMC models

def fit_one_season(h: pd.DataFrame, mu_sd: float, sigma_sd: float, draws: int, tune: int, chains: int, seed: int):
    import pymc as pm

    with pm.Model(coords={"hitter": h["batter"].astype(str).to_numpy()}) as model:
        mu = pm.Normal("mu", -1.1, mu_sd)                       # logit(0.25) = -1.1
        sigma = pm.HalfNormal("sigma", sigma_sd)                # spread of true talent, logit scale
        z = pm.Normal("z", 0, 1, dims="hitter")                 # non-centered: samples cleanly at small n
        p = pm.Deterministic("p", pm.math.invlogit(mu + sigma * z), dims="hitter")
        pm.Binomial("whiffs", n=h["swings"].to_numpy(), p=p, observed=h["whiffs"].to_numpy(), dims="hitter")
        idata = pm.sample(draws=draws, tune=tune, chains=chains, cores=min(chains, 4), random_seed=seed,
                          target_accept=TARGET_ACCEPT, progressbar=False)
    return model, idata


def fit_by_pitch_group(c: pd.DataFrame, season: int, mu_sd: float, sigma_sd: float, draws: int, tune: int,
                       chains: int, seed: int):
    """Exercise 2: a pitch-group level.  logit p_ig = mu + beta_g + sigma * z_i + sigma_g * u_ig.
    beta_g: how much harder each pitch group is to hit for everyone.  sigma_g: how much hitters differ from
    their own overall level on that group.  A hitter's overall rate is his swing-weighted mix of p_ig."""
    import pymc as pm

    d = c[c["season"].eq(season) & c["swings"].gt(0)].reset_index(drop=True)
    hit_ids, hit_idx = np.unique(d["batter"].to_numpy(), return_inverse=True)
    grp_idx = d["pitch_group"].map({g: k for k, g in enumerate(GROUPS)}).to_numpy()
    with pm.Model(coords={"hitter": hit_ids.astype(str), "group": list(GROUPS), "cell": np.arange(len(d))}) as model:
        mu = pm.Normal("mu", -1.1, mu_sd)
        beta = pm.Normal("beta", 0, 1, dims="group")
        sigma = pm.HalfNormal("sigma", sigma_sd)
        sigma_g = pm.HalfNormal("sigma_g", sigma_sd, dims="group")
        z = pm.Normal("z", 0, 1, dims="hitter")
        if CENTERED:   # exercise 3: the hitter-by-group effects sampled directly, d ~ N(0, sigma_g)
            dev = pm.Normal("d", 0, sigma_g[grp_idx], dims="cell")
        else:          # non-centered: u ~ N(0, 1), effect = sigma_g * u
            dev = sigma_g[grp_idx] * pm.Normal("u", 0, 1, dims="cell")
        p = pm.Deterministic("p_cell", pm.math.invlogit(mu + beta[grp_idx] + sigma * z[hit_idx] + dev), dims="cell")
        pm.Binomial("whiffs", n=d["swings"].to_numpy(), p=p, observed=d["whiffs"].to_numpy(), dims="cell")
        idata = pm.sample(draws=draws, tune=tune, chains=chains, cores=min(chains, 4), random_seed=seed,
                          target_accept=TARGET_ACCEPT, progressbar=False)
    return model, idata, d, hit_ids, hit_idx


def fit_two_season(c: pd.DataFrame, s0: int, s1: int, mu_sd: float, sigma_sd: float, draws: int, tune: int,
                   chains: int, seed: int):
    import pymc as pm

    h0, h1 = hitters(c, s0), hitters(c, s1)
    ids = np.union1d(h0["batter"], h1["batter"])
    n = np.zeros((len(ids), 2), int)
    y = np.zeros((len(ids), 2), int)
    for k, h in enumerate((h0, h1)):
        pos = np.searchsorted(ids, h["batter"].to_numpy())
        n[pos, k], y[pos, k] = h["swings"], h["whiffs"]
    with pm.Model(coords={"hitter": ids.astype(str), "season": [s0, s1]}) as model:
        mu = pm.Normal("mu", -1.1, mu_sd, dims="season")
        sigma = pm.HalfNormal("sigma", sigma_sd, dims="season")
        rho = pm.Uniform("rho", -1, 1)                          # year-to-year talent correlation
        z0 = pm.Normal("z0", 0, 1, dims="hitter")
        e1 = pm.Normal("e1", 0, 1, dims="hitter")
        z1 = pm.Deterministic("z1", rho * z0 + pm.math.sqrt(1 - rho ** 2) * e1, dims="hitter")
        z = pm.math.stack([z0, z1], axis=1)
        p = pm.Deterministic("p", pm.math.invlogit(mu + sigma * z), dims=("hitter", "season"))
        pm.Binomial("whiffs", n=n, p=p, observed=y, dims=("hitter", "season"))
        idata = pm.sample(draws=draws, tune=tune, chains=chains, cores=min(chains, 4), random_seed=seed,
                          target_accept=TARGET_ACCEPT, progressbar=False)
    return model, idata, ids


def draws_of(idata, name: str) -> np.ndarray:
    """Posterior draws flattened over chains: shape (draws, ...)."""
    x = idata.posterior[name]
    return x.stack(sample=("chain", "draw")).transpose("sample", ...).to_numpy()


def diagnostics(idata, var_names) -> dict:
    import arviz as az

    s = az.summary(idata, var_names=var_names, kind="diagnostics")
    div = int(idata.sample_stats["diverging"].sum())
    return {"max_rhat": float(s["r_hat"].max()), "min_ess_bulk": float(s["ess_bulk"].min()),
            "min_ess_tail": float(s["ess_tail"].min()), "divergences": div,
            "n_params_checked": int(len(s))}


# ---------------------------------------------------------------- scoring 2026

def pit_binomial_mixture(y: np.ndarray, n: np.ndarray, p_draws: np.ndarray, rng) -> np.ndarray:
    """Randomized PIT of an observed count under a posterior predictive Binomial(n, p_s) mixture.
    Uniform(0, 1) if the predictive is calibrated, so an x% central interval covers when |PIT - 0.5| < x/2.
    Randomizing inside the jump at y makes discrete counts fair (no free coverage from ties)."""
    from scipy.stats import binom

    F_hi = binom.cdf(y[None, :], n[None, :], p_draws).mean(0)
    F_lo = binom.cdf(y[None, :] - 1, n[None, :], p_draws).mean(0)
    return F_lo + rng.uniform(size=len(y)) * (F_hi - F_lo)


def compare_2025(t25: pd.DataFrame) -> pd.DataFrame:
    """Where the two methods agree and differ on 2025 talent, by the Atlas weight on his data."""
    rows = []
    groups = [("all", np.ones(len(t25), bool))] + [(b, t25["bucket"].eq(b).to_numpy())
                                                   for b in ["< M/4", "M/4 to M", "M to 3M", "3M +"]]
    q = t25["obs"].where(t25["swings"] >= 3 * ATLAS["M"])
    groups += [("extreme: top 5% raw (3M+)", (q >= q.quantile(0.95)).to_numpy()),
               ("extreme: bottom 5% raw (3M+)", (q <= q.quantile(0.05)).to_numpy())]
    for name, m in groups:
        x = t25[m]
        d = 100 * (x["bayes_est"] - x["atlas_est"])
        rows.append({"group": name, "hitters": int(m.sum()), "median_swings": float(x["swings"].median()),
                     "mean_raw_pts": 100 * x["obs"].mean(),
                     "mean_atlas_pts": 100 * x["atlas_est"].mean(), "mean_bayes_pts": 100 * x["bayes_est"].mean(),
                     "mean_abs_diff_pts": float(d.abs().mean()), "max_abs_diff_pts": float(d.abs().max()),
                     "atlas_width95_pts": 100 * float((x["atlas_hi95"] - x["atlas_lo95"]).mean()),
                     "bayes_width95_pts": 100 * float((x["bayes_hi95"] - x["bayes_lo95"]).mean()),
                     "bayes_upper_share": float(((x["bayes_hi95"] - x["bayes_est"]) /
                                                 (x["bayes_hi95"] - x["bayes_lo95"])).mean()),
                     "bayes_implied_M_median": float(x["bayes_implied_M"].median())})
    return pd.DataFrame(rows)


def bucket(w: np.ndarray) -> np.ndarray:
    labels = np.array(["< M/4", "M/4 to M", "M to 3M", "3M +"])
    return labels[np.digitize(w, [0.2, 0.5, 0.75])]


def score(t: pd.DataFrame, methods: dict[str, dict]) -> pd.DataFrame:
    """methods: name -> {'est': forecast of the 2026 rate, 'cov80', 'cov95': bool arrays}."""
    rows = []
    for b in ["all", "< M/4", "M/4 to M", "M to 3M", "3M +"]:
        m = np.ones(len(t), bool) if b == "all" else t["bucket"].eq(b).to_numpy()
        for name, f in methods.items():
            e = f["est"][m] - t["obs26"].to_numpy()[m]
            rows.append({"bucket": b, "method": name, "hitters": int(m.sum()),
                         "mae_pts": 100 * np.mean(np.abs(e)), "rmse_pts": 100 * np.sqrt(np.mean(e ** 2)),
                         "cov80": 100 * f["cov80"][m].mean() if "cov80" in f else np.nan,
                         "cov95": 100 * f["cov95"][m].mean() if "cov95" in f else np.nan,
                         "width80_pts": 100 * np.mean(f["w80"][m]) if "w80" in f else np.nan})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- main

def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--counts", help="counts CSV instead of data/seq/")
    ap.add_argument("--mu-sd", type=float, default=1.0, help="prior sd of the league mean, logit scale (default 1)")
    ap.add_argument("--sigma-sd", type=float, default=0.5, help="HalfNormal scale of the talent spread, logit (0.5)")
    ap.add_argument("--draws", type=int, default=1000)
    ap.add_argument("--tune", type=int, default=1000)
    ap.add_argument("--chains", type=int, default=4)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--by-pitch-group", action="store_true", help="exercise 2: add a pitch-group level (2025)")
    ap.add_argument("--skip-two-season", action="store_true", help="faster: one-season model only")
    ap.add_argument("--sample-hitters", type=int, default=0,
                    help="exercise 1: fit on a random N hitters only (a small roster), to see when the prior matters")
    ap.add_argument("--target-accept", type=float, default=0.9, help="NUTS step-size target (raise to 0.95-0.99 to fix divergences)")
    ap.add_argument("--centered", action="store_true", help="exercise 3: centered hitter-by-group effects (with --by-pitch-group)")
    ap.add_argument("--tag", default="", help="suffix for output files, e.g. tight_prior")
    a = ap.parse_args(argv)

    global TARGET_ACCEPT, CENTERED
    TARGET_ACCEPT, CENTERED = a.target_accept, a.centered
    OUT.mkdir(parents=True, exist_ok=True)
    tag = f"_{a.tag}" if a.tag else ""
    c = load_counts([2024, 2025, 2026], a.counts)
    if not a.counts:
        c.to_csv(OUT / "whiff_counts_2024_2026.csv", index=False)
    h25, h26 = hitters(c, 2025), hitters(c, 2026)
    lg25, lg26 = league_mean(h25), league_mean(h26)
    shift = lg26 - lg25
    if a.sample_hitters:                                                  # league means stay the full league's
        keep = h25.sample(a.sample_hitters, random_state=a.seed)["batter"]
        h25 = h25[h25["batter"].isin(keep)].reset_index(drop=True)
        c = c[~c["season"].eq(2025) | c["batter"].isin(keep)]
        a.skip_two_season = True
    rng = np.random.default_rng(a.seed)
    print(f"2025: {len(h25)} hitters, {h25['swings'].sum():,} swings, league whiff {lg25:.4f}")
    print(f"2026: {len(h26)} hitters, {h26['swings'].sum():,} swings, league whiff {lg26:.4f} (shift {100 * shift:+.2f} pts)")

    # --- 2025: the one-season model against the closed form
    if a.by_pitch_group:
        _, idata, d, hit_ids, hit_idx = fit_by_pitch_group(c, 2025, a.mu_sd, a.sigma_sd, a.draws, a.tune, a.chains, a.seed)
        pc = draws_of(idata, "p_cell")                                   # (S, cells)
        sw = d["swings"].to_numpy()
        num = np.zeros((pc.shape[0], len(hit_ids)))
        for k in range(pc.shape[1]):
            num[:, hit_idx[k]] += pc[:, k] * sw[k]
        p25 = num / np.bincount(hit_idx, weights=sw)[None, :]            # his mix-weighted overall rate
        p25 = pd.DataFrame(p25, columns=hit_ids)[h25["batter"].to_numpy()].to_numpy()
        diag = diagnostics(idata, ["mu", "beta", "sigma", "sigma_g"])
        import arviz as az
        print(az.summary(idata, var_names=["mu", "beta", "sigma", "sigma_g"]))
    else:
        _, idata = fit_one_season(h25, a.mu_sd, a.sigma_sd, a.draws, a.tune, a.chains, a.seed)
        p25 = draws_of(idata, "p")
        diag = diagnostics(idata, ["mu", "sigma", "z"])
        import arviz as az
        print(az.summary(idata, var_names=["mu", "sigma"]))
    obs25, n25 = (h25["whiffs"] / h25["swings"]).to_numpy(), h25["swings"].to_numpy(float)
    est, lo95, hi95, w = atlas_season(obs25, n25, lg25, 0.95)
    _, lo80, hi80, _ = atlas_season(obs25, n25, lg25, 0.80)
    t25 = h25.assign(obs=obs25, w_atlas=w, bucket=bucket(w),
                     atlas_est=est, atlas_lo95=lo95, atlas_hi95=hi95, atlas_lo80=lo80, atlas_hi80=hi80,
                     bayes_est=p25.mean(0), bayes_lo95=np.quantile(p25, 0.025, 0), bayes_hi95=np.quantile(p25, 0.975, 0),
                     bayes_lo80=np.quantile(p25, 0.10, 0), bayes_hi80=np.quantile(p25, 0.90, 0))
    with np.errstate(invalid="ignore", divide="ignore"):
        wb = (t25["bayes_est"] - lg25) / (t25["obs"] - lg25)             # the weight the model put on his data
        t25["bayes_implied_M"] = np.where((wb > 0.02) & (wb < 0.98), n25 * (1 - wb) / wb, np.nan)
    t25.to_csv(OUT / f"estimates_2025{tag}.csv", index=False)
    cmp25 = compare_2025(t25)
    cmp25.to_csv(OUT / f"compare_2025{tag}.csv", index=False)
    print(cmp25.round(2).to_string(index=False))

    # --- 2026: forecasts and scoring
    t = h25[["batter", "player_name", "swings", "whiffs"]].merge(
        h26[["batter", "swings", "whiffs"]], on="batter", suffixes=("25", "26"))
    t = t[t["swings26"] >= ATLAS["M"] / 5].reset_index(drop=True)
    pos = h25.reset_index().set_index("batter").loc[t["batter"], "index"].to_numpy()
    t["obs25"], t["obs26"] = t["whiffs25"] / t["swings25"], t["whiffs26"] / t["swings26"]
    t["bucket"] = bucket(t["swings25"] / (t["swings25"] + ATLAS["M"]))
    n2, y2 = t["swings26"].to_numpy(), t["whiffs26"].to_numpy()

    methods = {}
    e, l95, u95 = atlas_next(t["obs25"].to_numpy(), t["swings25"].to_numpy(float), lg25, n2, 0.95)
    _, l80, u80 = atlas_next(t["obs25"].to_numpy(), t["swings25"].to_numpy(float), lg25, n2, 0.80)
    y26 = t["obs26"].to_numpy() - shift                                    # Atlas convention: obs2 - shift
    from scipy.stats import norm
    methods["Atlas closed form"] = {"est": e + shift, "cov80": (y26 >= l80) & (y26 <= u80),
                                    "cov95": (y26 >= l95) & (y26 <= u95), "w80": u80 - l80,
                                    "pit": norm.cdf((y26 - e) / ((u95 - l95) / (2 * norm.ppf(0.975))))}
    methods["Raw 2025 rate"] = {"est": t["obs25"].to_numpy() + shift}
    methods["League mean"] = {"est": np.full(len(t), lg26)}

    def logit(x):
        return np.log(x / (1 - x))

    dl = logit(lg26) - logit(lg25)                                       # the same league shift, on the logit scale

    def add_bayes(name, p26):
        p26 = 1 / (1 + np.exp(-(logit(np.clip(p26, 1e-9, 1 - 1e-9)) + dl)))
        pit = pit_binomial_mixture(y2, n2, p26, rng)
        sims = rng.binomial(n2[None, :], p26) / n2[None, :]
        methods[name] = {"est": p26.mean(0), "cov80": np.abs(pit - 0.5) < 0.40, "cov95": np.abs(pit - 0.5) < 0.475,
                         "w80": np.quantile(sims, 0.9, 0) - np.quantile(sims, 0.1, 0), "pit": pit}

    add_bayes("PyMC one-season (talent fixed)", p25[:, pos])

    diag2, rho_post = None, None
    if not a.skip_two_season and not a.by_pitch_group:
        _, idata2, ids = fit_two_season(c, 2024, 2025, a.mu_sd, a.sigma_sd, a.draws, a.tune, a.chains, a.seed)
        diag2 = diagnostics(idata2, ["mu", "sigma", "rho", "z0", "e1"])
        rho, mu, sig = draws_of(idata2, "rho"), draws_of(idata2, "mu")[:, 1], draws_of(idata2, "sigma")[:, 1]
        z1 = draws_of(idata2, "z1")[:, np.searchsorted(ids, t["batter"].to_numpy())]
        z2 = rho[:, None] * z1 + np.sqrt(1 - rho[:, None] ** 2) * rng.standard_normal(z1.shape)
        add_bayes("PyMC two-season (learned rho)", 1 / (1 + np.exp(-(mu[:, None] + sig[:, None] * z2))))
        # Same information as the Atlas: the hitter's 2025 swings only (one-season posterior), stepped to 2026
        # with the rho learned above.  Separates "what the year-to-year step does" from "what 2024 data adds".
        z25 = draws_of(idata, "z")[:, pos]
        mu1, sig1 = draws_of(idata, "mu"), draws_of(idata, "sigma")
        r = rng.permutation(rho)[: len(mu1)]
        z26 = r[:, None] * z25 + np.sqrt(1 - r[:, None] ** 2) * rng.standard_normal(z25.shape)
        add_bayes("PyMC 2025 only + learned rho", 1 / (1 + np.exp(-(mu1[:, None] + sig1[:, None] * z26))))
        rho_post = {"mean": float(rho.mean()), "lo95": float(np.quantile(rho, 0.025)), "hi95": float(np.quantile(rho, 0.975)),
                    "sigma_2025_logit": float(sig.mean())}
        import arviz as az
        print(az.summary(idata2, var_names=["mu", "sigma", "rho"]))
        trace_plot(idata2, ["mu", "sigma", "rho"], OUT / f"trace_two_season{tag}.png")
    trace_plot(idata, ["mu", "sigma"] + (["beta", "sigma_g"] if a.by_pitch_group else []), OUT / f"trace_one_season{tag}.png")

    s = score(t, methods)
    s.to_csv(OUT / f"score_2026{tag}.csv", index=False)
    f = t.copy()
    for name, m in methods.items():
        key = name.split(" (")[0].lower().replace(" ", "_").replace("+", "plus")
        f[f"{key}_est"] = m["est"]
        for k in ("cov80", "cov95", "pit"):
            if k in m:
                f[f"{key}_{k}"] = m[k]
    f.to_csv(OUT / f"forecasts_2026{tag}.csv", index=False)
    import arviz as az
    summ = az.summary(idata, var_names=["mu", "sigma"] if not a.by_pitch_group else ["mu", "sigma"])
    res = {"league_2025": lg25, "league_2026": lg26, "hitters_2025": len(h25), "swings_2025": int(h25["swings"].sum()),
           "hitters_2026": len(h26), "swings_2026": int(h26["swings"].sum()), "targets_2026": len(t),
           "prior": {"mu_sd": a.mu_sd, "sigma_sd": a.sigma_sd}, "by_pitch_group": a.by_pitch_group,
           "one_season": {"mu": float(summ.loc["mu", "mean"]), "sigma_logit": float(summ.loc["sigma", "mean"]),
                          "diagnostics": diag},
           "two_season": {"rho": rho_post, "diagnostics": diag2},
           "implied_M_median_by_bucket": t25.groupby("bucket")["bayes_implied_M"].median().round(1).to_dict()}
    (OUT / f"summary{tag}.json").write_text(json.dumps(res, indent=2))
    pd.set_option("display.width", 160)
    print(json.dumps(res, indent=2))
    print(s.round(2).to_string(index=False))
    if not a.by_pitch_group and not a.tag:
        figure(t25, t, methods, lg25)


def trace_plot(idata, var_names, path: Path) -> None:
    """Trace plots (left: each chain's posterior density; right: the draws in order) for exercise 3."""
    import arviz as az
    import matplotlib

    matplotlib.use("Agg")
    pc = az.plot_trace_dist(idata, var_names=var_names, backend="matplotlib")
    pc.savefig(path, dpi=110)
    print("trace plot:", path)


def figure(t25: pd.DataFrame, t: pd.DataFrame, methods: dict, lg25: float) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 2, figsize=(11, 4.4))
    # left: shrinkage, both methods, against swings
    x = t25["swings"]
    ax[0].scatter(x, 100 * (t25["obs"] - lg25), s=6, c="#c8c8c8", label="raw 2025 rate", zorder=1)
    ax[0].scatter(x, 100 * (t25["atlas_est"] - lg25), s=6, c="#2b6cb0", label="Atlas closed form", zorder=2)
    ax[0].scatter(x, 100 * (t25["bayes_est"] - lg25), s=6, c="#dd6b20", label="PyMC posterior mean", zorder=3)
    ax[0].set_xscale("log")
    ax[0].set_ylim(-30, 45)
    ax[0].axhline(0, c="k", lw=0.6)
    ax[0].axvline(55.4, c="k", lw=0.6, ls=":")
    ax[0].text(58, 40, "M = 55 swings", fontsize=8)
    ax[0].set_xlabel("2025 swings (log scale)")
    ax[0].set_ylabel("whiff rate minus league (pts)")
    ax[0].set_title("Nearly the same shrinkage; PyMC a little less at small n", fontsize=10, loc="left")
    ax[0].legend(fontsize=8, frameon=False, loc="lower right")
    # right: PIT histograms of the 2026 forecasts
    bins = np.linspace(0, 1, 11)
    for name, col in (("PyMC one-season (talent fixed)", "#a0aec0"), ("Atlas closed form", "#2b6cb0"),
                      ("PyMC two-season (learned rho)", "#dd6b20")):
        if name in methods:
            ax[1].hist(methods[name]["pit"], bins=bins, histtype="step", lw=2, color=col, density=True, label=name)
    ax[1].axhline(1, c="k", lw=0.6, ls=":")
    ax[1].set_xlabel("where the 2026 rate fell in its forecast (PIT)")
    ax[1].set_ylabel("density (flat = calibrated)")
    ax[1].set_title("2026 out of sample: fixed talent misses at both tails", fontsize=10, loc="left")
    ax[1].legend(fontsize=8, frameon=False, loc="upper center")
    fig.tight_layout()
    fig.savefig(HERE / "whiff_hierarchical.png", dpi=150)
    print("figure:", HERE / "whiff_hierarchical.png")


def test_definitions_match_repo() -> None:
    import importlib

    arsenal = importlib.import_module("baseball.evaluation.arsenal")       # the package re-exports a function
    reliability = importlib.import_module("baseball.evaluation.reliability")  # named arsenal, so import the module

    assert set(SWINGS) == set(arsenal.SWINGS) and set(WHIFFS) == set(arsenal.WHIFFS)
    assert set(NO_PITCH) == set(reliability.NO_PITCH)
    row = reliability.load_params().loc["hitter/whiff"]
    assert abs(row["M"] - ATLAS["M"]) < 1e-6 and abs(row["tau"] - ATLAS["tau"]) < 1e-6
    assert abs(row["rho_use"] - ATLAS["rho"]) < 1e-6


if __name__ == "__main__":
    main()
