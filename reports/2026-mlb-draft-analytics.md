<!-- portfolio:header -->
<sub>[← Portfolio](../README.md) &nbsp;|&nbsp; [← Hitter evaluation](2026-hitter-evaluation-torres.md) &nbsp;|&nbsp; [Skubal arsenal →](2025-skubal-arsenal.md)</sub>
<!-- /portfolio:header -->

# MLB Draft Analytics: what a pick is worth, and what a college line still tells you

<!-- portfolio:glance -->
<p><img src="https://img.shields.io/badge/status-summary-1d5c3f" alt="status: summary"> <img src="https://img.shields.io/badge/data-public-1f1f1f" alt="data: public"> <img src="https://img.shields.io/badge/for-Amateur%20scouting-6b6b6b" alt="for: Amateur scouting"> <img src="https://img.shields.io/badge/method-pick%20values-b4532a" alt="method: pick values"> <img src="https://img.shields.io/badge/method-out--of--sample-b4532a" alt="method: out-of-sample"> <img src="https://img.shields.io/badge/method-bonus%20pools-b4532a" alt="method: bonus pools"></p>

**At a glance**

- **The question:** What is a draft pick worth, and does a college stat line still beat the pick?
- **The answer:** Pick 1 is worth about \$69M on average over six seasons and about \$93M over the service-time window, counting bad seasons against the pick; from pick 11 on, about half the players return nothing or less. A college-stat model shows no gain over the pick on 2020-2023 classes.
- **For a club:** Pick values and bonus-pool math for the draft room, and an honest read on what public college lines still add.
<!-- /portfolio:glance -->

By Dylan Fanelli, October 2026, revised November 2026 to match the code repository. I used public data only. My code lives in a separate repository, `IForSureI/Dylan-Fanelli-Draft-Analytics`. If any club would like to view it, I will gladly share it.

I asked four questions about the MLB draft. I answered each with public data and tested every answer out of sample.

## 1. What is a pick worth?
I ran a pricing backtest on 17 drafts. I define value as WAR at \$11.23M a win, minus the minimum salary before arbitration and arbitration pay after it, discounted 7% a year, in 2026 dollars, before the bonus. **Nothing is floored:** a bad season counts against the pick. My first version floored every season at zero, which added about 40% to the average pick; that is why these numbers are lower than the October ones.

I count value two ways: six calendar seasons from the debut, and the service-time window (from the debut through the season the player reaches six years of service), which is the closer measure of team control.

| Pick | Six seasons, 2000-16 drafts | 90% interval on the average | Service window, 2000-16 | Six seasons, 2012-16 only | Service window, 2012-16 only |
|---|---|---|---|---|---|
| 1 | \$68.8M | \$48.2M-\$94.0M | \$92.6M | \$66.3M | \$89.4M |
| 4 | \$40.3M | \$31.7M-\$50.8M | \$49.5M | \$27.5M | \$36.7M |
| 11 | \$31.3M | \$24.7M-\$38.2M | \$38.3M | \$22.4M | \$29.7M |
| 47 | \$9.1M | \$7.7M-\$10.4M | \$11.8M | \$7.4M | \$9.8M |
| 106 | \$4.4M | \$3.8M-\$5.1M | \$6.0M | \$4.1M | \$5.8M |

- **The service window is worth about 30% more than six seasons.** Official service time isn't public in bulk, so I estimated it from MLB's transaction feed and game dates. Against official service time on 197 held-out players, my estimate missed by a median of 1 day.
- **Read both eras.** Curves fit on the 2000-2011 drafts over-predicted the 2012-16 drafts by about \$7M per first-round pick. Whether the drop is real isn't settled (p = 0.10 over six seasons).
- **The interval describes the average.** What one player returns is far wider: from pick 11 on, about half or more of the players returned \$0 or less.
- **Pitchers returned about two thirds of what hitters did in the first round** (65% over six seasons, 68% over the service window).
- **Public grades are worth less per step than the standard table says, for players as a whole:** the table is 1.4x to 2.6x steeper than what draftees returned. High schoolers are the exception and returned about what the table says.
- **A public grade adds almost nothing once you know the pick:** +1% per FV point at the same pick (95% interval -5% to +7%).
- **Over-slot money is inconclusive.** Twelve specifications ran from -\$2.62 to +\$4.18 back per dollar with six-season value.

