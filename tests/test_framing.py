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
