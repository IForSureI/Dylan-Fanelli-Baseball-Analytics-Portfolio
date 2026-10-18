"""Pricing a reliever acquisition: projected value, the reliever market's price of it, surplus, the qualifying
offer and the luxury tax, for any club and any list of relievers.

Money in $ millions. Every input that is an assumption, not a rule or a sourced fact, is labeled ASSUMPTION
and is an argument.

Why relievers need their own price line. The roster engine prices wins with FanGraphs' 2026 free-agent study
($12.84M per win at 2+ WAR, $8.51M at 1-2, $6.74M under 1; `money.dollars_per_war`). That study excludes
relievers (FanGraphs' 2026 free-agent study excludes relievers as a separate market), and
relievers' value per inning depends on leverage the WAR scale only partly credits. So this module prices a
reliever two ways and shows both:
  1. engine: projected wins (leverage-adjusted for the role) x the engine's tiered $/WAR;
  2. market: what the 2025-26 reliever market paid per projected win, fit on that winter's signings with the
     same projection method (`market_line`).
Where the two disagree, the gap is the premium the market puts on relief work beyond what the win scale
credits. Neither is the club's own value of a win, which depends on where its win curve sits.

Projection (`project_relief_war`), labeled a derived projection, not a published one:
  - rate: relief run value per 100 pitches (Statcast delta_run_exp, pitcher's view), seasons weighted 5/4/3
    most recent first (Marcel-style weights; ASSUMPTION), effective sample = weighted pitches / 5, regressed
    toward the league's relief mean with the Reliability Atlas constant for pitcher run value (M = 1,932
    pitches). The Atlas found run value's year-to-year persistence too imprecise to estimate, so the
    regressed rate is used as next season's rate without a persistence discount: an explicit simplification.
  - replacement: the relief run value of fringe arms (pitcher-seasons with 50-399 relief pitches;
    `replacement_level`). ASSUMPTION: freely available relief is what those arms produce.
  - wins: (rate - replacement) x pitches / 100 / runs per win (10; ASSUMPTION, the usual rule of thumb).
  - role: x (1 + LI) / 2 for a reliever used at leverage LI (the chaining convention FanGraphs uses for
    relievers). LI is an ASSUMPTION for the role, checked against the pitcher's own leverage proxy.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from baseball.roster.money import DISCOUNT, DPW_GROWTH, dollars_per_war, qualifying_offer, tax_cost_of_signing

RUNS_PER_WIN = 10.0          # ASSUMPTION (rule of thumb; FanGraphs' runs-per-win sits near 10 in this era)
WEIGHTS = (5, 4, 3)          # ASSUMPTION: most recent season first
RV100_M = 1932.2             # Reliability Atlas, pitcher run value per 100 pitches (reliability_params.json)
ROLE_LI = 1.6                # ASSUMPTION: a late-inning high-leverage role (the B1/B2 job in front of a closer)
ROLE_LIS = {"B1": 1.6, "B2": 1.4, "depth": 1.1}   # ASSUMPTION by role; checked against each pitcher's leverage proxy
RELIEVER_DECLINE = 0.10      # ASSUMPTION: relief value falls 10% a year from age 31 (FanGraphs' -0.4 WAR a year
DECLINE_FROM = 31            # is ~13% of a 3-WAR player; relievers are scaled proportionally, a little softer)

# ------------------------------------------------------------------ facts: the 2025-26 reliever market
# Terms: NBC Sports / Yahoo Sports free-agent tracker (D.J. Short, Feb. 12, 2026), quoted per signing.
# Ids: Chadwick register (data/people). One row per signing; options and opt-outs not priced.
COMPS_2025_26 = [
    # name, mlbam id, years, total $M, new club
    ("Edwin Díaz", 621242, 3, 69.0, "Dodgers"),
    ("Devin Williams", 642207, 3, 51.0, "Mets"),
    ("Robert Suarez", 663158, 3, 45.0, "Braves"),
    ("Tyler Rogers", 643511, 3, 37.0, "Blue Jays"),
    ("Ryan Helsley", 664854, 2, 28.0, "Orioles"),
    ("Brad Keller", 641745, 2, 22.0, "Phillies"),
    ("Luke Weaver", 596133, 2, 22.0, "Mets"),
    ("Seranthony Domínguez", 622554, 2, 20.0, "White Sox"),
    ("Emilio Pagán", 641941, 2, 20.0, "Reds"),
    ("Kyle Finnegan", 640448, 2, 19.0, "Tigers"),
    ("Phil Maton", 664208, 2, 14.5, "Cubs"),
    ("Raisel Iglesias", 628452, 1, 16.0, "Braves"),
    ("Pete Fairbanks", 664126, 1, 13.0, "Marlins"),
    ("Kenley Jansen", 445276, 1, 11.0, "Tigers"),
    ("Gregory Soto", 642397, 1, 7.75, "Pirates"),
    ("Pierce Johnson", 572955, 1, 6.5, "Reds"),
    ("Hunter Harvey", 640451, 1, 6.0, "Nationals"),
    ("Shawn Armstrong", 542888, 1, 5.5, "Guardians"),
    ("Kirby Yates", 489446, 1, 5.0, "Angels"),
    ("Tyler Kinley", 641755, 1, 4.25, "Braves"),
    ("Drew Pomeranz", 519141, 1, 4.0, "Angels"),
]
COMPS_SOURCE = "NBC Sports / Yahoo Sports MLB free agent tracker 2025-26 (D.J. Short), Feb. 12, 2026"

# Draft-pick value: Craig Edwards, "An Update on How to Value Draft Picks," FanGraphs, Apr. 5, 2019 ("present
# value of pick" = expected WAR value minus slot, 2019 dollars). Picks 45-60; a club's second pick lost to a
# qualified signing is "$4M to $10M, depending on draft position."
PICK_VALUE_2019 = {45: 6.7, 46: 6.6, 47: 6.4, 48: 6.3, 49: 6.1, 50: 5.9, 51: 5.8, 52: 5.7, 53: 5.5, 54: 5.4, 55: 5.3,
                   56: 5.2, 57: 5.0, 58: 4.9, 59: 4.8, 60: 4.7}

# Draft-pick value, my own: what picks 45-60 returned in the 2000-2016 drafts (first six MLB seasons priced at
# $11.23M per win, less salaries, discounted 7% to draft day, 2026 dollars; recent drafts weighted more), less the
# pick's 2026 slot value. Source: the Dylan-Fanelli-Draft-Analytics repo, backtest/results/pick_table_2000_2016.csv
# (column market_all), and MLB's 2026 slot values. About twice Edwards' 2019 figures: the 2000-2016 drafts returned
# more in rounds 2-4 than the curves behind those figures assumed. This is the house value.
PICK_VALUE_OWN = {45: 11.06, 46: 10.92, 47: 10.80, 48: 10.69, 49: 10.58, 50: 10.49, 51: 10.40, 52: 10.31, 53: 10.23,
                  54: 10.16, 55: 10.09, 56: 10.02, 57: 9.95, 58: 9.89, 59: 9.82, 60: 9.76}


# ------------------------------------------------------------------ relief seasons and replacement

def relief_seasons(flagged: pd.DataFrame) -> pd.DataFrame:
    """Relief pitches and run value per pitcher-season (flagged pitches from evaluation.reliever.flag).
    Grain: pitcher x season."""
    r = flagged[flagged["relief"] & flagged["rv"].notna()]
    out = r.groupby(["pitcher", "season"]).agg(pitches=("rv", "size"), rv=("rv", "sum"), games=("game_pk", "nunique"))
    out["rv100"] = 100 * out["rv"] / out["pitches"]
    return out.reset_index()


def replacement_level(rs: pd.DataFrame, lo: int = 50, hi: int = 400) -> float:
    """Relief run value per 100 pitches of fringe arms: pitcher-seasons with lo to hi-1 relief pitches,
    pitch-weighted. ASSUMPTION: that is what freely available relief produces."""
    f = rs[(rs["pitches"] >= lo) & (rs["pitches"] < hi)]
    return float(100 * f["rv"].sum() / f["pitches"].sum())


def league_relief_mean(rs: pd.DataFrame, seasons) -> float:
    s = rs[rs["season"].isin(list(seasons))]
    return float(100 * s["rv"].sum() / s["pitches"].sum())


@dataclass
class Projection:
    pitcher: int
    seasons: tuple
    observed_rv100: float      # weighted
    effective_pitches: float
    rv100: float               # regressed
    rv100_lo: float
    rv100_hi: float
    weight: float
    pitches: float             # projected relief pitches
    replacement: float
    war_neutral: float
    war_role: float
    war_lo: float
    war_hi: float


def project_relief_war(rs: pd.DataFrame, pitcher: int, last_season: int, league_mean: float, replacement: float,
                       pitches: float | None = None, n_seasons: int = 3, li: float = ROLE_LI,
                       weights=WEIGHTS, M: float = RV100_M, tau: float = 0.507256,
                       runs_per_win: float = RUNS_PER_WIN) -> Projection:
    """Next-season relief wins from the last n_seasons of relief run value (see module docstring).

    pitches: projected relief pitches next season; default = the weighted mean of his seasons' relief pitches.
    tau: the Atlas's talent SD for pitcher run value per 100 (for the interval; the interval covers his rate,
    not his playing time). Returns neutral wins (no leverage) and role wins (x (1 + li) / 2)."""
    seasons = tuple(range(last_season, last_season - n_seasons, -1))
    me = rs[rs["pitcher"].eq(pitcher)].set_index("season")
    w = dict(zip(seasons, weights[:n_seasons]))
    have = [s for s in seasons if s in me.index]
    if not have:
        raise ValueError(f"no relief seasons for {pitcher} in {seasons}")
    wrv = sum(w[s] * me.loc[s, "rv"] for s in have)
    wn = sum(w[s] * me.loc[s, "pitches"] for s in have)
    obs = 100 * wrv / wn
    n_eff = wn / weights[0]
    wt = n_eff / (n_eff + M)
    est = league_mean + wt * (obs - league_mean)
    sd = tau * np.sqrt(1 - wt)
    if pitches is None:
        pitches = sum(w[s] * me.loc[s, "pitches"] for s in have) / sum(w[s] for s in have)
    lev = (1 + li) / 2

    def wins(rate):
        return (rate - replacement) * pitches / 100 / runs_per_win

    return Projection(pitcher, seasons, obs, n_eff, est, est - 1.96 * sd, est + 1.96 * sd, wt, pitches, replacement,
                      wins(est), wins(est) * lev, wins(est - 1.96 * sd) * lev, wins(est + 1.96 * sd) * lev)


# ------------------------------------------------------------------ the market line

def comps_table(rs: pd.DataFrame, signing_season: int, league_mean: float, replacement: float,
                comps=COMPS_2025_26, n_seasons: int = 2) -> pd.DataFrame:
    """Each comparable signing with its projected neutral wins at signing (the same method, data through the
    season before the contract) and AAV. Grain: one signing."""
    rows = []
    for name, pid, years, total, club in comps:
        try:
            pr = project_relief_war(rs, pid, signing_season - 1, league_mean, replacement, n_seasons=n_seasons, li=1.0)
        except ValueError:
            continue
        rows.append({"name": name, "pitcher": pid, "club": club, "years": years, "total": total, "aav": total / years,
                     "rv100_reg": pr.rv100, "pitches": pr.pitches, "war_neutral": pr.war_neutral})
    return pd.DataFrame(rows)


def market_line(comps: pd.DataFrame) -> dict:
    """AAV = a + b x projected neutral wins, least squares over the comparable signings, with the residual SD,
    the coefficient covariance (for prediction intervals), the range of projections it was fit on, and the
    median AAV per projected win. A descriptive fit of one winter's prices, not a causal model."""
    x, y = comps["war_neutral"].to_numpy(float), comps["aav"].to_numpy(float)
    A = np.column_stack([np.ones_like(x), x])
    (a, b), *_ = np.linalg.lstsq(A, y, rcond=None)
    resid = y - (a + b * x)
    r2 = 1 - resid.var() / y.var()
    pos = x > 0.2
    s2 = float(np.sum(resid ** 2) / max(len(x) - 2, 1))
    cov = s2 * np.linalg.inv(A.T @ A)
    return {"intercept": float(a), "slope": float(b), "resid_sd": float(np.sqrt(s2)), "slope_se": float(np.sqrt(cov[1, 1])),
            "cov": cov.tolist(), "r2": float(r2), "n": int(len(x)), "x_min": float(x.min()), "x_max": float(x.max()),
            "x_mean": float(x.mean()), "median_aav_per_war": float(np.median(y[pos] / x[pos]))}


