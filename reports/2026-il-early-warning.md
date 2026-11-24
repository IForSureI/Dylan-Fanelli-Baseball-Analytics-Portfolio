<!-- portfolio:header -->
<sub>[← Portfolio](../README.md) &nbsp;|&nbsp; [← Development plan](2026-development-plan.md) &nbsp;|&nbsp; [Roster and CBA engine →](2026-roster-cba-engine.md)</sub>
<!-- /portfolio:header -->

# Velocity drops as an injured-list warning: what public pitch data can tell a medical staff (MLB 2024–26)

<!-- portfolio:glance -->
<p><img src="https://img.shields.io/badge/status-reviewed-1d5c3f" alt="status: reviewed"> <img src="https://img.shields.io/badge/data-public-1f1f1f" alt="data: public"> <img src="https://img.shields.io/badge/for-Medical%20and%20performance%20staff-6b6b6b" alt="for: Medical and performance staff"> <img src="https://img.shields.io/badge/method-out--of--sample-b4532a" alt="method: out-of-sample"> <img src="https://img.shields.io/badge/method-calibration-b4532a" alt="method: calibration"> <img src="https://img.shields.io/badge/method-alert%20rule-b4532a" alt="method: alert rule"></p>

**At a glance**

- **The question:** Does a drop in a pitcher's velocity or stuff, against his own regressed baseline, warn of an injured-list stint?
- **The answer:** Mostly late. A fastball 2+ mph below his baseline was followed by an arm IL stint within 14 days 10.4% of the time in 2026 (base rate 3.6%), mostly from the last outing before the stint. An earlier signal showed in 2024–25 but wasn't detected in 2026, and one test season can't settle it. As a forecast, tracking data adds no detectable gain to role, workload and IL history (AUC +0.005, -0.022 to +0.031).
- **For a club:** A same-day trainer check that costs about five false alarms per club-season, and a reason not to buy an injury forecast built on public pitch data.
<!-- /portfolio:glance -->

**League study from public pitch data and public transactions.**
- **Scope:** every regular-season outing by a pitcher in 2024–26 (Statcast), matched to every IL placement in the MLB Stats API transactions.
- **Out of sample:** every parameter (noise model, month curve, the three forecasting models, the alert threshold) is fit on 2024–25 only. 2026 is the test.
- **Observational:** a velocity drop and an IL placement can share a cause the data can't see. Nothing here says a drop causes an injury.

*Written 2026-11-15, updated 2026-11-24 after a separate review pass; Dylan Fanelli; Data: Statcast via Baseball Savant, 2,141,219 regular-season pitches, 7,288 games, 62,361 pitcher outings, 1,310 pitchers; MLB Stats API transactions 2023–26; Code: `baseball/health/il_warning.py` (`bb il-warning 2026`); Saved outputs: [`reports/outputs/il-warning-2026.json`](outputs/il-warning-2026.json); Builds on [the Reliability Atlas](2026-reliability-atlas.md); Separate review pass: not yet run*

![IL rate by velocity drop, and 2026 calibration of the two models](figures/2026-il-early-warning.png)

*Figure note (Nov. 24): read the right panel's "no better" as "no detectably better" (finding 2 gives the interval). The figure is from the saved Nov. 15 run and is redrawn with the next one.*

## Answer
- **A big velocity drop is a real warning sign, but it comes late.**
  - **The association replicates on 2026.** After an outing whose fastball sat 2–3 mph below the pitcher's own regressed baseline, 9.4% went on the IL for an arm injury within 14 days (14 of 149; 95% interval 5.7% to 15.2%). The 2026 base rate is 3.6%.
  - **Refit on 2026 alone,** each standard deviation of this outing's drop goes with 1.18 times the odds of an arm IL placement within 14 days (1.07 to 1.30, p < 0.001). In the 2024–25 fit the same velocity-only model gave 1.28.
  - **It is mostly the last outing before the IL.** Leave out each stint's final outing and the 2026 association is not detected: 1.02 (0.91 to 1.14). On 2024–25 the same check did find it (1.16 per SD, p = 0.001), and the early version of the flag held its lift in both periods (1.96 times the base rate on 2024–25, 1.94 on 2026, p = 0.07). So the drop mostly flags an injury that is already happening; an early signal of about twice the base rate is possible but not confirmed on 2026.
