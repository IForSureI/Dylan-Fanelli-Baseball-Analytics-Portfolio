<!-- portfolio:header -->
<sub>[← Portfolio](../README.md) &nbsp;|&nbsp; [← Draft analytics](2026-mlb-draft-analytics.md) &nbsp;|&nbsp; [Skubal arsenal →](2025-skubal-arsenal.md)</sub>
<!-- /portfolio:header -->

# The 2026-27 market board: my free-agent calls against MLB Trade Rumors, scored as they sign

<!-- portfolio:glance -->
<p><img src="https://img.shields.io/badge/status-open:%20scored%20as%20players%20sign-1d5c3f" alt="status: open: scored as players sign"> <img src="https://img.shields.io/badge/data-public-1f1f1f" alt="data: public"> <img src="https://img.shields.io/badge/for-GM%20and%20pro%20personnel-6b6b6b" alt="for: GM and pro personnel"> <img src="https://img.shields.io/badge/method-forecasting-b4532a" alt="method: forecasting"> <img src="https://img.shields.io/badge/method-benchmark-b4532a" alt="method: benchmark"> <img src="https://img.shields.io/badge/method-Brier%20score-b4532a" alt="method: Brier score"></p>

**At a glance**

- **The question:** Can I call this winter's free-agent contracts better than MLB Trade Rumors, before they sign?
- **The answer:** 38 dated calls (Nov. 23, 2026), scored against MLBTR's as players sign. Last winter's edge came from one player: without Kyle Tucker, my model and MLBTR were tied. This winter tests whether last winter's pattern repeats.
- **For a club:** A forecast a front office can check: every call dated and frozen, every miss counted against the public benchmark.
<!-- /portfolio:glance -->

Dylan Fanelli. Calls made Nov. 23, 2026, and never edited after that date. Data: MLB Trade Rumors' top-50 lists (2025-26 and 2026-27, with the signings they record), Baseball-Reference WAR files; all pulled Nov. 23, 2026.

**The question:** can I call this winter's free-agent contracts better than the public benchmark, in public, before the players sign?

**The answer so far:** not yet, and last winter's edge came from one player.
- **How the model works:** it starts from MLBTR's number and moves it on each player's three-year WAR, age and role. Each player was left out of the fit that predicted him.
- **The headline backtest:** average-salary (AAV) error $3.24M against MLBTR's $3.79M. That $0.55M edge has a 95% range of -$0.66M to +$2.05M.
- **Where the edge comes from:** almost all of it is Kyle Tucker. Leave him out and the two are tied ($3.31M against $3.33M). Leave out Tucker and Bo Bichette and MLBTR is better ($3.03M against $3.13M). The median miss is also slightly worse than MLBTR's ($2.74M against $2.63M).

So this board isn't a claim that I beat MLBTR. It's a dated, public test of one idea: last winter's pattern repeats. That pattern was shorter deals at higher salaries than predicted, and relievers paid more. I made 38 calls on this winter's open free agents, and they get scored against MLBTR's as each player signs.

## What I learned from last winter

On the 44 signed 2025-26 free agents with an MLB record:

- **Players took shorter deals at higher salaries than predicted.** MLBTR's average salaries ran **$2.0M a year low**, and 64% of the players signed above MLBTR's AAV. Its years ran **0.8 years long**, and its total guarantees ran **$10.6M high**. Kyle Tucker (MLBTR: 11 years, $400M; signed four years, $240M) and Bo Bichette (eight years, $208M; signed three years, $126M) are the extreme cases.
- **Relievers beat their predictions most.** With WAR, age and MLBTR's number held equal, a reliever signed for about 30% more per year than the formula gave a starter or hitter. Tyler Rogers (MLBTR: two years, $18M; signed three years, $37M) is the clearest case. That rests on 14 relievers, so it is the least certain part of the model.
- **Age matters beyond what MLBTR already priced in.** The term is linear in age around 30: about 5% less per year for each year over 30, and about 5% more for each year under. Adrián Morejón (27) and Trevor Rogers (28) get the second half of that.
- **The top of the WAR range rests on three players.** The training set's highest three-year WAR averages are Tucker (4.8), Alex Bregman (4.1) and Cody Bellinger (4.0). Seiya Suzuki (3.9) and Randy Arozarena (4.1) sit at that edge, so their calls lean hardest on those three.

