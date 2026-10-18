"""The prediction log: dated, probabilistic calls, scored after they resolve.

A log is a YAML file (predictions/<season>.yaml) with a header (made, by) and a list of calls. One call
is one claim that will be true or false on a public source by a stated date:

  id           short unique slug, e.g. "morejon-aav-18m"
  category     "free-agent contract" | "performance" | "draft outcome"
  claim        one sentence, precise enough that a stranger could resolve it
  probability  the chance the claim comes true, 0.05-0.95 in steps of 0.05
  basis        why that number: which analysis or public fact drives it ("judgment" where it is one)
  resolves_by  ISO date by which the outcome is known
  resolution   the exact rule and the public source that settles it
  outcome      null while open; true or false once resolved; "void" if the resolution rule voids it

Scoring is the Brier score: the mean of (probability - outcome)^2 over resolved calls (true = 1,
false = 0). Lower is better. Always saying 0.5 scores exactly 0.25, so 0.25 is the no-skill line, and
the skill score is 1 - Brier / 0.25. Void and open calls are left out of every score.

The wOBA performance calls use a next-season line: next wOBA on the last two seasons' wOBA and xwOBA,
each weighted 5/4 (most recent first) by plate appearances (`weighted_rate()`), fit by `fit_next_season()`.
The fitted values used for the log are in `NEXT_SEASON_WOBA`. Rate calls with no line of their own (walk
rate) use `regressed_rate()`: a 5/4/3 weighted rate pulled toward the league at the stat's stabilization
point; `abreu_walk_rate()` is the worked case. `prob_beyond()` turns a projection and its spread into the
chance of a threshold.

The header can carry `n_calls`; `check_file()` validates a log against it, so a new season's log needs no
code change.

The report's calls section is rebuilt from the YAML with `update_report()`, which replaces the text
between the two marker comments and leaves the hand-written parts alone.
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

CATEGORIES = ("free-agent contract", "performance", "draft outcome")
REQUIRED = ("id", "category", "claim", "probability", "basis", "resolves_by", "resolution", "outcome")
OUTCOMES = (None, True, False, "void")
N_CALLS = None                  # no fixed count; a log states its own in the header (n_calls)
P_MIN, P_MAX, P_STEP = 0.05, 0.95, 0.05
NO_SKILL = 0.25                 # Brier score of always saying 0.5, whatever happens
MARK_START = "<!-- calls:start -->"
MARK_END = "<!-- calls:end -->"

# Next-season wOBA lines behind the wOBA performance calls, fit with fit_next_season() on the repo's Statcast
# pulls (regular seasons). Inputs: 2024 and 2025 wOBA and xwOBA weighted 5/4 by PA (2025 = 5); target: 2026
# wOBA. Savant wOBA and xwOBA per PA (woba_denom; batters faced for pitchers). Three seasons of data give one
# target season, so the slopes are uncertain one by one (bootstrap sd about .14 for hitters) though their sum
# is stable. Leave-one-out error: .0264 for hitters (the one-season line on the same players: .0264; "same
# wOBA as last year": .0334) and .0294 for pitchers (.0299; .0358).
NEXT_SEASON_WOBA = {
    "hitter": {"intercept": 0.17716, "b_woba": 0.22213, "b_xwoba": 0.24521, "sd": 0.02620, "n": 194,
               "weights": (5, 4), "sample": "hitters with 300+ PA in the input season and the next"},
    "pitcher": {"intercept": 0.10030, "b_woba": 0.06535, "b_xwoba": 0.64772, "sd": 0.02892, "n": 84,
                "weights": (5, 4), "sample": "pitchers with 400+ batters faced in the input season and the next"},
}
SEASON_WEIGHTS = (5, 4, 3)      # most recent season first (Marcel)
# Unintentional walks per batter faced in relief, 2026 regular season (Statcast: relief = not the first
# pitcher of the half-inning side in that game). Walk rate stabilizes at about 170 batters faced.
RELIEF_UBB_2026 = 0.091
BB_STABILIZE = 170
# Bryan Abreu, regular-season Statcast: unintentional walks and batters faced (PA-ending events), most recent
# first. He had no intentional walks in 2024-26, so FanGraphs BB% (which counts them) matches.
ABREU_BB = {2026: (41, 268), 2025: (31, 296), 2024: (32, 325)}
WRC_PER_WOBA_POINT = 0.001 / (1.238 * 0.118) * 100


# ---------------------------------------------------------------- loading and validation

def load(path) -> list[dict]:
    """The calls in a log file. Accepts a mapping with a 'calls' list (the log format) or a bare list."""
    import yaml

    with open(path) as f:
        d = yaml.safe_load(f)
    calls = d.get("calls", []) if isinstance(d, dict) else d
    return list(calls or [])


def load_header(path) -> dict:
    """The log's header fields (everything except the calls)."""
    import yaml

    with open(path) as f:
        d = yaml.safe_load(f)
    return {k: v for k, v in (d or {}).items() if k != "calls"} if isinstance(d, dict) else {}