- **As a forecast, tracking data adds no detectable gain to what a club already knows.**
  - **The naive model** uses role, age, an IL stint in the last year, pitches thrown, the outing's length against his norm, rest and month. It has a 2026 AUC of 0.571.
  - **The tracking model** adds the drops in velocity, spin, ride, extension, release height and arm angle. AUC 0.576. The gain is +0.005, 95% interval −0.022 to +0.031. Log loss is no better (+0.0001, −0.0014 to +0.0017).
  - **Velocity alone** does the same: +0.009 (−0.013 to +0.032).
  - **Both models are too spread out on 2026** (calibration slopes 0.63 and 0.56, where 1 is calibrated). They rank risk weakly and overstate the gap between high and low.
- **Spin, ride, extension, release height and arm angle add no confirmed signal in the main row.** None survives the Benjamini–Hochberg correction across its eight tracking terms; the closest is release height (p = 0.036, q = 0.15). In the 7-day row, release height over the last three outings does pass its own row's correction (1.20 per SD, p = 0.002, q = 0.007). Corrected across all 36 non-velocity terms in the six rows it doesn't (q = 0.065), and it isn't tested on 2026, so I treat it as a lead.
- **A simple rule works as a same-day check.**
  - **The rule:** flag any outing whose fastball is 2.0 mph or more below his regressed baseline. The 2.0 was chosen on 2024–25 as the lowest threshold with no more than 10 false alarms per club-season.
  - **2026:** 164 flags, 5.5 per club-season. 17 were followed by an arm IL placement within 14 days: 10.4% (6.6% to 16.0%), 2.9 times the base rate (p < 0.001). False alarms: 4.9 per club-season (0 to 12 by club, median 4).
  - **What it misses:** it caught 15 of 175 arm IL stints (8.6%). The true flags came a median 2 days before the placement took effect and 3 days before it was announced.

## What a club can do with it
1. **Use the 2 mph flag as a same-day trainer check, not a forecast.**
   - When a pitcher's fastball sits 2+ mph below his regressed baseline, the athletic trainer talks to him before his next throwing day.
   - Expect about five flags per club-season. About one in ten will end in an arm IL stint within two weeks. Nine in ten won't.
   - In 2026 the flag was sharpest for starters: 9 of 24 flags (37.5%; 21.2% to 57.3%), which were 7 stints, against 8 of 140 for relievers (5.7%; 2.9% to 10.9%). That split was added after the main results and rests on 7 starter stints, so treat it as a lead, not a rule. Relievers make most of the flags (about 4.7 of the 5.5 per club-season), and their 2026 precision didn't beat their base rate.
2. **Don't build or buy an injury forecast on public pitch data.** On a season it never saw, a model with every velocity, spin, shape and release drop ranked risk no detectably better than one built on role, workload and IL history. Gains up to about 0.03 AUC aren't ruled out, and at the top 1% it caught 20 stints to the naive model's 15; that is too small a gain to build or buy on.
3. **Don't treat a spin, ride or release change as an injury sign on its own.** None carries a confirmed association once velocity is in the model; a release-height drop is the one lead worth scoring on 2027.
4. **For weeks-ahead warning, look past game data.** The public signal lives in the outing where something already went wrong. Earlier warning needs what the club has and the public doesn't: bullpen and catch-play velocity, strength and range-of-motion screens, and what the pitcher reports.

## Findings

### 1. IL rate by this outing's velocity drop (arm injuries, within 14 days)

