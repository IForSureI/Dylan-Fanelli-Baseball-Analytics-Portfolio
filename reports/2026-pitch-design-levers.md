# What pitch-design changes stick and pay, MLB 2024–26

**League study from public pitch data.** Every regular-season pitch of 2024, 2025 and 2026 (Statcast), not a scouting look and not any club's data. It is observational: pitchers chose these changes, so every number below is an association with controls, matching and a placebo, not the result of a randomized pitch-design program.
*Written 2026-10-12 · Dylan Fanelli · Data: Statcast via Baseball Savant, 2,141,219 pitches, 11,839 pitcher-season-pitch types, 1,822 season-over-season pitch pairs from 481 pitchers · Code: `baseball/development/levers.py`, `baseball/development/idp.py` · Not yet independently reviewed*

![What a shape change is worth, and whether it lasted](figures/2026-pitch-design-levers.png)

## The answer: which levers pay
Each row is the change in a pitch's results per unit of shape change from one season to the next. The shape change is net of the league's own change for that pitch type that year, and the previous season's actual whiff%, expected whiff%, run value, swings, age and role are held fixed (that is how regression to the mean is handled; see Method). Standard errors, clustered by pitcher, are in parentheses. q is Benjamini–Hochberg across all 152 lever tests (76 levers × whiff and run value).

| Pitch | Change | Whiff% per swing (pts) | Run value per 100 pitches | What physics expected (whiff pts) | Adding only (whiff pts) | Pairs | Evidence |
|---|---|---|---|---|---|---|---|
| Four-seamer | Velocity, +1 mph | **+1.81 (0.25)**, q < 0.001 | **+0.33 (0.05)**, q < 0.001 | +0.98 | +1.51 (0.44) | 545 | Confirmed; placebo warning (below) |
| Four-seamer | Ride (IVB), +2 in | **+1.62 (0.49)**, q = 0.02 | +0.21 (0.13), q = 0.35 | +1.14 | +3.17 (0.83) | 545 | Confirmed (whiffs) |
| Four-seamer | Spin, +100 rpm | **+2.09 (0.38)**, q < 0.001 | **+0.42 (0.10)**, q = 0.001 | +1.28 | +2.62 (0.78) | 545 | Confirmed; works mostly through ride and velocity |
| Slider | Drop, +2 in (less IVB) | **+1.30 (0.39)**, q = 0.02 | +0.01 (0.08) | +1.05 | +3.24 (0.70) | 266 | Confirmed (whiffs); the gain faded in year two |
| Slider | Speed gap below the fastball, +1 mph | **+1.06 (0.34)**, q = 0.02 | +0.03 (0.07) | +0.80 | +1.25 (0.58) | 266 | Confirmed (whiffs) |
| Slider | Spin, +100 rpm | **+1.41 (0.44)**, q = 0.02 | +0.13 (0.09) | +1.22 | +1.60 (0.73) | 266 | Confirmed (whiffs); not stable across season pairs |
| Slider | Arm angle, +3° (higher slot) | **+1.22 (0.36)**, q = 0.02 | +0.13 (0.07) | +0.39 | +0.85 (0.67) | 266 | Confirmed (whiffs) |
| Cutter | Speed gap below the fastball, +1 mph | **+2.45 (0.79)**, q = 0.03 | −0.18 (0.13) | +1.75 | +4.17 (1.11) | 102 | Confirmed (whiffs), small sample |
| Sweeper | Glove-side sweep, +2 in | −1.50 (0.63), q = 0.13 | **+0.39 (0.12)**, q = 0.02 | −0.27 | −0.43 (1.08) | 144 | Confirmed on run value only; fewer whiffs |
| Curveball | Arm angle, +3° (higher slot) | −0.56 (0.60) | **−0.31 (0.10)**, q = 0.03 | −0.12 | −1.21 (1.03) | 163 | Confirmed on run value (a cost) |
| Sweeper / curveball | Velocity, +1 mph | +1.57 (0.61) / +1.09 (0.41), q = 0.09 | −0.15 / +0.03 | +0.79 / +0.40 | | 144 / 163 | Lean; curveball fails the placebo |
| Splitter | Speed gap +1 mph / arm-side run +2 in / spin +100 rpm | +2.41 / −3.48 / −2.09, q = 0.09 | ≈ 0 | +1.21 / −1.33 / −0.98 | | 67 | Lean; 44 pitchers |

