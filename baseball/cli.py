"""bb: the command line for the baseball operations workspace.

  uv run bb pull skubal tarik 2025          pull a pitcher-season from Statcast into the warehouse
  uv run bb arsenal skubal tarik 2025       his arsenal from the warehouse (regular season by default)
  uv run bb arsenal skubal tarik 2025 --phase postseason
  uv run bb compare skubal tarik 2024 2025  his arsenal in two seasons side by side, with significance
  uv run bb pull-league 2025                every pitch of a season, month by month (resumable)
  uv run bb edge 2026                       run the edge engine on 2026 (2024-25 for validation)
  uv run bb board 2026                      build the Edge Board page from the engine's outputs
  uv run bb stuff-model 2026                train only the portable model (for TrackMan / Rapsodo data)
  uv run bb trades                          the MLB trade graph: pull trades + WAR, build data/graph/, who trades with whom
  uv run bb front-office                    front-office ties vs trade partners (Baseball-Reference pages, career histories)
  uv run bb delivery 2026 670970            delivery and release profile from tracking data (scouting-report support)
  uv run bb shape-exposure build            shape exposure study: build | fit-dev | fit-2026 | followup | figure
  uv run bb grade velo 99.5 --hand L        20-80 velocity grade (vs 2026 starters, and the traditional anchors)
  uv run bb grade ofp SI=70 CH=70 FF=70 SL=55 command=60   pitcher OFP roll-up
  uv run bb db                              what is in the warehouse
  uv run bb db rebuild                      rebuild the warehouse from the cached pulls in data/raw/
"""
from __future__ import annotations

import argparse
import itertools
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


def cmd_seq(a: argparse.Namespace) -> None:
    from baseball.edge.familiarity import write_seq
    from baseball.ingest.league import SEASON_MONTHS, month_path

    files = [month_path(a.season, m) for m in SEASON_MONTHS if month_path(a.season, m).exists()]
    paths = write_seq(a.season, files)
    print(f"{a.season}: {len(paths)} sequence parts in data/seq/")


def cmd_familiarity(a: argparse.Namespace) -> None:
    from baseball.edge.familiarity import run

    from baseball.edge.familiarity import build_page, figure

    seasons = list(range(a.season - a.years + 1, a.season + 1))
    res = run(seasons)
    print(f"Page: {build_page()}\nFigure: {figure()}")
    m = res["main"]
    m = m[m["term"].eq("prev: same - other") & m["outcome"].str.startswith("whiff")]
    print("\nWhiff per swing, per earlier same-type pitch in earlier PAs today (vs another type):")
    for _, r in m.iterrows():
        print(f"  {r['group']:<9} {r['coef']:+.2f} pts (SE {r['se']:.2f}, t {r['t']:.1f}; {int(r['n']):,} swings)")


def cmd_cbt(a: argparse.Namespace) -> None:
    from baseball.roster.money import cbt_bill

    b = cbt_bill(a.payroll, a.years_over, season=a.season, threshold=a.threshold)
    if b.over <= 0:
        print(f"${a.payroll:.3f}M is ${-b.over:.3f}M under the ${b.threshold:.0f}M threshold: no tax.")
        return
    print(f"CBT payroll ${b.payroll:.3f}M, threshold ${b.threshold:.0f}M, ${b.over:.3f}M over, "
          f"season {b.consecutive_years} in a row")
    print(f"  base {b.base:.3f} + 20-40 surcharge {b.surcharge_20_40:.3f} + 40-60 {b.surcharge_40_60:.3f} "
          f"+ 60+ {b.surcharge_60_plus:.3f} = ${b.total:.3f}M")
    print(f"  next $1 of salary costs ${b.cost_of_next_dollar:.2f}; "
          f"top draft pick {'drops 10 places' if b.pick_drop else 'unaffected'}")


