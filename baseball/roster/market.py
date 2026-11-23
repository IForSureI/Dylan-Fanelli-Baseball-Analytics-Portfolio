"""The 2026-27 market board: my free-agent contract calls, dated, next to MLB Trade Rumors' published
predictions, scored as the players sign.

Why a head-to-head: a contract call is only worth something next to a benchmark. MLB Trade Rumors' annual
top-50 list is the public one: every winter it predicts years and money for the top 50 free agents, and it
later writes each signing into the same page. That gives a dated benchmark and a public answer key, so my
calls can be scored against theirs on the same players.

What is scored (per player, once he signs):
- AAV: my point call vs MLBTR's (guaranteed money / guaranteed years; an accepted qualifying offer is one
  year at the offer). The board's headline is mean absolute error, mine vs theirs, on the same players.
- Over/under: my probability that he signs above MLBTR's AAV, in steps of 0.05, scored with the Brier
  score (0.25 = a coin flip).

The model, fit on the 2025-26 class (the one past winter whose actual deals MLBTR records on its list page):
  log(AAV) = b0 + b1 * weighted WAR + b2 * platform WAR + b3 * reliever + b4 * (age - 30) + b5 * log(MLBTR AAV)
Weighted WAR is Baseball-Reference WAR over the last three seasons, weighted 5/4/3 (most recent first) and
clipped to [-1, 8]; platform WAR is the last season's; age is the age Baseball-Reference lists for the
platform season. It is a blend: it starts from MLBTR's number and moves it on the record. Players with no
MLB record (NPB and KBO signings) get no call from me.

Backtest (leave one out on the 44 signed 2025-26 players with an MLB record): AAV error $3.24M for the blend
vs $3.79M for MLBTR, a $0.55M edge whose 95% bootstrap range (-$0.66M to +$2.05M) includes zero; the blend
was closer on 21 of 44. Over/under Brier 0.218 vs 0.25 for a coin flip and 0.231 for always saying the base
rate. A small edge on one winter: this board is the real test.

Sources: MLB Trade Rumors, "2025-26 Top 50 MLB Free Agents With Predictions" (Nov. 6, 2025) and
"2026-27 Top 50 Free Agents With Predictions" (Nov. 2, 2026), signings as recorded on those pages;
Baseball-Reference WAR files (war_daily_bat.txt, war_daily_pitch.txt). Pull dates are in the data files.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import date
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MARKET = ROOT / "market"
RAW = ROOT / "data" / "raw" / "market"
LISTS = {
    2025: "https://www.mlbtraderumors.com/2025/11/2025-26-top-50-mlb-free-agents-with-predictions.html",
    2026: "https://www.mlbtraderumors.com/2026/11/2026-27-top-50-free-agents-with-predictions.html",
}
WAR_FILES = {"bat": "https://www.baseball-reference.com/data/war_daily_bat.txt",
             "pitch": "https://www.baseball-reference.com/data/war_daily_pitch.txt"}
WEIGHTS = (5, 4, 3)
WAR_CLIP = (-1.0, 8.0)
FEATURES = ("const", "wwar", "war0", "reliever", "age30", "log_mlbtr")
QO_2026 = 23.15          # the 2026-27 qualifying offer, $M (MLB.com, Nov. 2026)
QO_2025 = 22.025         # the 2025-26 qualifying offer, $M (MLB.com glossary)
# Names Baseball-Reference spells differently, or shares with another player.
MANUAL_IDS = {"Trevor Rogers": "rogertr01", "Matthew Boyd": "boydma01", "Nick Martinez": "martini01",
              "Carson Kelly": "kellyca02", "Edwin Diaz": "diazed04", "Devin Williams": "willide03"}
NUMBER_WORDS = dict(one=1, two=2, three=3, four=4, five=5, six=6, seven=7, eight=8, nine=9, ten=10,
                    eleven=11, twelve=12, thirteen=13, fourteen=14, fifteen=15)


# ------------------------------------------------------------------ parsing
def terms(text: str) -> tuple[int | None, float | None]:
    """'Nine years, $425MM' -> (9, 425.0); 'One year $23.15MM' -> (1, 23.15)."""
    m = re.search(r"(\w+)[\s-]+years?,?\s*\$([\d.]+)\s*MM", text or "", re.I)
    if not m:
        return None, None
    word = m.group(1).lower()
    years = NUMBER_WORDS.get(word) or (int(word) if word.isdigit() else None)
    return years, float(m.group(2))


MLB_CLUBS = ("Angels", "Astros", "Athletics", "A's", "Blue Jays", "Braves", "Brewers", "Cardinals", "Cubs", "Diamondbacks",
             "D-backs", "Dodgers", "Giants", "Guardians", "Mariners", "Marlins", "Mets", "Nationals", "Orioles", "Padres",
             "Phillies", "Pirates", "Rangers", "Rays", "Red Sox", "Reds", "Rockies", "Royals", "Tigers", "Twins",
             "White Sox", "Yankees")
SCORE_BY = "2027-04-30"     # a signing line first seen after this date isn't scored (a lockout included)


_CLUB_RX = re.compile(r"(?:with|from) (?:the )?(" + "|".join(re.escape(c) for c in sorted(MLB_CLUBS, key=len, reverse=True)) + r")\b(?! of)", re.I)
FOREIGN = ("yomiuri", "hanshin", "chunichi", "yakult", "hiroshima", "yokohama", "orix", "softbank", "rakuten", "seibu",
           "nippon-ham", "nippon ham", "lotte", "kia", "lg ", "lg twins", "doosan", "samsung", "kiwoom", "hanwha", "kt wiz",
           "ssg", "nc dinos", "npb", "kbo", "cpbl", "mexican league", "japan", "korea", "taiwan")


def mlb_deal(text: str) -> bool:
    """A major league contract with an MLB club, or an accepted qualifying offer. Minor-league deals, clubs outside
    MLB (including NPB and KBO clubs that share an MLB nickname, like the Yomiuri Giants or Hanshin Tigers) and
    retirements aren't scored. The club must follow "with" or "from", as in MLBTR's signing lines."""
    t = (text or "").lower()
    if not t or "minor league" in t or "minor-league" in t or "retire" in t or any(f in t for f in FOREIGN):
        return False
    return bool(_CLUB_RX.search(text))


def signed_club(text: str) -> str | None:
    """The MLB club a signing line names ('Signed with Mets for ...' -> 'Mets'), or None when the line isn't a
    major league deal with an MLB club."""
    if not mlb_deal(text):
        return None
    m = _CLUB_RX.search(text)
    hit = m.group(1).lower()
    return next(c for c in MLB_CLUBS if c.lower() == hit)


# Status notes on a signing line that MLBTR's one-line entry doesn't carry, each with its source.
SIGNING_NOTES = {
    "Tarik Skubal": "agreed Nov. 22; official after physical",   # MLBTR, Nov. 22, 2026; MLB.com: pending a physical
}


def unparsed(players: list[dict]) -> list[str]:
    """Signing lines that name an MLB club but whose years or money can't be read. They would drop out of the
    score silently, so `bb market score` lists them for a hand check."""
    return [p["name"] for p in players if p.get("signed") and mlb_deal(p["signed"]) and None in actual_terms(p["signed"], QO_2026)]


def actual_terms(text: str, qo: float) -> tuple[int | None, float | None]:
    """The signing line MLBTR adds under a player: 'Signed with Mets for nine years, $450MM' or
    'Accepted $23.15MM qualifying offer from Twins'. Years and money are MLBTR's stated guarantee at face value
    (deferrals included); a line that names a player option counts its year, as MLBTR states the years. Anything
    that isn't a major league deal with an MLB club returns nothing."""
    if not text or not mlb_deal(text):
        return None, None
    if text.lower().startswith("accepted"):
        m = re.search(r"\$([\d.]+)", text)
        return 1, float(m.group(1)) if m else qo
    return terms(text)


