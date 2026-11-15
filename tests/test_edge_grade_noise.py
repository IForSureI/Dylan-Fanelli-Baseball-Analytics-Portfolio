"""Grade ranges across refits: the logic, on small made-up tables."""
import numpy as np
import pandas as pd
import pytest

from baseball.edge import grade_noise as gn
from baseball.evaluation.reliever import grade_from_percentile, percentile


def _table(x_of_target, n=101):
    """One pitch type, 100 league pitches with expected whiff 0..99 plus pitcher 1 at `x_of_target`."""
    t = pd.DataFrame({"pitcher": np.arange(100, 100 + n - 1), "pitch_type": "SL", "swings": 100, "whiff_pct": 30.0,
                      "x_whiff_pct": np.arange(n - 1, dtype=float)})
    me = pd.DataFrame({"pitcher": [1], "pitch_type": ["SL"], "swings": [73], "whiff_pct": [30.0], "x_whiff_pct": [float(x_of_target)]})
    return pd.concat([t, me], ignore_index=True)


def test_reorder_keeps_the_rows_and_order_zero_is_untouched():
    s = pd.DataFrame({"a": range(50)})
    assert gn.reorder(s, 0) is s
    r = gn.reorder(s, 3)
    assert sorted(r["a"]) == list(range(50)) and r["a"].tolist() != list(range(50))
    assert r["a"].tolist() == gn.reorder(s, 3)["a"].tolist() and r["a"].tolist() != gn.reorder(s, 4)["a"].tolist()


def test_grade_rows_use_the_memo_grading():
    t = _table(97.5)
    proj = t.assign(proj_whiff_pct=t["x_whiff_pct"] / 2)
    g = gn.grade_rows(t, proj, [1]).iloc[0]
    pct = percentile(t["x_whiff_pct"], 97.5)
    assert g["pct_stuff"] == pytest.approx(pct) and g["grade_stuff"] == grade_from_percentile(pct) == 70
    assert g["gap"] == pytest.approx(30.0 - 97.5) and g["grade_next"] == g["grade_stuff"]   # same rank in the projection
    assert len(gn.grade_rows(t, proj, [1])) == 1


def test_grades_compare_within_the_pitch_type_group_only():
    t = pd.concat([_table(50.0), _table(50.0).assign(pitch_type="FF", x_whiff_pct=lambda d: d["x_whiff_pct"] + 1000)], ignore_index=True)
    g = gn.grade_rows(t, t.assign(proj_whiff_pct=t["x_whiff_pct"]), [1])
    sl = g[g["pitch_type"] == "SL"].iloc[0]
    assert sl["grade_stuff"] == 50   # the four-seamers' far larger numbers are not in its reference


def test_summarize_gives_the_range_and_every_grade_seen():
    fits = []
    for x in (84.5, 97.5, 99.5, 84.5):
        t = _table(x)
        fits.append(gn.grade_rows(t, t.assign(proj_whiff_pct=t["x_whiff_pct"]), [1]))
    s = gn.summarize(fits)["1_SL"]
    assert s["fits"] == 4 and (s["x_whiff_pct"]["lo"], s["x_whiff_pct"]["hi"]) == (84.5, 99.5)
    assert (s["grade_stuff"]["lo"], s["grade_stuff"]["hi"]) == (60, 75) and s["grade_stuff"]["counts"] == {"60": 2, "70": 1, "75": 1}
    assert s["gap"]["lo"] == pytest.approx(30.0 - 99.5) and s["gap"]["hi"] == pytest.approx(30.0 - 84.5)


def test_projection_follows_the_engine_rule():
    """Two-year weights are used only where they score better leave-one-out, as in edge/run.py."""
    from baseball.edge import stuff

    rng = np.random.default_rng(0)
    n = 300
    truth = rng.normal(28, 5, n)
    base = pd.DataFrame({"pitcher": np.arange(n), "pitch_type": "SL", "swings": rng.integers(60, 300, n)})
    tables = {y: base.assign(whiff_pct=truth + rng.normal(0, 4, n), x_whiff_pct=truth + rng.normal(0, 2, n)) for y in (2024, 2025, 2026)}
    p = gn.projection(tables, 2026)
    two = stuff.validate_two_year(tables[2024], tables[2025], tables[2026])
    better = two["loo_rmse"]["two_seasons_plus_expected"] < two["loo_rmse"]["last_plus_expected"]
    assert set(p["proj_basis"]) == ({"two seasons"} if better else {"one season"}) and p["proj_whiff_pct"].notna().all()
    one = gn.projection({2025: tables[2025], 2026: tables[2026]}, 2026)
    assert set(one["proj_basis"]) == {"one season"}


def test_pitcher_level_is_swing_weighted():
    t = pd.DataFrame({"pitcher": [1, 1, 2], "swings": [300, 100, 50], "x_whiff_pct": [20.0, 40.0, 33.0]})
    out = gn.pitcher_level([t, t.assign(x_whiff_pct=t["x_whiff_pct"] + 2)], [1])
    assert out == {"1": {"lo": pytest.approx(25.0), "hi": pytest.approx(27.0)}}