def cmd_cbt_check(a: argparse.Namespace) -> None:
    from baseball.roster.cases import cbt_2025_check

    t = cbt_2025_check()
    print(t[["club", "cbt_payroll", "consecutive_years", "actual", "computed", "difference"]]
          .round(6).to_string(index=False))


def cmd_service(a: argparse.Namespace) -> None:
    from baseball.roster.service import SUPER_TWO_CUTOFFS, timeline

    cutoff = a.cutoff or SUPER_TWO_CUTOFFS.get(a.season + 1)
    days = [int(d) for d in a.days.split(",")] if a.days else 172
    t = timeline(a.service, a.season, future_days=days, days_last_season=a.days_last, super_two_cutoff=cutoff)
    print(f"Service after {a.season}: {t.service_now}"
          + (f" (Super Two cutoff {cutoff})" if cutoff else " (no Super Two cutoff given)"))
    print("  path: " + ", ".join(f"{s} {v}" for s, v in t.path))
    print(f"  control: {t.control_seasons}; arbitration: {t.arb_seasons}"
          + (" (Super Two)" if t.super_two else ""))
    print(f"  free agent after: {t.free_agent_after or 'beyond the horizon'}")


def cmd_roster_cases(a: argparse.Namespace) -> None:
    from baseball.roster import cases

    cases.main()
    print(f"\nFigure: {cases.band_figure()}")

def cmd_levers(a: argparse.Namespace) -> None:
    from baseball.development import levers

    res = levers.run((a.season - 2, a.season - 1, a.season))
    print(f"Figure: {levers.figure()}")
    ans = res["answer"]
    print(f"\nPayoff per unit of league-net shape change ({len(res['pairs']):,} pitch pairs), confirmed (q < 0.05):")
    for _, r in ans[ans["verdict"].eq("confirmed")].iterrows():
        caveat = f"  [{r['caveat']}]" if isinstance(r.get("caveat"), str) and r["caveat"] else ""
        print(f"  {r['pitch_type']:<3} {r['change']:<52} whiff {r['whiff']:+.2f} pts (SE {r['whiff_se']:.2f}), "
              f"run value {r['rv100']:+.2f}/100 (SE {r['rv100_se']:.2f}){caveat}")
    v = res["validation"].set_index("pitch_type").loc["all"]
    print(f"\nOut of sample ({a.season - 1}->{a.season}): expected-whiff change removes {v['gain_physics_pct']:.1f}% of the "
          f"baseline's error; every lever {v['gain_levers_pct']:.1f}%")


def cmd_idp(a: argparse.Namespace) -> None:
    from pathlib import Path

    from baseball.development import idp

    text = idp.review(a.plan, a.as_of)
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n")
        print(f"\nReview: {a.out}")
    if a.figure:
        plan = idp.load_plan(a.plan)
        print(f"Figure: {idp.progress_figure(plan, idp.pitches_for(plan), a.figure)}")

def cmd_hook(a: argparse.Namespace) -> None:
    from baseball.edge.hook import figure, run

    res = run(a.season)
    s = res["summary"]
    m = res["calibration"].query("season == @a.season and spec == 'main'").iloc[0]
    print(f"Figure: {figure()}")
    print(f"\nCalibration slope, {a.season} (costs from {s['cost_seasons'][0]}-{s['cost_seasons'][-1]} only; 1.0 = calibrated): "
          f"{m['coef']:+.2f} (SE {m['se']:.2f}, p vs 1 = {m['p_vs_1']:.4f}; {int(m['n']):,} starter PAs)")
    pc = s["pooled_calibration"]
    print(f"Pooled {min(pc['seasons'])}-{max(pc['seasons'])}: {pc['slope']:+.2f} (SE {pc['se']:.2f})")
    r = res["removal"].query("season == @a.season and spec == 'next hitter' and term == 'x0'").iloc[0]
    print(f"Removal on the next hitter's index: {r['coef']:+.2f} points per run/100 PAs (SE {r['se']:.2f}; {int(r['n']):,} decisions)")


