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


# ---------------------------------------------------------------- filter cubes: "all" reproduces the published charts

def _agg(cube, keep=lambda d: True):
    from baseball.postseason_web import aggregate
    return aggregate(cube, keep)


def _close(a, b, tol=0.0011):
    return a is not None and b is not None and abs(a - b) <= tol


def test_cubes_reproduce_charts_at_all(page):
    _, d, f = page
    cu, ch = d["cubes"], d["charts"]
    h = _agg(cu["hpa"])
    top = sorted(h.items(), key=lambda kv: -kv[1]["wpa"])[:20]
    assert [k for k, _ in top] == [r["id"] for r in ch["hitter_wpa"]]
    assert all(_close(v["wpa"], r["v"]) and v["pa"] == r["right"] for (_, v), r in zip(top, ch["hitter_wpa"]))
    p = _agg(cu["ppa"])
    top = sorted(p.items(), key=lambda kv: -kv[1]["wpa"])[:20]
    assert [k for k, _ in top] == [r["id"] for r in ch["pitcher_wpa"]]
    # chart 5: results vs contact, min 25 PA in the wOBA denominator
    x = {k: (v["x"] / v["dn"], v["woba"] / v["dn"]) for k, v in h.items() if v["dn"] >= f["hitter_xwoba_woba"]["min_pa"]}
    assert set(x) == {r["id"] for r in ch["hitter_x"]}
    assert all(_close(x[r["id"]][0], r["x"]) and _close(x[r["id"]][1], r["y"]) for r in ch["hitter_x"])
    # chart 6: swing decisions, hitters with 25+ PA
    hp = _agg(cu["hp"])
    sw = {k: (v["osw"] / v["o"], v["wh"] / v["sw"]) for k, v in hp.items() if h.get(k, {}).get("pa", 0) >= 25 and v["o"] and v["sw"]}
    assert set(sw) == {r["id"] for r in ch["swing"]}
    assert all(_close(sw[r["id"]][0], r["x"]) and _close(sw[r["id"]][1], r["y"]) for r in ch["swing"])
    lg = {c: sum(v[c] for v in hp.values()) for c in ("o", "osw", "sw", "wh")}
    assert _close(lg["osw"] / lg["o"], d["league"]["chase"]) and _close(lg["wh"] / lg["sw"], d["league"]["whiff"])
    # chart 7: pitchers, min 100 pitches
    pp = _agg(cu["pp"])
    px = {k: (v["wh"] / v["sw"], p[k]["x"] / p[k]["dn"]) for k, v in pp.items()
          if v["n"] >= f["pitcher_whiff_xwoba"]["min_pitches"] and v["sw"] and p.get(k, {}).get("dn")}
    assert set(px) == {r["id"] for r in ch["pitcher_x"]}
    assert all(_close(px[r["id"]][0], r["x"]) and _close(px[r["id"]][1], r["y"]) for r in ch["pitcher_x"])
    # charts 8 and 9: velocity and exit velocity leaders
    v = sorted(((k, w["v"] / w["fb"], w["vmax"]) for k, w in pp.items() if w["fb"] >= 15), key=lambda t: -t[1])[:20]
    assert [k for k, *_ in v] == [r["id"] for r in ch["velo"]] and all(_close(a, r["v"], 0.051) and b == r["right"] for (_, a, b), r in zip(v, ch["velo"]))
    e = sorted(((k, w["ev"] / w["bip"], w["evmax"]) for k, w in hp.items() if w["bip"] >= 15), key=lambda t: -t[1])[:20]
    assert [k for k, *_ in e] == [r["id"] for r in ch["ev"]] and all(_close(a, r["v"], 0.051) and b == r["right"] for (_, a, b), r in zip(e, ch["ev"]))
    # chart 2: clubs; chart 10: starters
    tf, ta = _agg(cu["tfor"]), _agg(cu["tagainst"])
    for r in ch["team_contact"]:
        assert _close(tf[r["team"]]["x"] / tf[r["team"]]["n"], r["x"]) and _close(ta[r["team"]]["x"] / ta[r["team"]]["n"], r["y"])
    s = _agg(cu["starters"])
    for r in ch["starters"]:
        assert s[r["team"]]["g"] == r["games"] and _close(s[r["team"]]["outs"] / s[r["team"]]["g"] / 3, r["v"], 0.006)


def test_cubes_cut_by_round(page):
    """A filter is a real cut: the rounds partition the plate appearances, and only the two finalists play in the last."""
    _, d, f = page
    by_round = [sum(v["pa"] for v in _agg(d["cubes"]["hpa"], lambda c, r=r: c["r"] == r).values()) for r in range(4)]
    assert sum(by_round) == f["plate_appearances"] and all(by_round)
    teams = {k for k, v in _agg(d["cubes"]["tfor"], lambda c: c["r"] == 3).items() if v["n"]}
    assert teams == {"MIL", "TB"}


def test_one_filter_row_light_only(page):
    """One filter row scopes every chart (not one per chart), and the page is light only."""
    html, _, _ = page
    assert html.count('class="filterbar"') == 1 and "prefers-color-scheme" not in html and 'data-theme="dark"' not in html
