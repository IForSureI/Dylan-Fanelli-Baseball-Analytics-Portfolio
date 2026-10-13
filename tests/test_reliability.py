"""The Reliability Atlas: hand-checked arithmetic, and recovery of known truths on FICTIONAL simulated players.

Every frame built here is fictional: simulated players with a true talent we set, so the split-half
machinery can be checked against the answer it should find.
"""
import math

import numpy as np
import pandas as pd
import pytest

from baseball.evaluation import reliability as R
from baseball.stats import fit_reliability_constant, shrink, spearman_brown


# ---------------------------------------------------------------- fictional data

def _fictional(players=300, games=40, per_game=10, tau=1.0, sigma_g=0.0, sigma_e=1.0, seasons=(2026,), rho=1.0,
               rho_half=1.0, binary=False, p_mean=0.25, seed=0) -> pd.DataFrame:
    """FICTIONAL players. Value = talent + game effect + event noise (or a Bernoulli draw at p = p_mean + talent).
    Talent correlates rho across seasons, and rho_half between the first and second half of a season's games."""
    rng = np.random.default_rng(seed)
    P, G, K = players, games, per_game
    base = rng.normal(0, tau, P)
    frames = []
    for si, season in enumerate(seasons):
        if si:
            base = rho * base + math.sqrt(1 - rho ** 2) * rng.normal(0, tau, P)
        later = rho_half * base + math.sqrt(1 - rho_half ** 2) * rng.normal(0, tau, P)
        talent = np.where(np.arange(G)[None, :] < G // 2, base[:, None], later[:, None])          # P x G
        value = talent[:, :, None] + rng.normal(0, sigma_g, (P, G))[:, :, None] * (sigma_g > 0) \
            + rng.normal(0, sigma_e, (P, G, K))
        if binary:
            value = (rng.random((P, G, K)) < np.clip(p_mean + talent, 0.01, 0.99)[:, :, None]).astype(float)
        pl, gm, ev = (a.ravel() for a in np.meshgrid(np.arange(P), np.arange(G), np.arange(K), indexing="ij"))
        dates = np.array([str(pd.Timestamp(f"{season}-04-01") + pd.Timedelta(days=int(g)))[:10] for g in range(G)])
        frames.append(pd.DataFrame({"batter": pl, "season": season, "game_pk": season * 100_000 + pl * 100 + gm,
                                    "game_date": dates[gm], "at_bat_number": ev // 4 + 1, "pitch_number": ev % 4 + 1,
                                    "pitch_type": "FF", "x": value.ravel()}))
    return pd.concat(frames, ignore_index=True)


X = R.Metric("x", "Fictional metric", "hitter", "mean", "events", lambda d: d["x"].to_numpy(float),
             lambda d: np.ones(len(d), bool))


def _summary(d, seasons, reps=12, unit="game", seed=3, boot=60):
    fam = R.build_family(d, "hitter", unit=unit)
    job = R._job(fam, [X], list(seasons), boot)
    R.run_splits([job], reps, seed=seed, log=None)
    return R.summarize(job)[1].iloc[0]


# ---------------------------------------------------------------- shared statistics (hand-checked)

def test_spearman_brown_hand_checked():
    # Two halves correlating 0.5 -> whole sample: 2(0.5) / (1 + 0.5) = 0.6667
    assert round(spearman_brown(0.5, 2), 4) == 0.6667
    # Exact under r(n) = n/(n+M): n = 30, M = 60 -> r = 1/3; tripled: 3(1/3)/(1 + 2/3) = 0.6 = 90/(90+60)
    assert spearman_brown(30 / 90, 3) == pytest.approx(90 / 150)


def test_fit_reliability_constant_recovers_an_exact_curve():
    n = np.array([5, 10, 20, 40, 80, 160, 320])
    assert fit_reliability_constant(n, n / (n + 50.0)) == pytest.approx(50.0, rel=1e-4)
    # weights don't move an exact fit
    assert fit_reliability_constant(n, n / (n + 50.0), w=np.arange(1, 8)) == pytest.approx(50.0, rel=1e-4)


def test_shrink_hand_checked():
    # (100 x .300 + 100 x .250) / 200 = .275; no sample -> the prior
    assert shrink(0.300, 100, 0.250, 100) == pytest.approx(0.275)
    assert shrink(0.300, 0, 0.250, 100) == pytest.approx(0.250)
    np.testing.assert_allclose(shrink([0.3, 0.2], [300, 100], 0.25, 100), [0.2875, 0.225])  # w = .75 and .5


def test_regress_hand_checked():
    # w = 100/(100+100) = 0.5 -> .275; sd = .02 sqrt(1 - .5) = .0141421; 95%: +/- 1.959964 x .0141421 = .0277181
    r = R.regress("x", 0.300, 100, 0.250, M=100, tau=0.02).iloc[0]
    assert r["estimate"] == pytest.approx(0.275)
    assert r["sd"] == pytest.approx(0.0141421, abs=1e-6)
    assert (r["lo"], r["hi"]) == pytest.approx((0.247282, 0.302718), abs=1e-5)
    # next season with rho = .8: .25 + .8 x .5 x .05 = .27; sd = .02 sqrt(1 - .64 x .5) = .0164924
    r = R.regress("x", 0.300, 100, 0.250, horizon="next_season", M=100, tau=0.02, rho=0.8).iloc[0]
    assert r["estimate"] == pytest.approx(0.27) and r["weight"] == pytest.approx(0.4)
    assert r["sd"] == pytest.approx(0.0164924, abs=1e-6)
    # rest of season: same estimate, sd = sqrt(.02^2 x .5 + .01^2) = sqrt(.0003) = .0173205
    r = R.regress("x", 0.300, 100, 0.250, horizon="rest_of_season", M=100, tau=0.02, drift_sd=0.01).iloc[0]
    assert r["estimate"] == pytest.approx(0.275) and r["sd"] == pytest.approx(0.0173205, abs=1e-6)
    with pytest.raises(ValueError):
        R.regress("x", 0.3, 100, 0.25, horizon="career", M=100, tau=0.02)


def test_split_half_r_hand_checked_and_matches_the_pooled_sums():
    # a = 1,2,3; b = 1,3,2; common mean 2. cov = ((-1)(-1) + 0(1) + 1(0))/3 = 1/3;
    # var = ((1+1)/2 + (0+1)/2 + (1+0)/2)/3 = 2/3 -> r = 0.5
    a, b = np.array([1.0, 2, 3]), np.array([1.0, 3, 2])
    assert R.split_half_r(a, b) == pytest.approx(0.5)
    sums = R.within_sums(np.stack([a, b], -1)[None], np.zeros(3, np.int64), 1, np.ones((1, 3)))
    n, c, v = R.centered(sums)
    assert (c / v)[0, 0, 0] == pytest.approx(0.5) and c[0, 0, 0] / n[0, 0, 0] == pytest.approx(1 / 3)
    # a bootstrap draw that takes the first player twice and drops the third: a = 1,1,2; b = 1,1,3
    # mean 1.5; cov = (.25 + .25 + .5 x 1.5)/3 = 1.25/3; var = (.25 + .25 + (.25 + 2.25)/2)/3 = 1.75/3 -> r = 5/7
    n, c, v = R.centered(R.within_sums(np.stack([a, b], -1)[None], np.zeros(3, np.int64), 1, np.array([[2.0, 1, 0]])))
    assert (c / v)[0, 0, 0] == pytest.approx(5 / 7)


# ---------------------------------------------------------------- the split engine

def test_half_means_takes_exactly_n_with_a_partial_last_game():
    # One fictional hitter, four games of two events: g1 = 1,1  g2 = 0,0  g3 = 1,0  g4 = 0,1.
    # Half A = games 1 and 3, half B = games 2 and 4 (in that order).
    a = R.Arrays(c=np.array([2, 2, 2, 2]), s=np.array([2.0, 0, 1, 1]), off=np.array([0, 2, 4, 6]),
                 cs=np.r_[0.0, np.cumsum([1, 1, 0, 0, 1, 0, 0, 1])])
    sp = R.Split(order=np.array([0, 2, 1, 3]), seg=np.array([0, 0, 1, 1]), first=np.array([0, 2]), length=np.array([2, 2]))
    m = R.half_means(a, sp, 1, [3, 4, 5])
    # n = 3: A = 1+1 + first of g3 (1) = 3/3 = 1.0; B = 0+0 + first of g4 (0) = 0.0
    assert m[0, 0].tolist() == [1.0, 0.0]
    # n = 4: A = (1+1+1+0)/4 = .75; B = (0+0+0+1)/4 = .25. n = 5: not enough events.
    assert m[1, 0].tolist() == [0.75, 0.25]
    assert np.isnan(m[2, 0]).all()


def test_random_halves_never_share_a_game_and_match_a_brute_force_count():
    d = _fictional(players=60, games=12, per_game=3, seed=1)
    fam = R.build_family(d, "hitter")
    a = R.metric_arrays(fam, X)
    sp = R.random_split(fam, np.random.default_rng(5))
    got = R.half_means(a, sp, fam.n_entity, [7])
    rows = fam.events.assign(row=fam.event_row)
    for e in range(fam.n_entity):
        halves = []
        for h in (0, 1):
            seq = sp.order[sp.seg == 2 * e + h]                    # rows of this half, in shuffled order
            halves.append(seq)
            vals = np.concatenate([rows.loc[rows["row"] == r, "x"].to_numpy() for r in seq])
            want = vals[:7].mean() if len(vals) >= 7 else np.nan
            assert got[0, e, h] == pytest.approx(want, nan_ok=True)
        assert not set(fam.row_og[halves[0]]) & set(fam.row_og[halves[1]])   # no game in both halves
        assert abs(len(halves[0]) - len(halves[1])) <= 1                       # games dealt alternately


def test_split_half_recovers_a_known_reliability_on_rates():
    # FICTIONAL rates: p = .25 + talent (sd .05). Noise per event p(1-p); M = E[p(1-p)] / var(p).
    d = _fictional(players=400, games=40, per_game=8, tau=0.05, binary=True, seed=2)
    rng = np.random.default_rng(2)
    p = np.clip(0.25 + rng.normal(0, 0.05, 400), 0.01, 0.99)   # the same talent draws as the generator
    m_true = np.mean(p * (1 - p)) / np.var(p)
    s = _summary(d, [2026], reps=12)
    assert s["M"] == pytest.approx(m_true, rel=0.15)
    assert s["tau"] == pytest.approx(np.std(p), rel=0.1)
    assert s["sigma2"] == pytest.approx(np.mean(p * (1 - p)), rel=0.05)    # noise per event: p(1 - p)
    assert s["sigma2"] == pytest.approx(s["M"] * s["tau"] ** 2)             # consistent by construction


def test_a_pitch_level_split_overstates_reliability_when_days_differ():
    # FICTIONAL: talent sd 1, a day effect sd .5 shared by the game's 10 events, event noise sd 1.
    # Game split, halves spanning many games: noise per event (1 + 10 x .25) -> M = 3.5.
    d = _fictional(players=300, games=40, per_game=10, tau=1.0, sigma_g=0.5, sigma_e=1.0, seed=4)
    game = _summary(d, [2026], reps=10)
    event = _summary(d, [2026], reps=10, unit="event")
    assert game["M"] == pytest.approx(3.5, rel=0.2)
    assert event["M"] < 0.6 * game["M"]                        # shared days make events look more reliable


def test_year_to_year_persistence_and_in_season_persistence_are_recovered():
    # FICTIONAL: talent correlates .6 between seasons and is constant within a season
    d = _fictional(players=400, games=30, per_game=6, tau=1.0, sigma_e=2.0, seasons=(2025, 2026), rho=0.6, seed=6)
    s = _summary(d, [2025, 2026], reps=10)
    assert s["rho"] == pytest.approx(0.6, abs=0.1)
    assert s["rho_lo"] < s["rho"] < s["rho_hi"]

    assert s["r_y2y"] < s["r_within_match"]                    # same players, same n: the gap is persistence


def _drift(d, seasons):
    fam = R.build_family(d, "hitter")
    job = R._job(fam, [X], list(seasons), boot=0)
    return R.drift_table(job, list(seasons), reps=20).iloc[0]


def test_in_season_drift_is_recovered():
    # FICTIONAL: first-half and second-half talent (sd 1 each) correlate .5, so the true change from one
    # half to the other has variance 1 + 1 - 2(.5) = 1: drift sd 1.0
    d = _fictional(players=400, games=40, per_game=6, tau=1.0, sigma_e=2.0, rho_half=0.5, seed=8)
    t = _drift(d, [2026])
    assert t["drift_sd"] == pytest.approx(1.0, abs=0.12)


def test_day_to_day_swings_are_not_mistaken_for_drift():
    # FICTIONAL: no drift at all, but big day effects (sd 1, like a pitcher's velocity from start to start)
    # and only 10 games. Each half's noise is measured by splitting its games, so the day effects are noise.
    d = _fictional(players=400, games=10, per_game=8, tau=1.0, sigma_g=1.0, sigma_e=1.0, seed=12)
    t = _drift(d, [2026])
    assert abs(t["drift_var"]) < 3 * t["drift_var_se"] and t["drift_sd"] < 0.25
    # and a real drift with the same day effects is still found (true change variance 2(1 - .5) = 1)
    d = _fictional(players=400, games=10, per_game=8, tau=1.0, sigma_g=1.0, sigma_e=1.0, rho_half=0.5, seed=13)
    assert _drift(d, [2026])["drift_sd"] == pytest.approx(1.0, abs=0.15)


# ---------------------------------------------------------------- metric definitions

def test_spray_angle_and_pull_hand_checked():
    # Straight away center: (125.42, 98.27) -> 0 degrees. (25.42, 98.27): atan2(-100, 100) = -45 (left-field line)
    ang = R.spray_angle([125.42, 25.42, 225.42], [98.27, 98.27, 98.27])
    np.testing.assert_allclose(ang, [0, -45, 45], atol=1e-9)
    # A righty pulls to left field; a lefty to right field; 0 degrees is nobody's pull
    np.testing.assert_array_equal(R.pulled(ang, ["R", "R", "L"]), [0.0, 1.0, 1.0])
    np.testing.assert_array_equal(R.pulled([-45, np.nan], ["L", "R"])[:1], [0.0])
    assert np.isnan(R.pulled([np.nan], ["R"])[0])


def test_competitive_swings_fastest_90_percent_plus_hard_contact_no_bunts():
    # FICTIONAL batter: ten swings at 50, 55, ..., 95 mph and one bunt. 10th percentile (linear) = 50 + .9 x 5 = 54.5,
    # so the 50 mph swing is out unless it was hit 90+ (it wasn't); the bunt never counts.
    d = pd.DataFrame({"batter": 1, "season": 2026, "bat_speed": [50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 20.0],
                      "launch_speed": np.nan, "swing": True, "description": ["foul"] * 10 + ["foul_bunt"]})
    comp = R.competitive_swings(d)
    assert comp.sum() == 9 and not comp[0] and not comp[-1]
    d.loc[0, ["bat_speed", "launch_speed"]] = [61, 95.0]       # a 61 mph swing hit 95: competitive anyway
    assert R.competitive_swings(d)[0]


def test_prepare_flags_hand_counted():
    # FICTIONAL: one pitcher, one batter, six pitches (the pitch-clock ball isn't a pitch).
    p = pd.DataFrame({
        "game_pk": 1, "game_date": "2026-05-01", "game_year": 2026, "at_bat_number": [1, 1, 1, 1, 1, 2],
        "pitch_number": [1, 2, 3, 4, 5, 1], "pitcher": 9, "batter": 7, "p_throws": "R", "stand": "R", "pitch_type": "FF",
        "description": ["called_strike", "swinging_strike", "foul", "ball", "hit_into_play", "automatic_ball"],
        "type": ["S", "S", "S", "B", "X", "B"], "zone": [5, 14, 2, 12, 8, np.nan],
        "bb_type": [None, None, None, None, "line_drive", None], "estimated_woba_using_speedangle": [np.nan] * 4 + [0.9, np.nan],
        "launch_speed": [np.nan] * 4 + [101.0, np.nan], "launch_angle": [np.nan] * 4 + [22.0, np.nan],
        "launch_speed_angle": [np.nan] * 4 + [6, np.nan], "hc_x": [np.nan] * 4 + [60.0, np.nan], "hc_y": [np.nan] * 4 + [100.0, np.nan],
        "delta_run_exp": [-0.05, -0.06, -0.04, 0.03, 0.4, 0.0], "woba_value": [np.nan] * 4 + [1.25, np.nan],
        "woba_denom": [np.nan] * 4 + [1.0, np.nan], "release_speed": 95.0, "release_spin_rate": 2300.0, "pfx_x": -0.5,
        "pfx_z": 1.25, "arm_angle": 40.0, "release_extension": 6.5, "bat_speed": [np.nan, 70, 72, np.nan, 75, np.nan],
        "swing_length": [np.nan, 7, 7.2, np.nan, 7.5, np.nan], "attack_angle": [np.nan, 5, 8, np.nan, 12, np.nan],
        "attack_direction": [np.nan, -3, 0, np.nan, -10, np.nan], "swing_path_tilt": [np.nan, 30, 31, np.nan, 33, np.nan],
    })
    d = R.prepare(p)
    assert len(d) == 5

    def rate(role, key):
        m = R.METRICS[(role, key)]
        den = np.asarray(m.den(d), bool)
        return np.asarray(m.value(d), float)[den].mean()

    assert rate("pitcher", "whiff") == pytest.approx(1 / 3)      # 1 whiff / 3 swings
    assert rate("pitcher", "csw") == pytest.approx(2 / 5)        # called + whiff / 5 pitches
    assert rate("pitcher", "chase") == pytest.approx(1 / 2)      # 1 swing / 2 pitches outside the zone
    assert rate("pitcher", "zone") == pytest.approx(3 / 5)
    assert rate("pitcher", "hard_hit") == 1 and rate("pitcher", "barrel") == 1
    assert rate("pitcher", "rv100") == pytest.approx(-100 * (-0.05 - 0.06 - 0.04 + 0.03 + 0.4) / 5)  # -5.6 runs/100
    assert rate("pitcher", "ivb") == pytest.approx(15.0) and rate("pitcher", "hb") == pytest.approx(6.0)  # RHP: -pfx_x
    assert rate("hitter", "zone_contact") == pytest.approx(2 / 2)  # foul + in play, both in the zone
    assert rate("hitter", "pull") == 1                           # 60, 100 is toward left field: a righty's pull
    assert rate("hitter", "woba") == pytest.approx(1.25)
    # Competitive swings: the fastest 90% of 70, 72, 75 mph (10th percentile 70.4) drops the 70 mph whiff,
    # so attack direction (pull +) averages the 72 and 75 mph swings: (0 + 10) / 2 = 5
    assert rate("hitter", "attack_direction") == pytest.approx(5.0)
    assert rate("hitter", "bat_speed") == pytest.approx(73.5)


# ---------------------------------------------------------------- validation and the shipped constants

def test_score_forecast_rewards_shrinkage_and_its_intervals_cover():
    # FICTIONAL: talent sd .05 around .25, first samples of 5-400 events, second samples of 300
    rng = np.random.default_rng(10)
    k = 3000
    p = np.clip(0.25 + rng.normal(0, 0.05, k), 0.01, 0.99)
    n1 = rng.integers(5, 400, k)
    n2 = np.full(k, 300)
    o1, o2 = rng.binomial(n1, p) / n1, rng.binomial(n2, p) / n2
    M = np.mean(p * (1 - p)) / 0.05 ** 2                         # 75
    tab, info = R.score_forecast(o1, n1, o2, n2, 0.25, M, 0.05)
    small = tab[tab["bucket"].eq("< M/4")].iloc[0]
    assert small["cut_pct"] > 20 and small["cut_lo"] > 0           # tiny samples: big gain from regressing
    assert tab.loc[tab["bucket"].eq("all"), "rmse_shrunk"].iloc[0] < tab.loc[tab["bucket"].eq("all"), "rmse_raw"].iloc[0]
    assert 0.67 < info["best_over_M"] < 1.5                        # the right M is (about) the best one
    assert info["cover95"] == pytest.approx(0.95, abs=0.03) and info["cover80"] == pytest.approx(0.80, abs=0.04)


def test_shipped_constants_cover_the_atlas_and_regress_uses_them():
    params = R.load_params()
    for mid in ("hitter/bat_speed", "hitter/woba", "pitcher/whiff", "pitcher/FF/velo", "pitcher/CH/whiff"):
        assert mid in params.index
        assert params.loc[mid, "M"] > 0 and params.loc[mid, "tau"] > 0
    row = params.loc["hitter/whiff"]
    out = R.regress("hitter/whiff", 0.40, 50, 0.25)
    w = 50 / (50 + row["M"])
    assert out["estimate"].iloc[0] == pytest.approx(0.25 + w * 0.15)
    assert 0 <= out["lo"].iloc[0] < out["estimate"].iloc[0] < out["hi"].iloc[0] <= 1
