# Log

Newest first. One entry per working session: what was built, what was decided, what was learned.

## 2026-11-23: Seiya Suzuki in the swing lab
**Built**
- **Suzuki's 78 home-run clips** through the same video pipeline: 17 measurable after I removed two by eye (a side replay and an off-axis camera; `reports/outputs/suzuki_excluded_by_eye.json`). Contact read by eye on five swings came 6-7 frames after the shoulders square, in line with Arozarena's offset.

**Learned**
- His home-run swing shows no significant change in sequence or posture, and his home-run contact held steady (median exit velocity 104.9, 105.6, 105.0). His toe-tap load barely lifts the front foot, so foot-down timing can't be read from the center-field camera for him. His ISO still projects down (.179-.191 against .204), which is regression rather than a warning sign.

## 2026-11-23: Randy Arozarena, frame by frame
**Built**
- **Video lab** (`baseball/video/`, `bb swing-video`): it finds MLB's own highlight clip of every play through the MLB Stats API content feed (matched by Statcast play id). It cuts the clip into camera shots, finds the center-field pitch view, and tracks the batter frame by frame with a pose model at 59.94 fps. Then it measures timing and posture from the big joints, and draws the figures from the measured joints, so no MLB frame is reproduced.
- **Arozarena breakdown** (`reports/2026-arozarena-swing-breakdown.md`): all 73 of his 2024-26 home-run clips, 23 measurable. Contact is timed from the moment his shoulders square, with the offset read by eye on seven swings (5 to 7 frames, median 6).
- **Bat tracking vs power** (`bb bat-power`): fit on 2024 to 2025, scored on 2025 to 2026, with the batted-ball model chosen by cross-validation on the training pairs (ISO + barrel rate). Bat speed and swing length add about 1% of the error; nothing moves it by 0.001 ISO.

**Learned**
- His 2026 ISO rise is fewer strikeouts (26.8% to 21.6%) with flat damage per contact at-bat (.272 both years), while barrels, hard-hit exit velocity and bat speed fell. The league model puts his 2027 ISO at .169-.180, which supports prediction-log call 6. The video found no timing change larger than it could detect (78 ms at foot down). Head drop differs, but the parks are too lopsided to say whether it's him or the cameras.
- Savant's own clip host sits behind a bot check, so I didn't use it. MLB's content feed serves the same broadcast clips openly.

## 2026-11-23: Catcher framing after the ABS challenge system
**Built**
- **Framing study** (`reports/2026-catcher-framing.md`, `bb framing`): a called-strike model on every 2024-26 take (1.11 million), fit out of fold by game; extra strikes valued count by count from run expectancy; a pitcher- and park-adjusted version. It matches Baseball Savant's framing runs at r 0.97, 0.98 and 0.92.
- **League data on the cloud machine:** I pulled 2024-26 Statcast and wrote the sequence files there too, so studies that need every pitch no longer wait for the Mac.

**Learned**
- In 2026, the first ABS challenge season, calls got clearly more predictable: the uncertain band shrank from 21% of takes to 15%, and called balls well inside the zone nearly disappeared. Framing's spread per pitch fell 23% on my model and 10% on Savant's, after a 8-10% drop the year before, so I can't separate an ABS effect from the trend on one season. Patrick Bailey went from +27.6 to +3.3. Framing still repeats within a season (0.73). The year-to-year drop (0.61 to 0.34 on the same 37 catchers) isn't significant.
- Baseball Savant's leaderboard CSV ignores `year=` and returns the current season; the season has to go in `seasonStart` and `seasonEnd`. A test keeps it that way.

## 2026-11-23: The 2026-27 market board
**Built**
- **Market board** (`reports/2027-market-board.md`, `bb market`): 38 dated calls on this winter's open free agents, each an average salary and a probability of signing above MLB Trade Rumors' predicted salary, scored against MLBTR's Nov. 2 calls as players sign. The calls are frozen in `market/calls_2026-27.json`.
- **The model:** it starts from MLBTR's number and moves it on Baseball-Reference WAR (three seasons, weighted 5/4/3), platform-season WAR, age and role. It is fit on the 2025-26 class, the one past winter whose signings MLBTR records on its list page. In the leave-one-out backtest my average error was $3.24M a year against MLBTR's $3.79M (95% range of the edge -$0.66M to +$2.05M; closer on 21 of 44), and the over/under Brier score was 0.218 (coin flip 0.250).

**Learned**
- Last winter's free agents took shorter deals at higher salaries than MLBTR predicted: salaries $2.0M a year low, years 0.8 long, total guarantees $10.6M high. Relievers beat their predictions most.

**Not done**
- MLBTR's 2022-23 to 2024-25 lists don't record the signings, and news posts word the terms too inconsistently to use as one answer key, so the backtest is one winter.

## 2026-11-18: Morejón declined the qualifying offer
**Built**
- **Bullpen memo, one-page and Morejón report:** he turned down the Padres' $23.15M qualifying offer on Nov. 17 and is a free agent (MLB.com, AJ Cassavell; NBC Sports; both Nov. 17, 2026). The pages now say so, the memo has a dated Nov. 18 update, and the "if he accepts" branch is marked as not having happened. The price, grades, ranking and recommendation did not change: the Nov. 14 numbers already assumed the offer was attached.

- **Prediction log:** a dated Nov. 18 note records that Morejón, Rogers and Arozarena (calls 1, 3 and 4) all declined, so none of the three calls can resolve false through an accepted offer; Bednar and Jeffers accepted (MLB.com; NBC Sports; Nov. 17, 2026). The calls and probabilities are unchanged.
- **Morejón one-page PDF (Nov. 19):** the status line now reads that he declined the Padres' $23.15M qualifying offer on Nov. 17 and is a free agent (MLB.com, Nov. 17, 2026). Nothing else on the page changed.

## 2026-11-18: TrackMan loader keeps contact point, hang time and catcher throws
**Built**
- **Loader:** `baseball/ingest/tracking.py` now keeps TrackMan's contact point (`contact_depth` from ContactPositionX, feet in front of the plate; `contact_height` and `contact_side` from Y and Z), hang time, bearing and peak height, and the catcher-throw fields (pop time, exchange time, throw speed). On a public college export (Mendeley Data, CC BY 4.0) contact depth runs -1.4 to 4.7 ft with a 2.2 ft median, and 76 throws carry a pop time (median 2.07 s). A test covers the mapping; the sample generator's column list carries the three throw fields.
- **Sequence files keep the catcher:** `fielder_2` joins the columns the monthly update writes, so a framing method can be checked against MLB catchers.

