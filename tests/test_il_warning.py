"""Velocity and stuff decline as an IL early warning: hand-checked numbers on hand-built data.
All data here is FICTIONAL (made-up pitchers, games and transactions)."""
import math

import numpy as np
import pandas as pd
import pytest

from baseball.health import il_warning as w


# ---------------------------------------------------------------- injuries and transactions

@pytest.mark.parametrize("reason,cat", [
    ("Right elbow inflammation.", "arm"),
    ("Right UCL sprain.", "arm"),
    ("Right lat strain.", "arm"),
    ("Right shoulder impingement.", "arm"),
    ("Left hip labral tear.", "lower"),           # a hip labrum is lower body, not the shoulder labrum
    ("Right middle finger blister.", "hand"),
    ("Left oblique strain.", "trunk"),
    ("Right hamstring strain.", "lower"),
    ("Viral illness.", "illness"),
    ("Right inflammation.", "other"),             # "inflammation" contains "lat" but not as a word
    ("Right brachialis muscle injury.", "arm"),   # wordings and typos from MLB's own transaction text
    ("Bone stress reaction to the left ulna.", "arm"),
    ("Left AC Joint Sprain.", "arm"),
    ("Right elnow sprain.", "arm"),
    ("Unar nerve inflammation.", "arm"),
    ("", "unspecified"),
])
def test_classify_injury(reason, cat):
    assert w.classify_injury(reason) == cat


def _tx(desc, date, eff=None, pid=1, team="Fictional Club"):
    t = {"description": desc, "date": date, "person": {"id": pid, "fullName": "Pitcher One"}, "toTeam": {"name": team}}
    if eff:
        t["effectiveDate"] = eff
    return t


def test_parse_placements_keeps_placements_only_and_uses_the_retroactive_date():
    tx = [
        _tx("Fictional Club placed RHP Pitcher One on the 15-day injured list retroactive to May 8, 2026. Right forearm strain.",
            "2026-05-10", "2026-05-08"),
        _tx("Fictional Club transferred RHP Pitcher One from the 15-day injured list to the 60-day injured list.",
            "2026-06-01", "2026-06-01"),
        _tx("Fictional Club activated RHP Pitcher One from the 15-day injured list.", "2026-07-01", "2026-07-01"),
        _tx("Fictional Club placed LHP Pitcher Two on the 15-day injured list. Left knee sprain.", "2026-08-02", pid=2),
    ]
    il = w.parse_placements(tx)
    assert len(il) == 2                                       # the transfer and the activation are not placements
    one = il[il["person"].eq(1)].iloc[0]
    assert one["effective"] == pd.Timestamp("2026-05-08") and one["announced"] == pd.Timestamp("2026-05-10")
    assert one["il_days"] == 15 and one["category"] == "arm"
    two = il[il["person"].eq(2)].iloc[0]
    assert two["effective"] == pd.Timestamp("2026-08-02") and two["category"] == "lower"   # no effectiveDate: the date


# ---------------------------------------------------------------- outings

def _pitch(game, date, ab, num, pitcher, half, pt, velo, spin=2300.0, ivb=1.25):
    return {"game_pk": game, "game_date": date, "game_year": int(date[:4]), "at_bat_number": ab, "pitch_number": num,
            "pitcher": pitcher, "inning_topbot": half, "home_team": "HOM", "away_team": "AWY", "pitch_type": pt,
            "age_pit": 28, "release_speed": velo, "release_spin_rate": spin, "pfx_z": ivb, "release_extension": 6.5,
            "release_pos_z": 5.8, "arm_angle": 40.0}


