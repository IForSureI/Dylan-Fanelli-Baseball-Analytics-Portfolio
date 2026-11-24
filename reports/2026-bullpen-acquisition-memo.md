<!-- portfolio:header -->
<sub>[← Portfolio](../README.md) &nbsp;|&nbsp; [Pitch familiarity →](2026-league-pitch-familiarity.md)</sub>
<!-- /portfolio:header -->

# Bullpen acquisition memo, 2026-27 offseason: three relievers for the Texas Rangers

<!-- portfolio:glance -->
<p><img src="https://img.shields.io/badge/status-reviewed-1d5c3f" alt="status: reviewed"> <img src="https://img.shields.io/badge/data-public-1f1f1f" alt="data: public"> <img src="https://img.shields.io/badge/for-GM%20and%20pro%20personnel-6b6b6b" alt="for: GM and pro personnel"> <img src="https://img.shields.io/badge/method-decision%20memo-b4532a" alt="method: decision memo"> <img src="https://img.shields.io/badge/method-contract%20pricing-b4532a" alt="method: contract pricing"> <img src="https://img.shields.io/badge/method-20--80%20scouting-b4532a" alt="method: 20-80 scouting"></p>

**At a glance**

- **The question:** Which reliever should the Rangers sign this winter, and at what price?
- **The answer:** Adrián Morejón, at no more than 4 years, \$60M now that he has a qualifying offer (Nov. 2). He declined it on Nov. 17 and is a free agent. That lands him about one time in four, so Bryan Abreu, who costs no pick, is the likely signing.
- **For a club:** One real offseason decision made the way a front office makes it: the target, the opening offer, the walk-away and the plan if he goes elsewhere. The [one-page version](2026-bullpen-one-page.md) is what a GM reads.
<!-- /portfolio:glance -->

**Decision memo from public data.** One real offseason decision, made the way a front office makes it: the club's need, three relievers it could sign this winter, a data-informed scouting report on each, what each costs and is worth under the 2022-26 agreement and its December 1 expiration, and a ranked recommendation with a price.
- **The scouting reports are data-informed, not a live look.** Grades come from Statcast shape and results. Health appears only as public injured-list and surgery reporting, cited, with no inference.

*Written 2026-10-13; Dylan Fanelli; Data: Statcast via Baseball Savant (regular seasons 2024-26); Outside facts: dated public reporting, listed under Sources; Code: `baseball/evaluation/reliever.py`, `baseball/roster/acquisition.py`, `baseball/roster/bullpen_case.py`; Reviewed in a separate pass 2026-10-13; findings addressed*

