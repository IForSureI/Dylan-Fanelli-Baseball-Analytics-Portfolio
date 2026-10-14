"""Front offices: who ran each club, where they worked before, and whether shared history predicts trade partners.

Grain:
- staff: one person in one listed role for one club-season (Baseball-Reference team pages list President,
  General Manager, Farm Director and Scouting Director).
- stint: one person's job at one club over a span of seasons, from the staff panel or from a sourced career
  history (`executive_careers.json`, which adds roles Baseball-Reference doesn't list, such as assistant GM).
- pair-season: two clubs in one season, with their two-club trades and whether their decision-makers are tied.

Decision-makers are the club's President (of baseball operations) and General Manager in a season.
"""
from __future__ import annotations

import html
import json
import re
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from baseball.roster.trades import TEAMS

RAW = Path("data/raw/front_office")
OUT = Path("data/graph")
CAREERS = Path(__file__).with_name("executive_careers.json")
ROLES = ("President", "General Manager", "Farm Director", "Scouting Director")
TOP_ROLES = ("President", "General Manager")


def bbref_code(abbr: str, season: int) -> str:
    """Baseball-Reference's team code for a club in a season (franchise renames included)."""
    if abbr == "LAA":
        return "ANA" if season <= 2004 else "LAA"
    if abbr == "MIA":
        return "FLA" if season <= 2011 else "MIA"
    if abbr == "WSN":
        return "MON" if season <= 2004 else "WSN"
    if abbr == "TBR":
        return "TBD" if season <= 2007 else "TBR"
    if abbr == "ATH":
        return "OAK" if season <= 2024 else "ATH"
    return abbr


def pull(first: int = 1998, last: int = 2026, raw: Path = RAW, pause: float = 3.5, refresh_last: bool = True) -> int:
    """Cache every club-season team page from Baseball-Reference (about 20 requests a minute, their stated limit).
    Club-seasons already in the parsed cache (`staff_panel.csv`) are skipped, except the last season."""
    raw.mkdir(parents=True, exist_ok=True)
    done = set()
    if (raw / "staff_panel.csv").exists():
        c = pd.read_csv(raw / "staff_panel.csv")
        done = set(zip(c.club, c.season))
    fetched = 0
    for season in range(first, last + 1):
        for _, (abbr, _) in sorted(TEAMS.items()):
            f = raw / f"{abbr}_{season}.html"
            fresh = refresh_last and season == last
            if (f.exists() or (abbr, season) in done) and not fresh:
                continue
            url = f"https://www.baseball-reference.com/teams/{bbref_code(abbr, season)}/{season}.shtml"
            for attempt in range(4):
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research; one request per 3.5s)"})
                    with urllib.request.urlopen(req, timeout=60) as r:
                        f.write_bytes(r.read())
                    break
                except Exception:
                    time.sleep(30 * (attempt + 1))
            fetched += 1
            time.sleep(pause)
    return fetched


_BLOCK = re.compile(r"<strong>(President|General Manager|Farm Director|Scouting Director):</strong>(.*?)</p>", re.S)
_LINK = re.compile(r'<a href="/register/player\.fcgi\?id=([^"]+)">([^<]+)</a>')


def _split_people(plain: str) -> list[tuple[str, str]]:
    """'A (note (nested)), B and C (note)' -> [(A, 'note (nested)'), (B, ''), (C, 'note')]: splits on commas and
    'and' outside parentheses."""
    chunks, depth, cur = [], 0, ""
    i = 0
    while i < len(plain):
        ch = plain[i]
        depth += ch == "("
        depth -= ch == ")"
        if depth == 0 and (ch == "," or plain[i:i + 5] == " and "):
            chunks.append(cur)
            cur = ""
            i += 1 if ch == "," else 5
            continue
        cur += ch
        i += 1
    chunks.append(cur)
    out = []
    for c in chunks:
        k = c.find("(")
        name = (c if k < 0 else c[:k]).strip()
        note = "" if k < 0 else c[k + 1:c.rfind(")") if ")" in c else len(c)].strip()
        if name:
            out.append((name, note))
    return out


def parse_page(text: str) -> list[dict]:
    """The listed front-office roles on one team page: [{role, name, bbref_id, note}]. A role held by several
    people in a season (a change mid-year) gives one row each, in the order listed."""
    rows = []
    for role, body in _BLOCK.findall(text):
        links = {name.strip(): pid for pid, name in _LINK.findall(body)}
        plain = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", body))).strip()
        for name, note in _split_people(plain):
            rows.append({"role": role, "name": name, "bbref_id": links.get(name, ""), "note": note})
    return rows


