"""Service time, control, options, Rule 5 and roster rights. Players here are fictional unless named;
named cases (Skenes) use public facts cited in baseball/roster/facts.py."""
from datetime import date

import pytest

from baseball.roster.service import (SUPER_TWO_CUTOFFS, Service, can_option, earliest_recall, is_full_season,
                                     is_super_two, options_remaining, outright_rights, rookie_of_year_credit,
                                     rule5_age_at_signing, rule5_first_eligible, ten_and_five, timeline,
                                     uses_option_year)


def test_parse_and_print_years_days():
    assert Service.parse("3.045").total_days == 3 * 172 + 45        # 561
    assert str(Service.parse("3.045")) == "3.045"
    assert str(Service.parse("2.14")) == "2.140"                    # trailing digits pad: 2.14 = 2.140
    assert str(Service.parse(2.14)) == "2.140"                      # the float reads the same way
    assert str(Service.parse("5")) == "5.000"
    with pytest.raises(ValueError):
        Service.parse("2.172")                                      # 172 days is a year, not days


def test_a_season_counts_at_most_one_year_and_partial_seasons_carry():
    # 2.150 + 187 days: only 172 count -> 3.150 (not 4.015)
    assert str(Service.parse("2.150").plus_season(187)) == "3.150"
    # 2.150 + 50 days = 2*172 + 200 = 544 days = 3 years 28 days
    assert str(Service.parse("2.150").plus_season(50)) == "3.028"
    with pytest.raises(ValueError):
        Service.parse("1.000").plus_season(188)                     # a season has 187 days


def test_rookie_of_year_credit():
    assert rookie_of_year_credit(142, 1) == 172                     # Skenes 2024: .142 -> 1.000
    assert rookie_of_year_credit(142, 2) == 172
    assert rookie_of_year_credit(142, 3) == 142
    assert rookie_of_year_credit(142, None) == 142


def test_super_two_needs_cutoff_and_86_days():
    cut = SUPER_TWO_CUTOFFS[2026]                                   # 2.140 (AP, Nov. 7, 2025)
    assert is_super_two("2.140", 120, cut)                          # at the cutoff qualifies
    assert not is_super_two("2.139", 120, cut)                      # one day short
    assert not is_super_two("2.150", 85, cut)                       # under 86 days that season
    assert not is_super_two("3.000", 172, cut)                      # 3+ is ordinary arbitration
    assert SUPER_TWO_CUTOFFS[2024] == "2.118" and SUPER_TWO_CUTOFFS[2025] == "2.132"


def test_timeline_ordinary_arbitration_and_free_agency():
    # Fictional: 3.000 after 2026, full seasons -> arb 2027-29, 6.000 after 2029
    t = timeline("3.000", 2026)
    assert t.arb_seasons == [2027, 2028, 2029] and t.free_agent_after == 2029
    assert t.control_seasons == [2027, 2028, 2029] and not t.super_two
    assert t.path[:3] == [(2027, "4.000"), (2028, "5.000"), (2029, "6.000")]


def test_timeline_super_two_gets_four_arbitration_years():
    # Fictional: 2.142 after 2026 with 172 days in 2026, cutoff 2.133 -> four arbitration years
    t = timeline("2.142", 2026, super_two_cutoff="2.133")
    assert t.super_two and t.arb_seasons == [2027, 2028, 2029, 2030]
    # 2.142 -> 3.142 (2027) -> 4.142 -> 5.142 -> 6.142 after 2030
    assert t.free_agent_after == 2030
    # below the cutoff: pre-arb 2027, then three arbitration years
    t2 = timeline("2.120", 2026, super_two_cutoff="2.133")
    assert not t2.super_two and t2.arb_seasons == [2028, 2029, 2030] and t2.control_seasons[0] == 2027


def test_timeline_short_seasons_delay_free_agency():
    # Fictional: 5.100 after 2026; 60 days in 2027 -> 5.160; 6.000 needs 12 more days in 2028
    t = timeline("5.100", 2026, future_days=[60, 172])
    assert t.path == [(2027, "5.160"), (2028, "6.160")] and t.free_agent_after == 2028
    # a lockout year that leaves only 150 credited days still gets 5.100 -> 6.078
    t2 = timeline("5.100", 2026, future_days=[150])
    assert t2.free_agent_after == 2027


