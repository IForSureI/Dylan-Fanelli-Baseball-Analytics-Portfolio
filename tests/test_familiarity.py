"""Pitch-type familiarity: exposure counts on a hand-built game (fictional), and the estimator."""
import numpy as np
import pandas as pd
import pytest

from baseball.edge import familiarity as f
from baseball.stats import absorb, clustered_wls


def _game() -> pd.DataFrame:
    """Fictional. Game 1: pitcher 1 (R) vs batters 10 and 11, then reliever 2 (R) vs batter 10, then a
    mid-PA pinch hitter (13 for 12). Game 2 (later date): pitcher 1 vs batter 10 again."""
    rows = [
        # game, date, ab, pitch_no, pitcher, batter, type
        (1, "2026-05-01", 1, 1, 1, 10, "FF"),
        (1, "2026-05-01", 1, 2, 1, 10, "CH"),
        (1, "2026-05-01", 1, 3, 1, 10, "FF"),
        (1, "2026-05-01", 2, 1, 1, 11, "SL"),
        (1, "2026-05-01", 3, 1, 1, 10, "CH"),
        (1, "2026-05-01", 3, 2, 1, 10, "FF"),
        (1, "2026-05-01", 4, 1, 2, 10, "CH"),
        (1, "2026-05-01", 5, 1, 2, 12, "FF"),
        (1, "2026-05-01", 5, 2, 2, 13, "SL"),   # pinch hitter mid-PA
        (2, "2026-05-09", 1, 1, 1, 10, "FF"),
    ]
    d = pd.DataFrame(rows, columns=["game_pk", "game_date", "at_bat_number", "pitch_number", "pitcher", "batter", "pitch_type"])
    d["game_year"] = 2026
    d["p_throws"] = "R"
    d["stand"] = "R"
    d["inning"] = 1
    return d


@pytest.fixture(scope="module")
def ex():
    return f.exposures(_game()).set_index(["game_pk", "at_bat_number", "pitch_number"])


def test_earlier_pa_and_this_pa_counts(ex):
    # PA 3, pitch 1 (CH): batter 10 saw FF, CH, FF in PA 1
    r = ex.loc[(1, 3, 1)]
    assert (r.prev_same, r.prev_other, r.pa_same, r.pa_other, r.prior_pa) == (1, 2, 0, 0, 1)
    # PA 3, pitch 2 (FF): two FF and one CH in PA 1, one CH earlier in this PA
    r = ex.loc[(1, 3, 2)]
    assert (r.prev_same, r.prev_other, r.pa_same, r.pa_other) == (2, 1, 0, 1)
    # PA 1, pitch 3 (FF): one FF and one CH earlier in this PA, nothing before
    r = ex.loc[(1, 1, 3)]
    assert (r.prev_same, r.prev_other, r.pa_same, r.pa_other, r.prior_pa) == (0, 0, 1, 1, 0)


def test_placebo_counts_later_pas_only(ex):
    # PA 1, pitch 1 (FF): later PAs vs pitcher 1 today = PA 3 (CH, FF)
    r = ex.loc[(1, 1, 1)]
    assert (r.next_same, r.next_other, r.has_later_pa) == (1, 1, 1)
    assert ex.loc[(1, 3, 2)].has_later_pa == 0


def test_other_pitcher_exposure(ex):
    # Reliever 2's CH to batter 10: he saw 2 CH (and 5 pitches) from pitcher 1, a same-handed pitcher
    r = ex.loc[(1, 4, 1)]
    assert (r.prev_same, r.prior_pa) == (0, 0)
    assert (r.xp_same, r.xp_total, r.xp_group_other_type) == (2, 5, 0)
    assert (r.xp_same_samehand, r.xp_same_otherhand) == (2, 0)


def test_pinch_hitter_starts_his_own_count(ex):
    r = ex.loc[(1, 5, 2)]
    assert (r.pa_same, r.pa_other, r.prev_same, r.prev_other) == (0, 0, 0, 0)


def test_earlier_games_this_season(ex):
    # Game 2: batter 10 saw 3 FF and 2 CH from pitcher 1 in game 1
    r = ex.loc[(2, 1, 1)]
    assert (r.game_same, r.game_other, r.prev_same) == (3, 2, 0)


def test_absorb_matches_dummy_regression():
    rng = np.random.default_rng(1)
    n = 400
    d = pd.DataFrame({"a": rng.integers(0, 12, n), "b": rng.integers(0, 7, n), "x": rng.normal(size=n)})
    d["y"] = 1.5 * d["x"] + 0.3 * d["a"] - 0.2 * d["b"] + rng.normal(size=n)
    r = absorb(d, ["y", "x"], ["a", "b"], iters=500, tol=1e-12)
    slope = (r["x"] @ r["y"]) / (r["x"] @ r["x"])
    X = np.column_stack([d["x"], pd.get_dummies(d["a"], dtype=float), pd.get_dummies(d["b"], drop_first=True, dtype=float)])
    full = np.linalg.lstsq(X, d["y"], rcond=None)[0][0]
    assert slope == pytest.approx(full, abs=1e-8)


