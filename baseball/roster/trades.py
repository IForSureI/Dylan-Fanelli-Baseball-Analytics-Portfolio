"""The MLB trade graph, 2009 to today: every trade, every player moved, the WAR each club got, and the trade trees.

Grain:
- trade: one MLB trade (MLB Stats API transaction id, typeCode TR). The feed starts in 2009.
- leg: one player moved from one MLB club to another in one trade.
- side: one club's half of one trade (what it got and gave).
- link: a club acquired a player in trade A and sent him away in trade B (the edge of a trade tree).

Value: the WAR a player gave the club that acquired him (Baseball-Reference WAR, batting plus pitching,
by stint), from the trade through his continuous tenure with that club.
- Trades made October-December count from the next season.
- The first season adds the acquiring club's stint if there is one.
- After that, a season with the club adds its stint; a season only with other MLB clubs ends the tenure;
  a season with no MLB time (minors, injury) is skipped without ending it.
This is realized value: it ignores salary and the control a recent trade still has left (see still_accruing).

Sources: MLB Stats API /transactions; Baseball-Reference war_daily_bat.txt and war_daily_pitch.txt.
`patches.json` (next to this file) repairs trades the feed records incompletely, one documented entry each.
"""
from __future__ import annotations

import collections
import datetime as dt
import itertools
import json
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path("data/raw/trades")
OUT = Path("data/graph")
FIRST_SEASON = 2009
PATCHES = Path(__file__).with_name("trade_patches.json")
CYPHER = Path(__file__).with_name("trade_graph.cypher")

# MLB Stats API team id -> (abbreviation, Baseball-Reference team codes across its names)
TEAMS = {108: ("LAA", ["LAA"]), 109: ("ARI", ["ARI"]), 110: ("BAL", ["BAL"]), 111: ("BOS", ["BOS"]),
         112: ("CHC", ["CHC"]), 113: ("CIN", ["CIN"]), 114: ("CLE", ["CLE"]), 115: ("COL", ["COL"]),
         116: ("DET", ["DET"]), 117: ("HOU", ["HOU"]), 118: ("KCR", ["KCR"]), 119: ("LAD", ["LAD"]),
         120: ("WSN", ["WSN"]), 121: ("NYM", ["NYM"]), 133: ("ATH", ["OAK", "ATH"]), 134: ("PIT", ["PIT"]),
         135: ("SDP", ["SDP"]), 136: ("SEA", ["SEA"]), 137: ("SFG", ["SFG"]), 138: ("STL", ["STL"]),
         139: ("TBR", ["TBR"]), 140: ("TEX", ["TEX"]), 141: ("TOR", ["TOR"]), 142: ("MIN", ["MIN"]),
         143: ("PHI", ["PHI"]), 144: ("ATL", ["ATL"]), 145: ("CHW", ["CHW"]), 146: ("MIA", ["FLA", "MIA"]),
         147: ("NYY", ["NYY"]), 158: ("MIL", ["MIL"])}
DIVISIONS = {"AL East": "BAL BOS NYY TBR TOR", "AL Central": "CHW CLE DET KCR MIN", "AL West": "HOU LAA ATH SEA TEX",
             "NL East": "ATL MIA NYM PHI WSN", "NL Central": "CHC CIN MIL PIT STL", "NL West": "ARI COL LAD SDP SFG"}


# ---------------------------------------------------------------- pull
def _get(url: str) -> bytes:
    for i in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except Exception:
            if i == 3:
                raise
            time.sleep(3)


def pull(raw: Path = RAW, through: dt.date | None = None, refresh: bool = False) -> None:
    """MLB trades by season (the current season is always re-pulled) and Baseball-Reference WAR."""
    through = through or dt.date.today()
    raw.mkdir(parents=True, exist_ok=True)
    for y in range(FIRST_SEASON, through.year + 1):
        f = raw / f"tr_{y}.json"
        if f.exists() and y < through.year and not refresh:
            continue
        end = f"{y}-12-31" if y < through.year else through.isoformat()
        d = json.loads(_get(f"https://statsapi.mlb.com/api/v1/transactions?startDate={y}-01-01&endDate={end}&sportId=1"))
        f.write_text(json.dumps([t for t in d.get("transactions", []) if t.get("typeCode") == "TR"]))
    for name in ("war_daily_bat.txt", "war_daily_pitch.txt"):
        (raw / name).write_bytes(_get(f"https://www.baseball-reference.com/data/{name}"))
    if not (raw / "tran.txt").exists():                   # Retrosheet's file is no longer updated: fetch once
        import io
        import zipfile

        with zipfile.ZipFile(io.BytesIO(_get("https://www.retrosheet.org/transactions/tranDB.zip"))) as z:
            (raw / "tran.txt").write_bytes(z.read("tran.txt"))


