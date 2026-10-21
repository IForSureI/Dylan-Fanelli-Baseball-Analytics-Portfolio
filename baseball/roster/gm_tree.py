"""The GM tree: whose front offices today's heads of baseball operations came through, which bosses had future heads
working under them, and what the path to the chair looks like.

Inputs are the front-office graph tables `bb front-office` exports to data/graph/ (and loads into Neo4j):
- worked_for.csv: every sourced job, one row per person, club, role and span of seasons;
- ran.csv: who ran each club (the president of baseball operations and the general manager), with dates.

Definitions:
- **Head seasons** are the seasons a person held a club's top baseball-operations job: a non-interim decision role in
  ran.csv (a GM under a president counts), plus, before 2009, a general manager title in worked_for.csv.
  Interim and acting roles don't count. "Interim, then permanent" tenures count from their start. Baseball-Reference
  lists interim GMs as plain "General Manager", so those GM-title rows are dropped where ran.csv marks the season
  interim and for four pre-2009 interims it doesn't cover (KNOWN_INTERIM).
- A club's **bosses** in a season are the people with a head season there. A person **became a head** in his first
  head season.
- **Learned under:** a person worked for a club, below its boss, in a season that boss ran it. Co-heads aren't each
  other's juniors. The edge keeps the club and the first and last shared seasons. It records shared employment only.
- A boss **had a future head under him** when someone who worked under him later became a head, after their first
  shared season.

Coverage: ran.csv and the careers file research every decision-maker from 2009 on, and Baseball-Reference's team
pages add each club's GM, scouting director and farm director from 1998. People who never reached one of those jobs
are mostly missing, so the tree counts future heads only.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

GRAPH = Path("data/graph")
FILL_BEFORE = 2009      # ran.csv covers every club from this season on; GM titles fill in before it

# Interim GMs before 2009 that Baseball-Reference lists as plain "General Manager" and ran.csv doesn't cover:
# Mike Port, Boston 2002 (acting GM, Feb.-Nov. 2002; en.wikipedia.org/wiki/Mike_Port); Tom Lasorda, Los Angeles 1998
# (interim GM, June-Sept. 1998); Dave Wallace, Los Angeles 2001 (interim GM; en.wikipedia.org/wiki/Dave_Wallace_(baseball));
# Bob Gebhard, Arizona 2005 (interim GM, Aug. 7-Oct. 28, 2005; en.wikipedia.org/wiki/Bob_Gebhard).
KNOWN_INTERIM = {("mikeport", "BOS", 2002), ("tomlasorda", "LAD", 1998), ("davewallace", "LAD", 2001),
                 ("bobgebhard", "ARI", 2005)}

_GM = re.compile(r"general manager", re.I)
_NOT_GM = re.compile(r"assistant|to the general manager|interim|acting|\bco-|committee", re.I)
_INTERIM = re.compile(r"interim|acting|\bco-|co-head|committee", re.I)


def is_gm_title(role: str) -> bool:
    """A general manager title that means running (or co-running under a president) the club's baseball side."""
    return bool(_GM.search(role or "")) and not _NOT_GM.search(role or "")


_BECAME_PERMANENT = re.compile(r"(interim|acting)[^;]*\bthen\b", re.I)
_SHARED = re.compile(r"\bco-|co-head|committee", re.I)


def is_interim(role: str) -> bool:
    """An interim, acting or shared caretaker role. "Interim GM, then General Manager" became permanent, so it isn't."""
    r = role or ""
    if _SHARED.search(r):
        return True
    return bool(_INTERIM.search(r)) and not _BECAME_PERMANENT.search(r)


def _years(df: pd.DataFrame) -> pd.DataFrame:
    """One row per season of each span (start..end inclusive)."""
    out = df.assign(year=[list(range(int(s), int(e) + 1)) for s, e in zip(df["start"], df["end"].fillna(df["start"]))])
    return out.explode("year").astype({"year": int}).reset_index(drop=True)


def load(graph: Path = GRAPH) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    wf = pd.read_csv(graph / "worked_for.csv")
    ran = pd.read_csv(graph / "ran.csv")
    names = dict(pd.read_csv(graph / "executives.csv")[["key", "name"]].itertuples(index=False))
    return wf, ran, names