def cmd_hook_card(a: argparse.Namespace) -> None:
    from baseball.edge.hook import hook_card, load_context
    from baseball.ingest import people

    ctx = load_context(a.season)
    g = ctx["pa"][ctx["pa"]["game_pk"].eq(a.game_pk)]
    names = people.names([*g["batter"].unique(), a.pitcher])
    card = hook_card(a.game_pk, a.pitcher, ctx, names=names)
    if card.empty:
        print(f"No decision points for pitcher {a.pitcher} in game {a.game_pk} (not that game's starter, or out before the second time through).")
        return
    print(f"{names.get(a.pitcher, a.pitcher)}, game {a.game_pk}: cost vs. the average reliever, runs per 100 PAs "
          "(positive = the reliever is expected to be better); index at face value in brackets")
    for _, r in card.iterrows():
        nxt = "; ".join(f"{r[f'hitter_{j}']} ({r[f'times_{j}']}): {r[f'cost_base_{j}']:+.1f} [{r[f'cost_index_{j}']:+.1f}], idx {r[f'idx_{j}']:.1f}"
                        for j in (1, 2, 3))
        print(f"  after {r['after_bf']:>2} | inn {r['inning']} {r['outs']} out | {r['pitches']:>3} p | "
              f"{'PULLED ' if r['removed'] else ''}{nxt}")

def cmd_reliability(a: argparse.Namespace) -> None:
    from baseball.evaluation import reliability as R

    seasons = list(range(a.season - a.years + 1, a.season + 1))
    res = R.run(seasons, reps=a.reps, boot=a.boot, reuse_sums=a.reuse, ship=a.ship)
    print(f"Figure: {R.figure()}")
    p = res["params"]
    p = p[p["group"].eq("ALL")]
    print("\nM = sample for r = 0.5 (regress halfway); rho = year-to-year true-talent correlation")
    for _, r in p.iterrows():
        rho = f"{r['rho']:.2f}" if r.get("rho_use") == r.get("rho_use") else "  - "
        signal = "no signal" if r["r_at_max"] < 0.2 else f"M {r['M']:>8,.1f} {r['unit']}"
        print(f"  {r['metric']:<26} {signal:<45} rho {rho}")
    v = res["validation"]
    for test in ("within", "next"):
        t = v[v["test"].eq(test)]
        print(f"\nOut of sample ({test}): regressing beat raw for {int((t['cut_pct'] > 0).sum())} of {int(t['cut_pct'].notna().sum())} metrics; "
              f"median RMSE cut {t['cut_pct'].median():.1f}%; 95% interval coverage (median) {100 * t['cover95'].median():.0f}%")


def cmd_regress(a: argparse.Namespace) -> None:
    from baseball.evaluation.reliability import load_params, regress

    params = load_params()
    if a.metric not in params.index:
        sys.exit(f"Unknown metric {a.metric}. Examples: {', '.join(params.index[:5])}, pitcher/FF/velo")
    mean = a.mean if a.mean is not None else float(params.loc[a.metric, "league_mean_last"])
    out = regress(a.metric, a.observed, a.n, mean, horizon=a.horizon, games=a.games)
    print(f"{a.metric}: observed {a.observed} on n = {a.n:g}, league mean {mean:.4f}, horizon {a.horizon}")
    print(out.round(4).to_string(index=False))


