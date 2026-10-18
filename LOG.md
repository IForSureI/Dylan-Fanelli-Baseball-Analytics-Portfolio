# Log

Newest first. One entry per working session: what was built, what was decided, what was learned.

## 2026-10-18 (later): Four pieces of everyday department work, a prediction log, and five commands
**Built**
- **Advance packet** (`baseball/advance/packet.py`, `bb advance TB 2026 --name Rays`): hitter cards for an opponent's lineup from Statcast. Swing decisions, whiff and damage by zone and pitch group, first-pitch and two-strike tendencies, bat tracking, platoon split and a plan line, every rate with its n and regressed to the league rate for the same zone or pitch group. Switch-hitters are drawn from the side they bat on most. Reports: the [analyst packet](reports/2026-advance-packet-tb.md), a [one-page coach version](reports/2026-advance-packet-tb-coach.md) and the [same page in Spanish](reports/2026-advance-packet-tb-coach-es.md).
- **Arbitration case** (`baseball/roster/arbitration.py`, `bb arb-case`): Cade Smith's first arbitration year, worked from the club side. A comp pool built by a stated rule (`POOL_RULE`, 19 fit rows, exclusions listed with reasons in `SCREENED_OUT`), a comp line restated to 2027 dollars, the club's filing, the player's likely number, hearing odds at the midpoint, the walk point, the cost of losing, and a second-year exhibit. The brief cites the 2022-26 agreement's Article VI(E)(10) criteria, including what a panel can't hear. [Brief](reports/2027-arbitration-brief-smith.md).
- **Swing-decision study and hitter evaluation** (`baseball/evaluation/swing_decisions.py`, `bb swing-decisions`): decision value for every regular from 2024-26, tested for year-to-year repeatability (r 0.80) and for predicting next season, then a card and a price for Gleyber Torres. [Evaluation](reports/2026-hitter-evaluation-torres.md).
- **SQL module** (`sql/*.sql`, `baseball/sqlkit.py`, `bb sql list|show|run`): twelve named DuckDB queries over the pitch files, each with a header stating the question, inputs, output columns and definitions. [README](sql/README.md), with eight interview-style questions answered.
- **Prediction log** (`predictions/2027.yaml`, `baseball/predictions.py`, `bb predictions check|score|render`): fifteen calls for 2027 with probabilities, dated Oct. 18, 2026, scored with the Brier score after the season. [Log](reports/2027-prediction-log.md).
- **Tests:** new test files for all five, with the arithmetic in comments.

**Changed**
- **Torres:** the first draft priced him on FanGraphs' WAR tiers, which put a cliff at 2.0 WAR (1.98 WAR was worth $30.3M over two years; 2.00 would have been $39.6M). He is now priced at one rate per win. Adding baserunning (8th-percentile sprint speed) took the base case from 1.98 to 1.54 WAR.
- **Arbitration:** the review pass rebuilt the comp pool from a rule instead of a hand list, added the second-year closers his side would cite, removed evidence a panel can't hear (Statcast, pre-arbitration bonus-pool pay), and retitled the brief as an independent exercise. The filing stayed at $4.8M; the walk point moved from $5.25M to $5.20M.
- **Advance packet:** the review pass fixed the changeup exception (it's left-handers' changeups away from right-handed hitters), replaced "avoid" lines the data didn't support with "nothing stands out", and corrected the Spanish.
- **Wording:** the Skubal summary no longer uses a "him, not the cameras" construction.

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
