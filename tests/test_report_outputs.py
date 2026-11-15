"""The headline numbers in five reports, checked against the small saved tables in reports/outputs/.
If a report and its table disagree, one of them is stale."""
import json
from pathlib import Path

import pytest
from scipy.stats import t as tdist

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "outputs"


def _load(name):
    return json.loads((OUT / name).read_text())


def _text(name):
    return (ROOT / "reports" / name).read_text()


def test_bullpen_memo_matches_its_saved_table():
    b, memo = _load("bullpen-2026.json"), _text("2026-bullpen-acquisition-memo.md")
    line, p = b["line"], b["price"]["670970"]["comps_way"]
    assert line["n"] == 21 and "21 relief signings" in memo
    # expected price and its 95% prediction interval: $18.4M, $7.4M to $29.3M
    assert f"${p['aav']:.1f}M a year" in memo
    assert f"${p['lo']:.1f}M to ${p['hi']:.1f}M" in memo
    # landing odds are the line's t distribution (n - 2 df) at the walk-away AAV: 26% at $15.0M, 47% at $18.0M
    odds = lambda aav: 100 * tdist.cdf((aav - p["aav"]) / p["sd_pred"], line["n"] - 2)
    assert round(odds(15.0)) == 26 and "about 26% of the time (47% at $72M)" in memo
    assert round(odds(18.0)) == 47
    assert odds(18.0) / 100 == pytest.approx(b["landing"][2]["chance_price_at_or_below"], abs=1e-3)
    # the qualifying-offer cost and the walk-away it implies: 18.1 - 10.59 spread over four discounted years
    assert b["qo"]["670970"]["total_value"] == pytest.approx(10.59) and "about $10.6M" in memo
    annuity4 = sum(1 / 1.10 ** t for t in range(4))
    assert 4 * (b["breakeven"]["(670970, 4)"]["market"] - 10.59 / annuity4) == pytest.approx(60.2, abs=0.1)
    # workload retention and the availability case
    r, a = b["retention"], b["availability_case"]["(670970, 4)"]
    assert r["n"] == 170 and f"kept {100 * r['one_season']:.0f}% of that workload in 2025 and {100 * r['two_seasons']:.0f}% in 2026" in memo
    # the yearly step is the second season over the first: 0.475 / 0.628 = 0.756
    assert r["step"] == pytest.approx(r["two_seasons"] / r["one_season"], abs=0.001) and "0.76 of the first" in memo
    assert f"${a['total']:.1f}M" in memo and f"${a['breakeven_aav']:.1f}M" in memo


def test_edge_board_matches_its_saved_table():
    e, board = _load("edge-2026.json"), _text("2026-edge-board.md")
    g = e["gap_persistence"]
    assert f"r = {g['2024->2025']['r_gap']:.2f}" in board and f"and {g['2025->2026']['r_gap']:.2f} (2025" in board
    two = e["projection_two_year"]
    loo = two["loo_rmse"]
    assert f"RMSE {loo['two_seasons_plus_expected']:.2f} vs. {loo['last_season']:.2f} on {two['matched_pitches']} pitches" in board
    assert 100 * (1 - loo["two_seasons_plus_expected"] / loo["last_season"]) == pytest.approx(two["gain_vs_last_season_pct"], abs=0.01)
    assert f"{two['gain_vs_last_season_pct']:.1f}% against a regressed" in board
    h = e["holdout_fit_2024_25_scored_2025_26"]
    assert 100 * (1 - h["rmse_blend"] / h["rmse_regressed_baseline"]) == pytest.approx(h["gain_pct"], abs=0.01)
    assert f"cut error {h['gain_pct']:.1f}%" in board
    assert f"RMSE {h['rmse_blend']:.2f} vs. {h['rmse_regressed_baseline']:.2f}; 95% interval {h['gain_pct_lo']:.1f}% to {h['gain_pct_hi']:.1f}%" in board
    assert h["rmse_blend"] < h["rmse_regressed_baseline"] < h["rmse_raw_last_season"]
    assert f"{e['stuff_model_auc']['2026']:.3f}" in board and f"{e['portable_model']['auc']:.3f}" in board
    t = e["tell_cost_pooled"]
    assert f"+{t['raw']['slope']:.2f} whiff points" in board and f"+{t['controlled']['slope']:.2f} (" in board
    s = e["shifts_rebuilt_from_saved_table"]
    assert f"{s['candidates']} in 2026, by {s['pitchers']} pitchers" in board and f"{s['whiff_change_p_below_05']} ({100 * s['whiff_change_p_below_05'] / s['candidates']:.1f}%)" in board
    assert s["whiff_change_q_below_05"] == 0 and f"{s['whiff_change_q_below_10']} clear 10%" in board


