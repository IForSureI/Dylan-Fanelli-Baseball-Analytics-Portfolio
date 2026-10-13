"""The engine applied to public cases: the 2025 tax bills and the Paul Skenes extension decision.

`uv run python -m baseball.roster.cases` prints every number the report quotes.
"""
from __future__ import annotations

import pandas as pd

from baseball.roster import facts
from baseball.roster.money import (DISCOUNT, arb_path, cbt_bill, dollars_per_war, extension_band, level_aav,
                                   project_war, pv, qualifying_offer)
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


def skenes_service() -> dict:
    s = Service.parse("0.000")
    credited_2024 = rookie_of_year_credit(facts.SKENES["days_2024_on_field"], facts.SKENES["roy_2024_finish"])
    s = s.plus_season(credited_2024).plus_season(172).plus_season(172)   # 2024 (credited), 2025, 2026
    t = timeline(s, 2026, future_days=172)
    without = Service(0).plus_season(facts.SKENES["days_2024_on_field"]).plus_season(172).plus_season(172)
    t0 = timeline(without, 2026, future_days=172, super_two_cutoff=SUPER_TWO_2027_ESTIMATE)
    return {"service_after_2026": str(s), "matches_mlbtr": str(s) == facts.SKENES["service_after_2026"],
            "arb_seasons": t.arb_seasons, "free_agent_after": t.free_agent_after,
            "control_seasons": t.control_seasons,
            "without_roy_credit": {"service_after_2026": str(without), "super_two_2027": t0.super_two,
                                   "arb_seasons": t0.arb_seasons, "free_agent_after": t0.free_agent_after}}


def skenes_war_base() -> float:
    """Weighted fWAR, 2026/2025/2024 at 5/4/3. No public 2027 projection existed on 2026-10-12."""
    w = facts.SKENES["fwar"]
    return sum(k * w[y] for k, y in zip(WEIGHTS, (2026, 2025, 2024))) / sum(WEIGHTS)


def skenes_paths(war1: float) -> dict:
    """Arbitration salaries and free-agent values, 2027-34, for a 2027 WAR of war1 (aged from 25)."""
    years = 3 + FA_YEARS_BOUGHT
    war = project_war(war1, first_age=25, years=years)                 # ages 25-32 in 2027-34
    platform = [facts.SKENES["fwar"][2026], war[0], war[1]]             # 2026 actual, then projected
    arb_fg = arb_path(platform, FIRST_ARB)                               # FanGraphs shares alone
    arb_mlbtr_rows = arb_path(platform, FIRST_ARB, first_salary=facts.SKENES["mlbtr_2027_arb"], calibrate=True)
    seasons = list(range(FIRST_ARB, FIRST_ARB + years))
    value = [w * dollars_per_war(w, s) for w, s in zip(war, seasons)]
    return {"seasons": seasons, "war": war, "value": value,
            "arb_fangraphs": [r["salary"] for r in arb_fg],
            "arb_mlbtr": [r["salary"] for r in arb_mlbtr_rows],
            "fa_value": value[3:]}


def mlb_proposal_max(seasons: list[int], share: float | None = None) -> list[float]:
    """Most a new club could pay in each free-agent season under MLB's June 25, 2026 proposal:
    15% of the cap in the first year (cap grown from 2027 at CAP_GROWTH), then +5% a year."""
    p = facts.MLB_PROPOSAL
    share = p["new_club_share"] if share is None else share
    first = share * p["cap_2027"] * (1 + CAP_GROWTH) ** (seasons[0] - 2027)
    return [first * (1 + p["raise"]) ** k for k in range(len(seasons))]


def skenes_extension() -> dict:
    base_war = skenes_war_base()
    paths = {k: skenes_paths(base_war * m) for k, m in SCENARIOS.items()}
    fa_seasons = paths["base"]["seasons"][3:]
    cap_path = mlb_proposal_max(fa_seasons)
    bands = {
        "status quo (2022-26 rules)": extension_band(paths["low"]["arb_mlbtr"], paths["base"]["arb_mlbtr"],
                                                     paths["low"]["fa_value"], paths["base"]["fa_value"]),
        "MLB proposal (15% max on the open market)": extension_band(
            paths["low"]["arb_mlbtr"], paths["base"]["arb_mlbtr"], paths["low"]["fa_value"],
            paths["base"]["fa_value"], fa_max_salary=cap_path),
        "FanGraphs arbitration shares (no MLBTR anchor)": extension_band(
            paths["low"]["arb_fangraphs"], paths["base"]["arb_fangraphs"], paths["low"]["fa_value"],
            paths["base"]["fa_value"]),
        "status quo, injury-stress floor (x0.6 WAR)": extension_band(
            paths["stress"]["arb_mlbtr"], paths["base"]["arb_mlbtr"], paths["stress"]["fa_value"],
            paths["base"]["fa_value"]),
    }
    control = {k: {"pv_value_2027_29": pv(p["value"][:3]), "pv_arb_2027_29": pv(p["arb_mlbtr"]),
                   "pv_surplus_2027_29": pv(p["value"][:3]) - pv(p["arb_mlbtr"])} for k, p in paths.items()}
    qo = qualifying_offer("recipient", "other", 200.0)
    return {"base_war_2027": base_war, "paths": paths, "control_surplus": control, "bands": bands,
            "mlb_cap_path": cap_path, "qo_if_he_leaves": qo}


