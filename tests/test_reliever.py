"""Reliever evaluation: the 20-80 mapping, control and OFP, and the comparison tables, on FICTIONAL pitches.

Every pitcher, game and pitch built here is fictional (ids 1-9, team codes HOM and AWY). The arithmetic behind
each expected number is in the comment beside it.
"""
import numpy as np
import pandas as pd
import pytest

from baseball.evaluation import reliever as R


# ---------------------------------------------------------------- the 20-80 mapping

@pytest.mark.parametrize("pct,grade", [
    (50.0, 50),       # z = 0 -> 50
    (84.13, 60),      # z = 1.000 -> 60.0
    (97.72, 70),      # z = 2.000 -> 70.0
    (15.87, 40),      # z = -1.000 -> 40.0
    (2.28, 30),       # z = -2.000 -> 30.0
    (75.0, 55),       # z = 0.674 -> 56.7 -> nearest 5 = 55
    (69.15, 55),      # z = 0.500 -> 55.0
    (99.99, 80),      # z = 3.72 -> 87.2 -> clamped to 80
    (0.01, 20),       # z = -3.72 -> 12.8 -> clamped to 20
])
def test_grade_from_percentile_is_50_plus_10z(pct, grade):
    assert R.grade_from_percentile(pct) == grade


def test_grade_from_percentile_missing():
    assert R.grade_from_percentile(float("nan")) is None


def test_percentile_is_mid_rank():
    ref = [1, 2, 3, 4]
    # x = 3: 2 below, 1 tie -> (2 + 0.5 + 0.5) / (4 + 1) = 60
    assert R.percentile(ref, 3) == pytest.approx(60.0)
    # x = 10: 4 below -> (4 + 0 + 0.5) / 5 = 90 (never 100, so z stays finite)
    assert R.percentile(ref, 10) == pytest.approx(90.0)
    # x = 0: (0 + 0 + 0.5) / 5 = 10
    assert R.percentile(ref, 0) == pytest.approx(10.0)


@pytest.mark.parametrize("bb,grade", [
    (8.0, 50),        # anchor
    (5.75, 60),       # anchor
    (10.5, 40),       # anchor
    (6.875, 55),      # halfway between 5.75 (60) and 8.0 (50) -> 55
    (3.0, 75),        # below the first anchor: held at 75
    (15.3, 20),       # 15%+ -> 20
    (11.25, 35),      # halfway between 10.5 (40) and 12.0 (30) -> 35
])
def test_control_grade_from_walk_rate(bb, grade):
    assert R.control_grade(bb) == grade


def test_reliever_ofp_formula_and_cap():
    # 0.55 x 70 + 0.35 x 60 + 0.10 x 50 = 38.5 + 21 + 5 = 64.5 -> capped at 60 -> "Elite closer"
    o = R.reliever_ofp({"FF": 70, "SL": 60, "CH": 40}, 50)
    assert o["ofp"] == 60 and o["role"] == "Elite closer" and o["raw"] == pytest.approx(60.0)
    # 0.55 x 55 + 0.35 x 50 + 0.10 x 40 = 30.25 + 17.5 + 4 = 51.75 -> 50 -> setup
    o = R.reliever_ofp({"FF": 50, "SL": 55}, 40)
    assert o["raw"] == pytest.approx(51.75) and o["ofp"] == 50 and o["role"] == "Setup / high-leverage reliever"
    # one graded pitch: no OFP
    assert R.reliever_ofp({"FF": 60}, 50)["ofp"] is None


# ---------------------------------------------------------------- fictional pitches

def _p(**kw):
    base = {"game_pk": 1, "game_date": "2026-05-01", "game_year": 2026, "game_type": "R", "at_bat_number": 1,
            "pitch_number": 1, "inning": 8, "inning_topbot": "Top", "home_team": "HOM", "away_team": "AWY",
            "pitcher": 1, "batter": 100, "player_name": "Fictional, One", "p_throws": "R", "stand": "R", "pitch_type": "FF",
            "description": "ball", "type": "B", "events": None, "zone": 11, "release_speed": 96.0,
            "release_spin_rate": 2300.0, "pfx_x": -0.5, "pfx_z": 1.25, "estimated_woba_using_speedangle": np.nan,
            "launch_speed": np.nan, "bb_type": None, "woba_value": np.nan, "woba_denom": np.nan, "delta_run_exp": 0.0,
            "delta_home_win_exp": 0.0, "bat_score": 2, "fld_score": 3}
    base.update(kw)
    return base