| Last winter, each player left out of his own fit | My model | MLBTR |
|---|---|---|
| Average error in AAV | $3.24M | $3.79M |
| Average error without Kyle Tucker (43 players) | $3.31M | $3.33M |
| Average error without Tucker and Bo Bichette (42) | $3.13M | $3.03M |
| Median error in AAV | $2.74M | $2.63M |
| Closer to the actual AAV | 21 of 44 | 23 of 44 |
| Brier score on "signs above MLBTR's AAV", lower is better (always guessing last winter's 64% base rate scores 0.231; a coin flip 0.250) | 0.218 | n/a |

So the edge is in one big miss, not in the typical player. MLBTR's worst miss last winter was Tucker's short, rich deal, and the model caught part of it. Whether that was a pattern or one player is what this winter answers.

## How the board is scored

- **AAV:** guaranteed money divided by guaranteed years. An accepted qualifying offer counts as one year at $23.15M.
  - The answer key is the signing line MLBTR adds under each player on its own list page.
  - The headline is average error, mine against MLBTR's, on the same players.
- **Over/under:** my probability, in steps of 0.05, that a player signs above MLBTR's AAV, scored with the Brier score.
  - The probability comes from the gap between my AAV and MLBTR's, measured against how far off my model's left-out predictions were last winter (a log spread of 0.30).
- **Fairness:** MLBTR made its calls on Nov. 2; mine are three weeks later.
  - I had the qualifying-offer decisions (Nov. 17) and three weeks of reporting that MLBTR didn't. That's a real advantage, and I note it here rather than hide it.
  - Players who signed before Nov. 23 aren't scored at all.
- **No call:** I make no call on players without an MLB record (Teruaki Sato, Kaima Taira, Hiromi Itoh), because the model has nothing to work from.

**Scoring rules.** I set these on Nov. 23, before any called player signed. They're the rules in `market.score()`.
- **What counts as signed:** the signing line MLBTR adds under the player on its own list. An agreement counts; I don't wait for the club's announcement. My prediction log waits for the announcement, so the same signing can resolve on different days in the two documents. Skubal is the current example: agreed Nov. 22, official after his physical.
- **Deadline:** a signing line first seen after April 30, 2027 isn't scored. A player unsigned by then, a lockout included, isn't scored. Each line's first-seen date is recorded when the list is pulled.
- **Major league deals only:** a minor-league deal, a deal with a club outside MLB, or a retirement isn't scored. An accepted qualifying offer is one year at $23.15M.
- **Money and years:** MLBTR's stated guarantee over its stated years. Deferred money counts at face value. When MLBTR counts a player option as a year (Sonny Gray's "two years, includes second-year player option"), so do I.
- **Ties:** a deal at exactly MLBTR's AAV counts as not above it. A deal exactly as far from my call as from MLBTR's counts for neither side.

`uv run bb market score` scores whatever has signed. `uv run bb market pull` re-reads the signing lines. `uv run bb market render` rewrites the table below.

## The board

<!-- board:start -->
**Score so far (9 of 38 signed):** AAV error mine $3.4M vs MLBTR $2.7M; mine closer on 3; over/under Brier 0.219 (a coin flip scores 0.250).

