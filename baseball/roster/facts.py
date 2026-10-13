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
    "born": "2002-05-29",                     # Baseball-Reference, read 2026-10-12
    # MLBTR, "Projected Arbitration Salaries For 2027" (Darragh McDonald, Oct. 2, 2026): "Paul Skenes (3.000):
    # $7.2MM". Read through Yardbarker's authorized syndication of the full article (Oct. 2, 2026);
    # mlbtraderumors.com blocks automated reading.
    "service_after_2026": "3.000",
    "mlbtr_2027_arb": 7.2,
    # .142 on the field in 2024 (Bucs on Deck, written before his May 2024 debut, undated); credited 1.000.
    # Rule: a player with under 60 days of prior service, on 2 of 3 preseason top-100 lists, who finishes top
    # two in ROY voting gets a full year (UB Law Sports Forum, Mike Perlo, Nov. 17, 2022); applied to Skenes
    # by MLBTR (via SI, Brady Farkas, Nov. 19, 2024).
    "days_2024_on_field": 142,
    "roy_2024_finish": 1,                     # 2024 NL Rookie of the Year (Baseball-Reference)
    "fwar": {2024: 4.3, 2025: 6.5, 2026: 4.2},  # FanGraphs player page, read 2026-10-12
    "bwar": {2024: 5.8, 2025: 8.0, 2026: 3.3},  # Baseball-Reference, read 2026-10-12
    "ip": {2024: 133.0, 2025: 187.2, 2026: 174.1},      # Baseball-Reference, read 2026-10-12
    "era": {2024: 1.96, 2025: 1.97, 2026: 3.82},        # Baseball-Reference, read 2026-10-12
    "fip": {2024: 2.44, 2025: 2.36, 2026: 3.33},        # FanGraphs, read 2026-10-12
    "projection_2026_preseason_war": {"Steamer": 5.7, "ZiPS": 5.0, "ATC": 5.7, "THE BAT": 6.0,
                                      "OOPSY": 5.5, "Depth Charts": 5.4},  # FanGraphs, read 2026-10-12
    "awards": "2024 NL ROY; 2025 NL Cy Young; All-Star 2024-26",   # Baseball-Reference
    "revenue_sharing_recipient_2025": True,   # CBS Sports (Mike Axisa), Nov. 5, 2025. QO compensation turns on
                                              # the club's status when he leaves (2029), which isn't known.
    "ppi_pick": False,                        # MLBTR (via SI, Nov. 19, 2024): held down into May 2024, no PPI pick
}
PIRATES_2026_CBT_PAYROLL = 120.720416     # Spotrac, Pirates 2026 financial summary, read 2026-10-13

# ------------------------------------------------------------------ comparables (pitchers)
PITCHER_COMPS = [
    # who, deal, years, total, note, source
    ("Garrett Crochet", "Red Sox extension, Apr. 1, 2025", 6, 170.0,
     "2026-31: $4M bonus, $24M 2026, $28M 2027-30, $30M 2031; opt-out after 2030. 120 straight days on the IL "
     "with a left-arm injury voids the opt-out and adds a $15M 2032 club option, which was triggered on "
     "Aug. 23, 2026 (shoulder inflammation)",
     "CBS Sports (Dayn Perry), Apr. 1, 2025; MLB.com (Theo DeRosa), Aug. 23, 2026"),
    ("Corbin Burnes", "Diamondbacks free agent, Dec. 2024", 6, 210.0,
     "opt-out after 2026; age 30; 2021 NL Cy Young", "MLB.com, Dec. 28 and Dec. 31, 2024"),
    ("Max Fried", "Yankees free agent, Dec. 2024", 8, 218.0,
     "no opt-out, no deferrals, full no-trade", "MLB Trade Rumors, Dec. 2024 (day not shown on the page read)"),
    ("Yoshinobu Yamamoto", "Dodgers free agent, Dec. 21, 2023", 12, 325.0,
     "age 25; plus a $50.6M posting fee to Orix", "Dodgers Digest (Chad Moriyama), Dec. 21, 2023"),
    ("Gerrit Cole", "Yankees free agent, Dec. 2019", 9, 324.0,
     "age 29; then the record total for a pitcher", "MLB.com (Andrew Simon), Dec. 18, 2019"),
    ("Tarik Skubal", "Tigers arbitration award, Feb. 5, 2026", 1, 32.0,
     "record arbitration salary after the 2024 and 2025 AL Cy Youngs; club filed $19M",
     "AP via WTOP, Feb. 2026 (ruling the day after the hearing; dated Feb. 5 in AP syndication URLs)"),
]
RECORD_PITCHER_AAV = (43.333, "Max Scherzer, Mets, 3 years $130M, Nov. 29, 2021 (Globe and Mail/AP: a record "
                      "average salary at signing). No pitcher contract found above it as of 2026-10-13.")

# Contracts priced with a sourced projection, for comps_check(). dpw_row: FanGraphs $/WAR row of that offseason.
MARKET_COMPS = [
    {"name": "Yoshinobu Yamamoto", "deal": "Dodgers, Dec. 2023", "age": 25, "years": 12, "total": 325.0,
     "dpw_row": 2024, "war1": 3.1,
     "projection_note": "FanGraphs projection at signing, 3.1 WAR in 166 IP (via Dodgers Digest, Dec. 21, 2023)"},
    {"name": "Gerrit Cole", "deal": "Yankees, Dec. 2019", "age": 29, "years": 9, "total": 324.0, "dpw_row": 2020,
     "war_path": [6.5, 5.9, 5.3, 4.6, 4.0, 3.5, 3.0, 2.5, 2.0],
     "projection_note": "Oliver projection with Tango WAR, 37.4 over 9 years as published, 37.3 summed by year (MLB.com, Dec. 18, 2019); "
                        "a different WAR scale from fWAR"},
    {"name": "Corbin Burnes", "deal": "Diamondbacks, Dec. 2024", "age": 30, "years": 6, "total": 210.0,
     "dpw_row": 2025, "war1": None},
    {"name": "Max Fried", "deal": "Yankees, Dec. 2024", "age": None, "years": 8, "total": 218.0,
     "dpw_row": 2025, "war1": None},
]

# ------------------------------------------------------------------ the next agreement (proposals)
# MLB, June 25, 2026 (MLB.com, Anthony Castrovince; AP, Ronald Blum): contracts starting 2027 with a new
# club capped at 5 free-agent years and a first-year salary of 15% of the cap (5% raises; $202M total);
# "Cornerstone" re-signings with the own club 6 years and 16%; limits count free-agent years projected at
# signing. 2027 cap $245.3M, floor $171.2M (May 28, 2026). Deferrals banned in new deals. QO eliminated.
# MLB.com and AP both say "15% of the cap" (negotiations notes said "of payroll"). The reported $202M total is
# MLB's figure; 15% x $245.3M = $36.8M with 5% raises over 5 years is $203.3M by this arithmetic.
MLB_PROPOSAL = {"cap_2027": 245.3, "floor_2027": 171.2, "new_club_share": 0.15, "own_club_share": 0.16,
                "raise": 0.05, "new_club_max_years": 5, "own_club_max_fa_years": 6}
