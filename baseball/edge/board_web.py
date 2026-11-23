"""The Edge Board as a dashboard: every pitcher-pitch of the saved run on one page a reader can search, filter and sort.

    uv run bb board-web 2026            # -> docs/edge-board.html (served on GitHub Pages)
    uv run python -m baseball.edge.board_web 2026
    uv run python -m baseball.edge.board_web --restyle   # template change only: re-wrap the page's own data

Nothing is fit here. The page is built from the saved `bb edge` run and the small saved tables:

  data/edge/<season>/projection.parquet       one row per pitcher and pitch type with 50+ tracked swings: actual whiff
                                              rate, expected whiff (physics), the gap, and next season's projection
  data/edge/<season>/stuff_<season>.parquet   the same pitches as the stuff model wrote them (cross-checked)
  data/edge/<season>/stuff_loc_<season>.parquet  location-aware expected whiff per pitch (the Nov. 15 fit)
  reports/outputs/edge-<season>.json          the held-out test of the projection
  reports/outputs/edge-grade-noise-<season>.json   how far a grade moves between refits
  reports/outputs/edge-stuff-location-<season>.json  sweepers: physics vs. location-aware
  reports/outputs/bullpen-grades-<season>.json     the grades already printed in the bullpen memo
  data/people/people.parquet                  names
  data/raw/league_<season>_*.parquet          club and usage, counted from the regular-season pitch files (optional)

The 20-80 grades are the same mapping the bullpen memo uses (reliever.percentile and grade_from_percentile, each pitch
against every pitch of its type with 50+ tracked swings). The build stops if a grade here differs from one already
printed, or if the saved tables disagree with each other, so the page cannot drift from the reports.
"""
from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

from baseball.evaluation.reliever import _ptype, grade_from_percentile, percentile

ROOT = Path(__file__).resolve().parents[2]
EDGE_DIR = ROOT / "data" / "edge"
OUTPUTS = ROOT / "reports" / "outputs"
PEOPLE = ROOT / "data" / "people" / "people.parquet"
PAGE = ROOT / "docs" / "edge-board.html"
TEMPLATE = Path(__file__).with_name("board_web.html")

# The date of the saved `bb edge` run, as reports/2026-edge-board.md states it; the location-aware fit came later.
RUN_LABEL = {2026: "Oct. 17, 2026"}
LOCATION_FIT_LABEL = {2026: "Nov. 15, 2026"}

# A grade is a rank inside the pitch type, so a type with only a few pitches on the board gets none.
MIN_GRADE_REF = 25

# One row of the embedded table. Rates are in whiffs per 100 swings, rounded to one decimal.
COLS = ["id", "pt", "swings", "whiffs", "whiff", "lo", "hi", "x", "gap", "clear", "proj", "chg", "basis", "prior",
        "xloc", "g_stuff", "g_next", "velo", "ivb", "hb", "usage"]


def r1(x) -> float | None:
    return None if x is None or pd.isna(x) else round(float(x), 1)


def _g(x) -> int | None:
    return None if pd.isna(x) else int(x)


def plain(s: str) -> str:
    """Lower case without accents, for search: 'Adrián Morejón' -> 'adrian morejon'."""
    return "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn").lower()


def savant_name(s: str) -> str:
    """'Skubal, Tarik' -> 'Tarik Skubal'."""
    if not isinstance(s, str) or ", " not in s:
        return str(s)
    last, first = s.split(", ", 1)
    return f"{first} {last}"


def names(ids, fallback: dict[int, str], people_path: Path = PEOPLE) -> dict[int, list[str]]:
    """[display name, extra search text] per pitcher id. The display name is the people table's; the pitch files'
    spelling is kept as search text where it differs, so 'Matthew Boyd' still finds Matt Boyd."""
    table = {}
    if people_path.exists():
        p = pd.read_parquet(people_path, columns=["key_mlbam", "name"]).dropna(subset=["key_mlbam"])
        table = dict(zip(p["key_mlbam"].astype(int), p["name"]))
    out = {}
    for i in ids:
        alt = savant_name(fallback.get(i, ""))
        name = table.get(i) or alt or str(i)
        out[i] = [name, alt if plain(alt) != plain(name) else ""]
    return out


