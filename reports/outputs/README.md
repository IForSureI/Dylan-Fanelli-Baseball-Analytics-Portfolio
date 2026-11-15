# Saved outputs

Small tables behind five reports, so a reader can check the headline numbers without the pitch data. Added 2026-11-14.

| File | Report | Built from |
|---|---|---|
| `bullpen-2026.json` | [Bullpen memo](../2026-bullpen-acquisition-memo.md) | `baseball.roster.bullpen_case.money()` on the relief-season tables: the market line, each price and its interval, break-even prices, the qualifying-offer cost, landing odds, workload retention and the availability case |
| `edge-2026.json` | [Edge Board](../2026-edge-board.md) | the `bb edge 2026` summary, plus `validate_holdout()` on the saved pitch tables and counts from the saved pitch-change table |
| `edge-shift-null-2026.json` | [Edge Board](../2026-edge-board.md) | `python -m baseball.edge.shift_null 2026`: 200 shuffled seasons of the pitch-change detector, the count each one finds, and the real count beside them |
| `familiarity-2024-26.json` | [Pitch familiarity](../2026-league-pitch-familiarity.md) | the `bb familiarity 2026` coefficient table and sample counts |
| `familiarity-checks-2024-26.json` | [Pitch familiarity](../2026-league-pitch-familiarity.md) | `python -m baseball.edge.familiarity_checks`: the shuffle null (1,000 shuffles per design and pitch group) and the leave-own-game-out refits |
| `il-warning-2026.json` | [IL early warning](../2026-il-early-warning.md) | the `bb il-warning 2026` summary (added 2026-11-15): sample counts, the noise model, every outcome row's scores and intervals, every alert rule, the velocity bins and the calibration deciles |
| `skenes-checks-2026.json` | [Roster and CBA memo](../2026-roster-cba-engine.md) | `python -m baseball.roster.cases` (added 2026-11-15): the break-even grid on both prices of a win, the published surgery shares read two ways with the grid at 25% and 33%, the walk-away by place on a 2006 win curve, and the Nov. 3 cap offer against the memo's cap path |

- **What these are:** aggregates only. No pitch-level rows are in this repository.
- **What checks them:** `tests/test_report_outputs.py` reads each report and fails if a headline number no longer matches its table.
- **What isn't here yet:** the other studies' outputs. They stay in `data/` with the pitch data.
