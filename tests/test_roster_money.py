"""The Competitive Balance Tax against real 2025 bills, and valuation arithmetic checked by hand.
Real: the 2025 payrolls and bills (CBS Sports, Dec. 20, 2025), Skenes and the comparable contracts (sources in
baseball/roster/facts.py). Every other player or club here is fictional and labeled so."""
import pytest

from baseball.roster import facts
from baseball.roster.money import (arb_path, cbt_bill, cbt_pick_dropped, dollars_per_war, extension_band, implied_dpw, implied_war1,
                                   level_aav, project_war, pv, qualifying_offer, tax_cost_of_signing, value_seasons)

DOLLAR = 1e-6   # $1 in $ millions


@pytest.mark.parametrize("club,payroll,years,actual", [c for c in facts.CBT_2025 if c[0] != "Red Sox"])
def test_cbt_reproduces_2025_bills_to_the_dollar(club, payroll, years, actual):
    assert cbt_bill(payroll, years, season=2025).total == pytest.approx(actual, abs=DOLLAR)


def test_cbt_dodgers_by_hand():
    # Over = 417.341608 - 241 = 176.341608. Base 50% = 88.170804; 12% x 20 = 2.4; 45% x 20 = 9.0;
    # 60% x 116.341608 = 69.8049648. Total 169.3757688 vs the bill's $169,375,768.
    b = cbt_bill(417.341608, 5, season=2025)
    assert b.base == pytest.approx(88.170804) and b.surcharge_60_plus == pytest.approx(69.8049648)
    assert b.marginal_rate == pytest.approx(1.10) and b.cost_of_next_dollar == pytest.approx(2.10)
    assert b.pick_drop


def test_cbt_first_time_payor_gets_42_5_percent():
    # Blue Jays 2025, first year over: 20% x 45.135551 = 9.0271102; 12% x 20 = 2.4;
    # 42.5% x 5.135551 = 2.18260918; total 13.60971938 (bill $13,609,719). At 45% it would be 13.7381.
    b = cbt_bill(286.135551, 1, season=2025)
    assert b.surcharge_40_60 == pytest.approx(0.425 * 5.135551)
    assert b.total == pytest.approx(13.609719, abs=DOLLAR)
    assert b.pick_drop                                             # $45.1M over: top pick drops 10 places


def test_cbt_repeat_payor_rate_is_by_status_not_tier_history():
    # Phillies 2025: $40-60M tier at 45% although their 2024 bill ($14.4M at 50/62%) means they were
    # under the $277M third line in 2024. 50% x 73.329912 = 36.664956; + 2.4 + 9.0 + 60% x 13.329912
    # (7.9979472) = 56.0629032 (bill $56,062,903). At 42.5% the bill would be $0.5M lower.
    assert cbt_bill(314.329912, 4, season=2025).total == pytest.approx(56.062903, abs=DOLLAR)


def test_red_sox_2025_gap_is_documented_not_hidden():
    # 20% x (248.859139 - 241) = 1.5718278 vs the published 1.496828: exactly $75,000 apart, i.e. the
    # bill was computed on a payroll $375,000 lower than the one published.
    _, payroll, years, actual = next(c for c in facts.CBT_2025 if c[0] == "Red Sox")
    computed = cbt_bill(payroll, years, season=2025).total
    assert computed - actual == pytest.approx(facts.RED_SOX_GAP, abs=DOLLAR)
    assert cbt_bill(payroll - 0.375, years, season=2025).total == pytest.approx(actual, abs=DOLLAR)


def test_cbt_pick_penalty_top_six_exception():
    # MLB.com glossary: $40M+ over moves the highest pick back 10 places, or the second-highest if the
    # highest is in the top six. Fictional club picking 5th and 40th.
    assert cbt_pick_dropped(45.0, [5, 40]) == 40
    assert cbt_pick_dropped(45.0, [12, 40]) == 12
    assert cbt_pick_dropped(39.9, [12, 40]) is None