| # | Player | MLBTR's call (Nov. 2) | MLBTR AAV | My AAV | P(beats MLBTR AAV) | WAR (5/4/3 average), age | Signed | Result |
|---|---|---|---|---|---|---|---|---|
| 2 | Trevor Rogers | Five years, $115MM | $23.0M | $29.0M | 0.80 | 2.8, 28 | Signed with Cubs for five years, $120MM (agreed Nov. 23, after my calls; official after physical) | $24.0M AAV; MLBTR closer |
| 3 | Freddy Peralta | Five years, $110MM | $22.0M | $24.6M | 0.65 | 2.8, 30 | Signed with Orioles for five years, $125MM | $25.0M AAV; mine closer |
| 4 | Seiya Suzuki | Four years, $105MM | $26.25M | $33.2M | 0.80 | 3.9, 31 |  |  |
| 5 | Randy Arozarena | Four years, $100MM | $25.0M | $33.0M | 0.80 | 4.1, 31 |  |  |
| 6 | Michael King | Four years, $92MM | $23.0M | $26.4M | 0.70 | 3.2, 31 |  |  |
| 8 | Adrián Morejón | Five years, $80MM | $16.0M | $24.8M | 0.95 | 1.9 (RP), 27 |  |  |
| 11 | Brandon Lowe | Three years, $69MM | $23.0M | $27.5M | 0.70 | 3.4, 31 |  |  |
| 14 | Tyler Mahle | Three years, $54MM | $18.0M | $15.9M | 0.35 | 1.4, 31 |  |  |
| 15 | Luis Arraez | Three years, $48MM | $16.0M | $17.3M | 0.60 | 1.9, 29 |  |  |
| 16 | Clay Holmes | Three years, $45MM | $15.0M | $12.7M | 0.30 | 1.7, 33 |  |  |
| 17 | Ian Happ | Three years, $45MM | $15.0M | $18.6M | 0.75 | 3.4, 31 |  |  |
| 18 | Kevin Gausman | Two years, $44MM | $22.0M | $16.9M | 0.20 | 2.1, 35 | Signed with Tigers for one year, $25MM | $25.0M AAV; MLBTR closer |
| 19 | Nick Martinez | Two years, $42MM | $21.0M | $20.1M | 0.45 | 3.3, 35 |  |  |
| 20 | Jazz Chisholm Jr. | Two years, $40MM (with an opt-out) | $20.0M | $25.5M | 0.80 | 2.8, 28 |  |  |
| 21 | Shota Imanaga | Two years, $40MM | $20.0M | $18.4M | 0.40 | 2.1, 32 |  |  |
| 22 | Foster Griffin | Three years, $39MM | $13.0M | $12.5M | 0.45 | 1.4, 30 | Signed with Guardians for three years, $48MM | $16.0M AAV; MLBTR closer |
| 23 | Ty France | Two years, $32MM | $16.0M | $16.0M | 0.50 | 2.1, 31 |  |  |
| 25 | Casey Mize | Two years, $28MM (opt-out) | $14.0M | $13.5M | 0.45 | 1.2, 29 |  |  |
| 26 | Michael Soroka | Two years, $26MM (opt-out) | $13.0M | $13.6M | 0.55 | 1.3, 28 |  |  |
| 27 | Alex Vesia | Two years, $26MM | $13.0M | $16.2M | 0.75 | 1.4 (RP), 30 |  |  |
| 28 | Nick Pivetta | Two years, $26MM | $13.0M | $12.5M | 0.45 | 2.5, 33 |  |  |
| 30 | David Peterson | Two years, $24MM | $12.0M | $11.2M | 0.40 | 1.2, 30 | Signed with Rockies for two years, $32MM | $16.0M AAV; MLBTR closer |
| 32 | Bryan Abreu | Two years, $22MM (opt-out) | $11.0M | $15.4M | 0.85 | 1.7 (RP), 29 |  |  |
| 33 | Carson Kelly | Two years, $20MM | $10.0M | $10.5M | 0.55 | 2.1, 31 |  |  |
| 34 | Daulton Varsho | Two years, $20MM | $10.0M | $12.2M | 0.75 | 2.4, 29 |  |  |
| 37 | Mauricio Dubón | Two years, $18MM | $9.0M | $9.3M | 0.55 | 1.9, 31 |  |  |
| 38 | Raisel Iglesias | One year, $17MM | $17.0M | $15.8M | 0.40 | 1.7 (RP), 36 |  |  |
| 39 | J.P. Crawford | Two years, $16MM | $8.0M | $8.7M | 0.60 | 2.2, 31 |  |  |
| 40 | Tyler Stephenson | Two years, $15MM | $7.5M | $9.0M | 0.75 | 2.1, 29 | Signed with Reds for three years, $30MM | $10.0M AAV; mine closer |
| 41 | Paul Blackburn | Two years, $15MM | $7.5M | $8.8M | 0.70 | 1.2 (RP), 32 |  |  |
| 42 | Steven Okert | Two years, $14MM | $7.0M | $7.5M | 0.60 | 1.4 (RP), 34 |  |  |
| 43 | Luis Robert Jr. | One year, $14MM | $14.0M | $14.3M | 0.55 | 1.2, 28 | Signed with Orioles for one year, $12MM | $12.0M AAV; MLBTR closer |
| 44 | Joc Pederson | One year, $14MM | $14.0M | $10.6M | 0.20 | 1.3, 34 |  |  |
| 46 | JoJo Romero | Two years, $13MM | $6.5M | $8.8M | 0.85 | 1.1 (RP), 29 | Signed with Padres for three years, $21MM | $7.0M AAV; MLBTR closer |
| 47 | Matthew Boyd | One year, $13MM | $13.0M | $9.6M | 0.15 | 1.5, 35 |  |  |
| 48 | Kris Bubic | One year, $12.5MM | $12.5M | $13.9M | 0.65 | 1.7, 28 | Signed with Guardians for one year, $17.5MM | $17.5M AAV; mine closer |
| 49 | Taylor Ward | One year, $12MM | $12.0M | $12.0M | 0.50 | 2.3, 32 |  |  |
| 50 | Robbie Ray | One year, $12MM | $12.0M | $10.3M | 0.30 | 1.9, 34 |  |  |

