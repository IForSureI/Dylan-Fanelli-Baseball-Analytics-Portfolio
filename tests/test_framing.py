"""Catcher framing: the strike value's sign, the Savant URL (the season must be in seasonStart/seasonEnd), and the
report's numbers against the saved outputs."""
import json
from pathlib import Path

import pandas as pd

from baseball.evaluation import framing as fr

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = json.loads((ROOT / "reports" / "outputs" / "framing_summary.json").read_text())
REPORT = (ROOT / "reports" / "2026-catcher-framing.md").read_text()


def test_a_strike_is_worth_more_with_more_balls():
    d = pd.DataFrame({"count": ["0-0"] * 4 + ["3-2"] * 4, "strike": [1, 1, 0, 0] * 2,
                      "delta_run_exp": [-0.03, -0.03, 0.04, 0.04, -0.3, -0.3, 0.3, 0.3]})
    v = fr.strike_values(d)
    assert 0 < v["0-0"] < v["3-2"]


def test_savant_url_names_the_season():
    u = fr.SAVANT_URL.format(y=2024)
    assert "seasonStart=2024" in u and "seasonEnd=2024" in u and "year=" not in u


def test_report_matches_saved_outputs():
    s = SUMMARY["seasons"]
    for y, r in (("2024", "0.97"), ("2025", "0.98"), ("2026", "0.92")):
        assert f"{s[y]['savant']['r_raw']:.2f}" == r and r in REPORT
    for y, r in (("2024", "0.66"), ("2025", "0.74"), ("2026", "0.73")):
        assert f"{s[y]['split_half']['r_season']:.2f}" == r and r in REPORT
    for y, sd in (("2024", "6.0"), ("2025", "5.6"), ("2026", "3.6")):
        assert f"{SUMMARY['spread'][y]['sd_adj']:.1f}" == sd
    assert f"{SUMMARY['year_to_year_adj']['2024->2025']['r']:.2f}" == "0.58" and "0.58" in REPORT
    assert f"{SUMMARY['year_to_year_adj']['2025->2026']['r']:.2f}" == "0.33" and "0.33" in REPORT
    assert sum(v["takes"] for v in s.values()) > 1_100_000 and "1.11 million" in REPORT
    for y, n in (("2024", "366,873"), ("2025", "368,845"), ("2026", "371,385")):
        assert f"{s[y]['takes']:,}" == n and n in REPORT


def test_catcher_table_has_the_headline_cases():
    t = pd.read_json(ROOT / "reports" / "outputs" / "framing_catchers.json")
    bailey = t[t.name == "Bailey, Patrick"].set_index("season").adj_runs.round(1)
    assert bailey[2025] == 27.6 and bailey[2026] == 3.3


def test_per_take_spread_zone_and_significance_match_the_report():
    sp = SUMMARY["spread"]
    per = {y: sp[y]["sd_per_1000"] for y in ("2024", "2025", "2026")}
    assert [f"{per[y]:.2f}" for y in per] == ["1.14", "1.03", "0.79"]
    assert round(100 * (1 - per["2026"] / per["2025"])) == 23 and round(100 * (1 - per["2025"] / per["2024"])) == 10
    sv = {y: sp[y]["sd_savant_per_1000"] for y in ("2024", "2025", "2026")}
    assert round(100 * (1 - sv["2026"] / sv["2025"])) == 10 and round(100 * (1 - sv["2025"] / sv["2024"])) == 8
    assert "**-23%**" in REPORT and "**-10%**" in REPORT
    pr = SUMMARY["year_to_year_paired"]
    assert pr["catchers"] == 37 and pr["diff_lo"] < 0 < pr["diff_hi"]
    z = {y: SUMMARY["seasons"][y]["zone"] for y in ("2024", "2025", "2026")}
    assert [f"{100 * z[y]['uncertain_share']:.1f}%" for y in z] == ["21.7%", "20.9%", "15.2%"]
    assert [f"{100 * z[y]['balls_well_inside']:.2f}%" for y in z] == ["0.17%", "0.12%", "0.02%"]
    t = SUMMARY["year_to_year_test"]
    assert t["p"] > 0.05 and "p = 0.14" in REPORT