| Fastball vs his baseline | 2024–25 outings | IL rate (95% interval) | 2026 outings | IL rate (95% interval) |
|---|---|---|---|---|
| 1+ mph above | 3,515 | 2.2% (1.8–2.8%) | 1,791 | 2.7% (2.1–3.6%) |
| 0–1 mph above | 15,708 | 2.8% (2.5–3.0%) | 7,784 | 3.5% (3.2–4.0%) |
| 0–1 mph below | 14,155 | 3.7% (3.4–4.1%) | 7,296 | 3.3% (2.9–3.8%) |
| 1–2 mph below | 2,904 | 5.4% (4.6–6.3%) | 1,596 | 5.0% (4.0–6.2%) |
| 2–3 mph below | 292 | 9.2% (6.4–13.1%) | 149 | 9.4% (5.7–15.2%) |
| 3+ mph below | 39 | 23.1% (12.6–38.3%) | 15 | 3 of 15 (7.0–45.2%) |

- **Reading the table:** the drop is this outing's fastball mean against his regressed baseline, adjusted for the league's month-of-season curve (Method). Intervals are Wilson intervals on outings.
- **The pattern holds on 2026:** for drops of 1 mph or more, the 2026 rates match 2024–25 within their intervals. In 2026, drops under 1 mph sat at the base rate.
- **Outings are not independent:** a pitcher's several outings before one stint all count. The model tests below cluster by pitcher.

### 2. Does tracking data improve the forecast? (2026, models fit on 2024–25)

| Outcome | Outings (events) | AUC naive | AUC tracking | Tracking − naive, AUC (95% interval) | Velocity only − naive, AUC | Velocity drop, 2026 refit, odds ratio per SD |
|---|---|---|---|---|---|---|
| **Arm IL within 14 days (main)** | **18,631 (665)** | **0.571** | **0.576** | **+0.005 (−0.022 to +0.031)** | **+0.009 (−0.013 to +0.032)** | **1.18 (1.07 to 1.30)** |
| Arm IL within 7 days | 18,631 (393) | 0.570 | 0.600 | +0.030 (−0.005 to +0.064) | +0.028 (−0.003 to +0.060) | 1.36 (1.19 to 1.56) |
| Arm IL within 30 days | 18,631 (1,173) | 0.578 | 0.584 | +0.006 (−0.015 to +0.027) | +0.012 (−0.005 to +0.029) | 1.09 (1.03 to 1.15) |
| Arm IL within 14 days, stint's last outing left out | 18,456 (490) | 0.566 | 0.557 | −0.008 (−0.030 to +0.014) | −0.002 (−0.022 to +0.016) | 1.02 (0.91 to 1.14) |
| Any IL within 14 days | 18,631 (1,170) | 0.563 | 0.564 | +0.001 (−0.014 to +0.015) | +0.004 (−0.010 to +0.018) | 1.10 (1.02 to 1.19) |
| Lower-body or illness IL within 14 days (specificity check) | 18,631 (253) | 0.625 | 0.625 | −0.000 (−0.014 to +0.013) | −0.001 (−0.006 to +0.003) | 1.00 (0.86 to 1.17) |

- **Intervals:** 1,000 bootstrap resamples of pitchers on the 2026 outings.
- **Log loss** (the tracking model against the naive one) is not better in any row. Across the six rows the smallest Benjamini–Hochberg q is 0.80.
- **The 7-day row is the closest** (+0.030, p = 0.11). It is not confirmed, and it is the row most dominated by the last outing before the stint.
- **The specificity check is mixed:** on 2026 the drop has no association with lower-body or illness placements (1.00, 0.86 to 1.17, 253 events), but in the 2024–25 fit it had one (1.15 per SD, p = 0.010, q = 0.08). So part of the signal may be a general "something is off" marker, which is one more reason to treat a flag as a question for the trainer, not an arm diagnosis.
- **The last column** refits the velocity model on 2026 alone. It shows the association is there; the AUC columns show it doesn't rank enough outings to matter as a forecast. Fewer than 200 outings a season have a drop of 2 mph or more (164 in 2026).
- **Calibration on 2026** (main row): slope 0.63 (SE 0.10) naive, 0.56 (SE 0.08) tracking; mean predicted 3.4% and 3.5% against 3.6% observed.

