"""The exposure-aware hook: hand-checked numbers on a hand-built game. All data here is FICTIONAL."""
import numpy as np
import pandas as pd
import pytest

from baseball.edge import hook as h

COST = {"FF": 0.002, "CH": 0.004}     # fictional costs: runs per pitch per earlier same-type pitch
PPA = 4.0


def _pitch(game, date, ab, num, inning, half, pitcher, batter, pt, velo, desc, rv=0.1, last=False, on_1b=np.nan,
           bat_score=0, fld_score=0):
    return {"game_pk": game, "game_date": date, "game_year": int(date[:4]), "at_bat_number": ab, "pitch_number": num,
            "pitcher": pitcher, "batter": batter, "p_throws": "R", "stand": "R", "pitch_type": pt,
            "release_speed": velo, "description": desc, "events": "single" if last else None, "inning": inning,
            "inning_topbot": half, "outs_when_up": 0, "on_1b": on_1b, "on_2b": np.nan, "on_3b": np.nan,
            "bat_score": bat_score, "fld_score": fld_score, "home_team": "HOM", "away_team": "AWY",
            "delta_run_exp": rv, "delta_home_win_exp": 0.01, "woba_value": 0.9 if last else np.nan,
            "woba_denom": 1.0 if last else np.nan}


def _game() -> pd.DataFrame:
    """FICTIONAL game 1 (2026-05-01). Top half: home starter 1 faces the away lineup 101-109 once, then 101-103
    again in the 4th; reliever 2 starts the 5th against pinch hitter 199 (batting in 104's slot).
    Bottom half: away starter 9 throws one pitch to 201 each inning.
    Top-half PAs: 101 sees FF 95 (ball), CH 85 (whiff), FF 95 (in play); every other PA is one FF in play,
    at 95 in the 1st, 94 in the 2nd, 93 from the 3rd. Every pitch has run value 0.1. Batter 102 bats with a
    runner on first and his team down 2 (fielding team leads by 2)."""
    rows, ab = [], 0
    top = [(101, 1), (102, 1), (103, 1), (104, 2), (105, 2), (106, 2), (107, 3), (108, 3), (109, 3),
           (101, 4), (102, 4), (103, 4), (199, 5)]
    by_inning = {}
    for i, (b, inn) in enumerate(top):
        by_inning.setdefault(inn, []).append((i, b))
    for inn in range(1, 6):
        for i, b in by_inning[inn]:
            ab += 1
            pitcher = 2 if b == 199 else 1
            velo = {1: 95.0, 2: 94.0}.get(inn, 93.0)
            if i == 0:
                rows += [_pitch(1, "2026-05-01", ab, 1, inn, "Top", 1, b, "FF", 95.0, "ball"),
                         _pitch(1, "2026-05-01", ab, 2, inn, "Top", 1, b, "CH", 85.0, "swinging_strike"),
                         _pitch(1, "2026-05-01", ab, 3, inn, "Top", 1, b, "FF", 95.0, "hit_into_play", last=True)]
            else:
                kw = {"on_1b": 555, "bat_score": 0, "fld_score": 2} if i == 1 else {}
                rows.append(_pitch(1, "2026-05-01", ab, 1, inn, "Top", pitcher, b, "FF", velo, "hit_into_play", last=True, **kw))
        ab += 1
        rows.append(_pitch(1, "2026-05-01", ab, 1, inn, "Bot", 9, 201, "SL", 85.0, "hit_into_play", last=True))
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def pa():
    return h.plate_appearances(_game())


def _top(pa, bat_idx):
    return pa[pa["half"].eq("Top") & pa["bat_idx"].eq(bat_idx)].iloc[0]


def test_cost_per_pitch_sign():
    # rv_coef is runs per 100 pitches, pitcher's view: -0.45 -> the offense gains 0.0045 runs per pitch
    c = h.cost_per_pitch(pd.DataFrame({"pitch_type": ["CH", "FF"], "rv_coef": [-0.45, -0.19]}))
    assert c == pytest.approx({"CH": 0.0045, "FF": 0.0019})