def head_seasons(wf: pd.DataFrame, ran: pd.DataFrame, fill_before: int = FILL_BEFORE) -> pd.DataFrame:
    """key, club, year: every season a person held a club's top baseball-operations job (see the module notes)."""
    r = _years(ran[~ran["role"].map(is_interim)])[["key", "club", "year"]]
    interim = {(k, c, y) for k, c, y in _years(ran[ran["role"].map(is_interim)])[["key", "club", "year"]].itertuples(index=False)}
    g = _years(wf[wf["role"].map(is_gm_title)])[["key", "club", "year"]]
    keep = [(y < fill_before) and (k, c, y) not in interim and (k, c, y) not in KNOWN_INTERIM
            for k, c, y in g.itertuples(index=False)]
    g = g[np.array(keep, dtype=bool)]
    return pd.concat([r, g]).drop_duplicates().reset_index(drop=True)


def boss_years(wf: pd.DataFrame, ran: pd.DataFrame, fill_before: int = FILL_BEFORE) -> pd.DataFrame:
    """club, year, boss: who ran each club each season (a club can have two: a president and his GM)."""
    return head_seasons(wf, ran, fill_before).rename(columns={"key": "boss"})[["club", "year", "boss"]]


def first_head_year(wf: pd.DataFrame, ran: pd.DataFrame) -> pd.Series:
    """The first head season of each person."""
    return head_seasons(wf, ran).groupby("key")["year"].min().astype(int).rename("first_head")


def learned_under(wf: pd.DataFrame, bosses: pd.DataFrame) -> pd.DataFrame:
    """junior, boss, club, first, last, seasons: every boss a person worked below, and when."""
    j = _years(wf)[["key", "club", "year"]].drop_duplicates()
    m = j.merge(bosses, on=["club", "year"])
    m = m[m["key"] != m["boss"]]
    boss_set = set(zip(bosses["boss"], bosses["club"], bosses["year"]))
    m = m[np.array([(k, c, y) not in boss_set for k, c, y in zip(m["key"], m["club"], m["year"])], dtype=bool)]   # co-heads aren't juniors
    e = m.groupby(["key", "boss", "club"])["year"].agg(first="min", last="max", seasons="nunique").reset_index()
    return e.rename(columns={"key": "junior"})


def produced(edges: pd.DataFrame, first_head: pd.Series) -> pd.DataFrame:
    """The learned-under edges whose junior later became a head (after the first shared season)."""
    e = edges.assign(junior_first_head=edges["junior"].map(first_head))
    return e[e["junior_first_head"].notna() & (e["junior_first_head"] > e["first"])].astype({"junior_first_head": int})


def pagerank(edges: pd.DataFrame, src: str = "junior", dst: str = "boss", damping: float = 0.85, iters: int = 200,
             tol: float = 1e-12) -> pd.Series:
    """PageRank with junior -> boss links: a boss scores high when the people who worked under him went on to have
    future heads under them too. Dangling nodes spread their rank evenly, so scores sum to 1. Neo4j GDS's pageRank on the
    same graph leaves scores unnormalized and keeps dangling rank, but on this tree it gives the same top-12 order."""
    pairs = edges[[src, dst]].drop_duplicates()
    nodes = sorted(set(pairs[src]) | set(pairs[dst]))
    idx = {n: i for i, n in enumerate(nodes)}
    n = len(nodes)
    out_deg = np.zeros(n)
    for s in pairs[src]:
        out_deg[idx[s]] += 1
    r = np.full(n, 1.0 / n)
    for _ in range(iters):
        new = np.full(n, (1 - damping) / n)
        new += damping * r[out_deg == 0].sum() / n
        for s, d in zip(pairs[src], pairs[dst]):
            new[idx[d]] += damping * r[idx[s]] / out_deg[idx[s]]
        if np.abs(new - r).sum() < tol:
            r = new
            break
        r = new
    return pd.Series(r, index=nodes, name="pagerank").sort_values(ascending=False)


def descendants(prod: pd.DataFrame) -> dict[str, set[str]]:
    """Every head descended from each boss: the heads he produced, the heads they produced, and so on."""
    kids: dict[str, set[str]] = {}
    for b, j in zip(prod["boss"], prod["junior"]):
        kids.setdefault(b, set()).add(j)
    memo: dict[str, set[str]] = {}

    def walk(b: str, path: frozenset) -> set[str]:
        if b in memo:
            return memo[b]
        out: set[str] = set()
        for k in kids.get(b, ()):
            if k in path:
                continue
            out.add(k)
            out |= walk(k, path | {k})
        memo[b] = out
        return out

    return {b: walk(b, frozenset({b})) - {b} for b in kids}


