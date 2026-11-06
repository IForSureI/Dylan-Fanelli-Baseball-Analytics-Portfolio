# Data dictionary

Public data only. Raw data is pulled locally and never committed (`data/` is in `.gitignore`); every result rebuilds from it with the `bb` toolkit.

## Sources

| Source | What it covers | Used in | How it is pulled |
|---|---|---|---|
| Statcast via Baseball Savant | Every regular-season pitch, 2024-2026 (2.14 million), with pitch physics, outcomes, run value and bat tracking | Nearly every pitch and hitter study | `bb pull-league <season>`, `bb seq <season>` |
| Chadwick Bureau register | Player names and IDs across systems | Names in every report | `bb people` |
| MLB Stats API | Transactions, rosters, games | Trade network and roster work | Through the `bb` trade and roster tools |
| Baseball-Reference | WAR and front-office listings | GM tree, front-office ties, valuations | Cited and dated in each report |
| Retrosheet | Historical game and transaction records | Cited where used | Cited and dated in each report |
| Public reporting (cited, dated) | Contracts, transactions, executive careers | Memos, arbitration briefs, GM tree | Linked in each report |

## Key Statcast columns

| Column | Meaning |
|---|---|
| `pitch_type`, `pitch_name` | Statcast pitch classification |
| `release_speed`, `release_spin_rate`, `release_extension` | Velocity (mph), spin (rpm), extension (ft) |
| `pfx_x`, `pfx_z` | Horizontal and vertical movement (ft; ×12 for inches) |
| `plate_x`, `plate_z` | Location at the plate |
| `description`, `events` | Pitch result and plate-appearance result |
| `delta_run_exp` | Change in run expectancy on the pitch, from the offense's side |
| `estimated_woba_using_speedangle` | xwOBA on batted balls |
| `bat_speed`, `swing_length` | Bat tracking (2024 on) |
| `attack_angle`, `attack_direction`, `swing_path_tilt` | Bat tracking (2025 on) |
| `game_type` | `R` for regular season; analyses default to the regular season |

## Conventions
- Regular season only unless a report says otherwise.
- Seasons are pooled only with standard errors clustered by player (pitcher, batter or both, as each report states).
- Dollars are stated with their year and discount rate in each memo.
- Every number in a report traces to a saved output that the separate review pass checks.
