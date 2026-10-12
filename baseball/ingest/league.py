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


def missing_months(season: int) -> list[int]:
    return [m for m in SEASON_MONTHS if not month_path(season, m).exists()]


def load_season(season: int, columns: list[str] | None = None) -> pd.DataFrame:
    """Every cached month of a season as one frame (read straight from the files, no warehouse lock)."""
    parts = [pd.read_parquet(month_path(season, m), columns=columns) for m in SEASON_MONTHS if month_path(season, m).exists()]
    parts = [p for p in parts if len(p)]
    if not parts:
        raise FileNotFoundError(f"No league data cached for {season}. Run: uv run bb pull-league {season}")
    return pd.concat(parts, ignore_index=True)