No call from me (signed before Nov. 23, or no MLB record):

- 1. Tarik Skubal: signed before the board; Signed with Mets for nine years, $450MM (agreed Nov. 22; official after physical).
- 7. Teruaki Sato: no MLB record; Signed with Cubs for six years, $120MM.
- 9. Ryan Jeffers: signed before the board; Accepted $23.15MM qualifying offer from Twins.
- 10. Kaima Taira: no MLB record; Signed with Blue Jays for five years, $80MM. Includes opt-out after third year.
- 12. David Bednar: signed before the board; Accepted $23.15MM qualifying offer from Yankees.
- 13. Sonny Gray: signed before the board; Signed with Twins for two years, $55MM. Includes second-year player option.
- 24. Dustin May: signed before the board; Signed with White Sox for three years, $52.5MM.
- 29. Evan Phillips: signed before the board; Signed with Braves for three years, $35MM.
- 31. Jake Bauers: signed before the board; Signed with Red Sox for four years, $58MM.
- 35. Emilio Pagán: signed before the board; Signed with Tigers for one year, $11.5MM.
- 36. Hiromi Itoh: no MLB record.
- 45. Jonathan Loáisiga: signed before the board; Signed with Yankees for two years, $19MM.
<!-- board:end -->

## Where the board disagrees most with MLBTR

- **Adrián Morejón (MLBTR $16.0M a year; mine $24.8M; 0.95 over).** It's the reliever effect plus a young age (27). This is where the board and my earlier work disagree most; the next section takes it up.
- **Suzuki and Arozarena (MLBTR about $25-26M; mine about $33M).** Both are 31 with about 4 WAR a year over three seasons. Last winter, players like that took shorter deals at higher salaries.
- **Kevin Gausman (MLBTR $22.0M; mine $16.9M; 0.20 over).** At 35, with WAR of 1.1, 4.0 and 1.1 over the last three seasons, he gets the age penalty.

## How the board squares with my prediction log and bullpen memo

Three of my documents forecast the same market, and they don't agree.

| Player | Prediction log (Oct. 18) | Probability in the log | The board's model at the same AAV line (it doesn't call years) |
|---|---|---|---|
| Adrián Morejón | AAV above $18.0M, two or more years | 0.55 | 0.86 |
| Randy Arozarena | AAV above $21.7M, two or more years | 0.65 | 0.92 |
| Trevor Rogers | AAV above $29.5M, two or more years | 0.60 | 0.48 |