def test_familiarity_report_matches_its_saved_table():
    f, rep = _load("familiarity-2024-26.json"), _text("2026-league-pitch-familiarity.md")
    main = {r["group"]: r for r in f["coefficients"] if r["outcome"].startswith("whiff") and r["term"] == "prev: same - other"}
    fb, br, off = (abs(main[k]["coef"]) for k in ("fastball", "breaking", "offspeed"))
    assert f"{fb:.2f} points on fastballs, {br:.2f} on breaking balls and {off:.2f} on changeups and splitters" in rep
    assert all(main[k]["p"] < 0.001 for k in ("fastball", "breaking", "offspeed"))
    assert f"{f['sample']['pitches']:,} pitches" in rep and f"{f['sample']['games']:,} games" in rep


def test_il_warning_report_matches_its_saved_table():
    s, rep = _load("il-warning-2026.json"), _text("2026-il-early-warning.md")
    readme = (ROOT / "README.md").read_text()
    pct = lambda x: f"{100 * x:.1f}%"
    m = s["specs"]["arm_14"]
    assert s["train"] == [2024, 2025] and s["test"] == 2026
    assert f"{s['sample']['pitches']:,} regular-season pitches" in rep and f"{s['sample']['outings']:,} pitcher outings" in rep
    # the forecast: AUCs and the bootstrap difference
    assert f"AUC of {m['auc']['naive']:.3f}" in rep and f"AUC {m['auc']['tracking']:.3f}" in rep
    d = m["tracking_vs_naive"]["auc"]
    gain = f"+{d['diff']:.3f}, 95% interval \u2212{abs(d['lo']):.3f} to +{d['hi']:.3f}"
    assert gain in rep
    assert f"AUC +{d['diff']:.3f}, \u2212{abs(d['lo']):.3f} to +{d['hi']:.3f}" in readme
    v = m["velocity_vs_naive"]["auc"]
    assert f"+{v['diff']:.3f} (\u2212{abs(v['lo']):.3f} to +{v['hi']:.3f})" in rep
    # the association, refit on 2026, and without the stint's last outing
    r, e = m["replication_in_test"], s["specs"]["arm_14_early"]["replication_in_test"]
    assert f"{r['odds_ratio']:.2f} times the odds" in rep and f"({r['or_lo']:.2f} to {r['or_hi']:.2f}, p < 0.001)" in rep
    assert r["p"] < 0.001
    assert f"{e['odds_ratio']:.2f} ({e['or_lo']:.2f} to {e['or_hi']:.2f})" in rep and e["p"] > 0.05
    # calibration slopes
    c = m["calibration"]
    assert f"calibration slopes {c['naive']['slope']:.2f} and {c['tracking']['slope']:.2f}" in rep
    # the chosen rule: threshold set on 2024-25, scored on 2026
    assert s["chosen_threshold_mph"] == 2.0
    t = s["rules"]["velo_drop_2.0"]["test"]
    assert f"2026:** {t['alerts']} flags, {t['alerts_per_club_season']:.1f} per club-season. {t['true_alerts']} were followed" in rep
    assert f"{pct(t['precision'])} ({pct(t['precision_lo'])} to {pct(t['precision_hi'])}), {t['lift']:.1f} times the base rate" in rep
    assert f"{t['false_alarms_per_club_season']:.1f} per club-season (0 to {s['false_alarms_by_club_test']['max']} by club, median {s['false_alarms_by_club_test']['median']:.0f})" in rep
    assert f"caught {t['stints_caught']} of {t['stints']} arm IL stints ({pct(t['share_caught'])})" in rep
    assert f"{t['true_alerts']} of {t['alerts']}; base rate {pct(t['base_rate'])}" in readme
    # the 2-3 mph bin
    b = next(x for x in s["velocity_bins"]["test"] if x["bin"] == "down 2-3")
    assert f"{pct(b['rate'])} went on the IL for an arm injury within 14 days ({b['events']} of {b['n']}; 95% interval {pct(b['lo'])} to {pct(b['hi'])})" in rep
    # starters vs relievers
    st, rl = s["rules"]["chosen_starter"]["test"], s["rules"]["chosen_reliever"]["test"]
    assert f"{st['true_alerts']} of {st['alerts']} flags ({pct(st['precision'])}; {pct(st['precision_lo'])} to {pct(st['precision_hi'])})" in rep
    assert f"{rl['true_alerts']} of {rl['alerts']} for relievers ({pct(rl['precision'])}; {pct(rl['precision_lo'])} to {pct(rl['precision_hi'])})" in rep
    # the multiple-test correction across the six outcome rows
    q = min(x["tracking_vs_naive"]["log_loss"]["q_bh"] for x in s["specs"].values())
    assert f"the smallest Benjamini\u2013Hochberg q is {q:.2f}" in rep


