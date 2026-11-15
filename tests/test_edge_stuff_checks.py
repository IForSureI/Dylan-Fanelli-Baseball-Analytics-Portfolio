"""The sweeper diagnosis and the candidate-fix rule, on fictional pitchers."""
import numpy as np
import pandas as pd
import pytest

from baseball.edge import stuff
from baseball.edge import stuff_checks as sc


def _swings(n_pitchers=40, seed=3):
    """Fictional swings on two pitch types. Slider whiffs follow the speed gap to the fastball (physics).
    Sweeper whiffs follow how often the pitcher gets chases (usage), which no physical input holds."""
    rng = np.random.default_rng(seed)
    rows = []
    for pid in range(1, n_pitchers + 1):
        fb, gap, chase_rate = rng.normal(94, 2), rng.normal(9, 2.5), rng.uniform(0.2, 0.7)
        for pt in ("SL", "ST"):
            for _ in range(150):
                chase = rng.random() < chase_rate
                p = 0.10 + 0.03 * gap if pt == "SL" else 0.15 + (0.45 if chase else 0.0)
                rows.append({"pitcher": pid, "pitch_type": pt, "whiff": int(rng.random() < np.clip(p, 0.02, 0.95)),
                             "velo": fb - gap + rng.normal(0, 0.5), "d_velo": -gap + rng.normal(0, 0.5), "ivb_in": 2.0, "d_ivb": -14.0,
                             "hb_arm_in": -8.0, "d_hb": -15.0, "spin": 2400.0, "ext_ft": 6.3, "rel_z_ft": 5.8, "rel_x_arm_ft": 1.9,
                             "arm_angle": 40.0, "same_hand": int(rng.random() < 0.6), "zone": 12 if chase else 5, "strikes": int(rng.integers(0, 3))})
    return sc.add_inputs(pd.DataFrame(rows))


def test_add_inputs_recovers_the_fastball_and_flags_usage():
    s = sc.add_inputs(pd.DataFrame({"pitch_type": ["SL", "FF"], "velo": [86.0, 95.0], "d_velo": [-9.0, 0.0], "ivb_in": [2.0, 16.0], "d_ivb": [-14.0, 0.0],
                                    "hb_arm_in": [-6.0, 8.0], "d_hb": [-14.0, 0.0], "zone": [13, 5], "strikes": [2, 1]}))
    assert s["fb_velo"].tolist() == [95.0, 95.0] and s["fb_ivb"].tolist() == [16.0, 16.0] and s["fb_hb"].tolist() == [8.0, 8.0]
    assert s["chase"].tolist() == [1.0, 0.0] and s["two_strikes"].tolist() == [1.0, 0.0]
    assert s["type_code"].nunique() == 2


def test_pitch_rows_average_swings_and_apply_the_floor():
    s = _swings(4)
    s = pd.concat([s, s[(s["pitcher"] == 1) & (s["pitch_type"] == "SL")].head(30).assign(pitcher=99)])   # 30 swings: under the floor
    t = sc.pitch_rows(s, pd.Series(0.3, index=s.index))
    assert 99 not in set(t["pitcher"]) and len(t) == 8 and (t["swings"] == 150).all()
    one = s[(s["pitcher"] == 2) & (s["pitch_type"] == "ST")]
    row = t[(t["pitcher"] == 2) & (t["pitch_type"] == "ST")].iloc[0]
    assert row["whiff_pct"] == pytest.approx(100 * one["whiff"].mean()) and row["x_whiff_pct"] == pytest.approx(30.0)
    assert row["chase_share"] == pytest.approx((one["zone"] > 9).mean()) and row["fb_velo"] == pytest.approx((one["velo"] - one["d_velo"]).mean())


def test_correlates_tell_physics_from_usage():
    """The planted structure is recovered: slider whiffs follow the speed gap, sweeper whiffs follow chases."""
    s = _swings(60)
    rows = sc.pitch_rows(s, pd.Series(0.3, index=s.index)).assign(season=2025)
    st, sl = sc.correlates(rows, "ST", n_boot=100), sc.correlates(rows, "SL", n_boot=100)
    assert st["chase_share"]["r"] > 0.6 and st["chase_share"]["lo"] > 0
    assert abs(st["d_velo"]["r"]) < 0.3 and st["d_velo"]["lo"] < 0 < st["d_velo"]["hi"]
    assert sl["d_velo"]["r"] < -0.6 and sl["strongest_physical_input"] in ("d_velo", "velo")
    assert abs(sl["chase_share"]["r"]) < 0.3