- **Where the log comes from:** the log and the bullpen memo price relievers with a market line fit on the 21 relief signings of 2025-26. That line puts Morejón's expected price at $18.4M a year.
- **Where the board comes from:** it uses MLBTR's number moved by the model above. Its reliever term rests on 14 relievers in one winter, and its edge rests on one hitter.
- **Which I stand behind:** for a buying decision, the memo. Its market line is built for relievers, and the board's reliever term is its least certain part.
  - **If the board is right, both of the memo's targets price out:**
    - On the board's model, Morejón's market pays him more than $15M a year about 95% of the time, so the memo's $64M walk-away would land him about 7% of the time, not 33% (Nov. 24; at the earlier $60M walk-away it was 5% against 26%).
    - Abreu's board price is $15.4M a year. The memo's walk-away for him (above $25M over two years, $12.5M a year) would land him about 24% of the time.
    - The memo's third name is Raisel Iglesias on one year. The board has him at $15.8M against MLBTR's $17.0M, so he's the one target whose price the board doesn't push up.
    - A club that believes the board has to raise its walk-aways or move to Iglesias. The memo now carries a dated note saying so.
  - The board's "about 7%" uses the AAV condition only; the memo's 33% is for four years and $64M.
- **How each is scored:** the log's probabilities stay frozen and are scored as written; the board is scored separately against MLBTR. When both resolve, they'll show which forecast was better. Dated Nov. 23 notes in the log record the board's numbers next to calls 1, 3 and 4.

## Limits

- **One winter of history, 44 players.** That's why the edge's 95% range includes zero, and why this winter is the test.
- **I could only backtest on one winter.** MLBTR's 2022-23 to 2024-25 list pages don't record the signings. Pulling those from news posts gave inconsistent wording (some posts give a total, some only salaries by year), so I left them out rather than mix answer keys.
- **WAR is Baseball-Reference's**, and none of it is a projection system's. The table's WAR column is the 5/4/3 weighted average of three seasons, not a total. Ages are Baseball-Reference's season ages, so Morejón is 27 here and 28 in my memo, which uses his age next season.
- **What the model doesn't know:** health, opt-outs, who is bidding, and draft-pick cost. Rogers, Morejón and Arozarena all declined qualifying offers, so a club that signs them gives up a pick, and the model has no term for it.
- **The calls are one linked bet:** 23 of the 38 lean above MLBTR, 13 below, and 2 sit at 0.50. If last winter's "MLBTR ran low" doesn't repeat, or a lockout moves the whole market, most of the calls miss together.
- **The model doesn't call years.** Last winter MLBTR's years ran long, but my years model wasn't better than MLBTR's left-out, so I only call AAV.
- **The backtest is partly in-sample.** The spread behind the probabilities (0.298) comes from the same left-out errors the 0.218 Brier score is computed on, and I chose the reliever and age terms after looking at the same winter. This winter's score is the clean test.

## Sources

- MLB Trade Rumors, "2025-26 Top 50 MLB Free Agents With Predictions" (Nov. 6, 2025), with the signings recorded on the page; pulled Nov. 23, 2026.
- MLB Trade Rumors, "2026-27 Top 50 Free Agents With Predictions" (Nov. 2, 2026); pulled Nov. 23, 2026.
- Baseball-Reference WAR files (war_daily_bat.txt, war_daily_pitch.txt); pulled Nov. 23, 2026.
- Qualifying offer, $23.15M for 2027: MLB.com.

Code: `baseball/roster/market.py`. Data: `market/` (players, calls, signing lines; facts only, no page text). Tests: `tests/test_market.py`.

<!-- portfolio:footer -->
---
<sub>[← Portfolio](../README.md) &nbsp;|&nbsp; [← Draft analytics](2026-mlb-draft-analytics.md) &nbsp;|&nbsp; [Skubal arsenal →](2025-skubal-arsenal.md)</sub>

<sub>© 2026 Dylan Fanelli. All rights reserved. To cite: Fanelli, D. (2026). *The 2026-27 market board: my free-agent calls against MLB Trade Rumors, scored as they sign*. Dylan Fanelli Baseball Analytics Portfolio. https://github.com/IForSureI/Dylan-Fanelli-Baseball-Analytics-Portfolio/blob/main/reports/2027-market-board.md</sub>
<!-- /portfolio:footer -->
