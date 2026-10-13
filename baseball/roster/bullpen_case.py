"""The 2026-27 bullpen acquisition memo (Texas Rangers): every number the report quotes, and its figure.

`uv run python -m baseball.roster.bullpen_case` prints them and writes reports/figures/2026-bullpen-acquisition-memo.png.
Public data only. Outside facts carry their source and date; derived numbers say so.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from baseball.evaluation import reliever as R
from baseball.roster import acquisition as A
from baseball.stats import two_proportion

SEASON = 2026
CLUB = "TEX"
CANDIDATES = {670970: "Adrian Morejon", 650556: "Bryan Abreu", 664126: "Pete Fairbanks"}
REFERENCE = {670280: "David Bednar"}     # the market's other closer name, set aside (see the report)
AGE_2027 = {670970: 28, 650556: 30, 664126: 33, 670280: 32}   # 2027 seasonal ages, MLB.com (Oct. 8, 2026)

# The rest of the free-agent relief pool screened (MLB.com, "All of the 2026-2027 free agents," Oct. 8, 2026;
# no option listed). Ids from the Chadwick register.
POOL = {670970: "Adrian Morejon", 670280: "David Bednar", 650556: "Bryan Abreu", 664126: "Pete Fairbanks",
        628452: "Raisel Iglesias", 595345: "Steven Okert", 656464: "Kevin Ginkel", 681911: "Alex Vesia",
        657097: "Jacob Webb", 642397: "Gregory Soto", 660853: "Enyel De Los Santos", 641941: "Emilio Pagán",
        621237: "José Alvarado", 623465: "Evan Phillips", 592773: "Ryne Stanek", 642528: "Jonathan Loáisiga",
        641755: "Tyler Kinley", 573204: "Caleb Thielbar"}

FACTS = {
    "record_2026": "80-82; the third AL wild card (White Sox) finished 84-78 (final 2026 standings, SportRadar feed, read 2026-10-13)",
    "cbt_payroll_2026": 205.991666,     # Spotrac, Rangers 2026 tax page (read 2026-10-13; page shows no as-of date)
    "cbt_payroll_2026_si": 210.0,       # Spotrac via Matt Postins, Texas Rangers On SI, Oct. 2, 2026
    "cbt_payroll_2025": 241.380966,     # CBS Sports (Axisa), Dec. 20, 2025: third straight season over (AP)
    "committed_2027_tax": 142.1,        # Spotrac via Postins (SI), Oct. 2, 2026: eight players, incl. three mutual options
    "arb_2027": {"MacKenzie Gore": 8.9, "Jake Burger": 6.075, "Ezequiel Duran": 4.075, "Josh Jung": 5.95,
                 "Logan O'Hoppe": 2.9, "Cody Bradford": 1.2, "Robert Garcia": 0.925, "Wyatt Langford": 3.525,
                 "Evan Carter": 1.625, "Jacob Latz": 3.05},   # Zach Cioffi, Just Baseball, Oct. 7, 2026 (his own comps)
    "qo_tier_2026_27": {"TEX": "other", "SD": "payor", "HOU": "other", "MIA": "recipient", "NYY": "payor"},
    # MLB Trade Rumors, "Each Team's Penalty For Signing A Qualifying Offer-Rejecting Free Agent," republished by
    # NewsBeep Oct. 12, 2026 (mlbtraderumors.com blocks automated reading)
    "qo_2026": 22.025,                  # MLB.com glossary; the 2027 amount is set in early November 2026
}
OTHER_ROSTER_SPOTS = 14                 # ASSUMPTION: the rest of the 26/40-man at the 2026 minimum ($0.78M)
RANGERS_SECOND_PICK = 55                # ESTIMATE: 2nd-round pick of a club with the ~15th-worst record (80-82)
STRUCTURES = {                          # contract shapes priced in the report (AAV $M, years)
    670970: [(15.0, 4), (17.5, 4), (20.0, 5)],     # opening, walk-away, the "nine-figure" case
    650556: [(9.0, 2), (12.0, 2)],                  # opening, walk-away
    664126: [(5.0, 1)],
}


def rangers_payroll_2027() -> dict:
    arb = sum(FACTS["arb_2027"].values())
    rest = OTHER_ROSTER_SPOTS * 0.78
    return {"committed": FACTS["committed_2027_tax"], "arb": arb, "rest": rest,
            "total": FACTS["committed_2027_tax"] + arb + rest}


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = R.load_seasons([SEASON - 2, SEASON - 1, SEASON])
    return raw, R.flag(raw)


def need(d: pd.DataFrame) -> dict:
    """The club's bullpen in 2025 and 2026 against the league, and who threw its late, close innings."""
    from baseball.ingest import people

    tb = {s: R.team_bullpens(d, s) for s in (SEASON - 1, SEASON)}
    r = d[d["season"].eq(SEASON) & d["relief"] & d["team"].eq(CLUB)].copy()
    r["late_close"] = (r["inning"] >= 7) & ((r["bat_score"] - r["fld_score"]).abs() <= 3)
    ln = R.season_line(r)
    lc = r[r["late_close"]].groupby("pitcher")["pa"].sum().rename("late_close_pa")
    ln = ln.join(lc, on="pitcher").sort_values("late_close_pa", ascending=False)
    ln["name"] = ln["pitcher"].map(people.names(ln["pitcher"]))
    hand = {}
    for who, rows in (("club", r), ("league", d[d["season"].eq(SEASON) & d["relief"]])):
        g = rows.groupby("stand").agg(xw=("xwoba_pa", lambda s: np.nansum(s * rows.loc[s.index, "xwoba_den"])),
                                      den=("xwoba_den", "sum"))
        hand[who] = (g["xw"] / g["den"]).to_dict()
    return {"teams": tb, "club_relievers": ln, "xwoba_by_hand": hand}


