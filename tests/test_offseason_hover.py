"""The packet's hover cards and type: every number that matters carries a card (data-hv) that breaks it down,
the cards read only data.json, and the page uses Baseball Savant's own typography (Roboto Condensed from Google
Fonts, Savant's Helvetica Neue heading stack). The browser check runs when node and Playwright are on the machine."""
import functools
import os
import http.server
import json
import re
import shutil
import subprocess
import threading
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
TPL = (ROOT / "docs" / "offseason_template.html").read_text(encoding="utf-8")
PAGE = (ROOT / "docs" / "offseason" / "index.html").read_text(encoding="utf-8")
D = json.loads((ROOT / "docs" / "offseason" / "data.json").read_text())


def test_savant_type_from_google_fonts_only():
    links = re.findall(r'<link rel="stylesheet" href="([^"]+)"', PAGE)
    assert links and all(h.startswith("https://fonts.googleapis.com/") for h in links)
    assert any("family=Roboto+Condensed" in h for h in links)
    css = PAGE[PAGE.index("<style>"):PAGE.index("</style>")]
    assert '--text:"Roboto Condensed"' in css and '--display:"Helvetica Neue",Helvetica,Arial' in css
    assert "Bricolage" not in PAGE and "Be Vietnam" not in PAGE
    assert "font-variant-numeric:tabular-nums" in css   # tables keep tabular numerals


def test_hover_targets_on_board_bubbles_catchers_and_swings():
    # board rows, the MLBTR / my / signed marks, and the chance bubble
    assert '<tr class="r" tabindex="0" aria-expanded="${open}" data-rank="${b.rank}"${hvM("b", b.rank)}>' in TPL
    for k in ('hvM("bm", b.rank)', 'hvA("bp", b.rank)', 'hvM("bs", b.rank)'):
        assert k in TPL, k
    # percentile bubbles: Savant's, mine, framing and the called-player ranks
    assert '<div class="pr"${r.hv || ""}>' in TPL
    for k in ('hvA("sv", b.rank, r.label)', 'hvA("lg", rank, r.key)', 'hvA("c", fc.id, s)', 'hvA("cr", rank, "wwar")'):
        assert k in TPL, k
    # catcher rows and the scatter dots
    assert 'return `<tr${hvA("c", c.id, s)}>' in TPL and 'hvM("c", c.id, s)' in TPL
    assert "<title>" not in TPL[TPL.index("function renderSpread"):TPL.index("function bindCatchers")]
    # swing-lab rows, measures, Statcast seasons, tiles and the skeleton
    for k in ('hvA("ls", state.lab, s.play_id)', 'hvA("lm", state.lab, key)', 'hvA("lst", state.lab, s.season)', 'hvA("lt", state.lab, 0)', 'hvA("lk", state.lab)'):
        assert k in TPL, k
    # every kind used has a card writer
    kinds = set(re.findall(r'hv[AM]\("([a-z]+)"', TPL))
    body = TPL[TPL.index("const HV = {"):TPL.index("function hvShow")]
    for k in kinds:
        assert re.search(rf"\n  {k}\(", body), k


def test_hover_card_behaviour_and_house_rules():
    js = TPL[TPL.index("function hvShow"):TPL.index("/* ---------------- print")]
    assert '"Escape"' in js and "pointerdown" in js and "focusin" in js and "hvEl.contains(e.target)" in js
    css = TPL[TPL.index("#hv{"):TPL.index("@media print{#hv")]
    assert "position:fixed" in css and "#hv.up" in css and "border-left" not in css
    assert 'id="hv" role="tooltip"' in TPL


def test_hover_fields_match_their_sources():
    from baseball.ingest import savant_percentiles as SP
    for b in D["board"]:
        if not b.get("savant"):
            continue
        kind = b["savant"]["kind"]
        prev = {r["label"]: r for r in (SP.card(b["mlbam"], kind, 2025) or {"rows": []})["rows"]}
        for r in b["savant"]["rows"]:
            p = prev.get(r["label"])
            assert r["value25"] == (p and p["value"]) and r["pctl25"] == (p and p["pctl"]), (b["name"], r["label"])
    bps = pd.read_json(ROOT / "reports" / "outputs" / "bat_power_seasons.json")
    for b in D["board"]:
        for r in (b.get("league") or {}).get("rows", []):
            s = bps[(bps.batter == b["mlbam"]) & (bps.season == 2025)]
            if r["value25"] is not None:
                assert abs(s[r["key"]].iloc[0] - r["value25"]) < 1e-4 and s.pa.iloc[0] >= 502
    saved = {s["play_id"]: s["home_team"] for s in json.loads((ROOT / "reports/outputs/arozarena_swings.json").read_text())}
    assert all(s["home_team"] == saved[s["play_id"]] for s in D["labs"]["arozarena"]["swings"])
    assert all(s.get("home_team") for L in D["labs"].values() for s in L["swings"])


