"""20-80 scouting grades from measurements: fastball velocity and the pitcher OFP roll-up.

Two velocity readings are reported, because the traditional anchors and today's league disagree:

* **vs. 2026 MLB starters** (the house reading): grade = 50 + 10 z, where z is the pitch's sitting velocity
  against 2026 starters' four-seam velocity (mean 94.5 mph, SD 2.15; pitchers with 2,200+ pitches,
  Baseball Savant leaderboard pulled 2026-09-30). Ten grade points is one standard deviation.
* **Traditional anchors** (shown for contrast): 80 = 98+, 70 = 97, 60 = 95, 50 = 93, 40 = 90.5, after the
  scale Baseball America publishes; 20 and 30 extrapolated. Left-handers are credited 1.5 mph. On these
  anchors a 93 mph fastball is a 50, but 93 sat near the 25th percentile of 2026 starters.

The OFP roll-up is a starting point that the scout overrides with a stated reason:

* starter estimate = 0.30 best + 0.20 second + 0.20 third + 0.30 command (third pitch 35 if there isn't one);
* reliever estimate = min(60, 0.55 best + 0.35 second + 0.10 command), since a one-inning role caps value;
* the starter estimate is used only with 3+ pitches at 45+ future and command at 45+.

  uv run bb grade velo 99.5 --hand L
  uv run bb grade ofp SI=70 CH=70 FF=70 SL=55 command=60
"""
from __future__ import annotations

import math

FF_STARTERS_2026 = (94.5, 2.15)  # mean, SD of 2026 MLB starters' four-seam velocity (mph)
TRADITIONAL_ANCHORS = [(85.0, 20), (88.0, 30), (90.5, 40), (92.0, 45), (93.0, 50), (94.0, 55),
                       (95.0, 60), (96.0, 65), (97.0, 70), (98.0, 80)]
LHP_CREDIT_MPH = 1.5

ROLE_BY_OFP_RELIEVER = {60: "Elite closer", 55: "Closer / high-leverage reliever",
                        50: "Setup / high-leverage reliever", 45: "Middle reliever",
                        40: "Up-and-down reliever", 30: "Organizational arm"}
ROLE_BY_OFP_STARTER = {80: "True ace", 70: "No. 1-2 starter", 60: "No. 2-3 starter", 55: "No. 3-4 starter",
                       50: "No. 4 starter", 45: "No. 5 starter", 40: "Up-and-down arm", 30: "Organizational arm"}


def to_scale(raw: float) -> int:
    """Round to the nearest 5 (halves round up) and clamp to 20-80."""
    return int(max(20, min(80, 5 * math.floor(raw / 5 + 0.5))))


def _interp(x: float, anchors: list[tuple[float, int]]) -> float:
    pts = sorted(anchors)
    if x <= pts[0][0]:
        return float(pts[0][1])
    if x >= pts[-1][0]:
        return float(pts[-1][1])
    for (x0, g0), (x1, g1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return g0 + (g1 - g0) * (x - x0) / (x1 - x0)
    raise ValueError(x)


def velo_grade(mph: float, hand: str = "R") -> dict:
    """Both velocity readings for a sitting velocity. `hand` only affects the traditional reading."""
    mean, sd = FF_STARTERS_2026
    raw_league = 50 + 10 * (mph - mean) / sd
    adj = mph + (LHP_CREDIT_MPH if hand.upper() == "L" else 0.0)
    raw_trad = _interp(adj, TRADITIONAL_ANCHORS)
    return {"mph": mph, "hand": hand.upper(),
            "vs_2026_starters": to_scale(raw_league), "vs_2026_starters_raw": round(raw_league, 1),
            "traditional": to_scale(raw_trad), "traditional_raw": round(raw_trad, 1)}


def _role(ofp: int, table: dict[int, str]) -> str:
    keys = [k for k in sorted(table) if ofp >= k]
    return table[keys[-1]] if keys else table[min(table)]


def ofp_pitcher(pitches: dict[str, int], command: int) -> dict:
    """The roll-up from future pitch grades and future command (see the module docstring)."""
    g = sorted(pitches.values(), reverse=True)
    if len(g) < 2:
        raise ValueError("need at least two graded pitches")
    third = g[2] if len(g) > 2 else 35
    starter = 0.30 * g[0] + 0.20 * g[1] + 0.20 * third + 0.30 * command
    reliever = min(60.0, 0.55 * g[0] + 0.35 * g[1] + 0.10 * command)
    viable = sum(v >= 45 for v in g) >= 3 and command >= 45
    ofp = to_scale(starter if viable else reliever)
    return {"starter_raw": round(starter, 1), "reliever_raw": round(reliever, 1),
            "starter_viable": viable, "starter_ofp": to_scale(starter), "reliever_ofp": to_scale(reliever),
            "suggested_ofp": ofp, "profile": "starter" if viable else "reliever",
            "role": _role(ofp, ROLE_BY_OFP_STARTER if viable else ROLE_BY_OFP_RELIEVER)}


def parse_pitches(items: list[str]) -> tuple[dict[str, int], int]:
    """['SI=70', 'CH=70', 'command=60'] -> ({'SI': 70, 'CH': 70}, 60)."""
    pitches, command = {}, None
    for it in items:
        k, v = it.split("=")
        if k.lower() == "command":
            command = int(v)
        else:
            pitches[k] = int(v)
    if command is None:
        raise ValueError("give command=<future command grade>")
    return pitches, command
