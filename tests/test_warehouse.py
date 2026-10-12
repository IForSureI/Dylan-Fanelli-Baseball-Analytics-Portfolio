import pandas as pd

from baseball import warehouse
from baseball.ingest.sample import fictional_pitcher
from baseball.phases import phase


def test_load_is_idempotent(tmp_path):
    con = warehouse.connect(tmp_path / "w.duckdb")
    p = fictional_pitcher(n_pitches=500)
    assert warehouse.load_pitches(con, p, "sample", "first load") == 500
    assert warehouse.load_pitches(con, p, "sample", "same pitches again") == 0
    assert con.execute("SELECT COUNT(*) FROM pulls").fetchone()[0] == 2


def test_new_columns_are_added(tmp_path):
    con = warehouse.connect(tmp_path / "w.duckdb")
    p = fictional_pitcher(n_pitches=200)
    warehouse.load_pitches(con, p.drop(columns=["release_extension"]), "sample", "old schema")
    more = fictional_pitcher(n_pitches=200, pitcher_id=999002)
    assert warehouse.load_pitches(con, more, "sample", "new column") == 200
    got = warehouse.pitcher_pitches(con, 999002)
    assert got["release_extension"].notna().all()


def test_summary_and_rebuild(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    fictional_pitcher(n_pitches=300).to_parquet(raw / "pitcher_999001_2025.parquet")
    con = warehouse.connect(tmp_path / "w.duckdb")
    assert warehouse.rebuild(con, raw) == 300
    s = warehouse.summary(con)
    assert s.loc[0, "pitches"] == 300 and s.loc[0, "season"] == 2025


def test_phase_filter():
    p = pd.DataFrame({"game_type": ["S", "R", "R", "D", "W"]})
    assert len(phase(p)) == 2
    assert len(phase(p, "postseason")) == 2
    assert len(phase(p, "spring")) == 1


def test_find_pitcher_by_name(tmp_path):
    con = warehouse.connect(tmp_path / "w.duckdb")
    assert warehouse.find_pitcher(con, "example", "fictional") is None   # empty warehouse
    warehouse.load_pitches(con, fictional_pitcher(n_pitches=100), "sample", "t")
    assert warehouse.find_pitcher(con, "Example", "Fictional") == 999001
    assert warehouse.find_pitcher(con, "nobody", "here") is None
