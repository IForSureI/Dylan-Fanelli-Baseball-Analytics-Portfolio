# SQL module

Twelve named queries that answer questions a baseball operations department asks every week, written in
DuckDB SQL against Statcast pitch-level data. Each file is one query with a header that states the question,
the inputs, the output columns and the definitions it uses. `baseball/sqlkit.py` runs them.

## Run it

```python
from baseball.sqlkit import run, connect, describe, queries

run("arsenal_by_count", pitcher=645261, season=2026)      # one query, one DataFrame

con = connect(seasons=[2024, 2025, 2026])                 # reuse one connection for several queries
run("league_baselines", con, season_from=2024, season_to=2026)
run("reliever_rest", con, season=2026, min_relief_apps=40)

queries()                                                 # every query name
describe("platoon_splits")["inputs"]                      # inputs and their defaults
```

`connect()` registers two views:

| View | Source | Built by |
|---|---|---|
| `pitches` | `data/seq/seq_<season>_*.parquet`, one row per pitch | `bb seq <season>` |
| `people` | `data/people/people.parquet`, MLBAM id to name | `bb people` |

The view casts id and count columns to BIGINT, because some seasons' files store them as FLOAT. Inputs are
DuckDB named parameters (`$season`). The runner reads each query's inputs and defaults from its header, fills
the defaults, and stops with a clear error on a missing or unknown input. A header that disagrees with the
parameters its query uses is an error too, and the tests check every header's column list against the real
output, so the documentation can't drift from the code.

You can also paste any file into DuckDB, DBeaver or the DuckDB CLI after creating the `pitches` view yourself
and replacing the `$` parameters.

## The queries

| File | Question | Key inputs |
|---|---|---|
| `arsenal_by_count.sql` | What he throws in each count state: usage, velocity, whiff and chase | `pitcher`, `season` |
| `hitter_zone_discipline.sql` | A hitter's swing, whiff and chase rates by Statcast zone (1-9, 11-14) | `batter`, `season` |
| `times_through_order.sql` | wOBA allowed the 1st, 2nd and 3rd time through, and the penalty | `season`, `min_pa_3rd` |
| `platoon_splits.sql` | Every pitcher vs LHH and RHH: PA, wOBA, xwOBA, K%, platoon gap | `season`, `min_pa` |
| `bat_tracking_leaders.sql` | Bat speed and swing length leaders on competitive swings | `season`, `min_swings` |
| `velocity_by_inning.sql` | A starter's fastball velocity by inning (fatigue) | `pitcher`, `season` |
| `first_pitch_outcomes.sql` | First-pitch strike rate, and how PAs end after 0-1 vs 1-0 | `season`, `pitcher` (optional) |
| `run_value_by_pitch_type.sql` | Runs saved per 100 pitches by pitcher and pitch type, ranked within type | `season`, `min_pitches` |
| `hitter_damage_zone.sql` | A hitter's xwOBA on contact, hard-hit and barrel rates by zone, optionally in one count state | `batter`, `season`, `count_state` |
| `reliever_rest.sql` | Relief outings on 0, 1, 2 and 3+ days' rest, and fastball velocity change vs rested | `season`, `min_relief_apps` |
| `league_baselines.sql` | League whiff, CSW, chase, zone rate and run value by pitch type and season | `season_from`, `season_to` |
| `velocity_drop_between_starts.sql` | Each starter's largest start-to-start fastball velocity drop, and whether it came back | `season`, `min_starts` |

## Definitions

These match the pandas code in `baseball/evaluation/` (`arsenal.py`, `reliability.py`, `reliever.py`,
`delivery.py`), so a number from SQL and a number from pandas mean the same thing.

