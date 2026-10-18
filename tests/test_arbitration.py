"""Salary arbitration, club side: comparables, the comp line, the hearing odds, the filing and the settle-or-go math,
checked by hand. Needs no data files. Real: Cade Smith and the comparable closers (sources on each row in
baseball/roster/arbitration.py) and the 2026 exchanges. Every other reliever here is fictional and labeled so."""
import math

import pytest

from baseball.roster.arbitration import (EXCHANGES_2026, MLBTR_2027, NEXT_GROUP, ORIGINAL_TEN, POOL, SCREENED_OUT, SMITH,
                                         SMITH_SEASONS, Reliever, added_predictor_tests, best_filing, bracket,
                                         breakeven_weight, carry_cost, comparable_by_service, distance, dominance,
                                         expected_award, fit_comp_line, fit_pool, gap_ratios, ip, loo_errors, median,
                                         midpoint, next_group_raises, p_club_wins, restate, select_comparables,
                                         sensitivity, settlement, smith_case, straddle, walk_point)


def fictional(name, season, psv, era, csv, salary=None, service=None):
    """A fictional reliever: only the panel stats matter here."""
    return Reliever(f"Fictional {name}", season, psv, era, 60.0, 70, csv, 180.0, False, service=service, salary=salary)


# ------------------------------------------------------------------ units and rules
def test_innings_notation():
    # '75.1' is 75 and one out = 75 1/3; '64.2' = 64 2/3; there is no '.3'.
    assert ip("75.1") == pytest.approx(75 + 1 / 3)
    assert ip("64.2") == pytest.approx(64 + 2 / 3)
    assert ip("74.0") == 74
    with pytest.raises(ValueError):
        ip("74.3")


def test_service_rule_allows_one_more_year_and_any_less():
    # Player at 3.000: a comp at 4.171 has one more full year (allowed); 5.000 has two (not); a Super Two is fine.
    assert comparable_by_service("3.000", "4.171")
    assert not comparable_by_service("3.000", "5.000")
    assert comparable_by_service("3.000", "2.115")
    assert comparable_by_service("3.000", None)


def test_smith_facts_add_up():
    # 1 + 16 + 41 = 58 career saves; 75 1/3 + 73 2/3 + 74 = 223 innings; 41 of 46 chances = 89.1%.
    assert sum(s["sv"] for s in SMITH_SEASONS.values()) == SMITH.career_sv == 58
    assert sum(s["ip"] for s in SMITH_SEASONS.values()) == pytest.approx(SMITH.career_ip) == pytest.approx(223.0)
    assert SMITH_SEASONS[2026]["sv"] / SMITH_SEASONS[2026]["sv_opp"] == pytest.approx(0.8913, abs=1e-4)
    assert all(c.source for c in POOL) and all(c.salary for c in POOL)
    hader = next(c for c in POOL if c.name == "Josh Hader")
    assert hader.super_two and hader.service == "2.115" and hader.club_figure == hader.salary == 4.1


# ------------------------------------------------------------------ comparables
def test_distance_by_hand():
    # Smith (41 SV, 1.95, 58 career, 2027) vs Bednar (39, 2.00, 61, 2024):
    # (2/10)^2 + (-3/25)^2 + (-0.05/1)^2 + (3/8)^2 = 0.04 + 0.0144 + 0.0025 + 0.140625 = 0.197525 -> 0.444438.
    bednar = next(c for c in POOL if c.name == "David Bednar")
    assert distance(SMITH, bednar) == pytest.approx(math.sqrt(0.197525))


def test_select_comparables_nearest_first_and_service_eligible():
    far = fictional("veteran", 2026, 41, 1.95, 58, salary=9.0, service="5.010")   # two more years: excluded
    near = fictional("twin", 2027, 41, 1.95, 58, salary=4.0, service="3.000")
    picked = select_comparables(SMITH, POOL + [far, near], k=3)
    assert picked[0][0].name == "Fictional twin" and picked[0][1] == 0
    assert all(c.name != "Fictional veteran" for c, _ in picked)
    # Knebel 2018: (2/10)^2 + (17/25)^2 + (0.17/1)^2 + (9/8)^2 = 0.04 + 0.4624 + 0.0289 + 1.265625 = 1.796925 -> 1.3405
    assert [c.name for c, _ in select_comparables(SMITH, POOL, k=6)] == [
        "David Bednar", "Jordan Romano", "Josh Hader", "Corey Knebel", "Ken Giles", "Jeurys Familia"]
    knebel = next(c for c in POOL if c.name == "Corey Knebel")
    assert distance(SMITH, knebel) == pytest.approx(math.sqrt(1.796925))


