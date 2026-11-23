"""The swing labs added after Arozarena and Suzuki: Jazz Chisholm Jr. and Brandon Lowe. The saved outputs, the clips
removed by eye and the packet's data are pinned to each other and to the numbers the page and the log quote."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "outputs"
DATA = json.loads((ROOT / "docs" / "offseason" / "data.json").read_text())
TEMPLATE = (ROOT / "docs" / "offseason_template.html").read_text(encoding="utf-8")
BP = json.loads((OUT / "bat_power_summary.json").read_text())


def _load(name):
    return (json.loads((OUT / f"{name}_swing_summary.json").read_text()), json.loads((OUT / f"{name}_swings.json").read_text()),
            json.loads((OUT / f"{name}_excluded_by_eye.json").read_text())["excluded"],
            [e["offset_frames"] for e in json.loads((OUT / f"{name}_contact_by_eye.json").read_text())["offsets"]])


def test_chisholm_sample_is_too_small_to_test_2026():
    s, sw, ex, eye = _load("chisholm")
    assert s["clips"] == 74 and s["measured"] == 12 and len(ex) == 2
    assert [r["n"] for r in s["by_season"]] == [2, 6, 4]
    assert all("diff" not in t for t in s["tests"].values())          # 2026 has 4 swings, a test needs 5 a side
    assert (min(eye), max(eye), len(eye)) == (4, 7, 7)
    hr = s["statcast_hr_medians"]
    assert [hr[y]["n"] for y in ("2024", "2025", "2026")] == [24, 31, 19]
    assert [round(hr[y]["launch_speed"], 1) for y in ("2024", "2025", "2026")] == [104.9, 105.7, 105.3]
    assert [round(hr[y]["bat_speed"], 1) for y in ("2024", "2025", "2026")] == [74.8, 76.8, 75.5]


def test_lowe_sample_tests_and_detection_limits():
    s, sw, ex, eye = _load("lowe")
    assert s["clips"] == 87 and s["measured"] == 24 and len(ex) == 9
    assert [r["n"] for r in s["by_season"]] == [6, 2, 16]
    t = s["tests"]
    assert round(t["hip_lead_ms"]["diff"], 1) == -16.7 and 0.04 < t["hip_lead_ms"]["p"] < 0.05     # one frame; not robust to five tests
    assert all(t[c]["p"] > 0.15 for c in ("down_to_contact_ms", "lift_to_contact_ms", "head_drop", "shoulder_tilt"))
    d = s["detectable_change"]
    assert round(d["down_to_contact_ms"]) == 74 and round(d["hip_lead_ms"]) == 20 and round(d["shoulder_tilt"], 1) == 8.3
    assert (min(eye), max(eye), len(eye)) == (5, 7, 7)
    hr = s["statcast_hr_medians"]
    assert [hr[y]["n"] for y in ("2024", "2025", "2026")] == [21, 31, 35]
    assert [round(hr[y]["launch_speed"], 1) for y in ("2024", "2025", "2026")] == [104.4, 105.3, 104.5]


def test_clips_removed_by_eye_are_not_measured_and_have_reasons():
    for name in ("chisholm", "lowe"):
        s, sw, ex, eye = _load(name)
        measured = {r["play_id"] for r in sw if r["measured"]}
        ids = {e["play_id"] for e in ex}
        assert not ids & measured and ids <= {r["play_id"] for r in sw}
        assert all("checked by eye, Nov. 23, 2026" in e["reason"] and e["page"].startswith("https://www.mlb.com/video/") for e in ex)
        assert all(r["page"].startswith("https://www.mlb.com/video/") for r in sw if r["measured"])
    lowe = _load("lowe")[2]
    assert sum("Steinbrenner Field" in e["reason"] for e in lowe) == 6 and sum("umpire" in e["reason"] for e in lowe) == 1


def test_packet_labs_match_the_saved_outputs():
    for name in ("chisholm", "lowe"):
        s, sw, ex, eye = _load(name)
        L = DATA["labs"][name]
        assert L["clips"] == s["clips"] and L["measured"] == s["measured"] and L["excluded_by_eye"] == len(ex)
        assert L["by_season"] == s["by_season"] and L["stand"] == "L"
        assert {k: v for k, v in L["tests"].items()} == s["tests"]
        assert L["eye"] == dict(n=len(eye), lo=min(eye), hi=max(eye))
    assert DATA["labs"]["chisholm"]["iso_range"] == [0.16, 0.167] and DATA["labs"]["chisholm"]["p_match"] == [0.42, 0.49]
    assert DATA["labs"]["lowe"]["iso_range"] == [0.194, 0.21] and DATA["labs"]["lowe"]["p_match"] == [0.15, 0.27]


def test_added_projections_leave_the_first_two_alone():
    p = BP["projections"]
    assert round(p["668227"]["pair_2025_26"], 4) == 0.1693 and round(p["673548"]["train_2024_25"], 4) == 0.1913
    assert round(p["665862"]["iso_2026"], 3) == 0.168 and round(p["664040"]["iso_2026"], 3) == 0.233


def test_gaps_with_mlbtr_and_the_cards():
    b = {x["rank"]: x for x in DATA["board"]}
    assert (b[20]["name"], b[20]["my_aav"], b[20]["mlbtr_aav"]) == ("Jazz Chisholm Jr.", 25.5, 20.0)
    assert (b[11]["name"], b[11]["my_aav"], b[11]["mlbtr_aav"]) == ("Brandon Lowe", 27.5, 23.0)
    assert "${card(20," in TEMPLATE and "${card(11," in TEMPLATE
    assert "chisholm: {foot: true" in TEMPLATE and "lowe: {foot: true" in TEMPLATE
    assert "On Jazz Chisholm Jr. I'd stop at four years and $87M" in TEMPLATE
    assert "Too few 2026 swings to tell." in TEMPLATE