def _iso(v) -> date | None:
    """A date from a YAML date or an ISO string (YYYY-MM-DD); None if it is neither."""
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.strip()):
        try:
            return date.fromisoformat(v.strip())
        except ValueError:
            return None
    return None


def _on_grid(p: float) -> bool:
    k = p / P_STEP
    return abs(k - round(k)) < 1e-9


def validate(calls, n: int | None = N_CALLS) -> list[str]:
    """Every problem with a list of calls, as sentences. Empty list = valid. n=None skips the count check."""
    err = []
    if not isinstance(calls, list):
        return ["log: calls must be a list"]
    if n is not None and len(calls) != n:
        err.append(f"log: {len(calls)} calls; this log has exactly {n}")
    seen = set()
    for i, c in enumerate(calls, 1):
        if not isinstance(c, dict):
            err.append(f"call {i}: not a mapping")
            continue
        w = f"call {i} ({c.get('id', 'no id')})"
        err += [f"{w}: missing '{k}'" for k in REQUIRED if k not in c]
        err += [f"{w}: '{k}' is empty" for k in REQUIRED
                if k != "outcome" and k in c and (c[k] is None or str(c[k]).strip() == "")]
        cid = c.get("id")
        if cid:
            if cid in seen:
                err.append(f"{w}: duplicate id")
            seen.add(cid)
        if "category" in c and c["category"] not in CATEGORIES:
            err.append(f"{w}: category '{c['category']}' is not one of {', '.join(CATEGORIES)}")
        if "probability" in c:
            p = c["probability"]
            if isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p):
                err.append(f"{w}: probability must be a number")
            elif not P_MIN - 1e-9 <= p <= P_MAX + 1e-9:
                err.append(f"{w}: probability {p} is outside {P_MIN}-{P_MAX}")
            elif not _on_grid(p):
                err.append(f"{w}: probability {p} is not a step of {P_STEP}")
        if "resolves_by" in c and c["resolves_by"] not in (None, "") and _iso(c["resolves_by"]) is None:
            err.append(f"{w}: resolves_by '{c['resolves_by']}' is not an ISO date (YYYY-MM-DD)")
        if "outcome" in c and c["outcome"] not in OUTCOMES:
            err.append(f"{w}: outcome must be null, true, false or \"void\"")
    return err


def check(calls, n: int | None = N_CALLS) -> list[dict]:
    """validate() that raises with every problem listed; returns the calls when they're valid."""
    err = validate(calls, n)
    if err:
        raise ValueError("invalid prediction log:\n  " + "\n  ".join(err))
    return calls


def check_file(path) -> list[dict]:
    """Load and check a log file, using the header's n_calls (if any) as the expected count."""
    n = load_header(path).get("n_calls")
    return check(load(path), int(n) if n is not None else None)


# ---------------------------------------------------------------- scoring

def resolved(calls) -> list[dict]:
    """Calls with a true or false outcome (open and void calls are left out)."""
    return [c for c in calls if c.get("outcome") is True or c.get("outcome") is False]


def brier(calls) -> float:
    """Mean of (probability - outcome)^2 over resolved calls; nan when none has resolved."""
    r = resolved(calls)
    if not r:
        return math.nan
    return float(np.mean([(float(c["probability"]) - (1.0 if c["outcome"] else 0.0)) ** 2 for c in r]))


def skill(calls) -> float:
    """Brier skill score against always saying 0.5: 1 - Brier / 0.25. Above 0 beats a coin."""
    b = brier(calls)
    return 1 - b / NO_SKILL if math.isfinite(b) else math.nan


def calibration(calls, bins=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0)) -> pd.DataFrame:
    """Resolved calls grouped by stated probability: how often each group came true.

    bins: bin edges (left-open, right-closed; the first bin includes its left edge), or an int for that many
    equal-width bins on 0-1. Returns one row per bin: n, mean stated probability, share true, and a 95% Wilson
    interval on the share. Empty bins are kept with n = 0 so the table always has the same rows.
    """
    from baseball.stats import wilson

    edges = list(np.linspace(0, 1, int(bins) + 1)) if isinstance(bins, int) else list(bins)
    r = resolved(calls)
    p = np.array([float(c["probability"]) for c in r])
    y = np.array([1.0 if c["outcome"] else 0.0 for c in r])
    rows = []
    for k, (lo, hi) in enumerate(zip(edges[:-1], edges[1:])):
        m = ((p > lo) | ((p == lo) & (k == 0))) & (p <= hi) if len(p) else np.array([], bool)
        n = int(m.sum())
        hits = int(y[m].sum()) if n else 0
        ci = wilson(hits, n) if n else (math.nan, math.nan)
        rows.append({"bin": f"{lo:.2f}-{hi:.2f}", "n": n,
                     "mean_probability": float(p[m].mean()) if n else math.nan,
                     "share_true": hits / n if n else math.nan, "lo": ci[0], "hi": ci[1]})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- the numbers behind the performance calls

