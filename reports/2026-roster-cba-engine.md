# The roster and CBA engine, and the Paul Skenes extension: a decision memo for the 2026-27 offseason

**Decision memo from public data.** It covers the rules of the 2022-26 Basic Agreement as code, a test of that code against the real 2025 luxury-tax bills, where the labor talks stand on October 12, 2026, and one live decision worked end to end: whether, and at what price, the Pirates should extend Paul Skenes before the agreement expires.
*Written 2026-10-12 · Dylan Fanelli · Sources: CBS Sports, AP, MLB.com, MLB Trade Rumors, FanGraphs, Baseball-Reference (each dated below) · Code: `baseball/roster/` (`uv run python -m baseball.roster.cases`) · Independent review: pending*

![Skenes extension price band under each rule set](figures/2026-skenes-extension-band.png)

## Summary
- **Recommendation: offer Skenes an eight-year extension (2027-34) before December 1, priced at a present value of about $214-226M. That's roughly $290-310M in nominal dollars and a CBT AAV of about $38M.**
  - **Illustrative structure:** a $25M signing bonus paid before December 1, then $8M, $18M and $27M for 2027-29 and $46M a year for 2030-34. That's $308M nominal and $215.8M in present value.
  - **Walk-away:** a present value of $254M (about $346M nominal at a level salary). Above that, the club expects to lose money against the alternative: going year to year through arbitration, then paying market.
  - **What the offer buys:** five free-agent years, ages 28-32. The club keeps $38M of expected surplus at the base projection. Skenes gets $18.5M more than his risk-adjusted floor and, if MLB's proposed contract limits pass, $27M more than his expected outcome.
- **Why before December 1:**
  - The agreement expires at 11:59 p.m. ET on December 1. MLB's October memo to clubs says a lockout ends all contact with 40-man players.
  - Whatever comes next changes the price. MLB's proposed 15%-of-cap limit on free-agent salaries would cut Skenes's risk-adjusted floor from $197M to $174M in present value. The union's plan would push it the other way.
  - A deal signed now is priced under known rules. Its signing bonus is the one piece of pay a work stoppage doesn't touch.
- **If he says no, nothing is lost: tender him and keep three years of control.**
  - **2027 salary:** MLB Trade Rumors projects $7.2M for his first arbitration year.
  - **Value of the control years:** surplus over 2027-29 is worth $106-163M in present value (low to high WAR case). An injury-stress case still leaves $78M.
  - **If he leaves after 2029:** under current rules the Pirates, a revenue-sharing recipient, would get a pick after the first round for a contract of $50M or more. Both sides have proposed eliminating the qualifying offer, which would remove that pick.
- **The tax engine reproduces the published 2025 bill to the dollar for eight of the nine clubs that paid.**
  - **The ninth (the Red Sox):** the published bill is exactly $75,000 below 20% of the published payroll overage. That means the bill was computed on a payroll $375,000 lower than the one published. It's reported here, not adjusted.
  - **A rule settled by the data:** the 2025 Phillies bill shows the 42.5%/45% surcharge depends on whether the club is a first-time or repeat payor, not on whether it was in that tier the year before.

## (a) Proof the tax engine is right
Grain: one club, 2025 season. CBT payroll and bill are to the dollar from CBS Sports (Mike Axisa, Dec. 20, 2025). Consecutive seasons over come from AP (Dec. 20, 2024 and Dec. 19, 2025). Threshold: $241M.