# ---------------------------------------------------------------- WAR
def war_tables(bat: pd.DataFrame, pitch: pd.DataFrame, first_season: int = FIRST_SEASON):
    """(player -> season -> {club: WAR}, player -> season -> club of his last stint)."""
    w = pd.concat([bat, pitch])
    w = w[w.year_ID >= first_season].fillna({"WAR": 0})
    code2id = {c: i for i, (_, cs) in TEAMS.items() for c in cs}
    w = w.assign(club=w.team_ID.map(code2id)).dropna(subset=["club"])
    by_club = collections.defaultdict(dict)
    for (pid, y, club), v in w.groupby(["mlb_ID", "year_ID", "club"]).WAR.sum().items():
        by_club[int(pid)].setdefault(int(y), {})[int(club)] = float(v)
    last = collections.defaultdict(dict)
    for (pid, y), club in w.sort_values(["mlb_ID", "year_ID", "stint_ID"]).groupby(["mlb_ID", "year_ID"]).club.last().items():
        last[int(pid)][int(y)] = int(club)
    return by_club, last


def tenure_value(seasons: dict[int, dict[int, float]], club: int, date: str, last_season: int) -> tuple[float, list[int]]:
    """WAR a club got from a player it acquired on `date`, and the seasons it came in (rules in the module doc)."""
    y0 = int(date[:4]) + (1 if int(date[5:7]) >= 10 else 0)
    total, years = 0.0, []
    for y in range(y0, last_season + 1):
        s = seasons.get(y)
        if s is None:
            continue
        if club in s:
            total += s[club]
            years.append(y)
        elif y > y0:
            break
    return round(total, 2), years


def club_before(last_stint: dict[int, int], date: str) -> int | None:
    """The MLB club a player last appeared for before a trade (repairs a blank sending club)."""
    y, m = int(date[:4]), int(date[5:7])
    years = [yy for yy in last_stint if yy <= (y if m >= 5 else y - 1)]
    return last_stint[max(years)] if years else None


# ---------------------------------------------------------------- trades
def parse_trades(raw_legs: list[dict], last_stint: dict, patches: dict | None = None):
    """Feed rows -> (trades, legs). Keeps MLB-to-MLB player moves; repairs blank sending clubs;
    applies patches; drops a move MLB filed twice under two ids (keeps the fuller record)."""
    trades, legs, seen = {}, [], set()
    for t in raw_legs:
        tid = t["id"]
        tr = trades.setdefault(tid, {"trade_id": tid, "date": t["date"], "description": t.get("description", ""),
                                     "teams": set(), "non_player_legs": 0, "non_mlb_party": False,
                                     "record_repaired": False, "record_incomplete": False})
        ft, tt = t.get("fromTeam"), t.get("toTeam")
        if not ft or not tt:
            tr["record_incomplete"] = True
        if "person" in t and tt and not ft:
            guess = club_before(last_stint.get(t["person"]["id"], {}), t["date"])
            if guess and guess != tt["id"]:
                ft = {"id": guess}
                tr["record_repaired"] = True
        for x in (ft, tt):
            if x and x["id"] in TEAMS:
                tr["teams"].add(x["id"])
            elif x:
                tr["non_mlb_party"] = True
        if "person" not in t:
            tr["non_player_legs"] += 1
            continue
        if not ft or not tt or ft["id"] not in TEAMS or tt["id"] not in TEAMS:
            continue
        key = (tid, t["person"]["id"], ft["id"], tt["id"])
        if key in seen:
            continue
        seen.add(key)
        legs.append({"trade_id": tid, "date": t["date"], "player_id": t["person"]["id"],
                     "player_name": t["person"].get("fullName", f"MLBAM {t['person']['id']}"),
                     "from_id": ft["id"], "to_id": tt["id"]})
    for tid, fix in (patches or {}).items():
        if tid.startswith("_") or int(tid) not in trades:
            continue
        tr = trades[int(tid)]
        for x in fix["legs"]:
            legs.append({"trade_id": int(tid), "date": tr["date"], **x})
            tr["teams"].update([x["from_id"], x["to_id"]])
        tr["record_repaired"], tr["description"] = True, fix["trade"]
    trades = {k: v for k, v in trades.items() if len(v["teams"]) >= 2}
    legs = [l for l in legs if l["trade_id"] in trades]
    n_legs = collections.Counter(l["trade_id"] for l in legs)
    best = {}
    for l in legs:
        k = (l["player_id"], l["date"], l["from_id"], l["to_id"])
        if k not in best or (n_legs[l["trade_id"]], -l["trade_id"]) > (n_legs[best[k]["trade_id"]], -best[k]["trade_id"]):
            best[k] = l
    legs = [l for l in legs if best[(l["player_id"], l["date"], l["from_id"], l["to_id"])] is l]
    alive = {l["trade_id"] for l in legs}
    return {k: v for k, v in trades.items() if k in alive}, legs


