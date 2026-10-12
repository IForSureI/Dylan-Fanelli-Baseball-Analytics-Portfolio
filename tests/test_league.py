from baseball.ingest import league


def test_month_windows():
    assert league.month_window(2025, 3) == ("2025-03-01", "2025-03-31")
    assert league.month_window(2024, 2 + 2) == ("2024-04-01", "2024-04-30")
    assert league.month_window(2025, 11) == ("2025-11-01", "2025-11-10")


def test_resume_skips_cached_month(tmp_path, monkeypatch):
    import pandas as pd

    monkeypatch.setattr(league, "RAW_DIR", tmp_path)
    pd.DataFrame({"game_pk": [1, 2, 3]}).to_parquet(league.month_path(2025, 4))
    path, rows, cached = league.pull_month(2025, 4)       # must not touch the network
    assert cached and rows == 3
    assert 4 not in league.missing_months(2025) and 5 in league.missing_months(2025)


def test_nullable_numbers_become_plain_floats():
    import numpy as np
    import pandas as pd

    df = pd.DataFrame({"a": pd.array([1.5, None], dtype="Float64"), "b": pd.array([1, None], dtype="Int64"), "c": ["x", "y"]})
    out = league.to_plain_dtypes(df)
    assert out["a"].dtype == np.float64 and out["b"].dtype == np.float64 and np.isnan(out["b"][1])
    assert out["c"].dtype == object or str(out["c"].dtype).startswith("str")


def test_recent_months_cover_growing_data():
    from datetime import date

    assert league.recent_months(2026, today=date(2026, 10, 12)) == [8, 9, 10]   # ended within 45 days, or live
    assert league.recent_months(2026, today=date(2026, 7, 1)) == [5, 6, 7]
    assert league.recent_months(2025, today=date(2026, 10, 12)) == []           # a finished season never refreshes


def test_write_slim_round_trip(tmp_path, monkeypatch):
    import pandas as pd

    monkeypatch.setattr(league, "RAW_DIR", tmp_path / "raw")
    (tmp_path / "raw").mkdir()
    pd.DataFrame({"game_pk": range(500), "pitch_type": "FF", "extra_column": 1}).to_parquet(league.month_path(2026, 4))
    paths = league.write_slim(2026, rows_per_part=200)
    assert len(paths) == 3
    assert "extra_column" not in pd.read_parquet(paths[0]).columns