**No sign of payoff** (q ≥ 0.10, raw p ≥ 0.05, and the 95% interval rules out more than 2 whiff points per unit):
- **Changeup speed gap:** +0.58 (0.52) whiff points per mph, interval −0.44 to +1.60. The same for changeup separation (+0.62 per 2 in), drop (+0.88), spin and velocity. A changeup's speed gap is the most-repeated pitch-design rule of thumb, and these data can't see it pay on its own.
- **Four-seam arm-side run** (−0.15 per 2 in), **extension** (+0.50 per 3 in), **release height and side, arm angle.** Extension's "free perceived velocity" doesn't show up in whiffs or run value at this sample (gains alone: +1.50 (0.95)).
- **Sinkers: every lever.** Velocity (+0.18), ride, run, spin, release, arm angle. Sinker results barely move with sinker shape season to season.
- **Slider sweep and velocity; sweeper drop, separation and speed gap; curveball drop, speed gap and separation.**

**Not confirmed** (p < 0.05 alone, not after the correction): changeup arm-side run (−1.67 (0.68) per 2 in, so *less* run went with more whiffs), changeup arm angle (+0.91), slider separation (+1.01) and release height (+1.57), curveball sweep (+1.04), cutter separation (+1.70), splitter velocity (−1.66), sinker ride on run value. **Can't tell** (too wide): 18 rows, mostly extension and release height on secondaries, cutter and splitter shape.

