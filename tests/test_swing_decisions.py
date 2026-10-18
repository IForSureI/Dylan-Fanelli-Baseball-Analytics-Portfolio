"""Swing decisions: hand-checked arithmetic, and recovery of a known decision skill on FICTIONAL data.

Every frame here is fictional (built in the test or by swing_decisions.fictional_pitches): no Statcast
file is read, so the tests run with no data.
"""
import numpy as np
import pandas as pd
import pytest

from baseball.evaluation import swing_decisions as S


# ---------------------------------------------------------------- hand-checked pieces

def _pitch(**kw):
    row = {"game_pk": 1, "game_year": 2025, "at_bat_number": 1, "pitch_number": 1, "batter": 1, "stand": "R",
           "pitch_type": "FF", "description": "ball", "events": None, "type": "B", "balls": 0, "strikes": 0,
           "plate_x": 0.0, "plate_z": 2.5, "sz_top": 3.5, "sz_bot": 1.5, "zone": 5, "delta_run_exp": 0.03,
           "woba_value": np.nan, "woba_denom": np.nan, "estimated_woba_using_speedangle": np.nan,
           "launch_speed": np.nan, "launch_angle": np.nan, "release_speed": 94.0, "bat_speed": np.nan,
           "swing_length": np.nan, "attack_angle": np.nan, "attack_direction": np.nan, "swing_path_tilt": np.nan,
           "intercept_ball_minus_batter_pos_y_inches": np.nan}
    row.update(kw)
    return row


def test_prepare_mirrors_lefties_and_scales_height():
    # FICTIONAL: a pitch 0.5 ft toward first base is away from a righty (+6 in) and in on a lefty (-6 in);
    # plate_z 3.0 in a 1.5-3.5 zone is 75% of the way up.
    p = pd.DataFrame([_pitch(plate_x=0.5, plate_z=3.0, stand="R"), _pitch(plate_x=0.5, plate_z=3.0, stand="L")])
    d = S.prepare(p)
    assert d["x_in"].tolist() == pytest.approx([6.0, -6.0])
    assert d["z_rel"].tolist() == pytest.approx([0.75, 0.75])


def test_prepare_drops_non_decisions():
    # FICTIONAL: automatic balls, pitchouts, bunts and unlabeled pitches are not decisions
    p = pd.DataFrame([_pitch(), _pitch(description="automatic_ball"), _pitch(description="pitchout"),
                      _pitch(description="foul_bunt"), _pitch(description="hit_into_play", events="sac_bunt"),
                      _pitch(pitch_type="EP"), _pitch(plate_x=np.nan)])
    assert len(S.prepare(p)) == 1


def test_prepare_uses_fixed_zones_when_given():
    # FICTIONAL: the batter's fixed zone replaces the per-pitch one
    p = pd.DataFrame([_pitch(sz_top=3.9, sz_bot=1.9, plate_z=2.5)])
    zones = pd.DataFrame({"sz_top": [3.5], "sz_bot": [1.5]}, index=[1])
    assert S.prepare(p, zones)["z_rel"].iloc[0] == pytest.approx(0.5)


def test_attack_regions_hand_checked():
    h = S.HALF_PLATE_IN
    x = [0, 0.9 * h, 1.5 * h, 2.5 * h, 0, 0]
    z = [0.5, 0.5, 0.5, 0.5, 1.1, -0.3]
    assert S.attack_region(x, z).tolist() == ["heart", "shadow", "chase", "waste", "shadow", "chase"]


