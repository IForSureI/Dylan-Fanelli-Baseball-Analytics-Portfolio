"""Trade graph: tenure value, repairs, de-duplication, trade trees and the pair model (fictional rows)."""
import numpy as np
import pandas as pd
import pytest

from baseball.roster import trades as tg

A, B, C = 108, 109, 110          # three real club ids so the MLB-club filter keeps them; the rows are fictional


def test_tenure_value_rules():
    seasons = {2014: {B: 1.0}, 2015: {A: 2.0}, 2017: {A: 3.5}, 2018: {C: 4.0}, 2019: {A: 9.0}}
    # Trade in November 2014: counts from 2015. 2016 has no MLB time (skipped), 2018 only elsewhere (ends it).
    assert tg.tenure_value(seasons, A, "2014-11-20", 2026) == (5.5, [2015, 2017])
    # Mid-season trade: the first season adds the new club's stint even though he also played for B that year.
    assert tg.tenure_value({2014: {B: 1.0, A: 0.5}, 2015: {B: 2.0}}, A, "2014-07-30", 2026) == (0.5, [2014])
    # First season with no stint for the new club doesn't end the tenure (hurt after the deadline deal).
    assert tg.tenure_value({2014: {B: 1.0}, 2015: {A: 2.0}}, A, "2014-07-30", 2026) == (2.0, [2015])
    # Never reached the majors: no value, no seasons.
    assert tg.tenure_value({}, A, "2020-07-01", 2026) == (0.0, [])


def test_club_before():
    last = {2019: B, 2020: C}
    assert tg.club_before(last, "2020-12-08") == C        # offseason: the season just ended
    assert tg.club_before(last, "2020-02-10") == B        # before May: the previous season
    assert tg.club_before({}, "2020-02-10") is None


def _row(tid, date, pid, frm, to, name="X"):
    r = {"id": tid, "date": date, "description": "d", "typeCode": "TR", "person": {"id": pid, "fullName": name}}
    if frm:
        r["fromTeam"] = {"id": frm}
    if to:
        r["toTeam"] = {"id": to}
    return r


def test_parse_repairs_dedupes_and_drops_non_mlb():
    feed = [
        _row(1, "2020-12-08", 11, None, A),               # blank sending club: repaired from his last stint (B)
        _row(2, "2020-12-08", 11, B, A),                  # same move filed again in a fuller record
        _row(2, "2020-12-08", 12, A, B),
        _row(3, "2021-03-01", 13, A, 999),                # to a non-MLB club: dropped, and the trade with it
    ]
    trades, legs = tg.parse_trades(feed, {11: {2020: B}})
    assert set(trades) == {2}                             # trade 1's only move was a duplicate of trade 2's
    assert sorted((l["player_id"], l["from_id"], l["to_id"]) for l in legs) == [(11, B, A), (12, A, B)]


def test_patches_add_missing_legs():
    feed = [_row(5, "2021-01-07", 21, A, B)]
    patch = {"5": {"trade": "fixed", "legs": [{"player_id": 22, "player_name": "Y", "from_id": B, "to_id": A}]}}
    trades, legs = tg.parse_trades(feed, {}, patch)
    assert trades[5]["record_repaired"] and trades[5]["description"] == "fixed"
    assert len(legs) == 2


def test_tree_value_follows_flips():
    # A gets P1 from B in trade 1. A flips P1 and P2 to C in trade 2 for P3. A flips P3 to B in trade 3 for P4.
    legs = [
        {"trade_id": 1, "date": "2015-01-01", "player_id": 1, "player_name": "P1", "from_id": B, "to_id": A, "war_for_acquirer": 2.0},
        {"trade_id": 2, "date": "2016-01-01", "player_id": 1, "player_name": "P1", "from_id": A, "to_id": C, "war_for_acquirer": 1.0},
        {"trade_id": 2, "date": "2016-01-01", "player_id": 2, "player_name": "P2", "from_id": A, "to_id": C, "war_for_acquirer": 0.0},
        {"trade_id": 2, "date": "2016-01-01", "player_id": 3, "player_name": "P3", "from_id": C, "to_id": A, "war_for_acquirer": 6.0},
        {"trade_id": 3, "date": "2018-01-01", "player_id": 3, "player_name": "P3", "from_id": A, "to_id": B, "war_for_acquirer": 1.5},
        {"trade_id": 3, "date": "2018-01-01", "player_id": 4, "player_name": "P4", "from_id": B, "to_id": A, "war_for_acquirer": 4.0},
    ]
    links = tg.tree_links(legs)
    assert {(k["from_trade"], k["to_trade"], k["team_id"]) for k in links} == {(1, 2, A), (2, 3, A)}
    side = {(s["trade_id"], s["team_id"]): s for s in tg.sides_table(legs, links)}
    # Trade 3 for A: 4.0 received. Trade 2 for A: 6.0 + 4.0 (P3 was the only player A sent in trade 3) = 10.0.
    # Trade 1 for A: 2.0 + 10.0 / 2 (A sent two players in trade 2, one of them from this tree) = 7.0.
    assert side[(3, A)]["tree_war_received"] == 4.0
    assert side[(2, A)]["tree_war_received"] == 10.0
    assert side[(1, A)]["tree_war_received"] == 7.0
    assert side[(2, A)]["net_war"] == 6.0 - 1.0        # got P3 (6.0), gave P1 (1.0 for C) and P2 (0.0)