**What a player-development department can do with it:**
1. **Four-seamers: velocity and ride, in that order of evidence.** They hold up together in one model (+1.63 (0.26) per mph and +1.87 (0.54) per 2 in), and the ride payoff lasted a second season (below). Spin pays mostly through them: with the other levers held fixed it drops to +0.81 (0.42), p = 0.06. Losing velocity costs more than gaining it pays (−2.22 vs +1.51 per mph), and velocity is the one confirmed lever that fails the placebo, so part of the velocity number is pitchers bouncing back from a down year.
2. **Sliders: slower, deeper, from a higher slot.** Drop, speed gap and spin move together (drop and speed gap correlate 0.66), so they are one design direction, not three independent levers. In one model only the speed gap (+1.28 (0.50)) and arm angle (+1.13 (0.58)) keep their size. Build the slider down and away from the fastball's speed, not just with more spin.
3. **Sweepers: more sweep bought run value, not whiffs.** +0.39 runs per 100 pitches per 2 in (q = 0.02) with −1.50 whiff points (q = 0.13). Wider sweepers get weaker contact or more takes for strikes, not more misses; grade them on run value. The run-value gain did not clearly last (below).
4. **Don't sell a changeup redesign on speed gap alone.** No sign of payoff from the gap, separation, drop or velocity of the changeup itself. The stuff model also predicts only small changeup gains (+0.33 per mph of gap) and the gains it predicts arrive at 41% (below). Changeup results depend on things this study doesn't measure: location, sequencing, deception (see the familiarity study's wear-out results).
5. **Score a specific design with the expected-whiff model, and use this table for direction.** Out of sample, the stuff model's single expected-whiff change forecasts next season's whiff change better than the lever-by-lever model for every pitch type but four-seamers and curveballs (pooled: 8.7% of the error removed against 1.2%).

## Method

**Grain.**
- **Pitch-season:** one row per pitcher × season × pitch type (Statcast's label; knuckle-curves pooled with curveballs), regular season only.
- **Pair:** the same pitcher and pitch type in two consecutive seasons, both with at least 150 pitches and 50 swings: 886 pairs for 2024→25 and 936 for 2025→26.

**The levers.** Per pitch-season means of velocity, induced vertical break, horizontal break in the pitch's own direction (arm side for four-seamers, sinkers, changeups and splitters; glove side for the rest), spin, release height and side (arm side +), extension and arm angle, plus two relative levers for secondaries: speed gap and movement separation (inches, IVB × break plane) from the pitcher's primary fastball. The primary fastball is his most-thrown four-seamer, sinker or cutter over *both* seasons compared, so the reference is the same pitch in both years. Gap and separation aren't levers for four-seamers and sinkers.

**Net of the league.** Each change is minus the median change of every returning pitch of that type in the same season pair. The league moved: four-seam spin +21 rpm in 2024→25 and −12 rpm in 2025→26, and arm angle −0.6° on four-seamers in 2024→25. Those are camera and ball changes or league-wide training trends, not one pitcher's work.

**A deliberate change, defined from noise.**
- **The noise reference:** how far a pitch's shape moves between the first and second half of one season (split where half its pitches had been thrown), net of the league's half-to-half shift.
- **The threshold:** the 90th percentile of that movement, by pitch type and lever. Examples: four-seam velocity 0.96 mph, four-seam IVB 1.13 in, four-seam spin 66 rpm, slider IVB 2.09 in, slider speed gap 1.18 mph, changeup speed gap 0.96 mph, sweeper sweep 2.37 in, arm angle 2.8–3.3°.
- **Why it is conservative:** a half-season mean has twice the sampling variance of a full-season mean, and the halves also carry in-season drift and mid-season tweaks.
- **What it found:** 22–28% of pitch pairs changed beyond the threshold on each lever (velocity 23%, IVB 22%, arm angle 28%), against at most 10% if seasons moved only as much as halves do. Season-to-season shape change is mostly real change.
- **Its limit:** with ten levers per pitch, 79% of pitch pairs cross at least one threshold. "Deliberate" means beyond within-season noise on that lever; the data can't show intent.

**Expected whiffs (the physics check).**
- **One model for all three seasons:** the edge engine's expected-whiff model (gradient boosting on velocity, movement, spin, release, extension, arm angle, differences from the pitcher's primary fastball, and batter hand), trained on 2024–26 pooled and cross-fitted by pitcher. Every pitch of a pitcher, in every season, is scored by a model that never saw him. AUC 0.634 on 1,014,222 swings.
- **Fixed batter-hand mix:** every pitch is scored against a same-handed and an opposite-handed hitter, then weighted by that pitch's own 2024–26 share. A change in expected whiff is then a change in physics only, not a new model year or a different mix of hitters.

**Payoff per unit (the table above).**
- **The model:** change in whiff% (or run value per 100 pitches, or expected whiff%) on one lever's net change, weighted least squares with weights equal to the harmonic mean of the two seasons' swings (the inverse variance of a change in a rate), an intercept per season pair, SEs clustered by pitcher (481 pitchers; the same pitchers appear in both pairs).
- **Regression to the mean:** a pitch that had an unlucky season improves the next with no change at all, and pitchers redesign pitches after bad seasons. The controls are the prior season's actual whiff%, expected whiff% (a stable read of the pitch's true level), run value, log swings, age, prior role and a role-change flag. On fictional data built with exactly this selection, a lever with no effect shows a spurious +1.1 points per unit without the controls and about zero with them (`tests/test_levers.py`).
- **One lever at a time, then all together:** the table's first columns are each lever alone (the payoff of changing it, including what usually changes with it). The joint model puts every lever in one regression per pitch type, so each is net of the others.
- **Gains and losses separately:** the "adding only" column is the slope over increases alone, from a model with separate slopes for increases and decreases.
- **Multiple testing:** Benjamini–Hochberg across all 152 tests. Confirmed = q < 0.05; lean = q < 0.10. With 10 confirmed rows at q < 0.05, fewer than one is expected to be a false finding.

