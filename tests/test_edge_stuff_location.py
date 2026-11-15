"""The location-aware expected whiff: its inputs, the no-leakage design and the adoption rule, on fictional data."""
import numpy as np
import pandas as pd
import pytest

from baseball.edge import savant_benchmark as sb
from baseball.edge import stuff_location as sl


def test_add_location_signs_toward_the_hitter_and_scales_height():
    s = pd.DataFrame({"plate_x": [-0.5, -0.5, 0.5, np.nan], "plate_z": [1.5, 3.5, 2.5, 2.0], "sz_top": [3.5, 3.5, 3.5, 3.5], "sz_bot": [1.5, 1.5, 1.5, 1.5],
                      "stand": ["R", "L", "L", "R"], "balls": [0, 1, 3, 0], "strikes": [2, 0, 1, 0]})
    out = sl.add_location(s)
    assert len(out) == 3                                             # the swing with no tracked location is dropped
    assert out["px_in"].tolist() == [0.5, -0.5, 0.5]                 # inside to a right-hander, away from a left-hander, inside to a left-hander
    assert out["pz_rel"].tolist() == [0.0, 1.0, 0.5]                 # bottom, top and middle of the zone
    assert out["strikes"].tolist() == [2.0, 0.0, 1.0]


def _swings(n_pitchers=60, per=160, seed=4):
    """Fictional swings on one pitch type. Whiffs come from chasing below the zone, and pitchers differ in how
    often they get that swing. Nothing physical differs between pitchers."""
    rng = np.random.default_rng(seed)
    rows = []
    for pid in range(1, n_pitchers + 1):
        low_rate = rng.uniform(0.15, 0.75)
        for _ in range(per):
            low = rng.random() < low_rate
            pz = rng.normal(1.1, 0.2) if low else rng.normal(2.6, 0.3)
            rows.append({"pitcher": pid, "player_name": f"Pitcher {pid}", "p_throws": "R", "stand": "R", "game_year": 2025, "pitch_type": "ST", "pitch_name": "Sweeper",
                         "whiff": int(rng.random() < (0.60 if low else 0.12)), "velo": 82 + rng.normal(0, 1), "ivb_in": rng.normal(1, 1), "hb_arm_in": rng.normal(-14, 1),
                         "spin": 2600.0, "ext_ft": 6.3, "rel_z_ft": 5.6, "rel_x_arm_ft": 2.0, "arm_angle": 35.0, "d_velo": -11.0, "d_ivb": -14.0, "d_hb": -20.0,
                         "same_hand": 1, "plate_x": rng.normal(0, 0.6), "plate_z": pz, "sz_top": 3.4, "sz_bot": 1.6, "balls": int(rng.integers(0, 4)),
                         "strikes": int(rng.integers(0, 3))})
    return sl.add_location(pd.DataFrame(rows))


def test_location_measure_finds_what_physics_cannot_and_is_cross_fit():
    s = _swings()
    t, diag = sl.both_tables(s)
    assert diag["auc_location"] > diag["auc_physics"] + 0.1 and diag["auc_physics"] < 0.56
    r = sl.same_season(t, n_boot=100)["ST"]
    assert r["location"]["r"] > 0.7 and r["location"]["lo"] > 0 and abs(r["physics"]["r"]) < 0.35
    # cross-fit: flip one pitcher's outcomes and his own location-aware number does not move
    target = 7
    flipped = s.assign(whiff=s["whiff"].where(s["pitcher"] != target, 1 - s["whiff"]))
    t2, _ = sl.both_tables(flipped)
    a = t.set_index("pitcher").loc[target, "x_loc_pct"]
    b = t2.set_index("pitcher").loc[target, "x_loc_pct"]
    assert a == pytest.approx(b)
    assert t2.set_index("pitcher").loc[target, "whiff_pct"] == pytest.approx(100 - t.set_index("pitcher").loc[target, "whiff_pct"])


