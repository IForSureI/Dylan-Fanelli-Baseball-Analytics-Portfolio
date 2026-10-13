# The Reliability Atlas: which numbers to trust, and when (MLB 2024–26)

**League study from public pitch data.** Every regular-season pitch of 2024, 2025 and 2026 (Statcast), not a scouting look. For 157 pitcher and hitter metrics it measures how fast each one becomes signal, how much of it carries into the next season, how much a player's true level moves within a season, and how far to regress. The regression function was tested out of sample before anything here was called a result.
*Written 2026-10-13 · Dylan Fanelli · Data: Statcast via Baseball Savant, 2,134,079 pitches, 7,288 games, 1,310 pitchers, 905 batters · Code: `baseball/evaluation/reliability.py` · Not yet independently reviewed*

![The atlas: how fast each metric becomes signal against how much it carries over](figures/2026-reliability-atlas.png)

## The answer
**How to read the tables.**
- **M** is the sample, in the metric's own events, at which split-half reliability reaches 0.5. At that point signal and noise are equal, so you regress halfway. It is also the regression constant: estimate = (n × observed + M × league) / (n + M).
- **n for r = 0.7** is 7M/3 under the fitted curve. Where the measured curve disagrees by more than 25%, the observed crossing is shown too.
- **ρ (rho)** is the year-to-year correlation of true talent: same players, same sample size, between-season correlation divided by within-season reliability. 1.0 means the skill carries over completely.
- **Drift** is the standard deviation of a player's true change from the first half of a season to the second, net of sampling noise.
- **Intervals** are 95%, from a bootstrap of players.
- **"No signal"** means within-season reliability stayed under 0.2 at the largest sample the data allow.

**Hitters**

| Metric | n counts | M (95% CI) | M in PA | n for r = 0.7 | ρ year to year (95% CI) | Drift SD |
|---|---|---|---|---|---|---|
| Bat speed | competitive swings | 2.6 (2.4–2.9) | 1.6 | 6.1 | 0.92 (0.90–0.93) | 0.66 mph |
| Swing path tilt | competitive swings | 2.9 (2.6–3.2) | 1.8 | 6.7 | 0.92 (0.91–0.94) | 1.0° |
| Swing length | competitive swings | 4.6 (4.1–5.2) | 2.8 | 11 | 0.94 (0.93–0.95) | 0.11 ft |
| Fast-swing rate (75+ mph) | competitive swings | 4.8 (4.2–5.4) | 3.0 | 11 | 0.92 (0.90–0.94) | 5.6 pts |
| Attack angle | competitive swings | 10 (9–11) | 6.2 | 23 | 0.87 (0.85–0.89) | 1.5° |
| Attack direction | competitive swings | 19 (18–21) | 12 | 45 | 0.86 (0.83–0.88) | 1.9° |
| Whiff per swing | swings | 55 (49–63) | 30 | 129 | 0.93 (0.91–0.95) | 2.4 pts |
| Zone contact | swings in the zone | 58 (51–67) | 45 | 136 | 0.90 (0.87–0.93) | 1.9 pts |
| Zone swing | pitches in the zone | 63 (56–71) | 33 | 147 | 0.84 (0.81–0.87) | 3.0 pts |
| Chase | pitches outside the zone | 65 (59–72) | 33 | 152 | 0.91 (0.89–0.93) | 2.7 pts |
| Swing % | pitches | 97 (88–107) | 25 | 227 | 0.85 (0.82–0.88) | 2.9 pts |
| Average exit velocity | balls in play | 32 (28–36) | 46 | 74 | 0.94 (0.91–0.97) | 0.29 mph |
| Hard-hit % (95+) | balls in play | 44 (39–50) | 64 | 102 | 0.95 (0.92–0.98) | 2.2 pts |
| Average launch angle | balls in play | 43 (38–49) | 63 | 101 | 0.91 (0.87–0.94) | 2.1° |
| Barrel % | balls in play | 53 (46–61) | 77 | 123 | 0.92 (0.88–0.96) | 1.7 pts |
| xwOBA on contact | balls in play | 64 (55–74) | 94 | 149 | 0.92 (0.88–0.97) | .016 |
| Pull % | balls in play | 86 (76–98) | 126 | 201 (beyond data) | 0.93 (0.88–0.98) | 2.7 pts |
| wOBA | PA | 511 (374–699) | 511 | 1,192 (beyond data) | too imprecise (0.92, 0.55–1.30) | .019 |
| Run value per 100 pitches | pitches | 1,985 (1,482–2,659) | 506 | 4,632 (beyond data) | too imprecise (0.90, 0.54–1.26) | 0.52 |

**Pitchers, all pitches**

