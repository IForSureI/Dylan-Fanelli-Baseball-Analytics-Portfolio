"""Delivery and release profile, on FICTIONAL pitches.

Every pitcher, game and pitch here is fictional (pitcher ids 1-3). The arithmetic behind each expected number
is in the comment beside it.
"""
import math

import numpy as np
import pandas as pd
import pytest

from baseball.evaluation import delivery as D


def _pitch(pitcher=1, hand="L", pt="SI", velo=95.0, game=10, ab=1, num=1, balls=0, strikes=0, desc="ball",
           zone=5, plate_z=2.5, pfx_x=1.0, pfx_z=0.5, rel_x=2.0, rel_z=6.0, ext=6.0, arm=40.0, gtype="R", stand="R"):
    return dict(pitcher=pitcher, p_throws=hand, pitch_type=pt, release_speed=velo, game_pk=game, at_bat_number=ab,
                pitch_number=num, balls=balls, strikes=strikes, description=desc, zone=zone, plate_z=plate_z,
                pfx_x=pfx_x, pfx_z=pfx_z, release_pos_x=rel_x, release_pos_z=rel_z, release_extension=ext,
                arm_angle=arm, release_spin_rate=2200.0, game_type=gtype, stand=stand,
                vy0=-130.0, ay=26.0, vz0=-5.0, az=-15.0)


def test_vaa_hand_checked():
    # d = 50 - 17/12 = 48.5833; vy0^2 - 2*ay*d = 16900 - 52*48.5833 = 14373.667 -> vy_f = -119.8902
    # t = (-119.8902 + 130) / 26 = 0.388837; vz_f = -5 - 15*0.388837 = -10.83256
    # VAA = -atan(-10.83256 / -119.8902) = -atan(0.090354) = -5.1629 degrees
    df = pd.DataFrame([_pitch()])
    assert D.vaa(df).iloc[0] == pytest.approx(-5.1629, abs=1e-3)


def test_vaa_flatter_with_less_downward_velocity():
    a = pd.DataFrame([_pitch()])
    b = a.assign(vz0=-3.0)            # less downward velocity at 50 ft -> flatter arrival
    assert D.vaa(b).iloc[0] > D.vaa(a).iloc[0]


def test_arm_side_sign_flips_for_right_handers():
    rows = [_pitch(pitcher=1, hand="L", pfx_x=1.0, rel_x=2.0), _pitch(pitcher=2, hand="R", pfx_x=-1.0, rel_x=-2.0)]
    p = D._prep(pd.DataFrame(rows))
    # LHP: +1.0 ft * 12 = +12 in arm side; RHP: -1.0 ft * 12 * -1 = +12 in arm side. Release sides both +2.0 ft.
    assert list(p["hb_arm_in"]) == [12.0, 12.0]
    assert list(p["rel_x_arm_ft"]) == [2.0, 2.0]


def _outing():
    # One fictional pitcher, one game, five regular-season pitches plus one spring pitch that must be dropped.
    return pd.DataFrame([
        _pitch(pt="SI", velo=99.0, num=1, desc="called_strike", zone=5, plate_z=2.5, arm=40, rel_z=6.0),
        _pitch(pt="SI", velo=98.0, num=2, balls=0, strikes=1, desc="swinging_strike", zone=5, plate_z=3.2, arm=42, rel_z=6.2),
        _pitch(pt="SI", velo=97.0, num=3, balls=0, strikes=2, desc="foul", zone=11, plate_z=1.5, arm=41, rel_z=6.1),
        _pitch(pt="CH", velo=90.0, num=4, balls=0, strikes=2, desc="swinging_strike", zone=14, plate_z=1.2, arm=44, rel_z=6.3),
        _pitch(pt="CH", velo=91.0, ab=2, num=1, desc="ball", zone=13, plate_z=1.0, arm=46, rel_z=6.1),
        _pitch(pt="SI", velo=80.0, gtype="S", desc="ball"),
    ])


