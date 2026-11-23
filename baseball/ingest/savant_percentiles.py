"""Baseball Savant's own percentile rankings, saved in the repo so the offseason packet can show them without
the pitch data.

Two Savant sources, both public pages:
- The percentile-rankings leaderboard export (one CSV per player type and season):
  https://baseballsavant.mlb.com/leaderboard/percentile-rankings?type=pitcher&year=2026&csv=true
  It carries only the percentiles (1-100, oriented so that a high number is the good end for that player).
- Each player's Savant page (https://baseballsavant.mlb.com/savant-player/<id>), which holds the same
  percentiles for every season next to the values they rank (xERA 2.34, K% 30.4 and so on), plus a few the
  CSV leaves out (fastball extension, ground-ball rate, sweet-spot rate). I keep only the season rows.

    uv run python -m baseball.ingest.savant_percentiles            (both CSVs, 2025 and 2026)
    uv run python -m baseball.ingest.savant_percentiles --players 670970 592332 650556

Files: market/savant/percentile_rankings_<type>_<year>.csv (Savant's export as downloaded),
market/savant/player_pages.json (season rows from the player pages) and market/savant/manifest.json
(each file's URL, pull date and row count).
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import time
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAVANT = ROOT / "market" / "savant"
CSV_URL = "https://baseballsavant.mlb.com/leaderboard/percentile-rankings?type={kind}&year={year}&csv=true"
PAGE_URL = "https://baseballsavant.mlb.com/savant-player/{mlbam}"
UA = {"User-Agent": "Mozilla/5.0"}

# The rows of Savant's percentile card, in Savant's order and with Savant's names.
# (label, CSV column or None when only the player page carries it, player-page percentile key, player-page value key,
#  format: 2f, avg (.237), pct (30.4%), mph, ft, fts)
PITCHER = (
    ("xERA", "xera", "percent_rank_xera", "xera", "2f"),
    ("xBA", "xba", "percent_rank_xba", "xba", "avg"),
    ("xwOBA", "xwoba", "percent_rank_xwoba", "xwoba", "avg"),
    ("Fastball Velo", "fb_velocity", "percent_rank_fastball_velo", "fastball_velo", "mph"),
    ("Avg Exit Velocity", "exit_velocity", "percent_rank_exit_velocity_avg", "exit_velocity_avg", "mph"),
    ("Chase %", "chase_percent", "percent_rank_chase_percent", "oz_swing_percent", "pct"),
    ("Whiff %", "whiff_percent", "percent_rank_whiff_percent", "whiff_percent", "pct"),
    ("K %", "k_percent", "percent_rank_k_percent", "k_percent", "pct"),
    ("BB %", "bb_percent", "percent_rank_bb_percent", "bb_percent", "pct"),
    ("Barrel %", "brl_percent", "percent_rank_barrel_batted_rate", "barrel_batted_rate", "pct"),
    ("Hard-Hit %", "hard_hit_percent", "percent_rank_hard_hit_percent", "hard_hit_percent", "pct"),
    ("GB %", None, "percent_rank_groundballs_percent", "groundballs_percent", "pct"),
    ("Extension", None, "percent_rank_fastball_extension", "fastball_extension", "ft"),
)
BATTER = (
    ("xwOBA", "xwoba", "percent_rank_xwoba", "xwoba", "avg"),
    ("xBA", "xba", "percent_rank_xba", "xba", "avg"),
    ("xSLG", "xslg", "percent_rank_xslg", "xslg", "avg"),
    ("Avg Exit Velocity", "exit_velocity", "percent_rank_exit_velocity_avg", "exit_velocity_avg", "mph"),
    ("Barrel %", "brl_percent", "percent_rank_barrel_batted_rate", "barrel_batted_rate", "pct"),
    ("Hard-Hit %", "hard_hit_percent", "percent_rank_hard_hit_percent", "hard_hit_percent", "pct"),
    ("LA Sweet-Spot %", None, "percent_rank_sweet_spot_percent", "sweet_spot_percent", "pct"),
    ("Bat Speed", "bat_speed", "percent_rank_swing_speed", "avg_swing_speed", "mph"),
    ("Squared-Up %", "squared_up_rate", "percent_rank_squared_up_swing", "squared_up_swing", "pct"),
    ("Chase %", "chase_percent", "percent_rank_chase_percent", "oz_swing_percent", "pct"),
    ("Whiff %", "whiff_percent", "percent_rank_whiff_percent", "whiff_percent", "pct"),
    ("K %", "k_percent", "percent_rank_k_percent", "k_percent", "pct"),
    ("BB %", "bb_percent", "percent_rank_bb_percent", "bb_percent", "pct"),
    ("Sprint Speed", "sprint_speed", "percent_speed_order", "sprint_speed", "fts"),
)
METRICS = {"pitcher": PITCHER, "batter": BATTER}


def csv_path(kind: str, year: int, root: Path = SAVANT) -> Path:
    return root / f"percentile_rankings_{kind}_{year}.csv"


def _get(url: str) -> tuple[bytes, int]:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read(), r.status


def _manifest(root: Path) -> dict:
    p = root / "manifest.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _write_manifest(root: Path, m: dict) -> None:
    (root / "manifest.json").write_text(json.dumps(dict(sorted(m.items())), indent=1) + "\n")


def pull(years=(2025, 2026), kinds=("pitcher", "batter"), root: Path = SAVANT, get=_get, pulled: str | None = None,
         pause: float = 3.0) -> list[Path]:
    """Download Savant's percentile-rankings CSVs as they come and record each one's URL, date and row count."""
    root.mkdir(parents=True, exist_ok=True)
    m, out = _manifest(root), []
    for kind in kinds:
        for year in years:
            url = CSV_URL.format(kind=kind, year=year)
            body, status = get(url)
            text = body.decode("utf-8-sig")
            rows = list(csv.DictReader(io.StringIO(text)))
            if not rows or "player_id" not in rows[0]:
                raise RuntimeError(f"Savant sent no percentile table for {kind} {year} (status {status}); not saved")
            p = csv_path(kind, year, root)
            p.write_bytes(body)
            m[p.name] = dict(url=url, pulled=pulled or date.today().isoformat(), rows=len(rows), status=status)
            out.append(p)
            time.sleep(pause)
    _write_manifest(root, m)
    return out


def season_rows(page: str, seasons=(2025, 2026)) -> dict:
    """The per-season rows ("Pitcher and Year" / "Batter and Year") from a Savant player page, by season and type."""
    dec, out = json.JSONDecoder(), {}
    for mt in re.finditer(r'\{"aggregate": ?"0"', page):
        try:
            o, _ = dec.raw_decode(page[mt.start():])
        except ValueError:
            continue
        y, kind = o.get("year"), o.get("player_type")
        if y in seasons and kind in METRICS and str(o.get("grouping_code", "")).endswith("and Year"):
            out.setdefault(kind, {})[str(y)] = {k: v for k, v in o.items() if not k.endswith("_unrounded")}
    return out


def pull_players(ids, seasons=(2025, 2026), root: Path = SAVANT, get=_get, pulled: str | None = None, pause: float = 3.0) -> Path:
    """Read each player's Savant page and keep his season rows (values and percentiles) in player_pages.json."""
    p = root / "player_pages.json"
    have = json.loads(p.read_text()) if p.exists() else {}
    when = pulled or date.today().isoformat()
    for mid in ids:
        url = PAGE_URL.format(mlbam=int(mid))
        body, status = get(url)
        rows = season_rows(body.decode("utf-8", errors="ignore"), seasons)
        if not rows:
            raise RuntimeError(f"no season rows on {url} (status {status})")
        have[str(int(mid))] = dict(url=url, pulled=when, seasons=rows)
        time.sleep(pause)
    p.write_text(json.dumps(dict(sorted(have.items(), key=lambda kv: int(kv[0]))), indent=1, ensure_ascii=False) + "\n")
    m = _manifest(root)
    m[p.name] = dict(url=PAGE_URL.format(mlbam="<id>"), pulled=when, rows=len(have), status=200)
    _write_manifest(root, m)
    return p