| Metric | n counts | M (95% CI) | M in BF | n for r = 0.7 | ρ year to year (95% CI) | Drift SD |
|---|---|---|---|---|---|---|
| Ground-ball % | balls in play | 56 (48–65) | 81 | 130 (observed: r = 0.68 at 181) | 0.92 (0.88–0.96) | 1.5 pts |
| Whiff per swing | swings | 121 (108–137) | 65 | 283 (observed 456) | 0.91 (0.87–0.94) | 2.0 pts |
| Hard-hit % (95+) | balls in play | 271 (229–320) | 396 | 632 (beyond data) | 0.93 (0.78–1.09) | 0 |
| Zone % | pitches | 300 (264–341) | 77 | 700 (observed 1,005) | 0.86 (0.80–0.91) | 1.7 pts |
| Chase | pitches outside the zone | 313 (271–362) | 157 | 731 (beyond data) | 0.85 (0.77–0.93) | 1.5 pts |
| Called-strike % | pitches | 396 (343–458) | 101 | 925 (observed: r = 0.62 at 1,024) | 0.82 (0.75–0.90) | 0.7 pts |
| CSW | pitches | 438 (384–500) | 112 | 1,023 (observed: r = 0.62 at 1,024) | 0.85 (0.78–0.91) | 1.2 pts |
| Run value per 100 pitches | pitches | 1,932 (1,560–2,394) | 493 | 4,508 (beyond data) | too imprecise | 0.29 |
| xwOBA on contact | balls in play | no signal (r = 0.15 at 181) | | | too imprecise | |
| Barrel % | balls in play | no signal (r = 0.18 at 181) | | | too imprecise | |

**Pitchers, by pitch type: M (pitches of the type, or swings / balls in play of it)**

| Metric | FF | SI | FC | SL | ST | CU | CH | FS |
|---|---|---|---|---|---|---|---|---|
| Velocity, spin, arm angle, extension | <1.5 | <1.5 | <1.5 | <1.5 | <1.5 | <1.5 | <1.5 | <1.5 |
| Induced vertical break | 1.8 | <1 | 1.8 | 1.5 | 1.6 | <1 | <1 | 1.9 |
| Horizontal break | 1.2 | 2.5 | 2.3 | 1.3 | 3.1 | <1 | 2.5 | 2.5 |
| Whiff per swing | 77 | 92 | 75 | 41 | 57 | 53 | 42 | 38 |
| Ground-ball % | 52 | 40 | 49 | 60 | 66 | no signal | 40 | 53 |
| Chase | 128 | 69 | 103 | 90 | 101 | 78 | 64 | 113 |
| Zone % | 149 | 112 | 101 | 78 | 82 | 65 | 54 | 52 |
| Called-strike % | 139 | 110 | 131 | 105 | 62 | 50 | 112 | 97 |
| CSW | 232 | 194 | 200 | 109 | 123 | 125 | 89 | 108 |
| Hard-hit % | no signal | 92 | no signal | 101 | no signal | 57 | 57 | 73 |
| xwOBA on contact, barrel %, run value | no signal | no signal (xwOBAcon on sinkers: 163) | no signal | no signal | no signal | no signal | no signal | no signal |

**By pitch type: ρ year to year** ("–" means too imprecise to use, SE above 0.15)

| Metric | FF | SI | FC | SL | ST | CU | CH | FS |
|---|---|---|---|---|---|---|---|---|
| Arm angle | 0.97 | 0.98 | 0.97 | 0.97 | 0.97 | 0.96 | 0.96 | 0.96 |
| Extension | 0.97 | 0.97 | 0.96 | 0.97 | 0.97 | 0.95 | 0.96 | 0.97 |
| Velocity | 0.94 | 0.95 | 0.91 | 0.89 | 0.92 | 0.94 | 0.95 | 0.95 |
| Spin rate | 0.93 | 0.94 | 0.94 | 0.95 | 0.95 | 0.97 | 0.91 | 0.92 |
| Induced vertical break | 0.94 | 0.95 | 0.83 | 0.78 | 0.86 | 0.94 | 0.90 | 0.89 |
| Horizontal break | 0.93 | 0.91 | 0.81 | 0.90 | 0.78 | 0.91 | 0.86 | 0.88 |
| Whiff per swing | 0.86 | 0.91 | 0.69 | 0.94 | 0.86 | 0.92 | 0.83 | 1.02 |
| Chase | 0.88 | 0.85 | 0.61 | 0.85 | 0.89 | 0.77 | 0.85 | – |
| Zone % | 0.82 | 0.72 | 0.79 | 0.75 | 0.86 | 0.84 | 0.73 | 0.85 |
| CSW | 0.73 | 0.81 | 0.65 | 0.89 | 0.84 | 0.83 | 0.90 | – |
| Ground-ball % | 0.98 | 0.91 | 0.88 | 0.78 | – | – | 0.81 | – |

The full table (every metric, CIs, τ, M among full-time players, per-season-pair ρ) is `data/edge/reliability/params.parquet`. The shipped constants are in `baseball/evaluation/reliability_params.json`.