![Pitch grades, the reliever market's price per projected win, and fastball velocity by month](figures/2026-bullpen-acquisition-memo.png)

*Figure note (Nov. 23): the figure is redrawn from the saved Oct. 17 run, so every marker matches the tables below.*

## Decision summary

**Update, Nov. 18, 2026: Morejón declined the qualifying offer.**
- **The facts:** he turned down the Padres' one-year, $23.15M qualifying offer on Nov. 17 and is a free agent (MLB.com, AJ Cassavell, Nov. 17, 2026; NBC Sports, Nov. 17, 2026). The Padres get a pick after the fourth round of the 2027 draft if he signs elsewhere (MLB.com, Nov. 17, 2026).
- **What it does to the bid:** nothing new. The Nov. 14 numbers below already assumed he'd have the offer attached: four years, $60M, and no higher. The "if he accepts" branch is off; the bid is live until the agreement expires Dec. 1.

**Update, Nov. 14, 2026: Morejón has a qualifying offer, so the walk-away is $60M.**
- **The facts:** the Padres made Morejón a $23.15M qualifying offer on Nov. 2, one of eight in the league (AP, Nov. 2, 2026). He has until 4 p.m. ET on Nov. 17 to accept (CBS Sports, Nov. 2, 2026). No decision was reported as of Nov. 14.
- **What it does to the bid:** this memo's own rule applies. Signing him now costs the Rangers their second-highest pick and $0.5M of pool, worth about $10.6M. **The walk-away is four years, $60M, the same number as the opening offer.** At $60M the market line lands him about 26% of the time, down from 47% at $72M.
- **If he accepts the offer:** he stays in San Diego for 2027 and this bid is off. Go to Abreu.
- **Abreu has no qualifying offer.** He is not among the eight, so he costs no pick. His prices are unchanged: open at two years, $18M, walk away above $25M. With Morejón at about one chance in four, Abreu is now the likely outcome.
- **Bednar did get one** (Yankees). He stays set aside.
- **A second check added today, on availability:** relievers who threw 800 or more relief pitches in 2024 kept 63% of that workload in 2025 and 48% in 2026 (170 pitchers, this portfolio's relief-season table). The contract values below assume four full seasons. Section 4 now prices that: on the workload relievers kept, four years of Morejón are worth about $45M at the market line, not $63M.
- **What didn't change:** the scouting reports, the projections and the market line. Everything dated Oct. 13 or Oct. 18 below is left as written and marked where the Nov. 2 facts overtake it.

**Update, Nov. 23, 2026: a second forecast of his market.** My [market board](2027-market-board.md) forecasts Morejón's average salary at $24.8M a year (MLBTR: $16.0M), with about a 95% chance the market pays him more than $15M a year. If that's right, the $60M walk-away lands him about 5% of the time, not 26%. The same model puts Abreu at $15.4M a year, so my walk-away for him (above $25M over two years) would land him about 24% of the time. Both targets would price out, and the plan would be a higher walk-away or Raisel Iglesias on one year (the board has him at $15.8M, below MLBTR's $17.0M). I keep this memo's numbers: its market line is fit on the 21 relief signings of 2025-26, while the board's reliever term rests on 14 relievers in one winter and its edge over MLBTR rests on one hitter. The walk-away, the grades and the ranking don't change. If an early reliever signing clears $20M a year, I'll treat that as evidence for the board's view.

**Update, Oct. 18, 2026: the qualifying-offer case.** The first version priced the pick a QO would cost the Rangers (a second-rounder near No. 55) at $5.3M, a 2019 public estimate. My own draft-pick backtest (the values are in `baseball/roster/acquisition.py`, `PICK_VALUE_OWN`) puts that pick at about $10.1M after its 2026 slot, from what picks 45-60 returned in the 2000-2016 drafts. On that value the pick and pool cost $10.6M in present value, and **the walk-away with a QO falls from about $66M to about $60M, the opening offer**: if the Padres attach a QO, open at $60M and don't go higher. The 2027 QO is $23.15M (reported Oct. 8, 2026). Everything else below is unchanged; the QO figures are updated in place and marked.

**Compiled:** 2026-10-13; revised 2026-11-14 for the qualifying offer and 2026-11-18 for his decision (declined Nov. 17); **On:** Bid on Adrián Morejón up to $60M; expect Abreu about three times in four

**Recommendation.**
- **Bid on Adrián Morejón, up to four years, $60M** with a 2031 club option. He has a qualifying offer (Nov. 2), so $60M is both the opening offer and the walk-away.
  - **Without the offer** the walk-away was four years, $72M ($18M a year). That is the market's expected price for his projection, not a surplus value: at $72M the contract's surplus is about zero by construction.
  - **The odds:** at $60M, we land him about 26% of the time (47% at $72M). Paying more is a call on what 2027 wins are worth to this club.
- **If he goes elsewhere, sign Bryan Abreu.** Open at two years, $18M, and walk away above $25M.
- **Pete Fairbanks is not the 2027 answer.** He is having thoracic outlet surgery with a typical recovery of nine to ten months (MLB.com, Sept. 19, 2026). The memo assumes he pitches about a third of 2027.

**Why.**
1. **The need is late-inning run prevention, and most of the late innings are leaving.**
   - **The fall:** Texas relievers dropped from 4th in run value per 100 pitches in 2025 to 24th in 2026 (+0.42 to −0.26). In late, close spots (7th inning on, within three runs) they fell from 6th to 26th (Statcast, regular seasons; 1 = best).
   - **Who's leaving:** Jakob Junis (mutual option) and Tyler Alexander (free agent) threw 309 of the 1,140 late, close plate appearances (27%; MLB.com free-agent list, Oct. 8, 2026). Chris Martin and Jalen Beeks, also free agents, bring it to 400 (35%).
   - **Win probability added says less.** It moved the other way (23rd → 17th) because it depends on when runs scored.
   - **The skill measures fell less than the results (added Nov. 14).** Strikeouts minus walks went from 14th to 23rd (13.9% to 11.4%) and xwOBA from 16th to 22nd (.311 to .316). The drop from 4th to 24th is in run value. So this was an average bullpen that got good results in 2025 and a below-average one in 2026. The need is real, and smaller than "4th to 24th" reads.
2. **Morejón projects for the most 2027 wins of any free-agent reliever.**
   - **The projection:** about 2.3 wins in a closer/high-leverage role. That's derived from his run value only, so the interval understates the uncertainty (95% range on the rate alone: 1.3–3.2).
   - **Against the others:** Abreu projects 1.5 in a setup role, or 1.6 in the same job. Fairbanks projects 0.24 for the part of 2027 he's expected to pitch.
   - **His record:** above-average relief run value three straight years (+0.33, +2.11 and +1.39 runs per 100 pitches), 211 games, no injured-list placement in 2024-26 (MiLB.com transactions, read Oct. 13, 2026), and a 58% ground-ball rate in 2026.
3. **His price is uncertain, and $72M is about the middle of the plausible range.**
   - **The market line:** a line fit on the 21 relief signings of 2025-26 puts his expected price at $18.4M a year.
   - **How wide that band is:** a 95% prediction interval runs from $7.4M to $29.3M. His projection is also above every comparable signing's, so that price is an extrapolation.
   - **Our value is close to the expected price:** $18.1M a year on our three-season projection.
   - **Two public guesses:** a rival executive's four years and $60M (FanSided, Sept. 9). Dennis Lin of The Athletic said Morejón "could attract nine-figure offers," which I read secondhand through Padres On SI (Oct. 10).

**Alternatives.**
- **Abreu (2nd):** the best 2027 whiff projection of the three (33.1%), on half the commitment.
  - **The second half of 2026:** his fastball returned from 95.0 to 96.4 mph, and his walk rate fell from 19.7% to 11.3%. The walk-rate drop is borderline (p = 0.058).
- **Raisel Iglesias:** a one-year alternative, about as many 2027 wins as Abreu (1.67 after one year's aging), at 37.
- **Fairbanks (3rd):** at most a two-year rehab contract, about $3M a year.

**Risk.** Morejón's 2026 rested on two new things.
- **A velocity gain:** +1.8 mph on the sinker, net of the league. In the levers study, pitchers mostly kept velocity gains a year later, but the whiff gains from them were not shown to last.
- **A changeup:** it went from 7% to 23% of his pitches and got whiffs 13 points above its physics. The edge engine expects about half of such a gap to carry over.
- **Health:** he had Tommy John surgery in 2021 and a 60-day elbow sprain in 2023 (MLB.com, Apr. 21, 2021; CBS Sports, Mar. 30, 2023).

**What would change the recommendation.**
- **His price above $60M (he has the QO; $72M was the number without it), a fifth guaranteed year, or an opt-out:** switch to Abreu.
- **He accepts the qualifying offer by Nov. 17:** he is off the market. Sign Abreu. *(Did not happen: he declined on Nov. 17.)*
- **A relief budget under about $15M a year:** Abreu, or Iglesias on one year.
- **A club decision that 2027 wins near the wild-card line are worth more than the market rate:** raise the walk-away. At $80M we'd land him about 62% of the time, at a market-rate cost of about $6.6M in present value.
- **A club medical review of any of them** (not public, not in this memo).

**Ask.** Approve the offer and the walk-away now that he has declined the qualifying offer (Nov. 17). Before that, the ask was ahead of his Nov. 17 decision (the first version asked for approval by the qualifying-offer deadline, which passed Nov. 2). Sign before the agreement expires December 1 at 11:59 p.m. ET. A lockout is expected to start Dec. 2 (MLB Trade Rumors, Nov. 12, 2026).
- **Why that date:** MLB's lockout memo ends free-agent negotiations and trades: "No free agent negotiations. No trades." (Bleacher Nation's summary of the memo, Brett Taylor, Oct. 8, 2026).
- **Last winter's timing doesn't help:** the top relievers signed December 9-11 (Díaz: AP, Dec. 9, 2025; Suarez: amNY, Dec. 11, 2025), and a lockout would take that window away.

## The three, side by side

| Rank (tier) | Player | B/T, 2027 age, 2026 club | OFP | Present role (2026) | 2027 role | Risk | Best pitch (present / 2027 grade) | Cost | Projected 2027 wins in his role |
|---|---|---|---|---|---|---|---|---|---|
| 1 (A) | Adrián Morejón | L/L, 28, Padres | 60 | B1 (42.1 save-situation IP; Padres On SI, Oct. 10) | B1 | Moderate | Changeup / four-seamer (75 / 75) | Free agent. Expected market price $18.4M a year (95% band $7.4–29.3M). Has a qualifying offer (Nov. 2); the Padres pay the tax | 2.3 (B1; rate-only 95% range 1.3–3.2) |
| 2 (B) | Bryan Abreu | R/R, 30, Astros | 50 | B2 setup (15% walks) | B2; B1 if his walk rate stays at or below about 11% | Moderate to high | Slider and four-seamer (60 / 65) | Free agent. Expected price $12.2M ($3.1–21.3M). No public projection found. No qualifying offer (not among the eight, Nov. 2), so no pick cost | 1.5 (B2); 1.6 in the B1 job |
| 3 (C) | Pete Fairbanks | R/R, 33, Marlins | 50 | B2 when active | Out about 9-10 months after surgery; B2 when back | High (health) | Cutter (65 / 75; 86 swings) | Free agent. 2026 deal 1 year, $13M. Rehab-deal value about $4.5M a year over two years | 0.24 in 2027 (about a third of a season) |

- **Roles:** a reliever role scale (B1 closer or high leverage, OFP band 55-60; B2 setup, OFP 50).
- **OFP:** my reliever formula, min(60, 0.55 × best pitch + 0.35 × second + 0.10 × control), overridden where stated.
- **Control:** graded from unintentional walk rate, as a stand-in for command, which the formula asks for and public data can't measure.

**Preference list and statements.**
- **Tier A, Morejón:** an impact late-inning arm.
- **Tier B, Abreu (and Iglesias on a one-year deal):** an average-or-better late-inning arm with one open question.
- **Tier C, Fairbanks:** a speculative rehab signing.
- **I prefer Morejón to Abreu for the late-inning job next to Jacob Latz.** He projects for more wins (2.3 vs 1.6 at the same leverage) and has the higher floor (1.3 vs 0.7 at the low end of the rate interval, same leverage). Abreu's bat-missing is intact; his walks are the question.
  - **Morejón moves below Abreu** if his price passes $72M for four years.
  - **If the objective is the most wins per dollar** with no commitment past 2028, Abreu at $25M or less.
- **I prefer Abreu to Fairbanks** because Fairbanks will miss most of 2027 after surgery, and even healthy he projects for fewer wins (0.93 vs 1.64 at the same leverage).
  - **Fairbanks moves above Abreu** only if the club's own medical review expects him back by Opening Day, and that isn't the public timeline.

## Where the tools disagree, and how I weighed them

**Two "regressed run value" numbers appear in this memo, and they measure different things.**
- **The scouting reports** use the Reliability Atlas's `regress()` on 2026 alone: Morejón +0.56, Abreu +0.09, Fairbanks −0.16 runs per 100 pitches. That is his 2026 true level.
- **The projection** pools 2024-26 relief pitches, weighted 5/4/3, and regresses with the same Atlas constant: Morejón +0.83, Abreu +0.37, Fairbanks +0.18. That is the 2027 rate used for wins and value.

| Question | Tool A says | Tool B says | Weighed |
|---|---|---|---|
| Who misses the most bats next year? | **Edge engine** (validated two-season whiff projection, blends results and stuff): Abreu 33.1%, Morejón 31.0%, Fairbanks 29.8% | **The projection** (2024-26 relief run value, regressed; counts walks, contact and grounders): Morejón +0.83, Abreu +0.37, Fairbanks +0.18 | Both are right about different things. Abreu's gap is walks, which a whiff model can't see. Morejón's edge includes a 55% regressed ground-ball rate (Atlas year-to-year persistence 0.92). I rank on run value and use the whiff projection to establish that Abreu's swing-and-miss survived 2026 |
| What is Morejón worth? | **Roster engine** ($/WAR tiers): about $30.7M a year | **Reliever market line:** his value is $18.1M; his expected price is $18.4M | They are on different win scales. This memo's wins use a fringe-arm replacement level that isn't calibrated to fWAR, and FanGraphs' $/WAR is set in fWAR (and excludes relievers). The engine column is an order of magnitude, not a price. I price only with the market line, which uses the same projection on both sides |
| Did Fairbanks's slider get better? | **Levers study:** every confirmed slider lever he moved (drop +3.1 in, speed gap +1.5 mph, slot −1.6°) implies about +2.9 whiff points | **The stuff model** (levers version, fixed hand mix): expected whiff on the slider fell 5.9 points | The levers study's own result is that the single expected-whiff change predicts better than lever lists (pooled +7.5 points of squared error). Its slider-drop and speed-gap gains are also "not shown to last." His slider whiff jump (30.8% → 40.5%, 79 swings) is treated as mostly noise. Usage fell from 40% to 26%, which by itself lowers hitters' familiarity |
| Is Morejón's slider a weakness? | **Stuff grade:** 70 (expected whiff 41%, 97th percentile; ten refits gave 70 to 75 and 41.6% to 44.4%) | **Present grade:** 45 (30% whiffs, 73 tracked swings) | Slider whiff reaches r = 0.5 at about 41 swings (Atlas), so the regressed rate already carries most of the weight, and it's a tick below average. Graded 45 now and 50 for 2027 (the engine's projection). A possible lever, not a flaw |
| Abreu's cutter (new in 2026) | **Stuff:** 40 (ten refits gave 35 to 40) | **Present:** 65 (36% whiffs, 61 swings) | Results beating stuff carries over between seasons (edge engine, r ≈ 0.55), but 61 swings in one season isn't a pattern. It's 11% of his mix and doesn't drive the grade |

## 1. The need: why the Rangers, why a reliever

**The club.**
- **2026 finish:** 80-82, 4.0 games behind the third AL wild card (White Sox, 84-78; MLB.com standings, last updated Oct. 7, 2026).
- **In July** they were a half-game out of the AL West lead, and the bullpen was already called the problem: "Texas cannot realistically expect to contend throughout the remainder of the season with its current bullpen construction" (Eduardo Solano, Roundtable Sports, July 21, 2026).

**The bullpen, 2025 vs. 2026.**
- **Grain:** relief pitches and plate appearances, regular season. Relief is any pitcher after his team's first; position players pitching count as relief, a negligible share.
- **Ranks:** 1 = best of 30.

| Season | Relief PA | K-BB% (rank) | xwOBA (rank) | Run value /100 pitches (rank) | Late, close run value /100 (rank) | Win probability added (rank) |
|---|---|---|---|---|---|---|
| 2025 | 2,426 | 13.9 (14) | .311 (16) | +0.42 (4) | +0.63 (6) | +1.9 (23) |
| 2026 | 2,641 | 11.4 (23) | .316 (22) | −0.26 (24) | −0.27 (26) | +2.2 (17) |

**Who threw the late, close innings in 2026,** and who is leaving (status: MLB.com free-agent list, Oct. 8, 2026):

| Pitcher | Throws | Late, close PA (of 1,140) | K-BB% | Run value /100 | 2027 status |
|---|---|---|---|---|---|
| Jacob Latz | L | 221 | 22.6 | +1.81 | Arbitration, projected $3.05M (Just Baseball, Oct. 7) |
| Jakob Junis | R | 164 | 8.0 | +0.94 | Mutual option |
| Tyler Alexander | L | 145 | 11.3 | +0.20 | Free agent |
| Peyton Gray | R | 113 | 17.3 | −0.37 | Under control |
| Cole Winn | R | 102 | 15.6 | −0.80 | Under control |
| Robby Ahlstrom | L | 67 | 11.6 | −0.66 | Under control |

- **The job:** a high-leverage arm for the seventh and eighth innings beside Latz.
- **A platoon need is not established.**
  - **The gap against right-handers:** Texas relievers allowed a .318 xwOBA (1,419 PA) against .306 for the league's relievers. The difference, .012 (SE .010), is not significant (p = 0.25).
  - **Against left-handers:** .315 vs .314.
  - **Within the club:** its own right-left split is .318 vs .315. So the memo doesn't screen for handedness.

**Money and the luxury tax.**

| Item | Value | Source |
|---|---|---|
| 2025 CBT payroll | $241.4M, third straight season over | CBS Sports, Dec. 20, 2025; AP |
| 2026 CBT payroll | $206.0M (Spotrac page, no as-of date); $210M (Spotrac via SI, Oct. 2) | Spotrac, read Oct. 13, 2026; Matt Postins, Texas Rangers On SI, Oct. 2, 2026 |
| 2027 committed (tax) | $142.1M to eight players, including mutual options for Pederson, Higashioka and Junis | Postins (SI), Oct. 2, 2026 |
| 2027 arbitration class | $38.2M for ten players (Gore $8.9M ... Latz $3.05M) | Zach Cioffi, Just Baseball, Oct. 7, 2026 (his own comparables) |
| 2027 payroll before additions | about $191M (derived: the two lines above, plus 14 roster spots at the 2026 minimum of $0.78M) | This memo |
| QO status for signing | "Other": a qualified signing costs the 2nd-highest 2027 pick and $500K of international pool | MLB Trade Rumors, Oct. 12, 2026 |

- **What the $191M leaves out:** player benefits, which count toward the CBT payroll, and 40-man minor-league salaries. Neither is estimated here.
  - **The conclusion survives a generous allowance:** $191M + $20M + an $18M signing = $229M, still under a $244M line.
- **The reset:** being under in 2026 resets the tax clock. If a 2027 threshold exists and they cross it, they pay first-time rates: 20% on the overage instead of 50% (`cbt_bill`).
- **The budget:** Chris Young will know his budget before free agency opens, and Ray Davis's approval decides how active he can be (Postins, SI, Oct. 2). The rotation competes for the same dollars.

## 2. The pool and why these three

**The rule.** Every reliever on MLB.com's free-agent list (Oct. 8, 2026) with no club, player or mutual option or opt-out pending, and 150+ plate appearances in 2026.
- **The count:** 38 qualify.
- **The ranking:** projected wins in the B1 role, the same leverage for everyone, so the column ranks talent.
- **The table shows** the top 12 plus Fairbanks.

| Rank of 38 | Reliever | 2027 age | 2026 G | K-BB% | Run value /100 (2026) | Projection rate (2024-26) | Projected wins, B1 role | 2027 whiff% (engine) |
|---|---|---|---|---|---|---|---|---|
| 1 | **Adrián Morejón** | 28 | 76 | 22.4 | +1.39 | +0.83 | **2.28** | 31.0 |
| 2 | Alex Vesia | 31 | 72 | 17.7 | +1.22 | +0.72 | 1.91 | 30.0 |
| 3 | Raisel Iglesias | 37 | 59 | 19.7 | +1.21 | +0.83 | 1.86 | 27.4 |
| 4 | David Bednar | 32 | 64 | 20.0 | +1.23 | +0.51 | 1.70 | 28.9 |
| 5 | **Bryan Abreu** | 30 | 66 | 14.6 | +0.27 | +0.37 | **1.64** | **33.1** |
| 6 | Steven Okert | 35 | 68 | 20.7 | +1.25 | +0.67 | 1.64 | 30.3 |
| 7 | Taylor Clarke | 33 | 71 | 10.8 | +0.86 | +0.53 | 1.53 | 22.6 |
| 8 | Dennis Santana | 31 | 57 | 9.6 | −0.65 | +0.35 | 1.36 | 25.0 |
| 9 | Paul Blackburn | 33 | 62 | 10.7 | +1.35 | +0.52 | 1.31 | 21.7 |
| 10 | Sean Newcomb | 34 | 60 | 13.4 | +0.80 | +0.35 | 1.30 | 23.3 |
| 11 | JoJo Romero | 30 | 55 | 15.1 | +0.14 | +0.31 | 1.24 | 21.0 |
| 12 | Tyler Kinley | 36 | 64 | 9.5 | +0.17 | +0.17 | 1.23 | 29.5 |
| 25 | **Pete Fairbanks** | 33 | 46 | 19.7 | −0.54 | +0.18 | 0.93 (healthy) | 29.8 |

**Why these three.** They make the comparison hard in three different ways.
- **Morejón** is the best and youngest arm in the pool, at the highest price.
- **Abreu** is a buy-low whose bat-missing is intact and whose problem has a measured, partly reversed cause. He ranks 5th.
- **Fairbanks** was chosen as a case type, not on projection (25th of 38): a cheap arm whose stuff beat his results.
  - **What changed:** his surgery, announced five days after his last outing, ends that case for 2027.
  - **Why he stays:** to show how a durability fact overrides the data.

**Set aside:**
- **Vesia (31, left-handed, 1.91):** a strong alternative and worth a call if Morejón's price runs.
- **Iglesias (37):** a one-year alternative to Abreu at about the same 2027 value.
  - **Aged one year:** 1.67 B1 wins against Abreu's 1.64 in the same job.
  - **Price:** about $12.1M expected, with a one-year value of $13.3M.
  - **Why he's second to Abreu:** the late-inning need runs past 2027, with Junis and Alexander gone and Latz the only established arm, and Abreu covers two seasons at 30. If the club wants no 2028 money, Iglesias is the pick.
- **Bednar:** the market's other closer name.
  - **Velocity:** his four-seamer lost 0.86 mph net of the league (97.1 → 96.1), with 79 rpm less spin.
  - **What the levers study says:** both changes go in directions it confirms cost whiffs (about −1.6 and −1.7 points, as associations).
  - **The rest:** he's 32, and his projection (1.70) trails Morejón's at an expected price of about $14.5M.
- **Clarke, Santana, Blackburn:** their run values outrun their bat-missing (K-BB 9.6–10.8%, engine whiff 21.7–25.0%). That is the profile the projection trusts least.
- **Club options:** Andrés Muñoz and Garrett Whitlock carry 2027 club options, as do others on the list, so they aren't free agents yet (MLB.com, Oct. 8). Their decisions were not checked.

## 3. Scouting reports (data-informed, not a live look)

**How to read the grades.** Each pitch gets three 20-80 grades, against every MLB pitch of the same Statcast type in 2026 with 50+ swings (the stuff model's tracked swings):
- **Present:** 2026 whiff per swing, regressed with that type's Atlas constant.
- **2027:** the edge engine's validated next-season whiff projection.
- **Stuff:** expected whiff from the physics alone.

The mapping is 50 + 10z of the percentile, to the nearest 5 (Method).
- **Control:** graded from unintentional walk rate, as a stand-in for command.
- **Health:** each report lists the same thing for every pitcher: public injured-list placements and surgeries since 2021, with sources. Nothing is inferred beyond them.
- **Where the stuff and 2027 numbers come from (reset Nov. 15):** every stuff grade, 2027 grade, expected whiff, gap and engine whiff projection in this memo is the saved Nov. 14 run's value ([`outputs/bullpen-grades-2026.json`](outputs/bullpen-grades-2026.json), checked by a test). The Oct. 14 memo printed an earlier fit that was not saved; the reset moved four grades by 5 points and is listed in the change log below.
- **Fit noise (added Nov. 15):** those numbers come from one fit of the expected-whiff model, and a refit moves them. I fit the same swings ten more times in different row orders. Every stuff and 2027 grade printed for these three pitchers stayed within 5 points of the printed grade, with one exception: Fairbanks's slider stuff grade, printed 45, ran 35 to 50. No role, OFP or ranking here rests on it. The range for every pitch is in [`outputs/edge-grade-noise-2026.json`](outputs/edge-grade-noise-2026.json).
- **Limits:** whiff is one job of a pitch, so sinkers and strike-throwing cutters are undergraded, and they are compared only within their own type. The reference pool includes starters. These grades describe the pitch in a relief role.

---

### Adrián Morejón, LHP, Padres, B/T L/L, 5'11", 224 lb, born Feb. 27, 1999 (27 on the report date; 2027 age 28), free agent

**Basis:** data only (Statcast 2024-26 regular season), not a live look.
- **Measurements:** MiLB.com player page, read Oct. 13, 2026.
- **2026 public line:** 76 G, 86.0 IP (Padres On SI, Oct. 10, 2026). A 2.83 ERA, 1.08 WHIP, 107 K and 28 BB (CBS Sports player page, read Oct. 13, 2026).
- **Statcast counts:** 352 PA, 107 K and 28 BB (7 intentional), which matches.
- **Free agency:** "set to become a free agent after the 2026 season" (Matt Levine, Padres On SI, Aug. 3, 2026). The same piece said The Athletic called him a qualifying-offer candidate.
- **QO eligibility:** he spent all of 2026 with San Diego (game logs, no transactions) and this is his first free agency, so he can't have received a QO before.

**Health (public):**
- **2021:** Tommy John surgery, April 20 (Daniel Guerrero, MLB.com, Apr. 21, 2021).
- **2023:** 60-day IL for a left elbow sprain, Mar. 30 (CBS Sports, Mar. 30, 2023), and 15-day IL for right knee inflammation, July 16 (MiLB.com transactions).
- **2024-26:** no IL placement (MiLB.com transactions, read Oct. 13, 2026).

**Arsenal (2026; whiff% on all swings, grades on tracked swings)**

| Pitch | Usage (vs LHH / RHH) | Velo | IVB / arm-side HB (in) | Whiff% (swings) | Present | 2027 | Stuff | Notes |
|---|---|---|---|---|---|---|---|---|
| Sinker | 47.6% (55 / 43) | 99.5 | 9.2 / 16.0 | 19.3 (311) | 65 | 60 | 65 | His primary pitch. 58% ground balls overall |
| Changeup | 23.1% (2 / 36) | 92.1 | −1.1 / 10.7 | 56.0 (182) | 75 | 75 | 70 | 7% of pitches in 2025, 23% in 2026; almost only to RHH |
| Slider | 15.2% (27 / 8) | 89.4 | −0.5 / −5.7 | 29.9 (77; 73 tracked) | 45 | 50 | 70 | Results trail the physics (small sample) |
| Four-seamer | 14.2% (16 / 13) | 99.3 | 15.2 / 6.0 | 42.3 (123) | 75 | 75 | 70 | A carry four-seamer at 99 |
| Control | uBB 6.0% (BB 8.0% with 7 intentional) | | | | 60 | 60 | | 2024-25 uBB 7.0% and 4.9% |

**Performance, regressed** (Atlas constants; estimate and 95% interval for his 2026 true level; league = all pitchers 2026):

| Metric | Observed (n) | Regressed (95%) | Next season (Atlas) |
|---|---|---|---|
| Whiff per swing | 34.2% (676 swings) | 32.8% (29.6–36.1) | 32.1% |
| Chase | 38.6% | 36.0% (33.1–38.9) | 35.2% |
| xwOBA on contact | .300 (212 BIP) | .347 (.323–.372) | not given (no year-to-year signal) |
| Ground-ball % | 58.0% | 54.8% (48.8–60.7) | 53.8% |
| Run value /100 | +1.39 (1,318 pitches) | +0.56 (−0.21 to +1.33) | not given (persistence too imprecise) |

**The halves of 2026** (through June / July on):
- **K-BB:** 24.9%, then 20.1%.
- **Walks:** all seven intentional walks came in the second half. Unintentional walk rate went 4.6% → 7.3%.
- **xwOBA:** .238, then .236.

**Stuff vs. results (edge engine; swing-weighted expected whiff, then the gap):**
- 2024: 26.1% expected, +0.0 gap.
- 2025: 24.7% expected, −3.0 gap.
- 2026: 28.6% expected, +5.6 gap.
- **The read:** his physics rose in 2026 and his results rose more. Before 2026 his results matched or trailed his physics.
- **Where the 2026 gap sits:** the four-seamer (+15.2) and changeup (+12.9) beat their physics, and the slider (−11.1) trailed it. Ten refits gave +13.7 to +16.2, +13.7 to +16.8 and −14.2 to −11.5, so the signs hold.
- **The changeup regressed:** 51.4% (45.2–57.6) for 2026 and 48.1% for next season. The engine projects 49.6% (ten refits gave 48.2% to 49.4%), still the 99th percentile of changeups.

**Velocity (league baseline):**
- **The gain:** sinker 97.4 (2024) → 97.7 (2025) → 99.5 (2026). The 2026 gain is +1.79, and the league's returning sinkers moved −0.05, so it's +1.85 net.
- **Precision:** the regressed level is 99.5 (99.3–99.7) on 76 games, regressed by games.
- **Through the season:** it held all year. Aug–Sep minus Mar–May: +0.03, against +0.25 for 199 league relievers.
- **Not cameras:** the gain is his, because the league didn't move. The same rise showed on his four-seamer (96.5 → 99.3) and slider (87.5 → 89.4).

**Usage and platoon:**
- **Against right-handers:** he leans on the changeup. 215 PA, 31.6% K, .247 xwOBA, 38.8% whiffs (35.8% regressed).
- **Against left-handers:** 137 PA, 28.5% K, .221 xwOBA, with sinker and slider.
- **The direction:** the xwOBA split runs the normal way. Lefties fared worse, and the gap (.027, p = 0.43) isn't significant. Only his strikeout and whiff rates run in reverse. The three-batter minimum doesn't bind him.

**Workload (game logs):**
- **Appearances:** 60, 75 and 76 in 2024-26.
- **2026 workload:** 18 back-to-backs, 25 outings of four or more outs, and 12 outings that completed three in four days. His longest gap between outings was 5 days.
- **Velocity on no rest:** sinker −0.11 mph on back-to-back days.
- **Leverage proxy:** 1.60 (his mean win-probability swing per PA over the league relief mean).

**Pitch design (levers study, 2025 → 2026, net of the league, beyond the noise threshold; associations, not forecasts):**

| Change | Size | Payoff per unit | Evidence | Implied whiff points | Year two |
|---|---|---|---|---|---|
| Slider spin | +54 rpm | +1.41 per 100 rpm | Confirmed | +0.8 | Unstable across season pairs |
| Slider slot | −2.2° (lower) | +1.22 per 3° higher | Confirmed | −0.9 | Year-two gain, borderline |
| Sinker velocity | +1.85 mph | +0.18 per mph | Not detected (sinkers) | +0.3 | Not followed |

- **The open lever is the slider.** Its physics grade (70; ten refits gave 70 to 75) is far ahead of its results (45), and the study can't say which change would close that gap.

**Familiarity:**
- **Low exposure:** as a reliever, hitters had seen almost none of his pitches earlier in the game (0.00 same-type pitches in earlier PAs) and 0.30 changeups in earlier games per changeup.
- **The cost:** at the league study's rates that's about −0.23 whiff points.
- **As a starter**, using the study's starter rates (Finding 7: 3.13 pitches seen in earlier PAs and 2.35 in earlier games per pitch thrown) at 23% changeup usage:
  - Earlier PAs: 0.23 × 3.13 = 0.72 same-type pitches × −1.87 = −1.35 points.
  - Earlier games: 0.23 × 2.35 = 0.54 × −0.77 = −0.42 points.
  - The total, about −1.8 points, is one measured reason to value him as a reliever.

**OFP 60; Role: B1 now and in 2027; Risk: moderate.**
- **The formula:** 0.55 × 75 + 0.35 × 75 + 0.10 × 60 = 73.5, capped at 60.
- **The risk** rests on three things: the velocity gain and the changeup's share of his results holding, and an elbow with a 2021 reconstruction and a 2023 sprain behind three healthy seasons.
- **Summary:** a ground-ball, platoon-neutral late-inning lefty at 28, coming off his best season, whose velocity has climbed for two years.
- **The biggest question:** how much of a 15-point changeup gap survives a second look from the league.
- **Action:** pref list #1, tier A.

---

### Bryan Abreu, RHP, Astros, B/T R/R, 6'1", 230 lb, born Apr. 22, 1997 (29 on the report date; 2027 age 30), free agent

**Basis:** data only (Statcast 2024-26 regular season), not a live look.
- **Measurements and transactions:** MiLB.com player page, read Oct. 13, 2026.
- **Public context:** a 14.73 ERA and a walk rate four times his 2025 rate on April 18.
- **His own explanation:** "a little bit of lack of confidence in my delivery" (Brian McTaggart, MLB.com, Apr. 18, 2026).
- **Free agency:** "slated to become a free agent at the end of the 2026 season" (MLB Trade Rumors, Mar. 14, 2026).
- **QO eligibility:** with Houston all season (game logs; MiLB.com shows no 2026 trade or assignment) and in his first free agency.

**Health (public):**
- **Injured list:** 2020 IL stints (no injury listed) and 10-day IL May 30, 2021, for a left calf strain. None for 2022-26 (MiLB.com transactions, read Oct. 13, 2026).
- **Not an injury:** three days on the restricted list, June 22-25, 2026, for a personal matter (NBC Sports, June 22 and 25, 2026). The club kept him, so QO eligibility is unaffected.

**Arsenal (2026)**

| Pitch | Usage (vs LHH / RHH) | Velo | IVB / arm-side HB (in) | Whiff% (swings) | Present | 2027 | Stuff | Notes |
|---|---|---|---|---|---|---|---|---|
| Slider | 44.5% (44 / 45) | 86.5 | −5.4 / −6.7 | 39.0 (205) | 60 | 65 | 65 | 46% whiffs in 2025 |
| Four-seamer | 44.0% (40 / 49) | 95.7 | 16.7 / 6.1 | 27.8 (194) | 60 | 65 | 55 | 36% whiffs at 97.3 mph in 2025 |
| Cutter | 11.4% (16 / 6) | 93.0 | 11.3 / −0.1 | 36.1 (61) | 65 | 65 | 40 | New in 2026; mostly to LHH |
| Control | uBB 15.3% (first half 19.7%, second 11.3%) | | | | 20 | 40 | | 2024: 9.8%, 2025: 10.5% |

- **The 2027 control grade (40)** is his 2024-25 rate (about 10%) and his second half of 2026 (11.3%). The first half of 2026 is treated as the outlier, which is the bet itself.

**Performance, regressed:**

| Metric | Observed (n) | Regressed (95%) | Next season |
|---|---|---|---|
| Whiff per swing | 33.8% (460) | 32.0% (28.2–35.8) | 31.4% |
| Chase | 27.6% | 28.6% (25.6–31.6) | 28.8% |
| xwOBA on contact | .363 | .362 (.336–.388) | not given |
| Ground-ball % | 41.5% | 41.8% | 41.8% |
| Run value /100 | +0.27 (1,093) | +0.09 (−0.70 to +0.89) | not given |

**The two halves of 2026** (through June / July on; a conventional calendar split fixed before looking):

| | G | PA | BB% | K% | K-BB% | xwOBA | Run value /100 | Four-seam velo (games) | Four-seam spin |
|---|---|---|---|---|---|---|---|---|---|
| First half | 31 | 127 | 19.7 | 26.8 | 7.1 | .365 | −0.97 | 95.0 (30) | 2,165 |
| Second half | 35 | 141 | 11.3 | 32.6 | 21.3 | .264 | +1.35 | 96.4 (35) | 2,295 |
| 2025 | 70 | 296 | 10.5 | 35.5 | 25.0 | .289 | +1.18 | 97.3 | 2,314 |

- **Walk rate:** the drop (25 of 127 to 16 of 141) has p = 0.058. That is borderline under the repo's standard, not confirmed.
- **Strikeout rate:** the rise has p = 0.30. Not distinguishable.
- **Velocity:** the gain is not noise.
  - **Regressed by games:** 95.0 (94.7–95.3) in the first half and 96.4 (96.2–96.7) in the second.
  - **Against normal movement:** a true pitcher's fastball moves about 0.55 mph between halves (Atlas), so +1.4 is about 2.6 times that.
  - **For the full season:** late minus early was +1.61, against +0.25 for the league's relievers.
- **Still short of 2025:** the second-half four-seamer was 0.9 mph below his 2025 level.

**Stuff vs. results:**
- 2024: 33.5% expected, +0.3 gap.
- 2025: 33.3% expected, +8.1 gap.
- 2026: 29.2% expected, +4.7 gap.
- **The read:** results beat his physics two years running, and that gap is a trait that carries over (edge engine, r ≈ 0.55).
- **The engine's 2027 whiff projection, 33.1%,** is the best of the three.

**Velocity (league baseline):** four-seamer 97.3 → 95.7 for the season, −1.49 net of the league (−0.10).

**Usage and platoon:**
- **Against right-handers:** 125 PA, 14.4% BB, .306 xwOBA, 36.5% whiffs.
- **Against left-handers:** 143 PA, 16.1% BB, .317.
- **The direction:** the xwOBA gap (.011, p = 0.81) isn't significant. The cutter (16% to lefties) is new.

**Workload:**
- **Appearances:** 78, 70 and 66.
- **2026 workload:** 13 back-to-backs (four-seamer −0.32 mph on no rest), 10 multi-inning outings, and a longest gap of 7 days.
- **Leverage proxy:** 1.36.

**Pitch design (every lever beyond the noise threshold with an evidence label of "confirmed"):**

| Change | Size | Payoff per unit | Evidence | Implied whiff points | Year two |
|---|---|---|---|---|---|
| Four-seam velocity | −1.51 mph | +1.81 per mph | Confirmed; placebo fails (selection or recovery not ruled out) | −2.7 | Not shown to last (borderline) |
| Four-seam spin | −72 rpm | +2.09 per 100 rpm | Confirmed | −1.5 | Whiff gain held; run value not shown to last |
| Slider speed gap | −1.58 mph (the fastball slowed) | +1.06 per mph | Confirmed | −1.7 | Not shown to last (borderline) |
| Slider spin | −82 rpm | +1.41 per 100 rpm | Confirmed | −1.2 | Unstable across season pairs |
| Slider slot | +1.4° (higher) | +1.22 per 3° | Confirmed | +0.6 | Year-two gain, borderline |

- **The lever is to get the four-seamer back to 97.**
  - **Half of it already happened:** second half 96.4 and 2,295 rpm, against 97.3 and 2,314 in 2025.
  - **The slider gap would follow:** it is measured from the fastball.
- **The study's caveat cuts both ways.**
  - **For the bet:** the velocity association fails its placebo, which means "pitchers whose velocity comes back get their whiffs back." That is exactly the bet here.
  - **Against it:** the same study found those gains not shown to last a second season (borderline).
- **The walk rate is the bigger risk.** The study doesn't model command, and the data can't say whether the second half will hold.

**Familiarity:** low, as for any reliever: −0.27 whiff points on the slider from earlier-game exposure, −0.20 on the four-seamer.

**OFP 50 (formula 60, overridden); Role: B2 in 2027; B1 if his unintentional walk rate holds at or below about 11% through his first 150 PA; Risk: moderate to high.**
- **Why the override:** the formula gives control 10% weight. A 15% walk rate costs runs that whiff-based pitch grades can't see.
  - **On the role scale:** a 55 would be a B1 (55-60 band). Until the walks are settled, his role is B2 (50).
- **Action:** pref list #2, tier B, the plan if Morejón's price passes the walk-away.

---

### Pete Fairbanks, RHP, Marlins, B/T R/R, 6'6", 225 lb, born Dec. 16, 1993 (32 on the report date; 2027 age 33), free agent

**Basis:** data only (Statcast 2024-26 regular season), not a live look.
- **Measurements:** RotoWire player page, read Oct. 13, 2026.
- **2026:** 6.31 ERA, 41.1 IP, 57 K, 21 BB (1 intentional), 19 saves in 23 chances, on a one-year, $13M deal (MLB.com, Sept. 19, 2026; Roundtable Sports, Sept. 16).
- **Statcast counts:** 57 K and 21 BB, which matches.

**Health (public):**
- **Earlier surgery:** Tommy John surgery that cost him 2018 (RotoWire, read Oct. 13, 2026).
- **IL trips:**
  - 2022: a lat injury.
  - 2023: forearm and hip inflammation.
  - 2024: a nerve-related issue (Matt Snyder, CBS Sports, Apr. 22, 2024) and a season-ending lat strain.
  - 2026: three placements, "related to the nerve issue" (right median nerve irritation; Brandon Liguori, Roundtable Sports, Sept. 16, 2026). The 2022-24 trips are from RotoWire.
- **The surgery:** on Sept. 19, 2026 the Marlins announced thoracic outlet syndrome surgery, date to be set. "The typical recovery period for a pitcher is about nine or 10 months" (Christina De Nicola, MLB.com, Sept. 19, 2026).
- **What the memo assumes:** he pitches about a third of 2027. Nothing beyond the reports is inferred.

**Arsenal (2026)**

| Pitch | Usage (vs LHH / RHH) | Velo | IVB / arm-side HB (in) | Whiff% (swings) | Present | 2027 | Stuff | Notes |
|---|---|---|---|---|---|---|---|---|
| Four-seamer | 48.7% (49 / 49) | 97.2 | 18.1 / 1.6 | 27.4 (175) | 60 | 60 | 60 | Ride +1.0 in net of the league |
| Slider | 26.4% (32 / 19) | 83.7 | −8.5 / −6.0 | 40.5 (79) | 60 | 55 | 45 | The physics grade is not stable: ten refits gave 35 to 50 (expected whiff 27.7% to 32.7%). In every fit the results beat it (+7.8 to +12.8 points) |
| Cutter | 23.1% (16 / 32) | 89.6 | 3.3 / −5.6 | 34.9 (86) | 65 | 75 | 75 | 4% of pitches in 2025 (41), 23% in 2026 |
| Control | uBB 10.9% | | | | 35 | 40 | | 2024-25 uBB 8.1% and 7.4% |

- **The 2027 control grade (40)** blends his 2024-25 rate (about 7.7%, a 50) with 2026 (35). It gives the recent year more weight, and his health makes 2027 control uncertain anyway.

**Performance, regressed:**

| Metric | Observed (n) | Regressed (95%) | Next season |
|---|---|---|---|
| Whiff per swing | 31.9% (340) | 30.1% (25.8–34.4) | 29.6% |
| xwOBA on contact | .417 (102 BIP) | .369 (.342–.395) | not given |
| Hard-hit % | 43.6% | 40.0% (35.0–45.0) | 39.9% |
| Ground-ball % | 24.5% | 30.8% (23.1–38.5) | 31.7% |
| Run value /100 | −0.54 (766) | −0.16 (−1.00 to +0.68) | not given |

- **Stuff beat results in 2026.** The 6.31 ERA came mostly from contact.
  - **The contact number is the least trustworthy:** pitchers' xwOBA on contact shows no within-season signal in the Atlas (r = 0.15 at 181 balls in play), so it regresses most of the way to the league.
  - **What holds:** his swing-and-miss and 19.7% K-BB.
  - **Fly balls:** his 31% regressed ground-ball rate keeps hard contact costly.
- **Stuff vs. results:**
  - 2024: 28.3% expected, −7.4 gap.
  - 2025: 26.6% expected, −1.1 gap.
  - 2026: 30.8% expected, +1.5 gap.
  - **The read:** his physics were at their best in 2026, after a dip in 2025. The cutter, 4% of his pitches in 2025 and 23% in 2026, carries the best physics grade he has.

**Velocity:**
- **Season:** four-seamer 97.2, unchanged net of the league.
- **Late season:** −0.80 mph against the league relievers' +0.25.
- **September:** 2 outings and 10 fastballs at 94.4 and 95.4 mph. The second ended after six pitches, when he left with the nerve irritation (Roundtable).

**Usage and platoon:**
- **The split in the data:** right-handers .265 xwOBA (78 PA), left-handers .365 (103 PA). The difference (.100, SE .064, p = 0.11) is not confirmed, on samples near 100 PA each.

**Workload:**
- **2026:** 46 games, zero multi-inning outings, 8 back-to-backs, and 19-day gaps twice (IL stints).
- **Earlier:** 46 and 61 games in 2024-25.

**Pitch design (every confirmed lever beyond the noise threshold, 2025 → 2026):**

| Change | Size | Payoff per unit | Implied whiff points | Year two |
|---|---|---|---|---|
| Four-seam ride | +1.0 in | +1.62 per 2 in | +0.8 | Point estimate held; can't exclude a full fade |
| Slider drop | +3.1 in | +1.30 per 2 in | +2.0 | Not shown in year one in this sample; not shown to last (borderline) |
| Slider speed gap | +1.5 mph | +1.06 per mph | +1.6 | Not shown to last (borderline) |
| Slider slot | −1.6° (lower) | +1.22 per 3° higher | −0.7 | Year-two gain, borderline |

- **The slider total:** about +2.9 points by the levers, against −5.9 expected-whiff points by the physics model. See "Where the tools disagree."
- **No cutter lever:** the cutter had 41 pitches in 2025, below the study's floor, so the study has no pair for it.

**Familiarity:** low: −0.10 to −0.13 whiff points per group.

**OFP 50 (formula 60, overridden); Role: B2 when healthy; Risk: high (health).**
- **Why the override:** the cutter's 65 present grade rests on 86 swings in its first season, and an 11% walk rate keeps him off the B1 line.
- **Action:** pref list #3, tier C.
  - **2027:** not an option.
  - **If wanted:** a two-year rehab contract at about $3M a year (2y/$6M), with incentives, subject to the club's medical review.

## 4. Cost and value

**The projection.**
- **Method:** derived, not published. Relief run value per 100 pitches, 2024-26 weighted 5/4/3, regressed with the Atlas constant (M = 1,932 pitches) toward the league relief mean (+0.08).
- **Replacement:** fringe arms' −0.70 (pitcher-seasons with 50–399 relief pitches, 2024-26).
- **Wins:** 10 runs per win.
- **Role:** × (1 + LI) / 2 with the leverage of the role each is priced in (assumptions). B1 is 1.6, matching Morejón's 1.60 proxy. B2 is 1.4; Abreu's proxy was 1.36. Depth is 1.1.
- **What the interval covers:** the rate only. It understates the uncertainty, because it leaves out:
  - **Playing time and leverage.**
  - **Next-season persistence:** the Atlas couldn't measure run value's year-to-year persistence, so the regressed rate is used as next season's.
  - **The constant's own range:** the Atlas's M for run value is extrapolated beyond its data (largest measured n 1,024), and these samples run to 2,800.

| | Morejón | Abreu | Fairbanks |
|---|---|---|---|
| Projection rate /100 (95%) | +0.83 (+0.19 to +1.47) | +0.37 (−0.26 to +1.01) | +0.18 (−0.52 to +0.88) |
| Relief pitches, weighted | 1,148 | 1,177 | 811 (healthy) |
| Wins, no leverage | 1.75 | 1.26 | 0.71 |
| Wins in role (rate-only 95%) | **2.28** B1 (1.32–3.23) | **1.51** B2 (0.62–2.41); 1.64 as B1 | **0.75** depth, healthy; **0.24** for 2027 |

**What the reliever market paid in 2025-26.**
- **The comps:** every reliever the NBC Sports/Yahoo free-agent tracker (D.J. Short, Feb. 12, 2026) lists with contract terms. That is 21 signings, with no salary floor and options and opt-outs not priced.
  - **Checked against wire reports:** Díaz three years, $69M (AP, Dec. 9, 2025; the deal includes deferrals, so its present value is below the nominal $23M a year) and Suarez three years, $45M (amNY, Dec. 11, 2025).
- **Projected the comps' way:** each comp from his two pre-signing seasons (2024-25, weighted 5/4) with a 2024-25 replacement level (−0.65), so no post-signing data leaks in. For the market price, the candidates are projected the same way, from 2025-26.
- **The fit:** AAV = $0.93M + $9.60M × wins (no leverage). R² is 0.27, the residual SD is $4.2M, and the slope's SE is $3.6M. The comps' projections run 0.45–1.42 wins.

| | Projected wins, comps' way | Expected AAV | 95% prediction interval | Inside the comps' range? |
|---|---|---|---|---|
| Morejón | 1.82 | $18.4M | $7.4–29.3M | No (extrapolated) |
| Abreu | 1.17 | $12.2M | $3.1–21.3M | Yes |
| Fairbanks (healthy) | 0.62 | $6.9M | minimum–$16.3M | Yes |

- **The low R² is itself a finding.** The market priced relievers loosely on run value; saves, velocity, health and reputation move prices this projection doesn't see. So a price band of ±$10M is honest, not mispricing.
- **The public guesses:** for Morejón, four years and $60M from a rival executive (Pat Ragazzo, FanSided/Friars on Base, Sept. 9) and Lin's "nine-figure offers" (via Padres On SI, Oct. 10). That article raised a rotation role as a way for the Padres to keep him. No public projection was found for Abreu or Fairbanks.

**Value and surplus.**
- **Present value:** 10%. The market line and the price of a win grow 3% a year, and relief value falls 10% a year from age 31. All assumptions are in `acquisition.py`.
- **"Value at the market line"** prices our three-season projection at the line's rate. It is a market price, not a club value: a contract at the break-even has zero surplus by construction, and the odds table follows from the same line. No club win curve is modeled. The engine column is not on the same win scale, so it is shown as an order of magnitude only.

| Contract | PV of salary | Value at the market line | Surplus | Engine value (different scale) |
|---|---|---|---|---|
| Morejón 4 years, $60M (opening) | $52.3M | $63.1M | +$10.8M | $107M |
| Morejón 4 years, $66M (first version's walk-away with a QO) | $57.5M | $63.1M | +$5.6M (less the first version's $5.8M pick and pool = about 0) | $107M |
| Morejón 4 years, $72M (walk-away) | $62.8M | $63.1M | +$0.4M | $107M |
| Morejón 4 years, $80M (stretch) | $69.7M | $63.1M | −$6.6M | $107M |
| Morejón 5 years, $100M ("nine figures") | $83.4M | $74.3M | −$9.1M | $119M |
| Abreu 2 years, $18M (opening) | $17.2M | $24.1M | +$7.0M | $24.5M |
| Abreu 2 years, $25M (walk-away) | $23.9M | $24.1M | +$0.3M | $24.5M |
| Fairbanks 2 years, $6M (rehab: a third of 2027, then 2028) | $5.7M | $8.5M | +$2.8M | $5.6M |

*Updated Oct. 18: with the house pick value ($10.6M of pick and pool), the opening row ($60M, surplus +$10.8M) is the one that nets to about zero with a QO.*

**Break-even AAV** (value at the market line):

| Pitcher | Three-season projection | Comps' way (two seasons) |
|---|---|---|
| Morejón (4 years) | $18.1M | $18.7M |
| Abreu (2 years) | $12.6M | $11.8M |
| Fairbanks (2-year rehab) | $4.5M | $4.0M |

**The walk-away and the odds of landing him.**
- **The walk-away is the market line's price for his projection: $18.1M, so four years and $72M.** It is the market's expected price with no premium, and he sits above every comparable signing's projection (1.82 wins against a range of 0.45 to 1.42), so it is an extrapolation with a 95% band of $7.4M to $29.3M a year. With the qualifying offer it falls to $60M (see the Nov. 14 update).
- **His expected price is $18.4M.** Reading the line's prediction interval as the distribution of his price (a rough guide, not a market model):

| Walk-away (4 years) | Chance his price is at or below it |
|---|---|
| $66M ($16.4M a year: the first version's QO case) | 36% |
| $70M | 44% |
| $72M | 47% |
| $80M | 62% |
| $88M | 75% |

*Updated Oct. 18: the QO case is now $60M, below the lowest step in this table. Added Nov. 14: at $60M ($15.0M a year) the chance is 26%, from the same line (`chance_price_at_or_below`).*

- **What the club gives up:** a walk-away at the market's expected price lands him about half the time; with the qualifying offer the walk-away is $60M and the chance is about one in four. The alternative, Abreu at his own value, carries about zero surplus, so losing Morejón costs his extra wins, not money.
- **Raising the walk-away** is worth it only if 2027 wins are worth more to this club than the market rate. The Rangers missed the wild card by four games, and their win curve isn't modeled here, so it's the GM's call. The table gives the price of each step.

**Availability: what the contract is worth if he keeps a typical reliever's workload (added Nov. 14).**
- **Why this was missing:** the values above give Morejón his projected workload in every contract year and no decline until age 31. He had Tommy John surgery in 2021 and a 60-day elbow sprain in 2023.
- **The rate, from this portfolio's own data:** the 170 relievers who threw 800 or more relief pitches in 2024 threw 63% as many in 2025 and 48% as many in 2026. The second season cost another 24% (0.76 of the first; bootstrap 95% range 0.68 to 0.84).
- **How it is applied:** year one stays at his projection, which already uses his own three-season workload. Each later year keeps 0.76 of the year before (`availability_path`). Beyond two seasons the data can't say, so the same step is assumed.
- **What it counts and misses:** relief pitches only, so a move to the rotation reads as lost work. All ages are pooled, and the group was picked on a heavy 2024.

| Contract | Wins in role, full workload | Wins in role, typical workload | Break-even AAV at the market line | Total |
|---|---|---|---|---|
| Morejón, 4 years | 8.9 | 6.2 | $12.9M | $51.5M |
| Morejón, 3 years | 6.8 | 5.3 | $14.3M | $43.0M |
| Abreu, 2 years | 2.9 | 2.5 | $11.2M | $22.4M |

- **Read with the qualifying offer:** four years at $60M buys about $44.9M of value on this reading, before the $10.6M of pick and pool. So $60M is a ceiling, not a target.
- **Two readings, kept apart:** $72M (now $60M with the offer) is the market's expected price for his projection. The availability figure is what that money buys if he ages like the relievers in the data. The market pays the first; a club that believes the second should let another club pay it.
- **Abreu holds up better:** two years lose less. His walk-away moves from $25M to about $22M on the same reading.
- **Not done:** a survival curve by age and injury history, and more than two seasons of follow-up. Three seasons of pitch data can't support either.

**The qualifying offer.**
- **The rules:** a qualifying offer is the 2022-26 agreement's ($22.025M in 2026; $23.15M for 2027, reported Oct. 8, 2026).
  - **Morejón:** the Padres made the offer on Nov. 2 (AP). He had until 4 p.m. ET on Nov. 17 and declined it that day (MLB.com, AJ Cassavell, Nov. 17, 2026; NBC Sports, Nov. 17, 2026). The Padres paid tax in 2026, so losing him earns them only a pick after Round 4.
  - **Abreu:** was eligible, and Houston did not make the offer (he is not among the eight). Signing him costs no pick.
- **The Rangers' cost:** their 2nd-highest 2027 pick plus $0.5M of pool.
  - **The pick:** a 2nd-rounder near No. 55. That number is an estimate from their 80-82 finish.
  - **Its value (updated Oct. 18):** about $10.1M, from my 2000-2016 draft table (picks 45-60 average what they returned, less the 2026 slot), in place of the first version's $5.3M in 2019 dollars (Craig Edwards, FanGraphs, Apr. 5, 2019).
  - **In total:** about $10.6M in present value. That lowers Morejón's walk-away by $3.04M a year, or $12.2M nominal over four years, to about $15.1M a year, or $60M. On the 2019 figure it was $5.8M, $1.66M a year and $66M.
- **The QO may not outlive this agreement.** The union proposed eliminating it (CBS Sports, Dayn Perry, May 28, 2026), and MLB said it would agree (AP, June 25, 2026).
  - **Before December 1:** a signing falls under current rules.
  - **After a lockout:** a signing might fall under rules without the QO. That isn't known.

**The luxury tax.**

| Pre-signing 2027 CBT payroll | +$7M | +$12M | +$18M |
|---|---|---|---|
| ~$191M (this memo's estimate, before benefits) | $0 | $0 | $0 |
| $235M | $0 | $0.6M | $1.8M |
| $244M | $1.4M | $2.4M | $3.6M |

- **The threshold:** $244M, the 2026 line, used as an assumption. The 2022-26 agreement sets no 2027 line.
- **MLB's proposal is a different system:** a $245.3M salary cap including benefits, from 2027 (Dayn Perry, CBS Sports, May 28, 2026).
- **The rate:** first-time payor, 20%.

**Timing and the labor clock.**
- **Current rules run the window.** Qualifying-offer decisions come a few days after the World Series, and the agreement expires December 1 at 11:59 p.m. ET.
- **A lockout ends free-agent negotiation and trades** (MLB's memo, as summarized by Bleacher Nation, Oct. 8, 2026). The window under known rules is about three to four weeks of November, shorter than the December window in which last winter's top relievers signed.
- **What that means:**
  - **Morejón:** if he isn't qualified, move early, before a bidder treating him as a starter sets the price. If he is qualified, the pick and pool's $10.6M (updated Oct. 18; first version $5.8M) is a known cost. Waiting through a lockout to see whether the QO survives trades that for not knowing when, or whether, he can be signed.
  - **Abreu:** his price should fall the longer the market waits, so he is the natural late option. Under a lockout, "late" may mean March.
  - **A signing bonus paid before December 1** survives a stoppage. Salaries are paid by games played and stop in a stoppage; a bonus doesn't (the Skenes memo's logic).
    - **For the player,** that certainty is worth something.
    - **For the club,** it gives up the savings it would get in a stoppage, which makes it a risk transfer, not a free gain.
    - **Use it** to win a close bid rather than to raise the AAV.

## 5. The recommendation

1. **Bid on Morejón, to his value.**
   - **Open:** four years, $60M (2027-30), with a 2031 club option. Use part of it as a signing bonus paid before December 1 to win a close bid.
   - **Walk away:** above four years and $60M. He carries a qualifying offer as of Nov. 2 (without it the walk-away was $72M). No fifth guaranteed year, no opt-out.
   - **The odds:** expect to land him about one time in four (26% at $60M).
   - **If he accepts the offer by Nov. 17:** stop. He is not a free agent.
2. **If his price passes the walk-away, sign Abreu.**
   - **Open:** two years, $18M, with a 2029 club option.
   - **Walk away:** above two years and $25M.
   - **The condition:** the second half of 2026 is the bet. It is borderline evidence (p = 0.058 on walks), so price it like one.
   - **If the club wants no 2028 money:** Iglesias on one year, up to about $13M, is the equivalent.
3. **Fairbanks is not the 2027 answer.** If the club wants him for 2028, a two-year rehab contract up to about $9M total, with incentives, subject to its medical review.

**What changes the call.**
- **Morejón's market:** any bid at starter money (five years, nine figures) puts him above his value by about $9M in present value.
- **The budget:** under about $15M a year for relief means Abreu (or Iglesias) first.
- **The qualifying offer (made Nov. 2):** it lowers Morejón's walk-away by about $12M nominal, to $60M (updated Oct. 18; first version $6.7M).
- **The club's view of 2027 wins:** valuing them above the market raises the walk-away. Each step's price and odds are in section 4.
- **New information:** a club medical review of any of the three, or a winter look at Abreu's delivery (team data, outside this public memo).
- **The labor outcome:** if a lockout starts December 2 with Morejón unsigned, the decision moves to whenever free agency reopens, under rules nobody has yet.

**What changed after the review pass.**
- **Ranking:** unchanged.
- **Prices:**
  - Morejón's walk-away rose from $70M to $72M, after the market line was refit with consistent projections and a leak-free replacement level. With a QO it rose from $63M to $66M.
  - Abreu's walk-away rose from $24M to $25M.
- **Fairbanks:** went from a one-year $5M bet to "not a 2027 option," after his Sept. 19 surgery announcement.
- **OFPs:** Abreu's and Fairbanks's fell from 55 to 50, to match the role scale.

**What changed on Nov. 15: the model numbers were reset to the saved run.**
- **Why:** the Oct. 14 memo printed stuff and 2027 numbers from a fit of the expected-whiff model that was not saved. They now equal the saved Nov. 14 run and a test holds them there.
- **Grades that moved, all by 5 points:**
  - Abreu's slider: stuff 60 to 65 and 2027 60 to 65. The side-by-side table now reads "(60 / 65)".
  - Fairbanks's four-seamer: stuff 65 to 60.
  - Fairbanks's slider: stuff 40 to 45.
  - Morejón's slider: 2027 grade 55 to 50. Its stuff grade stays 70 (expected whiff went from 42% to 41%, the 98th percentile to the 97th).
- **Morejón's 2026 gaps:** changeup +15.1 to +12.9, four-seamer +13.6 to +15.2, slider −12.0 to −11.1. The changeup projection went from 48.9% to 49.6%.
- **Expected whiff and gap by season:** all nine lines moved, by 1.5 points at most. One read changed: Fairbanks's physics no longer "improved every year" (28.3%, 26.6%, 30.8%). They were best in 2026.
- **Engine whiff projections:** nine of the thirteen in the candidate table moved by 0.1 or 0.2 (Abreu 32.9% to 33.1%, Morejón 30.9% to 31.0%, Fairbanks 29.9% to 29.8%).
- **What did not move:** the ranking, the roles, the OFPs (each formula value is still 60 before the overrides), the prices and the recommendation. Present grades do not use the model, but they depend on which swings the run tracks: see the Nov. 23 correction.

- **Correction (Nov. 23):** rerunning `bb bullpen-case` on the saved Oct. 17 Edge Board run gives Morejón's slider a present grade of 45, not the 50 I printed. Its regressed whiff rate is 31.3%, the 40.0th percentile of 279 slider-group pitches, just under the 45/50 line (about 40.1). The 50 came from an earlier fit that wasn't saved (40.4th percentile): 39 pitches had different tracked-swing counts between the runs, which shifts the comparison pool. The other 29 present, 2027 and stuff grades match the saved run exactly. His OFP, role, ranking, price and the recommendation don't change, because his OFP rests on the sinker, changeup and four-seamer. The figure is now drawn from the saved run.
- **The figure** was drawn from the earlier fit until Nov. 23, when I redrew it from the saved Oct. 17 run. Every marker now matches this table, including the three that sat 5 points off (Abreu's slider and Fairbanks's four-seamer and slider).

## Method

**Grain.** Pitch rows from the sequence copy (regular seasons 2024-26). Lines are pitcher × season, grades are pitcher × pitch type, the market fit is one row per signing, and the team table is one row per club.

**The comparison table** (`reliever.compare_relievers(ids, season)`): every number in section 3, for any list of pitcher ids.
- **Flags:** set once on every row.
- **No-pitch rows** (intentional walks and pitch-clock calls, `automatic_ball`/`automatic_strike`) count toward PA and walks but not pitches, swings, zone or run value.
- **Relief:** any pitcher after his team's first pitcher of the game.
- **Rates:** from summed counts.
- **IP:** from event outs, so it is approximate. Morejón shows 84.2 against an official 86.0.

**The 20-80 mapping** (`grade_from_percentile`, tested).
- **The formula:** grade = 50 + 10z, where z is the normal quantile of the pitch's mid-rank percentile among MLB pitches of the same type with 50+ tracked swings that season. Rounded to the nearest 5, clamped to 20-80.
- **The scale:** the scouting scale's 10 points per SD (the 20-80 convention).
- **The anchors:** percentile 84 → 60, 98 → 70, 16 → 40, 2 → 30.
- **Present** uses the regressed whiff rate (pitch-type M), **2027** the engine's projection, **stuff** the expected whiff.
- **Control** (`control_grade`) interpolates my walk-rate anchors on unintentional walk rate: 4% → 75, 5.75% → 60, 8% → 50, 10.5% → 40, 12% → 30, 15% → 20.
- **OFP** is my reliever formula, with overrides stated.
- **Limits:** whiff-only; the reference includes starters; no command within the zone, deception or delivery.

**Regression.** `reliability.regress` with the shipped 2024-26 constants.
- **Physics:** velocity is regressed by games.
- **Next season:** given only where the Atlas measured year-to-year persistence.

**Tests of differences.**
- **Rates:** two-proportion z-tests.
- **xwOBA:** a two-sample z-test on per-PA values (`xwoba_diff_test`). It treats PAs as independent, which slightly understates the SE.

**Velocity baseline.**
- **Season over season:** his change minus the median change of every pitcher with 100+ pitches of that type in both seasons.
- **In season:** Aug–Sep minus Mar–May (game means), against the median of the same for 199 relievers with 5+ outings in each window.

**Familiarity** (`familiarity_load`): exposures from `edge.familiarity.exposures`, priced with the league study's per-pitch costs. Those costs are contrasts against an earlier pitch of another type, so the totals are approximate.

**Pitch design** (`lever_read`): the levers study's 2025 → 2026 pairs, net of the league, flagged beyond each lever's noise threshold.
- **Each row carries:** the study's per-unit payoff, its evidence label and its year-two label (`LEVER_PERSISTENCE`).
- **The implied whiff change** is the league association, not a forecast for the pitcher.

**Money** (`roster/acquisition.py`):
- **The projection, replacement level and contract values** described in section 4.
- **The market line and its prediction interval:** `market_line`, `market_price_interval`.
- **The landing odds:** `chance_price_at_or_below`.
- **Partial seasons:** `availability` in `contract_value`.
- **Engine values:** `money.dollars_per_war`.
- **QO:** `money.qualifying_offer`.
- **Tax:** `money.tax_cost_of_signing`.

## What this doesn't show

- **No live look, no video, no medical review.** The grades are data-informed, and a scout's look at Abreu's delivery could move his report.
- **The projection's intervals cover the rate only.** Run value's persistence is unmeasured, and the Atlas constant is extrapolated at these sample sizes.
- **The market line is one winter, 21 signings, R² 0.27.** Morejón's price is an extrapolation beyond every comp. The odds table reads a regression's prediction interval as a price distribution, which is an approximation.
- **The win scale isn't calibrated to fWAR.** Engine-$/WAR values are not comparable to the market-line values, and none of the decisions rest on them.
- **Unverified or estimated:**
  - the Rangers' 2027 payroll (derived; benefits excluded)
  - their 2nd-highest pick number (No. 55, estimated)
  - the pick's value (the house figure, about $10.1M, comes from my own draft backtest, which values a pick with a floor of zero on each season; without that floor it is lower, so the $60M walk-away would be somewhat higher)
  - Morejón's decision on his qualifying offer (due Nov. 17; not reported as of Nov. 14)
  - whether any 2027 tax threshold exists
  - option decisions for the excluded relievers
  - Lin's quote (read secondhand)
  - Fairbanks's 2027 availability (35%, assumed from the typical recovery time, with the surgery date not yet set)
- **One source error found:** Friars on Base (Sept. 9) gives Robert Suarez's Braves deal as four years and $60M. The NBC/Yahoo tracker and amNY (Dec. 11, 2025) give three years and $45M, and those are used.
- **No causal claims.** The lever effects are associations from an observational study. That Abreu's velocity and walks recovered together is a pattern, not proof the delivery is fixed.
- **No club-specific win value.** The Rangers' revenue per marginal win near the wild-card line isn't modeled. It is the input behind any walk-away above $72M.

## Reproduce
```bash
uv run python -m baseball.roster.bullpen_case        # every number in this memo, and the figure
uv run pytest tests/test_reliever.py tests/test_acquisition.py
uv run bb bullpen-case                               # the same numbers through the CLI
uv run bb compare-relievers 2026 670970 650556 664126   # needs the 2024-26 seasons pulled first (bb pull-league, bb seq)
```

## Sources
- **Pitch data:** Statcast, MLB Advanced Media, via [Baseball Savant](https://baseballsavant.mlb.com/) (regular seasons 2024-26).
- **Names and ids:** the Chadwick Bureau register.
- **Free-agent class:** MLB.com, "All of the 2026-2027 free agents, position by position" (Oct. 8, 2026).
- **Standings:** MLB.com standings, 2026 (last updated Oct. 7, 2026).
- **Rangers:**
  - Matt Postins, Texas Rangers On SI (Oct. 2, 2026)
  - Spotrac, Rangers 2026 tax page (read Oct. 13, 2026)
  - Zach Cioffi, Just Baseball (Oct. 7, 2026)
  - Eduardo Solano, Roundtable Sports (July 21, 2026)
  - 2025 CBT bill: CBS Sports (Mike Axisa, Dec. 20, 2025)
- **Qualifying offer:**
  - Tiers: MLB Trade Rumors, "Each Team's Penalty For Signing A Qualifying Offer-Rejecting Free Agent," republished by NewsBeep (Oct. 12, 2026)
  - Rules: MLB.com glossary
  - Its future: CBS Sports (Dayn Perry, May 28, 2026) and AP (June 25, 2026)
- **Morejón:**
  - J.P. Hoornstra (Oct. 10, 2026) and Matt Levine (Aug. 3, 2026), Padres On SI
  - Pat Ragazzo, FanSided/Friars on Base (Sept. 9, 2026)
  - CBS Sports player page (read Oct. 13, 2026)
  - MiLB.com player page and transactions (read Oct. 13, 2026)
  - Daniel Guerrero, MLB.com (Apr. 21, 2021)
  - CBS Sports (Mar. 30, 2023)
- **Abreu:**
  - Brian McTaggart, MLB.com (Apr. 18, 2026)
  - Mark Polishuk, MLB Trade Rumors via Yardbarker (Mar. 14, 2026)
  - NBC Sports player news (June 22 and 25, 2026)
  - MiLB.com player page (read Oct. 13, 2026)
- **Fairbanks:**
  - Christina De Nicola, MLB.com (Sept. 19, 2026)
  - Brandon Liguori, Roundtable Sports (Sept. 16, 2026)
  - NBC Sports (Sept. 15, 2026)
  - Matt Snyder, CBS Sports (Apr. 22, 2024)
  - RotoWire player page (read Oct. 13, 2026)
- **2025-26 reliever contracts:**
  - D.J. Short, MLB free agent tracker, NBC Sports/Yahoo Sports (Feb. 12, 2026)
  - AP via CBS (Dec. 9, 2025)
  - amNY (Joe Pantorno, Dec. 11, 2025)
- **Draft-pick value:** Craig Edwards, "An Update on How to Value Draft Picks," FanGraphs (Apr. 5, 2019).
- **$/WAR and valuation:** FanGraphs, Ben Clemens (Feb. 24 and July 2, 2026), via `baseball/roster/money.py`.
- **Labor:**
  - MLB's lockout memo: Brett Taylor, Bleacher Nation (Oct. 8, 2026)
  - MLB's cap proposal: Dayn Perry, CBS Sports (May 28, 2026)
  - The rest of the labor background: [the roster and CBA memo](2026-roster-cba-engine.md)
- **This repo's studies:** [Reliability Atlas](2026-reliability-atlas.md), [pitch familiarity](2026-league-pitch-familiarity.md), [pitch-design levers](2026-pitch-design-levers.md), the edge engine (LOG.md, 2026-10-12).

---
© 2026 Dylan Fanelli. All rights reserved. See [LICENSE](../LICENSE).

<!-- portfolio:footer -->
---
<sub>[← Portfolio](../README.md) &nbsp;|&nbsp; [Pitch familiarity →](2026-league-pitch-familiarity.md)</sub>

<sub>© 2026 Dylan Fanelli. All rights reserved. To cite: Fanelli, D. (2026). *Bullpen acquisition memo, 2026-27 offseason: three relievers for the Texas Rangers*. Dylan Fanelli Baseball Analytics Portfolio. https://github.com/IForSureI/Dylan-Fanelli-Baseball-Analytics-Portfolio/blob/main/reports/2026-bullpen-acquisition-memo.md</sub>
<!-- /portfolio:footer -->
