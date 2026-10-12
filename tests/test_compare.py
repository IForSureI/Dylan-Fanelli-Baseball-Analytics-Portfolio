import pandas as pd

from baseball.evaluation.compare import compare_arsenals
from baseball.ingest.sample import fictional_pitcher


def _pitches(pitch_type, n_whiff, n_contact, n_take, velo):
    rows = (["swinging_strike"] * n_whiff) + (["foul"] * n_contact) + (["ball"] * n_take)
    return pd.DataFrame(
        {"pitcher": 1, "p_throws": "R", "pitch_type": pitch_type, "pitch_name": pitch_type,
         "release_speed": velo, "release_spin_rate": 2000, "pfx_x": -0.5, "pfx_z": 1.0, "description": rows}
    )


def test_hand_checked_real_change():
    before = _pitches("FF", 30, 70, 50, 95.0)    # 30% whiff on 100 swings
    after = _pitches("FF", 50, 50, 50, 96.0)     # 50% whiff on 100 swings
    out = compare_arsenals(before, after)
    r = out["results"].set_index("pitch_type").loc["FF"]
    assert r["whiff_pct_a"] == 30.0 and r["whiff_pct_b"] == 50.0 and r["whiff_chg"] == 20.0
    assert r["p_value"] == 0.004 and r["verdict"] == "real change"
    s = out["shape"].set_index("pitch_type").loc["FF"]
    assert s["velo_chg"] == 1.0


def test_small_sample_verdict():
    out = compare_arsenals(_pitches("CU", 2, 3, 20, 80.0), _pitches("CU", 9, 1, 20, 80.0))
    assert out["results"].loc[0, "verdict"] == "small sample"


def test_pitch_only_in_one_season_is_kept():
    before = _pitches("FF", 30, 70, 50, 95.0)
    after = pd.concat([_pitches("FF", 30, 70, 50, 95.0), _pitches("SL", 10, 20, 10, 86.0)])
    out = compare_arsenals(before, after)
    sl = out["shape"].set_index("pitch_type").loc["SL"]
    assert pd.isna(sl["usage_pct_a"]) and sl["usage_pct_b"] > 0


def test_same_sample_is_noise():
    p = fictional_pitcher()
    out = compare_arsenals(p, p)
    assert (out["results"]["whiff_chg"] == 0).all()
    assert set(out["results"]["verdict"]) == {"noise"}
