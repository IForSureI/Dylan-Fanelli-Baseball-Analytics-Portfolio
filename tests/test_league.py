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
