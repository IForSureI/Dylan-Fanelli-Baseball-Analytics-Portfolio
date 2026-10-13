"""The engine applied to public cases: the 2025 tax bills and the Paul Skenes extension decision.

`uv run python -m baseball.roster.cases` prints every number the report quotes.
"""
from __future__ import annotations

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
STRESS_PROBS = (0.0, 0.2, 0.35)  # ASSUMPTION: illustrative chances of the stress path (no sourced rate)
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
        ax.plot([b["player_floor_pv"], b["club_ceiling_pv"]], [y, y], color="#2a78d6", lw=7, solid_capstyle="butt")
        ax.text(b["player_floor_pv"] - 2, y, f"{b['player_floor_pv']:.0f}", ha="right", va="center", fontsize=8, color=MUTED)
        ax.text(b["club_ceiling_pv"] + 2, y, f"{b['club_ceiling_pv']:.0f}", ha="left", va="center", fontsize=8, color=MUTED)
        if k in adj:
            ax.plot(adj[k], y, marker="v", ms=7, color=INK, zorder=3)
    walk = structure_pv(WALK_AWAY["signing_bonus"], WALK_AWAY["salaries"])["pv"]
    ax.axvline(offer, color="#eb6834", lw=1.5, ls="--")
    ax.text(offer - 1, len(order) - 0.45, f"opening offer {offer:.0f}", color="#eb6834", fontsize=8, ha="right")
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
    o = structure_pv(ILLUSTRATIVE_OFFER["signing_bonus"], ILLUSTRATIVE_OFFER["salaries"])
    print("\nOpening offer:", ILLUSTRATIVE_OFFER, {k: round(v, 1) for k, v in o.items()})
    w = structure_pv(WALK_AWAY["signing_bonus"], WALK_AWAY["salaries"])
    print("Walk-away:", WALK_AWAY, {k: round(v, 1) for k, v in w.items()})
    print("\nComparable contracts:\n", comps_check().round(2).to_string(index=False))
    print("\nQO if he leaves after 2029 (current rules):", e["qo_if_he_leaves"])
    print("Lost 2027 salary at $7.2M if 60 games are canceled:", round(lost_salary(7.2, 60), 2))


if __name__ == "__main__":
    main()