def test_skenes_memo_matches_its_saved_table(tmp_path):
    from baseball.roster.cases import save_checks
    s, memo = _load("skenes-checks-2026.json"), _text("2026-roster-cba-engine.md")
    # the saved table is what the code writes today
    assert json.loads(save_checks(tmp_path / "skenes.json").read_text()) == s
    m = lambda x: f"${x:.0f}M"
    inj, be = s["injury"], s["breakeven"]
    # the memo's own grid and the flat-price grid, row q = 0.25
    assert f"| 0.25 | {m(be['q=0.25, stress=0.0'])} | {m(be['q=0.25, stress=0.2'])} | {m(be['q=0.25, stress=0.35'])} |" in memo
    fl = s["breakeven_flat_price"]
    assert f"| 0.25 | {m(fl['q=0.25, stress=0.0'])} | {m(fl['q=0.25, stress=0.2'])} | {m(fl['q=0.25, stress=0.35'])} |" in memo
    # the published shares: 96 of 382 and 281 of 851
    conte, kriz = inj["rows"]
    assert f"{100 * conte['share']:.0f}% ({conte['n']} of {conte['of']})" in memo
    assert f"{100 * kriz['share']:.1f}% ({kriz['n']} of {kriz['of']})" in memo
    # the two readings of each share, and the scenario between them
    for r in (conte, kriz):
        share = f"{100 * r['share']:.0f}%"
        assert f"| Time missed only, {share} of pitchers | {100 * r['stress_chance_time_only']:.0f}% | {m(r['breakeven_time_only'])} |" in memo
        assert f"| Every surgery costs the full stress path, {share} of pitchers | {share} | {m(r['breakeven_full_stress'])} |" in memo
    assert f"| **The memo's scenario** | **20%** | **{m(inj['headline_breakeven'])}** |" in memo
    assert inj["headline_stress_chance"] == 0.2
    lo, hi = conte["stress_chance_time_only"], kriz["share"]
    assert f"{100 * lo:.0f}% to {100 * hi:.0f}%" in memo and lo < 0.2 < hi
    assert f"the bracket is {m(kriz['breakeven_full_stress'])} to {m(conte['breakeven_time_only'])}" in memo
    assert f"removes {100 * inj['war_share_lost_on_stress_path']:.0f}% of his projected wins" in memo
    assert f"{inj['days_out']} days removes {100 * inj['share_of_deal_missed']:.0f}% of an eight-year deal" in memo
    # the grid at the sourced shares
    g = inj["grid"]
    for q, label in ((0.0, "0"), (0.25, "0.25"), (0.5, "0.5"), (1.0, "1")):
        assert f"| {label} | {m(g[f'q={q}, stress=0.2'])} | {m(g[f'q={q}, stress=0.25'])} | {m(g[f'q={q}, stress=0.33'])} |" in memo
    # the win curve: the ratio, the multiples and the two walk-aways
    w = s["win_curve"]
    low, high = w["rows"]
    a, b = "market price = value at 86 to 91 wins", "market price = mean of the two bands"
    assert f"{w['ratio_86_91_to_78_83']:.1f} times as much" in memo
    assert f"| 86 to 91 wins | {high[a]['multiple']:.2f} ({high[b]['multiple']:.2f}) | {m(high[a]['breakeven'])} ({m(high[b]['breakeven'])}) |" in memo
    assert f"| 78 to 83 wins | {low[a]['multiple']:.2f} ({low[b]['multiple']:.2f}) | {m(low[a]['breakeven'])} ({m(low[b]['breakeven'])}) |" in memo
    assert f"The two anchors differ by {m(low[b]['breakeven'] - low[a]['breakeven'])} in the lower band" in memo
    assert f"walks away at {m(low[a]['breakeven'])} to {m(low[b]['breakeven'])}, not {m(w['market_breakeven'])}" in memo
    # the Nov. 3 offer
    n = s["nov3_cap"]
    assert f"{100 * (n['ratio'] - 1):.1f}% above this memo's path ($245.3M grown 3% is ${n['memo_cap_2028']:.1f}M)" in memo
    assert f"${n['own_club_max_2030_nov3']:.1f}M, not ${n['own_club_max_2030_memo']:.1f}M" in memo
    assert f"about {m(n['mlb_plan_ceiling_nov3'])}, not {m(n['mlb_plan_ceiling_memo'])}" in memo


