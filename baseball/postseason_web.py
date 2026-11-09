"""2026 Postseason Snippets, interactive: the ten charts as one web page where every player, club and
pitch opens its breakdown on hover (tap on a phone, focus with the keyboard).

The page is built from the same pull and the same data steps as baseball/postseason.py, and the build
stops if any headline number differs from reports/2026-postseason-snippets/findings.json, so the
interactive charts can never drift from the published ones.

    uv run python -m baseball.postseason_web     # -> docs/postseason.html (served on GitHub Pages)

Data: Baseball Savant pitch-level search and the MLB Stats API (see baseball/postseason.py).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from baseball import postseason as ps

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "postseason.html"
TEMPLATE = Path(__file__).with_name("postseason_web.html")
FINDINGS = ps.OUT / "findings.json"

ROUND = {"F": "Wild Card", "D": "Division Series", "L": "LCS", "W": "World Series"}
ROUND_ORDER = ["F", "D", "L", "W"]
HITS = {"single": 1, "double": 2, "triple": 3, "home_run": 4}
WALKS = {"walk", "intent_walk"}
NOT_AB = WALKS | {"hit_by_pitch", "sac_fly", "sac_bunt", "catcher_interf", "sac_fly_double_play", "sac_bunt_double_play"}
KS = {"strikeout", "strikeout_double_play"}
GROUP = {"FF": "Fastball", "SI": "Fastball", "FC": "Fastball",
         "SL": "Breaking", "ST": "Breaking", "CU": "Breaking", "KC": "Breaking", "SV": "Breaking", "CS": "Breaking",
         "CH": "Offspeed", "FS": "Offspeed", "FO": "Offspeed", "SC": "Offspeed", "KN": "Offspeed", "EP": "Offspeed"}
EVENT = {"single": "single", "double": "double", "triple": "triple", "home_run": "home run", "walk": "walk",
         "intent_walk": "intentional walk", "hit_by_pitch": "hit by pitch", "strikeout": "strikeout",
         "strikeout_double_play": "strikeout double play", "field_out": "out", "force_out": "force out",
         "grounded_into_double_play": "double play", "double_play": "double play", "sac_fly": "sac fly",
         "sac_bunt": "sac bunt", "field_error": "reached on error", "fielders_choice": "fielder's choice",
         "fielders_choice_out": "fielder's choice", "catcher_interf": "catcher's interference"}


def r3(x) -> float | None:
    return None if x is None or pd.isna(x) else round(float(x), 3)


def r1(x) -> float | None:
    return None if x is None or pd.isna(x) else round(float(x), 1)


def ev_name(e) -> str:
    return EVENT.get(str(e), str(e).replace("_", " "))


def moment(row, people, opp_col: str) -> dict:
    """One plate appearance, described plainly: date, round, inning, matchup and result."""
    half = "top" if row.inning_topbot == "Top" else "bottom"
    return {"date": pd.to_datetime(row.game_date).strftime("%b %-d"), "round": ROUND[row.game_type],
            "inning": f"{half} {int(row.inning)}", "vs": ps.nm(people, row[opp_col]), "event": ev_name(row.events),
            "wpa": r3(row.bat_wpa if opp_col == "pitcher" else -row.bat_wpa)}


def slash(p: pd.DataFrame) -> dict:
    ev = p.events
    h = ev.isin(HITS).sum()
    bb, hbp, sf = ev.isin(WALKS).sum(), (ev == "hit_by_pitch").sum(), ev.isin({"sac_fly", "sac_fly_double_play"}).sum()
    ab = len(p) - ev.isin(NOT_AB).sum()
    tb = ev.map(HITS).fillna(0).sum()
    obp_d = ab + bb + hbp + sf
    return {"ab": int(ab), "h": int(h), "hr": int((ev == "home_run").sum()), "bb": int(bb), "k": int(ev.isin(KS).sum()),
            "avg": r3(h / ab) if ab else None, "obp": r3((h + bb + hbp) / obp_d) if obp_d else None,
            "slg": r3(tb / ab) if ab else None}


def by_round(p: pd.DataFrame, wpa_sign: float) -> list[dict]:
    out = []
    for g in ROUND_ORDER:
        q = p[p.game_type == g]
        if len(q):
            den = q[q.woba_denom == 1]
            out.append({"round": ROUND[g], "pa": int(len(q)), "woba": r3(den.woba_value.mean()) if len(den) else None,
                        "wpa": r3(wpa_sign * q.bat_wpa.sum())})
    return out


def rate(num: pd.Series) -> float | None:
    return r3(num.mean()) if len(num) else None


def hitter_profile(bid, a, pa, people) -> dict:
    p = pa[pa.batter == bid]
    d = a[(a.batter == bid) & a.thrown]
    den = p[p.woba_denom == 1]
    bip = d[d.type.eq("X") & d.launch_speed.notna()]
    sw = d[d.swing]
    o = d[~d.in_zone & d.zone.notna()]
    z = d[d.in_zone]
    groups = []
    for gname in ("Fastball", "Breaking", "Offspeed"):
        g = d[d.pitch_type.map(GROUP) == gname]
        gs = g[g.swing]
        if len(g):
            groups.append({"group": gname, "seen": int(len(g)), "whiff": rate(gs.whiff), "swings": int(len(gs))})
    best = p.loc[p.bat_wpa.idxmax()] if len(p) else None
    return {"name": people.get(str(int(bid)), {}).get("full", str(bid)), "short": ps.nm(people, bid),
            "team": p.bat_team.mode().iat[0], "pa": int(len(p)), "games": int(p.game_pk.nunique()),
            **slash(p), "woba": r3(den.woba_value.mean()), "xwoba": r3(den.x.mean()), "wpa": r3(p.bat_wpa.sum()),
            "rounds": by_round(p, 1.0), "best": moment(best, people, "pitcher") if best is not None else None,
            "pitches": int(len(d)), "chase": rate(o.swing), "zswing": rate(z.swing), "whiff": rate(sw.whiff),
            "groups": groups, "bip": int(len(bip)), "ev": r1(bip.launch_speed.mean()), "maxev": r1(bip.launch_speed.max()),
            "hard": rate(bip.launch_speed >= 95), "la": r1(bip.launch_angle.mean()),
            "barrels": int((bip.launch_speed_angle == 6).sum())}


def pitcher_profile(pid, a, pa, people) -> dict:
    p = pa[pa.pitcher == pid]
    d = a[(a.pitcher == pid) & a.thrown]
    den = p[p.woba_denom == 1]
    sw = d[d.swing]
    o = d[~d.in_zone & d.zone.notna()]
    arsenal = []
    for pt, g in d.groupby("pitch_name"):
        gs = g[g.swing]
        arsenal.append({"pitch": pt, "n": int(len(g)), "usage": r3(len(g) / len(d)), "velo": r1(g.release_speed.mean()),
                        "whiff": rate(gs.whiff), "swings": int(len(gs))})
    arsenal.sort(key=lambda r: -r["n"])
    best = p.loc[(-p.bat_wpa).idxmax()] if len(p) else None
    games = p.game_pk.nunique()
    starts = int((ps.starters().pitcher == int(pid)).sum())  # official box scores
    ev = p.events
    return {"name": people.get(str(int(pid)), {}).get("full", str(pid)), "short": ps.nm(people, pid),
            "team": p.fld_team.mode().iat[0], "bf": int(len(p)), "games": int(games), "starts": starts,
            "pitches": int(len(d)), "k": int(ev.isin(KS).sum()), "bb": int(ev.isin(WALKS).sum()),
            "hr": int((ev == "home_run").sum()), "woba": r3(den.woba_value.mean()), "xwoba": r3(den.x.mean()),
            "wpa": r3(-p.bat_wpa.sum()), "rounds": by_round(p, -1.0),
            "best": moment(best, people, "batter") if best is not None else None,
            "whiff": rate(sw.whiff), "chase": rate(o.swing), "arsenal": arsenal[:6],
            "late": rate(p.inning >= 7)}


def team_profiles(a, pa, people) -> dict:
    games = []
    for g, d in a.groupby("game_pk"):
        hs, as_ = int(d.post_home_score.max()), int(d.post_away_score.max())
        h, w = d.home_team.iat[0], d.away_team.iat[0]
        games.append({"game_pk": int(g), "type": d.game_type.iat[0], "date": str(d.game_date.iat[0])[:10],
                      "home": h, "away": w, "hs": hs, "as": as_})
    games = pd.DataFrame(games)
    st = ps.starters().merge(games, on="game_pk")
    den = pa[pa.woba_denom == 1]
    out = {}
    for t in sorted(set(games.home) | set(games.away)):
        g = games[(games.home == t) | (games.away == t)]
        rf = np.where(g.home == t, g.hs, g["as"]).sum()
        ra = np.where(g.home == t, g["as"], g.hs).sum()
        wins = int(((g.home == t) & (g.hs > g["as"]) | (g.away == t) & (g["as"] > g.hs)).sum())
        rounds = []
        for r in ROUND_ORDER:
            gg = g[g.type == r]
            if len(gg):
                w_ = int(((gg.home == t) & (gg.hs > gg["as"]) | (gg.away == t) & (gg["as"] > gg.hs)).sum())
                opp = sorted(set(gg.home) | set(gg.away) - {t})
                rounds.append({"round": ROUND[r], "opp": ", ".join(o for o in opp if o != t), "w": w_, "l": int(len(gg) - w_)})
        s = st[st.team == t].sort_values("date")
        starts = [{"date": pd.to_datetime(r.date).strftime("%b %-d"), "pitcher": ps.nm(people, r.pitcher),
                   "opp": r.away if r.home == t else r.home, "outs": int(r.outs), "pitches": int(r.pitches)}
                  for r in s.itertuples()]
        top_h = pa[pa.bat_team == t].groupby("batter").bat_wpa.sum().sort_values(ascending=False).head(2)
        top_p = (-pa[pa.fld_team == t].groupby("pitcher").bat_wpa.sum()).sort_values(ascending=False).head(2)
        out[t] = {"team": t, "games": int(len(g)), "w": wins, "l": int(len(g) - wins), "rf": int(rf), "ra": int(ra),
                  "x_for": r3(den[den.bat_team == t].x.mean()), "x_against": r3(den[den.fld_team == t].x.mean()),
                  "pa_for": int((den.bat_team == t).sum()), "pa_against": int((den.fld_team == t).sum()),
                  "hr_for": int(((pa.bat_team == t) & (pa.events == "home_run")).sum()),
                  "hr_against": int(((pa.fld_team == t) & (pa.events == "home_run")).sum()),
                  "rounds": rounds, "starts": starts,
                  "top_bats": [{"name": ps.nm(people, i), "wpa": r3(v)} for i, v in top_h.items()],
                  "top_arms": [{"name": ps.nm(people, i), "wpa": r3(v)} for i, v in top_p.items()]}
    return out


def world_series(a, people) -> list[dict]:
    ws = a[a.game_type == "W"]
    games = sorted(ws.game_pk.unique(), key=lambda g: ws.loc[ws.game_pk == g, "game_date"].iloc[0])
    out = []
    for i, g in enumerate(games):
        d = ws[ws.game_pk == g]
        home, away = d.home_team.iat[0], d.away_team.iat[0]
        hw = (d.home_win_exp + d.delta_home_win_exp.fillna(0)).to_numpy()
        mil = hw if home == "MIL" else 1 - hw
        sgn = 1 if home == "MIL" else -1
        pts = []
        for r, m in zip(d.itertuples(), mil):
            pts.append([round(float(m), 3), f"{'T' if r.inning_topbot == 'Top' else 'B'}{int(r.inning)}",
                        ps.nm(people, r.batter), ps.nm(people, r.pitcher), f"{int(r.balls)}-{int(r.strikes)}",
                        str(r.pitch_name) if pd.notna(r.pitch_name) else "", r1(r.release_speed),
                        ev_name(r.events) if pd.notna(r.events) else str(r.description).replace("_", " "),
                        f"{away} {int(r.post_away_score)}, {home} {int(r.post_home_score)}",
                        round(float(sgn * (0 if pd.isna(r.delta_home_win_exp) else r.delta_home_win_exp)), 3)])
        hs, as_ = int(d.post_home_score.max()), int(d.post_away_score.max())
        k = int(np.argmax([abs(p[-1]) for p in pts]))
        out.append({"game": i + 1, "date": pd.to_datetime(d.game_date.iat[0]).strftime("%b %-d"), "home": home, "away": away,
                    "hs": hs, "as": as_, "winner": home if hs > as_ else away, "innings": int(d.inning.max()),
                    "big": k, "pts": pts})
    return out


# ---------------------------------------------------------------- filter cubes
# Each chart on the page can be re-cut by the reader. Rather than precompute every combination, the page gets additive
# cells (sums and counts) per player or club x round x inning group x count, and its script re-aggregates, re-ranks and
# redraws. Means are sums over counts, so the "all" setting reproduces the published numbers exactly.
#   round:  index into ROUND_ORDER (Wild Card, Division Series, LCS, World Series), a range slider on every chart
#   inning: 0 = 1st-3rd, 1 = 4th-6th, 2 = 7th-9th, 3 = extras
#   count:  balls * 3 + strikes before the pitch (0-0 .. 3-2); for a plate appearance, the count on its last pitch
INNING_GROUPS = ["1–3", "4–6", "7–9", "Extras"]


def _dims(df: pd.DataFrame) -> pd.DataFrame:
    return df.assign(_r=df.game_type.map({g: i for i, g in enumerate(ROUND_ORDER)}).astype(int),
                     _i=np.select([df.inning <= 3, df.inning <= 6, df.inning <= 9], [0, 1, 2], 3),
                     _c=(df.balls.clip(upper=3) * 3 + df.strikes.clip(upper=2)).astype(int))


def _cube(df: pd.DataFrame, key: str, dims: list[str], aggs: dict) -> dict:
    """Group df by entity and the filter dimensions; aggs maps column -> (series, 'sum' | 'max')."""
    work = pd.DataFrame({k: v for k, (v, _) in aggs.items()}, index=df.index)
    work["_k"] = df[key].astype(str).str.replace(r"\.0$", "", regex=True)
    for d in dims:
        work[d] = df[d]
    g = work.groupby(["_k"] + dims)
    out = pd.concat([getattr(g[k], how)() for k, (_, how) in aggs.items()], axis=1).reset_index()
    keys = sorted(out._k.unique(), key=lambda k: (len(k), k))
    idx = {k: i for i, k in enumerate(keys)}
    rows = []
    for r in out.to_dict("records"):
        vals = []
        for k in aggs:
            v = r[k]
            vals.append(None if pd.isna(v) else (int(v) if float(v).is_integer() else round(float(v), 6)))
        rows.append([idx[r["_k"]]] + [int(r[d]) for d in dims] + vals)
    return {"keys": keys, "dims": [d.strip("_") for d in dims], "cols": list(aggs), "rows": rows}


def cubes(a: pd.DataFrame, pa: pd.DataFrame) -> dict:
    a, pa = _dims(a), _dims(pa)
    den = pa.woba_denom == 1
    one = lambda df: pd.Series(1, index=df.index)  # noqa: E731
    z = lambda m: m.astype(int)  # noqa: E731
    # hitters, plate-appearance level (charts 3 and 5; PA counts also decide who qualifies for chart 6)
    hpa = _cube(pa, "batter", ["_r", "_i"], {
        "pa": (one(pa), "sum"), "wpa": (pa.bat_wpa, "sum"), "dn": (z(den), "sum"),
        "woba": (pa.woba_value.where(den, 0.0), "sum"), "x": (pa.x.where(den, 0.0), "sum")})
    # pitchers, plate-appearance level (charts 4 and 7); count = the count on the PA's last pitch
    ppa = _cube(pa, "pitcher", ["_r", "_i", "_c"], {
        "bf": (one(pa), "sum"), "wpa": (-pa.bat_wpa, "sum"), "dn": (z(den), "sum"), "x": (pa.x.where(den, 0.0), "sum")})
    # clubs (chart 2): xwOBA for and against
    tf = _cube(pa[den], "bat_team", ["_r", "_i"], {"n": (one(pa[den]), "sum"), "x": (pa.x[den], "sum")})
    ta = _cube(pa[den], "fld_team", ["_r", "_i"], {"n": (one(pa[den]), "sum"), "x": (pa.x[den], "sum")})
    # hitters, pitch level (charts 6 and 9): every pitch, as the published chart reads it
    out = ~a.in_zone & a.zone.notna()
    bip = a.type.eq("X") & a.launch_speed.notna()
    hp = _cube(a, "batter", ["_r", "_i", "_c"], {
        "o": (z(out), "sum"), "osw": (z(out & a.swing), "sum"), "sw": (z(a.swing), "sum"), "wh": (z(a.swing & a.whiff), "sum"),
        "bip": (z(bip), "sum"), "ev": (a.launch_speed.where(bip, 0.0), "sum"), "evmax": (a.launch_speed.where(bip), "max")})
    # pitchers, pitch level (charts 7 and 8): thrown pitches; four-seamers and sinkers for velocity
    th = a[a.thrown]
    fb = th.pitch_type.isin(ps.FASTBALLS - {"FC"}) & th.release_speed.notna()
    pp = _cube(th, "pitcher", ["_r", "_i", "_c"], {
        "n": (one(th), "sum"), "sw": (z(th.swing), "sum"), "wh": (z(th.swing & th.whiff), "sum"),
        "fb": (z(fb), "sum"), "v": (th.release_speed.where(fb, 0.0), "sum"), "vmax": (th.release_speed.where(fb), "max")})
    # starters (chart 10): official box-score lines by round
    st = ps.starters().merge(a.drop_duplicates("game_pk")[["game_pk", "_r"]], on="game_pk")
    sc = _cube(st, "team", ["_r"], {"g": (one(st), "sum"), "outs": (st.outs, "sum"), "p": (st.pitches, "sum")})
    return {"hpa": hpa, "ppa": ppa, "tfor": tf, "tagainst": ta, "hp": hp, "pp": pp, "starters": sc}


def names(a: pd.DataFrame, pa: pd.DataFrame, people: dict) -> dict:
    """Short name and club for every batter and pitcher, so a player who qualifies only under a filter can be labelled."""
    h = pa.groupby("batter").bat_team.agg(lambda s: s.mode().iat[0])
    p = pa.groupby("pitcher").fld_team.agg(lambda s: s.mode().iat[0])
    hh = {str(int(i)): [ps.nm(people, i), t] for i, t in h.items()}
    for i, t in a.groupby("batter").bat_team.agg(lambda s: s.mode().iat[0]).items():
        hh.setdefault(str(int(i)), [ps.nm(people, i), t])
    pp_ = {str(int(i)): [ps.nm(people, i), t] for i, t in p.items()}
    for i, t in a.groupby("pitcher").fld_team.agg(lambda s: s.mode().iat[0]).items():
        pp_.setdefault(str(int(i)), [ps.nm(people, i), t])
    return {"h": hh, "p": pp_}


def aggregate(cube: dict, keep=lambda r: True) -> dict:
    """Sum a cube's cells per entity (the page's script does the same); used by the tests."""
    nd = len(cube["dims"])
    out: dict = {}
    for row in cube["rows"]:
        if not keep(dict(zip(cube["dims"], row[1:1 + nd]))):
            continue
        k = cube["keys"][row[0]]
        acc = out.setdefault(k, {c: None for c in cube["cols"]})
        for c, v in zip(cube["cols"], row[1 + nd:]):
            if v is None:
                continue
            if c.endswith("max"):
                acc[c] = v if acc[c] is None else max(acc[c], v)
            else:
                acc[c] = (acc[c] or 0) + v
    return out


def build() -> dict:
    a, people = ps.pull(False)
    a = ps.prep(a)
    pa = ps.plate_appearances(a)
    f = json.loads(FINDINGS.read_text())
    den = pa[pa.woba_denom == 1]
    th = a[a.thrown]

    def check(label, got, want, tol=0.0015):
        if abs(float(got) - float(want)) > tol:
            raise SystemExit(f"{label}: page {got} vs findings.json {want}; rebuild the snippets first")

    check("games", a.game_pk.nunique(), f["games"], 0)
    check("pitches", int(a.thrown.sum()), f["pitches"], 0)
    check("plate appearances", len(pa), f["plate_appearances"], 0)
    check("league xwOBA", den.x.mean(), f["team_contact"]["league_xwoba"])

    H, P = {}, {}

    def hp(i):
        k = str(int(i))
        if k not in H:
            H[k] = hitter_profile(i, a, pa, people)
        return k

    def pp(i):
        k = str(int(i))
        if k not in P:
            P[k] = pitcher_profile(i, a, pa, people)
        return k

    teams = team_profiles(a, pa, people)
    for t in f["team_contact"]["teams"]:
        check(f"{t['bat_team']} xwOBA for", teams[t["bat_team"]]["x_for"], t["x_for"])
        check(f"{t['bat_team']} xwOBA against", teams[t["bat_team"]]["x_against"], t["x_against"])

    # 3-4. WPA leaders (top 20, as charted)
    b = pa.groupby("batter").agg(pa=("bat_wpa", "size"), wpa=("bat_wpa", "sum")).reset_index().sort_values("wpa", ascending=False)
    hit_wpa = [{"id": hp(r.batter), "v": r3(r.wpa), "right": int(r.pa)} for r in b.head(20).itertuples()]
    for got, want in zip(hit_wpa, f["hitter_wpa"]["top5"]):
        check(f"hitter WPA {want['lab']}", got["v"], want["wpa"])
    p = pa.groupby("pitcher").agg(bf=("bat_wpa", "size"), wpa=("bat_wpa", lambda s: -s.sum())).reset_index().sort_values("wpa", ascending=False)
    pit_wpa = [{"id": pp(r.pitcher), "v": r3(r.wpa), "right": int(r.bf)} for r in p.head(20).itertuples()]
    for got, want in zip(pit_wpa, f["pitcher_wpa"]["top5"]):
        check(f"pitcher WPA {want['lab']}", got["v"], want["wpa"])

    # 5. results vs contact (min 25 PA)
    h = den.groupby("batter").agg(n=("x", "size"), woba=("woba_value", "mean"), xwoba=("x", "mean")).reset_index()
    h = h[h.n >= f["hitter_xwoba_woba"]["min_pa"]]
    check("hitters charted (xwOBA)", len(h), f["hitter_xwoba_woba"]["n"], 0)
    hit_x = [{"id": hp(r.batter), "x": r3(r.xwoba), "y": r3(r.woba)} for r in h.itertuples()]

    # 6. swing decisions (min 25 PA)
    pcount = pa.groupby("batter").size()
    keep = pcount[pcount >= 25].index
    d = a[a.batter.isin(keep)]
    o = d[~d.in_zone & d.zone.notna()]
    g = pd.DataFrame({"chase": o.groupby("batter").swing.mean(), "whiff": d[d.swing].groupby("batter").whiff.mean()}).dropna()
    check("hitters charted (swing decisions)", len(g), f["hitter_swing_decisions"]["n"], 0)
    lg_chase, lg_whiff = float(a[~a.in_zone & a.zone.notna()].swing.mean()), float(a[a.swing].whiff.mean())
    check("league chase", lg_chase, f["hitter_swing_decisions"]["league_chase"])
    swing = [{"id": hp(i), "x": r3(r.chase), "y": r3(r.whiff)} for i, r in g.iterrows()]

    # 7. pitchers: whiff vs damage (min 100 pitches)
    n = th.groupby("pitcher").size()
    keepp = n[n >= f["pitcher_whiff_xwoba"]["min_pitches"]].index
    dp = th[th.pitcher.isin(keepp)]
    denp = den[den.pitcher.isin(keepp)]
    gp = pd.DataFrame({"whiff": dp[dp.swing].groupby("pitcher").whiff.mean(), "xwoba": denp.groupby("pitcher").x.mean()}).dropna()
    check("pitchers charted", len(gp), f["pitcher_whiff_xwoba"]["n"], 0)
    pit_x = [{"id": pp(i), "x": r3(r.whiff), "y": r3(r.xwoba)} for i, r in gp.iterrows()]

    # 8. velocity leaders (min 15 four-seamers or sinkers)
    fb = a[a.pitch_type.isin(ps.FASTBALLS - {"FC"}) & a.release_speed.notna()]
    v = fb.groupby("pitcher").agg(n=("release_speed", "size"), velo=("release_speed", "mean"), top=("release_speed", "max")).reset_index()
    v = v[v.n >= 15].sort_values("velo", ascending=False).head(20)
    velo = [{"id": pp(r.pitcher), "v": r1(r.velo), "right": r1(r.top), "n": int(r.n)} for r in v.itertuples()]
    check("league fastball velocity", fb.release_speed.mean(), f["velo_leaders"]["league_fb_velo"], 0.006)
    check("velocity leader", velo[0]["v"], f["velo_leaders"]["top5"][0]["velo"], 0.051)

    # 9. exit velocity leaders (min 15 batted balls)
    bb = a[a.type.eq("X") & a.launch_speed.notna()]
    e = bb.groupby("batter").agg(n=("launch_speed", "size"), ev=("launch_speed", "mean"), top=("launch_speed", "max")).reset_index()
    e = e[e.n >= 15].sort_values("ev", ascending=False).head(20)
    evl = [{"id": hp(r.batter), "v": r1(r.ev), "right": r1(r.top), "n": int(r.n)} for r in e.itertuples()]
    check("league exit velocity", bb.launch_speed.mean(), f["ev_leaders"]["league_ev"], 0.006)
    check("exit velocity leader", evl[0]["v"], f["ev_leaders"]["top5"][0]["ev"], 0.051)

    # 10. starter depth (official box scores)
    sd = [{"team": t["team"], "v": round(t["outs"] / 3, 2), "pitches": t["pitches"], "games": t["games"]}
          for t in f["starter_depth"]["teams"]]

    ws = world_series(a, people)
    for got, want in zip(ws, f["world_series"]["games"]):
        if got["winner"] != want["winner"]:
            raise SystemExit(f"World Series game {want['game']} winner differs from findings.json")

    return {
        "meta": {k: f[k] for k in ("games", "pitches", "plate_appearances", "first_date", "last_date")} | {"built": f["built"]},
        "findings": f,  # the page header (at a glance) quotes findings.json directly
        "colors": ps.TEAM,
        "league": {"xwoba": r3(den.x.mean()), "chase": r3(lg_chase), "whiff": r3(lg_whiff),
                   "fb_velo": r1(fb.release_speed.mean()), "ev": r1(bb.launch_speed.mean())},
        "hitters": H, "pitchers": P, "teams": teams, "cubes": cubes(a, pa), "names": names(a, pa, people),
        "filters": {"rounds": [ROUND[g] for g in ROUND_ORDER], "innings": INNING_GROUPS},
        "charts": {"ws": ws, "team_contact": [{"team": t, "x": v_["x_for"], "y": v_["x_against"]} for t, v_ in teams.items()],
                   "hitter_wpa": hit_wpa, "pitcher_wpa": pit_wpa, "hitter_x": hit_x, "swing": swing, "pitcher_x": pit_x,
                   "velo": velo, "ev": evl, "starters": sd},
    }


def write(data: dict, out: Path = PAGE) -> Path:
    html = TEMPLATE.read_text()
    blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    out.write_text(html.replace("/*DATA*/null", blob))
    return out


if __name__ == "__main__":
    d = build()
    print(write(d), f"{len(d['hitters'])} hitters, {len(d['pitchers'])} pitchers, {len(d['teams'])} clubs")