def test_fit_by_type_and_hitter_side_use_the_right_swings():
    s = _swings(50)
    gap = -s["d_velo"]
    x = pd.Series(np.clip(0.10 + 0.03 * gap, 0.02, 0.95), index=s.index)      # the true slider rule, applied to every swing
    rows = sc.pitch_rows(s, x)
    f = sc.fit_by_type(rows, s, x)
    assert f["SL"]["r_expected_actual"] > 0.6 > f["ST"]["r_expected_actual"]    # right for sliders, blind on sweepers
    assert f["SL"]["swing_auc"] > 0.55 and f["SL"]["pitchers"] == 50
    sides = sc.by_hitter_side(s, x, "SL", min_swings=40)
    same = s[(s["pitch_type"] == "SL") & (s["same_hand"] == 1)]
    assert sides["same_side"]["mean_actual"] == pytest.approx(100 * same["whiff"].mean())
    assert sides["same_side"]["pitchers"] + sides["opposite_side"]["pitchers"] <= 100


def _tables(seed, noise):
    """Two seasons of pitch tables where expected whiff is the truth plus `noise`."""
    rng = np.random.default_rng(seed)
    n = 300
    truth = rng.normal(28, 5, n)
    base = pd.DataFrame({"pitcher": np.arange(n) // 2, "pitch_type": np.tile(["SL", "ST"], n // 2), "swings": rng.integers(60, 300, n)})
    prev = base.assign(whiff_pct=truth + rng.normal(0, 4, n), x_whiff_pct=truth + rng.normal(0, noise, n))
    curr = base.assign(whiff_pct=truth + rng.normal(0, 4, n), x_whiff_pct=0.0)
    return prev, curr


def test_blend_errors_match_validate_holdout():
    (p0, c0), (p1, c1) = _tables(1, 2.0), _tables(2, 2.0)
    e = sc.blend_errors(p0, c0, p1, c1)
    h = stuff.validate_holdout(p0, c0, p1, c1, n_boot=5)
    assert float(np.sqrt(np.average(e["sq_err"], weights=e["w"]))) == pytest.approx(h["rmse_blend"])
    assert len(e) == h["test_pitches"]


def test_rule_adopts_a_real_improvement_and_rejects_noise():
    (p0, c0), (p1, c1) = _tables(1, 6.0), _tables(2, 6.0)
    base = sc.blend_errors(p0, c0, p1, c1)
    # a candidate whose expected whiff is the truth on every pitch (the first draw in _tables)
    sharp0, sharp1 = p0.copy(), p1.copy()
    for sharp, seed in ((sharp0, 1), (sharp1, 2)):
        sharp["x_whiff_pct"] = np.random.default_rng(seed).normal(28, 5, len(sharp))
    comp = sc.compare_errors(base, sc.blend_errors(sharp0, c0, sharp1, c1), n_boot=300)
    assert comp["ST"]["diff"] < 0 and comp["ST"]["hi"] < 0
    assert comp["all"]["diff"] == pytest.approx(comp["all"]["rmse_candidate"] - comp["all"]["rmse_base"])
    assert sc.verdict(comp)["adopt"] is True
    same = sc.compare_errors(base, base, n_boot=50)
    assert same["ST"]["diff"] == 0 and sc.verdict(same) == {"helps_target": False, "clearly_worse_on": [], "adopt": False}
    # helps sweepers but is clearly worse on sliders: not adopted. Better on sweepers with an interval through zero: not adopted.
    v = sc.verdict({"all": {"lo": -0.1, "hi": 0.1}, "ST": {"lo": -0.5, "hi": -0.1}, "SL": {"lo": 0.05, "hi": 0.4}})
    assert v == {"helps_target": True, "clearly_worse_on": ["SL"], "adopt": False}
    assert sc.verdict({"ST": {"lo": -0.5, "hi": 0.02}, "SL": {"lo": -0.1, "hi": 0.1}})["adopt"] is False


def test_carry_over_reads_the_right_columns():
    prev, curr = _tables(4, 2.0)
    out = sc.carry_over(prev, curr)
    m = prev.merge(curr, on=["pitcher", "pitch_type"], suffixes=("_p", "_c"))
    st = m[m["pitch_type"] == "ST"]
    assert out["ST"]["pitches"] == 150
    assert out["ST"]["r_actual_actual"] == pytest.approx(np.corrcoef(st["whiff_pct_p"], st["whiff_pct_c"])[0, 1])
    assert out["ST"]["r_expected_next_actual"] == pytest.approx(np.corrcoef(st["x_whiff_pct_p"], st["whiff_pct_c"])[0, 1])