def parse_list(page: str, season: int) -> list[dict]:
    """The 50 entries of an MLBTR top-50 page: rank, name, position, MLBTR's call, the signing line if any,
    and the Baseball-Reference id where the entry links one."""
    published = re.search(r'<time[^>]*datetime="([^"]+)"', page).group(1)[:10]
    links = {int(m.group(1)): m.group(2) for m in re.finditer(
        r'<strong>\s*(\d{1,2})\.\s*(?:<strong>)?\s*<a[^>]*href="https://www.baseball-reference.com/players/\w/(\w+)\.shtml', page)}
    body = page[page.find('<div class="entry-content">'):]
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", body, flags=re.S)
    text = re.sub(r"[ \t\xa0]+", " ", _unescape(re.sub(r"<[^>]+>", "\n", body)))
    text = re.sub(r"\n\s*\n+", "\n", text)
    rows, seen = [], set()
    for m in re.finditer(r"\n\s*(\d{1,2})\.\s*\n([^\n]{2,60})\n\s*[,:]\s*([^\n:]{1,20}):\s*([^\n]{3,90})\n(?=((?:[^\n]*\n){0,4}))", text):
        rank = int(m.group(1))
        if rank > 50 or rank in seen:
            continue
        seen.add(rank)
        signed = re.search(r"(?im)^\s*((?:Signed|Re-signed|Accepted|Agreed)[^\n]*)", m.group(5))
        rows.append(dict(rank=rank, name=m.group(2).strip(), pos=m.group(3).strip(), mlbtr=m.group(4).strip(),
                         signed=signed.group(1).strip() if signed else "", bref_id=links.get(rank)))
    if len(rows) != 50:
        raise ValueError(f"{season}: parsed {len(rows)} entries, expected 50")
    return [dict(r, season=season, published=published) for r in sorted(rows, key=lambda r: r["rank"])]