def test_fixed_zones_map_stance_to_abs():
    # FICTIONAL: 40 batters seen in both eras with ABS top = 1.8 + 0.4 x stance top, plus one seen only in 2025
    rng = np.random.default_rng(0)
    stance = rng.normal(3.4, 0.15, 40)
    rows = []
    for b, st in enumerate(stance):
        rows.append({"batter": b, "game_year": 2025, "sz_top": st, "sz_bot": 1.6})
        top = 1.8 + 0.4 * st
        rows.append({"batter": b, "game_year": 2026, "sz_top": top, "sz_bot": top * 27 / 53.5})
    rows.append({"batter": 99, "game_year": 2025, "sz_top": 3.5, "sz_bot": 1.6})
    z = S.fixed_zones(pd.DataFrame(rows))
    assert z.loc[99, "zone_source"] == "mapped"
    assert z.loc[99, "sz_top"] == pytest.approx(1.8 + 0.4 * 3.5, abs=1e-6)
    assert z.loc[99, "sz_bot"] == pytest.approx(z.loc[99, "sz_top"] * 0.27 / 0.535)
    assert (z.loc[list(range(40)), "zone_source"] == "abs").all()


def test_fixed_zones_without_abs_era_use_stance():
    z = S.fixed_zones(pd.DataFrame({"batter": [1, 1], "game_year": [2024, 2025], "sz_top": [3.4, 3.6],
                                    "sz_bot": [1.5, 1.7]}))
    assert z.loc[1, "sz_top"] == pytest.approx(3.5) and z.loc[1, "zone_source"] == "stance"


class _Const:
    """A stand-in league model with fixed values, to hand-check the decision arithmetic."""
    def __init__(self, es, et, p):
        self.v = (es, et, p)

    def predict(self, d):
        es, et, p = self.v
        return pd.DataFrame({"es": es, "et": et, "p": p}, index=d.index)


def test_decision_value_hand_checked():
    # es - et = 0.05 and an average hitter swings 70% of the time.
    # Swing: (1 - 0.7) x 0.05 = +0.015.  Take: (0 - 0.7) x 0.05 = -0.035.
    # Raw choice-minus-alternative: swing +0.05, take -0.05; the identity raw = 2 dv + (2p - 1) gap holds.
    d = S.prepare(pd.DataFrame([_pitch(description="foul", type="S"), _pitch()]))
    s = S.score(d, _Const(0.02, -0.03, 0.7))
    assert s["dv"].tolist() == pytest.approx([0.015, -0.035], abs=1e-6)
    raw = (2 * s["swing"] - 1) * s["gap"]
    assert raw.tolist() == pytest.approx((2 * s["dv"] + s["mix"]).tolist(), abs=1e-6)


def test_hitter_seasons_hand_checked():
    # FICTIONAL: two pitches, one swing (dv +0.015, in zone) and one take (dv -0.035, out of zone)
    d = S.prepare(pd.DataFrame([_pitch(description="foul", type="S", zone=5), _pitch(zone=13, plate_x=1.5)]))
    h = S.hitter_seasons(S.score(d, _Const(0.02, -0.03, 0.7))).iloc[0]
    assert h["pitches"] == 2
    assert h["dv100"] == pytest.approx(100 * (0.015 - 0.035) / 2, abs=1e-4)
    assert h["dv100_zone"] + h["dv100_out"] == pytest.approx(h["dv100"], abs=1e-6)
    assert h["chase"] == 0 and h["zone_swing"] == 1


def test_squared_up_hand_checked():
    # 1.23 x 70 + 0.23 x 85 = 105.65 mph possible; 84.52 is 80% of it
    assert S.squared_up(84.52, 70, 85)[()] == pytest.approx(0.8, abs=1e-4)


def test_fisher_interval_brackets_r():
    lo, hi = S.fisher_ci(0.8, 200)
    assert lo < 0.8 < hi and hi - lo < 0.15


def test_tool_grade_hand_checked():
    # one SD above the mean is a 60; 1.25 SD below is 37.5, which rounds to 40 (halves round up)
    assert S.tool_grade(0.270, 0.246, 0.024)["grade"] == 60
    assert S.tool_grade(100.825, 104.2, 2.7)["grade"] == 40
    assert S.tool_grade(0.15, 0.20, 0.05, higher_is_better=False)["grade"] == 60