def tree_links(legs: list[dict]) -> list[dict]:
    """A club acquired a player in trade A; his next trade, B, sends him away from that club."""
    by_player = collections.defaultdict(list)
    for l in legs:
        by_player[l["player_id"]].append(l)
    links = []
    for pid, ls in by_player.items():
        ls.sort(key=lambda l: (l["date"], l["trade_id"]))
        for i, a in enumerate(ls):
            for b in ls[i + 1:]:
                if b["trade_id"] == a["trade_id"]:
                    continue
                if b["from_id"] == a["to_id"]:
                    links.append({"from_trade": a["trade_id"], "to_trade": b["trade_id"], "team_id": a["to_id"],
                                  "player_id": pid, "player_name": a["player_name"],
                                  "days_held": (pd.Timestamp(b["date"]) - pd.Timestamp(a["date"])).days})
                break
    return links


def sides_table(legs: list[dict], links: list[dict]) -> list[dict]:
    """Each club's half of each trade, with the tree value: what it received directly plus, for every
    acquired player it later flipped, its share of what the flip returned (share = 1 / players it sent in the flip)."""
    sides = collections.defaultdict(lambda: {"received": 0.0, "sent": 0.0, "n_in": 0, "n_out": 0})
    sent_in = collections.defaultdict(list)
    for l in legs:
        sides[(l["trade_id"], l["to_id"])]["received"] += l["war_for_acquirer"]
        sides[(l["trade_id"], l["to_id"])]["n_in"] += 1
        sides[(l["trade_id"], l["from_id"])]["sent"] += l["war_for_acquirer"]
        sides[(l["trade_id"], l["from_id"])]["n_out"] += 1
        sent_in[(l["trade_id"], l["from_id"])].append(l)
    children = collections.defaultdict(list)
    for k in links:
        children[(k["from_trade"], k["team_id"])].append(k)

    def tree(tid, team, stack=()):
        total = sides[(tid, team)]["received"]
        if (tid, team) in stack or len(stack) > 25:
            return total
        for k in children[(tid, team)]:
            total += tree(k["to_trade"], team, stack + ((tid, team),)) / max(1, len(sent_in[(k["to_trade"], team)]))
        return total

    return [{"trade_id": tid, "team_id": team, "war_received": round(s["received"], 2), "war_sent": round(s["sent"], 2),
             "net_war": round(s["received"] - s["sent"], 2), "players_in": s["n_in"], "players_out": s["n_out"],
             "tree_war_received": round(tree(tid, team), 2), "flips": len(children[(tid, team)])}
            for (tid, team), s in list(sides.items())]


def build(raw: Path = RAW, out: Path = OUT, last_season: int | None = None) -> dict[str, int]:
    """Raw pulls -> the graph CSVs in data/graph/ (also Neo4j's import folder)."""
    cols = ["mlb_ID", "year_ID", "team_ID", "stint_ID", "WAR"]
    bat = pd.read_csv(raw / "war_daily_bat.txt", usecols=cols, na_values="NULL")
    pitch = pd.read_csv(raw / "war_daily_pitch.txt", usecols=cols, na_values="NULL")
    last_season = last_season or int(max(bat.year_ID.max(), pitch.year_ID.max()))
    by_club, last = war_tables(bat, pitch)
    feed = [t for f in sorted(raw.glob("tr_*.json")) for t in json.loads(f.read_text())]
    trades, legs = parse_trades(feed, last, json.loads(PATCHES.read_text()) if PATCHES.exists() else None)
    for l in legs:
        l["war_for_acquirer"], years = tenure_value(by_club.get(l["player_id"], {}), l["to_id"], l["date"], last_season)
        l["seasons_with_acquirer"] = len(years)
        l["reached_mlb_with_acquirer"] = bool(years)
        l["still_accruing"] = bool(years) and years[-1] == last_season
        y, m = int(l["date"][:4]), int(l["date"][5:7])
        l["mlb_before"] = any(yy < y or (yy == y and m >= 7) for yy in last.get(l["player_id"], {}))
    links = tree_links(legs)
    sides = sides_table(legs, links)
    names = {}
    for l in legs:
        names[l["player_id"]] = l["player_name"]
    n_player_legs = collections.Counter(l["trade_id"] for l in legs)
    has_mlb = {l["trade_id"] for l in legs if l["mlb_before"]}
    out.mkdir(parents=True, exist_ok=True)
    tables = {
        "teams": [{"team_id": i, "abbr": a} for i, (a, _) in TEAMS.items()],
        "players": [{"player_id": k, "name": v} for k, v in names.items()],
        "trades": [{"trade_id": t["trade_id"], "date": t["date"], "season": int(t["date"][:4]),
                    "description": t["description"].replace("\n", " "), "n_teams": len(t["teams"]),
                    "n_player_legs": n_player_legs[t["trade_id"]], "cash_or_ptbnl_legs": t["non_player_legs"],
                    "non_mlb_party": t["non_mlb_party"], "record_repaired": t["record_repaired"],
                    "record_incomplete": t["record_incomplete"], "has_mlb_player": t["trade_id"] in has_mlb}
                   for t in trades.values()],
        "legs": legs, "sides": sides, "links": links,
    }
    for name, rows in tables.items():
        pd.DataFrame(rows).to_csv(out / f"{name}.csv", index=False)
    return {k: len(v) for k, v in tables.items()}


