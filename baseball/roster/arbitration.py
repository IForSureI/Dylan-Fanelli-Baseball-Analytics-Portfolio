"""Salary arbitration from the club's side: comparables, the panel's likely value, the filing number, the
midpoint, the chance of winning a hearing, the cost of being wrong and the settle-or-hearing decision.

Money in $ millions. Inputs that are judgment calls (rules and sourced facts aside) are labeled ASSUMPTION
and are arguments, so a reader can change them.

The rules: the 2022-2026 Basic Agreement, Article VI(E) (the text the MLBPA posts publicly), with the MLB.com
glossary entry Salary Arbitration (read 2026-10-18) for the plain-language version.
- Final offer: a three-arbitrator panel picks the player's figure or the club's, nothing in between. Figures are
  exchanged on the second Friday in January; each side gets an hour to present and 30 minutes of rebuttal, the
  player first, and "neither party shall carry the burden of proof." The decision comes within 24 hours.
- The criteria (Article VI(E)(10)(a)): the quality of the player's contribution to his club in the past season
  "(including but not limited to his overall performance, special qualities of leadership and public appeal)",
  the length and consistency of his career contribution, the record of his past compensation, comparative
  baseball salaries, any physical or mental defects, and "the recent performance record of the Club including but
  not limited to its League standing and attendance."
- Comparisons: "particular attention, for comparative salary purposes," goes to players with service not exceeding
  "one annual service group above the Player's annual service group" (`COMPARABLE_EXTRA_YEARS`). The same clause:
  "This shall not limit the ability of a Player or his representative, because of special accomplishment, to argue
  the equal relevance of salaries of Players without regard to service."
- Not admissible (Article VI(E)(10)(b) and (c)): the club's or the player's finances; press comments and
  testimonials (recognized annual awards for playing excellence are allowed); offers made before the hearing; the
  cost of representation; salaries in other sports or occupations; the Pre-Arbitration Performance Bonus Program
  and any amounts earned under it; and statistics and data "generated through the use of performance technology,
  wearable technology, or 'STATCAST', whether publicly available or not." The competitive balance tax can't be
  cited either.
That agreement expires Dec. 1, 2026 at 11:59 p.m. ET. The exchange date, the hearing calendar and the system itself
for 2027 depend on the next agreement; nothing here assumes the system changes.

The method, in the order a club's arbitration group works a case:
1. Comparables (`select_comparables`): first-time-eligible relievers whose salary was set by settlement or
   hearing (the pool rule is `POOL_RULE`), nearest the player on the stats panels weigh (platform saves, career
   saves, platform ERA) and in time. Distance scales are ASSUMPTIONS (`DISTANCE_SCALES`). Second-year closers
   (one service group above, so admissible) are the player's exhibits (`NEXT_GROUP`); `next_group_raises` splits
   each into the first-year base and the raise.
2. The bracket (`bracket`): comps the player beats on every panel stat set a floor the club can't file under
   without losing credibility; comps that beat him on every stat set a ceiling the player can't credibly pass.
3. The comp line (`fit_comp_line`): log salary on platform saves, career saves and the salary season, fit on
   the comps. The season term estimates how fast this market's salaries grow, so old comps are restated in
   the target season's dollars at a rate the comps themselves estimate. Its prediction
   standard error is the panel-noise stand-in.
4. The hearing (`p_club_wins`): the panel picks the figure nearer its own value V, so the club wins when
   V < midpoint. V ~ Normal(mu, sigma) under each view of the case; a list of weighted views gives a mixture.
5. The filing (`best_filing`): the club figure that minimizes the expected award against the player's likely
   figure, never below the bracket floor (Farber 1980: the side that files nearer the panel's expected award
   wins more often).
6. Settle or go (`walk_point`, `carry_cost`): a risk-neutral club accepts any settlement at or below the
   expected hearing award. Arbitration raises build on the prior salary, so a 2027 dollar is paid again in
   each later arbitration year (`carry_cost`; how much of the gap carries is an ASSUMPTION, `CARRY_SHARE`).

Two cases are worked here, each a `Target` record: Cade Smith (Cleveland, a three-year player) and Louis Varland
(Toronto, a Super Two). Sources for the facts below are on each row and in the two briefs,
reports/2027-arbitration-brief-smith.md and reports/2027-arbitration-brief-varland.md.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from baseball.roster.money import DISCOUNT
from baseball.roster.service import Service, timeline

COMPARABLE_EXTRA_YEARS = 1          # 'one annual service group above' (CBA Article VI(E)(10)(a))
DISTANCE_SCALES = {"platform_sv": 10.0, "career_sv": 25.0, "platform_era": 1.0, "years": 8.0}   # ASSUMPTION
CAREER_SV_TOLERANCE = 5             # ASSUMPTION: a panel reads career saves within 5 as even
FIT_MAX_AGE = 11                    # ASSUMPTION: comps more than 11 salary seasons old stay exhibits outside the fit
VIEW_WEIGHT_MARKET = 0.5            # ASSUMPTION: weight on the market-projection view of the panel (see the brief)
CARRY_SHARE = 1.0                   # ASSUMPTION: share of a 2027 gap still in the salary in each later arb year

POOL_RULE = ("Every reliever with 20 or more saves in a platform season from 2015 to 2025 (MLB Stats API season "
             "leaders) whose next season was his first arbitration year, Super Twos included, and whose salary "
             "for it was set by a one-year settlement or a hearing. Extensions, multi-year deals, players already "
             "past their first arbitration year, and candidates whose status or salary couldn't be confirmed from a "
             "public source are listed in SCREENED_OUT with the reason.")


def ip(text: str | float) -> float:
    """Innings in baseball notation to true innings: '75.1' -> 75 1/3, '64.2' -> 64 2/3."""
    s = f"{text}" if not isinstance(text, float) else f"{text:.1f}"
    whole, _, outs = s.partition(".")
    outs = int(outs or 0)
    if outs not in (0, 1, 2):
        raise ValueError(f"innings fraction must be .0, .1 or .2, got {text!r}")
    return int(whole) + outs / 3


@dataclass(frozen=True)
class Reliever:
    """One reliever's case as a panel sees it. Career figures run through the platform season."""
    name: str
    season: int                     # the salary season being decided
    platform_sv: int
    platform_era: float
    platform_ip: float              # true innings
    platform_so: int
    career_sv: int
    career_ip: float | None         # true innings through the platform season; None where not recorded here
    all_star_platform: bool
    service: str | None = None      # years.days when sourced
    super_two: bool = False
    salary: float | None = None     # $M; None for the player whose salary is being decided
    how: str = ""                   # settled / hearing result
    player_figure: float | None = None
    club_figure: float | None = None
    source: str = ""


# ------------------------------------------------------------------ the player
# Baseball-Reference player page (read 2026-10-18): 2024-26 lines, 2026 All-Star, born May 9, 1999. MLB Trade
# Rumors, "Projected Arbitration Salaries For 2027" (Darragh McDonald, Oct. 2, 2026): "Cade Smith: 3.000, $5.5MM".
# 41 saves in 46 chances: CBS Sports player page (Sept. 24, 2026 note). Tied for the MLB lead with Tampa Bay's Bryan
# Baker (41): Baseball-Reference 2026 leaders; Yardbarker, "The MLB annual save leaders since 2008" quiz (Oct. 14, 2026).
SMITH = Reliever("Cade Smith", 2027, platform_sv=41, platform_era=1.95, platform_ip=ip("74.0"), platform_so=107,
                 career_sv=58, career_ip=ip("223.0"), all_star_platform=True, service="3.000",
                 source="Baseball-Reference (read 2026-10-18); MLB Trade Rumors (Oct. 2, 2026)")
