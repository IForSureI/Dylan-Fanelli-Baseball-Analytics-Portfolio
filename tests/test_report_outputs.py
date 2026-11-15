"""The headline numbers in three reports, checked against the small saved tables in reports/outputs/.
If a report and its table disagree, one of them is stale."""
import json
from pathlib import Path

import pytest
from scipy.stats import t as tdist

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "outputs"


def _load(name):
    return json.loads((OUT / name).read_text())


def _text(name):
    return (ROOT / "reports" / name).read_text()


def test_bullpen_memo_matches_its_saved_table():
    b, memo = _load("bullpen-2026.json"), _text("2026-bullpen-acquisition-memo.md")
    line, p = b["line"], b["price"]["670970"]["comps_way"]
    assert line["n"] == 21 and "21 relief signings" in memo
    # expected price and its 95% prediction interval: $18.4M, $7.4M to $29.3M
    assert f"${p['aav']:.1f}M a year" in memo
    assert f"${p['lo']:.1f}M to ${p['hi']:.1f}M" in memo
    # landing odds are the line's t distribution (n - 2 df) at the walk-away AAV: 26% at $15.0M, 47% at $18.0M
    odds = lambda aav: 100 * tdist.cdf((aav - p["aav"]) / p["sd_pred"], line["n"] - 2)
    assert round(odds(15.0)) == 26 and "about 26% of the time (47% at $72M)" in memo
    assert round(odds(18.0)) == 47
    assert odds(18.0) / 100 == pytest.approx(b["landing"][2]["chance_price_at_or_below"], abs=1e-3)
    # the qualifying-offer cost and the walk-away it implies: 18.1 - 10.59 spread over four discounted years
    assert b["qo"]["670970"]["total_value"] == pytest.approx(10.59) and "about $10.6M" in memo
    annuity4 = sum(1 / 1.10 ** t for t in range(4))
    assert 4 * (b["breakeven"]["(670970, 4)"]["market"] - 10.59 / annuity4) == pytest.approx(60.2, abs=0.1)
    # workload retention and the availability case
    r, a = b["retention"], b["availability_case"]["(670970, 4)"]
    assert r["n"] == 170 and f"kept {100 * r['one_season']:.0f}% of that workload in 2025 and {100 * r['two_seasons']:.0f}% in 2026" in memo
    # the yearly step is the second season over the first: 0.475 / 0.628 = 0.756
    assert r["step"] == pytest.approx(r["two_seasons"] / r["one_season"], abs=0.001) and "0.76 of the first" in memo
    assert f"${a['total']:.1f}M" in memo and f"${a['breakeven_aav']:.1f}M" in memo


def test_edge_board_matches_its_saved_table():
    e, board = _load("edge-2026.json"), _text("2026-edge-board.md")
    g = e["gap_persistence"]
    assert f"r = {g['2024->2025']['r_gap']:.2f}" in board and f"and {g['2025->2026']['r_gap']:.2f} (2025" in board
    two = e["projection_two_year"]
    loo = two["loo_rmse"]
    assert f"RMSE {loo['two_seasons_plus_expected']:.2f} vs. {loo['last_season']:.2f} on {two['matched_pitches']} pitches" in board
    assert 100 * (1 - loo["two_seasons_plus_expected"] / loo["last_season"]) == pytest.approx(two["gain_vs_last_season_pct"], abs=0.01)
    assert f"{two['gain_vs_last_season_pct']:.1f}% against a regressed" in board
    h = e["holdout_fit_2024_25_scored_2025_26"]
    assert 100 * (1 - h["rmse_blend"] / h["rmse_regressed_baseline"]) == pytest.approx(h["gain_pct"], abs=0.01)
    assert f"cut error {h['gain_pct']:.1f}%" in board
    assert f"RMSE {h['rmse_blend']:.2f} vs. {h['rmse_regressed_baseline']:.2f}; 95% interval {h['gain_pct_lo']:.1f}% to {h['gain_pct_hi']:.1f}%" in board
    assert h["rmse_blend"] < h["rmse_regressed_baseline"] < h["rmse_raw_last_season"]
    assert f"{e['stuff_model_auc']['2026']:.3f}" in board and f"{e['portable_model']['auc']:.3f}" in board
    t = e["tell_cost_pooled"]
    assert f"+{t['raw']['slope']:.2f} whiff points" in board and f"+{t['controlled']['slope']:.2f} (" in board
    s = e["shifts_rebuilt_from_saved_table"]
    assert f"{s['candidates']} in 2026, by {s['pitchers']} pitchers" in board and f"{s['whiff_change_p_below_05']} ({100 * s['whiff_change_p_below_05'] / s['candidates']:.1f}%)" in board
    assert s["whiff_change_q_below_05"] == 0 and f"{s['whiff_change_q_below_10']} clear 10%" in board


def test_familiarity_report_matches_its_saved_table():
    f, rep = _load("familiarity-2024-26.json"), _text("2026-league-pitch-familiarity.md")
    main = {r["group"]: r for r in f["coefficients"] if r["outcome"].startswith("whiff") and r["term"] == "prev: same - other"}
    fb, br, off = (abs(main[k]["coef"]) for k in ("fastball", "breaking", "offspeed"))
    assert f"{fb:.2f} points on fastballs, {br:.2f} on breaking balls and {off:.2f} on changeups and splitters" in rep
    assert all(main[k]["p"] < 0.001 for k in ("fastball", "breaking", "offspeed"))
    assert f"{f['sample']['pitches']:,} pitches" in rep and f"{f['sample']['games']:,} games" in rep
