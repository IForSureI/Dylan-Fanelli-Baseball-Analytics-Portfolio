"""League-wide Statcast pulls: every pitch of a season, month by month.

A full season is roughly 700,000 pitches. Pulling it month by month makes the job resumable:
each finished month is saved to data/raw/league_<season>_<MM>.parquet and skipped next time,
so an interrupted pull (laptop asleep, Savant timeout) picks up where it stopped.
"""
from __future__ import annotations

import calendar
from datetime import date
from pathlib import Path

import pandas as pd

from baseball.ingest.statcast import RAW_DIR

SEASON_MONTHS = range(3, 12)  # March (spring + opening) through November (World Series)


def month_path(season: int, month: int) -> Path:
    return RAW_DIR / f"league_{season}_{month:02d}.parquet"


def month_window(season: int, month: int) -> tuple[str, str]:
    last = calendar.monthrange(season, month)[1]
    end = date(season, month, last)
    if month == 11:
        end = date(season, 11, 10)  # nothing is played after the World Series
    return date(season, month, 1).isoformat(), end.isoformat()


def pull_month(season: int, month: int, refresh: bool = False) -> tuple[Path, int, bool]:
    """Pull one month of every pitch. Returns (path, rows, was_cached)."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = month_path(season, month)
    if path.exists() and not refresh:
        return path, len(pd.read_parquet(path, columns=["game_pk"])), True

    from pybaseball import cache, statcast

    cache.enable()
    start, end = month_window(season, month)
    df = statcast(start_dt=start, end_dt=end, verbose=False, parallel=True)
    if df is None:
        df = pd.DataFrame()
    df.to_parquet(path, index=False)
    return path, len(df), False


def recent_months(season: int, today: date | None = None, days: int = 45) -> list[int]:
    """Months whose data may still be growing: any month that ended within `days` of today, or hasn't ended.
    A scheduled update re-pulls these so partial months fill in."""
    today = today or date.today()
    out = []
    for m in SEASON_MONTHS:
        start, end = (date.fromisoformat(d) for d in month_window(season, m))
        if start <= today and (today - end).days <= days:
            out.append(m)
    return out


def write_slim(season: int, rows_per_part: int = 200_000) -> list[Path]:
    """Write the slim copy of a season (engine columns only, ~3 MB parts) from the monthly files."""
    from baseball.edge.run import COLUMNS

    parts = [pd.read_parquet(month_path(season, m)) for m in SEASON_MONTHS if month_path(season, m).exists()]
    parts = [p[[c for c in COLUMNS if c in p.columns]] for p in parts if len(p)]
    if not parts:
        raise FileNotFoundError(f"No monthly files for {season}.")
    df = pd.concat(parts, ignore_index=True)
    out_dir = RAW_DIR.parent / "slim"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob(f"league_{season}_part*.parquet"):
        old.unlink()
    paths = []
    for i, start in enumerate(range(0, len(df), rows_per_part)):
        path = out_dir / f"league_{season}_part{i}.parquet"
        df.iloc[start:start + rows_per_part].to_parquet(path, index=False, compression="zstd")
        paths.append(path)
    return paths


def missing_months(season: int) -> list[int]:
    return [m for m in SEASON_MONTHS if not month_path(season, m).exists()]


def slim_parts(season: int) -> list[Path]:
    """The slim copy of a season: only the columns the engine uses, split into ~3 MB parts that are
    quick to move between machines."""
    return sorted((RAW_DIR.parent / "slim").glob(f"league_{season}_part*.parquet"))


def load_season(season: int, columns: list[str] | None = None) -> pd.DataFrame:
    """Every cached month of a season as one frame (read straight from the files, no warehouse lock).
    Falls back to the slim single-file copy (data/slim/) when the monthly files aren't present."""
    parts = [pd.read_parquet(month_path(season, m), columns=columns) for m in SEASON_MONTHS if month_path(season, m).exists()]
    parts = [p for p in parts if len(p)]
    if not parts:
        parts = [pd.read_parquet(p, columns=columns) for p in slim_parts(season)]
    if not parts:
        raise FileNotFoundError(f"No league data cached for {season}. Run: uv run bb pull-league {season}")
    return to_plain_dtypes(pd.concat(parts, ignore_index=True))


def to_plain_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """pybaseball returns pandas nullable numbers (Float64, Int64) whose missing values are pd.NA,
    which numpy and scikit-learn can't handle. Convert them to float64 with NaN."""
    for col in df.columns:
        if pd.api.types.is_extension_array_dtype(df[col]) and pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].astype("float64")
    return df