def boss_table(prod: pd.DataFrame, names: dict[str, str]) -> pd.DataFrame:
    """Per boss: future heads who worked under him (all, and those who shared two or more seasons with him), heads in
    the whole tree, PageRank, and the names."""
    direct = prod.groupby("boss")["junior"].apply(lambda s: sorted(set(s)))
    seasons = prod.groupby(["boss", "junior"])["seasons"].sum()
    two_plus = seasons[seasons >= 2].reset_index().groupby("boss")["junior"].nunique()
    desc = descendants(prod)
    pr = pagerank(prod)
    t = pd.DataFrame({"boss": direct.index, "direct": direct.map(len).values,
                      "direct_2plus": [int(two_plus.get(b, 0)) for b in direct.index],
                      "tree": [len(desc.get(b, ())) for b in direct.index],
                      "pagerank": [pr.get(b, 0.0) for b in direct.index],
                      "heads": [", ".join(names.get(j, j) for j in v) for v in direct.values]})
    t.insert(1, "name", t["boss"].map(lambda k: names.get(k, k)))
    return t.sort_values(["direct", "tree", "pagerank"], ascending=False).reset_index(drop=True)


def current_heads(ran: pd.DataFrame, current_year: int = 2026) -> set[str]:
    """People running a club now: a non-interim decision role that runs through `current_year` with no departure
    date (ran.csv's `left` is blank or "current")."""
    r = ran[(ran["end"] == current_year) & ~ran["role"].map(is_interim)]
    if "left" in r:
        r = r[r["left"].isna() | (r["left"].astype(str).str.strip().str.lower() == "current")]
    return set(r["key"])


def club_table(wf: pd.DataFrame, first_head: pd.Series, current: set[str], names: dict[str, str]) -> pd.DataFrame:
    """Per club: future heads who worked there before their first head job, and how many of today's heads did."""
    w = _years(wf)[["key", "club", "year"]].drop_duplicates()
    w = w.assign(first_head=w["key"].map(first_head)).dropna(subset=["first_head"])
    w = w[w["year"] < w["first_head"]]
    g = w.groupby("club")["key"].apply(lambda s: sorted(set(s)))
    t = pd.DataFrame({"club": g.index, "future_heads": g.map(len).values,
                      "current_heads": [len(set(v) & current) for v in g.values],
                      "names": [", ".join(names.get(k, k) for k in v) for v in g.values]})
    return t.sort_values(["future_heads", "current_heads"], ascending=False).reset_index(drop=True)


_AGM = re.compile(r"assistant (general manager|gm)\b|\bagm\b", re.I)
_SCOUT_DIR = re.compile(r"scouting director|director of (amateur |professional |pro )?scouting|director, (amateur|pro)", re.I)
_PRO = re.compile(r"\bpro(fessional)?\b", re.I)
_PD_DIR = re.compile(r"farm director|player development|minor league", re.I)
_ENTRY = re.compile(r"\bintern(ship)?s?\b|assistant, baseball operations|baseball operations assistant|entry-level|video",
                    re.I)
_SCOUT = re.compile(r"scout", re.I)


def _amateur_director(role: str) -> bool:
    return bool(_SCOUT_DIR.search(role)) and not re.search(r"assistant", role, re.I) and not _PRO.search(role)


def _pro_director(role: str) -> bool:
    return bool(_SCOUT_DIR.search(role)) and not re.search(r"assistant", role, re.I) and bool(_PRO.search(role))


def paths(wf: pd.DataFrame, ran: pd.DataFrame, first_head: pd.Series, since: int = FILL_BEFORE) -> pd.DataFrame:
    """One row per head whose first head job came in `since` or later: what came before it."""
    hs = head_seasons(wf, ran)
    rows = []
    for k, fh in first_head.items():
        if fh < since:
            continue
        head_club = sorted(hs.loc[(hs["key"] == k) & (hs["year"] == fh), "club"])[0]
        before = wf[(wf["key"] == k) & (wf["start"] < fh)]
        if before.empty:
            rows.append({"key": k, "first_head": fh, "head_club": head_club, "first_job": np.nan,
                         "years_to_head": np.nan, "clubs_before": 0, "only_club_hired_there": False})
            continue
        roles = list(before["role"].astype(str))
        clubs = set(before["club"])
        rows.append({"key": k, "first_head": fh, "head_club": head_club, "first_job": int(before["start"].min()),
                     "years_to_head": fh - int(before["start"].min()), "clubs_before": len(clubs),
                     "only_club_hired_there": clubs == {head_club},
                     "agm": any(_AGM.search(r) for r in roles),
                     "amateur_scouting_director": any(_amateur_director(r) for r in roles),
                     "pro_scouting_director": any(_pro_director(r) for r in roles),
                     "pd_role": any(_PD_DIR.search(r) for r in roles),
                     "entry_level": any(_ENTRY.search(r) for r in roles),
                     "scout": any(_SCOUT.search(r) for r in roles),
                     "internal": bool(((before["club"] == head_club) & (before["end"].fillna(before["start"]) >= fh - 1)).any()),
                     "prior_roles": " | ".join(roles)})
    return pd.DataFrame(rows)


