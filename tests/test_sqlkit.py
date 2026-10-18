"""Every named SQL query in sql/, run on a tiny FICTIONAL pitch file built here (no real data needed, so
this runs in CI). Each scenario uses its own games and players so the hand-checked answers stay small.
All players, games and numbers below are fictional."""
import math

import pandas as pd
import pytest

from baseball import sqlkit
from baseball.sqlkit import REQUIRED, connect, describe, queries, run

BALL_LIKE = {"ball", "blocked_ball", "automatic_ball", "hit_by_pitch", "pitchout", "intent_ball"}
INT_COLS = ["game_pk", "game_year", "inning", "at_bat_number", "pitch_number", "pitcher", "batter", "balls",
            "strikes", "zone", "n_thruorder_pitcher", "woba_denom", "launch_speed_angle"]
FLOAT_COLS = ["release_speed", "delta_run_exp", "woba_value", "estimated_woba_using_speedangle", "launch_speed",
              "bat_speed", "swing_length"]


def pitch(game_pk, date, ab, pn, pitcher, batter, desc, *, pt="FF", velo=90.0, balls=0, strikes=0, zone=5,
          inning=1, half="Top", p_throws="R", stand="R", events=None, woba=None, den=None, est=None, ev=None,
          lsa=None, thru=1, rv=0.0, bat=None, length=None, game_type="R"):
    """One fictional pitch row in the Statcast schema (only the columns the queries read)."""
    return {
        "game_pk": game_pk, "game_date": date, "game_year": int(date[:4]), "game_type": game_type,
        "home_team": "HOM", "away_team": "AWY", "inning": inning, "inning_topbot": half,
        "at_bat_number": ab, "pitch_number": pn, "pitcher": pitcher, "batter": batter,
        "p_throws": p_throws, "stand": stand, "pitch_type": pt, "description": desc,
        "type": "X" if desc.startswith("hit_into_play") else ("B" if desc in BALL_LIKE else "S"),
        "events": events, "balls": balls, "strikes": strikes, "zone": zone, "release_speed": velo,
        "n_thruorder_pitcher": thru, "delta_run_exp": rv, "woba_value": woba, "woba_denom": den,
        "estimated_woba_using_speedangle": est, "launch_speed": ev, "launch_speed_angle": lsa,
        "bat_speed": bat, "swing_length": length,
    }


def scenario_arsenal():
    """A: pitcher 10 (RHP), one start, game 101. Six thrown pitches, plus one automatic ball and one spring
    training pitch that must both be ignored."""
    g, d = 101, "2026-04-01"
    return [
        pitch(g, d, 1, 1, 10, 900, "called_strike", velo=95, zone=5, rv=-0.05),
        pitch(g, d, 1, 2, 10, 900, "swinging_strike", pt="SL", velo=85, strikes=1, zone=14, rv=-0.10),
        pitch(g, d, 1, 3, 10, 900, "foul", pt="SL", velo=85, strikes=2, zone=13, rv=-0.02),
        pitch(g, d, 1, 4, 10, 900, "swinging_strike", velo=97, strikes=2, zone=2, rv=-0.10,
              events="strikeout", woba=0.0, den=1),
        pitch(g, d, 2, 1, 10, 900, "ball", velo=95, zone=11, rv=0.02),
        pitch(g, d, 2, 2, 10, 900, "hit_into_play", velo=96, balls=1, zone=5, rv=0.30,
              events="single", woba=0.9, den=1, est=0.5, ev=98.0, lsa=6),
        pitch(g, d, 3, 1, 10, 901, "automatic_ball", velo=80, zone=None),            # no pitch thrown
        pitch(199, "2026-03-10", 1, 1, 10, 900, "swinging_strike", velo=80, game_type="S"),  # spring
    ]


