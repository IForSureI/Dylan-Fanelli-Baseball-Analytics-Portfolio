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
    assert q["pick_value"] == 10.09 and q["total_value"] == pytest.approx(10.59)   # house value at pick 55 + $0.5M pool
    e = A.qo_cost("other", "payor", 64.0, 55, pick_values=A.PICK_VALUE_2019)
    assert e["pick_value"] == 5.3 and e["total_value"] == pytest.approx(5.8)      # Edwards (2019), pick 55


def test_tax_table_first_time_payor():
    t = A.tax_table([235.0, 244.0, 200.0], 12.0, threshold=244.0).set_index("payroll_before")
    assert t.loc[235.0, "added_tax"] == pytest.approx(0.6)            # 3 over x 20%
    assert t.loc[244.0, "added_tax"] == pytest.approx(2.4)            # 12 over x 20%
    assert t.loc[200.0, "added_tax"] == 0.0 and t.loc[200.0, "all_in_cost"] == 12.0


def test_market_price_interval_adds_fit_and_residual_variance():
    # FICTIONAL comps: x = 0, 1, 2, 3; y = 1, 3, 5, 9 -> least squares a = 0.6, b = 2.6; residuals 0.4, -0.2, -0.8, 0.6
    comps = pd.DataFrame({"war_neutral": [0.0, 1.0, 2.0, 3.0], "aav": [1.0, 3.0, 5.0, 9.0]})
    m = A.market_line(comps)
    assert m["intercept"] == pytest.approx(0.6) and m["slope"] == pytest.approx(2.6)
    # s^2 = (0.16 + 0.04 + 0.64 + 0.36) / 2 = 0.6; Sxx = 5, so var(slope) = 0.6 / 5 = 0.12
    assert m["resid_sd"] ** 2 == pytest.approx(0.6) and m["slope_se"] ** 2 == pytest.approx(0.12)
    # At x = 4 (beyond the comps): fit 11.0; var(fit) = 0.6 x (1/4 + (4 - 1.5)^2 / 5) = 0.6 x 1.5 = 0.9;
    # predictive SD = sqrt(0.6 + 0.9) = 1.2247
    pi = A.market_price_interval(4.0, m)
    assert pi["aav"] == pytest.approx(11.0) and pi["se_fit"] ** 2 == pytest.approx(0.9)
    assert pi["sd_pred"] == pytest.approx(1.5 ** 0.5) and pi["extrapolated"]
    # Half the predictive mass sits below the fitted price
    assert A.chance_price_at_or_below(11.0, 4.0, m) == pytest.approx(0.5)


def test_contract_value_with_partial_availability():
    # 2 years, $3M; 1.0 neutral and role win a full season; he pitches 35% of year 1 and all of year 2; age 28
    v = A.contract_value(3.0, 2, 1.0, 1.0, 28, 2026, LINE, availability=[0.35, 1.0])
    # Market: year 1 = 0.35 x (1 + 10 x 1.0) = 3.85; year 2 = 11 x 1.03 = 11.33, discounted 11.33 / 1.1 = 10.3 -> 14.15
    assert v["pv_value_market"] == pytest.approx(3.85 + 10.3)
    # Engine: 0.35 wins at the 0-1 tier ($6.74M) = 2.359; 1.0 win at the 1-2 tier x 1.03 / 1.1
    assert v["pv_value_engine"] == pytest.approx(0.35 * 6.74 + 8.51 * 1.03 / 1.1)


def test_walk_away_with_a_qo_uses_the_house_pick_value():
    from baseball.roster import bullpen_case as B

    m = {"breakeven": {(670970, 4): {"market": 18.1, "market_comps_way": 18.7, "engine": 30.7}},
         "price": {670970: {"comps_way": {"aav": 18.4}}},
         "qo": {670970: A.qo_cost("other", "payor", 64.0, 55)}}
    w = B.walk_away(m)
    annuity4 = 1 + 1 / 1.1 + 1 / 1.1 ** 2 + 1 / 1.1 ** 3          # 3.4869
    # house: $10.09M pick + $0.5M pool = $10.59M of present value -> $3.04M a year off $18.1M
    assert w["qo_value_pv"] == pytest.approx(10.59)
    assert w["walkaway_with_qo_aav"] == pytest.approx(18.1 - 10.59 / annuity4)
    assert 4 * w["walkaway_with_qo_aav"] == pytest.approx(60.25, abs=0.01)
    # Edwards (2019): $5.3M + $0.5M -> about $66M, the memo's first figure
    assert 4 * w["walkaway_with_qo_aav_edwards_2019"] == pytest.approx(65.75, abs=0.01)