def _fictional_game():
    """One FICTIONAL game: home starter 9 throws the first pitch of the top half; reliever 1 then faces three
    hitters. PA 1: swinging strike, ball outside, strikeout (whiff); PA 2: walk on four balls outside;
    PA 3: ground ball in play (xwOBA .200, 98 mph)."""
    rows = [_p(pitcher=9, at_bat_number=1, inning=1, description="called_strike", type="S", zone=5)]
    ab = 10
    rows += [
        _p(at_bat_number=ab, pitch_number=1, description="swinging_strike", type="S", zone=5, delta_run_exp=-0.05),
        _p(at_bat_number=ab, pitch_number=2, description="ball", zone=13, delta_run_exp=0.03),
        _p(at_bat_number=ab, pitch_number=3, description="swinging_strike", type="S", zone=14, delta_run_exp=-0.04),
        _p(at_bat_number=ab, pitch_number=4, description="swinging_strike", type="S", zone=6, events="strikeout",
           woba_value=0.0, woba_denom=1, delta_run_exp=-0.20, delta_home_win_exp=0.03),
    ]
    rows += [_p(at_bat_number=ab + 1, pitch_number=i + 1, description="ball", zone=12, delta_run_exp=0.05,
                events="walk" if i == 3 else None, woba_value=0.7 if i == 3 else np.nan, woba_denom=1 if i == 3 else np.nan,
                delta_home_win_exp=-0.04 if i == 3 else 0.0) for i in range(4)]
    rows += [_p(at_bat_number=ab + 2, pitch_number=1, description="hit_into_play", type="X", zone=8, events="field_out",
                estimated_woba_using_speedangle=0.200, launch_speed=98.0, bb_type="ground_ball", woba_value=0.0, woba_denom=1,
                delta_run_exp=-0.25, delta_home_win_exp=0.02)]
    return pd.DataFrame(rows)


def test_flag_marks_relief_and_counts_events():
    d = R.flag(_fictional_game())
    me = d[d["pitcher"].eq(1)]
    assert me["relief"].all() and not d.loc[d["pitcher"].eq(9), "relief"].any()   # 9 threw his team's first pitch
    assert me["team"].eq("HOM").all()                                               # top half: the home team pitches
    assert int(me["pa"].sum()) == 3 and int(me["k"].sum()) == 1 and int(me["bb"].sum()) == 1
    assert int(me["outs"].sum()) == 2                                               # strikeout + field out


def test_season_line_rates_from_summed_counts():
    d = R.flag(_fictional_game())
    ln = R.season_line(d[d["pitcher"].eq(1)]).iloc[0]
    # Swings: 3 swinging strikes + 1 ball in play = 4; whiffs 3 -> 75%
    assert ln["swings"] == 4 and ln["whiff"] == pytest.approx(0.75)
    # Out of zone (11-14): 1 (zone 13) + 1 (zone 14) + 4 (zone 12) = 6 pitches; one swing (the zone-14 whiff) -> 1/6
    assert ln["out_zone"] == 6 and ln["chase"] == pytest.approx(1 / 6)
    # K% = 1/3, BB% = 1/3, so K-BB = 0
    assert ln["k_pct"] == pytest.approx(100 / 3) and ln["k_bb_pct"] == pytest.approx(0.0)
    # xwOBA per PA: (0 + 0.7 + 0.200) / 3 = 0.300 (the ball in play uses its expected value)
    assert ln["xwoba"] == pytest.approx(0.3)
    # Run value, pitcher's view: -(-0.05 + 0.03 - 0.04 - 0.20 + 4 x 0.05 - 0.25) = 0.31 over 9 pitches
    assert ln["rv100"] == pytest.approx(100 * 0.31 / 9)
    assert ln["ip"] == pytest.approx(0.2)                                          # 2 outs, baseball notation
    assert ln["hard_hit"] == pytest.approx(1.0) and ln["gb_rate"] == pytest.approx(1.0)


def test_team_bullpens_counts_only_relief():
    d = R.flag(_fictional_game())
    t = R.team_bullpens(d, 2026).set_index("team")
    assert t.loc["HOM", "pa"] == 3                                     # the starter's pitch is excluded
    # Win probability added for the home team's pitchers: top half, so +delta: 0.03 - 0.04 + 0.02 = 0.01
    assert t.loc["HOM", "wpa"] == pytest.approx(0.01)
    # Late and close: inning 8, score 2-3 -> every relief PA
    assert t.loc["HOM", "late_close_pa"] == 3