SMITH_SEASONS = {   # Baseball-Reference standard and value tables; FanGraphs for fWAR and xFIP (read 2026-10-18)
    2024: dict(sv=1, era=1.91, ip=ip("75.1"), so=103, bb=17, hr=1, g=74, gf=2, w=6, l=1, era_plus=211, fip=1.40,
               xfip=2.41, bwar=2.4, fwar=2.7, wpa=3.0, gmli=1.19, holds=28),
    2025: dict(sv=16, era=2.93, ip=ip("73.2"), so=104, bb=19, hr=4, g=76, gf=30, w=8, l=5, era_plus=142, fip=1.95,
               xfip=2.65, bwar=0.8, fwar=2.7, wpa=2.2, gmli=1.76, ra9=3.79),
    2026: dict(sv=41, era=1.95, ip=ip("74.0"), so=107, bb=23, hr=5, g=69, gf=60, w=6, l=1, era_plus=212, fip=2.18,
               xfip=2.63, bwar=2.9, fwar=2.6, wpa=4.7, gmli=1.81, sv_opp=46),
}   # 2024 holds: MLB.com player page bio (read 2026-10-18).
MLBTR_2027 = 5.5                  # MLBTR projection (Matt Swartz's model), Oct. 2, 2026
SMITH_FREE_AGENT_AFTER = 2029     # Baseball-Reference: "Free Agent: 2030"; arbitration 2027-29

# Baseball-Reference player page (read 2026-10-20): 2022-26 standard and value tables, 2026 All-Star, born Dec. 9, 1997,
# "Service Time (01/2026): 1.163", "Arb Eligible: 2027", "Free Agent: 2031". MLB Trade Rumors, "Projected Arbitration
# Salaries For 2027" (Darragh McDonald, Oct. 2, 2026): "Louis Varland, 2.163, $3.8MM", a Super Two (2 years 163 days);
# Heavy (Alvin Garcia, Oct. 14, 2026): "Louis Varland is projected at $3.8 million." First career save Apr. 21, 2026,
# the closer's job from April (Wikipedia, "Louis Varland", read 2026-10-20).
VARLAND = Reliever("Louis Varland", 2027, platform_sv=35, platform_era=1.27, platform_ip=ip("78.0"), platform_so=97,
                   career_sv=35, career_ip=ip("294.1"), all_star_platform=True, service="2.163", super_two=True,
                   source="Baseball-Reference (read 2026-10-20); MLB Trade Rumors (Oct. 2, 2026)")
VARLAND_SEASONS = {   # Baseball-Reference standard and value tables (read 2026-10-20); 2025 is Minnesota and Toronto
    2022: dict(sv=0, era=3.81, ip=ip("26.0"), so=21, bb=6, hr=4, g=5, gs=5, gf=0, w=1, l=2, era_plus=104, fip=4.30,
               bwar=0.4),
    2023: dict(sv=0, era=4.63, ip=ip("68.0"), so=71, bb=17, hr=16, g=17, gs=10, gf=1, w=4, l=3, era_plus=95, fip=5.02,
               bwar=0.6),
    2024: dict(sv=0, era=7.61, ip=ip("49.2"), so=49, bb=16, hr=12, g=16, gs=7, gf=1, w=0, l=6, era_plus=55, fip=5.54,
               bwar=-1.3),
    2025: dict(sv=0, era=2.97, ip=ip("72.2"), so=75, bb=22, hr=6, g=74, gs=1, gf=8, w=4, l=3, era_plus=144, fip=3.14,
               bwar=1.7),
    2026: dict(sv=35, era=1.27, ip=ip("78.0"), so=97, bb=23, hr=2, g=71, gs=0, gf=53, w=5, l=6, era_plus=348, fip=1.83,
               bwar=3.6, whip=1.000),
}
VARLAND_MLBTR_2027 = 3.8          # MLBTR projection (Matt Swartz's model), Oct. 2, 2026
VARLAND_FREE_AGENT_AFTER = 2030   # Baseball-Reference: "Free Agent: 2031"; as a Super Two, arbitration 2027-30
# MLB Trade Rumors lists him among the 2027 arbitration eligibles at 2.163; the official Super Two cutoff is set after
# the season, and its 2027 list includes players at 2.133, so 2.163 is above any cutoff that list implies.
SUPER_TWO_CUTOFF_2027 = "2.133"

