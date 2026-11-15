"""The Stuff+ benchmark's logic, on fictional pitchers and a made-up Stuff+ table."""
import numpy as np
import pandas as pd
import pytest

from baseball.edge import savant_benchmark as sb
from baseball.edge import stuffplus_benchmark as sp


def _fg(rows):
    """(season, fgid, {column: Stuff+}) -> a table shaped like the FanGraphs one."""
    out = []
    for season, fgid, vals in rows:
        out.append({"season": season, "fgid": fgid, "ip": 50.0, **{c: vals.get(c, np.nan) for c in sp.FG_COLUMNS}, "stuff": vals.get("stuff", 100)})
    return pd.DataFrame(out)


def _counts(rows):
    return pd.DataFrame(rows, columns=["pitcher", "pitch_type", "pitches"])


def _table(rows):
    return pd.DataFrame(rows, columns=["pitcher", "pitch_type", "swings", "whiff_pct", "x_whiff_pct"])


def test_ids_map_only_through_the_register():
    fg = _fg([(2025, 11, {"FA": 100}), (2025, 12, {"FA": 110}), (2026, 11, {"FA": 105}), (2026, 99, {"FA": 90})])
    register = pd.DataFrame({"key_fangraphs": ["11", "12", None, "sa123"], "key_mlbam": [501, 502, 503, 504]})
    mapped, counts = sp.map_ids(fg, register)
    assert counts == {"2025": {"rows": 2, "mapped": 2, "unmapped": 0}, "2026": {"rows": 2, "mapped": 1, "unmapped": 1}}
    assert sorted(zip(mapped["season"], mapped["pitcher"])) == [(2025, 501), (2025, 502), (2026, 501)]   # 99 has no link and is not guessed


def test_long_stuff_keeps_only_filled_columns():
    fg = _fg([(2025, 1, {"FA": 101, "SL": 120})]).assign(pitcher=501)
    out = sp.long_stuff(fg)
    assert sorted(zip(out["fg_col"], out["stuff_plus"])) == [("FA", 101), ("SL", 120)]


def test_pitch_type_rule():
    counts = _counts([(1, "FF", 900), (1, "ST", 400),                    # sweeper only: owns SL
                      (2, "SL", 500), (2, "ST", 30),                     # a few stray sweepers: the slider is 94% and owns SL
                      (3, "SL", 300), (3, "ST", 300),                    # both: neither owns SL
                      (4, "SV", 200), (5, "KC", 250), (6, "CU", 250), (6, "SV", 20),
                      (7, "KN", 800), (8, "FS", 150), (8, "FO", 150)])
    table = _table([(p, t, 100, 30.0, 30.0) for p, t, _ in counts.itertuples(index=False)])
    out = sp.fg_column(table, counts)
    got = {(p, t): c for p, t, c in zip(out["pitcher"], out["pitch_type"], out["fg_col"])}
    assert got == {(1, "FF"): "FA", (1, "ST"): "SL", (2, "SL"): "SL", (4, "SV"): "CU", (5, "KC"): "KC", (6, "CU"): "CU",
                   (8, "FS"): "FS", (8, "FO"): "FO"}
    # dropped: 2's stray sweepers, both of 3's, 6's stray slurves, and the knuckleball FanGraphs has no column for


def test_shared_column_share_uses_every_pitch_not_only_rows_over_the_floor():
    """A pitcher's second pitch can be under 60 swings and still share the column."""
    counts = _counts([(1, "SL", 300), (1, "ST", 250)])
    table = _table([(1, "SL", 100, 30.0, 30.0)])   # the sweeper never reached the swing floor
    assert sp.fg_column(table, counts).empty