# ---------------------------------------------------------------- who trades with whom
def expected_pairs(counts: pd.Series) -> pd.DataFrame:
    """Expected trades between every pair of clubs if each club's trades were spread over the other 29
    in proportion to their activity (configuration model without self-pairs: every row sums to the club's trades)."""
    teams = sorted(counts.index)
    k = counts.reindex(teams).to_numpy(float)
    x = k / np.sqrt(k.sum())
    for _ in range(5000):
        x = 0.5 * x + 0.5 * k / (x.sum() - x)
    e = np.outer(x, x)
    np.fill_diagonal(e, 0)
    return pd.DataFrame(e, index=teams, columns=teams)


def pair_excess(graph: Path = OUT) -> tuple[pd.DataFrame, dict]:
    """Observed vs expected two-club trades for all 435 pairs (Poisson tails, Benjamini-Hochberg q),
    and division rivals pooled against everyone else."""
    from scipy.stats import poisson

    from baseball.stats import benjamini_hochberg

    sides = pd.read_csv(graph / "sides.csv")
    trades = pd.read_csv(graph / "trades.csv")
    abbr = {i: a for i, (a, _) in TEAMS.items()}
    s2 = sides[sides.trade_id.isin(trades.loc[trades.n_teams == 2, "trade_id"])]
    pairs = s2.groupby("trade_id").team_id.apply(lambda x: tuple(sorted(x)))
    obs = pairs.value_counts()
    e = expected_pairs(s2.team_id.value_counts())
    div = {t: d for d, ts in DIVISIONS.items() for t in ts.split()}
    rows = []
    for a, b in itertools.combinations(e.index, 2):
        o, ex = int(obs.get((a, b), 0)), float(e.loc[a, b])
        rows.append({"pair": f"{abbr[a]}-{abbr[b]}", "observed": o, "expected": ex, "ratio": o / ex,
                     "same_division": div[abbr[a]] == div[abbr[b]],
                     "p_more": float(poisson.sf(o - 1, ex)), "p_fewer": float(poisson.cdf(o, ex))})
    r = pd.DataFrame(rows)
    r["q_more"] = benjamini_hochberg(r.p_more.to_numpy())
    r["q_fewer"] = benjamini_hochberg(r.p_fewer.to_numpy())
    o, ex = r.loc[r.same_division, "observed"].sum(), r.loc[r.same_division, "expected"].sum()
    lo, hi = (v / ex for v in garwood(int(o)))
    rivals = {"observed": int(o), "expected": round(float(ex), 1), "rate_ratio": round(float(o / ex), 3),
              "ci95": (round(float(lo), 2), round(float(hi), 2)), "p_fewer": float(poisson.cdf(o, ex)),
              "pairs_below": int((r.same_division & (r.observed < r.expected)).sum()), "pairs": int(r.same_division.sum())}
    return r, rivals


# ---------------------------------------------------------------- the report: rivals and front-office ties
def _pairs_in(sides: pd.DataFrame, trade_ids) -> pd.DataFrame:
    """Observed and expected counts for every pair, from one subset of two-club trades (expected refit on the subset)."""
    abbr = {i: a for i, (a, _) in TEAMS.items()}
    div = {t: d for d, ts in DIVISIONS.items() for t in ts.split()}
    s2 = sides[sides.trade_id.isin(trade_ids)]
    obs = s2.groupby("trade_id").team_id.apply(lambda x: tuple(sorted(x))).value_counts()
    e = expected_pairs(s2.team_id.value_counts())
    rows = []
    for a, b in itertools.combinations(e.index, 2):
        A, B = abbr[a], abbr[b]
        kind = "same division" if div[A] == div[B] else ("same league" if div[A][:2] == div[B][:2] else "interleague")
        rows.append({"pair": f"{A}-{B}", "kind": kind, "division": div[A] if kind == "same division" else "",
                     "observed": int(obs.get((a, b), 0)), "expected": float(e.loc[a, b])})
    return pd.DataFrame(rows)


def garwood(o: int, level: float = 0.95) -> tuple[float, float]:
    """Exact (Garwood) confidence interval for a Poisson count."""
    from scipy.stats import chi2

    a = 1 - level
    return (0.0 if o == 0 else float(chi2.ppf(a / 2, 2 * o) / 2), float(chi2.ppf(1 - a / 2, 2 * o + 2) / 2))


