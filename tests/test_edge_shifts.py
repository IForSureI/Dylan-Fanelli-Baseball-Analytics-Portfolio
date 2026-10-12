import numpy as np
import pandas as pd

from baseball.edge.shifts import pitcher_shifts


def _season(sl_ivb_jump=0.0, all_velo_jump=0.0, jump_game=10, games=20, seed=3):
    """Fictional RHP, 20 starts. Planted: slider IVB change and/or a velo change on every pitch."""
    rng = np.random.default_rng(seed)
    rows = []
    for g in range(games):
        after = g >= jump_game
        for pt, n, velo, ivb in [("FF", 45, 95.0, 16.0), ("SL", 25, 86.0, 2.0), ("CH", 20, 87.0, 7.0)]:
            for i in range(n):
                v = velo + (all_velo_jump if after else 0) + rng.normal(0, 0.8)
                z = ivb + (sl_ivb_jump if (after and pt == "SL") else 0) + rng.normal(0, 1.5)
                rows.append({
                    "pitcher": 7, "player_name": "Example, Fictional", "game_year": 2025, "p_throws": "R",
                    "game_pk": 500 + g, "game_date": str(pd.Timestamp("2025-04-01") + pd.Timedelta(days=5 * g))[:10],
                    "pitch_type": pt, "pitch_name": pt, "release_speed": v, "pfx_z": z / 12,
                    "pfx_x": -0.5 + rng.normal(0, 0.1), "release_spin_rate": 2300 + rng.normal(0, 50),
                    "arm_angle": 45 + rng.normal(0, 2),
                    "description": "swinging_strike" if rng.random() < 0.15 else "ball",
                    "type": "S", "estimated_woba_using_speedangle": np.nan,
                })
    return pd.DataFrame(rows)


def test_finds_isolated_slider_change_on_the_right_date():
    s = pitcher_shifts(_season(sl_ivb_jump=-4.0))
    sl = s[(s["pitch_type"] == "SL") & (s["metric"].str.startswith("induced"))]
    assert len(sl) == 1
    row = sl.iloc[0]
    assert row["split_date"] == "2025-05-21"          # game index 10 = Apr 1 + 50 days
    assert abs(row["shift"] + 4.0) < 0.5
    assert row["scope"] == "this pitch only"


def test_shared_velocity_jump_is_labeled_all_pitches():
    s = pitcher_shifts(_season(all_velo_jump=2.0))
    velo = s[s["metric"].str.startswith("velocity")]
    assert len(velo) >= 1
    assert set(velo["scope"]) == {"all pitches"}


def test_quiet_season_finds_nothing():
    assert pitcher_shifts(_season()).empty


def test_relabel_is_flagged():
    # Slider "changes" into the curveball's exact shape: that's a label moving, not a new pitch
    rows = []
    for g in range(20):
        date = str(pd.Timestamp("2025-04-01") + pd.Timedelta(days=5 * g))[:10]
        after = g >= 10
        for pt, n, velo, ivb in [("FF", 40, 95.0, 16.0), ("SL", 20, 80.0 if after else 86.0, -8.0 if after else 2.0), ("CU", 20, 80.0, -8.0)]:
            for i in range(n):
                rows.append({"pitcher": 9, "player_name": "Example, Fictional", "game_year": 2025, "p_throws": "R",
                             "game_pk": 700 + g, "game_date": date, "pitch_type": pt, "pitch_name": pt,
                             "release_speed": velo + 0.3 * ((i % 5) - 2), "pfx_z": (ivb + 0.5 * ((i % 3) - 1)) / 12, "pfx_x": -0.5,
                             "release_spin_rate": 2300.0 + i, "arm_angle": 45.0, "description": "ball", "type": "B",
                             "estimated_woba_using_speedangle": np.nan})
    s = pitcher_shifts(pd.DataFrame(rows))
    sl = s[s["pitch_type"] == "SL"]
    assert len(sl) and (sl["label_check"] == "possible relabel from CU").all()