**The tracking model's terms, fit on 2024–25** (main outcome; odds ratio per standard deviation of the drop, clustered by pitcher):

| Term | Odds ratio | p | BH q (8 tracking terms) |
|---|---|---|---|
| **Velocity, this outing** | **1.29** | **< 0.001** | **< 0.001** |
| Velocity, last three outings | 1.08 | 0.11 | 0.30 |
| Release height, last three outings | 1.11 | 0.036 | 0.15 |
| Extension, last three outings | 0.96 | 0.45 | 0.89 |
| Spin, this outing | 1.00 | 0.91 | 0.96 |
| Spin, last three outings | 1.00 | 0.96 | 0.96 |
| Ride (induced vertical break), last three outings | 1.00 | 0.94 | 0.96 |
| Arm angle, last three outings | 0.98 | 0.62 | 0.96 |

- **The naive terms, for scale** (same model): a starter 2.95 times the odds of a reliever, an IL stint in the last 365 days 1.59, and each 100 pitches in the outing 0.23. Fewer pitches go with more risk, so the naive model already catches some injury exits.

### 3. Alert rules on 2026 (arm IL within 14 days)

| Rule (threshold set on 2024–25) | Flags per club-season | Precision (95% interval) | Lift over 3.6% | False alarms per club-season | Stints caught (of 175) | Median days to effective date |
|---|---|---|---|---|---|---|
| Fastball 1.0+ mph below | 58.7 | 5.5% (4.5–6.7%) | 1.5 | 55.4 | 67 | 3 |
| Fastball 1.5+ mph below | 18.1 | 6.1% (4.4–8.4%) | 1.7 | 17.0 | 26 | 2 |
| **Fastball 2.0+ mph below (chosen)** | **5.5** | **10.4% (6.6–16.0%)** | **2.9** | **4.9** | **15** | **2** |
| Fastball 2.5+ mph below | 1.4 | 14.6% (6.9–28.4%) | 4.1 | 1.2 | 6 | 1.5 |
| Fastball 3.0+ mph below | 0.5 | 3 of 15 (7.0–45.2%) | 5.6 | 0.4 | 3 | 1 |
| Tracking model, top 1% of 2024–25 risk | 7.7 | 10.8% (7.4–15.5%) | 3.0 | 6.9 | 20 | 1 |
| Naive model, top 1% of 2024–25 risk | 8.2 | 6.9% (4.4–10.8%) | 1.9 | 7.6 | 15 | 1 |
| Tracking model, top 5% | 35.1 | 6.8% (5.5–8.5%) | 1.9 | 32.7 | 49 | 2 |
| Naive model, top 5% | 36.4 | 6.9% (5.5–8.5%) | 1.9 | 33.9 | 45 | 6 |

- **The chosen rule held its training numbers:** on 2024–25 it gave 5.5 flags and 4.9 false alarms per club-season at 10.9% precision (8.0% to 14.7%). On 2026: 5.5, 4.9 and 10.4%.
- **At the very top, the tracking list is the velocity flag again.** Its top 1% caught 20 stints against the naive list's 15, a median 1 day before the placement. That comparison is descriptive; the two lists weren't tested against each other.
- **Lower thresholds don't buy warning, they buy noise.** At 1.0 mph a club gets 59 flags a season to catch about 2 of its own arm stints (67 of 175 league-wide), with 1 in 18 flags followed by an arm IL placement.

**Splits of the chosen rule** (exploratory: added after the main results):