def test_expected_pairs_rows_sum_to_activity():
    D = 111
    e = tg.expected_pairs(pd.Series({A: 40, B: 30, C: 20, D: 10}))
    assert e.sum(axis=1).tolist() == pytest.approx([40, 30, 20, 10], abs=1e-6)
    assert e.loc[A, B] == pytest.approx(e.loc[B, A])
    assert (e.values.diagonal() == 0).all()
    # Four equally active clubs: 30 trades each spread evenly over the other three.
    eq = tg.expected_pairs(pd.Series({A: 30, B: 30, C: 30, D: 30}))
    assert eq.loc[A, B] == pytest.approx(10, abs=1e-6)


def test_compare_rate_ratios():
    # Hand check: log(0.733 / 0.492) = 0.399; SE = sqrt(1/127 + 1/85) = 0.140; z = 2.85; two-sided p = 0.0044.
    ratio, p = tg.compare_rate_ratios(127, 0.733, 85, 0.492)
    assert ratio == pytest.approx(1.490, abs=1e-3)
    assert p == pytest.approx(0.0044, abs=2e-4)
    assert tg.compare_rate_ratios(100, 0.8, 100, 0.8) == (pytest.approx(1.0), pytest.approx(1.0))


def test_pair_kinds():
    sides = pd.DataFrame({"trade_id": [1, 1, 2, 2, 3, 3], "team_id": [147, 111, 147, 108, 147, 119]})
    p = tg._pairs_in(sides, [1, 2, 3]).set_index("pair")
    assert p.loc["BOS-NYY", "kind"] == "same division" and p.loc["BOS-NYY", "division"] == "AL East"
    assert p.loc["LAA-NYY", "kind"] == "same league"
    assert p.loc["LAD-NYY", "kind"] == "interleague"
    assert p.observed.sum() == 3


def test_garwood_interval():
    # Hand check: chi2.ppf(0.025, 56) / 2 = 18.61 and chi2.ppf(0.975, 58) / 2 = 40.47 for 28 events.
    lo, hi = tg.garwood(28)
    assert (round(lo, 2), round(hi, 2)) == (18.61, 40.47)
    assert tg.garwood(0)[0] == 0.0 and tg.garwood(0)[1] == pytest.approx(3.689, abs=1e-3)


def test_poisson_glm_recovers_a_known_rate_ratio():
    # Expected counts exactly exp(X b): the fit returns b, and dispersion is 0 (no noise).
    X = np.array([[1, 0], [1, 1], [1, 0], [1, 1]], float)
    y = np.exp(X @ np.array([np.log(10.0), np.log(0.5)]))
    b, se, phi = tg.poisson_glm(y, X)
    assert np.exp(b) == pytest.approx([10.0, 0.5], rel=1e-8)
    assert phi == pytest.approx(0.0, abs=1e-12)


def test_side_gap_baseline_and_burst_scan(tmp_path):
    # Fictional graph: 4 clubs, two-club trades. Every trade nets exactly 1 WAR to one side.
    ids = range(1, 41)
    trades = pd.DataFrame({"trade_id": list(ids), "date": pd.date_range("2021-01-01", periods=40, freq="30D").strftime("%Y-%m-%d"),
                           "n_teams": 2})
    clubs = [(108, 144)] * 16 + [(109, 110), (110, 111), (109, 111), (108, 110)] * 6
    sides = pd.DataFrame([{"trade_id": t, "team_id": c, "net_war": 1.0 if k == 0 else -1.0}
                          for t, pair in zip(ids, clubs) for k, c in enumerate(pair)])
    trades.to_csv(tmp_path / "trades.csv", index=False)
    sides.to_csv(tmp_path / "sides.csv", index=False)
    # 13 trades with +-1 each: |sum| >= 13 only when all 13 signs agree, 2 / 2^13.
    assert tg.side_gap_baseline(tmp_path, "2021-01-01", "2030-01-01", n=13, observed_gap=13, draws=200000) == pytest.approx(2 / 2 ** 13, abs=2e-4)
    scan = tg.burst_scan(tmp_path, years=1.0, step_months=3)
    assert scan.iloc[0].pair == "LAA-ATL"                # the pair that made 16 of 40 trades leads


def test_retrosheet_check(tmp_path):
    # Fictional Retrosheet rows: date, time, approx, date2, approx2, id, player, type, from, lg, to, lg, ...
    rows = [
        '"20070809",,,,,1,"aaaa001","T","LAN","NL","SFN","NL",,,,',
        '"20070825",,,,,2,"bbbb001","T","SFN","NL","LAN","NL",,,,',
        '"20040604",,,,,3,"cccc001","C","CLE","AL","KCA","AL",,,,',
        '"20031106",,,,,4,"dddd001","T","KCA","AL","CLE","AL",,,,',
        '"20121219",,,,,5,"eeee001","T","ANA","AL","SEA","AL",,,,',
        '"20100301",,,,,6,"ffff001","T","NYA","AL","BOS","AL",,,,',
        '"20100302",,,,,7,"gggg001","F","","","NYA","AL",,,,',     # free-agent signing: ignored
    ]
    (tmp_path / "tran.txt").write_text("\n".join(rows))
    pd.DataFrame({"trade_id": [1, 2, 3], "season": [2010, 2010, 2012], "n_teams": 2}).to_csv(tmp_path / "trades.csv", index=False)
    r = tg.retrosheet_check(tmp_path / "tran.txt", tmp_path, pairs=("LAD-SFG", "CLE-KCR", "LAA-SEA"))
    last = r["last_before_2009"]
    assert str(last.loc["LAD-SFG", "T"].date()) == "2007-08-25"
    assert str(last.loc["CLE-KCR", "C"].date()) == "2004-06-04" and str(last.loc["CLE-KCR", "T"].date()) == "2003-11-06"
    assert [str(d) for d in r["since_2009"].loc["LAA-SEA", "deals"]] == ["2012-12-19"]
    assert r["coverage"].set_index("season").loc[2010, "ratio"] == 2.0     # 2 feed trades, 1 Retrosheet trade