def load(kind: str, year: int, root: Path = SAVANT) -> dict[int, dict]:
    """Savant's CSV for one type and season, by player id (percentiles as ints, blanks as None)."""
    out = {}
    with open(csv_path(kind, year, root), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            out[int(r["player_id"])] = {k: (int(v) if v not in ("", None) and k not in ("player_name",) else (v or None))
                                        for k, v in r.items()}
    return out


def pool_size(kind: str, year: int, column: str, root: Path = SAVANT) -> int:
    """How many players Savant ranks on one CSV column that season."""
    return sum(1 for r in load(kind, year, root).values() if r.get(column) is not None)


def _num(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def card(mlbam: int, kind: str, year: int, root: Path = SAVANT) -> dict | None:
    """Savant's percentile card for one player-season: each row's percentile (from the CSV when it has the
    column, else the player page) and the value it ranks (player page). None if Savant doesn't rank him."""
    tab = load(kind, year, root).get(int(mlbam))
    pages = json.loads((root / "player_pages.json").read_text()) if (root / "player_pages.json").exists() else {}
    page = pages.get(str(int(mlbam)), {})
    rec = page.get("seasons", {}).get(kind, {}).get(str(year), {})
    if tab is None:
        return None
    m = _manifest(root)
    rows = []
    for label, col, pkey, vkey, fmt in METRICS[kind]:
        p = tab.get(col) if col else rec.get(pkey)
        if p is None:
            continue
        rows.append(dict(label=label, pctl=int(p), value=_num(rec.get(vkey)), fmt=fmt, from_csv=bool(col)))
    if not rows:
        return None
    f = csv_path(kind, year, root).name
    return dict(season=year, kind=kind, rows=rows, csv=dict(file=f, url=m.get(f, {}).get("url"), pulled=m.get(f, {}).get("pulled")),
                page=dict(url=page.get("url"), pulled=page.get("pulled")) if page else None,
                pa=rec.get("pa"))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--years", type=int, nargs="+", default=[2025, 2026])
    ap.add_argument("--players", type=int, nargs="*", help="also read these players' Savant pages")
    a = ap.parse_args(argv)
    if a.players:
        print(pull_players(a.players, seasons=tuple(a.years)))
    else:
        for p in pull(years=tuple(a.years)):
            print(p)


if __name__ == "__main__":
    main()