| Split | 2024–25 flags, precision | 2026 flags, precision (95% interval) | 2026 median days to effective date |
|---|---|---|---|
| Starters | 64, 17.2% | 24, 37.5% (21.2–57.3%) | 2 |
| Relievers | 267, 9.4% | 140, 5.7% (2.9–10.9%), p vs base rate 0.15 | 2.5 |
| Normal-length outing (75%+ of his recent pitch count) | 181, 11.6% | 93, 11.8% (6.7–20.0%) | 6 |
| Short outing | 150, 10.0% | 71, 8.5% (3.9–17.2%) | 1 |
| Stint's last outing left out | 310, 4.8% | 155, 5.2% (2.6–9.9%), p vs base rate 0.07 | 7 |

- **Starters:** a possible reason, not tested here: a starter's fastball mean comes from more pitches, and his rest is regular, so a drop is less often noise. The starter base rate is 4.0% in 2026.
- **Relievers:** a reliever's drop is noisier (fewer fastballs, back-to-back days), and in 2026 the flag was not distinguishable from his base rate.
- **The flag is not just an injury exit:** in a normal-length outing it still ran 11.8% in 2026. It isn't only the pitcher who left the game hurt.
- **Without the last outing,** the rule is borderline on 2026 (p = 0.07), a median 7 days ahead, after 4.8% (lift 1.96, p = 0.015) on 2024–25. That's about twice the base rate in both periods, on 7 and 13 stints.

### 4. Who the study can see
- **2026 arm placements:** 205 took effect between the first and last game of the season for pitchers who pitched in the majors that year. 175 (85%) had a scored outing in the 14 days before. 2024: 174 of 241. 2025: 167 of 231.
- **The rest** were optioned or hurt in the minors, had too few outings for a baseline, or had last pitched more than 14 days earlier.

## Method
**Grain.** One row per pitcher outing (pitcher, game), regular season. Fastball physics are computed per fastball type (four-seamer, sinker, cutter) per game, then combined by pitch count.

**The baseline: his own, regressed** (per pitcher, season, fastball type and metric):
- **Month curve:** each game mean is first adjusted by the league's month-of-season curve for that type and metric, fit on 2024–25. The normal rise in velocity into summer isn't counted as a change.
- **Noise per game:** day-to-day plus pitch-to-pitch, γ² + σ²/n. This is the [Reliability Atlas](2026-reliability-atlas.md)'s two-level physics model, re-estimated here on 2024–25 only.
  - Four-seam velocity: σ = 0.94 mph pitch to pitch, γ = 0.65 mph day to day. The Atlas, on all three seasons, has 0.94 and 0.67.
- **Prior:** last season's mean for the type, with variance (its own noise + δ², the year-to-year change in true level; δ = 0.80 mph for four-seam velocity). With no last season, the league mean with the spread between pitchers.
- **Baseline before a window:** the normal–normal posterior from the prior and every earlier game of that type this season.
- **Windows:** this outing (k = 1) and his last three outings with the type (k = 3).
- **The drop:** baseline minus window, in the metric's units, and as z = drop / √(baseline variance + window variance).
- **Metrics:** velocity, spin, induced vertical break, extension, release height and arm angle, each from the fastballs.
- **Model inputs:** the z values, clipped at ±5 (a handful of tracking errors reach 15+). A missing spin or arm-angle reading is set to 0, i.e. at his baseline.

**Scored outings.** 18,631 of 20,800 in 2026 (17,919 in 2024; 18,694 in 2025). An outing is scored when:
- he threw a fastball in it, and in at least two earlier outings this season with that fastball type;
- his baseline has last season as its prior or at least three earlier fastball games this season;
- his fastball baseline is 85 mph or more (this drops position players pitching).