# ------------------------------------------------------------------ comparables: first-time-eligible closers
# The screen (POOL_RULE): MLB Stats API season pitching leaders by saves, 2015-25 (read 2026-10-18), every reliever
# with 20+ saves; career saves summed from the same API's year-by-year lines. Platform lines below match
# Baseball-Reference for the original eleven rows and for Soto, Alzolay, Foley and Megill, whose career saves and
# innings are summed from its year-by-year lines (read 2026-10-18). Salaries, first-year status and how each salary
# was set: the source on each row.
POOL = [
    Reliever("Jonathan Papelbon", 2009, 41, 2.34, ip("69.1"), 77, 113, ip("230.0"), True, salary=6.25,
             how="settled", source="MLBTR arbitration records (Jan. 17, 2017): first-time reliever record; "
                                   "MLB.com (Adam McCalvy, Feb. 15, 2020)"),
    Reliever("Trevor Rosenthal", 2016, 48, 2.10, ip("68.2"), 83, 96, ip("237.0"), True, salary=5.6,
             how="settled", source="MLBTR arbitration records (Jan. 17, 2017)"),
    Reliever("Jeurys Familia", 2016, 43, 1.85, ip("78.0"), 86, 49, ip("178.1"), False, salary=4.1,
             how="settled", source="MLB.com (Adam McCalvy, Feb. 15, 2020): record for one full season as closer"),
    Reliever("Cody Allen", 2016, 34, 2.99, ip("69.1"), 99, 60, ip("238.1"), False, salary=4.15,
             how="settled", source="Spotrac (pre-arb 2014-15; signed Jan. 15, 2016, avoiding arbitration); "
                                   "AP via Fox News, 'Indians, closer Allen agree to 1-year, $4.15 million deal'"),
    Reliever("Héctor Rondón", 2016, 30, 1.67, ip("70.0"), 69, 59, ip("188.0"), False, salary=4.2,
             how="settled", source="Spotrac (pre-arb 2014-15; signed Jan. 15, 2016, avoiding arbitration)"),
    Reliever("Shawn Tolleson", 2016, 35, 2.99, ip("72.1"), 76, 35, ip("181.2"), False, salary=3.275,
             how="settled", source="AP via Fox 4 Dallas (Jan. 25, 2016): 'Eligible for arbitration for the first "
                                   "time'"),
    Reliever("A.J. Ramos", 2016, 32, 2.30, ip("70.1"), 87, 32, ip("223.2"), False, salary=3.4,
             how="settled", source="Spotrac (pre-arb 2014-15; signed Jan. 15, 2016)"),
    Reliever("Sam Dyson", 2017, 38, 2.43, ip("70.1"), 55, 40, ip("199.1"), False, salary=3.52,
             how="settled", source="Spotrac (pre-arb 2015-16; signed Jan. 13, 2017, avoiding arbitration); AP via "
                                   "Washington Times (Jan. 13, 2017)"),
    Reliever("Roberto Osuna", 2018, 39, 3.38, ip("64.0"), 83, 95, ip("207.2"), True, salary=5.3,
             how="hearing, club won", player_figure=5.8, club_figure=5.3,
             source="MLB.com (Deesha Thosar, Feb. 3, 2018)"),
    Reliever("Corey Knebel", 2018, 39, 1.78, ip("76.0"), 126, 41, ip("167.2"), True, super_two=True, salary=3.65,
             how="settled", source="MLB.com (Jan. 12, 2018): $3.65M per USA Today's Bob Nightengale; Brew Crew "
                                   "Ball (Jan. 12, 2018): 'first year of arbitration eligibility, qualifying as a "
                                   "Super Two'"),
    Reliever("Álex Colomé", 2018, 47, 3.24, ip("66.2"), 58, 84, ip("272.2"), False, salary=5.3,
             how="settled", source="DRaysBay (Jan. 12, 2018): $5.3M; DRaysBay (Nov. 16, 2017): 'just now entering his "
                                   "first year of arbitration'"),
    Reliever("Ken Giles", 2018, 34, 2.30, ip("62.2"), 83, 65, ip("244.0"), False, salary=4.6,
             how="hearing, player won", player_figure=4.6, club_figure=4.2,
             source="MLB.com (Feb. 3, 2018): Giles won, $4.6M over the Astros' $4.2M; Spotrac (pre-arb 2016-17)"),
    Reliever("Edwin Díaz", 2020, 26, 5.59, ip("58.0"), 99, 135, ip("249.0"), False, salary=5.1,
             how="settled", source="Spotrac (signed Jan. 10, 2020, avoiding arbitration)"),
    Reliever("Josh Hader", 2020, 37, 2.62, ip("75.2"), 138, 49, ip("204.2"), True, service="2.115",
             super_two=True, salary=4.1, how="hearing, club won", player_figure=6.4, club_figure=4.1,
             source="MLB.com (Adam McCalvy, Feb. 15, 2020)"),
    Reliever("Jordan Romano", 2023, 36, 2.11, ip("64.0"), 73, 61, ip("157.0"), True, salary=4.5375,
             how="settled", source="MLB.com (Keegan Matheson, Jan. 14, 2023); Spotrac"),
    Reliever("Gregory Soto", 2023, 30, 3.28, ip("60.1"), 60, 50, ip("204.2"), True, service="3.102", salary=3.925,
             how="settled", source="MLBTR, 'Projected Arbitration Salaries For 2023' (Oct. 10, 2022): 'Gregory Soto "
                                   "(3.102)', absent from the 2022 list; Philadelphia Inquirer (Alex Coffey, Jan. 13, "
                                   "2023): one-year deal, 'Soto ($3.925 million)'"),
    Reliever("David Bednar", 2024, 39, 2.00, ip("67.1"), 80, 61, ip("197.0"), True, service="3.076", salary=4.51,
             how="settled", source="MLB.com (Jake Crouse, Jan. 11, 2024); Spotrac (3.076)"),
    Reliever("Adbert Alzolay", 2024, 22, 2.67, ip("64.0"), 67, 23, ip("236.2"), False, service="3.050", salary=2.11,
             how="settled", source="MLBTR, 'Projected Arbitration Salaries For 2024' (Oct. 6, 2023): 'Adbert Alzolay "
                                   "(3.050)'; MLB.com (Jordan Bastian, Jan. 11, 2024): avoided arbitration, '$2.11 "
                                   "million for '24'"),
    Reliever("Alexis Díaz", 2025, 28, 3.99, ip("56.1"), 55, 75, ip("187.1"), False, service="3.000", salary=4.5,
             how="settled", source="Reds On SI (Greg Kuffner, Jan. 2025); Spotrac (3.000, signed Jan. 9, 2025)"),
    Reliever("Jhoan Duran", 2025, 23, 3.64, ip("54.1"), 66, 58, ip("184.1"), False, service="3.000", salary=4.125,
             how="settled", source="CBS Sports (Jan. 9, 2025); Spotrac (3.000)"),
    Reliever("Camilo Doval", 2025, 23, 4.88, ip("59.0"), 78, 92, ip("221.1"), False, service="3.071", salary=4.525,
             how="settled", source="Spotrac (3.071; signed Jan. 9, 2025, avoiding arbitration)"),
    Reliever("Jason Foley", 2025, 28, 3.15, ip("60.0"), 46, 35, ip("199.2"), False, service="3.033", salary=3.15,
             how="settled", source="MLBTR, 'Projected Arbitration Salaries For 2025' (Oct. 1, 2024): 'Jason Foley "
                                   "(3.033)'; MLB.com (Anne Rogers, Jan. 9, 2025): 'settled with ... Foley at $3.15 "
                                   "million'"),
    Reliever("Trevor Megill", 2025, 21, 2.72, ip("46.1"), 50, 21, ip("149.2"), False, service="3.002", salary=1.94,
             how="settled", source="MLBTR, 'Projected Arbitration Salaries For 2025' (Oct. 1, 2024): 'Trevor Megill "
                                   "(3.002)'; MLB.com (Adam McCalvy, Jan. 10, 2025): avoided arbitration, '$1.94 "
                                   "million'"),
    Reliever("Mason Miller", 2026, 22, 2.63, ip("61.2"), 104, 50, ip("160.0"), False, super_two=True, salary=4.0,
             how="settled", source="MLB.com (AJ Cassavell, Jan. 9, 2026): Super Two, $4M"),
]
ORIGINAL_TEN = ["Trevor Rosenthal", "Jeurys Familia", "Roberto Osuna", "Edwin Díaz", "Josh Hader", "Jordan Romano",
                "David Bednar", "Alexis Díaz", "Jhoan Duran", "Mason Miller"]   # the hand-built set, for comparison

