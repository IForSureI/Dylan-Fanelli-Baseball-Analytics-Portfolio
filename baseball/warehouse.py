"""The warehouse: one DuckDB database that every pull lands in, so the data keeps growing.

Tables
- pitches : every Statcast pitch ever pulled, one row per pitch,
            keyed by (game_pk, at_bat_number, pitch_number). Re-loading the same pitches is a no-op.
- pulls   : provenance, one row per load: when, what, how many rows were new.

The database file (data/warehouse.duckdb) is not committed. Rebuild it any time from the cached
pulls in data/raw/ with `bb db rebuild`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "warehouse.duckdb"
KEY = ("game_pk", "at_bat_number", "pitch_number")


def connect(path: str | Path | None = None) -> duckdb.DuckDBPyConnection:
    path = Path(path) if path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS pulls (
            loaded_at   TIMESTAMP,
            source      VARCHAR,
            description VARCHAR,
            rows_in     INTEGER,
            rows_new    INTEGER
        )
        """
    )
    return con


def _table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    return con.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?", [name]).fetchone()[0] > 0


def load_pitches(con: duckdb.DuckDBPyConnection, df: pd.DataFrame, source: str, description: str) -> int:
    """Add Statcast pitches to the warehouse, skipping any already there. Returns the number of new rows."""
    missing = [k for k in KEY if k not in df.columns]
    if missing:
        raise ValueError(f"Pitch data is missing key columns {missing}.")
    df = df.drop_duplicates(subset=list(KEY))
    con.register("incoming", df)

    if not _table_exists(con, "pitches"):
        con.execute("CREATE TABLE pitches AS SELECT * FROM incoming LIMIT 0")

    # Statcast adds columns over the years (bat tracking, arm angle). Add any new ones instead of failing.
    have = {r[0] for r in con.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'pitches'").fetchall()}
    types = dict(con.execute("SELECT column_name, column_type FROM (DESCRIBE incoming)").fetchall())
    for col in df.columns:
        if col not in have:
            con.execute(f'ALTER TABLE pitches ADD COLUMN "{col}" {types[col]}')

    before = con.execute("SELECT COUNT(*) FROM pitches").fetchone()[0]
    join = " AND ".join(f"p.{k} = i.{k}" for k in KEY)
    con.execute(f"INSERT INTO pitches BY NAME SELECT i.* FROM incoming i WHERE NOT EXISTS (SELECT 1 FROM pitches p WHERE {join})")
    new = con.execute("SELECT COUNT(*) FROM pitches").fetchone()[0] - before

    con.execute(
        "INSERT INTO pulls VALUES (?, ?, ?, ?, ?)",
        [datetime.now(timezone.utc).replace(tzinfo=None), source, description, len(df), new],
    )
    con.unregister("incoming")
    return new


def find_pitcher(con: duckdb.DuckDBPyConnection, last: str, first: str) -> int | None:
    """MLBAM id of a pitcher already in the warehouse, matched on Statcast's "Last, First" name. None if absent."""
    if not _table_exists(con, "pitches"):
        return None
    rows = con.execute(
        "SELECT DISTINCT pitcher FROM pitches WHERE lower(player_name) = lower(?)", [f"{last}, {first}"]
    ).fetchall()
    if len(rows) > 1:
        raise LookupError(f"More than one pitcher named {first} {last} in the warehouse: {[r[0] for r in rows]}. Use the id.")
    return rows[0][0] if rows else None


def pitcher_pitches(con: duckdb.DuckDBPyConnection, pitcher_id: int, season: int | None = None) -> pd.DataFrame:
    """All warehouse pitches for one pitcher, optionally one season."""
    sql = "SELECT * FROM pitches WHERE pitcher = ?"
    params: list = [pitcher_id]
    if season is not None:
        sql += " AND game_year = ?"
        params.append(season)
    return con.execute(sql + " ORDER BY game_date, game_pk, at_bat_number, pitch_number", params).df()


def summary(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """What is in the warehouse: one row per pitcher-season."""
    if not _table_exists(con, "pitches"):
        return pd.DataFrame()
    return con.execute(
        """
        SELECT player_name, pitcher, game_year AS season,
               COUNT(*) AS pitches,
               COUNT(DISTINCT game_pk) AS games,
               COUNT(*) FILTER (WHERE game_type = 'R') AS regular_season_pitches,
               MIN(game_date) AS first_date, MAX(game_date) AS last_date
        FROM pitches
        GROUP BY ALL
        ORDER BY season DESC, player_name
        """
    ).df()


def rebuild(con: duckdb.DuckDBPyConnection, raw_dir: Path | None = None) -> int:
    """Reload every cached pull in data/raw/ into the warehouse. Returns total new rows."""
    raw_dir = raw_dir or DATA_DIR / "raw"
    total = 0
    for path in sorted(raw_dir.glob("*.parquet")):
        total += load_pitches(con, pd.read_parquet(path), source="cache", description=path.name)
    return total
