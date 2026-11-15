"""The Savant benchmark's logic, on fictional pitchers and made-up leaderboard files."""
import numpy as np
import pandas as pd
import pytest

from baseball.edge import savant_benchmark as sb


def _table(rows):
    """A pitch table like stuff.pitch_table(): (pitcher, pitch_type, swings, whiff_pct, x_whiff_pct)."""
    return pd.DataFrame(rows, columns=["pitcher", "pitch_type", "swings", "whiff_pct", "x_whiff_pct"])


def _savant(rows):
    return pd.DataFrame(rows, columns=["pitcher", "pitch_type", "sv_whiff_pct", "sv_rv100", "sv_miss_in"]).assign(
        sv_put_away=np.nan, sv_xwoba=np.nan, sv_pitches=500, sv_swings=200)


def test_knuckle_curve_matches_savant_curveball_and_clashes_are_dropped():
    t = _table([(1, "KC", 100, 30.0, 28.0), (2, "CU", 100, 25.0, 26.0), (3, "KC", 100, 31.0, 30.0), (3, "CU", 100, 20.0, 22.0),
                (4, "FA", 100, 10.0, 12.0), (5, "FF", 100, 22.0, 21.0)])
    out = sb.savant_type(t)
    assert dict(zip(out["pitcher"], out["sv_type"])) == {1: "CU", 2: "CU", 5: "FF"}   # 3 has both, 4 is not a Savant type


def test_match_joins_on_pitcher_id_and_type_above_the_floor():
    t = _table([(1, "FF", 60, 20.0, 19.0), (1, "SL", 59, 35.0, 33.0), (2, "FF", 200, 25.0, 24.0), (9, "KC", 80, 30.0, 29.0)])
    s = _savant([(1, "FF", 20.0, 0.5, 1.0), (1, "SL", 35.0, 1.0, 4.0), (2, "SL", 30.0, 0.0, 4.2), (9, "CU", 30.1, -0.2, 4.6)])
    m = sb.match(t, s)
    # 1 SL is under 60 swings; 2 FF has no Savant row of its type; 9's knuckle curve finds Savant's CU row
    assert sorted(zip(m["pitcher"], m["pitch_type"])) == [(1, "FF"), (9, "KC")]
    assert m.set_index("pitcher").loc[9, "sv_miss_in"] == 4.6


def test_raw_counts_use_my_swing_and_whiff_definitions():
    desc = (["swinging_strike"] * 3 + ["swinging_strike_blocked"] + ["foul_tip"] * 2 + ["missed_bunt"] + ["foul_bunt"]
            + ["foul"] * 6 + ["hit_into_play"] * 6 + ["ball"] * 5 + ["called_strike"] * 5)
    miss = [2.0, 4.0, 6.0, 8.0] + [np.nan] * (len(desc) - 4)
    p = pd.DataFrame({"pitcher": 7, "pitch_type": "SL", "description": desc, "miss_distance": miss})
    r = sb.raw_counts(p).iloc[0]
    assert (r["pitches"], r["swings"], r["whiffs"], r["foul_tips"]) == (30, 20, 7, 2)
    assert r["whiff_pct"] == pytest.approx(35.0) and r["whiff_pct_no_foul_tips"] == pytest.approx(25.0)
    assert r["miss_in"] == pytest.approx(5.0) and r["misses_measured"] == 4   # an average over the misses that carry one


def test_agreement_counts_rounding_as_a_match():
    a = sb.agreement([20.04, 30.00, 41.0], [20.0, 30.0, 40.0], tol=0.0501)
    assert a["n"] == 3 and a["mean_abs_diff"] == pytest.approx((0.04 + 0 + 1.0) / 3)
    assert a["share_within_tol"] == pytest.approx(2 / 3) and a["max_abs_diff"] == pytest.approx(1.0)


def test_pipeline_check_sees_a_foul_tip_definition_gap():
    """If Savant's whiff% is built with foul tips, my with-foul-tips rate matches it and the rate without them does not."""
    rng = np.random.default_rng(0)
    rows, sv, table = [], [], []
    for pid in range(1, 41):
        n_ss, n_ft, n_other = int(rng.integers(20, 40)), int(rng.integers(3, 9)), int(rng.integers(60, 90))
        rows += [{"pitcher": pid, "pitch_type": "FF", "description": d, "miss_distance": np.nan}
                 for d in ["swinging_strike"] * n_ss + ["foul_tip"] * n_ft + ["foul"] * n_other]
        whiff = 100 * (n_ss + n_ft) / (n_ss + n_ft + n_other)
        sv.append((pid, "FF", round(whiff, 1), 0.0, 1.0))
        table.append((pid, "FF", n_ss + n_ft + n_other, whiff, whiff))
    out = sb.pipeline_check(_table(table), _savant(sv), sb.raw_counts(pd.DataFrame(rows)))
    assert out["pitch_files_vs_savant"]["mean_abs_diff"] <= 0.05 and out["pitch_files_vs_savant"]["share_within_tol"] == 1.0
    assert out["pitch_files_without_foul_tips_vs_savant"]["mean_abs_diff"] > 2
    assert out["off_by_more_than_1_point"] == 0