| Club | CBT payroll | Seasons over (incl. 2025) | Actual bill | Computed | Difference | Rate on the next $ |
|---|---|---|---|---|---|---|
| Dodgers | $417,341,608 | 5 | $169,375,768 | $169,375,769 | +$1 (rounding) | 110% |
| Mets | $346,670,456 | 4 | $91,637,501 | $91,637,502 | +$1 (rounding) | 110% |
| Yankees | $319,522,564 | 4 | $61,774,820 | $61,774,820 | $0 | 110% |
| Phillies | $314,329,912 | 4 | $56,062,903 | $56,062,903 | $0 | 110% |
| Blue Jays | $286,135,551 | 1 | $13,609,719 | $13,609,719 | $0 | 62.5% |
| Padres | $270,351,396 | 1 | $6,992,447 | $6,992,447 | $0 | 32% |
| Red Sox | $248,859,139 | 1 | $1,496,828 | $1,571,828 | **+$75,000** | 20% |
| Astros | $245,991,459 | 2 | $1,497,438 | $1,497,438 | $0 | 30% |
| Rangers | $241,380,966 | 3 | $190,483 | $190,483 | $0 | 50% |

**The rules the bills confirm** (MLB.com glossary, Competitive Balance Tax):
- **Base rate:** 20% / 30% / 50% for the first, second, and third-or-later consecutive season over the threshold.
- **Surcharges:** 12% on the part $20-40M over, 42.5% or 45% on $40-60M over, and 60% beyond $60M.
- **Pick penalty:** a club $40M or more over has its top pick dropped 10 places.

**Two things the data settled:**
- **The 42.5% vs 45% surcharge goes by payor status.**
  - **The ambiguity:** the glossary says "42.5% in the first year, 45% for each consecutive year after," which doesn't say first year of what.
  - **What the Phillies show:** they paid a $14.4M bill in 2024 (AP, Dec. 20, 2024) at the 50% and 62% marginal rates. That puts them $27.1M over the $237M line, below the $40M tier.
  - **The test:** in 2025 they were charged 95% (50% + 45%) on the $281-301M band. The bill reproduces at 45% and is $0.5M too low at 42.5%.
  - **Toronto, a first-time payor in 2025,** reproduces only at 42.5%.
- **Red Sox:** 20% × ($248,859,139 − $241,000,000) = $1,571,828, against a published $1,496,828.
  - **The gap:** exactly $75,000 of tax, so the bill used a payroll $375,000 lower than the published figure.
  - **Status:** no source explains it. Two readings fit: a late payroll adjustment, or a reporting difference. The test suite pins the gap so a future correction shows up.

**What a club does with this:**
- **The real price of salary:** a repeat payor $60M+ over pays $2.10 for every $1 of new salary.
- **Tier lines:** for 2026 they fall at $264M, $284M and $304M (threshold $244M plus $20M steps).
- **Using it:** `tax_cost_of_signing()` prices any addition against the club's line.

## (b) The labor clock
**Where it stands (verified 2026-10-12):**
- **Expiration:** the 2022-26 Basic Agreement expires **December 1, 2026 at 11:59 p.m. ET**.
- **The talks:** formal bargaining began May 12.
  - **MLB's position:** its core proposal (May 28) is a 2027 salary cap of $245.3M and a floor of $171.2M. Its economic, roster and schedule offers are tied to the union accepting a cap.
  - **Latest session, October 8:** MLB proposed:
    - a 154-game season and best-of-seven Division Series from 2029
    - higher seeds choosing their Wild Card opponents from 2027
  - **The union's response:** it is "reviewing" the proposals and restated its opposition to a cap (Yahoo Sports/Men's Journal, Oct. 8; CBS Sports timeline, updated Oct. 8).
- **Lockout preparation:** MLB sent clubs a memo on operating during a lockout (Yahoo Sports, Bleacher Nation, Oct. 8). Once owners lock out:
  - all baseball operations involving 40-man players stop: no contact, no free-agent negotiation, no trades
  - the major-league phase of the Rule 5 Draft is postponed at minimum
  - the draft lottery is probably postponed
- **No sign of a deal:** no reporting found a deal or deadline extension in sight. Every source read for this memo treats a December lockout as the base case.

**Before December 1, the old rules run the offseason.**
- **Option and qualifying-offer decisions:** a few days after the World Series.
- **The 40-man protection deadline and the non-tender deadline:** in 2025 these fell on November 18 and November 21. The 2026 dates weren't published when this was written.
  - **Expected date:** non-tender on Friday, November 20, 2026, following the 2023-25 pattern of the Friday before Thanksgiving. That date is not confirmed.
