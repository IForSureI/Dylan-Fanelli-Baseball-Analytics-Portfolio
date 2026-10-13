# The exposure-aware hook: should what a hitter has seen decide when the starter comes out? MLB 2024–26

**League study from public pitch data.** Every regular-season plate appearance by a starting pitcher in 2024–26 (Statcast), with the familiarity costs re-estimated on 2024–25 only so that 2026 is a true out-of-sample test. It is observational: every number below is an association with fixed effects and controls, not a randomized test of pulling a pitcher.
*Written 2026-10-12 · Dylan Fanelli · Data: Statcast via Baseball Savant; 104,249 starter PAs and 66,016 removal decisions in 2026 (2,429 games), plus 2024 and 2025 · Code: `baseball/edge/hook.py` · Builds on [Does a pitch wear out?](2026-league-pitch-familiarity.md) · Not yet independently reviewed*

![Calibration of the exposure index, and what managers act on](figures/2026-exposure-aware-hook.png)

## Answer
- **No: a hitter's exposure to the starter's pitch mix should not move the hook, and managers already ignore it.**
- **The index doesn't predict run value out of sample.**
  - **The index:** for each hitter, the familiarity cost the starter's mix should carry against what that hitter has already seen today, in runs per PA. Costs come from 2024–25 only.
  - **The test:** if the index means what it says, a PA's run value rises one-for-one with it (slope 1.0).
  - **2026 (out of sample):** slope −0.28 (SE 0.37). Slope 1.0 is rejected (p < 0.001), and the 95% interval (−1.0 to 0.44) excludes even half of the predicted effect.
  - **All three seasons pooled:** 0.20 (SE 0.21). Only 2025 looks calibrated (0.92), and 2025 helped estimate the costs.
  - **As a forecast:** taking the index at face value makes 2026 PA forecasts slightly *worse* (p = 0.002 across games; p = 0.02 on a forward August–September split).
- **The mechanism is real; the step from pitches to runs is what fails.**
  - **Per pitch:** the run-value cost replicates in 2026 on its own: −0.15 / −0.22 / −0.53 runs per 100 pitches per earlier same-type pitch for fastballs, breaking balls and changeups/splitters, all p < 0.05.
  - **Whiffs per PA:** the same index built with whiff costs predicts the PA's whiff rate out of sample, about half calibrated (0.46 of the predicted drop, p = 0.05), and 0.79 (SE 0.24) once the PA's pitch mix is held fixed.
  - **Runs per PA:** hitters miss less, as the familiarity study says, and it doesn't add up to runs at a level anyone can detect.
- **Managers don't price it, and they do price something that doesn't predict either.**
  - **Exposure:** at 66,016 decisions from the second time through, the chance of removal doesn't move with the next hitter's index: −0.19 points per run/100 PAs (SE 0.27). The next three hitters' index doesn't move it either (−0.45, SE 0.45).
  - **Run value allowed so far:** removal rises 1.7 points per standard deviation (p < 0.001), but it has no association with the next PA's run value (−0.11 runs/100 PAs per SD, p = 0.75).
  - **Whiffs so far:** they do predict the next PA (−1.09 runs/100 PAs per SD, p < 0.001), and managers respond only weakly (−0.38 points per SD).
- **The ceiling is small even if the index were right.**
  - **The bound:** at face value, the top decile of third-time-through exposure is worth 1.7 runs per team-season (71 PAs × 2.3 runs/100 PAs above the median).
  - **At the 2026 estimate:** −0.5 runs, with a 95% upper bound of 0.7 runs per team-season.

## What a club can do with it
1. **Keep exposure out of the hook model.**
   - **Where it belongs:** pitch selection and sequencing, where it was measured. A changeup a hitter has seen five times is a weaker changeup.
   - **Where it doesn't:** a forecast of who wins the next PA. Pitchers already lean into what each hitter has seen (finding 4), and the per-pitch cost doesn't survive to the PA.
