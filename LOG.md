# Log

Newest first. One entry per working session: what was built, what was decided, what was learned.

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
- **Report:** `reports/2026-bullpen-acquisition-memo.md`, independently reviewed 2026-10-13 and revised.
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
Each study was built and integrated, then independently reviewed against its own outputs, fixed and re-checked.

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

**Answered (independently reviewed twice)**
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
- Portable stuff model (`bb stuff-model`). It uses only features TrackMan and Rapsodo also measure, so there's no arm angle. Cross-fitted AUC is 0.631, against 0.633 for the full model, so device data gets essentially the same model. It's saved with MLB percentile references by pitch type.
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

**Findings (after an independent review)**
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
- Every finished report gets an independent review before it's final.
- A change counts as confirmed at p < 0.05 with at least 30 swings in each sample. Anything near 0.05 is called borderline, because many tests run at once.

**Learned**
- An independent review of the report caught three wrong claims and several sentences that went stale once the 2024 data arrived. Examples: "a full mph harder from the first month" was really +0.7 for the season, and "fewest misses" was wrong because the sinker has fewer.
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
