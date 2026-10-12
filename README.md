# Baseball

Dylan Fanelli's baseball operations workspace: the data, tools and written work I build on the way to a front office.

It's organized around the jobs a front office does: getting data in, evaluating players, developing them, building a roster, and running the business. Each analysis is a tested library function first, so the toolkit grows and later work builds on earlier work.

## Reports
| Date | Report |
|---|---|
| 2026-10-12 | [Tarik Skubal: 2025 arsenal read](reports/2025-skubal-arsenal.md) |

## What's built
| Area | Tools |
|---|---|
| **Data** | Statcast pulls cached locally; a DuckDB warehouse that skips duplicate pitches, adapts to new Statcast columns, and logs every load |
| **Evaluation** | Arsenal tables in pandas and SQL (cross-checked by tests), outcome metrics, usage by batter handedness, movement charts |
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
uv run pytest                          # 12 tests
uv run bb pull skubal tarik 2025       # Statcast pitcher-season into the warehouse
uv run bb arsenal skubal tarik 2025    # his arsenal, regular season
```

Notebooks are in `notebooks/`. Open one in VS Code, choose the `.venv` kernel, and click **Run All**.

## Data
Public data only: Statcast from Baseball Savant via [pybaseball](https://github.com/jldbc/pybaseball). Nothing in `data/` is committed, and `uv run bb db rebuild` rebuilds the warehouse from the cached pulls.