def path_summary(p: pd.DataFrame) -> dict:
    """The path to the chair in numbers (heads with a recorded job before their first head job)."""
    q = p.dropna(subset=["years_to_head"])
    out = {"heads": len(p), "with_prior_jobs": len(q),
           "years_median": float(q["years_to_head"].median()), "years_p25": float(q["years_to_head"].quantile(0.25)),
           "years_p75": float(q["years_to_head"].quantile(0.75)), "clubs_median": float(q["clubs_before"].median()),
           "one_club": int((q["clubs_before"] == 1).sum()), "one_club_hired_there": int(q["only_club_hired_there"].sum())}
    for c in ("agm", "amateur_scouting_director", "pro_scouting_director", "pd_role", "entry_level", "scout", "internal"):
        out[c] = int(q[c].astype(bool).sum())
    return out


def neo4j_rows(edges: pd.DataFrame, first_head: pd.Series) -> list[dict]:
    """The learned-under edges as parameter rows for Neo4j (see LOAD_CYPHER)."""
    e = edges.assign(produced_head=[bool(pd.notna(first_head.get(j)) and first_head.get(j) > f)
                                    for j, f in zip(edges["junior"], edges["first"])])
    return [{k: (int(v) if isinstance(v, (np.integer,)) else v) for k, v in r.items()}
            for r in e[["junior", "boss", "club", "first", "last", "seasons", "produced_head"]].to_dict("records")]


def export_tables(out: Path = GRAPH, graph: Path = GRAPH) -> dict[str, int]:
    """learned_under.csv and heads.csv for Neo4j (load with gm_tree.cypher)."""
    o = run(graph)
    rows = pd.DataFrame(neo4j_rows(o["edges"], o["first_head"]))
    rows.to_csv(out / "learned_under.csv", index=False)
    heads = o["first_head"].rename_axis("key").reset_index()
    heads.to_csv(out / "heads.csv", index=False)
    return {"learned_under": len(rows), "heads": len(heads)}


CYPHER = Path(__file__).with_name("gm_tree.cypher")

LOAD_CYPHER = """
UNWIND $rows AS r
MATCH (j:Executive {key: r.junior}), (b:Executive {key: r.boss})
MERGE (j)-[e:LEARNED_UNDER {club: r.club}]->(b)
SET e.first = r.first, e.last = r.last, e.seasons = r.seasons, e.produced_head = r.produced_head
"""

HEAD_CYPHER = """
UNWIND $rows AS r
MATCH (x:Executive {key: r.key})
SET x.first_head = r.first_head
"""


def run(graph: Path = GRAPH) -> dict:
    wf, ran, names = load(graph)
    bosses = boss_years(wf, ran)
    fh = first_head_year(wf, ran)
    edges = learned_under(wf, bosses)
    prod = produced(edges, fh)
    p = paths(wf, ran, fh)
    return {"bosses": bosses, "first_head": fh, "edges": edges, "produced": prod,
            "boss_table": boss_table(prod, names), "current": current_heads(ran),
            "club_table": club_table(wf, fh, current_heads(ran), names),
            "paths": p, "path_summary": path_summary(p), "names": names}


def tree_layers(prod: pd.DataFrame, root: str, keep: set[str] | None = None) -> tuple[dict[int, list[str]], dict[str, str]]:
    """Generations below `root` (breadth-first, each person at his shortest distance). With `keep`, only people in
    `keep` and the people on a shortest line from the root down to them."""
    kids: dict[str, set[str]] = {}
    for b, j in zip(prod["boss"], prod["junior"]):
        kids.setdefault(b, set()).add(j)
    gen, parent, frontier = {root: 0}, {}, [root]
    while frontier:
        nxt = []
        for x in sorted(frontier):
            for k in sorted(kids.get(x, ())):
                if k not in gen:
                    gen[k], parent[k] = gen[x] + 1, x
                    nxt.append(k)
        frontier = nxt
    if keep is not None:
        on = {root}
        for k in set(gen) & keep:
            while k != root:
                on.add(k)
                k = parent[k]
        gen = {k: g for k, g in gen.items() if k in on}
    layers: dict[int, list[str]] = {}
    for k, g in gen.items():
        layers.setdefault(g, []).append(k)
    return {g: sorted(v) for g, v in sorted(layers.items())}, parent