def test_pitcher_draws_keep_a_pitchers_rows_together():
    pitchers = np.array([1, 1, 1, 2, 3, 3])
    for idx in sb.pitcher_draws(pitchers, 50, seed=1):
        drawn = pitchers[idx]
        for pid, size in ((1, 3), (2, 1), (3, 2)):
            assert (drawn == pid).sum() % size == 0   # whole pitchers only
    a = [i.tolist() for i in sb.pitcher_draws(pitchers, 3, seed=5)]
    assert a == [i.tolist() for i in sb.pitcher_draws(pitchers, 3, seed=5)]   # same seed, same draws


def test_within_type_correlation_removes_a_pure_pitch_type_effect():
    """Two columns that share only a pitch-type level correlate strongly together and not at all within type."""
    rng = np.random.default_rng(2)
    n = 600
    types = rng.choice(["FF", "SL", "CH"], n)
    level = pd.Series(types).map({"FF": 0.0, "SL": 10.0, "CH": 5.0}).to_numpy()
    f = pd.DataFrame({"pitcher": rng.integers(1, 200, n), "sv_type": types, "a": level + rng.normal(0, 1, n), "b": level + rng.normal(0, 1, n)})
    raw, inside = sb.corr_row(f, "a", "b", None, 300, 1), sb.corr_row(f, "a", "b", ["sv_type"], 300, 1)
    assert raw["r"] > 0.9 and raw["lo"] <= raw["r"] <= raw["hi"]
    assert inside["lo"] < 0 < inside["hi"] and abs(inside["r"]) < 0.1
    assert raw["n"] == n and raw["pitchers"] == f["pitcher"].nunique()


def test_center_removes_group_means():
    out = sb.center(np.array([1.0, 3.0, 10.0, 20.0]), np.array([0, 0, 1, 1]))
    assert out.tolist() == [-1.0, 1.0, -5.0, 5.0]


