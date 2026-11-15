"""The permutation null for the pitch-change detector, on fictional seasons."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from baseball.edge import shift_null as sn
from baseball.edge import shifts

ROOT = Path(__file__).resolve().parent.parent


def _season(pitcher=7, sl_step=0.0, sl_ramp=0.0, game_sd=0.0, step_game=10, games=20, seed=3):
    """Fictional RHP, 20 starts, three pitches. Optional: a slider IVB step at one game, a slider IVB
    ramp across the season, or a random per-game offset on every pitch's IVB (no time order)."""
    rng = np.random.default_rng(seed)
    rows = []
    for g in range(games):
        date = str(pd.Timestamp("2025-04-01") + pd.Timedelta(days=5 * g))[:10]
        offset = rng.normal(0, game_sd) if game_sd else 0.0
        for pt, n, velo, ivb in [("FF", 45, 95.0, 16.0), ("SL", 30, 86.0, 2.0), ("CH", 20, 87.0, 7.0)]:
            extra = (sl_step if g >= step_game else 0.0) + sl_ramp * g / (games - 1) if pt == "SL" else 0.0
            for i in range(n):
                rows.append({
                    "pitcher": pitcher, "player_name": "Example, Fictional", "game_year": 2025, "p_throws": "R",
                    "game_pk": 500 + g, "game_date": date, "pitch_type": pt, "pitch_name": pt,
                    "release_speed": velo + rng.normal(0, 0.8), "pfx_z": (ivb + extra + offset + rng.normal(0, 1.5)) / 12,
                    "pfx_x": -0.5 + rng.normal(0, 0.1), "release_spin_rate": 2300 + rng.normal(0, 50),
                    "arm_angle": 45 + rng.normal(0, 2), "description": "swinging_strike" if i % 3 == 0 else "ball",
                    "type": "S", "estimated_woba_using_speedangle": np.nan,
                })
    return pd.DataFrame(rows)


def test_candidates_filter_keeps_one_row_per_pitch_on_the_largest_t():
    base = {"pitcher": 1, "pitch_type": "SL", "scope": "this pitch only", "label_check": "ok",
            "metric": "velocity (mph)", "swings_before": 50, "swings_after": 50, "t": 7.0}
    rows = pd.DataFrame([
        base,
        {**base, "metric": "spin (rpm)", "t": -9.0},                       # same pitch, larger |t|: this one is kept
        {**base, "pitch_type": "CH", "scope": "all pitches"},              # whole arsenal moved
        {**base, "pitch_type": "CU", "label_check": "possible relabel from SL"},
        {**base, "pitch_type": "FF", "swings_after": 39},                  # too few swings after
        {**base, "pitch_type": "SI", "metric": "arm angle (deg)"},         # arm angle is left out
    ])
    c = shifts.candidates(rows)
    assert len(c) == 1 and c.loc[0, "metric"] == "spin (rpm)"


def test_planted_step_is_found_and_the_null_finds_about_zero():
    prepared = sn.prepare(_season(sl_step=-4.0))
    real = shifts.candidates(sn.detect(prepared))
    assert list(real["pitch_type"]) == ["SL"] and real.loc[0, "split_date"] == "2025-05-21"
    null = sn.permutation_null(prepared, n=25, seed=1, real=real)
    # A shuffled step leaves two clumps of games, and the split search sometimes lines them up by chance.
    # So a pitch with a real change adds to the null now and then, far less often than the real order does.
    assert null["candidates"].mean() < 0.5
    assert null["candidates_on_real_list"].equals(null["candidates"])   # every such hit is the changed pitch


def test_unchanged_series_gives_about_zero_real_and_shuffled():
    prepared = sn.prepare(pd.concat([_season(pitcher=p, seed=p) for p in (11, 12, 13)]))
    assert sn.detect(prepared).empty
    assert sn.permutation_null(prepared, n=25, seed=2)["candidates"].sum() == 0


def test_screened_run_matches_the_plain_detector_on_shuffled_seasons():
    # per-game offsets with no time order: the kind of series the detector can fire on by chance
    season = pd.concat([_season(pitcher=p, seed=p, game_sd=1.2) for p in range(20, 28)])
    prepared = sn.prepare(season)
    hits = 0
    for i in range(4):
        fast = sn.detect(prepared, np.random.default_rng([5, i]))
        slow = sn.detect(prepared, np.random.default_rng([5, i]), screen=False)
        assert len(fast) == len(slow)
        if len(fast):
            key = ["pitcher", "pitch_type", "metric"]
            pd.testing.assert_frame_equal(fast.sort_values(key).reset_index(drop=True), slow.sort_values(key).reset_index(drop=True))
        hits += len(fast)
    assert hits > 0                                  # the comparison saw real detections, not two empty frames