def test_pa_outcome_state_and_roles(pa):
    first = _top(pa, 0)
    # three pitches at 0.1 run value each; wOBA only on the last pitch
    assert (first["pitches"], first["rv"], first["woba_value"], first["woba_denom"]) == (3, pytest.approx(0.3), pytest.approx(0.9), 1.0)
    assert first["dwe"] == pytest.approx(0.03)
    second = _top(pa, 1)
    assert (second["base"], second["lead"], second["fld_team"], second["bat_team"]) == (1, 2.0, "HOM", "AWY")
    assert pa.loc[pa["pitcher"].eq(1), "starter"].eq(1).all() and pa.loc[pa["pitcher"].eq(9), "starter"].eq(1).all()
    assert pa.loc[pa["pitcher"].eq(2), "starter"].eq(0).all()
    assert pa["mid_pa_change"].sum() == 0 and len(pa) == 13 + 5


def test_seen_counts_exclude_this_pa(pa):
    tenth = _top(pa, 9)                       # 101's second PA: he saw FF, CH, FF in his first
    assert (tenth["prior_pa"], tenth["seen_FF"], tenth["seen_CH"], tenth["seen_total"]) == (1, 2, 1, 3)
    assert (tenth["seen_after_FF"], tenth["seen_after_total"]) == (3, 4)
    assert (_top(pa, 0)["seen_total"], _top(pa, 0)["prior_pa"]) == (0, 0)
    # the reliever's batter has seen nothing from the reliever
    assert _top(pa, 12)["seen_total"] == 0


def test_pitcher_state_before_and_after(pa):
    tenth = _top(pa, 9)
    # before PA 10: 3 + 8 = 11 pitches, 11 x 0.1 = 1.1 run value, 1 whiff, 2 + 8 = 10 swings, 9 batters faced
    assert (tenth["pitch_count"], tenth["whiffs_so_far"], tenth["swings_so_far"], tenth["bf"]) == (11, 1, 10, 9)
    assert tenth["rv_so_far"] == pytest.approx(1.1)
    assert (tenth["pitch_count_after"], tenth["rv_so_far_after"]) == (12, pytest.approx(1.2))


def test_velocity_drop(pa):
    # first inning fastballs: 95, 95, 95, 95 -> 95. Last three PAs before PA 10 (3rd inning): 93 -> -2
    assert _top(pa, 9)["velo_drop"] == pytest.approx(-2.0)
    # after PA 10: last three PAs are 108, 109, 101 (all 93) -> still -2
    assert _top(pa, 9)["velo_drop_after"] == pytest.approx(-2.0)
    # PA 2: first-inning mean from PA 1 (95, 95) and last PA (95) -> 0, not missing
    assert (_top(pa, 1)["velo_drop"], _top(pa, 1)["velo_missing"]) == (0.0, 0)
    assert _top(pa, 0)["velo_missing"] == 1      # nothing thrown yet


def test_usage_blends_last_season():
    """FICTIONAL pitcher 7: 2025 to right-handers 6 FF + 4 SL; 2026 game 20 (Apr 1) 5 SL; game 21 (Apr 7)."""
    rows = [(2025, "2025-06-01", 10, "FF")] * 6 + [(2025, "2025-06-01", 10, "SL")] * 4
    rows += [(2026, "2026-04-01", 20, "SL")] * 5 + [(2026, "2026-04-07", 21, "FF")]
    p = pd.DataFrame(rows, columns=["game_year", "game_date", "game_pk", "pitch_type"]).assign(pitcher=7, stand="R")
    u = h.usage_table(p, k=10).set_index("game_pk")
    # game 20: nothing this season yet -> last season's shares
    assert (u.loc[20, "use_FF"], u.loc[20, "use_SL"], u.loc[20, "use_src"]) == (pytest.approx(0.6), pytest.approx(0.4), "last season")
    # game 21: (0 + 10 x 0.6) / (5 + 10) = 0.4 FF;  (5 + 10 x 0.4) / 15 = 0.6 SL. Game 21's own pitch is not used.
    assert (u.loc[21, "use_FF"], u.loc[21, "use_SL"], u.loc[21, "use_src"]) == (pytest.approx(0.4), pytest.approx(0.6), "season+last")
    assert np.isnan(u.loc[10, "use_FF"]) and u.loc[10, "use_src"] == "none"     # 2025 has no 2024 here