def grades(table: pd.DataFrame, min_ref: int = MIN_GRADE_REF) -> pd.DataFrame:
    """Stuff and next-season 20-80 grades for every row of a pitch table (needs pitch_type, x_whiff_pct and
    proj_whiff_pct). Each pitch is ranked against every pitch of its type group in the same table, then
    grade = 50 + 10 z to the nearest 5: the mapping of reliever.pitch_grades() and edge.grade_noise.grade_rows().
    A type group with fewer than `min_ref` pitches is left ungraded (NaN)."""
    t = table.reset_index(drop=True)
    group = t["pitch_type"].map(_ptype)
    out = pd.DataFrame(index=t.index, columns=["pct_stuff", "grade_stuff", "pct_next", "grade_next"], dtype=float)
    for _, idx in t.groupby(group).groups.items():
        ref = t.loc[idx]
        if len(ref) < min_ref:
            continue
        for i in idx:
            ps, pn = percentile(ref["x_whiff_pct"], t.at[i, "x_whiff_pct"]), percentile(ref["proj_whiff_pct"], t.at[i, "proj_whiff_pct"])
            out.loc[i] = [ps, grade_from_percentile(ps), pn, grade_from_percentile(pn)]
    return out


def club_and_usage(pitches: pd.DataFrame) -> tuple[dict[int, str], dict[tuple[int, str], float]]:
    """From one regular season of pitches: the club each pitcher last pitched for (the fielding side of his last
    game), and each pitch type's share of his typed pitches, in percent."""
    d = pitches.dropna(subset=["pitcher"])
    club = np.where(d["inning_topbot"].eq("Top"), d["home_team"], d["away_team"])
    last = d.assign(club=club).sort_values(["game_date", "game_pk"]).groupby("pitcher")["club"].last()
    typed = d.dropna(subset=["pitch_type"])
    n = typed.groupby(["pitcher", "pitch_type"]).size()
    share = 100 * n / n.groupby(level=0).transform("sum")
    return {int(k): str(v) for k, v in last.items()}, {(int(p), str(t)): float(v) for (p, t), v in share.items()}


def _season_pitches(season: int) -> pd.DataFrame | None:
    from baseball.ingest.league import load_season
    from baseball.phases import phase

    try:
        d = load_season(season, ["game_pk", "game_date", "game_type", "pitcher", "pitch_type", "home_team", "away_team", "inning_topbot"])
    except Exception:  # no pitch files on this machine: the page leaves club and usage out
        return None
    return phase(d)


def grade_noise_note(j: dict) -> dict:
    """From the saved refit study: of the grades it checked, how many stayed within 5 points of the saved run's
    grade in every refit, and the widest range any one grade took."""
    total = within = 0
    widest = {"span": -1}
    for key, row in j["pitches"].items():
        saved = j["saved_run"][key]
        for g in ("grade_stuff", "grade_next"):
            lo, hi, was = row[g]["lo"], row[g]["hi"], saved[g]
            total += 1
            within += max(abs(lo - was), abs(hi - was)) <= 5
            if hi - lo > widest["span"]:
                widest = {"span": hi - lo, "lo": lo, "hi": hi, "key": key, "which": g}
    return {"grades": total, "within5": int(within), "fits": int(j["orders"]["count"]), "pitches": len(j["pitches"]),
            "widest_lo": widest.get("lo"), "widest_hi": widest.get("hi")}


def notes(season: int, outputs: Path = OUTPUTS) -> dict:
    """The limits quoted in the page's 'how to read this' block, each read from a saved table."""
    def load(name):
        return json.loads((outputs / name).read_text())

    h = load(f"edge-{season}.json")["holdout_fit_2024_25_scored_2025_26"]
    edge = load(f"edge-{season}.json")
    loc = load(f"edge-stuff-location-{season}.json")["same_season"][str(season)]
    out = {
        "holdout": {"gain": r1(h["gain_pct"]), "lo": r1(h["gain_pct_lo"]), "hi": r1(h["gain_pct_hi"]),
                    "rmse_blend": round(h["rmse_blend"], 2), "rmse_base": round(h["rmse_regressed_baseline"], 2),
                    "train": int(h["train_pitches"]), "test": int(h["test_pitches"])},
        "auc": round(edge["stuff_model_auc"][str(season)], 3),
        "gap_r": {k: {"r": round(v["r_gap"], 2), "n": int(v["pitches"])} for k, v in edge["gap_persistence"].items()},
        "noise": grade_noise_note(load(f"edge-grade-noise-{season}.json")),
        "sweeper": {"r_physics": round(loc["ST"]["physics"]["r"], 2), "r_location": round(loc["ST"]["location"]["r"], 2),
                    "n": int(loc["ST"]["physics"]["n"])},
        "slider": {"r_physics": round(loc["SL"]["physics"]["r"], 2), "n": int(loc["SL"]["physics"]["n"])},
    }
    return out


