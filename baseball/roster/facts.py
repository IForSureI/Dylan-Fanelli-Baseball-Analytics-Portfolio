"""Public facts the roster engine is tested against or applied to, each with its source.

Money in $ millions. Nothing here is estimated unless the field name or note says so.
"""
from __future__ import annotations

# ------------------------------------------------------------------ 2025 Competitive Balance Tax
# CBT payroll and bill to the dollar: Mike Axisa, CBS Sports, Dec. 20, 2025 ("Dodgers rack up
# record-smashing $169 million luxury tax bill"). Consecutive seasons over, counting 2025: AP
# (Ronald Blum), Dec. 19, 2025 (Mets, Dodgers, Yankees, Phillies four straight; Astros second) and
# Dec. 20, 2024 (2024 payors: Dodgers fourth straight; Rangers and Braves second; Astros first; the
# Blue Jays under at $233.9M; no Padres or Red Sox), so 2025 was the first year over for Toronto,
# San Diego and Boston, and the third for Texas. Any count of 3+ gets the same rate.
CBT_2025 = [
    # club, CBT payroll, consecutive seasons over, actual bill
    ("Dodgers", 417.341608, 5, 169.375768),
    ("Mets", 346.670456, 4, 91.637501),
    ("Yankees", 319.522564, 4, 61.774820),
    ("Phillies", 314.329912, 4, 56.062903),
    ("Blue Jays", 286.135551, 1, 13.609719),
    ("Padres", 270.351396, 1, 6.992447),
    ("Red Sox", 248.859139, 1, 1.496828),
    ("Astros", 245.991459, 2, 1.497438),
    ("Rangers", 241.380966, 3, 0.190483),
]
CBT_2025_SOURCE = "CBS Sports (Mike Axisa), Dec. 20, 2025; years over from AP, Dec. 20, 2024 and Dec. 19, 2025"
# The one club the published payroll doesn't reproduce: 20% x ($248,859,139 - $241,000,000) = $1,571,828,
# exactly $75,000 more than the published bill, i.e. a $375,000 difference in the payroll the bill was
# computed on. Not explained in the sources; reported, not adjusted.
RED_SOX_GAP = 0.075

# ------------------------------------------------------------------ Paul Skenes (Pirates, RHP)
SKENES = {
    "name": "Paul Skenes",
    "club": "Pirates",
    "born": "2002-05-29",                     # Baseball-Reference
    "service_after_2026": "3.000",            # MLBTR 2027 arbitration projections (Oct. 2, 2026), via Yardbarker/SI
    "days_2024_on_field": 142,                # .142 projected at his May 2024 debut (Bucs on Deck); credited 1.000
    "roy_2024_finish": 1,                     # NL Rookie of the Year 2024 (B-Ref; MLBTR: full year credited)
    "fwar": {2024: 4.3, 2025: 6.5, 2026: 4.2},  # FanGraphs player page, read 2026-10-12
    "bwar": {2024: 5.8, 2025: 8.0, 2026: 3.3},  # Baseball-Reference, read 2026-10-12
    "ip": {2024: 133.0, 2025: 187.2, 2026: 174.1},
    "era": {2024: 1.96, 2025: 1.97, 2026: 3.82},
    "fip": {2024: 2.44, 2025: 2.36, 2026: 3.33},
    "projection_2026_preseason_war": {"Steamer": 5.7, "ZiPS": 5.0, "ATC": 5.7, "THE BAT": 6.0,
                                      "OOPSY": 5.5, "Depth Charts": 5.4},  # FanGraphs, read 2026-10-12
    "mlbtr_2027_arb": 7.2,                    # MLBTR (Matt Swartz model), Oct. 2, 2026
    "awards": "2024 NL ROY; 2025 NL Cy Young; All-Star 2024-26",   # B-Ref
    "revenue_sharing_recipient": True,        # CBS Sports (Axisa), Nov. 5, 2025: Pirates received revenue sharing in 2025
    "ppi_pick": False,                        # MLBTR: no PPI pick (held down into May 2024)
}

# ------------------------------------------------------------------ comparables (pitchers)
PITCHER_COMPS = [
    # who, deal, years, total, note, source
    ("Garrett Crochet", "Red Sox extension, Apr. 2025", 6, 170.0,
     "covers 2026-31: final arbitration year + five free-agent years; $30M 2031 player option",
     "MLB.com / Sports Illustrated (case library)"),
    ("Corbin Burnes", "Diamondbacks free agent, Dec. 2024", 6, 210.0,
     "opt-out after 2026; 2021 NL Cy Young", "MLB.com, Dec. 31, 2024"),
    ("Max Fried", "Yankees free agent, Dec. 2024", 8, 218.0,
     "no opt-out, no deferrals, full no-trade", "MLB Trade Rumors, Dec. 2024"),
    ("Tarik Skubal", "Tigers arbitration award, Feb. 2026", 1, 32.0,
     "record arbitration salary after the 2024 and 2025 AL Cy Youngs; club filed $19M",
     "AP via WTOP, Feb. 2026"),
]

# ------------------------------------------------------------------ the next agreement (proposals)
# MLB, June 25, 2026 (MLB.com, Anthony Castrovince; AP, Ronald Blum): contracts starting 2027 with a new
# club capped at 5 free-agent years and a first-year salary of 15% of the cap (5% raises; $202M total);
# "Cornerstone" re-signings with the own club 6 years and 16%; limits count free-agent years projected at
# signing. 2027 cap $245.3M, floor $171.2M (May 28, 2026). Deferrals banned in new deals. QO eliminated.
MLB_PROPOSAL = {"cap_2027": 245.3, "floor_2027": 171.2, "new_club_share": 0.15, "own_club_share": 0.16,
                "raise": 0.05, "new_club_max_years": 5, "own_club_max_fa_years": 6}
