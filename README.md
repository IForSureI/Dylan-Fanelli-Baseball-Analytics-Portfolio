# Baseball

Baseball analytics workspace: pulling Statcast pitch data, turning it into scouting tables, and checking the work in both Python and SQL.

## What's here

| Path | What it does |
|---|---|
| `notebooks/01_arsenal.ipynb` | Pulls one pitcher's season, checks the data, and builds his arsenal table and a movement plot |
| `baseball/statcast.py` | Statcast pulls through `pybaseball`, cached to `data/raw/` as Parquet so each pull happens once |
| `baseball/arsenal.py` | The arsenal table built twice, in pandas and in DuckDB SQL, with every metric defined |
| `baseball/sample.py` | Fictional Statcast-shaped data for offline work and tests (not real data) |
| `tests/` | Hand-checked arithmetic, plus a test that the pandas and SQL versions agree |

## The arsenal table

One row per pitch type for one pitcher:

| Column | Meaning |
|---|---|
| `usage_pct` | Share of all his pitches, computed before small pitch types are dropped |
| `velo`, `spin` | Mean release speed (mph) and spin rate (rpm) |
| `ivb_in` | Induced vertical break, inches |
| `hb_arm_in` | Horizontal break toward his arm side, inches (negative = glove side) |
| `whiff_pct` | Whiffs per swing |
| `csw_pct` | Called strikes plus whiffs, per pitch |

## Setup

Requires [uv](https://docs.astral.sh/uv/) (`brew install uv`).

```bash
git clone https://github.com/IForSureI/Baseball.git ~/Baseball
cd ~/Baseball
uv sync              # creates .venv and installs everything in uv.lock
uv run pytest        # 5 tests, about a second
code .               # open in VS Code
```

In VS Code, open `notebooks/01_arsenal.ipynb`, choose the `.venv` kernel when asked, and click **Run All**. To look at a different pitcher, change `PITCHER` and `SEASON` in the second cell.

## Data

Data comes from Baseball Savant through [pybaseball](https://github.com/jldbc/pybaseball). Nothing in `data/` is committed: pulls are large and can be re-run. If Savant is down, set `USE_SAMPLE = True` in the notebook to run on fictional data.
