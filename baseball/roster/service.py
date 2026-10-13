"""Service time, control, options, Rule 5 and roster rights under the 2022-26 Basic Agreement.

Every rule here carries its source and the date it was checked. Rules marked UNVERIFIED were not
confirmed in a primary or reliable secondary source and should not be quoted without checking.
The agreement expires Dec. 1, 2026 at 11:59 p.m. ET; parameters that the 2026 proposals would
change are arguments, so a scenario can be run under the old and proposed rules side by side.

Grain: one player. Service time is written years.days (172 days = 1 year), e.g. 3.045.

Sources (checked 2026-10-12):
- MLB.com glossary, Service Time: 172 days = one year; 187-day season; arbitration at 3 to <6 years;
  free agency at 6 years after that season; Super Two = top 22% of players with 2 to <3 years and
  86+ days that season.
- Super Two cutoffs: AP, Nov. 7, 2025 (2.140 for 2026; 2.132 for 2025; 2.118 for 2024);
  UB Law Sports Forum, Nov. 2, 2022 (2.128 for 2023; 2.116 for 2022).
- UB Law Sports Forum (Mike Perlo, Nov. 17, 2022): a player with under 60 days of prior service, on at
  least two of the three preseason top-100 lists, "receives a full year of service time" for a top-two
  Rookie of the Year finish; MLBTR (via SI, Brady Farkas, Nov. 19, 2024) applied it to Skenes.
- MLB.com glossary, Minor League Options: 20+ days on optional assignment uses an option year;
  fourth option for players with fewer than five full seasons; at most five optional assignments a
  season; 10 days down for position players, 15 for pitchers.
- The Cub Reporter, MLB roster rules (Options; Rule 5): full season = 90+ days on the active list
  (or 30-89 active plus injured-list days reaching 90); spring-training options don't count toward
  the five; Rule 5 age is measured on the June 5 immediately preceding the first contract; a
  player who signs after the minor-league season ends has the next season as his first.
- MLB.com glossary, Rule 5 Draft: signed at 18 or younger, five seasons to protect; 19 or older, four.
- MLB.com glossary, Outright Waivers; MLBTR (June 2024, Luis Urías outright): 3+ years or a prior
  outright may refuse an outright assignment and elect free agency, forfeiting salary unless the
  player has 5+ years.
- MLB.com glossary, 10-and-5 rights.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

DAYS_PER_YEAR = 172          # MLB.com glossary
SEASON_DAYS = 187            # MLB.com glossary (183 before 2018)
SUPER_TWO_SHARE = 0.22       # MLB.com glossary
SUPER_TWO_MIN_DAYS = 86      # MLB.com glossary

# Super Two cutoff by the salary season it applies to (set the November before).
SUPER_TWO_CUTOFFS = {
    2022: "2.116",  # UB Law Sports Forum, Nov. 2, 2022 ("last year's 2.116")
    2023: "2.128",  # UB Law Sports Forum, Nov. 2, 2022
    2024: "2.118",  # AP, Nov. 7, 2025 ("two years, 118 days for 2024")
    2025: "2.132",  # AP, Nov. 7, 2025 ("two years, 132 days last offseason")
    2026: "2.140",  # AP, Nov. 7, 2025 (34 Super Twos)
}
SUPER_TWO_2027_ESTIMATE = "2.133"  # MLBTR projection, Oct. 2, 2026 (Hullihen estimate 2.134). NOT official.


@dataclass(frozen=True, order=True)
class Service:
    """MLB service time as total days; prints as years.days."""
    total_days: int

    @classmethod
    def parse(cls, s: str | float | "Service") -> "Service":
        """'3.045' -> 3 years 45 days. Strings are safest: the float 2.14 means 2.140, not 2.014."""
        if isinstance(s, Service):
            return s
        text = f"{s:.3f}" if isinstance(s, float) else str(s).strip()
        if "." in text:
            y, d = text.split(".", 1)
            if len(d) > 3:
                raise ValueError(f"days part has more than three digits: {text!r}")
            d = int(d.ljust(3, "0"))
        else:
            y, d = text, 0
        y = int(y)
        if not 0 <= d < DAYS_PER_YEAR:
            raise ValueError(f"days must be 0-171, got {d} in {text!r}")
        return cls(y * DAYS_PER_YEAR + d)

    @property
    def years(self) -> int:
        return self.total_days // DAYS_PER_YEAR

    @property
    def days(self) -> int:
        return self.total_days % DAYS_PER_YEAR

    def __str__(self) -> str:
        return f"{self.years}.{self.days:03d}"

    def plus_season(self, days: int) -> "Service":
        """Add one season. At most 172 days count in a season (one year); shorter stints carry over."""
        if days < 0 or days > SEASON_DAYS:
            raise ValueError(f"a season has 0-{SEASON_DAYS} service days, got {days}")
        return Service(self.total_days + min(days, DAYS_PER_YEAR))


def rookie_of_year_credit(days: int, roy_finish: int | None) -> int:
    """Days credited for a rookie season: a top-two Rookie of the Year finish lifts it to a full year.

    Source: UB Law Sports Forum, Nov. 17, 2022 (conditions: under 60 days of prior service, on two of
    three preseason top-100 lists; the caller checks them); Skenes .142 -> 1.000 per MLBTR via SI,
    Nov. 19, 2024. Not confirmed in the CBA text itself.
    """
    if roy_finish is not None and roy_finish <= 2:
        return max(days, DAYS_PER_YEAR)
    return days


def is_super_two(service_after_season: str | Service, days_that_season: int, cutoff: str | Service) -> bool:
    """Arbitration-eligible with 2 to <3 years: 86+ days that season and at or above the cutoff."""
    s, c = Service.parse(service_after_season), Service.parse(cutoff)
    return (2 <= s.years < 3) and days_that_season >= SUPER_TWO_MIN_DAYS and s >= c


@dataclass
class Timeline:
    service_now: str
    path: list[tuple[int, str]]            # (season, service after it)
    arb_seasons: list[int]                 # salary seasons decided by arbitration
    super_two: bool
    free_agent_after: int | None           # season after which he reaches 6.000
    control_seasons: list[int]             # seasons the club controls (pre-arb + arb) from next_season on

    @property
    def arb_years(self) -> int:
        return len(self.arb_seasons)


def timeline(service_now: str | Service, last_season: int, future_days: list[int] | int = DAYS_PER_YEAR,
             days_last_season: int = DAYS_PER_YEAR, super_two_cutoff: str | Service | None = None,
             horizon: int = 8) -> Timeline:
    """Control path from service after `last_season`.

    future_days: service days per future season (a list, or one number for every season; 172 = full).
    super_two_cutoff: checked in the one season he ends with 2.xxx (with days_last_season or that
        season's future days); pass the cutoff for that offseason.

    Rules: arbitration for season S+1 if service after S is 3.000 to <6.000, or Super Two; free agency
    after the season in which he reaches 6.000.
    """
    s = Service.parse(service_now)
    if isinstance(future_days, int):
        future_days = [future_days] * horizon
    path, arb, control = [], [], []
    super_two, fa = False, None
    cur, season, days_prev = s, last_season, days_last_season
    for i in range(len(future_days) + 1):
        # here `cur` is service after `season`
        if cur.years >= 6:
            fa = season
            break
        nxt = season + 1
        control.append(nxt)
        if cur.years >= 3:
            arb.append(nxt)
        elif cur.years == 2 and super_two_cutoff is not None and is_super_two(cur, days_prev, super_two_cutoff):
            arb.append(nxt)
            super_two = True
        if i == len(future_days):
            break
        days_prev = future_days[i]
        season, cur = nxt, cur.plus_season(days_prev)
        path.append((season, str(cur)))
    return Timeline(str(s), path, arb, super_two, fa, control)


# ---------------------------------------------------------------- options
OPTION_YEAR_MIN_DAYS = 20
MAX_OPTIONAL_ASSIGNMENTS = 5       # 2022-26; MLB proposed 4 (Aug. 27, 2026), MLBPA 3 (July 1, 2026)
MIN_DAYS_DOWN = {"position": 10, "pitcher": 15}
FULL_SEASON_ACTIVE_DAYS = 90


def uses_option_year(days_on_optional_assignment: int) -> bool:
    """20+ days on optional assignment in a season uses one option year (however many trips)."""
    return days_on_optional_assignment >= OPTION_YEAR_MIN_DAYS


def is_full_season(active_days: int, injured_days: int = 0) -> bool:
    """A 'full season' for fourth-option purposes: 90+ days on an active list, or 30-89 active days
    topped up to 90 with injured-list days (Cub Reporter's reading of the rule)."""
    if active_days >= FULL_SEASON_ACTIVE_DAYS:
        return True
    return active_days >= 30 and active_days + injured_days >= FULL_SEASON_ACTIVE_DAYS


def options_remaining(option_years_used: int, full_seasons: int) -> int:
    """Three option years; a fourth if all three are used and he has fewer than five full seasons."""
    if option_years_used < 3:
        return 3 - option_years_used
    if option_years_used == 3 and full_seasons < 5:
        return 1
    return 0


def can_option(option_years_left: int, assignments_this_season: int, in_spring: bool = False,
               max_assignments: int = MAX_OPTIONAL_ASSIGNMENTS) -> bool:
    """Optionable if an option year is left (or he is inside a year already used) and under the
    per-season limit. Spring-training options don't count toward the limit."""
    if option_years_left <= 0:
        return False
    return in_spring or assignments_this_season < max_assignments


def earliest_recall(optioned: date, role: str, replacing_injured: bool = False) -> date:
    """10 days down for position players, 15 for pitchers, unless he replaces an injured player (or is
    a doubleheader 27th man)."""
    from datetime import timedelta
    if replacing_injured:
        return optioned
    return optioned + timedelta(days=MIN_DAYS_DOWN[role])


# ---------------------------------------------------------------- Rule 5
def rule5_age_at_signing(birth: date, signed: date) -> int:
    """Age on the June 5 immediately preceding the first contract (Cub Reporter, Rule 5 chapter)."""
    june5 = date(signed.year, 6, 5)
    if signed < june5:
        june5 = date(signed.year - 1, 6, 5)
    return june5.year - birth.year - ((june5.month, june5.day) < (birth.month, birth.day))


def rule5_first_eligible(birth: date, signed: date, signed_after_season_end: bool = False,
                         years_earlier: int = 0) -> dict:
    """First December Rule 5 Draft at which the player is eligible if he isn't on the 40-man roster.

    18 or younger (June 5 rule): eligible at the 5th Rule 5 Draft after his first qualified season,
    i.e. first season + 4; 19 or older: first season + 3. The season of signing is the first unless he
    signed after the minor-league season ended. Checks: a high-schooler drafted and signed in July 2021
    -> Dec. 2025; a college junior signed in 2022 -> Dec. 2025.
    years_earlier: MLB's Aug. 27, 2026 proposal moves eligibility up a year (pass 1).
    """
    age = rule5_age_at_signing(birth, signed)
    first = signed.year + (1 if signed_after_season_end else 0)
    draft = first + (4 if age <= 18 else 3) - years_earlier
    return {"age_june5": age, "first_qualified_season": first, "first_eligible_draft": draft,
            "protect_by": f"November {draft} 40-man deadline"}


# ---------------------------------------------------------------- outrights and trade rights
def outright_rights(service: str | Service, previously_outrighted: bool = False) -> dict:
    """What a player can do when outrighted off the 40-man roster.

    3+ years or a prior outright: may refuse and elect free agency. Under 5 years, refusing forfeits
    the rest of his salary; 5+ years keeps it, and can't be outrighted without consent.
    """
    s = Service.parse(service)
    can_refuse = s.years >= 3 or previously_outrighted
    five = s.years >= 5
    return {"service": str(s), "can_refuse": can_refuse,
            "keeps_salary_if_refuses": five,
            "consent_required": five,
            "note": ("must accept the assignment" if not can_refuse else
                     "may elect free agency" + (" and keep his salary" if five else ", forfeiting remaining salary"))}


def ten_and_five(service: str | Service, consecutive_seasons_with_club: int) -> bool:
    """10+ years of service, the last five consecutive with the current club: veto over any trade."""
    return Service.parse(service).years >= 10 and consecutive_seasons_with_club >= 5