def _rate(d: pd.DataFrame) -> dict:
    from scipy.stats import poisson

    o, e = int(d.observed.sum()), float(d.expected.sum())
    lo, hi = garwood(o)
    return {"observed": o, "expected": round(e, 1), "rate_ratio": round(o / e, 3), "ci_low": round(lo / e, 2),
            "ci_high": round(hi / e, 2), "p_fewer": float(poisson.cdf(o, e)), "p_more": float(poisson.sf(o - 1, e)),
            "pairs": len(d), "pairs_below": int((d.observed < d.expected).sum())}


def breakdown(graph: Path = OUT) -> dict[str, pd.DataFrame]:
    """The report's tables: rate ratios by pair type, by division, by trade window and by era
    (expected counts refit within each subset)."""
    sides = pd.read_csv(graph / "sides.csv")
    trades = pd.read_csv(graph / "trades.csv", parse_dates=["date"])
    two = trades[trades.n_teams == 2]
    allp = _pairs_in(sides, two.trade_id)
    out = {"by_type": pd.DataFrame([{"pairs_of": k, **_rate(allp[allp.kind == k])}
                                    for k in ("same division", "same league", "interleague")])}
    rivals = allp[allp.kind == "same division"]
    out["by_division"] = pd.DataFrame([{"division": k, **_rate(g)} for k, g in rivals.groupby("division")])
    month = two.date.dt.month
    windows = {"deadline (Jul-Aug)": month.isin([7, 8]), "offseason (Oct-Mar)": month.isin([10, 11, 12, 1, 2, 3]),
               "rest of season (Apr-Jun, Sep)": month.isin([4, 5, 6, 9])}
    eras = {"2009-2017": two.date.dt.year <= 2017, "2018-2026": two.date.dt.year >= 2018}
    for name, cuts in (("by_window", windows), ("by_era", eras)):
        rows = []
        for label, m in cuts.items():
            p = _pairs_in(sides, two[m].trade_id)
            for k in ("same division", "same league"):
                rows.append({name[3:]: label, "trades": int(m.sum()), "pairs_of": k, **_rate(p[p.kind == k])})
        out[name] = pd.DataFrame(rows)
    rows = []
    for label, m in {"with a player who had MLB time": two.has_mlb_player, "minor leaguers only": ~two.has_mlb_player,
                     "2009-2011 only": two.date.dt.year <= 2011}.items():
        p = _pairs_in(sides, two[m].trade_id)
        rows.append({"subset": label, "trades": int(m.sum()), **_rate(p[p.kind == "same division"])})
    out["by_subset"] = pd.DataFrame(rows)
    from scipy.stats import mannwhitneyu

    gap = sides[sides.trade_id.isin(two.trade_id)].groupby("trade_id").net_war.max()
    rival_ids = set()
    s2 = sides[sides.trade_id.isin(two.trade_id)]
    div = {i: d for d, ts in DIVISIONS.items() for t in ts.split() for i, (a, _) in TEAMS.items() if a == t}
    for tid, g in s2.groupby("trade_id").team_id:
        a, b = list(g)
        if div[a] == div[b]:
            rival_ids.add(tid)
    is_rival = gap.index.isin(rival_ids)
    out["lopsided"] = pd.DataFrame([{"trades": k, "n": int(m.sum()), "median_abs_net_war": round(float(gap[m].median()), 3),
                                     "share_1_war_plus": round(float((gap[m] >= 1).mean()), 3)}
                                    for k, m in (("division rivals", is_rival), ("all other pairs", ~is_rival))])
    out["lopsided_p"] = float(mannwhitneyu(gap[is_rival], gap[~is_rival]).pvalue)
    out["pairs"] = allp
    return out


def side_gap_baseline(graph: Path = OUT, start: str = "2020-11-12", end: str = "2026-06-26", n: int = 13,
                      observed_gap: float = 11.14, draws: int = 20000, seed: int = 7) -> float:
    """How often n random two-club trades from the window give one side a realized-WAR gap at least this large
    (each trade's side chosen at random). The reference point for any one pair's ledger."""
    sides = pd.read_csv(graph / "sides.csv")
    trades = pd.read_csv(graph / "trades.csv", parse_dates=["date"])
    ids = trades[(trades.n_teams == 2) & (trades.date >= start) & (trades.date < end)].trade_id
    net = sides[sides.trade_id.isin(ids)].groupby("trade_id").net_war.max().to_numpy()
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(net), size=(draws, n))
    sign = rng.choice([-1.0, 1.0], size=(draws, n))
    return float((np.abs((net[pick] * sign).sum(axis=1)) >= observed_gap).mean())