def test_cbt_resets_and_thresholds():
    assert cbt_bill(240.0, 3, season=2025).total == 0               # under the line: no tax
    assert cbt_bill(251.0, 1, season=2025).total == pytest.approx(2.0)   # 20% x 10
    assert cbt_bill(251.0, 2, season=2025).total == pytest.approx(3.0)   # 30% x 10
    assert cbt_bill(254.0, 1, season=2026).total == pytest.approx(2.0)   # 2026 line $244M
    with pytest.raises(ValueError):
        cbt_bill(260.0, 1, season=2027)                             # no 2027 rules until a new agreement
    assert cbt_bill(310.0, 1, threshold=300.0).total == pytest.approx(2.0)   # MLBPA's reported $300M line


def test_tax_cost_of_signing():
    # Fictional repeat payor at $300M in 2026 (56 over): adding $10M crosses $304M (60 over).
    # Tax before: 50% x 56 = 28 + 2.4 + 45% x 16 = 7.2 -> 37.6. After (66 over): 33 + 2.4 + 9 + 0.6 x 6 = 3.6 -> 48.0.
    r = tax_cost_of_signing(300.0, 10.0, 3, season=2026)
    assert r["added_tax"] == pytest.approx(10.4) and r["all_in_cost"] == pytest.approx(20.4)


def test_dollars_per_war_tiers_and_growth():
    assert dollars_per_war(4.0) == 12.84 and dollars_per_war(1.5) == 8.51 and dollars_per_war(0.5) == 6.74
    assert dollars_per_war(4.0, tiered=False) == 11.23
    assert dollars_per_war(4.0, season=2028) == pytest.approx(12.84 * 1.03 ** 2)   # 13.622
    assert dollars_per_war(-0.5) == 6.74


def test_project_war_aging():
    # Fictional 4.0 WAR at 27: flat at 27-28, -0.4 at 29-33, -0.6 after 33
    assert project_war(4.0, 27, 4) == pytest.approx([4.0, 4.0, 3.6, 3.2])
    assert project_war(2.0, 33, 3) == pytest.approx([2.0, 1.4, 0.8])    # 33 is year 1, 34 and 35 steep
    assert project_war(0.5, 31, 3) == pytest.approx([0.5, 0.1, 0.0])    # never below zero


def test_arb_path_fangraphs_shares_by_hand():
    # Fictional: platform WAR 3.0 (2026), 3.0, 3.0. Arb 1 = 15% x 3 x 12.84 = 5.778;
    # Arb 2 = 35% x 3 x 13.2252 = 13.88646; Arb 3 = 50% x 3 x 13.621956 = 20.432934
    rows = arb_path([3.0, 3.0, 3.0], 2027)
    assert [r["salary"] for r in rows] == pytest.approx([5.778, 13.88646, 20.432934])


def test_arb_path_anchored_to_an_outside_projection():
    # MLBTR-style year 1 of 5.0 instead of 5.778: later years scale by 5.0 / 5.778 = 0.865351
    rows = arb_path([3.0, 3.0, 3.0], 2027, first_salary=5.0, calibrate=True)
    assert rows[0]["salary"] == 5.0
    assert rows[1]["salary"] == pytest.approx(13.88646 * 5.0 / 5.778)
    # uncalibrated: only year 1 is replaced
    assert arb_path([3.0, 3.0, 3.0], 2027, first_salary=5.0)[1]["salary"] == pytest.approx(13.88646)


def test_arb_path_floor_and_never_down():
    rows = arb_path([3.0, 0.2, 0.2], 2027)                          # a collapse after a good platform year
    assert rows[1]["salary"] == pytest.approx(5.778)                # held at the prior award
    assert arb_path([0.0], 2027)[0]["salary"] == 0.78               # the 2026 minimum as a floor


def test_value_and_discounting_by_hand():
    # Fictional 2 WAR in 2026 and 2027, salaries 5 and 5: values 25.68 and 26.4504; PV at 10%:
    # value 25.68 + 26.4504 / 1.1 (24.045818) = 49.725818; salary 5 + 4.545455 = 9.545455; surplus 40.180364
    v = value_seasons([2.0, 2.0], 2026, [5.0, 5.0])
    assert v.pv_value == pytest.approx(49.725818, abs=1e-6) and v.pv_surplus == pytest.approx(40.180364, abs=1e-6)
    assert pv([11.0, 11.0]) == pytest.approx(21.0)
    assert level_aav(21.0, 2) == pytest.approx(11.0)


