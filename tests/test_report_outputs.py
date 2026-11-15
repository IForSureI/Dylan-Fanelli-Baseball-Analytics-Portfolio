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
    assert "This is not a Stuff+ comparison." in board
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


def test_edge_board_stuffplus_benchmark_matches_its_saved_table():
    b, board = _load("edge-stuffplus-benchmark-2026.json"), _text("2026-edge-board.md")
    assert "Still open: a Stuff+ benchmark" not in board and "Stuff+ benchmark (added Nov. 15)" in board
    z = lambda v: 0.0 if abs(v) < 0.005 else v
    ci = lambda x: f"{z(x['r']):.2f} ({x['lo']:.2f} to {x['hi']:.2f})"
    gain = lambda x: f"{x['gain_vs_baseline_pct']:.1f}% ({x['gain_lo']:.1f}% to {x['gain_hi']:.1f}%)"
    size = lambda x: f"{abs(x['rmse_diff']):.2f} ({min(abs(x['lo']), abs(x['hi'])):.2f} to {max(abs(x['lo']), abs(x['hi'])):.2f})"
    span = lambda x: f"{z(x['rmse_diff']):.2f}, interval {x['lo']:.2f} to {x['hi']:.2f}"
    # the source and its limits, as the source note describes them
    rows, rows15 = b["fangraphs_table"]["rows"], b["fangraphs_table"]["rows_15_ip"]
    assert (f"{rows['2024']} of 855 pitchers for 2024 (everyone with 15+ innings), {rows['2025']} of 873 for 2025 "
            f"(the 139 missing all threw under 15 innings) and {rows['2026']} of 868 for 2026") in board
    assert 873 - rows["2025"] == 139 and "as shown on the public page on Nov. 15, 2026" in board
    assert rows15["2024"] == rows["2024"] and rows15["2026"] == rows["2026"] and rows15["2025"] < rows["2025"]   # only 2025 holds shorter pitchers
    assert "One held-out test" in board and "There is no 2024 table" not in board
    # ids: no row is counted as mapped unless the register links it
    ids = b["id_mapping"]["by_season"]
    assert all(v["mapped"] + v["unmapped"] == v["rows"] == rows[s] for s, v in ids.items())
    assert (f"{ids['2024']['mapped']} of {ids['2024']['rows']} rows for 2024, {ids['2025']['mapped']} of {ids['2025']['rows']} for 2025 "
            f"and {ids['2026']['mapped']} of {ids['2026']['rows']} for 2026") in board
    assert f"The {ids['2026']['unmapped']} without a link are left out" in board
    # the pitch-type rule and the counts it rests on
    rule, cov = b["pitch_type_rule"], b["coverage"]
    assert rule["map"]["ST"] == "SL" and rule["map"]["SV"] == "CU" and rule["map"]["KC"] == "KC" and rule["map"]["FF"] == "FA"
    for e in rule["evidence"].values():   # sweepers and knuckle curves follow the counts in every season, 2024 included
        assert e["sweeper_no_slider"]["with_SL"] >= 0.95 * e["sweeper_no_slider"]["pitchers"]
        assert e["no_slider_sweeper_or_slurve"]["with_SL"] <= 0.15 * e["no_slider_sweeper_or_slurve"]["pitchers"]
        assert e["knuckle_curve_no_curveball"]["with_KC"] > 0.85 * e["knuckle_curve_no_curveball"]["pitchers"]
    e4, e5, e6 = (rule["evidence"][y] for y in ("2024", "2025", "2026"))
    for e in (e5, e6):                     # slurves: clean in 2025 and 2026, and the page says 2024 is not
        assert e["slurve_no_slider_or_sweeper"]["with_SL"] == 0 and e["slurve_no_slider_or_sweeper"]["with_CU"] == e["slurve_no_slider_or_sweeper"]["pitchers"]
    sv4 = e4["slurve_no_slider_or_sweeper"]
    assert f"2024 is less clean (SL filled {sv4['with_SL']} of {sv4['pitchers']}, CU {sv4['with_CU']} of {sv4['pitchers']})" in board
    assert (f"Slurves are {cov['2024']['slurves_with_stuff_plus']}, {cov['2025']['slurves_with_stuff_plus']} and "
            f"{cov['2026']['slurves_with_stuff_plus']} of the matched pitches") in board
    assert all(cov[y]["slurves_with_stuff_plus"] < 0.01 * cov[y]["with_stuff_plus"] for y in cov)
    assert f"SL column {e5['sweeper_no_slider']['with_SL']} times of {e5['sweeper_no_slider']['pitchers']} (2025) and {e6['sweeper_no_slider']['with_SL']} of {e6['sweeper_no_slider']['pitchers']} (2026)" in board
    assert f"have one {e5['no_slider_sweeper_or_slurve']['with_SL']} times of {e5['no_slider_sweeper_or_slurve']['pitchers']} and {e6['no_slider_sweeper_or_slurve']['with_SL']} of {e6['no_slider_sweeper_or_slurve']['pitchers']}" in board
    assert f"CU filled {e5['slurve_no_slider_or_sweeper']['with_CU']} of {e5['slurve_no_slider_or_sweeper']['pitchers']} and {e6['slurve_no_slider_or_sweeper']['with_CU']} of {e6['slurve_no_slider_or_sweeper']['pitchers']}" in board
    assert f"KC: {e5['knuckle_curve_no_curveball']['with_KC']} of {e5['knuckle_curve_no_curveball']['pitchers']} and {e6['knuckle_curve_no_curveball']['with_KC']} of {e6['knuckle_curve_no_curveball']['pitchers']}" in board
    assert (f"drops {cov['2024']['dropped_by_shared_column_rule']} pitches in 2024, {cov['2025']['dropped_by_shared_column_rule']} in 2025 "
            f"and {cov['2026']['dropped_by_shared_column_rule']} in 2026") in board
    # 1. same season
    pooled = b["same_season"]["pooled"]
    xs = pooled["x_whiff_pct ~ stuff_plus"]
    assert b["same_season_pooled_is"] == "2025 and 2026"
    assert f"r = {ci(xs['raw'])} across all pitches and {ci(xs['within_pitch_type'])} within pitch type, on {xs['raw']['n']:,} pitches by {xs['raw']['pitchers']} pitchers" in board
    assert len({v["raw"]["n"] for v in pooled.values()}) == 1   # the three measures are compared on one set of rows
    bt = b["expected_vs_stuff_by_pitch_type"]
    others = [v["r"] for k, v in bt.items() if k != "ST"]
    assert f"runs {min(others):.2f} to {max(others):.2f}, except sweepers: r = {ci(bt['ST'])} on {bt['ST']['n']} sweepers" in board
    assert bt["ST"]["lo"] < 0 < bt["ST"]["hi"] and min(v["lo"] for k, v in bt.items() if k != "ST") > 0
    w = lambda k: pooled[k]["within_pitch_type"]
    assert (f"Stuff+ {w('stuff_plus ~ whiff_pct')['r']:.2f}, Savant miss distance {w('sv_miss_in ~ whiff_pct')['r']:.2f}, "
            f"my expected whiff {w('x_whiff_pct ~ whiff_pct')['r']:.2f}") in board
    assert (f"Stuff+ {ci(w('stuff_plus ~ sv_rv100'))}, mine {ci(w('x_whiff_pct ~ sv_rv100'))}, "
            f"miss distance {ci(w('sv_miss_in ~ sv_rv100'))}") in board
    assert w("stuff_plus ~ sv_rv100")["r"] > w("x_whiff_pct ~ sv_rv100")["r"] and w("stuff_plus ~ whiff_pct")["r"] > w("x_whiff_pct ~ whiff_pct")["r"]
    # 2. pitcher level
    p = b["pitcher_level"]
    assert f"r = {ci(p['x_whiff_pct ~ stuff_plus'])} on {p['pitcher_seasons']:,} pitcher-seasons ({p['pitchers']} pitchers)" in board
    assert f"Stuff+ is {ci(p['stuff_plus ~ sv_rv100'])} and mine {ci(p['x_whiff_pct ~ sv_rv100'])}" in board
    # 3. next season, held out: weights from 2024 into 2025, scored on 2025 into 2026, 15+ innings throughout
    n = b["next_season"]
    held, cv = n["held_out"], n["cross_validated_by_pitcher"]
    ho, hall = held["15_ip_every_season"], held["all_rows_in_the_tables"]
    m, c = ho["models"], ho["contrasts"]
    assert held["fit"] == "2024->2025" and held["scored"] == "2025->2026"
    assert f"fit on 2024 → 2025 ({ho['train_pitches']} pitches) and scored on 2025 → 2026 ({ho['pitches']} pitches, {ho['pitchers']} pitchers)" in board
    assert hall["pitches"] - ho["pitches"] == held["test_pitches_from_pitchers_under_15_ip"] and hall["pitches"] == cv["pitches"]
    assert (f"{held['test_pitches_from_pitchers_under_15_ip']} of the {hall['pitches']} scored pitches come from such pitchers, and with them left in "
            f"the Stuff+ lead below is {size(hall['contrasts']['expected+type minus stuff+type'])}") in board
    assert f"(RMSE {m['last_whiff']['rmse']:.2f})" in board and f"Raw Stuff+ scores {m['stuff']['rmse']:.2f}" in board
    assert all(m["last_whiff"]["rmse"] < m[k]["rmse"] for k in ("expected", "stuff", "miss", "expected+type", "stuff+type", "miss+type"))
    assert f"Stuff+ {m['stuff+type']['rmse']:.2f}, miss distance {m['miss+type']['rmse']:.2f}, mine {m['expected+type']['rmse']:.2f}" in board
    assert f"ahead of mine by {size(c['expected+type minus stuff+type'])}" in board
    assert f"tie (difference {span(c['stuff+type minus miss+type'])})" in board
    assert f"mine {gain(m['last+expected+type'])}, Stuff+ {gain(m['last+stuff+type'])}, miss distance {gain(m['last+miss+type'])}" in board
    assert f"Mine against Stuff+: difference {span(c['last+expected+type minus last+stuff+type'])}" in board
    add_stuff, add_mine = c["last+expected+stuff+type minus last+expected+type"], c["last+expected+stuff+type minus last+stuff+type"]
    assert f"takes {size(add_stuff)} off RMSE" in board and f"Stuff+ blend takes {size(add_mine)} off" in board
    assert add_stuff["hi"] < 0 and add_mine["hi"] < 0                       # "each adds a little to the other"
    assert f"cut {gain(m['last+expected+stuff+miss+type'])}" in board
    # the words follow the saved verdicts, held out and in both innings samples
    for res in (ho, hall):
        assert res["winner"]["alone_given_pitch_type"] == "stuff+type" and res["winner"]["with_last_season_given_pitch_type"] == "tie"
        assert res["winner"]["stuff_vs_miss_alone_given_pitch_type"] == "tie"
    assert "Given the pitch type, Stuff+ beats my model." in board
    # the cross-validated numbers kept beside it
    cc = cv["contrasts"]
    assert cv["folds"] == 5 and f"five-fold cross-validation by pitcher ({cv['pitches']} pitches)" in board
    assert f"Stuff+ ahead of mine by {size(cc['expected+type minus stuff+type'])} given the pitch type" in board
    assert f"a tie once last season is in (difference {span(cc['last+expected+type minus last+stuff+type'])})" in board
    cv_add = cc["last+expected+stuff+type minus last+expected+type"]
    assert f"not clear there ({span(cv_add)})" in board and cv_add["lo"] < 0 < cv_add["hi"]
    assert cv["winner"]["alone_given_pitch_type"] == "stuff+type" and cv["winner"]["with_last_season_given_pitch_type"] == "tie"
    assert not any("stuff" in k for k in n["weights_from_earlier_pair"]["models"])
    # sweepers
    xw, sw = b["expected_vs_whiff_by_pitch_type"]["ST"], b["stuff_vs_whiff_by_pitch_type"]["ST"]
    assert xw["lo"] < 0 < xw["hi"] and sw["lo"] > xw["hi"]