def market_price_interval(war_neutral: float, line: dict, level: float = 0.95) -> dict:
    """The line's expected AAV at a projection, the SE of that fitted mean, and a prediction interval for one
    signing's AAV (residual variance + the fitted mean's variance, t with n - 2 df). Flags extrapolation beyond
    the projections the line was fit on."""
    from scipy.stats import t as tdist

    c = np.asarray(line["cov"])
    v = np.array([1.0, war_neutral])
    se_fit = float(np.sqrt(v @ c @ v))
    sd_pred = float(np.sqrt(line["resid_sd"] ** 2 + se_fit ** 2))
    q = float(tdist.ppf(0.5 + level / 2, line["n"] - 2))
    mid = market_aav(war_neutral, line)
    return {"aav": mid, "se_fit": se_fit, "sd_pred": sd_pred, "lo": mid - q * sd_pred, "hi": mid + q * sd_pred,
            "extrapolated": not (line["x_min"] <= war_neutral <= line["x_max"])}


def chance_price_at_or_below(walk_away: float, war_neutral: float, line: dict) -> float:
    """If one signing's AAV is distributed as the line's prediction (t, n - 2 df), the chance his price comes in
    at or below `walk_away`: a rough guide to how often a walk-away lands the player, not a market model."""
    from scipy.stats import t as tdist

    pi = market_price_interval(war_neutral, line)
    return float(tdist.cdf((walk_away - pi["aav"]) / pi["sd_pred"], line["n"] - 2))