def test_usage_this_season_only():
    p = pd.DataFrame({"game_year": 2026, "game_date": ["2026-04-01"] * 4 + ["2026-04-06"], "game_pk": [1] * 4 + [2],
                      "pitch_type": ["FF", "FF", "FF", "CU", "CU"], "pitcher": 8, "stand": "L"})
    u = h.usage_table(p).set_index("game_pk")
    assert (u.loc[2, "use_FF"], u.loc[2, "use_CU"], u.loc[2, "use_src"]) == (0.75, 0.25, "season")


def test_exposure_index_and_today_fallback(pa):
    use = h.usage_table(_game())                       # one game: no earlier games -> today's pitches
    d = h.add_index(pa, use, COST, PPA)
    tenth = d[d["half"].eq("Top") & d["bat_idx"].eq(9)].iloc[0]
    # before PA 10 he threw 11 pitches: 10 FF, 1 CH. 101 has seen 2 FF and 1 CH.
    # 4 x (10/11 x 2 x 0.002 + 1/11 x 1 x 0.004) = 4 x (0.0036364 + 0.0003636) = 0.016
    assert tenth["use_src"] == "today"
    assert tenth["idx"] == pytest.approx(0.016)
    # flat cost: the mean of the costs (0.003) for every type: 4 x 0.003 x (10/11 x 2 + 1/11 x 1) = 0.012 x 21/11
    assert tenth["idx_flat"] == pytest.approx(0.012 * 21 / 11)
    assert d.loc[d["prior_pa"].eq(0), "idx"].eq(0).all()


def test_decisions_flag_state_and_lineup_slots(pa):
    use = h.usage_table(_game())
    d = h.decisions(h.add_index(pa, use, COST, PPA), use, COST, PPA)
    d = d[d["pitcher"].eq(1)].set_index("bf")
    # after his 12th batter the next top-half PA is thrown by reliever 2 to start the 5th
    last = d.loc[12]
    assert (last["removed"], last["new_inning"], last["inning"], last["pitch_count"]) == (1, 1, 5, 14)
    # next hitters come from the lineup slots (104, 105, 106), not the pinch hitter who actually batted
    assert (last["batter_0"], last["batter_1"], last["batter_2"], last["slot"]) == (104, 105, 106, 3)
    # 104 saw one FF; through 12 batters he threw 14 pitches (13 FF, 1 CH): 4 x 13/14 x 1 x 0.002
    assert last["idx_0"] == pytest.approx(4 * 13 / 14 * 0.002)
    assert d["removed"].sum() == 1 and d.loc[10, "removed"] == 0
    # before the second time through, the decision's next-hitter index equals the next PA's own index
    nine = d.loc[9]
    assert (nine["batter_0"], nine["prior_pa"], nine["idx_0"]) == (101, 1, pytest.approx(0.016))
    # a first-time-through decision has no slot data
    assert d.loc[3, "next_ok"] == 0


def test_leverage_shrinks_toward_parent():
    # FICTIONAL PAs: cell A (two PAs, |dWE| .02 and .04), cell B in the same inning/half/lead (.06), one more
    # elsewhere (.08). Overall mean .05; parent of A = .04. With k = 1: (.06 + 1 x .04) / 3 = .03333 -> / .05
    d = pd.DataFrame({"inning": [1, 1, 1, 7], "half": "Top", "outs": [0, 0, 1, 2], "base": [0, 0, 0, 3],
                      "lead": [0, 0, 0, 1], "dwe": [0.02, -0.04, 0.06, 0.08]})
    lev = h.leverage_table(d, k=1)
    a = lev[(lev["inn"] == 1) & (lev["outs"] == 0)]["li"].iloc[0]
    assert a == pytest.approx(0.1 / 3 / 0.05)
    assert h.add_leverage(pd.DataFrame({"inning": [3], "half": ["Top"], "outs": [0], "base": [0], "lead": [0]}), lev).iloc[0] == 1.0


def test_shrinkage_k_hand_checked():
    # groups [1, 3] and [5, 7]: within variance 2; variance of means 8; minus 2/2 -> 7; k = 2/7
    assert h.shrinkage_k(pd.Series([1.0, 3, 5, 7]), pd.Series(["a", "a", "b", "b"])) == pytest.approx(2 / 7)


