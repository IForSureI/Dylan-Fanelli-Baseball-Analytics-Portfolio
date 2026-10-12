"""Pull Statcast pitch data with pybaseball and cache it locally as Parquet.

Pulls are slow and Baseball Savant rate-limits, so every pull is saved to data/raw/ and
re-used on the next run. Delete the file to force a fresh pull.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
RAW_DIR = DATA_DIR / "raw"


def lookup_mlbam(last: str, first: str) -> int:
    """MLBAM id for a player by name (uses the Chadwick register through pybaseball)."""
    from pybaseball import playerid_lookup

    hits = playerid_lookup(last, first)
    hits = hits.dropna(subset=["key_mlbam"])
    if hits.empty:
        raise LookupError(f"No MLBAM id found for {first} {last}.")
    if len(hits) > 1:
        # Several players share the name: take the one who played most recently
        hits = hits.sort_values("mlb_played_last", ascending=False)
    return int(hits.iloc[0]["key_mlbam"])


def pitcher_season(mlbam_id: int, season: int, refresh: bool = False) -> pd.DataFrame:
    """All Statcast pitches thrown by one pitcher in one season.

    Includes spring training and the postseason; filter with baseball.phases.phase() before analysis.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"pitcher_{mlbam_id}_{season}.parquet"
    if path.exists() and not refresh:
        return pd.read_parquet(path)

    from pybaseball import cache, statcast_pitcher

    cache.enable()
    df = statcast_pitcher(f"{season}-03-01", f"{season}-11-30", player_id=mlbam_id)
    if df is None or df.empty:
        raise RuntimeError(
            f"Statcast returned no rows for pitcher {mlbam_id} in {season}. "
            "Check the id and season, or try again later if Baseball Savant is slow."
        )
    df.to_parquet(path, index=False)
    return df