def test_workload_back_to_backs_and_three_in_four():
    # FICTIONAL reliever 1 pitches on May 1, 2, 4, 5, 6 (one pitch each, each his team's 2nd pitcher)
    rows = []
    for g, day in enumerate([1, 2, 4, 5, 6], start=1):
        rows.append(_p(game_pk=g, pitcher=9, at_bat_number=1, game_date=f"2026-05-0{day}"))
        rows.append(_p(game_pk=g, pitcher=1, at_bat_number=20, game_date=f"2026-05-0{day}", release_speed=96.0 + g / 10))
    w = R.workload(R.flag(pd.DataFrame(rows)), [1], 2026).iloc[0]
    assert w["games"] == 5 and w["back_to_back"] == 3                 # May 2, 5 and 6 follow an outing
    # Windows of four days ending on each outing: May 4 (1, 2, 4), 5 (2, 4, 5), 6 (4, 5, 6) hold three each
    assert w["three_in_four_days"] == 3
    assert w["longest_gap_days"] == 2
    # Velocity: back-to-back outings (games 2, 4, 5) average 96.2, 96.4, 96.5 -> 96.3667; others (1, 3) 96.1, 96.3 -> 96.2
    assert w["velo_b2b_minus_rest"] == pytest.approx(96.36667 - 96.2, abs=1e-4)


def test_velocity_read_nets_out_the_league():
    # FICTIONAL league: three pitchers, 100 four-seamers in 2025 and in 2026, one per game.
    rows = []
    for pid, v25, v26 in [(1, 95.0, 96.0), (2, 94.0, 94.0), (3, 93.0, 92.5)]:
        for season, v in ((2025, v25), (2026, v26)):
            for i in range(100):
                rows.append(_p(game_pk=season * 1000 + pid * 100 + i, game_year=season, game_date=f"{season}-06-01",
                               pitcher=pid, at_bat_number=5, release_speed=v))
                rows.append(_p(game_pk=season * 1000 + pid * 100 + i, game_year=season, game_date=f"{season}-06-01",
                               pitcher=99, at_bat_number=1))
    v = R.velocity_read(R.flag(pd.DataFrame(rows)), [1], 2026).iloc[0]
    # Changes +1.0, 0.0, -0.5 -> league median 0.0 -> pitcher 1 net +1.0
    assert v["change"] == pytest.approx(1.0) and v["league_change"] == pytest.approx(0.0)
    assert v["net_change"] == pytest.approx(1.0)
    # 100 games of identical velocity: the regressed level stays very near the observed 96.0
    assert v["velo_reg"] == pytest.approx(96.0, abs=0.05)


def test_pitch_grades_rank_within_type():
    # FICTIONAL stuff table: five four-seamers, same swings, so regression keeps their order
    stuff = pd.DataFrame({"pitcher": [1, 2, 3, 4, 5], "pitch_type": "FF", "swings": 100,
                          "whiffs": [30, 25, 20, 15, 10], "whiff_pct": [30.0, 25, 20, 15, 10],
                          "x_whiff_pct": [20.0, 21, 22, 23, 24]})
    proj = stuff.assign(proj_whiff_pct=[26.0, 24, 22, 20, 18])[["pitcher", "pitch_type", "proj_whiff_pct"]]
    g = R.pitch_grades(stuff, proj, [1, 3], {"whiff": 0.25, "FF/whiff": 0.20}).set_index("pitcher")
    # Pitcher 1: top of 5 -> (4 + 0.5 + 0.5) / 6 = 83.3 percentile -> z = 0.967 -> 59.7 -> 60
    assert g.loc[1, "pct_present"] == pytest.approx(100 * 5 / 6) and g.loc[1, "grade_present"] == 60
    # Pitcher 3: middle -> (2 + 0.5 + 0.5) / 6 = 50 -> 50
    assert g.loc[3, "grade_present"] == 50 and g.loc[3, "grade_2027"] == 50
    # Stuff runs the other way: pitcher 1 has the lowest expected whiff -> 1/6 = 16.7 -> z = -0.967 -> 40
    assert g.loc[1, "grade_stuff"] == 40
    # Regressed whiff: FF M = 77.3 swings, so 100 swings carry 100 / 177.3 = 0.564: 20 + 0.564 x (30 - 20) = 25.6
    assert g.loc[1, "reg_whiff_pct"] == pytest.approx(25.64, abs=0.05)