def test_regress_dv_uses_m():
    # w = 600 / (600 + 200) = 0.75: 0.8 observed -> 0.6 toward a league of 0
    r = S.regress_dv(0.8, 600, M=200, tau100=0.3).iloc[0]
    assert r["estimate"] == pytest.approx(0.6) and r["weight"] == pytest.approx(0.75)
    assert r["sd"] == pytest.approx(0.3 * np.sqrt(0.25))


def test_drop_follow_up_hand_checked():
    # FICTIONAL: batter 1 drops 2.0 then gains 0.5; batter 2 drops 0.2 then gains 0.1
    ch = pd.DataFrame({"batter": [1, 1, 2, 2], "season_a": [2024, 2025, 2024, 2025],
                       "season_b": [2025, 2026, 2025, 2026], "change": [-2.0, 0.5, -0.2, 0.1]})
    r = S.drop_follow_up(ch)
    assert r["n_drops"] == 1 and r["next_mean"] == pytest.approx(0.5) and r["share_back_half"] == 0.0


def test_execution_decomposition_adds_up():
    # rv = base + dv + swing execution + take luck, pitch by pitch, so per 100 as well
    d = S.prepare(pd.DataFrame([_pitch(description="foul", type="S", delta_run_exp=-0.04), _pitch(delta_run_exp=0.06)]))
    s = S.score(d, _Const(0.02, -0.03, 0.7))
    e = S.execution(s).iloc[0]
    total = e["base100"] + e["dv100"] + e["swing_exec100"] + e["take_luck100"]
    assert total == pytest.approx(100 * (-0.04 + 0.06) / 2, abs=1e-4)


# ---------------------------------------------------------------- recovery on fictional leagues

@pytest.fixture(scope="module")
def fictional():
    p, skill = S.fictional_pitches(hitters=80, per_hitter=700, seasons=(2024, 2025), seed=3)
    d = S.prepare(p)
    model = S.fit_model(d, min_leaf=100, iters=80)
    return S.score(d, model), skill


def test_model_learns_the_swing_take_gap(fictional):
    # FICTIONAL rule: swing minus take value is 0.06 x (1 - distance from the middle) - 0.01 x strikes
    s, _ = fictional
    middle = s[(s["x_in"].abs() < 3) & ((s["z_rel"] - 0.5).abs() < 0.15) & (s["strikes"] == 0)]
    far = s[(s["x_in"].abs() > 18)]
    assert middle["gap"].mean() > 0.03 and far["gap"].mean() < 0


def test_decision_value_recovers_known_skill(fictional):
    # FICTIONAL hitters were given a decision skill; DV100 should rank them by it
    s, skill = fictional
    h = S.hitter_seasons(s)
    dv = h.groupby("batter")["dv100"].mean()
    assert np.corrcoef(dv, skill.reindex(dv.index))[0, 1] > 0.7
    # and it carries from one fictional season to the next
    pr = S.pairs(h, 2024, 2025, min_pitches=500)
    assert np.corrcoef(pr["dv100_a"], pr["dv100_b"])[0, 1] > 0.5


def test_league_average_decision_value_is_near_zero(fictional):
    s, _ = fictional
    assert abs(100 * s["dv"].mean()) < 0.1


def test_split_half_reliability_rises_with_n(fictional):
    s, _ = fictional
    curve = S.split_half(s, grid=(50, 150, 300), reps=4)
    assert curve["r"].is_monotonic_increasing
    rc = S.reliability_constant(curve, S.within_variance(s))
    assert rc["M"] > 0 and rc["tau100"] > 0


def test_incremental_finds_a_real_added_signal():
    # FICTIONAL: next-season wOBA = 0.3 + 0.5 (wOBA - 0.3) + 0.02 x skill; skill is measured by dv100
    rng = np.random.default_rng(5)
    n = 300
    skill = rng.normal(0, 1, n)
    woba_a = 0.32 + rng.normal(0, 0.03, n)
    pr = pd.DataFrame({"woba_a": woba_a, "dv100_a": skill + rng.normal(0, 0.2, n), "pa_b": 500,
                       "woba_b": 0.3 + 0.5 * (woba_a - 0.3) + 0.02 * skill + rng.normal(0, 0.01, n)})
    r = S.incremental(pr, ["woba"], boot=200)
    assert r["coef_lo"] > 0 and r["loo_rmse_with"] < r["loo_rmse_base"]
    # and returns a null when the added column is noise
    pr["dv100_a"] = rng.normal(0, 1, n)
    r = S.incremental(pr, ["woba"], boot=200)
    assert r["coef_lo"] < 0 < r["coef_hi"]


