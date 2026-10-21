"""The second arbitration case, Louis Varland (Toronto, a Super Two), checked by hand. Needs no data files. Real:
Varland and the comparable closers (sources on each row in baseball/roster/arbitration.py)."""
import math

import pytest

from baseball.roster import arbitration as A
from baseball.roster.service import timeline


def phi(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def test_smith_case_is_the_generic_case_on_smith():
    # The refactor leaves the first brief alone: smith_case() is case(SMITH_CASE), number for number.
    a, b = A.smith_case(), A.case(A.SMITH_CASE)
    for k in ("club_filing", "player_likely", "line_value", "line_se", "walk_point", "cost_lose", "cost_lose_stoppage"):
        assert a[k] == b[k]
    assert a["club_filing"] == 4.65 and a["player_likely"] == 5.9


def test_super_two_control_and_a_stoppage():
    # 2.163 after 2026, above the 2.133 cutoff: arbitration 2027-30, free agent after 2030 (Baseball-Reference: 2031).
    t = timeline("2.163", 2026, super_two_cutoff="2.133")
    assert t.arb_seasons == [2027, 2028, 2029, 2030] and t.free_agent_after == 2030
    # A 120-day 2027: 2.163 + 120 days = 2.283 = 3.111 (172 days a year), then 4.111, 5.111, 6.111 after 2030.
    # Free agency doesn't move, so a stoppage adds no arbitration year for him (it does for Smith).
    s = timeline("2.163", 2026, future_days=[120] + [172] * 7, super_two_cutoff="2.133")
    assert s.free_agent_after == 2030
    c = A.varland_case()
    assert c["stoppage_arb_seasons"] == [2027, 2028, 2029, 2030]
    assert c["cost_lose_stoppage"] == pytest.approx(c["cost_lose"])


def test_player_figure_and_the_floor():
    c = A.varland_case()
    # Straddle MLBTR's $3.8M at the 2026 median ratio r: club = 2 x 3.8 / (1 + r), player = club x r, rounded to $50K.
    r = c["ratios_median"]
    assert c["club_symmetric"] == pytest.approx(7.6 / (1 + r))
    assert c["player_likely"] == round(7.6 * r / (1 + r) * 20) / 20 == 4.05
    # The floor: A.J. Ramos's $3.4M (2016) restated at the line's growth g for 11 seasons: 3.4 x (1 + g)^11 = $3.629M.
    g = c["growth"]
    assert c["bracket"]["floor_comp"] == "A.J. Ramos"
    assert c["bracket"]["floor"] == pytest.approx(3.4 * (1 + g) ** 11)
    # The filing: the floor rounded up to $50K.
    assert c["club_filing"] == 3.65


def test_hearing_odds_by_hand():
    c = A.varland_case()
    v, sd = c["line_value"], c["line_se"]
    mid = (3.65 + 4.05) / 2
    assert c["midpoint"] == pytest.approx(3.85)
    p_comp = phi((mid - v) / sd)                  # reads the comps
    p_mkt = phi((mid - 3.8) / sd)                 # reads MLBTR's $3.8M
    assert c["p_win"]["comp line"] == pytest.approx(p_comp)
    assert c["p_win"]["market"] == pytest.approx(p_mkt)
    assert c["p_win"]["blend"] == pytest.approx((p_comp + p_mkt) / 2)
    # Even the all-market view leaves the club the favorite (P > 0.5), so no weight flips the case.
    assert p_mkt > 0.5 and math.isnan(c["breakeven_weight"])
    # Expected award = P x club + (1 - P) x player; it is the walk point.
    p = c["p_win"]["blend"]
    assert c["walk_point"] == pytest.approx(p * 3.65 + (1 - p) * 4.05)
    assert c["walk_point_grid"] == 3.80


def test_carry_over_four_arbitration_years():
    c = A.varland_case()
    # Super Two: 2027-30, so the 2027 gap repeats four times at 10%: 1 + 1/1.1 + 1/1.21 + 1/1.331 = 3.4869.
    f = 1 + 1 / 1.1 + 1 / 1.21 + 1 / 1.331
    assert c["cost_lose"] == pytest.approx((4.05 - 3.65) * f)
    assert c["cost_lose_half_carry"] == pytest.approx((4.05 - 3.65) * (1 + 0.5 * (f - 1)))


def test_high_filing_and_sensitivity_rows():
    c = A.varland_case()
    assert c["record_figure"] == A.high_filing(3.8) == 4.55
    rows = {r["case"]: r for r in A.sensitivity(A.VARLAND_CASE)}
    assert "fit on the 2020-26 comps only (the recent market)" in rows
    assert "player files high ($4.55M)" in rows
    # The recent-market fit is the player's best line: above MLBTR, and the club becomes the underdog there.
    rec = rows["fit on the 2020-26 comps only (the recent market)"]
    assert rec["line_value"] > 3.8 and rec["p_win"] < 0.5
