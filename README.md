# Baseball

Dylan Fanelli's baseball operations workspace: the data, tools and written work I build on the way to a front office.

It's organized around the jobs a front office does: getting data in, evaluating players, developing them, building a roster, and running the business. Each analysis is a tested library function first, so the toolkit grows and later work builds on earlier work.

## The Edge Board
The edge engine runs league-wide detectors on every pitch of the last three seasons: release tells, hidden in-season changes, stuff vs. results, and validated next-season projections. `uv run bb edge 2026 && uv run bb board 2026` builds the page. A monthly job keeps it current.

## Reports
| Date | Report |
|---|---|
| 2026-10-12 | [Tarik Skubal: 2025 arsenal read, with 2024 comparison](reports/2025-skubal-arsenal.md) |

## What's built
| Area | Tools |
|---|---|
| **Data** | Statcast pulls cached locally; a DuckDB warehouse that skips duplicate pitches, adapts to new Statcast columns, and logs every load |
| **Evaluation** | Arsenal tables in pandas and SQL (cross-checked by tests), outcome metrics, usage by batter handedness, season-vs-season comparison with significance tests, movement charts |
| **Edge engine** | Release tells, hidden in-season changes, expected whiffs cross-fitted by pitcher, persistent gaps, two-season projections, league baselines, the Edge Board |
| **Familiarity** | Does a pitch wear out? Pitch-type exposure within games, across games and across pitchers; usage break-even; exposure ledger (`bb familiarity`) |
| **Development** | Planned |
| **Roster** | Planned |
| **Business** | Planned |

The roadmap is in [Issues](../../issues), and a dated record of the work is in [LOG.md](LOG.md).

## Run it
Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/IForSureI/Baseball.git ~/Baseball
cd ~/Baseball
uv sync
uv run pytest                          # 44 tests
uv run bb pull skubal tarik 2025       # Statcast pitcher-season into the warehouse
uv run bb arsenal skubal tarik 2025    # his arsenal, regular season
uv run bb compare skubal tarik 2024 2025
```

Notebooks are in `notebooks/`. Open one in VS Code, choose the `.venv` kernel, and click **Run All**.

## Data
Public data only: Statcast from Baseball Savant via [pybaseball](https://github.com/jldbc/pybaseball). Nothing in `data/` is committed, and `uv run bb db rebuild` rebuilds the warehouse from the cached pulls.
