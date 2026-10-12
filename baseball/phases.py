"""Statcast game_type codes and helpers to keep spring training out of season analysis."""
from __future__ import annotations

import pandas as pd

SPRING = ("S", "E")              # spring training, exhibition
REGULAR = ("R",)
POSTSEASON = ("F", "D", "L", "W")  # wild card, division series, LCS, World Series

PHASES = {"spring": SPRING, "regular": REGULAR, "postseason": POSTSEASON, "all": SPRING + REGULAR + POSTSEASON}


def phase(pitches: pd.DataFrame, which: str = "regular") -> pd.DataFrame:
    """Rows from one phase of the season. Default is the regular season."""
    if which not in PHASES:
        raise ValueError(f"phase must be one of {sorted(PHASES)}")
    return pitches[pitches["game_type"].isin(PHASES[which])]