def pair_by_period(a: str, b: str, cuts: list[str], graph: Path = OUT) -> pd.DataFrame:
    """One pair across periods split at `cuts` (dates): club a's two-club trades, those with b, a's share,
    and the pair's expected count refit within each period."""
    from scipy.stats import poisson

    sides = pd.read_csv(graph / "sides.csv")
    trades = pd.read_csv(graph / "trades.csv", parse_dates=["date"])
    two = trades[trades.n_teams == 2]
    ida, idb = ({v[0]: k for k, v in TEAMS.items()}[x] for x in (a, b))
    edges = [pd.Timestamp.min] + [pd.Timestamp(c) for c in cuts] + [pd.Timestamp.max]
    rows = []
    for lo, hi in zip(edges, edges[1:]):
        m = (two.date >= lo) & (two.date < hi)
        s = sides[sides.trade_id.isin(two[m].trade_id)]
        ta, tb = set(s[s.team_id == ida].trade_id), set(s[s.team_id == idb].trade_id)
        p = _pairs_in(sides, two[m].trade_id).set_index("pair")
        e = float(p.loc[f"{a}-{b}" if f"{a}-{b}" in p.index else f"{b}-{a}", "expected"])
        n = len(ta & tb)
        rows.append({"from": None if lo == pd.Timestamp.min else lo.date(), "to": None if hi == pd.Timestamp.max else hi.date(),
                     f"{a}_trades": len(ta), "with_" + b: n, "share": round(n / max(1, len(ta)), 3),
                     "expected": round(e, 2), "ratio": round(n / e, 2), "p_more": float(poisson.sf(n - 1, e))})
    return pd.DataFrame(rows)


def report_figure(graph: Path = OUT, out: Path = Path("reports/figures/2026-trade-network-rivals.png")) -> Path:
    """Left: observed / expected trades by pair type and division. Right: Angels trades per season, with the Braves,
    across Perry Minasian's tenure (Nov. 12, 2020 - June 26, 2026)."""
    import matplotlib.pyplot as plt

    from baseball.viz import GRID, INK, MUTED, OTHER, _style

    accent = "#2a78d6"
    b = breakdown(graph)
    rows = []
    order = b["by_division"].sort_values("rate_ratio", ascending=False)
    rows += [(f"{r.division} rivals", r, "div") for r in order.itertuples()]
    rows += [("Division rivals, all", b["by_type"].iloc[0], "rival")]

    per = pair_by_period("LAA", "ATL", ["2020-11-12", "2026-06-26"], graph)
    labels = ["Before\nApr. 2009 –\nNov. 11, 2020", "Minasian\nNov. 12, 2020 –\nJune 25, 2026", "Interim GM\nJune 26 –\nOct. 13, 2026"]

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.4), dpi=160, gridspec_kw={"width_ratios": [1.15, 1]})
    for ax in (a1, a2):
        _style(ax)
    for i, (label, r, g) in enumerate(rows):
        c = OTHER if g == "other" else accent
        a1.plot([r.ci_low, r.ci_high], [i, i], color=c, lw=2, solid_capstyle="round")
        a1.scatter([r.rate_ratio], [i], s=80 if g == "rival" else 46, color=c, edgecolors="#fcfcfb", linewidths=2, zorder=3)
        a1.text(1.36, i, f"{r.rate_ratio:.2f}", va="center", ha="right", fontsize=8.5, color=INK, fontweight="bold" if g == "rival" else "normal")
        a1.text(1.40, i, f"{int(r.observed):,} vs {r.expected:,.0f}", va="center", fontsize=8.5, color=MUTED)
    a1.axvline(1, color=MUTED, lw=1, ls=(0, (3, 3)))
    a1.set_yticks(range(len(rows)), [r[0] for r in rows], fontsize=9, color=INK)
    for t, (_, _, g) in zip(a1.get_yticklabels(), rows):
        t.set_fontweight("bold" if g == "rival" else "normal")
    a1.set_xlim(0.2, 1.72)
    a1.set_xticks([0.2, 0.4, 0.6, 0.8, 1.0, 1.2])
    a1.set_ylim(-0.6, len(rows) - 0.1)
    a1.text(1.36, len(rows) - 0.45, "ratio", ha="right", fontsize=8, color=MUTED)
    a1.text(1.40, len(rows) - 0.45, "observed vs expected", fontsize=8, color=MUTED)
    a1.set_xlabel("Trades observed ÷ expected from each club's trade volume (exact 95% interval)", color=MUTED, fontsize=9)
    n_two = int(b["by_type"].observed.sum())
    a1.set_title("Division rivals trade far less with each other", loc="left", color=INK, fontsize=12, fontweight="bold", pad=22)
    a1.text(0, 1.02, f"Two-club MLB trades, Apr. 2009 – Oct. 2026 (n = {n_two:,}). 1.0 = as often as the clubs' volume predicts.", transform=a1.transAxes, color=MUTED, fontsize=8.5)

    xs = np.arange(len(per))
    share = 100 * per.share.to_numpy()
    exp_share = 100 * per.expected.to_numpy() / per["LAA_trades"].to_numpy()
    colors = [GRID, accent, GRID]
    a2.bar(xs, share, width=0.6, color=colors, zorder=2)
    a2.scatter(xs, exp_share, marker="_", s=900, color=INK, linewidths=2, zorder=3)
    for x, e, c in zip(xs, exp_share, colors):
        a2.text(x, e + 0.6, f"expected {e:.1f}%", ha="center", va="bottom", fontsize=8, color="white" if c == accent else INK)
    for x, r, sh in zip(xs, per.itertuples(), share):
        a2.text(x, sh + 0.8, f"{sh:.1f}%\n{r.with_ATL} of {r.LAA_trades}", ha="center", va="bottom", fontsize=8.5, color=INK)
    a2.set_xticks(xs, labels, fontsize=8.5, color=INK)
    a2.set_ylim(0, 30)
    a2.set_ylabel("% of Angels two-club trades", color=MUTED, fontsize=9)
    a2.grid(axis="x", visible=False)
    a2.set_title("The Angels traded with Atlanta 3× as often under Minasian", loc="left", color=INK, fontsize=12, fontweight="bold", pad=22)
    a2.text(0, 1.02, "Share of Angels two-club trades made with the Braves; dash = expected from both clubs' volume.",
            transform=a2.transAxes, color=MUTED, fontsize=8.5)
    fig.text(0.01, 0.005, "Sources: MLB Stats API transactions; expected counts from a configuration model of each club's trade volume. "
             "Code: baseball/roster/trades.py.", fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.025, 1, 1))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out