def test_skenes_service_matches_mlbtr():
    from baseball.roster.cases import skenes_service
    s = skenes_service()
    assert s["service_after_2026"] == "3.000"                       # MLBTR, Oct. 2, 2026
    assert s["arb_seasons"] == [2027, 2028, 2029] and s["free_agent_after"] == 2029
    # without the ROY credit he'd sit at 2.142: a Super Two at the 2.133 estimate, free agent after 2030
    assert s["without_roy_credit"]["service_after_2026"] == "2.142"
    assert s["without_roy_credit"]["free_agent_after"] == 2030


def test_options_twenty_day_rule_and_fourth_option():
    assert not uses_option_year(19) and uses_option_year(20)
    assert options_remaining(0, 0) == 3 and options_remaining(2, 6) == 1
    assert options_remaining(3, 4) == 1                             # fewer than five full seasons
    assert options_remaining(3, 5) == 0
    assert options_remaining(4, 2) == 0                             # the fourth is the last
    assert is_full_season(90) and not is_full_season(89)
    assert is_full_season(40, injured_days=50)                      # 30-89 active topped up by IL
    assert not is_full_season(29, injured_days=100)


def test_five_optional_assignments_a_season():
    assert can_option(2, 4) and not can_option(2, 5)
    assert can_option(2, 5, in_spring=True)                         # spring options don't count
    assert not can_option(0, 0)
    assert can_option(2, 3, max_assignments=3) is False             # MLBPA's July 2026 proposal: 3
    assert earliest_recall(date(2026, 5, 1), "pitcher") == date(2026, 5, 16)
    assert earliest_recall(date(2026, 5, 1), "position") == date(2026, 5, 11)
    assert earliest_recall(date(2026, 5, 1), "pitcher", replacing_injured=True) == date(2026, 5, 1)


def test_rule5_june5_age_rule():
    # Fictional: born June 20, 2003; signed July 15, 2022 -> age on June 5, 2022 = 18 (turned 19 June 20)
    assert rule5_age_at_signing(date(2003, 6, 20), date(2022, 7, 15)) == 18
    r = rule5_first_eligible(date(2003, 6, 20), date(2022, 7, 15))
    assert r["first_eligible_draft"] == 2026                        # 2022 + 4
    # born June 1, 2003: 19 on June 5, 2022 -> 19+ clock, 2022 + 3
    assert rule5_first_eligible(date(2003, 6, 1), date(2022, 7, 15))["first_eligible_draft"] == 2025
    # January signing looks back to the prior June 5: born Mar. 1, 2006, signed Jan. 15, 2023 -> 16
    assert rule5_age_at_signing(date(2006, 3, 1), date(2023, 1, 15)) == 16
    assert rule5_first_eligible(date(2006, 3, 1), date(2023, 1, 15))["first_eligible_draft"] == 2027


def test_rule5_signing_after_season_and_proposal():
    # Fictional college player (21) signing in October after the minor-league season: 2023 is his first
    r = rule5_first_eligible(date(2001, 3, 1), date(2022, 10, 1), signed_after_season_end=True)
    assert r["first_qualified_season"] == 2023 and r["first_eligible_draft"] == 2026
    # MLB's Aug. 27, 2026 proposal moves eligibility up a year
    assert rule5_first_eligible(date(2003, 6, 20), date(2022, 7, 15), years_earlier=1)["first_eligible_draft"] == 2025


def test_outright_rights_and_ten_and_five():
    assert outright_rights("2.100")["can_refuse"] is False
    assert outright_rights("2.100", previously_outrighted=True)["can_refuse"] is True
    r3 = outright_rights("3.000")
    assert r3["can_refuse"] and not r3["keeps_salary_if_refuses"]
    r5 = outright_rights("5.000")
    assert r5["keeps_salary_if_refuses"] and r5["consent_required"]
    assert ten_and_five("10.000", 5) and not ten_and_five("9.171", 5) and not ten_and_five("12.000", 4)