def pool(d: pd.DataFrame, rs: pd.DataFrame, lm: float, repl: float) -> pd.DataFrame:
    """The free-agent relief pool screen: 2026 line, regressed run value, and the projection."""
    line = R.season_line(d[d["season"].eq(SEASON) & d["pitcher"].isin(list(POOL))])
    proj = pd.read_parquet(R.EDGE / str(SEASON) / "projection.parquet")
    pr = proj[proj["pitcher"].isin(list(POOL))]
    pr = pr.assign(pw=pr["proj_whiff_pct"] * pr["swings"]).groupby("pitcher").agg(pw=("pw", "sum"), sw=("swings", "sum"))
    rows = []
    for _, l in line.iterrows():
        p = A.project_relief_war(rs, int(l["pitcher"]), SEASON, lm, repl)
        rows.append({"pitcher": int(l["pitcher"]), "name": POOL[int(l["pitcher"])], "games": l["games"], "pa": l["pa"],
                     "k_bb_pct": l["k_bb_pct"], "rv100_2026": l["rv100"], "rv100_reg_3yr": p.rv100,
                     "war_role": p.war_role, "proj_whiff_2027": pr["pw"].get(l["pitcher"], np.nan) / pr["sw"].get(l["pitcher"], np.nan)})
    return pd.DataFrame(rows).sort_values("war_role", ascending=False)


def halves(d: pd.DataFrame, pid: int) -> dict:
    """2026 first half (through June) vs second half for one pitcher: line, fastball velocity, walk-rate test."""
    s = d[d["season"].eq(SEASON) & d["pitcher"].eq(pid)].copy()
    s["half"] = np.where(pd.to_datetime(s["game_date"]).dt.month <= 6, 1, 2)
    out = {}
    for h, g in s.groupby("half"):
        ln = R.season_line(g).iloc[0]
        fb = g[g["pitch_type"].eq("FF")]
        out[h] = {"games": int(ln["games"]), "pa": int(ln["pa"]), "bb": int(ln["bb"]), "k": int(ln["k"]),
                  "bb_pct": ln["bb_pct"], "k_pct": ln["k_pct"], "k_bb_pct": ln["k_bb_pct"], "whiff": ln["whiff"],
                  "xwoba": ln["xwoba"], "rv100": ln["rv100"], "ff_velo": fb["release_speed"].mean(),
                  "ff_spin": fb["release_spin_rate"].mean(), "ff_games": fb["game_pk"].nunique(), "ff_n": len(fb)}
    z, p = two_proportion(out[1]["bb"], out[1]["pa"], out[2]["bb"], out[2]["pa"])
    out["bb_test"] = {"z": z, "p": p}
    zk, pk = two_proportion(out[1]["k"], out[1]["pa"], out[2]["k"], out[2]["pa"])
    out["k_test"] = {"z": zk, "p": pk}
    return out


