"""The 2026-27 bullpen acquisition memo (Texas Rangers): every number the report quotes, and its figure.

`uv run python -m baseball.roster.bullpen_case` prints them and writes reports/figures/2026-bullpen-acquisition-memo.png.
Public data only. Outside facts carry their source and date; derived numbers say so.
"""
from __future__ import annotations

import unicodedata

import numpy as np
import pandas as pd

from baseball.evaluation import reliever as R
from baseball.roster import acquisition as A
from baseball.stats import two_proportion

SEASON = 2026
CLUB = "TEX"
CANDIDATES = {670970: "Adrian Morejon", 650556: "Bryan Abreu", 664126: "Pete Fairbanks"}
REFERENCE = {670280: "David Bednar", 628452: "Raisel Iglesias"}   # set aside in the report, with reasons
AGE_2027 = {670970: 28, 650556: 30, 664126: 33, 670280: 32, 628452: 37}   # 2027 seasonal ages, MLB.com (Oct. 8, 2026)
ROLE = {670970: "B1", 650556: "B2", 664126: "depth", 670280: "B1", 628452: "B1"}   # the role each is priced in
# Fairbanks: thoracic outlet syndrome surgery announced Sept. 19, 2026, date to be set; "the typical recovery period
# for a pitcher is about nine or 10 months" (Christina De Nicola, MLB.com, Sept. 19, 2026). ASSUMPTION: he pitches
# about a third of the 2027 season (back around July) and a full 2028.
AVAILABILITY = {664126: [0.35, 1.0]}

# MLB.com, "All of the 2026-2027 free agents, position by position" (Oct. 8, 2026): every relief pitcher and the
# option shown. Only "None" are free agents now; club, player and mutual options and opt-outs are decided later.
FA_RELIEVERS = [
    ("Adrian Morejon", "None"), ("Garrett Whitlock", "Club"), ("David Bednar", "None"), ("Sean Newcomb", "None"),
    ("Steven Okert", "None"), ("Andres Munoz", "Club"), ("Tyler Alexander", "None"), ("Raisel Iglesias", "None"),
    ("Alex Vesia", "None"), ("Gregory Soto", "None"), ("Bryan Abreu", "None"), ("Emilio Pagan", "Opt-out"),
    ("Shawn Armstrong", "Mutual"), ("Andrew Kittredge", "None"), ("Brooks Raley", "None"), ("Mark Leiter", "None"),
    ("Jason Adam", "None"), ("Emmanuel Clase", "Club"), ("JoJo Romero", "None"), ("Jose Alvarado", "None"),
    ("Brock Burke", "None"), ("Kevin Ginkel", "None"), ("Jakob Junis", "Mutual"), ("Paul Blackburn", "None"),
    ("Taylor Clarke", "None"), ("Carlos Estevez", "Club"), ("Pete Fairbanks", "None"), ("Hoby Milner", "None"),
    ("Wandy Peralta", "Player"), ("Dennis Santana", "None"), ("Antonio Senzatela", "Club"), ("Caleb Thielbar", "Mutual"),
    ("Kenley Jansen", "Club"), ("Jose Suarez", "None"), ("Brent Suter", "None"), ("Ryan Yarbrough", "None"),
    ("Drew Anderson", "Club"), ("Enyel De Los Santos", "None"), ("Caleb Ferguson", "None"), ("Kolby Allard", "None"),
    ("Dietrich Enns", "Club"), ("Jonathan Loaisiga", "None"), ("Danny Coulombe", "None"), ("Luis Garcia", "None"),
    ("Tyler Kinley", "None"), ("Evan Phillips", "None"), ("Ryan Thompson", "None"), ("Justin Topa", "None"),
    ("Jacob Webb", "Club"), ("Andrew Chafin", "None"), ("Kyle Hart", "Club"), ("A.J. Minter", "None"),
    ("Ryan Brasier", "None"), ("Hunter Harvey", "Mutual"), ("Chris Martin", "None"), ("Taylor Rogers", "None"),
    ("Matt Strahm", "None"), ("Ryan Helsley", "Opt-out"), ("Pierce Johnson", "Mutual"), ("Sam Moll", "None"),
    ("John Schreiber", "None"), ("Blake Treinen", "None"), ("Yimi Garcia", "None"), ("Yuki Matsui", "Opt-out"),
    ("Rafael Montero", "None"), ("Jordan Romano", "None"), ("Ryne Stanek", "Club"), ("Robert Stephenson", "Club"),
    ("Matt Bowman", "None"), ("Brusdar Graterol", "None"), ("Joe Jimenez", "None"), ("Drew Pomeranz", "None"),
    ("A.J. Puk", "None"), ("Tanner Rainey", "None"), ("Drew Smith", "None"), ("Trevor Stephan", "Club"),
    ("Hunter Strickland", "None"), ("Rowan Wick", "Club"), ("Jake Woodford", "None"), ("Jalen Beeks", "None"),
    ("Ryan Borucki", "None"), ("Lou Trivino", "None"), ("Dan Altavilla", "None"), ("Chris Devenski", "None"),
    ("Luke Jackson", "None"), ("Jose Leclerc", "None"), ("Tommy Kahnle", "None"), ("Joe Ross", "None"),
    ("Keegan Akin", "None"), ("Jorge Alcala", "None"), ("Scott Barlow", "None"), ("Aaron Bummer", "None"),
    ("Paul Sewald", "None"), ("Ryan Weiss", "Club"), ("Trent Thornton", "None"), ("Genesis Cabrera", "None"),
    ("Tim Hill", "None"),
]