- **Then the freeze:** after December 1, a lockout would freeze the 40-man side of the market.
- **2022 precedent for arbitration:**
  - **Exchange:** figures were exchanged on March 22, after the lockout ended, instead of mid-January.
  - **Hearings:** held May 2 to June 24 (AP, May 2, 2022).

**Which outputs depend on rules under negotiation:**

| Engine output | 2022-26 rule | MLB proposal | MLBPA proposal | Effect on the Skenes decision |
|---|---|---|---|---|
| Free-agent price of his 2030-34 seasons | Open market | New-club deals capped at 15% of the cap in year 1 (+5%/yr, 5 years, about $202M); own-club "Cornerstone" deals 16%, 6 free-agent years (MLB.com, June 25) | No cap; a higher CBT threshold (reported at $300M, not re-checked) with no draft-pick penalties (May 27) | MLB plan: his risk-adjusted floor falls from $197.3M to $173.6M in present value and the midpoint from $225.6M to $213.7M. Union plan: more room for big-market bidders, pushing his outside option up (not quantified) |
| Qualifying-offer pick if he leaves | Recipient club, $50M+ deal: pick between Round 1 and Competitive Balance Round A | Eliminated | Eliminated | The consolation for losing him disappears under either plan, which raises the value of extending |
| Free-agency timing | Six years | Five years for players 30+ (tied to a cap) | Five years for players 30+ | None: he reaches six years after his age-27 season |
| Service time in a stoppage | Not covered | Not addressed | Not addressed | If 2027 loses more than 15 of its 187 days and lost days aren't credited, he finishes 2027 at 3.150 and becomes a free agent after **2030**, with a fourth arbitration year (engine: `timeline("3.000", 2026, [150, 172, 172, 172])`) |
| Deferred pay | Allowed, counted at present value | Banned in new deals; existing deals unaffected | — | A deal signed before Dec. 1 keeps the option |
| Contract limits on extensions | None | Limits count free-agent years projected at signing; AP reports service-time-scaled maximums between $265M/6 years (free-agent eligible) and $500M/12 years (pre-debut). The figure for a player at 3.000 is not published | None | **Unverified risk:** a $300M+ extension signed under a new agreement might hit a maximum; one signed now would not |
| Arbitration | Final-offer arbitration | Keep the system, open to a new framework (MLB.com, June 25) | Expanded eligibility (May 27; not re-checked) | His 2027-29 path is the assumption most exposed to a new framework |
| Minimum salary, options, Rule 5 | $780K; 5 optional assignments; Rule 5 after 4/5 seasons | $1M (2+ years, verified); 4 assignments and Rule 5 a year earlier (Aug. 27; not re-checked) | $1.5M (verified); 3 assignments (July 1; not re-checked) | None for Skenes. The engine takes each as an argument (`max_assignments`, `years_earlier`) for roster cases |

## (c) The decision: Paul Skenes

### Why this case
- **The stakes:** it's the largest pre-free-agency decision any club faces this winter. Skenes won the 2024 NL Rookie of the Year and the 2025 NL Cy Young, and was an All-Star in 2026.
- **The labor clock bites:** the extension window and the agreement's expiration overlap, and the next agreement moves his price in both directions.
- **It runs every part of the engine:**
  - a service-time credit from the Rookie of the Year award
  - a Super Two counterfactual
  - an arbitration projection
  - surplus value
  - extension pricing
  - qualifying-offer consequences
- **The tender question is trivial; the price isn't.** He'll be tendered at about $7.2M. What the Pirates should pay to own his ages 28-32 is the real question, and it has to be answered before a lockout freezes contact.

