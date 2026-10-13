import numpy as np
import pandas as pd

from baseball.edge.tells import pitcher_tells


def _pitcher(ch_shift_in=0.0, sl_shift_in=0.0, game_offsets=False, seed=1):
    """Fictional LHP: fastballs, changeups, sliders over 12 games. Shifts are planted in horizontal release."""
    rng = np.random.default_rng(seed)
    rows = []
    for g in range(12):
        off = rng.normal(0, 3) if game_offsets else 0.0   # a whole-game camera offset, in inches
        for pt, n, shift in [("FF", 40, 0.0), ("CH", 15, ch_shift_in), ("SL", 15, sl_shift_in)]:
            for _ in range(n):
                rows.append({
                    "pitcher": 1, "player_name": "Example, Fictional", "p_throws": "L", "game_year": 2025,
                    "game_pk": 100 + g, "pitch_type": pt, "pitch_name": pt,
                    "release_pos_x": (18 + off + shift + rng.normal(0, 1.5)) / 12,
                    "release_pos_z": (72 + rng.normal(0, 1.5)) / 12,
                    "release_extension": (78 + rng.normal(0, 1.5)) / 12,
                    "arm_angle": 50 + rng.normal(0, 2),
                })
    return pd.DataFrame(rows)


def test_planted_tell_is_found_and_clean_pitch_is_not():
    t = pitcher_tells(_pitcher(ch_shift_in=4.0)).set_index("pitch_type")
    assert t.loc["CH", "tell_auc"] > 0.9
    assert abs(t.loc["CH", "rel_x_arm_diff_in"] - 4.0) < 0.6
    assert t.loc["CH", "top_tell"] == "horizontal release"
    assert t.loc["SL", "tell_auc"] < 0.65


def test_game_level_camera_offsets_do_not_create_tells():
    # Big game-to-game offsets shared by every pitch must be removed by the within-game demeaning
    t = pitcher_tells(_pitcher(game_offsets=True)).set_index("pitch_type")
    assert (t["tell_auc"] < 0.65).all()


def test_right_handers_are_flipped_to_arm_side():
    p = _pitcher(ch_shift_in=4.0).assign(p_throws="R")
    p["release_pos_x"] = -p["release_pos_x"]          # RHP: arm side is negative x in Statcast
    t = pitcher_tells(p).set_index("pitch_type")
    assert t.loc["CH", "rel_x_arm_diff_in"] > 3.4


def test_no_fastball_reference_returns_empty():
    p = _pitcher()
    assert pitcher_tells(p[p["pitch_type"] != "FF"]).empty


def test_portable_tells_on_device_sessions():
    from baseball.edge.tells import PORTABLE_FEATURES

    p = _pitcher(ch_shift_in=4.0).drop(columns=["arm_angle"])
    p["game_id"] = "pen-" + p["game_pk"].astype(str)
    t = pitcher_tells(p, features=PORTABLE_FEATURES, session="game_id", min_pitches=50, min_games=3).set_index("pitch_type")
    assert t.loc["CH", "tell_auc"] > 0.9 and np.isnan(t.loc["CH", "arm_angle_diff_deg"])