def _unescape(s: str) -> str:
    import html
    return html.unescape(s)


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", "", s).strip()


# ------------------------------------------------------------------ features
def war_tables(raw: Path = RAW) -> tuple[pd.DataFrame, pd.DataFrame]:
    bat = pd.read_csv(raw / "war_daily_bat.txt", na_values="NULL", low_memory=False)
    pit = pd.read_csv(raw / "war_daily_pitch.txt", na_values="NULL", low_memory=False)
    bat["nm"], pit["nm"] = bat.name_common.map(_norm), pit.name_common.map(_norm)
    return bat, pit


def player_features(name: str, bref_id: str | None, season: int, bat: pd.DataFrame, pit: pd.DataFrame) -> dict:
    """WAR in the platform season and the two before (batting + pitching, a pitcher's own batting rows
    left out), age in the platform season, and whether he pitched mostly in relief."""
    pid = bref_id or MANUAL_IDS.get(name)
    if not pid:
        ids = set(bat[(bat.nm == _norm(name)) & (bat.year_ID >= season - 2)].player_ID) | \
              set(pit[(pit.nm == _norm(name)) & (pit.year_ID >= season - 2)].player_ID)
        pid = ids.pop() if len(ids) == 1 else None
    if not pid:
        return dict(bref_id=None)
    b = bat[(bat.player_ID == pid) & bat.year_ID.between(season - 2, season)]
    p = pit[(pit.player_ID == pid) & pit.year_ID.between(season - 2, season)]
    if b.empty and p.empty:
        return dict(bref_id=None)
    wars, ip, pa, gs, g = [], 0.0, 0.0, 0.0, 0.0
    for yr in (season, season - 1, season - 2):
        wb, wp = b[b.year_ID == yr], p[p.year_ID == yr]
        hitting = wb[wb.pitcher != "Y"].WAR.sum() if len(wp) else wb.WAR.sum()
        wars.append(round(float(hitting + wp.WAR.sum()), 2))
        ip += wp.IPouts.sum() / 3
        pa += wb[wb.pitcher != "Y"].PA.sum() if len(wp) else wb.PA.sum()
        gs += wp.GS.sum()
        g += wp.G.sum()
    last = b if not b.empty else p
    age = float(last.age.iloc[-1] - last.year_ID.iloc[-1] + season)
    reliever = bool(ip > 30 and ip * 3 > pa and g > 0 and gs / g < 0.4)
    return dict(bref_id=pid, age=age, war=wars, reliever=reliever)


def weighted_war(wars: list[float], weights=WEIGHTS) -> float:
    return sum(w * x for w, x in zip(weights, wars)) / sum(weights)


