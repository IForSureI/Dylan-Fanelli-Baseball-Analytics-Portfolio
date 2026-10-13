"""Player names and ids from the Chadwick Bureau register (public, CC BY 4.0).

Statcast identifies players by MLBAM id only. The register maps MLBAM, FanGraphs, Baseball-Reference
and Retrosheet ids to names and birth dates. `bb people` clones it (shallow) and writes
data/people/people.parquet; `names()` and `lookup()` read that file.

Grain of people.parquet: one row per person with an MLBAM id.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data" / "people"
REGISTER_URL = "https://github.com/chadwickbureau/register"
KEEP = ["key_mlbam", "key_fangraphs", "key_bbref", "key_retro", "name_first", "name_last",
        "birth_year", "birth_month", "birth_day", "mlb_played_first", "mlb_played_last"]


def refresh(out_dir: Path = DATA) -> Path:
    """Clone (or update) the register and write people.parquet. Needs network access to GitHub."""
    out_dir.mkdir(parents=True, exist_ok=True)
    repo = out_dir / "register"
    if (repo / ".git").exists():
        subprocess.run(["git", "-C", str(repo), "pull", "-q", "--ff-only"], check=True)
    else:
        subprocess.run(["git", "clone", "-q", "--depth", "1", REGISTER_URL, str(repo)], check=True)
    return build(sorted((repo / "data").glob("people-*.csv")), out_dir / "people.parquet")


def build(csv_files: list[Path], out_path: Path) -> Path:
    """Combine the register's people-*.csv files into one MLBAM-keyed table."""
    frames = [pd.read_csv(f, usecols=lambda c: c in KEEP, dtype=str, low_memory=False) for f in csv_files]
    p = pd.concat(frames, ignore_index=True).dropna(subset=["key_mlbam"])
    p["key_mlbam"] = pd.to_numeric(p["key_mlbam"], errors="coerce").astype("Int64")
    p = p.dropna(subset=["key_mlbam"]).drop_duplicates("key_mlbam")
    for c in ("birth_year", "birth_month", "birth_day", "mlb_played_first", "mlb_played_last"):
        if c in p:
            p[c] = pd.to_numeric(p[c], errors="coerce").astype("Int64")
    p["name"] = (p["name_first"].fillna("") + " " + p["name_last"].fillna("")).str.strip()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    p.to_parquet(out_path, index=False)
    return out_path


def load(path: Path | None = None) -> pd.DataFrame:
    path = Path(path or DATA / "people.parquet")
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run: uv run bb people")
    return pd.read_parquet(path)


def names(ids, path: Path | None = None) -> dict[int, str]:
    """MLBAM id -> 'First Last' for the ids given (ids not in the register map to their id as text)."""
    p = load(path).set_index("key_mlbam")["name"]
    return {int(i): p.get(int(i), str(int(i))) for i in pd.unique(pd.Series(list(ids)).dropna())}


def lookup(last: str, first: str | None = None, path: Path | None = None) -> pd.DataFrame:
    """Find people by name (case-insensitive, accents ignored). Most recent MLB players first."""
    p = load(path)

    def fold(s: pd.Series) -> pd.Series:
        return s.fillna("").str.normalize("NFKD").str.encode("ascii", "ignore").str.decode("ascii").str.lower()

    m = fold(p["name_last"]).eq(_fold1(last))
    if first:
        m &= fold(p["name_first"]).str.startswith(_fold1(first))
    return p[m].sort_values("mlb_played_last", ascending=False, na_position="last")


def _fold1(s: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower().strip()
