# The Edge Board, 2026: a monthly league scan

*Written 2026-10-17 by Dylan Fanelli. Data: Statcast via Baseball Savant, 2024-2026 regular seasons (2,141,219 pitches). Code: `baseball/edge/` (`bb edge 2026`, then `bb board 2026`).*

The board is rebuilt on the 1st of every month. These are the numbers behind the README's summary, from the Oct. 17 run.

## What it found
- **Hidden in-season pitch changes: 291 in 2026, by 225 pitchers.** A change counts when one pitch moved on its own (not the pitcher's whole arsenal), the label check passed (no relabel), and there were 40+ swings on each side of the date. One row per pitch, kept on its strongest signal: induced vertical break 108, arm-side break 95, velocity 59, spin 29.
- **Results beyond stuff persist.** The gap between a pitch's actual and expected whiff rate carries over: r = 0.56 (2024 → 2025, 997 pitches) and 0.53 (2025 → 2026, 1,040).
- **Next-season whiff projection.** Two seasons of results plus expected whiffs cut leave-one-out error 8.1% against a regressed last-season baseline (RMSE 4.62 vs. 5.03 on 659 pitches). Expected whiffs add 2.6% of that.
- **Release tells and whiffs.** Pooled 2024-26 with errors clustered by pitcher: +0.45 whiff points per 0.1 of tell AUC (95% interval +0.10 to +0.81). With usage and context controlled it falls to +0.18 (-0.13 to +0.49), so no cost is detected.
- **The stuff model** reads swings and misses from physics alone with a cross-fitted AUC of 0.633; the portable version for TrackMan and Rapsodo data, without arm angle, is 0.630.

## League baselines
Every season-over-season change is read against the league's: for each pitch type, the distribution of every returning pitcher's change. The Skubal report uses it to settle whether his 2025 jump was him or the cameras ([report](2025-skubal-arsenal.md)): his changes sat at the 80th-98th percentile while the league median barely moved.