2. **Use the base card: times through and the starter's quality against a reliever baseline.**
   - **It validates out of sample:** slope 0.91 (SE 0.13) on 2026 PAs.
   - **Managers already track it:** 4.0% of starters are removed when the card says he's better than an average reliever, 16% when he's 4+ runs/100 PAs worse.
   - **Adding the index doesn't help:** it adds −0.06 (SE 0.22).
3. **Audit how much the hook leans on runs allowed.**
   - **The pattern:** run value allowed so far is the strongest in-game driver of removal here and the one with no forward signal.
   - **The other side:** whiffs so far carry forward signal and get little weight.
   - **The caveat:** selection may hide some signal in runs allowed (Limits).
4. **Don't buy an exposure-based hook product.** The per-hitter index can be built from public data (`hook_card`), and on a season it never saw it carries no run information.

## Findings

### 1. Calibration: does the index mean what it says? (PA run value on the index, both in runs per 100 PAs)

| Season | Main spec | p (slope = 1) | wOBA version (1 = calibrated) | PAs | Pitchers |
|---|---|---|---|---|---|
| 2024 (costs in sample) | 0.04 (0.36) | 0.008 | 0.09 (0.36) | 106,901 | 370 |
| 2025 (costs in sample) | 0.92 (0.39) | 0.83 | 0.73 (0.37) | 106,704 | 369 |
| **2026 (out of sample)** | **−0.28 (0.37)** | **< 0.001** | **−0.13 (0.35)** | **104,247** | **377** |
| Pooled, inverse-variance | 0.20 (0.21) | < 0.001 | | | |