def check_printed_grades(g: pd.DataFrame, season: int, outputs: Path = OUTPUTS) -> int:
    """Stop the build if a grade on this page differs from one a report already prints. Returns how many were checked."""
    checked = 0
    idx = {(int(r.pitcher), r.pitch_type): r for r in g.itertuples()}
    for name, field in ((f"bullpen-grades-{season}.json", "pitches"), (f"edge-grade-noise-{season}.json", "saved_run")):
        path = outputs / name
        if not path.exists():
            continue
        for row in json.loads(path.read_text())[field].values():
            mine = idx.get((int(row["pitcher"]), row["pitch_type"]))
            if mine is None:
                raise SystemExit(f"{name}: pitcher {row['pitcher']} {row['pitch_type']} is not in the saved run")
            if (int(mine.grade_stuff), int(mine.grade_next)) != (row["grade_stuff"], row["grade_next"]):
                raise SystemExit(f"{name}: grades for {row['pitcher']} {row['pitch_type']} differ: page "
                                 f"{int(mine.grade_stuff)}/{int(mine.grade_next)} vs {row['grade_stuff']}/{row['grade_next']}")
            checked += 1
    return checked


def build(season: int, edge_dir: Path | None = None, outputs: Path = OUTPUTS, people_path: Path = PEOPLE,
          pitches: pd.DataFrame | None = None, use_pitch_files: bool = True) -> dict:
    base = edge_dir or EDGE_DIR / str(season)
    proj = pd.read_parquet(base / "projection.parquet")
    stuff = pd.read_parquet(base / f"stuff_{season}.parquet")
    key = ["pitcher", "pitch_type"]
    if proj.duplicated(key).any():
        raise SystemExit("projection.parquet has two rows for one pitcher and pitch type")

    # the two saved tables of the run must describe the same pitches
    m = proj.merge(stuff[key + ["swings", "whiffs", "x_whiff_pct"]], on=key, how="outer", suffixes=("", "_s"), indicator=True)
    if not m["_merge"].eq("both").all():
        raise SystemExit("projection.parquet and the stuff table hold different pitches")
    for c in ("swings", "whiffs", "x_whiff_pct"):
        if not np.allclose(m[c], m[f"{c}_s"], atol=1e-9):
            raise SystemExit(f"projection.parquet and the stuff table disagree on {c}")
    if not np.allclose(proj["gap"], proj["whiff_pct"] - proj["x_whiff_pct"], atol=1e-9):
        raise SystemExit("gap is not actual minus expected whiff")

    # location-aware expected whiff: a later fit on the same swings, so match on swings and whiffs too
    loc_path = base / f"stuff_loc_{season}.parquet"
    has_loc = loc_path.exists()
    if has_loc:
        loc = pd.read_parquet(loc_path)[key + ["swings", "whiffs", "x_loc_pct"]]
        proj = proj.merge(loc, on=key, how="left", suffixes=("", "_loc"))
        same = proj["swings"].eq(proj["swings_loc"]) & proj["whiffs"].eq(proj["whiffs_loc"])
        if not same[proj["x_loc_pct"].notna()].all():
            raise SystemExit("the location-aware table counts different swings from the saved run")
    else:
        proj["x_loc_pct"] = np.nan

    g = grades(proj)
    proj = pd.concat([proj.reset_index(drop=True), g], axis=1)
    checked = check_printed_grades(proj, season, outputs)

    if pitches is None and use_pitch_files:
        pitches = _season_pitches(season)
    club, usage = club_and_usage(pitches) if pitches is not None and len(pitches) else ({}, {})

    proj["pitcher"] = proj["pitcher"].astype(int)
    proj = proj.sort_values(["gap", "pitcher", "pitch_type"], ascending=[False, True, True]).reset_index(drop=True)
    ids = [int(i) for i in dict.fromkeys(proj["pitcher"])]
    who = names(ids, dict(zip(proj["pitcher"], proj["player_name"])), people_path)
    hand = dict(zip(proj["pitcher"], proj["p_throws"]))

    rows = []
    for r in proj.itertuples():
        rows.append([
            int(r.pitcher), r.pitch_type, int(r.swings), int(r.whiffs), r1(r.whiff_pct), r1(r.whiff_lo), r1(r.whiff_hi),
            r1(r.x_whiff_pct), r1(r.gap), int(bool(r.gap_clear)), r1(r.proj_whiff_pct), r1(r.proj_change),
            2 if r.proj_basis == "two seasons" else 1, r1(r.whiff_pct_prior), r1(r.x_loc_pct),
            _g(r.grade_stuff), _g(r.grade_next), r1(r.velo), r1(r.ivb_in), r1(r.hb_arm_in),
            r1(usage.get((int(r.pitcher), r.pitch_type))),
        ])
    pitch_names = {pt: nm for pt, nm in proj.groupby("pitch_type")["pitch_name"].agg(lambda s: s.mode().iat[0]).items()}
    counts = proj["pitch_type"].value_counts()
    return {
        "meta": {"season": season, "next": season + 1, "run": RUN_LABEL.get(season, ""),
                 "location_fit": LOCATION_FIT_LABEL.get(season, "") if has_loc else "",
                 "rows": len(rows), "pitchers": len(ids), "min_swings": int(proj["swings"].min()),
                 "max_swings": int(proj["swings"].max()), "swings": int(proj["swings"].sum()),
                 "two_season_rows": int(proj["proj_basis"].eq("two seasons").sum()),
                 "one_season_rows": int(proj["proj_basis"].eq("one season").sum()),
                 "gap_clear_rows": int(proj["gap_clear"].sum()), "has_location": bool(has_loc),
                 "has_club": bool(club), "has_usage": bool(usage), "grades_checked": checked,
                 "min_grade_ref": MIN_GRADE_REF, "ungraded_rows": int(proj["grade_stuff"].isna().sum())},
        "notes": notes(season, outputs),
        "cols": COLS,
        "rows": rows,
        "pitchers": {str(i): [who[i][0], who[i][1], hand[i], club.get(i, "")] for i in ids},
        "pitch_types": [[pt, pitch_names[pt], int(n)] for pt, n in counts.items()],
    }