## 2026-11-15: Skenes checks sourced, first-person rule, one index row
**Built**
- **Skenes memo, the three open items:** I read the published surgery rates and set them beside the 20% stress chance (`skenes_injury_check()`, saved in `reports/outputs/skenes-checks-2026.json`). 25% of major league pitchers (96 of 382; Conte et al., AJSM 2015) and 33.0% of 2011-20 top-five-round draftees (281 of 851; Kriz et al., JSES International 2026) have had an elbow ligament reconstruction; a surgery costs a mean 470 days (Meta et al., OJSM 2025). None is a forward eight-year chance, and the stress path (44% of his wins lost in every season) is harsher than one surgery, so each share is read two ways: time missed only (9% and 12% stress chance, break-even $230M and $227M) and as the stress chance itself (25% and 33%, $213M and $204M). The headline keeps 20% and about $215M, now inside a sourced bracket of 9% to 33% and $204M to $230M; "no sourced injury rate" is gone. The cap chance stays a scenario because no source prices it; the memo now cites the Nov. 3 offer (cap from 2028 at $258.2M; MLB.com and AP, Nov. 4), which is 2.2% above the memo's cap path and moves the MLB-plan ceiling from $198M to about $201M if the 16% share holds (not re-priced, because neither article states the maximums). Win curve: `skenes_win_curve_check()` and `club_ceiling_own_value()` apply the shape of Gennaro's 2006 revenue curves (five wins worth $4.2M at 78 wins and $11.7M at 86) under one stated anchor: a contender walks away at $218M, a club near .500 for all eight years at $109M to $144M. It is a labeled sensitivity, and a current curve (marginal revenue per win at 70 to 100 wins, current playoff format, 2026 dollars) is still open. Six new tests in `tests/test_roster_money.py` and one in `tests/test_report_outputs.py`; a note in `docs/valuation-conventions.md`.
- **First person, checked by a test:** `tests/test_voice.py` fails if any page refers to me in the third person or shows a scratch path or tool name. The rule is in `docs/report-standard.md`.
- **Saved outputs index:** a row for `edge-shift-null-2026.json`.
- **Edge Board, an outside benchmark against Baseball Savant (not Stuff+):** `baseball/edge/savant_benchmark.py` matches my pitch tables for 2024-2026 to Savant's Pitch Arsenal Stats and Swing Timing + Miss Distance leaderboards on MLBAM pitcher ID and pitch type (each page's CSV download, pulled Nov. 15; 60-swing floor on my side; knuckle curves matched to Savant's curveball row). Pipeline: my whiff rate from the pitch files sits 0.03 to 0.04 points from Savant's whiff% on average, and Savant counts foul tips as whiffs as I do. Same season: expected whiff against miss distance is r = 0.71 across all pitches and 0.25 within pitch type (4,964 pitches); against run value per 100 it is 0.04 and 0.11. Next season, weights fit on 2024 → 2025 and scored on 2025 → 2026 (1,040 pitches): last season's whiff rate wins alone (RMSE 5.57, expected whiff 6.37, miss distance 6.97). My expected whiff beats raw miss distance and ties it once pitch type is known (6.18 vs. 6.03). Added to last season's whiff rate, mine cuts error 6.5% and miss distance 4.2%, a tie given pitch type (7.2% and 7.3%); all three together cut 7.6%, so miss distance holds something my model lacks. The page now says my model is about as good as miss distance and no better. Saved in `reports/outputs/edge-savant-benchmark-2026.json`, with a check in `tests/test_report_outputs.py` and 15 logic tests in `tests/test_edge_savant_benchmark.py`. The "No outside benchmark yet" bullet is replaced; the Stuff+ comparison stays open and still needs the FanGraphs members-only export.
- **Edge Board, the Stuff+ benchmark:** `baseball/edge/stuffplus_benchmark.py` sets my expected whiff beside FanGraphs Stuff+ by pitch type for 2025 and 2026 (the public leaderboard page as read Nov. 15, 2026: 734 of 873 pitchers for 2025, 597 with 15+ innings for 2026), with Savant miss distance and run value on the same pitches. IDs go through the Chadwick register (734 of 734 rows for 2025, 514 of 597 for 2026; the 83 without a link are left out, no one matched by name). Pitch-type rule, from the counts: sweepers read FanGraphs' SL column (filled for 94 of 95 and 79 of 79 pitchers with a sweeper and no slider) and slurves its CU column; a pitch sharing a column must be 90% of the pitcher's pitches there. Same season: r = 0.35 across all pitches and 0.47 within pitch type (2,948 pitches). Against Savant's run value per 100, within type: Stuff+ 0.26, mine 0.11. Pitcher level: 0.29 (1,059 pitcher-seasons). Next season's whiff rate, 2025 → 2026 only, five-fold cross-validation by pitcher (966 pitches): given the pitch type, Stuff+ beats my model alone (RMSE 5.89 vs. 6.10, difference 0.21, interval 0.03 to 0.39); added to last season's whiff rate and pitch type the two tie (8.1% and 7.9% cut in error). The page says so. It also found a weakness: on 174 sweepers my expected whiff does not track the actual whiff rate (r = 0.07) and Stuff+ does (0.44). Saved in `reports/outputs/edge-stuffplus-benchmark-2026.json`, with a check in `tests/test_report_outputs.py` and 13 logic tests in `tests/test_edge_stuffplus_benchmark.py`. Limits on the page: one season pair, no 2024 table, only the pitch types FanGraphs lists.
- **Stuff+ benchmark, now held out:** with the 2024 FanGraphs table (588 pitchers with 15+ innings, read from the public page Nov. 15), every model's weights are fit on 2024 → 2025 (918 pitches) and scored on 2025 → 2026 (963 pitches, 388 pitchers, 15+ innings in each earlier season). Given the pitch type, Stuff+ beats my expected whiff alone (RMSE 5.84 vs. 6.05; difference 0.21, interval 0.05 to 0.37). Added to last season's whiff rate and pitch type they tie (7.7% and 7.8% cut in error; difference -0.01, interval -0.05 to 0.04). Each adds 0.04 of RMSE to the other's blend, a clear gain held out that was not clear cross-validated. The cross-validated numbers stay on the page beside these. Only 3 of 966 scored pitches come from the under-15-inning rows the 2025 table kept, so the innings floor changes nothing.
- **Sweepers diagnosed, no fix adopted (`baseball/edge/stuff_checks.py`, `reports/outputs/edge-stuff-checks-2026.json`):** expected against actual whiff rate on sweepers is r = 0.23, 0.14 and 0.14 in 2024-26, the weakest type every season. It is not a sign, label or pooling error: the average is right, the model sorts sweeper swings as well as slider swings (AUC 0.56 inside each type), and pitch type as an input changes nothing. Sweeper whiffs follow usage: chase share r = 0.62 on 431 sweeper seasons, against 0.28 for the best physical measure (fastball velocity). I set the rule first (lower held-out sweeper error with an interval off zero, no type clearly worse) and tried pitch type, fastball velocity, and fastball velocity plus shape as inputs, and a sweeper-only model. None passed, so `stuff.py` is unchanged and no published number moved. No report quotes a sweeper grade from the model.
- **Refit noise measured:** the same swings in another row order move a pitch's expected whiff 0.64 to 0.65 points on average (6.5 to 8.2 on the worst pitch), because the cross-fit folds and the binning follow row order. Same rows, same order, same machine agree exactly. The 6.4% against 6.5% gap between the saved tables and my refit (0.5 points per pitch) is smaller than that. I cannot say whether the saved run differed in row order or in library version.
- **Quoted pitch grades now carry their refit range (`baseball/edge/grade_noise.py`, `reports/outputs/edge-grade-noise-2026.json`):** the bullpen memo and the Morejón report quote stuff and 2027 grades for ten pitches (Morejón, Abreu, Fairbanks) from one fit. I fit the same swings ten times in different row orders and regraded each pitch. Nineteen of the twenty grades stayed within 5 points of the printed one. Fairbanks's slider stuff grade did not (printed 40, 35 to 50 across fits, expected whiff 27.7% to 32.7%), so the memo now prints 35-50 and says the physics grade is not stable; the results beat it in every fit. Morejón's slider stuff grade (70) runs 70 to 75, so "physics far ahead of results" holds. No role, OFP or ranking moved. A test keeps the noise lines on both pages. The Morejón PDF still says "a 70 stuff grade" without the range and needs a rebuild.
- **The bullpen memo's model numbers now come from the saved run (`reports/outputs/bullpen-grades-2026.json`):** the Oct. 14 memo printed stuff and 2027 numbers from a fit that was never saved. Every stuff grade, 2027 grade, expected whiff, gap and engine whiff projection in it now equals the saved Nov. 14 run, written by `grade_noise.py --saved` and held by a test. Four grades moved 5 points (Abreu slider stuff 60 to 65 and 2027 60 to 65, Fairbanks four-seamer stuff 65 to 60, Fairbanks slider stuff 40 to 45, Morejón slider 2027 55 to 50), Morejón's three gaps and all nine by-season lines moved, and nine of thirteen engine whiff projections moved 0.1 or 0.2. One read changed: Fairbanks's physics did not improve every year (28.3%, 26.6%, 30.8%). The ranking, roles, OFPs, prices and recommendation did not move. The memo's figure still shows the earlier fit and needs `bb bullpen-case` rerun.
- **Location-aware expected whiff, a second measure (`baseball/edge/stuff_location.py`, `reports/outputs/edge-stuff-location-2026.json`):** the stuff model plus where the pitch crossed the plate and the count, cross-fit the same way. It is not stuff, and the stuff grade keeps its meaning. On sweepers it tracks the actual whiff rate at r = 0.75, 0.71 and 0.71 in 2024-26 (physics: 0.23, 0.14, 0.14) and sees next season's rate at 0.61 (physics 0.14, last season's rate 0.65). Held out (weights from 2024 → 2025, scored on 2025 → 2026), used alone it beats the physics number on all pitches (-0.65 RMSE, -0.87 to -0.44) and on sweepers (-1.71, -2.54 to -0.82), with no type worse, so by the rule it is the model read for sweepers, changeups, curveballs and sinkers. Added to last season's whiff rate it is no better than the physics number (+0.04, -0.02 to 0.10) and clearly worse on sliders, so the projection is unchanged. It does not beat last season's whiff rate alone (5.70 vs. 5.56). The Stuff+ benchmark carries it as extra rows; no existing row changed.
- **Morejón one-page PDF rebuilt:** the status line and the price now match the report (qualifying offer made Nov. 2; at or under 4/$60M, was 4/$72M), and the slider line carries the refit range (70-75). Nothing else on the page changed. Its input is saved in `reports/onepage/2026-morejon-pro-scouting-report.json`. The report's status paragraph no longer says the offer is still the Padres' call.
- **Edge Board, a dashboard:** `docs/edge-board.html` puts every pitch of the Oct. 17 run in one table a reader can search, filter and sort (1,889 pitches, 599 pitchers): whiff rate, expected whiff, location-aware expected whiff, the gap, the 2027 projection and 20-80 stuff and 2027 grades, with two charts that follow the filters and a click-through to each pitcher's arsenal. Built by `bb board-web 2026` (`baseball/edge/board_web.py`) from the saved run; nothing is refit. The build stops if a grade differs from one already printed (20 checked) or if the saved tables disagree. Pitch types with fewer than 25 pitches get no grade. Club and usage are counted from the 2026 pitch files. The limits are on top of the page. `tests/test_edge_board_web.py` checks the logic and that every embedded row equals the saved run.
- **Torres one-page PDF:** `reports/2026-hitter-evaluation-torres.pdf`, the hitter evaluation's grades on the 20-80 form beside the Morejón page. Every grade and number is copied from the evaluation (hit 55/50, raw power 35/40, game power 40/40, swing decisions 70/70, run 35/30, field 40/40, OFP 50). Arm, the body, and the swing and glove items that need eyes are NG: there has been no live or video look. Its input is saved in `reports/onepage/2026-hitter-evaluation-torres.json`.
- **Development plan page for player-development readers:** `reports/2026-development-plan.md` puts the hypothetical 2026 plan for Logan Gilbert on one page: three priorities with metric, baseline, target, date, floor, mechanism, process goal, owner, checkpoints, risk and guard, the engine's verdicts as of Sept. 27 (velocity and slider depth on track; slider whiffs inconclusive with the usage guard breached), the power check, and what I would do next. I re-ran the engine and it matches the levers report. The plan is retrospective and finished; no 2027 plan is written. Its checkpoint table is saved (`reports/outputs/idp-gilbert-2026.json`, `bb idp --json`) and held to the page by `tests/test_development_plan.py`. The plan figure was redrawn with its current label.
- **`docs/build_pages.py --only <slug>`:** stamps only the named reports.

