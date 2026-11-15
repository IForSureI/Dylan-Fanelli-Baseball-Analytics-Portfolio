"""The engine applied to public cases: the 2025 tax bills and the Paul Skenes extension decision.

`uv run python -m baseball.roster.cases` prints every number the report quotes and saves the two Nov. 15
checks (sourced injury rates, a club's own value of a win) to `reports/outputs/skenes-checks-2026.json`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from baseball.roster import facts
from baseball.roster.money import (DISCOUNT, DPW_TIERS_HISTORY, arb_path, cbt_bill, dollars_per_war, extension_band,
                                   implied_dpw, implied_war1, project_war, pv, qualifying_offer)
from baseball.roster.service import SUPER_TWO_2027_ESTIMATE, Service, rookie_of_year_credit, timeline


# ------------------------------------------------------------------ (a) the 2025 tax bills
def cbt_2025_check() -> pd.DataFrame:
    """Computed vs actual 2025 CBT bills. Grain: one club."""
    rows = []
    for club, payroll, years, actual in facts.CBT_2025:
        b = cbt_bill(payroll, years, season=2025)
        rows.append({"club": club, "cbt_payroll": payroll, "consecutive_years": years, "over": b.over,
                     "actual": actual, "computed": b.total, "difference": b.total - actual,
                     "marginal_rate": b.marginal_rate, "pick_drop": b.pick_drop})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ (c) Paul Skenes
FIRST_ARB = 2027
FA_YEARS_BOUGHT = 5            # 2030-34: an 8-year extension through his age-32 season
WEIGHTS = (5, 4, 3)            # ASSUMPTION: Marcel-style weights on the last three seasons, most recent first
SCENARIOS = {"low": 0.8, "base": 1.0, "high": 1.2, "stress": 0.6}   # stress: ILLUSTRATIVE major-arm-injury case
CAP_GROWTH = 0.03              # ASSUMPTION for the MLB-proposal case: the cap grows like the cost of a win
STRESS_PROBS = (0.0, 0.2, 0.35)  # ASSUMPTION: chances of the stress path. Scenarios; skenes_injury_check()
                                 # sets them beside the published surgery shares
CAP_PROBS = (0.0, 0.25, 0.5, 1.0)  # chance MLB's cap-and-max system is adopted as proposed (not estimated)


def skenes_service() -> dict:
    s = Service.parse("0.000")
    credited_2024 = rookie_of_year_credit(facts.SKENES["days_2024_on_field"], facts.SKENES["roy_2024_finish"])
    s = s.plus_season(credited_2024).plus_season(172).plus_season(172)   # 2024 (credited), 2025, 2026
    t = timeline(s, 2026, future_days=172)
    without = Service(0).plus_season(facts.SKENES["days_2024_on_field"]).plus_season(172).plus_season(172)
    t0 = timeline(without, 2026, future_days=172, super_two_cutoff=SUPER_TWO_2027_ESTIMATE)
    stoppage = timeline(s, 2026, future_days=[150, 172, 172, 172])
    return {"service_after_2026": str(s), "matches_mlbtr": str(s) == facts.SKENES["service_after_2026"],
            "arb_seasons": t.arb_seasons, "free_agent_after": t.free_agent_after,
            "control_seasons": t.control_seasons,
            "without_roy_credit": {"service_after_2026": str(without), "super_two_2027": t0.super_two,
                                   "arb_seasons": t0.arb_seasons, "free_agent_after": t0.free_agent_after},
            "stoppage_uncredited": {"path": stoppage.path, "free_agent_after": stoppage.free_agent_after}}


def skenes_war_base() -> float:
    """Weighted fWAR, 2026/2025/2024 at 5/4/3. No public 2027 projection existed on 2026-10-12."""
    w = facts.SKENES["fwar"]
    return sum(k * w[y] for k, y in zip(WEIGHTS, (2026, 2025, 2024))) / sum(WEIGHTS)


def skenes_paths(war1: float, base_season: int = 2026) -> dict:
    """Arbitration salaries and free-agent values, 2027-34, for a 2027 WAR of war1 (aged from 25)."""
    years = 3 + FA_YEARS_BOUGHT
    war = project_war(war1, first_age=25, years=years)                 # ages 25-32 in 2027-34
    platform = [facts.SKENES["fwar"][2026], war[0], war[1]]             # 2026 actual, then projected
    arb_fg = arb_path(platform, FIRST_ARB)                               # FanGraphs shares alone
    arb_mlbtr_rows = arb_path(platform, FIRST_ARB, first_salary=facts.SKENES["mlbtr_2027_arb"], calibrate=True)
    seasons = list(range(FIRST_ARB, FIRST_ARB + years))
    value = [w * dollars_per_war(w, s, base_season=base_season) for w, s in zip(war, seasons)]
    return {"seasons": seasons, "war": war, "value": value,
            "arb_fangraphs": [r["salary"] for r in arb_fg],
            "arb_mlbtr": [r["salary"] for r in arb_mlbtr_rows],
            "fa_value": value[3:]}


def mlb_proposal_max(seasons: list[int], share: float | None = None) -> list[float]:
    """Most a club could pay in each free-agent season under MLB's June 25, 2026 proposal: `share` of the
    cap in the first year (15% new club, 16% own-club "Cornerstone"; cap grown from 2027 at CAP_GROWTH),
    then +5% a year."""
    p = facts.MLB_PROPOSAL
    share = p["new_club_share"] if share is None else share
    first = share * p["cap_2027"] * (1 + CAP_GROWTH) ** (seasons[0] - 2027)
    return [first * (1 + p["raise"]) ** k for k in range(len(seasons))]


def _mix(a: list[float], b: list[float], w_b: float) -> list[float]:
    return [(1 - w_b) * x + w_b * y for x, y in zip(a, b)]


def _capped(values: list[float], cap: list[float] | None) -> list[float]:
    return list(values) if cap is None else [min(v, c) for v, c in zip(values, cap)]


def club_ceiling(paths: dict, stress_prob: float, cap: list[float] | None) -> float:
    """Durability-adjusted club ceiling: the probability-weighted cost of the club's alternative (base path
    with 1 - stress_prob, stress path with stress_prob). In the alternative the club pays arbitration and
    then the going price of the free-agent seasons, min(value, cap) under MLB's plan; after an injury it
    owes less, which is the risk an extension moves onto the club."""
    b, st = paths["base"], paths["stress"]
    arb = _mix(b["arb_mlbtr"], st["arb_mlbtr"], stress_prob)
    fa = _mix(_capped(b["fa_value"], cap), _capped(st["fa_value"], cap), stress_prob)
    return pv(arb) + pv([0.0] * len(arb) + fa)


def skenes_extension() -> dict:
    base_war = skenes_war_base()
    paths = {k: skenes_paths(base_war * m) for k, m in SCENARIOS.items()}
    fa_seasons = paths["base"]["seasons"][3:]
    own_max = mlb_proposal_max(fa_seasons, facts.MLB_PROPOSAL["own_club_share"])     # 16%, Cornerstone
    new_max = mlb_proposal_max(fa_seasons)                                           # 15%, another club
    lo, b, st = paths["low"], paths["base"], paths["stress"]
    bands = {
        "current rules": extension_band(lo["arb_mlbtr"], b["arb_mlbtr"], lo["fa_value"], b["fa_value"]),
        # ASSUMPTION: under MLB's plan the club keeps him at the own-club maximum (the rule exists so the
        # own club can outbid others by a point), so both the club's alternative cost and his best
        # outside pay are min(value, 16% path).
        "MLB plan": extension_band(lo["arb_mlbtr"], b["arb_mlbtr"], lo["fa_value"], b["fa_value"],
                                   fa_max_salary=own_max, club_fa_max=own_max),
        "MLB plan, 15% outside offers": extension_band(lo["arb_mlbtr"], b["arb_mlbtr"], lo["fa_value"],
                                                       b["fa_value"], fa_max_salary=new_max, club_fa_max=own_max),
        "current rules, injury-stress floor": extension_band(st["arb_mlbtr"], b["arb_mlbtr"], st["fa_value"],
                                                             b["fa_value"]),
        "FanGraphs arbitration shares": extension_band(lo["arb_fangraphs"], b["arb_fangraphs"], lo["fa_value"],
                                                       b["fa_value"]),
    }
    ceilings = {(rules, sp): club_ceiling(paths, sp, None if rules == "current rules" else own_max)
                for rules in ("current rules", "MLB plan") for sp in STRESS_PROBS}
    breakeven = {(q, sp): (1 - q) * ceilings[("current rules", sp)] + q * ceilings[("MLB plan", sp)]
                 for q in CAP_PROBS for sp in STRESS_PROBS}
    floors = {q: (1 - q) * bands["current rules"]["player_floor_pv"] + q * bands["MLB plan"]["player_floor_pv"]
              for q in CAP_PROBS}
    alt = {k: skenes_paths(base_war * m, base_season=2025) for k, m in SCENARIOS.items()}
    base_2025 = extension_band(alt["low"]["arb_mlbtr"], alt["base"]["arb_mlbtr"], alt["low"]["fa_value"],
                               alt["base"]["fa_value"])
    control = {k: {"pv_value_2027_29": pv(p["value"][:3]), "pv_arb_2027_29": pv(p["arb_mlbtr"]),
                   "pv_surplus_2027_29": pv(p["value"][:3]) - pv(p["arb_mlbtr"])} for k, p in paths.items()}
    fa_nominal = sum(b["fa_value"])
    fa_2026_dollars = [v / 1.03 ** (s - 2026) for v, s in zip(b["fa_value"], fa_seasons)]
    qo = qualifying_offer("recipient", "other", 200.0)
    return {"base_war_2027": base_war, "paths": paths, "control_surplus": control, "bands": bands,
            "own_club_max": own_max, "new_club_max": new_max, "ceilings": ceilings, "breakeven": breakeven,
            "player_floor_by_q": floors, "ceiling_if_dpw_base_2025": base_2025["club_ceiling_pv"],
            "fa_aav_nominal": fa_nominal / FA_YEARS_BOUGHT,
            "fa_aav_2026_dollars": sum(fa_2026_dollars) / FA_YEARS_BOUGHT, "qo_if_he_leaves": qo}


def skenes_flat_price_check() -> dict:
    """The same extension priced at one flat price of a win ($11.23M, FanGraphs' overall figure) in place of the
    tiered price ($12.84M at 2+ WAR). The Torres evaluation rejects tiers; this shows how much of the Skenes price
    rests on them. Returns the club's break-even grid and the player's floor on the flat price."""
    from baseball.roster import money as _m

    tiers = _m.DPW_TIERS_2026
    _m.DPW_TIERS_2026 = ((0.0, _m.DPW_FLAT_2026),)
    try:
        e = skenes_extension()
    finally:
        _m.DPW_TIERS_2026 = tiers
    return {"breakeven": e["breakeven"], "ceilings": e["ceilings"], "player_floor_by_q": e["player_floor_by_q"],
            "fa_aav_nominal": e["fa_aav_nominal"]}


def breakeven_at(paths: dict, own_max: list[float], stress_prob: float, q: float) -> float:
    """The club's break-even at any stress chance and any chance q of MLB's plan: the same mix as the grid in
    `skenes_extension()`, for values the grid doesn't carry."""
    return (1 - q) * club_ceiling(paths, stress_prob, None) + q * club_ceiling(paths, stress_prob, own_max)


def stress_equivalent(surgery_share: float, days_out: float, war_share_lost: float, years: int = 8) -> float:
    """The stress chance that loses as many expected wins as a surgery that only costs time. A surgery with
    chance `surgery_share` that costs `days_out` of a `years`-year deal loses surgery_share x days_out /
    (365 x years) of the wins; the stress path loses `war_share_lost` of them. The ratio is the chance."""
    return surgery_share * days_out / (365 * years) / war_share_lost


def skenes_injury_check(q: float = 0.25) -> dict:
    """The memo's stress chance beside published surgery shares (facts.UCL_EVIDENCE). The published figures
    are shares of pitchers with an elbow ligament reconstruction in their history, not a forward chance for
    one pitcher, and the stress path (60% of his wins in every season) is harsher than one surgery. So each
    share is read two ways: as the stress chance itself (every surgery costs the whole stress path), and as
    time missed only (the mean 470 days out, then the same pitcher). The memo's 20% sits between them."""
    e = skenes_extension()
    paths, own = e["paths"], e["own_club_max"]
    lost = 1 - sum(paths["stress"]["war"]) / sum(paths["base"]["war"])
    ev = facts.UCL_EVIDENCE
    rows = []
    for label, key in (("major league pitchers (Conte 2015)", "mlb_pitchers_with_history"),
                       ("top-five-round draftees, 2011-20 (Kriz 2026)", "top_five_round_draftees_with_history")):
        share = ev[key]["share"]
        time_only = stress_equivalent(share, ev["days_to_return"], lost, years=len(paths["base"]["war"]))
        rows.append({"population": label, "n": ev[key]["n"], "of": ev[key]["of"], "share": share,
                     "stress_chance_time_only": time_only,
                     "breakeven_time_only": breakeven_at(paths, own, time_only, q),
                     "breakeven_full_stress": breakeven_at(paths, own, share, q)})
    grid = {(qq, sp): breakeven_at(paths, own, sp, qq) for qq in CAP_PROBS for sp in (0.2, 0.25, 0.33)}
    return {"q": q, "war_share_lost_on_stress_path": lost, "days_out": ev["days_to_return"],
            "share_of_deal_missed": ev["days_to_return"] / (365 * len(paths["base"]["war"])),
            "rows": rows, "headline_stress_chance": 0.2, "headline_breakeven": e["breakeven"][(q, 0.2)],
            "grid": grid}


def club_ceiling_own_value(paths: dict, stress_prob: float, cap: list[float] | None, multiple: float) -> float:
    """The club ceiling when a win is worth `multiple` times the market price to this club. Season by
    season the club's alternative costs what `club_ceiling` says (arbitration, then the going price), but a
    club never pays more for a season than the season is worth to it, so each season counts
    min(alternative cost, multiple x market value). At multiple >= 1 this is `club_ceiling`: a club that
    values a win above the market price can still buy the seasons at the market price."""
    def cost(p: dict) -> list[float]:
        alt = list(p["arb_mlbtr"]) + _capped(p["fa_value"], cap)
        return [min(a, multiple * v) for a, v in zip(alt, p["value"])]
    return pv(_mix(cost(paths["base"]), cost(paths["stress"]), stress_prob))


def skenes_win_curve_check(stress_prob: float = 0.2, q: float = 0.25) -> dict:
    """The walk-away for a club by where it sits on the win curve (facts.WIN_CURVE_GENNARO_2006; shape only).
    ASSUMPTION: the market price of a win is what a win is worth to a club at 86 to 91 wins, because those
    are the clubs that bid for stars. The second anchor (the mean of the two bands) is shown beside it."""
    e = skenes_extension()
    paths, own = e["paths"], e["own_club_max"]
    g = facts.WIN_CURVE_GENNARO_2006
    lo, hi = g["78-83"]["average"], g["86-91"]["average"]
    anchors = {"market price = value at 86 to 91 wins": hi, "market price = mean of the two bands": (lo + hi) / 2}

    def walk(multiple: float) -> float:
        return ((1 - q) * club_ceiling_own_value(paths, stress_prob, None, multiple)
                + q * club_ceiling_own_value(paths, stress_prob, own, multiple))

    rows = []
    for band, five in (("78 to 83 wins", lo), ("86 to 91 wins", hi)):
        row = {"band": band, "value_of_five_wins_2006": five}
        for name, ref in anchors.items():
            row[name] = {"multiple": five / ref, "breakeven": walk(five / ref)}
        rows.append(row)
    return {"stress_prob": stress_prob, "q": q, "market_breakeven": e["breakeven"][(q, stress_prob)],
            "ratio_86_91_to_78_83": hi / lo,
            "pirates_ratio_86_91_to_78_83": g["86-91"]["pirates"] / g["78-83"]["pirates"],
            "pirates_share_of_average_86_91": g["86-91"]["pirates"] / hi, "rows": rows}


def nov3_cap_check() -> dict:
    """MLB's Nov. 3, 2026 offer against the cap path this memo uses. The memo grows the May figure 3% a year;
    the new offer starts in 2028. If the 16% share is unchanged (not reported), the own-club maximum and the
    healthy MLB-plan ceiling's free-agent part rise by the same ratio."""
    e = skenes_extension()
    memo_2028 = facts.MLB_PROPOSAL["cap_2027"] * (1 + CAP_GROWTH)
    ratio = facts.MLB_PROPOSAL_NOV3["cap_2028"] / memo_2028
    arb = pv(e["paths"]["base"]["arb_mlbtr"])
    ceiling = e["bands"]["MLB plan"]["club_ceiling_pv"]
    return {"memo_cap_2028": memo_2028, "nov3_cap_2028": facts.MLB_PROPOSAL_NOV3["cap_2028"], "ratio": ratio,
            "own_club_max_2030_memo": e["own_club_max"][0], "own_club_max_2030_nov3": e["own_club_max"][0] * ratio,
            "mlb_plan_ceiling_memo": ceiling, "mlb_plan_ceiling_nov3": arb + ratio * (ceiling - arb)}


def _jsonable(x):
    if isinstance(x, dict):
        return {(f"q={k[0]}, stress={k[1]}" if isinstance(k, tuple) else str(k)): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    return round(x, 4) if isinstance(x, float) else x


def save_checks(path: str | Path | None = None) -> Path:
    """Write the Nov. 15 checks to reports/outputs/skenes-checks-2026.json."""
    path = Path(path) if path else Path(__file__).resolve().parents[2] / "reports" / "outputs" / "skenes-checks-2026.json"
    e, fl = skenes_extension(), skenes_flat_price_check()
    out = {"source": "Built 2026-11-15 by baseball.roster.cases.save_checks() from the public facts in "
                     "baseball/roster/facts.py. Dollars are $M of present value at the start of 2027.",
           "breakeven": e["breakeven"], "breakeven_flat_price": fl["breakeven"],
           "injury": skenes_injury_check(), "win_curve": skenes_win_curve_check(), "nov3_cap": nov3_cap_check()}
    path.write_text(json.dumps(_jsonable(out), indent=1) + "\n")
    return path


def comps_check() -> pd.DataFrame:
    """Does the linear $/WAR price reproduce real pitcher contracts? FanGraphs' study method
    (`implied_dpw`): level pay deflated 5% a year over the aged projection. Grain: one contract."""
    rows = []
    for c in facts.MARKET_COMPS:
        rate = DPW_TIERS_HISTORY[c["dpw_row"]][2]
        row = {"pitcher": c["name"], "deal": c["deal"], "age": c["age"], "years": c["years"], "total": c["total"],
               "aav": c["total"] / c["years"], "fangraphs_2plus_rate": rate}
        if c.get("war_path"):
            pay = sum((c["total"] / c["years"]) / 1.05 ** t for t in range(c["years"]))
            row["implied_dpw"] = pay / sum(c["war_path"])
            row["projection"] = c["projection_note"]
        elif c.get("war1") is not None:
            row["implied_dpw"] = implied_dpw(c["total"], c["years"], c["war1"])
            row["projection"] = c["projection_note"]
        else:
            row["implied_war1_at_rate"] = implied_war1(c["total"], c["years"], rate)
            row["projection"] = "none sourced; implied year-1 WAR shown"
        if "implied_dpw" in row:
            row["ratio_to_rate"] = row["implied_dpw"] / rate
        rows.append(row)
    return pd.DataFrame(rows)


def structure_pv(signing_bonus: float, salaries: list[float], discount: float = DISCOUNT) -> dict:
    """PV of a contract paid as a signing bonus (counted at t = 0, i.e. paid before the 2027 season) plus
    salaries from 2027 (t = 0). CBT AAV = (bonus + salaries) / years."""
    total = signing_bonus + sum(salaries)
    return {"pv": signing_bonus + pv(salaries, discount), "nominal": total, "aav": total / len(salaries)}


ILLUSTRATIVE_OFFER = {"signing_bonus": 25.0, "salaries": [8.0, 17.0, 25.0, 42.0, 42.0, 42.0, 42.0, 42.0]}
# Walk-away: about the club's break-even with a 20% stress chance and a 25% chance of MLB's plan (PV ~218).
WALK_AWAY = {"signing_bonus": 25.0, "salaries": [8.0, 18.0, 27.0, 46.0, 46.0, 46.0, 46.0, 46.0]}


def lost_salary(salary: float, games_lost: int, games: int = 162) -> float:
    """Salary not paid for canceled games. Salaries are paid by games played; a signing bonus is paid
    regardless (CBS Sports, Matt Snyder, Apr. 9, 2025, on Guerrero's contract). Proportional approximation."""
    return salary * games_lost / games


def band_figure(path: str = "reports/figures/2026-skenes-extension-band.png") -> str:
    """The extension price band (player floor to club ceiling, PV at 2027) under each rule set, plus the
    durability-adjusted club ceiling (20% stress chance) and the offer."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from baseball.house import SERIES
    from baseball.viz import INK, MUTED, _style

    e = skenes_extension()
    order = ["current rules", "MLB plan", "current rules, injury-stress floor", "FanGraphs arbitration shares"]
    labels = ["Current rules", "MLB's June 2026 plan\n(16% own-club max)", "Current rules,\ninjury-stress floor",
              "Arbitration by FanGraphs\nshares (no MLBTR anchor)"]
    adj = {"current rules": e["ceilings"][("current rules", 0.2)], "MLB plan": e["ceilings"][("MLB plan", 0.2)],
           "current rules, injury-stress floor": e["ceilings"][("current rules", 0.2)]}
    offer = structure_pv(ILLUSTRATIVE_OFFER["signing_bonus"], ILLUSTRATIVE_OFFER["salaries"])["pv"]
    fig, ax = plt.subplots(figsize=(8, 3.8), dpi=150)
    _style(ax)
    ax.grid(axis="y", visible=False)
    for i, k in enumerate(order):
        b = e["bands"][k]
        y = len(order) - 1 - i
        ax.plot([b["player_floor_pv"], b["club_ceiling_pv"]], [y, y], color=SERIES[0], lw=7, solid_capstyle="butt")
        ax.text(b["player_floor_pv"] - 2, y, f"{b['player_floor_pv']:.0f}", ha="right", va="center", fontsize=8, color=MUTED)
        ax.text(b["club_ceiling_pv"] + 2, y, f"{b['club_ceiling_pv']:.0f}", ha="left", va="center", fontsize=8, color=MUTED)
        if k in adj:
            ax.plot(adj[k], y, marker="v", ms=7, color=INK, zorder=3)
    walk = structure_pv(WALK_AWAY["signing_bonus"], WALK_AWAY["salaries"])["pv"]
    ax.axvline(offer, color=SERIES[1], lw=1.5, ls="--")
    ax.text(offer - 1, len(order) - 0.45, f"opening offer {offer:.0f}", color=SERIES[1], fontsize=8, ha="right")
    ax.axvline(walk, color=MUTED, lw=1.2, ls=":")
    ax.text(walk + 1, len(order) - 0.45, f"walk-away {walk:.0f}", color=MUTED, fontsize=8, ha="left")
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(labels[::-1], fontsize=8.5, color=INK)
    ax.set_ylim(-0.6, len(order) - 0.2)
    lo = min(e["bands"][k]["player_floor_pv"] for k in order)
    hi = max(e["bands"][k]["club_ceiling_pv"] for k in order)
    ax.set_xlim(lo - 14, hi + 12)
    ax.set_xlabel("Present value at the start of 2027, $M (10% discount)\n"
                  "Triangle: club ceiling with a 20% injury-stress chance (assumption)", fontsize=8, color=MUTED)
    ax.set_title("Paul Skenes, 8 years (2027-34): player floor to healthy-path club ceiling",
                 fontsize=10, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def main() -> None:
    pd.set_option("display.width", 200)
    t = cbt_2025_check()
    print("(a) 2025 CBT bills, $M\n", t.round(6).to_string(index=False))
    print("\n(c) Skenes service:", skenes_service())
    e = skenes_extension()
    print(f"\nBase 2027 WAR (5/4/3 fWAR): {e['base_war_2027']:.3f}")
    for k, p in e["paths"].items():
        print(f"  {k}: WAR {[round(w, 2) for w in p['war']]}")
        print(f"     value {[round(v, 1) for v in p['value']]}")
        print(f"     arb MLBTR-anchored {[round(v, 2) for v in p['arb_mlbtr']]}, FanGraphs {[round(v, 2) for v in p['arb_fangraphs']]}")
    print("\nControl-years surplus (PV at 2027):", {k: {kk: round(vv, 1) for kk, vv in v.items()} for k, v in e["control_surplus"].items()})
    print("MLB plan max salary 2030-34, own club 16%:", [round(x, 1) for x in e["own_club_max"]],
          " other club 15%:", [round(x, 1) for x in e["new_club_max"]])
    print(f"Free-agent price implied for 2030-34: ${e['fa_aav_nominal']:.1f}M a year nominal, "
          f"${e['fa_aav_2026_dollars']:.1f}M in 2026 dollars")
    for k, b in e["bands"].items():
        print(f"\n{k}:")
        print({kk: (round(vv, 1) if isinstance(vv, float) else vv) for kk, vv in b.items()})
        print(f"   nominal 8-yr totals at level AAV: floor {8 * b['player_floor_aav']:.0f}, mid {8 * b['midpoint_aav']:.0f}, ceiling {8 * b['club_ceiling_aav']:.0f}")
    print("\nDurability-adjusted club ceilings (rules, stress chance): PV")
    for k, v in e["ceilings"].items():
        print(f"   {k}: {v:.1f}")
    print("Club break-even price by chance of MLB's plan q (rows) and stress chance (cols):")
    for q in CAP_PROBS:
        print(f"   q={q:.2f}: " + "  ".join(f"{e['breakeven'][(q, sp)]:.1f}" for sp in STRESS_PROBS)
              + f"   | player floor {e['player_floor_by_q'][q]:.1f}")
    print(f"Ceiling if FanGraphs' $12.84M is a 2025 price: {e['ceiling_if_dpw_base_2025']:.1f}")
    fl = skenes_flat_price_check()
    print("Same grid at one flat price of a win ($11.23M, no tiers):")
    for q in CAP_PROBS:
        print(f"   q={q:.2f}: " + "  ".join(f"{fl['breakeven'][(q, sp)]:.1f}" for sp in STRESS_PROBS)
              + f"   | player floor {fl['player_floor_by_q'][q]:.1f}")
    inj = skenes_injury_check()
    print(f"\nSourced surgery shares beside the stress chance (q = {inj['q']}); the stress path loses "
          f"{100 * inj['war_share_lost_on_stress_path']:.1f}% of his wins, {inj['days_out']} days is "
          f"{100 * inj['share_of_deal_missed']:.1f}% of the deal:")
    for r in inj["rows"]:
        print(f"   {r['population']}: {r['n']} of {r['of']} = {100 * r['share']:.1f}%; time only = stress chance "
              f"{100 * r['stress_chance_time_only']:.1f}%, break-even {r['breakeven_time_only']:.1f}; "
              f"as the stress chance, break-even {r['breakeven_full_stress']:.1f}")
    for qq in CAP_PROBS:
        print(f"   q={qq:.2f}: " + "  ".join(f"{inj['grid'][(qq, sp)]:.1f}" for sp in (0.2, 0.25, 0.33)))
    wc = skenes_win_curve_check()
    print(f"\nWalk-away by place on the win curve (Gennaro 2006 shape; market break-even {wc['market_breakeven']:.1f}):")
    for r in wc["rows"]:
        print(f"   {r['band']}: " + "; ".join(f"{k}: x{v['multiple']:.2f} -> {v['breakeven']:.1f}"
                                             for k, v in r.items() if isinstance(v, dict)))
    print("Nov. 3 cap offer:", {k: round(v, 3) for k, v in nov3_cap_check().items()})
    print("Saved:", save_checks())
    o = structure_pv(ILLUSTRATIVE_OFFER["signing_bonus"], ILLUSTRATIVE_OFFER["salaries"])
    print("\nOpening offer:", ILLUSTRATIVE_OFFER, {k: round(v, 1) for k, v in o.items()})
    w = structure_pv(WALK_AWAY["signing_bonus"], WALK_AWAY["salaries"])
    print("Walk-away:", WALK_AWAY, {k: round(v, 1) for k, v in w.items()})
    print("\nComparable contracts:\n", comps_check().round(2).to_string(index=False))
    print("\nQO if he leaves after 2029 (current rules):", e["qo_if_he_leaves"])
    print("Lost 2027 salary at $7.2M if 60 games are canceled:", round(lost_salary(7.2, 60), 2))


if __name__ == "__main__":
    main()
