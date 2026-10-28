"""The PyMC whiff report (reports/bayes/whiff_hierarchical.py): its copies of the repo's definitions and of the
Atlas's closed form agree with the library, and its counting and scoring helpers are right on FICTIONAL rows.
None of these tests import PyMC."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from baseball.evaluation.reliability import regress

_spec = importlib.util.spec_from_file_location(
    "whiff_hierarchical", Path(__file__).resolve().parents[1] / "reports" / "bayes" / "whiff_hierarchical.py")
W = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(W)


def test_definitions_and_constants_match_the_repo():
    W.test_definitions_match_repo()


def test_closed_form_copy_equals_regress():
    obs, n = np.array([0.40, 0.10, 0.25, 0.0]), np.array([50.0, 600.0, 5.0, 1.0])
    est, lo, hi, w = W.atlas_season(obs, n, 0.251, 0.95)
    r = regress("hitter/whiff", obs, n, 0.251, horizon="season")
    assert np.allclose(est, r["estimate"]) and np.allclose(lo, r["lo"]) and np.allclose(hi, r["hi"])
    # the talk-track example: 40% on 50 swings, league 25.1% -> 32.2% (23.4-40.9)
    assert round(100 * est[0], 1) == 32.2 and round(100 * lo[0], 1) == 23.4 and round(100 * hi[0], 1) == 40.9


def test_next_season_predictive_adds_the_new_sample_noise():
    obs, n, n2 = np.array([0.40]), np.array([50.0]), np.array([200.0])
    est, lo, hi = W.atlas_next(obs, n, 0.251, n2, 0.95)
    r = regress("hitter/whiff", obs, n, 0.251, horizon="next_season")
    sd = np.sqrt(r["sd"].to_numpy() ** 2 + W.ATLAS["M"] * W.ATLAS["tau"] ** 2 / n2)
    assert est == pytest.approx(r["estimate"].to_numpy())
    assert hi - lo == pytest.approx(2 * 1.959964 * sd, rel=1e-6)


def test_counts_from_fictional_pitches():
    rows = [  # FICTIONAL: one hitter, five pitches, one pitch-clock ball and one duplicated row
        (1, 2025, "R", 1, 1, 9, "Fictional, Hitter", "FF", "swinging_strike"),
        (1, 2025, "R", 1, 2, 9, "Fictional, Hitter", "FF", "foul"),
        (1, 2025, "R", 1, 2, 9, "Fictional, Hitter", "FF", "foul"),
        (1, 2025, "R", 1, 3, 9, "Fictional, Hitter", "SL", "foul_tip"),
        (1, 2025, "R", 1, 4, 9, "Fictional, Hitter", "SL", "ball"),
        (1, 2025, "R", 1, 5, 9, "Fictional, Hitter", None, "automatic_ball"),
        (2, 2025, "S", 1, 1, 9, "Fictional, Hitter", "CH", "swinging_strike"),   # spring: dropped
    ]
    p = pd.DataFrame(rows, columns=["game_pk", "game_year", "game_type", "at_bat_number", "pitch_number", "batter",
                                    "player_name", "pitch_type", "description"])
    c = W.counts_from_pitches(p).set_index("pitch_group")
    assert c.loc["fastball", "swings"] == 2 and c.loc["fastball", "whiffs"] == 1
    assert c.loc["breaking", "swings"] == 1 and c.loc["breaking", "whiffs"] == 1
    assert "offspeed" not in c.index


def test_randomized_pit_is_uniform_when_the_forecast_is_right():
    rng = np.random.default_rng(0)
    n = rng.integers(5, 400, 4000)
    p_true = rng.uniform(0.1, 0.4, 4000)
    y = rng.binomial(n, p_true)
    pit = W.pit_binomial_mixture(y, n, np.repeat(p_true[None, :], 3, 0), rng)
    assert abs(np.mean(np.abs(pit - 0.5) < 0.40) - 0.80) < 0.02
    assert abs(np.mean(np.abs(pit - 0.5) < 0.475) - 0.95) < 0.015
