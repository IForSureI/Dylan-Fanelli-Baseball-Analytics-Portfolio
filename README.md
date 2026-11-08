<p align="center"><img src="assets/banner.jpg" alt="Baseball Analytics by Dylan Fanelli" width="100%"></p>

<p align="center"><a href="https://github.com/IForSureI/Dylan-Fanelli-Baseball-Analytics-Portfolio/actions/workflows/tests.yml"><img src="https://github.com/IForSureI/Dylan-Fanelli-Baseball-Analytics-Portfolio/actions/workflows/tests.yml/badge.svg" alt="tests"></a> <img src="https://img.shields.io/badge/python-3.11%2B-1f1f1f" alt="python: 3.11+"> <img src="https://img.shields.io/badge/data-2.14M%20pitches,%202024--2026-1f1f1f" alt="data: 2.14M pitches, 2024-2026"> <img src="https://img.shields.io/badge/tools-Python,%20SQL,%20Neo4j,%20R-b4532a" alt="tools: Python, SQL, Neo4j, R"> <img src="https://img.shields.io/badge/license-all%20rights%20reserved-6b6b6b" alt="license: all rights reserved"></p>

<p align="center"><b><a href="#start-here">Start here</a> &nbsp;|&nbsp; <a href="#the-research">The research</a> &nbsp;|&nbsp; <a href="#what-a-club-gets">What a club gets</a> &nbsp;|&nbsp; <a href="#how-the-work-is-held-up">How the work is held up</a> &nbsp;|&nbsp; <a href="#the-toolkit-bb">Toolkit</a> &nbsp;|&nbsp; <a href="docs/glossary.md">Glossary</a> &nbsp;|&nbsp; <a href="#about">About</a></b></p>

# Dylan Fanelli Baseball Analytics Portfolio

My baseball-operations research and tools, built on every public pitch of 2024–2026 (2.14 million regular-season pitches) and every MLB trade since 2009. Each piece:
- **Answers a question a club would want to know.**
- **Is validated out of sample.**
- **Gets a separate review pass** that checks every number against its saved outputs before it's final.
- **Ships as code a club can run.** Nulls are reported as nulls.

<p align="center"><img src="assets/at-a-glance.png" alt="Selected studies at a glance" width="100%"></p>

