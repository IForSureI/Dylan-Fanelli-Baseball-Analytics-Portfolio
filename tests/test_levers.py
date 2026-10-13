"""Pitch-design levers: hand-built FICTIONAL pitches and pairs with the arithmetic in the comments."""
import numpy as np
import pandas as pd
import pytest

from baseball.development import levers as L


def _pitch(**kw):
    base = {"game_pk": 1, "game_date": "2025-05-01", "game_year": 2025, "at_bat_number": 1, "pitch_number": 1,
            "inning": 1, "inning_topbot": "Top", "pitcher": 1, "player_name": "Fictional, A", "p_throws": "R",
            "stand": "R", "pitch_type": "FF", "description": "ball", "zone": 11, "release_speed": 95.0,
            "release_spin_rate": 2300.0, "release_extension": 6.5, "release_pos_x": -2.0, "release_pos_z": 6.0,
            "arm_angle": 45.0, "pfx_x": -0.5, "pfx_z": 1.25, "delta_run_exp": 0.0, "age_pit": 27}
    base.update(kw)
    return base


def test_shape_columns_units_and_arm_side_sign():
    p = L.shape_columns(pd.DataFrame([
        _pitch(),                                                     # RHP: pfx_x -0.5 ft is arm side
        _pitch(p_throws="L", pfx_x=0.5, release_pos_x=2.0),            # LHP: +0.5 ft is arm side
        _pitch(pitch_type="KC"),
    ]))
    # -0.5 ft * 12 * (-1) = +6 in arm side for the righty; +0.5 * 12 * (+1) = +6 for the lefty
    assert p["hb_arm_in"].tolist() == [6.0, 6.0, 6.0]
    assert p["ivb_in"].iloc[0] == 15.0                               # 1.25 ft * 12
    assert p["rel_x_arm_in"].tolist() == [24.0, 24.0, 24.0]          # 2 ft toward the arm side either way
    assert p["ext_in"].iloc[0] == 78.0                               # 6.5 ft * 12
    assert p["pitch_type"].iloc[2] == "CU"                           # knuckle-curves pooled with curveballs


def test_roles_from_first_pitch_of_each_half_inning():
    rows = [
        # game 1: pitcher 1 starts the top of the 1st (home starter); pitcher 2 starts the bottom; 3 relieves
        _pitch(game_pk=1, pitcher=1, inning=1, inning_topbot="Top", at_bat_number=1),
        _pitch(game_pk=1, pitcher=2, inning=1, inning_topbot="Bot", at_bat_number=4),
        _pitch(game_pk=1, pitcher=3, inning=7, inning_topbot="Top", at_bat_number=50),
        # game 2: pitcher 1 starts again; pitcher 3 relieves; pitcher 2 relieves
        _pitch(game_pk=2, pitcher=1, inning=1, inning_topbot="Top", at_bat_number=1),
        _pitch(game_pk=2, pitcher=3, inning=8, inning_topbot="Top", at_bat_number=60),
        _pitch(game_pk=2, pitcher=2, inning=9, inning_topbot="Bot", at_bat_number=70),
    ]
    r = L.roles(pd.DataFrame(rows)).set_index("pitcher")
    assert r.loc[1, "role"] == "SP" and r.loc[1, "starts"] == 2      # 2 starts in 2 games
    assert r.loc[2, "role"] == "SP"                                    # 1 start in 2 games = 50%, the cutoff
    assert r.loc[3, "role"] == "RP" and r.loc[3, "starts"] == 0


def test_halves_split_where_half_the_pitches_are_thrown():
    # Games of 10, 10 and 20 pitches: pitches before each game 0, 10, 20 of 40 -> halves 1, 1, 2
    rows = []
    for g, (d, k) in enumerate([("2025-04-01", 10), ("2025-04-06", 10), ("2025-04-11", 20)], start=1):
        rows += [_pitch(game_pk=g, game_date=d, pitch_number=i + 1) for i in range(k)]
    p = pd.DataFrame(rows)
    halves = pd.Series(L._halves(p), index=p.index)
    assert halves.groupby(p["game_pk"]).first().tolist() == [1, 1, 2]


def test_pitch_season_rates_after_aggregation():
    rows = ([_pitch(description="swinging_strike", delta_run_exp=-0.05)] * 3       # 3 whiffs
            + [_pitch(description="foul", delta_run_exp=-0.03)] * 5                # 5 swings, no whiff
            + [_pitch(description="ball", delta_run_exp=0.04)] * 2
            + [_pitch(pitch_type="SL", description="ball", delta_run_exp=0.04)] * 10)
    ps = L.pitch_seasons(L.shape_columns(pd.DataFrame(rows))).set_index("pitch_type")
    ff = ps.loc["FF"]
    assert ff["swings"] == 8 and ff["whiffs"] == 3
    assert ff["whiff_pct"] == pytest.approx(37.5)                    # 3 / 8
    # run value, pitcher's view: -(3*-0.05 + 5*-0.03 + 2*0.04) = 0.22 runs on 10 pitches -> 2.2 per 100
    assert ff["rv100"] == pytest.approx(2.2)
    assert ff["usage_pct"] == pytest.approx(50.0)                    # 10 of 20 pitches


