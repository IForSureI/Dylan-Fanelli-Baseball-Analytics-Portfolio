<!-- portfolio:header -->
<sub>[← Portfolio](../README.md) &nbsp;|&nbsp; [← Skubal arsenal](2025-skubal-arsenal.md)</sub>
<!-- /portfolio:header -->

# The Edge Board, 2026: a monthly league scan

<!-- portfolio:glance -->
<p><img src="https://img.shields.io/badge/status-Oct.%2017%20run-1d5c3f" alt="status: Oct. 17 run"> <img src="https://img.shields.io/badge/data-public-1f1f1f" alt="data: public"> <img src="https://img.shields.io/badge/for-R&D%20and%20pro%20scouting-6b6b6b" alt="for: R&D and pro scouting"> <img src="https://img.shields.io/badge/method-league%20scan-b4532a" alt="method: league scan"> <img src="https://img.shields.io/badge/method-release%20tells-b4532a" alt="method: release tells"> <img src="https://img.shields.io/badge/method-projections-b4532a" alt="method: projections"></p>

**At a glance**

- **The question:** What changed across the league this month?
- **The answer:** Release tells, 292 candidate in-season pitch changes in 2026, results beyond stuff, and next-season whiff projections that cut error 6.4% on a held-out season against a regressed baseline.
- **For a club:** A list of leads for pro scouts and coaches. The toolkit rebuilds it monthly; this page shows the Oct. 17 run.
<!-- /portfolio:glance -->

*Written 2026-10-17 by Dylan Fanelli. Data: Statcast via Baseball Savant, 2024-2026 regular seasons (2,141,219 pitches). Code: `baseball/edge/` (`bb edge 2026`, then `bb board 2026`).*

The toolkit rebuilds the board monthly. These are the numbers behind the README's summary. The page was written from the Oct. 17 run and has not had a monthly refresh since; on Nov. 14 every number here was reset to the saved run's table, which moved four of them in the last digit. Revised 2026-11-14: a held-out test of the projection, and plainer labels on the pitch changes. The numbers are saved in [`outputs/edge-2026.json`](outputs/edge-2026.json).

## What it found
- **Candidate in-season pitch changes: 292 in 2026, by 225 pitchers.** A candidate counts when one pitch moved on its own (not the pitcher's whole arsenal), the label check passed (no relabel), and there were 40+ swings on each side of the date. One row per pitch, kept on its strongest signal: induced vertical break 109, arm-side break 95, velocity 59, spin 29. (The Oct. 17 page said 291 and 108; the saved table gives one more.)
  - **These are leads, not confirmed changes.** The detector tries every split date and keeps the best one, with a high bar (|t| of 6 or more, and three of four later games on the new side). How often that fires on a pitcher who changed nothing has not been measured: no permutation run exists.
  - **Did results follow?** Of the 292, 28 (9.6%) show a whiff change at p < 0.05, where chance alone gives about 5%. None clears a 5% false-discovery rate and 4 clear 10%. So most of these shape changes came with no detectable change in whiffs.
- **Results beyond stuff persist.** The gap between a pitch's actual and expected whiff rate carries over: r = 0.56 (2024 → 2025, 997 pitches) and 0.53 (2025 → 2026, 1,040).
- **Next-season whiff projection, on a season it never saw (added Nov. 14).** Weights fit on 2024 → 2025 (997 pitches) and scored on 2025 → 2026 (1,040 pitches): last season's whiff rate plus expected whiffs cut error 6.4% against a regressed last-season baseline (RMSE 5.20 vs. 5.56; 95% interval 4.9% to 8.0%, resampling pitchers). Raw last season scores 5.96. On pitches with 150 or fewer swings the year before (450 of them) it is 6.01 vs. 6.61 (`validate_holdout()` in `baseball/edge/stuff.py`).
- **The two-season version is leave-one-out, not held out.** Two seasons of results plus expected whiffs cut leave-one-out error 8.2% against a regressed last-season baseline (RMSE 4.62 vs. 5.03 on 659 pitches). Expected whiffs add 2.7 points of that. It needs three seasons per pitch, so 2026 is its only target year and no later season exists to score it on.
- **No outside benchmark.** The expected-whiff model has not been compared with a public Stuff+ on the same pitches. FanGraphs publishes Stuff+ by pitch type; the comparison needs an export of that leaderboard matched on pitcher and pitch type, and it is not done.
- **What the grades built on it mean:** the 20-80 pitch grades in the bullpen memo and the Morejón report come from this model. With a held-out gain of about 6%, a grade is a half-grade band, not a point.
- **Release tells and whiffs.** Pooled 2024-26 with errors clustered by pitcher: +0.45 whiff points per 0.1 of tell AUC (95% interval +0.09 to +0.82). With usage and context controlled it falls to +0.19 (-0.12 to +0.50), so no cost is detected.
- **The stuff model** reads swings and misses from physics alone with a cross-fitted AUC of 0.633; the portable version for TrackMan and Rapsodo data, without arm angle, is 0.631.

## League baselines
Every season-over-season change is read against the league's: for each pitch type, the distribution of every returning pitcher's change. The Skubal report uses it to settle whether his 2025 jump was him or the cameras ([report](2025-skubal-arsenal.md)): his changes sat at the 80th-98th percentile while the league median barely moved.

<!-- portfolio:footer -->
---
<sub>[← Portfolio](../README.md) &nbsp;|&nbsp; [← Skubal arsenal](2025-skubal-arsenal.md)</sub>

<sub>© 2026 Dylan Fanelli. All rights reserved. To cite: Fanelli, D. (2026). *The Edge Board, 2026: a monthly league scan*. Dylan Fanelli Baseball Analytics Portfolio. https://github.com/IForSureI/Dylan-Fanelli-Baseball-Analytics-Portfolio/blob/main/reports/2026-edge-board.md</sub>
<!-- /portfolio:footer -->
