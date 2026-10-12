"""bb: the command line for the baseball operations workspace.

  uv run bb pull skubal tarik 2025          pull a pitcher-season from Statcast into the warehouse
  uv run bb arsenal skubal tarik 2025       his arsenal from the warehouse (regular season by default)
  uv run bb arsenal skubal tarik 2025 --phase postseason
  uv run bb compare skubal tarik 2024 2025  his arsenal in two seasons side by side, with significance
  uv run bb db                              what is in the warehouse
  uv run bb db rebuild                      rebuild the warehouse from the cached pulls in data/raw/
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from baseball import warehouse
from baseball.evaluation import arsenal, compare_arsenals, outcomes, usage_by_hand
from baseball.phases import PHASES, phase


def _pitcher_id(last: str, first: str) -> int:
    """Warehouse first (works offline), then the Chadwick register over the network."""
    found = warehouse.find_pitcher(warehouse.connect(), last, first)
    if found is not None:
        return found
    from baseball.ingest.statcast import lookup_mlbam

    return lookup_mlbam(last, first)


def cmd_pull(a: argparse.Namespace) -> None:
    from baseball.ingest.statcast import pitcher_season

    pid = _pitcher_id(a.last, a.first)
    df = pitcher_season(pid, a.season, refresh=a.refresh)
    con = warehouse.connect()
    new = warehouse.load_pitches(con, df, source="statcast", description=f"pitcher {pid} ({a.first} {a.last}) {a.season}")
    print(f"{a.first.title()} {a.last.title()} {a.season}: {len(df):,} pitches pulled, {new:,} new in the warehouse.")


def cmd_arsenal(a: argparse.Namespace) -> None:
    pid = _pitcher_id(a.last, a.first)
    con = warehouse.connect()
    p = warehouse.pitcher_pitches(con, pid, a.season)
    if p.empty:
        sys.exit(f"Nothing in the warehouse for {a.first} {a.last} {a.season}. Run: uv run bb pull {a.last} {a.first} {a.season}")
    p = phase(p, a.phase)
    print(f"{p['player_name'].iloc[0]}, {a.season} {a.phase}: {len(p):,} pitches in {p['game_pk'].nunique()} games\n")
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(arsenal(p, min_n=a.min_n).to_string(index=False), "\n")
        print(outcomes(p, min_n=a.min_n).to_string(index=False), "\n")
        print(usage_by_hand(p, min_n=a.min_n).to_string(index=False))


def cmd_compare(a: argparse.Namespace) -> None:
    pid = _pitcher_id(a.last, a.first)
    con = warehouse.connect()
    samples = {}
    for season in (a.season_a, a.season_b):
        p = phase(warehouse.pitcher_pitches(con, pid, season), a.phase)
        if p.empty:
            sys.exit(f"No {a.phase} pitches for {a.first} {a.last} {season}. Run: uv run bb pull {a.last} {a.first} {season}")
        samples[season] = p
    out = compare_arsenals(samples[a.season_a], samples[a.season_b], min_n=a.min_n)
    name = samples[a.season_b]["player_name"].iloc[0]
    print(f"{name}, {a.phase}: {a.season_a} (_a, {len(samples[a.season_a]):,} pitches) vs {a.season_b} (_b, {len(samples[a.season_b]):,} pitches)\n")
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(out["shape"].to_string(index=False), "\n")
        print(out["results"].to_string(index=False))


def cmd_db(a: argparse.Namespace) -> None:
    con = warehouse.connect()
    if a.action == "rebuild":
        print(f"{warehouse.rebuild(con):,} new rows loaded from data/raw/.")
    s = warehouse.summary(con)
    print("The warehouse is empty. Start with: uv run bb pull skubal tarik 2025" if s.empty else s.to_string(index=False))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="bb", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pull", help="pull a pitcher-season from Statcast into the warehouse")
    p.add_argument("last"); p.add_argument("first"); p.add_argument("season", type=int)
    p.add_argument("--refresh", action="store_true", help="ignore the cached pull and download again")
    p.set_defaults(func=cmd_pull)

    r = sub.add_parser("arsenal", help="a pitcher's arsenal from the warehouse")
    r.add_argument("last"); r.add_argument("first"); r.add_argument("season", type=int)
    r.add_argument("--phase", default="regular", choices=sorted(PHASES))
    r.add_argument("--min-n", type=int, default=20)
    r.set_defaults(func=cmd_arsenal)

    c = sub.add_parser("compare", help="one pitcher's arsenal in two seasons, side by side")
    c.add_argument("last"); c.add_argument("first")
    c.add_argument("season_a", type=int); c.add_argument("season_b", type=int)
    c.add_argument("--phase", default="regular", choices=sorted(PHASES))
    c.add_argument("--min-n", type=int, default=20)
    c.set_defaults(func=cmd_compare)

    d = sub.add_parser("db", help="what is in the warehouse")
    d.add_argument("action", nargs="?", choices=["rebuild"])
    d.set_defaults(func=cmd_db)

    a = ap.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()