def market_aav(war_neutral: float, line: dict) -> float:
    return line["intercept"] + line["slope"] * war_neutral


# ------------------------------------------------------------------ contract value

def war_path(war1: float, first_age: int, years: int, decline: float = RELIEVER_DECLINE, decline_from: int = DECLINE_FROM) -> list[float]:
    """Relief wins by contract year. war1 is his projected level from recent seasons; every season played at age
    decline_from or older (the first contract season included) takes `decline` off the previous level. ASSUMPTION.
    Example: war1 = 1.0 from age 33 -> 0.9, 0.81, ...; from age 28 -> 1.0, 1.0, 1.0, 0.9 (age 31), 0.81."""
    out, level = [], war1
    for t in range(years):
        if first_age + t >= decline_from:
            level *= 1 - decline
        out.append(level)
    return out


def contract_value(aav: float, years: int, war1_role: float, war1_neutral: float, first_age: int, first_season: int,
                   line: dict, discount: float = DISCOUNT, growth: float = DPW_GROWTH,
                   availability: list[float] | None = None) -> dict:
    """PV of a contract's salary, of the wins it buys at the engine's tiered $/WAR (role wins) and at the
    reliever market line (neutral wins, the basis the line was fit on), and the two surpluses. Salaries level,
    paid from t = 0; the market line grows like the engine's price of a win (3%/yr, ASSUMPTION).
    availability: share of a full season he pitches each contract year (default 1.0 every year), e.g. [0.35, 1.0]
    for a pitcher returning from surgery at mid-season (ASSUMPTION, stated where used).
    The engine column is NOT on the same win scale as FanGraphs' $/WAR (this module's replacement level isn't
    calibrated to fWAR), so read it as an order of magnitude, not a price."""
    avail = list(availability) if availability is not None else [1.0] * years
    role = [w * a for w, a in zip(war_path(war1_role, first_age, years), avail)]
    neut = [w * a for w, a in zip(war_path(war1_neutral, first_age, years), avail)]
    f = [(1 + discount) ** t for t in range(years)]
    pv_salary = sum(aav / x for x in f)
    pv_engine = sum(w * dollars_per_war(w, first_season + t) / x for t, (w, x) in enumerate(zip(role, f)))
    # a partial season is worth the line's price of his full-season projection times the share he pitches
    pv_market = sum(max(market_aav(w / a if a else 0.0, line), 0.0) * a * (1 + growth) ** t / x
                    for t, (w, a, x) in enumerate(zip(neut, avail, f)))
    return {"years": years, "aav": aav, "total": aav * years, "pv_salary": pv_salary, "war_role_path": role,
            "pv_value_engine": pv_engine, "surplus_engine": pv_engine - pv_salary,
            "pv_value_market": pv_market, "surplus_market": pv_market - pv_salary}


