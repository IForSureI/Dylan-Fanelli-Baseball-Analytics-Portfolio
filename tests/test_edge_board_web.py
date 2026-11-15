"""The Edge Board dashboard (docs/edge-board.html): the generator's logic on small made-up tables, and the built
page against the saved run it was built from."""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from baseball.edge import board_web as bw
from baseball.evaluation.reliever import grade_from_percentile, percentile

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "edge-board.html"
TEMPLATE = ROOT / "baseball" / "edge" / "board_web.html"
SAVED = ROOT / "data" / "edge" / "2026"
OUTPUTS = ROOT / "reports" / "outputs"


# ------------------------------------------------------------------ small made-up run

def _table(n_ff=30, n_cu=20, n_kc=8, n_sv=3, seed=3) -> pd.DataFrame:
    """A projection table shaped like the saved one: pitcher x pitch type."""
    rng = np.random.default_rng(seed)
    rows, pid = [], 1000
    for pt, name, n in (("FF", "4-Seam Fastball", n_ff), ("CU", "Curveball", n_cu), ("KC", "Knuckle Curve", n_kc), ("SV", "Slurve", n_sv)):
        for _ in range(n):
            pid += 1
            swings = int(rng.integers(50, 400))
            whiffs = int(rng.integers(5, swings // 2))
            x = float(rng.uniform(10, 45))
            w = 100 * whiffs / swings
            rows.append({"pitcher": float(pid), "player_name": f"Last{pid}, First", "p_throws": "L" if pid % 3 == 0 else "R", "season": 2026.0,
                         "pitch_type": pt, "pitch_name": name, "swings": swings, "whiffs": whiffs, "velo": 90.0, "ivb_in": 10.0,
                         "hb_arm_in": 5.0, "d_velo": 0.0, "whiff_pct": w, "x_whiff_pct": x, "gap": w - x, "whiff_lo": w - 8, "whiff_hi": w + 8,
                         "gap_clear": abs(w - x) > 8, "proj_whiff_pct": 0.6 * w + 0.4 * x, "proj_change": 0.4 * (x - w),
                         "proj_basis": "two seasons" if pid % 2 else "one season", "whiff_pct_prior": w if pid % 2 else np.nan})
    return pd.DataFrame(rows)


def _outputs(folder: Path, grades_json: dict | None = None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "edge-2026.json").write_text(json.dumps({
        "stuff_model_auc": {"2026": 0.6332}, "gap_persistence": {"2025->2026": {"pitches": 1040, "r_gap": 0.5341}},
        "holdout_fit_2024_25_scored_2025_26": {"train_pitches": 997, "test_pitches": 1040, "rmse_regressed_baseline": 5.5609,
                                               "rmse_blend": 5.2032, "gain_pct": 6.4316, "gain_pct_lo": 4.896, "gain_pct_hi": 8.0345}}))
    (folder / "edge-stuff-location-2026.json").write_text(json.dumps({"same_season": {"2026": {
        "ST": {"physics": {"r": 0.141, "n": 151}, "location": {"r": 0.712, "n": 151}}, "SL": {"physics": {"r": 0.409, "n": 245}}}}}))
    (folder / "edge-grade-noise-2026.json").write_text(json.dumps({"orders": {"count": 10}, "pitches": {}, "saved_run": {}}))
    if grades_json is not None:
        (folder / "bullpen-grades-2026.json").write_text(json.dumps(grades_json))
    return folder


def _run(tmp_path: Path, table: pd.DataFrame, loc: bool = True, grades_json: dict | None = None):
    edge = tmp_path / "edge"
    edge.mkdir(parents=True, exist_ok=True)
    table.to_parquet(edge / "projection.parquet")
    table.drop(columns=["proj_whiff_pct", "proj_change", "proj_basis", "whiff_pct_prior"]).to_parquet(edge / "stuff_2026.parquet")
    if loc:
        table[["pitcher", "pitch_type", "swings", "whiffs"]].assign(x_loc_pct=table["x_whiff_pct"] + 1.26).to_parquet(edge / "stuff_loc_2026.parquet")
    return edge, _outputs(tmp_path / "outputs", grades_json)


def _build(tmp_path, table, **kw):
    edge, out = _run(tmp_path, table, **{k: v for k, v in kw.items() if k in ("loc", "grades_json")})
    return bw.build(2026, edge_dir=edge, outputs=out, people_path=tmp_path / "none.parquet", pitches=kw.get("pitches"), use_pitch_files=False)


# ------------------------------------------------------------------ generator logic

def test_grades_rank_inside_the_type_group_with_the_memo_mapping():
    t = _table()
    g = bw.grades(t)
    cu = t[t.pitch_type.isin(["CU", "KC"])]          # knuckle curves are graded with curveballs
    i = t.index[t.pitch_type.eq("KC")][0]
    assert g.loc[i, "grade_stuff"] == grade_from_percentile(percentile(cu.x_whiff_pct, t.loc[i, "x_whiff_pct"]))
    assert g.loc[i, "grade_next"] == grade_from_percentile(percentile(cu.proj_whiff_pct, t.loc[i, "proj_whiff_pct"]))
    ff = t[t.pitch_type.eq("FF")]
    best = ff.x_whiff_pct.idxmax()
    assert g.loc[best, "grade_stuff"] == g.loc[ff.index, "grade_stuff"].max()
    assert set(g.dropna().grade_stuff) <= set(range(20, 85, 5))


def test_a_type_with_too_few_pitches_gets_no_grade():
    t = _table(n_sv=3)
    g = bw.grades(t)
    assert g.loc[t.pitch_type.eq("SV")].isna().all().all()
    assert g.loc[~t.pitch_type.eq("SV")].notna().all().all()
    assert bw.grades(t, min_ref=1).notna().all().all()


def test_club_is_the_fielding_side_of_the_last_game_and_usage_sums_to_100():
    p = pd.DataFrame({
        "pitcher": [1, 1, 1, 1, 1, 2, 2],
        "game_pk": [10, 10, 10, 20, 20, 10, 10],
        "game_date": ["2026-04-01"] * 3 + ["2026-08-01"] * 2 + ["2026-04-01"] * 2,
        "home_team": ["DET", "DET", "DET", "SEA", "SEA", "DET", "DET"],
        "away_team": ["NYY", "NYY", "NYY", "LAD", "LAD", "NYY", "NYY"],
        "inning_topbot": ["Top", "Top", "Top", "Bot", "Bot", "Bot", "Bot"],   # top half: the home club is in the field
        "pitch_type": ["FF", "FF", "CH", "FF", None, "SL", "SL"],
    })
    club, usage = bw.club_and_usage(p)
    assert club == {1: "LAD", 2: "NYY"}               # pitcher 1 was traded: his last game decides
    assert usage[(1, "FF")] == pytest.approx(75.0) and usage[(1, "CH")] == pytest.approx(25.0)   # the untyped pitch is left out
    assert usage[(2, "SL")] == pytest.approx(100.0)


def test_names_come_from_the_people_table_and_search_ignores_accents(tmp_path):
    pd.DataFrame({"key_mlbam": pd.array([1, 2, None], dtype="Int64"), "name": ["Adrián Morejón", "Matt Boyd", "Nobody"]}).to_parquet(tmp_path / "people.parquet")
    n = bw.names([1, 2, 3], {1: "Morejon, Adrian", 2: "Boyd, Matthew", 3: "Doe, John"}, tmp_path / "people.parquet")
    assert n[1] == ["Adrián Morejón", ""]              # same name once accents are dropped: no extra search text
    assert n[2] == ["Matt Boyd", "Matthew Boyd"]       # the pitch files' spelling stays searchable
    assert n[3] == ["John Doe", ""]                    # not in the people table: the pitch files' name
    assert bw.plain("Adrián Morejón") == "adrian morejon"
    assert bw.savant_name("McCullers Jr., Lance") == "Lance McCullers Jr."


def test_grade_noise_note_counts_grades_that_stay_within_five():
    j = {"orders": {"count": 10},
         "pitches": {"1_SL": {"grade_stuff": {"lo": 35, "hi": 50}, "grade_next": {"lo": 50, "hi": 55}},
                     "2_FF": {"grade_stuff": {"lo": 60, "hi": 65}, "grade_next": {"lo": 55, "hi": 60}}},
         "saved_run": {"1_SL": {"grade_stuff": 45, "grade_next": 50}, "2_FF": {"grade_stuff": 60, "grade_next": 60}}}
    n = bw.grade_noise_note(j)
    assert (n["grades"], n["within5"], n["pitches"], n["fits"]) == (4, 3, 2, 10)   # 35 is 10 under the saved 45
    assert (n["widest_lo"], n["widest_hi"]) == (35, 50)


def test_build_embeds_every_saved_row_rounded_and_nothing_else(tmp_path):
    t = _table()
    d = _build(tmp_path, t)
    rec = {(r["id"], r["pt"]): r for r in bw.records(d)}
    assert len(rec) == len(t) == d["meta"]["rows"]
    assert d["meta"]["pitchers"] == t.pitcher.nunique() and d["meta"]["swings"] == int(t.swings.sum())
    for r in t.itertuples():
        e = rec[(int(r.pitcher), r.pitch_type)]
        assert (e["swings"], e["whiffs"]) == (r.swings, r.whiffs)
        assert e["whiff"] == round(r.whiff_pct, 1) and e["x"] == round(r.x_whiff_pct, 1) and e["gap"] == round(r.gap, 1)
        assert e["proj"] == round(r.proj_whiff_pct, 1) and e["xloc"] == round(r.x_whiff_pct + 1.26, 1)
        assert e["basis"] == (2 if r.proj_basis == "two seasons" else 1)
        assert (e["prior"] is None) == bool(pd.isna(r.whiff_pct_prior))
        assert e["usage"] is None                      # no pitch files given: usage and club stay empty
    assert not d["meta"]["has_club"] and all(p[3] == "" for p in d["pitchers"].values())
    assert d["notes"]["holdout"] == {"gain": 6.4, "lo": 4.9, "hi": 8.0, "rmse_blend": 5.2, "rmse_base": 5.56, "train": 997, "test": 1040}
    assert d["notes"]["sweeper"] == {"r_physics": 0.14, "r_location": 0.71, "n": 151}


def test_build_without_the_location_table_leaves_that_column_empty(tmp_path):
    d = _build(tmp_path, _table(), loc=False)
    assert not d["meta"]["has_location"] and all(r["xloc"] is None for r in bw.records(d))


def test_build_stops_when_the_saved_tables_disagree(tmp_path):
    t = _table()
    edge, out = _run(tmp_path, t)
    s = pd.read_parquet(edge / "stuff_2026.parquet")
    s.loc[0, "x_whiff_pct"] += 1.0
    s.to_parquet(edge / "stuff_2026.parquet")
    with pytest.raises(SystemExit, match="x_whiff_pct"):
        bw.build(2026, edge_dir=edge, outputs=out, people_path=tmp_path / "none.parquet", use_pitch_files=False)


def test_build_stops_when_a_printed_grade_differs(tmp_path):
    t = _table()
    g = bw.grades(t)
    r = t.iloc[0]
    printed = {"pitches": {"k": {"pitcher": int(r.pitcher), "pitch_type": r.pitch_type, "grade_stuff": int(g.grade_stuff[0]), "grade_next": int(g.grade_next[0])}}}
    assert _build(tmp_path / "ok", t, grades_json=printed)["meta"]["grades_checked"] == 1
    printed["pitches"]["k"]["grade_stuff"] += 5
    with pytest.raises(SystemExit, match="differ"):
        _build(tmp_path / "bad", t, grades_json=printed)


def test_select_applies_each_control(tmp_path):
    t = _table()
    pitches = pd.DataFrame({"pitcher": t.pitcher, "game_pk": 1, "game_date": "2026-04-01", "pitch_type": t.pitch_type,
                            "home_team": np.where(t.pitcher % 2 == 0, "MIL", "TB"), "away_team": "SD", "inning_topbot": "Top"})
    d = _build(tmp_path, t, pitches=pitches)
    assert len(bw.select(d)) == len(t)
    assert {r["pt"] for r in bw.select(d, pitch="CU")} == {"CU"}
    assert len(bw.select(d, hand="L")) == int(t.p_throws.eq("L").sum())
    assert len(bw.select(d, club="MIL")) == int((t.pitcher % 2 == 0).sum())
    assert len(bw.select(d, min_swings=200)) == int((t.swings >= 200).sum())
    assert len(bw.select(d, clear_only=True)) == int(t.gap_clear.sum())
    assert [r["id"] for r in bw.select(d, search="  LAST1005 ")] == [1005]
    both = bw.select(d, pitch="FF", hand="R", min_swings=150)
    assert len(both) == int((t.pitch_type.eq("FF") & t.p_throws.eq("R") & (t.swings >= 150)).sum())
    assert all(r["usage"] == 100.0 for r in bw.records(d))


def test_write_fills_the_template_and_keeps_the_script_tag_safe(tmp_path):
    d = _build(tmp_path, _table())
    d["pitchers"][next(iter(d["pitchers"]))][0] = "A </script> B"
    out = bw.write(d, tmp_path / "page.html")
    html = out.read_text(encoding="utf-8")
    assert "/*DATA*/null" not in html and html.count("</script>") == 1
    blob = re.search(r"const DATA = (\{.*?\});\n", html, re.S).group(1)
    assert json.loads(blob)["rows"] == d["rows"]


# ------------------------------------------------------------------ the template

def test_template_is_one_file_with_no_outside_requests():
    html = TEMPLATE.read_text(encoding="utf-8")
    assert not re.search(r"<script[^>]+src=|<link\b|<img\b|@import|url\(", html)
    assert "\u2013" not in html and "\u2014" not in html
    for control in ("f-q", "f-pt", "f-team", "f-hand", "f-min", "f-clear", "csv"):
        assert f'id="{control}"' in html


def test_run_date_on_the_page_is_the_one_the_report_states():
    report = (ROOT / "reports" / "2026-edge-board.md").read_text()
    month_day = bw.RUN_LABEL[2026].split(",")[0]       # "Oct. 17"
    assert f"{month_day} run" in report


# ------------------------------------------------------------------ the built page

@pytest.fixture(scope="module")
def page():
    if not PAGE.exists():
        pytest.skip("edge board dashboard not built")
    html = PAGE.read_text(encoding="utf-8")
    return html, json.loads(re.search(r"const DATA = (\{.*?\});\n", html, re.S).group(1))


def test_page_is_small_and_self_contained(page):
    html, d = page
    assert len(html.encode()) < 2_000_000
    assert not re.search(r"<script[^>]+src=|<link\b|<img\b", html)
    assert len(d["rows"]) == d["meta"]["rows"] and all(len(r) == len(d["cols"]) for r in d["rows"])
    assert len({(r[0], r[1]) for r in d["rows"]}) == len(d["rows"])
    assert {str(r[0]) for r in d["rows"]} == set(d["pitchers"])


def test_page_rows_are_internally_consistent(page):
    _, d = page
    for r in bw.records(d):
        assert r["swings"] >= d["meta"]["min_swings"] and 0 <= r["whiffs"] <= r["swings"]
        assert r["whiff"] == round(100 * r["whiffs"] / r["swings"], 1)
        assert r["lo"] <= r["whiff"] <= r["hi"]
        assert abs(r["gap"] - (r["whiff"] - r["x"])) <= 0.11          # each side is rounded to one decimal
        assert abs(r["chg"] - (r["proj"] - r["whiff"])) <= 0.11
        assert bool(r["clear"]) == (not r["lo"] <= r["x"] <= r["hi"]) or abs(r["x"] - r["lo"]) < 0.06 or abs(r["x"] - r["hi"]) < 0.06
        assert r["g_stuff"] is None or r["g_stuff"] in range(20, 85, 5)
        assert (r["basis"] == 2) == (r["prior"] is not None)


def test_page_limits_quote_the_saved_tables(page):
    _, d = page
    h = json.loads((OUTPUTS / "edge-2026.json").read_text())["holdout_fit_2024_25_scored_2025_26"]
    n = d["notes"]["holdout"]
    assert (n["gain"], n["lo"], n["hi"]) == (round(h["gain_pct"], 1), round(h["gain_pct_lo"], 1), round(h["gain_pct_hi"], 1))
    assert (n["rmse_blend"], n["rmse_base"]) == (round(h["rmse_blend"], 2), round(h["rmse_regressed_baseline"], 2))
    loc = json.loads((OUTPUTS / "edge-stuff-location-2026.json").read_text())["same_season"]["2026"]["ST"]
    assert d["notes"]["sweeper"] == {"r_physics": round(loc["physics"]["r"], 2), "r_location": round(loc["location"]["r"], 2), "n": loc["physics"]["n"]}
    assert d["notes"]["noise"] == bw.grade_noise_note(json.loads((OUTPUTS / "edge-grade-noise-2026.json").read_text()))


def test_page_grades_match_the_grades_my_reports_print(page):
    _, d = page
    rec = {(r["id"], r["pt"]): r for r in bw.records(d)}
    printed = json.loads((OUTPUTS / "bullpen-grades-2026.json").read_text())["pitches"]
    assert printed
    for row in printed.values():
        e = rec[(row["pitcher"], row["pitch_type"])]
        assert (e["g_stuff"], e["g_next"]) == (row["grade_stuff"], row["grade_next"])
        assert e["x"] == round(row["x_whiff_pct"], 1) and e["proj"] == round(row["proj_whiff_pct"], 1)


def test_page_rows_equal_the_saved_run(page):
    if not (SAVED / "projection.parquet").exists():
        pytest.skip("the saved run is not on this machine")
    _, d = page
    saved = pd.read_parquet(SAVED / "projection.parquet")
    loc = pd.read_parquet(SAVED / "stuff_loc_2026.parquet").set_index(["pitcher", "pitch_type"])["x_loc_pct"]
    rec = {(r["id"], r["pt"]): r for r in bw.records(d)}
    assert len(rec) == len(saved)
    for r in saved.itertuples():
        e = rec[(int(r.pitcher), r.pitch_type)]
        assert (e["swings"], e["whiffs"]) == (r.swings, r.whiffs)
        assert e["whiff"] == round(r.whiff_pct, 1) and e["x"] == round(r.x_whiff_pct, 1) and e["gap"] == round(r.gap, 1)
        assert e["proj"] == round(r.proj_whiff_pct, 1) and e["chg"] == round(r.proj_change, 1)
        assert e["xloc"] == round(float(loc[(r.pitcher, r.pitch_type)]), 1)
        assert bool(e["clear"]) == bool(r.gap_clear)
        assert d["pitchers"][str(e["id"])][2] == r.p_throws