# Screened by POOL_RULE and left out, with the reason. Service time in parentheses is MLB Trade Rumors' figure from its
# "Projected Arbitration Salaries" list for that winter; salaries are Baseball-Reference's salary table (read 2026-10-18).
SCREENED_OUT = [
    ("Brad Boxberger", 2016, "pre-arbitration in 2016 (first arbitration salary $1.6M in 2017; AP via Fox News)"),
    ("Zack Britton", 2016, "second arbitration year: a Super Two in 2015 (2.158), settled at $3.2M (MLBTR, Feb. 4, "
                           "2015); 2016 was $6.75M at 3.158"),
    ("Héctor Neris", 2018, "pre-arbitration in 2018 (Spotrac)"),
    ("Keone Kela", 2019, "second arbitration year (Super Two in 2018; Spotrac)"),
    ("Blake Treinen", 2019, "second arbitration year: first was 2018 at $2.15M (3.065; MLBTR, Oct. 10, 2017)"),
    ("Shane Greene", 2019, "second arbitration year: first was 2018 at $1.95M (3.075; MLBTR, Oct. 10, 2017)"),
    ("Taylor Rogers", 2020, "second arbitration year (Super Two in 2019; Spotrac)"),
    ("Hansel Robles", 2020, "third arbitration year (Spotrac)"),
    ("Lou Trivino", 2022, "second arbitration year (Super Two in 2021; Spotrac)"),
    ("Alex Reyes", 2022, "second arbitration year (Spotrac)"),
    ("Felipe Vázquez, Raisel Iglesias, Brad Hand, Emmanuel Clase, Pete Fairbanks, Andrés Muñoz", None,
     "extensions or multi-year contracts"),
    ("Clay Holmes", 2023, "second arbitration year: first was 2022 at $1.1M (3.031; MLBTR, Feb. 17, 2022)"),
    ("Paul Sewald", 2023, "second arbitration year: first was 2022 at $1.735M (3.072; MLBTR, Feb. 17, 2022)"),
    ("Scott Barlow", 2023, "second arbitration year: first was 2022 at $2.4M (3.030; MLBTR, Feb. 17, 2022)"),
    ("Evan Phillips", 2024, "second arbitration year: a Super Two in 2023 at $1.3M (2.136; MLBTR, Oct. 10, 2022; "
                            "True Blue LA, Jan. 7, 2023)"),
    ("Will Vest", 2026, "second arbitration year: first was 2025 at $1.4M (3.100; MLBTR, Oct. 1, 2024), after a "
                        "two-save platform"),
    ("Daniel Palencia", 2026, "pre-arbitration in 2026 (1.154 service; Baseball-Reference, earliest arbitration 2027)"),
]

# ------------------------------------------------------------------ the next service group (the player's exhibits)
# Second-year arbitration salaries of closers one service group above Smith: admissible under VI(E)(10)(a). Each is a
# raise on a first-year arbitration base (`first_year`). Platform lines: MLB Stats API (read 2026-10-18).
NEXT_GROUP = [
    dict(name="Jordan Romano", season=2024, platform_sv=36, platform_era=2.90, career_sv=97, salary=7.75,
         first_year=4.5375, source="Canadian Press via CP24 (Jan. 12, 2024): 'a deal worth US$7.75 million'"),
    dict(name="David Bednar", season=2025, platform_sv=23, platform_era=5.77, career_sv=84, salary=5.9,
         first_year=4.51, source="Pittsburgh Baseball Now (Jan. 9, 2025): '$5.9 million'"),
    dict(name="Jhoan Duran", season=2026, platform_sv=32, platform_era=2.06, career_sv=90, salary=7.5,
         first_year=4.125, source="MLB.com, Phillies avoid arbitration (Jan. 8, 2026): '$7.5 million'"),
    dict(name="Camilo Doval", season=2026, platform_sv=16, platform_era=3.58, career_sv=108, salary=6.1,
         first_year=4.525, source="Spotrac (4.071; signed Jan. 8, 2026); Yankees On SI (Jan. 8, 2026)"),
]

# ------------------------------------------------------------------ 2026 exchanges (the size of real gaps)
# Mark Feinsand, MLB.com, "3 takeaways from arbitration deadline" (Jan. 9, 2026): player figure, club figure.
# Results: AP (Feb. 6, 2026, via NY1) and Brew Crew Ball's post-deadline recap: players 8-4 in 2026 hearings.
EXCHANGES_2026 = [
    ("Reid Detmers", 2.925, 2.625, "club"), ("Yainer Diaz", 4.5, 3.0, "player"),
    ("Isaac Paredes", 9.95, 8.75, "settled"), ("Eric Lauer", 5.75, 4.4, "club"),
    ("Dylan Lee", 2.2, 2.0, "player"), ("William Contreras", 9.9, 8.55, "settled"),
    ("Bryce Miller", 2.625, 2.25, "settled"), ("Calvin Faucher", 2.05, 1.8, "club"),
    ("Cade Cavalli", 0.9, 0.825, "settled"), ("Kyle Bradish", 3.55, 2.875, "player"),
    ("Keegan Akin", 3.375, 2.975, "club"), ("Edwin Uceta", 1.525, 1.2, "player"),
    ("Graham Ashcraft", 1.75, 1.25, "player"), ("Tyler Stephenson", 6.8, 6.55, "player"),
    ("Vinnie Pasquantino", 4.5, 4.0, "settled"), ("Kris Bubic", 6.15, 5.15, "player"),
    ("Tarik Skubal", 32.0, 19.0, "player"), ("Joe Ryan", 6.35, 5.85, "settled"),
]


# ------------------------------------------------------------------ comparables
def comparable_by_service(player_service: str | Service, comp_service: str | Service | None,
                          extra_years: int = COMPARABLE_EXTRA_YEARS) -> bool:
    """A comp may have at most `extra_years` more full years of service than the player; less is allowed.
    Unknown comp service (None) passes; check it by hand."""
    if comp_service is None:
        return True
    return Service.parse(comp_service).years <= Service.parse(player_service).years + extra_years


def distance(player: Reliever, comp: Reliever, scales: dict = DISTANCE_SCALES) -> float:
    """Scaled distance on the stats a panel weighs for a reliever, plus time between the salary seasons."""
    d = ((player.platform_sv - comp.platform_sv) / scales["platform_sv"]) ** 2
    d += ((player.career_sv - comp.career_sv) / scales["career_sv"]) ** 2
    d += ((player.platform_era - comp.platform_era) / scales["platform_era"]) ** 2
    d += ((player.season - comp.season) / scales["years"]) ** 2
    return math.sqrt(d)


def select_comparables(player: Reliever, pool: list[Reliever], k: int = 6,
                       scales: dict = DISTANCE_SCALES) -> list[tuple[Reliever, float]]:
    """The k nearest service-eligible comps with a known salary, nearest first."""
    ok = [c for c in pool if c.salary is not None and comparable_by_service(player.service or "3.000", c.service)]
    return sorted(((c, distance(player, c, scales)) for c in ok), key=lambda t: t[1])[:k]


def dominance(player: Reliever, comp: Reliever, career_tol: int = CAREER_SV_TOLERANCE) -> int:
    """+1 if the player is at least as good on platform saves, platform ERA and career saves (within the
    tolerance); -1 if the comp is at least as good on all three; 0 if mixed."""
    p_ge = (player.platform_sv >= comp.platform_sv and player.platform_era <= comp.platform_era
            and player.career_sv >= comp.career_sv - career_tol)
    c_ge = (comp.platform_sv >= player.platform_sv and comp.platform_era <= player.platform_era
            and comp.career_sv >= player.career_sv - career_tol)
    if p_ge and not c_ge:
        return 1
    if c_ge and not p_ge:
        return -1
    return 0


def restate(salary: float, from_season: int, to_season: int, growth: float) -> float:
    """A salary set in `from_season`, restated in `to_season` dollars at `growth` a year."""
    return salary * (1 + growth) ** (to_season - from_season)


def bracket(player: Reliever, comps: list[Reliever], growth: float) -> dict:
    """Floor: the highest restated salary among comps the player beats on every panel stat. Ceiling: the lowest
    among comps that beat him on every stat (None when no comp does)."""
    below = [(restate(c.salary, c.season, player.season, growth), c.name) for c in comps if dominance(player, c) == 1]
    above = [(restate(c.salary, c.season, player.season, growth), c.name) for c in comps if dominance(player, c) == -1]
    floor = max(below) if below else None
    ceiling = min(above) if above else None
    return {"floor": floor[0] if floor else None, "floor_comp": floor[1] if floor else None,
            "ceiling": ceiling[0] if ceiling else None, "ceiling_comp": ceiling[1] if ceiling else None,
            "beats": sorted(n for _, n in below), "beaten_by": sorted(n for _, n in above),
            "mixed": sorted(c.name for c in comps if dominance(player, c) == 0)}