def cmd_compare_relievers(a: argparse.Namespace) -> None:
    from pathlib import Path

    from baseball.evaluation.reliever import compare_relievers, summary_view

    res = compare_relievers(a.ids, a.season)
    if res["summary"].empty:
        sys.exit(f"None of {a.ids} pitched in {a.season} (check the ids with bb people / baseball.ingest.people.lookup).")
    with pd.option_context("display.width", 250, "display.max_colwidth", 70):
        print(f"Relievers, {a.season} regular season (data-informed, not a live look)\n")
        print(summary_view(res["summary"]).to_string())
        g = res["grades"].merge(res["summary"][["pitcher", "name"]], on="pitcher").sort_values(["name", "grade_present"], ascending=[True, False])
        print("\nPitch grades (20-80 = 50 + 10z of the percentile among MLB pitches of the type, 50+ swings)")
        print(g[["name", "pitch_type", "swings", "whiff_pct", "x_whiff_pct", "proj_whiff_pct", "grade_present",
                 "grade_2027", "grade_stuff"]].round(1).to_string(index=False))
    if a.out:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        for name, table in res.items():
            table.to_csv(out / f"{name}.csv", index=False)
        print(f"\nEvery table -> {out}/")


def cmd_delivery(a: argparse.Namespace) -> None:
    from baseball.evaluation import delivery as dv
    from baseball.ingest.league import load_season

    cols = ["game_pk", "game_type", "pitch_name", "at_bat_number", "pitch_number", "pitcher", "p_throws", "stand", "pitch_type",
            "description", "zone", "plate_z", "balls", "strikes", "release_speed", "release_spin_rate", "pfx_x", "pfx_z",
            "release_extension", "release_pos_x", "release_pos_z", "arm_angle", "vy0", "vz0", "ay", "az"]
    p = load_season(a.season, columns=cols)
    prof = dv.pitch_profile(p, a.pitcher)
    if prof.empty:
        sys.exit(f"No regular-season pitches for {a.pitcher} in {a.season}.")
    with pd.option_context("display.width", 250):
        print(f"Delivery and release profile, pitcher {a.pitcher}, {a.season} regular season (tracking data, not a look)\n")
        print(prof.round(2).to_string(index=False))
        print("\nSlot check against the primary pitch, season means (degrees; inches)")
        print(dv.slot_check(prof).round(2).to_string(index=False))
        print("\nRelease against the same game's fastballs (FF and SI), mean per pitch type (inches; degrees)")
        print(dv.release_offsets(p, a.pitcher).groupby("pitch_type")[["d_side_in", "d_height_in", "d_arm_deg"]].mean().round(2).to_string())
        c = dv.league_context(p, a.pitcher)
        print(f"\nLeague context ({c['pitchers']} {c['hand']}HP with 300+ pitches): extension {c['ext_ft']:.2f} ft "
              f"({c['ext_pct']:.0f}th pct; mean {c['ext_league_mean']:.2f}), arm angle {c['arm_angle']:.1f} "
              f"({c['arm_pct']:.0f}th pct; mean {c['arm_league_mean']:.1f})")
        print(f"Median release scatter, pitcher-pitch rows with 200+ ({c['scatter_rows']}): "
              f"height SD {c['median_sd_rel_z_ft']:.3f} ft, side SD {c['median_sd_rel_x_ft']:.3f} ft")
        print("League VAA (all / upper third): " + ", ".join(
            f"{k} {v:.2f} / {c['vaa_league_upper'].get(k, float('nan')):.2f}" for k, v in sorted(c["vaa_league"].items())
            if k in set(prof["pitch_type"])))
        fps = dv.first_pitch_strike(p, a.pitcher)
        print(f"First-pitch strike: {fps['pct']:.1f}% ({fps['strikes']} of {fps['n']}); league {fps['league_pct']:.1f}%")
        primary = prof["pitch_type"].iloc[0]
        print(f"\n{primary} velocity by pitch number in the outing")
        print(dv.velo_by_pitch_count(p, a.pitcher, primary).round(2).to_string(index=False))
        lengths = dv.outing_lengths(p, a.pitcher)
        print(f"Outings {len(lengths)}, mean {lengths.mean():.1f} pitches, max {lengths.max()}, 25+ pitches: {(lengths >= 25).sum()}")
        print("\nUsage by count state and batter hand")
        print(dv.usage_by_count(p, a.pitcher).round(1).to_string(index=False))
    if a.figure:
        print(f"\nFigure -> {dv.figure(p, a.pitcher, a.title or f'Pitcher {a.pitcher}, {a.season}', a.figure)}")