def scenario_zones():
    """B: batter 300 sees nine pitches with a zone from pitcher 30 (game 102), plus two that must be ignored."""
    g, d = 102, "2026-04-01"
    rows = [(5, "swinging_strike"), (5, "foul"), (1, "called_strike"), (11, "ball"), (11, "swinging_strike"),
            (13, "foul"), (14, "ball"), (14, "ball"), (None, "ball"), (12, "automatic_ball")]
    return [pitch(g, d, 1, i + 1, 30, 300, desc, pt="SL", velo=84, zone=z) for i, (z, desc) in enumerate(rows)]


def scenario_tto():
    """C: pitcher 40 (RHP), game 103: one row per PA. L = left-handed hitter 401, R = right-handed 402."""
    g, d = 103, "2026-04-02"
    pas = [  # (time through, stand, description, events, woba_value, woba_denom, xwOBA estimate)
        (1, "L", "hit_into_play", "single", 0.9, 1, 0.5),
        (1, "R", "hit_into_play", "field_out", 0.0, 1, 0.1),
        (1, "L", "swinging_strike", "strikeout", 0.0, 1, None),
        (1, "L", "automatic_ball", "intent_walk", 0.4, None, None),   # intentional walk: not a wOBA PA
        (2, "R", "ball", "walk", 0.7, 1, None),
        (2, "L", "hit_into_play", "field_out", 0.0, 1, 0.1),
        (3, "R", "hit_into_play", "home_run", 2.0, 1, 1.8),
        (3, "L", "hit_into_play", "field_out", 0.0, 1, 0.1),
        (4, "R", "hit_into_play", "field_out", 0.0, 1, 0.1),          # 4th time folds into 3rd
    ]
    return [pitch(g, d, i + 1, 1, 40, 401 if s == "L" else 402, desc, stand=s, thru=t, events=e, woba=w, den=n, est=x)
            for i, (t, s, desc, e, w, n, x) in enumerate(pas)]


def scenario_bat_tracking():
    """D: hitters 500 and 501 against pitcher 50, game 104."""
    g, d = 104, "2026-04-02"
    rows = []
    # 500: one slow swing (50 mph) under his 10th percentile, nine at 70-78, and a bunt that never counts
    speeds = [50] + list(range(70, 79))
    for i, s in enumerate(speeds):
        rows.append(pitch(g, d, 1, i + 1, 50, 500, "foul", bat=float(s), length=8.0 if s >= 75 else 7.0))
    rows.append(pitch(g, d, 1, 11, 50, 500, "foul_bunt", bat=30.0, length=2.0))
    rows.append(pitch(g, d, 1, 12, 50, 500, "ball"))
    # 501: a 61 mph swing below his cut that still counts (60+ mph and 90+ mph exit velocity), nine at 70-78
    rows.append(pitch(g, d, 2, 1, 50, 501, "hit_into_play", bat=61.0, length=7.5, ev=95.0, events="field_out",
                      woba=0.0, den=1, est=0.3))
    for i, s in enumerate(range(70, 79)):
        rows.append(pitch(g, d, 3, i + 1, 50, 501, "foul", bat=float(s), length=7.5))
    return rows


def scenario_reliever():
    """E: reliever 11 behind starter 12 in five games. Fastball speeds by date: Apr 1 95 (first outing, no
    rest value), Apr 2 93 (0 days' rest), Apr 4 94 (1), Apr 7 94.5 (2), Apr 11 96 (3+)."""
    games = [(110, "2026-04-01", 95.0), (111, "2026-04-02", 93.0), (112, "2026-04-04", 94.0),
             (113, "2026-04-07", 94.5), (114, "2026-04-11", 96.0)]
    rows = []
    for g, d, v in games:
        rows.append(pitch(g, d, 1, 1, 12, 902, "ball", velo=92.0))                      # starter's first pitch
        rows.append(pitch(g, d, 5, 1, 11, 903, "called_strike", velo=v, inning=7))
        rows.append(pitch(g, d, 5, 2, 11, 903, "foul", velo=v, inning=7, strikes=1))
        rows.append(pitch(g, d, 5, 3, 11, 903, "ball", pt="SL", velo=85.0, inning=7, strikes=2))
    # a postseason outing (game_type F) at 80 mph: if it counted, it would be a 3+ rest outing and drag velo_3plus
    rows.append(pitch(115, "2026-10-02", 1, 1, 12, 902, "ball", velo=92.0, game_type="F"))
    rows.append(pitch(115, "2026-10-02", 5, 1, 11, 903, "called_strike", velo=80.0, inning=7, game_type="F"))
    rows.append(pitch(115, "2026-10-02", 5, 2, 11, 903, "foul", velo=80.0, inning=7, strikes=1, game_type="F"))
    return rows