def test_paired_mse_test_hand_checked():
    # d = e0^2 - e1^2 = [1, 3, 0, -3], mean .25; cluster sums of deviations: a 3.5, b -3.5;
    # se = sqrt(2/1 x 24.5) / 4 = 7/4
    r = h.paired_mse_test([1, 2, 0, 1], [0, 1, 0, 2], ["a", "a", "b", "b"])
    assert (r["d_mean"], r["se"], r["mse0"]) == (pytest.approx(0.25), pytest.approx(1.75), pytest.approx(1.5))
    assert r["pct_reduction"] == pytest.approx(100 * 0.25 / 1.5)


def test_decile_table_hand_checked():
    d = pd.DataFrame({"x": [1.0, 2, 3, 4], "y": [0.0, 0, 1, 3], "pitcher": ["a", "b", "c", "d"]})
    tab, diff = h.decile_table(d, "x", "y", q=2)
    assert tab["y_mean"].tolist() == [0.0, 2.0]
    assert (diff["y_diff"], diff["x_diff"]) == (pytest.approx(2.0), pytest.approx(2.0))


def test_fe_fit_predict_recovers_effects():
    """FICTIONAL: y = 2x + pitcher effect + batter effect exactly; predictions on held-out rows match."""
    rng = np.random.default_rng(4)
    n = 600
    d = pd.DataFrame({"p": rng.integers(0, 8, n).astype(str), "b": rng.integers(0, 15, n).astype(str), "x": rng.normal(size=n)})
    pe, be = {str(i): v for i, v in enumerate(rng.normal(size=8))}, {str(i): v for i, v in enumerate(rng.normal(size=15))}
    d["y"] = 2 * d["x"] + d["p"].map(pe) + d["b"].map(be)
    pred = h.fe_fit_predict(d.iloc[:500], d.iloc[500:], "y", ["x"], ["p", "b"], iters=2000)
    assert pred == pytest.approx(d["y"].iloc[500:].to_numpy(), abs=1e-6)
    # with an offset taken at face value the slope left to fit is 1
    d["o"] = d["x"]
    pred = h.fe_fit_predict(d.iloc[:500], d.iloc[500:], "y", ["x"], ["p", "b"], iters=2000, offset="o")
    assert pred == pytest.approx(d["y"].iloc[500:].to_numpy(), abs=1e-6)


def test_calibration_slope_recovered_with_fixed_effects():
    """FICTIONAL PAs: run value = 1.0 x index + pitcher + batter effects + noise -> slope ~1, and 0 when the
    outcome ignores the index."""
    rng = np.random.default_rng(5)
    n = 30_000
    d = pd.DataFrame({"pkey": rng.integers(0, 150, n), "bkey": rng.integers(0, 400, n), "x": rng.gamma(2, 1, n)})
    d["pitcher"] = d["pkey"]
    d["y"] = d["x"] + rng.normal(0, 1, 150)[d["pkey"]] + rng.normal(0, 1, 400)[d["bkey"]] + rng.normal(0, 3, n)
    t = h.fe_ols(d, "y", ["x"], ["pkey", "bkey"]).iloc[0]
    assert t["coef"] == pytest.approx(1.0, abs=4 * t["se"])
    d["y0"] = d["y"] - d["x"]
    assert abs(h.fe_ols(d, "y0", ["x"], ["pkey", "bkey"]).iloc[0]["coef"]) < 4 * t["se"]


def test_expected_vs_reliever_arithmetic():
    model = {"cells": pd.DataFrame({"times": [3], "same_hand": [1], "rv": [0.02], "idx": [0.015]}),
             "reliever": pd.DataFrame({"same_hand": [-1], "rv": [-0.01]})}
    e = h.expected_vs_reliever([3], [1], [0.025], [0.005], model).iloc[0]
    # base 0.02 + 0.005 = 0.025; with the index 0.025 + (0.025 - 0.015) = 0.035; minus the reliever (-0.01)
    assert (e["starter_base"], e["starter_index"]) == (pytest.approx(0.025), pytest.approx(0.035))
    assert (e["cost_base"], e["cost_index"]) == (pytest.approx(0.035), pytest.approx(0.045))


