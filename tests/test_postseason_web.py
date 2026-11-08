"""Interactive postseason snippets (docs/postseason.html): the page's numbers match the published charts'
findings.json, every charted point has a breakdown, and the page is one self-contained file."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "postseason.html"
F = ROOT / "reports" / "2026-postseason-snippets" / "findings.json"


@pytest.fixture(scope="module")
def page():
    if not PAGE.exists() or not F.exists():
        pytest.skip("interactive postseason page not built")
    html = PAGE.read_text()
    blob = re.search(r"const DATA = (\{.*?\});\n", html, re.S).group(1)
    return html, json.loads(blob), json.loads(F.read_text())


def test_totals_match_findings(page):
    _, d, f = page
    for k in ("games", "pitches", "plate_appearances", "first_date", "last_date"):
        assert d["meta"][k] == f[k]
    assert d["league"]["xwoba"] == f["team_contact"]["league_xwoba"]
    assert d["league"]["chase"] == f["hitter_swing_decisions"]["league_chase"]


def test_world_series_matches_findings(page):
    _, d, f = page
    ws = d["charts"]["ws"]
    assert [g["winner"] for g in ws] == [g["winner"] for g in f["world_series"]["games"]]
    assert [(g["as"], g["hs"]) for g in ws] == [(g["away_runs"], g["home_runs"]) for g in f["world_series"]["games"]]
    assert all(0 <= p[0] <= 1 for g in ws for p in g["pts"])


def test_leaders_match_findings(page):
    _, d, f = page
    c, H, P = d["charts"], d["hitters"], d["pitchers"]
    for got, want in zip(c["hitter_wpa"], f["hitter_wpa"]["top5"]):
        assert want["lab"].startswith(H[got["id"]]["short"]) and abs(got["v"] - want["wpa"]) < 0.0015
        assert got["right"] == want["pa"]
    for got, want in zip(c["pitcher_wpa"], f["pitcher_wpa"]["top5"]):
        assert want["lab"].startswith(P[got["id"]]["short"]) and abs(got["v"] - want["wpa"]) < 0.0015
        assert got["right"] == want["bf"]
    assert abs(c["velo"][0]["v"] - f["velo_leaders"]["top5"][0]["velo"]) < 0.051
    assert abs(c["ev"][0]["v"] - f["ev_leaders"]["top5"][0]["ev"]) < 0.051
    assert len(c["hitter_x"]) == f["hitter_xwoba_woba"]["n"]
    assert len(c["swing"]) == f["hitter_swing_decisions"]["n"]
    assert len(c["pitcher_x"]) == f["pitcher_whiff_xwoba"]["n"]


def test_clubs_match_findings(page):
    _, d, f = page
    for t in f["team_contact"]["teams"]:
        m = d["teams"][t["bat_team"]]
        assert abs(m["x_for"] - t["x_for"]) < 0.0015 and abs(m["x_against"] - t["x_against"]) < 0.0015
    assert [t["team"] for t in d["charts"]["starters"]] == [t["team"] for t in f["starter_depth"]["teams"]]


def test_every_point_has_a_breakdown(page):
    _, d, _ = page
    c = d["charts"]
    for key, who in (("hitter_wpa", "hitters"), ("hitter_x", "hitters"), ("swing", "hitters"), ("ev", "hitters"),
                     ("pitcher_wpa", "pitchers"), ("pitcher_x", "pitchers"), ("velo", "pitchers")):
        assert c[key] and all(r["id"] in d[who] for r in c[key]), key
    for h in d["hitters"].values():
        assert h["pa"] == sum(r["pa"] for r in h["rounds"])
    for p in d["pitchers"].values():
        assert p["bf"] == sum(r["pa"] for r in p["rounds"]) and p["arsenal"]
    for t in d["teams"].values():
        assert t["w"] + t["l"] == t["games"] and len(t["starts"]) == t["games"]


def test_page_is_self_contained(page):
    html, _, _ = page
    assert not re.search(r"<script[^>]+src=|@import|url\(http", html)  # no outside code or styles
    links = re.findall(r'<link[^>]+href="([^"]+)"', html)
    assert all(h.startswith(("https://fonts.googleapis.com", "https://fonts.gstatic.com")) for h in links)  # fonts only