def test_lever_read_uses_flagged_changes_and_the_study():
    pairs = pd.DataFrame([{"pitcher": 1, "season_1": 2026, "pitch_type": "FF", "net_velo": -1.5, "chg_velo": True,
                           "net_spin": -50.0, "chg_spin": False, "net_ivb": 0.0, "chg_ivb": False, "d_whiff": -8.0, "d_xwhiff": -2.0}])
    answer = pd.DataFrame([{"pitch_type": "FF", "lever": "velo", "whiff": 1.8, "verdict": "confirmed", "caveat": "placebo fails"},
                           {"pitch_type": "FF", "lever": "spin", "whiff": 2.1, "verdict": "confirmed", "caveat": ""}])
    lv = R.lever_read(pairs, answer, [1], 2026)
    assert lv["lever"].tolist() == ["velo"]                            # spin moved, but not beyond the threshold
    # -1.5 mph / 1 mph per unit x +1.8 whiff points per unit = -2.7
    assert lv["implied_whiff"].iloc[0] == pytest.approx(-2.7) and lv["verdict"].iloc[0] == "confirmed"


def test_gap_history_swing_weighted():
    t = pd.DataFrame({"pitcher": [1, 1], "pitch_type": ["FF", "SL"], "swings": [100, 300], "whiffs": [20, 120],
                      "x_whiff_pct": [22.0, 34.0]})
    h = R.gap_history({2026: t}, [1]).iloc[0]
    # Actual 140 / 400 = 35.0; expected (22 x 100 + 34 x 300) / 400 = 31.0; gap +4.0
    assert h["whiff_pct_2026"] == pytest.approx(35.0) and h["x_whiff_pct_2026"] == pytest.approx(31.0)
    assert h["gap_2026"] == pytest.approx(4.0)


def test_intentional_walk_counts_as_pa_but_not_a_pitch():
    # FICTIONAL: Statcast records an intentional walk as one row with description automatic_ball and no pitch
    g = _fictional_game()
    ibb = _p(at_bat_number=13, pitch_number=1, description="automatic_ball", type="B", zone=np.nan, pitch_type=None,
             release_speed=np.nan, events="intent_walk", delta_run_exp=np.nan)
    d = R.flag(pd.concat([g, pd.DataFrame([ibb])], ignore_index=True))
    ln = R.season_line(d[d["pitcher"].eq(1)]).iloc[0]
    # 4 PA (3 + the intentional walk), 2 walks, 1 unintentional; still 9 pitches thrown
    assert ln["pa"] == 4 and ln["bb"] == 2 and ln["ubb"] == 1 and ln["pitches"] == 9
    assert ln["bb_pct"] == pytest.approx(50.0) and ln["ubb_pct"] == pytest.approx(25.0)
    # xwOBA per PA excludes intentional walks (no wOBA denominator): still (0 + 0.7 + 0.2) / 3
    assert ln["xwoba"] == pytest.approx(0.3)


def test_xwoba_diff_test_by_hand():
    a = {"mean": 0.318, "se": 0.010}
    b = {"mean": 0.306, "se": 0.002}
    t = R.xwoba_diff_test(a, b)
    # diff .012; SE sqrt(.010^2 + .002^2) = .0101980; z = 1.1767; two-sided p = 0.2393
    assert t["diff"] == pytest.approx(0.012) and t["se"] == pytest.approx(0.0101980, abs=1e-6)
    assert t["z"] == pytest.approx(1.1767, abs=1e-3) and t["p"] == pytest.approx(0.2393, abs=1e-3)


def test_xwoba_stats_counts_only_woba_pas():
    d = R.flag(_fictional_game())
    s = R.xwoba_stats(d[d["pitcher"].eq(1)])
    # Three wOBA PAs with values 0, 0.7, 0.2: mean 0.3, SD sqrt(((.3)^2 + (.4)^2 + (.1)^2) / 2) = sqrt(0.13) = 0.36056
    assert s["n"] == 3 and s["mean"] == pytest.approx(0.3) and s["sd"] == pytest.approx(0.36056, abs=1e-5)
    assert s["se"] == pytest.approx(0.36056 / np.sqrt(3), abs=1e-5)


def test_lever_read_carries_the_persistence_label():
    pairs = pd.DataFrame([{"pitcher": 1, "season_1": 2026, "pitch_type": "SL", "net_gap": 1.5, "chg_gap": True,
                           "d_whiff": 5.0, "d_xwhiff": -1.0}])
    answer = pd.DataFrame([{"pitch_type": "SL", "lever": "gap", "whiff": 1.06, "verdict": "confirmed", "caveat": ""}])
    lv = R.lever_read(pairs, answer, [1], 2026).iloc[0]
    assert lv["persistence"] == "not shown to last (borderline)"
    assert lv["implied_whiff"] == pytest.approx(1.5 * 1.06)