**IL placements.** Every "placed ... on the N-day injured list" record in the Stats API transactions, 2023–26 (2023 for the one-year IL history only).
- **Dropped:** transfers from the 15-day to the 60-day list, and activations.
- **The date:** the effective date, which is the retroactive date when a club backdates the move.
- **Category:** from the reason text.
  - **Arm:** elbow, UCL, ulnar, Tommy John, forearm, flexor, pronator, extensor, shoulder, rotator cuff, labrum or labral (not hip), capsule, lat or latissimus, teres, biceps, triceps, "arm", thoracic outlet, scapula, median or radial nerve, subscapularis, acromioclavicular, plus the misspelling "should" for shoulder. The Nov. 24 fix added ulna, brachialis, AC joint and the misspellings "elnow" and "unar"; the saved numbers come from the list before those five.
  - **The other categories:** hand and finger, trunk, lower body, illness, other, and unspecified (no reason given).
  - **2026 placements by pitchers who pitched in the majors that year, calendar year:** arm 249, lower body 88, trunk 56, unspecified 22, other 17, hand 17, illness 8.

**The label.** 1 if a placement of the category takes effect in the 14 days after the outing's date (from the day after through day 14). A placement effective the same day doesn't count.

**Models.** Logistic regression fit on 2024–25 outings, standard errors clustered by pitcher.
- **Naive:** starter, age, an IL placement effective in the 365 days up to the outing, pitches (per 100), pitches against the mean of his previous five outings in the same role this season, log days of rest, month.
- **Tracking:** the naive model plus the eight drop terms in finding 2.
- **Velocity only:** the naive model plus the two velocity terms.

**Scoring on 2026.**
- **Measures:** AUC, log loss and Brier score.
- **Model differences:** a bootstrap that resamples pitchers (1,000 draws).
- **Calibration:** the slope of the observed outcome on the logit of the forecast.
- **Rules:** Wilson intervals, and an exact binomial test against the base rate (the base rate taken as known). Both treat flags as independent; several flags can precede one stint (the 17 true flags were 15 stints), so these intervals and p-values are somewhat too narrow.
- **Multiple tests:** Benjamini–Hochberg across the six outcome rows and across the eight tracking terms.

**Fixed before the test season was scored:** the specifications, the 14-day main horizon, the six outcome rows and the threshold rule (lowest threshold on a 0.5 mph grid with at most 10 false alarms per club-season on 2024–25). Added after the first scoring of 2026: the 2026 refit of the velocity term (a check on the association, not a forecast), the rule on the early sample, and the starter, reliever and outing-length splits. The splits are labeled exploratory.

**Tests.** 36 in `tests/test_il_warning.py`, on hand-built fictional data with the arithmetic in comments. They cover:
- the injury categories (including a hip labrum and "inflammation" not reading as a lat, and the Nov. 24 wordings)
- pitch-clock automatic balls and strikes not counted as pitches
- placements against transfers and activations, and the retroactive date
- outings, starters and teams; game means and within-game sums of squares
- the two noise terms; the month curve
- the baseline against a league prior and against last season, by hand
- combining fastball types by pitch count
- the label window, the same-day rule and the last-outing flag
- IL history, rest and pitch ratio; which outings are scored
- the logistic fit against a 2 × 2 table; AUC, log loss and Brier
- recalibration of a calibrated forecast; the bootstrap
- the alert table and the threshold rule

`tests/test_report_outputs.py` checks this page's headline numbers against the saved outputs.