FACTS = {
    "record_2026": "80-82, 4.0 games behind the third AL wild card (White Sox, 84-78); MLB.com standings, last updated Oct. 7, 2026",
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
    "qo_2026": 22.025,                  # MLB.com glossary
    "qo_2027": 23.15,                   # reported Oct. 8, 2026 (Joel Sherman, New York Post)
}
OTHER_ROSTER_SPOTS = 14                 # ASSUMPTION: the rest of the 26/40-man at the 2026 minimum ($0.78M)
RANGERS_SECOND_PICK = 55                # ESTIMATE: 2nd-round pick of a club with the ~15th-worst record (80-82)
STRUCTURES = {                          # contract shapes priced in the report (AAV $M, years)
    670970: [(15.0, 4), (16.5, 4), (18.0, 4), (20.0, 4), (20.0, 5)],   # opening, walk-away with QO, walk-away, stretch, "nine figures"
    650556: [(9.0, 2), (12.5, 2)],                           # opening, walk-away
    664126: [(3.0, 2), (5.0, 2)],                            # a two-year rehab deal (2027 partial, 2028)
}
WALK_AWAYS = (16.4, 17.5, 18.0, 20.0, 22.0)


def rangers_payroll_2027() -> dict:
    arb = sum(FACTS["arb_2027"].values())
    rest = OTHER_ROSTER_SPOTS * 0.78
    return {"committed": FACTS["committed_2027_tax"], "arb": arb, "rest": rest,
            "total": FACTS["committed_2027_tax"] + arb + rest}


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = R.load_seasons([SEASON - 2, SEASON - 1, SEASON])
    return raw, R.flag(raw)


def _fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().replace(".", "").replace(" ", "")


def need(d: pd.DataFrame) -> dict:
    """The club's bullpen in 2025 and 2026 against the league, who threw its late, close innings, and the
    platoon gap with its test."""
    from baseball.ingest import people

    tb = {s: R.team_bullpens(d, s) for s in (SEASON - 1, SEASON)}
    r = d[d["season"].eq(SEASON) & d["relief"] & d["team"].eq(CLUB)].copy()
    r["late_close"] = (r["inning"] >= 7) & ((r["bat_score"] - r["fld_score"]).abs() <= 3)
    ln = R.season_line(r)
    lc = r[r["late_close"]].groupby("pitcher")["pa"].sum().rename("late_close_pa")
    ln = ln.join(lc, on="pitcher").sort_values("late_close_pa", ascending=False)
    ln["name"] = ln["pitcher"].map(people.names(ln["pitcher"]))
    lg = d[d["season"].eq(SEASON) & d["relief"]]
    stats = {(who, h): R.xwoba_stats(rows[rows["stand"].eq(h)]) for who, rows in (("club", r), ("league", lg)) for h in ("L", "R")}
    tests = {"club_vs_league_RHH": R.xwoba_diff_test(stats[("club", "R")], stats[("league", "R")]),
             "club_vs_league_LHH": R.xwoba_diff_test(stats[("club", "L")], stats[("league", "L")]),
             "club_RHH_vs_LHH": R.xwoba_diff_test(stats[("club", "R")], stats[("club", "L")])}
    return {"teams": tb, "club_relievers": ln, "xwoba": stats, "tests": tests,
            "late_close_pa": int(r.loc[r["late_close"], "pa"].sum())}