# ------------------------------------------------------------------ the comp line
@dataclass
class CompLine:
    """log(salary) = b0 + b1 platform_sv + b2 career_sv + b3 (season - target)."""
    coef: np.ndarray
    target_season: int
    resid_sd: float                 # log units
    xtx_inv: np.ndarray
    names: list[str] = field(default_factory=list)
    residuals: list[float] = field(default_factory=list)

    @property
    def growth(self) -> float:
        """Annual growth in this market's salaries implied by the season term."""
        return math.exp(self.coef[3]) - 1

    def _x(self, r: Reliever) -> np.ndarray:
        return np.array([1.0, r.platform_sv, r.career_sv, r.season - self.target_season])

    def predict(self, r: Reliever) -> dict:
        """Line value in $M and its prediction standard error (log units and $M at the line value)."""
        x = self._x(r)
        log_v = float(x @ self.coef)
        se_log = self.resid_sd * math.sqrt(1 + float(x @ self.xtx_inv @ x))
        value = math.exp(log_v)
        return {"value": value, "se_log": se_log, "se": value * se_log}


def fit_comp_line(comps: list[Reliever], target_season: int) -> CompLine:
    """Least squares on log salary. Needs at least five comps (four coefficients plus one degree of freedom)."""
    rows = [c for c in comps if c.salary is not None]
    if len(rows) < 5:
        raise ValueError("the comp line needs at least five comps with salaries")
    X = np.array([[1.0, c.platform_sv, c.career_sv, c.season - target_season] for c in rows])
    y = np.log([c.salary for c in rows])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    sd = math.sqrt(float(resid @ resid) / (len(rows) - X.shape[1]))
    return CompLine(coef, target_season, sd, np.linalg.inv(X.T @ X), [c.name for c in rows], [float(e) for e in resid])


def fit_pool(pool: list[Reliever], target_season: int, max_age: int = FIT_MAX_AGE) -> list[Reliever]:
    """Comps recent enough to fit the line on (older ones stay exhibits, e.g. a 2009 record)."""
    return [c for c in pool if c.salary is not None and target_season - c.season <= max_age]


def loo_errors(comps: list[Reliever], target_season: int) -> list[float]:
    """Leave-one-out errors in log salary: each comp predicted by the line fit on the others."""
    out = []
    for i, c in enumerate(comps):
        rest = comps[:i] + comps[i + 1:]
        out.append(math.log(c.salary) - math.log(fit_comp_line(rest, target_season).predict(c)["value"]))
    return out


def rms(xs: list[float]) -> float:
    return math.sqrt(sum(x * x for x in xs) / len(xs))


def added_predictor_tests(comps: list[Reliever], player: Reliever, target_season: int) -> list[dict]:
    """Refit the comp line with one more panel stat at a time (platform ERA, an All-Star dummy, platform strikeouts)
    and report its coefficient, the player's value and the fit. Answers 'do panels pay for these?' as far as the
    comps can."""
    extras = {"platform ERA (per run)": lambda r: r.platform_era,
              "All-Star in the platform year": lambda r: float(r.all_star_platform),
              "platform strikeouts (per 10)": lambda r: r.platform_so / 10}
    y = np.log([c.salary for c in comps])
    rows = []
    for label, f in extras.items():
        X = np.array([[1.0, c.platform_sv, c.career_sv, c.season - target_season, f(c)] for c in comps])
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ coef
        sd = math.sqrt(float(resid @ resid) / (len(comps) - X.shape[1]))
        xtx = np.linalg.pinv(X.T @ X)                     # pinv: a stat with no variation gets coefficient 0
        x0 = np.array([1.0, player.platform_sv, player.career_sv, player.season - target_season, f(player)])
        value = math.exp(float(x0 @ coef))
        rows.append({"stat": label, "coef": float(coef[4]), "coef_se": sd * math.sqrt(xtx[4, 4]), "value": value,
                     "se": value * sd * math.sqrt(1 + float(x0 @ xtx @ x0)), "resid_sd": sd})
    return rows


def next_group_raises(rows: list[dict] = NEXT_GROUP) -> list[dict]:
    """Each second-year salary split into the first-year arbitration base and the raise on it."""
    return [dict(r, raise_=r["salary"] - r["first_year"]) for r in rows]


def breakeven_weight(club: float, player: float, mu_comp: float, mu_market: float, sigma: float) -> float:
    """The weight on the market view at which the club's chance at `club` is exactly one half (bisection)."""
    lo, hi = 0.0, 1.0
    f = lambda w: p_club_wins(club, player, [(1 - w, mu_comp, sigma), (w, mu_market, sigma)]) - 0.5
    if f(lo) * f(hi) > 0:
        return float("nan")
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(lo) * f(mid) > 0 else (lo, mid)
    return (lo + hi) / 2


# ------------------------------------------------------------------ the hearing
def norm_cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def midpoint(club: float, player: float) -> float:
    return (club + player) / 2


def p_club_wins(club: float, player: float, views: list[tuple[float, float, float]]) -> float:
    """Chance the panel picks the club's figure. views: (weight, mu, sigma) for the panel's value V ~ Normal;
    the club wins when V is below the midpoint. Weights are normalized."""
    if club >= player:
        raise ValueError("the club's figure must be below the player's")
    m = midpoint(club, player)
    tot = sum(w for w, _, _ in views)
    return sum(w * norm_cdf((m - mu) / sd) for w, mu, sd in views) / tot


def expected_award(club: float, player: float, views: list[tuple[float, float, float]]) -> float:
    p = p_club_wins(club, player, views)
    return p * club + (1 - p) * player


def walk_point(club: float, player: float, views: list[tuple[float, float, float]]) -> float:
    """The settlement at which a risk-neutral club is indifferent to a hearing: the expected award. Settle at
    or below it; above it, the hearing is cheaper on average."""
    return expected_award(club, player, views)


def best_filing(player: float, views: list[tuple[float, float, float]], floor: float | None = None,
                step: float = 0.05, lo: float = 0.5) -> dict:
    """Club figure (on a `step` grid) minimizing the expected award against the player's figure, never below
    `floor`. Ties go to the higher figure (the more defensible one)."""
    start = max(lo, floor if floor is not None else lo)
    n = int(math.floor((player - start) / step + 1e-9))
    grid = [round(start + i * step, 6) for i in range(n) if start + i * step < player - 1e-9]
    if not grid:
        raise ValueError("no club figure between the floor and the player's figure")
    best = min(grid, key=lambda c: (round(expected_award(c, player, views), 9), -c))
    return {"club": best, "expected_award": expected_award(best, player, views),
            "p_club_wins": p_club_wins(best, player, views), "midpoint": midpoint(best, player)}


def settlement(club: float, player: float, share: float = 0.5) -> float:
    """A settlement `share` of the way from the club's figure to the player's. Bennett (Baseball Prospectus,
    Feb. 2, 2010): 50% of the gap was the most common point; the average was 46%."""
    return club + share * (player - club)