## Summary
- **Regressing helps, out of sample, and never hurt.**
  - **The setup:** parameters were fit on 2024–25 only.
  - **Within the season:** shrinking 2026 first-half values cut the error in predicting second-half values for 133 of 147 metrics. The cut is significant for 99, and the median RMSE cut is 26.7%.
  - **The next season:** for 2025 → 2026 the error fell for 89 of 96 metrics (significant for 69; median cut 15.6%).
  - **No metric got significantly worse** in either test. Only 2 of 602 metric × sample-size cells did, both in the largest-sample bucket.
- **The intervals are honest only once two more numbers are priced.**
  - **The two numbers:** year-to-year persistence (ρ) and in-season drift.
  - **Next season:** with ρ, 95% intervals covered a median 95.3% of outcomes and 80% intervals covered 81.8%. Using the within-season weight alone gave 75% and 57%.
  - **Within the season:** adding drift raised the 10th-percentile metric's coverage from 74% to 93% (95% intervals).
- **The five results a club analyst wouldn't have found in the public tables:**
  1. **Swing tracking reads faster than anything else measured on a hitter, and it sticks.**
     - **Speed:** bat speed reaches r = 0.5 at 2.6 competitive swings and r = 0.7 at about 6 (one game). Swing path tilt and swing length are almost as fast.
     - **Persistence:** all carry over at ρ = 0.92–0.94.
     - **The exception:** attack angle and attack direction take 10 and 19 swings, carry over less (0.87, 0.86), and drift about 0.44 talent-SDs within a season against 0.24 for bat speed. They are the parts of the swing a hitter chooses, not the parts he's built with.
  2. **A pitch-by-pitch split overstates reliability whenever days differ.**
     - **Velocity:** splitting by game, M for fastball velocity is 4.7 times what a pitch-by-pitch split says (0.96 vs 0.21 pitches); slider velocity 7.7 times.
     - **Bat tracking:** 1.3–1.4 times.
     - **Plate discipline:** 1.05–1.16 times.
     - **Prior work:** the public "2 swings" bat-speed figure is matched by our pitch-level split (2.1). By game it is 2.6.
  3. **M belongs to a metric and a population, not a metric.**
     - **What stays fixed:** the noise in one plate appearance is a property of wOBA (variance 0.25–0.29 per PA at every sample size).
     - **What changes:** the spread of true talent shrinks among full-time players. The covariance of the halves gives a true-talent SD of .035 across nearly all hitters (6-PA halves) and .020 among hitters with 512+ PA (256-PA halves).
     - **The effect:** M rises from 511 to 628. For pitcher whiff rate, the fitted curve says r = 0.7 at 283 swings, but the measured curve gets there at 456, because only starters reach that sample.
     - **The implication:** stabilization points computed on regulars don't transfer to part-timers.
  4. **Contact quality and chase are hitter traits far more than pitcher traits.**
     - **Contact quality:** hitters' xwOBA on contact reaches r = 0.5 at 64 balls in play. Pitchers' never reaches 0.2 in a season (0.15 at 181 balls in play).
     - **Hard-hit rate:** 44 vs 271 balls in play.
     - **Chase:** 65 vs 313 out-of-zone pitches.
     - **The pitcher-side exception:** ground-ball rate, at 56 balls in play, with ρ = 0.92.
  5. **Pitch physics is readable from one pitch, but it moves within a season.**
     - **Reliability:** a single fastball's velocity correlates 0.83 with another game's.
     - **Movement in season:** a pitcher's true fastball velocity changes by a standard deviation of 0.55 mph from the first half of a season to the second.
     - **Breaking-ball shape is the least stable across seasons:** slider IVB and sweeper horizontal break have ρ = 0.78, against 0.94–0.95 for four-seam and sinker IVB.

## What a club can do with it
1. **Regress every number with `regress()`, and pick the horizon.** Worked examples below, hypothetical players against 2026 league means, with the shipped 2024–26 constants. Each row reads: estimate, then 95% interval.

   | Player | This season's level | Rest of this season | Next season |
   |---|---|---|---|
   | Hitter: 40.0% whiff in 50 swings (league 25.1%) | 32.2% (23.4–40.9) | 32.2% (22.2–42.1) | 31.7% (22.4–41.0) |
   | Hitter: 75.0 mph bat speed in 30 competitive swings (league 72.1) | 74.8 (73.2–76.3) | 74.8 (72.8–76.8) | 74.5 (72.0–77.1) |
   | Changeup: 45% whiff on 40 swings (league 31.4%) | 38.0% (27.8–48.2) | 38.0% (27.2–48.8) | 36.9% (25.3–48.5) |
   | Hitter: .400 wOBA in 150 PA (league .324) | .341 (.302–.380) | .341 (.287–.395) | not given (ρ too imprecise) |

   **How to read it:**
   - **Bat speed:** 30 swings already carry 92% weight.
   - **wOBA:** 150 PA carry 23%.
   - **The interval:** it is for the player's true level. To bracket a future observed rate over n2 events, add M τ²/n2 to its variance.