def pool(d: pd.DataFrame, rs: pd.DataFrame, lm: float, repl: float, min_pa: int = 150) -> pd.DataFrame:
    """Every MLB.com-listed free-agent reliever with no option pending and min_pa+ PA in the season, with the
    2026 line and the projection (B1 role leverage for all, so the column ranks talent)."""
    cur = d[d["season"].eq(SEASON)]
    names = cur.groupby("pitcher")["player_name"].last()
    key = {_fold(" ".join(reversed(n.split(", ")))): pid for pid, n in names.items() if isinstance(n, str)}
    rows = []
    proj = pd.read_parquet(R.EDGE / str(SEASON) / "projection.parquet")
    for name, option in FA_RELIEVERS:
        pid = key.get(_fold(name))
        if pid is None or option != "None":
            continue
        line = R.season_line(cur[cur["pitcher"].eq(pid)]).iloc[0]
        if line["pa"] < min_pa:
            continue
        p = A.project_relief_war(rs, int(pid), SEASON, lm, repl, li=A.ROLE_LIS["B1"])
        pr = proj[proj["pitcher"].eq(pid)]
        rows.append({"pitcher": int(pid), "name": name, "games": int(line["games"]), "pa": int(line["pa"]),
                     "k_bb_pct": line["k_bb_pct"], "rv100_2026": line["rv100"], "rv100_reg_3yr": p.rv100,
                     "war_b1": p.war_role, "proj_whiff_2027": (pr["proj_whiff_pct"] * pr["swings"]).sum() / pr["swings"].sum()})
    out = pd.DataFrame(rows).sort_values("war_b1", ascending=False).reset_index(drop=True)
    out["rank"] = np.arange(1, len(out) + 1)
    return out


def halves(d: pd.DataFrame, pid: int) -> dict:
    """2026 through June vs July on (a calendar split fixed before looking): line, fastball velocity, tests."""
    s = d[d["season"].eq(SEASON) & d["pitcher"].eq(pid)].copy()
    s["half"] = np.where(pd.to_datetime(s["game_date"]).dt.month <= 6, 1, 2)
    out = {}
    for h, g in s.groupby("half"):
        ln = R.season_line(g).iloc[0]
        fb = g[g["pitch_type"].eq("FF")]
        out[h] = {"games": int(ln["games"]), "pa": int(ln["pa"]), "bb": int(ln["bb"]), "ubb": int(ln["ubb"]), "k": int(ln["k"]),
                  "bb_pct": ln["bb_pct"], "k_pct": ln["k_pct"], "k_bb_pct": ln["k_bb_pct"], "whiff": ln["whiff"],
                  "xwoba": ln["xwoba"], "rv100": ln["rv100"], "ff_velo": fb["release_speed"].mean(),
                  "ff_spin": fb["release_spin_rate"].mean(), "ff_games": fb["game_pk"].nunique(), "ff_n": len(fb)}
    out["bb_test"] = dict(zip(("z", "p"), two_proportion(out[1]["bb"], out[1]["pa"], out[2]["bb"], out[2]["pa"])))
    out["k_test"] = dict(zip(("z", "p"), two_proportion(out[1]["k"], out[1]["pa"], out[2]["k"], out[2]["pa"])))
    return out


def platoon_tests(d: pd.DataFrame) -> dict:
    """Each candidate's xwOBA vs RHH minus vs LHH, with its test."""
    out = {}
    for pid in CANDIDATES:
        rows = d[d["season"].eq(SEASON) & d["pitcher"].eq(pid)]
        a, b = R.xwoba_stats(rows[rows["stand"].eq("R")]), R.xwoba_stats(rows[rows["stand"].eq("L")])
        out[pid] = {"R": a, "L": b, "test": R.xwoba_diff_test(a, b)}
    return out