**Not done**
- A physics-only fix for sweepers. None of three passed, so my stuff grade on a sweeper stays unproven; the location-aware number is the model read there, and the actual whiff rate comes first.
- A location-aware number that beats last season's whiff rate, or adds to it. This one does neither on sweepers (-0.27 RMSE, -0.61 to 0.07, when added).
- Redrawing the bullpen memo's figure from the saved run (three hollow markers sit 5 points from the tables). It needs the Atlas league means, which are not in this copy.
- Present grades in the bullpen memo are not regenerated by the new check, for the same reason. They do not use the model.
- A second held-out year for the Stuff+ comparison (2027).
- Averaging several cross-fits so one pitch's expected whiff stops moving between fits (0.65 points on average, up to 8 on one pitch). It would move every number built on the model, so it waits for the next full run.
- A register link for the 83 FanGraphs IDs new in 2026.
- A forward eight-year injury rate by age and velocity band, and a current win curve (marginal revenue per win from 70 to 100 wins, 2026 dollars). Nothing published gives either.

## 2026-11-15: Velocity drops as an injured-list warning
**Built**
- **`baseball/health/il_warning.py`, `bb il-warning 2026`:** every pitcher outing of 2024–26 with its fastball velocity, spin, ride, extension, release height and arm angle against his own regressed baseline (the Atlas's two-level noise model and a month-of-season curve, both re-fit on 2024–25), matched to every IL placement in the MLB Stats API transactions. A naive model (role, age, IL history, workload, rest, month) and a tracking model, both fit on 2024–25 and scored on 2026, plus alert rules with false alarms per club-season.
- **`reports/2026-il-early-warning.md`** with its figure, a README row, a "What a club gets" row and a `Health` toolkit row. Status: awaiting its separate review.
- **`reports/outputs/il-warning-2026.json`** and a check in `tests/test_report_outputs.py`; 30 hand-checked tests in `tests/test_il_warning.py`.

**Decided**
- **The alert threshold was set on 2024–25 by a stated rule** (the lowest on a 0.5 mph grid with at most 10 false alarms per club-season): 2.0 mph. 2026 kept the training numbers: 164 flags, 10.4% followed by an arm IL placement within 14 days (base rate 3.6%), 4.9 false alarms per club-season.
- **The starter and reliever split is reported as exploratory.** It came after the first scoring of 2026 and rests on 24 starter flags.

**Learned**
- The association is real and replicates (odds ratio 1.18 per SD on 2026), but it lives in the last outing before the stint. With that outing left out, it is not detected in 2026 (1.02, 0.91 to 1.14).
- Replicating an association is not the same as improving a forecast: the tracking model's AUC gain on 2026 is +0.005 (−0.022 to +0.031).
- Spin, ride, extension, release height and arm angle add no confirmed signal once velocity is in.

**Not done**
- The separate review pass. In-game velocity paths, secondary-pitch velocity and pitch-mix changes as earlier signs. A second held-out season (2027).

## 2026-11-14: Audit fixes: qualifying offers, availability, one valuation table, held-out stuff test
**Built**
- **Bullpen memo and one-pager:** the Nov. 2 qualifying offers entered as facts (AP, CBS Sports): Morejón and Bednar have one, Abreu does not. The memo's own rule now sets the walk-away at four years, $60M, the same as the opening offer, and the landing odds there are 26% (47% at $72M). Abreu is the likely signing. The Fairbanks line now says he is priced for a third of 2027.
- **`baseball/roster/acquisition.py`, `bullpen_case.py`:** `workload_retention()` and `availability_path()`. The 170 relievers with 800+ relief pitches in 2024 kept 63% of that workload in 2025 and 48% in 2026. On that path four years of Morejón are worth $51.5M at the market line ($12.9M a year), not $72M.
- **`docs/valuation-conventions.md`:** one table for the four prices of a win and the one discount convention (10% on dollars, 3% growth, about 7% net). The Torres module now imports growth and discount from `baseball/roster/money.py`.
- **`skenes_flat_price_check()`:** the Skenes grid at one flat price of a win. The break-even at 20% stress and q = 0.25 is about $202M, against $218M on the tiers.
- **`validate_holdout()` in `baseball/edge/stuff.py`:** blend weights fit on 2024 → 2025 and scored on 2025 → 2026. 6.4% less error than a regressed baseline (4.9% to 8.0%; RMSE 5.20 vs. 5.56 on 1,040 pitches).
- **`reports/outputs/` and `tests/test_report_outputs.py`:** small saved tables for the bullpen memo, the Edge Board and pitch familiarity, and a test that checks each report's headline numbers against them.
- **Wording and dates:** pitch familiarity is now "in association, yes" with its placebo stated up front; pitch changes on the Edge Board are candidates; arbitration odds carry their ranges (Smith 49% to 71%, Varland 40% to 77%); the tender deadline is Nov. 20; the draft table says average where it meant average; front-office ties say how the dating rule moves p; the Atlas lists three gaps; the Skubal page is marked as not updated for 2026; two ambiguous lines on the Spanish coach page now carry a subject.
- **README:** the blanket claims are replaced with what was tested and how. The test count is no longer a hard number. "Run it" says what compare-relievers needs.

- **Pitch familiarity, the two open checks:** Pitch familiarity: ran the two open checks on the 2024-26 pitch data (`baseball/edge/familiarity_checks.py`, results in `reports/outputs/familiarity-checks-2024-26.json`, 2,141,219 pitches). Shuffle null, 1,000 shuffles per design and pitch group, seed 20261114: with pitch types scrambled inside the plate appearance the whiff coefficient falls to −0.08 / +0.07 / −0.13 (fastballs / breaking / changeups and splitters) against −0.70 / −0.91 / −1.87 real, and no shuffle reached the real number; about half survives a swap of counts across hitters facing the same pitcher, so that half can't be assigned to the hitter's own exposure. Leave-own-game-out: −0.68 / −0.87 / −1.83 under fixed effects, −0.44 / −0.55 / −1.47 under season levels, all p < 0.001, so the published sizes are now stated as the top of a 60% to 100% range. Downgraded: cutters are unconfirmed (p = 0.09 with the own game left out, p = 0.19 across hitters), and "probably not overstated" is gone because the fixed effects tilt the estimate 3% to 4% away from zero. Fixed two cutter cells that didn't match the saved table (−0.50 to −0.49 whiff; +0.45 (0.23), p = 0.06 to +0.46 (0.24), p = 0.05 chase).
- **The Edge Board's pitch-change detector has a measured chance rate.** `baseball/edge/shift_null.py` puts each pitcher's games in random order and reruns the detector (200 shuffled seasons, seed 20261114, 868 pitchers, 2,144 pitcher-pitch series): about 33 candidates per shuffled season against the 292 found (11%; range 20 to 50), saved in `reports/outputs/edge-shift-null-2026.json`. The report drops "has not been measured" and says about nine in ten are more than chance order. They stay leads: the shuffle cannot tell a deliberate change from drift, and a straight line fits 43 of the 292 as well as the step. The public Stuff+ comparison was tried Nov. 15 and is still not done (the pybaseball pull came back empty); it needs the FanGraphs Stuff+ CSV export for 2025 and 2026.
**Decided**
- **The prediction log's calls are not edited.** The qualifying offers and the held-out result are in a dated notes section above the calls.
- **The Skenes headline keeps the tiered price,** because that is what the cited study reports, and shows the flat-price answer beside it. A club that prices every player at one rate should walk away at about $200M.
- **The Edge Board page is reset to the saved run's table.** Four numbers moved in the last digit (292 candidates, not 291; 8.2% and 2.7, not 8.1% and 2.6; tells +0.19 controlled, not +0.18; portable AUC 0.631).

**Learned**
- The new outputs test caught two of my own numbers the day it was written: the two-season workload figure is 47.5%, which I had written as 47%, and the Edge Board page was one run behind its saved table.
- A walk-away at the market's expected price is not a surplus. Once the offer was made on Nov. 2, the memo's headline ($72M) and its own qualifying-offer rule ($60M) disagreed until this revision.
- Leave-one-out inside the fitting seasons is not a held-out season. The held-out gain is smaller (6.4% against 8.2%).

**Not done**
- A Stuff+ benchmark (the FanGraphs table would not load as data on Nov. 15; it needs a CSV export with player IDs); a sourced injury rate and cap probability for Skenes; a club win curve for any contract price. Each needs the pitch-level data or an outside table, and each report now says so.

## 2026-11-09: Postseason page filters, new palette and display face
**Built**
- **`docs/postseason.html`:** one filter row above every chart (round range, inning, count, reset; sticky, and one line on a phone), so all ten charts re-cut to the same slice. The page carries additive cells per player or club, round, inning group and count, and re-ranks from them; with every filter on "All" it matches the published charts exactly (tested in Python and in the browser). Minimum samples scale with the cut. Charts a filter can't apply to say so. Marks keep the club colours (main colour fill, second colour border); bars rounded at the data end with value labels measured clear of the right-hand column; velocity and exit velocity as dots, since their axis can't start at zero. New palette on warm paper (ink, blue #285d9e, stitch red #c8392b; checked for colour-blind separation and contrast), light only; Be Vietnam Pro for headings in place of Syne.
- **`baseball/house.py`, `baseball/postseason.py`:** the same palette and display face for the static charts and report figures (series: blue, red, green, ochre, validated); the ten postseason charts and the Skenes, Smith and Varland figures redrawn (same numbers).

## 2026-11-08: House chart style for the whole package
**Built**
- **`baseball/house.py`:** one chart style loaded with the package, matching the interactive pages: Syne titles where they fit their panels (one title face per figure), Bricolage Grotesque text, paper and plate surfaces, and a blue, magenta, orange, teal series order checked with the dataviz validator. `baseball/viz.py` takes its tokens from it. Every study picks it up the next time it runs.
- **Redrawn now:** the Skenes extension band and the Smith and Varland arbitration figures, whose numbers come from tables in the code (Smith files $4.65M, 23 comps; Varland files $3.65M; unchanged).

**Not redrawn, and why**
- **Trade network:** a re-pull through Oct. 13, 2026 returns 3,291 trades rather than the report's 3,290 (MLB Stats API revision); the rival rate ratio holds at 0.56 (0.49-0.65), but a figure is only replaced when every number matches, so the reviewed figure stays.
- **GM tree, front-office ties, bullpen memo and the pitch-level studies:** they need hundreds of rate-limited Baseball-Reference pages or the full Savant pull; they take the house style on their next run.

## 2026-11-08: Postseason charts restyled to match the page
**Built**
- **`baseball/postseason.py`:** the ten charts now share the page's design: Syne and Bricolage Grotesque (in `assets/fonts/`, OFL), numbered plates with the number printed in two offset inks, crop marks, the title set left, a plain footer in place of the dark band, names in ink with club colours on the marks, and no bar-end badges or shadows. Same pull and code; `findings.json` and the README are unchanged.

## 2026-11-08: Postseason page redesigned
**Built**
- **`docs/postseason.html`:** set as a long-form essay (Syne and Bricolage Grotesque, risograph pink and blue on off-white), with the 4-1 Series as the one oversized numeral and each chart's takeaway in the margin. Charts redraw at the screen's width so phone text stays readable; a dark mode with its own colors; names in ink with club colors on the marks; a table under every chart, including the World Series game by game; the provenance line at the top.

## 2026-11-08: Numbers on the portfolio page open their breakdowns
**Built**
- **`docs/portfolio.html`:** all 34 number labels on the study cards open a card on hover, tap or keyboard focus: the number's pieces (splits, samples, intervals, the placebo or holdout result, what it's worth), a plain note on what it means, and a link to the report section it comes from. The breakdowns live in `docs/num-details.json`; `docs/build_portfolio.py` puts them in the page. The test count at the top now reads 423.
- **`tests/test_num_details.py`:** every label has a breakdown, every number in a breakdown appears in the report it cites, and every link points at a real heading.

## 2026-11-08: Postseason snippets, interactive
**Built**
- **`docs/postseason.html`** ([live](https://iforsurei.github.io/Dylan-Fanelli-Baseball-Analytics-Portfolio/postseason.html)): the ten snippets as one self-contained web page. Hover, tap or tab to any point for its breakdown: hitters (slash line, wOBA and xwOBA, WPA by round, biggest swing, chase, zone-swing and whiff rate by pitch group, exit velocity, hard-hit rate, barrels), pitchers (WPA by round, biggest out, arsenal with usage, velocity and whiff rate), clubs (record and path, xwOBA for and against, every start from the box scores, top bats and arms) and every pitch of the World Series (count, pitch, speed, result, win-probability change; arrow keys step through a game).
- **`baseball/postseason_web.py`:** builds the page from the same pull and data steps as the charts. The build stops if any headline number (games, pitches, plate appearances, league xwOBA, every club's xwOBA for and against, the top five by WPA, the charted player counts, league chase, velocity and exit velocity, the World Series winners) differs from `findings.json`.
- **`tests/test_postseason_web.py`:** the page's numbers match `findings.json`, every charted player has a breakdown, and the page loads nothing from outside.

**Fixed**
- **`baseball/postseason.py`:** a Nov. 8 re-pull from Savant returned 557 pitch rows twice, verbatim (12,070 thrown pitches instead of 11,513). The pull now keeps one row per pitch, so a refresh reproduces the published numbers.

## 2026-11-08: 2026 postseason snippets
**Built**
- **`reports/2026-postseason-snippets/`:** ten charts on all 40 games of the 2026 postseason (World Series win probability pitch by pitch, team contact quality, hitter and pitcher WPA leaders, results vs. contact, swing decisions, whiffs vs. damage, velocity and exit-velocity leaders, starter depth), with a README written from `findings.json`.
- **`baseball/postseason.py`:** pulls Savant day by day for game types F, D, L and W, names from the MLB Stats API, and draws every chart.
- **`tests/test_postseason_snippets.py`:** the World Series result, the 40-game count and Houston's starter line are pinned to the official record.

**Checked**
- All 40 completed games in the official schedule are in the pull; every game's win-expectancy changes sum to its result.
- Starter depth is read from the official MLB box scores (Houston's starters: two outs in each of two games).

**Review** (separate pass, every number recomputed and checked against MLB Stats API box scores and linescores for all 40 games)
- The World Series result, all 40 final scores and every player's club confirmed.
- Changed: starter depth now comes from the box scores (computing it from pitches gave a starter the out on a plate appearance a reliever finished, and counted intentional-walk placeholders as pitches); `truncated_pa` rows dropped (2,928 plate appearances, not 2,933); automatic balls kept out of pitch counts; the World Series shading is described as "favored", not "ahead"; the win-probability note now says between-pitch changes (pickoffs, caught stealings) aren't credited, so a game falls short of its result by up to about 0.06.

## 2026-11-05: The MLB draft project added to the portfolio
**Built**
- **`reports/2026-mlb-draft-analytics.md`:** my summary of my separate draft repository (pick values on 17 drafts, the college-stat model and its recent-class failure, 2026 bonus pools, amateur pitch shapes graded by this portfolio's whiff model).
- **README:** one row in the research table.
- **Voice:** the draft report, the README intro and About now speak in first person.

## 2026-10-28: The atlas's whiff step, rebuilt in R
**Built**
- **`reports/r/`:** hitter whiff per swing, split-half reliability by game, the fit r(n) = n/(n + M), and `regress()` with intervals, in R (tidyverse, DuckDB through DBI). Data: every 2026 regular-season swing, pulled from Baseball Savant into DuckDB by `pull_swings.R`.
- **A cross-language check:** `python_reference.py` runs `baseball/evaluation/reliability.py` on the same DuckDB file; `check_against_python.R` compares the two. 79 of 79 checks pass.

**Answered**
- **R matches Python.** On the same 20 splits, r(n) agrees to 1e-14; on the same curve, M agrees to within 1e-6 swings; `regress()` agrees exactly. Independent runs: M = 54.5 (R) vs 54.7 (Python) swings, inside Python's own seed-to-seed range (54.2-54.8).
- **2026 alone gives M = 54.5 swings (48.6-61.2),** next to the atlas's pooled 55.4 (49.0-62.7).
- **Splitting by swing instead of by game** gives M = 46.9, the same 1.16 ratio the atlas found.
- **By pitch group (first read, one season):** hitters' whiff rate on offspeed reads fastest (M = 35 swings), fastballs slowest (52).

## 2026-10-20: A second arbitration case, Louis Varland (Toronto)
**Built**
- **`baseball/roster/arbitration.py`:** the case is now data. A `Target` record holds the player, club, seasons, MLB Trade Rumors projection, free-agent year, Super Two cutoff and figure layout; `case(target)` works any of them, and `smith_case()` is a wrapper that returns exactly what it did before (the Smith brief's numbers and figure are unchanged).
- **`bb arb-case varland`** (`smith` stays the default).
- **Report:** [Louis Varland's 2027 arbitration case](reports/2027-arbitration-brief-varland.md), worked from the club side as an independent exercise naming the Toronto Blue Jays.
- **Tests:** 6 in `tests/test_arbitration_varland.py`; the 19 Smith tests are untouched.

**Answered**
- **File $3.65M, settle at $3.8M or less, walk above $3.8M.** The same 23-closer pool puts him at $3.58M; A.J. Ramos's 2016 salary, restated to $3.63M, sets the floor.
- **The club is favored under every weighting:** 61% at a $3.85M midpoint in the base case, 69% reading the comps, 54% reading MLBTR's $3.8M. The two views sit only $0.22M apart, against $0.92M for Smith.
- **Super Two money:** four arbitration years (2027-30), so losing at $4.05M costs $1.39M in present value.
- **His side's best route:** the 2020-26 market alone puts him at $4.40M and drops the club to 40%. The answer is career saves: 35, all from 2026.
- **A 2027 stoppage doesn't move his free agency** (6.111 after 2030); for Smith it adds a year.

## 2026-10-20: The GM tree, built in Neo4j
**Built**
- **`baseball/roster/gm_tree.py`** (`bb gm-tree`): who worked under whom in every front office, from the graph tables `bb front-office` exports.
  - **Outputs:** which bosses had future heads of baseball operations working under them, which clubs future heads came through, PageRank on the tree, and the path today's heads took to the chair.
  - **Neo4j:** `gm_tree.cypher` loads 927 `LEARNED_UNDER` relationships and a `first_head` year beside the trade graph. Graph Data Science's PageRank gives the same top-12 order as the Python version.
  - **Report:** [the GM tree](reports/2026-gm-tree.md).
- **Tests:** 13 in `tests/test_gm_tree.py`, on a fictional front office.

**Answered**
- **More future heads came through Cleveland than any other club.** 15 worked there before their first head job, and 9 hold a top baseball-operations job today.
- **John Hart's tree is the largest across generations and on PageRank.** It has 40 heads, including 21 of today's 38. Directly, he and Epstein are tied at 10, counting people who shared two or more seasons with them.
- **The path to the chair, since 2009:**
  - a median of 14 years from the first recorded front-office job (10-17 for the middle half);
  - 75% held an assistant GM title first;
  - 58% were promoted from inside the club they then ran.

**Changed (same day, after a separate review pass)**
- **Interim GMs:** Baseball-Reference lists interim GMs as plain "General Manager", so eight interims had counted as heads. They're out, using the decision-maker list's interim flags plus four documented pre-2009 interims.
- **"Interim, then permanent" tenures:** Rizzo, Terry Ryan and Gillick had been dropped whole, which left Washington and Minnesota without a boss for several seasons. They now count from their start.
- **GMs before 2009:** they're filled in by person, so a GM working beside a president counts as a co-boss.
- **Corrected numbers:**
  - Cleveland 16 to 15; Hart's tree 43 to 40.
  - Heads who got the job at the only club they'd worked for: 15. The first version said 30, which is the number who had worked for only one club, before the interim fix.
  - Scouting director split into amateur (12) and pro (9).
- **Wording:**
  - "Trained" became "came through" and "worked under", because the data record shared employment.
  - "Heads" means the 38 people in a club's top baseball-operations job, a GM under a president included.

**Learned**
- **"Today's heads" needs a departure date.** Counting everyone who ran a club at any point in 2026 included four people who had already left (Forst, Brown, Perry Minasian and Fuld) and two interims.
- **Title matching needs care, in both directions.** A first Cypher prototype treated "Vice President of Baseball Operations" as running the club. The first Python version then counted Baseball-Reference's interim GMs as heads. Both are now tested.

## 2026-10-18 (later): Four pieces of everyday department work, a prediction log, and five commands
**Built**
- **Advance packet** (`baseball/advance/packet.py`, `bb advance TB 2026 --name Rays`): hitter cards for an opponent's lineup from Statcast. Swing decisions, whiff and damage by zone and pitch group, first-pitch and two-strike tendencies, bat tracking, platoon split and a plan line, every rate with its n and regressed to the league rate for the same zone or pitch group. Switch-hitters are drawn from the side they bat on most. Reports: the [analyst packet](reports/2026-advance-packet-tb.md), a [one-page coach version](reports/2026-advance-packet-tb-coach.md) and the [same page in Spanish](reports/2026-advance-packet-tb-coach-es.md).
- **Arbitration case** (`baseball/roster/arbitration.py`, `bb arb-case`): Cade Smith's first arbitration year, worked from the club side. A comp pool built by a stated rule (`POOL_RULE`, 23 fit rows after the comps were confirmed, exclusions listed with reasons in `SCREENED_OUT`), a comp line restated to 2027 dollars, the club's filing, the player's likely number, hearing odds at the midpoint, the walk point, the cost of losing, and a second-year exhibit. The brief cites the 2022-26 agreement's Article VI(E)(10) criteria, including what a panel can't hear. [Brief](reports/2027-arbitration-brief-smith.md).
- **Swing-decision study and hitter evaluation** (`baseball/evaluation/swing_decisions.py`, `bb swing-decisions`): decision value for every regular from 2024-26, tested for year-to-year repeatability (r 0.80) and for predicting next season, then a card and a price for Gleyber Torres. [Evaluation](reports/2026-hitter-evaluation-torres.md).
- **SQL module** (`sql/*.sql`, `baseball/sqlkit.py`, `bb sql list|show|run`): twelve named DuckDB queries over the pitch files, each with a header stating the question, inputs, output columns and definitions. [README](sql/README.md), with eight interview-style questions answered.
- **Prediction log** (`predictions/2027.yaml`, `baseball/predictions.py`, `bb predictions check|score|render`): fifteen calls for 2027 with probabilities, dated Oct. 18, 2026, scored with the Brier score after the season. [Log](reports/2027-prediction-log.md).
- **Tests:** new test files for all five, with the arithmetic in comments.

**Changed**
- **Torres:** the first draft priced him on FanGraphs' WAR tiers, which put a cliff at 2.0 WAR (1.98 WAR was worth $30.3M over two years; 2.00 would have been $39.6M). He is now priced at one rate per win. Adding baserunning (7th-percentile sprint speed in 2026) took the base case from 1.98 to 1.54 WAR. Later that evening Savant's own leaderboards loaded: −5 outs above average in each of 2024-26 (−3, −4 and −3 fielding runs), which replaced the secondary readings, including a 2026 "+3 runs" claim Statcast doesn't support. Field is now graded 40 from data; the base case is 1.50 WAR and $29.6M over two years, and the fielding range narrowed from $23.4-44.1M to $25.0-34.2M. The recommendation didn't change.
- **Arbitration:** the review pass rebuilt the comp pool from a rule instead of a hand list, added the second-year closers his side would cite, removed evidence a panel can't hear (Statcast, pre-arbitration bonus-pool pay), and retitled the brief as an independent exercise. The filing stayed at $4.8M; the walk point moved from $5.25M to $5.20M.
- **Advance packet:** the review pass fixed the changeup exception (it's left-handers' changeups away from right-handed hitters), replaced "avoid" lines the data didn't support with "nothing stands out", and corrected the Spanish.
- **Wording:** the Skubal summary no longer uses a "him, not the cameras" construction.

- **Arbitration comps confirmed (same evening):** the ten 2023-26 candidates and three older exclusions were checked against MLB Trade Rumors' service lists and Baseball-Reference salaries. Soto (2023), Alzolay (2024), Foley (2025) and Megill (2025) meet the pool rule and joined it; the rest were in a second arbitration year or still pre-arbitration. All four were paid less than the first 19 comps predicted, so the line fell from $4.82M to $4.58M, leave-one-out error rose from 8% to 16%, and the filing moved from $4.8M to $4.65M (settle $5.0-5.1M, club wins at the midpoint about 60%). Leaving unconfirmed candidates out had kept the line high.

**Learned**
- **Statcast's 2026 strike zone is the challenge-system zone.** From 2026, `sz_top` and `sz_bot` sit at 53.5% and 27% of the batter's height (MLB, Sept. 23, 2025), so 2026 zones don't compare with 2024-25 stance zones. A model that ignores this concludes the whole league got worse at swing decisions. The swing-decision study gives every batter one fixed zone in all three seasons.
- **Tiered prices manufacture precision.** A quarter of a run moved Torres's value by $9M on the tiers; one rate removes the cliff.

## 2026-10-18: Shape exposure study (pre-registered), one pick value, and consistency fixes
**Built**
- **`baseball/edge/shape_exposure.py`** (`bb shape-exposure`): does a hitter miss a pitch less when he has recently seen similar shapes from other pitchers?
  - The plan was committed before any fit; development results, then the 2026 results, were each committed before the next step.
  - The planned test replicated on 2026 and failed its lead placebo. Two exploratory follow-up designs, committed before they ran, separate recent exposure from season-level selection: [report](reports/2026-shape-exposure.md). A separate review pass then caught run-value numbers that no committed code produced; the run-value check, the translation and two-way errors are now in `fit_followup` and `translate`.
- **`baseball/evaluation/grades.py`** (`bb grade velo`, `bb grade ofp`): the velocity grades and OFP roll-up the Morejón report uses, now in the repo with tests, so its grades reproduce from here.
- **House pick value:** `acquisition.PICK_VALUE_OWN`, picks 45-60 from my 2000-2016 draft backtest less the 2026 slot. `qo_cost` uses it by default; Edwards (2019) stays available for comparison.

**Changed**
- **Bullpen memo:** the qualifying-offer walk-away is about $60M, not $66M, on the house pick value; the 2027 QO amount is $23.15M (reported Oct. 8). Marked as an update in the memo.
- **Morejón report:** the changeup grade's reason no longer docks the pitch for its usage against left-handers (that's a role question); FIP is shown both ways; the one-page PDF is rebuilt.
- **Wording:** "independently reviewed" became "a separate review pass", which is what the reviews were. The familiarity summary now says the 1.87 is against an earlier pitch of another type. The Atlas states that 147 of its 157 groups could be scored, and why its pitch count differs.

**Learned**
- **An exposure effect without a lead placebo overstates.** Here the raw estimate was about two and a half times the one that survived the placebo.

## 2026-10-15: Pro scouting report on Adrián Morejón, and the delivery module
**Built**
- **`baseball/evaluation/delivery.py`** (`bb delivery <season> <pitcher> [--figure PATH --title TEXT]`): the tracking evidence behind a report's delivery notes. It does seven things:
  - **Exact VAA** from Statcast's kinematics at the front of the plate.
  - **A pitch profile:** velocity band and top, shape, extension, release point, arm angle, release scatter, VAA overall and upper third, zone and low rates, whiffs.
  - **A slot check** against the primary pitch.
  - **Release and arm-angle offsets** against each game's own fastballs.
  - **League percentiles** for extension and arm angle (same hand), plus the median release scatter.
  - **Primary-pitch velocity** by pitch number within the outing.
  - **Usage by count state, and first-pitch strikes** against the league.
- **Report:** `reports/2026-morejon-pro-scouting-report.md`, a one-page PDF and its figure. It has 20-80 present and future grades, OFP, a B1 role, risk, delivery, makeup (observed / reported / unknown), a preference statement against Abreu, and the look to take before the bid. Independently reviewed twice (Oct. 14–15), with every finding addressed.
- **Tests:** 12 in the new `tests/test_delivery.py`.

**Answered**
- **Morejón grades out as an OFP 60 reliever.** Sinker, changeup and four-seamer are 70 / 70; the slider is 50 / 55; control is 60; command is NG.
  - **The roll-up:** 64 as a starter, graded down to the reliever. He doesn't throw the changeup to left-handers, his longest outing was 40 pitches, and he has an elbow history.
- **The 2026 changeup isn't new.** It matches the low-spin pitch Statcast labeled a knuckleball in 2024 (86.2 mph, 843 rpm, 51% whiffs on 35 swings). The bullpen memo's history line missed this.
- **The slider's decline goes with a shape change, not its release.**
  - **Shape:** 86.0 → 89.4 mph and −3.2 → −0.5 in IVB from 2024 to 2026.
  - **Release:** it separated from the fastballs as much in 2024, his best slider year (tell AUC 0.990, 0.991, 0.997).
- **Runners attempted 1.9 steals per nine innings against him**, against a league rate of 0.9. His FIP is 2.15, against a 2.83 ERA.

**Decided**
- **Fastball base grades** use the 2026-starter reading from `bb grade velo`, and every move off the base is stated.
- **Command is NG without a look.** Location data isn't intent.
- **Data-only reports name the look and when it happens.** Here that's before the money: the bid's deadline is the QO decision and the Dec. 1 expiration.

## 2026-10-14: Front-office ties and trade partners, across all 30 clubs
**Built**
- **`baseball/roster/front_office.py`** (`bb front-office [--no-pull] [--permute N]`). It does six things:
  - **Pulls the listings:** Baseball-Reference team pages, 1998–2026 (president, GM, farm and scouting directors). Pages are cached and merged into `data/raw/front_office/staff_panel.csv`.
  - **Builds the decision-maker panel** from researched, dated roles.
  - **Turns careers into seasons:** person-club-seasons, with business-side jobs dropped and consultants flagged.
  - **Scores three ties per pair-season:** former employer, former colleagues and protégé.
  - **Fits the models:** a Poisson model with pair and club-season fixed effects, standard errors clustered by pair (optionally with a stricter correction), and an event study.
  - **Tests and outputs:** a rotation permutation test, the Neo4j tables and the figure.
- **`baseball/roster/executive_careers.json`:** 115 decision-makers, 181 dated decision roles and 825 front-office stints. Each stint has a source URL; inferred years are flagged.
- **`baseball/roster/front_office.cypher`:** loads the executives into Neo4j:
  - `Executive` nodes
  - `WORKED_FOR` relationships (club, seasons, role)
  - `RAN` relationships (decision roles)
- **Report:** `reports/2026-front-office-ties.md` and its figure, put through three separate review passes (Oct. 13–14), with every finding addressed. The rivals report's front-office lines were updated to match.
- **Tests:** 14 in the new `tests/test_front_office.py`.

**Answered**
- **Front-office ties go with about 14–18% more trading within the same pair of clubs. Confirmed.**
  - **The estimate:** 1.18 (1.04–1.34), p = 0.009; permutation p = 0.015 (1,000 rotations).
  - **Robustness:** it holds without the Angels and Braves (1.16, p = 0.020), across pairs (1.15, p = 0.004), on stated-year stints only (p = 0.015) and under the earlier and an August dating rule (p = 0.023, 0.044).
- **The protégé tie (a decision-maker facing his old boss) is borderline.**
  - **The estimate:** 1.19, p = 0.054. The permutation test doesn't confirm it (p = 0.11).
  - **Variants:** stronger with Baseball-Reference's listings (p = 0.013) and on stated-year stints (p = 0.029).
  - **Without the Angels and Braves:** not significant (p = 0.15).
- **No detected rise before a protégé tie forms** (leads 0.80–1.08). The kinds of tie can't be separated in a joint model.
- **For scale:** division rivalry is −45%.

**Decided**
- **One season calendar:** October 1 starts the next season for trades and jobs alike.
  - **Hires:** in September or later count from the next season, since 2.5% of trades fall in September.
  - **Departures:** before April don't count that season.
  - **Offseason-only roles** count for no season.
- **Decision-makers** are researched, dated presidents of baseball operations and GMs. Baseball-Reference's listings are a sensitivity check, because they include business-side presidents and one owner.
- **Protégé** means worked below the president/GM level in a season the other ran that front office. A GM under his own president doesn't count, and neither do successors, consultants or the same person at both clubs.
- **Main test** is within-pair (pair and club-season fixed effects), backed by an event study and a rotation permutation test. Nested before/after windows were dropped.

**Learned**
- **Season alignment decides the answer.** Dating trades by calendar year scored a new decision-maker's first offseason deals with his old club as untied and hid the effect. The September-hire rule also moved results near 0.05, so three dating rules are reported (any tie 1.14–1.18, p = 0.009–0.044).
- **Baseball-Reference team pages** list several people per role with notes in nested parentheses, and some names differ (Dave/David Dombrowski, Doug/Douglas Melvin, Mike/Michael Hill). They match the researched decision-makers in 532 of 540 club-seasons.
- **Permutation runs** need single-threaded BLAS (`OMP_NUM_THREADS=1`). Two parallel jobs contending for threads ran several times slower.
- **Stricter small-sample correction:** for this design, (N−1)/(N−K) widens standard errors by about 7%. It moves former employer in the main data (0.042 to 0.057) and three variant any-tie results across 0.05, but not the main any-tie result (0.014).

## 2026-10-13: The MLB trade graph in Neo4j, and the report on who trades with whom
**Built**
- **Neo4j:** Neo4j Desktop with a local `baseball` instance (Neo4j 2026.09.0, APOC and Graph Data Science). Its import folder (`server.directories.import` in neo4j.conf) is `~/Baseball/data/graph`.
- **`baseball/roster/trades.py`** (`bb trades [--no-pull] [--refresh] [--report]`): pulls every MLB trade from the MLB Stats API (the feed starts in 2009), Baseball-Reference WAR and, once, Retrosheet's transaction file. It writes the graph tables to `data/graph/`.
  - **Size:** 3,290 trades, 6,163 player moves, 4,110 players, 6,597 club sides, 1,369 trade-tree links.
  - **Value rule:** the WAR the acquiring club got from the player, from the trade through his continuous tenure there.
  - **Tree value:** follows every flip of an acquired player. Each flip's return is shared by the number of players sent in it.
  - **Pair analysis:**
    - observed vs expected counts for all 435 pairs (configuration model, exact Poisson intervals, Benjamini-Hochberg q)
    - a Poisson model with club effects and quasi-Poisson errors (`rivalry_model`)
    - windows, eras and subsets (`breakdown`)
    - pair periods (`pair_by_period`)
    - a sliding-window burst scan (`burst_scan`)
    - a random-trade baseline for WAR gaps (`side_gap_baseline`)
    - the Retrosheet cross-check (`retrosheet_check`)
- **`baseball/roster/trade_graph.cypher`:** loads `data/graph/` into Neo4j and is rerunnable.
  - Nodes: `Team`, `Player`, `Trade`.
  - Relationships: `MADE`, `MOVED`, `LED_TO`, `TRADED_WITH`.
- **`baseball/roster/trade_patches.json`:** documented repairs for trades the MLB feed records incompletely.
- **Report:** `reports/2026-trade-network-rivals.md` and its figure, put through two separate review passes on 2026-10-13, with every finding addressed.
- **Monthly update:** `bb trades` added to `scripts/automation/update.sh`.
- **Tests:** 12 new in `tests/test_trades.py`.

**Answered**
- **Division rivals trade with each other at 0.56 times the rate of other pairs.**
  - **The model:** club effects, quasi-Poisson, 95% interval 0.49–0.65, p < 1e-10.
  - **Raw counts:** 270 rival trades against 454.7 expected.
  - **Breadth:** every division on its own, and 52 of 60 rival pairs below expectation, plus one tie.
  - **It's the division, not the league:** same-league pairs are no different from interleague pairs (1.03, p = 0.53).
  - **Never traded since 2009:** Dodgers-Giants, Guardians-Royals and Cubs-Cardinals. Retrosheet agrees through Dec. 2021.
- **The deadline is the one window where rivals come closer to normal.** 0.73 vs 0.49 in the offseason (p = 0.010). The offseason and the rest of the season can't be told apart.
- **Rival trades are no more lopsided than other trades.** The median realized-WAR gap is 0.28 for both (p = 0.79).
- **Angels-Braves is the strongest burst of any pair in a scan of 435 pairs x 48 windows.**
  - **The share:** Angels trades made with Atlanta rose from 7.2% to 22.0% (13 of 59) during Perry Minasian's tenure (Nov. 12, 2020 - June 26, 2026). Minasian had been Anthopoulos's assistant GM in Atlanta.
  - **Not unique:** Dodgers-Phillies (2011-16) and Rangers-White Sox (2015-21) had bursts of similar size with no tie offered.
  - **The WAR gap is ordinary:** in those 13 trades the Braves got 8.8 WAR and the Angels -2.4, almost all of it Iglesias. A gap that size turns up in 14% of random 13-trade sets.

**Decided**
- **Tracked files:** the graph tables live in `data/graph/` and are never committed. Neo4j reads them there.
- **Coverage:** starts in 2009 because the MLB feed does. Retrosheet (deals through Dec. 2021, no longer maintained) is the route to earlier seasons.
- **Headline estimate:** the club-effects model's rival contrast. The raw observed-to-expected ratio pushes non-rival pairs slightly above 1.0 because each club's total is fixed.

**Learned**
- **Feed quality:** the MLB feed leaves a club blank on some 2019-23 trade records and files 15 moves twice.
  - **Duplicates:** the fuller record is kept.
  - **Blanks:** filled from the player's last Baseball-Reference stint.
  - **Missing players:** the Lindor trade's missing players are patched by hand, documented.
- **Early coverage:** 2009-11 records far fewer minor-league deals than later seasons (1.15-1.34 feed trades per Retrosheet trade, vs 1.46-1.78).
- **Exact intervals:** `poisson.interval` gives a distribution's quantiles, not a confidence interval for a rate. Use exact (Garwood) intervals.
- **Overdispersion:** pair counts vary about 21% more than Poisson. State the dispersion and scale errors by it.
- **Post hoc splits:** a split chosen after a scan finds a pair needs a scan-wide comparison, not a Bonferroni bar.
- **Team codes:** Baseball-Reference uses OAK through 2024, ATH from 2025, and FLA through 2011.

## 2026-10-13 (late morning): Published for viewing
**Decided**
- The repository goes public so clubs can read it, as **IForSureI/Dylan-Fanelli-Baseball-Analytics-Portfolio**: a fresh repository holding only the cleaned history (the original repository is kept private as an archive). All rights reserved: `LICENSE` permits viewing only; copying, modifying or reusing the code, reports or figures needs written permission.
- `CITATION.cff` puts a "Cite this repository" button on the page. Every report and the README end with a copyright line.
- `main` is protected by a ruleset: no force-pushes, no deletion.

## 2026-10-13 (morning): A claims audit of the summaries
**Checked**
- Every summary number in the README, the portfolio page and this log was re-read against its full report. Four summaries said more than their reports do, and were tightened:
  - Fairbanks: "not a 2027 option" (the memo assumes about a third of 2027), not "out for 2027."
  - Bat speed: r = 0.5 after about 3 swings and r = 0.7 after about 6. "Reliable" at r = 0.5 overstated it.
  - wOBA's r = 0.5 at about 500 PA is an extrapolation past the largest measured sample (256 PA).
  - The expected-whiff vs. lever comparison holds pooled across pitch types, given the realized shape, against the full lever model. By type only sinkers separate.

**Answered**
- **Skubal's slider in 2026:** 28.8% whiffs on 146 swings (42 whiffs), between 2024 (34.4%) and 2025 (25.5%) and not distinguishable from either (p = 0.52 vs. 2025, p = 0.27 vs. 2024; two-proportion tests, regular season, `data/seq`). Over 2025-26: 27.0% on 307 swings, below the league's 33% for sliders. The 2025 drop is neither confirmed nor reversed.

**Learned**
- **Summaries drift stronger than reports.** A one-line answer drops the qualifier ("extrapolated," "pooled," "borderline"). Check every summary against its report, not only the report against its data.

## 2026-10-13: The capstone. A bullpen acquisition memo for the Rangers (closes #13 and #8)
**Built**
- **`baseball/evaluation/reliever.py`** (`bb compare-relievers <season> <id> ...`): one comparison table for any list of pitchers. It covers:
  - regressed whiff, chase, CSW, zone, xwOBA on contact, hard-hit, ground-ball and run value
  - stuff vs results by season, and the engine's 2027 whiff projection
  - primary-fastball velocity against the league's change, and early vs late season against league relievers
  - workload: back-to-backs, multi-inning outings, velocity on no rest, a leverage proxy
  - platoon and usage by hand
  - familiarity exposure, priced
  - 2025 → 2026 lever changes with the study's evidence and year-two labels
  - xwOBA difference tests (`xwoba_diff_test`)
  - 20-80 grades per pitch (present, 2027, stuff), a control grade (unintentional walks, a stand-in for command) and a reliever OFP
  - intentional walks and pitch-clock calls count as plate appearances, not pitches
- **The 20-80 mapping** (`grade_from_percentile`): 50 + 10z of the percentile among MLB pitches of the type, documented and tested.
- **`baseball/roster/acquisition.py`:** reliever pricing.
  - **Projection:** relief run value weighted 5/4/3 and regressed, with replacement from fringe arms.
  - **The 2025-26 reliever market line:** fit on 21 signings, with the comps and candidates projected the same way, a 95% prediction interval and the odds that a walk-away lands the player.
  - **Contracts:** value at the market line (the engine's $/WAR is shown on a different, uncalibrated scale), partial-season availability, break-even AAV, qualifying-offer cost and a tax table.
- **`baseball/roster/bullpen_case.py`** (`bb bullpen-case`): the memo's numbers and figure.
- **Report:** `reports/2026-bullpen-acquisition-memo.md`, put through a separate review pass on 2026-10-13 and revised.
- **Tests:** 228 (up from 187).

**Answered**
- **Rangers need:** late-inning run prevention.
  - **The fall:** the bullpen went from 4th in run value per 100 pitches (2025) to 24th (2026), and from 6th to 26th in late, close spots.
  - **The departures:** Junis (mutual option) and Alexander (free agent) threw 27% of the late, close PAs; with Martin and Beeks, 35%.
  - **Not a platoon need:** the xwOBA gap against right-handers (.318 vs .306) is not significant (p = 0.25).
- **Recommendation:** bid on Adrián Morejón to his value.
  - **Morejón:** four years, open at $60M, walk away above $72M (about $66M with a qualifying offer). Expect to land him about half the time; his expected price is $18.4M a year, with a 95% band of $7.4–29.3M, extrapolated past every comp.
  - **Abreu:** the plan above that (two years, walk away above $25M).
  - **Fairbanks:** not a 2027 option after thoracic outlet surgery (MLB.com, Sept. 19, 2026).
- **Projected 2027 wins in the role each would fill** (rate-only intervals, which understate): Morejón 2.3 (B1), Abreu 1.5 (B2; 1.6 as B1), Fairbanks 0.24 (a third of a season).
- **Where the tools disagree:**
  - The engine's whiff projection ranks Abreu first (walks are invisible to it).
  - The engine's $/WAR is on a different win scale than the memo's projection, so only the market line prices.
  - The levers study likes Fairbanks's slider changes; the physics model doesn't.

**Learned**
- **The reliever market prices loosely on run value.** The 2025-26 line has R² 0.27 and a residual SD of $4.2M, so treat a reliever's "market price" as a band.
- **The engine's $/WAR tiers aren't built for relievers** (FanGraphs' study excludes them), and a run-value win scale with a fringe-arm replacement level isn't fWAR. Price relievers on their own market line, with the comps and the player projected the same way.
- **A walk-away at value is a coin flip on landing the player.** Say so, and price each step above it.
- **Statcast intentional walks are "automatic_ball" rows with no pitch.** Dropping no-pitch rows silently loses every intentional walk (545 in 2026). Count them as plate appearances, not pitches.
- **Health facts change a case.** Fairbanks's surgery (announced Sept. 19) wasn't in the first draft. Check public IL and surgery history for every candidate, with one rule for all.
- **A source error:** Friars on Base (Sept. 9) lists Robert Suarez's Braves deal as four years and $60M, against three and $45M in the NBC/Yahoo tracker and amNY (Dec. 11, 2025). The tracker is used.

## 2026-10-13 (overnight): Four studies, reviewed: reliability, the hook, pitch-design levers, the roster engine
Each study was built and integrated, then put through a separate review pass against its own outputs, fixed and re-checked.

**Built**
- **Reliability Atlas** (`baseball/evaluation/reliability.py`, `bb reliability`, `bb regress`):
  - 29 metrics in 157 groups (hitters including bat tracking and swing path; pitchers overall and by pitch type)
  - split-half by game; year-to-year rho; in-season drift with intervals
  - a two-level noise model for pitch physics (day and pitch)
  - `regress()` with intervals for this season, the rest of it, and next season; constants ship in `reliability_params.json`
- **The exposure-aware hook** (`baseball/edge/hook.py`, `bb hook`, `bb hook-card`): a per-hitter exposure index from the familiarity costs, 2026 calibration out of sample, the starter-removal model, and a hook card against a reliever baseline.
- **Pitch-design levers and development plans** (`baseball/development/levers.py`, `idp.py`, `bb levers`, `bb idp`):
  - **Levers:** league-net shape changes, noise thresholds, payoff per unit with regression to the mean handled, matching, placebo, persistence and validation.
  - **Development plans:** written as YAML, with a progress engine that issues verdicts (including "inconclusive") and checks power when the plan is written.
- **Roster and CBA engine** (`baseball/roster/`, `bb cbt`, `bb cbt-check`, `bb service`, `bb roster-cases`; closes #12):
  - service time, Super Two, options, Rule 5, outright and 10-and-5 rights
  - a luxury-tax engine validated on the real 2025 bills
  - arbitration paths, surplus value, extension bands with labor-rule and injury scenarios, qualifying offers
  - the Paul Skenes extension memo
- **Data:** wider sequence copy (base/out state, score, launch angle, spray, woba values, swing path); `bb people` (Chadwick register names).
- **Tests:** 187 (up from 66).

**Answered**
- **Regressing beats raw numbers out of sample.**
  - **2026 halves:** 135 of 147 metrics better, median error cut 27%.
  - **2025 → 2026:** 91 of 96 better.
  - **Clean replication** (fit 2024, test 2025): 140 of 145 better.
  - **Speed of stabilizing:** bat speed reaches r = 0.5 after about 3 competitive swings and r = 0.7 after about 6; wOBA's fitted curve reaches r = 0.5 at about 500 PA, an extrapolation past the largest measured sample (256 PA).
- **The familiarity cost doesn't carry to plate-appearance runs.** The 2026 calibration slope is −0.28 (SE 0.37). Managers show no response to it (MDE about 0.75 points). Keep exposure for pitch selection, not the hook.
- **Pitch design:**
  - **Four-seam ride:** +1.62 whiff points per 2 in, the best-supported lever.
  - **Velocity:** pays in the data but fails the placebo (recovery not ruled out).
  - **Slider levers:** pay but aren't shown to last.
  - **Expected whiff:** the single change in expected whiff predicts better than any lever list.
- **Skenes:** open at about $200M present value and walk away above about $215M, given illustrative odds of a major arm injury and of MLB's cap plan passing. His Rookie of the Year credit cost Pittsburgh a year of control.

**Decided**
- **Physics metrics are regressed by games, not pitches.**
- **Exposure stays out of the hook.**

**Learned**
- **Independent review earned its keep on every study.**
  - **Roster:** a ceiling defined one way and computed another changed the Skenes recommendation.
  - **Reliability:** a noise model held for outcomes but broke for pitch physics.
  - **Hook:** outcome noise was described as attenuation.
  - **Levers:** a lever that fails its placebo was ranked first.
- **A significant per-pitch effect isn't a plate-appearance forecast.** For small signals, use calibration slopes.
- **"No sign" needs an interval narrower than the effects you care about.** Otherwise say "not detected", with the bound.

## 2026-10-12 (overnight): Does a pitch wear out? Pitch-type familiarity
**Built**
- **Sequence copy of the league data** (`bb seq`, `data/seq/`, about 3 MB parts): regular season with batter ids, plate location, run value and bat tracking. The slim engine copy has no batter ids.
- **`baseball/edge/familiarity.py`** (`bb familiarity 2026`):
  - per-pitch exposure counts: same type vs. other types; earlier PAs, this PA and earlier games; and from other pitchers
  - the same-minus-other contrast, with two-way fixed effects and pitcher-clustered SEs
  - placebo, robustness, dose-response, per pitch type, carryover between pitchers, TTO decomposition, a trait screen with BH correction, persistence, and a usage break-even formula
  - the exposure ledger for a start
  - page and figure builders
- **`baseball.stats.absorb()`** for multi-way fixed effects. `clustered_wls` is now a one-pass sum, fast on a million rows.
- **The Familiarity page** (`bb familiarity` writes it to `data/edge/familiarity/`).
- **Report:** `reports/2026-league-pitch-familiarity.md`.
- **Monthly update:** now writes the sequence copy and reruns the study.
- **Tests:** 65 (up from 55).

**Answered (two separate review passes)**
- **A pitch type loses whiffs the more of it a hitter has seen from the pitcher.** Per earlier same-type pitch in earlier PAs today, relative to another type: −0.70 (fastballs), −0.91 (breaking balls), −1.87 (changeups/splitters) whiff points per swing, all p < 0.001 and in every season. After 4+ changeups/splitters: −8.2 points.
- **It carries across games and across pitchers.**
  - After 1–3 of this pitcher's changeups in earlier games this season: −3.5 points.
  - Same-hand changeup carryover from another pitcher today: −0.79 per earlier changeup.
- **Familiarity shows up as contact, not discipline.** Chase rises on familiar fastballs and breaking balls.
- **Changeup exposure accounts for part of the third-time-through decline on changeups/splitters:** −3.5 gross, −2.3 net, against −4.6 total.
- **Usage break-even with all three windows priced:** about −0.18 to +0.43 runs per 100 pitches for starters, about 0 for relievers. Repetition alone is a weak reason to hold back a better pitch.

**Learned**
- **Placebo before claims.** Pitchers throw more of what's working (future-exposure coefficient +2 to +3 points). A like-for-like comparison showed the placebo-adjusted numbers moved because of the smaller sample, not the control.
- **A null persistence test can be a power problem.** Each pitch-season slope carries 3–4 points of noise, so per-pitch wear-out can't be graded from a season of data. Say "can't measure", not "doesn't exist".
- **Compare like with like.** In carryover tables, say what the reference group is. A coefficient relative to another pitch isn't an absolute effect.
- **Keep reviewed snapshots separate from automated output.** Monthly runs write their figure to `data/`, so they never touch a reviewed report.
- **Moving data:** staging two ~3 MB parts per call works; parallel staging calls fail.

## 2026-10-12 (late): Tracking data pipeline (public loader, private repo)
**Built**
- `baseball/ingest/tracking.py`: the TrackMan / Rapsodo / Savant loader, with tests. It tests the horizontal sign on the data itself and flags QC problems.
- Portable stuff model (`bb stuff-model`). It uses only features TrackMan and Rapsodo also measure, so there's no arm angle. Cross-fitted AUC is 0.630, against 0.633 for the full model, so device data gets essentially the same model. It's saved with MLB percentile references by pitch type.
- Release tells now take any feature set and session column, so they work on pen and game files.
- Private repo `bbp` commands: `ingest` (inbox, QC, deduplicated store), `report` (shape per device, MLB-equivalent expected whiff% with percentile, game results, release consistency, velocity by session), and `demo` on fictional files.
- The monthly update now pulls the private repo, processes its inbox, and commits and pushes.

**Decided**
- The loader code is public. Team files, stores and reports stay private.
- Pen files never produce whiff%, CSW% or chase%.

## 2026-10-12 (night): The edge engine, automation, the Edge Board
**Built**
- League-wide data for 2024, 2025 and 2026 (2.14 million regular-season pitches): `bb pull-league`, slim copies, `bb slim`.
- The edge engine (`bb edge`):
  - **Release tells:** release-only AUC per pitch, with release measured relative to that game's fastballs.
  - **Hidden changes:** dated in-season changes, with checks for whether a change is isolated to one pitch or is a relabel, judged on expected whiffs at a fixed batter-hand mix.
  - **Stuff model:** expected whiffs, cross-fitted by pitcher, with persistent gaps and a validated 2027 projection.
  - **League baselines.**
- The Edge Board (`bb board`): an interactive page with the findings, five lists, and a lookup for any 2026 pitcher.
- **Automation:** a monthly LaunchAgent (1st of the month, 6 AM) that updates the code, pulls new pitches, runs the engine and rebuilds the board.
- **Private repo** IForSureI/Baseball-private (~/Baseball-private) with inbox folders for team data and scouting notes.
- 44 tests.

**Answered**
- **Skubal 2024 → 2025: it was him, not the cameras.** The league didn't move (median spin change +21 rpm on four-seamers, extension about 0). Skubal sat at the 80th–98th percentile on velocity, spin, extension and arm angle. He raised his arm slot on everything except the changeup, which is why his changeup's release tell jumped (0.81 → 0.95).

**Findings (after a separate review pass)**
- **Results beyond stuff persist.** The gap between actual and expected whiffs carries over year to year: r = 0.56 and 0.53. With location, count, role and pitch type removed, it's still about 0.45.
- **No sign that release tells cost whiffs.** Pooled 2024–26 with SEs clustered by pitcher: +0.44 per 0.1 AUC (CI +0.08 to +0.80). That falls to about +0.2, not significant, once usage is controlled. Changeups show nothing either way.
- **Projection.** Two seasons of results plus expected whiffs cut next-year error about 8% out of sample against a regressed last-season baseline. Most of that comes from the second season; physics adds about 2.5%.

**Learned**
- **Pooling seasons.** You can't pool seasons as independent samples, because the same pitchers recur. Cluster by pitcher.
- **The right baseline.** A forecast comparison against raw last season flatters any regressed model. Compare against a regressed baseline, out of sample.
- **Batter-hand mix.** An expected-whiff change can come from who the pitch is thrown to (the model knows batter hand). Hold the mix fixed.
- **Duplicate changes.** One real change trips several metrics a few days apart. Show one row per pitch.
- **What Hawk-Eye can see.** It can tell most secondaries from the fastball by release (median AUC 0.90). A high tell score alone means nothing.

## 2026-10-12 (evening): Skubal 2024 vs 2025, issue #2
**Built**
- `bb compare <last> <first> <season_a> <season_b>`: one pitcher's arsenal in two samples side by side. It shows shape changes, whiff% with 95% intervals, and a verdict on each change (real change, noise, or small sample).
- `baseball/stats.py`: Wilson intervals and a two-proportion test, kept in one shared place for every tool.
- `arsenal_counts()`: the arsenal with the swing and whiff counts kept, so other tools can build intervals and tests on it.
- 19 tests (up from 12).

**Answered**
- Skubal's changeup whiff rate is his real level: 46.4% in 2024 and 46.8% in 2025, or 46.6% on 997 swings across both (95% interval 43.6–49.7%).

**Decided**
- Every finished report gets a separate review pass before it's final.
- A change counts as confirmed at p < 0.05 with at least 30 swings in each sample. Anything near 0.05 is called borderline, because many tests run at once.

**Learned**
- A separate review pass caught three wrong claims and several sentences that went stale once the 2024 data arrived. Examples: "a full mph harder from the first month" was really +0.7 for the season, and "fewest misses" was wrong because the sinker has fewer.
  - Lesson: when new data comes in, re-check every earlier claim, not just the new section.
- Use one evidence standard throughout. I had called a non-significant rise in four-seamer damage noise, then presented an equally non-significant changeup improvement as a gain.
- Velocity, spin, extension and arm angle all rose on every pitch in 2025. The same rise on every pitch in one year can be a change in how Statcast measured him, so season-to-season comparisons need league-wide changes as a baseline (issue #3).
- Statcast's "splitters" from Skubal (3 per season) spin at 882–995 rpm, about half his changeup. They're either mislabels or a rare separate grip, so don't assume either.

## 2026-10-12: Foundation and first real analysis
**Built**
- Set up the tools on the Mac: Homebrew, uv, DuckDB, Git, GitHub CLI, R, Positron, RStudio, Tableau Public, DBeaver Community, DB Browser for SQLite, plus the VS Code extensions.
- Organized the repo by front-office job: `ingest/`, `evaluation/`, `development/`, `roster/`, `business/`.
- Added the DuckDB warehouse. Loads skip pitches already stored, add any new Statcast columns automatically, and log every load in `pulls`.
- Added the `bb` command line (`pull`, `arsenal`, `db`).
- Arsenal tables now run in both pandas and SQL, plus outcome metrics (zone%, chase%, xwOBA on contact, hard-hit%, runs saved per 100) and usage by batter handedness.
- Added the shared chart style with fixed pitch colors (checked for colorblind separation).
- Wrote the first report: `reports/2025-skubal-arsenal.md`.
- 12 tests.

**Decided**
- This repo is the long-term operations workspace and will eventually go public as a portfolio. Team data stays out of it.
- Analyses use the regular season by default.

**Learned**
- A Statcast pull from March 1 includes spring training: 252 of Skubal's 3,404 pitches, 84 of them with no pitch type recorded. Filter by `game_type` before any season analysis.
- Pandas rounds a trailing 5 to the even digit (33.25 → 33.2) while DuckDB rounds it up (33.3). Compare the two with a tolerance, not exact equality.
- Statcast's `delta_run_exp` is from the offense's point of view, so a pitcher's runs saved is its negative.
- Skubal's changeup gets whiffs on 46.8% of swings (95% interval 42.7–51.1%) against about 31% for changeups overall. The postseason rate of 70.5% came on only 44 swings.
- 2026-11-09: Postseason page: player headshots on the three player scatters (linked from MLB's image server, with MLB's generic silhouette when a player has none), shown only where the faces fit without pushing players off their spots; on a phone the club-colour dots stay.