def test_appearances_starter_team_and_pitch_count():
    """FICTIONAL game 1: home pitcher 10 throws the top of the 1st (3 pitches), reliever 11 one pitch in the top of
    the 2nd; away pitcher 20 throws the bottom of the 1st (2 pitches)."""
    p = pd.DataFrame([_pitch(1, "2026-05-01", 1, 1, 10, "Top", "FF", 95), _pitch(1, "2026-05-01", 1, 2, 10, "Top", "SL", 85),
                      _pitch(1, "2026-05-01", 2, 1, 10, "Top", "FF", 95), _pitch(1, "2026-05-01", 3, 1, 20, "Bot", "SI", 93),
                      _pitch(1, "2026-05-01", 3, 2, 20, "Bot", "SI", 93), _pitch(1, "2026-05-01", 4, 1, 11, "Top", "FF", 97)])
    a = w.appearances(p).set_index("pitcher")
    assert a.loc[10, "team"] == "HOM" and a.loc[20, "team"] == "AWY" and a.loc[11, "team"] == "HOM"
    assert a.loc[10, "starter"] == 1 and a.loc[20, "starter"] == 1 and a.loc[11, "starter"] == 0
    assert a.loc[10, "pitches"] == 3 and a.loc[11, "pitches"] == 1


def test_pitch_clock_automatic_balls_and_strikes_are_not_pitches():
    """FICTIONAL: pitcher 10 throws two pitches and is charged an automatic ball (no pitch thrown, no tracking).
    His count is 2, not 3; a row without the description column counts every row."""
    rows = [_pitch(1, "2026-05-01", 1, 1, 10, "Top", "FF", 95), _pitch(1, "2026-05-01", 1, 2, 10, "Top", "FF", 95),
            _pitch(1, "2026-05-01", 1, 3, 10, "Top", None, float("nan"))]
    for r, d in zip(rows, ("ball", "called_strike", "automatic_ball")):
        r["description"] = d
    assert w.appearances(pd.DataFrame(rows)).set_index("pitcher").loc[10, "pitches"] == 2
    rows[2]["description"] = "automatic_strike"
    assert w.appearances(pd.DataFrame(rows)).set_index("pitcher").loc[10, "pitches"] == 2


def test_type_games_means_and_within_game_sum_of_squares():
    """Pitcher 10 throws FF at 94 and 96 and a slider: FF mean 95, sum of squares (94-95)^2 + (96-95)^2 = 2.
    Ride is pfx_z x 12: 1.25 ft -> 15 in."""
    p = pd.DataFrame([_pitch(1, "2026-05-01", 1, 1, 10, "Top", "FF", 94), _pitch(1, "2026-05-01", 1, 2, 10, "Top", "FF", 96),
                      _pitch(1, "2026-05-01", 1, 3, 10, "Top", "SL", 85)])
    tg = w.type_games(p)
    assert len(tg) == 1 and tg.iloc[0]["ptype"] == "FF"     # the slider is not a fastball type
    assert tg.iloc[0]["n"] == 2 and tg.iloc[0]["velo"] == pytest.approx(95.0) and tg.iloc[0]["velo_ss"] == pytest.approx(2.0)
    assert tg.iloc[0]["ivb"] == pytest.approx(15.0)


def test_noise_params_sigma2_and_gamma2():
    """FICTIONAL pitcher, three games of two four-seamers: (94, 96), (96, 98), (98, 100).
    sigma2 = pooled within-game variance = (2 + 2 + 2) / (1 + 1 + 1) = 2.
    Game means 95, 97, 99 around the season mean 97: deviations -2, 0, 2. With the G/(G-1) = 3/2 correction the raw
    variance is (4 x 1.5 + 0 + 4 x 1.5) / 3 = 4; less sigma2 / n = 2 / 2 = 1 gives gamma2 = 3."""
    rows = []
    for g, (v1, v2) in enumerate([(94, 96), (96, 98), (98, 100)], start=1):
        rows += [_pitch(g, f"2026-05-0{g}", 1, 1, 10, "Top", "FF", v1), _pitch(g, f"2026-05-0{g}", 1, 2, 10, "Top", "FF", v2)]
    P = w.noise_params(w.type_games(pd.DataFrame(rows))).set_index(["ptype", "metric"])
    assert P.at[("FF", "velo"), "sigma2"] == pytest.approx(2.0)
    assert P.at[("FF", "velo"), "gamma2"] == pytest.approx(3.0)