def money(rs: pd.DataFrame) -> dict:
    """Projections, the market line (comps and candidates projected the same way), prices, values and walk-aways."""
    repl = A.replacement_level(rs)                                            # 2024-26, for 2027 projections
    repl_c = A.replacement_level(rs[rs["season"].isin([SEASON - 2, SEASON - 1])])   # 2024-25: no post-signing data
    lm3 = A.league_relief_mean(rs, [SEASON - 2, SEASON - 1, SEASON])
    lm2 = A.league_relief_mean(rs, [SEASON - 1, SEASON])
    lm_c = A.league_relief_mean(rs, [SEASON - 2, SEASON - 1])
    comps = A.comps_table(rs, SEASON, lm_c, repl_c)
    line = A.market_line(comps)
    proj, proj2, price, values, breakeven = {}, {}, {}, [], {}
    for pid in list(CANDIDATES) + list(REFERENCE):
        li = A.ROLE_LIS[ROLE[pid]]
        p = A.project_relief_war(rs, pid, SEASON, lm3, repl, li=li)
        proj[pid] = p
        # the comps' way: two seasons (5/4), comps' replacement level, so the line's price applies like for like
        p2 = A.project_relief_war(rs, pid, SEASON, lm2, repl_c, n_seasons=2, li=li)
        proj2[pid] = p2
        price[pid] = {"comps_way": A.market_price_interval(p2.war_neutral, line),
                      "three_season": A.market_price_interval(p.war_neutral, line)}
        avail = AVAILABILITY.get(pid)
        for aav, yrs in STRUCTURES.get(pid, []):
            v = A.contract_value(aav, yrs, p.war_role, p.war_neutral, AGE_2027[pid], SEASON + 1, line,
                                 availability=(avail or [1.0] * yrs)[:yrs] + [1.0] * max(0, yrs - len(avail or [])))
            values.append({"pitcher": pid, "aav": aav, "years": yrs, "total": aav * yrs, "pv_salary": v["pv_salary"],
                           "pv_value_market": v["pv_value_market"], "surplus_market": v["surplus_market"],
                           "pv_value_engine": v["pv_value_engine"], "surplus_engine": v["surplus_engine"]})
        for yrs in sorted({y for _, y in STRUCTURES.get(pid, [(0, 1)])}):
            av = (avail or [1.0] * yrs)[:yrs] + [1.0] * max(0, yrs - len(avail or []))
            breakeven[(pid, yrs)] = {b: A.breakeven_aav(yrs, p.war_role, p.war_neutral, AGE_2027[pid], SEASON + 1, line,
                                                        basis=b, availability=av) for b in ("market", "engine")}
            breakeven[(pid, yrs)]["market_comps_way"] = A.breakeven_aav(yrs, p2.war_role, p2.war_neutral, AGE_2027[pid],
                                                                        SEASON + 1, line, availability=av)
    payroll = rangers_payroll_2027()
    tax = pd.concat([A.tax_table([payroll["total"], 225.0, 235.0, 244.0], aav, threshold=244.0) for aav in (7.0, 12.0, 18.0)])
    qo = {pid: A.qo_cost(FACTS["qo_tier_2026_27"][CLUB], FACTS["qo_tier_2026_27"][team], 64.0 if pid == 670970 else 24.0,
                         RANGERS_SECOND_PICK) for pid, team in ((670970, "SD"), (650556, "HOU"))}
    landing = pd.DataFrame([{"walk_away_aav": w, "total_4y": 4 * w,
                             "chance_price_at_or_below": A.chance_price_at_or_below(w, proj2[670970].war_neutral, line)}
                            for w in WALK_AWAYS])
    iglesias_one_year = A.war_path(proj[628452].war_role, AGE_2027[628452], 1)[0]
    return {"replacement": repl, "replacement_comps": repl_c, "league_relief_mean": lm3, "comps": comps, "line": line,
            "projections": proj, "projections_comps_way": proj2, "price": price, "values": pd.DataFrame(values),
            "breakeven": breakeven, "payroll_2027": payroll, "tax": tax, "qo": qo, "landing": landing,
            "iglesias_2027_role_wins": iglesias_one_year}


