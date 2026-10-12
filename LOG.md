# Log

Newest first. One entry per working session: what was built, what was decided, what was learned.

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