def test_real_order_run_matches_league_shifts():
    season = pd.concat([_season(pitcher=30, sl_step=-4.0), _season(pitcher=31, seed=8)])
    plain = shifts.league_shifts(season)
    plain = plain[plain["metric"].isin(shifts.CANDIDATE_METRICS)].reset_index(drop=True)
    pd.testing.assert_frame_equal(sn.detect(sn.prepare(season)), plain, check_dtype=False)


def test_shuffle_moves_whole_games_and_keeps_pitch_types_together(monkeypatch):
    season = _season()
    seen = {}
    monkeypatch.setattr(sn, "_passes_screen", lambda s, perm: True)
    monkeypatch.setattr(shifts, "pitcher_shifts", lambda p: seen.setdefault("p", p) is None or pd.DataFrame())
    sn.detect(sn.prepare(season), np.random.default_rng(4))
    shuffled = seen["p"]
    assert (shuffled["game_pk"].to_numpy() != season["game_pk"].to_numpy()).any()        # the order did change
    # every original game lands in exactly one slot, with all of its pitches of every type
    pairs = pd.DataFrame({"old": season["game_pk"].to_numpy(), "new": shuffled["game_pk"].to_numpy()}).drop_duplicates()
    assert len(pairs) == season["game_pk"].nunique() == pairs["new"].nunique()
    assert sorted(shuffled["game_pk"].unique()) == sorted(season["game_pk"].unique())
    assert shuffled.groupby("game_pk")["game_date"].nunique().eq(1).all()
    np.testing.assert_array_equal(shuffled["pfx_z"].to_numpy(), season["pfx_z"].to_numpy())


def test_null_is_repeatable_and_does_not_depend_on_worker_count():
    prepared = sn.prepare(pd.concat([_season(pitcher=p, seed=p, game_sd=1.2) for p in range(40, 44)]))
    a = sn.permutation_null(prepared, n=4, seed=9)
    b = sn.permutation_null(prepared, n=4, seed=9, workers=2)
    pd.testing.assert_frame_equal(a, b)
    assert not a.equals(sn.permutation_null(prepared, n=4, seed=10)) or a["detector_rows"].sum() == 0


def test_step_or_trend_tells_a_step_from_a_ramp():
    step = _season(sl_step=-4.0)
    cand = shifts.candidates(shifts.pitcher_shifts(step))
    assert not sn.step_or_trend(step, cand)["line_fits_as_well"].any()
    ramp = _season(sl_ramp=-6.0)
    found = shifts.pitcher_shifts(ramp)                                   # a ramp does trip the detector
    sl = found[(found["pitch_type"] == "SL") & found["metric"].str.startswith("induced")]
    assert len(sl) == 1
    assert sn.step_or_trend(ramp, sl)["line_fits_as_well"].all()


def test_edge_board_quotes_the_saved_null():
    r = json.loads((ROOT / "reports" / "outputs" / "edge-shift-null-2026.json").read_text())
    board = (ROOT / "reports" / "2026-edge-board.md").read_text()
    e = json.loads((ROOT / "reports" / "outputs" / "edge-2026.json").read_text())["shifts_rebuilt_from_saved_table"]
    obs, null = r["observed"], r["null"]
    assert obs["candidates"] == e["candidates"] and obs["pitchers"] == e["pitchers"]
    assert null["candidates_mean"] == pytest.approx(np.mean(null["counts"])) and len(null["counts"]) == r["permutations"]
    assert r["false_share_of_candidates"] == pytest.approx(null["candidates_mean"] / obs["candidates"])
    assert f"about {null['candidates_mean']:.0f} candidates" in board
    assert f"({100 * r['false_share_of_candidates']:.0f}% of the {obs['candidates']})" in board
    assert f"{r['permutations']} shuffled seasons" in board and f"seed {r['seed']}" in board
    assert f"About {null['on_real_list_mean']:.0f} of the {null['candidates_mean']:.0f}" in board
    assert f"{r['pitchers']} pitchers, {r['pitch_series_tested']:,} pitcher-pitch series" in board
    assert f"from {null['candidates_min']} to {null['candidates_max']}" in board
    s = r["step_or_trend"]
    assert f"{s['line_fits_as_well_as_step']} of the {s['candidates']}" in board
