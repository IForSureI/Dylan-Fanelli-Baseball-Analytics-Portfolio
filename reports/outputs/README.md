# Saved outputs

Small tables behind three reports, so a reader can check the headline numbers without the pitch data. Added 2026-11-14.

| File | Report | Built from |
|---|---|---|
| `bullpen-2026.json` | [Bullpen memo](../2026-bullpen-acquisition-memo.md) | `baseball.roster.bullpen_case.money()` on the relief-season tables: the market line, each price and its interval, break-even prices, the qualifying-offer cost, landing odds, workload retention and the availability case |
| `edge-2026.json` | [Edge Board](../2026-edge-board.md) | the `bb edge 2026` summary, plus `validate_holdout()` on the saved pitch tables and counts from the saved pitch-change table |
| `familiarity-2024-26.json` | [Pitch familiarity](../2026-league-pitch-familiarity.md) | the `bb familiarity 2026` coefficient table and sample counts |

- **What these are:** aggregates only. No pitch-level rows are in this repository.
- **What checks them:** `tests/test_report_outputs.py` reads each report and fails if a headline number no longer matches its table.
- **What isn't here yet:** the other studies' outputs. They stay in `data/` with the pitch data.