def test_dominance_with_career_tolerance():
    # Fictional player 40 SV, 2.00 ERA, 60 career saves.
    p = fictional("player", 2027, 40, 2.00, 60)
    assert dominance(p, fictional("a", 2024, 35, 2.50, 64)) == 1     # 64 is within 5 of 60: still beaten
    assert dominance(p, fictional("b", 2024, 35, 2.50, 70)) == 0     # 70 career saves is a real edge: mixed
    assert dominance(p, fictional("c", 2024, 45, 1.80, 90)) == -1    # better on all three
    assert dominance(p, fictional("d", 2024, 45, 2.10, 90)) == 0     # more saves, worse ERA: mixed


def test_restate_and_bracket():
    # $4.0M set in 2025 at 2% a year: 4.0 x 1.02^2 = 4.1616 in 2027.
    assert restate(4.0, 2025, 2027, 0.02) == pytest.approx(4.1616)
    p = fictional("player", 2027, 40, 2.00, 60)
    comps = [fictional("low", 2025, 35, 2.50, 50, salary=4.0), fictional("lower", 2027, 30, 3.00, 40, salary=3.5),
             fictional("high", 2026, 45, 1.80, 90, salary=6.0), fictional("mixed", 2027, 45, 2.50, 40, salary=5.0)]
    b = bracket(p, comps, growth=0.02)
    # Floor: max(4.1616, 3.5) from "low"; ceiling: 6.0 x 1.02 = 6.12 from "high"; "mixed" is neither.
    assert b["floor"] == pytest.approx(4.1616) and b["floor_comp"] == "Fictional low"
    assert b["ceiling"] == pytest.approx(6.12) and b["ceiling_comp"] == "Fictional high"
    assert b["mixed"] == ["Fictional mixed"]


def test_comp_line_recovers_an_exact_line():
    # Fictional comps on log(s) = 1.0 + 0.01 psv + 0.004 csv + 0.012 (season - 2027), no noise.
    rows = [(30, 40, 2020), (35, 60, 2022), (40, 50, 2024), (25, 90, 2025), (45, 70, 2026), (38, 55, 2019)]
    comps = [fictional(f"c{i}", yr, psv, 2.5, csv, salary=math.exp(1 + 0.01 * psv + 0.004 * csv + 0.012 * (yr - 2027)))
             for i, (psv, csv, yr) in enumerate(rows)]
    line = fit_comp_line(comps, 2027)
    assert line.coef == pytest.approx([1.0, 0.01, 0.004, 0.012], abs=1e-9)
    assert line.growth == pytest.approx(math.exp(0.012) - 1)          # 1.2072% a year
    # 41 SV, 58 career, 2027: exp(1 + 0.41 + 0.232) = exp(1.642) = 5.16549; no residual, so no error.
    pred = line.predict(fictional("p", 2027, 41, 2.0, 58))
    assert pred["value"] == pytest.approx(math.exp(1.642)) and pred["se"] == pytest.approx(0, abs=1e-6)
    with pytest.raises(ValueError):
        fit_comp_line(comps[:4], 2027)


def test_fit_pool_keeps_recent_comps_only():
    names = [c.name for c in fit_pool(POOL, 2027)]
    assert "Jonathan Papelbon" not in names and len(names) == 19           # 2009 is 18 seasons back: an exhibit
    assert "Jonathan Papelbon" in [c.name for c in fit_pool(POOL, 2027, max_age=30)]
    assert set(ORIGINAL_TEN) <= set(names)


def test_pool_follows_its_rule():
    # Every fit row had 20+ platform saves and a sourced salary; nobody is both in the pool and screened out.
    rows = fit_pool(POOL, 2027)
    assert all(c.platform_sv >= 20 and c.salary and c.source for c in rows)
    assert len({(c.name, c.season) for c in POOL}) == len(POOL)
    screened = {(n, y) for n, y, _ in SCREENED_OUT}
    assert not screened & {(c.name, c.season) for c in POOL}


