"""Does bat tracking predict next season's power better than what the ball already told us?

Bat speed and swing length (Statcast, 2024 on) are measured on every swing, hit or miss. Exit velocity and barrels
are measured only when the ball is put in play. The question for a front office pricing a hitter: once you know a
hitter's ISO, barrel rate and hardest-hit exit velocities, does his bat speed tell you anything more about next
season's power?

Design (regular seasons; hitters with 300+ PA and 150+ competitive swings in season t, and 300+ PA in t+1):
- Predictors from season t: ISO; barrel rate per batted ball; average exit velocity and its 90th percentile; bat
  speed, swing length, attack angle, squared-up rate and blast rate on competitive swings (Statcast's definition:
  the fastest 90% of a hitter's swings plus any 60+ mph swing that produced 90+ mph).
- Outcome: ISO in season t+1.
- Fit on 2024 -> 2025 pairs; score on 2025 -> 2026 pairs, which the fit never saw (out-of-sample R^2 and RMSE).
- The batted-ball model is chosen by 5-fold cross-validation on the 2024 -> 2025 pairs alone, so the 2025 -> 2026
  pairs stay untouched until scoring.
- Then the question proper: add each bat-tracking measure to that model and see whether the out-of-sample error
  falls.
- Also: whether a change in bat speed warns of lost power (bat_speed_change), and a named hitter's projection under
  three fits (projection), so a report can show how much the number depends on the fit.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SEQ = ROOT / "data" / "seq"
OUT = ROOT / "reports" / "outputs"
COLS = ["game_type", "game_date", "batter", "description", "events", "woba_denom", "launch_speed", "launch_angle",
        "launch_speed_angle", "bat_speed", "swing_length", "attack_angle", "release_speed", "estimated_woba_using_speedangle"]
SWINGS = {"swinging_strike", "swinging_strike_blocked", "foul", "foul_tip", "hit_into_play", "foul_bunt",
          "missed_bunt", "bunt_foul_tip"}
NOT_AB = {"walk", "intent_walk", "hit_by_pitch", "sac_fly", "sac_bunt", "catcher_interf", "sac_fly_double_play",
          "sac_bunt_double_play", "truncated_pa"}
TB = {"single": 1, "double": 2, "triple": 3, "home_run": 4}
MIN_PA, MIN_SWINGS = 300, 150
BALL_MODELS = {
    "ISO": ["iso"],
    "ISO + barrel rate": ["iso", "barrel"],
    "ISO + 90th-pct EV": ["iso", "ev90"],
    "ISO + barrel rate + 90th-pct EV": ["iso", "barrel", "ev90"],
}
BAT = ["bat_speed", "swing_length", "attack_angle", "squared_up", "blast"]


def load(season: int) -> pd.DataFrame:
    d = pd.concat([pd.read_parquet(p, columns=COLS) for p in sorted(SEQ.glob(f"seq_{season}_*.parquet"))], ignore_index=True)
    d = d[d.game_type == "R"].copy()
    d["season"] = season
    return d


def seasons_table(d: pd.DataFrame) -> pd.DataFrame:
    pa = d[d.events.notna() & (d.events != "")]
    ab = pa[~pa.events.isin(NOT_AB)]
    g = pd.DataFrame({
        "pa": pa.groupby("batter").size(),
        "ab": ab.groupby("batter").size(),
        "hits_tb": ab.events.map(TB).fillna(0).groupby(ab.batter).sum(),
        "hits": ab.events.isin(TB).groupby(ab.batter).sum(),
        "hr": (pa.events == "home_run").groupby(pa.batter).sum(),
        "so": pa.events.isin({"strikeout", "strikeout_double_play"}).groupby(pa.batter).sum(),
    })
    g["k_rate"] = g.so / g.pa
    g["xb"] = g.hits_tb - g.hits
    g["xb_per_contact_ab"] = g.xb / (g.ab - g.so)          # extra bases per at-bat that didn't end in a strikeout
    g["iso"] = (g.hits_tb - g.hits) / g.ab
    bip = d[d.description.eq("hit_into_play") & d.launch_speed.notna()]
    g["barrel"] = (bip.launch_speed_angle == 6).groupby(bip.batter).mean()
    g["ev"] = bip.groupby("batter").launch_speed.mean()
    g["ev90"] = bip.groupby("batter").launch_speed.quantile(0.9)
    g["xwobacon"] = bip.groupby("batter").estimated_woba_using_speedangle.mean()
    sw = d[d.description.isin(SWINGS) & d.bat_speed.notna()].copy()
    q10 = sw.groupby("batter").bat_speed.transform(lambda x: x.quantile(0.10))
    comp = sw[(sw.bat_speed >= q10) | ((sw.bat_speed >= 60) & (sw.launch_speed >= 90))].copy()
    mx = 1.23 * comp.bat_speed + 0.23 * 0.92 * comp.release_speed
    share = comp.launch_speed / mx
    comp["sq"] = (share >= 0.8).astype(float).where(comp.launch_speed.notna())
    comp["blast"] = ((share * 100 + comp.bat_speed) >= 164).astype(float).where(comp.launch_speed.notna())
    b = comp.groupby("batter").agg(swings=("bat_speed", "size"), bat_speed=("bat_speed", "mean"),
                                   swing_length=("swing_length", "mean"), attack_angle=("attack_angle", "mean"),
                                   squared_up=("sq", "mean"), blast=("blast", "mean"))
    g = g.join(b)
    g["season"] = int(d.season.iloc[0])
    return g.reset_index()


def pairs(tables: dict[int, pd.DataFrame], a: int) -> pd.DataFrame:
    x = tables[a][(tables[a].pa >= MIN_PA) & (tables[a].swings >= MIN_SWINGS)]
    y = tables[a + 1][tables[a + 1].pa >= MIN_PA][["batter", "iso", "pa"]].rename(columns={"iso": "iso_next", "pa": "pa_next"})
    return x.merge(y, on="batter").dropna(subset=["iso", "barrel", "ev90"] + BAT)


def _fit(train: pd.DataFrame, cols: list[str]):
    X = np.column_stack([np.ones(len(train))] + [train[c] for c in cols])
    coef, *_ = np.linalg.lstsq(X, train.iso_next, rcond=None)
    return coef


def _pred(df: pd.DataFrame, cols: list[str], coef) -> np.ndarray:
    return np.column_stack([np.ones(len(df))] + [df[c] for c in cols]) @ coef


def score(train: pd.DataFrame, test: pd.DataFrame, cols: list[str], boot: int = 2000, seed: int = 11) -> dict:
    coef = _fit(train, cols)
    p = _pred(test, cols, coef)
    y = test.iso_next.to_numpy()
    sse = ((p - y) ** 2).sum()
    r2 = 1 - sse / ((y - y.mean()) ** 2).sum()
    return dict(cols=cols, r2_out=float(r2), rmse_out=float(np.sqrt(sse / len(y))), coef=[float(c) for c in coef])


def compare(train: pd.DataFrame, test: pd.DataFrame, base: list[str], add: str, boot: int = 2000, seed: int = 11) -> dict:
    """Out-of-sample RMSE with and without `add`, and a bootstrap (over test hitters) of the difference."""
    pb = _pred(test, base, _fit(train, base))
    pa = _pred(test, base + [add], _fit(train, base + [add]))
    y = test.iso_next.to_numpy()
    e0, e1 = (pb - y) ** 2, (pa - y) ** 2
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(y), (boot, len(y)))
    diff = np.sqrt(e0[idx].mean(1)) - np.sqrt(e1[idx].mean(1))
    return dict(add=add, rmse_base=float(np.sqrt(e0.mean())), rmse_with=float(np.sqrt(e1.mean())),
                gain=float(np.sqrt(e0.mean()) - np.sqrt(e1.mean())), gain_lo=float(np.percentile(diff, 2.5)),
                gain_hi=float(np.percentile(diff, 97.5)))


def cv_rmse(df: pd.DataFrame, cols: list[str], k: int = 5, seed: int = 3) -> float:
    fold = np.random.default_rng(seed).integers(0, k, len(df))
    err = []
    for f in range(k):
        tr, te = df[fold != f], df[fold == f]
        err.append((_pred(te, cols, _fit(tr, cols)) - te.iso_next.to_numpy()) ** 2)
    return float(np.sqrt(np.concatenate(err).mean()))


def bat_speed_change(tables: dict[int, pd.DataFrame], boot: int = 4000, seed: int = 3) -> dict:
    """Does a change in bat speed from 2024 to 2025 predict 2026 ISO beyond 2025's ISO and 90th-pct EV?
    Hitters qualifying (300+ PA, 150+ competitive swings) in 2024 and 2025 and with 300+ PA in 2026."""
    q = lambda s: tables[s][(tables[s].pa >= MIN_PA) & (tables[s].swings >= MIN_SWINGS)].set_index("batter")
    a, b = q(2024), q(2025)
    c = tables[2026][tables[2026].pa >= MIN_PA].set_index("batter")
    ids = a.index.intersection(b.index).intersection(c.index)
    d = pd.DataFrame({"iso": b.loc[ids, "iso"], "ev90": b.loc[ids, "ev90"],
                      "dbs": b.loc[ids, "bat_speed"] - a.loc[ids, "bat_speed"], "y": c.loc[ids, "iso"]}).dropna()
    X = np.column_stack([np.ones(len(d)), d.iso, d.ev90, d.dbs])
    coef = np.linalg.lstsq(X, d.y, rcond=None)[0]
    rng = np.random.default_rng(seed)
    bs = [np.linalg.lstsq(X[i], d.y.to_numpy()[i], rcond=None)[0][3] for i in (rng.integers(0, len(d), len(d)) for _ in range(boot))]
    return dict(n=int(len(d)), per_mph=float(coef[3]), lo=float(np.percentile(bs, 2.5)), hi=float(np.percentile(bs, 97.5)))


def projection(tables: dict[int, pd.DataFrame], batter: int, cols=("iso", "ev90")) -> dict:
    """Next-season ISO for one hitter from his 2026 line, three ways: the fit scored out of sample (2024->25
    pairs only), a refit on both year pairs, and a fit on 2025->26 alone; with the residual spread of the
    two-pair refit and the chance of matching his 2026 ISO."""
    from statistics import NormalDist
    cols = list(cols)
    x = tables[2026][tables[2026].batter == batter]
    if x.empty:
        return {}
    p24, p25 = pairs(tables, 2024), pairs(tables, 2025)
    both = pd.concat([p24, p25])
    fits = {"train_2024_25": _fit(p24, cols), "both_pairs": _fit(both, cols), "pair_2025_26": _fit(p25, cols)}
    out = {k: float(_pred(x, cols, c)[0]) for k, c in fits.items()}
    sd = float((both.iso_next - _pred(both, cols, fits["both_pairs"])).std())
    iso26 = float(x.iso.iloc[0])
    out.update(resid_sd=sd, iso_2026=iso26,
               p_match={k: float(1 - NormalDist(v, sd).cdf(iso26)) for k, v in list(out.items())[:3]})
    return out


def run(project: tuple[int, ...] = (668227, 673548)) -> dict:
    tables = {s: seasons_table(load(s)) for s in (2024, 2025, 2026)}
    train, test = pairs(tables, 2024), pairs(tables, 2025)
    out = dict(n_train=int(len(train)), n_test=int(len(test)),
               ball={k: score(train, test, v) for k, v in BALL_MODELS.items()},
               bat_alone={c: score(train, test, [c]) for c in BAT})
    # the batted-ball model is chosen on the training pairs alone (5-fold cross-validation), never on the test pairs
    out["cv_train"] = {k: cv_rmse(train, v) for k, v in BALL_MODELS.items()}
    best = min(out["cv_train"], key=out["cv_train"].get)
    out["best_ball"] = best
    out["adds"] = {c: compare(train, test, BALL_MODELS[best], c) for c in BAT}
    out["bat_speed_change"] = bat_speed_change(tables)
    out["projections"] = {str(b): projection(tables, b, tuple(BALL_MODELS[best])) for b in project}
    out["stability"] = {}
    for c in BAT + ["iso", "barrel", "ev90"]:
        m = tables[2025][(tables[2025].pa >= MIN_PA) & (tables[2025].swings >= MIN_SWINGS)][["batter", c]].merge(
            tables[2026][(tables[2026].pa >= MIN_PA) & (tables[2026].swings >= MIN_SWINGS)][["batter", c]], on="batter").dropna()
        out["stability"][c] = dict(n=int(len(m)), r=float(np.corrcoef(m[c + "_x"], m[c + "_y"])[0, 1]))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "bat_power_summary.json").write_text(json.dumps(out, indent=1) + "\n")
    pd.concat(tables.values()).round(4).to_json(OUT / "bat_power_seasons.json", orient="records")
    return out


def add_projections(batters: tuple[int, ...]) -> dict:
    """Add hitters to the saved summary's projections without refitting anything else: the same three fits, run on
    the saved season tables (reports/outputs/bat_power_seasons.json, the tables run() wrote). On those tables the
    stored Arozarena and Suzuki projections come back to three places, so a hitter added later is projected the
    same way as the first two. Used for Chisholm (665862) and Lowe (664040), Nov. 23, 2026."""
    s = pd.read_json(OUT / "bat_power_seasons.json")
    tables = {int(y): g.drop(columns="season").reset_index(drop=True) for y, g in s.groupby("season")}
    path = OUT / "bat_power_summary.json"
    out = json.loads(path.read_text())
    for b in batters:
        out["projections"][str(b)] = projection(tables, b, tuple(BALL_MODELS[out["best_ball"]]))
    path.write_text(json.dumps(out, indent=1) + "\n")
    return out