# ------------------------------------------------------------------ data files
def load(season: int, root: Path = MARKET) -> dict:
    return json.loads((root / f"mlbtr_{season}-{(season + 1) % 100:02d}.json").read_text())


def frame(data: dict) -> pd.DataFrame:
    """One row per player with MLBTR's call, the actual deal (if signed) and the model's features."""
    qo = QO_2026 if data["season"] == 2026 else QO_2025
    rows = []
    for r in data["players"]:
        py, pt = terms(r["mlbtr"])
        ay, at = actual_terms(r.get("signed", ""), qo)
        war = r.get("war") or [None, None, None]
        rows.append(dict(season=data["season"], rank=r["rank"], name=r["name"], pos=r["pos"], mlbtr=r["mlbtr"],
                         signed=r.get("signed", ""), mlbtr_years=py, mlbtr_total=pt,
                         mlbtr_aav=pt / py if py else None, actual_years=ay, actual_total=at,
                         actual_aav=at / ay if ay else None, bref_id=r.get("bref_id"), age=r.get("age"),
                         war0=war[0], wwar=weighted_war(war) if None not in war else None,
                         reliever=r.get("reliever")))
    return pd.DataFrame(rows)


def design(d: pd.DataFrame) -> np.ndarray:
    return np.column_stack([np.ones(len(d)), d.wwar.astype(float).clip(*WAR_CLIP), d.war0.astype(float),
                            d.reliever.astype(float), d.age.astype(float) - 30,
                            np.log(d.mlbtr_aav.astype(float))])


def modelable(d: pd.DataFrame) -> pd.Series:
    return d.bref_id.notna() & d.age.notna() & d.wwar.notna() & d.mlbtr_aav.notna()


# ------------------------------------------------------------------ fit and backtest
def fit(train: pd.DataFrame) -> np.ndarray:
    t = train[modelable(train) & train.actual_aav.notna()]
    coef, *_ = np.linalg.lstsq(design(t), np.log(t.actual_aav.astype(float)), rcond=None)
    return coef


def backtest(train: pd.DataFrame, n_boot: int = 10000, seed: int = 7) -> dict:
    """Leave-one-out on the signed, modelable players: AAV error vs MLBTR, the bootstrap range of the
    edge, the blend's log spread (for the over/under probabilities) and the over/under Brier score."""
    t = train[modelable(train) & train.actual_aav.notna()].reset_index(drop=True)
    X, y = design(t), np.log(t.actual_aav.astype(float).to_numpy())
    loo = np.empty(len(t))
    for i in range(len(t)):
        keep = np.arange(len(t)) != i
        c, *_ = np.linalg.lstsq(X[keep], y[keep], rcond=None)
        loo[i] = X[i] @ c
    mine = np.exp(loo)
    err_mine = np.abs(mine - t.actual_aav)
    err_mlbtr = np.abs(t.mlbtr_aav - t.actual_aav)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(t), (n_boot, len(t)))
    edge = err_mlbtr.to_numpy()[idx].mean(1) - err_mine.to_numpy()[idx].mean(1)
    sigma = float(np.std(loo - y, ddof=1))
    p = np.array([over_probability(m, b, sigma) for m, b in zip(mine, t.mlbtr_aav)])
    over = (t.actual_aav > t.mlbtr_aav + 1e-9).astype(float).to_numpy()
    return dict(n=len(t), mae_mine=float(err_mine.mean()), mae_mlbtr=float(err_mlbtr.mean()),
                edge=float(err_mlbtr.mean() - err_mine.mean()), edge_lo=float(np.percentile(edge, 2.5)),
                edge_hi=float(np.percentile(edge, 97.5)), closer=int((err_mine < err_mlbtr).sum()),
                sigma=sigma, brier=float(((p - over) ** 2).mean()), base_rate=float(over.mean()),
                brier_base=float(((over.mean() - over) ** 2).mean()),
                mlbtr_bias=float((t.mlbtr_aav - t.actual_aav).mean()),
                years_bias=float((t.mlbtr_years - t.actual_years).mean()),
                total_bias=float((t.mlbtr_total - t.actual_total).mean()))


