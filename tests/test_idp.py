"""IDP data model and progress engine. Every plan and pitch here is FICTIONAL except the check that the
real worked example's YAML is a valid plan (no data is read for that)."""
import copy
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from baseball.development import idp

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.fixture(scope="module")
def fictional_plan_dict():
    return yaml.safe_load((EXAMPLES / "idp-fictional.yaml").read_text())


def test_example_plans_are_valid(fictional_plan_dict):
    assert idp.validate_plan(fictional_plan_dict) == []
    real = yaml.safe_load((EXAMPLES / "idp-gilbert-2026.yaml").read_text())
    assert idp.validate_plan(real) == []
    assert "HYPOTHETICAL" in real["label"] and "not the club" in real["label"]
    plan = idp.plan_from_dict(fictional_plan_dict)
    assert len(plan.priorities) == 3 and plan.priorities[0].guard.limit == 93.0


def test_validation_names_every_problem(fictional_plan_dict):
    d = copy.deepcopy(fictional_plan_dict)
    d["label"] = "an example"                                  # fictional data must say so
    p = d["priorities"][0]
    p["metric"] = {"stat": "ivb_inches", "pitch_type": "FF"}   # unknown stat
    p["target"] = p["baseline"]["value"]                       # a goal that moves nothing (checked after the stat)
    p["checkpoints"] = ["2026-01-01"]                          # outside the period
    del d["priorities"][1]["owner"]
    d["priorities"][2]["metric"] = {"stat": "speed_gap", "pitch_type": "CH"}   # no reference fastball
    err = "\n".join(idp.validate_plan(d))
    for s in ("FICTIONAL", "unknown stat", "outside the plan period", "missing 'owner'", "ref_pitch_type"):
        assert s in err
    one = copy.deepcopy(fictional_plan_dict)
    one["priorities"] = one["priorities"][:1]
    assert any("2-4" in e for e in idp.validate_plan(one))
    with pytest.raises(ValueError):
        idp.plan_from_dict(one)


def test_jackknife_by_game_by_hand():
    # Three games: values (1, 3), (5), (6, 6, 6): sums 4, 5, 18 on 2, 1, 3 pitches; mean 27 / 6 = 4.5
    c = pd.DataFrame({"s": [4.0, 5.0, 18.0], "n": [2, 1, 3]})
    value, se = idp.jackknife(c, lambda T: T["s"] / T["n"])
    # Leave one game out: 23/4 = 5.75, 22/5 = 4.4, 9/3 = 3.0; mean 4.3833; squared deviations
    # 1.86778 + 0.00028 + 1.91361 = 3.78167; x (G-1)/G = 2/3 -> 2.52111; sqrt -> 1.58780
    assert value == pytest.approx(4.5)
    assert se == pytest.approx(1.58780, abs=1e-5)


def _pitches(rows):
    base = {"p_throws": "R", "stand": "R", "zone": 5, "release_speed": 95.0, "pfx_x": -0.6, "pfx_z": 1.3,
            "release_spin_rate": 2300.0, "release_extension": 6.5, "release_pos_x": -2.0, "release_pos_z": 6.0,
            "arm_angle": 45.0, "delta_run_exp": 0.0, "description": "ball", "game_date": "2027-04-10"}
    return pd.DataFrame([{**base, **r} for r in rows])


def test_estimates_rates_and_relative_metrics():
    p = _pitches([
        {"game_pk": 1, "pitch_type": "FF", "release_speed": 95.0, "description": "swinging_strike"},
        {"game_pk": 1, "pitch_type": "FF", "release_speed": 96.0, "description": "foul"},
        {"game_pk": 1, "pitch_type": "CH", "release_speed": 86.0, "description": "ball", "zone": 13},
        {"game_pk": 2, "pitch_type": "CH", "release_speed": 86.0, "description": "swinging_strike", "zone": 14},
        {"game_pk": 2, "pitch_type": "FF", "release_speed": 95.5, "description": "hit_into_play"},
    ])
    M = idp.Metric
    gap = idp.estimate(p, M("speed_gap", "CH", "FF"))
    assert gap["value"] == pytest.approx(95.5 - 86.0) and gap["n"] == 2          # FF mean 95.5, CH mean 86
    wh = idp.estimate(p, M("whiff_pct", "FF"))
    assert wh["value"] == pytest.approx(100 / 3) and wh["n"] == 3                 # 1 whiff on 3 swings
    ch = idp.estimate(p, M("chase_pct", "CH"))
    assert ch["value"] == pytest.approx(50.0) and ch["n"] == 2                    # 1 swing on 2 out-of-zone pitches
    us = idp.estimate(p, M("usage_pct", "CH"))
    assert us["value"] == pytest.approx(40.0) and us["n"] == 5                    # 2 of 5 pitches


@pytest.mark.parametrize("est,se,n,expected", [
    (11.2, 0.2, 500, "on_track"),    # z = 1.2/0.2 = 6; on-pace value 10 + 0.5*2 = 11.0, already past it
    (10.6, 0.2, 500, "behind"),      # z = 3; 10.6 + 1.96*0.2 = 10.99 < 11.0, clearly short of pace
    (10.85, 0.2, 500, "on_track"),   # z = 4.25; 10.85 + 0.39 = 11.24 reaches the pace value: not clearly behind
    (10.2, 0.2, 500, "flat"),        # z = 1: no move distinguishable from the baseline
    (9.5, 0.2, 500, "wrong_way"),    # z = -2.5
    # past the target but z = 1.25, and the move expected by now (0.5 x 2 = 1.0) is under 1.96 x 2.0 = 3.92: underpowered
    (12.5, 2.0, 500, "inconclusive"),
    (11.5, 0.2, 50, "insufficient"), # under the floor of 100
])
def test_verdict_rules(est, se, n, expected):
    v = idp.verdict(baseline=10.0, target=12.0, est=est, se=se, n=n, floor=100, expected_fraction=0.5)
    assert v["verdict"] == expected