def test_season_curve_is_the_mean_deviation_by_month():
    """FICTIONAL: one pitcher, an April game at 94 and a July game at 96 (season mean 95): the April shift is -1 and
    the July shift +1. Adjusting removes it: both games become 95."""
    p = pd.DataFrame([_pitch(1, "2026-04-10", 1, 1, 10, "Top", "FF", 94), _pitch(2, "2026-07-10", 1, 1, 10, "Top", "FF", 96)])
    tg = w.type_games(p)
    c = w.season_curve(tg)
    v = c[c["metric"].eq("velo")].set_index("month")["shift"]
    assert v[4] == pytest.approx(-1.0) and v[7] == pytest.approx(1.0)
    assert w._adjust(tg, c)["velo"].tolist() == pytest.approx([95.0, 95.0])


# ---------------------------------------------------------------- baselines and drops

def _params(gamma2=0.5, sigma2=1.0, tau2=1.0, delta2=0.25, league=95.0):
    return pd.DataFrame([{"ptype": "FF", "metric": m, "sigma2": sigma2, "gamma2": gamma2, "tau2": tau2, "delta2": delta2,
                          "league": league} for m in w.METRICS])


def _tg(rows):
    """Type-game rows (pitcher, game_pk, date, season, n, velo); every metric takes the velo value."""
    out = []
    for pid, g, date, season, n, v in rows:
        r = {"pitcher": pid, "game_pk": g, "ptype": "FF", "game_date": pd.Timestamp(date), "season": season, "n": n}
        for m in w.METRICS:
            r[m], r[f"{m}_n"], r[f"{m}_ss"] = v, n, 0.0
        out.append(r)
    return pd.DataFrame(out)


NO_CURVE = pd.DataFrame(columns=["ptype", "month", "shift", "metric"])


def test_drop_against_a_league_prior():
    """FICTIONAL pitcher with no last season: prior = league 95 with variance tau2 = 1. Each game has two pitches, so
    its noise is gamma2 + sigma2 / n = 0.5 + 1 / 2 = 1. Games at 95, 97, then 93.
    Third game, k = 1: baseline = (95/1 + 95/1 + 97/1) / (1 + 1 + 1) = 287/3 = 95.667, variance 1/3.
    Window = 93 (variance 1). Drop = 2.667; z = 2.667 / sqrt(1/3 + 1) = 2.309.
    Third game, k = 3: baseline is the prior alone (95, variance 1); window = mean(95, 97, 93) = 95 with variance
    1/3: drop 0, z 0."""
    d = w.add_drops(_tg([(1, 1, "2026-05-01", 2026, 2, 95.0), (1, 2, "2026-05-06", 2026, 2, 97.0),
                         (1, 3, "2026-05-11", 2026, 2, 93.0)]), _params(), NO_CURVE)
    r = d[d["game_pk"].eq(3)].iloc[0]
    assert r["base_velo_1"] == pytest.approx(287 / 3)
    assert r["drop_velo_1"] == pytest.approx(287 / 3 - 93)
    assert r["z_velo_1"] == pytest.approx((287 / 3 - 93) / math.sqrt(1 / 3 + 1))
    assert r["drop_velo_3"] == pytest.approx(0.0) and r["z_velo_3"] == pytest.approx(0.0)
    assert r["prior_velo"] == "league"
    # the first two games have fewer than three outings, so their k = 3 window is empty
    assert d[d["game_pk"].lt(3)]["z_velo_3"].isna().all()


