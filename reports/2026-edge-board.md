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

The toolkit rebuilds the board monthly. These are the numbers behind the README's summary. The page was written from the Oct. 17 run and has not had a monthly refresh since; on Nov. 14 every number here was reset to the saved run's table, which moved four of them in the last digit. Revised 2026-11-14: a held-out test of the projection, plainer labels on the pitch changes, and a shuffle test of how often the pitch-change detector fires by chance. Revised 2026-11-15: a benchmark of expected whiffs against Baseball Savant's public leaderboards. The numbers are saved in [`outputs/edge-2026.json`](outputs/edge-2026.json).

## What it found
- **Candidate in-season pitch changes: 292 in 2026, by 225 pitchers.** A candidate counts when one pitch moved on its own (not the pitcher's whole arsenal), the label check passed (no relabel), and there were 40+ swings on each side of the date. One row per pitch, kept on its strongest signal: induced vertical break 109, arm-side break 95, velocity 59, spin 29. (The Oct. 17 page said 291 and 108; the saved table gives one more.)
  - **About nine in ten are more than chance order (measured Nov. 14).** The detector tries every split date and keeps the best one, with a high bar (|t| of 6 or more, and three of four later games on the new side). To see how often that fires when nothing changed, each pitcher's games were put in random order and the same detector and filter were rerun: 200 shuffled seasons, seed 20261114, 868 pitchers, 2,144 pitcher-pitch series. Pitches stay in their game and a pitcher's pitch types move together.
    - A shuffled season gave about 33 candidates on average (11% of the 292). The 200 runs ranged from 20 to 50.
    - So expect about 33 of the 292 to be chance. No row says which ones.
    - About 16 of the 33 land on pitches that are on the real list. A pitch with a real change can still split by chance once its games are shuffled, so 33 is likely high for pitchers who changed nothing.
    - Why chance gets through a bar of 6: the t counts every pitch as independent, and pitches in one game move together.
  - **They are still leads.** The shuffle removes everything tied to the calendar. It cannot tell a deliberate change from slow drift, a run of games in one park, or a tracking change. In 43 of the 292, a straight line through the season fits the game averages at least as well as the step does, and those read as drift. A scout or coach has to confirm each one. Saved in [`outputs/edge-shift-null-2026.json`](outputs/edge-shift-null-2026.json) (`python -m baseball.edge.shift_null 2026`).
  - **Did results follow?** Of the 292, 28 (9.6%) show a whiff change at p < 0.05, where chance alone gives about 5%. None clears a 5% false-discovery rate and 4 clear 10%. So most of these shape changes came with no detectable change in whiffs.
- **Results beyond stuff persist.** The gap between a pitch's actual and expected whiff rate carries over: r = 0.56 (2024 → 2025, 997 pitches) and 0.53 (2025 → 2026, 1,040).
- **Next-season whiff projection, on a season it never saw (added Nov. 14).** Weights fit on 2024 → 2025 (997 pitches) and scored on 2025 → 2026 (1,040 pitches): last season's whiff rate plus expected whiffs cut error 6.4% against a regressed last-season baseline (RMSE 5.20 vs. 5.56; 95% interval 4.9% to 8.0%, resampling pitchers). Raw last season scores 5.96. On pitches with 150 or fewer swings the year before (450 of them) it is 6.01 vs. 6.61 (`validate_holdout()` in `baseball/edge/stuff.py`).
- **The two-season version is leave-one-out, not held out.** Two seasons of results plus expected whiffs cut leave-one-out error 8.2% against a regressed last-season baseline (RMSE 4.62 vs. 5.03 on 659 pitches). Expected whiffs add 2.7 points of that. It needs three seasons per pitch, so 2026 is its only target year and no later season exists to score it on.
- **Outside benchmark: Baseball Savant's public leaderboards (added Nov. 15). This is not a Stuff+ comparison.** I matched my pitch tables for 2024-2026 to two Savant tables, on MLBAM pitcher ID and pitch type, from each page's own CSV download (pulled Nov. 15).
  - **The two tables.** Pitch Arsenal Stats gives whiff% and run value per 100 pitches. Swing Timing + Miss Distance, added in June 2026, gives miss distance: how far the barrel half of the bat was from the ball, in inches, averaged over swings and misses. Miss distance is a result from games, like whiff rate. It is the closest thing Savant publishes to a stuff measure, and it is not a physics model.
  - **Matching.** Statcast pitch codes on both sides. Savant files knuckle curves under curveball, so my KC rows match its CU row. Floors: 60 swings on my side in each season; 50 pitches (Arsenal Stats) and 50 swings (Miss Distance) in Savant's files. Intervals are 95%, resampling pitchers.
  - **The pipeline matches.** My whiff rate from the pitch files sits 0.03 to 0.04 points from Savant's published whiff% on average in each season. In 2026 that is 0.04 on 1,698 pitches, and 98% equal the one decimal Savant prints. Savant counts foul tips as whiffs, as I do. Without them the gap would be about 2.1 points. The model's tables use only swings with complete tracking and sit 0.10 to 0.14 away.
  - **Same season, expected whiff tracks miss distance mostly through pitch type.** All pitches together: r = 0.71 (0.70 to 0.73) on 4,964 pitches by 888 pitchers. Each pitch against others of its type: r = 0.25 (0.21 to 0.29).
  - **It barely tracks run value.** Against Savant's run value per 100: r = 0.04 (0.01 to 0.07) together and 0.11 (0.08 to 0.14) within type, on 4,973 pitches. My actual whiff rate reaches 0.20 and 0.30. Expected whiff is a read on misses, not on run prevention.
  - **Next season's whiff rate: last season's whiff rate wins alone.** Weights fit on 2024 → 2025 (994 pitches) and scored on 2025 → 2026 (1,040 pitches, 395 pitchers), every model on the same pitches. RMSE: last season's whiff rate 5.57, my expected whiff 6.37, Savant's miss distance 6.97.
  - **Mine beats raw miss distance and ties it once pitch type is known.** Raw, mine is ahead by 0.61 (0.28 to 0.92). But miss distance does not know what pitch it is looking at: the average four-seamer here misses by 1.0 inches and the average curveball by 4.6. Given the pitch type, miss distance scores 6.03 and mine 6.18: a tie (difference 0.15, interval -0.07 to 0.39) with miss distance nominally ahead.
  - **Added to last season's whiff rate, the same picture.** Mine cuts error 6.5% (5.0% to 8.1%) against the regressed baseline. Miss distance cuts 4.2% (2.6% to 5.8%). Given the pitch type they tie at 7.2% and 7.3%. (The 6.4% above is the same test with three more pitches in the fit.)
  - **Together is best.** All three cut 7.6% (5.8% to 9.5%). Miss distance takes 0.06 (0.01 to 0.12) of RMSE off my blend, so it holds something my model lacks.
  - **Fit the other way** (2025 → 2026 weights scored on 2024 → 2025, 994 pitches): alone, 5.62, 6.83 and 7.25 in the same order. With last season's whiff rate the two tie (4.1% and 3.3%), and miss distance again adds 0.07 (0.03 to 0.11).
  - **The verdict.** My expected whiff predicts next season about as well as Savant's miss distance read within pitch type, and no better. Neither beats last season's whiff rate alone. What mine has that miss distance lacks: it needs no swings, so it can grade a bullpen session or a TrackMan pitch.
  - **Refit check.** A second fit of the model from the same pitch files moves expected whiff 0.5 points per pitch on average (r = 0.996 between fits). The verdicts are the same and the gain is 6.5%.
  - Saved in [`outputs/edge-savant-benchmark-2026.json`](outputs/edge-savant-benchmark-2026.json) (`python -m baseball.edge.savant_benchmark 2026`). The downloaded Savant files stay out of the repository.
- **Still open: a Stuff+ benchmark.** I have not compared the model with a public Stuff+ on the same pitches.
  - FanGraphs publishes Stuff+ by pitch type: one column each for FA, SI, FC, FS, SL, CU, CH, KC and FO (read on its leaderboard page Nov. 15). The export is for members only.
  - Needs: that leaderboard exported as CSV for 2025 and for 2026 (pitchers, no innings minimum, with player IDs), matched here on pitcher and pitch type. That table has no sweeper column, so Statcast sweepers and sliders need one mapping rule.
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