| Term | Definition |
|---|---|
| Regular season | `game_type = 'R'` |
| Pitch | Any row except `automatic_ball` and `automatic_strike` (pitch-clock calls and intentional walks, where no pitch was thrown). PA-level queries keep those rows when they end a PA, since an automatic strike three is still a strikeout. |
| Swing | `swinging_strike`, `swinging_strike_blocked`, `foul`, `foul_tip`, `foul_bunt`, `missed_bunt`, `hit_into_play` (plus the older `hit_into_play_no_out` and `hit_into_play_score` labels) |
| Whiff | `swinging_strike`, `swinging_strike_blocked`, `foul_tip`, `missed_bunt`. Whiff% = whiffs / swings. |
| Neither | `bunt_foul_tip` (28 rows in 2026) and `swinging_pitchout` are neither swings nor whiffs, on purpose: it matches `arsenal.py`, and both are too rare to move a rate. |
| CSW% | (called strikes + whiffs) / pitches |
| Zone | Statcast zones 1-9 are in the strike zone, 11-14 outside it. Chase% = swings at 11-14 / pitches at 11-14. Zone% = pitches at 1-9 / all pitches. |
| Count state | 0-0; 2 strikes; behind (more balls than strikes); even/ahead (the rest) |
| PA | A row whose `events` ends a plate appearance (baserunning events such as `caught_stealing_2b` and `truncated_pa` don't count) |
| wOBA | `SUM(woba_value) / SUM(woba_denom)` over rows with `woba_denom = 1` |
| xwOBA | Same denominator; balls in play use `estimated_woba_using_speedangle` (the actual value when Statcast has no estimate), everything else uses `woba_value` |
| Competitive swing | The fastest 90% of a hitter's tracked swings in the season, plus any 60+ mph swing with a 90+ mph exit velocity; bunts never count |
| Run value | `delta_run_exp` flipped to the pitcher's side: runs saved = `-SUM(delta_run_exp)` |
| Start | The pitcher threw his team's first pitch of the game |
| Days' rest | Calendar days since his previous appearance minus one: back-to-back days = 0 |

## How the queries are written

- **Grain first.** Every CTE has a comment saying what one row is.
- **Flags once, rates after aggregation.** Swing, whiff and zone flags are built in one CTE. Rates come from
  summed counts: `100.0 * COUNT(*) FILTER (WHERE is_whiff) / NULLIF(COUNT(*) FILTER (WHERE is_swing), 0)`. The
  `100.0` keeps the division decimal in engines that truncate integer division.
- **Floors after shares.** Usage is computed over every pitch before a minimum is applied (`QUALIFY` after the
  window), so a floor never inflates a share.
- **Counts next to rates.** Every rate has its sample beside it.
- **Lean reads.** Each query selects only the columns it needs and filters the season in its first CTE, so
  DuckDB reads only a few columns from disk.

## Validation on 2026 data

All twelve queries run on the full 2026 regular season (716,792 rows) in 0.1 to 0.4 seconds each, and every
output matches the columns its header lists. Three spot checks against the repo's pandas code:

| Check | Result |
|---|---|
| `arsenal_by_count` (the "all" rows) vs `arsenal_counts()` and `outcomes()` in `arsenal.py`, Sandy Alcantara 2026 | Identical on all 7 pitch types: n, usage, velocity, whiff% and chase% (max difference 0.0) |
| `run_value_by_pitch_type` vs `outcomes()` rv_per100, same pitcher | Identical on all 7 pitch types |
| `bat_tracking_leaders` vs `competitive_swings()` in `reliability.py`, every 2026 hitter | Same 660 hitters, same competitive-swing count for all 660, bat speed and swing length equal to the rounding |

The bat-tracking check caught a real issue: DuckDB's interpolated 10th percentile came out as
63.900000000000006 for one hitter, which dropped two swings recorded at exactly 63.9 mph. The query now
compares with a 1e-9 slack.

`first_pitch_outcomes` gives Alcantara 63.0% first-pitch strikes on 894 PAs; `first_pitch_strike()` in
`delivery.py` gives 63.1% on 899 first pitches. The five-pitch gap is PAs that never reached a PA-ending
event (the inning ended on the bases), which the SQL needs for the outcome columns.

Tests: `tests/test_sqlkit.py` builds a fictional parquet file in a temp folder (plus a 2025 file stored with
FLOAT ids, to test the cast) and runs every query against it, with hand-checked answers for eleven of them.
It needs no real data, so it runs in CI.

## Walk me through it

Questions to answer cold about these queries, with short answers.

**1. Why write these as CTEs instead of nested subqueries?**
Each CTE is one step with one grain: filter, flag, aggregate, rank. You read it top to bottom like the
analysis itself, you can run any step alone to debug it, and a step used more than once is written once:
`his_starts` in `velocity_by_inning`, `primary_fb` and `with_rest` in `reliever_rest`. DuckDB inlines or materializes CTEs as it sees fit, so the readability costs nothing.

**2. What does the window function do in `velocity_drop_between_starts`?**
`LAG(velo) OVER (PARTITION BY pitcher ORDER BY game_date)` puts the previous start's fastball velocity on
each start's row, so the drop is a simple subtraction on one row. `LEAD` does the same with the next start, to
show whether the velocity came back. Then `ROW_NUMBER() OVER (PARTITION BY pitcher ORDER BY drop DESC)`
numbers each pitcher's drops from biggest to smallest, and `QUALIFY ... = 1` keeps the biggest. A window keeps
every row while it computes; `GROUP BY` would collapse the starts and lose the order.

**3. In `arsenal_by_count`, why is the sample floor a `QUALIFY`?**
SQL runs `WHERE`, then `GROUP BY` and `HAVING`, then window functions, then `QUALIFY`. Usage is a window
(`n / SUM(n) OVER (PARTITION BY count_state)`). Filtering with `WHERE` or `HAVING` would drop the small pitch
types before the window runs, and the remaining pitches' usage would add up to 100% of a smaller total.
`QUALIFY` filters after the window, so usage is still out of every pitch he threw.

**4. Why compute whiff% as `COUNT(*) FILTER (WHERE is_whiff) / COUNT(*) FILTER (WHERE is_swing)`?**
A rate is a ratio of sums. Averaging per-game rates gives a 1-for-1 game the same weight as a 20-swing game.
`FILTER` counts the numerator and the denominator in the same pass over the rows; `NULLIF(swings, 0)` returns
NULL instead of dividing by zero. One trap: `COUNT(*) / COUNT(*)` divides two integers. DuckDB returns a
decimal, but Postgres and SQL Server truncate it to 0, so the queries write `100.0 * COUNT(*) FILTER (...) /
NULLIF(COUNT(*) FILTER (...), 0)` and get a percentage in every engine.

**5. What do `GROUPING SETS` and `GROUPING()` do in `league_baselines`?**
`GROUP BY GROUPING SETS ((season, pitch_type), (season))` produces the pitch-type rows and the season total in
one scan, the same as a `UNION ALL` of two `GROUP BY` queries that each read the data. On the total row
`pitch_type` is NULL; `GROUPING(pitch_type) = 1` tells you the NULL came from the rollup, so it can be labeled
`ALL` safely even if a real NULL pitch type ever appeared.

**6. How would you make this fast on 10 years of data?**
- Store the pitches as parquet partitioned by season (`season=2026/`), so a one-season query opens one folder.
- Sort each file by `game_date` and `pitcher`; DuckDB keeps min and max per row group and skips the ones a
  filter rules out.
- Read only the columns you need (parquet is columnar, so `SELECT *` on 79 columns is the expensive habit).
- Pre-aggregate what gets asked every day into small tables: pitcher-game (pitches, fastball velocity, outs)
  and pitcher-season-pitch-type (counts behind every rate). Most of these queries then read thousands of rows
  instead of millions.
- Build those tables incrementally: each night, add the new games instead of rebuilding.

**7. How does a query know who started, and where does that rule break?**
`ROW_NUMBER() OVER (PARTITION BY game_pk, fielding_team ORDER BY at_bat_number, pitch_number) = 1` finds the
first pitch each team threw; whoever threw it started. The fielding team is the home team in the top of the
inning. The rule calls an opener a starter and the bulk pitcher after him a reliever, so a club that uses
openers shows up with short "starts". The fix is a rule on outs or pitches (for example, a start needs 9+ outs)
or a role table maintained by hand.

**8. Is the times-through-the-order penalty a skill?**
Treat it as a measurement with selection in it. Pitchers who are struggling get pulled before the third time
through, so the third-time sample leans toward their good days, and the hitters it includes are the
lineup's top. The query gives counts beside every wOBA. Before calling a pitcher's penalty his own, shrink it
toward the league penalty from the same query in proportion to his third-time PAs; at 100-200 PAs it is mostly
noise.

© 2026 Dylan Fanelli. All rights reserved. See [LICENSE](../LICENSE).
