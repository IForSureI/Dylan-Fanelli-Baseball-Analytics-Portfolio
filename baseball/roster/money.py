"""Money under the 2022-26 Basic Agreement: the Competitive Balance Tax, arbitration salaries,
surplus value, extension pricing and qualifying-offer consequences.

Money is in $ millions throughout. Every rate carries its source; valuation inputs that are
assumptions (not rules) are labeled ASSUMPTION and are arguments, so a reader can change them.

Sources (checked 2026-10-12):
- CBT thresholds, base rates and surcharges: MLB.com glossary, Competitive Balance Tax. The third
  surcharge (42.5% vs 45%) depends on payor status, not tier history: the 2025 Phillies were not
  $40M+ over in 2024 (AP, Dec. 20, 2024: a $14.4M bill) yet paid 95% (50% + 45%) on $281-301M in
  2025 (AP, Dec. 19, 2025). The 2025 bills are reproduced in tests/test_roster_money.py.
- Minimum salary: 2022-26 Basic Agreement as reported by MLB.com.
- $/WAR: FanGraphs, Ben Clemens, "What Are Teams Paying for a Win in Free Agency? 2026 Edition"
  (Feb. 24, 2026): $12.84M (2+ WAR), $8.51M (1-2), $6.74M (0-1), $11.23M overall.
- Arbitration shares and discounting: FanGraphs, "The Details of Our New Prospect Valuation
  Methodology" (Clemens, July 2, 2026): Arb 1-4 = 15/35/50/75% of the prior season's WAR at
  free-agent prices; net 7% discount = 10% minus a 3% annual rise in the cost of a win.
- Qualifying offer: MLB.com glossary, Qualifying Offer ($22.025M for 2026; compensation and
  forfeiture by club status, including a second signing).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ------------------------------------------------------------------ CBT
CBT_THRESHOLDS = {2022: 230.0, 2023: 233.0, 2024: 237.0, 2025: 241.0, 2026: 244.0}
BASE_RATES = {1: 0.20, 2: 0.30, 3: 0.50}          # by consecutive seasons over (3 = third or more)
SURCHARGE_1 = 0.12                                # $20-40M over
SURCHARGE_2_FIRST, SURCHARGE_2_REPEAT = 0.425, 0.45   # $40-60M over: first-time vs repeat payor
SURCHARGE_3 = 0.60                                # $60M+ over
PICK_DROP_OVER = 40.0                             # $40M+ over: top pick moves back 10 places

MIN_SALARY = {2022: 0.700, 2023: 0.720, 2024: 0.740, 2025: 0.760, 2026: 0.780}


@dataclass
class TaxBill:
    payroll: float
    threshold: float
    consecutive_years: int
    over: float
    base: float
    surcharge_20_40: float
    surcharge_40_60: float
    surcharge_60_plus: float
    marginal_rate: float
    pick_drop: bool

    @property
    def total(self) -> float:
        return self.base + self.surcharge_20_40 + self.surcharge_40_60 + self.surcharge_60_plus

    @property
    def cost_of_next_dollar(self) -> float:
        """All-in cost of $1 more of tax payroll (salary plus tax)."""
        return 1 + self.marginal_rate


def cbt_bill(payroll: float, consecutive_years: int, season: int | None = None,
             threshold: float | None = None) -> TaxBill:
    """Competitive Balance Tax on a season's CBT payroll.

    consecutive_years: seasons in a row over the threshold, counting this one (a season under resets to 1).
    Rates are the 2022-26 agreement's; the 2027+ rules depend on the next agreement, so pass `threshold`
    explicitly for any later season.
    """
    if threshold is None:
        if season not in CBT_THRESHOLDS:
            raise ValueError(f"no threshold for {season}: the 2022-26 agreement expires Dec. 1, 2026; pass threshold=")
        threshold = CBT_THRESHOLDS[season]
    if consecutive_years < 1:
        raise ValueError("consecutive_years counts this season, so it is at least 1 when over")
    over = payroll - threshold
    if over <= 0:
        return TaxBill(payroll, threshold, 0, over, 0.0, 0.0, 0.0, 0.0, 0.0, False)
    base_rate = BASE_RATES[min(consecutive_years, 3)]
    s2_rate = SURCHARGE_2_FIRST if consecutive_years == 1 else SURCHARGE_2_REPEAT
    s1 = SURCHARGE_1 * min(max(over - 20, 0), 20)
    s2 = s2_rate * min(max(over - 40, 0), 20)
    s3 = SURCHARGE_3 * max(over - 60, 0)
    marginal = base_rate + (SURCHARGE_3 if over > 60 else s2_rate if over > 40 else SURCHARGE_1 if over > 20 else 0)
    return TaxBill(payroll, threshold, consecutive_years, over, base_rate * over, s1, s2, s3, marginal,
                   over >= PICK_DROP_OVER)


def tax_cost_of_signing(payroll: float, added_aav: float, consecutive_years: int, season: int | None = None,
                        threshold: float | None = None) -> dict:
    """Extra tax from adding `added_aav` of CBT payroll (the club's true cost is salary + this)."""
    before = cbt_bill(payroll, consecutive_years, season, threshold).total
    after = cbt_bill(payroll + added_aav, consecutive_years, season, threshold).total
    return {"tax_before": before, "tax_after": after, "added_tax": after - before,
            "all_in_cost": added_aav + after - before}


# ------------------------------------------------------------------ $/WAR and aging
DPW_TIERS_2026 = ((2.0, 12.84), (1.0, 8.51), (0.0, 6.74))   # (projected WAR at least, $M per WAR)
DPW_FLAT_2026 = 11.23
DPW_BASE_SEASON = 2026       # the FanGraphs 2026 study prices contracts signed for the 2026 season
DPW_GROWTH = 0.03            # ASSUMPTION: FanGraphs' July 2026 methodology (3% a year)
DISCOUNT = 0.10              # ASSUMPTION: FanGraphs' July 2026 methodology (10%; net 7% with growth)
ARB_SHARES = (0.15, 0.35, 0.50, 0.75)   # ASSUMPTION: FanGraphs July 2026 prospect methodology


def dollars_per_war(war: float, season: int = DPW_BASE_SEASON, tiered: bool = True,
                    growth: float = DPW_GROWTH) -> float:
    """Free-agent price of a win for a player projected at `war`, in `season` dollars."""
    if tiered:
        rate = next(r for lo, r in DPW_TIERS_2026 if war >= lo) if war >= 0 else DPW_TIERS_2026[-1][1]
    else:
        rate = DPW_FLAT_2026
    return rate * (1 + growth) ** (season - DPW_BASE_SEASON)


def project_war(war: float, first_age: int, years: int, aging: float = 0.4, decline_from: int = 29,
                steep_after: int = 33, steep: float = 0.6) -> list[float]:
    """WAR by year. ASSUMPTION (valuation.md, after FanGraphs' 0.4/yr): flat through age decline_from - 1,
    -aging a year from decline_from, -steep a year after steep_after; never below zero."""
    out, w = [], war
    for t in range(years):
        age = first_age + t
        if t > 0 and age >= decline_from:
            w -= steep if age > steep_after else aging
        out.append(max(w, 0.0))
    return out


# ------------------------------------------------------------------ arbitration
def arb_path(prior_wars: list[float], first_season: int, first_salary: float | None = None,
             calibrate: bool = False, shares: tuple[float, ...] = ARB_SHARES, tiered: bool = True,
             growth: float = DPW_GROWTH, min_salary: float = 0.78, never_down: bool = True) -> list[dict]:
    """Arbitration salaries: share_i x WAR in the season before x that season's free-agent $/WAR.

    prior_wars[i]: WAR in the platform season before arbitration year i+1 (actual for the first,
    projected after). first_salary: an outside projection for year 1 (e.g. MLB Trade Rumors); with
    calibrate=True, later years are scaled by first_salary / (share-rule year 1), so the path keeps the
    projection's level. never_down: ASSUMPTION that awards don't fall (they rarely do in practice).
    """
    rows, prev = [], 0.0
    rule_first = None
    for i, w in enumerate(prior_wars):
        platform = first_season + i - 1
        rate = dollars_per_war(w, platform, tiered, growth)
        rule = shares[i] * max(w, 0.0) * rate
        if i == 0:
            rule_first = rule
        scale = (first_salary / rule_first) if (calibrate and first_salary and rule_first) else 1.0
        sal = first_salary if (i == 0 and first_salary is not None) else rule * scale
        sal = max(sal, min_salary, prev if never_down else 0.0)
        rows.append({"season": first_season + i, "arb_year": i + 1, "platform_war": w, "share": shares[i],
                     "dollars_per_war": rate, "rule_salary": rule, "salary": sal})
        prev = sal
    return rows


# ------------------------------------------------------------------ surplus value
@dataclass
class Valuation:
    seasons: list[int]
    war: list[float]
    value: list[float]
    salary: list[float]
    discount: float
    pv_value: float = field(init=False)
    pv_salary: float = field(init=False)

    def __post_init__(self):
        f = [(1 + self.discount) ** t for t in range(len(self.seasons))]
        self.pv_value = sum(v / d for v, d in zip(self.value, f))
        self.pv_salary = sum(s / d for s, d in zip(self.salary, f))

    @property
    def pv_surplus(self) -> float:
        return self.pv_value - self.pv_salary


def value_seasons(war: list[float], first_season: int, salaries: list[float] | None = None,
                  tiered: bool = True, growth: float = DPW_GROWTH, discount: float = DISCOUNT) -> Valuation:
    """Free-agent value of each season (WAR x that season's $/WAR at the WAR's tier), less salary,
    discounted to the start of the first season (t = 0)."""
    seasons = [first_season + t for t in range(len(war))]
    value = [w * dollars_per_war(w, s, tiered, growth) for w, s in zip(war, seasons)]
    salary = list(salaries) if salaries is not None else [0.0] * len(war)
    if len(salary) != len(war):
        raise ValueError("one salary per season")
    return Valuation(seasons, list(war), value, salary, discount)


def surplus_range(war: float, first_age: int, first_season: int, salaries: list[float],
                  multipliers: tuple[float, float, float] = (0.8, 1.0, 1.2), **kw) -> dict:
    """Low / base / high PV surplus: the WAR projection scaled by `multipliers`, aged, priced, discounted."""
    aging = {k: kw.pop(k) for k in ("aging", "decline_from") if k in kw}
    out = {}
    for name, m in zip(("low", "base", "high"), multipliers):
        v = value_seasons(project_war(war * m, first_age, len(salaries), **aging), first_season, salaries, **kw)
        out[name] = v
    return out


def pv(amounts: list[float], discount: float = DISCOUNT) -> float:
    return sum(a / (1 + discount) ** t for t, a in enumerate(amounts))


def level_aav(present_value: float, years: int, discount: float = DISCOUNT) -> float:
    """The flat annual salary over `years` (first paid at t = 0) with this present value."""
    return present_value / sum(1 / (1 + discount) ** t for t in range(years))


# ------------------------------------------------------------------ extensions
def extension_band(arb_low: list[float], arb_base: list[float], fa_value_low: list[float],
                   fa_value_base: list[float], discount: float = DISCOUNT,
                   fa_max_salary: list[float] | None = None) -> dict:
    """Price band for an extension that replaces the arbitration years and buys free-agent years.

    Counterfactual (no extension): the club pays arbitration salaries, then the player is paid his
    market value as a free agent (by this club or another).
    - Club ceiling: PV of base arbitration salaries + PV of base free-agent value. Paying more gives
      the club negative expected surplus against going year to year and then paying market.
    - Player floor: PV of low arbitration + PV of low free-agent value. ASSUMPTION: the low (x0.8 WAR)
      case stands in for a risk-averse player's certainty equivalent.
    - fa_max_salary: a per-season cap on what the open market may pay (MLB's June 25, 2026 proposal);
      free-agent value is min(value, cap) for the player's outside option. The club's value of the
      wins is unchanged.
    All amounts are per season starting with the first arbitration season (t = 0).
    """
    n_arb = len(arb_base)
    if len(arb_low) != n_arb or len(fa_value_low) != len(fa_value_base):
        raise ValueError("low and base paths need the same length")
    fa_low = list(fa_value_low)
    fa_base_player = list(fa_value_base)
    if fa_max_salary is not None:
        fa_low = [min(v, c) for v, c in zip(fa_low, fa_max_salary)]
        fa_base_player = [min(v, c) for v, c in zip(fa_base_player, fa_max_salary)]
    lead = [0.0] * n_arb
    club_ceiling = pv(arb_base, discount) + pv(lead + list(fa_value_base), discount)
    player_floor = pv(arb_low, discount) + pv(lead + fa_low, discount)
    player_expected = pv(arb_base, discount) + pv(lead + fa_base_player, discount)
    years = n_arb + len(fa_value_base)
    mid = (club_ceiling + player_floor) / 2
    return {"years": years, "club_ceiling_pv": club_ceiling, "player_floor_pv": player_floor,
            "player_expected_pv": player_expected, "midpoint_pv": mid,
            "club_ceiling_aav": level_aav(club_ceiling, years, discount),
            "player_floor_aav": level_aav(player_floor, years, discount),
            "midpoint_aav": level_aav(mid, years, discount),
            "overlap": club_ceiling >= player_floor}


# ------------------------------------------------------------------ qualifying offer
QO_AMOUNT = {2026: 22.025}   # MLB.com glossary; the 2027 amount is set in early November 2026


def qualifying_offer(losing: str, signing: str, contract_total: float, nth_signing: int = 1) -> dict:
    """Compensation to the club losing a qualified free agent and the signing club's forfeiture.

    Status is 'payor' (CBT), 'recipient' (revenue sharing) or 'other'. nth_signing: 2 for the second
    qualified free agent a club signs that offseason. Both sides proposed ending the QO in 2026.
    """
    for s in (losing, signing):
        if s not in ("payor", "recipient", "other"):
            raise ValueError(f"status must be payor, recipient or other: {s!r}")
    if losing == "payor":
        comp = "pick after Round 4"
    elif losing == "recipient" and contract_total >= 50:
        comp = "pick between Round 1 and Competitive Balance Round A"
    else:
        comp = "pick after Competitive Balance Round B"
    if nth_signing == 1:
        forfeit = {"payor": (["2nd-highest", "5th-highest"], 1.0),
                   "recipient": (["3rd-highest"], 0.0),
                   "other": (["2nd-highest"], 0.5)}[signing]
        pool_note = None
    elif nth_signing == 2:
        forfeit = {"payor": (["3rd-highest", "6th-highest"], None),
                   "recipient": (["4th-highest"], None),
                   "other": (["3rd-highest"], None)}[signing]
        pool_note = "UNVERIFIED: MLB.com's glossary lists the picks for a second signing but not pool money"
    else:
        raise ValueError("rules are listed for a first and second signing only")
    return {"losing_club_gets": comp, "signing_club_forfeits_picks": forfeit[0],
            "signing_club_forfeits_pool": forfeit[1], "note": pool_note}