def test_mapping_evidence_counts_filled_columns():
    counts = _counts([(1, "ST", 300), (2, "ST", 300), (3, "FF", 500), (4, "SV", 150), (5, "KC", 200), (6, "SL", 200), (6, "ST", 200)])
    fg = _fg([(2025, 1, {"SL": 110}), (2025, 2, {}), (2025, 3, {"FA": 100}), (2025, 4, {"CU": 95}), (2025, 5, {"KC": 105}), (2025, 6, {"SL": 99})])
    fg = fg.assign(pitcher=fg["fgid"])
    e = sp.mapping_evidence(counts, fg)
    assert e["sweeper_no_slider"] == {"pitchers": 2, "with_SL": 1}
    assert e["no_slider_sweeper_or_slurve"] == {"pitchers": 2, "with_SL": 0}          # pitchers 3 and 5
    assert e["slurve_no_slider_or_sweeper"] == {"pitchers": 1, "with_SL": 0, "with_CU": 1}
    assert e["knuckle_curve_no_curveball"] == {"pitchers": 1, "with_KC": 1, "with_CU": 0}
    assert e["slider_and_sweeper_100_each"] == {"pitchers": 1, "with_SL": 1}


def test_season_frame_joins_stuff_and_savant_on_the_right_columns():
    counts = _counts([(1, "FF", 900), (1, "ST", 400), (2, "KC", 300)])
    table = _table([(1, "FF", 200, 22.0, 21.0), (1, "ST", 100, 35.0, 33.0), (2, "KC", 80, 30.0, 31.0), (2, "CH", 40, 30.0, 31.0)])
    stuff = pd.DataFrame({"pitcher": [1, 1, 2, 2], "fg_col": ["FA", "SL", "KC", "CU"], "stuff_plus": [104.0, 118.0, 97.0, 50.0], "ip": 50.0})
    savant = pd.DataFrame({"pitcher": [1, 1, 2], "pitch_type": ["FF", "ST", "CU"], "sv_whiff_pct": [22.0, 35.0, 30.0], "sv_rv100": [0.5, 1.0, -0.2],
                           "sv_put_away": np.nan, "sv_xwoba": np.nan, "sv_pitches": [900, 400, 300], "sv_miss_in": [1.0, 4.8, 4.4], "sv_swings": 100})
    f = sp.season_frame(table, counts, stuff, savant).set_index(["pitcher", "pitch_type"])
    assert f.loc[(1, "ST"), "stuff_plus"] == 118.0                      # the sweeper reads FanGraphs' SL column
    assert f.loc[(2, "KC"), "stuff_plus"] == 97.0 and f.loc[(2, "KC"), "sv_miss_in"] == 4.4   # KC: FanGraphs KC, Savant CU
    assert len(f) == 3                                                  # the 40-swing changeup is under the floor


def test_folds_keep_a_pitcher_together_and_are_repeatable():
    pitchers = np.repeat(np.arange(40), 3)
    f = sp.folds(pitchers, 5, seed=1)
    assert all(len(set(f[pitchers == p])) == 1 for p in range(40))
    assert sorted(np.bincount(f).tolist()) == [24] * 5
    assert (f == sp.folds(pitchers, 5, seed=1)).all() and (f != sp.folds(pitchers, 5, seed=2)).any()


