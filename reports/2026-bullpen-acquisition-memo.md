# Bullpen acquisition memo, 2026-27 offseason: three relievers for the Texas Rangers

**Decision memo from public data.** One real offseason decision, made the way a front office makes it: the club's need, three relievers it could sign this winter, a data-informed scouting report on each, what each costs and is worth under the 2022-26 agreement and its December 1 expiration, and a ranked recommendation with a price.
- **The scouting reports are data-informed, not a live look.** Every grade comes from Statcast shape and results. No delivery, deception, makeup or medical information is used, because none is public.
- **Closes roadmap issues #13** (acquisition memo: compare three relievers) **and #8** (20-80 scouting report template and first full report).

*Written 2026-10-13 · Dylan Fanelli · Data: Statcast via Baseball Savant (regular seasons 2024-26) · Outside facts: MLB.com, MLB Trade Rumors (via NewsBeep and Yardbarker), Spotrac, Texas Rangers On SI, Padres On SI, FanSided, Just Baseball, Roundtable, NBC Sports, Yahoo Sports, FanGraphs (each dated below) · Code: `baseball/evaluation/reliever.py`, `baseball/roster/acquisition.py`, `baseball/roster/bullpen_case.py` · Independent review: pending*

![Pitch grades, the reliever market's price per projected win, and fastball velocity by month](figures/2026-bullpen-acquisition-memo.png)

## Decision summary

**To:** General manager · **From:** Dylan Fanelli, baseball operations · **Date:** 2026-10-13 · **Re:** Sign Adrián Morejón; walk away above $70M for four years

**Recommendation.** Make Adrián Morejón the target. Open at four years and $60M with a 2031 club option, and walk away above four years and $70M ($17.5M a year). If the Padres give him a qualifying offer, the walk-away drops to about $63M. Bryan Abreu is the plan if Morejón's price passes the walk-away: two years, open at $18M, walk away above $24M. Pete Fairbanks is a one-year depth bet at $5M or less, not the answer to the need.

**Why.**
1. **The need is late-inning relief against right-handed hitters, and two of the three arms who covered those innings may not be back.**
   - Texas relievers fell from 4th in run value per 100 pitches in 2025 to 24th in 2026 (+0.42 to −0.26), and to 26th in late, close spots (7th inning on, within three runs; Statcast, regular seasons).
   - Jakob Junis (mutual option) and Tyler Alexander (free agent) threw 307 of the bullpen's 1,117 late, close plate appearances (27%; MLB.com free-agent list, Oct. 8, 2026). With Chris Martin and Jalen Beeks, also free agents, it's 397 (36%).
   - The bullpen allowed a .318 xwOBA to right-handed hitters against a league relief average of .306; against lefties it was at the league rate (.315 vs .314).
2. **Morejón projects for the most wins of anyone available: about 2.3 in a high-leverage role (95% range 1.3–3.2), against 1.6 for Abreu and 0.9 for Fairbanks** (derived projection; method below).
   - **The record:** three straight seasons of above-average relief run value (+0.33, +2.11 and +1.39 runs per 100 pitches) across 211 games.
   - **2026:** 24.9% K-BB in both halves, and a 58% ground-ball rate.
   - **Against right-handers:** a 38.8% whiff rate and a .247 xwOBA, from a changeup he throws them 36% of the time.
3. **The price is close to fair and nothing like the engine's ceiling.**
   - **The reliever market's own price line**, fit on the 21 relief signings of 2025-26, puts his projection at $17.1M a year, with a residual SD of $4.2M. The four-year break-even is $17.5M.
   - **His marginal wins over Abreu at that price:** the extra 0.64 wins cost about $8.6M each, about what the roster engine charges for a 1–2-win player ($8.51M).
   - **Two public guesses frame it:** a rival executive's four years and $60M (FanSided, Sept. 9) and The Athletic's Dennis Lin, who wrote he "could attract nine-figure offers" (quoted by Padres On SI, Oct. 10).

**Alternatives.**
- **Abreu (2nd):** the best expected whiff rate of the three in 2027 (32.9%), on half the commitment. In the second half his fastball came back from 95.0 to 96.4 mph and his walk rate fell from 19.7% to 11.3%. That walk-rate drop is borderline (p = 0.058), and walks are the whole risk.
- **Fairbanks (3rd):** his stuff beat his 6.31 ERA (20.3% K-BB, and stuff grades of 65 on the four-seamer and 75 on the cutter). But he made three injured-list trips in 2026 for a recurring nerve issue (Roundtable Sports, Sept. 16), and his September fastball sat 94–95 mph.

**Risk.** Morejón's 2026 rested on two new things: a 1.8 mph velocity gain (net of the league) and a changeup that went from 7% to 23% of his pitches.
- **Velocity:** in the levers study, velocity gains usually held their shape a year later (median 99% kept), but the whiff gains from them were not shown to last.
- **The changeup:** its 56% whiff rate is 15 points above what its physics predict. The edge engine expects about half of such a gap to persist.

**What would change the recommendation.**
- **His price above $70M for four years (or $63M with a qualifying offer), a fifth guaranteed year, or an opt-out:** switch to Abreu.
- **A club budget for relief under about $15M a year:** Abreu.
- **A club medical review** (not public, and not in this memo) on either pitcher.

**Ask.** Approve the offer and the walk-away by the qualifying-offer deadline, a few days after the World Series.
- **The window:** sign before the agreement expires December 1 at 11:59 p.m. ET.
- **Why that date matters:** MLB's lockout memo says a lockout stops all contact and free-agent negotiation with 40-man players (Yahoo Sports and Bleacher Nation, Oct. 8, 2026).

## The three, side by side

| Rank | Player | Bats/throws, 2027 age, 2026 club | OFP | Present role (2026) | Role in 2027 | Risk | Best pitch (present / 2027 grade) | Cost | Projected 2027 wins (role, 95%) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Adrián Morejón | LHP, 28, Padres | 60 | B1, high leverage (42.1 save-situation IP; Padres On SI, Oct. 10) | B1 | Moderate | Changeup / four-seamer (75 / 75) | Free agent. Market line $17.1M a year; public guess 4 years, $60M. QO-eligible (Padres pay the tax) | 2.3 (1.3–3.2) |
| 2 | Bryan Abreu | RHP, 30, Astros | 55 (formula: 60) | B2 setup (15% walks) | B1/B2 if walks return to about 11% | Moderate to high | Slider and four-seamer (60 / 60-65) | Free agent. Market line $12.6M a year; no public projection found. QO-eligible | 1.6 (0.7–2.6) |
| 3 | Pete Fairbanks | RHP, 33, Marlins | 55 (formula: 60) | B2 when active | B2 | High (durability) | Cutter (65 / 75; 86 swings) | Free agent. Market line $7.4M; 2026 deal 1 year, $13M. A QO is very unlikely | 0.9 (0.2–1.7) |

Roles use the model system in the pro-scouting-ops skill (B1 closer or high leverage, B2 setup). The OFP formula is the scouting-report skill's: min(60, 0.55 × best pitch + 0.35 × second + 0.10 × control). Overrides are explained in each report.

**Preference statement.**
- **I prefer Morejón for the late-inning job next to Jacob Latz.** He brings the most wins and the narrowest range: his low-end projection (1.3) is close to Abreu's middle (1.6).
- **Abreu differs in one way:** his bat-missing is intact, and his walks are the question.
- **If the objective is the most wins per dollar over two years** with no long commitment, the answer is Abreu at $12M or less.
- **Morejón moves below Abreu** if his price passes $17.5M a year for four years, or about $15.8M with a qualifying offer attached.

## Where the tools disagree, and how I weighed them

| Question | Tool A says | Tool B says | Weighed |
|---|---|---|---|
| Who misses the most bats next year? | **Edge engine** (validated two-season whiff projection, blends results and stuff): Abreu 32.9%, Morejón 30.9%, Fairbanks 29.9% | **Reliability Atlas** (regressed run value, which counts walks, contact and grounders): Morejón +0.83 runs/100, Abreu +0.37, Fairbanks +0.18 | Both are right about different things. Abreu's gap is walks, which a whiff model can't see. Morejón's edge includes a 55% regressed ground-ball rate (the Atlas puts ground-ball year-to-year persistence at 0.92). I rank on run value and use the whiff projection to establish that Abreu's swing-and-miss survived 2026 |
| What is Morejón worth? | **Roster engine** ($/WAR tiers): about $30.7M a year for four years | **Reliever market line:** $17.5M | The engine's number is a tier cliff. His leverage-credited projection (2.28) crosses the 2-WAR line, where FanGraphs' price jumps from $8.51M to $12.84M a win. At the 1–2 tier the engine says $20.3M. The FanGraphs study also excludes relievers. I price with the market line and read the engine as headroom |
| Did Fairbanks's slider get better? | **Levers study:** his changes are in confirmed directions. Net of the league, about +3.1 in more drop and +1.5 mph more speed gap, implying about +3.6 whiff points | **The stuff model** (levers version, fixed hand mix): expected whiff on the slider fell 5.9 points | The levers study's own finding is that the single expected-whiff change predicts better than lever lists (pooled +7.5 points of squared error). His slider whiff jump (30.8% → 40.5%, 79 swings) is treated as mostly noise. Usage also fell from 40% to 26%, which by itself lowers hitters' familiarity |
| Is Morejón's slider a weakness? | **Stuff grade:** 70 (expected whiff 42%, 98th percentile) | **Present grade:** 50 (30% whiffs on 73 swings) | 73 swings is a small sample. Whiff on sliders reaches r = 0.5 at about 41 swings, so the regressed rate already carries most of the weight, and it's average. I grade it 50 now and 55 for 2027 (the engine's projection). It's a possible lever, not a flaw |
| Abreu's cutter (new in 2026) | **Stuff:** 40 | **Present:** 65 (36% whiffs, 61 swings) | Results beating stuff carries over between seasons (edge engine, r ≈ 0.55), but one season of 61 swings isn't a pattern. The cutter is 11% of his mix, so it doesn't drive the grade |

## 1. The need: why the Rangers, why a reliever

**The club.**
- **2026 finish:** 80-82, four games behind the third AL wild card (White Sox, 84-78; final standings, SportRadar feed, read 2026-10-13).
- **In July** they were a half-game out of the AL West lead, and the bullpen was already called the problem: "Texas cannot realistically expect to contend throughout the remainder of the season with its current bullpen construction" (Eduardo Solano, Roundtable Sports, July 21, 2026).

**The bullpen, 2025 vs. 2026.**
- **Grain:** relief pitches (any pitcher after his team's first) and plate appearances, regular season.
- **Ranks:** 1 = best of 30 clubs.

| Season | Relief PA | K-BB% (rank) | xwOBA (rank) | Run value /100 pitches (rank) | Late, close run value /100 (rank) | Win probability added (rank) |
|---|---|---|---|---|---|---|
| 2025 | 2,404 | 14.8 (12) | .311 (16) | +0.42 (4) | +0.63 (6) | +2.2 (23) |
| 2026 | 2,612 | 12.6 (21) | .316 (22) | −0.26 (24) | −0.27 (26) | +2.7 (16) |

- **Run value vs. win probability:** win probability added ranks the 2026 bullpen 16th, because it depends on when runs were allowed. Run value is the context-neutral measure, and every rate-based column says the same thing: the 2026 relief corps was below average.

**Who threw the late, close innings in 2026**, and who is leaving (status: MLB.com free-agent list, Oct. 8, 2026):

| Pitcher | Throws | Late, close PA | K-BB% | Run value /100 | 2027 status |
|---|---|---|---|---|---|
| Jacob Latz | L | 214 | 26.0 | +1.81 | Arbitration, projected $3.05M (Just Baseball, Oct. 7) |
| Jakob Junis | R | 162 | 9.5 | +0.94 | Mutual option |
| Tyler Alexander | L | 145 | 11.7 | +0.20 | Free agent |
| Peyton Gray | R | 110 | 18.7 | −0.37 | Under control |
| Cole Winn | R | 101 | 16.1 | −0.80 | Under control |
| Robby Ahlstrom | L | 65 | 13.7 | −0.66 | Under control |

- **The job:** one right-handed-hitter-capable arm for the seventh and eighth innings in front of, or alongside, Latz.
- **The platoon gap:** Texas relievers allowed a .318 xwOBA to right-handed hitters against .306 for the league's relievers, and .315 vs .314 to lefties.

**Money and the luxury tax.**

| Item | Value | Source |
|---|---|---|
| 2025 CBT payroll | $241.4M, third straight season over | CBS Sports, Dec. 20, 2025; AP |
| 2026 CBT payroll | $206.0M (Spotrac page, no as-of date); $210M (Spotrac via SI, Oct. 2) | Spotrac, read Oct. 13, 2026; Matt Postins, Texas Rangers On SI, Oct. 2, 2026 |
| 2027 committed (tax) | $142.1M to eight players, including mutual options for Pederson, Higashioka and Junis | Postins (SI), Oct. 2, 2026 |
| 2027 arbitration class | $38.2M for ten players (Gore $8.9M, Burger, Jung, Duran, Langford, Latz $3.05M and others) | Zach Cioffi, Just Baseball, Oct. 7, 2026 (his own comparables) |
| 2027 payroll before additions | about $191M (derived: the two lines above, plus 14 roster spots at the 2026 minimum of $0.78M; benefits and the mutual options make this approximate) | This memo |
| QO status for signing | "Other" (neither a tax payor nor a revenue-sharing recipient): a qualified signing costs the 2nd-highest 2027 pick and $500K of international pool | MLB Trade Rumors via NewsBeep, Oct. 12, 2026 |

- **The reset:** being under in 2026 resets the Rangers' tax clock.
  - If a 2027 threshold exists and they cross it, they pay as first-time payors: 20% on the overage instead of 50% (`cbt_bill`).
  - At about $191M, none of these three adds a dollar of tax. At a $244M line, an $18M addition costs tax only once the rest of the payroll passes $226M.
- **The budget:** Chris Young will know his budget before free agency opens, and Ray Davis's approval decides how active he can be (Postins, SI, Oct. 2). The rotation competes for the same dollars.
  - That is why the walk-away prices matter more than the tax.

## 2. The pool and why these three

**The pool.** Every 2026-27 free-agent reliever with 150+ PA in 2026 (MLB.com list, Oct. 8, 2026; no club, player or mutual option listed).

| Reliever | 2027 age | 2026 G | K-BB% | Run value /100 (2026) | Regressed, 2024-26 | Projected wins, role | 2027 whiff% (engine) |
|---|---|---|---|---|---|---|---|
| **Adrián Morejón** | 28 | 76 | 24.9 | +1.39 | +0.83 | **2.28** | 30.9 |
| Alex Vesia | 31 | 72 | 19.2 | +1.22 | +0.72 | 1.91 | 30.1 |
| Raisel Iglesias | 37 | 59 | 20.2 | +1.21 | +0.83 | 1.86 | 27.5 |
| David Bednar | 32 | 64 | 20.9 | +1.23 | +0.51 | 1.70 | 28.9 |
| **Bryan Abreu** | 30 | 66 | 14.6 | +0.27 | +0.37 | **1.64** | **32.9** |
| Steven Okert | 35 | 68 | 20.7 | +1.25 | +0.67 | 1.64 | 30.3 |
| Jacob Webb | 33 | 68 | 16.9 | −0.03 | +0.28 | 1.32 | 30.7 |
| Gregory Soto | 32 | 69 | 18.4 | +0.53 | +0.09 | 1.08 | 26.2 |
| Kevin Ginkel | 33 | 74 | 20.1 | +0.39 | +0.10 | 0.95 | 28.9 |
| **Pete Fairbanks** | 33 | 46 | 20.3 | −0.54 | +0.18 | **0.93** | 29.9 |

**Why these three.** They make the comparison hard in three different ways.
- **The best and youngest arm, at the highest price:** Morejón.
- **A buy-low whose bat-missing is intact and whose problem has a measured, partly reversed cause:** Abreu.
- **A cheap arm whose stuff beats his results, with a public durability flag:** Fairbanks.

**Set aside:**
- **Bednar:** the market's other closer name.
  - **Velocity:** his four-seamer lost 0.86 mph net of the league (97.1 → 96.1), with 79 rpm less spin.
  - **What the levers study says:** both changes go in directions it confirms cost whiffs (about −1.6 points each, as associations).
  - **The rest:** he's 32, and his projection (1.70) trails Morejón's at a likely similar price.
- **Iglesias:** 37.
- **Vesia:** a left-handed alternative to Morejón (1.91, at 31), worth a call if Morejón's price runs.
- **Club options:** Andrés Muñoz and Garrett Whitlock have 2027 club options, so they aren't counted as free agents (MLB.com, Oct. 8). Their option decisions were not checked.

## 3. Scouting reports (data-informed, not a live look)

**How to read the grades.** Each pitch gets three 20-80 grades, against every MLB pitch of the same Statcast type in 2026 with 50+ swings:
- **Present:** 2026 whiff per swing, regressed with that pitch type's Atlas constant.
- **2027:** the edge engine's validated next-season whiff projection.
- **Stuff:** expected whiff from the physics alone.

The mapping is 50 + 10z of the percentile, to the nearest 5 (Method).
- **Control:** graded from walk rate on the scouting-report skill's anchors.
- **Limits:** whiff is one job of a pitch, so sinkers and strike-throwing cutters are undergraded, and they are compared only within their own type. The reference pool includes starters, whose whiff rates run lower than a one-inning reliever's. These grades describe the pitch in a relief role.

---

### Adrián Morejón · LHP · Padres · born Feb. 27, 1999 (2027 age 28) · free agent

**Basis:** data only (Statcast 2024-26 regular season), not a live look.
- **2026 public line:** 76 G, 86.0 IP, 107 K, $3.9M salary (Padres On SI, Oct. 10, 2026).
- **ERA:** 2.86 through Sept. 9 (FanSided, Sept. 9).
- **Statcast counts:** 345 PA and 107 K, which matches the strikeout total.

**Arsenal (2026)**

| Pitch | Usage (vs LHH / RHH) | Velo | IVB / arm-side HB (in) | Whiff% (swings) | Present | 2027 | Stuff | Notes |
|---|---|---|---|---|---|---|---|---|
| Sinker | 47.6% (55 / 43) | 99.5 | 9.2 / 16.0 | 19.3 (311) | 65 | 60 | 65 | His primary pitch. 58% ground balls overall |
| Changeup | 23.1% (2 / 36) | 92.1 | −1.1 / 10.7 | 56.0 (182) | 75 | 75 | 70 | 7% of pitches in 2025, 23% in 2026; almost only to RHH |
| Slider | 15.2% (27 / 8) | 89.4 | −0.5 / −5.7 | 29.9 (77) | 50 | 55 | 70 | Results trail the physics (small sample) |
| Four-seamer | 14.2% (16 / 13) | 99.3 | 15.2 / 6.0 | 42.3 (123) | 75 | 75 | 70 | A carry four-seamer at 99 |
| Control | BB 6.1% | | | | 60 | 60 | | 5.1% vs LHH, 6.7% vs RHH |

**Performance, regressed** (Atlas constants; estimate and 95% interval for his 2026 true level; league = all pitchers 2026):

| Metric | Observed (n) | Regressed (95%) | Next season (Atlas) |
|---|---|---|---|
| Whiff per swing | 34.2% (676 swings) | 32.8% (29.6–36.1) | 32.1% |
| Chase | 38.6% | 36.0% (33.1–38.9) | 35.2% |
| xwOBA on contact | .300 (212 BIP) | .347 (.323–.372) | not given (no year-to-year signal) |
| Ground-ball % | 58.0% | 54.8% (48.8–60.7) | 53.8% |
| Run value /100 | +1.39 (1,318 pitches) | +0.56 (−0.21 to +1.33) | not given (persistence too imprecise) |

**Stuff vs. results (edge engine; swing-weighted expected whiff, then the gap):**
- 2024: 26.5% expected, −0.4 gap.
- 2025: 24.2% expected, −2.5 gap.
- 2026: 28.3% expected, +5.8 gap.
- **The read:** his stuff rose in 2026 and his results rose more. Before 2026 his results matched or trailed his physics.
- **Where the 2026 gap sits:** the changeup (+15.1) and four-seamer (+13.6) beat their physics, and the slider (−12.0) trailed it.
- **The changeup regressed:** 51.4% (45.2–57.6) for 2026 and 48.1% for next season. The edge engine projects 48.8%, still the 99th percentile of changeups.

**Velocity (league baseline):**
- **The gain:** sinker 97.7 → 99.5 mph, +1.79. The league's returning sinkers moved −0.05, so the gain is +1.85 net.
- **Precision:** the regressed level is 99.5 (99.3–99.7) on 76 games. Physics metrics are regressed by games.
- **Through the season:** it held all year. Aug–Sep minus Mar–May: +0.03, against +0.25 for the league's relievers.
- **Not cameras:** the sinker gain is his, because the league didn't move. The same rise showed on his four-seamer (96.5 → 99.3) and slider (87.5 → 89.4).

**Usage and platoon:**
- **Against right-handers:** a reverse-looking split, because he attacks them with the changeup. 208 PA, 32.7% K, .247 xwOBA, 38.8% whiffs (35.8% regressed).
- **Against left-handers:** 137 PA, 28.5% K, .221 xwOBA, with sinker and slider.
- **The three-batter minimum doesn't bind him.**

**Durability and workload (game logs; no injury inference):**
- **Appearances:** 60, 75 and 76 in 2024-26.
- **2026 workload:** 18 back-to-backs, 25 outings of four or more outs, and 12 outings that completed three in four days. His longest gap between outings was 5 days.
- **Velocity on no rest:** sinker −0.11 mph on back-to-back days.
- **Leverage proxy:** 1.61 (his mean win-probability swing per PA over the league relief mean).

**Pitch design (levers study; association, not a forecast):**
- **Slider changes:** +54 rpm of spin (confirmed lever, implied +0.8 whiff points) and a slot 2.2° lower (confirmed in the other direction, implied −0.9).
- **Sinker velocity:** "not detected" for sinkers.
- **The open lever is the slider.** Its physics grade (70) is far ahead of its results (50), and the study can't say which change would close that gap.

**Familiarity:**
- **Low exposure:** as a reliever, hitters had seen almost none of his pitches earlier in the game (0.00 same-type pitches in earlier PAs) and 0.30 changeups in earlier games per changeup.
- **The cost:** at the league study's rates that's about −0.2 whiff points.
- **As a starter:** the changeup's exposure would rise to about 0.7 same-type pitches in earlier PAs (23% usage × 3.13 pitches seen per pitch). The cost would rise to about −1.8 points. That is one measured reason to value him as a reliever, not a starter.

**OFP 60 · Role: B1 now and in 2027 · Risk: moderate.**
- **The formula:** 0.55 × 75 + 0.35 × 75 + 0.10 × 60 = 73.5, capped at 60.
- **The risk** rests on the velocity gain and the changeup's share of his results both holding.
- **Summary:** a durable, ground-ball, platoon-neutral late-inning lefty at 28, coming off his best season, with stuff that has climbed for two years.
- **The biggest question:** how much of a 15-point changeup gap survives a second look from the league.
- **Action:** pref list #1.

---

### Bryan Abreu · RHP · Astros · born Apr. 22, 1997 (2027 age 30) · free agent

**Basis:** data only (Statcast 2024-26 regular season), not a live look.
- **Public context:** a 14.73 ERA and a walk rate four times his 2025 rate on April 18.
- **His own explanation:** "a little bit of lack of confidence in my delivery" (Brian McTaggart, MLB.com, Apr. 18, 2026).
- **Free-agent status:** "slated to become a free agent at the end of the 2026 season" (MLB Trade Rumors via Yardbarker, Mar. 14, 2026).

**Arsenal (2026)**

| Pitch | Usage (vs LHH / RHH) | Velo | IVB / arm-side HB (in) | Whiff% (swings) | Present | 2027 | Stuff | Notes |
|---|---|---|---|---|---|---|---|---|
| Slider | 44.5% (44 / 45) | 86.5 | −5.4 / −6.7 | 39.0 (205) | 60 | 60 | 60 | 46% whiffs in 2025 |
| Four-seamer | 44.0% (40 / 49) | 95.7 | 16.7 / 6.1 | 27.8 (194) | 60 | 65 | 55 | 36% whiffs at 97.3 mph in 2025 |
| Cutter | 11.4% (16 / 6) | 93.0 | 11.3 / −0.1 | 36.1 (61) | 65 | 65 | 40 | New in 2026; mostly to LHH |
| Control | BB 15.3% (H1 19.7%, H2 11.3%) | | | | 20 | 40 | | 2024: 9.8%, 2025: 10.5% |

**Performance, regressed:**

| Metric | Observed (n) | Regressed (95%) | Next season |
|---|---|---|---|
| Whiff per swing | 33.8% (460) | 32.0% (28.2–35.8) | 31.4% |
| Chase | 27.6% | 28.6% (25.6–31.6) | 28.8% |
| xwOBA on contact | .363 | .362 (.336–.388) | not given |
| Ground-ball % | 41.5% | 41.8% | 41.8% |
| Run value /100 | +0.27 (1,093) | +0.09 (−0.70 to +0.89) | not given |

**The two halves of 2026** (through June / after):

| | G | PA | BB% | K-BB% | xwOBA | Run value /100 | Four-seam velo (games) | Four-seam spin |
|---|---|---|---|---|---|---|---|---|
| First half | 31 | 127 | 19.7 | 7.1 | .365 | −0.97 | 95.0 (30) | 2,165 |
| Second half | 35 | 141 | 11.3 | 21.3 | .264 | +1.35 | 96.4 (35) | 2,295 |
| 2025 | 70 | 296 | 10.5 | 25.0 | .289 | +1.18 | 97.3 | 2,314 |

- **Walk rate:** the drop (25 of 127 to 16 of 141) has p = 0.058. That is borderline under the repo's standard, not confirmed.
- **Velocity:** the gain is not noise.
  - **Regressed by games:** 95.0 (94.7–95.3) in the first half and 96.4 (96.2–96.7) in the second.
  - **Against normal movement:** a true pitcher's fastball moves about 0.55 mph between halves (Atlas), so +1.4 is about 2.6 times that.
  - **For the full season:** late minus early was +1.61, against +0.25 for the league's relievers.
- **Still short of 2025:** the second-half four-seamer (96.4) was 0.9 mph below his 2025 level.

**Stuff vs. results:**
- 2024: 33.1% expected, +0.7 gap.
- 2025: 33.0% expected, +8.4 gap.
- 2026: 28.6% expected, +5.3 gap.
- **The read:** results beat his physics two years running, and that gap is a trait that carries over (edge engine, r ≈ 0.55).
- **The engine's 2027 whiff projection, 32.9%,** is the best of the three.

**Velocity (league baseline):** four-seamer 97.3 → 95.7 for the season, −1.49 net of the league (−0.10).

**Usage and platoon:**
- **Against right-handers:** 125 PA, 14.4% BB, .306 xwOBA, 36.5% whiffs.
- **Against left-handers:** 143 PA, 16.1% BB, .317. He walked lefties more.
- **The cutter** (16% to lefties) is his new answer to them.

**Durability and workload:**
- **Appearances:** 78, 70 and 66.
- **2026 workload:** 13 back-to-backs (four-seamer −0.32 mph on no rest), 10 multi-inning outings, and a longest gap of 7 days.
- **Leverage proxy:** 1.36. He was used below closer leverage in 2026.

**Pitch design (levers study, 2025 → 2026, net of the league, beyond the noise threshold):**

| Change | Size | Study's payoff per unit | Evidence | Implied whiff points |
|---|---|---|---|---|
| Four-seam velocity | −1.51 mph | +1.81 per mph | Confirmed; placebo fails (selection or recovery not ruled out) | −2.7 |
| Four-seam spin | −72 rpm | +2.09 per 100 rpm | Confirmed | −1.5 |
| Slider speed gap | −1.58 mph (the fastball slowed) | +1.06 per mph | Confirmed | −1.7 |
| Slider spin | −82 rpm | +1.41 per 100 rpm | Confirmed; not stable across season pairs | −1.2 |

- **The lever is to get the four-seamer back to 97.**
  - **Half of it already happened:** second half 96.4 and 2,295 rpm, against 97.3 and 2,314 in 2025.
  - **The slider gap would follow:** it is measured from the fastball, so it returns with the velocity.
- **The study's caveat cuts both ways.**
  - **For the bet:** the velocity association fails its placebo, which means "pitchers whose velocity comes back get their whiffs back." That is exactly the bet here.
  - **Against it:** the same study found velocity-driven whiff gains not shown to last a second season (borderline).
- **The walk rate is the bigger risk.** The study doesn't model command.
  - **What the data say:** the walk spike came with the velocity loss and the delivery he described, and partly reversed with them.
  - **What they can't say:** whether it will hold.

**Familiarity:** low, as for any reliever: −0.27 whiff points on the slider from earlier-game exposure, −0.20 on the four-seamer.

**OFP 55 (formula 60, overridden) · Role: B2 now; B1/B2 in 2027 if walks stay near 11% · Risk: moderate to high.**
- **Why the override:** the formula gives control 10% weight. A 15% walk rate costs runs that whiff-based pitch grades can't see, and a closer can't carry it.
- **The condition for B1:** at his 2024-25 walk rate (about 10%, a 40 control grade), his 2024-25 run values (+0.27, +1.18) say B1 is reachable.
- **Action:** pref list #2, the plan if Morejón's price passes the walk-away.

---

### Pete Fairbanks · RHP · Marlins · born Dec. 16, 1993 (2027 age 33) · free agent

**Basis:** data only (Statcast 2024-26 regular season), not a live look. Public line and health record:
- **2026:** 6.31 ERA, 41.1 IP, 57 K, 21 BB, 19 saves in 23 chances. One year, $13M from the Marlins. Three injured-list placements this season, each "related to the nerve issue" (right median nerve irritation; Brandon Liguori, Roundtable Sports, Sept. 16, 2026; NBC Sports, Sept. 15).
- **Not inferred here:** nothing about his health beyond those reports.
- **Statcast counts:** 57 K matches; the data show 20 walks against the official 21.

**Arsenal (2026)**

| Pitch | Usage (vs LHH / RHH) | Velo | IVB / arm-side HB (in) | Whiff% (swings) | Present | 2027 | Stuff | Notes |
|---|---|---|---|---|---|---|---|---|
| Four-seamer | 48.7% (49 / 49) | 97.2 | 18.1 / 1.6 | 27.4 (175) | 60 | 60 | 65 | Ride +1.0 in net of the league |
| Slider | 26.4% (32 / 19) | 83.7 | −8.5 / −6.0 | 40.5 (79) | 60 | 55 | 40 | Physics says worse; results say better |
| Cutter | 23.1% (16 / 32) | 89.6 | 3.3 / −5.6 | 34.9 (86) | 65 | 75 | 75 | 4% of pitches in 2025, 23% in 2026 |
| Control | BB 11.0% | | | | 35 | 40 | | 7.4% in 2025 |

**Performance, regressed:**

| Metric | Observed (n) | Regressed (95%) | Next season |
|---|---|---|---|
| Whiff per swing | 31.9% (340) | 30.1% (25.8–34.4) | 29.6% |
| xwOBA on contact | .417 (102 BIP) | .369 (.342–.395) | not given |
| Hard-hit % | 43.6% | 40.0% (35.0–45.0) | 39.9% |
| Ground-ball % | 24.5% | 30.8% (23.1–38.5) | 31.7% |
| Run value /100 | −0.54 (766) | −0.16 (−1.00 to +0.68) | not given |

- **This is the "stuff beats results" case.** The 6.31 ERA came mostly from contact.
  - **The contact number is the least trustworthy:** pitchers' xwOBA on contact shows no within-season signal at the pitcher level in the Atlas (r = 0.15 at 181 balls in play), so it regresses from .417 most of the way to the league.
  - **What holds:** his swing-and-miss and K-BB (20.3%) do.
  - **Fly balls:** his 31% regressed ground-ball rate keeps hard contact costly.
- **Stuff vs. results:**
  - 2024: 26.8% expected, −6.0 gap.
  - 2025: 27.8% expected, −2.2 gap.
  - 2026: 30.8% expected, +1.6 gap.
  - **The read:** his physics improved every year, mostly through the cutter. Results trailed his stuff in 2024-25 and caught up in 2026.

**Velocity:**
- **Season:** four-seamer 97.2, unchanged from 2025 net of the league.
- **Late season:** −0.80 mph against the league relievers' +0.25.
- **September:** 2 outings and 10 fastballs at 94.4 and 95.4 mph, the second ending after six pitches when he left with the nerve irritation (Roundtable).

**Usage and platoon:**
- **A real split:** right-handers .265 xwOBA (78 PA, 38.7% whiffs); left-handers .365 (104 PA, 26.3%).
- **What it means for the role:** he needs to be deployed against right-handed-heavy pockets.

**Durability and workload:**
- **2026:** 46 games, zero multi-inning outings, 8 back-to-backs, and a 19-day gap twice (IL stints).
- **Earlier:** 46 and 61 games in 2024-25.

**Pitch design (2025 → 2026):**
- **The levers study's direction:** slider drop +3.1 in (confirmed lever, implied +2.0), slider speed gap +1.5 mph (confirmed, +1.6) and four-seam ride +1.0 in (confirmed, +0.8).
- **The physics model's direction:** it scores his slider 5.9 expected-whiff points worse (see "Where the tools disagree").
- **The read:** the cutter is the change that shows up in both tools.

**Familiarity:** low: −0.10 to −0.13 whiff points per group.

**OFP 55 (formula 60, overridden) · Role: B2 · Risk: high (durability).**
- **Why the override:** the cutter's 65 present grade rests on 86 swings in its first season, and an 11% walk rate keeps him off the closer line.
- **Action:** a one-year depth bet only, priced at or below his market break-even and subject to the club's medical review. Pref list #3.

## 4. Cost and value

**The projection.**
- **Method:** derived, not published. Relief run value per 100 pitches, 2024-26 weighted 5/4/3, regressed with the Atlas constant (M = 1,932 pitches) toward the league relief mean (+0.08).
- **Replacement:** set at fringe arms' −0.70 (pitcher-seasons with 50–399 relief pitches, 2024-26).
- **Wins:** 10 runs per win.
- **Role:** × (1 + 1.6) / 2 for a leverage index of 1.6. All three candidates' leverage proxies were 1.36–1.63.

| | Morejón | Abreu | Fairbanks |
|---|---|---|---|
| Regressed run value /100 (95%) | +0.83 (+0.19 to +1.47) | +0.37 (−0.26 to +1.01) | +0.18 (−0.52 to +0.88) |
| Relief pitches, weighted | 1,148 | 1,177 | 811 |
| Wins, no leverage | 1.75 | 1.26 | 0.71 |
| Wins, high-leverage role (95%) | **2.28 (1.32–3.23)** | **1.64 (0.67–2.61)** | **0.93 (0.19–1.67)** |

**What the reliever market paid in 2025-26.**
- **The data:** 21 relief signings with their terms (NBC Sports/Yahoo free-agent tracker, D.J. Short, Feb. 12, 2026), projected the same way from 2024-25 data.
- **The fit:** AAV = $0.77M + $9.33M × wins (no leverage). R² is 0.27, the residual SD is $4.2M, and the median is $10.3M per projected win.
- **What the low R² means:** it is itself a finding. The market priced relievers loosely on run value. Saves, velocity and reputation move prices this projection doesn't see. So a ±$4M band around the line is normal, not mispricing.
- **The examples:** Díaz 3 years/$69M ($23M) at a 1.32-win projection; Williams 3/$51M at 0.98; Suarez 3/$45M at 1.40; Fairbanks 1/$13M at 0.91.

**Projected contracts.**

| | Public projection | Derived (market line ± 1 SD) | Likely shape |
|---|---|---|---|
| Morejón | 4 years, $60M, from a rival executive (Pat Ragazzo, FanSided/Friars on Base, Sept. 9). "Could attract nine-figure offers" (Dennis Lin, The Athletic, quoted by Padres On SI, Oct. 10). That article suggests the Padres might move him to the rotation | $17.1M a year ($12.9–21.3M) | 4-5 years. Starter interest is the upside risk to price |
| Abreu | None found as of Oct. 13 | $12.6M ($8.3–16.8M) | 2-3 years; the first half of 2026 will pull offers down |
| Fairbanks | None found | $7.4M ($3.2–11.6M) | 1 year, probably with incentives |

**Surplus** (present value at 10%; the market line and win prices grow 3% a year; relief value falls 10% a year from age 31; all assumptions are in `acquisition.py`):

| Contract | PV of salary | Value at the market line | Surplus | Value at the engine's $/WAR (role wins) | Surplus |
|---|---|---|---|---|---|
| Morejón 4 years, $60M (opening) | $52.3M | $60.9M | +$8.6M | $107.0M | +$54.7M |
| Morejón 4 years, $70M (walk-away) | $61.0M | $60.9M | −$0.2M | $107.0M | +$45.9M |
| Morejón 5 years, $100M (the "nine-figure" case) | $83.4M | $71.6M | −$11.8M | $119.4M | +$36.0M |
| Abreu 2 years, $18M (opening) | $17.2M | $23.2M | +$6.0M | $26.5M | +$9.3M |
| Abreu 2 years, $24M (walk-away) | $22.9M | $23.2M | +$0.3M | $26.5M | +$3.6M |
| Fairbanks 1 year, $5M | $5.0M | $6.8M | +$1.8M | $5.8M | +$0.8M |

**Break-even AAV.**

| Pitcher | Market line | Engine, 2+ WAR tier | Engine, 1–2 tier |
|---|---|---|---|
| Morejón (4 years) | $17.5M | $30.7M | $20.3M |
| Abreu (2 years) | $12.2M | $13.9M | — |
| Fairbanks (1 year) | $6.8M | $5.8M | — |

- **The walk-away for Morejón is $17.5M.** Three methods land within $0.2M:
  - **The market line:** $17.5M.
  - **The price at which his extra 0.64 wins over Abreu cost the engine's 1–2-win rate:** $17.7M (Abreu at his own break-even of $12.15M, plus 0.64 × $8.51M × 1.03).
  - **The rounding:** four years and $70M.

**The qualifying offer.**
- **The rules:** a qualifying offer is the 2022-26 agreement's ($22.025M in 2026; the 2027 figure is set in early November).
  - **Morejón:** he spent all of 2026 with the Padres and has never received one, so he is eligible. The Padres paid tax in 2026, so losing him earns them only a pick after Round 4. Whether they make the offer is unknown. Friars on Base (Sept. 9) said they "may."
  - **Abreu:** eligible on the same facts, though an offer after his 2026 is less likely.
- **The Rangers' cost:** their 2nd-highest 2027 pick plus $0.5M of pool.
  - **The pick:** a 2nd-rounder near No. 55. That number is an estimate from their 80-82 finish.
  - **Its value:** about $5.3M in 2019 dollars (Craig Edwards, FanGraphs, Apr. 5, 2019).
  - **The total:** about $5.8M, which cuts Morejón's walk-away to about $15.8M a year (about $63M for four).
- **Both sides proposed ending the QO** in the 2026 talks (CBA skill reference notes; see the roster memo). A signing before December 1 is under the current rules. A signing after a lockout could fall under rules without it, which isn't known.

**The luxury tax.**

| Pre-signing 2027 CBT payroll | +$7M | +$12M | +$18M |
|---|---|---|---|
| ~$191M (this memo's estimate) | $0 | $0 | $0 |
| $235M | $0 | $0.6M | $1.8M |
| $244M | $1.4M | $2.4M | $3.6M |

- **The threshold:** $244M, the 2026 line, used as an assumption. The 2022-26 agreement sets no 2027 line; MLB's June proposal is a $245.3M salary cap, a different system.
- **The rate:** first-time payor, 20%.

**Timing and the labor clock.**
- **Current rules run the window.** Qualifying-offer decisions come a few days after the World Series, and the agreement expires December 1 at 11:59 p.m. ET.
- **A lockout freezes free agency for 40-man players** (MLB's memo to clubs; Yahoo Sports and Bleacher Nation, Oct. 8). The window to sign under known rules is about three to four weeks of November.
- **What that means:**
  - **Morejón:** if he isn't qualified, move early, before a bidder treating him as a starter sets the price. If he is qualified, the pick's $5.8M is a known cost. Waiting through a lockout to see whether the QO survives trades that for not knowing when, or whether, he can be signed.
  - **Abreu:** his price should fall the longer the market waits, so he is the natural late option. Under a lockout, "late" may mean March.
  - **The contract:** a signing bonus paid before December 1 is worth more to the player than it costs the club, because salaries stop in a stoppage and a bonus doesn't (the Skenes memo's logic). Use it to win a close bid instead of raising the AAV.

## 5. The recommendation

1. **Pursue Morejón.**
   - **Open:** four years, $60M (2027-30), with a 2031 club option. Put part of it in a signing bonus paid before December 1.
   - **Walk away:** above four years and $70M, and above about $63M if he carries a qualifying offer. No fifth guaranteed year, no opt-out.
2. **If his price passes the walk-away, sign Abreu.**
   - **Open:** two years, $18M, with a 2029 club option.
   - **Walk away:** above two years and $24M.
   - **The condition:** the second half of 2026 is the bet. It is borderline evidence (p = 0.058 on walks), so price it like one.
3. **Fairbanks:** one year at $5M or less with incentives, only after the club's own medical review. He doesn't replace either of the first two.

**What changes the call.**
- **Morejón's market:** any bid at starter money (five years, nine figures) puts him above every one of this memo's value lines except the engine's, and the engine's number is a tier artifact.
- **The budget:** if the relief budget is under about $15M a year, Abreu becomes the first call.
- **A qualifying offer:** it moves Morejón's walk-away down about $7M in total.
- **New information:** the club's medical review of any of the three, or a winter look at Abreu's delivery (team data, outside this public memo).
- **The labor outcome:** if a lockout starts December 2 with Morejón unsigned, the decision moves to whenever free agency reopens, under rules nobody has yet.

## Method

**Grain.** Pitch rows from the sequence copy (regular seasons 2024-26). Lines are pitcher × season, grades are pitcher × pitch type, the market fit is one row per signing, and the team table is one row per club.

**The comparison table** (`reliever.compare_relievers(ids, season)`): every number in section 3, for any list of pitcher ids.
- **Flags:** set once on every pitch (swing, whiff, chase, BIP, PA, outs).
- **Relief:** any pitcher after his team's first pitcher of the game.
- **Rates:** from summed counts.
- **IP:** from event outs, so it is approximate. Baserunning outs other than caught stealing and pickoffs aren't counted. Morejón shows 84.2 against an official 86.0.

**The 20-80 mapping** (`grade_from_percentile`, tested).
- **The formula:** grade = 50 + 10z, where z is the normal quantile of the pitch's mid-rank percentile among MLB pitches of the same type with 50+ swings that season. Rounded to the nearest 5, clamped to 20-80.
- **The scale:** the scouting scale's 10 points per SD (the 20-80 convention).
- **The anchors:** percentile 84 → 60, 98 → 70, 16 → 40, 2 → 30.
- **Present** uses the regressed whiff rate (pitch-type M), **2027** the engine's projection, **stuff** the expected whiff.
- **Control** (`control_grade`) interpolates my walk-rate anchors: 4% → 75, 5.75% → 60, 8% → 50, 10.5% → 40, 12% → 30, 15% → 20.
- **OFP** is my reliever formula, and overrides are stated.
- **Limits:** whiff-only; the reference includes starters; no command within the zone, deception or delivery.

**Regression.** `reliability.regress` with the shipped 2024-26 constants.
- **Physics:** velocity is regressed by games.
- **Next season:** given only where the Atlas measured year-to-year persistence (not for run value or xwOBA on contact).

**Velocity baseline.**
- **Season over season:** his change minus the median change of every pitcher with 100+ pitches of that type in both seasons.
- **In season:** Aug–Sep minus Mar–May (game means), against the median of the same for 199 relievers with 5+ outings in each window.

**Familiarity** (`familiarity_load`): exposures from `edge.familiarity.exposures`, priced with the league study's per-pitch costs for earlier PAs today and earlier games this season. Those costs are contrasts against an earlier pitch of another type, so the totals are approximate.

**Pitch design** (`lever_read`): the levers study's 2025 → 2026 pairs, net of the league, flagged beyond each lever's noise threshold, with the study's per-unit payoff and evidence label. The implied whiff change is the league association, not a forecast for the pitcher.

**Money** (`roster/acquisition.py`): the projection, replacement level, market line, contract values and break-evens described in section 4.
- **Engine values:** `money.dollars_per_war`.
- **QO:** `money.qualifying_offer`.
- **Tax:** `money.tax_cost_of_signing`.

## What this doesn't show

- **No live look, no video, no medical review.** The grades are data-informed, and a scout's look at Abreu's delivery or Fairbanks's arm action could move either report.
- **Run value's year-to-year persistence is unmeasured** (the Atlas found it too imprecise). The projection treats the regressed rate as next year's, so its intervals understate the uncertainty.
- **The market line is one winter, 21 signings, R² 0.27.** The prices it implies are a band, not a point.
- **Unverified or estimated:**
  - the Rangers' 2027 payroll (derived)
  - their 2nd-highest pick number (No. 55, estimated)
  - pick value in 2019 dollars (not inflated)
  - 2027 qualifying-offer amounts and decisions (not yet made)
  - whether any 2027 tax threshold exists
  - Muñoz's and Whitlock's option decisions
  - Abreu's and Fairbanks's market prices (no public projection found)
  - Dennis Lin's quote (read secondhand)
- **One source error found:** Friars on Base (Sept. 9) gives Robert Suarez's Braves deal as four years and $60M. The NBC/Yahoo tracker (Feb. 12) lists three years and $45M, and the tracker is used here.
- **No causal claims.** The lever effects are associations from an observational study. That Abreu's velocity and walks recovered together is a pattern in the data, not proof the delivery is fixed.
- **No club-specific win value.** The Rangers' revenue per marginal win near the wild-card line isn't modeled.

## Reproduce
```bash
uv run python -m baseball.roster.bullpen_case        # every number in this memo, and the figure
uv run pytest tests/test_reliever.py tests/test_acquisition.py
# once integrated: uv run bb compare-relievers 2026 670970 650556 664126
```

## Sources
- **Pitch data:** Statcast, MLB Advanced Media, via [Baseball Savant](https://baseballsavant.mlb.com/) (regular seasons 2024-26).
- **Names and ids:** the Chadwick Bureau register, via `bb people`.
- **Free-agent class:** MLB.com, "All of the 2026-2027 free agents, position by position" (Oct. 8, 2026).
- **Standings:** final 2026 regular season (SportRadar feed, read Oct. 13, 2026).
- **Rangers:**
  - Matt Postins, "How Much Can the Texas Rangers Actually Spend This Offseason?", Texas Rangers On SI (Oct. 2, 2026)
  - Spotrac, Rangers 2026 tax page (read Oct. 13, 2026)
  - Zach Cioffi, "Texas Rangers Arbitration Projections and Tender Decisions", Just Baseball (Oct. 7, 2026)
  - Eduardo Solano, Roundtable Sports (July 21, 2026)
  - 2025 CBT bill: CBS Sports (Mike Axisa, Dec. 20, 2025)
- **Qualifying offer tiers:** MLB Trade Rumors, "Each Team's Penalty For Signing A Qualifying Offer-Rejecting Free Agent," republished by NewsBeep (Oct. 12, 2026). QO rules: MLB.com glossary.
- **Morejón:**
  - J.P. Hoornstra, Padres On SI via Yahoo Sports (Oct. 10, 2026)
  - Pat Ragazzo, FanSided/Friars on Base (Sept. 9, 2026)
- **Abreu:**
  - Brian McTaggart, MLB.com (Apr. 18, 2026)
  - Mark Polishuk, MLB Trade Rumors via Yardbarker (Mar. 14, 2026)
- **Fairbanks:**
  - Brandon Liguori, Roundtable Sports (Sept. 16, 2026)
  - NBC Sports player news (Sept. 15, 2026)
  - Jon Paul Hoornstra, Newsweek (May 28, 2026)
- **2025-26 reliever contracts:** D.J. Short, MLB free agent tracker, NBC Sports/Yahoo Sports (Feb. 12, 2026).
- **Draft-pick value:** Craig Edwards, "An Update on How to Value Draft Picks," FanGraphs (Apr. 5, 2019).
- **$/WAR and valuation:** FanGraphs, Ben Clemens (Feb. 24 and July 2, 2026), via `baseball/roster/money.py`.
- **Labor:**
  - MLB's lockout memo: Yahoo Sports (Chris Cwik) and Bleacher Nation (Brett Taylor), Oct. 8, 2026
  - The rest of the labor background: [the roster and CBA memo](2026-roster-cba-engine.md)
- **This repo's studies:** [Reliability Atlas](2026-reliability-atlas.md), [pitch familiarity](2026-league-pitch-familiarity.md), [pitch-design levers](2026-pitch-design-levers.md), the edge engine (LOG.md, 2026-10-12).