def figure(o: dict, out: Path = Path("reports/figures/2026-gm-tree.png"), root: str = "johnhart") -> Path:
    """Left: clubs ranked by future heads who worked there first. Right: the lines from John Hart (Cleveland, then
    Texas) to today's heads."""
    import matplotlib.pyplot as plt

    from baseball.viz import GRID, INK, MUTED, OTHER, _style

    accent = "#2a78d6"
    names, cur = o["names"], o["current"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(14, 7.6), dpi=160, gridspec_kw={"width_ratios": [1, 2.1]})
    ct = o["club_table"].head(12).iloc[::-1]
    _style(a)
    y = np.arange(len(ct))
    a.barh(y, ct["future_heads"], color=OTHER, height=0.62)
    a.barh(y, ct["current_heads"], color=accent, height=0.62)
    for yi, (f, c) in enumerate(zip(ct["future_heads"], ct["current_heads"])):
        a.text(f + 0.25, yi, f"{f}  ({c} today)", va="center", fontsize=8.5, color=INK)
    a.set_yticks(y, ct["club"], fontsize=9, color=INK)
    a.set_xlim(0, ct["future_heads"].max() + 3.5)
    from matplotlib.ticker import MaxNLocator
    a.xaxis.set_major_locator(MaxNLocator(integer=True))
    a.grid(axis="y", visible=False)
    a.set_xlabel("Future heads who worked there first (blue: in a top job today)", color=MUTED, fontsize=9)
    a.set_title("Where future heads worked first", loc="left", color=INK, fontsize=11.5, fontweight="bold")

    layers, parent = tree_layers(o["produced"], root, keep=cur)
    b.set_facecolor("#fcfcfb")
    b.axis("off")
    pos: dict[str, tuple[float, float]] = {}
    tallest = max(len(v) for v in layers.values())
    for g, people in layers.items():
        if g:   # children sit in their parents' order, which keeps most lines apart
            people = sorted(people, key=lambda k: (-pos[parent[k]][1], names.get(k, k)))
        n = len(people)
        for i, k in enumerate(people):
            pos[k] = (g, (n - 1) / 2 - i)
    for k, (x, yy) in pos.items():
        if k in parent and parent[k] in pos:
            px, py = pos[parent[k]]
            b.plot([px + (0.72 if parent[k] == root else 0.55), x - 0.04], [py, yy], color=GRID, lw=1.1, zorder=1)
    for k, (x, yy) in pos.items():
        is_cur = k in cur
        b.scatter([x], [yy], s=34, color=accent if is_cur else OTHER, zorder=3, edgecolors="#fcfcfb", linewidths=1.2)
        b.text(x + 0.05, yy, names.get(k, k), va="center", fontsize=7.8, color=INK if is_cur else MUTED,
               fontweight="bold" if k == root else "normal")
    rx, ry = pos[root]
    b.text(rx + 0.05, ry - 0.45, "GM: Cleveland 1991-2001,\nTexas 2002-05", va="top", fontsize=7.2, color=MUTED)
    gens = max(layers)
    heads = ["", "worked under Hart", "worked under them", "the next generation"]
    for g in range(gens + 1):
        b.text(g, tallest / 2 + 0.2, heads[min(g, 3)], fontsize=8.5, color=MUTED, ha="left")
    b.set_xlim(-0.1, gens + 0.75)
    b.set_ylim(-tallest / 2 - 0.3, tallest / 2 + 0.7)
    b.set_title(f"From John Hart to {len(set().union(*layers.values()) & cur)} of the {len(cur)} people in a club's "
                f"top baseball-operations job today (blue)", loc="left", color=INK, fontsize=11.5, fontweight="bold")
    fig.suptitle("The GM tree: more future heads of baseball operations came through Cleveland than any other club",
                 x=0.01, ha="left", color=INK, fontsize=13, fontweight="bold")
    fig.text(0.01, 0.008, "A head held a club's top baseball-operations job: president of baseball operations or GM, "
             "interims excluded. Worked under = worked for the club below its boss in the same season (shared employment; the "
             "data hold no record of mentoring).\nLines show each person's shortest route to Hart; where two are equally short, "
             "one is drawn. Gray = no longer in a top job. Today = Oct. 2026. Sources: sourced career histories of every "
             "decision-maker since 2009; Baseball-Reference team pages, 1998-2026.", color=MUTED, fontsize=7.3)
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    return out


if __name__ == "__main__":
    out = run()
    with pd.option_context("display.width", 220, "display.max_colwidth", 120):
        print(out["boss_table"].head(20).to_string(index=False))
        print(out["club_table"].head(15).to_string(index=False))
        print(out["path_summary"])