def test_edge_board_sweeper_and_refit_checks_match_their_saved_table():
    k, board = _load("edge-stuff-checks-2026.json"), _text("2026-edge-board.md")
    z = lambda v: 0.0 if abs(v) < 0.005 else v
    ci = lambda x: f"{z(x['r']):.2f} ({x['lo']:.2f} to {x['hi']:.2f})"
    ys = ("2024", "2025", "2026")
    lst = lambda f: ", ".join(f(y) for y in ys[:-1]) + " and " + f(ys[-1])
    fit = k["fit_by_pitch_type"]
    assert (f"r = {lst(lambda y: format(fit[y]['ST']['r_expected_actual'], '.2f'))} in 2024, 2025 and 2026 "
            f"({lst(lambda y: str(fit[y]['ST']['pitchers']))} sweepers). On sliders: {lst(lambda y: format(fit[y]['SL']['r_expected_actual'], '.2f'))}") in board
    assert all(fit[y]["ST"]["r_expected_actual"] == min(v["r_expected_actual"] for v in fit[y].values()) for y in ys)   # weakest type every season
    s25 = fit["2025"]
    assert f"{s25['ST']['mean_expected']:.1f}% expected against {s25['ST']['mean_actual']:.1f}% actual" in board
    assert abs(s25["ST"]["mean_expected"] - s25["ST"]["mean_actual"]) < 1.5
    assert f"AUC inside the type {s25['ST']['swing_auc']:.2f} and {s25['SL']['swing_auc']:.2f} in 2025" in board
    st, sl = k["sweeper_correlates"], k["slider_correlates"]
    assert f"Across {st['chase_share']['n']} sweeper seasons" in board and f"at r = {ci(st['chase_share'])}" in board
    assert st["strongest_physical_input"] == "fb_velo" and f"r = {ci(st['fb_velo'])}, and no other passes" in board
    rest = max(abs(st[c]["r"]) for c in st["what_expected_whiff_follows"] if c != "fb_velo")
    assert f"no other passes {rest:.2f}" in board and rest < abs(st["fb_velo"]["r"]) < st["chase_share"]["lo"]
    assert f"speed gap to the fastball {sl['d_velo']['r']:.2f}, induced vertical break {sl['ivb_in']['r']:.2f}" in board
    fol = st["what_expected_whiff_follows"]
    assert f"follows velocity ({fol['velo']:.2f}) and extension ({fol['ext_ft']:.2f}). Those track sweeper whiffs at {st['velo']['r']:.2f} and {st['ext_ft']['r']:.2f}" in board
    side = k["by_hitter_side"]
    assert (f"same-side hitters r = {lst(lambda y: format(side[y]['ST']['same_side']['r_expected_actual'], '.2f'))}; against opposite-side hitters "
            f"{lst(lambda y: format(side[y]['ST']['opposite_side']['r_expected_actual'], '.2f'))}") in board
    co = k["carry_over"]
    a, b2 = co["2024->2025"]["ST"], co["2025->2026"]["ST"]
    assert f"(r = {a['r_actual_actual']:.2f} and {b2['r_actual_actual']:.2f})" in board
    assert f"next season's actual at {a['r_expected_next_actual']:.2f} and {b2['r_expected_next_actual']:.2f}" in board
    so = k["sweeper_only_model"]
    assert f"({so['swings']:,} swings, three seasons) reaches r = {so['r_expected_actual']:.2f} on {so['pitcher_seasons']} sweeper seasons" in board
    # the candidate fixes and the rule
    cand = k["candidates"]
    cd = lambda name: (lambda v: f"{z(v['diff']):+.2f} ({v['lo']:.2f} to {v['hi']:.2f})")(cand[name]["held_out_rmse_vs_base"]["ST"])
    assert (f"on {cand['pitch_type']['held_out_rmse_vs_base']['ST']['pitches']} sweepers: pitch type as an input {cd('pitch_type')}; "
            f"the fastball's velocity as an input {cd('fastball_velocity')}; its velocity and shape {cd('fastball_velocity_and_shape')}") in board
    for v in cand.values():
        comp = v["held_out_rmse_vs_base"]
        assert v["rule"]["adopt"] == (comp["ST"]["hi"] < 0 and not any(x["lo"] > 0 for x in comp.values()))
        assert not v["rule"]["adopt"] and v["rule"]["clearly_worse_on"] == []      # "None passes. None is clearly worse elsewhere either."
    assert k["model_changed"] is False and "The stuff model is unchanged, so no published number moved." in board
    # no sweeper grade from the model is quoted in the two reports that print pitch grades
    for name in ("2026-bullpen-acquisition-memo.md", "2026-bullpen-one-page.md", "2026-morejon-pro-scouting-report.md"):
        assert "sweeper" not in _text(name).lower()
    # refit noise
    o = k["refit_noise"]["orders"]
    mv, mx = [v["mean_abs_move"] for v in o.values()], [v["max_abs_move"] for v in o.values()]
    assert f"by {min(mv):.2f} to {max(mv):.2f} points on average (r = {min(v['r'] for v in o.values()):.3f} or better" in board
    assert f"is {min(mx):.1f} to {max(mx):.1f} points" in board
    sv = _load("edge-savant-benchmark-2026.json")["refit_check"]
    assert f"sat {sv['x_whiff_mean_abs_diff']:.1f} points per pitch from the saved tables and gave a held-out gain of {k['base_model']['held_out_gain_pct']:.1f}%" in board
    assert sv["x_whiff_mean_abs_diff"] < min(mv)                                   # "smaller than a reordering makes"


