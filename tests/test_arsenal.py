import pandas as pd
import pytest

from baseball.evaluation.arsenal import arsenal, arsenal_sql, outcomes, usage_by_hand
from baseball.ingest.sample import fictional_pitcher


def _tiny() -> pd.DataFrame:
    """Five pitches small enough to check by hand."""
    base = {"pitcher": 1, "p_throws": "R", "release_spin_rate": 2000}
    rows = [
        # pitch_type, name, velo, pfx_x, pfx_z, description
        ("FF", "4-Seam Fastball", 95.0, -0.5, 1.0, "swinging_strike"),
        ("FF", "4-Seam Fastball", 97.0, -0.5, 1.0, "called_strike"),
        ("FF", "4-Seam Fastball", 96.0, -0.5, 1.0, "foul"),
        ("FF", "4-Seam Fastball", 96.0, -0.5, 1.0, "ball"),
        ("SL", "Slider", 86.0, 0.25, 0.0, "hit_into_play"),
    ]
    return pd.DataFrame(
        [{**base, "pitch_type": t, "pitch_name": n, "release_speed": v, "pfx_x": x, "pfx_z": z, "description": d}
         for t, n, v, x, z, d in rows]
    )


def test_hand_checked_fastball():
    ff = arsenal(_tiny(), min_n=1).set_index("pitch_type").loc["FF"]
    assert ff["n"] == 4
    assert ff["usage_pct"] == 80.0          # 4 of 5 pitches
    assert ff["velo"] == 96.0
    assert ff["ivb_in"] == 12.0             # 1.0 ft x 12
    assert ff["hb_arm_in"] == 6.0           # RHP: -(-0.5 ft) x 12 = 6 in of arm-side run
    assert ff["whiff_pct"] == 50.0          # 1 whiff / 2 swings (whiff + foul)
    assert ff["csw_pct"] == 50.0            # (1 called + 1 whiff) / 4 pitches


def test_slider_glove_side_and_no_whiffs():
    sl = arsenal(_tiny(), min_n=1).set_index("pitch_type").loc["SL"]
    assert sl["hb_arm_in"] == -3.0          # glove-side break shows as negative
    assert sl["whiff_pct"] == 0.0


def test_usage_computed_before_floor():
    out = arsenal(_tiny(), min_n=2)
    assert list(out["pitch_type"]) == ["FF"]
    assert out.loc[0, "usage_pct"] == 80.0  # still out of 5, not 4


def test_pandas_and_sql_agree():
    p = fictional_pitcher()
    a = arsenal(p, min_n=20)
    b = arsenal_sql(p, min_n=20)
    assert list(a["pitch_type"]) == list(b["pitch_type"])
    # pandas rounds a trailing 5 to the even digit (33.25 -> 33.2); DuckDB rounds it up (33.3).
    # So the two can differ by one unit in the last decimal place, and no more.
    pd.testing.assert_frame_equal(a.reset_index(drop=True), b[a.columns].reset_index(drop=True), check_dtype=False, atol=0.101)


def test_rejects_multiple_pitchers():
    p = pd.concat([_tiny(), _tiny().assign(pitcher=2)])
    with pytest.raises(ValueError):
        arsenal(p)


def test_outcomes_hand_checked():
    t = _tiny().assign(
        zone=[5, 5, 12, 13, 5],                     # FF: 2 in zone, 2 out; the foul (zone 12) is a chase
        type=["S", "S", "S", "B", "X"],
        launch_speed=[None, None, None, None, 100.0],
        estimated_woba_using_speedangle=[None, None, None, None, 0.6],
        delta_run_exp=[-0.05, -0.05, -0.03, 0.04, 0.10],
        release_extension=6.5,
    )
    o = outcomes(t, min_n=1).set_index("pitch_type")
    assert o.loc["FF", "zone_pct"] == 50.0
    assert o.loc["FF", "chase_pct"] == 50.0       # 1 chase / 2 pitches out of the zone
    assert o.loc["FF", "rv_per100"] == 2.25       # -(-0.09)/4 x 100
    assert o.loc["SL", "hard_hit_pct"] == 100.0
    assert o.loc["SL", "xwoba_con"] == 0.6


def test_usage_by_hand_sums_to_100():
    u = usage_by_hand(fictional_pitcher(), min_n=1)
    assert abs(u["vs_LHH_pct"].sum() - 100) < 0.5
    assert abs(u["vs_RHH_pct"].sum() - 100) < 0.5