def test_next_group_raises_by_hand():
    # Duran 2026: $7.5M on a $4.125M first-year base = a $3.375M raise; Bednar 2025: 5.9 - 4.51 = 1.39.
    r = {x["name"]: x for x in next_group_raises()}
    assert r["Jhoan Duran"]["raise_"] == pytest.approx(3.375) and r["David Bednar"]["raise_"] == pytest.approx(1.39)
    assert len(NEXT_GROUP) == 4 and all(x["source"] for x in NEXT_GROUP)


def test_loo_and_added_predictors_on_an_exact_line():
    # Fictional comps on an exact saves line: leave-one-out errors are zero; an added stat gets coefficient ~0.
    rows = [(30, 40, 2020, 2.1), (35, 60, 2022, 3.0), (40, 50, 2024, 2.5), (25, 90, 2025, 1.9), (45, 70, 2026, 3.4),
            (38, 55, 2019, 2.2), (33, 45, 2023, 2.8)]
    comps = [fictional(f"c{i}", yr, psv, era, csv, salary=math.exp(1 + 0.01 * psv + 0.004 * csv + 0.012 * (yr - 2027)))
             for i, (psv, csv, yr, era) in enumerate(rows)]
    assert max(abs(e) for e in loo_errors(comps, 2027)) < 1e-9
    era = added_predictor_tests(comps, fictional("p", 2027, 41, 2.0, 58), 2027)[0]
    assert era["coef"] == pytest.approx(0, abs=1e-9) and era["value"] == pytest.approx(math.exp(1.642))


# ------------------------------------------------------------------ the hearing
def test_hearing_odds_by_hand():
    # Club 4.0, player 6.0: midpoint 5.0. Panel value N(5.0, 0.5): a coin flip. N(4.5, 0.5): Phi(1) = 0.841345.
    assert midpoint(4.0, 6.0) == 5.0
    assert p_club_wins(4.0, 6.0, [(1, 5.0, 0.5)]) == pytest.approx(0.5)
    assert p_club_wins(4.0, 6.0, [(1, 4.5, 0.5)]) == pytest.approx(0.841345, abs=1e-6)
    # An even mixture of N(4.5, .5) and N(5.5, .5) is symmetric about the midpoint: 0.5.
    assert p_club_wins(4.0, 6.0, [(1, 4.5, 0.5), (1, 5.5, 0.5)]) == pytest.approx(0.5)
    # Expected award at p = 0.841345: 4 x 0.841345 + 6 x 0.158655 = 4.317310. The walk point is the same number.
    assert expected_award(4.0, 6.0, [(1, 4.5, 0.5)]) == pytest.approx(4.317310, abs=1e-6)
    assert walk_point(4.0, 6.0, [(1, 4.5, 0.5)]) == expected_award(4.0, 6.0, [(1, 4.5, 0.5)])
    with pytest.raises(ValueError):
        p_club_wins(6.0, 6.0, [(1, 5.0, 0.5)])


def test_best_filing_by_hand():
    # Player files 6.0; panel N(5.0, 0.5). Expected award E(C) = C p + 6 (1 - p), p = Phi(((C + 6)/2 - 5)/0.5):
    #   C 4.30: p = Phi(0.30) = 0.617911, E = 4.949551;  C 4.35: p = Phi(0.35) = 0.636831, E = 4.949229
    #   C 4.40: p = Phi(0.40) = 0.655422, E = 4.951325.  Grid minimum at 4.35.
    views = [(1, 5.0, 0.5)]
    b = best_filing(6.0, views, lo=4.0)
    assert b["club"] == pytest.approx(4.35) and b["expected_award"] == pytest.approx(4.949229, abs=1e-6)
    # With a credibility floor of 4.8 the floor binds: E(4.80) = 4.8 x 0.788145 + 6 x 0.211855 = 5.054226,
    # and E rises above it (E(4.85) = 5.077312).
    f = best_filing(6.0, views, floor=4.8)
    assert f["club"] == pytest.approx(4.8) and f["expected_award"] == pytest.approx(5.054226, abs=1e-6)