def _memo_rows(memo, heading):
    """The arsenal table under one pitcher's heading: pitch name -> (2027 grade, stuff grade) as printed."""
    block = memo[memo.index(heading):]
    block = block[block.index("| Pitch | Usage"):]
    out = {}
    for line in block.splitlines()[2:]:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells[0] != "Control":
            out[cells[0]] = (int(cells[6]), int(cells[7]))
    return out


MEMO_PITCHERS = {"670970": ("### Adrián Morejón", {"Sinker": "SI", "Changeup": "CH", "Slider": "SL", "Four-seamer": "FF"}),
                 "650556": ("### Bryan Abreu", {"Slider": "SL", "Four-seamer": "FF", "Cutter": "FC"}),
                 "664126": ("### Pete Fairbanks", {"Four-seamer": "FF", "Slider": "SL", "Cutter": "FC"})}


def test_bullpen_memo_model_numbers_are_the_saved_run():
    """Every stuff grade, 2027 grade, expected whiff, gap and engine projection the memo prints is generated from the
    saved run (bullpen-grades-2026.json), and the Morejón report repeats the same grades."""
    g = _load("bullpen-grades-2026.json")
    memo, scout = _text("2026-bullpen-acquisition-memo.md"), _text("2026-morejon-pro-scouting-report.md")
    pitches, by_season, proj = g["pitches"], g["pitcher_by_season"], g["projected_whiff_next_season"]
    sg = lambda v: f"+{abs(v):.1f}" if round(v, 1) >= 0 else f"\u2212{abs(v):.1f}"
    # the three arsenal tables, cell by cell
    seen = 0
    for pid, (heading, types) in MEMO_PITCHERS.items():
        rows = _memo_rows(memo, heading)
        assert set(rows) == set(types)
        for name, code in types.items():
            assert rows[name] == (pitches[f"{pid}_{code}"]["grade_next"], pitches[f"{pid}_{code}"]["grade_stuff"]), (pid, name)
            seen += 1
        # stuff vs. results by season
        for season, v in by_season[pid].items():
            assert f"{season}: {v['x_whiff_pct']:.1f}% expected, {sg(v['gap'])} gap." in memo, (pid, season)
    assert seen == len(pitches) == 10
    mo, ab, fa = "670970", "650556", "664126"
    msl, mch, mff, asl = pitches[mo + "_SL"], pitches[mo + "_CH"], pitches[mo + "_FF"], pitches[ab + "_SL"]
    # single pitches quoted in prose
    assert f"**Stuff grade:** {msl['grade_stuff']} (expected whiff {msl['x_whiff_pct']:.0f}%, {msl['pct_stuff']:.0f}th percentile;" in memo
    assert f"Graded 50 now and {msl['grade_next']} for 2027" in memo
    assert f"**Stuff:** {pitches[ab + '_FC']['grade_stuff']} (ten refits gave" in memo
    assert f"the four-seamer ({sg(mff['gap'])}) and changeup ({sg(mch['gap'])}) beat their physics, and the slider ({sg(msl['gap'])}) trailed it" in memo
    assert f"got whiffs {mch['gap']:.0f} points above its physics" in memo
    assert f"The engine projects {mch['proj_whiff_pct']:.1f}%" in memo and mch["pct_next"] >= 99      # "still the 99th percentile of changeups"
    assert f"Its physics grade ({msl['grade_stuff']};" in memo
    # the side-by-side labels: 2027 grades of the pitches named
    assert f"Changeup / four-seamer (75 / {mch['grade_next']})" in memo and mch["grade_next"] == mff["grade_next"]
    assert f"Slider and four-seamer (60 / {asl['grade_next']})" in memo and asl["grade_next"] == pitches[ab + "_FF"]["grade_next"]
    assert f"Cutter (65 / {pitches[fa + '_FC']['grade_next']}; 86 swings)" in memo
    # engine whiff projections: the three, and the candidate table
    w = lambda pid: f"{proj[pid]:.1f}"
    assert f"Abreu {w(ab)}%, Morejón {w(mo)}%, Fairbanks {w(fa)}%" in memo and proj[ab] > proj[mo] > proj[fa]
    assert f"the best 2027 whiff projection of the three ({w(ab)}%)" in memo and f"whiff projection, {w(ab)}%,** is the best of the three" in memo
    table = {"Adrián Morejón": mo, "Alex Vesia": "681911", "Raisel Iglesias": "628452", "David Bednar": "670280", "Bryan Abreu": ab,
             "Steven Okert": "595345", "Taylor Clarke": "664199", "Dennis Santana": "642701", "Paul Blackburn": "621112",
             "Sean Newcomb": "656794", "JoJo Romero": "668941", "Tyler Kinley": "641755", "Pete Fairbanks": fa}
    assert set(table.values()) == set(proj)
    block = memo[memo.index("| Rank of 38 |"):]
    rows = {c[1].strip("* "): c[-1].strip("* ") for c in ([x.strip() for x in line.strip("|").split("|")] for line in block.splitlines()[2:15])}
    assert rows == {name: w(pid) for name, pid in table.items()}
    low3 = [proj[k] for k in ("664199", "642701", "621112")]
    assert f"engine whiff {min(low3):.1f}–{max(low3):.1f}%" in memo
    # the reads that rest on these numbers still hold in the saved run
    m, a, f = by_season[mo], by_season[ab], by_season[fa]
    assert m["2026"]["gap"] > 0 and m["2024"]["gap"] < 0.5 and m["2025"]["gap"] < 0          # "before 2026 his results matched or trailed his physics"
    assert a["2025"]["gap"] > 0 and a["2026"]["gap"] > 0                                      # "results beat his physics two years running"
    assert f["2026"]["x_whiff_pct"] > f["2024"]["x_whiff_pct"] > f["2025"]["x_whiff_pct"]     # "best in 2026, after a dip in 2025"
    assert "his physics were at their best in 2026, after a dip in 2025" in memo and "improved every year" not in memo.split("What changed on Nov. 15")[0]
    # the formula OFP is still at its 60 cap for each pitcher, so no override or role changed
    for pid, control in ((mo, 60), (ab, 40), (fa, 40)):
        best = sorted((p["grade_next"] for k, p in pitches.items() if k.startswith(pid)), reverse=True)
        assert min(60, 0.55 * best[0] + 0.35 * best[1] + 0.10 * control) == 60
    # the Morejón report's copy of the memo's grades (present / 2027)
    for name, code, present in (("Sinker", "SI", 65), ("Changeup", "CH", 75), ("Four-seamer", "FF", 75), ("Slider", "SL", 50)):
        assert f"| {present} / {pitches[mo + '_' + code]['grade_next']} |" in scout[scout.index("## How these grades relate to the memo's"):], name
    assert f"a {msl['grade_stuff']} stuff grade from the physics" in scout


