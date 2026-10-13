"""Reliever acquisition pricing: hand-checked arithmetic on FICTIONAL pitchers and signings.

Every pitcher and contract here is fictional (ids 1-9) except the rule tables the functions call, which are the
2022-26 agreement's (sources in baseball/roster/money.py). The arithmetic is in the comments.
"""
import pandas as pd
import pytest

from baseball.roster import acquisition as A


def test_replacement_level_is_pitch_weighted_fringe_run_value():
    rs = pd.DataFrame({"pitcher": [1, 2, 3], "season": 2026, "pitches": [100, 300, 500], "rv": [-2.0, -1.0, 3.0]})
    # Fringe = 50-399 pitches: pitchers 1 and 2. 100 x (-2 - 1) / 400 = -0.75 runs per 100 pitches
    assert A.replacement_level(rs) == pytest.approx(-0.75)


def test_project_relief_war_by_hand():
    # FICTIONAL reliever: 2026 1,000 relief pitches, +10 runs; 2025 800 pitches, +4 runs. Weights 5/4.
    rs = pd.DataFrame({"pitcher": [1, 1], "season": [2026, 2025], "pitches": [1000, 800], "rv": [10.0, 4.0]})
    p = A.project_relief_war(rs, 1, 2026, league_mean=0.0, replacement=-0.7, n_seasons=2, li=1.6)
    # Weighted: (5 x 10 + 4 x 4) / (5 x 1000 + 4 x 800) = 66 / 8200 -> 0.804878 per 100
    assert p.observed_rv100 == pytest.approx(100 * 66 / 8200)
    # Effective n = 8200 / 5 = 1640; weight 1640 / (1640 + 1932.2) = 0.459101; estimate 0.369517
    assert p.weight == pytest.approx(1640 / 3572.2) and p.rv100 == pytest.approx(0.804878 * 1640 / 3572.2, abs=1e-5)
    # Pitches: (5 x 1000 + 4 x 800) / 9 = 911.11; wins (0.369517 + 0.7) x 9.1111 / 10 = 0.97445
    assert p.pitches == pytest.approx(8200 / 9)
    assert p.war_neutral == pytest.approx(0.97445, abs=1e-4)
    # Role: x (1 + 1.6) / 2 = 1.3 -> 1.26679
    assert p.war_role == pytest.approx(0.97445 * 1.3, abs=1e-4)


def test_market_line_recovers_an_exact_line():
    comps = pd.DataFrame({"war_neutral": [0.5, 1.0, 1.5], "aav": [6.0, 11.0, 16.0]})     # AAV = 1 + 10 x WAR
    m = A.market_line(comps)
    assert m["intercept"] == pytest.approx(1.0) and m["slope"] == pytest.approx(10.0) and m["resid_sd"] == pytest.approx(0.0, abs=1e-9)
    # $ per win: 12, 11, 10.667 -> median 11
    assert m["median_aav_per_war"] == pytest.approx(11.0)
    assert A.market_aav(1.2, m) == pytest.approx(13.0)


def test_war_path_declines_from_31():
    assert A.war_path(1.0, 33, 3) == pytest.approx([0.9, 0.81, 0.729])          # every season at 31+
    assert A.war_path(1.0, 28, 5) == pytest.approx([1.0, 1.0, 1.0, 0.9, 0.81])   # ages 28, 29, 30, 31, 32


LINE = {"intercept": 1.0, "slope": 10.0}


def test_contract_value_one_year():
    # 1 year at $5M, role 1.5 wins, neutral 1.0, age 28, 2026 (the engine's base season: no growth)
    v = A.contract_value(5.0, 1, 1.5, 1.0, 28, 2026, LINE)
    assert v["pv_value_market"] == pytest.approx(11.0)                 # 1 + 10 x 1.0
    assert v["pv_value_engine"] == pytest.approx(1.5 * 8.51)           # 1-2 WAR tier, $8.51M per win
    assert v["surplus_market"] == pytest.approx(6.0) and v["surplus_engine"] == pytest.approx(12.765 - 5.0)


def test_breakeven_aav_two_years():
    # Market value 11 then 11 x 1.03 = 11.33; PV = 11 + 11.33 / 1.1 = 21.3; annuity 1 + 1 / 1.1 = 1.909091 -> 11.15714
    assert A.breakeven_aav(2, 1.5, 1.0, 28, 2026, LINE, basis="market") == pytest.approx(21.3 / (1 + 1 / 1.1))
    # One year: break-even equals the year's value
    assert A.breakeven_aav(1, 1.5, 1.0, 28, 2026, LINE, basis="engine") == pytest.approx(12.765)


def test_qo_cost_for_a_club_neither_payor_nor_recipient():
    q = A.qo_cost("other", "payor", 64.0, 55)
    # Signing club "other": its 2nd-highest pick and $0.5M of pool; the payor losing him gets a pick after Round 4
    assert q["signing_club_forfeits_picks"] == ["2nd-highest"] and q["signing_club_forfeits_pool"] == 0.5
    assert q["losing_club_gets"] == "pick after Round 4"
    assert q["pick_value_2019_dollars"] == 5.3 and q["total_value"] == pytest.approx(5.8)   # Edwards (2019), pick 55


def test_tax_table_first_time_payor():
    t = A.tax_table([235.0, 244.0, 200.0], 12.0, threshold=244.0).set_index("payroll_before")
    assert t.loc[235.0, "added_tax"] == pytest.approx(0.6)            # 3 over x 20%
    assert t.loc[244.0, "added_tax"] == pytest.approx(2.4)            # 12 over x 20%
    assert t.loc[200.0, "added_tax"] == 0.0 and t.loc[200.0, "all_in_cost"] == 12.0