def compare_rate_ratios(o1: int, rr1: float, o2: int, rr2: float, dispersion: float = 1.0) -> tuple[float, float]:
    """Two independent observed/expected ratios: (ratio of the two, two-sided p) from the log-rate test,
    with Poisson variance on the observed counts scaled by `dispersion` (expected counts treated as fixed)."""
    from scipy.stats import norm

    d = np.log(rr1 / rr2)
    return float(np.exp(d)), float(2 * norm.sf(abs(d) / np.sqrt(max(dispersion, 1.0) * (1 / o1 + 1 / o2))))


def poisson_glm(y: np.ndarray, X: np.ndarray, iters: int = 100) -> tuple[np.ndarray, np.ndarray, float]:
    """Poisson regression by iteratively reweighted least squares: (coefficients, standard errors, Pearson dispersion)."""
    b = np.zeros(X.shape[1])
    b[:] = np.log(max(y.mean(), 1e-9)) / max(1, X.sum(axis=1).mean())
    for _ in range(iters):
        mu = np.exp(X @ b)
        z = X @ b + (y - mu) / mu
        XtW = X.T * mu
        new = np.linalg.solve(XtW @ X, XtW @ z)
        if np.max(np.abs(new - b)) < 1e-10:
            b = new
            break
        b = new
    mu = np.exp(X @ b)
    se = np.sqrt(np.diag(np.linalg.inv((X.T * mu) @ X)))
    phi = float(((y - mu) ** 2 / mu).sum() / (len(y) - X.shape[1]))
    return b, se, phi


def rivalry_model(graph: Path = OUT) -> dict:
    """Two-club trades per pair ~ Poisson(exp(club_i + club_j + same_division + same_league)), interleague as the base.
    Rate ratios with quasi-Poisson intervals (standard errors scaled by the Pearson dispersion)."""
    from scipy.stats import norm

    sides = pd.read_csv(graph / "sides.csv")
    trades = pd.read_csv(graph / "trades.csv")
    p = _pairs_in(sides, trades.loc[trades.n_teams == 2, "trade_id"])
    clubs = sorted({c for pr in p.pair for c in pr.split("-")})
    X = np.zeros((len(p), len(clubs) + 2))
    for r, pr in enumerate(p.pair):
        for c in pr.split("-"):
            X[r, clubs.index(c)] = 1
    X[:, -2] = (p.kind == "same division").to_numpy()
    X[:, -1] = (p.kind == "same league").to_numpy()
    y = p.observed.to_numpy(float)
    b, se, phi = poisson_glm(y, X)
    out = {"dispersion": round(phi, 3), "pairs": len(p)}
    for name, i in (("same_division", -2), ("same_league", -1)):
        s = se[i] * np.sqrt(max(phi, 1.0))
        out[name] = {"rate_ratio": round(float(np.exp(b[i])), 3), "ci_low": round(float(np.exp(b[i] - 1.96 * s)), 2),
                     "ci_high": round(float(np.exp(b[i] + 1.96 * s)), 2), "p": float(2 * norm.sf(abs(b[i]) / s))}
    mu = np.exp(X @ b)
    non = (p.kind != "same division").to_numpy()
    out["dispersion_non_rival"] = round(float(((y[non] - mu[non]) ** 2 / mu[non]).sum() / (non.sum() - len(clubs))), 3)
    return out


