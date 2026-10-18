# The 2027 prediction log: fifteen dated calls, scored after the season

*Made 2026-10-18; Dylan Fanelli; scored after the 2027 season; Code: `baseball/predictions.py`*

## Summary
- **What this is:** fifteen calls on the 2026-27 free-agent market, 2027 performance and the 2026 draft class, each with a probability, written down before anything resolved. The file of record is `predictions/2027.yaml`; the calls section of this page is rendered from it with `update_report()` in `baseball/predictions.py`.
- **Why:** a front office is paid to be right more often than the market about prices, performance and amateurs. A dated, public log with numbers attached is how to show that over time: nobody can go back and edit the probabilities.
- **The three kinds of call:**
  - **Contracts (5):** will the market pay more than my own walk-away price for five of this winter's free agents?
  - **Performance (5):** players whose 2026 numbers misstate how well they played, in both directions.
  - **Draft outcomes (5):** where my own grades on the 2026 draft class disagree with the industry.
- **How it's scored:** the Brier score, the average of (probability − outcome)² over resolved calls, with true = 1 and false = 0. Lower is better. Saying 0.5 on everything scores exactly 0.25, so 0.25 is the no-skill line.
- **Where the probabilities come from:** my own numbers wherever they exist (the bullpen memo's landing odds, the edge engine's whiff projection, a next-season wOBA line fit on 2024-26 Statcast, a regressed walk rate), or a public market survey. The rest are judgment, and each of those says so.
- **Facts checked as of Oct. 18, 2026:** the free-agent statuses, clubs, draft slots and current levels in the claims were checked against public sources as of that date; the sources behind each number are named in its basis.
- **Contract terms:** three contract calls resolve on average annual value on a deal of two or more years, because each threshold is my price per year at a set length; two resolve on total money, for reasons given in the log file. Player options and opt-outs count at face value; club and mutual options count only their buyouts.
- **If there's a lockout:** the 2022-26 agreement expires Dec. 1. A contract call with no signing by April 30, 2027 is void. Performance calls carry sample minimums, so a season cut short voids them before it can bend them. Void calls are left out of the score.

<!-- calls:start -->
## Score

- **No call has resolved yet.** 15 open, 0 void. The first contract calls can resolve once free agency opens after the World Series.

## The calls

| # | Category | Claim | Probability | Resolves by | Outcome |
|---|---|---|---|---|---|
| 1 | free-agent contract | Adrián Morejón (LHP, Padres in 2026, a free agent this winter) signs a major league contract of two or more guaranteed years with an average annual value above $18.0 million. | 0.55 | 2027-04-30 | open |
| 2 | free-agent contract | Tarik Skubal (LHP, Dodgers since his deadline trade from Detroit, a free agent this winter) signs a contract guaranteeing more than $365 million in total. | 0.40 | 2027-04-30 | open |
| 3 | free-agent contract | Trevor Rogers (LHP, Orioles in 2026, a free agent this winter) signs a contract of two or more guaranteed years with an average annual value above $29.5 million. | 0.60 | 2027-04-30 | open |
| 4 | free-agent contract | Randy Arozarena (OF, Mariners in 2026, a free agent this winter) signs a contract of two or more guaranteed years with an average annual value above $21.7 million. | 0.65 | 2027-04-30 | open |
| 5 | free-agent contract | Jazz Chisholm Jr. (2B, Yankees in 2026, a free agent this winter) signs a contract guaranteeing more than $87 million in total. | 0.30 | 2027-04-30 | open |
| 6 | performance | Randy Arozarena's 2027 wRC+ is 130 or lower (2026, Mariners: 151). | 0.70 | 2027-10-15 | open |
| 7 | performance | Jarren Duran's 2027 wRC+ is 90 or higher (2026, Red Sox: 69). | 0.70 | 2027-10-15 | open |
| 8 | performance | Freddy Peralta's 2027 wOBA allowed is .320 or lower (2026, Mets and Rays: .328). | 0.60 | 2027-10-15 | open |
| 9 | performance | Adrián Morejón's changeup gets whiffs on 50% or more of swings in 2027 (2026: 56.0% on 182 swings). | 0.40 | 2027-10-15 | open |
| 10 | performance | Bryan Abreu's 2027 walk rate is 11.0% or lower (2026, Astros: 15.3%). | 0.40 | 2027-10-15 | open |
| 11 | draft outcome | Roch Cholowsky (SS, White Sox, No. 1 pick in 2026) plays at least one regular-season game at Double-A or higher in 2027. | 0.70 | 2027-10-15 | open |
| 12 | draft outcome | Jackson Flora (RHP, Giants, No. 4 pick in 2026) ranks ahead of Roch Cholowsky on the last MLB Pipeline Top 100 published on or before Oct. 15, 2027. | 0.30 | 2027-10-15 | open |
| 13 | draft outcome | Drew Burress (OF, Athletics, No. 8 pick in 2026) strikes out in 25.0% or more of his 2027 plate appearances. | 0.55 | 2027-10-15 | open |
| 14 | draft outcome | Grady Emerson (SS, Rays, No. 2 pick in 2026) posts an isolated power (SLG minus AVG) of .120 or higher in 2027. | 0.40 | 2027-10-15 | open |
| 15 | draft outcome | Mason Edwards (LHP, Athletics, No. 47 pick in 2026) walks 10.0% or fewer of the batters he faces in 2027. | 0.40 | 2027-10-15 | open |