def scenario_starter():
    """F: starter 60, four starts. Each start: a 1st-inning fastball at v + 0.5, a changeup, and a 2nd-inning
    fastball at v - 0.5, so the start's fastball mean is v: 95.0, 93.0, 94.0, 94.5. Between the 93.0 and 94.0
    starts, a short start (Apr 9) with no fastballs: it stays in the sequence but is never compared. After the
    season, a postseason start (game_type F) at 85 mph that must be ignored."""
    rows = [pitch(124, "2026-04-09", 1, 1, 60, 904, "ball", pt="CH", velo=85.0, inning=1),
            pitch(125, "2026-10-03", 1, 1, 60, 904, "called_strike", velo=85.0, inning=1, game_type="F"),
            pitch(125, "2026-10-03", 4, 1, 60, 905, "foul", velo=85.0, inning=2, game_type="F")]
    for g, d, v in [(120, "2026-04-01", 95.0), (121, "2026-04-07", 93.0), (122, "2026-04-12", 94.0),
                    (123, "2026-04-18", 94.5)]:
        rows.append(pitch(g, d, 1, 1, 60, 904, "called_strike", velo=v + 0.5, inning=1))
        rows.append(pitch(g, d, 1, 2, 60, 904, "ball", pt="CH", velo=85.0, inning=1, strikes=1))
        rows.append(pitch(g, d, 4, 1, 60, 905, "foul", velo=v - 0.5, inning=2))
    return rows


def scenario_first_pitch():
    """G: pitcher 70, game 130: five PAs with a thrown first pitch, plus an intentional walk with none."""
    g, d = 130, "2026-04-03"
    return [
        pitch(g, d, 1, 1, 70, 700, "called_strike"),
        pitch(g, d, 1, 2, 70, 700, "swinging_strike", strikes=1),
        pitch(g, d, 1, 3, 70, 700, "swinging_strike", strikes=2, events="strikeout", woba=0.0, den=1),
        pitch(g, d, 2, 1, 70, 700, "foul"),
        pitch(g, d, 2, 2, 70, 700, "hit_into_play", strikes=1, events="field_out", woba=0.0, den=1, est=0.2),
        pitch(g, d, 3, 1, 70, 700, "ball"),
        pitch(g, d, 3, 2, 70, 700, "ball", balls=1),
        pitch(g, d, 3, 3, 70, 700, "ball", balls=2),
        pitch(g, d, 3, 4, 70, 700, "ball", balls=3, events="walk", woba=0.7, den=1),
        pitch(g, d, 4, 1, 70, 700, "hit_into_play", events="single", woba=0.9, den=1, est=0.6),
        pitch(g, d, 5, 1, 70, 700, "hit_by_pitch", events="hit_by_pitch", woba=0.7, den=1),
        pitch(g, d, 6, 1, 70, 700, "automatic_ball", zone=None, events="intent_walk", woba=0.4),
    ]


