<!-- portfolio:header -->
<sub>[← Portfolio](../README.md) &nbsp;|&nbsp; [← Hitter evaluation](2026-hitter-evaluation-torres.md) &nbsp;|&nbsp; [Skubal arsenal →](2025-skubal-arsenal.md)</sub>
<!-- /portfolio:header -->

# MLB Draft Analytics: what a pick is worth, and what a college line still tells you

<!-- portfolio:glance -->
<p><img src="https://img.shields.io/badge/status-summary-1d5c3f" alt="status: summary"> <img src="https://img.shields.io/badge/data-public-1f1f1f" alt="data: public"> <img src="https://img.shields.io/badge/for-Amateur%20scouting-6b6b6b" alt="for: Amateur scouting"> <img src="https://img.shields.io/badge/method-pick%20values-b4532a" alt="method: pick values"> <img src="https://img.shields.io/badge/method-out--of--sample-b4532a" alt="method: out-of-sample"> <img src="https://img.shields.io/badge/method-bonus%20pools-b4532a" alt="method: bonus pools"></p>

**At a glance**

- **The question:** What is a draft pick worth, and does a college stat line still beat the pick?
- **The answer:** Pick 1 is worth about \$75M before the bonus; from the second round on, the typical player returns nothing. A college-stat model no longer adds to the pick on 2020-2023 classes.
- **For a club:** Pick values and bonus-pool math for the draft room, and an honest read on what public college lines still add.
<!-- /portfolio:glance -->

By Dylan Fanelli, October 2026. I used public data only. My code lives in a separate repository, `IForSureI/Dylan-Fanelli-Draft-Analytics`. If any club would like to view it, I will gladly share it.

I asked four questions about the MLB draft. I answered each with public data and tested every answer out of sample.

## 1. What is a pick worth?
I ran a pricing backtest on 17 drafts. I define value as a player's first six MLB seasons (WAR at $11.23M a win, minus the minimum salary in years 1-3 and arbitration in years 4-6, no season below zero, discounted 7% a year), in 2026 dollars, before the bonus.

| Pick | Typical value before the bonus, 2000-16 drafts | 90% range | Hitters | Pitchers |
|---|---|---|---|---|
| 1 | $75.4M | $55.7M-$105.2M | $86.8M | $59.1M |
| 4 | $45.0M | $38.1M-$54.2M | $59.0M | $36.9M |
| 11 | $36.5M | $30.8M-$42.5M | $39.2M | $33.0M |
| 47 | $12.9M | $11.2M-$14.7M | $15.4M | $10.6M |
| 106 | $7.2M | $6.4M-$8.0M | $7.7M | $6.8M |

- **Pitchers return about 72% of what hitters do at the same pick.**
- **From the second round on, the typical player returns nothing.** The median is about $0; the average is a few players who hit.
- **Public grades are worth less per step than the standard table says:** about 12% more value per FanGraphs FV point, against the 18% the table implies.
- **A public grade adds almost nothing once you know the pick:** +1% per FV point at the same pick (95% range -5% to +7%).
- **Over-slot money is inconclusive.** Twelve specifications ran from -$2.60 to +$5.60 back per dollar.

## 2. Can a college stat line rank a class?
I built a draft model on NCAA lines, summer wood-bat lines (pitchers), age, age for level and conference tier.

- **On 2012-2019 draftees (out of sample, one year at a time), the line ranked a class nearly as well as draft order** (within-year rank correlation .370 vs .425 for hitters, .282 vs .327 for pitchers), and inside a pick band the model's top half returned 1.16x and 1.23x what the pick predicted.
- **It hasn't held up on recent classes.** On the 2020-2023 college draftees it never saw, it adds nothing to the pick on reaching the majors (hitters AUC .768 from the pick, .759 with the model). A rebuild under a protocol written in advance failed its locked 2023 test. The draft order has absorbed the public college line.
- **Age matters beyond the pick:** holding pick, pitcher and year fixed, value fell about 19% per year older for college players (-30% to -6%) and about 40% for high schoolers (-62% to -4%).

## 3. Where did the 2026 bonus money go?
- 23 of 30 clubs went over their pool, and 17 finished within half a point of the 5% line.
- Clubs paid $8.62M in tax. None crossed 5%, so in practice the pool is the assigned pool times 1.05, and the last 5% costs $1.75 per dollar.

## 4. What do amateur pitch shapes look like to a big-league model?
I pulled 590,044 Hawk-Eye pitches from 1,874 amateur games at pro parks (2024-2026) and scored them with my physics-only expected-whiff model trained on the 2026 MLB season.

- **The MLB model reads amateur pitches about as well as big-league ones:** AUC .623 on 252,920 amateur swings, against .630 on MLB swings.
- **Shape is the steadier read:** last year's shape predicted this year's whiff% at .65; last year's whiff% did .57 (n=79 pitcher-pitches).

## Limits
- The top of the draft is thin: picks 1-5 rest on 84 players.
- Public grades only, from one outlet.
- Six seasons stands in for team control, and the short 2020 season falls inside most windows.
- The college model has no tracking data and only a three-tier conference code.
- Shape grades come from a few games per pitcher.

<!-- portfolio:footer -->
---
<sub>[← Portfolio](../README.md) &nbsp;|&nbsp; [← Hitter evaluation](2026-hitter-evaluation-torres.md) &nbsp;|&nbsp; [Skubal arsenal →](2025-skubal-arsenal.md)</sub>

<sub>© 2026 Dylan Fanelli. All rights reserved. To cite: Fanelli, D. (2026). *MLB Draft Analytics: what a pick is worth, and what a college line still tells you*. Dylan Fanelli Baseball Analytics Portfolio. https://github.com/IForSureI/Dylan-Fanelli-Baseball-Analytics-Portfolio/blob/main/reports/2026-mlb-draft-analytics.md</sub>
<!-- /portfolio:footer -->