### Free-agent contract calls

**1. Adrián Morejón (LHP, Padres in 2026, a free agent this winter) signs a major league contract of two or more guaranteed years with an average annual value above $18.0 million.** (0.55; `morejon-aav-18m`)
- **Basis:** The bullpen memo (Oct. 13, updated Oct. 18) puts my walk-away at four years and $72M, $18.0M a year, and reads the reliever market line's prediction interval as his four-year price: a 47% chance it lands at or below $72M ($18.0M a year), so 53% above, rounded to 0.55. Public guesses run from a rival executive's four years and $60M ($15M a year; Pat Ragazzo, FanSided, Sept. 9) to Dennis Lin of The Athletic saying he "could attract nine-figure offers," which I read secondhand (J.P. Hoornstra, Padres On SI, Oct. 10); my number sits between them.
- **Resolves by:** 2027-04-30. AAV (guaranteed money over guaranteed years; player options and opt-outs at face value, club and mutual options only their buyouts), from the signing club's official announcement, or MLB.com's report of the deal if the club gives no figure. A one-year deal, an accepted qualifying offer included, resolves no. If he has not signed a major league contract by April 30, 2027 (a lockout included), the call is void.

**2. Tarik Skubal (LHP, Dodgers since his deadline trade from Detroit, a free agent this winter) signs a contract guaranteeing more than $365 million in total.** (0.40; `skubal-over-365m`)
- **Basis:** I value him at seven years and $365M, my walk-away. In Kiley McDaniel's survey of 27 industry insiders (ESPN, via TSN, Oct. 2, 2026), 11 of the 27 guesses were above $365M and the median was $350M, so 11/27 = 0.41, rounded to 0.40. I value him a little above the industry's middle guess, with the May 2026 elbow procedure (loose bodies removed) already priced in.
- **Resolves by:** 2027-04-30. Total guaranteed money in the signing club's official announcement, or in MLB.com's report if the club gives no figure. An extension with the Dodgers counts. If he has not signed by April 30, 2027 (a lockout included), the call is void.