# ---------------------------------------------------------------- projection and price (hand-checked, fictional inputs)

def test_blend_woba_weights_regression_and_age():
    seasons = {2026: {"woba": 0.330, "xwoba": 0.330, "pa": 400}, 2025: {"woba": 0.300, "xwoba": 0.300, "pa": 600},
               2024: {"woba": 0.310, "xwoba": 0.310, "pa": 500}}
    b = S.blend_woba(seasons, league=0.316)
    # weights 5x400, 4x600, 3x500 = 2000, 2400, 1500
    blend = (2000 * 0.330 + 2400 * 0.300 + 1500 * 0.310) / 5900
    assert b["blend"] == pytest.approx(blend)
    assert b["regressed"] == pytest.approx((1500 * blend + 1200 * 0.316) / 2700)
    assert b["projection"] == pytest.approx(b["regressed"] - 0.003)


def test_bsr_rate_weights_by_season_and_pa():
    r = S.bsr_rate({2026: (-5.0, 500), 2025: (-2.0, 600), 2024: (0.0, 700)})
    assert r == pytest.approx((5 * -5 + 4 * -2 + 0) / (5 * 500 + 4 * 600 + 3 * 700))


def test_war_components_add_up():
    p = S.project_war_season(S.LEAGUE_WOBA + S.WOBA_SCALE * 0.01, 650, fielding=-3.0, bsr_per_pa=-0.01)
    assert p["batting"] == pytest.approx(6.5)
    assert p["position"] == pytest.approx(S.POS_2B_PER_650)
    assert p["baserunning"] == pytest.approx(-6.5)
    assert p["war"] == pytest.approx((6.5 + S.REPLACEMENT_RUNS_PER_PA * 650 + 2.5 - 3.0 - 6.5) / S.RUNS_PER_WIN)
    assert S.project_war_season(0.32, 650, -3.0, -0.01, include_bsr=False)["baserunning"] == 0.0


def test_contract_value_is_smooth_across_two_war():
    lo, hi = S.contract_value(1.99, 2), S.contract_value(2.01, 2)
    # one price: 0.02 WAR is worth about 0.02 x 11.66 in each year, no cliff
    assert hi["pv"] - lo["pv"] < 0.5
    # the tiered check jumps at 2.0
    assert hi["tiered_pv"] - lo["tiered_pv"] > 5
    v = S.contract_value(2.0, 2, age_2027=30)
    assert v["war"] == pytest.approx([2.0, 1.6])
    assert v["value"] == pytest.approx([2.0 * 11.66, 1.6 * 11.66 * 1.03])
    assert v["pv"] == pytest.approx(v["value"][0] + v["value"][1] / 1.1)


def test_torres_price_scenarios_order_and_range():
    card = {"2024": {"woba": 0.322, "xwoba": 0.314, "pa": 660}, "2025": {"woba": 0.341, "xwoba": 0.363, "pa": 627},
            "2026": {"woba": 0.333, "xwoba": 0.325, "pa": 417}}
    r = S.torres_price(card)
    sc = r["scenarios"]
    assert sc["low"]["war"] < sc["base"]["war"] < sc["high"]["war"]
    assert r["fielding_range"]["low"]["value_2y"]["pv"] < sc["base"]["value_2y"]["pv"] < r["fielding_range"]["high"]["value_2y"]["pv"]
    assert r["without_baserunning"]["war"] > sc["base"]["war"]


def test_grade_from_percentile():
    assert S.grade_from_percentile(50)["grade"] == 50
    assert S.grade_from_percentile(8)["grade"] == 35