def _frame(rows) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for c in INT_COLS:
        df[c] = df[c].astype("Int64")
    for c in FLOAT_COLS:
        df[c] = df[c].astype("float64")
    return df


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    root = tmp_path_factory.mktemp("fictional")
    (root / "seq").mkdir()
    (root / "people").mkdir()
    rows = (scenario_arsenal() + scenario_zones() + scenario_tto() + scenario_bat_tracking() + scenario_reliever()
            + scenario_starter() + scenario_first_pitch())
    _frame(rows).to_parquet(root / "seq" / "seq_2026_00.parquet", index=False)
    # A 2025 file with whole-number columns stored as FLOAT (as some real seasons are): the view must cast them
    # back, and season filters must keep this 70 mph pitch out of every 2026 answer.
    old = _frame([pitch(90, "2025-06-01", 1, 1, 10, 900, "swinging_strike", velo=70.0)])
    for c in INT_COLS:
        old[c] = old[c].astype("float32")
    old.to_parquet(root / "seq" / "seq_2025_00.parquet", index=False)
    pd.DataFrame({"key_mlbam": [10, 40, 60], "name": ["Fictional Ten", "Fictional Forty", "Fictional Sixty"]}
                 ).to_parquet(root / "people" / "people.parquet", index=False)
    return root


@pytest.fixture(scope="module")
def con(data_dir):
    c = connect(data_dir)
    yield c
    c.close()


# Arguments that make every query return rows on the fictional file
ARGS = {
    "arsenal_by_count": dict(pitcher=10, season=2026),
    "hitter_zone_discipline": dict(batter=300, season=2026),
    "times_through_order": dict(season=2026, min_pa_3rd=1),
    "platoon_splits": dict(season=2026, min_pa=1),
    "bat_tracking_leaders": dict(season=2026, min_swings=5),
    "velocity_by_inning": dict(pitcher=60, season=2026),
    "first_pitch_outcomes": dict(season=2026, pitcher=70),
    "run_value_by_pitch_type": dict(season=2026, pitcher=10, min_pitches=1),
    "hitter_damage_zone": dict(batter=900, season=2026),
    "reliever_rest": dict(season=2026, min_relief_apps=3),
    "league_baselines": dict(season_from=2025, season_to=2026, min_pitches=1),
    "velocity_drop_between_starts": dict(season=2026, min_starts=3, min_fb=2),
}


# ------------------------------------------------------------------ every query

def test_every_query_has_test_arguments():
    assert sorted(ARGS) == queries()


@pytest.mark.parametrize("name", sorted(ARGS))
def test_every_query_runs_and_matches_its_header(con, name):
    info = describe(name)
    assert info["question"], f"{name}: header has no question"
    assert info["columns"], f"{name}: header lists no output columns"
    out = run(name, con, **ARGS[name])
    assert len(out) > 0, f"{name} returned no rows on the fictional file"
    assert list(out.columns) == info["columns"], f"{name}: output columns differ from the header"


@pytest.mark.parametrize("name", ["first_pitch_outcomes", "run_value_by_pitch_type"])
def test_league_wide_default_runs(con, name):
    """The NULL default (every pitcher) binds and runs."""
    args = {k: v for k, v in ARGS[name].items() if k != "pitcher"}
    assert len(run(name, con, **args)) > 0


def test_view_casts_float_ids_to_integers(con):
    types = dict(con.execute("SELECT column_name, column_type FROM (DESCRIBE pitches)").fetchall())
    assert types["pitcher"] == "BIGINT" and types["game_pk"] == "BIGINT" and types["zone"] == "BIGINT"


# ------------------------------------------------------------------ hand-checked answers