**Matching (the second design).**
- **Treated:** a deliberate change in one direction on one lever (e.g., four-seam velocity up at least 0.96 mph). **Controls:** the same pitch type with that lever within half the threshold.
- **Coarsened exact matching** on season pair, prior role, role change, and terciles of prior actual and expected whiff% within the pitch type; then the same weighted regression with the continuous controls, SEs clustered by pitcher.
- **Balance:** the median standardized difference in prior whiff% between changers and controls falls from 0.19 to 0.06 (largest after matching: 0.38, a 15-pitch group).
- **Results** (84 comparisons, BH across them): three survive at q < 0.10.
  - **Four-seam velocity loss** (mean −1.29 mph): −3.05 (0.78) whiff points, q = 0.01. The raw change for these pitches was −4.57: they also had higher whiff rates the year before (+0.36 SD), so part of the raw drop was regression.
  - **Slider drop** (mean +3.1 in more drop): +5.36 (1.38), q = 0.01. Raw +3.56: these sliders had *lower* prior whiff rates, and the controls make the gain larger, not smaller.
  - **Changeup separation** (+3.35 in): +4.86 (1.47), q = 0.05, the one changeup result anywhere in the study. It doesn't hold in the per-unit model (+0.62 (0.65) per 2 in), so it is a lean.
  - **The rest point the same way as the per-unit table but are noisier:** four-seam ride up +2.30 (0.97), spin up +2.46 (0.85), velocity up +0.94 (0.86).

**Placebo: does next year's change "predict" last year's results?** It can't cause them. The model regresses the 2024→25 results change on the 2025→26 net lever change, with 2024 priors and the 2024→25 change in the same lever controlled (a 2025 velocity dip lowers 2025 whiffs and is followed by a 2026 rebound; that is mechanics, not selection).
- **Overall:** 19 of 152 tests at p < 0.05, against about 8 expected by chance; none survives the correction (smallest q = 0.36). Some selection into changing is left after the controls, spread thinly.
- **On the confirmed rows:** four-seam velocity fails it (−0.83 (0.40) whiff points per later mph, p = 0.04; run value −0.22, p = 0.04). Pitchers who gained velocity in 2026 had lost results in 2025 beyond what their 2025 velocity explains, so part of the +1.81 is recovery (health, mechanics) rather than a new gain. Every other confirmed row passes (p ≥ 0.14, sliders p ≥ 0.87). Curveball velocity (a lean) fails it (p = 0.02).

**Robustness** (whiff points per unit, four-seamer, cutter and slider rows):

| Specification | FF velo | FF ride | FF spin | FC gap | SL drop | SL gap | SL spin | SL slot |
|---|---|---|---|---|---|---|---|---|
| Main | +1.81 | +1.62 | +2.09 | +2.45 | +1.30 | +1.06 | +1.41 | +1.22 |
| + usage and platoon-mix change | +1.82 | +1.63 | +2.10 | +2.46 | +1.27 | +1.01 | +1.43 | +1.15 |
| No role changers (92% of pairs) | +1.62 | +1.44 | +2.08 | +2.17 | +1.12 | +0.94 | +1.35 | +1.31 |
| 100+ swings in both seasons | +1.93 | +1.63 | +2.18 | +1.62 | +1.03 | +0.89 | +1.44 | +0.97 |
| 2024→25 only | +1.38 | +1.96 | +2.31 | +2.43 | +1.05 | +0.98 | +2.49 | +1.00 |
| 2025→26 only | +2.16 | +1.36 | +1.91 | +2.84 | +1.54 | +1.26 | +0.24 | +1.36 |
| Without prior-season controls | +2.03 | +1.97 | +2.31 | +2.73 | +1.13 | +1.08 | +1.45 | +1.02 |

- **Every row keeps its sign and rough size** except slider spin, which is +2.49 in 2024→25 and +0.24 (p = 0.62) in 2025→26. Treat slider spin as unstable.
- **Run-value rows:** sweeper sweep +0.31 to +0.49 runs per 100 across specifications (p ≤ 0.08); curveball slot −0.18 to −0.41 (not significant in 2025→26 alone, p = 0.34).

