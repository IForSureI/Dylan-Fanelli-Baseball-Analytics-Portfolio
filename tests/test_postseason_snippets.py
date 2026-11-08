"""2026 postseason snippets: the saved numbers agree with the official record and stay baseball-sane."""
import json
from pathlib import Path

import pytest

F = Path(__file__).resolve().parents[1] / "reports" / "2026-postseason-snippets" / "findings.json"


@pytest.fixture(scope="module")
def f():
    if not F.exists():
        pytest.skip("postseason snippets not built")
    return json.loads(F.read_text())


def test_every_postseason_game_is_in(f):
    assert f["games"] == 40          # MLB Stats API schedule: 40 completed 2026 postseason games


def test_world_series_matches_the_record(f):
    ws = f["world_series"]
    assert ws["mil_wins"] == 4 and len(ws["games"]) == 5
    assert [g["winner"] for g in ws["games"]] == ["MIL", "MIL", "MIL", "TB", "MIL"]


def test_numbers_stay_sane(f):
    assert 0.25 < f["team_contact"]["league_xwoba"] < 0.36
    assert 93 < f["velo_leaders"]["league_fb_velo"] < 98
    assert 85 < f["ev_leaders"]["league_ev"] < 91
    assert all(abs(r["wpa"]) < 3 for r in f["hitter_wpa"]["top5"] + f["pitcher_wpa"]["top5"])
    # Houston's starters got two outs in each of its two games (official box scores)
    hou = [t for t in f["starter_depth"]["teams"] if t["team"] == "HOU"][0]
    assert hou["games"] == 2 and hou["outs"] == 2