def structure_pv(signing_bonus: float, salaries: list[float], discount: float = DISCOUNT) -> dict:
    """PV of a contract paid as a signing bonus (counted at t = 0, i.e. paid before the 2027 season) plus
    salaries from 2027 (t = 0). CBT AAV = (bonus + salaries) / years."""
    total = signing_bonus + sum(salaries)
    return {"pv": signing_bonus + pv(salaries, discount), "nominal": total, "aav": total / len(salaries)}


ILLUSTRATIVE_OFFER = {"signing_bonus": 25.0, "salaries": [8.0, 18.0, 27.0, 46.0, 46.0, 46.0, 46.0, 46.0]}


def lost_salary(salary: float, games_lost: int, games: int = 162) -> float:
    """Salary not paid for canceled games (salaries are paid over the season; signing bonuses are not
    affected by a stoppage, per the Guerrero case). Proportional approximation."""
    return salary * games_lost / games


def band_figure(path: str = "reports/figures/2026-skenes-extension-band.png") -> str:
    """The extension price band (player floor to club ceiling, PV at 2027) under each rule set."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from baseball.viz import INK, MUTED, _style

    e = skenes_extension()
    order = ["status quo (2022-26 rules)", "MLB proposal (15% max on the open market)",
             "status quo, injury-stress floor (x0.6 WAR)", "FanGraphs arbitration shares (no MLBTR anchor)"]
    labels = ["Current rules", "MLB's June 2026 plan\n(15%-of-cap market max)",
              "Current rules,\ninjury-stress floor", "Arbitration by FanGraphs\nshares (no MLBTR anchor)"]
    offer = structure_pv(ILLUSTRATIVE_OFFER["signing_bonus"], ILLUSTRATIVE_OFFER["salaries"])["pv"]
    fig, ax = plt.subplots(figsize=(8, 3.6), dpi=150)
    _style(ax)
    ax.grid(axis="y", visible=False)
    for i, k in enumerate(order):
        b = e["bands"][k]
        y = len(order) - 1 - i
        ax.plot([b["player_floor_pv"], b["club_ceiling_pv"]], [y, y], color="#2a78d6", lw=7, solid_capstyle="butt")
        ax.plot(b["midpoint_pv"], y, marker="|", ms=16, mew=2.5, color=INK)
        ax.text(b["player_floor_pv"] - 2, y, f"{b['player_floor_pv']:.0f}", ha="right", va="center", fontsize=8, color=MUTED)
        ax.text(b["club_ceiling_pv"] + 2, y, f"{b['club_ceiling_pv']:.0f}", ha="left", va="center", fontsize=8, color=MUTED)
    ax.axvline(offer, color="#eb6834", lw=1.5, ls="--")
    ax.text(offer, len(order) - 0.45, f"illustrative offer, PV {offer:.0f}", color="#eb6834", fontsize=8, ha="center")
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(labels[::-1], fontsize=8.5, color=INK)
    ax.set_ylim(-0.6, len(order) - 0.2)
    lo = min(e["bands"][k]["player_floor_pv"] for k in order)
    hi = max(e["bands"][k]["club_ceiling_pv"] for k in order)
    ax.set_xlim(lo - 14, hi + 12)
    ax.set_xlabel("Present value at the start of 2027, $M (10% discount)", fontsize=9, color=MUTED)
    ax.set_title("Paul Skenes, 8 years (2027-34): player floor to club ceiling; tick = midpoint",
                 fontsize=10, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def main() -> None:
    pd.set_option("display.width", 160)
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
    print("MLB-proposal max salary path 2030-34:", [round(x, 1) for x in e["mlb_cap_path"]])
    for k, b in e["bands"].items():
        print(f"\n{k}:")
        print({kk: (round(vv, 1) if isinstance(vv, float) else vv) for kk, vv in b.items()})
        print(f"   nominal 8-yr totals at level AAV: floor {8 * b['player_floor_aav']:.0f}, mid {8 * b['midpoint_aav']:.0f}, ceiling {8 * b['club_ceiling_aav']:.0f}")
    o = structure_pv(ILLUSTRATIVE_OFFER["signing_bonus"], ILLUSTRATIVE_OFFER["salaries"])
    print("\nIllustrative offer:", ILLUSTRATIVE_OFFER, {k: round(v, 1) for k, v in o.items()})
    print("\nQO if he leaves after 2029 (current rules):", e["qo_if_he_leaves"])
    print("Lost 2027 salary at $7.2M if 60 games are canceled:", round(lost_salary(7.2, 60), 2))


if __name__ == "__main__":
    main()
