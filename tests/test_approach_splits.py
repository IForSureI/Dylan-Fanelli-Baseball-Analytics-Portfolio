"""Approach splits: the definitions on a tiny hand-built season, and the Arozarena report's numbers against the
saved outputs (reports/outputs/arozarena_approach.json and arozarena_video_sample.json)."""
import json
from pathlib import Path

import pandas as pd
import pytest

from baseball.evaluation import approach_splits as A

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "outputs"
REPORT = (ROOT / "reports" / "2026-arozarena-swing-breakdown.md").read_text()


def _pitch(**kw):
    base = dict(game_type="R", stand="R", description="ball", events=None, zone=5, strikes=0, balls=0,
                pitch_type="FF", plate_x=0.0, plate_z=2.5, sz_top=3.5, sz_bot=1.5, delta_run_exp=0.0,
                bb_type=None, launch_speed=None, launch_angle=None, estimated_woba_using_speedangle=None,
                woba_value=None, bat_speed=None, swing_length=None, attack_angle=None,
                intercept_ball_minus_batter_pos_y_inches=None)
    base.update(kw)
    return base


def test_definitions_on_a_tiny_season():
    d = pd.DataFrame([
        _pitch(zone=14, strikes=2, description="swinging_strike", events="strikeout", bat_speed=70.0),  # 2K chase whiff, K
        _pitch(zone=14, strikes=2, description="foul", bat_speed=68.0),                                  # 2K chase contact
        _pitch(zone=14, strikes=2, description="hit_into_play", events="field_out", bb_type="ground_ball",
               launch_speed=96.0, launch_angle=-5.0, estimated_woba_using_speedangle=0.2, woba_value=0.0),
        _pitch(zone=5, strikes=0, description="hit_into_play", events="home_run", bb_type="fly_ball",
               launch_speed=105.0, launch_angle=28.0, estimated_woba_using_speedangle=1.5, woba_value=2.0),
        _pitch(zone=12, strikes=1, description="ball"),
        _pitch(zone=5, game_type="S", description="swinging_strike"),                                   # spring: dropped
    ])
    s = A.season_splits(d)
    assert s["pitches"] == 5 and s["pa"] == 3
    assert s["strikeout"]["pct"] == pytest.approx(33.3)
    assert s["discipline"]["chase"]["k"] == 3 and s["discipline"]["chase"]["n"] == 4      # 3 of 4 pitches outside
    assert s["two_strikes"]["chase_contact"]["pct"] == pytest.approx(66.7)                 # a foul tip would be a whiff
    assert s["two_strikes"]["strikeout_once_there"]["pct"] == 50.0
    b = s["batted"]
    assert b["hard_hit"]["pct"] == 100.0 and b["hard_hit_on_ground"]["pct"] == 50.0
    assert b["by_type"]["fly_ball"]["woba"] == 2.0
    # zone 14 is low and away for a right-handed hitter (catcher's view), low and in for a lefty
    assert A._away_low_zones("R") == {9, 14} and A._away_low_zones("L") == {7, 13}


def test_attack_regions():
    d = pd.DataFrame([_pitch(plate_x=0.0, plate_z=2.5), _pitch(plate_x=0.8, plate_z=2.5),
                      _pitch(plate_x=1.4, plate_z=2.5), _pitch(plate_x=2.0, plate_z=2.5)])
    assert list(A.attack_region(d)) == ["heart", "shadow", "chase", "waste"]


AP = json.loads((OUT / "arozarena_approach.json").read_text())
T = AP["tests"]


def _q(q):
    return "<.001" if q < 0.001 else f"{q:.3f}"[1:] if q < 0.01 else f"{q:.3f}"[1:] if q < 0.1 else f"{q:.2f}"[1:]


def test_two_strike_table_matches_the_outputs():
    for key, label in [("two_strike_chase", "Two-strike chase rate"), ("two_strike_chase_contact", "Contact on two-strike chases"),
                       ("strikeout_once_at_two_strikes", "Strikeout rate once at two strikes")]:
        t = T[key]
        assert f"| {label} | {t['from']}% | {t['to']}% |" in REPORT, key
        assert t["q"] < 0.05
    assert T["two_strike_zone_contact"]["q"] > 0.05 and "| .46 | within the noise |" in REPORT
    assert "the 17 tests" in REPORT and len(T) == 17


def test_high_fastball_and_swing_numbers_match():
    hi = AP["second"]["high_fastball"]
    assert T["high_fb_bat_speed"]["from"] == 69.1 and T["high_fb_bat_speed"]["to"] == 64.4
    assert f"| {T['high_fb_launch_angle']['from']}° ({AP['first']['high_fastball']['batted']['n']} balls) | " \
           f"{T['high_fb_launch_angle']['to']}° ({hi['batted']['n']} balls) |" in REPORT
    assert T["contact_depth_all_swings"]["diff"] == -2.3 and "2.3 inches" in REPORT
    assert AP["first"]["zones"]["1"]["xwoba_con"] == 0.412 and AP["second"]["zones"]["1"]["whiff"]["pct"] == 49.1


def test_results_against_contact_match():
    for season, col in (("first", "2025"), ("second", "2026")):
        b = AP[season]["batted"]
        assert f"{b['woba_con']:.3f}"[1:] in REPORT and f"{b['xwoba_con']:.3f}"[1:] in REPORT, col
    lds = AP["second"]["batted"]["by_type"]["line_drive"]
    assert round(lds["woba"] - lds["xwoba"], 3) == 0.113 and ".113 more" in REPORT


def test_video_sample_is_complete_and_linked():
    v = json.loads((OUT / "arozarena_video_sample.json").read_text())
    assert len(v) == 41 and [x["swing"] for x in v] == list(range(1, 42))
    assert all(x["clip"].startswith("https://baseballsavant.mlb.com/sporty-videos?playId=") and "nan" not in x["clip"] for x in v)
    assert REPORT.count("sporty-videos?playId=") == 41
    fails = [x for x in v if x["read"] != "good swing"]
    by = lambda yr, r: sum(1 for x in fails if x["season"] == yr and x["read"] == r)  # noqa: E731
    assert (by(2026, "late"), by(2026, "fooled by spin or speed"), by(2026, "on time, wrong plane")) == (6, 7, 8)
    assert (by(2025, "late"), by(2025, "fooled by spin or speed")) == (3, 3)
    assert "| Late on velocity | 3 | 6 |" in REPORT
    assert sum(x["second_angle"] for x in v) == 5