def test_reports_that_quote_pitch_grades_carry_the_refit_range():
    """Every stuff or 2027 pitch grade printed from the expected-whiff model is one fit. The memo and the scouting
    report must say how far a refit moves it, and name any grade that moves more than 5 points."""
    n, g = _load("edge-grade-noise-2026.json"), _load("bullpen-grades-2026.json")
    memo, scout = _text("2026-bullpen-acquisition-memo.md"), _text("2026-morejon-pro-scouting-report.md")
    pitches, printed = n["pitches"], g["pitches"]
    assert n["orders"]["count"] == 10 and all(p["fits"] == 10 for p in pitches.values()) and set(printed) == set(pitches)
    far = lambda r, v: max(abs(r["lo"] - v), abs(r["hi"] - v)) > 5
    unstable = sorted((k, kind) for k, p in printed.items() for kind, col in (("grade_stuff", "grade_stuff"), ("grade_next", "grade_next"))
                      if far(pitches[k][kind], p[col]))
    assert unstable == [("664126_SL", "grade_stuff")]                       # the one exception the memo names
    assert "Every stuff and 2027 grade printed for these three pitchers stayed within 5 points of the printed grade, with one exception" in memo
    fsl = pitches["664126_SL"]
    lo, hi = fsl["grade_stuff"]["lo"], fsl["grade_stuff"]["hi"]
    assert f"Fairbanks's slider stuff grade, printed {printed['664126_SL']['grade_stuff']}, ran {lo} to {hi}" in memo
    assert f"The physics grade is not stable: ten refits gave {lo} to {hi} (expected whiff {fsl['x_whiff_pct']['lo']:.1f}% to {fsl['x_whiff_pct']['hi']:.1f}%)" in memo
    assert fsl["gap"]["lo"] > 0 and "In every fit the results beat it" in memo
    # single numbers quoted in prose carry their range
    msl, mch, mff, afc = pitches["670970_SL"], pitches["670970_CH"], pitches["670970_FF"], pitches["650556_FC"]
    sg = lambda v: f"+{v:.1f}" if v >= 0 else f"\u2212{abs(v):.1f}"
    assert (f"ten refits gave {msl['grade_stuff']['lo']} to {msl['grade_stuff']['hi']} and {msl['x_whiff_pct']['lo']:.1f}% to "
            f"{msl['x_whiff_pct']['hi']:.1f}%)") in memo
    assert msl["grade_stuff"]["lo"] >= 70 and printed["670970_SL"]["grade_stuff"] >= 70     # "far ahead of its results (50)" holds in every fit
    assert f"(ten refits gave {afc['grade_stuff']['lo']} to {afc['grade_stuff']['hi']})" in memo
    assert (f"Ten refits gave {sg(mff['gap']['lo'])} to {sg(mff['gap']['hi'])}, {sg(mch['gap']['lo'])} to {sg(mch['gap']['hi'])} and "
            f"{sg(msl['gap']['lo'])} to {sg(msl['gap']['hi'])}, so the signs hold") in memo
    assert mch["gap"]["lo"] > 0 and mff["gap"]["lo"] > 0 and msl["gap"]["hi"] < 0
    assert f"(ten refits gave {mch['proj_whiff_pct']['lo']:.1f}% to {mch['proj_whiff_pct']['hi']:.1f}%)" in memo and mch["pct_next"]["lo"] >= 98.5
    assert f"ten refits gave {msl['grade_stuff']['lo']} to {msl['grade_stuff']['hi']}) is far ahead of its results (50)" in memo
    # no ranking or role rests on a grade that moved: the two best 2027 grades of each pitcher keep the formula OFP at its cap
    for pid, control in (("670970", 60), ("650556", 40), ("664126", 40)):
        lows = sorted((p["grade_next"]["lo"] for k, p in pitches.items() if k.startswith(pid)), reverse=True)
        assert 0.55 * lows[0] + 0.35 * lows[1] + 0.10 * control >= 57.5      # still a 60 on the 5-point scale
    # the scouting report
    assert f"a 70 stuff grade from the physics ({msl['grade_stuff']['lo']} to {msl['grade_stuff']['hi']} across ten refits of the model)" in scout
    assert "stayed within 5 points of the printed ones" in scout and "edge-grade-noise-2026.json" in scout and "edge-grade-noise-2026.json" in memo
    board = _text("2026-edge-board.md")
    assert f"kept {2 * len(printed) - len(unstable)} of the {2 * len(printed)} stuff and 2027 grades within 5 points" in board
    assert f"Fairbanks's slider stuff grade, {lo} to {hi}" in board


