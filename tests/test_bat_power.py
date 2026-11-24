"""Bat tracking vs next season's power, and the Arozarena breakdown: the report's numbers against the saved outputs."""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BP = json.loads((ROOT / "reports" / "outputs" / "bat_power_summary.json").read_text())
AZ = json.loads((ROOT / "reports" / "outputs" / "arozarena_swing_summary.json").read_text())
REPORT = (ROOT / "reports" / "2026-arozarena-swing-breakdown.md").read_text()


def test_league_models_match_the_report():
    # the batted-ball model is picked on the training pairs (cross-validation), never on the test pairs
    assert BP["n_train"] == 199 and BP["n_test"] == 194
    assert BP["best_ball"] == min(BP["cv_train"], key=BP["cv_train"].get) == "ISO + barrel rate"
    assert f"{BP['ball']['ISO + 90th-pct EV']['r2_out']:.2f}" == "0.37" and f"{BP['ball']['ISO + barrel rate']['r2_out']:.2f}" == "0.35"
    assert all(v["gain"] < 0.001 for v in BP["adds"].values())       # nothing moves the error by 0.001 ISO
    assert BP["adds"]["bat_speed"]["gain_lo"] > 0 and "about 1% of the error" in REPORT
    assert f"{BP['stability']['bat_speed']['r']:.2f}" == "0.94" and "0.94" in REPORT
    c = BP["bat_speed_change"]
    assert c["n"] == 151 and c["lo"] < 0 < c["hi"] and "-0.008 to +0.004" in REPORT


def test_projection_range_matches_the_report():
    p = BP["projections"]["668227"]
    vals = sorted(round(p[k], 3) for k in ("train_2024_25", "both_pairs", "pair_2025_26"))
    assert f".{str(vals[0])[2:]} to .{str(vals[-1])[2:]}" in REPORT
    assert round(p["iso_2026"], 3) == 0.203


def test_video_sample_and_tests_match_the_report():
    assert AZ["clips"] == 73 and AZ["measured"] == 23 and "23 of the 73" in REPORT
    assert AZ["tests"]["down_to_contact_ms"]["diff"] == 0
    assert round(AZ["tests"]["head_drop"]["p"], 3) <= 0.01


def test_every_measured_swing_links_its_clip():
    t = pd.read_json(ROOT / "reports" / "outputs" / "arozarena_swings.json")
    assert t[t.measured].page.str.startswith("https://www.mlb.com/video/").all()


def test_a_truncated_pa_is_not_a_plate_appearance():
    # the inning can end on the bases mid-at-bat; Statcast logs that as "truncated_pa", MLB doesn't count it
    from baseball.evaluation import bat_power as BPM
    d = pd.DataFrame({"batter": [1, 1, 1, 1], "events": ["single", "strikeout", "truncated_pa", None],
                      "description": ["hit_into_play", "swinging_strike", "ball", "ball"], "woba_denom": [1, 1, None, None],
                      "launch_speed": [100.0, None, None, None], "launch_angle": [20.0, None, None, None],
                      "launch_speed_angle": [4, None, None, None], "bat_speed": [72.0, 70.0, None, None],
                      "swing_length": [7.2, 7.0, None, None], "attack_angle": [10.0, 8.0, None, None],
                      "release_speed": [95.0] * 4, "estimated_woba_using_speedangle": [0.5, None, None, None],
                      "game_type": ["R"] * 4, "game_date": ["2026-05-01"] * 4, "season": [2026] * 4})
    t = BPM.seasons_table(d).set_index("batter")
    assert t.loc[1, "pa"] == 2 and t.loc[1, "ab"] == 2 and t.loc[1, "k_rate"] == 0.5


def test_lab_plate_appearances_are_mlb_counts():
    # MLB Stats API season totals, pulled Nov. 24, 2026 (the swing-lab hitters)
    official = {(668227, 2024): 648, (668227, 2025): 709, (668227, 2026): 670, (673548, 2024): 585, (673548, 2025): 651,
                (673548, 2026): 634, (665862, 2024): 621, (665862, 2025): 531, (665862, 2026): 532, (664040, 2024): 425,
                (664040, 2025): 553, (664040, 2026): 656}
    s = pd.read_json(ROOT / "reports" / "outputs" / "bat_power_seasons.json")
    for (b, y), pa in official.items():
        assert s[(s.batter == b) & (s.season == y)].pa.iloc[0] == pa, (b, y)
    assert "| Plate appearances, at-bats | 648, 549 | 709, 613 | 670, 572 |" in REPORT