def carry_cost(gap_2027: float, seasons: int, discount: float = DISCOUNT, share: float = CARRY_SHARE) -> float:
    """PV (at the start of the first season) of a salary gap paid in full in the first season and at `share` of it in
    each later arbitration season. ASSUMPTION: later raises are added to the prior salary, so with share 1 a dollar
    of 2027 base is paid again each year."""
    return gap_2027 + sum(share * gap_2027 / (1 + discount) ** t for t in range(1, seasons))


def gap_ratios(exchanges: list[tuple] = EXCHANGES_2026) -> list[float]:
    """Player figure / club figure for each exchange."""
    return [p / c for _, p, c, _ in exchanges]


def median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def straddle(center: float, ratio: float) -> tuple[float, float]:
    """Club and player figures with player/club = ratio whose midpoint is `center`."""
    club = 2 * center / (1 + ratio)
    return club, club * ratio


# ------------------------------------------------------------------ the case
@dataclass(frozen=True)
class Target:
    """One arbitration case: the player, his club, his season lines, the market projection, his control, and the
    figure's layout (label positions only)."""
    player: Reliever
    club: str
    seasons: dict
    mlbtr: float                          # MLB Trade Rumors' projection, $M
    free_agent_after: int                 # Baseball-Reference's free-agency season minus one
    slug: str
    super_two_cutoff: str | None = None
    record_figure: float | None = None    # a high player filing to test; None = high_filing(mlbtr)
    record_label: str = ""
    grid: tuple = ()                      # club figures to tabulate; () = $0.1M steps around the filing
    alt_fit: str = "original_ten"         # the extra comp-set row in sensitivity(): "original_ten" or "recent"
    layout: dict = field(default_factory=dict)


SMITH_CASE = Target(SMITH, "Cleveland Guardians", SMITH_SEASONS, MLBTR_2027, SMITH_FREE_AGENT_AFTER, "smith",
                    record_figure=6.3, record_label="player files the record claim ($6.3M)",
                    grid=(4.5, 4.6, 4.75, 4.8, 4.9, 5.0, 5.1, 5.2), alt_fit="original_ten",
                    layout=dict(callouts={"Romano": (4.85, 5.1), "Bednar": (4.85, 4.9), "Doval": (4.85, 4.45),
                                          "A. Díaz": (4.85, 4.25), "Familia": (4.85, 4.05), "Allen": (4.85, 3.85)},
                                value_xy=(4.68, 3.5), labels_right=("club files",), grid_from=4.4,
                                filing_text="left", legend="lower right"))
VARLAND_CASE = Target(VARLAND, "Toronto Blue Jays", VARLAND_SEASONS, VARLAND_MLBTR_2027, VARLAND_FREE_AGENT_AFTER,
                      "varland", super_two_cutoff=SUPER_TWO_CUTOFF_2027, alt_fit="recent",
                      layout=dict(callouts={"Romano": (4.85, 5.35), "Bednar": (4.85, 5.15), "Doval": (4.85, 4.95),
                                            "A. Díaz": (4.85, 4.75), "Familia": (4.85, 4.55), "Allen": (4.85, 4.35),
                                            "Rondón": (1.95, 5.0), "Hader": (1.95, 4.8), "Duran": (1.95, 4.6),
                                            "Miller": (1.95, 4.4), "Soto": (1.95, 4.2), "Knebel": (1.95, 3.92),
                                            "Dyson": (1.95, 3.5), "Ramos": (1.95, 3.3), "Tolleson": (1.95, 3.1),
                                            "Foley": (1.95, 2.9)},
                                  value_xy=(4.3, 3.35), labels_right=("club files", "player's likely figure",
                                                                       "MLBTR projection"),
                                  grid_from=None, filing_text="top", legend="upper left"))
CASES = {"smith": SMITH_CASE, "varland": VARLAND_CASE}


def high_filing(center: float, exchanges: list[tuple] | None = None, skip: tuple[str, ...] = ("Tarik Skubal",)) -> float:
    """A high player filing: the widest 2026 player/club ratio (Skubal's record case left out) straddling `center`,
    rounded to $50K."""
    exchanges = EXCHANGES_2026 if exchanges is None else exchanges
    r = max(p / c for n, p, c, _ in exchanges if n not in skip)
    return round(straddle(center, r)[1] * 20) / 20


def smith_case(view_weight_market: float = VIEW_WEIGHT_MARKET, record_figure: float = 6.3,
               seasons_carried: int | None = None) -> dict:
    """Cade Smith's case (the first brief)."""
    return case(SMITH_CASE, view_weight_market, record_figure, seasons_carried)


def varland_case(view_weight_market: float = VIEW_WEIGHT_MARKET, record_figure: float | None = None,
                 seasons_carried: int | None = None) -> dict:
    """Louis Varland's case (the second brief)."""
    return case(VARLAND_CASE, view_weight_market, record_figure, seasons_carried)


def case(t: Target = SMITH_CASE, view_weight_market: float = VIEW_WEIGHT_MARKET, record_figure: float | None = None,
         seasons_carried: int | None = None) -> dict:
    """Every number in a brief. The two views of the panel: the comp line (mu = its value) and the market
    projection (mu = MLBTR's figure), each with the comp line's prediction SE as sigma."""
    P, MLBTR = t.player, t.mlbtr
    record_figure = record_figure if record_figure is not None else (
        t.record_figure if t.record_figure is not None else high_filing(MLBTR))
    target = P.season
    chosen = select_comparables(P, POOL, k=6)
    fit_rows = fit_pool(POOL, target)
    line = fit_comp_line(fit_rows, target)
    pred = line.predict(P)
    sigma = pred["se"]
    views = [(1 - view_weight_market, pred["value"], sigma), (view_weight_market, MLBTR, sigma)]
    comp_only = [(1.0, pred["value"], sigma)]
    market_only = [(1.0, MLBTR, sigma)]
    br = bracket(P, [c for c, _ in chosen], line.growth)
    ratios = gap_ratios()
    r_med = median(ratios)
    club_sym, player_likely = straddle(MLBTR, r_med)
    player_likely = round(player_likely * 20) / 20          # filings are round numbers: nearest $50K
    fil = best_filing(player_likely, views, floor=br["floor"])
    club = math.ceil(fil["club"] * 20 - 1e-9) / 20      # round up to $50K so the figure stays at or above the floor
    control = timeline(P.service, target - 1, super_two_cutoff=t.super_two_cutoff)
    if control.free_agent_after != t.free_agent_after:
        raise ValueError("service engine and Baseball-Reference disagree on free agency")
    seasons = seasons_carried or control.arb_years
    out = {
        "target": t, "player": P.name, "club": t.club, "mlbtr": MLBTR,
        "chosen": [(c.name, d) for c, d in chosen],
        "line": line, "line_value": pred["value"], "line_se": sigma, "growth": line.growth,
        "bracket": br, "ratios_median": r_med, "player_likely": player_likely, "record_figure": record_figure,
        "club_symmetric": club_sym, "club_filing": club, "views": views,
        "midpoint": midpoint(club, player_likely),
        "p_win": {"blend": p_club_wins(club, player_likely, views),
                  "comp line": p_club_wins(club, player_likely, comp_only),
                  "market": p_club_wins(club, player_likely, market_only)},
        "expected_award": {"blend": expected_award(club, player_likely, views),
                           "comp line": expected_award(club, player_likely, comp_only),
                           "market": expected_award(club, player_likely, market_only)},
        "settle_50": settlement(club, player_likely, 0.5), "settle_46": settlement(club, player_likely, 0.46),
        "seasons_carried": seasons, "arb_seasons": control.arb_seasons,
        "cost_lose": carry_cost(player_likely - club, seasons),
        "record_case": {"p_win": p_club_wins(club, record_figure, views),
                        "midpoint": midpoint(club, record_figure),
                        "expected_award": expected_award(club, record_figure, views)},
    }
    out["walk_point"] = out["expected_award"]["blend"]
    out["walk_point_grid"] = math.floor(out["walk_point"] * 20 + 1e-9) / 20     # settle at or below this $50K figure
    out["cost_settle_at_mid_vs_hearing"] = carry_cost(out["settle_50"] - out["walk_point"], seasons)
    out["cost_lose_half_carry"] = carry_cost(player_likely - club, seasons, share=0.5)
    # A 2027 cut to 120 credited days: one more arbitration year before free agency.
    stop = timeline(P.service, target - 1, future_days=[120] + [172] * 7, super_two_cutoff=t.super_two_cutoff)
    out["stoppage_arb_seasons"] = stop.arb_seasons
    out["cost_lose_stoppage"] = carry_cost(player_likely - club, stop.arb_years)
    out["fit_n"] = len(fit_rows)
    out["loo"] = loo_errors(fit_rows, target)
    out["loo_rmse"] = rms(out["loo"])
    out["in_sample_sd"] = line.resid_sd
    out["added_predictors"] = added_predictor_tests(fit_rows, P, target)
    out["breakeven_weight"] = breakeven_weight(club, player_likely, pred["value"], MLBTR, sigma)
    out["next_group"] = next_group_raises()
    out["grid"] = [(c, p_club_wins(c, player_likely, views), expected_award(c, player_likely, views),
                    p_club_wins(c, player_likely, comp_only), p_club_wins(c, player_likely, market_only))
                   for c in sorted(set(t.grid or {round(club + d, 2) for d in (-0.3, -0.2, -0.1, 0.1, 0.2, 0.3, 0.4, 0.5)
                                                   if club + d < player_likely}) | {club})]
    return out