def money(rs: pd.DataFrame) -> dict:
    repl = A.replacement_level(rs)
    lm3 = A.league_relief_mean(rs, [SEASON - 2, SEASON - 1, SEASON])
    lm_comps = A.league_relief_mean(rs, [SEASON - 2, SEASON - 1])
    comps = A.comps_table(rs, SEASON, lm_comps, repl)
    line = A.market_line(comps)
    proj, values, breakeven = {}, [], {}
    for pid in list(CANDIDATES) + list(REFERENCE):
        p = A.project_relief_war(rs, pid, SEASON, lm3, repl)
        proj[pid] = p
        for aav, yrs in STRUCTURES.get(pid, []):
            v = A.contract_value(aav, yrs, p.war_role, p.war_neutral, AGE_2027[pid], SEASON + 1, line)
            values.append({"pitcher": pid, "aav": aav, "years": yrs, "total": aav * yrs, "pv_salary": v["pv_salary"],
                           "pv_value_market": v["pv_value_market"], "surplus_market": v["surplus_market"],
                           "pv_value_engine": v["pv_value_engine"], "surplus_engine": v["surplus_engine"]})
        for yrs in sorted({y for _, y in STRUCTURES.get(pid, [(0, 1)])}):
            breakeven[(pid, yrs)] = {b: A.breakeven_aav(yrs, p.war_role, p.war_neutral, AGE_2027[pid], SEASON + 1, line, basis=b)
                                     for b in ("market", "engine")}
    payroll = rangers_payroll_2027()
    tax = pd.concat([A.tax_table([payroll["total"], 225.0, 235.0, 244.0], aav, threshold=244.0) for aav in (7.0, 12.0, 18.0)])
    qo = {pid: A.qo_cost(FACTS["qo_tier_2026_27"][CLUB], FACTS["qo_tier_2026_27"][team], 64.0 if pid == 670970 else 24.0,
                         RANGERS_SECOND_PICK) for pid, team in ((670970, "SD"), (650556, "HOU"))}
    return {"replacement": repl, "league_relief_mean": lm3, "comps": comps, "line": line, "projections": proj,
            "values": pd.DataFrame(values), "breakeven": breakeven, "payroll_2027": payroll, "tax": tax, "qo": qo}


def walk_away(m: dict) -> dict:
    """The three routes to Morejon's walk-away and its qualifying-offer adjustment."""
    from baseball.roster.money import pv

    mo, ab = m["projections"][670970], m["projections"][650556]
    be_m = m["breakeven"][(670970, 4)]["market"]
    be_a = m["breakeven"][(650556, 2)]["market"]
    annuity4 = sum(1 / 1.1 ** t for t in range(4))
    path = A.war_path(mo.war_role, AGE_2027[670970], 4)
    engine_low_tier = pv([w * 8.51 * 1.03 ** (t + 1) for t, w in enumerate(path)]) / annuity4   # 1-2 WAR tier, 2027+ dollars
    d_role = mo.war_role - ab.war_role
    return {"morejon_market_breakeven_4y": be_m, "morejon_engine_2plus_tier_4y": m["breakeven"][(670970, 4)]["engine"],
            "morejon_engine_1to2_tier_4y": engine_low_tier, "extra_role_wins_vs_abreu": d_role,
            "indifference_vs_abreu_at_breakeven": be_a + d_role * 8.51 * 1.03,
            "cost_per_extra_win_at_17.5_vs_12": (17.5 - 12.0) / d_role,
            "qo_value": m["qo"][670970]["total_value"],
            "morejon_walkaway_with_qo_aav": (be_m * annuity4 - m["qo"][670970]["total_value"]) / annuity4}


# ------------------------------------------------------------------ figure

