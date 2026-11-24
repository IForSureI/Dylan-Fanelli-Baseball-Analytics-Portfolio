"""The packet's board filters and swing-lab timeline, checked in a browser: a role filter keeps players who signed
before my calls, "Unsigned" counts everyone still unsigned, and the timeline marks contact where it is on the slider.
Runs when node and Playwright are on the machine."""
import json

from tests.test_offseason_hover import D, _run_node

SCRIPT = r"""
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
  const out = {};
  await p.goto(process.argv[1] + '#board', { waitUntil: 'networkidle' });
  for (const g of ['sp', 'rp', 'bat']) for (const s of ['all', 'signed', 'open']) {
    await p.click(`#app .seg[data-k=group] button[data-v=${g}]`); await p.click(`#app .seg[data-k=status] button[data-v=${s}]`);
    out[g + '|' + s] = await p.$$eval('#rows tr.r', r => r.map(x => +x.dataset.rank));
  }
  await p.click('#app .seg[data-k=group] button[data-v=all]');
  out['all|open'] = await p.$$eval('#rows tr.r', r => r.map(x => +x.dataset.rank));
  await p.evaluate(() => { location.hash = 'swing'; }); await p.waitForTimeout(300);
  out.tick = await p.evaluate(() => { const r = document.getElementById('scrub').getBoundingClientRect(),
    t = document.querySelector('.tick-labels .at').getBoundingClientRect(); return (t.left + t.width / 2 - r.left) / r.width; });
  out.valuetext = await p.$eval('#scrub', e => e.getAttribute('aria-valuetext'));
  console.log(JSON.stringify(out)); await b.close();
})();
"""


def test_filters_and_timeline_in_a_browser():
    got = _run_node(SCRIPT, "offseason/")
    group = lambda b: "rp" if b["reliever"] else ("sp" if b["pos"].endswith("HP") else "bat")
    known = [b for b in D["board"] if b["mlbam"] or group(b) == "bat"]
    signed = lambda b: b["actual_aav"] is not None or b["signed"]
    for g in ("sp", "rp", "bat"):
        assert sorted(got[f"{g}|all"]) == sorted(b["rank"] for b in known if group(b) == g)
        assert sorted(got[f"{g}|signed"]) == sorted(b["rank"] for b in known if group(b) == g and signed(b))
    assert got["rp|signed"] and got["sp|signed"]                          # Bednar, Phillips; Skubal, Gray, May
    assert sorted(got["all|open"]) == sorted(b["rank"] for b in D["board"] if not signed(b))
    L = D["labs"]["arozarena"]["traj"]
    assert abs(got["tick"] - L["pre"] / (L["pre"] + L["post"])) < 0.03   # Contact sits at contact on the slider
    assert got["valuetext"] == "contact"