def test_settlement_and_carry_by_hand():
    # Halfway from 4.8 to 5.9 = 5.35; 46% of the way = 4.8 + 0.506 = 5.306.
    assert settlement(4.8, 5.9) == pytest.approx(5.35)
    assert settlement(4.8, 5.9, 0.46) == pytest.approx(5.306)
    # A $1.1M gap paid in 2027, 2028 and 2029 at 10%: 1.1 x (1 + 1/1.1 + 1/1.21) = 1.1 x 2.735537 = 3.009091.
    assert carry_cost(1.1, 3) == pytest.approx(3.009091, abs=1e-6)
    # Half the gap carried: 1.1 + 0.55 x (1/1.1 + 1/1.21) = 1.1 + 0.55 x 1.735537 = 2.054545.
    assert carry_cost(1.1, 3, share=0.5) == pytest.approx(2.054545, abs=1e-6)


def test_breakeven_weight_by_hand():
    # Club 4, player 6 (midpoint 5); views N(4.5, .5) and N(5.5, .5) are mirror images: P = 0.5 at weight 0.5.
    assert breakeven_weight(4.0, 6.0, 4.5, 5.5, 0.5) == pytest.approx(0.5, abs=1e-9)


def test_2026_exchange_gaps_and_straddle():
    # 18 exchanges; the middle two ratios are Faucher 2.05/1.8 = 1.138889 and Contreras 9.9/8.55 = 1.157895.
    r = gap_ratios()
    assert len(EXCHANGES_2026) == 18
    assert median(r) == pytest.approx((2.05 / 1.8 + 9.9 / 8.55) / 2)
    assert median([1.0, 3.0, 2.0]) == 2.0
    # Straddling $5.5M at that ratio: club = 11 / 2.148392 = 5.120108, player = 5.879892.
    club, player = straddle(MLBTR_2027, median(r))
    assert club == pytest.approx(5.120108, abs=1e-5) and player == pytest.approx(5.879892, abs=1e-5)
    assert midpoint(club, player) == pytest.approx(MLBTR_2027)


# ------------------------------------------------------------------ the case (pins the brief's numbers)
def test_smith_case_numbers():
    c = smith_case()
    assert c["fit_n"] == 19
    assert c["line_value"] == pytest.approx(4.817, abs=0.001) and c["line_se"] == pytest.approx(0.375, abs=0.001)
    assert c["growth"] == pytest.approx(0.0120, abs=0.0001)
    assert c["bracket"]["floor_comp"] == "Jordan Romano" and c["bracket"]["floor"] == pytest.approx(4.758, abs=0.001)
    assert c["bracket"]["ceiling"] is None                       # no comp beats him on every panel stat
    assert c["player_likely"] == 5.9 and c["club_filing"] == 4.8 and c["midpoint"] == pytest.approx(5.35)
    # P(win): comp view Phi((5.35 - 4.817)/0.375) = Phi(1.42) = 0.923; market Phi((5.35 - 5.5)/0.375) = Phi(-0.40) = 0.345.
    assert c["p_win"]["comp line"] == pytest.approx(0.923, abs=0.002)
    assert c["p_win"]["market"] == pytest.approx(0.345, abs=0.002)
    assert c["p_win"]["blend"] == pytest.approx((0.923 + 0.345) / 2, abs=0.002)
    # Expected award 4.8 x 0.634 + 5.9 x 0.366 = 5.203; settle at or below $5.20M; losing costs 1.1 x 2.735537 = 3.009.
    assert c["walk_point"] == pytest.approx(5.203, abs=0.002) and c["walk_point_grid"] == pytest.approx(5.20)
    assert c["cost_lose"] == pytest.approx(3.009, abs=0.001)
    # Out of sample the line misses by about 8% (in sample about 6%).
    assert c["in_sample_sd"] == pytest.approx(0.060, abs=0.001) and c["loo_rmse"] == pytest.approx(0.079, abs=0.001)


def test_sensitivity_rows():
    rows = {r["case"]: r for r in sensitivity()}
    base = rows["base: even blend of the comp line and MLBTR"]
    assert rows["weight on MLBTR's view 0.75"]["p_win"] < base["p_win"] < rows["weight on MLBTR's view 0.25"]["p_win"]
    # Dropping the three hearing awards barely moves the line (under $0.02M): the comps fit the same saves line.
    assert rows["fit without the three hearing awards (Hader, Osuna, Giles)"]["line_value"] == pytest.approx(base["line_value"], abs=0.02)
    # The hand-built ten-comp line was $0.09M higher; the filing doesn't change.
    assert rows["fit on the original ten comps only"]["line_value"] == pytest.approx(4.903, abs=0.001)