## Start here
1. **[Bullpen acquisition memo, 2026-27](reports/2026-bullpen-acquisition-memo.md)** and its **[one-page version](reports/2026-bullpen-one-page.md)** for a GM. The capstone: one real offseason decision made the way a front office makes it, using every tool below.
2. **[Do hitters adapt to shapes they've seen from other pitchers?](reports/2026-shape-exposure.md)** A pre-registered study whose planned test failed its own placebo, and what an exploratory follow-up found.
3. **[Does a pitch wear out?](reports/2026-league-pitch-familiarity.md)** An original question with a clear answer, and a [follow-up](reports/2026-exposure-aware-hook.md) that tested whether it should change the hook. It shouldn't.
4. **[The Reliability Atlas](reports/2026-reliability-atlas.md).** Which numbers to trust, after how many pitches, swings or batted balls, and how far to regress them.
5. **The everyday work of a department:** an [advance packet](reports/2026-advance-packet-tb.md) with a [coach page](reports/2026-advance-packet-tb-coach.md) in English and [Spanish](reports/2026-advance-packet-tb-coach-es.md), two arbitration cases ([Cade Smith](reports/2027-arbitration-brief-smith.md) and [Louis Varland](reports/2027-arbitration-brief-varland.md)), a [hitter evaluation](reports/2026-hitter-evaluation-torres.md), a [SQL module](sql/README.md), and a [dated prediction log](reports/2027-prediction-log.md) scored after 2027.

<p><img src="assets/img/strip-field_dusk.jpg" width="100%" alt="Late nights at the ballpark, Harry & David Field"></p>
<p align="center"><sub>Late nights at the ballpark. Harry & David Field, Medford, Oregon.</sub></p>

## The research

| Question | Answer | Report |
|---|---|---|
| Which reliever should the Rangers sign this winter, and at what price? | Adrián Morejón. Open at 4 years, $60M; walk away above $72M, which lands him about half the time. Bryan Abreu is the plan above that. Pete Fairbanks isn't a 2027 option after thoracic outlet surgery. | [Memo](reports/2026-bullpen-acquisition-memo.md) |
| Does a pitch lose effectiveness on a hitter the more of it he has seen? | Yes, and it's specific to the pitch type. An earlier changeup or splitter in his earlier plate appearances today, in place of a pitch of another type, goes with 1.87 fewer whiff points on the next one. The effect carries across games and partly to the next same-handed pitcher. | [Report](reports/2026-league-pitch-familiarity.md) |
| Do hitters adapt to pitch shapes they've seen from *other* pitchers? | The planned test can't say: in a pre-registered test with 2026 held out, the raw association (−0.74 whiff points per SD) replicated, then failed its own lead placebo, which points to selection on who plays against what. An exploratory follow-up that holds a hitter's season-long diet fixed finds a small recent effect, −0.27 (−0.48 to −0.06): at most about 2 runs a club-season. | [Report](reports/2026-shape-exposure.md) |
| Should that change when the starter comes out? | No. The per-pitch cost replicates out of sample, but it doesn't reach plate-appearance run value (2026 calibration slope −0.28, SE 0.37). Managers show no response to it either. | [Report](reports/2026-exposure-aware-hook.md) |
| Which numbers can you trust, and when? | Regressing beats raw numbers out of sample for 135 of 147 scored metric groups, confirmed on a clean 2024 → 2025 replication. That shrinkage helps is expected; the useful output is how far to regress each number, and after how many pitches, swings or batted balls. Bat speed is half signal after about 3 swings and reaches r = 0.7 after about 6; wOBA's fitted curve doesn't reach r = 0.5 until about 500 plate appearances (an extrapolation). Pitch physics regress by games, not pitches. | [Atlas](reports/2026-reliability-atlas.md) |
| Which pitch-design changes stick and pay? | Four-seam ride is the best-supported lever (+1.62 whiff points per 2 in). Velocity's payoff fails a placebo, so recovery isn't ruled out. Given the shape change, the single change in expected whiff predicts next season's whiff change better than the full lever model, pooled across pitch types. | [Report](reports/2026-pitch-design-levers.md) |
| Should the Pirates extend Paul Skenes before the CBA expires on Dec. 1? | Open at about $200M in present value and walk away above about $215M. The answer depends on the next agreement, and the memo prices both rule sets. The tax engine reproduces the 2025 luxury-tax bills within $1 for eight of nine clubs. | [Memo](reports/2026-roster-cba-engine.md) |
| Who trades with whom? | Division rivals trade at 0.56 times the rate of other pairs (0.49–0.65), and 52 of 60 rival pairs fall below expectation. The deadline is the one window where they come closer to normal. Dodgers–Giants, Guardians–Royals and Cubs–Cardinals haven't traded since 2009. | [Report](reports/2026-trade-network-rivals.md) |
| Do front-office ties predict trade partners? | Yes, modestly. A pair of clubs trades about 14–18% more in seasons when their decision-makers share front-office history (1.18, 1.04–1.34, p = 0.009; permutation p = 0.015), and it holds without the Angels and Braves. The narrower protégé-meets-old-boss tie is borderline at best. For scale, division rivalry is −45%. | [Report](reports/2026-front-office-ties.md) |
| Whose front offices did today's heads of baseball operations come through, and how did they get the job? | More future heads came through Cleveland than any other club: 15 worked there before their first head job, and 9 hold a club's top baseball-operations job today. John Hart's tree reaches 21 of today's 38 within three generations; directly, he and Epstein are tied at 10 counting two or more shared seasons. Since 2009 the median head took 14 years from his first recorded front-office job, 75% held an assistant GM title first, and 58% were promoted from inside. Built as a graph in Neo4j, with PageRank from Graph Data Science. | [Report](reports/2026-gm-tree.md) |
| What would a pro scout write on the top free-agent reliever? | Adrián Morejón: OFP 60, a B1 reliever for 2027. Sinker, changeup and four-seamer grade 70; the slider is 50 now and 55 future. It got 3.3 mph harder and lost 2.7 in of drop as its whiffs fell from 40% to 30%. Delivery items that need eyes are NG, and the look before the bid is written out. | [Report](reports/2026-morejon-pro-scouting-report.md), [one page](reports/2026-morejon-pro-scouting-report.pdf) |
| How should a club pitch the Rays' lineup in the ALCS? | Pitch in the zone and get outs on weak contact: the nine regulars missed on 19.9% of swings (league 25.1%) and do little damage on contact (.331 xwOBA, league .362). The usual put-away pitch, a breaking ball below the zone, gets 17.4 swinging strikes per 100 against the league's 23.2. Hitter by hitter cards, a one-page coach version and the same page in Spanish. | [Packet](reports/2026-advance-packet-tb.md), [coach](reports/2026-advance-packet-tb-coach.md), [en español](reports/2026-advance-packet-tb-coach-es.md) |
| What should a club file in Cade Smith's first arbitration case? | $4.65M, settle at $5.0-5.1M, and go to a hearing above $5.1M. A comp pool built by a stated rule (every 20-save platform year since 2015 going into a first arbitration year, 23 closers) puts him at $4.58M; the club wins at a $5.275M midpoint about 60% of the time. An independent exercise from public data, with the 2022-26 agreement's criteria and what a panel can't hear. | [Brief](reports/2027-arbitration-brief-smith.md) |
| Does the same method hold for a Super Two on another club? Toronto's Louis Varland | Yes. File $3.65M, settle at $3.8M or less, and go to a hearing above $3.8M. The same 23-closer pool puts him at $3.58M, MLB Trade Rumors says $3.8M, and the club wins at a $3.85M midpoint about 61% of the time, favored under any weighting of the two views. As a Super Two he has four arbitration years, so losing costs $1.39M in present value. His side's best route is the 2020-26 market alone ($4.40M). An independent exercise from public data. | [Brief](reports/2027-arbitration-brief-varland.md) |
| Do good swing decisions last, and what is Gleyber Torres worth? | Yes: decision value repeats year to year (r = 0.80 from 2025 to 2026). Torres's decisions are among the best in baseball, but his bat lost 2 mph in 2026. 1.50 WAR projected for 2027 with baserunning; sign at two years, $28-32M, walk away above $17M a year. | [Evaluation](reports/2026-hitter-evaluation-torres.md) |
| What is a draft pick worth, and does a college stat line still beat the pick? | Pick 1 is worth about $75M before the bonus; from the second round on the typical player returns nothing, and pitchers return about 72% of hitters at the same pick. A college-stat model helped on 2012-2019 classes but adds nothing to the pick on 2020-2023 classes: the draft order has absorbed the public line. 23 of 30 clubs went over their 2026 bonus pool and none crossed 5%. | [Report](reports/2026-mlb-draft-analytics.md) |
| Can I beat the market on prices, performance and amateurs? | Fifteen calls for 2027, each with a probability, dated Oct. 18, 2026, and scored with the Brier score after the season (0.25 is the no-skill line). | [Log](reports/2027-prediction-log.md) |
| Was Tarik Skubal's 2025 change real? | Yes, and the change was his: he ranked at the 80th–98th percentile on the changes, and the league didn't move. His changeup's 46.6% whiff rate (997 swings) is his true level. | [Report](reports/2025-skubal-arsenal.md) |

The **Edge Board** is a monthly league scan, refreshed by `bb edge` and `bb board` ([numbers](reports/2026-edge-board.md)). It covers:
- release tells
- hidden in-season pitch changes (291 in 2026, by 225 pitchers)
- results beyond stuff, which persist year to year (r = 0.56 and 0.53)
- next-season whiff projections, validated against a regressed baseline (8.1% less error, leave-one-out)

<table>
<tr><td width="25%" valign="top"><a href="reports/2026-bullpen-acquisition-memo.md"><img src="reports/figures/2026-bullpen-acquisition-memo.png" width="100%" alt="Bullpen memo"></a><br><sub><b>Bullpen memo</b></sub></td><td width="25%" valign="top"><a href="reports/2026-league-pitch-familiarity.md"><img src="reports/figures/2026-league-pitch-familiarity.png" width="100%" alt="Pitch familiarity"></a><br><sub><b>Pitch familiarity</b></sub></td><td width="25%" valign="top"><a href="reports/2026-reliability-atlas.md"><img src="reports/figures/2026-reliability-atlas.png" width="100%" alt="Reliability Atlas"></a><br><sub><b>Reliability Atlas</b></sub></td><td width="25%" valign="top"><a href="reports/2026-pitch-design-levers.md"><img src="reports/figures/2026-pitch-design-levers.png" width="100%" alt="Pitch-design levers"></a><br><sub><b>Pitch-design levers</b></sub></td></tr>
<tr><td width="25%" valign="top"><a href="reports/2026-roster-cba-engine.md"><img src="reports/figures/2026-skenes-extension-band.png" width="100%" alt="Skenes extension"></a><br><sub><b>Skenes extension</b></sub></td><td width="25%" valign="top"><a href="reports/2026-gm-tree.md"><img src="reports/figures/2026-gm-tree.png" width="100%" alt="GM tree"></a><br><sub><b>GM tree</b></sub></td><td width="25%" valign="top"><a href="reports/2026-morejon-pro-scouting-report.md"><img src="reports/figures/2026-morejon-pro-scouting-report.png" width="100%" alt="Pro scouting report"></a><br><sub><b>Pro scouting report</b></sub></td><td width="25%" valign="top"><a href="reports/2026-advance-packet-tb.md"><img src="reports/figures/2026-advance-tb-whiff.png" width="100%" alt="Advance packet"></a><br><sub><b>Advance packet</b></sub></td></tr>
<tr><td width="25%" valign="top"><a href="reports/2027-arbitration-brief-smith.md"><img src="reports/figures/2027-arbitration-brief-smith.png" width="100%" alt="Arbitration case"></a><br><sub><b>Arbitration case</b></sub></td><td width="25%" valign="top"><a href="reports/2026-trade-network-rivals.md"><img src="reports/figures/2026-trade-network-rivals.png" width="100%" alt="Trade network"></a><br><sub><b>Trade network</b></sub></td><td width="25%" valign="top"><a href="reports/2026-hitter-evaluation-torres.md"><img src="reports/figures/2026-hitter-evaluation-torres.png" width="100%" alt="Hitter evaluation"></a><br><sub><b>Hitter evaluation</b></sub></td><td width="25%" valign="top"><a href="reports/2025-skubal-arsenal.md"><img src="reports/figures/2025-skubal-movement.png" width="100%" alt="Skubal arsenal"></a><br><sub><b>Skubal arsenal</b></sub></td></tr>
</table>

## 2026 postseason snippets

Ten quick charts on the 2026 postseason, from the Wild Card Series through the Brewers' five-game World Series win over the Rays: win probability pitch by pitch, the biggest bats and arms by WPA, contact quality, swing decisions, velocity and exit-velocity leaders, and how deep the starters went. [See them all](reports/2026-postseason-snippets/).

<table>
<tr><td width="33%"><a href="reports/2026-postseason-snippets/"><img src="reports/2026-postseason-snippets/world_series_wp.png" width="100%" alt="World Series win probability"></a></td><td width="33%"><a href="reports/2026-postseason-snippets/"><img src="reports/2026-postseason-snippets/pitcher_wpa.png" width="100%" alt="Pitcher WPA"></a></td><td width="33%"><a href="reports/2026-postseason-snippets/"><img src="reports/2026-postseason-snippets/team_contact.png" width="100%" alt="Team contact quality"></a></td></tr>
</table>

<a id="what-a-club-gets"></a>
## What a club gets

| Department | Question it answers | Work |
|---|---|---|
| GM and pro personnel | Who do we sign, at what price, and where do we walk away? | [Bullpen memo](reports/2026-bullpen-acquisition-memo.md), [hitter evaluation](reports/2026-hitter-evaluation-torres.md) |
| Front office and payroll | What does the tax bill look like, and what is an extension worth under the next CBA? | [Roster and CBA engine](reports/2026-roster-cba-engine.md) |
| Arbitration | What do we file, where do we settle, when do we go to a hearing? | [Smith](reports/2027-arbitration-brief-smith.md), [Varland](reports/2027-arbitration-brief-varland.md) |
| Pro scouting and trades | Who are the realistic trade partners, and what does a scout write before a bid? | [Trade network](reports/2026-trade-network-rivals.md), [front-office ties](reports/2026-front-office-ties.md), [pro scouting report](reports/2026-morejon-pro-scouting-report.md) |
| Advance scouting and coaches | How do we pitch this lineup, in a page a coach will read (in English or Spanish)? | [Advance packet](reports/2026-advance-packet-tb.md) |
| Player development | Which pitch-design changes stick and pay, and how is a plan tracked? | [Pitch-design levers](reports/2026-pitch-design-levers.md) |
| In-game strategy | Do pitches wear out, and should that change the hook? | [Pitch familiarity](reports/2026-league-pitch-familiarity.md), [exposure-aware hook](reports/2026-exposure-aware-hook.md) |
| Amateur scouting | What is a pick worth, and what does a college line still add? | [Draft analytics](reports/2026-mlb-draft-analytics.md) |
| R&D, every department | How much should we believe this number? | [Reliability Atlas](reports/2026-reliability-atlas.md), [shape exposure](reports/2026-shape-exposure.md) |

Every report page opens the same way: the question, the answer and what a club does with it, then the full work. The format is written down in the [report standard](docs/report-standard.md).

<p><img src="assets/img/strip-scouting.jpg" width="100%" alt="Dylan Fanelli with a radar gun in the stands"></p>
<p align="center"><sub>Radar gun in the stands with the Medford Rogues. The work starts at the park.</sub></p>

## How the work is held up
- **Out of sample by default.** Forecasts are tested on seasons their parameters never saw, against a regressed baseline, never raw last season.
- **One evidence standard.**
  - Confirmed means p < 0.05 with enough sample; near 0.05 is borderline.
  - Many tests at once get a Benjamini–Hochberg correction.
  - "No sign of an effect" is claimed only when the interval rules out effects that matter. Otherwise the report says "not detected" and gives the bound.
- **Separate review.** Every finished report gets a separate review pass that checks each number against the saved outputs. The reviews changed real conclusions:
  - the Skenes price
  - the ranking of pitch-design levers
  - a noise model for pitch physics
  - a free-agent reliever's 2027 status
  - the dating of front-office ties, and which tie results count as confirmed
  - a reliever's changeup history and the cause of his slider's decline
  - [LOG.md](LOG.md) records each one.
- **Hand-checked tests.** 401 of them, with the arithmetic in comments.
- **Pooling and regression rules.** Seasons are pooled only with standard errors clustered by pitcher. Small samples are regressed before they're compared.
- **Public data only.** Statcast via Baseball Savant, the Chadwick register for names, MLB Stats API transactions, Baseball-Reference (WAR and front-office listings), Retrosheet, and cited, dated public reporting for contracts, transactions and executive careers. No club's data is in this repository.

## The toolkit (`bb`)

| Job | Commands |
|---|---|
| **Data** | `pull-league`, `slim`, `seq` (every pitch with batter, location, base-out state, bat tracking), `people` (names), `db` |
| **Evaluation** | `arsenal`, `compare` (two seasons, with significance), `reliability` and `regress` (regress any number, with an interval), `compare-relievers` (regressed results, stuff, velocity vs league, workload, platoon, 20-80 grades), `delivery` (slot, extension, release scatter, exact VAA, release offsets against each game's fastballs) |
| **Edge** | `edge`, `board` (release tells, hidden changes, stuff vs results, projections), `familiarity`, `hook`, `hook-card` (one start, hitter by hitter) |
| **Development** | `levers` (what shape changes pay), `idp` (individual development plans in YAML, with a progress engine that issues verdicts and checks statistical power) |
| **Roster** | `cbt` and `cbt-check` (luxury tax, checked against the real 2025 bills), `service` (control, Super Two, arbitration, free agency), `roster-cases`, `bullpen-case`, `trades` (the MLB trade graph in Neo4j, rival and burst analysis), `gm-tree` (whose front offices today's heads came through, in Neo4j), `front-office` (executive careers and the ties model) |
| **Department work** | `advance` (an opponent's hitter cards, figures and plan), `arb-case` (an arbitration case from comps to walk point: `smith` or `varland`), `swing-decisions` (decision value and one hitter's card and price), `predictions` (check, score and render the prediction log), `sql` (twelve named DuckDB queries: `list`, `show`, `run`) |
| **Tracking data** | A TrackMan/Rapsodo loader with sign checks and QC, a TrackMan session-PDF reader, and a portable expected-whiff model for device data |

A dated record of what was built, decided and learned is in [LOG.md](LOG.md). The roadmap is in [Issues](../../issues).

## Under the hood

```mermaid
flowchart LR
    A[Public data<br>Statcast, MLB Stats API,<br>Baseball-Reference, Retrosheet] --> B[DuckDB warehouse<br>and slim parquet seasons]
    B --> C[bb toolkit<br>evaluation, edge, development,<br>roster, department work]
    C --> D[Reports and figures<br>reports/]
    C --> E[Neo4j graphs<br>trades, front offices]
    D --> F[Separate review pass<br>every number checked]
    C --> G[Hand-checked tests<br>GitHub Actions]
```

## Run it
Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/IForSureI/Dylan-Fanelli-Baseball-Analytics-Portfolio.git ~/Baseball
cd ~/Baseball
uv sync
uv run pytest                                # 401 tests
uv run bb people                             # player names
uv run bb pull-league 2026 && uv run bb seq 2026   # every pitch of a season (pulls from Baseball Savant)
uv run bb regress hitter/whiff 0.40 50 --horizon next_season
uv run bb cbt 417.341608 5 --season 2025     # the Dodgers' 2025 tax bill: $169.376M
uv run bb compare-relievers 2026 670970 650556
uv run bb sql run velocity_by_inning -p pitcher=669373 -p season=2026
uv run bb predictions check
```

A monthly job (`scripts/automation/`) pulls new pitches and reruns the studies. The data stays local (`data/` is never committed) and every result rebuilds from it.

## Reference
- [Glossary](docs/glossary.md): the terms used across the reports, in plain words first.
- [Data dictionary](docs/data-dictionary.md): every source, what it covers, and the key columns.
- [Report standard](docs/report-standard.md): how every report page is built.
- [Photo credits](docs/photo-credits.md): the photographs are from my own playing and scouting years.


<a id="about"></a>
## About
I'm Dylan Fanelli, an M.S. Sport Management candidate at the Isenberg School of Management (McCormack Department of Sport Management), UMass Amherst. I'm working toward a career in baseball operations. [LinkedIn](https://www.linkedin.com/in/dylanfanelli/)

I pitched at Allegheny, Occidental and UMass and for the Medford Rogues, where I also built scouting reports on opposing hitters and pitchers. The questions in this portfolio come from there.

<table>
<tr><td width="25%" align="center" valign="top"><img src="assets/img/tile-allegheny.jpg" width="100%" alt="Dylan Fanelli, Allegheny College"><br><sub><b>Allegheny College</b></sub></td><td width="25%" align="center" valign="top"><img src="assets/img/tile-oxy.jpg" width="100%" alt="Dylan Fanelli, Occidental College"><br><sub><b>Occidental College</b></sub></td><td width="25%" align="center" valign="top"><img src="assets/img/tile-rogues.jpg" width="100%" alt="Dylan Fanelli, Medford Rogues"><br><sub><b>Medford Rogues</b></sub></td><td width="25%" align="center" valign="top"><img src="assets/img/tile-umass.jpg" width="100%" alt="Dylan Fanelli, UMass Amherst"><br><sub><b>UMass Amherst</b></sub></td></tr>
</table>

## License
© 2026 Dylan Fanelli. All rights reserved. The code, reports and figures may be viewed here; they may not be copied, modified or used without written permission. See [LICENSE](LICENSE). To cite this work, use the **Cite this repository** button (from [CITATION.cff](CITATION.cff)).
