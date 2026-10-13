# Log

Newest first. One entry per working session: what was built, what was decided, what was learned.

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