def test_drop_against_last_season():
    """FICTIONAL: last season, one game at 96 with noise 1, so the prior is 96 with variance 1 + delta2 = 1.25.
    This season's first game at 94: baseline (k = 1) = 96, drop 2, z = 2 / sqrt(1.25 + 1) = 1.333."""
    d = w.add_drops(_tg([(1, 1, "2025-08-01", 2025, 2, 96.0), (1, 2, "2026-04-05", 2026, 2, 94.0)]), _params(), NO_CURVE)
    r = d[d["game_pk"].eq(2)].iloc[0]
    assert r["prior_velo"] == "last"
    assert r["base_velo_1"] == pytest.approx(96.0)
    assert r["z_velo_1"] == pytest.approx(2 / math.sqrt(2.25))


def test_outing_features_weight_types_by_pitches():
    """FICTIONAL outing with 10 four-seamers 2 mph down and 30 sinkers on baseline: combined drop = (10 x 2 + 30 x 0)
    / 40 = 0.5 mph. The fastball baseline is the pitch-weighted (10 x 95 + 30 x 93) / 40 = 93.5."""
    base = {f"{k}_{m}_{n}": 0.0 for k in ("drop", "z") for m in w.METRICS for n in (1, 3)}
    rows = [dict(base, pitcher=1, season=2026, game_pk=5, ptype="FF", n=10, base_velo_1=95.0, prior_velo="last",
                 games_before_1=4, drop_velo_1=2.0, z_velo_1=2.0),
            dict(base, pitcher=1, season=2026, game_pk=5, ptype="SI", n=30, base_velo_1=93.0, prior_velo="last",
                 games_before_1=4)]
    app = pd.DataFrame([{"pitcher": 1, "game_pk": 5}])
    f = w.outing_features(app, pd.DataFrame(rows), windows=(1,)).iloc[0]
    assert f["drop_velo_1"] == pytest.approx(0.5) and f["z_velo_1"] == pytest.approx(0.5)
    assert f["fb_base_velo"] == pytest.approx(93.5) and f["prior_last_share"] == pytest.approx(1.0)


# ---------------------------------------------------------------- labels and context

def _il(rows):
    return pd.DataFrame([{"person": p, "effective": pd.Timestamp(e), "announced": pd.Timestamp(a), "category": c}
                         for p, e, a, c in rows])


def test_label_window_lead_and_last_outing():
    """FICTIONAL pitcher: outings May 1, May 5 and May 20; an arm placement effective May 10 (announced May 12).
    May 1: 9 days before, inside 14 -> 1, not his last outing before it (May 5 is). May 5: 5 days -> 1, last.
    May 20: no placement after it -> 0. Lead to the announcement from May 5 is 7 days."""
    a = pd.DataFrame({"pitcher": 1, "game_pk": [1, 2, 3], "game_date": pd.to_datetime(["2026-05-01", "2026-05-05", "2026-05-20"])})
    d = w.label(a, _il([(1, "2026-05-10", "2026-05-12", "arm")]), 14, ["arm"])
    assert d["y"].tolist() == [1, 1, 0]
    assert d["y_days"].tolist()[:2] == [9.0, 5.0]
    assert d["y_last_before"].tolist() == [0, 1, 0]
    assert d["y_lead_announced"].iloc[1] == 7.0
    # a 7-day horizon drops May 1 (9 days); a lower-body placement doesn't count for the arm label
    assert w.label(a, _il([(1, "2026-05-10", "2026-05-12", "arm")]), 7, ["arm"])["y"].tolist() == [0, 1, 0]
    assert w.label(a, _il([(1, "2026-05-10", "2026-05-12", "lower")]), 14, ["arm"])["y"].sum() == 0


def test_label_placement_on_the_outing_day_does_not_count():
    """Only placements strictly after the outing's date: one effective the same day is not a forecast."""
    a = pd.DataFrame({"pitcher": [1], "game_pk": [1], "game_date": pd.to_datetime(["2026-05-01"])})
    assert w.label(a, _il([(1, "2026-05-01", "2026-05-01", "arm")]), 14, ["arm"])["y"].tolist() == [0]