## Does the physics show up?
How much of a predicted whiff change arrives: the change in actual whiff% on the change in expected whiff% (fixed hand mix), same controls.

| Pitch | Four-seamer | Sinker | Cutter | Slider | Sweeper | Curveball | Changeup | Splitter | All |
|---|---|---|---|---|---|---|---|---|---|
| Actual points per expected point | 0.89 (0.11) | 0.87 (0.29) | 0.63 (0.24) | 1.05 (0.14) | 0.64 (0.29) | 0.20 (0.26) | 0.41 (0.22) | 0.88 (0.25) | **0.74 (0.07)** |

- **About three quarters of a physics-predicted change arrives,** in full for sliders and nearly so for four-seamers.
- **Curveballs and changeups:** a shape change the model likes gets 20–41% of it, and the curveball slope isn't distinguishable from zero. What makes these pitches work is mostly outside the physics the model sees.

**Out-of-sample check.** Every model is fit on 2024→25 and scored on 2025→26. The figure is the share of a controls-only baseline's squared error removed (regression to the mean, role, age, sample), with a 95% interval from resampling 2025→26 pitchers.

| Pitch | Pairs (train / test) | Every lever | Expected-whiff change only |
|---|---|---|---|
| Four-seamer | 267 / 278 | **15.1% (7.4 to 22.5)** | **13.3% (7.7 to 18.4)** |
| Sinker | 141 / 157 | −8.7% (−17.6 to 0.2) | 6.7% (−2.3 to 14.6) |
| Slider | 135 / 131 | −3.1% (−29.2 to 16.3) | 8.6% (−6.0 to 22.1) |
| Sweeper | 64 / 80 | −12.1% (−42.7 to 10.5) | 4.0% (0.2 to 7.5) |
| Curveball | 80 / 83 | 11.0% (−3.9 to 23.7) | 1.5% (−1.5 to 4.1) |
| Changeup | 98 / 104 | −4.1% (−30.2 to 15.1) | 2.7% (−7.8 to 11.9) |
| All pitches pooled | 886 / 936 | 1.2% (−2.0 to 4.4) | **8.7% (5.0 to 12.5)** |

- **Four-seamers:** the levers forecast next year's whiff change out of sample (15%), as well as or better than the stuff model.
- **Everything else:** eight or ten lever coefficients fit on about 100 pairs overfit; the one-number physics summary forecasts better. That is why the table above is a guide to direction and the expected-whiff model is the tool for scoring a specific design.

## Persistence: did the shape and the gain last?
For 2024→25 changes, followed into 2026.

**Shape held.**

| Lever | Deliberate 2024→25 changes | Still thrown in 2026 (changers / within noise) | Median share of the change kept | Kept half or more | Reversed past the start |
|---|---|---|---|---|---|
| Velocity | 211 | 61% / 65% | 0.99 | 75% | 7% |
| IVB | 193 | 62% / 65% | 0.86 | 74% | 8% |
| Horizontal break | 181 | 64% / 67% | 0.85 | 67% | 9% |
| Spin | 181 | 62% / 69% | 0.92 | 71% | 8% |
| Speed gap | 120 | 58% / 67% | 0.93 | 77% | 7% |
| Arm angle | 248 | 63% / 67% | 0.95 | 68% | 10% |

