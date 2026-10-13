"""bb: the command line for the baseball operations workspace.

  uv run bb pull skubal tarik 2025          pull a pitcher-season from Statcast into the warehouse
  uv run bb arsenal skubal tarik 2025       his arsenal from the warehouse (regular season by default)
  uv run bb arsenal skubal tarik 2025 --phase postseason
  uv run bb compare skubal tarik 2024 2025  his arsenal in two seasons side by side, with significance
  uv run bb pull-league 2025                every pitch of a season, month by month (resumable)
  uv run bb edge 2026                       run the edge engine on 2026 (2024-25 for validation)
  uv run bb board 2026                      build the Edge Board page from the engine's outputs
  uv run bb stuff-model 2026                train only the portable model (for TrackMan / Rapsodo data)
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


def cmd_pull_league(a: argparse.Namespace) -> None:
    import time

    from baseball.ingest.league import SEASON_MONTHS, pull_month, recent_months

    refresh = set(SEASON_MONTHS) if a.refresh else set(recent_months(a.season) if a.refresh_recent else [])
    con = warehouse.connect()
    total = 0
    print(f"Pulling every {a.season} pitch, month by month. Finished months are saved and skipped on a re-run.")
    for m in SEASON_MONTHS:
        t0 = time.time()
        try:
            path, rows, cached = pull_month(a.season, m, refresh=m in refresh)
        except Exception as e:  # Savant timeouts happen; keep the months that worked
            print(f"  {a.season}-{m:02d}: failed ({type(e).__name__}: {e}). Re-run the same command to retry.")
            continue
        new = 0
        if rows and not cached:  # cached months were loaded when first pulled (bb db rebuild reloads everything)
            new = warehouse.load_pitches(con, pd.read_parquet(path), source="statcast-league", description=path.name)
        total += rows
        state = "cached" if cached else f"pulled in {time.time() - t0:,.0f}s"
        print(f"  {a.season}-{m:02d}: {rows:>8,} pitches ({state}), {new:,} new in the warehouse")
    print(f"Done: {total:,} pitches for {a.season}.")


def cmd_edge(a: argparse.Namespace) -> None:
    from baseball.edge.run import run

    s = run(a.season)
    print(f"\nStuff model AUC {s['stuff_model'][str(a.season)]['auc']:.3f}")
    for pair, v in s["validation"].items():
        print(f"  {pair}: next-season whiff% from actual r = {v['r_actual_prev']:.3f}, from expected r = "
              f"{v['r_xwhiff_prev']:.3f}, blend r = {v['r_blend']:.3f} ({v['matched_pitches']} pitches)")


def cmd_slim(a: argparse.Namespace) -> None:
    from baseball.ingest.league import write_slim

    paths = write_slim(a.season)
    print(f"{a.season}: {len(paths)} slim parts in data/slim/")


def cmd_board(a: argparse.Namespace) -> None:
    from baseball.edge.board import build

    print(f"Edge Board: {build(a.season)}")


def cmd_stuff_model(a: argparse.Namespace) -> None:
    from baseball.edge import stuff
    from baseball.edge.run import COLUMNS, OUT_DIR
    from baseball.ingest.league import load_season

    out = OUT_DIR / str(a.season)
    out.mkdir(parents=True, exist_ok=True)
    bundle = stuff.build_portable(phase(load_season(a.season, COLUMNS)), a.season)
    stuff.save_portable(bundle, out / "stuff_portable.joblib")
    d = bundle["diagnostics"]
    print(f"Portable model ({a.season}, {bundle['trained_swings']:,} swings): cross-fitted AUC {d['auc']:.3f}, "
          f"log loss {d['log_loss']:.4f} vs {d['log_loss_baseline']:.4f} baseline -> {out / 'stuff_portable.joblib'}")


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

    lg = sub.add_parser("pull-league", help="every pitch of a season into the warehouse (resumable)")
    lg.add_argument("season", type=int)
    lg.add_argument("--refresh", action="store_true", help="download every month again even if cached")
    lg.add_argument("--refresh-recent", action="store_true", help="re-download months that may still be growing")
    lg.set_defaults(func=cmd_pull_league)

    e = sub.add_parser("edge", help="run the edge engine on two seasons of league data")
    e.add_argument("season", type=int)
    e.set_defaults(func=cmd_edge)

    sl = sub.add_parser("slim", help="write the compact engine copy of a season (data/slim/)")
    sl.add_argument("season", type=int)
    sl.set_defaults(func=cmd_slim)

    bd = sub.add_parser("board", help="build the Edge Board page (data/edge/<season>/edge-board.html)")
    bd.add_argument("season", type=int)
    bd.set_defaults(func=cmd_board)

    sm = sub.add_parser("stuff-model", help="train the portable expected-whiff model used on TrackMan / Rapsodo data")
    sm.add_argument("season", type=int)
    sm.set_defaults(func=cmd_stuff_model)

    d = sub.add_parser("db", help="what is in the warehouse")
    d.add_argument("action", nargs="?", choices=["rebuild"])
    d.set_defaults(func=cmd_db)

    a = ap.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()
