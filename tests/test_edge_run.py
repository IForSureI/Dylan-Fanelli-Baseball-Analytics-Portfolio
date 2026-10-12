import numpy as np
import pandas as pd

from baseball.edge import run as edge_run
from baseball.ingest import league


def _fake_season(season, seed):
    rng = np.random.default_rng(seed)
    rows = []
    for pid in range(1, 41):
        throws = "R" if pid % 2 else "L"
        sign = -1 if throws == "R" else 1
        fb = rng.normal(94, 2)
        for g in range(10):
            date = str(pd.Timestamp(f"{season}-04-01") + pd.Timedelta(days=6 * g))[:10]
            for k, (pt, n, dv, ivb) in enumerate([("FF", 50, 0, 16), ("CH", 20, -9, 6), ("SL", 20, -8, 2)]):
                for i in range(n):
                    rows.append({
                        "game_pk": season * 10000 + pid * 100 + g, "game_date": date, "game_year": season,
                        "game_type": "R", "at_bat_number": i, "pitch_number": k, "pitcher": pid,
                        "player_name": f"P{pid}", "p_throws": throws, "stand": "L" if i % 2 else "R",
                        "pitch_type": pt, "pitch_name": pt, "description": "swinging_strike" if rng.random() < 0.15 + (0.1 if pt != "FF" else 0) else "foul",
                        "type": "S", "release_speed": fb + dv + rng.normal(0, 0.8), "release_spin_rate": 2300 + rng.normal(0, 50),
                        "release_extension": 6.3 + rng.normal(0, 0.1), "release_pos_x": sign * (1.8 + (0.25 if pt == "CH" and pid < 5 else 0) + rng.normal(0, 0.12)),
                        "release_pos_z": 5.9 + rng.normal(0, 0.1), "arm_angle": 42 + rng.normal(0, 2),
                        "pfx_x": sign * 0.5 + rng.normal(0, 0.1), "pfx_z": (ivb + rng.normal(0, 1.5)) / 12,
                        "estimated_woba_using_speedangle": np.nan, "launch_speed": np.nan, "zone": 5, "balls": 0, "strikes": 0,
                    })
    return pd.DataFrame(rows)


def test_engine_runs_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(league, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(edge_run, "OUT_DIR", tmp_path / "edge")
    (tmp_path / "raw").mkdir()
    for season, seed in [(2024, 1), (2025, 2)]:
        _fake_season(season, seed).to_parquet(league.month_path(season, 4))
    s = edge_run.run(2025, log=lambda *_: None)
    assert s["counts"]["tells"] > 0 and s["counts"]["stuff_pitches"] > 0
    assert "slope_per_0.1_auc" in s["tell_cost"]["2025"]
    assert s["seasons"] == [2024, 2025] and "2024->2025" in s["validation"]
    t = pd.read_parquet(tmp_path / "edge" / "2025" / "tells_2025.parquet")
    planted = t[(t["pitcher"] < 5) & (t["pitch_type"] == "CH")]
    assert (planted["tell_auc"] > 0.85).all()          # the planted changeup tells are found