def walk_away(m: dict) -> dict:
    """Morejon's walk-away (the club's value at the market line, three-season projection) and its QO adjustment."""
    be = m["breakeven"][(670970, 4)]
    annuity4 = sum(1 / 1.1 ** t for t in range(4))
    qo = m["qo"][670970]["total_value"]
    with_qo = (be["market"] * annuity4 - qo) / annuity4
    qo_e = A.qo_cost(FACTS["qo_tier_2026_27"][CLUB], "payor", 64.0, RANGERS_SECOND_PICK, pick_values=A.PICK_VALUE_2019)["total_value"]
    with_qo_e = (be["market"] * annuity4 - qo_e) / annuity4
    return {"value_breakeven_4y_three_season": be["market"], "value_breakeven_4y_comps_way": be["market_comps_way"],
            "engine_breakeven_4y_not_same_scale": be["engine"], "expected_price_comps_way": m["price"][670970]["comps_way"]["aav"],
            "qo_value_pv": qo, "walkaway_with_qo_aav": with_qo, "qo_cut_per_year": be["market"] - with_qo,
            "qo_cut_nominal_4y": 4 * (be["market"] - with_qo),
            "qo_value_pv_edwards_2019": qo_e, "walkaway_with_qo_aav_edwards_2019": with_qo_e}


# ------------------------------------------------------------------ figure

def figure(res: dict, m: dict, d: pd.DataFrame, path: str = "reports/figures/2026-bullpen-acquisition-memo.png") -> str:
    """Three panels: (a) each pitch's present grade vs its stuff grade (pitch colors fixed), (b) the 2025-26
    reliever market's price per projected win, with the candidates' 95% prediction intervals, (c) primary-fastball
    velocity by month."""
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
    ln = m["line"]
    ax.scatter(c["war_neutral"], c["aav"], s=26, color=OTHER, alpha=0.8, linewidths=0, label="2025-26 relief signings")
    for r in c.itertuples():
        if r.name in ("Edwin Díaz", "Devin Williams", "Robert Suarez", "Pete Fairbanks", "Raisel Iglesias"):
            ax.annotate(r.name.split()[-1], (r.war_neutral, r.aav), xytext=(4, 2), textcoords="offset points", fontsize=7, color=MUTED)
    xs = np.linspace(ln["x_min"], ln["x_max"], 10)
    ax.plot(xs, ln["intercept"] + ln["slope"] * xs, color=MUTED, lw=1.5, label="market line (least squares)")
    xe = np.linspace(ln["x_max"], 2.0, 5)
    ax.plot(xe, ln["intercept"] + ln["slope"] * xe, color=MUTED, lw=1.5, ls="--", label="extrapolated past the comps")
    for pid in CANDIDATES:
        p = m["projections_comps_way"][pid]
        pi = m["price"][pid]["comps_way"]
        lo = max(pi["lo"], 0.78)        # no contract pays less than the minimum salary
        ax.errorbar([p.war_neutral], [pi["aav"]], yerr=[[pi["aav"] - lo], [pi["hi"] - pi["aav"]]], fmt=marker[pid],
                    color=INK, ms=7, capsize=3, lw=1, zorder=4)
        ax.annotate(short[pid], (p.war_neutral, pi["aav"]), xytext=(6, -10), textcoords="offset points", fontsize=7.5, color=INK)
    ax.set_xlabel("Projected relief wins at signing (two seasons, no leverage credit)", color=MUTED, fontsize=8.5)
    ax.set_ylabel("Average annual value, $M", color=MUTED, fontsize=8.5)
    ax.set_title("(b) What the reliever market paid per projected win", loc="left", color=INK, fontsize=10.5, fontweight="bold")
    ax.legend(loc="upper left", fontsize=7.5, frameon=False, labelcolor=INK)

    # (c) velocity by month
    ax = axes[2]
    _style(ax)
    styles = {670970: "-", 650556: "--", 664126: ":"}
    prim = R.primary_fastball(d[d["season"].eq(SEASON)])
    for pid in CANDIDATES:
        pt = prim.get((pid, SEASON))
        for season, alpha in ((SEASON - 1, 0.35), (SEASON, 1.0)):
            s = d[d["season"].eq(season) & d["pitcher"].eq(pid) & d["pitch_type"].eq(pt)]
            s = s.assign(month=pd.to_datetime(s["game_date"]).dt.month)
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
    fig.text(0.01, 0.005, "Statcast via Baseball Savant, regular seasons 2024-26. Grades: 50 + 10z of the percentile among MLB pitches "
             "of the type (50+ swings). Market: NBC Sports/Yahoo free-agent tracker (Feb. 12, 2026); projections derived "
             "(baseball/roster/acquisition.py); bars = 95% prediction intervals for one signing (floored at the minimum salary).", fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path)
    plt.close(fig)
    return path