def test_arsenal_by_count_hand_checked(con):
    out = run("arsenal_by_count", con, pitcher=10, season=2026)
    cell = out.set_index(["count_state", "pitch_type"])
    ff, sl = cell.loc[("all", "FF")], cell.loc[("all", "SL")]
    # FF: 95, 97, 95, 96 (the automatic ball, the spring pitch and the 2025 pitch are all excluded)
    assert ff["n"] == 4 and ff["usage_pct"] == 66.7 and ff["velo"] == 95.8
    assert ff["swings"] == 2 and ff["whiffs"] == 1 and ff["whiff_pct"] == 50.0    # whiff + ball in play
    assert ff["out_zone"] == 1 and ff["chase_pct"] == 0.0                         # the zone-11 ball, taken
    assert sl["n"] == 2 and sl["usage_pct"] == 33.3 and sl["whiff_pct"] == 50.0 and sl["chase_pct"] == 100.0
    # 0-0: two fastballs, no swings; 2 strikes: one FF whiff, one SL chased foul
    zero = cell.loc[("0-0", "FF")]
    assert zero["n"] == 2 and zero["usage_pct"] == 100.0 and math.isnan(zero["whiff_pct"])
    assert cell.loc[("2 strikes", "FF"), "whiff_pct"] == 100.0
    assert cell.loc[("2 strikes", "SL"), "usage_pct"] == 50.0
    assert cell.loc[("behind", "FF"), "n"] == 1
    assert list(dict.fromkeys(out["count_state"])) == ["all", "0-0", "even/ahead", "behind", "2 strikes"]
    # the floor is applied after usage: 0-0 FF keeps 100% and all-counts FF keeps 66.7%
    floored = run("arsenal_by_count", con, pitcher=10, season=2026, min_n=2).set_index(["count_state", "pitch_type"])
    assert sorted(floored.index) == [("0-0", "FF"), ("all", "FF"), ("all", "SL")]
    assert floored.loc[("all", "FF"), "usage_pct"] == 66.7


def test_hitter_zone_discipline_hand_checked(con):
    out = run("hitter_zone_discipline", con, batter=300, season=2026)
    totals = out[out["zone"].isna()].set_index("region")
    assert totals.loc["in zone", ["pitches", "swings", "whiffs"]].tolist() == [3, 2, 1]
    assert totals.loc["in zone", "swing_pct"] == 66.7 and totals.loc["in zone", "whiff_pct"] == 50.0
    assert math.isnan(totals.loc["in zone", "chase_pct"])
    assert totals.loc["out of zone", ["pitches", "swings", "whiffs"]].tolist() == [5, 2, 1]
    assert totals.loc["out of zone", "chase_pct"] == 40.0
    z11 = out[out["zone"].eq(11)].iloc[0]
    assert z11["pitches"] == 2 and z11["chase_pct"] == 50.0 and z11["whiff_pct"] == 100.0
    assert sorted(out["zone"].dropna().astype(int)) == [1, 5, 11, 13, 14]     # no-zone and automatic rows dropped


def test_times_through_order_hand_checked(con):
    out = run("times_through_order", con, season=2026, min_pa_3rd=1)
    assert out["pitcher"].tolist() == [40]
    r = out.iloc[0]
    assert r["name"] == "Fictional Forty"
    assert (r["pa_1st"], r["woba_1st"]) == (3, 0.300)        # (0.9 + 0 + 0) / 3; the intentional walk is out
    assert (r["pa_2nd"], r["woba_2nd"]) == (2, 0.350)        # (0.7 + 0) / 2
    assert (r["pa_3rd"], r["woba_3rd"]) == (3, 0.667)        # (2.0 + 0 + 0) / 3, 4th time folded in
    assert r["penalty_2nd"] == 0.050 and r["penalty_3rd"] == 0.367


def test_platoon_splits_hand_checked(con):
    r = run("platoon_splits", con, season=2026, min_pa=1).set_index("pitcher").loc[40]
    assert r["pa_vs_l"] == 5 and r["woba_vs_l"] == 0.225 and r["k_pct_vs_l"] == 20.0   # the IBB counts as a PA but has no wOBA weight
    assert r["xwoba_vs_l"] == 0.175                                                      # (0.5 + 0 + 0.1 + 0.1) / 4
    assert r["pa_vs_r"] == 4 and r["woba_vs_r"] == 0.675 and r["xwoba_vs_r"] == 0.675
    assert r["platoon_gap"] == -0.5                                                      # RHP: vs L minus vs R


