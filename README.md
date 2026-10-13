# Baseball research: Dylan Fanelli

Baseball-operations research and tools built on every public pitch of 2024–2026 (2.14 million regular-season pitches). Each piece:
- **Answers a question a club pays to answer.**
- **Is validated out of sample.**
- **Is independently reviewed** against its own outputs before it's final.
- **Ships as code a club can run.** Nulls are reported as nulls.

## Start here (10 minutes)
1. **[Bullpen acquisition memo, 2026-27](reports/2026-bullpen-acquisition-memo.md).** The capstone: one real offseason decision made the way a front office makes it, using every tool below.
2. **[Does a pitch wear out?](reports/2026-league-pitch-familiarity.md)** An original question with a clear answer, and a [follow-up](reports/2026-exposure-aware-hook.md) that tested whether it should change the hook. It shouldn't.
3. **[The Reliability Atlas](reports/2026-reliability-atlas.md).** Which numbers to trust, after how many pitches, swings or batted balls, and how far to regress them.

## The research

| Question | Answer | Report |
|---|---|---|
| Which reliever should the Rangers sign this winter, and at what price? | Adrián Morejón. Open at 4 years, $60M; walk away above $72M, which lands him about half the time. Bryan Abreu is the plan above that. Pete Fairbanks isn't a 2027 option after thoracic outlet surgery. | [Memo](reports/2026-bullpen-acquisition-memo.md) |
| Does a pitch lose effectiveness on a hitter the more of it he has seen? | Yes, and it's specific to the pitch type. Each earlier changeup or splitter in his earlier plate appearances today goes with 1.87 fewer whiff points on the next one. The effect carries across games and partly to the next same-handed pitcher. | [Report](reports/2026-league-pitch-familiarity.md) |
| Should that change when the starter comes out? | No. The per-pitch cost replicates out of sample, but it doesn't reach plate-appearance run value (2026 calibration slope −0.28, SE 0.37). Managers show no response to it either. | [Report](reports/2026-exposure-aware-hook.md) |
| Which numbers can you trust, and when? | Regressing beats raw numbers out of sample for 135 of 147 metric groups, confirmed on a clean 2024 → 2025 replication. Bat speed is half signal after about 3 swings and reaches r = 0.7 after about 6; wOBA's fitted curve doesn't reach r = 0.5 until about 500 plate appearances (an extrapolation). Pitch physics regress by games, not pitches. | [Atlas](reports/2026-reliability-atlas.md) |
| Which pitch-design changes stick and pay? | Four-seam ride is the best-supported lever (+1.62 whiff points per 2 in). Velocity's payoff fails a placebo, so recovery isn't ruled out. Given the shape change, the single change in expected whiff predicts next season's whiff change better than the full lever model, pooled across pitch types. | [Report](reports/2026-pitch-design-levers.md) |
| Should the Pirates extend Paul Skenes before the CBA expires on Dec. 1? | Open at about $200M in present value and walk away above about $215M. The answer depends on the next agreement, and the memo prices both rule sets. The tax engine reproduces the 2025 luxury-tax bills within $1 for eight of nine clubs. | [Memo](reports/2026-roster-cba-engine.md) |
| Was Tarik Skubal's 2025 change real? | Yes. It was him, not the cameras: he ranked at the 80th–98th percentile on the changes, and the league didn't move. His changeup's 46.6% whiff rate (997 swings) is his true level. | [Report](reports/2025-skubal-arsenal.md) |

The **Edge Board** is a monthly league scan, refreshed by `bb edge` and `bb board`. It covers:
- release tells
- hidden in-season pitch changes (291 in 2026)
- results beyond stuff, which persist year to year (r = 0.56 and 0.53)
- next-season whiff projections, validated against a regressed baseline (8% less error, leave-one-out)

## How the work is held up
- **Out of sample by default.** Forecasts are tested on seasons their parameters never saw, against a regressed baseline, never raw last season.
- **One evidence standard.**
  - Confirmed means p < 0.05 with enough sample; near 0.05 is borderline.
  - Many tests at once get a Benjamini–Hochberg correction.
  - "No sign of an effect" is claimed only when the interval rules out effects that matter. Otherwise the report says "not detected" and gives the bound.
- **Independent review.** Every finished report goes to a reviewer who didn't build it and who checks each number against the saved outputs. The reviews changed real conclusions:
  - the Skenes price
  - the ranking of pitch-design levers
  - a noise model for pitch physics
  - a free-agent reliever's 2027 status
  - [LOG.md](LOG.md) records each one.
- **Hand-checked tests.** 228 of them, with the arithmetic in comments.
- **Pooling and regression rules.** Seasons are pooled only with standard errors clustered by pitcher. Small samples are regressed before they're compared.
- **Public data only.** Statcast via Baseball Savant, the Chadwick register for names, and cited, dated public reporting for contracts and transactions. No club's data is in this repository.

## The toolkit (`bb`)

| Job | Commands |
|---|---|
| **Data** | `pull-league`, `slim`, `seq` (every pitch with batter, location, base-out state, bat tracking), `people` (names), `db` |
| **Evaluation** | `arsenal`, `compare` (two seasons, with significance), `reliability` and `regress` (regress any number, with an interval), `compare-relievers` (regressed results, stuff, velocity vs league, workload, platoon, 20-80 grades) |
| **Edge** | `edge`, `board` (release tells, hidden changes, stuff vs results, projections), `familiarity`, `hook`, `hook-card` (one start, hitter by hitter) |
| **Development** | `levers` (what shape changes pay), `idp` (individual development plans in YAML, with a progress engine that issues verdicts and checks statistical power) |
| **Roster** | `cbt` and `cbt-check` (luxury tax, checked against the real 2025 bills), `service` (control, Super Two, arbitration, free agency), `roster-cases`, `bullpen-case` |
| **Tracking data** | A TrackMan/Rapsodo loader with sign checks and QC, a TrackMan session-PDF reader, and a portable expected-whiff model for device data |

A dated record of what was built, decided and learned is in [LOG.md](LOG.md). The roadmap is in [Issues](../../issues).

## Run it
Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/IForSureI/Baseball.git ~/Baseball
cd ~/Baseball
uv sync
uv run pytest                                # 228 tests
uv run bb people                             # player names
uv run bb pull-league 2026 && uv run bb seq 2026   # every pitch of a season (pulls from Baseball Savant)
uv run bb regress hitter/whiff 0.40 50 --horizon next_season
uv run bb cbt 417.341608 5 --season 2025     # the Dodgers' 2025 tax bill: $169.376M
uv run bb compare-relievers 2026 670970 650556
```

A monthly job (`scripts/automation/`) pulls new pitches and reruns the studies. The data stays local (`data/` is never committed) and every result rebuilds from it.

## About
Dylan Fanelli, M.S. Sport Management candidate at the Isenberg School of Management (McCormack Department of Sport Management), UMass Amherst. Working toward baseball operations. [LinkedIn](https://www.linkedin.com/in/dylanfanelli/)

## License
© 2026 Dylan Fanelli. All rights reserved. The code, reports and figures may be viewed here; they may not be copied, modified or used without written permission. See [LICENSE](LICENSE). To cite this work, use the **Cite this repository** button (from [CITATION.cff](CITATION.cff)).