NODE_SCRIPT = r"""
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
  const out = {};
  const card = async (view, key) => {
    await p.evaluate(v => { location.hash = v; }, view); await p.waitForTimeout(250);
    out[key] = await p.evaluate(k => { const el = document.querySelector(`#app [data-hv="${k}"]`); if (!el) return null;
      el.dispatchEvent(new MouseEvent('mouseover', { bubbles: true })); const h = document.getElementById('hv');
      return h.classList.contains('on') ? h.innerText : ''; }, key);
  };
  await p.goto(process.argv[1] + '#board', { waitUntil: 'networkidle' });
  for (const [v, k] of JSON.parse(process.argv[2])) await card(v, k);
  console.log(JSON.stringify(out)); await b.close();
})();
"""


def _browser_cards(keys):
    return _run_node(NODE_SCRIPT, "offseason/", json.dumps(keys))


def _run_node(script, page, *args):
    """Serve docs/ locally and run a Playwright script on the page; skip when node or Playwright isn't here."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node isn't on this machine")
    root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip() if shutil.which("npm") else ""
    if subprocess.run([node, "-e", "require('playwright')"], env={**os.environ, "NODE_PATH": root}, capture_output=True).returncode:
        pytest.skip("Playwright isn't installed for node")
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    handler = functools.partial(Quiet, directory=str(ROOT / "docs"))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        r = subprocess.run([node, "-e", script, f"http://127.0.0.1:{srv.server_port}/{page}", *args],
                           env={**os.environ, "NODE_PATH": root}, capture_output=True, text=True, timeout=180)
    finally:
        srv.shutdown()
    if r.returncode:
        if re.search(r"browserType\.launch|Executable doesn't exist|Host system is missing dependencies", r.stderr):
            pytest.skip("the browser didn't start: " + r.stderr[-300:])
        pytest.fail("the browser check failed: " + r.stderr[-1500:])   # a page or script error is a failure, not a skip
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_hover_numbers_equal_data_json():
    b = next(x for x in D["board"] if x["rank"] == 8)
    sv = next(r for r in b["savant"]["rows"] if r["label"] == "xERA")
    c = next(x for x in D["framing"]["catchers"] if x["name"] == "Patrick Bailey")
    sw = next(s for s in D["labs"]["arozarena"]["swings"] if s["measured"])
    keys = [["board", "b|8"], ["board", "bp|8"], ["players", "sv|8|xERA"], ["players", "bw|8"],
            ["catchers", f"c|{c['id']}|2026"], ["swing", f"ls|arozarena|{sw['play_id']}"]]
    got = _browser_cards(keys)
    row = got["b|8"]
    assert "$16.0M" in row and "$24.8M" in row and "95%" in row and b["mlbtr"] in row
    for w in b["war"]:
        assert f"{w:.1f}" in row
    assert f"{D['backtest']['sigma']:.3f}" in got["bp|8"] and f"{D['backtest']['brier']:.3f}" in got["bp|8"]
    s = got["sv|8|xERA"]
    assert f"{sv['value']:.2f}" in s and f"{sv['value25']:.2f}" in s and f"{sv['pctl']}th" in s and f"{sv['pctl25']}th" in s
    assert str(D["savant"]["pools"]["pitcher"]) in s
    w = got["bw|8"]
    assert all(f"{x:.2f}" in w for x in b["war"])
    k = got[f"c|{c['id']}|2026"]
    for y, v in c["seasons"].items():
        assert f"{v['takes']:,}" in k and f"{v['adj']:+.1f}" in k
    h = got[f"ls|arozarena|{sw['play_id']}"]
    assert f"{sw['launch_speed']:.1f}" in h and f"{sw['bat_speed']:.1f}" in h and sw["home_team"] in h
    assert f"{round(sw['down_to_contact_ms'])} ms" in h and f"{sw['head_drop']:.2f}" in h and str(int(sw["contact_frame"])) in h