def figure(res: dict, m: dict, d: pd.DataFrame, path: str = "reports/figures/2026-bullpen-acquisition-memo.png") -> str:
    """Three panels: (a) each pitch's present grade vs its stuff grade (pitch colors fixed), (b) the 2025-26
    reliever market's price per projected win with the three candidates, (c) primary-fastball velocity by month."""
    import matplotlib.pyplot as plt

    from baseball.viz import INK, MUTED, OTHER, PITCH_COLORS, _style

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.4), dpi=150)
    marker = {670970: "o", 650556: "s", 664126: "^"}
    short = {670970: "Morejon", 650556: "Abreu", 664126: "Fairbanks"}

    # (a) grades: one row per pitch, hollow = stuff grade, filled = present grade, joined
    ax = axes[0]
    _style(ax)
    g = res["grades"][res["grades"]["pitcher"].isin(list(CANDIDATES))].copy()
    mix = res["usage"].set_index(["pitcher", "pitch_type"])["usage_pct"]
    g["order"] = g["pitcher"].map({pid: i for i, pid in enumerate(CANDIDATES)})
    g = g.sort_values(["order", "grade_present"], ascending=[False, True]).reset_index(drop=True)
    ys = np.arange(len(g)) + g["order"].map({2: 0, 1: 0.8, 0: 1.6}).to_numpy()
    for y, r in zip(ys, g.itertuples()):
        color = PITCH_COLORS.get(r.pitch_type, OTHER)
        ax.plot([r.grade_stuff, r.grade_present], [y, y], color=color, lw=2, zorder=2)
        ax.scatter([r.grade_stuff], [y], s=60, facecolors="white", edgecolors=color, linewidths=2, zorder=3)
        ax.scatter([r.grade_present], [y], s=60, color=color, edgecolors="white", linewidths=1.5, zorder=4)
    ax.set_yticks(ys)
    ax.set_yticklabels([f"{short[r.pitcher]} {r.pitch_type} ({mix.get((r.pitcher, r.pitch_type), np.nan):.0f}%)" for r in g.itertuples()],
                       fontsize=7.5, color=INK)
    ax.set_xlim(30, 80)
    ax.set_xticks(range(30, 85, 5))
    ax.set_xlabel("20-80 grade: hollow = stuff (physics only), filled = present (2026 whiff, regressed)", color=MUTED, fontsize=8)
    ax.set_title("(a) Pitch grades: stuff vs results", loc="left", color=INK, fontsize=10.5, fontweight="bold")

    # (b) market
    ax = axes[1]
    _style(ax)
    c = m["comps"]
    ax.scatter(c["war_neutral"], c["aav"], s=26, color=OTHER, alpha=0.8, linewidths=0, label="2025-26 relief signings")
    for r in c.itertuples():
        if r.name in ("Edwin Díaz", "Devin Williams", "Robert Suarez", "Pete Fairbanks", "Raisel Iglesias"):
            ax.annotate(r.name.split()[-1], (r.war_neutral, r.aav), xytext=(4, 2), textcoords="offset points", fontsize=7, color=MUTED)
    xs = np.linspace(0.3, 2.1, 10)
    ln = m["line"]
    ax.plot(xs, ln["intercept"] + ln["slope"] * xs, color=MUTED, lw=1.5, label="market line (least squares)")
    for pid in CANDIDATES:
        p = m["projections"][pid]
        y = A.market_aav(p.war_neutral, ln)
        ax.errorbar([p.war_neutral], [y], yerr=[[ln["resid_sd"]], [ln["resid_sd"]]], fmt=marker[pid], color=INK, ms=7,
                    capsize=3, lw=1, zorder=4)
        ax.annotate(f"{short[pid]} (2027 proj.)", (p.war_neutral, y), xytext=(6, -10), textcoords="offset points", fontsize=7.5, color=INK)
    ax.set_xlabel("Projected relief wins at signing (no leverage credit)", color=MUTED, fontsize=8.5)
    ax.set_ylabel("Average annual value, $M", color=MUTED, fontsize=8.5)
    ax.set_title("(b) What the reliever market paid per projected win", loc="left", color=INK, fontsize=10.5, fontweight="bold")
    ax.legend(loc="upper left", fontsize=7.5, frameon=False, labelcolor=INK)

    # (c) velocity by month
    ax = axes[2]
    _style(ax)
    styles = {670970: "-", 650556: "--", 664126: ":"}
    for pid in CANDIDATES:
        for season, alpha in ((SEASON - 1, 0.35), (SEASON, 1.0)):
            s = d[d["season"].eq(season) & d["pitcher"].eq(pid)]
            pt = R.primary_fastball(d[d["season"].eq(SEASON)]).get((pid, SEASON))
            s = s[s["pitch_type"].eq(pt)].assign(month=lambda x: pd.to_datetime(x["game_date"]).dt.month)
            s = s[s["month"].between(4, 9)]
            gm = s.groupby(["month", "game_pk"])["release_speed"].mean().groupby("month").mean()
            ax.plot(gm.index, gm.values, ls=styles[pid], marker=marker[pid], ms=5, lw=1.8, color=INK, alpha=alpha)
            ax.annotate(f"{short[pid]} {pt} {season}", (gm.index[-1], gm.values[-1]), xytext=(5, 0), textcoords="offset points",
                        fontsize=7.2, color=INK, alpha=max(alpha, 0.6), va="center")
    ax.set_xticks(range(4, 10))
    ax.set_xticklabels(["Apr", "May", "Jun", "Jul", "Aug", "Sep"])
    ax.set_xlim(3.7, 11.2)
    ax.set_ylabel("Primary fastball, mph (mean of game means)", color=MUTED, fontsize=8.5)
    ax.set_title("(c) Fastball velocity by month", loc="left", color=INK, fontsize=10.5, fontweight="bold")
    ax.text(0.02, 0.02, "faint = 2025, dark = 2026; Fairbanks's September is 2 outings, 10 fastballs", transform=ax.transAxes,
            fontsize=7.2, color=MUTED)
    fig.text(0.01, 0.005, "Statcast via Baseball Savant, regular seasons 2025-26. Grades: 50 + 10z of the percentile among MLB pitches "
             "of the type (50+ swings). Market: NBC Sports/Yahoo free-agent tracker (Feb. 12, 2026); projections derived "
             "(baseball/roster/acquisition.py); bars = the line's residual SD.", fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path)
    plt.close(fig)
    return path