- **Most deliberate changes stick:** the median pitch kept 82–99% of its change a year later (net of the league's two-year shift), and the slope of 2024→26 change on 2024→25 change across all pitches is 0.85–0.94.
- **Attrition:** changed pitches were a little less likely to still be thrown above the floors in 2026 (58–67% against 62–69%), so the payoff tables describe pitches that survived.

**Results: mostly held on four-seamers, faded on sliders.** The same per-unit model on the 581 pitches thrown in all three seasons. The 2024→25 shape change is the treatment at each horizon; "fade" is the 2025→26 results change on that same 2024→25 change, with its own SE.

| Change (2024→25) | Whiff pts, 2024→25 | Whiff pts, 2024→26 | Fade, 2025→26 | Pitches |
|---|---|---|---|---|
| Four-seam ride, +2 in | +1.75 (0.82) | +1.74 (0.81) | −0.02 (0.92) | 176 |
| Four-seam spin, +100 rpm | +2.13 (0.57) | +2.04 (0.65) | −0.09 (0.64) | 176 |
| Four-seam velocity, +1 mph | +1.28 (0.40) | +0.44 (0.52) | −0.85 (0.42), p = 0.045 | 176 |
| Slider drop, +2 in | +1.03 (0.76) | −0.59 (0.74) | −1.62 (0.77), p = 0.04 | 80 |
| Slider speed gap, +1 mph | +0.62 (0.62) | −0.89 (0.67) | −1.51 (0.59), p = 0.01 | 80 |
| Slider slot, +3° | +0.57 (0.67) | +1.55 (0.66) | +0.98 (0.70) | 80 |
| Expected-whiff change, +1 pt (all pitches) | +0.67 (0.13) | +0.61 (0.14) | −0.06 (0.14) | 581 |

- **Four-seam ride:** the gain held in full.
- **Four-seam spin:** the whiff gain held, but its run-value gain didn't (+0.46 (0.17) → −0.13 (0.19); fade −0.60 (0.23), p = 0.01).
- **Velocity and slider shape:** the year-two whiff gains shrank, at p = 0.01–0.05. With dozens of persistence tests run, single results at that level are borderline, so read them as "no evidence the slider gain lasts," not proof it vanishes.
- **What clearly lasts:** the physics-predicted gain, pooled. Gains the expected-whiff model predicted for 2024→25 changes were still there in 2026 (+0.61 per point).
- **Sweeper sweep's run value:** +0.50 (0.20) → −0.01 (0.26), fade p = 0.11. Not shown to last.

## The tool: an individual development plan with a progress engine
`baseball/development/idp.py` turns the study into the plan a coordinator writes and the review a front office reads. It follows the player-development standard: 2–4 priorities, each with a metric, a dated and sourced baseline, a target and date, a sample floor, the mechanism, a weekly process goal, an owner, checkpoints, and the risk with its own guard metric. Plans are YAML (`examples/`), validated before anything runs.

**The engine.** For each priority it computes the metric from the plan's start to the as-of date from pitch data:
- **Uncertainty:** an SE by jackknife over games, because pitches in one game share a body, a mound and a day.
- **Metrics:** shape (velocity, IVB, break, spin, release, extension, arm angle), speed gap and separation, whiff, CSW, zone, chase, usage and run value.
- **Verdicts:**
  - **Insufficient:** under the floor.
  - **On track:** a move toward the target clear of the baseline (z ≥ 1.96, both SEs counted), not clearly short of the calendar's pace. Pace is linear, or "step" for offseason changes expected from day one.
  - **Behind:** a real move, but the interval sits short of pace.
  - **Flat:** no move distinguishable from the baseline, even if the point estimate passed the target.
  - **Wrong way:** a real move away from the target.
- **Guards** read ok / watch / breached.
- **Two notes from the same numbers:** one for the coach (plain language, what to keep doing) and one for the front office (baseline → now with n and interval, keep / adjust / stop, a recommendation and the condition that would reverse it). `examples/idp-fictional.yaml` runs the whole flow on fictional pitches.

### Worked example: Logan Gilbert, 2026 (a hypothetical, retrospective plan)
**This is Dylan Fanelli's hypothetical plan written from public data. It is not his club's plan, and nothing here says what the club or the pitcher actually worked on.**
- **Written as if in the 2025–26 offseason:** every baseline is his 2025 Statcast data, and every payoff used to set a target comes from 2024→25 pairs only (`plan_target()`).
- **Hindsight in the choice of pitcher:** he was picked *because* the study flags his 2025→26 changes (four-seam velocity +1.04 mph net of the league, slider drop +2.75 in, slider spin +308 rpm). That is selection, and the result can't be read as a test of the method.

**Where he was (2025 regular season, 25 games):**
- **Four-seamer:** 95.4 mph (n = 795), 20.6% whiffs.
- **Slider:** +0.8 in IVB (n = 760), 34.5% whiffs on 365 swings, expected 38.4%, thrown 35% of the time.

**The plan and its targets** (`examples/idp-gilbert-2026.yaml`):

| # | Priority | Baseline | Target | Where the target comes from | Guard |
|---|---|---|---|---|---|
| 1 | Four-seam velocity | 95.4 mph | 96.4 by May 15 (step) | About the deliberate-change threshold (0.96 mph); 2024→25 pairs priced it at +1.38 (0.33) whiff points per mph | Four-seam zone% stays above 60 |
| 2 | Slider depth | +0.8 in IVB | −1.2 by May 15 (step) | About the slider threshold (2.1 in) | Slider zone% stays above 45 |
| 3 | Slider whiffs | 34.5% | 37.2% by season's end | 34.5 + 1.7 expected drift (his expected whiff was 3.8 points above his actual) + 1.0 for 2 in of drop (2024→25 pairs alone: +0.52 per inch, SE 0.33, *not* significant at the time) | Slider usage stays above 28%, so the gain isn't bought by throwing it less |

**Checkpoints, run on his actual 2026 pitches:**

| # | May 15 | July 1 | Season's end (Sept. 27) |
|---|---|---|---|
| 1. Four-seam velocity | insufficient (95.3, 257 pitches) | flat (95.8, z = 1.7) | **on track:** 96.4 (96.1 to 96.7), 1,187 pitches |
| 2. Slider depth | insufficient (−1.9, 174 pitches) | on track (−2.2) | **on track:** −2.0 in (−2.2 to −1.8), 746 pitches |
| 3. Slider whiffs | insufficient (92 swings) | insufficient (199 swings) | **flat:** 37.5% (32.4 to 42.6), 403 swings; z = 0.7 against the baseline. Guard **breached:** usage 25.0% (22.6 to 27.4) |

![Logan Gilbert, 2026: the hypothetical plan's three priorities to date](figures/2026-pitch-design-levers-idp.png)

**The front-office note the engine wrote** (season's end, trimmed to the priorities and the call):
> **Priority 1: Four-seam velocity.** 95.4 (2025) → 96.4 (95% interval 96.1 to 96.7; n = 1,187 pitches, 32 games). Target 96.4 by 2026-05-15. Trend up (z = 5.6); 97% of the gap closed. **On track. Keep.** Guard: four-seam zone% 61.8 (58.9 to 64.6), limit 60: ok.
> **Priority 2: Slider depth.** 0.8 → −2.0 in (−2.2 to −1.8; n = 746). **On track. Keep.** Guard: slider zone% 47.9 (43.1 to 52.6), limit 45: ok.
> **Priority 3: Slider whiffs.** 34.5% → 37.5% (32.4 to 42.6; n = 403 swings). The point estimate is past the target but not distinguishable from the baseline. **Flat. Adjust the method.** Guard: slider usage 25.0% (22.6 to 27.4), limit above 28: breached.
> **Recommendation:** review priority 3 with the coach: its guard is breached, so the risk the plan named is showing.

**What an analyst adds to the engine's call:**
- **Both shape priorities landed, and late.** Velocity reached the target only as a season average. To date it sat at 95.3 in mid-May and climbed all summer (figure), so the "step" assumption was wrong for this pitcher. A real plan would have moved the date at the July checkpoint.
- **The slider whiff priority can't be graded on one season of swings.** 403 swings can't separate a 3-point gain from noise.
  - **What the physics says:** his slider's expected whiff rose from 38.4% to 41.4% at a fixed hand mix, so the shape moved the right way by the model's read.
  - **The guard's warning:** his slider usage fell from 35% to 25% while he added a changeup (215 pitches) and a cutter (152) that he hadn't thrown in 2025. By the familiarity study's wear-out results, fewer sliders means hitters have seen fewer of them, which by itself raises whiffs per swing. The guard did its job: it says the whiff number is confounded.
  - **The study's own result:** slider-drop gains faded in year two for 2024→25 changers. The 2027 plan should re-test the slider whiff priority before building on it.
- **The four-seamer outran the plan's own payoff estimate:** 20.6% → 22.7% whiffs, against +0.7 predicted (−0.65 drift + 1.38 for the mph). On one pitcher-season that isn't evidence of anything; the velocity row carries a placebo warning.

## What this doesn't show
- **It's observational.** Changes are chosen, not assigned.
  - **What the design handles:** league drift, regression to the mean (prior actual and expected whiffs), role changes, age and sample. The placebo, matching and out-of-sample checks guard against the known selection.
  - **What it can't handle:** a pitcher who changes a pitch *and* changes something unseen at the same time (health, conditioning, a new pitching coach, a new organization's game plan) gets credited to the shape.
- **Injuries are unseen.** Velocity losses after an injury and gains on the way back sit in the same velocity coefficient, and the velocity placebo says some of that is in there.
- **Location, count and sequencing are not controlled.** They are partly how a pitcher uses a new shape (a mediator). Usage and platoon-mix changes barely move the estimates (robustness table).
- **Survivorship.** A pair needs 150 pitches and 50 swings in both seasons, so pitches that were changed, failed and were shelved early are missing. Payoffs describe changes that lasted long enough to be measured.
- **Statcast's labels.** A slider that Statcast relabeled as a sweeper (or a new grip that kept its old label) falls out of, or mixes into, a pitch type's pairs. Labels weren't corrected.
- **"Deliberate" means beyond within-season noise on that lever,** not proven intent. With ten levers, most pitches cross at least one threshold.
- **The levers are correlated.** Slider drop, speed gap and spin move together; four-seam spin rides on velocity and ride. The joint model shows which keep their size, but the data can't hand a coach ten independent dials.
- **Small samples:** splitters (67 pairs, 44 pitchers) and cutters as a secondary (102 pairs).
- **Expected whiff is a whiff-per-swing model.** It doesn't price chase, called strikes or contact quality, which is why the sweeper's run-value gain doesn't show up in it.
- **Not yet independently reviewed.** Per the repo's rule, a report-qa review comes before this is final.

## Reproduce
```bash
uv run bb levers 2026                               # the study: tables -> data/edge/levers/, figure (pools 2024-26)
uv run bb idp examples/idp-gilbert-2026.yaml        # the worked plan on his 2026 pitches (sequence copy needed)
uv run bb idp examples/idp-fictional.yaml           # the fictional example, no data needed
```
(`bb levers` and `bb idp` are listed in INTEGRATION.md until they are wired into `cli.py`.)

## Sources
- **Pitch data:** Statcast, MLB Advanced Media, via [Baseball Savant](https://baseballsavant.mlb.com/) (regular seasons 2024–2026, pulled through October 2026).
- **Player names and ids:** the Chadwick Bureau register (github.com/chadwickbureau/register, CC BY 4.0), via `bb people`.
- **Multiple testing:** Yoav Benjamini and Yosef Hochberg, "Controlling the False Discovery Rate," *Journal of the Royal Statistical Society, Series B* 57(1), 1995.
- **Matching:** Stefano Iacus, Gary King and Giuseppe Porro, "Causal Inference without Balance Checking: Coarsened Exact Matching," *Political Analysis* 20(1), 2012.
- **Clustered standard errors:** A. Colin Cameron and Douglas Miller, "A Practitioner's Guide to Cluster-Robust Inference," *Journal of Human Resources* 50(2), 2015.
- **Expected whiffs, league baselines and the familiarity results cited:** this repo's edge engine and `reports/2026-league-pitch-familiarity.md`.