def test_bat_tracking_competitive_swings_hand_checked(con):
    out = run("bat_tracking_leaders", con, season=2026, min_swings=5).set_index("batter")
    a = out.loc[500]
    # 10 tracked (the bunt never counts); 10th percentile = 50 + 0.9 x (70 - 50) = 68, so the 50 drops
    assert a["tracked_swings"] == 10 and a["competitive_swings"] == 9
    assert a["bat_speed"] == 74.0 and a["swing_length"] == 7.44 and a["fast_swing_pct"] == 44.4
    b = out.loc[501]
    # cut = 61 + 0.9 x 9 = 69.1; the 61 mph swing stays in on the 60+ mph / 90+ mph exit velocity rule
    assert b["competitive_swings"] == 10 and b["bat_speed"] == 72.7 and b["fast_swing_pct"] == 40.0
    assert (a["bat_speed_rank"], b["bat_speed_rank"]) == (1, 2)
    assert (a["swing_length_rank"], b["swing_length_rank"]) == (1, 2)


def test_velocity_by_inning_hand_checked(con):
    out = run("velocity_by_inning", con, pitcher=60, season=2026).set_index("inning")
    assert out["pitch_type"].unique().tolist() == ["FF"]          # primary fastball picked automatically
    assert out.loc[1, "velo"] == 94.6 and out.loc[2, "velo"] == 93.6   # 94.625 and 93.625
    assert out.loc[1, "velo_vs_1st"] == 0.0 and out.loc[2, "velo_vs_1st"] == -1.0
    assert out.loc[1, "starts"] == 4 and out.loc[1, "max_velo"] == 95.5
    assert out.loc[1, "avg_pitch_of_game"] == 1 and out.loc[2, "avg_pitch_of_game"] == 3
    ch = run("velocity_by_inning", con, pitcher=60, season=2026, pitch_type="CH")
    assert ch["pitch_type"].tolist() == ["CH"] and ch["velo"].tolist() == [85.0]


def test_first_pitch_outcomes_hand_checked(con):
    out = run("first_pitch_outcomes", con, season=2026, pitcher=70).set_index("after_first_pitch")
    assert out.index.tolist() == ["0-1", "1-0", "in play on 0-0", "hit by pitch on 0-0"]
    assert out["pa"].tolist() == [2, 1, 1, 1]                      # the intentional walk has no thrown 0-0 pitch
    assert out["first_pitch_strike_pct"].unique().tolist() == [60.0]   # (2 + 1) / 5
    assert out.loc["0-1", "share_pct"] == 40.0
    assert out.loc["0-1", "woba"] == 0.0 and out.loc["0-1", "xwoba"] == 0.1 and out.loc["0-1", "k_pct"] == 50.0
    assert out.loc["1-0", "woba"] == 0.7 and out.loc["1-0", "bb_pct"] == 100.0
    assert out.loc["in play on 0-0", "xwoba"] == 0.6


def test_run_value_hand_checked(con):
    out = run("run_value_by_pitch_type", con, season=2026, pitcher=10, min_pitches=1).set_index("pitch_type")
    # FF delta_run_exp: -0.05, -0.10, +0.02, +0.30 -> 0.17 runs allowed -> -4.25 saved per 100
    assert out.loc["FF", "rv_per100"] == -4.25 and out.loc["FF", "runs_saved"] == -0.2
    # SL: -0.10, -0.02 -> 0.12 runs saved over 2 pitches -> 6.00 per 100
    assert out.loc["SL", "rv_per100"] == 6.0
    assert out.loc["FF", "usage_pct"] == 66.7 and out.loc["FF", "name"] == "Fictional Ten"


def test_reliever_rest_hand_checked(con):
    out = run("reliever_rest", con, season=2026, min_relief_apps=3)
    assert out["pitcher"].tolist() == [11]                   # the starter (12) has no relief outings
    r = out.iloc[0]
    assert r["relief_apps"] == 5
    assert [r["apps_0d"], r["apps_1d"], r["apps_2d"], r["apps_3plus"]] == [1, 1, 1, 1]   # first outing: no bucket
    assert r["fb_type"] == "FF" and r["velo_3plus"] == 96.0
    assert [r["velo_chg_0d"], r["velo_chg_1d"], r["velo_chg_2d"]] == [-3.0, -2.0, -1.5]
    assert pd.isna(r["name"])                                # not in the people file: name stays NULL