### Facts
| Item | Value | Source |
|---|---|---|
| Born | May 29, 2002 (age 25 in 2027) | Baseball-Reference |
| Service after 2026 | 3.000 | MLBTR 2027 arbitration projections (Oct. 2, 2026) |
| 2024 service | .142 on the field, credited 1.000 for finishing first in Rookie of the Year voting | Bucs on Deck (debut-day projection); MLBTR via SI (Nov. 19, 2024) |
| PPI draft pick | None: he was held down into May 2024 | MLBTR |
| fWAR 2024 / 2025 / 2026 | 4.3 / 6.5 / 4.2 | FanGraphs (read Oct. 12, 2026) |
| bWAR 2024 / 2025 / 2026 | 5.8 / 8.0 / 3.3 | Baseball-Reference (read Oct. 12, 2026) |
| 2026 line | 174.1 IP, 3.82 ERA, 3.33 FIP, 200 SO, 49 BB | Baseball-Reference, FanGraphs |
| 2026 preseason projections (WAR) | Steamer 5.7, ZiPS 5.0, ATC 5.7, THE BAT 6.0, OOPSY 5.5, Depth Charts 5.4 | FanGraphs |
| 2027 arbitration projection | $7.2M | MLBTR (Matt Swartz model), Oct. 2, 2026 |
| Pirates' status | Revenue-sharing recipient in 2025 | CBS Sports (Axisa), Nov. 5, 2025 |

### Service and control
- **The path:** 3.000 → arbitration in 2027, 2028 and 2029 → six years after 2029 → free agent after his age-27 season.
- **What the Rookie of the Year credit cost Pittsburgh: one year of control.**
  - **Without it:** he'd have finished 2026 at 2.142. That is above MLBTR's estimated 2027 Super Two line of 2.133 (not official).
  - **The result:** four arbitration years (2027-30) and free agency after **2030**.