**3. Trevor Rogers (LHP, Orioles in 2026, a free agent this winter) signs a contract of two or more guaranteed years with an average annual value above $29.5 million.** (0.60; `rogers-aav-29m`)
- **Basis:** My walk-away is four years and $118M, $29.5M a year, after $10M off for the pick and pool money his expected qualifying offer costs. I stop at four years because he has one 30-start season in three (25, 18 and 30 starts in 2024-26, Statcast). Spotrac puts his market value near $32M a year (Baltimore Banner, Sept. 25, 2026), above my price at any length. The way this comes out no is a one-year deal, his qualifying offer included, or a longer deal that spreads the money thin. Judgment: a lean that someone pays more per year than I would.
- **Resolves by:** 2027-04-30. AAV (guaranteed money over guaranteed years; player options and opt-outs at face value, club and mutual options only their buyouts), from the signing club's official announcement, or MLB.com's report if the club gives no figure. A one-year deal, an accepted qualifying offer included, resolves no. Unsigned by April 30, 2027 (a lockout included): void.

**4. Randy Arozarena (OF, Mariners in 2026, a free agent this winter) signs a contract of two or more guaranteed years with an average annual value above $21.7 million.** (0.65; `arozarena-aav-21m`)
- **Basis:** I'd pay three years and $65M, $21.7M a year, after $10M off for the qualifying-offer pick: I project 2.6 WAR in 2027, down from 5.5 in 2026, because his 2026 wOBA ran about 35 points over his xwOBA. Public estimates run three to four years at $70-100M ($17.5-33M a year), and Bleacher Report (Oct. 7, 2026) cited a payday near $100M, so I expect the market to pay for the 151 wRC+ that call 6 discounts. The low end of those estimates (four years at $70M) and a one-year deal are the ways this comes out no. Judgment.
- **Resolves by:** 2027-04-30. AAV (guaranteed money over guaranteed years; player options and opt-outs at face value, club and mutual options only their buyouts), from the signing club's official announcement, or MLB.com's report if the club gives no figure. A one-year deal, an accepted qualifying offer included, resolves no. Unsigned by April 30, 2027 (a lockout included): void.

**5. Jazz Chisholm Jr. (2B, Yankees in 2026, a free agent this winter) signs a contract guaranteeing more than $87 million in total.** (0.30; `chisholm-over-87m`)
- **Basis:** I'd pay four years and $87M, which I think is at or above the market. In Mark Feinsand's Oct. 11, 2026 piece on MLB.com, an executive gave three to four years near $20M a year ($60-80M) and questioned the qualifying offer, and Feinsand raised a one-year deal; his reported ask is eight to 10 years at $35M. Judgment: a deal near the ask is the only route above $87M.
- **Resolves by:** 2027-04-30. Total guaranteed money in the signing club's official announcement, or in MLB.com's report if the club gives no figure. Accepting a qualifying offer counts as one year and $23.15M. Unsigned by April 30, 2027 (a lockout included): void.

### Performance calls

**6. Randy Arozarena's 2027 wRC+ is 130 or lower (2026, Mariners: 151).** (0.70; `arozarena-wrc-130`)
- **Basis:** His 2026 wOBA (.384 in Statcast) ran 35 points over his xwOBA (.348), the 19th-largest gap of 205 hitters with 400+ PA, and 2025 sat well below it (.340 wOBA, .327 xwOBA; FanGraphs wRC+ 120). Weighting 2026 and 2025 5/4, the next-season line puts his 2027 wOBA at .341, about 122 wRC+ with an 18-point spread, so P(130 or lower) = 0.68, rounded to 0.70. This is the regression that sets my price in call 4.
- **Resolves by:** 2027-10-15. FanGraphs wRC+, 2027 regular season, all clubs combined. Fewer than 400 PA voids the call.

**7. Jarren Duran's 2027 wRC+ is 90 or higher (2026, Red Sox: 69).** (0.70; `duran-wrc-90`)
- **Basis:** His 2026 wOBA (.278 in Statcast) sat 23 points under his xwOBA (.301), the 9th-largest shortfall of 205 hitters with 400+ PA, with a .252 BABIP after .326 in 2025 (FanGraphs), when he had a .348 wOBA, a .326 xwOBA and a 113 wRC+. Weighting 2026 and 2025 5/4, the next-season line puts his 2027 wOBA at .323, about 100 wRC+ with an 18-point spread, so P(90 or higher) = 0.71, rounded to 0.70. The 69 understates how he hit.
- **Resolves by:** 2027-10-15. FanGraphs wRC+, 2027 regular season, all clubs combined. Fewer than 400 PA voids the call.