def cmd_bullpen_case(a: argparse.Namespace) -> None:
    from baseball.roster import bullpen_case

    bullpen_case.main()


def cmd_people(a: argparse.Namespace) -> None:
    from baseball.ingest import people

    path = people.refresh()
    print(f"{len(people.load(path)):,} people with MLBAM ids -> {path}")


def cmd_trades(a: argparse.Namespace) -> None:
    from baseball.roster import trades

    if not a.no_pull:
        trades.pull(refresh=a.refresh)
    n = trades.build()
    if a.report:
        b = trades.breakdown()
        with pd.option_context("display.width", 220, "display.max_columns", 20):
            m = trades.rivalry_model()
            print(f"\nModel (club effects, quasi-Poisson, dispersion {m['dispersion']}): same division {m['same_division']}, "
                  f"same league {m['same_league']}; non-rival dispersion {m['dispersion_non_rival']}")
            for k in ("by_type", "by_division", "by_window", "by_era", "by_subset"):
                print(f"\n{k}\n" + b[k].drop(columns=["p_more"]).to_string(index=False))
            w = b["by_window"].set_index(["window", "pairs_of"])
            win = {k: w.loc[(k, "same division")] for k in ("deadline (Jul-Aug)", "offseason (Oct-Mar)", "rest of season (Apr-Jun, Sep)")}
            for x, y in itertools.combinations(win, 2):
                print(f"{x} vs {y} (rivals): ratio %.2f, p = %.3f" % trades.compare_rate_ratios(
                    win[x].observed, win[x].rate_ratio, win[y].observed, win[y].rate_ratio, dispersion=m["dispersion"]))
            print("\nlopsided\n" + b["lopsided"].to_string(index=False) + f"\nMann-Whitney p = {b['lopsided_p']:.2f}")
            print("\nAngels-Braves across Minasian's tenure\n" + trades.pair_by_period("LAA", "ATL", ["2020-11-12", "2026-06-26"]).to_string(index=False))
            print("\nBurst scan (most extreme window per pair)\n" + trades.burst_scan().head(6).to_string(index=False))
            print(f"\nRandom 13-trade sets (Nov 2020 - June 2026) with a one-sided gap of 11.1+ WAR: {trades.side_gap_baseline():.1%}")
            tran = trades.RAW / "tran.txt"
            if tran.exists():
                rc = trades.retrosheet_check(tran)
                print("\nRetrosheet coverage (feed trades per Retrosheet trade)\n" + rc["coverage"].to_string(index=False))
                print("\nRetrosheet last deals before Apr. 15, 2009 (C = conditional, T = trade)\n" + rc["last_before_2009"].to_string())
                print("\nRetrosheet deals since Apr. 15, 2009\n" + rc["since_2009"].to_string())
        print(f"\nFigure -> {trades.report_figure()}")
    print("Trade graph -> data/graph/: " + ", ".join(f"{v:,} {k}" for k, v in n.items()))
    pairs, rivals = trades.pair_excess()
    print(f"\nDivision rivals: {rivals['observed']} trades vs {rivals['expected']} expected "
          f"(rate ratio {rivals['rate_ratio']}, 95% CI {rivals['ci95'][0]}-{rivals['ci95'][1]}, "
          f"{rivals['pairs_below']} of {rivals['pairs']} rival pairs below expected)")
    cols = ["pair", "observed", "expected", "ratio", "q_more", "q_fewer"]
    with pd.option_context("display.width", 200):
        print("\nPairs that trade most beyond their activity:\n" + pairs.nsmallest(8, "p_more")[cols].round(3).to_string(index=False))
        print("\nPairs that trade least:\n" + pairs.nsmallest(8, "p_fewer")[cols].round(3).to_string(index=False))
    pairs.to_csv("data/graph/pair_excess.csv", index=False)
    print(f"\nLoad into Neo4j: run {trades.CYPHER} (Neo4j's import folder is data/graph/).")