def over_probability(mine: float, mlbtr: float, sigma: float) -> float:
    """P(actual AAV > MLBTR's), with log(actual) ~ Normal(log(mine), sigma), on the 0.05 grid."""
    p = NormalDist().cdf((math.log(mine) - math.log(mlbtr)) / sigma)
    return min(0.95, max(0.05, round(p * 20) / 20))


# ------------------------------------------------------------------ the board
def board(current: pd.DataFrame, coef: np.ndarray, sigma: float, as_of: str) -> pd.DataFrame:
    """My call for every player not signed by `as_of`: AAV, the total at MLBTR's length, and the chance he
    beats MLBTR's AAV. Players signed before the board was made, or with no MLB record, get no call."""
    d = current.copy()
    open_ = d.actual_aav.isna() & ~d.signed.astype(bool)
    ok = modelable(d) & open_
    d["my_aav"] = np.nan
    d.loc[ok, "my_aav"] = np.exp(design(d[ok]) @ coef)
    d["my_total"] = d.my_aav * d.mlbtr_years
    d["p_over"] = [over_probability(m, b, sigma) if m == m else np.nan for m, b in zip(d.my_aav, d.mlbtr_aav)]
    d["call"] = np.where(ok, "called", np.where(~open_, "signed before the board", "no MLB record"))
    d["as_of"] = as_of
    return d


def score(called: pd.DataFrame, by: str = SCORE_BY) -> dict:
    """Score the calls that have resolved: AAV error mine vs MLBTR's, and the over/under Brier score.

    Rules (set Nov. 23, 2026, before any called player signed): a call resolves on the signing line MLBTR adds to
    its own list (an agreement counts; the club's announcement isn't awaited), for a major league deal with an MLB
    club first seen by `by`. AAV is MLBTR's stated guarantee over its stated years, deferrals at face value. A deal
    at exactly MLBTR's AAV counts as not above it; a tie in distance counts for neither side."""
    s = called[(called.call == "called") & called.actual_aav.notna()]
    if "first_seen" in s:
        s = s[s.first_seen.isna() | (s.first_seen.astype(str) <= by)]
    if s.empty:
        return dict(n=0)
    over = (s.actual_aav > s.mlbtr_aav + 1e-9).astype(float)
    mine, theirs = (s.my_aav - s.actual_aav).abs(), (s.mlbtr_aav - s.actual_aav).abs()
    return dict(n=len(s), mae_mine=float(mine.mean()), mae_mlbtr=float(theirs.mean()),
                closer=int((mine < theirs - 1e-9).sum()), mlbtr_closer=int((theirs < mine - 1e-9).sum()),
                ties=int(((mine - theirs).abs() <= 1e-9).sum()), brier=float(((s.p_over - over) ** 2).mean()))


# ------------------------------------------------------------------ pull (writes market/*.json)
def pull(season: int, raw: Path = RAW, root: Path = MARKET, pulled: str | None = None) -> Path:
    """Download the MLBTR list and the Baseball-Reference WAR files, and write market/mlbtr_<season>.json
    (facts only: names, calls, signing lines, WAR, age, role; never the page text)."""
    import urllib.request
    raw.mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)
    def get(url, name):
        p = raw / name
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            p.write_bytes(r.read())
        return p
    page = get(LISTS[season], f"mlbtr_top50_{season}.html").read_text(encoding="utf-8", errors="ignore")
    for k, url in WAR_FILES.items():
        get(url, f"war_daily_{k}.txt")
    bat, pit = war_tables(raw)
    players = []
    when = pulled or date.today().isoformat()
    prev = root / f"mlbtr_{season}-{(season + 1) % 100:02d}.json"
    seen = {}
    if prev.exists():
        seen = {q["rank"]: (q.get("signed", ""), q.get("first_seen")) for q in json.loads(prev.read_text())["players"]}
    for r in parse_list(page, season):
        f = player_features(r["name"], r["bref_id"], season, bat, pit)
        old_line, old_seen = seen.get(r["rank"], ("", None))
        # the first date any signing line appeared stays, even if MLBTR later edits the line (to add an opt-out, say)
        first = (old_seen or when) if r["signed"] else None
        rec = {**{k: r[k] for k in ("rank", "name", "pos", "mlbtr", "signed")}, **f, "first_seen": first}
        if old_line and r["signed"] and old_line != r["signed"]:
            rec["revised"] = when
        players.append(rec)
    out = root / f"mlbtr_{season}-{(season + 1) % 100:02d}.json"
    out.write_text(json.dumps(dict(season=season, source=LISTS[season], published=parse_list(page, season)[0]["published"],
                                   war_source="Baseball-Reference WAR files (war_daily_bat.txt, war_daily_pitch.txt)",
                                   pulled=pulled or date.today().isoformat(), players=players), indent=1, ensure_ascii=False) + "\n")
    return out