def test_pitch_profile_hand_checked():
    prof = D.pitch_profile(_outing(), 1).set_index("pitch_type")
    si, ch = prof.loc["SI"], prof.loc["CH"]
    assert si["n"] == 3 and ch["n"] == 2                       # spring pitch dropped
    assert si["usage_pct"] == pytest.approx(60.0)              # 3 of 5
    assert si["velo"] == pytest.approx(98.0)                   # (99 + 98 + 97) / 3
    assert si["velo_max"] == 99.0
    assert si["zone_pct"] == pytest.approx(200 / 3)            # zones 5, 5, 11 -> 2 of 3
    assert si["low_pct"] == pytest.approx(100 / 3)             # plate_z 1.5 < 2 -> 1 of 3
    assert si["swings"] == 2 and si["whiffs"] == 1             # swinging strike + foul; one whiff
    assert si["whiff_pct"] == pytest.approx(50.0)
    assert si["n_upper"] == 1                                  # plate_z 3.2 > 3
    assert si["arm_angle"] == pytest.approx(41.0)              # (40 + 42 + 41) / 3
    assert si["sd_rel_z_ft"] == pytest.approx(0.1)             # 6.0, 6.2, 6.1 -> sample SD 0.1
    assert ch["whiff_pct"] == pytest.approx(100.0)             # one swing, one whiff
    assert ch["low_pct"] == pytest.approx(100.0)
    assert list(prof.index) == ["SI", "CH"]                    # sorted by usage


def test_slot_check_against_primary():
    prof = D.pitch_profile(_outing(), 1)
    s = D.slot_check(prof).set_index("pitch_type")
    # CH arm angle (44 + 46)/2 = 45 vs SI 41 -> +4 degrees; release height (6.3 + 6.1)/2 = 6.2 vs 6.1 -> +1.2 in
    assert s.loc["CH", "d_arm_angle"] == pytest.approx(4.0)
    assert s.loc["CH", "d_rel_z_in"] == pytest.approx(1.2)
    assert s.loc["SI", "d_arm_angle"] == 0


def test_velo_by_pitch_count_buckets():
    rows = [_pitch(pt="SI", velo=100.0 - 0.1 * k, game=1, ab=1, num=k) for k in range(1, 31)]
    t = D.velo_by_pitch_count(pd.DataFrame(rows), 1, "SI").set_index("bucket")
    # pitches 1-15: mean of 99.9 .. 98.5 = 99.2; 16-25: 98.4 .. 97.5 = 97.95; 26-30: 97.4 .. 97.0 = 97.2
    assert t.loc["1-15", "n"] == 15 and t.loc["16-25", "n"] == 10 and t.loc["26+", "n"] == 5
    assert t.loc["1-15", "velo"] == pytest.approx(99.2)
    assert t.loc["16-25", "velo"] == pytest.approx(97.95)
    assert t.loc["26+", "velo"] == pytest.approx(97.2)


def test_count_state_and_usage():
    u = D.usage_by_count(_outing(), 1)
    two = u[u["count_state"] == "2 strikes"].set_index("pitch_type")
    # two-strike pitches: SI (num 3) and CH (num 4) -> 50% each
    assert two.loc["SI", "share_pct"] == pytest.approx(50.0) and two.loc["CH", "share_pct"] == pytest.approx(50.0)
    cs = D.count_state(pd.Series([0, 2, 1, 3]), pd.Series([0, 2, 1, 1]))
    assert list(cs) == ["0-0", "2 strikes", "even/ahead", "behind"]