def test_add_context_il_history_rest_and_pitch_ratio():
    """FICTIONAL pitcher (starter): 80 pitches Apr 1, 100 pitches Apr 6, 45 pitches Apr 12; an IL placement effective
    Mar 1, 2025 (more than 365 days before) and one Apr 3, 2026.
    Apr 1: il_365 = 0. Apr 6 and Apr 12: 1. Rest Apr 6 = 5 days. Pitch ratio Apr 12 = 45 / mean(80, 100) = 0.5."""
    a = pd.DataFrame({"pitcher": 1, "game_pk": [1, 2, 3], "season": 2026, "starter": 1, "age": 28,
                      "game_date": pd.to_datetime(["2026-04-01", "2026-04-06", "2026-04-12"]), "pitches": [80, 100, 45]})
    il = _il([(1, "2025-03-01", "2025-03-01", "arm"), (1, "2026-04-03", "2026-04-03", "arm")])
    c = w.add_context(a, il)
    assert c["il_365"].tolist() == [0, 1, 1]
    assert c["rest"].iloc[1] == 5
    assert c["pitch_ratio"].tolist() == pytest.approx([1.0, 1.25, 0.5])
    assert c["m4"].tolist() == [1, 1, 1]


def test_eligible():
    base = dict(z_velo_1=1.0, z_velo_3=1.0, prior_last_share=0.0, fb_games_before=3, fb_base_velo=94.0)
    a = pd.DataFrame([base, dict(base, fb_games_before=2), dict(base, fb_games_before=2, prior_last_share=1.0),
                      dict(base, fb_base_velo=72.0), dict(base, z_velo_3=np.nan)])
    assert w.eligible(a).tolist() == [True, False, True, False, False]


# ---------------------------------------------------------------- models and scoring

def test_logit_fit_recovers_the_log_odds_ratio():
    """FICTIONAL 2 x 2 table: x = 0 has 10 events in 100, x = 1 has 30 in 100. A saturated logistic fit gives
    intercept log(10/90) = -2.197 and slope log((30/70) / (10/90)) = log(3.857) = 1.350, with the usual standard
    error sqrt(1/10 + 1/90 + 1/30 + 1/70) = 0.398."""
    x = np.r_[np.zeros(100), np.ones(100)]
    y = np.r_[np.ones(10), np.zeros(90), np.ones(30), np.zeros(70)]
    f = w.logit_fit(np.column_stack([np.ones(200), x]), y)
    assert f["coef"][0] == pytest.approx(math.log(10 / 90))
    assert f["coef"][1] == pytest.approx(math.log((30 / 70) / (10 / 90)))
    assert f["se"][1] == pytest.approx(math.sqrt(1 / 10 + 1 / 90 + 1 / 30 + 1 / 70))


def test_auc_by_hand():
    """Pairs (event, non-event): 0.35 beats 0.1 but not 0.4; 0.8 beats both: 3 of 4 = 0.75. A tie counts half."""
    assert w.auc([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]) == pytest.approx(0.75)
    assert w.auc([0, 1], [0.5, 0.5]) == pytest.approx(0.5)


def test_log_loss_and_brier_by_hand():
    """y = (1, 0), p = (0.8, 0.2): log loss = -ln 0.8 = 0.2231; Brier = (0.04 + 0.04) / 2 = 0.04."""
    assert w.log_loss([1, 0], [0.8, 0.2]) == pytest.approx(-math.log(0.8))
    assert w.brier([1, 0], [0.8, 0.2]) == pytest.approx(0.04)


def test_recalibration_of_a_calibrated_forecast():
    """FICTIONAL: p = 0.1 on 10 rows with 1 event, p = 0.5 on 10 rows with 5 events. The forecast is exactly
    calibrated, so the slope is 1 and the intercept (slope held at 1) is 0."""
    p = np.r_[np.full(10, 0.1), np.full(10, 0.5)]
    y = np.r_[1, np.zeros(9), np.ones(5), np.zeros(5)]
    r = w.recalibration(y, p)
    assert r["slope"] == pytest.approx(1.0, abs=1e-6) and r["intercept_at_slope_1"] == pytest.approx(0.0, abs=1e-9)