## 2. Can a college stat line rank a class?
I built a draft model on draft-year and career NCAA lines, summer wood-bat lines (pitchers), age, age for level and conference tier.

- **On 2012-2019 draftees (out of sample, one year at a time), the line ranked a class nearly as well as draft order** (within-year rank correlation .370 vs .425 for hitters, .282 vs .327 for pitchers), and inside a pick band the model's top half returned 1.16x and 1.23x what the pick predicted.
- **On recent classes it shows no gain.** On the 2020-2023 college draftees it never saw, adding the model to the pick moved the AUC for reaching the majors from .768 to .759 for hitters and .723 to .719 for pitchers. Every interval on those gains includes zero, so this is "not shown to help." A rebuild under a protocol written in advance failed its locked 2023 test.
- **Why, if the edge is gone: a hypothesis.** Clubs may now run college-stat models of their own, so the line is already in the pick. I use the model only to order first looks.
- **Age is associated with value beyond the pick, in sample:** about 19% lower per year older for college players (-30% to -6%) and about 40% for high schoolers (-62% to -4%). It didn't improve predictions of a held-out year.

## 3. Where did the 2026 bonus money go?
- 23 of 30 clubs went over their pool, and 17 finished within half a point of the 5% line.
- Clubs paid \$8.62M in tax. None crossed 5%, so in practice the pool is the assigned pool times 1.05, and the last 5% costs \$1.75 per dollar.
- These are the 2026 rules. The collective bargaining agreement expires Dec. 1, 2026, and the pool formula, the 75% tax, the 5% line and the \$150,000 exemption for rounds 11-20 may change for the 2027 draft.

## 4. What do amateur pitch shapes look like to a big-league model?
I pulled 590,044 Hawk-Eye pitches from 1,874 amateur games at pro parks (MLB Draft League, Appalachian League, college events, 2024-2026) and scored them with my physics-only expected-whiff model trained on the 2026 MLB season.

- **The MLB model reads amateur pitches about as well as big-league ones:** AUC .623 on 252,920 amateur swings, against .630 on MLB swings.
- **Inside a pitch type, expected and actual whiff% rank-correlate at .38** (90% interval .34 to .41), against .58 pooled across types.
- **Shape and results carry over about equally.** Last year's shape predicted this year's whiff% at .65 and last year's whiff% did .57 (79 pitcher-pitches), but the difference has a 90% interval of -.09 to +.24, so the two can't be told apart. My October version called shape "the steadier read"; I withdrew that.

## Limits
- The top of the draft is thin: picks 1-5 rest on 84 players, and 24 in the bonus-pool era.
- Service time is estimated, close from 2009 on and rough before it.
- Public grades only, from one outlet.
- The short 2020 season falls inside most windows.
- The college model has no tracking data and only a three-tier conference code.
- Shape grades come from a few games per pitcher.

<!-- portfolio:footer -->
---
<sub>[← Portfolio](../README.md) &nbsp;|&nbsp; [← Hitter evaluation](2026-hitter-evaluation-torres.md) &nbsp;|&nbsp; [Skubal arsenal →](2025-skubal-arsenal.md)</sub>

<sub>© 2026 Dylan Fanelli. All rights reserved. To cite: Fanelli, D. (2026). *MLB Draft Analytics: what a pick is worth, and what a college line still tells you*. Dylan Fanelli Baseball Analytics Portfolio. https://github.com/IForSureI/Dylan-Fanelli-Baseball-Analytics-Portfolio/blob/main/reports/2026-mlb-draft-analytics.md</sub>
<!-- /portfolio:footer -->