def _tables(seed, n=240):
    """Two seasons where next season's whiff rate follows a trait the location number sees and the physics number does not, on sweepers only."""
    rng = np.random.default_rng(seed)
    types = np.tile(["ST", "SL", "FF"], n // 3)
    trait = rng.normal(0, 5, n)
    base = pd.DataFrame({"pitcher": np.arange(n) // 3, "pitch_type": types, "swings": rng.integers(60, 300, n)})
    sees = np.where(types == "ST", trait, 0.0)
    prev = base.assign(whiff_pct=28 + trait + rng.normal(0, 5, n), x_whiff_pct=28 + np.where(types == "ST", 0.0, trait) + rng.normal(0, 1, n),
                       x_loc_pct=28 + np.where(types == "ST", sees, trait) + rng.normal(0, 1, n))
    curr = base.assign(whiff_pct=28 + trait + rng.normal(0, 3, n), x_whiff_pct=0.0, x_loc_pct=0.0)
    return prev, curr


def test_pair_uses_only_the_earlier_seasons_predictors():
    prev, curr = _tables(1)
    m = sl.pair(prev, curr.assign(x_loc_pct=999.0, x_whiff_pct=999.0))        # next season's measures must never be read
    assert (m["x_loc_pct_prev"] < 100).all() and (m["x_whiff_pct_prev"] < 100).all()
    one = m.iloc[0]
    src = prev[(prev["pitcher"] == one["pitcher"]) & (prev["pitch_type"] == one["pitch_type"])].iloc[0]
    out = curr[(curr["pitcher"] == one["pitcher"]) & (curr["pitch_type"] == one["pitch_type"])].iloc[0]
    assert one["x_loc_pct_prev"] == src["x_loc_pct"] and one["whiff_pct_prev"] == src["whiff_pct"] and one["whiff_pct_curr"] == out["whiff_pct"]
    assert len(sl.pair(prev.assign(swings=59), curr)) == 0                      # the 60-swing floor


def test_held_out_adopts_only_where_the_interval_is_off_zero():
    (p0, c0), (p1, c1) = _tables(1), _tables(2)
    h = sl.held_out(sl.pair(p0, c0), sl.pair(p1, c1), n_boot=300)
    comp = h["contrasts"]["location minus physics"]
    assert comp["ST"]["hi"] < 0 and comp["SL"]["lo"] < 0 < comp["SL"]["hi"]     # better on sweepers, a wash on sliders
    assert h["rule_alone"]["adopted_for"] == ["ST"] and h["rule_alone"]["clearly_worse_on"] == []
    assert comp["all"]["diff"] == pytest.approx(h["rmse"]["location"] - h["rmse"]["physics"])
    assert h["r_with_next_season_whiff"]["ST"]["location"] > h["r_with_next_season_whiff"]["ST"]["physics"]


def test_weights_come_from_the_training_pair_only():
    from baseball.edge import stuff

    (p0, c0), (p1, c1) = _tables(3), _tables(4)
    train, test = sl.pair(p0, c0), sl.pair(p1, c1)
    e1 = sl.errors(train, test)
    assert len(e1) == len(test) and (e1["w"] == sb.weights(test)).all()
    # a test pitch's error does not depend on which other test pitches are scored with it: nothing is fit on the test pair
    part = sl.errors(train, test.iloc[:50].reset_index(drop=True))
    assert all(np.allclose(part[m], e1[m].iloc[:50]) for m in sl.MODELS)
    # and it does depend on the training pair's outcomes
    moved = sl.errors(train.assign(whiff_pct_curr=train["whiff_pct_curr"] + 10), test)
    assert not np.allclose(moved["last+location"], e1["last+location"])
    # the published blend, reproduced
    drop = lambda t: t.drop(columns="x_loc_pct")
    h = stuff.validate_holdout(drop(p0), drop(c0), drop(p1), drop(c1), n_boot=5)
    assert float(np.sqrt(np.average(e1["last+physics"], weights=e1["w"]))) == pytest.approx(h["rmse_blend"])


def test_decide_blocks_adoption_when_any_type_is_clearly_worse():
    comp = {"all": {"lo": -1, "hi": -0.5}, "ST": {"lo": -2.0, "hi": -0.5}, "SL": {"lo": 0.05, "hi": 0.4}, "FF": {"lo": -0.1, "hi": 0.1}}
    assert sl.decide(comp) == {"clearly_better_on": ["ST"], "clearly_worse_on": ["SL"], "adopted_for": []}
    comp["SL"] = {"lo": -0.1, "hi": 0.4}
    assert sl.decide(comp)["adopted_for"] == ["ST"]