def test_league_net_removes_the_median_shift():
    d = pd.DataFrame({"pitch_type": ["FF"] * 4 + ["SL"] * 2, "chg": [1.0, 2.0, 3.0, 10.0, -1.0, 1.0]})
    # FF median of 1, 2, 3, 10 is 2.5; SL median of -1, 1 is 0
    assert L.league_net(d, "chg", ["pitch_type"]).tolist() == [-1.5, -0.5, 0.5, 7.5, -1.0, 1.0]


def test_relative_levers_use_one_primary_fastball_across_seasons():
    ps = pd.DataFrame([
        # pitcher 1: more FF than SI over the two seasons -> FF is the primary fastball in both
        {"pitcher": 1, "season": 2024, "pitch_type": "FF", "n": 500, "velo": 95.0, "ivb_in": 16.0, "hb_arm_in": 8.0},
        {"pitcher": 1, "season": 2025, "pitch_type": "FF", "n": 300, "velo": 96.0, "ivb_in": 17.0, "hb_arm_in": 8.0},
        {"pitcher": 1, "season": 2025, "pitch_type": "SI", "n": 400, "velo": 94.0, "ivb_in": 8.0, "hb_arm_in": 15.0},
        {"pitcher": 1, "season": 2024, "pitch_type": "SL", "n": 200, "velo": 86.0, "ivb_in": 1.0, "hb_arm_in": -4.0},
        {"pitcher": 1, "season": 2025, "pitch_type": "SL", "n": 200, "velo": 86.0, "ivb_in": -2.0, "hb_arm_in": -4.0},
    ])
    for c in ("ivb_in", "hb_arm_in"):
        for h in ("h1", "h2"):
            ps[f"{c}_{h}"] = ps[c]
    ps["hb_arm_in_h1"] = ps["hb_arm_in"]
    t = L.add_relative(ps, [2024, 2025]).set_index(["season", "pitch_type"])
    assert t.loc[(2025, "SI"), "primary_fb"] == "FF"                 # 800 FF vs 400 SI over both seasons
    assert t.loc[(2024, "SL"), "speed_gap"] == 9.0                   # 95 - 86
    assert t.loc[(2025, "SL"), "speed_gap"] == 10.0                  # 96 - 86
    # separation 2025: hypot(-2 - 17, -4 - 8) = hypot(19, 12) = 22.47
    assert t.loc[(2025, "SL"), "separation_in"] == pytest.approx(np.hypot(19, 12))
    assert np.isnan(t.loc[(2025, "FF"), "speed_gap"])                # the primary fastball has no gap to itself
    assert t.loc[(2025, "SL"), "hb_own_in"] == 4.0                   # sliders report glove-side break: -(-4)


def test_threshold_is_the_90th_percentile_of_within_season_movement():
    noise = pd.DataFrame({"pitch_type": "FF", "lever": "velo", "net": np.arange(-10, 11) / 10})
    th = L.thresholds(noise).iloc[0]
    # |net| = 0, 0.1 (x2), ..., 1.0 (x2): 21 values; the 90th percentile by linear interpolation is 0.9
    assert th["threshold"] == pytest.approx(0.9)
    assert th["pitch_seasons"] == 21


def test_flag_changes_uses_the_threshold_and_a_quiet_zone():
    pr = pd.DataFrame({"pitch_type": "FF", **{f"net_{lv}": np.nan for lv in L.LEVERS}}, index=range(4))
    pr["net_velo"] = [1.2, -1.0, 0.4, 0.7]
    th = pd.DataFrame({"pitch_type": ["FF"], "lever": ["velo"], "threshold": [1.0]})
    c = L.flag_changes(pr, th)["chg_velo"].tolist()
    # >= 1.0 up, <= -1.0 down, < 0.5 within noise, 0.5-1.0 in between (neither group)
    assert c[:3] == [1, -1, 0] and np.isnan(c[3])


def test_cem_weights_make_controls_stand_in_for_the_treated_mix():
    d = pd.DataFrame({"s": ["A", "A", "A", "B", "B", "B", "C"], "treat": [1, 0, 0, 1, 1, 0, 1]})
    w = L.cem_weights(d, "treat", ["s"]).tolist()
    # matched treated 3 (A: 1, B: 2), matched controls 3 (A: 2, B: 1); C has no control -> dropped
    # control weight = (treated/controls in stratum) * (3 / 3): A 1/2 = 0.5, B 2/1 = 2
    assert w == [1.0, 0.5, 0.5, 1.0, 1.0, 2.0, 0.0]