def test_velocity_drop_hand_checked(con):
    out = run("velocity_drop_between_starts", con, season=2026, min_starts=3, min_fb=2)
    assert out["pitcher"].tolist() == [60]
    r = out.iloc[0]
    assert r["starts"] == 4 and r["season_velo"] == 94.1     # mean of 95, 93, 94, 94.5 = 94.125
    assert r["starts_skipped"] == 1                          # the Apr 9 start with no fastballs
    assert str(r["game_date"])[:10] == "2026-04-07" and str(r["prev_game_date"])[:10] == "2026-04-01"
    # the next start is the short one, so there is no next velo; and Apr 12 is never compared with Apr 7
    assert (r["prev_velo"], r["velo"], r["drop_mph"]) == (95.0, 93.0, 2.0) and pd.isna(r["next_velo"])
    # with no floor the short start counts... but it has no fastball velo, so nothing compares across it
    loose = run("velocity_drop_between_starts", con, season=2026, min_starts=3, min_fb=0).iloc[0]
    assert loose["starts_skipped"] == 0 and loose["drop_mph"] == 2.0


def test_hitter_damage_zone_hand_checked(con):
    out = run("hitter_damage_zone", con, batter=900, season=2026, min_bip=1)
    r = out.set_index("zone").loc[5]
    assert (r["pitches"], r["swings"], r["bip"]) == (2, 1, 1)
    assert r["tracked_bip"] == 1
    assert r["xwoba_con"] == 0.5 and r["hard_hit_pct"] == 100.0 and r["barrel_pct"] == 100.0 and r["damage_rank"] == 1
    # count filter: in the 1-0 count (behind) he saw only the pitch he put in play
    behind = run("hitter_damage_zone", con, batter=900, season=2026, count_state="behind", min_bip=1)
    assert behind["pitches"].tolist() == [1]
    with pytest.raises(Exception, match="count_state must be one of"):
        run("hitter_damage_zone", con, batter=900, season=2026, count_state="ahead")


def test_league_baselines_totals(con, data_dir):
    out = run("league_baselines", con, season_from=2025, season_to=2026, min_pitches=1)
    df = pd.read_parquet(data_dir / "seq" / "seq_2026_00.parquet")
    thrown = df[df["game_type"].eq("R") & df["pitch_type"].notna()
                & ~df["description"].isin(["automatic_ball", "automatic_strike"])]
    all26 = out[(out["season"] == 2026) & (out["pitch_type"] == "ALL")].iloc[0]
    assert all26["pitches"] == len(thrown)
    by_type = out[(out["season"] == 2026) & (out["pitch_type"] != "ALL")]
    assert by_type["pitches"].sum() == len(thrown)            # the ALL row is the sum of its parts
    assert out[(out["season"] == 2025)]["pitches"].tolist() == [1, 1]   # the 2025 file: ALL and FF
    floored = run("league_baselines", con, season_from=2026, season_to=2026, min_pitches=10**6)
    assert floored["pitch_type"].tolist() == ["ALL"]           # rare types lose their row, never the total


# ------------------------------------------------------------------ the runner

def test_runner_checks_parameters(con):
    with pytest.raises(TypeError, match="needs"):
        run("arsenal_by_count", con, season=2026)
    with pytest.raises(TypeError, match="no input"):
        run("arsenal_by_count", con, pitcher=10, season=2026, team="HOM")
    with pytest.raises(KeyError):
        run("no_such_query", con)


def test_headers_declare_exactly_the_parameters_used():
    for name in queries():
        info = describe(name)
        sql, values = sqlkit.bind(name, **{k: 0 for k, v in info["inputs"].items() if v is REQUIRED})
        assert set(values) == set(info["inputs"])


def test_missing_data_is_a_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        connect(tmp_path)