def _pair(n, seed, driver):
    """A fictional pair of seasons. `driver` is the column next season's whiff rate truly follows."""
    rng = np.random.default_rng(seed)
    types = rng.choice(["FF", "SL"], n)
    x = rng.normal(25, 5, n)
    miss = rng.normal(3, 1, n)
    last = rng.normal(25, 6, n)
    signal = {"x": x, "miss": 25 + 5 * (miss - 3), "neither": np.full(n, 25.0)}[driver]
    return pd.DataFrame({"pitcher": rng.integers(1, n // 2, n), "sv_type": types, "swings_prev": rng.integers(60, 400, n),
                         "swings_curr": rng.integers(60, 400, n), "whiff_pct_prev": last, "x_whiff_pct_prev": x, "sv_miss_in_prev": miss,
                         "whiff_pct_curr": signal + rng.normal(0, 2, n)})


def test_next_season_picks_the_measure_that_carries_the_signal():
    for driver, winner in (("x", "expected"), ("miss", "miss")):
        res = sb.next_season(_pair(500, 1, driver), _pair(500, 2, driver), n_boot=300, seed=3)
        assert sb.verdict(res) == winner
        loser = "miss" if winner == "expected" else "expected"
        assert res["models"][winner]["rmse"] < res["models"][loser]["rmse"]
        assert res["models"][winner]["rmse"] == pytest.approx(2.0, abs=0.25)   # the noise that was put in
    res = sb.next_season(_pair(500, 1, "neither"), _pair(500, 2, "neither"), n_boot=300, seed=3)
    assert sb.verdict(res) == "tie"


def test_next_season_baseline_and_gain_arithmetic():
    res = sb.next_season(_pair(400, 4, "x"), _pair(400, 5, "x"), n_boot=200, seed=3)
    m = res["models"]
    assert m["last_whiff"]["gain_vs_baseline_pct"] == 0 and (m["last_whiff"]["gain_lo"], m["last_whiff"]["gain_hi"]) == (0, 0)
    for name, row in m.items():
        assert row["gain_vs_baseline_pct"] == pytest.approx(100 * (1 - row["rmse"] / m["last_whiff"]["rmse"]))
    c = res["contrasts"]["expected minus miss"]
    assert c["rmse_diff"] == pytest.approx(m["expected"]["rmse"] - m["miss"]["rmse"]) and c["lo"] <= c["rmse_diff"] <= c["hi"]
    assert res["train_pitches"] == 400 and res["test_pitches"] == 400


def test_weights_never_see_the_test_outcomes():
    train, test = _pair(300, 6, "x"), _pair(300, 7, "x")
    a = sb.next_season(train, test, n_boot=20, seed=1)
    b = sb.next_season(train, test.assign(whiff_pct_curr=test["whiff_pct_curr"] + 50), n_boot=20, seed=1)
    for name in sb.MODELS:
        assert a["models"][name]["weights"] == b["models"][name]["weights"]
    assert b["models"]["expected"]["rmse"] > a["models"]["expected"]["rmse"] + 40


def test_fit_matches_validate_holdout_on_the_published_blend():
    """`last+expected` here is the blend in stuff.validate_holdout(): same weights, same weighted RMSE."""
    from baseball.edge import stuff

    def tables(seed):
        f = _pair(300, seed, "x").drop_duplicates("pitcher")
        prev = f.rename(columns={"sv_type": "pitch_type", "swings_prev": "swings", "whiff_pct_prev": "whiff_pct", "x_whiff_pct_prev": "x_whiff_pct"})
        curr = f.rename(columns={"sv_type": "pitch_type", "swings_curr": "swings", "whiff_pct_curr": "whiff_pct"}).assign(x_whiff_pct=0.0)
        keep = ["pitcher", "pitch_type", "swings", "whiff_pct", "x_whiff_pct"]
        return f, prev[keep], curr[keep]

    (ftr, p0, c0), (fte, p1, c1) = tables(8), tables(9)
    h = stuff.validate_holdout(p0, c0, p1, c1, n_boot=10)
    res = sb.next_season(ftr, fte, n_boot=10, seed=1)
    assert res["models"]["last+expected"]["rmse"] == pytest.approx(h["rmse_blend"])
    assert res["models"]["last_whiff"]["rmse"] == pytest.approx(h["rmse_regressed_baseline"])
    assert res["rmse_raw_last_season"] == pytest.approx(h["rmse_raw_last_season"])
    assert res["models"]["last+expected"]["weights"]["x_whiff_pct_prev"] == pytest.approx(h["blend"]["x_whiff"])


def test_pair_keeps_one_set_of_pitches_for_every_model():
    prev = _table([(1, "FF", 100, 20.0, 19.0), (2, "FF", 100, 22.0, 21.0), (3, "SL", 100, 35.0, 30.0), (4, "KC", 90, 30.0, 31.0)])
    curr = _table([(1, "FF", 100, 21.0, 0.0), (2, "FF", 40, 23.0, 0.0), (3, "SL", 100, 33.0, 0.0), (4, "CU", 90, 29.0, 0.0)])
    s = _savant([(1, "FF", 20.0, 0.1, 1.1), (2, "FF", 22.0, 0.1, 1.0), (3, "SL", 35.0, 0.1, np.nan), (4, "CU", 30.0, 0.1, 4.4)])
    m = sb.pair(prev, curr, s)
    # 2 is under the floor next season; 3 has no miss distance; 4's curve is a KC one year and a CU the next, the same Savant row
    assert sorted(m["pitcher"]) == [1, 4]
    assert m.set_index("pitcher").loc[4, ["whiff_pct_prev", "whiff_pct_curr", "sv_miss_in_prev"]].tolist() == [30.0, 29.0, 4.4]


class _Reply:
    def __init__(self, status, text):
        self.status_code, self.text = status, text


def test_pull_saves_a_csv_once_and_stops_on_a_refusal(tmp_path, monkeypatch):
    import requests

    monkeypatch.setattr(sb, "SAVANT_DIR", tmp_path)
    calls = []

    def ok(url, **kw):
        calls.append(url)
        return _Reply(200, '"player_id","pitch_type"\n1,"FF"\n2,"SL"\n')

    monkeypatch.setattr(requests, "get", ok)
    manifest = sb.pull([2025], pause=0, log=lambda *_: None)
    assert len(calls) == 2 and all("csv=true" in u and "2025" in u for u in calls)
    assert manifest["savant_arsenal_2025.csv"]["rows"] == 2 and manifest["savant_arsenal_2025.csv"]["url"] == calls[0]
    sb.pull([2025], pause=0, log=lambda *_: None)
    assert len(calls) == 2   # files on disk are not requested again

    def refused(url, **kw):
        calls.append(url)
        return _Reply(403, "<html>Forbidden</html>")

    monkeypatch.setattr(requests, "get", refused)
    with pytest.raises(RuntimeError, match="status 403 for https://baseballsavant.mlb.com/leaderboard/pitch-arsenal-stats"):
        sb.pull([2024], pause=0, log=lambda *_: None)
    assert len(calls) == 3 and not (tmp_path / "savant_arsenal_2024.csv").exists()   # one try, nothing saved, no second URL


def test_load_savant_reads_both_files_into_one_row_per_pitch(tmp_path, monkeypatch):
    monkeypatch.setattr(sb, "SAVANT_DIR", tmp_path)
    (tmp_path / "savant_arsenal_2025.csv").write_text(
        '"last_name, first_name","player_id","pitch_type","run_value_per_100","pitches","whiff_percent","put_away","est_woba"\n'
        '"Example, Fictional",11,"FF",0.6,"900",22.4,18.0,"0.310"\n"Example, Fictional",11,"EP",0.0,"60",5.0,2.0,"0.400"\n')
    (tmp_path / "savant_miss_2025.csv").write_text('"id","name","api_pitch_type","miss_distance","n_swings"\n11,"Example, Fictional","FF","1.25",410\n')
    s = sb.load_savant(2025)
    assert len(s) == 1   # the eephus is not a type I match on
    r = s.iloc[0]
    assert (r["pitcher"], r["pitch_type"], r["sv_whiff_pct"], r["sv_rv100"], r["sv_miss_in"], r["sv_swings"]) == (11, "FF", 22.4, 0.6, 1.25, 410)