def test_extension_band_by_hand():
    # Fictional: one arb year (low 4, base 5), one FA year (value low 16, base 22), 10% discount.
    # Club ceiling = 5 + 22 / 1.1 = 25; player floor = 4 + 16 / 1.1 = 18.545455; midpoint 21.772727
    b = extension_band([4.0], [5.0], [16.0], [22.0])
    assert b["club_ceiling_pv"] == pytest.approx(25.0) and b["player_floor_pv"] == pytest.approx(18.545455)
    assert b["midpoint_pv"] == pytest.approx(21.772727) and b["overlap"]
    # A cap of 12 on his outside offers lowers the player's floor; it moves the club's ceiling only if the
    # club's own cost of keeping him is capped too (club_fa_max)
    c = extension_band([4.0], [5.0], [16.0], [22.0], fa_max_salary=[12.0])
    assert c["club_ceiling_pv"] == pytest.approx(25.0) and c["player_floor_pv"] == pytest.approx(4 + 12 / 1.1)
    d = extension_band([4.0], [5.0], [16.0], [22.0], fa_max_salary=[12.0], club_fa_max=[18.0])
    assert d["club_ceiling_pv"] == pytest.approx(5 + 18 / 1.1)                    # 21.363636
    # split: a quarter of the surplus to the player: 18.545455 + 0.25 x (25 - 18.545455) = 20.159091
    assert extension_band([4.0], [5.0], [16.0], [22.0], split=0.25)["midpoint_pv"] == pytest.approx(20.159091)


def test_implied_dpw_and_war1_by_hand():
    # Fictional 2 years, $100M: pay 50 + 50 / 1.05 = 97.619048; wins 3.0 + 2.6 = 5.6 -> 17.431973 per WAR
    assert implied_dpw(100.0, 2, 3.0) == pytest.approx(17.431973)
    # and back: (97.619048 / 17.431973 + 0.4 x 1) / 2 = (5.6 + 0.4) / 2 = 3.0
    assert implied_war1(100.0, 2, 17.431973) == pytest.approx(3.0, abs=1e-6)


def test_dollars_per_war_base_year_and_tier_cliff():
    assert dollars_per_war(4.0, 2026, base_season=2025) == pytest.approx(12.84 * 1.03)
    # 1.99 WAR prices at the 1-2 tier: 1.99 x 8.51 = 16.93, against 2.0 x 12.84 = 25.68
    assert 1.99 * dollars_per_war(1.99) == pytest.approx(16.9349) and 2.0 * dollars_per_war(2.0) == pytest.approx(25.68)


def test_qualifying_offer_by_status():
    q = qualifying_offer("recipient", "payor", 60.0)
    assert q["losing_club_gets"] == "pick between Round 1 and Competitive Balance Round A"
    assert q["signing_club_forfeits_picks"] == ["2nd-highest", "5th-highest"] and q["signing_club_forfeits_pool"] == 1.0
    assert qualifying_offer("recipient", "other", 49.9)["losing_club_gets"] == "pick after Competitive Balance Round B"
    assert qualifying_offer("payor", "recipient", 300.0)["losing_club_gets"] == "pick after Round 4"
    assert qualifying_offer("other", "recipient", 300.0)["signing_club_forfeits_picks"] == ["3rd-highest"]
    second = qualifying_offer("other", "payor", 100.0, nth_signing=2)
    assert second["signing_club_forfeits_picks"] == ["3rd-highest", "6th-highest"] and second["note"]
    with pytest.raises(ValueError):
        qualifying_offer("small market", "other", 10.0)


def test_skenes_case_numbers():
    from baseball.roster.cases import skenes_extension, skenes_war_base
    # (5 x 4.2 + 4 x 6.5 + 3 x 4.3) / 12 = 59.9 / 12 = 4.991667
    assert skenes_war_base() == pytest.approx(4.991667, abs=1e-6)
    e = skenes_extension()
    base = e["paths"]["base"]
    assert base["arb_mlbtr"][0] == 7.2                              # MLBTR, Oct. 2, 2026
    # FanGraphs year 1: 15% x 4.2 x 12.84 = 8.0892
    assert base["arb_fangraphs"][0] == pytest.approx(8.0892)
    # MLB plan maxima in 2030: 16% x 245.3 x 1.03^3 = 42.8874 (own club); 15% -> 40.2069 (other clubs)
    assert e["own_club_max"][0] == pytest.approx(0.16 * 245.3 * 1.03 ** 3)
    assert e["new_club_max"][0] == pytest.approx(0.15 * 245.3 * 1.03 ** 3)