def burst_scan(graph: Path = OUT, years: float = 5.62, step_months: int = 3) -> pd.DataFrame:
    """Every pair in every sliding window of `years` (default: the length of Minasian's tenure), stepping `step_months`:
    two-club trades in the window vs the pair's expected count refit to that window. One row per pair, at its most
    extreme window (smallest Poisson p of as many or more)."""
    from scipy.stats import poisson

    sides = pd.read_csv(graph / "sides.csv")
    trades = pd.read_csv(graph / "trades.csv", parse_dates=["date"])
    two = trades[trades.n_teams == 2]
    first, last = two.date.min(), two.date.max()
    span = pd.DateOffset(days=round(years * 365.25))
    rows, start = [], first
    while start + span <= last + pd.DateOffset(days=1):
        m = (two.date >= start) & (two.date < start + span)
        p = _pairs_in(sides, two[m].trade_id)
        p["p_more"] = poisson.sf(p.observed - 1, p.expected)
        p["window_start"] = start.date()
        rows.append(p)
        start = start + pd.DateOffset(months=step_months)
    allw = pd.concat(rows)
    best = allw.sort_values("p_more").groupby("pair", as_index=False).first().sort_values("p_more")
    best["windows"] = len(rows)
    return best[["pair", "kind", "window_start", "observed", "expected", "p_more", "windows"]]


RETRO_CODES = {"BAL": "BAL", "BOS": "BOS", "NYA": "NYY", "TBA": "TBR", "TOR": "TOR", "CHA": "CHW", "CLE": "CLE", "DET": "DET",
               "KCA": "KCR", "MIN": "MIN", "HOU": "HOU", "ANA": "LAA", "CAL": "LAA", "OAK": "ATH", "ATH": "ATH", "SEA": "SEA",
               "TEX": "TEX", "ATL": "ATL", "FLO": "MIA", "MIA": "MIA", "NYN": "NYM", "PHI": "PHI", "WAS": "WSN", "MON": "WSN",
               "CHN": "CHC", "CIN": "CIN", "MIL": "MIL", "PIT": "PIT", "SLN": "STL", "ARI": "ARI", "COL": "COL", "LAN": "LAD",
               "SDN": "SDP", "SFN": "SFG"}


def retrosheet_check(tran: Path, graph: Path = OUT, pairs: tuple[str, ...] = ("LAD-SFG", "CLE-KCR", "CHC-STL", "PHI-ATL",
                     "LAA-SEA", "ARI-SDP")) -> dict[str, pd.DataFrame]:
    """Cross-check against Retrosheet's transaction file (tran.txt from tranDB.zip; maintained through Feb. 2022).
    - coverage: feed trades per Retrosheet trade (code T) by season. Retrosheet counts only players with MLB time.
    - last_before_2009: each pair's last deal before Apr. 15, 2009, separately for trades (T) and conditional deals (C).
    - since_2009: each pair's deals from Apr. 15, 2009 on (T or C)."""
    import csv

    rows = []
    with open(tran, encoding="latin-1") as f:
        for r in csv.reader(f):
            if len(r) > 10 and r[0][:4].isdigit() and r[7].strip() in ("T", "C"):
                a, b = RETRO_CODES.get(r[8].strip()), RETRO_CODES.get(r[10].strip())
                if a and b and a != b:
                    mm, dd = (r[0][4:6] if r[0][4:6] != "00" else "01"), (r[0][6:8] if r[0][6:8] != "00" else "01")
                    rows.append({"date": pd.Timestamp(f"{r[0][:4]}-{mm}-{dd}"),
                                 "id": r[5], "type": r[7].strip(), "pair": "-".join(sorted((a, b)))})
    t = pd.DataFrame(rows)
    last_record = t.date.max()
    feed = pd.read_csv(graph / "trades.csv").groupby("season").size()
    retro = t[t.type == "T"].groupby(t.date.dt.year).id.nunique()
    seasons = [y for y in feed.index if y in retro.index and y >= FIRST_SEASON and y <= last_record.year]
    coverage = pd.DataFrame({"season": seasons, "feed": [int(feed[y]) for y in seasons], "retrosheet": [int(retro[y]) for y in seasons]})
    coverage["ratio"] = (coverage.feed / coverage.retrosheet).round(2)
    want = {"-".join(sorted(p.split("-"))): p for p in pairs}
    t = t[t.pair.isin(want)].assign(pair=lambda d: d.pair.map(want))
    before = t[t.date < "2009-04-15"]
    last = before.groupby(["pair", "type"]).date.max().unstack().reindex(list(pairs))
    since = t[t.date >= "2009-04-15"].groupby("pair").date.apply(lambda d: sorted({x.date() for x in d})).reindex(list(pairs))
    return {"coverage": coverage, "last_before_2009": last, "since_2009": since.to_frame("deals"), "last_record": last_record}