def sensitivity(t: Target = SMITH_CASE) -> list[dict]:
    """How the line value, the chance of winning at the filing and the walk point move with each assumption."""
    base = case(t)
    P, MLBTR = t.player, t.mlbtr
    club, player = base["club_filing"], base["player_likely"]
    rows = []

    def add(label: str, line_value: float, views: list[tuple[float, float, float]], player_fig: float = player):
        rows.append({"case": label, "line_value": line_value, "p_win": p_club_wins(club, player_fig, views),
                     "walk_point": walk_point(club, player_fig, views)})

    v, sd = base["line_value"], base["line_se"]
    add("base: even blend of the comp line and MLBTR", v, base["views"])
    for w in (0.25, 0.6, 0.75):
        add(f"weight on MLBTR's view {w:.2f}", v, [(1 - w, v, sd), (w, MLBTR, sd)])
    add(t.record_label or f"player files high (${base['record_figure']:.2f}M)", v, base["views"],
        player_fig=base["record_figure"])
    alt = (("fit on the original ten comps only", [c for c in fit_pool(POOL, P.season) if c.name in ORIGINAL_TEN])
           if t.alt_fit == "original_ten" else
           ("fit on the 2020-26 comps only (the recent market)", [c for c in fit_pool(POOL, P.season) if c.season >= 2020]))
    for lab, rows_fit in (("fit without the three hearing awards (Hader, Osuna, Giles)",
                           [c for c in fit_pool(POOL, P.season) if not c.how.startswith("hearing")]),
                          alt,
                          ("fit including Papelbon 2009", fit_pool(POOL, P.season, max_age=30))):
        ln = fit_comp_line(rows_fit, P.season).predict(P)
        add(lab, ln["value"], [(1 - VIEW_WEIGHT_MARKET, ln["value"], ln["se"]), (VIEW_WEIGHT_MARKET, MLBTR, ln["se"])])
    era = next(r for r in base["added_predictors"] if r["stat"].startswith("platform ERA"))
    add("comp line with platform ERA added", era["value"],
        [(1 - VIEW_WEIGHT_MARKET, era["value"], era["se"]), (VIEW_WEIGHT_MARKET, MLBTR, era["se"])])
    for sd2 in (0.25, 0.5):
        add(f"panel noise sigma ${sd2:.2f}M", v, [(1 - VIEW_WEIGHT_MARKET, v, sd2), (VIEW_WEIGHT_MARKET, MLBTR, sd2)])
    return rows