def test_bootstrap_compare_of_identical_models_is_zero():
    rng = np.random.default_rng(3)
    y = rng.integers(0, 2, 200)
    p = rng.random(200)
    r = w.bootstrap_compare(y, p, p, np.repeat(np.arange(20), 10), reps=50)
    assert r["auc"]["diff"] == 0 and r["log_loss"]["lo"] == 0 and r["log_loss"]["hi"] == 0


def _alerts_frame():
    """FICTIONAL test season, 10 outings. Two IL stints: pitcher 1 (outings 0 and 1 before it, 6 and 2 days out;
    announced 8 and 4 days out) and pitcher 2 (outing 2, 3 days out). Flags on outings 1, 2, 5 and 6."""
    y = [1, 1, 1, 0, 0, 0, 0, 0, 0, 0]
    return pd.DataFrame({"pitcher": [1, 1, 2, 3, 3, 4, 5, 6, 7, 8], "game_date": pd.to_datetime(["2026-05-01"] * 10),
                         "y": y, "y_days": [6, 2, 3] + [np.nan] * 7, "y_lead_announced": [8, 4, 3] + [np.nan] * 7,
                         "y_effective": pd.to_datetime(["2026-05-07", "2026-05-07", "2026-05-04"] + [None] * 7)})


def test_alert_table_by_hand():
    """4 alerts, 2 true (outings 1 and 2): precision 0.5; base rate 3/10 = 0.3; lift 0.5 / 0.3 = 1.667.
    Over 30 clubs and one season: 4/30 alerts and 2/30 false alarms per club-season. Both stints have an alert:
    2 of 2 caught. Median days to the effective date over true alerts: median(2, 3) = 2.5; to the announcement:
    median(4, 3) = 3.5."""
    d = _alerts_frame()
    flag = np.zeros(10, bool)
    flag[[1, 2, 5, 6]] = True
    r = w.alert_table(d, flag)
    assert (r["alerts"], r["true_alerts"]) == (4, 2)
    assert r["precision"] == pytest.approx(0.5) and r["base_rate"] == pytest.approx(0.3)
    assert r["lift"] == pytest.approx(0.5 / 0.3)
    assert r["alerts_per_club_season"] == pytest.approx(4 / 30) and r["false_alarms_per_club_season"] == pytest.approx(2 / 30)
    assert (r["stints"], r["stints_caught"]) == (2, 2)
    assert r["median_days_to_effective"] == pytest.approx(2.5) and r["median_days_to_announced"] == pytest.approx(3.5)


def test_pick_threshold_uses_the_false_alarm_ceiling():
    """FICTIONAL training season: 30 clubs, 1 season. Velocity drops 0.6 (x 300 outings, no IL) and 1.2 (x 60 outings,
    no IL), plus 30 outings at 2.5 mph with IL. Threshold 0.5: 360 false alarms / 30 = 12 per club, above 10.
    Threshold 1.0: 60 / 30 = 2, at or below 10, so 1.0 is chosen."""
    n = 390
    d = pd.DataFrame({"pitcher": np.arange(n), "game_date": pd.Timestamp("2026-05-01"),
                      "drop_velo_1": [0.6] * 300 + [1.2] * 60 + [2.5] * 30, "y": [0] * 360 + [1] * 30,
                      "y_days": [np.nan] * 360 + [3] * 30, "y_lead_announced": [np.nan] * 360 + [3] * 30,
                      "y_effective": [pd.NaT] * 360 + [pd.Timestamp("2026-05-04")] * 30})
    assert w.pick_threshold(d, seasons=1) == 1.0