def test_first_pitch_strike_against_league():
    rows = [
        _pitch(pitcher=1, game=1, ab=1, desc="called_strike"),
        _pitch(pitcher=1, game=1, ab=2, desc="ball"),
        _pitch(pitcher=1, game=1, ab=3, desc="hit_into_play"),
        _pitch(pitcher=2, game=2, ab=1, desc="ball"),
        _pitch(pitcher=2, game=2, ab=2, desc="foul"),
        _pitch(pitcher=1, game=1, ab=4, balls=1, desc="ball"),       # not 0-0, ignored
    ]
    r = D.first_pitch_strike(pd.DataFrame(rows), 1)
    # his 0-0 pitches: strike, ball, in play -> 2 of 3; league: 3 of 5
    assert r["n"] == 3 and r["strikes"] == 2 and r["pct"] == pytest.approx(200 / 3)
    assert r["league_pct"] == pytest.approx(60.0)


def test_league_context_percentiles():
    rows = []
    for pid, ext, arm in [(1, 6.0, 40.0), (2, 6.5, 30.0), (3, 5.5, 50.0)]:
        rows += [_pitch(pitcher=pid, ext=ext, arm=arm, game=pid, ab=1, num=k) for k in range(1, 4)]
    c = D.league_context(pd.DataFrame(rows), 1, min_pitches=3, min_type=3)
    # extension 6.0: one of three pitchers (5.5) is below -> 33.3; arm 40: one (30) below -> 33.3
    assert c["ext_pct"] == pytest.approx(100 / 3) and c["arm_pct"] == pytest.approx(100 / 3)
    assert c["pitchers"] == 3 and c["ext_league_mean"] == pytest.approx(6.0)
    assert math.isclose(c["vaa_league"]["SI"], D.vaa(pd.DataFrame([_pitch()])).iloc[0])


def test_release_offsets_centered_on_each_games_fastballs():
    # Game 1 fastballs at side 2.0 and 2.2 ft (mean 2.1), height 6.0 and 6.2 (mean 6.1); slider at 2.5 / 5.9.
    # Game 2 has the camera shifted +1 ft: fastballs 3.0 / 3.2, slider 3.5 -> the same offsets after centering.
    rows = []
    for game, shift in [(1, 0.0), (2, 1.0)]:
        rows += [_pitch(game=game, pt="SI", rel_x=2.0 + shift, rel_z=6.0, num=1),
                 _pitch(game=game, pt="FF", rel_x=2.2 + shift, rel_z=6.2, num=2),
                 _pitch(game=game, pt="SL", rel_x=2.5 + shift, rel_z=5.9, num=3)]
    o = D.release_offsets(pd.DataFrame(rows), 1)
    sl = o[o["pitch_type"] == "SL"]
    # side: (2.5 - 2.1) * 12 = +4.8 in; height: (5.9 - 6.1) * 12 = -2.4 in, in both games
    assert np.allclose(sl["d_side_in"], 4.8) and np.allclose(sl["d_height_in"], -2.4)


def test_release_offsets_right_hander_and_arm_angle():
    # RHP: arm side is -x in Statcast, so a slider released at -2.5 ft against fastballs at -2.0 / -2.2 (mean -2.1)
    # is 0.4 ft = 4.8 in farther to the arm side. Arm angle 36 vs fastballs 40 / 42 (mean 41) -> -5 degrees.
    rows = [_pitch(hand="R", pt="SI", rel_x=-2.0, arm=40, num=1), _pitch(hand="R", pt="FF", rel_x=-2.2, arm=42, num=2),
            _pitch(hand="R", pt="SL", rel_x=-2.5, arm=36, num=3)]
    sl = D.release_offsets(pd.DataFrame(rows), 1).set_index("pitch_type").loc["SL"]
    assert sl["d_side_in"] == pytest.approx(4.8) and sl["d_arm_deg"] == pytest.approx(-5.0)


def test_first_pitch_strike_automatic_calls():
    # an automatic ball (pitch clock) on 0-0 counts as a ball, an automatic strike as a strike: 1 of 2
    rows = [_pitch(game=1, ab=1, desc="automatic_ball"), _pitch(game=1, ab=2, desc="automatic_strike")]
    r = D.first_pitch_strike(pd.DataFrame(rows), 1)
    assert r["n"] == 2 and r["strikes"] == 1