def test_pitcher_quality_uses_only_earlier_games():
    cols = dict(starter=1, mid_pa_change=0, pitcher=1)
    prev = pd.DataFrame({"game_pk": [1, 1], "game_date": ["2025-05-01"] * 2, "rv": [0.1, 0.3], **cols})
    cur = pd.DataFrame({"game_pk": [10, 11, 11], "game_date": ["2026-04-01", "2026-04-07", "2026-04-07"],
                        "rv": [0.5, 0.0, 0.2], **cols})
    q = h.pitcher_quality(prev, cur, league=0.1, k=2).set_index("game_pk")
    # game 10: last season only, mean .2 -> (.2 - .1) x 2/(2+2) = .05
    # game 11: (.4 + .5)/3 = .3 -> (.3 - .1) x 3/5 = .12 (game 11's own PAs are not used)
    assert (q.loc[10, "q"], q.loc[11, "q"], q.loc[11, "q_n"]) == (pytest.approx(0.05), pytest.approx(0.12), 3)


def test_bullpen_load_previous_three_days():
    pa = pd.DataFrame({"starter": 0, "fld_team": "T", "pitches": [30, 20, 10],
                       "game_date": ["2026-04-01", "2026-04-02", "2026-04-04"]})
    b = h.bullpen_load(pa).set_index("game_date")["pen_load"]
    # Apr 4: Apr 1-3 = 30 + 20 + 0 = 50; Apr 2: Apr 1 = 30; Apr 1: nothing earlier
    assert (b["2026-04-04"], b["2026-04-02"], b["2026-04-01"]) == (50, 30, 0)


def test_runs_per_woba_and_matchup():
    d = pd.DataFrame({"woba_denom": 1, "woba_value": [0.0, 0.9, 2.0, 0.7], "rv": [-0.2, 0.52, 1.4, 0.36]})
    # rv = 0.8 x wOBA - 0.2 exactly
    assert h.runs_per_woba(d) == pytest.approx(0.8)
    p = pd.DataFrame({"batter": 1, "game_year": 2026, "pitch_type": ["FF", "FF"], "delta_run_exp": [0.1, 0.1]})
    pa = pd.DataFrame({"batter": [1], "game_year": [2026], "use_FF": [0.5], "use_SL": [0.5]})
    for t in h.COST_TYPES:
        if f"use_{t}" not in pa:
            pa[f"use_{t}"] = 0.0
    # fastballs: 0.2 / (2 + 2) = 0.05 per pitch; breaking: none -> 0. 0.5 x 0.05 = 0.025
    assert h.matchup(p, pa, k=2)[0] == pytest.approx(0.025)


def test_hook_card_on_the_fictional_game(pa):
    use = h.usage_table(_game())
    cells = pd.DataFrame([(t, s, 0.01 * t, 0.002 * t, 100) for t in range(1, 5) for s in (0, 1)],
                         columns=["times", "same_hand", "rv", "idx", "n"])
    ctx = {"pa": h.add_index(pa, use, COST, PPA), "use": use, "cost": COST, "ppa": PPA,
           "model": {"cells": cells, "reliever": pd.DataFrame({"same_hand": [-1], "rv": [0.0]})},
           "quality": pd.DataFrame({"pitcher": [1], "game_pk": [1], "q": [0.005]})}
    card = h.hook_card(1, 1, ctx, names={104: "Fictional Four"}).set_index("after_bf")
    assert list(card.index) == [9, 10, 11, 12]            # from the second time through
    r = card.loc[12]
    assert (r["hitter_1"], r["times_1"], r["removed"]) == ("Fictional Four", 2, 1)
    # idx 4 x 13/14 x 0.002 = 0.0074286 -> 0.74 per 100 PAs; second time, same hand:
    # base cost = 0.02 + 0.005 - 0 = 0.025 (2.5 per 100); with index + (0.0074286 - 0.004)
    assert r["idx_1"] == pytest.approx(100 * 4 * 13 / 14 * 0.002)
    assert r["cost_base_1"] == pytest.approx(2.5)
    assert r["cost_index_1"] == pytest.approx(100 * (0.025 + 4 * 13 / 14 * 0.002 - 0.004))
