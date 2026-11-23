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
- Then the question proper: add each bat-tracking measure to the best batted-ball model and see whether the
  out-of-sample error falls.
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
    })
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


def run() -> dict:
    tables = {s: seasons_table(load(s)) for s in (2024, 2025, 2026)}
    train, test = pairs(tables, 2024), pairs(tables, 2025)
    out = dict(n_train=int(len(train)), n_test=int(len(test)),
               ball={k: score(train, test, v) for k, v in BALL_MODELS.items()},
               bat_alone={c: score(train, test, [c]) for c in BAT},
               year_to_year={c: float(np.corrcoef(test[c], test.merge(tables[2026], on="batter", suffixes=("", "_n"))[c + "_n"])[0, 1])
                             if False else None for c in []})
    best = min(out["ball"], key=lambda k: out["ball"][k]["rmse_out"])
    out["best_ball"] = best
    out["adds"] = {c: compare(train, test, BALL_MODELS[best], c) for c in BAT}
    both = pd.concat([train, test])
    out["stability"] = {}
    for c in BAT + ["iso", "barrel", "ev90"]:
        m = tables[2025][(tables[2025].pa >= MIN_PA) & (tables[2025].swings >= MIN_SWINGS)][["batter", c]].merge(
            tables[2026][(tables[2026].pa >= MIN_PA) & (tables[2026].swings >= MIN_SWINGS)][["batter", c]], on="batter").dropna()
        out["stability"][c] = dict(n=int(len(m)), r=float(np.corrcoef(m[c + "_x"], m[c + "_y"])[0, 1]))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "bat_power_summary.json").write_text(json.dumps(out, indent=1) + "\n")
    pd.concat(tables.values()).round(4).to_json(OUT / "bat_power_seasons.json", orient="records")
    return out