def cmd_front_office(a: argparse.Namespace) -> None:
    from baseball.roster import front_office as fo

    if not a.no_pull:
        print(f"{fo.pull():,} team pages fetched (cached in {fo.RAW}/)")
    panel = fo.staff_panel()
    print("Neo4j tables -> data/graph/: " + ", ".join(f"{v:,} {k}" for k, v in fo.export_graph_tables(panel=panel).items()))
    for expanded in (False, True):
        d = fo.build_panel(expanded=expanded)
        print(f"\n=== {'Expanded with Baseball-Reference listings' if expanded else 'Researched decision-makers and careers'} ===")
        with pd.option_context("display.width", 220):
            for k, t in fo.report_tables(d).items():
                print(f"\n{k}\n" + t.round(4).to_string(index=False))
            if a.permute and not expanded:
                for tie in ("tied", "protege"):
                    print(f"\npermutation test, {tie}: {fo.permutation_p(d, tie, draws=a.permute)}")
        if not expanded:
            for label, kw in (("Only stints with stated years", {"certain_only": True}),
                              ("September hires counted in that season", {"hire_cutoff": 10}),
                              ("August hires counted from the next season", {"hire_cutoff": 8})):
                c = fo.build_panel(**kw)
                with pd.option_context("display.width", 220):
                    print(f"\n=== {label} ===\n" + pd.concat([fo.fe_poisson(c, ["tied"]), fo.fe_poisson(c, ["protege"]),
                                                            fo.fe_poisson(c, ["tied"], stricter=True).assign(term="tied, stricter SE"),
                                                            fo.fe_poisson(c, ["protege"], stricter=True).assign(term="protege, stricter SE")]
                                                           ).round(4).to_string(index=False))
    print(f"\nFigure -> {fo.report_figure(fo.build_panel())}")
    print(f"\nLoad into Neo4j: run {fo.Path(fo.__file__).with_name('front_office.cypher')} after trade_graph.cypher.")


def cmd_db(a: argparse.Namespace) -> None:
    con = warehouse.connect()
    if a.action == "rebuild":
        print(f"{warehouse.rebuild(con):,} new rows loaded from data/raw/.")
    s = warehouse.summary(con)
    print("The warehouse is empty. Start with: uv run bb pull skubal tarik 2025" if s.empty else s.to_string(index=False))


def cmd_shape_exposure(a: argparse.Namespace) -> None:
    from baseball.edge import shape_exposure as S

    if a.step == "build":
        S.build()
    elif a.step == "fit-dev":
        S.run("dev")
    elif a.step == "fit-2026":
        S.run("2026")
    elif a.step == "followup":
        S.build_followup()
        S.fit_followup()
    else:
        print(S.figure())


