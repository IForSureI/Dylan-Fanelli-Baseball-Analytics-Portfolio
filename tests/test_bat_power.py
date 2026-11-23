"""Bat tracking vs next season's power, and the Arozarena breakdown: the report's numbers against the saved outputs."""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BP = json.loads((ROOT / "reports" / "outputs" / "bat_power_summary.json").read_text())
AZ = json.loads((ROOT / "reports" / "outputs" / "arozarena_swing_summary.json").read_text())
REPORT = (ROOT / "reports" / "2026-arozarena-swing-breakdown.md").read_text()


def test_league_models_match_the_report():
    assert BP["n_train"] == 199 and BP["n_test"] == 194 and BP["best_ball"] == "ISO + 90th-pct EV"
    assert f"{BP['ball']['ISO + 90th-pct EV']['r2_out']:.2f}" == "0.37"
    assert f"{BP['ball']['ISO']['r2_out']:.2f}" == "0.33"
    assert all(v["gain"] < 0.001 and v["gain_lo"] < 0 for v in BP["adds"].values())
    assert f"{BP['stability']['bat_speed']['r']:.2f}" == "0.94" and "0.94" in REPORT


def test_video_sample_and_tests_match_the_report():
    assert AZ["clips"] == 73 and AZ["measured"] == 23 and "23 of the 73" in REPORT
    assert AZ["tests"]["down_to_contact_ms"]["diff"] == 0
    assert round(AZ["tests"]["head_drop"]["p"], 3) <= 0.01


def test_every_measured_swing_links_its_clip():
    t = pd.read_json(ROOT / "reports" / "outputs" / "arozarena_swings.json")
    assert t[t.measured].page.str.startswith("https://www.mlb.com/video/").all()