**8. Freddy Peralta's 2027 wOBA allowed is .320 or lower (2026, Mets and Rays: .328).** (0.60; `peralta-woba-320`)
- **Basis:** Hitters' wOBA against him in 2026 was .328 on an xwOBA of .302, the 12th-largest gap against a pitcher among 112 with 500+ batters faced (Statcast; 4.42 ERA, 4.32 SIERA on FanGraphs); in 2025 it was .277 on a .289 xwOBA. Weighting 2026 and 2025 5/4, the pitchers' next-season line puts 2027 at .312 with a .029 spread, so P(.320 or lower) = 0.61, rounded to 0.60.
- **Resolves by:** 2027-10-15. Baseball Savant wOBA allowed, 2027 regular season, all clubs combined. Fewer than 400 batters faced voids the call.

**9. Adrián Morejón's changeup gets whiffs on 50% or more of swings in 2027 (2026: 56.0% on 182 swings).** (0.40; `morejon-ch-whiff-50`)
- **Basis:** The edge engine's next-season whiff projection (its 2026 projection table, data/edge/2026/projection.parquet; leave-one-out RMSE 4.6 points) has the pitch at 48.9%: its results beat its physics by 15 points in 2026, and about half of such a gap carries over. (The engine's row has 101 whiffs on 181 swings, one swing fewer than the 182 above because that pitch has no complete physics.) P(50% or more) = 0.41, rounded to 0.40. My scouting report on him (reports/2026-morejon-pro-scouting-report.md) calls the pitch's newness the biggest question in his profile.
- **Resolves by:** 2027-10-15. Baseball Savant whiff% (whiffs per swing) on the pitch Statcast labels his changeup, 2027 regular season, all clubs combined; if Statcast relabels it a split-finger, that pitch. Fewer than 75 swings voids the call.

**10. Bryan Abreu's 2027 walk rate is 11.0% or lower (2026, Astros: 15.3%).** (0.40; `abreu-bb-11`)
- **Basis:** The bullpen memo moves him into a closer's role only if his walk rate stays at or below about 11%, resting on a borderline second half (11.3%, p = 0.058). Weighting 2026/2025/2024 = 5/4/3 (15.3%, 10.5%, 9.8% unintentional walks per batter faced, Statcast) and regressing toward the 2026 relief average (9.1%) at the usual 170-batter stabilization point gives 11.6%, with a 2.3-point spread over 260 batters, so P = 0.40 (abreu_walk_rate() in baseball/predictions.py prints every step).
- **Resolves by:** 2027-10-15. FanGraphs BB%, 2027 regular season, all clubs combined. Fewer than 40 innings voids the call.

### Draft outcome calls

**11. Roch Cholowsky (SS, White Sox, No. 1 pick in 2026) plays at least one regular-season game at Double-A or higher in 2027.** (0.70; `cholowsky-double-a`)
- **Basis:** Top college bats usually reach Double-A in their first full season. I hold him a step under that: I grade the hit tool 55, with its play against wood as the open question (.218 in 65 Cape PA, .167 in 46 High-A PA), right wrist tendinitis ended his 2026 on Aug. 22, and the White Sox note he has never played a full season (MLB.com, Sept. 10, 2026). Judgment.
- **Resolves by:** 2027-10-15. His MiLB.com or MLB.com game log for the 2027 regular season. Rehab games count.