def cmd_grade(a: argparse.Namespace) -> None:
    from baseball.evaluation.grades import ofp_pitcher, parse_pitches, velo_grade

    if a.what == "velo":
        g = velo_grade(a.mph, a.hand)
        print(f"{g['mph']} mph ({g['hand']}HP): {g['vs_2026_starters']} vs 2026 MLB starters (raw {g['vs_2026_starters_raw']}); "
              f"traditional anchors {g['traditional']} (raw {g['traditional_raw']})")
    else:
        pitches, command = parse_pitches(a.grades)
        r = ofp_pitcher(pitches, command)
        print(f"Starter estimate {r['starter_raw']} -> {r['starter_ofp']}; reliever estimate {r['reliever_raw']} -> {r['reliever_ofp']}")
        print(f"Starter-viable: {r['starter_viable']} (3+ pitches at 45+ and command 45+). Suggested OFP {r['suggested_ofp']}, {r['role']}.")
        print("A starting point: override it with a stated reason.")


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

    sq = sub.add_parser("seq", help="write the sequence copy of a season (batter ids, location; data/seq/)")
    sq.add_argument("season", type=int)
    sq.set_defaults(func=cmd_seq)

    fm = sub.add_parser("familiarity", help="does a pitch wear out? pitch-type familiarity across the league")
    fm.add_argument("season", type=int)
    fm.add_argument("--years", type=int, default=3, help="seasons to pool, ending at <season> (default 3)")
    fm.set_defaults(func=cmd_familiarity)

    cb = sub.add_parser("cbt", help="Competitive Balance Tax bill for a CBT payroll ($M)")
    cb.add_argument("payroll", type=float)
    cb.add_argument("years_over", type=int, help="consecutive seasons over, counting this one")
    cb.add_argument("--season", type=int, default=2026)
    cb.add_argument("--threshold", type=float, help="required for 2027+ (no agreement yet)")
    cb.set_defaults(func=cmd_cbt)

    cc = sub.add_parser("cbt-check", help="the engine against the real 2025 luxury-tax bills")
    cc.set_defaults(func=cmd_cbt_check)

    sv = sub.add_parser("service", help="service time -> arbitration, free agency and control")
    sv.add_argument("service", help="years.days, e.g. 2.142")
    sv.add_argument("season", type=int, help="the season that service is through")
    sv.add_argument("--days", help="service days in each future season, comma-separated (default 172 each)")
    sv.add_argument("--days-last", type=int, default=172, help="days in <season> (Super Two needs 86+)")
    sv.add_argument("--cutoff", help="Super Two cutoff (default: the published one for <season>+1, if any)")
    sv.set_defaults(func=cmd_service)

    rc = sub.add_parser("roster-cases", help="the 2025 tax check and the Skenes extension memo numbers")
    rc.set_defaults(func=cmd_roster_cases)

    lv = sub.add_parser("levers", help="which pitch-design changes stick and pay (pools the season and the two before)")
    lv.add_argument("season", type=int)
    lv.set_defaults(func=cmd_levers)

    ip = sub.add_parser("idp", help="progress on an individual development plan (YAML) from pitch data")
    ip.add_argument("plan", help="plan file, e.g. examples/idp-fictional.yaml")
    ip.add_argument("--as-of", default=None, help="review date (default: the plan's end)")
    ip.add_argument("--out", default=None, help="write the review markdown here")
    ip.add_argument("--figure", default=None, help="write the progress figure (PNG) here")
    ip.set_defaults(func=cmd_idp)

    hk = sub.add_parser("hook", help="the exposure-aware hook: does what a hitter has seen predict the next PA, and do managers price it?")
    hk.add_argument("season", type=int)
    hk.set_defaults(func=cmd_hook)

    hc = sub.add_parser("hook-card", help="the hook card for one start (run `bb hook <season>` first)")
    hc.add_argument("game_pk", type=int)
    hc.add_argument("pitcher", type=int, help="MLBAM id of the starter")
    hc.add_argument("--season", type=int, default=2026)
    hc.set_defaults(func=cmd_hook_card)

    rl = sub.add_parser("reliability", help="the Reliability Atlas: which numbers to trust, and how far to regress them")
    rl.add_argument("season", type=int)
    rl.add_argument("--years", type=int, default=3, help="seasons to pool, ending at <season> (default 3)")
    rl.add_argument("--reps", type=int, default=200, help="random game splits (default 200)")
    rl.add_argument("--boot", type=int, default=100, help="bootstrap draws of players (default 100)")
    rl.add_argument("--reuse", action="store_true", help="refit from the saved split sums instead of re-splitting")
    rl.add_argument("--ship", action="store_true", help="also replace the constants shipped with the code (after review only)")
    rl.set_defaults(func=cmd_reliability)

    rg = sub.add_parser("regress", help="regress a player's number with the atlas constants")
    rg.add_argument("metric", help="e.g. hitter/whiff, pitcher/CH/whiff, hitter/bat_speed")
    rg.add_argument("observed", type=float, help="the player's value (rates as proportions: 0.31)")
    rg.add_argument("n", type=float, help="his sample, in the metric's own events")
    rg.add_argument("--mean", type=float, help="the mean to regress toward (default: last season's league mean)")
    rg.add_argument("--horizon", default="season", choices=["season", "rest_of_season", "next_season"])
    rg.add_argument("--games", type=float, help="pitch physics only: games the n pitches came from (one outing = 1)")
    rg.set_defaults(func=cmd_regress)

    cr = sub.add_parser("compare-relievers", help="compare relievers: regressed results, stuff, velocity, workload, grades")
    cr.add_argument("season", type=int)
    cr.add_argument("ids", type=int, nargs="+", help="MLBAM pitcher ids (e.g. 670970 650556 664126)")
    cr.add_argument("--out", help="also write every table as CSV to this folder")
    cr.set_defaults(func=cmd_compare_relievers)

    dl = sub.add_parser("delivery", help="delivery and release profile from tracking data (slot, extension, VAA, release scatter, usage by count)")
    dl.add_argument("season", type=int)
    dl.add_argument("pitcher", type=int, help="MLBAM pitcher id (e.g. 670970)")
    dl.add_argument("--figure", help="also draw the movement and release-point figure to this path")
    dl.add_argument("--title", help="the figure's title (default: pitcher id and season)")
    dl.set_defaults(func=cmd_delivery)

    bc = sub.add_parser("bullpen-case", help="the 2026-27 bullpen acquisition memo's numbers and figure")
    bc.set_defaults(func=cmd_bullpen_case)

    tr = sub.add_parser("trades", help="the MLB trade graph (2009-): trades, WAR each club got, trade trees, who trades with whom")
    tr.add_argument("--no-pull", action="store_true", help="rebuild from the files already in data/raw/trades/")
    tr.add_argument("--refresh", action="store_true", help="re-pull every season's trades, not only the current one")
    tr.add_argument("--report", action="store_true", help="also print the rivals report's tables and redraw its figure")
    tr.set_defaults(func=cmd_trades)

    fo_ = sub.add_parser("front-office", help="front-office ties vs trade partners: executives, careers, the tie models")
    fo_.add_argument("--no-pull", action="store_true", help="use the cached team pages in data/raw/front_office/")
    fo_.add_argument("--permute", type=int, default=0, help="also run the permutation test with this many draws (1,000 in the report; slow)")
    fo_.set_defaults(func=cmd_front_office)

    pe = sub.add_parser("people", help="player names and ids from the Chadwick register (data/people/)")
    pe.set_defaults(func=cmd_people)

    se_ = sub.add_parser("shape-exposure", help="do hitters adapt to shapes they've seen from other pitchers? (plan: reports/2026-shape-exposure-plan.md)")
    se_.add_argument("step", choices=["build", "fit-dev", "fit-2026", "followup", "figure"])
    se_.set_defaults(func=cmd_shape_exposure)

    gr = sub.add_parser("grade", help="20-80 grades from measurements: fastball velocity, pitcher OFP roll-up")
    gsub = gr.add_subparsers(dest="what", required=True)
    gv = gsub.add_parser("velo", help="sitting velocity -> grade vs 2026 starters (and the traditional anchors)")
    gv.add_argument("mph", type=float)
    gv.add_argument("--hand", default="R", choices=["R", "L", "r", "l"])
    go = gsub.add_parser("ofp", help="pitcher OFP roll-up, e.g. SI=70 CH=70 FF=70 SL=55 command=60")
    go.add_argument("grades", nargs="+")
    gr.set_defaults(func=cmd_grade)

    d = sub.add_parser("db", help="what is in the warehouse")
    d.add_argument("action", nargs="?", choices=["rebuild"])
    d.set_defaults(func=cmd_db)

    a = ap.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()