def breakeven_aav(years: int, war1_role: float, war1_neutral: float, first_age: int, first_season: int, line: dict,
                  basis: str = "market", discount: float = DISCOUNT, availability: list[float] | None = None) -> float:
    """Level AAV at which the contract's PV surplus is zero on the chosen basis ('market' or 'engine')."""
    v = contract_value(0.0, years, war1_role, war1_neutral, first_age, first_season, line, discount,
                       availability=availability)
    pv_value = v["pv_value_market"] if basis == "market" else v["pv_value_engine"]
    annuity = sum(1 / (1 + discount) ** t for t in range(years))
    return pv_value / annuity


# ------------------------------------------------------------------ the qualifying offer and the tax

def qo_cost(signing_status: str, losing_status: str, contract_total: float, pick_number: int | None,
            pick_values: dict = PICK_VALUE_OWN) -> dict:
    """What signing a qualified free agent costs the signing club: the picks and pool money it forfeits
    (`money.qualifying_offer`), and the value of the first forfeited pick when its number is known (house values by
    default; pass PICK_VALUE_2019 for Edwards' 2019 figures). Rules of the 2022-26 agreement; both sides proposed
    ending the QO in the 2026 talks."""
    q = qualifying_offer(losing_status, signing_status, contract_total)
    pick_value = pick_values.get(pick_number) if pick_number else None
    return q | {"pick_number": pick_number, "pick_value": pick_value,
                "total_value": (pick_value or 0.0) + q["signing_club_forfeits_pool"] if pick_value else None}


def tax_table(payrolls, aav: float, threshold: float, consecutive_years: int = 1) -> pd.DataFrame:
    """The tax an AAV adds at each pre-signing CBT payroll (`money.tax_cost_of_signing`). For 2027 there is no
    threshold until a new agreement, so it is an argument."""
    rows = []
    for p in payrolls:
        t = tax_cost_of_signing(p, aav, consecutive_years, threshold=threshold)
        rows.append({"payroll_before": p, "aav": aav, "threshold": threshold, "added_tax": t["added_tax"],
                     "all_in_cost": t["all_in_cost"]})
    return pd.DataFrame(rows)