# ------------------------------------------------------------------ frozen calls
def freeze(as_of: str, root: Path = MARKET) -> Path:
    """Write the dated calls (market/calls_2026-27.json). Once written, the calls are never edited: scoring
    reads the latest signing lines from a fresh pull and compares them with these."""
    out = root / "calls_2026-27.json"
    if out.exists():
        raise FileExistsError(f"{out} exists: the calls are frozen on the day they were made")
    train = frame(load(2025))
    bt, coef = backtest(train), fit(train)
    b = board(frame(load(2026)), coef, bt["sigma"], as_of)
    calls = [dict(rank=int(r["rank"]), name=r["name"], mlbtr=r["mlbtr"], mlbtr_aav=round(float(r["mlbtr_aav"]), 3),
                  call=r["call"], my_aav=None if r["my_aav"] != r["my_aav"] else round(float(r["my_aav"]), 1),
                  p_over=None if r["p_over"] != r["p_over"] else float(r["p_over"]))
             for _, r in b.iterrows()]
    out.write_text(json.dumps(dict(made=as_of, by="Dylan Fanelli", model=dict(zip(FEATURES, [round(float(c), 4) for c in coef])),
                                   sigma=round(bt["sigma"], 4), backtest={k: (round(v, 4) if isinstance(v, float) else v) for k, v in bt.items()},
                                   calls=calls), indent=1, ensure_ascii=False) + "\n")
    return out


def load_calls(root: Path = MARKET) -> pd.DataFrame:
    data = json.loads((root / "calls_2026-27.json").read_text())
    return pd.DataFrame(data["calls"]).assign(as_of=data["made"])


def scored(root: Path = MARKET) -> pd.DataFrame:
    """The frozen calls joined to the latest signing lines (market/mlbtr_2026-27.json, re-pulled)."""
    latest = frame(load(2026, root))[["rank", "signed", "actual_years", "actual_total", "actual_aav"]]
    seen = {q["rank"]: q.get("first_seen") for q in load(2026, root)["players"]}
    latest["first_seen"] = latest["rank"].map(seen)
    return load_calls(root).merge(latest, on="rank", how="left")


# ------------------------------------------------------------------ report
MARK_START, MARK_END = "<!-- board:start -->", "<!-- board:end -->"
DISPLAY = {"Adrian Morejon": "Adrián Morejón"}      # MLBTR's list drops the accents


def _money(x) -> str:
    return "" if x is None or x != x else f"${x:,.1f}M"


def _aav(x) -> str:
    """A contract's AAV: one decimal when that is exact, otherwise two, rounded half up ($26.25M, $23.15M,
    $11.67M), so the report and the packet print the same number."""
    if x is None or x != x:
        return ""
    from decimal import Decimal, ROUND_HALF_UP
    d = Decimal(repr(float(x)))
    one = d.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    if abs(float(one) - float(x)) < 1e-9:
        return f"${one:,}M"
    return f"${d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,}M"


def _signed(name: str, line) -> str:
    line = line if isinstance(line, str) else ""
    note = SIGNING_NOTES.get(name)
    return f"{line} ({note})" if line and note else line