def test_skenes_mlb_plan_ceiling_uses_the_capped_alternative():
    from baseball.roster.cases import skenes_extension
    e = skenes_extension()
    sq, mlb = e["bands"]["current rules"], e["bands"]["MLB plan"]
    # every base free-agent value (72.1 ... 55.2) exceeds the 16% path (42.9 ... 52.1), so the club's
    # alternative is the capped path: ceiling = PV(base arbitration) + PV(16% path from t = 3)
    expected = pv(e["paths"]["base"]["arb_mlbtr"]) + pv([0.0] * 3 + e["own_club_max"])
    assert mlb["club_ceiling_pv"] == pytest.approx(expected)
    assert mlb["club_ceiling_pv"] < sq["club_ceiling_pv"] and mlb["player_floor_pv"] < sq["player_floor_pv"]
    # 15% outside offers lower his floor further but not the club's cost of keeping him
    m15 = e["bands"]["MLB plan, 15% outside offers"]
    assert m15["player_floor_pv"] < mlb["player_floor_pv"] and m15["club_ceiling_pv"] == mlb["club_ceiling_pv"]


def test_skenes_durability_and_break_even():
    from baseball.roster.cases import club_ceiling, skenes_extension, skenes_paths, skenes_war_base, SCENARIOS
    e = skenes_extension()
    paths = {k: skenes_paths(skenes_war_base() * m) for k, m in SCENARIOS.items()}
    c0, c1 = club_ceiling(paths, 0.0, None), club_ceiling(paths, 1.0, None)
    # the ceiling is linear in the stress chance: 0.8 x healthy + 0.2 x stress
    assert e["ceilings"][("current rules", 0.2)] == pytest.approx(0.8 * c0 + 0.2 * c1)
    assert c1 < c0 and e["ceilings"][("current rules", 0.0)] == pytest.approx(e["bands"]["current rules"]["club_ceiling_pv"])
    # break-even mixes the two rule sets: q = 0.25 -> 0.75 x current + 0.25 x MLB plan
    be = e["breakeven"][(0.25, 0.2)]
    assert be == pytest.approx(0.75 * e["ceilings"][("current rules", 0.2)] + 0.25 * e["ceilings"][("MLB plan", 0.2)])


def test_skenes_dpw_base_year_sensitivity():
    from baseball.roster.cases import skenes_extension
    e = skenes_extension()
    # Arbitration is anchored to MLBTR, so only the free-agent part scales: +3% on it
    arb = pv(e["paths"]["base"]["arb_mlbtr"])
    sq = e["bands"]["current rules"]["club_ceiling_pv"]
    assert e["ceiling_if_dpw_base_2025"] == pytest.approx(arb + 1.03 * (sq - arb))


def test_comps_check_by_hand():
    from baseball.roster.cases import comps_check
    t = comps_check().set_index("pitcher")
    # Yamamoto: 325/12 = 27.0833 a year x sum of 1/1.05^t, t = 0..11 (9.306414) = 252.049;
    # wins 3.1 + 2.7 + ... + 0.3 (then 0) = 13.6 -> $18.53M per WAR vs $14.13M (FanGraphs 2024 2+ row)
    assert t.loc["Yoshinobu Yamamoto", "implied_dpw"] == pytest.approx(18.533, abs=1e-3)
    assert t.loc["Yoshinobu Yamamoto", "ratio_to_rate"] == pytest.approx(18.533 / 14.13, abs=1e-3)
    # Cole on MLB.com's Oliver path: 36 x 7.463213 = 268.676 over 37.3 WAR (the yearly figures; MLB.com's
    # 37.4 total is rounded) = 7.203
    assert t.loc["Gerrit Cole", "implied_dpw"] == pytest.approx(7.203, abs=1e-3)
    assert 2.5 < t.loc["Corbin Burnes", "implied_war1_at_rate"] < 4.0