def test_edge_board_savant_benchmark_matches_its_saved_table():
    b, board = _load("edge-savant-benchmark-2026.json"), _text("2026-edge-board.md")
    # what it is, and what is still open
    assert "This is not a Stuff+ comparison." in board and "Still open: a Stuff+ benchmark." in board
    assert "No outside benchmark yet" not in board
    assert len(b["savant_files"]) == 6 and all(f["status"] == 200 and "baseballsavant.mlb.com" in f["url"] and "csv=true" in f["url"]
                                               for f in b["savant_files"].values())
    assert not any("fangraphs" in f["url"].lower() for f in b["savant_files"].values())
    # 1. pipeline: my whiff rate against Savant's printed whiff%
    pipe = [b["pipeline"][s] for s in ("2024", "2025", "2026")]
    mad = [p["pitch_files_vs_savant"]["mean_abs_diff"] for p in pipe]
    assert f"sits {min(mad):.2f} to {max(mad):.2f} points from Savant's published whiff%" in board and max(mad) < 0.05
    p26 = pipe[2]["pitch_files_vs_savant"]
    assert f"that is {p26['mean_abs_diff']:.2f} on {p26['n']:,} pitches, and {100 * p26['share_within_tol']:.0f}% equal" in board
    no_tips = sum(p["pitch_files_without_foul_tips_vs_savant"]["mean_abs_diff"] for p in pipe) / 3
    assert f"about {no_tips:.1f} points" in board
    tab = [p["model_table_vs_savant"]["mean_abs_diff"] for p in pipe]
    assert f"sit {min(tab):.2f} to {max(tab):.2f} away" in board
    # 2. same season
    ci = lambda x: f"{x['r']:.2f} ({x['lo']:.2f} to {x['hi']:.2f})"
    pooled = b["same_season"]["pooled"]
    xm, xr, wr = pooled["x_whiff_pct ~ sv_miss_in"], pooled["x_whiff_pct ~ sv_rv100"], pooled["whiff_pct ~ sv_rv100"]
    assert f"r = {ci(xm['raw'])} on {xm['raw']['n']:,} pitches by {xm['raw']['pitchers']} pitchers" in board
    assert f"others of its type: r = {ci(xm['within_pitch_type'])}" in board
    assert f"r = {ci(xr['raw'])} together and {ci(xr['within_pitch_type'])} within type, on {xr['raw']['n']:,} pitches" in board
    assert f"reaches {wr['raw']['r']:.2f} and {wr['within_pitch_type']['r']:.2f}" in board
    t = b["miss_distance_by_type"]
    assert f"misses by {t['FF']['mean_in']:.1f} inches and the average curveball by {t['CU']['mean_in']:.1f}" in board
    # 3. next season: fit on one pair, scored on the other
    f, r = b["next_season"]["fit 2024->2025, scored 2025->2026"], b["next_season"]["fit 2025->2026, scored 2024->2025"]
    m, c = f["models"], f["contrasts"]
    assert f"({f['train_pitches']:,} pitches) and scored on 2025 → 2026 ({f['test_pitches']:,} pitches, {f['test_pitchers']} pitchers)" in board
    assert f"whiff rate {m['last_whiff']['rmse']:.2f}, my expected whiff {m['expected']['rmse']:.2f}, Savant's miss distance {m['miss']['rmse']:.2f}" in board
    gain = lambda x: f"{x['gain_vs_baseline_pct']:.1f}% ({x['gain_lo']:.1f}% to {x['gain_hi']:.1f}%)"
    size = lambda x: f"{abs(x['rmse_diff']):.2f} ({min(abs(x['lo']), abs(x['hi'])):.2f} to {max(abs(x['lo']), abs(x['hi'])):.2f})"
    assert f"mine is ahead by {size(c['expected minus miss'])}" in board
    ct = c["expected+type minus miss+type"]
    assert f"miss distance scores {m['miss+type']['rmse']:.2f} and mine {m['expected+type']['rmse']:.2f}: a tie (difference {abs(ct['rmse_diff']):.2f}, interval {ct['lo']:.2f} to {ct['hi']:.2f})" in board
    assert f"Mine cuts error {gain(m['last+expected'])}" in board and f"Miss distance cuts {gain(m['last+miss'])}" in board
    assert f"tie at {m['last+expected+type']['gain_vs_baseline_pct']:.1f}% and {m['last+miss+type']['gain_vs_baseline_pct']:.1f}%" in board
    assert f"All three cut {gain(m['last+expected+miss'])}" in board
    assert f"takes {size(c['last+expected+miss minus last+expected'])} of RMSE off my blend" in board
    rm, rc = r["models"], r["contrasts"]
    assert f"{r['test_pitches']:,} pitches): alone, {rm['last_whiff']['rmse']:.2f}, {rm['expected']['rmse']:.2f} and {rm['miss']['rmse']:.2f}" in board
    assert f"tie ({rm['last+expected']['gain_vs_baseline_pct']:.1f}% and {rm['last+miss']['gain_vs_baseline_pct']:.1f}%)" in board
    assert f"again adds {size(rc['last+expected+miss minus last+expected'])}" in board
    # the words follow the saved verdicts: a win needs an interval that excludes zero
    assert f["winner"] == {"alone": "expected", "alone_given_pitch_type": "tie", "with_last_season": "last+expected",
                           "with_last_season_given_pitch_type": "tie"}
    assert r["winner"]["with_last_season"] == "tie" and r["winner"]["alone_given_pitch_type"] == "tie"
    for res in (f, r):
        mm = res["models"]
        assert mm["last_whiff"]["rmse"] < mm["expected"]["rmse"] < mm["miss"]["rmse"]            # "wins alone", "same order"
        assert mm["last+expected"]["gain_lo"] > 0 and mm["last+miss"]["gain_lo"] > 0
        assert res["contrasts"]["last+expected+miss minus last+expected"]["hi"] < 0                # "holds something my model lacks"
        assert res["contrasts"]["expected minus miss"]["hi"] < 0                                   # "beats raw miss distance"
    # the same test set as the published held-out number, three fewer pitches in the fit
    h = _load("edge-2026.json")["holdout_fit_2024_25_scored_2025_26"]
    assert f["test_pitches"] == h["test_pitches"] and h["train_pitches"] - f["train_pitches"] == 3
    assert "three more pitches in the fit" in board
    assert f["rmse_raw_last_season"] == pytest.approx(h["rmse_raw_last_season"], abs=1e-3)
    assert m["last+expected"]["gain_vs_baseline_pct"] == pytest.approx(h["gain_pct"], abs=0.1)
    # the refit
    rf = b["refit_check"]
    k = rf["next_season"]["fit 2024->2025, scored 2025->2026"]
    assert f"moves expected whiff {rf['x_whiff_mean_abs_diff']:.1f} points per pitch on average (r = {rf['x_whiff_r_between_fits']:.3f} between fits)" in board
    assert k["winner"] == f["winner"] and f"the gain is {k['models']['last+expected']['gain_vs_baseline_pct']:.1f}%" in board
