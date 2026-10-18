from baseball.evaluation.grades import ofp_pitcher, parse_pitches, to_scale, velo_grade


def test_to_scale_rounds_halves_up_and_clamps():
    assert to_scale(72.5) == 75
    assert to_scale(72.4) == 70
    assert to_scale(95) == 80
    assert to_scale(3) == 20


def test_velo_vs_2026_starters():
    # 50 + 10 * (99.5 - 94.5) / 2.15 = 73.26 -> 75
    g = velo_grade(99.5, "L")
    assert g["vs_2026_starters_raw"] == 73.3 and g["vs_2026_starters"] == 75
    # 94.5 is the starter mean -> exactly 50
    assert velo_grade(94.5)["vs_2026_starters"] == 50


def test_velo_traditional_anchors_and_lefty_credit():
    # 93 RHP sits on the 50 anchor; a 93 LHP reads as 94.5 -> halfway from 55 to 60 = 57.5 -> 60
    assert velo_grade(93.0, "R")["traditional"] == 50
    assert velo_grade(93.0, "L")["traditional_raw"] == 57.5
    assert velo_grade(93.0, "L")["traditional"] == 60
    assert velo_grade(101.0)["traditional"] == 80


def test_ofp_morejon_rollup():
    # Reliever: min(60, 0.55*70 + 0.35*70 + 0.10*60) = min(60, 69.0) = 60.
    # Starter at command 50: 0.3*70 + 0.2*70 + 0.2*70 + 0.3*50 = 64.0; at command 60: 67.0.
    r = ofp_pitcher({"SI": 70, "CH": 70, "FF": 70, "SL": 55}, 60)
    assert r["reliever_raw"] == 60.0 and r["reliever_ofp"] == 60
    assert r["starter_raw"] == 67.0
    assert ofp_pitcher({"SI": 70, "CH": 70, "FF": 70, "SL": 55}, 50)["starter_raw"] == 64.0


def test_ofp_two_pitch_reliever_is_not_starter_viable():
    r = ofp_pitcher({"FF": 60, "SL": 60}, 50)
    # third pitch defaults to 35, so not starter-viable; reliever = 0.55*60 + 0.35*60 + 5 = 59 -> 60
    assert not r["starter_viable"] and r["profile"] == "reliever" and r["suggested_ofp"] == 60


def test_parse_pitches():
    assert parse_pitches(["SI=70", "CH=65", "command=55"]) == ({"SI": 70, "CH": 65}, 55)
