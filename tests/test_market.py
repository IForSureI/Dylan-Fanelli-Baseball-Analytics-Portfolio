"""The 2026-27 market board: parsing MLBTR's calls and signing lines, the backtest numbers the report quotes,
and the frozen calls (dated, never rewritten)."""
import json
import re
from pathlib import Path

import pytest

from baseball.roster import market as mk

ROOT = Path(__file__).resolve().parents[1]


def test_terms_and_signing_lines():
    assert mk.terms("Nine years, $425MM") == (9, 425.0)
    assert mk.terms("One year $23.15MM") == (1, 23.15)
    assert mk.terms("Two years, $40MM (with an opt-out)") == (2, 40.0)
    assert mk.actual_terms("Signed with Mets for nine years, $450MM", 23.15) == (9, 450.0)
    assert mk.actual_terms("Accepted $23.15MM qualifying offer from Twins", 23.15) == (1, 23.15)
    assert mk.actual_terms("", 23.15) == (None, None)


def test_over_probability_is_on_the_grid_and_monotone():
    ps = [mk.over_probability(m, 20.0, 0.30) for m in (10, 15, 20, 25, 40)]
    assert ps == sorted(ps) and ps[2] == 0.5 and ps[0] == 0.05 and ps[-1] == 0.95
    assert all(abs(p * 20 - round(p * 20)) < 1e-9 for p in ps)


def test_both_lists_have_fifty_players_and_sources():
    for season in (2025, 2026):
        data = mk.load(season)
        assert len(data["players"]) == 50 and data["source"].startswith("https://www.mlbtraderumors.com/")
        assert data["pulled"] and data["published"]


def test_backtest_matches_the_report():
    bt = mk.backtest(mk.frame(mk.load(2025)))
    assert bt["n"] == 44
    assert round(bt["mae_mine"], 2) == 3.24 and round(bt["mae_mlbtr"], 2) == 3.79
    assert bt["closer"] == 21 and round(bt["brier"], 3) == 0.218 and round(bt["brier_base"], 3) == 0.231
    assert round(bt["mlbtr_bias"], 1) == -2.0 and round(bt["years_bias"], 1) == 0.8 and round(bt["total_bias"], 1) == 10.6
    assert bt["edge_lo"] < 0 < bt["edge_hi"]           # the report says the edge's range includes zero
    text = (ROOT / "reports" / "2027-market-board.md").read_text()
    for s in ("$3.24M", "$3.79M", "0.218", "0.231", "21 of 44", "$2.0M a year low", "0.8 years long", "$10.6M high"):
        assert s in text, s


def test_frozen_calls():
    data = json.loads((ROOT / "market" / "calls_2026-27.json").read_text())
    assert data["made"] == "2026-11-23"
    called = [c for c in data["calls"] if c["call"] == "called"]
    assert len(data["calls"]) == 50 and len(called) == 38
    assert all(c["my_aav"] > 0 and 0.05 <= c["p_over"] <= 0.95 for c in called)
    assert all(c["my_aav"] is None for c in data["calls"] if c["call"] != "called")
    with pytest.raises(FileExistsError):
        mk.freeze("2026-11-23")


def test_report_board_is_rendered_from_the_calls():
    text = (ROOT / "reports" / "2027-market-board.md").read_text()
    board = text[text.index(mk.MARK_START):text.index(mk.MARK_END)]
    rows = [l for l in board.splitlines() if re.match(r"\| \d+ \|", l)]
    assert len(rows) == 38
    assert board.strip().endswith(mk.render_board().strip().splitlines()[-1].strip())


def test_scoring_rules_edge_cases():
    # clubs outside MLB that share an MLB nickname, minor-league deals and retirements aren't scored
    assert not mk.mlb_deal("Signed with Yomiuri Giants for two years, $10MM")
    assert not mk.mlb_deal("Signed with Hanshin Tigers for one year, $3MM")
    assert not mk.mlb_deal("Signed minor league deal with Twins")
    assert mk.mlb_deal("Signed with the Red Sox for four years, $58MM") and mk.mlb_deal("Accepted $23.15MM qualifying offer from Twins")
    assert mk.actual_terms("Signed with Tigers for one-year, $11.5MM", 23.15) == (1, 11.5)
    # a deal exactly at MLBTR's AAV is not "above", and an equal distance counts for neither side
    import pandas as pd
    s = pd.DataFrame([dict(call="called", actual_aav=16.0, mlbtr_aav=16.0, my_aav=16.0, p_over=0.5, first_seen="2026-12-01"),
                      dict(call="called", actual_aav=20.0, mlbtr_aav=18.0, my_aav=22.0, p_over=0.8, first_seen="2027-05-02")])
    r = mk.score(s)
    assert r["n"] == 1 and r["ties"] == 1 and r["closer"] == 0 and r["mlbtr_closer"] == 0 and r["brier"] == 0.25


def test_every_signed_line_parses():
    assert mk.unparsed(mk.load(2026)["players"]) == []
    assert mk.unparsed([dict(name="X", signed="Signed with Mets for an undisclosed deal")]) == ["X"]
