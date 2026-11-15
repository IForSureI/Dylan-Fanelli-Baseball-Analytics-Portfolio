"""The development plan page against its saved table (reports/outputs/idp-gilbert-2026.json), the saved
table against the engine's own rules, and the table writer on the fictional plan. Only the last test reads
real pitches, and it is skipped when the pitch data is not on the machine."""
import json
from datetime import date
from pathlib import Path

import pytest
import yaml

from baseball.development import idp

ROOT = Path(__file__).resolve().parents[1]
SAVED = ROOT / "reports" / "outputs" / "idp-gilbert-2026.json"
PLAN = ROOT / "examples" / "idp-gilbert-2026.yaml"
REPORT = ROOT / "reports" / "2026-development-plan.md"


@pytest.fixture(scope="module")
def saved():
    return json.loads(SAVED.read_text())


def test_summary_on_the_fictional_plan_matches_progress():
    path = ROOT / "examples" / "idp-fictional.yaml"
    plan = idp.load_plan(path)
    pitches = idp.fictional_pitches(plan.period_start.year)
    s = idp.summary(path, "2027-07-01", pitches)
    json.dumps(s)                                             # plain types only
    assert s["as_of"] == "2027-07-01" and s["data_source"] == "fictional"
    assert s["first_pitch_date"] >= s["period_start"] and s["last_pitch_date"] <= s["as_of"]
    days = [date.fromisoformat(d) for d in pitches["game_date"]]
    assert s["pitches"] == sum(plan.period_start <= d <= date(2027, 7, 1) for d in days)
    assert sorted({r["as_of"] for r in s["rows"]}) == ["2027-05-15", "2027-07-01"]   # checkpoints up to as_of only
    direct = idp.progress(plan, pitches, "2027-07-01")
    last = [r for r in s["rows"] if r["as_of"] == "2027-07-01"]
    assert [r["verdict"] for r in last] == direct["verdict"].tolist()
    assert [r["n"] for r in last] == direct["n"].tolist()
    assert [r["value"] for r in last] == pytest.approx(direct["value"].tolist(), abs=1e-4)
    assert [b["value"] for b in s["baselines"]] == [pr.baseline.value for pr in plan.priorities]


def test_saved_table_is_the_plan_file(saved):
    d = yaml.safe_load(PLAN.read_text())
    assert saved["player"] == d["player"] and saved["label"] == d["label"]
    assert saved["period_end"] == str(d["period_end"]) == saved["as_of"]
    assert saved["power_warnings"] == idp.power_check(d)
    for b, p in zip(saved["baselines"], d["priorities"]):
        assert (b["value"], b["se"], b["n"]) == (p["baseline"]["value"], p["baseline"]["se"], p["baseline"]["n"])
    for r in saved["rows"]:
        p = d["priorities"][r["priority"] - 1]
        assert (r["target"], r["floor"], r["target_date"]) == (p["target"], p["floor"], str(p["target_date"]))


def test_saved_verdicts_follow_from_the_saved_numbers(saved):
    """Recompute each verdict and guard status from the row's own value, SE and n."""
    plan = idp.load_plan(PLAN)
    for r in saved["rows"]:
        pr = plan.priorities[r["priority"] - 1]
        v = idp.verdict(pr.baseline.value, pr.target, r["value"], r["se"], r["n"], pr.floor, r["expected_fraction"],
                        pr.baseline.se)
        assert v["verdict"] == r["verdict"], r
        g = idp.guard_status(pr.guard, {"value": r["guard_value"], "lo": r["guard_lo"], "hi": r["guard_hi"],
                                        "n": r["guard_n"]})
        assert g == r["guard_status"], r


def test_report_matches_the_saved_table(saved):
    rep = REPORT.read_text()
    assert f"as of {saved['as_of']}" in rep
    assert f"{saved['pitches']:,} regular-season pitches in {saved['games']} games" in rep
    assert f"{saved['first_pitch_date']} to {saved['last_pitch_date']}" in rep
    grid = [ln for ln in rep.split("\n") if ln.startswith("| ")]
    for r in saved["rows"]:
        d = 2 if r["metric"].endswith(", ft") else 1
        verdict = r["verdict"].replace("_", " ")
        row = next(ln for ln in grid if ln.startswith(f"| {r['priority']}. ") and "baseline" in ln)
        cell = row.split("|")[2 + ["2026-05-15", "2026-07-01", "2026-09-27"].index(r["as_of"])]
        assert f"**{verdict}:**" in cell, (r["priority"], r["as_of"])
        assert f"{r['n']:,} {r['n_unit']}" in cell
        if r["verdict"] != "insufficient":
            assert f"{r['value']:.{d}f} ({r['lo']:.{d}f} to {r['hi']:.{d}f})" in cell
        guard = next(ln for ln in grid if ln.startswith(f"| {r['priority']}. ") and "baseline" not in ln)
        gcell = guard.split("|")[2 + ["2026-05-15", "2026-07-01", "2026-09-27"].index(r["as_of"])]
        assert r["guard_status"] in gcell
        if r["guard_status"] == "insufficient":
            assert f"{r['guard_n']:,} pitches" in gcell
        else:
            assert f"{r['guard_value']:.1f} ({r['guard_lo']:.1f} to {r['guard_hi']:.1f})" in gcell
    w = saved["power_warnings"]
    assert len(w) == 1 and w[0].startswith("priority 3") and "2.68" in w[0] and "9.47" in w[0]
    assert "2.68 points" in rep and "is 9.47" in rep
    last = {r["priority"]: r for r in saved["rows"] if r["as_of"] == saved["as_of"]}
    assert f"only a change of {last[3]['detectable_change']:.1f} points or more is detectable" in rep
    assert f"{100 * last[1]['fraction_closed']:.0f}% of the gap closed" in rep


def test_engine_reproduces_the_saved_table_when_the_pitch_data_is_here(saved):
    if not (ROOT / "data" / "seq").exists():
        pytest.skip("the pitch data isn't published")
    try:
        now = idp.summary(PLAN)
    except (FileNotFoundError, OSError):
        pytest.skip("the 2026 pitch data isn't on this machine")
    assert now == saved