def records(data: dict) -> list[dict]:
    """The embedded rows as dicts (the page's script reads them the same way); used by the tests."""
    return [dict(zip(data["cols"], row)) for row in data["rows"]]


def select(data: dict, search: str = "", pitch: str = "", club: str = "", hand: str = "", min_swings: int = 0,
           clear_only: bool = False) -> list[dict]:
    """The page's filter, in Python: the rows a reader sees for a given set of controls. Mirrors `visible()` in
    the page's script; used by the tests."""
    q = plain(search).strip()
    out = []
    for r in records(data):
        name, alt, throws, team = data["pitchers"][str(r["id"])]
        if q and q not in plain(name) and q not in plain(alt):
            continue
        if (pitch and r["pt"] != pitch) or (club and team != club) or (hand and throws != hand):
            continue
        if r["swings"] < min_swings or (clear_only and not r["clear"]):
            continue
        out.append(r)
    return out


def write(data: dict, out: Path = PAGE) -> Path:
    html = TEMPLATE.read_text(encoding="utf-8")
    blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    out.write_text(html.replace("/*DATA*/null", blob), encoding="utf-8")
    return out


def main(season: int = 2026) -> Path:
    d = build(season)
    path = write(d)
    print(f"{path}: {d['meta']['rows']} pitches by {d['meta']['pitchers']} pitchers, {path.stat().st_size / 1024:,.0f} KB")
    return path


def embedded(page: Path = PAGE) -> dict:
    """The data embedded in the published page, read back exactly as it was written (after `const DATA = `)."""
    text = page.read_text(encoding="utf-8")
    return json.JSONDecoder().raw_decode(text, text.index("const DATA = ") + len("const DATA = "))[0]


if __name__ == "__main__":
    if "--restyle" in sys.argv:   # new template, same data: re-wrap the published page's own data, no edge run needed
        print(write(embedded()), "restyled")
    else:
        main(int(sys.argv[1]) if len(sys.argv) > 1 else 2026)
