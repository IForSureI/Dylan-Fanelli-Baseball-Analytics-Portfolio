"""Read a TrackMan session-report PDF ("Pitches in session" table) into TrackMan CSV columns.

TrackMan's player app exports a PDF per session: a summary page, then one row per pitch with speed,
total spin, tilt, induced vertical break, horizontal break, extension, release height, release side
and spin efficiency. The pitch type is only drawn as a colored dot, so it's read from the dot's fill
color and matched to the legend.

The output uses TrackMan's native CSV column names, so `baseball.ingest.tracking.normalize(df,
source="trackman")` converts it like any TrackMan export (and tests the horizontal sign on the data).
These reports have no pitch location or outcome, so they're treated as pen data.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

# Fill colors TrackMan uses for the pitch-type dots (RGB 0-1), matched to its legend labels
COLOR_TYPES = {
    (0.5765, 0.0157, 0.0706): "Fastball",
    (0.8745, 0.7137, 0.0): "Slider",
    (0.4314, 0.6353, 0.0): "ChangeUp",
    (0.251, 0.5922, 0.9882): "Curveball",
    (0.5765, 0.5765, 0.5765): "Other",
}
COLUMNS = ["PitchNo", "RelSpeed", "SpinRate", "Tilt", "InducedVertBreak", "HorzBreak", "Extension", "RelHeight", "RelSide", "SpinEfficiency"]


def feet(s: str) -> float | None:
    """'6\\'4"' -> 6.333, '1\\'11"' -> 1.917, '11"' -> 0.917, '7\\'' -> 7.0, '-' -> None."""
    s = s.strip()
    if s in ("-", ""):
        return None
    m = re.fullmatch(r"(?:(-?\d+)')?\s*(?:(\d+(?:\.\d+)?)\")?", s)
    if not m or (m.group(1) is None and m.group(2) is None):
        raise ValueError(f"Can't read a length from {s!r}")
    ft = float(m.group(1) or 0)
    inch = float(m.group(2) or 0)
    return ft + (inch / 12 if ft >= 0 else -inch / 12)


def _num(s: str) -> float | None:
    s = s.strip().rstrip("%")
    return None if s in ("-", "") else float(s)


def _nearest_type(color) -> str:
    if not color or len(color) != 3:
        return "Undefined"
    best = min(COLOR_TYPES, key=lambda c: sum((a - b) ** 2 for a, b in zip(c, color)))
    return COLOR_TYPES[best] if sum((a - b) ** 2 for a, b in zip(best, color)) < 0.01 else "Undefined"


def read_session_pdf(path: str | Path, pitcher_throws: str | None = None) -> tuple[pd.DataFrame, dict]:
    """Return (rows in TrackMan CSV columns, session info)."""
    import pdfplumber

    rows, info = [], {}
    with pdfplumber.open(str(path)) as pdf:
        head = pdf.pages[0].extract_words()
        texts = [w["text"] for w in head[:14]]
        joined = " ".join(texts)
        m = re.search(r"(\d{1,2}) ([A-Z][a-z]{2}) (\d{4})", joined)
        info["date"] = datetime.strptime(m.group(0), "%d %b %Y").date().isoformat() if m else None
        lines = pdf.pages[0].extract_text().splitlines()
        info["facility"] = lines[0].strip() if lines else None
        if len(lines) > 1:
            parts = [p.strip() for p in re.split(r"\s{2,}|\|", lines[1]) if p.strip()]
            name_line = lines[1]
            date_txt = m.group(0) if m else ""
            rest = name_line.replace(date_txt, "").strip()
            for kind in ("Pitching practice", "Bullpen", "Live BP", "Game", "Practice"):
                if kind in rest:
                    info["session_type"] = kind
                    rest = rest.replace(kind, "").strip()
                    break
            info["player"] = rest.strip(" |")
        for page in pdf.pages:
            words = page.extract_words()
            dots = [c for c in page.curves if c.get("non_stroking_color")]
            for w in words:
                if not re.fullmatch(r"#\d+", w["text"]):
                    continue
                line = sorted((x for x in words if abs(x["top"] - w["top"]) < 3 and x["x0"] >= w["x0"]), key=lambda x: x["x0"])
                vals = [x["text"] for x in line]
                if len(vals) < len(COLUMNS):
                    continue
                near = [c for c in dots if abs((c["top"] + c["bottom"]) / 2 - (w["top"] + w["bottom"]) / 2) < 6 and c["x1"] <= w["x0"] + 1]
                color = tuple(round(v, 4) for v in near[-1]["non_stroking_color"]) if near else None
                rows.append({
                    "PitchNo": int(vals[0][1:]), "TaggedPitchType": _nearest_type(color),
                    "RelSpeed": _num(vals[1]), "SpinRate": _num(vals[2]), "Tilt": None if vals[3] == "-" else vals[3],
                    "InducedVertBreak": _num(vals[4]), "HorzBreak": _num(vals[5]), "Extension": feet(vals[6]),
                    "RelHeight": feet(vals[7]), "RelSide": feet(vals[8]), "SpinEfficiency": _num(vals[9]),
                })
    df = pd.DataFrame(rows).drop_duplicates("PitchNo").sort_values("PitchNo").reset_index(drop=True)
    name = info.get("player") or ""
    if " " in name and "," not in name:
        first, last = name.split(" ", 1)
        name = f"{last}, {first}"
    df.insert(0, "Date", info.get("date"))
    df.insert(1, "Pitcher", name)
    df.insert(2, "PitcherThrows", {"R": "Right", "L": "Left"}.get((pitcher_throws or "").upper()[:1], None))
    df["Stadium"] = info.get("facility")
    df["Level"] = info.get("session_type")
    df["GameID"] = f"{info.get('date')} {info.get('facility')} {info.get('session_type')}"
    df["AutoPitchType"] = df["TaggedPitchType"]
    info["pitches"] = int(len(df))
    info["types"] = df["TaggedPitchType"].value_counts().to_dict()
    return df, info