def main() -> None:
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 60)
    raw, d = load()
    nd = need(d)
    for s, t in nd["teams"].items():
        print(f"\n== Bullpens {s} (rank 1 = best) ==")
        print(t[t["team"].eq(CLUB)].round(3).T.to_string())
    print("\n== Rangers relievers 2026 by late, close PA ==")
    print(nd["club_relievers"][["name", "p_throws", "games", "pa", "k_bb_pct", "whiff", "xwoba", "rv100", "late_close_pa"]].head(10).round(3).to_string())
    print("xwOBA by hand:", {k: {h: round(v, 3) for h, v in x.items()} for k, x in nd["xwoba_by_hand"].items()})
    print("Payroll 2027 before additions:", rangers_payroll_2027())

    rs = A.relief_seasons(d)
    mm = money(rs)
    print("\n== Pool ==")
    print(pool(d, rs, mm["league_relief_mean"], mm["replacement"]).round(3).to_string())
    res = R.compare_relievers(list(CANDIDATES) + list(REFERENCE), SEASON, raw=raw[raw["game_year"] >= SEASON - 1])
    print("\n== Summary ==")
    print(res["summary"].T.to_string())
    for k in ("grades", "velocity", "workload", "platoon", "usage", "gaps", "levers", "familiarity"):
        print(f"\n== {k} ==")
        print(res[k].round(3).to_string())
    print("\n== Abreu halves ==", halves(d, 650556))
    print("\n== Money ==")
    print("replacement", mm["replacement"], "league relief mean", mm["league_relief_mean"])
    print(mm["comps"].round(2).to_string())
    print("market line", mm["line"])
    for pid, p in mm["projections"].items():
        print(pid, {k: (round(float(v), 3) if isinstance(v, (float, np.floating)) else v) for k, v in p.__dict__.items()},
              "market AAV", round(A.market_aav(p.war_neutral, mm["line"]), 2))
    print(mm["values"].round(2).to_string())
    print({k: {b: round(v, 2) for b, v in x.items()} for k, x in mm["breakeven"].items()})
    print(mm["tax"].round(3).to_string())
    print(mm["qo"])
    print("\n== Walk-away arithmetic ==")
    for k, v in walk_away(mm).items():
        print(k, round(float(v), 3))
    from baseball.evaluation.reliability import regress
    h = halves(d, 650556)
    for half in (1, 2):
        r = regress("pitcher/FF/velo", h[half]["ff_velo"], h[half]["ff_n"], R.league_means(SEASON)["FF/velo"], games=h[half]["ff_games"])
        print(f"Abreu half {half} four-seam velo regressed:", r.round(2).to_dict("records")[0])
    for horizon in ("season", "next_season"):
        r = regress("pitcher/CH/whiff", 102 / 182, 182, R.league_means(SEASON)["CH/whiff"], horizon=horizon)
        print(f"Morejon changeup whiff regressed ({horizon}):", r.round(3).to_dict("records")[0])
    print(figure(res, mm, d))


if __name__ == "__main__":
    main()