def _pair(n, seed, driver):
    rng = np.random.default_rng(seed)
    types = rng.choice(["FF", "SL"], n)
    level = np.where(types == "SL", 34.0, 22.0)                     # sliders miss more bats than four-seamers
    quality = rng.normal(0, 1, n)                                    # how good the pitch is for its type
    x = level + 4 * quality + rng.normal(0, 3, n)                    # knows the type and some of the quality
    stuff = 100 + 10 * quality + rng.normal(0, 3, n)                 # scaled inside the type: no type level
    miss = np.where(types == "SL", 4.2, 1.0) + rng.normal(0, 0.5, n)
    signal = {"quality": level + 4 * quality, "x": x, "none": np.full(n, 28.0)}[driver]
    return pd.DataFrame({"pitcher": rng.integers(1, n // 2, n), "sv_type": types, "pitch_type": types,
                         "swings_prev": rng.integers(60, 400, n), "swings_curr": rng.integers(60, 400, n),
                         "whiff_pct_prev": signal + rng.normal(0, 4, n), "x_whiff_pct_prev": x, "stuff_plus_prev": stuff,
                         "sv_miss_in_prev": miss, "whiff_pct_curr": signal + rng.normal(0, 2, n)})


def test_a_type_scaled_measure_needs_the_pitch_type_to_compete():
    """Stuff+ here carries the true quality but no type level: poor alone, best once the type is given."""
    res = sp.next_season(_pair(900, 1, "quality"), n_boot=300, seed=3)["cross_validated_by_pitcher"]
    m = res["models"]
    assert m["stuff"]["rmse"] > m["type"]["rmse"] > m["stuff+type"]["rmse"]
    assert m["stuff+type"]["rmse"] < m["expected+type"]["rmse"]
    assert res["winner"]["alone"] == "expected" and res["winner"]["alone_given_pitch_type"] == "stuff+type"


def test_verdict_is_a_tie_when_neither_measure_carries_signal():
    res = sp.next_season(_pair(900, 2, "none"), n_boot=300, seed=3)["cross_validated_by_pitcher"]
    assert res["winner"]["alone_given_pitch_type"] == "tie" and res["winner"]["with_last_season_given_pitch_type"] == "tie"
    assert res["models"]["last_whiff"]["gain_vs_baseline_pct"] == 0


def test_cross_validation_never_scores_a_pitcher_with_weights_fit_on_him():
    """Give one pitcher wild outcomes. His own predictions must be the same as if his outcomes were ordinary,
    because the weights that predict him are fit without him."""
    f = _pair(400, 4, "x")
    target = f["pitcher"].value_counts().index[0]
    wild = f.assign(whiff_pct_curr=f["whiff_pct_curr"].where(f["pitcher"] != target, 500.0))
    a, b = sp.cv_predictions(f, sp.MODELS, 5, 7), sp.cv_predictions(wild, sp.MODELS, 5, 7)
    mine = (f["pitcher"] == target).to_numpy()
    for name in sp.MODELS:
        assert np.allclose(a[name][mine], b[name][mine])
        assert not np.isnan(a[name]).any()
    other_folds = sp.folds(f["pitcher"]) != sp.folds(f["pitcher"])[mine][0]
    assert not np.allclose(a["expected"][other_folds], b["expected"][other_folds])   # the others' weights did see him


def test_score_arithmetic_and_contrasts():
    f = _pair(500, 5, "x")
    preds = sp.cv_predictions(f, sp.MODELS, 5, 7)
    s = sp.score(f, preds, sp.CONTRASTS, n_boot=200, seed=1)
    y, w = f["whiff_pct_curr"].to_numpy(float), sb.weights(f)
    assert s["models"]["expected"]["rmse"] == pytest.approx(np.sqrt(np.average((y - preds["expected"]) ** 2, weights=w)))
    for name, row in s["models"].items():
        assert row["gain_vs_baseline_pct"] == pytest.approx(100 * (1 - row["rmse"] / s["models"]["last_whiff"]["rmse"]))
    c = s["contrasts"]["expected minus stuff"]
    assert c["rmse_diff"] == pytest.approx(s["models"]["expected"]["rmse"] - s["models"]["stuff"]["rmse"]) and c["lo"] <= c["rmse_diff"] <= c["hi"]
    assert sp.verdict(s, "expected", "stuff") == "expected"


def test_earlier_pair_weights_are_used_only_for_models_without_stuff_plus():
    test, train = _pair(400, 6, "x"), _pair(400, 7, "x").drop(columns="stuff_plus_prev")   # the earlier pair has no Stuff+
    out = sp.next_season(test, train, n_boot=50, seed=1)
    ho = out["weights_from_earlier_pair"]
    assert ho["train_pitches"] == 400 and not any("stuff" in k for k in ho["models"])
    assert {"last_whiff", "expected", "miss", "last+expected", "last+miss+type"} <= set(ho["models"])
    same = sb.next_season(train.assign(stuff_plus_prev=0.0), test, n_boot=50, seed=1)["models"]["last+expected"]["rmse"]
    assert ho["models"]["last+expected"]["rmse"] == pytest.approx(same)   # the same fit the Savant benchmark makes


def test_pitcher_level_weights_by_swings():
    frame = pd.DataFrame({"season": 2025, "pitcher": [1, 1, 2], "swings": [300, 100, 200], "x_whiff_pct": [20.0, 40.0, 30.0],
                          "whiff_pct": [22.0, 38.0, 31.0], "sv_rv100": [1.0, -1.0, 0.5], "sv_pitches": [900, 300, 600]})
    more = pd.concat([frame] + [frame.assign(pitcher=frame["pitcher"] + 10 * i, x_whiff_pct=frame["x_whiff_pct"] + i) for i in range(1, 6)])
    overall = pd.DataFrame({"season": 2025, "pitcher": sorted(more["pitcher"].unique())}).assign(stuff=lambda d: 100.0 + d["pitcher"] % 7)
    out = sp.pitcher_level(more, overall, n_boot=50, seed=1)
    assert out["pitcher_seasons"] == 12 and out["median_swings"] == 300.0
    r = sp.roll_up(frame).set_index("pitcher")
    assert r.loc[1, "x_whiff_pct"] == pytest.approx(25.0) and r.loc[1, "whiff_pct"] == pytest.approx(26.0)   # (300 * 20 + 100 * 40) / 400
    assert r.loc[1, "sv_rv100"] == pytest.approx(0.5) and r.loc[1, "swings"] == 400                         # (900 * 1 - 300 * 1) / 1200
    assert np.isnan(sp.roll_up(frame.assign(sv_rv100=[1.0, np.nan, 0.5])).set_index("pitcher").loc[1, "sv_rv100"])


def test_load_fangraphs_stacks_every_season(tmp_path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    _fg([(2024, 1, {"FA": 99})]).to_csv(a, index=False)
    _fg([(2025, 1, {"FA": 101}), (2026, 1, {"FA": 103})]).to_csv(b, index=False)
    out = sp.load_fangraphs([a, b])
    assert out["season"].tolist() == [2024, 2025, 2026] and out["FA"].tolist() == [99, 101, 103]


def test_held_out_fits_stuff_weights_on_the_earlier_pair_only():
    train, test = _pair(600, 11, "quality"), _pair(600, 12, "quality")
    a = sp.held_out(train, test, n_boot=100, seed=1)
    assert a["train_pitches"] == 600 and a["pitches"] == 600 and set(sp.NEEDS_STUFF) <= set(a["models"])
    # the predictions for the test pair do not move when its outcomes do
    moved = test.assign(whiff_pct_curr=test["whiff_pct_curr"] + 40)
    p0, p1 = sp.holdout_predictions(train, test, sp.MODELS), sp.holdout_predictions(train, moved, sp.MODELS)
    assert all(np.allclose(p0[k], p1[k]) for k in sp.MODELS)
    # and they do move when the earlier pair's outcomes do
    p2 = sp.holdout_predictions(train.assign(whiff_pct_curr=train["whiff_pct_curr"] + 40), test, sp.MODELS)
    assert not np.allclose(p0["stuff+type"], p2["stuff+type"])
    # the planted structure is found out of sample: Stuff+ with the pitch type beats expected whiff with it
    assert a["winner"]["alone_given_pitch_type"] == "stuff+type" and a["winner"]["alone"] == "expected"
    w = sb.weights(test)
    assert a["models"]["stuff+type"]["rmse"] == pytest.approx(sb.rmse(test["whiff_pct_curr"], p0["stuff+type"], w))


def test_pair_carries_innings_so_the_floor_can_be_applied():
    counts = _counts([(1, "FF", 900), (2, "FF", 900)])
    prev = _table([(1, "FF", 200, 22.0, 21.0), (2, "FF", 200, 25.0, 24.0)])
    curr = _table([(1, "FF", 200, 23.0, 0.0), (2, "FF", 200, 24.0, 0.0)])
    stuff = pd.DataFrame({"pitcher": [1, 2], "fg_col": ["FA", "FA"], "stuff_plus": [104.0, 96.0], "ip": [9.2, 60.0]})
    savant = pd.DataFrame({"pitcher": [1, 2], "pitch_type": ["FF", "FF"], "sv_whiff_pct": [22.0, 25.0], "sv_rv100": [0.5, 0.1],
                           "sv_put_away": np.nan, "sv_xwoba": np.nan, "sv_pitches": [900, 900], "sv_miss_in": [1.0, 1.1], "sv_swings": 200})
    m = sp.pair(sp.season_frame(prev, counts, stuff, savant), curr)
    assert sorted(m["ip_prev"]) == [9.2, 60.0]
    assert m[m["ip_prev"] >= sp.MIN_IP]["pitcher"].tolist() == [2]