**12. Jackson Flora (RHP, Giants, No. 4 pick in 2026) ranks ahead of Roch Cholowsky on the last MLB Pipeline Top 100 published on or before Oct. 15, 2027.** (0.30; `flora-over-cholowsky`)
- **Basis:** I rank Flora first of the 20 draftees I've graded (FV 55, OFP 60, the rarer asset) and Cholowsky second. MLB Pipeline had Cholowsky No. 11 and Flora No. 30 in September 2026 (MLB.com, Sept. 10 and 18). Closing a 19-spot gap takes a strong full season at Double-A, so this is a judgment on whether the industry comes around to my order.
- **Resolves by:** 2027-10-15. MLB Pipeline's overall Top 100 on MLB.com, the last version published on or before Oct. 15, 2027. A player off the list ranks behind any listed player. If neither is listed, or either has lost prospect eligibility, the call is void.

**13. Drew Burress (OF, Athletics, No. 8 pick in 2026) strikes out in 25.0% or more of his 2027 plate appearances.** (0.55; `burress-k-25`)
- **Basis:** His pro debut at Single-A Stockton was loud (.291/.431/.591, 7 HR in 137 PA) but came with a 27.7% strikeout rate, and his 2024 Cape line with wood had 28.2%; in college, with metal, he struck out under 14%. The open question is whether the miss is chase or in-zone whiff, and I lean that the wood-bat strikeouts are real. Judgment.
- **Resolves by:** 2027-10-15. FanGraphs K%, 2027 regular season, all minor and major league levels combined. Fewer than 250 PA voids the call.

**14. Grady Emerson (SS, Rays, No. 2 pick in 2026) posts an isolated power (SLG minus AVG) of .120 or higher in 2027.** (0.40; `emerson-iso-120`)
- **Basis:** I rank him fourth of the top four picks because of the power: a .039 ISO and a 61.5% ground-ball rate in 60 PA at Single-A Charleston, where the league ISO was .135 (consensus had him No. 1 before the draft). I grade the hit tool 55 and expect the power to lag at 19. Judgment.
- **Resolves by:** 2027-10-15. FanGraphs ISO, 2027 regular season, all minor and major league levels combined. Fewer than 300 PA voids the call.

