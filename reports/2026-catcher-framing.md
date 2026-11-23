<!-- portfolio:header -->
<sub>[← Portfolio](../README.md) &nbsp;|&nbsp; [← Hitter evaluation](2026-hitter-evaluation-torres.md) &nbsp;|&nbsp; [Swing breakdown →](2026-arozarena-swing-breakdown.md)</sub>
<!-- /portfolio:header -->

# Catcher framing after the ABS challenge system: what it was worth, what it is worth now

<!-- portfolio:glance -->
<p><img src="https://img.shields.io/badge/status-reviewed-1d5c3f" alt="status: reviewed"> <img src="https://img.shields.io/badge/data-public-1f1f1f" alt="data: public"> <img src="https://img.shields.io/badge/for-Pro%20personnel%20and%20R&D-6b6b6b" alt="for: Pro personnel and R&D"> <img src="https://img.shields.io/badge/method-Statcast-b4532a" alt="method: Statcast"> <img src="https://img.shields.io/badge/method-benchmark%20vs%20Savant-b4532a" alt="method: benchmark vs Savant"> <img src="https://img.shields.io/badge/method-rule%20change-b4532a" alt="method: rule change"></p>

**At a glance**

- **The question:** How much is catcher framing worth, and did the ABS challenge system change it?
- **The answer:** My public model matches Baseball Savant's framing runs (r 0.92-0.98). Through 2025 one standard deviation of framing was about 6 runs, about \$6.5M a year; in 2026, the first ABS challenge season, it fell to 3.6 runs, and Patrick Bailey went from +27.6 to +3.3.
- **For a club:** Discount a catcher's pre-2026 framing by about 40% when pricing him, and start measuring challenge skill.
<!-- /portfolio:glance -->

Dylan Fanelli. Data: every regular-season take in Statcast, 2024-26 (1.11 million), and Baseball Savant's catcher framing leaderboard for each season; both pulled Nov. 23, 2026.

**The question:** how much is a good framer worth, does the skill repeat, and did MLB's first season of ABS challenges change the answer?

**The answer:** it changed. Through 2025, the spread between catchers was about 6 framing runs a season (one standard deviation), and the best framer, Patrick Bailey, added 20-28 runs a year. In 2026, the first season of the ABS challenge system, the spread fell to 3.6 runs, about 40% less, and Bailey fell to 3.3. The best catcher in 2026 added 11.7 runs.

- **The skill still exists:** it repeats within a season (odd vs even games, a full-season reliability of 0.73).
- **It carried over less into 2026:** catchers' 2025 framing predicted their 2026 framing about half as well as 2024 predicted 2025 (r 0.33 vs 0.58).
- **What that means for a club:** a catcher's pre-2026 framing record overstates what he'll add under challenges.

![Framing runs per catcher by season, and my framing runs against Baseball Savant's](figures/2026-catcher-framing.png)

## What I built, and how I know it's right

- **The call model:** every take, fit separately each season.
  - It works from the pitch's horizontal location, its height as a share of the batter's Statcast strike zone, the batter's side, the pitcher's hand and the count.
  - It is gradient-boosted trees fit out of fold by game, so no pitch is scored by a model that saw its own game.
- **Extra strikes:** each take gets the called strike (1 or 0) minus the model's strike probability.
- **What a strike is worth:** the change in run expectancy after a ball minus after a called strike, measured on each season's own takes, count by count.
  - At 0-0 it is 0.072 runs. At 3-2 it is 0.584 runs. On an average take it is about 0.14 runs.
- **Framing runs:** extra strikes times that value, summed for each catcher.
- **The adjusted version:** a ridge regression with catcher, pitcher and home park all in it.
  - It separates the catcher from his pitchers' command and from park and crew effects.
  - The umpire isn't in the public data, so the park stands in for part of the crew.

**Checks:**

| | 2024 | 2025 | 2026 |
|---|---|---|---|
| Takes | 366,873 | 368,845 | 371,385 |
| Call model: worst calibration gap across ten probability bins | 0.5 pts | 0.5 pts | 0.3 pts |
| Call model: Brier score (lower = calls more predictable from location) | 0.047 | 0.045 | 0.035 |
| Agreement with Baseball Savant's framing runs (r, my unadjusted runs; catchers on Savant's qualified list) | 0.97 (58) | 0.98 (57) | 0.92 (56) |
| Same, my pitcher- and park-adjusted runs | 0.91 | 0.93 | 0.87 |
| Within-season reliability (odd vs even games, stepped up to a full season; catchers with 1,500+ takes) | 0.66 (69) | 0.74 (71) | 0.73 (77) |

The model reproduces MLB's own leaderboard from public data. A club could run it on its own feed, or on a league it has TrackMan for, and get the same answer.

## What changed in 2026

The ABS challenge system began in 2026 (MLB.com, "MLB to use ABS Challenge System starting in 2026," approved Sept. 23, 2025). Each club gets two challenges a game and keeps the successful ones; only the pitcher, catcher or batter can challenge.