def weighted_inputs(seasons: pd.DataFrame, id_col: str, last: int, weights=(5, 4)) -> pd.DataFrame:
    """Each player's wOBA and xwOBA over the seasons up to `last`, weighted by season and by PA.

    seasons: one row per player and season with columns season, n (PA or batters faced), w and xw (the wOBA and
    xwOBA numerators, i.e. rate times n). Weights run most recent first; a season the player missed counts zero.
    Returns one row per player with a row in `last`: n (that season's), woba and xwoba (weighted).
    """
    d = seasons[seasons["season"].between(last - len(weights) + 1, last)].copy()
    d["wt"] = d["season"].map({last - i: float(w) for i, w in enumerate(weights)})
    d["wn"], d["ww"], d["wx"] = d["wt"] * d["n"], d["wt"] * d["w"], d["wt"] * d["xw"]
    g = d.groupby(id_col)[["wn", "ww", "wx"]].sum()
    cur = d[d["season"] == last].set_index(id_col)["n"]
    g = g.loc[g.index.intersection(cur.index)]
    return pd.DataFrame({"n": cur.loc[g.index], "woba": g["ww"] / g["wn"], "xwoba": g["wx"] / g["wn"]})


def fit_next_season(df: pd.DataFrame) -> dict:
    """OLS of next season's wOBA on the input wOBA and xwOBA (one season's, or weighted_inputs()).

    df: one row per player and input window, with columns woba, xwoba and woba_next.
    Returns intercept, b_woba, b_xwoba, the residual sd (the spread of a next-season value around its
    projection) and n.
    """
    d = df[["woba", "xwoba", "woba_next"]].dropna()
    X = np.c_[np.ones(len(d)), d["woba"].to_numpy(float), d["xwoba"].to_numpy(float)]
    y = d["woba_next"].to_numpy(float)
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ b
    sd = float(np.sqrt(resid @ resid / max(len(d) - 3, 1)))
    return {"intercept": float(b[0]), "b_woba": float(b[1]), "b_xwoba": float(b[2]), "sd": sd, "n": int(len(d))}


def project_woba(woba: float, xwoba: float, line: dict) -> float:
    """Next season's wOBA from the input wOBA and xwOBA (weighted as the line was fit) on a fitted line."""
    return line["intercept"] + line["b_woba"] * woba + line["b_xwoba"] * xwoba


def weighted_rate(events, chances, weights=SEASON_WEIGHTS) -> tuple[float, float]:
    """A multi-season rate, most recent season first: (sum w*events / sum w*chances, effective chances).

    events, chances: per-season totals, most recent first (wOBA points and PA work too). weights are scaled so
    the most recent season counts 1, so effective chances = sum (w / w[0]) * chances: older seasons count as
    fewer chances because they say less about next year.
    """
    k = min(len(events), len(chances), len(weights))
    if k == 0:
        raise ValueError("need at least one season")
    w = np.asarray(weights[:k], float) / float(weights[0])
    e, n = np.asarray(events[:k], float), np.asarray(chances[:k], float)
    eff = float(w @ n)
    if eff <= 0:
        raise ValueError("no chances to weight")
    return float(w @ e) / eff, eff


def regressed_rate(events, chances, league: float, stabilize: float, weights=SEASON_WEIGHTS) -> tuple[float, float]:
    """weighted_rate() pulled toward the league: (events_w + stabilize * league) / (chances_w + stabilize).

    Returns the projection and the effective chances behind it (chances_w + stabilize), so a caller can put
    an uncertainty on the true rate: sd = sqrt(p (1 - p) / effective).
    """
    r, eff = weighted_rate(events, chances, weights)
    total = eff + stabilize
    return (r * eff + league * stabilize) / total, total


def rate_spread(p: float, effective: float, next_chances: float) -> float:
    """The sd of next season's observed rate: the true-rate uncertainty plus binomial noise over next_chances."""
    return math.sqrt(p * (1 - p) / effective + p * (1 - p) / next_chances)


