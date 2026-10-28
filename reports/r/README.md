# Hitter whiff rate in R: the Reliability Atlas regress step

**What it shows.** One step of the [Reliability Atlas](../2026-reliability-atlas.md), rebuilt in R
(tidyverse + DuckDB), gives the same answer as the Python original.

- **The question:** after n swings, how much of a hitter's whiff rate is really him?
- **The answer (2026 regular season, 340,712 swings, 661 hitters):** whiff per swing is half signal at
  **M = 54.5 swings** (95% interval 48.6-61.2). Python's code on the same swings: **54.7** (48.0-62.4).
  The atlas's shipped 2024-26 constant: 55.4 (49.0-62.7).
- **What to do with it:** regress. A hitter at 40% whiffs in 50 swings, league 25.1%, is best read as a
  32.2% whiffer (95% interval 23.4-40.9%). Same as the atlas.

## Does R match Python?

Yes. 79 of 79 checks pass ([output/check-results.md](output/check-results.md)).

| Check | What is compared | Result | Tolerance |
|---|---|---|---|
| A. Same splits | r(n) at 18 sample sizes, from the same 20 random game splits | identical (largest gap 7e-15) | 1e-10 |
| B. Same points | M fitted in R vs Python on Python's curve | 54.732 vs 54.732 | 1e-6 relative |
| C. Same constants | `regress()` estimate, interval, weight on 6 examples | identical (largest gap 5e-16) | 1e-9 |
| D. Independent runs | M, tau, r(n), regressed estimates, each side with its own 200 random splits | M 54.52 vs 54.73; r(64) 0.532 vs 0.528; estimates within 0.02 points | M 1.5%, r 0.0075, estimates 0.1 point |

Check D can't be exact: each language draws its own random splits. Its bars are about 1.5 times how far
Python moves from itself when only the seed changes (M ranged 54.16-54.79 over 11 seeds).

## The method, in six lines

1. Split each hitter's season **by game**: shuffle his games, deal them alternately into two halves.
2. Fill each half until it holds exactly n swings.
3. Correlate the halves across hitters. That is the reliability of n swings, r(n). Repeat 200 times.
4. Fit r(n) = n / (n + M). M is where r = 0.5.
5. Talent spread: tau = sqrt(noise per swing / M) = 0.062 (6.2 points of whiff rate).
6. Regress: estimate = league + w (observed - league), w = n / (n + M), interval = estimate +/- 1.96 tau sqrt(1 - w).

## Files

| File | What it does |
|---|---|
| `pull_swings.R` | Pulls one season of regular-season swings from Baseball Savant into DuckDB (one request per day). |
| `whiff_regress.R` | The study: load (SQL via DBI), split by game, correlate, fit M, regress. Run it or `source()` it. |
| `whiff-regress-r.Rmd` / `.md` | The report, step by step, rendered with the curve plot. |
| `python_reference.py` | Runs the repo's own `baseball/evaluation/reliability.py` on the same DuckDB file. |
| `check_against_python.R` | Checks A-D above; writes `output/check-results.md`; fails if any check fails. |
| `output/*.json` | Both sides' numbers. |

## Run it (repo root)

```bash
Rscript -e 'install.packages(c("tidyverse", "DBI", "duckdb", "jsonlite", "testthat", "rmarkdown", "rprojroot"))'
Rscript reports/r/pull_swings.R 2026 data/r/swings_2026.duckdb            # about 20-30 minutes, polite to Savant
uv run python reports/r/python_reference.py 2026 data/r/swings_2026.duckdb
Rscript reports/r/whiff_regress.R 2026 data/r/swings_2026.duckdb           # about 1 minute
Rscript reports/r/check_against_python.R 2026 data/r/swings_2026.duckdb
Rscript -e 'rmarkdown::render("reports/r/whiff-regress-r.Rmd")'
```

The DuckDB file and the shared-splits CSV live in `data/r/` and are not committed (`.gitignore`).

## Limits

- **One season (2026), not the atlas's three.** It checks the method, not the shipped constant.
- **Swings only.** The pull skips pitches without a swing. Python ran on the same file, so the
  comparison is like for like.
- **No year-to-year persistence (rho) or in-season drift.** `regress()` takes them as inputs
  (`horizon = "next_season"`, `"rest_of_season"`), but this study doesn't measure them.
- **The prior is the league mean.** A better prior for part-timers was not tested.

*Built 2026-10-28. Data: Statcast via Baseball Savant, 2026 regular season (March 25 - September 27),
pulled 2026-10-28. R 4.3.3, duckdb 2.0.0, dplyr 1.1.4; Python 3.13, pandas 3.0.5, numpy 2.5.3, duckdb 2.0.0.*