def test_fast_clustered_se_matches_loop():
    rng = np.random.default_rng(2)
    n = 300
    X = np.column_stack([np.ones(n), rng.normal(size=n)])
    y = X @ [1.0, 0.5] + rng.normal(size=n)
    w, cl = rng.uniform(0.5, 2, n), rng.integers(0, 25, n)
    beta, se = clustered_wls(y, X, w, cl)
    # the slow textbook version
    Xw = X * w[:, None]
    bread = np.linalg.inv(X.T @ Xw)
    e = y - X @ (bread @ Xw.T @ y)
    meat = sum(np.outer(s, s) for s in ((Xw[cl == g] * e[cl == g][:, None]).sum(0) for g in np.unique(cl)))
    G = len(np.unique(cl))
    cov = (G / (G - 1)) * ((n - 1) / (n - 2)) * bread @ meat @ bread
    assert se == pytest.approx(np.sqrt(np.diag(cov)), rel=1e-10)


def test_fit_pairs_recovers_a_planted_contrast():
    """Fictional pitches: whiff falls 3 points per earlier same-type pitch and rises 0.5 per other pitch."""
    rng = np.random.default_rng(3)
    n = 40_000
    d = pd.DataFrame({
        "pitcher": rng.integers(0, 60, n), "batter": rng.integers(0, 200, n),
        "prev_same": rng.poisson(1.0, n), "prev_other": rng.poisson(2.0, n),
        "pa_same": rng.poisson(0.6, n), "pa_other": rng.poisson(1.2, n),
        "game_same": rng.poisson(0.5, n), "game_other": rng.poisson(1.0, n),
        "balls": rng.integers(0, 4, n), "strikes": rng.integers(0, 3, n), "prior_pa": rng.integers(0, 3, n),
        "pitch_count": rng.integers(0, 100, n), "release_speed": rng.normal(93, 2, n), "pfx_z": rng.normal(1.2, 0.2, n),
        "pfx_x": rng.normal(-0.6, 0.2, n), "release_spin_rate": rng.normal(2300, 100, n),
        "plate_x": rng.normal(0, 0.8, n), "plate_z": rng.normal(2.5, 0.8, n), "sz_top": 3.4, "sz_bot": 1.6,
        "zone": rng.integers(1, 15, n).astype(float),
    })
    d["p_throws"], d["stand"] = "R", np.where(rng.random(n) < 0.5, "R", "L")
    d.loc[d["zone"] == 10, "zone"] = 11
    d["pkey"], d["bkey"] = d["pitcher"].astype(str), d["batter"].astype(str)
    p_eff = rng.normal(0, 0.05, 60)[d["pitcher"]]
    prob = 0.30 + p_eff - 0.03 * d["prev_same"] + 0.005 * d["prev_other"]
    d["whiff"] = (rng.random(n) < prob.clip(0.01, 0.99)).astype(int)
    t = f.fit_pairs(d, "whiff").set_index("term")
    assert t.loc["prev: same - other", "coef"] == pytest.approx(-0.035, abs=0.006)
    assert t.loc["prev: other type", "coef"] == pytest.approx(0.005, abs=0.005)
    assert abs(t.loc["game: same - other", "coef"]) < 0.01


def test_break_even_hand_checked():
    # Skubal-like mix: 3.131*(0.454*0.256 - 0.195*0.38) + 2.349*(0.127*0.256 - 0.05*0.38)
    # = 3.131*0.042124 + 2.349*0.013512 = 0.131890 + 0.031740 = 0.163630
    assert f.break_even(0.454, 0.256, 0.195, 0.38, 3.131, 0.127, 0.05, 2.349) == pytest.approx(0.16363, abs=1e-5)
    # moving off a heavily used, fast-wearing pitch onto a light one is cheaper, not dearer
    assert f.break_even(0.454, 0.15, 0.195, 0.50, 3.131) < 0


def test_break_even_within_pa_window():
    # adds seen_pa x (pa_cost_b x use_b - pa_cost_a x use_a) = 1.918 x (0.059*0.26 - 0.097*0.38) = 1.918 x -0.02152 = -0.04128
    base = f.break_even(0.454, 0.26, 0.195, 0.38, 3.131, 0.127, 0.05, 2.349)
    full = f.break_even(0.454, 0.26, 0.195, 0.38, 3.131, 0.127, 0.05, 2.349, 0.059, 0.097, 1.918)
    assert full - base == pytest.approx(-0.04128, abs=1e-5)