def test_edge_board_location_aware_measure_matches_its_saved_table():
    loc, board = _load("edge-stuff-location-2026.json"), _text("2026-edge-board.md")
    extra = _load("edge-stuffplus-benchmark-2026.json")["location_aware"]
    z = lambda v: 0.0 if abs(v) < 0.005 else v
    d = lambda v: f"{z(v['diff']):+.2f} ({z(v['lo']):.2f} to {z(v['hi']):.2f})"
    ys = ("2024", "2025", "2026")
    lst = lambda f: ", ".join(f(y) for y in ys[:-1]) + " and " + f(ys[-1])
    # said plainly: not stuff, and the stuff grade keeps its meaning
    assert "It is not stuff." in board and "The stuff grade keeps its meaning (physics only)" in board
    assert "My stuff grade on a sweeper stays unproven." in board
    ss = loc["same_season"]
    assert (f"r = {lst(lambda y: format(ss[y]['ST']['location']['r'], '.2f'))} in 2024, 2025 and 2026, where the physics number gave "
            f"{lst(lambda y: format(ss[y]['ST']['physics']['r'], '.2f'))}") in board
    assert all(v["location"]["r"] > v["physics"]["r"] for y in ys for v in ss[y].values())          # "higher on every pitch type"
    stw = extra["same_season_vs_whiff_by_pitch_type"]["ST"]
    assert f"On the {stw['n']} sweepers matched to Stuff+ it is {stw['r']:.2f} ({stw['lo']:.2f} to {stw['hi']:.2f})" in board
    h, hr = loc["held_out"]["fit 2024->2025, scored 2025->2026"], loc["held_out"]["fit 2025->2026, scored 2024->2025"]
    assert f"({h['train_pitches']} pitches), scored on 2025 → 2026 ({h['test_pitches']:,} pitches)" in board
    rn = h["r_with_next_season_whiff"]["ST"]
    assert f"at r = {rn['location']:.2f}; the physics number at {rn['physics']:.2f}; last season's whiff rate itself at {rn['last_whiff']:.2f}" in board
    alone, blend = h["contrasts"]["location minus physics"], h["contrasts"]["last+location minus last+physics"]
    assert f"all pitches {d(alone['all'])}; sweepers {d(alone['ST'])} on {alone['ST']['pitches']}" in board
    # the rule, recomputed from the table: adopted for a type only with an interval below zero and no type clearly worse
    types = {k: v for k, v in alone.items() if k != "all"}
    assert h["rule_alone"]["adopted_for"] == sorted(k for k, v in types.items() if v["hi"] < 0) and not any(v["lo"] > 0 for v in types.values())
    assert h["rule_alone"]["adopted_for"] == ["CH", "CU", "SI", "ST"] and "changeups, curveballs, sinkers and sweepers" in board
    assert loc["decision"]["alone"] == h["rule_alone"] and loc["decision"]["with_last_season"]["adopted_for"] == []
    assert f"all pitches {d(blend['all'])}, sweepers {d(blend['ST'])}, and sliders are clearly worse ({d(blend['SL'])})" in board
    assert blend["SL"]["lo"] > 0 and blend["ST"]["lo"] < 0 < blend["ST"]["hi"] and "So the projection keeps the physics number." in board
    assert f"Putting both in moves all pitches {d(h['contrasts']['last+physics+location minus last+physics']['all'])}" in board
    vs_last = h["contrasts"]["last+location minus last_whiff"]["ST"]
    assert f"Alone it scores {h['rmse']['location']:.2f} against {h['rmse']['last_whiff']:.2f}" in board and h["rmse"]["location"] > h["rmse"]["last_whiff"]
    assert f"changes sweeper RMSE by {d(vs_last)}, which is not clear" in board and vs_last["lo"] < 0 < vs_last["hi"]
    ra = hr["contrasts"]["location minus physics"]
    rr = hr["r_with_next_season_whiff"]["ST"]
    assert (f"all pitches {d(ra['all'])} alone, sweepers {d(ra['ST'])} on {ra['ST']['pitches']}, next-season r {rr['location']:.2f} against "
            f"{rr['physics']:.2f}") in board
    # the published blend inside this module is the published held-out number, to refit noise
    pub = _load("edge-2026.json")["holdout_fit_2024_25_scored_2025_26"]
    assert h["test_pitches"] == pub["test_pitches"] and h["rmse"]["last+physics"] == pytest.approx(pub["rmse_blend"], abs=0.02)
    # beside Stuff+: extra rows only
    sp = extra["held_out_15_ip"]
    sm, sc = sp["models"], sp["contrasts"]
    main = _load("edge-stuffplus-benchmark-2026.json")["next_season"]["held_out"]["15_ip_every_season"]
    assert sp["pitches"] == main["pitches"] and extra["pitches_missing_the_measure"] == {"train": 0, "test": 0}
    for k in ("stuff+type", "expected+type", "last+stuff+type"):                         # the shared rows are the same rows
        assert sm[k]["rmse"] == pytest.approx(main["models"][k]["rmse"])
    assert not any("location" in k for k in main["models"])
    size = lambda x: f"{abs(x['rmse_diff']):.2f} ({min(abs(x['lo']), abs(x['hi'])):.2f} to {max(abs(x['lo']), abs(x['hi'])):.2f})"
    span = lambda x: f"{z(x['rmse_diff']):.2f}, interval {x['lo']:.2f} to {x['hi']:.2f}"
    assert (f"location-aware scores {sm['location+type']['rmse']:.2f} against {sm['stuff+type']['rmse']:.2f} for Stuff+ and "
            f"{sm['expected+type']['rmse']:.2f} for my physics number; it is ahead of Stuff+ by {size(sc['location+type minus stuff+type'])}") in board
    assert "That is not a like-for-like win: Stuff+ does not see location." in board
    assert f"they tie (difference {span(sc['last+location+type minus last+stuff+type'])})" in board
    assert sp["winner"]["last+location+type vs last+stuff+type"] == "tie"