def staff_panel(raw: Path = RAW) -> pd.DataFrame:
    """Every club-season's listed front office: club, season, role, name, bbref_id, note. Parses the cached pages,
    merges them over the parsed cache (`staff_panel.csv`, pages win) and rewrites the cache."""
    rows = []
    for f in sorted(raw.glob("*_*.html")):
        abbr, season = f.stem.split("_")
        for r in parse_page(f.read_text(encoding="utf-8", errors="ignore")):
            rows.append({"club": abbr, "season": int(season), **r})
    parsed = pd.DataFrame(rows, columns=["club", "season", "role", "name", "bbref_id", "note"])
    cache = raw / "staff_panel.csv"
    if cache.exists():
        old = pd.read_csv(cache, keep_default_na=False)
        keep = ~old.set_index(["club", "season"]).index.isin(parsed.set_index(["club", "season"]).index)
        parsed = pd.concat([old[keep], parsed], ignore_index=True)
    parsed = parsed.sort_values(["season", "club"]).reset_index(drop=True)
    if len(parsed):
        raw.mkdir(parents=True, exist_ok=True)
        parsed.to_csv(cache, index=False)
    return parsed


# ---------------------------------------------------------------- careers and ties
ALIASES = {"daviddombrowski": "davedombrowski", "douglasmelvin": "dougmelvin", "mikehill": "michaelhill",
}


def normalize(name: str) -> str:
    """Name key: accents, punctuation and suffixes dropped, lower case ("A.J. Preller" == "AJ Preller")."""
    import unicodedata

    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\b(jr|sr|ii|iii)\b\.?", "", n)
    n = re.sub(r"[^a-z]", "", n)
    return ALIASES.get(n, n)


def panel_spans(panel: pd.DataFrame) -> pd.DataFrame:
    """One row per person-club-role span of consecutive seasons in the staff panel (source: Baseball-Reference)."""
    p = panel.assign(person=panel.name.map(normalize)).sort_values(["person", "club", "role", "season"])
    rows = []
    for (person, club, role), g in p.groupby(["person", "club", "role"]):
        seasons = g.season.tolist()
        start = prev = seasons[0]
        for s in seasons[1:] + [None]:
            if s is not None and s == prev + 1:
                prev = s
                continue
            rows.append({"person": person, "name": g.name.iloc[0], "club": club, "role": role, "start": start, "end": prev,
                         "source": "Baseball-Reference team pages"})
            if s is not None:
                start = prev = s
    return pd.DataFrame(rows)


_NON_OPS = re.compile(r"media relations|public relations|marketing|sales|counsel|legal|ticket|communications|broadcast|"
                      r"finance|accounting|liaison|promotions|community|president of business", re.I)