| | 2024 | 2025 | 2026 |
|---|---|---|---|
| Spread of framing runs among catchers (SD; mine, adjusted) | 6.0 | 5.6 | 3.6 |
| Same, Baseball Savant's runs | 6.4 | 6.4 | 4.6 |
| Best catcher | Bailey +20.3 | Bailey +27.6 | Dillon Dingler +11.7 |
| Takes where the call was genuinely uncertain from location (strike probability 10-90%) | 21.7% | 20.9% | 15.2% |
| Called balls on pitches well inside the zone | 0.17% | 0.12% | 0.02% |
| Called strikes on pitches well outside the zone | 1.9% | 1.3% | 1.0% |

**Three things moved together.** The zone's edge got sharper: the uncertain band shrank by more than a quarter. The worst missed calls nearly disappeared, which is consistent with challenges reversing them. Statcast's pitch log appears to keep the call that stood. And framing's spread fell by 30-40% on both my numbers and Savant's.

**The top framers lost the most.**

| Catcher | 2024 | 2025 | 2026 | (Savant 2024 / 2025 / 2026) |
|---|---|---|---|---|
| Patrick Bailey | +20.3 | +27.6 | +3.3 | +22.4 / +25.1 / +4.1 |
| Cal Raleigh | +14.5 | +6.4 | -3.4 | +12.7 / +7.0 / -4.6 |
| Austin Hedges | +7.4 | +12.5 | -0.4 | +7.6 / +10.6 / +1.5 |
| Jose Trevino | +12.6 | +4.0 | +3.7 | +11.3 / +1.5 / +1.7 |

Some of each drop is the ordinary regression of an extreme season. But the spread across all catchers fell too, not just the top. And the year-to-year correlation halved across the rule change (0.58 from 2024 to 2025, 0.33 from 2025 to 2026, adjusted; 0.62 and 0.41 unadjusted; catchers with 2,000+ takes both years). So the change is in the game, not only in these players.

## What it's worth in money

At 10 runs a win and FanGraphs' $11.23M per win on the 2025-26 market (Ben Clemens, Feb. 24, 2026):

- **Through 2025:** a catcher one standard deviation above average added about 6 runs, about 0.6 wins, about **$6.5M a year**.
- **In 2026:** one standard deviation was 3.6 runs, about 0.36 wins, about **$4.0M a year**.
- **For a framing-first catcher on a multi-year deal:** that gap is most of his premium.

**This winter's free-agent catchers** (from my [market board](2027-market-board.md); adjusted runs, 2024 / 2025 / 2026):
- **Tyler Stephenson:** +2.6 / -6.7 / -7.4 (Savant -4.4 / -7.9 / -9.5). The bottom of the league in 2026, and my board's salary call ($9.0M a year against MLBTR's $7.5M) doesn't include framing. If a club prices framing, he's worth less than the call.
- **Carson Kelly:** +0.8 / +2.6 / +2.5 (Savant +2.5 / -1.9 / +0.3). About average, and steady.

## What a club should do with this

1. **Discount pre-2026 framing by about 40%** when pricing a catcher, until a second ABS season says whether 2026 is the new level.
2. **Value challenge skill as a separate catcher skill.** Baseball Savant now publishes ABS challenge results. Which catchers challenge well (right pitches, right counts) is the next study, and it's a skill that didn't exist before 2026.
3. **Keep measuring framing,** because it still repeats within a season. It just pays less.

## Limits

- **The umpire isn't in the public data.** The park term absorbs part of the crew effect, not all of it.
- **One ABS season.** 2026 could be a transition year, as umpires and catchers adjust. The year-to-year number rests on 48 catchers.
- **Statcast's calls after a challenge:** that the pitch log records the call that stood is my reading of the near-disappearance of deep-zone balls, not a documented field rule.

## Sources

- Statcast pitch data, 2024-26 regular seasons, via Baseball Savant; pulled Nov. 23, 2026.
- Baseball Savant, catcher framing leaderboard, 2024, 2025 and 2026 (qualified catchers); pulled Nov. 23, 2026.
- MLB.com, "MLB to use ABS Challenge System starting in 2026" (approval Sept. 23, 2025; rules).
- FanGraphs, Ben Clemens, "What Are Teams Paying for a Win in Free Agency? 2026 Edition" (Feb. 24, 2026): $11.23M per win overall.

Code: `baseball/evaluation/framing.py` (`uv run bb framing`). Outputs: `reports/outputs/framing_summary.json`, `reports/outputs/framing_catchers.json`. Tests: `tests/test_framing.py`.

<!-- portfolio:footer -->
---
<sub>[← Portfolio](../README.md) &nbsp;|&nbsp; [← Hitter evaluation](2026-hitter-evaluation-torres.md) &nbsp;|&nbsp; [Swing breakdown →](2026-arozarena-swing-breakdown.md)</sub>

<sub>© 2026 Dylan Fanelli. All rights reserved. To cite: Fanelli, D. (2026). *Catcher framing after the ABS challenge system: what it was worth, what it is worth now*. Dylan Fanelli Baseball Analytics Portfolio. https://github.com/IForSureI/Dylan-Fanelli-Baseball-Analytics-Portfolio/blob/main/reports/2026-catcher-framing.md</sub>
<!-- /portfolio:footer -->