**15. Mason Edwards (LHP, Athletics, No. 47 pick in 2026) walks 10.0% or fewer of the batters he faces in 2027.** (0.40; `edwards-bb-10`)
- **Basis:** He led Division I in strikeouts in 2026 (169 in 95 2/3 innings, MLB.com, July 21, 2026), a 42.7% strikeout rate, and walked 11.9%: 13.0% in his first eight starts, 8.4% in the next six, then 17.5% in three postseason starts. I grade him 45+ with the walks as the question. MLB.com (July 21) expected him not to pitch in 2026 after his college workload, and I found no pro appearance for him through Oct. 18 (RotoWire's player page lists none). Judgment.
- **Resolves by:** 2027-10-15. FanGraphs BB%, 2027 regular season, all minor and major league levels combined. Fewer than 60 innings voids the call.
<!-- calls:end -->

## Walk me through it

**Why 0.55 on Morejón getting more than $18M a year?**
- **It comes straight from the bullpen memo.** My walk-away is four years and $72M, $18.0M a year. I read the reliever market line's prediction interval as his four-year price: a 47% chance it lands at or below $72M, so 53% above. On a 0.05 grid that's 0.55.
- **Why a per-year price:** the memo prices four years. A five-year deal at $75M pays him less a year than I would, and a three-year deal at $60M pays more. Average annual value on a deal of two or more years asks the question the memo answers; total money at any length doesn't.
- **It also says my walk-away is a coin flip to hold up.** That is the point of setting the walk-away at his value: the club pays fair price or lets someone else overpay.

**What's a Brier score, and what would be good?**
- **The score:** for each resolved call, take (probability − outcome)², then average. A 0.8 call that comes true costs 0.04; the same call coming false costs 0.64.
- **The baseline:** always saying 0.5 scores 0.25 no matter what happens.
- **The honest bar for this log:** most of my numbers sit between 0.30 and 0.70, so even if every one of them is exactly right, the expected score is about 0.230, give or take 0.034, assuming the calls are independent. Some are linked (Arozarena's contract and his wRC+, Morejón's contract and his changeup, Flora and Cholowsky, and one market or lockout shock across all five contracts), so the true spread is wider. One year of fifteen calls can't separate skill from luck. The record over several logs, and the calibration table (do my 0.70s come true about 70% of the time?), is what will.

**How does this log protect you from hindsight?**
- **Everything is fixed before the outcome:** the claim, the number, the source and the rule, with a date on the file and the commit history behind it.
- **Losses stay on the page.** Outcomes get filled in, nothing gets deleted, and void calls are void only under the rule written on Oct. 18.

**Duran at 69 wRC+: why is he your answer to "a player whose performance doesn't reflect how well he's playing"?**
- **His contact was better than his results:** a .278 wOBA on a .301 xwOBA, the 9th-largest shortfall of 205 hitters with 400+ PA, and a .252 BABIP after .326 the year before.
- **The projection:** a line fit on 194 hitters takes his 2026 and 2025 wOBA and xwOBA, weighted 5/4 by plate appearances, and leans on xwOBA a little more than wOBA. It puts him near 100 wRC+ in 2027, about 30 points above 2026. Its leave-one-out error is .026 of wOBA (root mean square), against .033 for "same wOBA as last year."
- **Why two seasons:** with three seasons of Statcast in the repo, the two-season line can only be fit on one target year (2026), so its two slopes are uncertain one at a time; their sum is stable. On the same hitters it predicts as well as a one-season line (.026 either way), and it uses what a one-season line throws away: Duran hit .348 in 2025.

**Arozarena: you say the market pays him more than you would, and that his bat falls off. Isn't that a contradiction?**
- **It's the same read twice.** His 151 wRC+ rode a wOBA 35 points over his xwOBA, and his 2025 was a 120. I project about 122, so I'd stop at three years and $65M, $21.7M a year (0.65 that someone pays more a year), and expect his 2027 wRC+ at 130 or lower (0.70).
- **If both come true,** a club paid for 2026's line and got the projection. That's the scenario this log is built to catch.

**Where does Abreu's 11.6% come from?**
- **The rule:** weight his last three seasons 2026/2025/2024 = 5/4/3, scaled so 2026 counts in full; that's 870 effective batters faced. Add 170 batters at the 2026 relief average (9.1%), where walk rate stabilizes. The result is 11.6%.
- **The spread:** the uncertainty in his true rate plus the noise of about 260 batters next year, 2.3 points. P(11.0% or lower) = 0.40.
- **It's in code:** `abreu_walk_rate()` in `baseball/predictions.py` holds the counts and prints each step.

**You'd pay $365M for Skubal. Why only 0.40 that he gets more?**
- **The calls ask what the market does.** My valuation is the threshold. The probability comes from Kiley McDaniel's survey of 27 insiders: 11 guessed above $365M.
- **What it shows:** I value him a little above the industry's middle guess ($350M). If he signs for less, a club that agreed with me would have won him.

**Flora is No. 1 in your rankings. Why only 0.30 that MLB Pipeline agrees by next fall?**
- **My ranking is my opinion of the player; this call predicts the industry's.** Pipeline had Cholowsky 19 spots ahead in September, and lists move slowly.
- **What would flip it:** a strong full season from Flora at Double-A while Cholowsky's bat stays slow with wood. Even then, a 19-spot swing in one year is the less likely path.

**What happens to these calls if there's a lockout?**
- **Contracts:** no major league signings happen during a lockout. A signing before it starts, or after it ends, counts if it happens by April 30, 2027. No signing by then voids the call.
- **Performance and draft:** rates hold up in a short season; the sample minimums (400 PA, 40 innings and so on) void a call when the season is too short to judge. Minor leaguers off the 40-man roster have their own labor agreement, a five-year deal reached in March 2023 that runs through 2027 (True Blue LA, March 30, 2023), so a major league lockout shouldn't stop the draft calls.

---
© 2026 Dylan Fanelli. All rights reserved. See [LICENSE](../LICENSE).
