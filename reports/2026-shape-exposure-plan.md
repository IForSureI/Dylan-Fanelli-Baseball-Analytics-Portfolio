# Does a pitch shape lose value as hitters see more of it? Analysis plan, fixed before the data is fit

*Written 2026-10-18, before any outcome in this design was computed. Dylan Fanelli. The study report will cite this file's commit and list every departure from it.*

## The question
- **The decision it serves:** bullpen ordering, pitch design and pricing.
  - If a hitter's recent diet of a shape from *other* pitchers makes that shape less effective against him, then which reliever follows whom matters beyond handedness.
  - So does which shapes a club builds, and how much a free agent's value rests on a shape that's spreading through the league.
- **What's already known:**
  - Within a game, a hitter does better against a pitch type the more he has seen of it (my familiarity study, same pitcher and earlier plate appearances).
  - No public study I could find measures the carryover across pitchers and games, by shape rather than pitch label.
  - The closest public work asks whether the sweeper's decline is hitters adapting or weaker pitchers adopting it, and leaves it open.

## Data
- Statcast pitch-level data, regular seasons 2024–2026: every pitch with batter, pitcher, date, shape, location and count.
- **Development:** 2024–2025. Any choice not written here is made on these seasons only.
- **Confirmation:** 2026. It is fit once, with the frozen specification, after the development run is committed.

## Definitions (frozen)
- **Families:** fastball (FF, SI), cutter (FC), breaking (SL, ST, SV, CU, KC, CS), offspeed (CH, FS, FO, SC).
- **Shape:** six numbers per pitch: release speed, horizontal and vertical movement (pfx_x, pfx_z), release side and height, and extension.
  - Each is standardized within family × pitcher hand, using 2024–2025 means and SDs.
  - Pitches missing any of the six are left out of both the pool and the targets.
- **A hitter's recent diet for a target pitch** (batter b, date t, pitcher j, family f, pitcher hand h, batter side s): every pitch b saw with the same f, h and s, on dates t−30 through t−1, from pitchers other than j. The current game is never in it.
  - **Total:** N30, the count of those pitches.
  - **Similar-shape exposure:** K30, the sum of exp(−d²/2) over them, where d is the distance in standardized shape space (bandwidth 1 SD).
  - **Similarity share:** S30 = K30 / N30, the share of his recent diet that looks like this pitch. It's standardized within family on the 2024–2025 targets.
- **Targets:** swings (bunt attempts excluded) on pitches with a complete shape and N30 ≥ 25.
- **Whiff:** swinging strike, blocked swinging strike or foul tip, per swing (the repo's definition), in points (×100).

## Model (frozen)
- **Linear probability model:** whiff on S30 and log(N30).
- **Fixed effects:**
  - batter × season × family (the hitter's skill against that family)
  - pitcher × pitch type × season (the pitch's own quality)
  - family × Statcast zone (location)
  - family × count
  - season × week (league-wide drift)
- **Standard errors:** clustered by batter. Coefficients are in whiff points per 1 SD of S30.

## Tests
- **H1 (primary):** on 2026, the S30 coefficient is negative and its 95% interval excludes zero.
  - **Smallest effect that matters:** 0.5 whiff points per SD.
  - If the 2026 interval includes zero, the report says "not detected" and gives the bound. If the bound rules out 0.5, it says "no effect that matters."
- **H2 (specificity):** S30 rebuilt at bandwidths 0.5 and 2 SD, each fit alone.
  - If the effect is about shape, the narrow kernel's coefficient is at least as large in magnitude as the wide one's.
  - Reported with intervals; not a pass/fail test.
- **H3 (lead placebo):** S30 rebuilt from the *next* 30 days (dates t+1 to t+30, other pitchers), added next to the real S30.
  - Its coefficient should be near zero, with an interval that includes zero.
  - If it isn't, schedule or selection is driving the result, and H1 is reported as confounded.
- **H4 (decay):** three windows that don't overlap, fit together, each as a share with its own log count: days t−7 to t−1, t−30 to t−8, and t−90 to t−31.
  - Descriptive: does recent exposure matter more than older exposure?
- **H5 (runs):** the H1 model with run value per pitch (pitcher's side, runs per 100 pitches) on all pitches, not only swings.
  - It turns the effect into runs.
- **Multiple tests:** Benjamini–Hochberg across H1, H3 and H5 on 2026.

## Decision translation (frozen)
- **Relief pitches in 2026:** the gap in expected runs per 100 pitches between the 25th and 75th percentile of S30, from the H5 coefficient, with its interval.
- **Per club per season:** scaled by a typical club's relief pitches. It's labeled an upper bound, because a manager can't always choose the low-exposure arm.

## What gets reported whatever the result
- Every test above, including failures and the placebo.
- The development-season estimates next to the 2026 estimates.
- Any departure from this plan, with the reason and the date.