2. **Use swing tracking as the first read on a new hitter.**
   - **What a week tells you:** a week of competitive swings is enough to know bat speed and tilt (r ≥ 0.85 by 16–23 swings) and swing length (0.83 at 23).
   - **What it doesn't:** that same week says almost nothing about his wOBA (r = 0.05 at 16 PA).
   - **Watch attack angle and direction over time.** They are the ones that move.
3. **Don't evaluate pitchers on contact quality allowed within a season.**
   - **xwOBA on contact and barrels allowed:** no measurable signal within a season.
   - **Hard-hit allowed:** needs about 400 batters faced to reach r = 0.5.
   - **What to use instead:** ground-ball rate, whiff rate and pitch physics, which become reliable in weeks.
4. **For velocity and shape, count outings, not pitches.**
   - **The noise is day to day.** A 100-pitch sample from one game is much less informative than the pitch count implies.
   - **A drop is not proof of decline.** Net of noise and the league's own shift, pitchers' true fastball velocity moves by a standard deviation of 0.55 mph between the halves of a season, so a 0.5 mph change is ordinary on its own.
5. **Quote a stabilization point with its population.** "Whiff rate is reliable at N" is true for some set of players. For full-time players the same metric needs more sample.

## Findings

### 1. Swing tracking: fastest to read, and the swing-plane choices move
| Metric (competitive swings) | M | r at 11 swings | ρ | Drift / talent SD |
|---|---|---|---|---|
| Bat speed | 2.6 | 0.81 | 0.92 (0.90–0.93) | 0.24 |
| Swing path tilt | 2.9 | 0.79 | 0.92 (0.91–0.94) | 0.26 |
| Swing length | 4.6 | 0.70 | 0.94 (0.93–0.95) | 0.27 |
| Attack angle | 10.0 | 0.52 | 0.87 (0.85–0.89) | 0.43 |
| Attack direction | 19.4 | 0.36 | 0.86 (0.83–0.88) | 0.44 |

- **Bat speed, tilt and length behave like physical traits:**
  - one or two games read them
  - they carry over at 0.92–0.94
  - they move little within a season
- **Attack angle and direction behave like approach:**
  - slower to read
  - less persistent
  - drift nearly twice as much relative to their spread
- **Compared with results:** a hitter's whiff rate (M = 55 swings) needs 20 times the sample of his bat speed.
- **Definition:** "competitive swings" is Statcast's rule, the fastest 90% of a batter's swings plus any 60+ mph swing hit 90+ mph.
  - **The concern:** the 90% cut comes from his whole season, so both halves share it.
  - **The check:** with a fixed 50 mph floor instead, bat speed's M is 4.3 swings (3.9–4.8). The conclusion (under two games) holds.

### 2. Splitting by game is not a detail
Each row is M from a split by game (halves never share a game) against M from a split by single events (what a pitch-level random split does). Both use the same data, 40 splits each.

| Metric | M, by game | M, by pitch | Ratio |
|---|---|---|---|
| Slider velocity | 0.88 | 0.12 | 7.7 |
| Four-seam velocity | 0.96 | 0.21 | 4.7 |
| Four-seam IVB | 1.83 | 0.44 | 4.1 |
| Four-seam arm angle | 0.24 | 0.06 | 4.0 |
| Four-seam spin | 1.42 | 0.41 | 3.5 |
| Swing path tilt | 2.84 | 2.02 | 1.4 |
| Attack angle | 9.97 | 7.43 | 1.3 |
| Bat speed | 2.63 | 2.06 | 1.3 |
| Four-seam whiff (pitchers) | 79 | 63 | 1.3 |
| Hitter whiff | 55 | 48 | 1.2 |
| Hitter chase | 64 | 62 | 1.05 |
| Hitter exit velocity | 32 | 30 | 1.04 |