- **Reading the table:** standard errors, clustered by pitcher, are in parentheses.
- **The wOBA column:** the coefficient divided by what a calibrated index implies. That benchmark uses 0.835 runs per unit of wOBA, the PA-level slope in 2024–25.
- **Between seasons:** the slopes differ more than noise alone would usually give (Cochran's Q = 5.4, p = 0.07). The one calibrated season is the one least suited to be the test.

**2026 under other specifications** (none is calibrated; the interval reaches 1.0 only when the standard error grows):

| Specification | Slope (SE) |
|---|---|
| Without the pitches-seen control | 0.01 (0.24) |
| Pitcher-season × times-through fixed effects | −0.25 (0.44) |
| Pitcher-season × times-through × batter-side fixed effects | 0.19 (0.50), p vs 1 = 0.10 |
| One average cost for every pitch type | −0.05 (0.33) |
| + how this hitter does against this pitcher's mix this season | −0.20 (0.37) |
| After the season's first 30 days (usage settled) | −0.17 (0.40) |
| Second time through only | −0.36 (0.58) |
| Third time through only | −0.24 (0.48) |

### 2. Third time through, by decile of the index (2026)

| Decile | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Index (runs/100 PAs) | 0.70 | 1.09 | 1.34 | 1.57 | 1.79 | 2.03 | 2.31 | 2.62 | 3.08 | 4.21 |
| Run value, adjusted (runs/100 PAs) | −2.95 | 0.78 | 0.99 | 1.19 | −0.87 | 0.80 | 2.50 | 0.40 | −1.01 | −0.36 |

- **Adjusted means:** net of pitcher-season and batter-season fixed effects and every control except the index and pitches seen. Each decile has about 2,080 PAs.
- **Top minus bottom:**
  - +2.6 runs/100 PAs (SE 1.2, p = 0.03) against a predicted 3.5
  - raw: +3.3 (p = 0.007)
  - with pitches seen also held fixed: +2.2 (p = 0.054)
- **There is no gradient behind that gap.**
  - **Where the gap comes from:** all of it is the bottom decile. Hitters who had seen the least costly mix did unusually poorly.
  - **The middle:** deciles 2–9 show no trend; they bounce between −1.0 and +2.5 in no order.
  - **The top:** the top decile is below the decile average.
  - **The fitted slope:** −0.24 within the third time through.
- **Under the repo's one evidence standard**, a contrast that rests on one decile isn't a finding when the linear test says no.

### 3. Out-of-sample forecasting (2026)

| Design | Index slope fitted in training | Index taken at face value | Most the index could buy if calibrated |
|---|---|---|---|
| 5-fold, whole games | +0.0001% MSE (t = 0.08) | −0.017% (t = −3.1) | 0.0066% |
| Forward split, Mar–Jul → Aug–Sep | +0.003% (t = 1.5) | −0.025% (t = −2.3) | 0.0065% |

- **The tests:** paired squared-error differences, clustered by pitcher. Positive means the index helps.
- **The ceiling:** the last column is the index's variance net of controls and fixed effects, the most it could cut MSE if its slope were exactly 1. At that size the forecasting tests can't find a calibrated index. The calibration slope is the informative test.
- **What forecasting can catch:** an index that is wrong. Imposing slope 1 makes forecasts measurably worse.
- **The base model:** fixed effects and controls don't beat the training-set mean on PA run value either (−0.14% and −0.29%). Single-PA run value is close to unforecastable, so small signals are best tested with calibration, not forecast error.

### 4. Why it doesn't aggregate: what was tested

| Test (2026) | Estimate | What it says |
|---|---|---|
| Per-pitch run-value contrast, 2026 alone | FB −0.15 (0.06), BRK −0.22 (0.08), OFF −0.53 (0.11), CUT −0.49 (0.17) | The input holds up out of sample |
| PA whiff rate on the whiff index (calibrated = −1) | −0.46 (0.24), p = 0.05 | The mechanism reaches the PA, about half strength |
| Same, holding the PA's swing mix by pitch type fixed | −0.79 (0.24), p = 0.001 | Close to calibrated once the mix is fixed |
| This PA's share of a type on how far the hitter's seen share exceeds usage | +0.123 (0.007) | Pitchers lean into what he's seen, not away |
| Index split: the part usage predicts / the hitter-specific part | −0.82 (0.52) / 0.31 (0.53) | Neither predicts runs (2025: −0.03 / 2.06; 2024: 0.12 / −0.07) |

- **Not power:** with 104,000 PAs the interval excludes 1.0, and the pooled interval excludes 0.63.
- **Not a weak input:** the per-pitch cost replicates in 2026, and the whiff version of the index works at the PA level.
- **Not avoidance:** pitchers don't steer away from familiar pitches.
  - For every 10 points by which a hitter's seen share of a type exceeds the pitcher's usage, the pitcher's share of that type in this PA is 1.2 points higher.
  - So the realized exposure (1.56 runs/100 PAs) is above the usage-based index (1.44).
- **Not matchup quality:** adding how the hitter does against this pitcher's mix leaves the slope at −0.20.
- **What remains:** the per-pitch cost is estimated holding the count, location and pitch type fixed.
  - Run value per PA lets all three respond: which pitch, where, and in which count.
  - The chase finding in the familiarity study (hitters chase familiar fastballs and breaking balls more) is one offset in that direction.
  - Which offset dominates wasn't isolated. "Pitchers' choices absorb it" is the leading explanation, not a tested one.

### 5. The manager test: what moves the hook (2026)
Linear probability of removal before the next PA. 66,016 decisions from the second time through; 6.95% end in a removal. Fixed effects are pitcher-season and next-batter-season; standard errors are clustered by pitcher.

| Signal | Change in removal chance (points) |
|---|---|
| **Next hitter's index, per run/100 PAs** | **−0.19 (0.27), p = 0.48** |
| **Next three hitters' index, per run/100 PAs** | **−0.45 (0.45), p = 0.32** |
| Pitch count 80s / 90s / 100s / 110+ (vs. under 60) | +9.1 / +30.6 / +53.9 / +65.9 |
| Third / fourth time through (vs. second) | +2.9 (0.6) / +10.6 (1.8) |
| Run value allowed so far, per run | +0.96 (0.10) |
| Whiffs so far, per whiff | −0.10 (0.04) |
| Fastball velocity up vs. first inning, per mph | −0.41 (0.11) |
| Next hitter same-handed | −3.1 (0.3) |
| Bullpen's pitches in the last 3 days, per 100 | −0.96 (0.13) |
| Leverage proxy, per unit | −0.51 (0.78), p = 0.52 |

- **The model sees what managers do:** pitch-count steps, times through, platoon, a tired bullpen. So the null on the index isn't a dead model.
- **The index is null everywhere it was tested:**

| Subset | Next hitter | Next three |
|---|---|---|
| Rested bullpen (below-median load) | 0.05 (0.41) | −0.48 (0.63) |
| Start of an inning | 0.00 (0.65) | −1.49 (1.07) |
| Mid-inning | 0.02 (0.26) | 0.01 (0.44) |
| Third time through or later | −0.35 (0.42) | −0.10 (0.74) |
| 2025 | −0.17 (0.23) | −0.47 (0.40) |
| 2024 | −0.14 (0.29) | −0.73 (0.47) |

- **The one exception:** in 2024, with both index terms entered together, the next-three term is −0.99 (p = 0.04), the wrong direction for pricing. It doesn't repeat in 2025 or 2026, so it isn't a finding.
- **Priced vs. predictive** (both per standard deviation of the signal, 2026):

| Signal | Next PA's run value (runs/100 PAs) | Removal (points) |
|---|---|---|
| Exposure index (next hitter) | −0.21 (0.41) | −0.18 (0.26) |
| Run value allowed so far | −0.11 (0.36) | **+1.72 (0.19)** |
| Whiffs so far | **−1.09 (0.28)** | −0.38 (0.15) |
| Fastball velocity up vs. first inning | −0.28 (0.23) | −0.40 (0.11) |

### 6. The tool: `hook_card(game_pk, pitcher)`
At each decision point, the card shows the next three hitters by lineup slot, each one's exposure index, and his expected run cost against the reliever baseline, with and without the index.

**Definitions** (per PA, offense's view):
- **Starter, base:**
  - the league-average starter at this hitter's time through and platoon (2024–25)
  - plus the starter's own quality: his run value per PA as a starter last season and earlier this season, relative to the league, shrunk by n/(n + 500)
  - The 500 was chosen on 2024 → 2025 so the quality term is calibrated one season ahead. The method-of-moments value, 90, was under-shrunk: slope about 0.6 one season ahead.
- **Starter, with index:** the base, plus the hitter's index minus the average index at his time through and platoon.
- **Reliever baseline:** the league-average reliever (not his team's first pitcher) in innings 5–9 facing a hitter for the first time that game.
  - 2024–25: −0.52 runs/100 PAs (133,161 PAs)
  - 2026: −0.24, a different season, for comparison
  - It is pooled over platoon because the reliever's hand isn't known at the decision. Same-hand −1.33, opposite-hand +0.33.
- **Cost:** starter minus reliever. Positive means the average reliever is expected to be better.

**Validation on 2026:**
- **The base expectation:** PA run value on it has slope 0.91 (SE 0.13), with batter-season fixed effects, 61,178 PAs.
- **The index on top:** −0.06 (SE 0.22).
- **Changed calls:** at face value the index would flip the sign of the call for the next hitter at 12% of decision points, and Findings 1–4 say those flips aren't supported.

**One real start: Tarik Skubal against St. Louis, September 3, 2026** (Statcast lists the game as STL at LAD; 102 pitches)
- **His quality term:** −4.4 runs/100 PAs, from 1,246 earlier starter PAs. So the base card favors him over an average reliever all night.

| After batter | Inning, outs, runners | Pitches | Next three (time through) | Index (runs/100 PAs) | Cost vs. reliever, base | With index | Removed |
|---|---|---|---|---|---|---|---|
| 16 | 4th, 0 out, empty | 60 | Church (2), Pagés (2), Fermín (3) | 0.9 / 0.8 / 4.0 | −4.2 / −3.1 / −1.7 | −4.3 / −3.5 / 0.0 | No |
| 18 | 4th, 2 out, empty | 69 | Fermín (3), Herrera (3), Walker (3) | 4.0 / 2.6 / 2.8 | −1.7 / −1.7 / −1.7 | 0.0 / −1.5 / −1.3 | No |
| 25 | 6th, 1 out, 1st & 2nd | 97 | Church (3), Pagés (3), Fermín (4) | 1.9 / 2.3 / 5.4 | −3.2 / −1.7 / −2.8 | −3.4 / −1.7 / −0.5 | No |
| 26 | 6th, 2 out, 1st & 2nd | 102 | Pagés (3), Fermín (4), Herrera (4) | 2.3 / 5.4 / 2.8 | −1.7 / −2.8 / −2.8 | −1.7 / −0.5 / −3.0 | **Yes** |

- **The leadoff hitter, José Fermín:**
  - Before his third PA he had seen 5 changeups, 5 fastballs and a slider from Skubal, the highest index in the lineup.
  - At face value it takes his PA to break-even with an average reliever (−1.7 → 0.0). He made an out; one PA says nothing either way.
- **The hook:** Skubal came out at 102 pitches with two on in the sixth, a pitch-count-and-leverage hook the base card already ranks low-cost.

## Method
**Grain.** One row per plate appearance by a starter, regular season. A starter is the pitcher who threw his team's first pitch, so openers are included (they rarely reach the second time through).
- **Run value:** the sum of Statcast's `delta_run_exp` over the PA, from the offense's side.
- **wOBA:** `woba_value` on PAs with `woba_denom` = 1.
- **Excluded:** PAs with a mid-PA pitching change (0.03%) and 45 PAs in 2026 with no usage information at all.

**The exposure index**, built before each PA:

> index = 3.83 × Σ over pitch types T of usage_T × seen_T × cost_T

- **seen_T:** pitches of type T the hitter saw from this pitcher in earlier PAs today.
- **usage_T:** the pitcher's share of type T to this hitter's batting side in his earlier games this season.
  - It is blended with last season's share at a weight of 150 pitches, so early-season usage leans on last season and fades.
  - With neither (a debut), his pitches earlier in this game are used.
  - Sources in 2026: this season and last 84%, this season only 12%, last season only 4%, today 0.8%.
- **cost_T:** the familiarity study's per-type run-value contrast (`familiarity.by_pitch_type`), re-estimated on 2024–25 pitches only.
  - Values, in runs per 100 pitches per earlier same-type pitch: FF 0.19, SI 0.24, FC 0.22, SL 0.13, ST 0.36, CU 0.55, KC 0.72, CH 0.44, FS 0.33.
  - Knuckle-curve (SE 0.20) and splitter (SE 0.17) are the noisiest. Other types cost 0.
- **3.83:** average pitches per PA in starters' PAs from the second time through, 2024–25.
- **Size:** the index averages 1.09 runs/100 PAs the second time through (SD 0.68), 2.08 the third (SD 1.02) and 2.73 the fourth (SD 1.21).
- **What it measures:** a contrast against having seen the same number of pitches of other types. Its level isn't a total cost, so every model holds pitches seen fixed.

**Outcome model.** PA run value (runs per 100 PAs) on the index.
- **Controls:**
  - times-through dummies and pitch count (and its square)
  - in-game form: run value allowed so far, whiffs, swings, fastball velocity over his last three PAs minus his first inning
  - platoon, the 24 base-out states, score margin, inning, and the pitches the hitter has seen
- **Fixed effects:** pitcher-season and batter-season, absorbed by alternating projections (`baseball.stats.absorb`).
- **Standard errors:** clustered by pitcher.

**Decision points.** After each PA a starter completes, when his defense has another PA in the game.
- **Removed:** someone else throws the next PA's first pitch, between innings or mid-inning.
- **The state:** the next PA's starting state.
- **The upcoming hitters:** taken from the lineup (whoever batted in that slot last time), not from who actually batted. A pinch hitter can be a response to the pitching change.
- **Leverage proxy:** the average absolute swing in home win expectancy over a PA in the state (inning × half × outs × bases × lead, clipped at ±4), divided by the overall average. It follows Tango's leverage index. It is estimated on 2024–25 and shrunk toward the inning × half × lead cell.
- **Bullpen workload:** relievers' pitches on the three calendar days before the game.
- **The model:** linear probability with pitcher-season and next-batter-season fixed effects, pitch-count bins, times through, inning, base-out state, lead, leverage, start of an inning, in-game form, the next hitter's platoon and pitches seen, the next three hitters' average pitches seen and platoon share, lineup slot due up, and bullpen workload. SEs are clustered by pitcher.

**Out-of-sample discipline.**
- **Fit on 2024–25 only:** costs, pitches per PA, the leverage table, the card's starter cells, the reliever baseline, and the quality shrinkage (fit 2024 → 2025).
- **2026 never touches them.**
- **2024 and 2025** are shown as in-sample comparisons.

**Tests.** 20 in `tests/test_hook.py`, on a hand-built fictional game with the arithmetic in comments. They cover:
- exposure counts, pitcher state before and after a PA, velocity drop
- usage blending, no current-game leakage, the debut fallback
- the index, decision flags and lineup-slot hitters
- leverage shrinkage, the shrinkage constant, the paired forecast test, decile contrasts
- fixed-effect recovery in forecasts, slope recovery under fixed effects
- the card's arithmetic, pitcher quality, bullpen load, the wOBA scale and the matchup control

## Limits
- **Observational.** Nothing here is a randomized hook. "Managers don't price it" means removal isn't associated with the index after controls. It doesn't mean managers never think about it.
- **Selection in the outcome model.**
  - **The sample:** outcomes exist only for PAs the manager allowed. If managers pull starters on private information (stuff, mechanics, a tweak), the PAs left in high-risk states come from starters they trust.
  - **Direction:** toward zero for any signal managers act on. Run value allowed so far is the clearest case, so its "no forward signal" holds *among starters left in*, not for every starter.
  - **For the index:** managers don't act on it (finding 5), so this channel should bias its slope little.
- **Selection in the removal model.**
  - **Bullpen availability:**
    - Workload is controlled.
    - Specific relievers being unavailable isn't. That adds noise unrelated to the index, which pulls the coefficient toward zero.
    - The interval is tight: ±0.5 points per run/100 PAs.
  - **Injuries and ejections:** they force removals unrelated to the index (attenuation again). Mid-PA changes are excluded.
- **The run-value outcome is noisy.**
  - A PA's run value has an SD of about 45 runs/100 PAs. The index's within-cell SD is under 1.
  - The test still rejects calibration, but it can't rule out a true slope of about 0.4.
  - The index is linear. The familiarity study found the first fastball look costs the most.
- **Only one window is priced:** earlier PAs today against this pitcher. Within-PA, earlier-game and cross-pitcher exposure aren't in the index.
- **The card's baselines are league averages.**
  - The reliever baseline isn't the club's actual bullpen, and the reliever who comes in isn't random: high-leverage arms take high-leverage spots.
  - Batter quality and state are assumed to shift starter and reliever equally.
- **Lineup slots** miss double switches made before a hitter bats. That's rare for the opponent's lineup before the hook.
- **2026** runs through September 27 (the regular season in the data). Postseason hooks weren't tested.

## Reproduce
```bash
uv run bb hook 2026                    # costs on 2024-25 (cached), every table and the figure -> data/edge/hook/
uv run bb hook-card 823907 669373      # the card for Skubal's September 3, 2026 start
```

## Sources
- **Pitch data:** Statcast, MLB Advanced Media, via [Baseball Savant](https://baseballsavant.mlb.com/) (regular seasons 2024–2026, pulled through October 2026).
- **Player names:** the Chadwick Bureau register (`bb people`, CC BY 4.0).
- **The per-pitch familiarity costs:** this repo's [pitch-type familiarity study](2026-league-pitch-familiarity.md) (2026-10-12), re-estimated here on 2024–25.
- **Times through the order and leverage:** Tom Tango, Mitchel Lichtman and Andrew Dolphin, *The Book: Playing the Percentages in Baseball* (2007).
- **The continuous decline across batters faced:** Ryan Brill, Sameer Deshpande and Abraham Wyner, "A Bayesian analysis of the time through the order penalty in baseball," *Journal of Quantitative Analysis in Sports* (2023).