def test_retention_is_net_of_the_league_shift():
    # 10 -> 12 -> 11.5 while the league moved +0.5 each time: first-year net change 1.5, two-year net 1.0 -> 2/3 kept
    assert L.retention(10, 12, 11.5, league01=0.5, league02=0.5) == pytest.approx(2 / 3)
    assert L.retention(10, 12, 10) == 0.0


def test_display_reads_breaking_ball_depth_as_drop():
    assert L.display("SL", "ivb") == ("drop, +2 in (less induced vertical break)", -1.0)
    assert L.display("FF", "ivb")[1] == 1.0
    assert L.display("ST", "hb")[0].startswith("glove-side")
    assert "gap" not in L.levers_for("FF") and "gap" in L.levers_for("CH")


def _pairs(n=1500, effect=0.0, seed=0, pair="2024-2025"):
    """FICTIONAL pairs with regression to the mean built in: pitchers change a pitch after a bad-luck season
    (low observed whiff% for their talent), and the shape change has `effect` whiff points per unit."""
    rng = np.random.default_rng(seed)
    talent = rng.normal(25, 5, n)
    y0 = talent + rng.normal(0, 4, n)
    y1 = talent + rng.normal(0, 4, n)
    x0 = talent + rng.normal(0, 2, n)
    net = -0.1 * (y0 - 25) + rng.normal(0, 1, n)        # a bad season makes a change more likely
    swings = rng.integers(60, 400, n)
    d = pd.DataFrame({"pitcher": np.arange(n), "pitch_type": "FF", "pair": pair, "whiff_pct_0": y0, "x_whiff_pct_0": x0,
                      "rv100_0": rng.normal(0, 1, n), "log_swings": np.log(swings), "swings_0": swings,
                      "age_0": rng.integers(22, 36, n).astype(float), "role_0": rng.choice(["SP", "RP"], n),
                      "role_change": rng.integers(0, 2, n), "w": 100.0, "net_velo": net})
    d["d_whiff"] = y1 - y0 + effect * net
    d["d_xwhiff"] = 0.9 * effect * net + rng.normal(0, 0.3, n)
    return d


def test_prior_season_controls_remove_regression_to_the_mean():
    d = _pairs(effect=0.0)
    naive = L.ols_clustered(d, "d_whiff", ["net_velo"], controls=[]).iloc[0]
    adj = L.ols_clustered(d, "d_whiff", ["net_velo"]).iloc[0]
    # Naive slope: cov(net, y1 - y0) / var(net) = (-0.1 * -16) / (0.01 * 41 + 1) = 1.6 / 1.41 = 1.13: a spurious "payoff"
    assert naive["coef"] == pytest.approx(1.13, abs=0.25)
    # With the prior season's actual and expected whiff held fixed, the change carries no information: ~0
    assert abs(adj["coef"]) < 2.5 * adj["se"]


def test_planted_payoff_is_recovered_and_priced_for_a_plan():
    d = _pairs(effect=1.5, seed=1)
    adj = L.ols_clustered(d, "d_whiff", ["net_velo"]).iloc[0]
    assert adj["coef"] == pytest.approx(1.5, abs=3 * adj["se"])
    prior = {"whiff_pct_0": 20.0, "x_whiff_pct_0": 25.0, "rv100_0": 0.0, "swings_0": 200, "age_0": 27.0, "role_0": "SP"}
    t = L.plan_target(d, prior, "FF", "velo", planned_change=1.0)
    assert t["with_change"] == pytest.approx(t["drift"] + t["lever_part"])
    assert t["lever_part"] == pytest.approx(t["coef_per_unit"] * 1.0)
    assert t["drift"] > 0          # an unlucky 20% on 25% expected stuff should drift up with no change at all


def test_out_of_sample_validation_credits_a_real_lever():
    train, test = _pairs(effect=1.5, seed=2), _pairs(effect=1.5, seed=3, pair="2025-2026")
    for k, lv in enumerate(L.LEVERS):          # the other levers: present but pure noise
        if lv != "velo":
            rng = np.random.default_rng(100 + k)
            train[f"net_{lv}"], test[f"net_{lv}"] = rng.normal(0, 1, len(train)), rng.normal(0, 1, len(test))
    v = L.validate(train, test, types=["FF"], boot=200).set_index("pitch_type").loc["FF"]
    assert v["gain_levers_pct"] > 0 and v["gain_physics_pct"] > 0
    assert v["gain_levers_lo"] <= v["gain_levers_pct"] <= v["gain_levers_hi"]