def _r(x):
    return round(float(x), 3) if isinstance(x, (float, np.floating)) else x


def main() -> None:
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 60)
    raw, d = load()
    nd = need(d)
    for s, t in nd["teams"].items():
        print(f"\n== Bullpens {s} (rank 1 = best) ==")
        print(t[t["team"].eq(CLUB)].round(3).T.to_string())
    print("\n== Rangers relievers 2026 by late, close PA (total late, close PA:", nd["late_close_pa"], ") ==")
    print(nd["club_relievers"][["name", "p_throws", "games", "pa", "k_bb_pct", "whiff", "xwoba", "rv100", "late_close_pa"]].head(10).round(3).to_string())
    print("xwOBA by hand:", {k: {kk: _r(vv) for kk, vv in v.items()} for k, v in nd["xwoba"].items()})
    print("tests:", {k: {kk: _r(vv) for kk, vv in v.items()} for k, v in nd["tests"].items()})
    print("Payroll 2027 before additions:", rangers_payroll_2027())

    rs = A.relief_seasons(d)
    mm = money(rs)
    print("\n== Pool ==")
    print(pool(d, rs, mm["league_relief_mean"], mm["replacement"]).round(3).to_string())
    res = R.compare_relievers(list(CANDIDATES) + [670280], SEASON, raw=raw[raw["game_year"] >= SEASON - 1])
    print("\n== Summary ==")
    print(res["summary"].T.to_string())
    for k in ("grades", "velocity", "workload", "platoon", "usage", "gaps", "levers", "familiarity"):
        print(f"\n== {k} ==")
        print(res[k].round(3).to_string())
    print("\n== Abreu halves ==", {k: ({kk: _r(vv) for kk, vv in v.items()}) for k, v in halves(d, 650556).items()})
    print("\n== Platoon tests ==", {pid: {k: {kk: _r(vv) for kk, vv in v.items()} for k, v in t.items()} for pid, t in platoon_tests(d).items()})
    print("\n== Money ==")
    print("replacement (2024-26)", mm["replacement"], "replacement for comps (2024-25)", mm["replacement_comps"],
          "league relief mean", mm["league_relief_mean"])
    print(mm["comps"].round(2).to_string())
    print("market line", {k: v for k, v in mm["line"].items() if k != "cov"})
    for pid in mm["projections"]:
        print(pid, "3-season:", {k: _r(v) for k, v in mm["projections"][pid].__dict__.items()})
        print(pid, "comps' way:", {k: _r(v) for k, v in mm["projections_comps_way"][pid].__dict__.items()})
        print(pid, "price:", {b: {k: _r(v) for k, v in x.items()} for b, x in mm["price"][pid].items()})
    print(mm["values"].round(2).to_string())
    print({k: {b: round(float(v), 2) for b, v in x.items()} for k, x in mm["breakeven"].items()})
    print(mm["tax"].round(3).to_string())
    print(mm["qo"])
    print(mm["landing"].round(3).to_string())
    print("Iglesias 2027 role wins, one year aged:", round(mm["iglesias_2027_role_wins"], 3))
    print("\n== Walk-away ==", {k: round(float(v), 3) for k, v in walk_away(mm).items()})
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