- **Why:** a day's conditions (opponent, park, weather, how the player feels) are shared by every pitch that day. A pitch-level split puts the same day in both halves, so that shared part counts as skill.
- **Where it matters:** most for pitch physics, where day-to-day swings are large next to pitch-to-pitch noise (a pitcher's game-average fastball varies by 0.68 mph SD within a season).
- **Where it doesn't:** least for hitters' chase and exit velocity (1.04–1.05). Why those two are nearly immune wasn't tested.
- **A check on fictional data:** a simulated league with a day effect recovered the theoretical M by game (3.3 against 3.5) while the pitch split said 1.2 (tests).

### 3. The same metric, different populations
| Metric | M within one game | M (all players) | M among full-time players | True-talent SD from half covariances, all → full-time |
|---|---|---|---|---|
| Hitter wOBA (PA) | 192 | 511 | 628 | .030 → .021 |
| Pitcher whiff (swings) | 65 | 121 | 156 | 4.4 → 3.9 pts |
| Pitcher CSW (pitches) | 193 | 438 | 528 | 2.2 → 1.9 pts |
| Pitcher chase (out-of-zone pitches) | 219 | 313 | 442 | 2.9 → 2.3 pts |
| Hitter whiff (swings) | 50 | 55 | 59 | 6.2 → 5.9 pts |

- **The noise per event barely changes.** wOBA's is 0.25 per PA in 6-PA halves and 0.29 in 256-PA halves.
- **What changes is who can be measured.** Only regulars have 2n events, and regulars are more alike.
- **Hitter plate discipline barely moves.** Pitcher outcome metrics move a lot, because starters and relievers differ.
- **The headline M** is fit on halves of at least one game's worth of events, weighted by player-seasons. It describes the broad population that `regress()` is applied to.
- **"Within one game"** is the curve below one game's worth. Its M is smaller for two reasons: a half inside one game carries that day's swing once rather than once per event, so the per-event model doesn't apply, and the population at small n is the broadest.
- **The practical cost of choosing one M is small.** In validation, the M that would have minimized the error on the test data was 0.71–1.44 times ours (interquartile range, within-season test). Using ours instead of that best M cost a median 0.2% of RMSE (90th percentile 1.8%).

### 4. Hitter traits and pitcher traits
| Metric | Hitters: M (≈ PA) | ρ | Pitchers: M (≈ BF) | ρ |
|---|---|---|---|---|
| Whiff per swing | 55 (30) | 0.93 | 121 (65) | 0.91 |
| Chase | 65 (33) | 0.91 | 313 (157) | 0.85 |
| Ground-ball % | n/a | | 56 (81) | 0.92 |
| Hard-hit % | 44 (64) | 0.95 | 271 (396) | 0.93 (0.78–1.09) |
| Barrel % | 53 (77) | 0.92 | no signal | |
| xwOBA on contact | 64 (94) | 0.92 | no signal (r = 0.15 at 181 balls in play) | |

- **Contact quality is the hitter's.** Pitchers' xwOBA on contact shows no measurable within-season signal for any of the eight pitch types (the best is r = 0.24 on sinkers).
- **Chase is mostly the hitter's too.** A pitcher's chase rate takes 5 times the sample of a hitter's.
- **Pitchers' hard-hit rate:** where it can be measured, it does persist (ρ = 0.93), but with a wide interval, and only after about 400 batters faced.
- **Pitch types:** whiff rates on breaking balls and offspeed read twice as fast as on fastballs (M of 38–57 swings against 75–92).
  - **Why:** their true-talent spread is larger (SD 6.3–8.0 points against 3.7–5.0).

### 5. What changes within a season and across seasons
- **Within a season:** among pitcher metrics measured precisely, drift is largest relative to talent spread for zone% (0.60 talent-SDs) and CSW (0.56). It is smallest for arm angle and extension (0.12–0.18).
  - **What zone% drift means:** command and approach move inside a season more than stuff does.
- **Across seasons:** cutters are the least stable pitch on whiff (ρ = 0.69, 0.46–0.93) and chase (0.61). Breaking-ball shape is less stable than fastball shape.
  - **The likely reasons:** redesigned pitches, and pitches Statcast relabels between slider and sweeper, which this study treats as different pitches. Neither was tested here.
- **The two season pairs agree** for most metrics (hitter whiff 0.92 and 0.95; bat speed 0.92 and 0.92; pitcher GB% 0.95 and 0.90).
  - **The exceptions:** metrics whose ρ is flagged "too imprecise". wOBA's pairs read 1.09 and 0.61.

### 6. Validation: out of sample, by sample size
**The setup:**
- **Fit:** every parameter came from 2024–25.
- **Within season:** 2026 first half (games on or before the league's median pitch date) → second half. Prior = first-half league mean.
- **Next season:** 2025 → 2026. Prior = 2025 league mean.
- **Scoring:** errors are relative to the league (each period's league-wide shift is removed), and every player counts once.
- **The sample:** 41,063 player-metric pairs within season and 36,887 next season.

**RMSE cut from regressing (median across metrics), by the first sample's size in units of M:**

| First sample | Within season | Next season |
|---|---|---|
| Under M/4 | 52% (85 of 87 metrics significant) | 55% (45 of 47) |
| M/4 to M | 21% (71 of 94) | 24% (42 of 51) |
| M to 3M | 9.5% (50 of 77) | 11% (41 of 56) |
| 3M and up | 1.9% (35 of 95; 2 significantly worse) | 4.1% (53 of 95) |
| All players | 26.7% (99 of 147) | 15.6% (69 of 96) |

**Interval coverage (median across metrics, 10th-percentile metric in parentheses):**

| Test | 80% intervals | 95% intervals |
|---|---|---|
| Within season, with drift | 83% (78%) | 96% (93%) |
| Within season, no drift | 76% (57%) | 93% (74%) |
| Next season, with ρ | 82% (76%) | 95% (93%) |
| Next season, within-season weight only | 57% (35%) | 75% (50%) |

**Selected metrics (RMSE cut, all players, 95% CI):**

| Metric | Within season | Next season |
|---|---|---|
| Hitter whiff | 15% (5–24) | 31% (16–44) |
| Hitter chase | 28% (19–36) | 22% (13–31) |
| Hitter barrel % | 29% (18–39) | 25% (14–35) |
| Hitter xwOBA on contact | 29% (19–37) | 18% (11–26) |
| Hitter wOBA | 51% (27–65) | not tested (ρ too imprecise in 2024–25) |
| Hitter bat speed | 2.5% (−1.4 to 6.0) | 44% (0.3–62) |
| Pitcher whiff | 27% (15–40) | 12% (4–20) |
| Pitcher CSW | 28% (22–34) | 25% (17–32) |
| Pitcher xwOBA on contact | 36% (27–44) | not tested |
| Four-seam velocity | −2.5% (−5.3 to 0.7) | 0.1% (−2.0 to 2.2) |

- **Where regressing matters:** small samples, which is where decisions get made on too little data (call-ups, April, relievers).
- **Bat speed and velocity:** regressing changes almost nothing within a season, because M is a handful of events. A season of bat speed still needs regressing for next year (44% cut, driven by the few hitters with very few swings, hence the wide interval).
- **"Next season, within-season weight only"** has nearly the same point accuracy as using ρ, but its intervals are far too narrow. ρ matters for the uncertainty more than for the estimate.

## Method
**Grain.** One row per pitch, regular season only. Pitch-clock automatic balls and strikes are dropped because no pitch was thrown.

**Each metric's events are its own denominator:**
- swings for whiff
- pitches outside the zone (Statcast zones 11–14) for chase
- balls in play for contact metrics
- competitive swings for bat tracking
- wOBA-denominator PAs for wOBA
- pitches of the type for pitch-type metrics

**Definitions:**
- **Flags:** swing and whiff flags are the repo's (`arsenal.SWINGS`, `WHIFFS`).
- **Batted balls:** hard-hit is 95+ mph; barrel is Statcast's `launch_speed_angle` = 6; ground balls are Statcast's `bb_type`.
- **Run value:** `delta_run_exp` (pitcher's view for pitchers), per 100 pitches.
- **Pull:** a ball in play more than 15° to the batter's pull side of straightaway center, with spray angle from `hc_x`, `hc_y` around home plate at (125.42, 198.27). The foul lines fall at about ±45° in this data.
- **Attack direction:** flipped so pull is positive. In Statcast it is batter-relative with pull negative for both sides (checked against spray angle: +0.32 for righties, −0.29 for lefties).

**Split-half reliability:**
- **The split:** for each player-season (pitcher-season-pitch type for pitch metrics), shuffle his games and deal them alternately into two halves. A pitcher's games go to the same half for every pitch type.
- **The sample:** fill each half in shuffled order until it holds exactly n events. The last game contributes its first k events in pitch order.
- **The correlation:** the double-entry (intraclass) correlation of the halves across players, centered by season and pooled over seasons.
- **Repeats:** 200 random splits at 23 sample sizes, from 1 to 2,896 events. A point needs 50 or more player-seasons.

**Spearman–Brown, applied correctly.**
- **No correction is needed here:** each half holds exactly n events, so the correlation is already the reliability of n.
- **The common mistake:** splitting a season of N into halves of N/2 and quoting their correlation as the reliability of N. The right step-up is 2r/(1 + r), which equals N/(N + M) under the fitted curve (`stats.spearman_brown`, tested to agree exactly).
- **Example:** a hitter with 500 swings has whiff-rate reliability 500/555 = 0.90.

**The curve.**
- **The fit:** r(n) = n/(n + M), by weighted least squares (weights = player-seasons at each n). It uses only halves of at least one typical game's worth of events. Below that, a half sits inside one game and the curve has a different shape (Finding 2).
- **The other parameters:** σ², the noise variance of one event, is measured directly at each n as (variance of a half − covariance of the halves) × n, averaged over the same points. True-talent variance is then τ² = σ²/M, so r(n) = τ²/(τ² + σ²/n) = n/(n + M) holds exactly. The plain average covariance (`tau_cov`) is kept as a diagnostic; it differs because talent spread shrinks with n (Finding 3).
- **The model is an approximation.** Where it misfits, the table shows the observed crossing. This happens for pitch physics, because of day effects, and for metrics only full-time players reach at large n.

**Year to year (ρ).**
- **The design:** the same random-split machinery, with the player (and pitch type) matched across 2024→25 and 2025→26.
- **The estimate:** ρ = covariance between a season-1 half and a season-2 half (all four pairings, same n) divided by the within-season half covariances. This is the correlation of true talent, corrected for noise at that n.
- **Choosing n:** ρ is computed at every n with 100+ matched players and within-season r ≥ 0.2, and the most precise n is reported. For most metrics the estimates at different n agree within a few hundredths (bat speed 0.92–0.93, hitter whiff 0.91–0.93); the imprecise ones wander more (pitchers' hard-hit rate 0.75–0.93). Every range is in the table file (`rho_range_n`).
- **When it's used:** `regress()` uses ρ, clipped to 1, only if its SE is 0.15 or less.

**In-season drift.**
- **The split:** each season splits at the league's median pitch date.
- **Per player:** for each player-season with 4+ games in each half, take d = second-half mean − first-half mean. Each half's sampling noise is measured inside that half, by dealing its games at random into two sets: noise = (mean_X − mean_Y)² n_X n_Y / (n_X + n_Y)², averaged over 40 deals.
- **The estimate:** drift variance = mean(d² − noise₁ − noise₂) − mean(d)².
- **Why games:** games are the unit, so day-to-day swings count as noise, not drift.
- **A rejected first version:** an earlier estimator compared chronological with random halves. It was biased toward zero when players have few games and large day effects, and it failed a fictional test that this version passes.

**Uncertainty.**
- **Bootstrap:** 100 bootstrap draws of players are fixed in advance. Each draw is a multinomial count per player, shared across seasons so a player's seasons stay together.
- **Applying them:** every random split is scored under every draw (the sums are linear in the weights).
- **Why this design:** each draw's estimate is pooled over all 200 splits, so the spread across draws is player-sampling uncertainty, not split noise.
- **Calibrated on 30 fictional leagues with known truth:**
  - **ρ:** SE 0.038 against an actual spread of 0.037; 93% coverage.
  - **log M:** SE 0.074 against 0.058, so the M intervals are mildly conservative.

**The deliverable.**
- **The function:** `regress(metric, observed, n, league_mean, horizon)`. It is a normal–normal posterior:
  - **Weight:** w = n/(n + M).
  - **This season:** estimate = mean + w(observed − mean), SD = τ√(1 − w).
  - **Rest of season:** the same estimate, SD = √(τ²(1 − w) + drift²).
  - **Next season:** estimate = mean + ρw(observed − mean), SD = τ√(1 − ρ²w).
- **Why rest of season keeps the season weight:**
  - **The test:** an earlier version shrank toward the mean in proportion to in-season persistence.
  - **The result:** it made velocity, arm angle and extension forecasts significantly worse than raw.
  - **The conclusion:** in-season change behaves like drift, not reversion to the mean.
- **The constants** are shipped as JSON so the function works without the data. They are dated 2026-10-13, pooled 2024–26.

**Evidence standard.**
- **Confirmed:** p < 0.05 with enough sample.
- **Intervals** are 95%.
- **A CI from a bootstrap that includes 0** is called not significant.
- **"No signal"** is a statement about this data's sample sizes, not a claim that the skill doesn't exist.

## What this doesn't show
- **Three seasons, MLB only, regular season only.**
  - **ρ** comes from two season pairs.
  - **No postseason, minors or college.** The private repo's TrackMan and Rapsodo data would need its own atlas, because device noise differs.
- **The prior is the league mean.**
  - **The bias:** players who get few chances are, on average, worse. Shrinking a call-up toward the league mean is generous.
  - **The size:** validation shows the cost is small for these metrics, but a club prior by role or playing time would do better. That wasn't built here.
- **Populations differ (Finding 3).**
  - **The shipped M** describes the broad population.
  - **For full-time players,** use `M_fulltime` from the table file, or pass your own `tau`: M = σ²/τ² with σ² from the shipped constants.
- **Normal approximations.** For rare-event rates (barrel%) the posterior is skewed. Coverage held near nominal, and rate intervals are clipped to [0, 1].
- **ρ below 1 mixes real change with changed context:** new park, new catcher (framing affects called strikes), a new role, injuries. They weren't separated.
- **Pitch labels are Statcast's.** A slider relabeled as a sweeper becomes a new pitch, which lowers ρ for breaking-ball shape. That isn't measured.
- **xwOBA is Statcast's model**, so its reliability inherits that model's choices.
- **Not tested:** whether reliability differs by hitter or pitcher type, for example whether power hitters' contact quality stabilizes faster.

## What's new against prior public work
| Metric | Prior public estimate (date) | How it was measured | This atlas |
|---|---|---|---|
| Ground-ball rate, pitchers | 70 BIP to r = .70 (Carleton, BP, May 9, 2013) | KR-21 on events, pitchers with 2,000+ BF, 2003–12 | 130 BIP from the fit; observed r = 0.68 at 181 BIP |
| Exit velocity, hitters | r = .73 at 50 BIP (Carleton, BP, Apr 19, 2016) | 10/10 split within 20-PA frames, 2015 Statcast, 154 hitters with 300+ BIP | r = 0.58 at 45 and 0.65 at 64 BIP; r = .70 at 74–79 |
| Bat speed | "Regression amount of two swings" (Tango, random pitch-level split), "three swings" (FanGraphs test), both reported by Rosenblum, RotoGraphs, May 20, 2024 | 2024 data, early season | M = 2.6 competitive swings by game; 2.1 with a pitch-level split |
| Swing path tilt | r = .80 at 11 swings (Salorio, June 6, 2025) | not stated beyond a Tango-style method | r = 0.79 at 11 swings (0.77–0.81) |
| Attack angle | r = .80 at 40 swings (Salorio, June 6, 2025) | same | r = 0.76 at 32, 0.82 at 45 |
| Stuff+ | "reliable 80 pitches into the season" (McGrattan, FanGraphs Library, Mar 10, 2023) | Cronbach's alpha | not comparable (no Stuff+ here). Velocity, spin and shape: a single pitch correlates 0.83+ with another game's |

**Where this atlas agrees:** with the swing-path figures, where its numbers match.

**Where it disagrees:**
- **Pitcher ground-ball rate:** it finds a slower read, about twice the BIP for r = 0.7.
- **Hitter exit velocity:** about 1.5 times. The 2016 EV study used 2015 Statcast, which missed some batted balls, as readers noted at the time.
- **Not tested here:** which differences in data and method explain the gaps.

**What is new:**
- **Coverage:** reliability for the 2024+ bat-tracking and swing-path metrics and the Hawk-Eye pitch metrics (arm angle, extension, per-pitch-type physics) in one place.
- **Game-level splitting** and what it changes (Finding 2).
- **The population dependence of M** (Finding 3).
- **Year-to-year persistence and in-season drift** on the same footing as reliability.
- **A regression function with intervals,** validated out of sample by sample size, with calibrated coverage.

## Reproduce
```bash
uv run bb reliability 2026            # 2024-26: splits (about 15 minutes), parameters, drift, validation, checks, figure
uv run bb reliability 2026 --reuse    # refit everything from the saved split sums (about 3 minutes)
uv run bb reliability 2026 --ship     # also replace the shipped constants (only for a reviewed run)
uv run bb regress hitter/whiff 0.40 50 --mean 0.251 --horizon next_season
```
**Outputs:**
- **Tables:** `data/edge/reliability/` (params, curve, params_train, league_means, validation, validation_buckets, event_split, bat_speed_floor, summary.json).
- **Shipped constants:** `baseball/evaluation/reliability_params.json`.
- **Figure:** `reports/figures/2026-reliability-atlas.png`.

## Sources
- **Pitch data:** Statcast, MLB Advanced Media, via [Baseball Savant](https://baseballsavant.mlb.com/) (regular seasons 2024–2026, pulled through October 2026).
- **Bat-tracking definitions** (competitive swings, bat speed, fast swing, swing length, attack angle and direction, swing path tilt): [Baseball Savant bat-tracking leaderboard glossary](https://baseballsavant.mlb.com/leaderboard/bat-tracking), read 2026-10-12.
- **Russell A. Carleton:**
  - "Baseball Therapy: It's a Small Sample Size After All," *Baseball Prospectus*, July 16, 2012 ([link](https://baseballprospectus.com/news/article/17659/baseball-therapy-its-a-small-sample-size-after-all)).
  - "Baseball Therapy: Should I Worry About My Favorite Pitcher?," May 9, 2013 ([link](https://www.baseballprospectus.com/news/article/20516/baseball-therapy-should-i-worry-about-my-favorite-pitcher/)).
  - "Baseball Therapy: The One About Exit Velocity," April 19, 2016 ([link](https://www.baseballprospectus.com/news/article/28956/baseball-therapy-the-one-about-exit-velocity/)).
- **Steve Staude,** "Randomness, Stabilization, & Regression," *FanGraphs*, May 17, 2013 ([link](https://blogs.fangraphs.com/randomness-stabilization-regression)): the 0.5 vs 0.7 debate and the Spearman–Brown step-up.
- **Jonah Pemstein with Sean Dolinar,** "A New Way to Look at Sample Size," *FanGraphs*, June 22, 2015 ([link](https://blogs.fangraphs.com/a-new-way-to-look-at-sample-size)).
- **FanGraphs Library,** "Sample Size" (Piper Slowinski, 2010; updated by Neil Weinberg, August 2017) ([link](https://library.fangraphs.com/principles/sample-size/)).
- **Jordan Rosenblum,** "A Way-Too-Early Look at the Importance of Bat Speed," *RotoGraphs*, May 20, 2024 ([link](https://fantasy.fangraphs.com/a-way-too-early-look-at-the-importance-of-bat-speed)): source of the Tango and FanGraphs bat-speed regression amounts.
- **Adam Salorio,** "Examining Swing Path Tilt," June 6, 2025 ([link](https://adamsalorio.substack.com/p/examining-swing-path-tilt)).
- **Owen McGrattan,** "Stuff+, Location+, and Pitching+ Primer," *FanGraphs Library*, March 10, 2023 ([link](https://library.fangraphs.com/pitching/stuff-location-and-pitching-primer)).