def abreu_walk_rate(next_bf: float = 260, threshold: float = 0.110) -> dict:
    """The projection behind the Abreu walk-rate call, from ABREU_BB, RELIEF_UBB_2026 and BB_STABILIZE."""
    seasons = sorted(ABREU_BB, reverse=True)
    bb = [ABREU_BB[y][0] for y in seasons]
    bf = [ABREU_BB[y][1] for y in seasons]
    p, eff = regressed_rate(bb, bf, RELIEF_UBB_2026, BB_STABILIZE)
    sd = rate_spread(p, eff, next_bf)
    prob = prob_beyond(p, sd, threshold, above=False)
    return {"seasons": seasons, "rates": [b / n for b, n in zip(bb, bf)], "projection": p, "effective_bf": eff,
            "sd": sd, "p_at_or_below": prob, "probability": to_grid(prob)}


def prob_beyond(mean: float, sd: float, threshold: float, above: bool = True) -> float:
    """Chance a normal(mean, sd) outcome lands at or above (above=True) or at or below the threshold."""
    q = NormalDist(mean, sd).cdf(threshold)
    return 1 - q if above else q


def to_grid(p: float) -> float:
    """A probability rounded to the log's 0.05 grid and clipped to 0.05-0.95."""
    return float(min(P_MAX, max(P_MIN, round(round(p / P_STEP) * P_STEP, 2))))


# ---------------------------------------------------------------- rendering

def _outcome_word(o) -> str:
    return {None: "open", True: "yes", False: "no", "void": "void"}.get(o, str(o))


def _cell(s) -> str:
    return " ".join(str(s).split()).replace("|", "\\|")


def _fmt(x, nd=3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def render_markdown(calls) -> str:
    """The calls section of the report: the score so far, the table of calls, and each call's basis and rule."""
    r = resolved(calls)
    n_open = sum(1 for c in calls if c.get("outcome") is None)
    n_void = sum(1 for c in calls if c.get("outcome") == "void")
    out = ["## Score", ""]
    if r:
        out += [f"- **Brier score:** {_fmt(brier(calls))} on {len(r)} resolved calls "
                f"(no-skill line {NO_SKILL:.2f}; lower is better).",
                f"- **Skill score:** {_fmt(skill(calls), 2)} (1 − Brier / 0.25; above 0 beats always saying 0.5).",
                f"- **Still open:** {n_open}. **Void:** {n_void}.", ""]
        cal = calibration(calls)
        cal = cal[cal["n"] > 0]
        out += ["| Stated probability | Calls | Average stated | Came true |", "|---|---|---|---|"]
        out += [f"| {row.bin} | {row.n} | {row.mean_probability:.2f} | {row.share_true:.2f} "
                f"(95% {row.lo:.2f}-{row.hi:.2f}) |" for row in cal.itertuples()]
        out.append("")
    else:
        out += [f"- **No call has resolved yet.** {n_open} open, {n_void} void. "
                f"The first contract calls can resolve once free agency opens after the World Series.", ""]

    out += ["## The calls", "",
            "| # | Category | Claim | Probability | Resolves by | Outcome |", "|---|---|---|---|---|---|"]
    for i, c in enumerate(calls, 1):
        out.append(f"| {i} | {_cell(c['category'])} | {_cell(c['claim'])} | {float(c['probability']):.2f} | "
                   f"{_iso(c['resolves_by'])} | {_outcome_word(c.get('outcome'))} |")
    out.append("")

    for cat in CATEGORIES:
        group = [(i, c) for i, c in enumerate(calls, 1) if c["category"] == cat]
        if not group:
            continue
        out += [f"### {cat[0].upper() + cat[1:]} calls", ""]
        for i, c in group:
            out.append(f"**{i}. {_cell(c['claim'])}** ({float(c['probability']):.2f}; `{c['id']}`)")
            out.append(f"- **Basis:** {_cell(c['basis'])}")
            out.append(f"- **Resolves by:** {_iso(c['resolves_by'])}. {_cell(c['resolution'])}")
            if c.get("outcome") is not None:
                note = f" {_cell(c['note'])}" if c.get("note") else ""
                out.append(f"- **Outcome:** {_outcome_word(c['outcome'])}.{note}")
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def update_report(report_path, calls) -> str:
    """Rewrite the calls section of a report (between the marker comments) from the calls; returns the text."""
    path = Path(report_path)
    text = path.read_text()
    if MARK_START not in text or MARK_END not in text:
        raise ValueError(f"{path}: no {MARK_START} ... {MARK_END} block to replace")
    head, rest = text.split(MARK_START, 1)
    _, tail = rest.split(MARK_END, 1)
    new = f"{head}{MARK_START}\n{render_markdown(calls)}{MARK_END}{tail}"
    path.write_text(new)
    return new
