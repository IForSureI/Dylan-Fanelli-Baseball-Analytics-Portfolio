"""A small runner for the named SQL queries in sql/.

Each query is one file, sql/<name>.sql, that starts with a header comment: the question it answers, its
inputs, its output columns and the definitions it uses. This module

1. registers the pitch-level parquet files as a view named `pitches` and the player register as `people`,
2. reads the query's inputs from its header, fills defaults and checks for missing or unknown parameters,
3. runs it in DuckDB and returns a pandas DataFrame.

    from baseball.sqlkit import run
    run("arsenal_by_count", pitcher=669373, season=2026)

Data: `pitches` reads data/seq/seq_<season>_*.parquet (every Statcast pitch, built by `bb seq`) and
`people` reads data/people/people.parquet (`bb people`). Neither is committed; tests build their own
fictional files and pass `data_dir`.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"
DATA_DIR = ROOT / "data"

# Whole-number columns. Some seasons' files store them as FLOAT, which would widen every season to
# DOUBLE in the union; the view casts them back so ids print and join as integers.
INT_COLUMNS = (
    "game_pk", "game_year", "inning", "outs_when_up", "at_bat_number", "pitch_number", "pitcher", "batter",
    "balls", "strikes", "on_1b", "on_2b", "on_3b", "zone", "n_thruorder_pitcher", "woba_denom",
    "launch_speed_angle",
)


class _Required:
    def __repr__(self) -> str:
        return "REQUIRED"


REQUIRED = _Required()   # marker for an input with no default

_SECTION = re.compile(r"^--\s?(\w[\w ]*):")              # "-- Inputs:", "-- Output: one row per ..."
_INPUT = re.compile(r"^--\s+\$(\w+)\s+(.*)$")             # "--   $season   season (required)"
_COLUMN = re.compile(r"^-- {3}([a-z_][a-z0-9_]*)\s")     # "--   n          pitches in the cell"
_DEFAULT = re.compile(r"\(default\s+('[^']*'|[^\s),=]+)")     # "(default 20)", "(default NULL = league)"
_PARAM = re.compile(r"\$([A-Za-z_]\w*)")


def queries() -> list[str]:
    """Names of every query in sql/."""
    return sorted(p.stem for p in SQL_DIR.glob("*.sql"))


def _path(name: str) -> Path:
    path = SQL_DIR / f"{name}.sql"
    if not path.exists():
        raise KeyError(f"No query named {name!r}. Available: {', '.join(queries())}")
    return path


def _literal(text: str):
    text = text.strip()
    if text.upper() == "NULL":
        return None
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text


def describe(name: str) -> dict:
    """The query's header, parsed: question, inputs {name: default or REQUIRED}, output column names."""
    text = _path(name).read_text()
    header = []
    for line in text.splitlines():
        if not line.startswith("--"):
            break
        header.append(line)
    question, inputs, columns, section = [], {}, [], None
    for line in header:
        m = _SECTION.match(line)
        if m:
            section = m.group(1).split()[0].lower()
            rest = line[m.end():].strip()
            if section == "question" and rest:
                question.append(rest)
            continue
        if section == "question":
            question.append(line.lstrip("- ").strip())
        elif section == "inputs" and (m := _INPUT.match(line)):
            d = _DEFAULT.search(m.group(2))
            inputs[m.group(1)] = _literal(d.group(1)) if d else REQUIRED
        elif section == "output" and (m := _COLUMN.match(line)):
            columns.append(m.group(1))
    return {"name": name, "question": " ".join(q for q in question if q), "inputs": inputs, "columns": columns,
            "header": "\n".join(header)}


def _parameters_used(sql: str) -> set[str]:
    body = "\n".join(line.split("--", 1)[0] for line in sql.splitlines())   # parameters in comments don't count
    return set(_PARAM.findall(body))


def _quote(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def connect(data_dir: str | Path | None = None, seasons: list[int] | None = None) -> duckdb.DuckDBPyConnection:
    """An in-memory DuckDB connection with two views: `pitches` (the seq parquet files, optionally only some
    seasons) and `people` (the player register). Views read the files lazily: DuckDB only pulls the columns
    and row groups a query needs."""
    data_dir = Path(data_dir) if data_dir else DATA_DIR
    pattern = [f"seq_{s}_*.parquet" for s in seasons] if seasons else ["seq_*.parquet"]
    files = sorted(f for p in pattern for f in (data_dir / "seq").glob(p))
    if not files:
        raise FileNotFoundError(f"No pitch files matching {pattern} in {data_dir / 'seq'}. Build them with `bb seq <season>`.")
    con = duckdb.connect()
    source = f"read_parquet([{', '.join(map(_quote, files))}], union_by_name = true)"
    have = {r[0] for r in con.execute(f"SELECT column_name FROM (DESCRIBE SELECT * FROM {source})").fetchall()}
    casts = ", ".join(f"CAST({c} AS BIGINT) AS {c}" for c in INT_COLUMNS if c in have)
    con.execute(f"CREATE VIEW pitches AS SELECT * {f'REPLACE ({casts})' if casts else ''} FROM {source}")
    people = data_dir / "people" / "people.parquet"
    if people.exists():
        con.execute(f"CREATE VIEW people AS SELECT * FROM read_parquet({_quote(people)})")
    else:   # names are optional: queries LEFT JOIN people, so an empty view just leaves names NULL
        con.execute("CREATE VIEW people AS SELECT NULL::BIGINT AS key_mlbam, NULL::VARCHAR AS name WHERE false")
    return con


def bind(name: str, **params) -> tuple[str, dict]:
    """The query text and the full parameter dict (defaults filled). Raises on missing or unknown inputs."""
    sql = _path(name).read_text()
    declared = describe(name)["inputs"]
    used = _parameters_used(sql)
    if used != set(declared):
        raise ValueError(f"{name}.sql: header inputs {sorted(declared)} don't match parameters used {sorted(used)}")
    unknown = set(params) - set(declared)
    if unknown:
        raise TypeError(f"{name} has no input(s) {sorted(unknown)}; its inputs are {sorted(declared)}")
    values = {k: params.get(k, v) for k, v in declared.items()}
    missing = [k for k, v in values.items() if v is REQUIRED]
    if missing:
        raise TypeError(f"{name} needs {missing}")
    return sql, values


def run(name: str, con: duckdb.DuckDBPyConnection | None = None, *, data_dir: str | Path | None = None,
        **params) -> pd.DataFrame:
    """Run sql/<name>.sql with keyword parameters and return the result.

    Pass `con` (from connect()) to reuse one connection across several queries; otherwise a connection over
    every season in data_dir is opened and closed for this call."""
    sql, values = bind(name, **params)
    own = con is None
    con = connect(data_dir) if own else con
    try:
        return con.execute(sql, values).df()
    finally:
        if own:
            con.close()
