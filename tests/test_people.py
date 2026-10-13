"""Names register: build from register-format CSVs (fictional rows) and look up."""
import pandas as pd

from baseball.ingest import people


def test_build_names_and_lookup(tmp_path):
    csv = tmp_path / "people-0.csv"
    pd.DataFrame({
        "key_mlbam": ["100001", "100002", "", "100003"],
        "key_fangraphs": ["1", "2", "3", "4"],
        "name_first": ["José", "Jose", "Nobody", "Ana"],
        "name_last": ["Fermín", "Fermin", "Noid", "Reyes"],
        "mlb_played_last": ["2026", "", "", "2019"],
        "unused_column": ["x", "x", "x", "x"],
    }).to_csv(csv, index=False)
    out = people.build([csv], tmp_path / "people.parquet")
    p = people.load(out)
    assert len(p) == 3                                   # the row without an MLBAM id is dropped
    assert people.names([100001, 999], out) == {100001: "José Fermín", 999: "999"}
    hits = people.lookup("fermin", "jose", out)          # accents ignored, most recent player first
    assert hits["key_mlbam"].tolist() == [100001, 100002]