def figure(path: str | None = None, t: Target = SMITH_CASE) -> str:
    """Left: comps' salaries in 2027 dollars against the comp line, with the player's line value, the filing, the
    player's likely figure and MLBTR's projection. Right: chance the club wins by club figure, three views."""
    path = path or f"reports/figures/2027-arbitration-brief-{t.slug}.png"
    lay = t.layout
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from baseball.viz import INK, MUTED, _style

    cs = case(t)
    line = cs["line"]
    rows = fit_pool(POOL, t.player.season)
    fig, (a, b) = plt.subplots(1, 2, figsize=(10.5, 4.4), dpi=150, gridspec_kw={"width_ratios": [1.15, 1]})
    for ax in (a, b):
        _style(ax)
    blue, orange, green = "#2a78d6", "#eb6834", "#008300"
    chosen = {n for n, _ in cs["chosen"]}
    offsets = {"Osuna": (-5, 3, "right"), "Colomé": (5, 3, "left"), "Giles": (-6, 2, "right"),
               "Rondón": (-5, 4, "right"), "Hader": (-6, 3, "right"), "Duran": (-5, 0, "right"),
               "Knebel": (6, -6, "left"), "Miller": (0, -9, "center"), "Dyson": (-5, -3, "right"),
               "Ramos": (-5, -3, "right"), "Tolleson": (5, -3, "left"), "Rosenthal": (5, -3, "left"),
               "Soto": (5, -3, "left"), "Alzolay": (5, -3, "left"), "Foley": (5, -3, "left"),
               "Megill": (5, -3, "left")}
    # The crowded middle of the plot: labels in columns with leader lines (data coordinates), set per target.
    callouts = lay["callouts"]
    for c in rows:
        actual = restate(c.salary, c.season, t.player.season, line.growth)
        fitted = line.predict(c)["value"]
        hearing = c.how.startswith("hearing")
        a.scatter(fitted, actual, s=40 if c.name in chosen else 22, color=INK if hearing else blue,
                  marker="s" if hearing else "o", zorder=3, alpha=1 if c.name in chosen else 0.55)
        first, last = c.name.split()[0], c.name.split()[-1]
        label = f"{first[0]}. {last}" if last == "Díaz" else last
        color = INK if c.name in chosen else MUTED
        if label in callouts:
            a.annotate(f"{label} {c.season}", (fitted, actual), xytext=callouts[label], textcoords="data",
                       fontsize=6.5, color=color, ha="left", va="center",
                       arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.5, shrinkA=1, shrinkB=3))
            continue
        dx, dy, ha = offsets.get(last, (5, -3, "left"))
        if c.name == "Edwin Díaz":
            dx, dy, ha = -6, -9, "right"
        a.annotate(f"{label} {c.season}", (fitted, actual), xytext=(dx, dy), textcoords="offset points",
                   fontsize=6.5, color=color, ha=ha)
    lo, hi = 1.8, 6.6
    a.plot([lo, hi], [lo, hi], color=MUTED, lw=0.8, ls="--")
    v = cs["line_value"]
    a.errorbar([v], [v], yerr=[[cs["line_se"]], [cs["line_se"]]], fmt="D", color=orange, ms=7, capsize=3, zorder=4)
    a.annotate(f"{t.player.name.split()[-1]} line value \\${v:.2f}M", (v, v), xytext=lay["value_xy"], textcoords="data",
               ha="left", fontsize=8, color=orange)
    for y, txt, col in ((cs["club_filing"], "club files", green), (cs["player_likely"], "player's likely figure", MUTED),
                        (t.mlbtr, "MLBTR projection", MUTED)):
        a.axhline(y, color=col, lw=1, ls=":")
        right = txt in lay["labels_right"]
        a.text(hi - 0.03 if right else lo + 0.03, y + 0.03, f"{txt} \\${y:.2f}M", ha="right" if right else "left", fontsize=7, color=col)
    a.set_xlim(lo, hi)
    a.set_ylim(lo, hi)
    a.set_xlabel("Comp line: salary predicted from saves and season, \\$M (2027 dollars)", fontsize=8, color=MUTED)
    a.set_ylabel("Actual first-year salary, \\$M (2027 dollars)", fontsize=8, color=MUTED)
    a.set_title("First-time-eligible closers, 2016-26 (squares: hearings; bold: the six nearest)", fontsize=9, color=INK, loc="left")

    gfrom = lay["grid_from"] if lay["grid_from"] is not None else cs["club_filing"] - 0.6
    grid = np.arange(gfrom, cs["player_likely"] - 0.04, 0.02)
    P = cs["player_likely"]
    sig = cs["line_se"]
    for views, lab, col, ls in (([(1, v, sig)], "panel reads the comps", blue, "-"),
                                (cs["views"], "even blend (base case)", INK, "-"),
                                ([(1, t.mlbtr, sig)], "panel reads the market projection", orange, "--")):
        b.plot(grid, [p_club_wins(c, P, views) for c in grid], color=col, lw=1.8, ls=ls, label=lab)
    b.axvline(cs["club_filing"], color=green, lw=1, ls=":")
    if lay["filing_text"] == "left":
        b.text(cs["club_filing"] - 0.02, 0.06, f"club files \\${cs['club_filing']:.2f}M", fontsize=7.5, color=green, ha="right")
    else:
        b.text(cs["club_filing"] + 0.02, 0.95, f"club files \\${cs['club_filing']:.2f}M", fontsize=7.5, color=green, ha="left")
    b.set_ylim(0, 1)
    b.set_xlabel(f"Club figure, \\$M (player files \\${P:.2f}M)", fontsize=8, color=MUTED)
    b.set_ylabel("Chance the panel picks the club's figure", fontsize=8, color=MUTED)
    b.set_title("The hearing at each club figure", fontsize=9.5, color=INK, loc="left")
    b.legend(fontsize=7.5, frameon=False, loc=lay["legend"])
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def main(player: str = "smith") -> None:
    t = CASES[player.lower()]
    c = case(t)
    line = c["line"]
    print(f"{t.player.name} ({t.club}), service {t.player.service}{' (Super Two)' if t.player.super_two else ''}; "
          f"MLBTR ${t.mlbtr:.2f}M")
    print("Comparables chosen (distance):", [(n, round(d, 2)) for n, d in c["chosen"]])
    print("Comp line coefficients:", np.round(line.coef, 4), f"growth {line.growth:.4f}", f"resid sd {line.resid_sd:.4f}")
    print("Fit rows and residuals:", [(n, round(e, 3)) for n, e in zip(line.names, line.residuals)])
    print(f"{t.player.name} line value {c['line_value']:.3f}  se {c['line_se']:.3f}")
    print("Bracket:", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in c["bracket"].items()})
    for r in POOL:
        print(f"  {r.name:18s} {r.season} ${r.salary:.4f}M -> 2027 ${restate(r.salary, r.season, 2027, line.growth):.3f}M"
              f"  dominance {dominance(t.player, r):+d}  line {line.predict(r)['value']:.3f}")
    print(f"2026 exchange gap ratio median {c['ratios_median']:.4f}; symmetric club {c['club_symmetric']:.3f}")
    print(f"Player likely {c['player_likely']:.2f}; club files {c['club_filing']:.2f}; midpoint {c['midpoint']:.3f}")
    print("P(club wins):", {k: round(v, 3) for k, v in c["p_win"].items()})
    print("Expected award:", {k: round(v, 3) for k, v in c["expected_award"].items()})
    print(f"Settle at 50% {c['settle_50']:.3f}, at 46% {c['settle_46']:.3f}; walk point {c['walk_point']:.3f}")
    print(f"Cost of losing (PV, {c['seasons_carried']} seasons): {c['cost_lose']:.3f}; "
          f"settling at the midpoint vs hearing: {c['cost_settle_at_mid_vs_hearing']:.3f}")
    print(f"Walk point on the $50K grid: {c['walk_point_grid']:.2f}; breakeven weight on MLBTR's view "
          f"{c['breakeven_weight']:.3f}")
    print(f"Cost of losing with half the gap carried: {c['cost_lose_half_carry']:.3f}; with a fourth arbitration "
          f"year: {c['cost_lose_stoppage']:.3f}")
    print(f"Fit on {c['fit_n']} comps: in-sample sd {c['in_sample_sd']:.4f}, leave-one-out RMSE {c['loo_rmse']:.4f}")
    print("Leave-one-out errors:", [(n, round(e, 3)) for n, e in zip(line.names, c["loo"])])
    print("Added predictors:")
    for r in c["added_predictors"]:
        print(f"   {r['stat']:32s} coef {r['coef']:+.4f} (se {r['coef_se']:.4f})  player {r['value']:.3f}"
              f"  se {r['se']:.3f}  resid sd {r['resid_sd']:.4f}")
    print("Next service group (salary = first-year base + raise):")
    for r in c["next_group"]:
        print(f"   {r['name']:15s} {r['season']} ${r['salary']:.3f}M = ${r['first_year']:.4f}M + ${r['raise_']:.4f}M"
              f"  platform {r['platform_sv']} SV, {r['platform_era']} ERA, {r['career_sv']} career")
    print(f"Screened out: {len(SCREENED_OUT)} entries")
    print(f"High-filing case (${c['record_figure']:.2f}M):", {k: round(v, 3) for k, v in c["record_case"].items()})
    print("Grid (club, P blend, E blend, P comp, P market):")
    for g in c["grid"]:
        print("  ", [round(x, 3) for x in g])
    print("Sensitivity:")
    for r in sensitivity(t):
        print(f"   {r['case']:55s} line {r['line_value']:.3f}  P(win) {r['p_win']:.3f}  walk {r['walk_point']:.3f}")
    print(figure(t=t))


if __name__ == "__main__":
    import sys

    main(sys.argv[1] if len(sys.argv) > 1 else "smith")