def test_verdict_when_lower_is_better_and_baseline_uncertainty_counts():
    v = idp.verdict(baseline=10.0, target=8.0, est=7.5, se=0.2, n=500, floor=100, expected_fraction=1.0)
    assert v["verdict"] == "on_track" and v["reached"]
    # est 9.5: z = -0.5 / 0.2 = -2.5 toward the target alone, but with a baseline SE of 0.3 it is
    # -0.5 / sqrt(0.04 + 0.09) = -1.39: flat
    v = idp.verdict(baseline=10.0, target=8.0, est=9.5, se=0.2, n=500, floor=100, expected_fraction=0.5, baseline_se=0.3)
    assert v["verdict"] == "flat" and v["z"] == pytest.approx(-0.5 / np.sqrt(0.13))


def test_power_check_by_hand():
    def plan(stat, value, n, floor, target, se=None):
        b = {"value": value, "n": n, "period": "2026", "source": "fictional"}
        if se is not None:
            b["se"] = se
        return {"priorities": [{"metric": {"stat": stat, "pitch_type": "SL"}, "baseline": b, "floor": floor, "target": target}]}
    # Whiff% 30 on 400 swings, floor 400, target 33: SE = 100 * sqrt(0.3 * 0.7 / 400) = 2.291 at both ends;
    # MDC = 1.96 * sqrt(2 * 2.291^2) = 6.35 > 3; (3 / 1.96)^2 = 2.34 < 2.291^2 = 5.25, so no floor would do
    w = idp.power_check(plan("whiff_pct", 30.0, 400, 400, 33.0))
    assert len(w) == 1 and "6.35" in w[0] and "no floor would" in w[0]
    # SE 0.5 on 100, floor 100, gap 1.2: MDC = 1.96 * sqrt(0.25 + 0.25) = 1.386 > 1.2;
    # room = (1.2 / 1.96)^2 - 0.25 = 0.1248 -> floor = 0.25 * 100 / 0.1248 = 200.3 -> 201
    w = idp.power_check(plan("ivb_in", 1.0, 100, 100, 2.2, se=0.5))
    assert "about 201 would" in w[0]
    # Velocity: SE 0.09 on 795, floor 150: SE at floor 0.09 * sqrt(795 / 150) = 0.207; MDC 0.44 < 1.0 -> no warning
    assert idp.power_check(plan("velo", 95.4, 795, 150, 96.4, se=0.09)) == []
    real = yaml.safe_load((EXAMPLES / "idp-gilbert-2026.yaml").read_text())
    w = idp.power_check(real)
    assert len(w) == 1 and w[0].startswith("priority 3")          # the slider-whiff payoff check is underpowered


def test_expected_fraction_and_guards():
    s, t = date(2027, 4, 1), date(2027, 5, 1)                      # 30 days
    assert idp.expected_fraction(s, t, date(2027, 4, 16)) == 0.5   # 15 of 30 days
    assert idp.expected_fraction(s, t, date(2027, 6, 1)) == 1.0
    assert idp.expected_fraction(s, t, date(2027, 4, 2), pace="step") == 1.0
    g = idp.Guard(idp.Metric("velo", "FF"), limit=93.0, keep="above", floor=100)
    assert idp.guard_status(g, {"value": 94.0, "lo": 93.5, "hi": 94.5, "n": 300}) == "ok"
    assert idp.guard_status(g, {"value": 92.8, "lo": 92.4, "hi": 93.2, "n": 300}) == "watch"
    assert idp.guard_status(g, {"value": 92.0, "lo": 91.6, "hi": 92.4, "n": 300}) == "breached"
    assert idp.guard_status(g, {"value": 92.0, "lo": 91.6, "hi": 92.4, "n": 50}) == "insufficient"


def test_progress_and_notes_on_the_fictional_season():
    plan = idp.load_plan(EXAMPLES / "idp-fictional.yaml")
    p = idp.fictional_pitches(2027)
    rows = idp.progress(plan, p, plan.period_end)
    v = dict(zip(rows["priority"], rows["verdict"]))
    # The fictional ride arrives in five starts (+1.6 in against a +1.4 target) -> on track; the sweep builds
    # only ~2 in by the last start (season mean ~+1 against +2.4) -> behind; the changeup gap never moves
    assert v[1] == "on_track" and v[2] == "behind" and v[3] in ("flat", "wrong_way")
    assert plan.warnings == []                               # every fictional priority can detect its planned change
    early = idp.progress(plan, p, "2027-04-05")             # two starts: every priority under its floor
    assert set(early["verdict"]) == {"insufficient"}
    fo = idp.front_office_note(plan, rows)
    coach = idp.coach_note(plan, rows)
    assert "FICTIONAL" in fo and "FICTIONAL" in coach
    assert f"n = {rows.loc[0, 'n']:,} pitches" in fo and "Recommendation:" in fo
    assert "Keep doing" in coach