_OPS = re.compile(r"baseball op|player development|minor league|scout|general manager|farm|player personnel", re.I)
_CONSULT = re.compile(r"consult", re.I)
_DATE = re.compile(r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?")


def _parse_date(v) -> tuple[int, int] | None:
    m = _DATE.match(str(v or "").strip())
    return (int(m.group(1)), int(m.group(2) or 0)) if m else None


HIRE_CUTOFF = 9   # hired in this month or later: the job counts from the next season


def role_seasons(start: int, end: int, hired=None, left=None, hire_cutoff: int = HIRE_CUTOFF) -> range:
    """Seasons a person ran a club's trading, by the study's rule. From dates when given: hired in September or
    later counts from the next season (the season's trading is done by then: 2.5% of trades fall in September);
    left before April doesn't count that season. A job held only in an offseason gets no season.
    `hire_cutoff=10` is the sensitivity version, where September hires count in that season."""
    h, l = _parse_date(hired), _parse_date(left)
    if h and h[1]:
        start = h[0] + (1 if h[1] >= hire_cutoff else 0)
    if l and l[1]:
        end = l[0] - (1 if l[1] < 4 else 0)
    return range(int(start), int(end) + 1)


def is_baseball_ops(role: str) -> bool:
    """Front-office baseball operations (scouting, development, analytics, management), not business-side jobs."""
    return bool(_OPS.search(role)) or not _NON_OPS.search(role)


def stints_from_careers(path: Path = CAREERS, certain_only: bool = False, hire_cutoff: int = HIRE_CUTOFF) -> pd.DataFrame:
    """Sourced career histories (`executive_careers.json`): one row per person-club-season of baseball-operations
    work, with flags for consulting and for holding a decision role there that season. Exact duplicate stints
    from the merged research files collapse; business-side jobs are dropped."""
    data = json.loads(path.read_text())
    rows = []
    for p in data["people"]:
        k = normalize(p["name"])
        decision = {(r["club"], s) for r in p["decision_roles"]
                    for s in role_seasons(r["start"], r["end"], r.get("hired"), r.get("left"), hire_cutoff)}
        for st in p["stints"]:
            if not is_baseball_ops(st["role"]) or (certain_only and st.get("uncertain")):
                continue
            consult = bool(_CONSULT.search(st["role"])) and not re.search(r"interim general manager|scout", st["role"], re.I)
            for s in range(int(st["start"]), int(st["end"]) + 1):
                rows.append({"person": k, "club": st["club"], "season": s, "consultant": consult,
                             "decision": (st["club"], s) in decision})
        for club, s in decision:
            rows.append({"person": k, "club": club, "season": s, "consultant": False, "decision": True})
    d = pd.DataFrame(rows)
    # a season counts as a regular job if any stint that season was one; decision if any role that season was
    return (d.groupby(["person", "club", "season"], as_index=False)
             .agg(consultant=("consultant", "min"), decision=("decision", "max")))


def stints_from_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """Baseball-Reference listings as person-club-seasons (President and GM listings count as decision seasons)."""
    p = panel.assign(person=panel.name.map(normalize), decision=panel.role.isin(TOP_ROLES), consultant=False)
    return p.groupby(["person", "club", "season"], as_index=False).agg(consultant=("consultant", "min"), decision=("decision", "max"))


def decision_makers_from_careers(path: Path = CAREERS, seasons: range = range(2009, 2027), drop: tuple[str, ...] = (),
                                 hire_cutoff: int = HIRE_CUTOFF) -> pd.DataFrame:
    """Club-season -> decision-makers, from the dated decision roles (season rule from hire and departure dates)."""
    data = json.loads(path.read_text())
    rows = []
    for p in data["people"]:
        k = normalize(p["name"])
        if k in drop:
            continue
        for r in p["decision_roles"]:
            for s in role_seasons(r["start"], r["end"], r.get("hired"), r.get("left"), hire_cutoff):
                if s in seasons:
                    rows.append({"club": r["club"], "season": s, "person": k})
    d = pd.DataFrame(rows).drop_duplicates()
    return d.groupby(["club", "season"]).person.apply(sorted).reset_index()


def decision_makers(panel: pd.DataFrame, drop: tuple[str, ...] = ("jimcrane",)) -> pd.DataFrame:
    """Club-season -> the people Baseball-Reference lists as President or General Manager (owners dropped)."""
    d = panel[panel.role.isin(TOP_ROLES)].assign(person=lambda x: x.name.map(normalize))
    d = d[~d.person.isin(drop)]
    return d.groupby(["club", "season"]).person.apply(lambda s: sorted(set(s))).reset_index()


def _history(stints: pd.DataFrame) -> dict:
    """person -> club -> (all regular seasons, decision seasons), consulting excluded."""
    h = {}
    for r in stints[~stints.consultant].itertuples():
        a = h.setdefault(r.person, {}).setdefault(r.club, (set(), set()))
        a[0].add(r.season)
        if r.decision:
            a[1].add(r.season)
    return h


def tie_panel(dm: pd.DataFrame, stints: pd.DataFrame, seasons: range) -> pd.DataFrame:
    """Pair-season ties between two clubs' decision-makers, from seasons before the current one.
    - former_employer: one club's decision-maker worked in the other club's front office.
    - former_colleagues: they worked in the same front office in at least two common seasons, or one common
      season in which neither held a decision role there (a handover isn't colleagues).
    - protege: one worked in a front office, below the decision level, in a season the other ran it.
    The same person at both clubs (a mid-season move) is never a tie."""
    h = _history(stints)
    dmap = {(r.club, r.season): r.person for r in dm.itertuples()}
    clubs = sorted(a for a, _ in TEAMS.values())
    rows = []
    for s in seasons:
        for i, a in enumerate(clubs):
            for b in clubs[i + 1:]:
                pa, pb = dmap.get((a, s), []), dmap.get((b, s), [])
                emp, col, pro, who = False, False, False, []
                for x, other in [(p, b) for p in pa] + [(p, a) for p in pb]:
                    if x in pb and x in pa:
                        continue
                    seen = h.get(x, {}).get(other, (set(), set()))[0]
                    if any(t < s for t in seen):
                        emp = True
                        who.append(f"{x} worked for {other}")
                for x in pa:
                    for y in pb:
                        if x == y:
                            continue
                        hx, hy = h.get(x, {}), h.get(y, {})
                        for club in set(hx) & set(hy):
                            (sx, dx), (sy, dy) = hx[club], hy[club]
                            common = {t for t in sx & sy if t < s}
                            if len(common) >= 2 or any(t not in dx and t not in dy for t in common):
                                col = True
                                who.append(f"{x}+{y} colleagues at {club}")
                            for p_, q_, sp, dp, dq in ((x, y, sx, dx, dy), (y, x, sy, dy, dx)):
                                if any(t < s and t in dq and t not in dp for t in sp):
                                    pro = True
                                    who.append(f"{p_} under {q_} at {club}")
                rows.append({"season": s, "pair": f"{a}-{b}", "a": a, "b": b, "former_employer": emp,
                             "former_colleagues": col, "protege": pro, "tied": emp or col or pro,
                             "who": ";".join(sorted(set(who)))})
    return pd.DataFrame(rows)


def baseball_year(dates: pd.Series) -> pd.Series:
    """The season a date belongs to under the study's rule: October 1 onward counts toward the next season."""
    d = pd.to_datetime(dates)
    return d.dt.year + (d.dt.month >= 10).astype(int)


def pair_season_trades(graph: Path = OUT) -> pd.DataFrame:
    """Two-club trades per pair and baseball year (pair named by sorted abbreviations, as in tie_panel)."""
    abbr = {i: a for i, (a, _) in TEAMS.items()}
    sides = pd.read_csv(graph / "sides.csv")
    trades = pd.read_csv(graph / "trades.csv")
    two = trades[trades.n_teams == 2][["trade_id", "date"]].assign(season=lambda x: baseball_year(x.date))
    s = sides.merge(two, on="trade_id")
    pairs = s.groupby("trade_id").agg(season=("season", "first"), pair=("team_id", lambda x: "-".join(sorted(abbr[i] for i in x))))
    return pairs.groupby(["pair", "season"]).size().rename("trades").reset_index()


def fe_poisson(df: pd.DataFrame, x_cols: list[str], cluster: str = "pair", iters: int = 200, pair_fe: bool = True,
               se: bool = True, stricter: bool = False) -> pd.DataFrame:
    """Poisson regression of trades on x_cols with pair and club-season fixed effects, standard errors
    clustered by `cluster` with a G/(G-1) correction. `stricter` also applies (N-1)/(N-K), K the rank of the
    full design, fixed effects included. Pairs with no trades in any season carry no information and are
    dropped. Returns one row per x: rate ratio, 95% interval and p."""
    from scipy.stats import norm

    d = (df[df.groupby("pair").trades.transform("sum") > 0] if pair_fe else df).reset_index(drop=True)
    cs = pd.concat([d.a + "_" + d.season.astype(str), d.b + "_" + d.season.astype(str)])
    cs_levels = {k: i for i, k in enumerate(sorted(cs.unique()))}
    pair_levels = {k: i for i, k in enumerate(sorted(d.pair.unique()))} if pair_fe else {"_": 0}
    n, kp, kc, kx = len(d), len(pair_levels), len(cs_levels), len(x_cols)
    X = np.zeros((n, kp + kc + kx))
    X[np.arange(n), d.pair.map(pair_levels).to_numpy() if pair_fe else 0] = 0 if not pair_fe else 1
    X[np.arange(n), kp + (d.a + "_" + d.season.astype(str)).map(cs_levels).to_numpy()] += 1
    X[np.arange(n), kp + (d.b + "_" + d.season.astype(str)).map(cs_levels).to_numpy()] += 1
    X[:, kp + kc:] = d[x_cols].astype(float).to_numpy()
    X = X[:, 1:]                                     # one pair dummy is the reference (none without pair effects)
    y = d.trades.to_numpy(float)
    b = np.zeros(X.shape[1])
    b[:] = 0.0
    eta = np.log(np.maximum(y, 0.1))
    for _ in range(iters):
        mu = np.exp(eta)
        z = eta + (y - mu) / mu
        XtW = X.T * mu
        new = np.linalg.lstsq(XtW @ X + 1e-8 * np.eye(X.shape[1]), XtW @ z, rcond=None)[0]
        new_eta = X @ new
        if np.max(np.abs(new_eta - eta)) < 1e-9:
            b, eta = new, new_eta
            break
        b, eta = new, new_eta
    mu = np.exp(eta)
    if not se:
        k0 = X.shape[1] - kx
        return pd.DataFrame([{"term": n, "rate_ratio": float(np.exp(b[k0 + j]))} for j, n in enumerate(x_cols)])
    H = (X.T * mu) @ X
    Hinv = np.linalg.pinv(H)
    score = X * (y - mu)[:, None]
    g = d[cluster].to_numpy()
    S = np.zeros_like(H)
    for key in np.unique(g):
        sg = score[g == key].sum(axis=0)
        S += np.outer(sg, sg)
    G = len(np.unique(g))
    V = Hinv @ S @ Hinv * G / (G - 1)
    if stricter:
        V = V * (n - 1) / (n - np.linalg.matrix_rank(X))
    out = []
    for j, name in enumerate(x_cols):
        k = X.shape[1] - kx + j
        se = np.sqrt(V[k, k])
        out.append({"term": name, "rate_ratio": float(np.exp(b[k])), "ci_low": float(np.exp(b[k] - 1.96 * se)),
                    "ci_high": float(np.exp(b[k] + 1.96 * se)), "p": float(2 * norm.sf(abs(b[k]) / se)),
                    "pair_seasons": n, "pairs": int(d.pair.nunique()), "tied_pair_seasons": int(d[name].sum()) if d[name].dtype == bool or set(d[name].unique()) <= {0, 1} else None})
    return pd.DataFrame(out)


def panel_for_model(ties: pd.DataFrame, graph: Path = OUT) -> pd.DataFrame:
    """Every pair-season (zeros included) with its two-club trades and its ties."""
    t = pair_season_trades(graph)
    d = ties.merge(t, on=["pair", "season"], how="left").fillna({"trades": 0})
    d["trades"] = d.trades.astype(int)
    return d


def export_graph_tables(out: Path = OUT, path: Path = CAREERS, panel: pd.DataFrame | None = None) -> dict[str, int]:
    """Executives for Neo4j: executives.csv, worked_for.csv (every sourced stint, plus Baseball-Reference panel
    stints when a panel is given) and ran.csv (dated decision roles)."""
    data = json.loads(path.read_text())
    ex, wf, ran = {}, [], []
    for p in data["people"]:
        k = normalize(p["name"])
        ex[k] = {"key": k, "name": p["name"]}
        for s in p["stints"]:
            wf.append({"key": k, "club": s["club"], "role": s["role"], "start": int(s["start"]), "end": int(s["end"]),
                       "uncertain": bool(s.get("uncertain", False)), "source": s["source"]})
        for r in p["decision_roles"]:
            ran.append({"key": k, "club": r["club"], "role": r["role"], "start": int(r["start"]), "end": int(r["end"]),
                        "hired": r.get("hired") or "", "left": r.get("left") or ""})
    if panel is not None and len(panel):
        for r in panel_spans(panel).itertuples():
            ex.setdefault(r.person, {"key": r.person, "name": r.name})
            wf.append({"key": r.person, "club": r.club, "role": r.role, "start": r.start, "end": r.end, "uncertain": False,
                       "source": r.source})
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(ex.values()).to_csv(out / "executives.csv", index=False)
    wf = pd.DataFrame(wf).drop_duplicates(["key", "club", "role", "start", "end"])
    wf.to_csv(out / "worked_for.csv", index=False)
    pd.DataFrame(ran).to_csv(out / "ran.csv", index=False)
    return {"executives": len(ex), "worked_for": len(wf), "ran": len(ran)}


def build_panel(graph: Path = OUT, raw: Path = RAW, path: Path = CAREERS, expanded: bool = False,
                certain_only: bool = False, hire_cutoff: int = HIRE_CUTOFF) -> pd.DataFrame:
    """The pair-season panel (baseball years, October 1 boundary) with every tie and the event-time terms.
    `expanded` adds Baseball-Reference's listings: its presidents and GMs as decision-makers (club presidents
    with business titles included, owners not) and its listed seasons as career seasons from 1998.
    Divisions follow each season's alignment (Houston in the NL Central through 2012)."""
    seasons = range(2009, 2027)
    dm = decision_makers_from_careers(path, seasons, hire_cutoff=hire_cutoff)
    stints = stints_from_careers(path, certain_only=certain_only, hire_cutoff=hire_cutoff)
    if expanded:
        panel = staff_panel(raw)
        bb = decision_makers(panel[panel.season.isin(seasons)])
        dm = dm.merge(bb, on=["club", "season"], how="outer", suffixes=("", "_bb"))
        dm["person"] = [sorted(set(a if isinstance(a, list) else []) | set(b if isinstance(b, list) else []))
                        for a, b in zip(dm.person, dm.person_bb)]
        dm = dm[["club", "season", "person"]]
        stints = (pd.concat([stints, stints_from_panel(panel)], ignore_index=True)
                  .groupby(["person", "club", "season"], as_index=False).agg(consultant=("consultant", "min"), decision=("decision", "max")))
    d = panel_for_model(tie_panel(dm, stints, seasons), graph)
    d["same_division"] = [division(a, s) == division(b, s) for a, b, s in zip(d.a, d.b, d.season)]
    return add_event_time(d, "protege")


def division(club: str, season: int) -> str:
    """A club's division that season: today's alignment, except Houston in the NL Central through 2012."""
    from baseball.roster.trades import DIVISIONS

    if club == "HOU" and season <= 2012:
        return "NL Central"
    return next(k for k, ts in DIVISIONS.items() if club in ts.split())


def add_event_time(d: pd.DataFrame, tie: str) -> pd.DataFrame:
    """Event-time indicators around each pair's first `tie` season (onset): three seasons before (lead_3..lead_1),
    tied seasons by time since onset (on_0, on_1, on_2, on_3plus), and seasons after a tie has ended (ended).
    The reference is every other pair-season: never-tied pairs and seasons more than three before onset."""
    d = d.sort_values(["pair", "season"]).copy()
    onset = d.pair.map(d[d[tie]].groupby("pair").season.min())
    e = d.season - onset
    tied = d[tie]
    for k in (3, 2, 1):
        d[f"lead_{k}"] = (e == -k) & ~tied
    for k in (0, 1, 2):
        d[f"on_{k}"] = tied & (e == k)
    d["on_3plus"] = tied & (e >= 3)
    d["ended"] = ~tied & (e > 0)
    return d


EVENT_TERMS = ["lead_3", "lead_2", "lead_1", "on_0", "on_1", "on_2", "on_3plus", "ended"]


def permutation_p(d: pd.DataFrame, tie: str, draws: int = 300, seed: int = 11, progress=None) -> dict:
    """Randomization inference for one tie: each tied pair keeps its pattern of tied seasons, moved to a random
    circular shift within 2009-2026, and the model is refit. Two-sided p: the share of shifted estimates at least
    as far from 1 (in logs) as the observed one; one-sided p: the share at least as large. Both are (1 + count) /
    (draws + 1), with the Monte Carlo standard error of the two-sided p."""
    rng = np.random.default_rng(seed)
    obs = fe_poisson(d, [tie], se=False).rate_ratio.iloc[0]
    d = d.sort_values(["pair", "season"]).reset_index(drop=True)
    tied_pairs = d.groupby("pair")[tie].transform("any")
    out = []
    for _ in range(draws):
        x = d[tie].to_numpy().copy()
        for pr, idx in d[tied_pairs].groupby("pair").groups.items():
            idx = np.asarray(idx)
            x[idx] = np.roll(x[idx], rng.integers(1, len(idx)))
        out.append(fe_poisson(d.assign(**{tie: x}), [tie], se=False).rate_ratio.iloc[0])
        if progress is not None:
            progress(len(out))
    out = np.array(out)
    p2 = float((1 + (np.abs(np.log(out)) >= abs(np.log(obs))).sum()) / (draws + 1))
    return {"observed": float(obs), "draws": draws, "p_two_sided": p2, "mc_se": float(np.sqrt(p2 * (1 - p2) / draws)),
            "p_one_sided": float((1 + (out >= obs).sum()) / (draws + 1)), "null_median": float(np.median(out)),
            "share_below_observed": float((out < obs).mean())}


def report_tables(d: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Every model in reports/2026-front-office-ties.md."""
    nolaa = d[d.pair != "ATL-LAA"]
    within = pd.concat([
        fe_poisson(d, ["tied"]), fe_poisson(d, ["former_employer"]), fe_poisson(d, ["former_colleagues"]),
        fe_poisson(d, ["protege"]),
        fe_poisson(d, ["former_employer", "former_colleagues", "protege"]).assign(term=lambda x: x.term + " (joint)"),
        fe_poisson(nolaa, ["tied"]).assign(term="tied, without ATL-LAA"),
        fe_poisson(nolaa, ["protege"]).assign(term="protege, without ATL-LAA")])
    stricter = pd.concat([fe_poisson(d, [t], stricter=True) for t in ("tied", "former_employer", "former_colleagues", "protege")] + [
        fe_poisson(nolaa, ["tied"], stricter=True).assign(term="tied, without ATL-LAA"),
        fe_poisson(nolaa, ["protege"], stricter=True).assign(term="protege, without ATL-LAA")])
    event = fe_poisson(d, EVENT_TERMS)
    event_nolaa = fe_poisson(nolaa, EVENT_TERMS)
    across = pd.concat([fe_poisson(d, ["tied", "same_division"], pair_fe=False),
                        fe_poisson(d, ["protege", "same_division"], pair_fe=False)])
    m = d[d.trades.groupby(d.pair).transform("sum") > 0]
    sw = m.groupby("pair").tied.agg(["min", "max"])
    sp = m.groupby("pair").protege.agg(["min", "max"])
    status = pd.DataFrame([{"tie": "any", "switch": int((sw["min"] != sw["max"]).sum()), "always": int(sw["min"].sum()),
                            "never": int((~sw["max"].astype(bool)).sum())},
                           {"tie": "protege", "switch": int((sp["min"] != sp["max"]).sum()), "always": int(sp["min"].sum()),
                            "never": int((~sp["max"].astype(bool)).sum())}])
    return {"within": within, "within_stricter_se": stricter, "event": event, "event_without_ATL_LAA": event_nolaa, "across": across, "tie_status": status}


def report_figure(d: pd.DataFrame, out: Path = Path("reports/figures/2026-front-office-ties.png")) -> Path:
    """Event study around a pair's first protégé season: rate ratio and 95% interval by season from onset,
    all pairs and without the Angels and Braves."""
    import matplotlib.pyplot as plt

    from baseball.viz import GRID, INK, MUTED, OTHER, _style

    accent = "#2a78d6"
    labels = ["3 before", "2 before", "1 before", "1st tied\nseason", "2nd", "3rd", "4th on", "after tie\nended"]
    a = fe_poisson(d, EVENT_TERMS)
    b = fe_poisson(d[d.pair != "ATL-LAA"], EVENT_TERMS)
    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=160)
    _style(ax)
    x = np.arange(len(EVENT_TERMS))
    for off, res, color, name in ((-0.12, a, accent, "All pairs"), (0.12, b, OTHER, "Without the Angels and Braves")):
        ax.vlines(x + off, res.ci_low, res.ci_high, color=color, lw=2)
        ax.scatter(x + off, res.rate_ratio, s=46, color=color, edgecolors="#fcfcfb", linewidths=2, zorder=3, label=name)
    for i, r in a.iterrows():
        ax.text(x[i] - 0.12, r.ci_high + 0.05, f"{r.rate_ratio:.2f}", ha="center", fontsize=8, color=INK)
    ax.axhline(1, color=MUTED, lw=1, ls=(0, (3, 3)))
    ax.axvline(2.5, color=GRID, lw=1.5)
    ax.text(2.55, 2.55, "protégé tie begins →", fontsize=8.5, color=MUTED)
    ax.set_xticks(x, labels, fontsize=8.5, color=INK)
    ax.set_ylim(0.4, 2.7)
    ax.set_ylabel("Trades vs the pair's own baseline (rate ratio)", color=MUTED, fontsize=9)
    ax.legend(loc="upper left", frameon=False, fontsize=8.5, labelcolor=INK)
    ax.set_title("No detected rise before a protégé tie forms; trading runs higher, noisily, once it does", loc="left", color=INK,
                 fontsize=12, fontweight="bold", pad=22)
    ax.text(0, 1.02, "Poisson model with pair and club-season effects, 432 pairs, 2009–2026. 95% intervals clustered by pair.",
            transform=ax.transAxes, color=MUTED, fontsize=8.5)
    fig.text(0.01, 0.005, "Sources: MLB Stats API transactions; sourced career histories of 115 decision-makers. "
             "Code: baseball/roster/front_office.py.", fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out