def render_board(root: Path = MARKET) -> str:
    """The board section of the report: the score so far, then every call, from the frozen file and the
    latest signing lines."""
    s = scored(root)
    r = score(s)
    feats = frame(load(2026, root)).set_index("rank")
    lines = []
    if r["n"]:
        lines.append(f"**Score so far ({r['n']} of {(s.call == 'called').sum()} signed):** AAV error mine "
                     f"{_money(r['mae_mine'])} vs MLBTR {_money(r['mae_mlbtr'])}; mine closer on {r['closer']}; "
                     f"over/under Brier {r['brier']:.3f} (a coin flip scores 0.250).")
    else:
        lines.append(f"**Score so far:** none of the {(s.call == 'called').sum()} called players has signed.")
    lines += ["", "| # | Player | MLBTR's call (Nov. 2) | MLBTR AAV | My AAV | P(beats MLBTR AAV) | WAR (5/4/3 average), age | Signed | Result |",
              "|---|---|---|---|---|---|---|---|---|"]
    for _, c in s[s.call == "called"].sort_values("rank").iterrows():
        f = feats.loc[c["rank"]]
        res = ""
        if c["actual_aav"] == c["actual_aav"] and c["actual_aav"] is not None:
            mine, theirs = abs(c["my_aav"] - c["actual_aav"]), abs(c["mlbtr_aav"] - c["actual_aav"])
            res = f"{_aav(c['actual_aav'])} AAV; {'mine closer' if mine < theirs else 'MLBTR closer' if theirs < mine else 'tie'}"
        lines.append(f"| {c['rank']} | {DISPLAY.get(c['name'], c['name'])} | {c['mlbtr']} | {_aav(c['mlbtr_aav'])} | {_money(c['my_aav'])} | "
                     f"{c['p_over']:.2f} | {f['wwar']:.1f}{' (RP)' if f['reliever'] else ''}, {int(f['age'])} | "
                     f"{_signed(c['name'], c['signed'])} | {res} |")
    pre = s[s.call != "called"].sort_values("rank")
    lines += ["", "No call from me (signed before Nov. 23, or no MLB record):", ""]
    for _, c in pre.iterrows():
        sig = _signed(c["name"], c["signed"])
        lines.append(f"- {c['rank']}. {DISPLAY.get(c['name'], c['name'])}: {c['call']}{'; ' + sig if sig else ''}.")
    return "\n".join(lines)


def update_report(path, root: Path = MARKET) -> None:
    p = Path(path)
    text = p.read_text()
    a, b = text.index(MARK_START) + len(MARK_START), text.index(MARK_END)
    p.write_text(text[:a] + "\n" + render_board(root) + "\n" + text[b:])


# ------------------------------------------------------------------ robustness (the report's Limits section)
def robustness(train: pd.DataFrame) -> dict:
    """How much of the backtest edge rests on a few players: leave-one-out errors with Kyle Tucker, and with Tucker
    and Bo Bichette, left out of the scoring; median errors; and how many relievers set the reliever term."""
    t = train[modelable(train) & train.actual_aav.notna()].reset_index(drop=True)
    X, y = design(t), np.log(t.actual_aav.astype(float).to_numpy())
    loo = np.empty(len(t))
    for i in range(len(t)):
        keep = np.arange(len(t)) != i
        loo[i] = X[i] @ np.linalg.lstsq(X[keep], y[keep], rcond=None)[0]
    e_mine, e_mlbtr = np.abs(np.exp(loo) - t.actual_aav), np.abs(t.mlbtr_aav - t.actual_aav)
    out = dict(median_mine=float(np.median(e_mine)), median_mlbtr=float(np.median(e_mlbtr)),
               relievers=int(t.reliever.astype(bool).sum()), top_wwar=t.nlargest(3, "wwar")[["name", "wwar"]].values.tolist())
    for label, drop in (("without_tucker", ["Kyle Tucker"]), ("without_tucker_bichette", ["Kyle Tucker", "Bo Bichette"])):
        k = ~t.name.isin(drop)
        out[label] = dict(n=int(k.sum()), mae_mine=float(e_mine[k].mean()), mae_mlbtr=float(e_mlbtr[k].mean()))
    return out


def p_above(my_aav: float, threshold: float, sigma: float) -> float:
    """The board model's chance a player's AAV lands above a dollar threshold (log-normal around my call)."""
    return float(1 - NormalDist().cdf((math.log(threshold) - math.log(my_aav)) / sigma))