- **Super Two cutoffs**, by the salary season they set (the engine's `SUPER_TWO_CUTOFFS`):

| 2022 | 2023 | 2024 | 2025 | 2026 | 2027 |
|---|---|---|---|---|---|
| 2.116 | 2.128 | 2.118 | 2.132 | 2.140 | 2.133 (MLBTR estimate) |

- **Sources:** UB Law Sports Forum (Nov. 2, 2022) for 2022-23, and AP (Nov. 7, 2025) for 2024-26.

### Projection (assumption, not a published projection)
- **No public 2027 projection existed on October 12.** Steamer and ZiPS release theirs later in the winter.
- **The base case:** a 5/4/3 weighting of his last three fWAR seasons, (5 × 4.2 + 4 × 6.5 + 3 × 4.3) / 12 = **4.99 WAR** for 2027.
  - **Cross-check:** that sits between his 2026 (4.2) and the 2026 preseason consensus (5.0-6.0).
- **Why fWAR:**
  - **The 2026 gap:** fWAR and bWAR disagree on 2026 (4.2 vs 3.3) because his ERA (3.82) ran half a run above his FIP (3.33).
  - **Consistency:** the FanGraphs $/WAR study prices contracts in projected fWAR, so the same scale is used here.
- **Scenarios:**
  - low ×0.8 (3.99 WAR)
  - high ×1.2 (5.99)
  - an illustrative injury stress ×0.6 (3.0), which stands in for a major arm injury
- **Aging (assumption):** flat through age 28, then −0.4 WAR a year, the FanGraphs study's decline.
  - **Base path:** 4.99 in 2027-30, then 4.59, 4.19, 3.79 and 3.39 in 2031-34.

### Arbitration path
- **The method:** year 1 is MLBTR's $7.2M. Years 2-3 use FanGraphs' July 2026 shares (35% and 50% of the platform season's WAR at free-agent prices), scaled down by 7.2 / 8.09.
  - **Why scale:** 8.09 is what the share rule gives for year 1 (15% × 4.2 × $12.84M), so scaling keeps MLBTR's level.

| Case | 2027 | 2028 | 2029 | PV 2027-29 (10%) |
|---|---|---|---|---|
| Low | $7.2M | $16.5M | $24.2M | $42.2M |
| Base | $7.2M | $20.6M | $30.3M | $50.9M |
| High | $7.2M | $24.7M | $36.3M | $59.6M |
| FanGraphs shares, no MLBTR anchor (base) | $8.1M | $23.1M | $34.0M | — |

- **The record as a check:** the largest arbitration salary on record is Tarik Skubal's $32M (Feb. 2026, after two Cy Youngs; the Tigers filed $19M). The base path's $30.3M third year sits just below it.
- **Where the rule overshoots:** the high case's $36.3M would break that record. The share rule is linear in WAR, and arbitration has historically paid less than linearly at the top, so read the high case as an upper bound.

### Surplus over the control years (no extension)
- **Value side:** WAR × free-agent $/WAR at the 2+ WAR tier ($12.84M in 2026, +3% a year; FanGraphs, Feb. 24, 2026).
- **Discounting:** 10% to the start of 2027 (FanGraphs' July 2026 method).

| Case | PV of value, 2027-29 | PV of arbitration pay | PV surplus |
|---|---|---|---|
| Stress (×0.6) | $111.4M | $33.4M | $78.0M |
| Low | $148.6M | $42.2M | $106.4M |
| Base | $185.7M | $50.9M | $134.8M |
| High | $222.9M | $59.6M | $163.2M |

### The extension price
**The model** (`extension_band()`):
- **Club ceiling:** the most the club can pay without expecting to lose against its alternative.
  - **The alternative:** arbitration salaries (base), then the free-agent value of the seasons it buys (base).
- **Player floor:** the least a risk-averse player should take.
  - **His alternative:** arbitration, then free agency, both in the low case.
  - **Assumption:** the low case stands in for his certainty equivalent.
- **Under MLB's plan:** his free-agent pay in each season is capped at the plan's maximum. That's 15% of a cap assumed to grow 3% a year (an assumption), giving $40.2M in 2030 and rising 5% a year. The club's value of the wins doesn't change.

| Rule set | Player floor (PV) | Midpoint (PV) | Club ceiling (PV) | Midpoint as a level 8-year salary |
|---|---|---|---|---|
| Current rules | $197.3M | $225.6M | $253.8M | $38.4M a year ($307M) |
| MLB's June 2026 plan | $173.6M | $213.7M | $253.8M | $36.4M a year ($291M) |
| Current rules, injury-stress floor | $131.5M | $192.7M | $253.8M | $32.8M a year ($263M) |
| FanGraphs arbitration shares, no MLBTR anchor | $202.5M | $231.3M | $260.1M | $39.4M a year ($315M) |

**The offer:** $25M signing bonus; $8M, $18M and $27M for 2027-29; $46M a year for 2030-34.
- **Totals:** $308M nominal, CBT AAV $38.5M, present value $215.8M.
- **Where it lands:** between the MLB-plan midpoint and the current-rules midpoint, so it splits the labor uncertainty instead of betting on either side's proposal.
- **For the club:** expected surplus of $38.0M at the base projection ($253.8M − $215.8M).
- **For the player:**
  - $18.5M above his current-rules floor
  - $42.2M above his floor under MLB's plan
  - $27.0M above his expected outcome under MLB's plan ($188.8M)
- **Why the signing bonus:**
  - **It survives a stoppage.** Salaries aren't paid for canceled games, but a signing bonus is paid (the Guerrero precedent, 2025). Canceling 60 games would cost him about $2.7M of a $7.2M arbitration salary (proportional approximation).
  - **It's worth more to him than it costs the club.** It turns the lockout from a risk on his side into a reason to sign now.
- **CBT:** the AAV counts from 2027, when the new deal begins (MLB.com glossary). The Pirates are far below the $244M line, so the tax doesn't bind.
  - **Under a cap:** $38.5M would be 15.7% of MLB's proposed $245.3M cap.

**Comparables (verified terms):**

| Player | Deal | Note |
|---|---|---|
| Garrett Crochet | Red Sox extension, Apr. 2025: 6 years, $170M (2026-31) | Final arbitration year + five free-agent years; $30M 2031 player option |
| Corbin Burnes | Diamondbacks, Dec. 2024: 6 years, $210M | Free agent; opt-out after 2026 (MLB.com, Dec. 31, 2024) |
| Max Fried | Yankees, Dec. 2024: 8 years, $218M | Free agent; no opt-out, no deferrals (MLBTR) |
| Tarik Skubal | Arbitration award, Feb. 2026: $32M | Record arbitration salary (AP) |

- **The offer would be the largest pitcher extension in this set, and the reason is age.** It buys free-agent years at 28-32, while Burnes and Fried were bought on the open market later in their careers.
- **The model's price depends on one assumption: that the market pays a 5-WAR pitcher reaching free agency at 28 at the linear 2+ WAR rate.**
  - **The check that works:** that rate does reproduce the market for the comparables above.
  - **The check that's missing:** no pitcher of his projection has reached the open market that young, so it can't be tested.

### What changes the answer
- **His arm.**
  - **The size of the risk:** the injury-stress row drops the midpoint by $33M. That's the case for adding an injury-contingent option conversion, as in Crochet's deal (a 120-day arm-injury clause turns his 2031 player option into a club option).
- **The Pirates' value of a win.** The ceiling prices wins at the free-agent rate. A club whose marginal revenue per win is lower should treat the ceiling as lower. Payroll capacity isn't modeled.
- **The next agreement.**
  - **Service time:** a 2027 stoppage with lost days not credited adds a fourth control year. That is worth more to the club than any of the proposals above.
  - **Extension limits:** a maximum on extensions under a new agreement could make waiting impossible, not just costly.
- **His agent and his preferences.** They aren't modeled. Nothing here is a claim about whether he would sign.

## Method
**Grain.** One player (service, valuation), one club-season (tax), or one transaction (qualifying offer).

**The engine.**
- **`service.py`:**
  - **Service time:** years.days with 172 days to the year and at most one year per season, so shorter stints carry over.
  - **Timing:** arbitration and free agency, Super Two against a given cutoff, the Rookie of the Year credit, and control years.
  - **Options:**
    - the 20-day option-year rule
    - fourth-option eligibility, from full seasons of 90 active days or 30+ active days topped up with IL days
    - the five-assignment limit, with spring options excluded
    - minimum days down
  - **Rule 5:** age measured on the June 5 before signing, the first qualified season, and eligibility at season + 4 for players 18 and under, + 3 for 19 and older.
  - **Rights:** outright refusal (3+ years or a prior outright; 5+ keeps salary) and 10-and-5.
- **`money.py`:**
  - **The CBT bill:** components, marginal rate and pick flag.
  - **Valuation:** tiered $/WAR with growth, aging, an arbitration path (FanGraphs shares, optionally anchored to an outside year-1 projection), surplus value, and extension bands with an optional market maximum.
  - **The qualifying offer:** compensation and forfeiture by club status, including a second signing.
- **`facts.py`:** every public number, with its source. **`cases.py`:** this memo's numbers and figure.

**Tests.** 36 in `tests/test_roster_service.py` and `tests/test_roster_money.py`.
- **Real bills:** eight 2025 bills to the dollar, plus the Red Sox gap pinned.
- **Rule edge cases:** the June 5 birthday, a season over 172 days, the fourth option, and spring options.
- **Valuation arithmetic:** checked by hand in the comments.
- **The Skenes numbers.**

Fictional players in tests are labeled fictional.

**Evidence standard.** A rule is used only if a cited source confirms it. Where the sources are secondary or incomplete, the code says so (see below).

## What this doesn't show
- **Unverified or partly verified rules:**
  - **Rookie of the Year credit:** confirmed through MLBTR and SI, not the CBA text. Its top-100-list condition is the caller's to check.
  - **Pool forfeiture on a second qualified signing:** MLB.com lists the picks but not the pool money.
  - **Outright salary rule (5+ years keeps salary, under 5 forfeits):** sourced to MLB Trade Rumors, not the CBA text.
  - **"Full season" with IL days** for the fourth option: from The Cub Reporter's reading of the rules.
  - **The 2026 non-tender date:** inferred from the pattern.
  - **Proposal details not re-checked on Oct. 12:** the union's $300M threshold, expanded arbitration and three optional assignments, and MLB's four assignments and earlier Rule 5. These come from the repo's CBA reference notes, which cite CBS Sports and MLBPA releases.
- **Valuation is a model.** The weights, the ×0.8 floor, the ×0.6 stress, 3% growth, the 10% discount and the 3% cap growth are all assumptions, labeled in code and changeable. None of them is a published projection.
- **MLB's plan is modeled only as a free-agent maximum.** Its effect on demand, the cap's actual growth and the maximum for a 3.000 extension are unknown. The union's plan isn't quantified.
- **No probabilities on the labor outcome.** The memo shows how the price moves under each plan instead of weighting them.
- **No team data.** Everything is public.

## Reproduce
```bash
uv run python -m baseball.roster.cases     # every number in this memo, and the figure
uv run pytest tests/test_roster_service.py tests/test_roster_money.py
```

## Sources
- **CBT bills (to the dollar):** Mike Axisa, "Dodgers rack up record-smashing $169 million luxury tax bill," CBS Sports, Dec. 20, 2025.
- **Payor history:** AP (Ronald Blum), Dec. 19, 2025 and Dec. 20, 2024.
- **CBT rules:** MLB.com glossary, Competitive Balance Tax (read Oct. 12, 2026).
- **Service time and Super Two:** MLB.com glossary, Service Time.
- **Super Two cutoffs:** AP, "Mason Miller, Zach Neto among 34 Super 2s" (Nov. 7, 2025); UB Law Sports Forum, "2023 Super Two Service Time Set" (Nov. 2, 2022).
- **Roster rules:** MLB.com glossary, Minor League Options; Rule 5 Draft; Outright Waivers; Qualifying Offer; 10-and-5 Rights. The Cub Reporter, MLB roster rules (Options; Rule 5 Draft). MLB Trade Rumors, "Mariners Outright Luis Urías" (June 2024).
- **Skenes:**
  - Baseball-Reference and FanGraphs player pages (read Oct. 12, 2026)
  - MLB Trade Rumors, "Projected Arbitration Salaries For 2027" (Darragh McDonald, Oct. 2, 2026), via Yardbarker and Pirates On SI (Oct. 3, 2026)
  - Brady Farkas, Fastball on SI (Nov. 19, 2024)
  - Bucs on Deck, "Examining Paul Skenes' Service Time"
- **Valuation:** FanGraphs, Ben Clemens, "What Are Teams Paying for a Win in Free Agency? 2026 Edition" (Feb. 24, 2026) and "The Details of Our New Prospect Valuation Methodology" (July 2, 2026).
- **Revenue-sharing status:** CBS Sports (Mike Axisa), qualifying-offer explainer, Nov. 5, 2025.
- **Labor talks:**
  - CBS Sports, "MLB CBA negotiations timeline" (updated Oct. 8, 2026)
  - Yahoo Sports (Ezra Lombardi / Men's Journal), "MLB Proposes Significant Changes in Latest Labor Bargaining Session" (Oct. 8, 2026)
  - Yahoo Sports (Chris Cwik) and Bleacher Nation (Brett Taylor) on MLB's lockout memo (Oct. 8, 2026)
  - MLB.com (Anthony Castrovince), "MLB's latest CBA proposal includes minimum salary increase, free agency revisions" (June 25, 2026)
  - AP (Ronald Blum), June 25, 2026
  - AP, "Frazier, Mariners argue 1st of delayed arbitration cases" (May 2, 2022)
- **Comparables:**
  - Skubal: AP via WTOP, Feb. 2026
  - Burnes: MLB.com, Dec. 31, 2024
  - Fried: MLB Trade Rumors, Dec. 2024
  - Crochet: MLB.com and Sports Illustrated (via this repo's CBA reference library)
- **Dates for 2025-26:** Detroit Tigers On SI, offseason calendar.