## Limits
- **Observational.** A drop and a placement can share a cause the data can't see, and clubs may place a pitcher on the IL partly because they saw the drop.
- **The IL date is the club's choice.** Retroactive dates, roster needs and the 15-day minimum all move it. Some placements may be roster decisions with a mild injury attached, and the data can't tell which.
- **The public sees only major-league games.** Bullpen sessions, catch play, minor-league rehab games and the trainer's notes are where a club would see a problem first. Pitchers optioned and hurt in the minors never get a label here.
- **Lead time is measured to the placement, not to when the club knew.** The flag's median 3 days to the announcement is not 3 days of new information. The club may have known as soon as the outing ended.
- **The 2024 baselines are weaker.** There's no 2023 pitch data in the study, so 2024 baselines start from the league mean and need three games.
- **One test season.** 175 arm stints in 2026. The starter split rests on 24 flags from 7 stints.
- **Many checks.** Six outcome rows, nine rules and five splits are read off one season; only the model comparisons and tracking terms carry a multiple-test correction.
- **Nothing here is a diagnosis.** A flag is a reason to ask, and the answer comes from the medical staff.
- **Found after the run (Nov. 24, 2026 code check):** the arm classifier missed a few wordings in MLB's own transaction text ("brachialis," "ulna," "AC joint" and the misspellings "elnow" and "unar"), so those placements were filed as "other." One is a 2026 test-season arm stint (Matt Waldron, May 15). The outing pitch counts also included pitch-clock automatic balls and strikes. Both are fixed in the code; the numbers above are from the saved run before the fix, and the next run with the pitch files recomputes them. What moves: the reclassified stints change the arm counts (249, 205, 175), the arm base rate and every arm row, rule and AUC, by about one stint in 175 in 2026; any in 2024–25 also shift the training labels and could move the threshold choice. The any-IL and lower-body or illness rows don't change. The pitch-count fix changes pitches thrown and the outing-length ratio, so it moves every model's AUC, calibration and top-% rule and the normal/short-outing split, but not the velocity bins or the 2.0 mph rule's flags, which use fastballs only. I expect small moves; the counts by season come with the rerun.

## Next steps
- **Score 2027 with the rule and the threshold as they stand.** A second held-out season would tighten the 10.4% and test the starter split.
- **Add the in-game velocity path:** a drop within an outing (first inning against the last) may come earlier than the outing mean.
- **Add breaking-ball and changeup velocity, and pitch-mix changes,** as candidate early signs, with the same correction for many tests.

## Reproduce
```bash
uv run bb il-warning 2026     # fit on 2024-25, score 2026 -> data/edge/il_warning/ and reports/outputs/il-warning-2026.json
uv run pytest tests/test_il_warning.py tests/test_report_outputs.py
```
The study reads `data/seq/` (`bb seq` for 2024, 2025 and 2026) and pulls the Stats API transactions into `data/raw/transactions/` the first time it runs.

## Sources
- **Pitch data:** Statcast, MLB Advanced Media, via [Baseball Savant](https://baseballsavant.mlb.com/) (regular seasons 2024–2026).
- **IL placements:** the MLB Stats API transactions endpoint (`statsapi.mlb.com/api/v1/transactions`), calendar years 2023–2026, pulled 2026-11-15.
- **The two-level noise model for pitch physics:** this repo's [Reliability Atlas](2026-reliability-atlas.md), re-estimated here on 2024–25.
- **Every number on this page:** `bb il-warning 2026`, saved as `data/edge/il_warning/summary.json` and copied to [`reports/outputs/il-warning-2026.json`](outputs/il-warning-2026.json).

---
© 2026 Dylan Fanelli. All rights reserved. See [LICENSE](../LICENSE).

<!-- portfolio:footer -->
---
<sub>[← Portfolio](../README.md) &nbsp;|&nbsp; [← Development plan](2026-development-plan.md) &nbsp;|&nbsp; [Roster and CBA engine →](2026-roster-cba-engine.md)</sub>

<sub>© 2026 Dylan Fanelli. All rights reserved. To cite: Fanelli, D. (2026). *Velocity drops as an injured-list warning: what public pitch data can tell a medical staff (MLB 2024–26)*. Dylan Fanelli Baseball Analytics Portfolio. https://github.com/IForSureI/Dylan-Fanelli-Baseball-Analytics-Portfolio/blob/main/reports/2026-il-early-warning.md</sub>
<!-- /portfolio:footer -->
