
"""Normalize TrackMan / Rapsodo / Savant pitch exports to one Savant-style schema, with QC.

The output schema is the one the `baseball` evaluation tools read:
release_speed, pfx_x, pfx_z (feet, catcher's view), release_spin_rate, spin_axis,
release_extension, plate_x, plate_z, zone, sz_top, sz_bot, pitch_type (Savant codes),
description, type, events, stand, p_throws, launch_speed, launch_angle, game_date,
player_name, pitcher, batter, balls, strikes, vx0..az (when the source has them), plus
api_break_x_arm (inches, arm side positive) and api_break_z_induced (inches, IVB).

Usage examples:
  python -m baseball.ingest.tracking detect game.csv
  python -m baseball.ingest.tracking normalize game.csv normalized.csv --source auto
  python -m baseball.ingest.tracking normalize game.csv normalized.csv --source trackman --flip-hb
  python -m baseball.ingest.tracking normalize pen.csv pen_norm.csv --source rapsodo --p-throws L
  python -m baseball.ingest.tracking qc game.csv
  python -m baseball.ingest.tracking qc game.csv --json
  python -m baseball.ingest.tracking tilt 210            -> 1:00
  python -m baseball.ingest.tracking tilt 1:30 --to-degrees   -> 225
  python -m baseball.ingest.tracking efficiency --total 2400 --true 2100
  python -m baseball.ingest.tracking efficiency --total 2400 --efficiency 0.88

Then hand the normalized file to the sabermetrics tools:
  uv run bb arsenal  (or baseball.evaluation.arsenal on the normalized frame)

Frames and signs (see references/trackman-columns.md):
  TrackMan native fields (RelSide, HorzBreak, PlateLocSide) are positive toward the pitcher's
  right (third-base side, the right-handed batter's box). Savant plate_x / pfx_x / release_pos_x
  are positive toward the catcher's right (first-base side). The loader does not trust either
  assumption: it checks the median horizontal break of right-handed fastballs (arm side must
  come out negative in Savant pfx_x) and flips the whole horizontal family if needed. The
  decision is printed and written to the `hb_sign_decision` column. `--flip-hb` forces a flip.

No network calls. Standard library + pandas/numpy only. Synthetic data for tests comes from
make_sample_trackman.py and is fictional.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------------------------

TRACKMAN_SIGNATURE = {"PitchNo", "RelSpeed", "InducedVertBreak", "HorzBreak", "PlateLocSide",
                      "TaggedPitchType", "PitchCall", "PitcherThrows"}
RAPSODO_PITCH_SIGNATURE = {"Total Spin", "True Spin", "Spin Efficiency (release)", "VB (trajectory)",
                           "HB (trajectory)", "Strike Zone Side", "Velocity"}
RAPSODO_HIT_SIGNATURE = {"Exit Velocity", "Launch Angle", "Exit Direction"}
SAVANT_SIGNATURE = {"pitch_type", "release_speed", "pfx_x", "pfx_z", "plate_x", "plate_z", "description"}

# Pitch-type labels -> Savant codes. Keys are lower-cased with spaces/hyphens removed.
PITCH_TYPE_MAP = {
    "fastball": "FF", "fourseamfastball": "FF", "fourseam": "FF", "4seam": "FF", "4seamfastball": "FF",
    "ff": "FF", "fourseamer": "FF", "4s": "FF",
    "sinker": "SI", "twoseamfastball": "SI", "twoseam": "SI", "2seam": "SI", "2seamfastball": "SI",
    "si": "SI", "sinkerfastball": "SI", "2s": "SI",
    "cutter": "FC", "cutfastball": "FC", "fc": "FC", "cut": "FC",
    "slider": "SL", "sl": "SL", "gyroslider": "SL",
    "sweeper": "ST", "st": "ST", "sweepingslider": "ST",
    "slurve": "SV", "sv": "SV",
    "curveball": "CU", "curve": "CU", "cu": "CU", "cb": "CU", "12-6curve": "CU", "126curve": "CU",
    "knucklecurve": "KC", "kc": "KC", "knucklecurveball": "KC", "spikecurve": "KC",
    "changeup": "CH", "change": "CH", "ch": "CH", "circlechange": "CH", "vulcanchange": "CH",
    "splitter": "FS", "splitfinger": "FS", "fs": "FS", "splitfingerfastball": "FS", "split": "FS",
    "forkball": "FO", "fo": "FO",
    "screwball": "SC", "sc": "SC",
    "knuckleball": "KN", "kn": "KN", "knuckle": "KN",
    "eephus": "EP", "ep": "EP",
    "other": "UN", "undefined": "UN", "unknown": "UN", "": "UN", "-": "UN", "nan": "UN", "none": "UN",
}

# TrackMan PitchCall -> Savant description, and Savant `type` (B/S/X).
PITCHCALL_MAP = {
    "strikecalled": ("called_strike", "S"),
    "strikeswinging": ("swinging_strike", "S"),
    "ballcalled": ("ball", "B"),
    "ballindirt": ("blocked_ball", "B"),
    "ballintentional": ("ball", "B"),  # Savant retired intent_ball; keep as ball and flag in notes
    "hitbypitch": ("hit_by_pitch", "B"),
    "foulball": ("foul", "S"),
    "foulballnotfieldable": ("foul", "S"),
    "foulballfieldable": ("foul", "S"),
    "foultip": ("foul_tip", "S"),
    "inplay": ("hit_into_play", "X"),
    "undefined": (None, None),
    "": (None, None),
}

PLAYRESULT_MAP = {
    "single": "single", "double": "double", "triple": "triple", "homerun": "home_run",
    "out": "field_out", "error": "field_error", "fielderschoice": "fielders_choice",
    "sacrifice": "sac_fly",  # refined to sac_bunt when TaggedHitType is Bunt
    "undefined": None, "": None,
}
KORBB_MAP = {"strikeout": "strikeout", "walk": "walk", "undefined": None, "": None}
HITTYPE_MAP = {"groundball": "ground_ball", "linedrive": "line_drive", "flyball": "fly_ball",
               "popup": "popup", "bunt": "bunt", "undefined": None, "": None}

SZ_TOP_DEFAULT, SZ_BOT_DEFAULT = 3.5, 1.5       # feet; Savant-style defaults when no per-batter zone
HALF_PLATE_FT = 8.5 / 12.0                       # zone half-width used by statcast_tools

# QC thresholds (see references/qc-checklist.md)
LIMITS = {
    "release_speed": (50.0, 110.0),
    "release_spin_rate": (0.0, 3500.0),
    "release_extension": (4.0, 8.0),
    "release_pos_z": (3.0, 8.0),
    "release_pos_x": (-4.5, 4.5),
    "plate_x": (-4.0, 4.0),
    "plate_z": (-2.0, 7.0),
    "api_break_z_induced": (-30.0, 30.0),
    "api_break_x_arm": (-30.0, 30.0),
    "spin_axis": (0.0, 360.0),
    "launch_speed": (10.0, 125.0),
    "launch_angle": (-90.0, 90.0),
}

OUTPUT_ORDER = [
    "game_date", "game_id", "pitch_uid", "pitch_no", "source", "level", "league", "stadium",
    "player_name", "pitcher", "p_throws", "pitcher_team", "batter_name", "batter", "stand", "batter_team",
    "catcher_name", "catcher", "inning", "inning_topbot", "at_bat_number", "pitch_number",
    "balls", "strikes", "outs_when_up",
    "pitch_type", "pitch_name", "pitch_type_auto", "pitch_tag_disagree", "tag_fallback_to_auto",
    "description", "type", "events", "bb_type",
    "release_speed", "effective_speed", "zone_speed", "release_spin_rate", "spin_axis", "tilt",
    "active_spin", "spin_efficiency", "gyro_deg",
    "release_extension", "release_pos_x", "release_pos_z", "release_pos_y",
    "pfx_x", "pfx_z", "api_break_x_arm", "api_break_z_induced", "api_break_z_with_gravity",
    "ssw_hb_in", "ssw_vb_in",
    "plate_x", "plate_z", "zone", "sz_top", "sz_bot", "vaa_deg", "vaa_trackman", "haa_deg",
    "vx0", "vy0", "vz0", "ax", "ay", "az",
    "launch_speed", "launch_angle", "launch_direction", "hit_distance_sc", "hit_spin_rate",
    "release_confidence", "location_confidence", "movement_confidence", "low_confidence",
    "hb_sign_decision", "qc_flags", "notes",
]


# ---------------------------------------------------------------------------------------------
# Small pure helpers
# ---------------------------------------------------------------------------------------------

def _key(s) -> str:
    """Lower-case a label and drop spaces, hyphens, underscores, slashes."""
    return re.sub(r"[\s\-_/]+", "", str(s).strip().lower())


def map_pitch_type(label) -> str:
    """'FourSeamFastBall' -> 'FF', 'ChangeUp' -> 'CH', unknown -> 'UN'."""
    if label is None or (isinstance(label, float) and math.isnan(label)):
        return "UN"
    return PITCH_TYPE_MAP.get(_key(label), "UN")


def map_pitch_call(call) -> tuple:
    if call is None or (isinstance(call, float) and math.isnan(call)):
        return (None, None)
    return PITCHCALL_MAP.get(_key(call), (None, None))


def axis_to_tilt(axis_deg: float) -> str:
    """Spin axis in degrees (Savant/TrackMan: 180 = 12:00 pure backspin) -> clock 'H:MM'.

    tilt_hours = ((axis - 180) / 30 + 12) mod 12, 0 -> 12. Minutes rounded to the nearest 15,
    matching TrackMan's Tilt column. 210 -> 1:00, 240 -> 2:00, 90 -> 9:00, 180 -> 12:00.
    """
    if axis_deg is None or (isinstance(axis_deg, float) and math.isnan(axis_deg)):
        return ""
    hours = ((float(axis_deg) - 180.0) / 30.0 + 12.0) % 12.0
    quarter = int(round(hours * 4)) % 48       # 15-minute steps around the clock
    h, q = divmod(quarter, 4)
    h = 12 if h == 0 else h
    return f"{h}:{q * 15:02d}"


def tilt_to_axis(tilt: str) -> float:
    """'1:30' -> 225.0; '12:00' -> 180.0; '9:00' -> 90.0. Accepts 'H:MM', 'H.5', or hours as a number."""
    s = str(tilt).strip()
    if ":" in s:
        h, m = s.split(":")
        hours = int(h) % 12 + int(m) / 60.0
    else:
        hours = float(s) % 12
    return (180.0 + hours * 30.0) % 360.0


def spin_efficiency(total: float | None = None, true: float | None = None,
                    efficiency: float | None = None) -> dict:
    """Any two of total spin, true (active) spin, efficiency -> the third plus the gyro angle.

    efficiency = active / total; gyro_deg = degrees(arccos(efficiency)).
    """
    if efficiency is not None and efficiency > 1.0:
        efficiency = efficiency / 100.0
    if total is not None and true is not None:
        efficiency = true / total if total else float("nan")
    elif total is not None and efficiency is not None:
        true = total * efficiency
    elif true is not None and efficiency is not None:
        total = true / efficiency if efficiency else float("nan")
    else:
        raise ValueError("give two of --total, --true, --efficiency")
    eff = max(0.0, min(1.0, efficiency))
    gyro = math.degrees(math.acos(eff))
    return {"total_spin_rpm": round(total, 1), "active_spin_rpm": round(true, 1),
            "spin_efficiency": round(efficiency, 4), "spin_efficiency_pct": round(100 * efficiency, 1),
            "gyro_angle_deg": round(gyro, 2),
            "note": "efficiency = active spin / total spin; gyro angle = arccos(efficiency). "
                    "Rapsodo 'True Spin' is the active (movement-causing) component."}


def _to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def savant_zone(plate_x: pd.Series, plate_z: pd.Series, sz_top: pd.Series, sz_bot: pd.Series) -> pd.Series:
    """Savant zone 1-9 in the zone (catcher's view, 1 = top-left), 11-14 outside, NaN when untracked."""
    x, z = plate_x.astype(float), plate_z.astype(float)
    top, bot = sz_top.astype(float), sz_bot.astype(float)
    in_zone = (x.abs() <= HALF_PLATE_FT) & (z >= bot) & (z <= top)
    third = (top - bot) / 3.0
    col = np.where(x < -HALF_PLATE_FT / 3, 0, np.where(x > HALF_PLATE_FT / 3, 2, 1))
    row = np.where(z > top - third, 0, np.where(z < bot + third, 2, 1))
    inside = 1 + row * 3 + col
    mid = (top + bot) / 2.0
    outside = np.where(z >= mid, np.where(x < 0, 11, 12), np.where(x < 0, 13, 14))
    zone = np.where(in_zone, inside, outside).astype(float)
    zone[x.isna().values | z.isna().values] = np.nan
    return pd.Series(zone, index=plate_x.index)


# ---------------------------------------------------------------------------------------------
# Reading and detection
# ---------------------------------------------------------------------------------------------

def find_header_row(path: str, max_scan: int = 40) -> int:
    """Rapsodo exports put a few metadata lines before the real header. Return its 0-based line."""
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        lines = [next(fh, "") for _ in range(max_scan)]
    best, best_hits = 0, 0
    for i, line in enumerate(lines):
        cells = {c.strip().strip('"') for c in line.split(",")}
        hits = len(cells & (TRACKMAN_SIGNATURE | RAPSODO_PITCH_SIGNATURE | RAPSODO_HIT_SIGNATURE | SAVANT_SIGNATURE))
        if hits > best_hits:
            best, best_hits = i, hits
    return best


def read_any(path: str) -> tuple[pd.DataFrame, int]:
    hdr = find_header_row(path)
    df = pd.read_csv(path, skiprows=hdr, low_memory=False, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, [c for c in df.columns if not c.startswith("Unnamed")]]
    return df, hdr


def detect(df: pd.DataFrame) -> dict:
    cols = set(df.columns)
    scores = {
        "trackman": len(cols & TRACKMAN_SIGNATURE) / len(TRACKMAN_SIGNATURE),
        "rapsodo": len(cols & RAPSODO_PITCH_SIGNATURE) / len(RAPSODO_PITCH_SIGNATURE),
        "rapsodo_hitting": len(cols & RAPSODO_HIT_SIGNATURE) / len(RAPSODO_HIT_SIGNATURE),
        "savant": len(cols & SAVANT_SIGNATURE) / len(SAVANT_SIGNATURE),
    }
    source = max(scores, key=scores.get)
    conf = scores[source]
    if conf < 0.5:
        source = "unknown"
    evidence = sorted(cols & {
        "trackman": TRACKMAN_SIGNATURE, "rapsodo": RAPSODO_PITCH_SIGNATURE,
        "rapsodo_hitting": RAPSODO_HIT_SIGNATURE, "savant": SAVANT_SIGNATURE}.get(source, set()))
    extra = {}
    if source == "trackman":
        extra["system"] = sorted(df["System"].dropna().astype(str).unique().tolist()) if "System" in df else []
        extra["has_confidence_cols"] = "PitchReleaseConfidence" in cols
        extra["has_pfx_cols"] = {"pfxx", "pfxz", "x0", "vx0"}.issubset(cols)
    if source == "rapsodo":
        extra["device_serials"] = sorted(df["Device Serial Number"].dropna().astype(str).unique().tolist()) \
            if "Device Serial Number" in df else []
        extra["has_handedness"] = any(_key(c) in {"pitcherthrows", "throws", "hand", "pthrows"} for c in cols)
    return {"source": source, "confidence": round(conf, 2), "scores": {k: round(v, 2) for k, v in scores.items()},
            "evidence_columns": evidence, "n_rows": int(len(df)), "n_columns": int(len(cols)), **extra}


# ---------------------------------------------------------------------------------------------
# Horizontal-sign detection
# ---------------------------------------------------------------------------------------------

def decide_hb_sign(hb_in: pd.Series, p_throws: pd.Series, pitch_type: pd.Series, force_flip: bool = False) -> dict:
    """Decide whether horizontal values are in the Savant (catcher's view) frame.

    Savant: a RHP fastball's arm-side run is NEGATIVE pfx_x; a LHP's is POSITIVE. We take every
    FF/SI with a known hand, multiply HB by (+1 for R, -1 for L), and look at the median:
      median < 0  -> already Savant frame, multiplier +1
      median > 0  -> pitcher's-view frame (TrackMan native), multiplier -1
    """
    hand = p_throws.astype(str).str.upper().str[0]
    mask = pitch_type.isin(["FF", "SI"]) & hand.isin(["R", "L"]) & hb_in.notna()
    n = int(mask.sum())
    if force_flip:
        return {"multiplier": -1, "basis": "forced by --flip-hb", "n_fastballs": n, "median_armside_raw": None}
    if n < 5:
        return {"multiplier": -1, "basis": "fewer than 5 handed fastballs; assumed TrackMan native frame "
                                           "(pitcher's view, arm side positive for RHP) and flipped. Check it.",
                "n_fastballs": n, "median_armside_raw": None}
    signed = hb_in[mask] * np.where(hand[mask] == "R", 1.0, -1.0)
    med = float(np.nanmedian(signed))
    if med > 0:
        return {"multiplier": -1, "n_fastballs": n, "median_armside_raw": round(med, 2),
                "basis": f"RHP/LHP fastballs run arm side with POSITIVE raw sign (median {med:+.1f} in) -> "
                         "pitcher's-view frame; flipped to Savant catcher's view"}
    return {"multiplier": 1, "n_fastballs": n, "median_armside_raw": round(med, 2),
            "basis": f"RHP/LHP fastballs run arm side with NEGATIVE raw sign (median {med:+.1f} in) -> "
                     "already Savant catcher's view; no flip"}


# ---------------------------------------------------------------------------------------------
# Normalizers
# ---------------------------------------------------------------------------------------------

def _col(df: pd.DataFrame, *names):
    """First matching column (case/space-insensitive) or a NaN series."""
    keys = {_key(c): c for c in df.columns}
    for n in names:
        if _key(n) in keys:
            return df[keys[_key(n)]]
    return pd.Series(np.nan, index=df.index)


def _parse_date(s: pd.Series) -> pd.Series:
    d = pd.to_datetime(s, errors="coerce")
    return d.dt.strftime("%Y-%m-%d")


def normalize_trackman(df: pd.DataFrame, force_flip: bool = False) -> tuple[pd.DataFrame, dict]:
    out = pd.DataFrame(index=df.index)
    out["source"] = "trackman"
    out["game_date"] = _parse_date(_col(df, "Date"))
    out["game_id"] = _col(df, "GameID")
    out["pitch_uid"] = _col(df, "PitchUID")
    out["pitch_no"] = _to_num(_col(df, "PitchNo"))
    out["level"] = _col(df, "Level")
    out["league"] = _col(df, "League")
    out["stadium"] = _col(df, "Stadium")
    out["player_name"] = _col(df, "Pitcher")
    out["pitcher"] = _col(df, "PitcherId")
    out["p_throws"] = _col(df, "PitcherThrows").astype(str).str.upper().str[0].replace({"N": np.nan})
    out["pitcher_team"] = _col(df, "PitcherTeam")
    out["batter_name"] = _col(df, "Batter")
    out["batter"] = _col(df, "BatterId")
    out["stand"] = _col(df, "BatterSide").astype(str).str.upper().str[0].replace({"N": np.nan})
    out["batter_team"] = _col(df, "BatterTeam")
    out["catcher_name"] = _col(df, "Catcher")
    out["catcher"] = _col(df, "CatcherId")
    out["inning"] = _to_num(_col(df, "Inning"))
    out["inning_topbot"] = _col(df, "Top/Bottom").astype(str).str[:3].str.title().replace({"Nan": np.nan})
    out["at_bat_number"] = _to_num(_col(df, "PAofInning"))
    out["pitch_number"] = _to_num(_col(df, "PitchofPA"))
    out["balls"] = _to_num(_col(df, "Balls"))
    out["strikes"] = _to_num(_col(df, "Strikes"))
    out["outs_when_up"] = _to_num(_col(df, "Outs"))

    tagged = _col(df, "TaggedPitchType")
    auto = _col(df, "AutoPitchType")
    out["pitch_name"] = tagged
    out["pitch_type"] = tagged.map(map_pitch_type)
    out["pitch_type_auto"] = auto.map(map_pitch_type)
    # Fall back to the auto tag when the tagger left it undefined
    fallback = out["pitch_type"].eq("UN") & out["pitch_type_auto"].ne("UN")
    out.loc[fallback, "pitch_type"] = out.loc[fallback, "pitch_type_auto"]
    out["pitch_tag_disagree"] = (out["pitch_type"] != out["pitch_type_auto"]) & out["pitch_type_auto"].ne("UN") & ~fallback
    out["tag_fallback_to_auto"] = fallback

    calls = _col(df, "PitchCall").map(map_pitch_call)
    out["description"] = [c[0] for c in calls]
    out["type"] = [c[1] for c in calls]
    korbb = _col(df, "KorBB").map(lambda v: KORBB_MAP.get(_key(v), None))
    play = _col(df, "PlayResult").map(lambda v: PLAYRESULT_MAP.get(_key(v), None))
    hit = _col(df, "TaggedHitType").map(lambda v: HITTYPE_MAP.get(_key(v), None))
    events = play.copy()
    events = events.where(events.notna(), korbb)
    hbp = out["description"].eq("hit_by_pitch")
    events = events.where(~hbp, "hit_by_pitch")
    sac_bunt = events.eq("sac_fly") & hit.eq("bunt")
    events = events.where(~sac_bunt, "sac_bunt")
    out["events"] = events
    out["bb_type"] = hit.replace({"bunt": "ground_ball"})

    out["release_speed"] = _to_num(_col(df, "RelSpeed"))
    out["effective_speed"] = _to_num(_col(df, "EffectiveVelo"))
    out["zone_speed"] = _to_num(_col(df, "ZoneSpeed"))
    out["release_spin_rate"] = _to_num(_col(df, "SpinRate"))
    out["spin_axis"] = _to_num(_col(df, "SpinAxis"))
    out["tilt"] = _col(df, "Tilt")
    out["active_spin"] = _to_num(_col(df, "SpinAxis3dActiveSpinRate"))
    out["spin_efficiency"] = _to_num(_col(df, "SpinAxis3dSpinEfficiency"))
    out["gyro_deg"] = np.nan
    out["release_extension"] = _to_num(_col(df, "Extension"))
    out["release_pos_z"] = _to_num(_col(df, "RelHeight"))
    out["release_pos_y"] = 60.5 - out["release_extension"]

    ivb = _to_num(_col(df, "InducedVertBreak"))
    hb_raw = _to_num(_col(df, "HorzBreak"))
    decision = decide_hb_sign(hb_raw, out["p_throws"], out["pitch_type"], force_flip)
    m = decision["multiplier"]
    out["pfx_z"] = ivb / 12.0
    out["pfx_x"] = m * hb_raw / 12.0
    out["api_break_z_induced"] = ivb
    out["api_break_z_with_gravity"] = _to_num(_col(df, "VertBreak"))
    arm_sign = np.where(out["p_throws"].eq("R"), -1.0, np.where(out["p_throws"].eq("L"), 1.0, np.nan))
    out["api_break_x_arm"] = out["pfx_x"] * 12.0 * arm_sign
    out["ssw_hb_in"] = np.nan
    out["ssw_vb_in"] = np.nan
    out["release_pos_x"] = m * _to_num(_col(df, "RelSide"))
    out["plate_x"] = m * _to_num(_col(df, "PlateLocSide"))
    out["plate_z"] = _to_num(_col(df, "PlateLocHeight"))
    out["sz_top"] = SZ_TOP_DEFAULT
    out["sz_bot"] = SZ_BOT_DEFAULT
    out["zone"] = savant_zone(out["plate_x"], out["plate_z"], out["sz_top"], out["sz_bot"])
    out["vaa_deg"] = _to_num(_col(df, "VertApprAngle"))
    out["vaa_trackman"] = out["vaa_deg"]        # statcast_tools recomputes vaa_deg from vy0/ay/vz0/az; this keeps the measured one
    out["haa_deg"] = m * _to_num(_col(df, "HorzApprAngle"))

    # PITCHf/x-style fields. The TrackMan glossary example shows x0 = -1.93 ft against RelSide = +2.17 ft
    # for the same pitch, i.e. these are already in the catcher's-view frame. We test that on the data.
    x0 = _to_num(_col(df, "x0"))
    relside = _to_num(_col(df, "RelSide"))
    pfx_frame = "n/a"
    if x0.notna().sum() >= 5 and relside.notna().sum() >= 5:
        both = x0.notna() & relside.notna()
        same = float(np.nanmedian(np.sign(x0[both]) * np.sign(relside[both])))
        pfx_m = 1.0 if (same < 0) == (m == -1) else m   # x0 opposite RelSide -> already catcher frame
        pfx_frame = "catcher-view (kept)" if pfx_m == 1 else "pitcher-view (flipped)"
    else:
        pfx_m = 1.0
    for src, dst in (("vx0", "vx0"), ("vy0", "vy0"), ("vz0", "vz0"), ("ax0", "ax"), ("ay0", "ay"), ("az0", "az")):
        v = _to_num(_col(df, src))
        out[dst] = v * pfx_m if dst in ("vx0", "ax") else v
    decision["pfx_fields_frame"] = pfx_frame

    out["launch_speed"] = _to_num(_col(df, "ExitSpeed"))
    out["launch_angle"] = _to_num(_col(df, "Angle"))
    out["launch_direction"] = _to_num(_col(df, "Direction"))
    out["hit_distance_sc"] = _to_num(_col(df, "Distance"))
    out["hit_spin_rate"] = _to_num(_col(df, "HitSpinRate"))

    out["release_confidence"] = _col(df, "PitchReleaseConfidence")
    out["location_confidence"] = _col(df, "PitchLocationConfidence")
    out["movement_confidence"] = _col(df, "PitchMovementConfidence")
    lowset = {"low", "", "nan", "none"}
    conf_cols = ["release_confidence", "location_confidence", "movement_confidence"]
    if "PitchReleaseConfidence" in df.columns:
        low = out[conf_cols].astype(str).apply(lambda r: any(_key(v) in lowset for v in r), axis=1)
        out["low_confidence"] = low & out["release_speed"].notna()   # untracked rows are flagged separately
    else:
        out["low_confidence"] = False
    out["notes"] = _col(df, "Notes")
    out["hb_sign_decision"] = "x-1 (raw pitcher-view, flipped)" if m == -1 else "x1 (raw catcher-view, kept)"
    return out, decision


def _rapsodo_spin_axis(spin_dir: pd.Series) -> pd.Series:
    """Rapsodo 'Spin Direction' is a clock string ('1:15') or, on some exports, degrees."""
    def one(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return np.nan
        s = str(v).strip()
        if ":" in s:
            try:
                return tilt_to_axis(s)
            except ValueError:
                return np.nan
        try:
            return float(s)
        except ValueError:
            return np.nan
    return spin_dir.map(one)


def normalize_rapsodo(df: pd.DataFrame, p_throws: str | None = None, force_flip: bool = False,
                      player_name: str | None = None) -> tuple[pd.DataFrame, dict]:
    out = pd.DataFrame(index=df.index)
    out["source"] = "rapsodo"
    out["game_date"] = _parse_date(_col(df, "Date"))
    out["game_id"] = _col(df, "Session Name", "Session")
    out["pitch_uid"] = _col(df, "Pitch ID", "Unique ID")
    out["pitch_no"] = _to_num(_col(df, "No", "Pitch No", "#"))
    out["level"] = "bullpen"
    out["league"] = np.nan
    out["stadium"] = _col(df, "Device Serial Number")
    name = _col(df, "Player Name", "Player", "Pitcher")
    out["player_name"] = name if name.notna().any() else (player_name or "unknown")
    out["pitcher"] = _col(df, "Player ID", "PitcherId")
    hand_col = _col(df, "PitcherThrows", "Throws", "Hand")
    if hand_col.notna().any():
        out["p_throws"] = hand_col.astype(str).str.upper().str[0]
        hand_basis = "from file"
    else:
        out["p_throws"] = (p_throws or "R").upper()[0]
        hand_basis = f"--p-throws {p_throws}" if p_throws else "ASSUMED R (Rapsodo exports carry no handedness; pass --p-throws)"
    for c in ("pitcher_team", "batter_name", "batter", "stand", "batter_team", "catcher_name", "catcher",
              "inning", "inning_topbot", "at_bat_number", "pitch_number", "balls", "strikes", "outs_when_up",
              "events", "bb_type", "launch_speed", "launch_angle", "launch_direction", "hit_distance_sc",
              "hit_spin_rate", "effective_speed", "zone_speed", "vaa_deg", "notes",
              "vx0", "vy0", "vz0", "ax", "ay", "az", "api_break_z_with_gravity"):
        out[c] = np.nan
    out["pitch_name"] = _col(df, "Pitch Type")
    out["pitch_type"] = out["pitch_name"].map(map_pitch_type)
    out["pitch_type_auto"] = "UN"
    out["pitch_tag_disagree"] = False

    is_strike = _col(df, "Is Strike").astype(str).str.lower().isin(["true", "yes", "1", "strike", "1.0"])
    has_strike = _col(df, "Is Strike").notna()
    # Bullpen data has no swing outcomes: strikes become called_strike / balls become ball so that
    # zone% works; whiff% and CSW% from this file are meaningless and the QC report says so.
    out["description"] = np.where(has_strike, np.where(is_strike, "called_strike", "ball"), None)
    out["type"] = np.where(has_strike, np.where(is_strike, "S", "B"), None)

    out["release_speed"] = _to_num(_col(df, "Velocity", "Speed"))
    out["release_spin_rate"] = _to_num(_col(df, "Total Spin", "Spin Rate"))
    out["active_spin"] = _to_num(_col(df, "True Spin"))
    eff = _to_num(_col(df, "Spin Efficiency (release)", "Spin Efficiency"))
    out["spin_efficiency"] = np.where(eff > 1.0, eff / 100.0, eff)
    out["gyro_deg"] = _to_num(_col(df, "Gyro Degree (deg)", "Gyro Degree", "Gyro"))
    out["spin_axis"] = _rapsodo_spin_axis(_col(df, "Spin Direction", "Spin Axis"))
    out["tilt"] = out["spin_axis"].map(axis_to_tilt)
    out["release_extension"] = _to_num(_col(df, "Release Extension", "Extension"))
    out["release_pos_z"] = _to_num(_col(df, "Release Height"))
    out["release_pos_y"] = 60.5 - out["release_extension"]

    vb = _to_num(_col(df, "VB (trajectory)", "VB", "Vertical Break"))
    hb_raw = _to_num(_col(df, "HB (trajectory)", "HB", "Horizontal Break"))
    decision = decide_hb_sign(hb_raw, out["p_throws"], out["pitch_type"], force_flip)
    m = decision["multiplier"]
    decision["handedness_basis"] = hand_basis
    out["pfx_z"] = vb / 12.0
    out["pfx_x"] = m * hb_raw / 12.0
    out["api_break_z_induced"] = vb
    arm_sign = np.where(out["p_throws"].eq("R"), -1.0, 1.0)
    out["api_break_x_arm"] = out["pfx_x"] * 12.0 * arm_sign
    out["ssw_hb_in"] = m * _to_num(_col(df, "SSW HB"))
    out["ssw_vb_in"] = _to_num(_col(df, "SSW VB"))
    out["release_pos_x"] = m * _to_num(_col(df, "Release Side"))

    side = _to_num(_col(df, "Strike Zone Side"))
    height = _to_num(_col(df, "Strike Zone Height"))
    # Rapsodo 2.0 exports report location in inches; detect by magnitude.
    loc_units = "inches" if float(np.nanmedian(height.abs())) > 8 else "feet"
    k = 12.0 if loc_units == "inches" else 1.0
    out["plate_x"] = m * side / k
    out["plate_z"] = height / k
    decision["location_units"] = loc_units
    out["sz_top"] = SZ_TOP_DEFAULT
    out["sz_bot"] = SZ_BOT_DEFAULT
    out["zone"] = savant_zone(out["plate_x"], out["plate_z"], out["sz_top"], out["sz_bot"])
    out["haa_deg"] = m * _to_num(_col(df, "Horizontal Angle"))
    out["release_confidence"] = np.nan
    out["location_confidence"] = np.nan
    out["movement_confidence"] = _col(df, "Spin Confidence")
    sc = _to_num(_col(df, "Spin Confidence"))
    out["low_confidence"] = (sc < 0.5) if sc.notna().any() else False
    out["hb_sign_decision"] = "x-1 (raw pitcher-view, flipped)" if m == -1 else "x1 (raw catcher-view, kept)"
    return out, decision


def normalize_rapsodo_hitting(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    out = pd.DataFrame(index=df.index)
    out["source"] = "rapsodo_hitting"
    out["game_date"] = _parse_date(_col(df, "Date"))
    out["game_id"] = _col(df, "Session Name", "Session")
    out["pitch_uid"] = _col(df, "Hit ID", "Unique ID", "ID")
    out["pitch_no"] = _to_num(_col(df, "No", "#"))
    out["batter_name"] = _col(df, "Player Name", "Player")
    out["batter"] = _col(df, "Player ID")
    out["stand"] = _col(df, "Bats", "Side")
    out["launch_speed"] = _to_num(_col(df, "Exit Velocity", "Exit Speed"))
    out["launch_angle"] = _to_num(_col(df, "Launch Angle", "Angle"))
    out["launch_direction"] = _to_num(_col(df, "Exit Direction", "Direction"))
    out["hit_distance_sc"] = _to_num(_col(df, "Distance"))
    out["hit_spin_rate"] = _to_num(_col(df, "Spin", "Total Spin", "Spin Rate"))
    out["bb_type"] = _col(df, "Hit Type", "Type").map(lambda v: HITTYPE_MAP.get(_key(v), None) if pd.notna(v) else None)
    out["description"] = np.where(out["launch_speed"].notna(), "hit_into_play", None)
    out["type"] = np.where(out["launch_speed"].notna(), "X", None)
    out["release_speed"] = _to_num(_col(df, "Pitch Velocity", "Pitch Speed"))
    out["pitch_type"] = _col(df, "Pitch Type").map(map_pitch_type)
    out["hb_sign_decision"] = "n/a (hitting export)"
    out["low_confidence"] = False
    return out, {"multiplier": 1, "basis": "hitting export; no horizontal pitch fields"}


def normalize_savant(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    out = df.copy()
    out["source"] = "savant"
    if "release_spin_rate" not in out and "release_spin" in out:
        out["release_spin_rate"] = out["release_spin"]
    if "api_break_x_arm" not in out and {"pfx_x", "p_throws"}.issubset(out.columns):
        arm_sign = np.where(out["p_throws"].astype(str).str.upper().eq("R"), -1.0, 1.0)
        out["api_break_x_arm"] = out["pfx_x"] * 12.0 * arm_sign
    if "api_break_z_induced" not in out and "pfx_z" in out:
        out["api_break_z_induced"] = out["pfx_z"] * 12.0
    if "zone" not in out and {"plate_x", "plate_z"}.issubset(out.columns):
        top = out["sz_top"] if "sz_top" in out else pd.Series(SZ_TOP_DEFAULT, index=out.index)
        bot = out["sz_bot"] if "sz_bot" in out else pd.Series(SZ_BOT_DEFAULT, index=out.index)
        out["zone"] = savant_zone(out["plate_x"], out["plate_z"], top.fillna(SZ_TOP_DEFAULT), bot.fillna(SZ_BOT_DEFAULT))
    if "tilt" not in out and "spin_axis" in out:
        out["tilt"] = out["spin_axis"].map(axis_to_tilt)
    out["hb_sign_decision"] = "x1: Savant file; catcher's view by definition"
    out["low_confidence"] = False
    return out, {"multiplier": 1, "basis": "Savant source; no change"}


def normalize(df: pd.DataFrame, source: str = "auto", force_flip: bool = False, p_throws: str | None = None,
              player_name: str | None = None) -> tuple[pd.DataFrame, dict]:
    det = detect(df)
    src = det["source"] if source == "auto" else source
    if src == "trackman":
        out, dec = normalize_trackman(df, force_flip)
    elif src == "rapsodo":
        out, dec = normalize_rapsodo(df, p_throws, force_flip, player_name)
    elif src == "rapsodo_hitting":
        out, dec = normalize_rapsodo_hitting(df)
    elif src == "savant":
        out, dec = normalize_savant(df)
    else:
        raise SystemExit(f"could not detect the source (scores {det['scores']}); pass --source")
    ordered = [c for c in OUTPUT_ORDER if c in out.columns] + [c for c in out.columns if c not in OUTPUT_ORDER]
    out = out[ordered]
    out["qc_flags"] = row_flags(out)
    dec["source"] = src
    dec["detection"] = det
    return out, dec


# ---------------------------------------------------------------------------------------------
# QC
# ---------------------------------------------------------------------------------------------

def row_flags(n: pd.DataFrame) -> pd.Series:
    """Per-row semicolon-separated QC flags on a normalized frame."""
    flags = pd.Series([""] * len(n), index=n.index, dtype=object)

    def add(mask, label):
        nonlocal flags
        mask = pd.Series(mask, index=n.index).fillna(False).astype(bool)
        flags = flags.where(~mask, flags + label + ";")

    if "release_speed" in n:
        tracked_desc = n["description"].notna() if "description" in n else pd.Series(True, index=n.index)
        add(n["release_speed"].isna() & tracked_desc, "untracked")
    for col, (lo, hi) in LIMITS.items():
        if col in n:
            v = pd.to_numeric(n[col], errors="coerce")
            add(v.notna() & ((v < lo) | (v > hi)), f"impossible_{col}")
    if "low_confidence" in n:
        add(n["low_confidence"].fillna(False).astype(bool), "low_confidence")
    if "pitch_tag_disagree" in n:
        add(n["pitch_tag_disagree"].fillna(False).astype(bool), "tag_disagree")
    if "pitch_type" in n:
        add(n["pitch_type"].eq("UN"), "pitch_type_undefined")
    if "tag_fallback_to_auto" in n:
        add(n["tag_fallback_to_auto"].fillna(False).astype(bool), "tag_fallback_to_auto")
    if "pitch_uid" in n and n["pitch_uid"].notna().any():
        add(n["pitch_uid"].notna() & n.duplicated(subset=["pitch_uid"], keep="first"), "duplicate_uid")
    for col, hi in (("balls", 3), ("strikes", 2), ("outs_when_up", 2)):
        if col in n:
            v = pd.to_numeric(n[col], errors="coerce")
            add(v.notna() & ((v < 0) | (v > hi)), f"bad_{col}")
    if {"description", "launch_speed"}.issubset(n.columns):
        add(n["description"].eq("hit_into_play") & n["launch_speed"].isna(), "bip_untracked")
    if {"release_speed", "pitch_type", "pitcher"}.issubset(n.columns):
        grp = n.groupby(["pitcher", "pitch_type"])["release_speed"]
        med = grp.transform("median")
        mad = grp.transform(lambda s: float(np.nanmedian(np.abs(s - np.nanmedian(s)))) if s.notna().sum() >= 5 else np.nan)
        robust_z = (n["release_speed"] - med) / (1.4826 * mad.replace(0, np.nan))
        add(robust_z.abs() > 4, "velo_outlier_for_type")
    return flags.str.rstrip(";")


def qc_report(raw: pd.DataFrame, norm: pd.DataFrame, decision: dict) -> dict:
    rep = {"source": decision.get("source"), "rows": int(len(norm)), "hb_sign": decision.get("basis"),
           "checks": {}, "warnings": []}
    c = rep["checks"]

    flags = norm["qc_flags"].fillna("")
    for label in ["untracked", "low_confidence", "tag_disagree", "pitch_type_undefined", "tag_fallback_to_auto", "duplicate_uid",
                  "bip_untracked", "velo_outlier_for_type", "bad_balls", "bad_strikes", "bad_outs_when_up"]:
        c[label] = int(flags.str.contains(rf"(?:^|;){label}(?:;|$)").sum())
    for col in LIMITS:
        c[f"impossible_{col}"] = int(flags.str.contains(f"impossible_{col}").sum())

    # duplicates beyond the UID: identical (pitcher, date, pitch_no) or fully identical rows
    key = [k for k in ("pitcher", "game_date", "pitch_no") if k in norm]
    c["duplicate_rows_exact"] = int(raw.duplicated().sum())
    c["duplicate_pitch_keys"] = int(norm.duplicated(subset=key).sum()) if len(key) == 3 and norm["pitch_no"].notna().any() else 0

    # sequence gaps
    if "pitch_no" in norm and norm["pitch_no"].notna().any():
        gaps = []
        for g, s in norm.groupby("game_id" if "game_id" in norm else "game_date")["pitch_no"]:
            s = s.dropna().astype(int).sort_values().unique()
            if len(s) > 1:
                missing = sorted(set(range(int(s.min()), int(s.max()) + 1)) - set(s.tolist()))
                if missing:
                    gaps.append({"game": str(g), "missing_pitch_no": missing[:20], "n_missing": len(missing)})
        c["pitch_no_gaps"] = gaps

    # mixed devices
    if "System" in raw:
        c["systems"] = sorted(raw["System"].dropna().astype(str).unique().tolist())
    if "Device Serial Number" in raw:
        c["device_serials"] = sorted(raw["Device Serial Number"].dropna().astype(str).unique().tolist())
    if "stadium" in norm:
        c["stadiums"] = sorted(norm["stadium"].dropna().astype(str).unique().tolist())[:10]
    multi = (len(c.get("systems", [])) > 1) or (len(c.get("device_serials", [])) > 1)
    if multi:
        rep["warnings"].append("More than one device/system in the file: compare pitchers within a device only.")

    # dates and timestamps
    if "game_date" in norm:
        dates = sorted(norm["game_date"].dropna().unique().tolist())
        c["dates"] = dates[:15]
        c["n_dates"] = len(dates)
        if any(d is None or str(d) == "NaT" for d in norm["game_date"].tolist()):
            rep["warnings"].append("Some dates failed to parse.")
    for col in ("UTCDateTime", "LocalDateTime", "UTCDate", "Date", "Time"):
        if col in raw:
            c.setdefault("timestamp_columns", []).append(col)
    if {"UTCDate", "Date"}.issubset(raw.columns):
        try:
            utc = pd.to_datetime(raw["UTCDate"], errors="coerce").dt.date
            loc = pd.to_datetime(raw["Date"], errors="coerce").dt.date
            c["rows_where_utc_date_differs_from_local"] = int((utc != loc).sum())
            if c["rows_where_utc_date_differs_from_local"]:
                rep["warnings"].append("UTC and local dates differ on some rows (night game past 00:00 UTC): "
                                       "group by LocalDateTime/Date, never UTCDate.")
        except Exception:  # pragma: no cover
            pass

    # which team is which
    if {"PitcherTeam", "HomeTeam", "AwayTeam", "Top/Bottom"}.issubset(raw.columns):
        top = raw["Top/Bottom"].astype(str).str.lower().str.startswith("top")
        expected = np.where(top, raw["HomeTeam"], raw["AwayTeam"])
        mismatch = raw["PitcherTeam"].astype(str) != pd.Series(expected, index=raw.index).astype(str)
        c["pitcher_team_inconsistent_with_half_inning"] = int(mismatch.sum())
        if mismatch.any():
            rep["warnings"].append("PitcherTeam disagrees with Top/Bottom + Home/Away on some rows: "
                                   "the operator may have swapped teams at setup.")

    # handedness
    if "p_throws" in norm:
        c["p_throws_values"] = norm["p_throws"].fillna("missing").astype(str).value_counts().to_dict()
        if "pitcher" in norm:
            two = norm.dropna(subset=["p_throws"]).groupby("pitcher")["p_throws"].nunique()
            c["pitchers_listed_with_both_hands"] = int((two > 1).sum())
    if decision.get("handedness_basis"):
        c["handedness_basis"] = decision["handedness_basis"]
        if "ASSUMED" in decision["handedness_basis"]:
            rep["warnings"].append(decision["handedness_basis"])

    # workload sanity
    if {"pitcher", "game_date"}.issubset(norm.columns):
        who = "pitcher" if norm["pitcher"].notna().any() else "player_name"
        per = norm.groupby([who, "game_date"]).size()
        c["max_pitches_one_pitcher_one_date"] = int(per.max()) if len(per) else 0
        if len(per) and per.max() > 130:
            rep["warnings"].append("A pitcher has >130 pitches on one date: duplicated file, or two pitchers under one ID.")

    # sign decision summary
    c["hb_sign_multiplier"] = decision.get("multiplier")
    c["hb_sign_n_fastballs"] = decision.get("n_fastballs")
    if decision.get("pfx_fields_frame"):
        c["pfx_fields_frame"] = decision["pfx_fields_frame"]
    if decision.get("location_units"):
        c["rapsodo_location_units"] = decision["location_units"]
    if decision.get("source") == "rapsodo":
        rep["warnings"].append("Rapsodo bullpen: 'description' is inferred from Is Strike (called_strike/ball). "
                               "Whiff%, CSW% and chase% from this file mean nothing; use velo, movement, spin, location.")

    # per-pitcher summary for eyeballing
    if {"player_name", "pitch_type", "release_speed"}.issubset(norm.columns):
        summ = (norm.groupby(["player_name", "p_throws", "pitch_type"])
                .agg(n=("release_speed", "size"), velo=("release_speed", "mean"),
                     ivb=("api_break_z_induced", "mean"), hb_arm=("api_break_x_arm", "mean"),
                     spin=("release_spin_rate", "mean"))
                .round(1).reset_index())
        rep["arsenal_preview"] = summ.to_dict(orient="records")

    rep["rows_with_any_flag"] = int((flags != "").sum())
    rep["flagged_rows"] = norm.loc[flags != "", [k for k in ("pitch_no", "pitch_uid", "player_name", "pitch_type",
                                                             "release_speed", "qc_flags") if k in norm]].head(40).to_dict(orient="records")
    return rep


def format_qc(rep: dict) -> str:
    lines = [f"QC report  source={rep['source']}  rows={rep['rows']}", f"  horizontal sign: {rep['hb_sign']}", "  checks:"]
    for k, v in rep["checks"].items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            lines.append(f"    {k}: {len(v)} entries -> {json.dumps(v)[:300]}")
        else:
            lines.append(f"    {k}: {v}")
    lines.append(f"  rows with any flag: {rep['rows_with_any_flag']}")
    if rep.get("warnings"):
        lines.append("  WARNINGS:")
        lines += [f"    - {w}" for w in rep["warnings"]]
    if rep.get("arsenal_preview"):
        lines.append("  arsenal preview (mean velo / IVB / arm-side HB / spin):")
        for r in rep["arsenal_preview"]:
            lines.append(f"    {str(r['player_name'])[:22]:22s} {r['p_throws']}  {r['pitch_type']:3s} n={r['n']:<4} "
                         f"{r['velo']:5.1f}  {r['ivb']:6.1f}  {r['hb_arm']:6.1f}  {r['spin']:7.0f}")
    if rep.get("flagged_rows"):
        lines.append("  first flagged rows:")
        for r in rep["flagged_rows"][:15]:
            lines.append("    " + ", ".join(f"{k}={v}" for k, v in r.items()))
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------

def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("detect", help="detect the export type from the header")
    d.add_argument("csv")

    n = sub.add_parser("normalize", help="write a Savant-style CSV")
    n.add_argument("csv")
    n.add_argument("out")
    n.add_argument("--source", default="auto", choices=["auto", "trackman", "rapsodo", "rapsodo_hitting", "savant"])
    n.add_argument("--flip-hb", action="store_true", help="force a horizontal sign flip (overrides auto-detect)")
    n.add_argument("--p-throws", choices=["R", "L"], help="pitcher hand for Rapsodo files (no hand column)")
    n.add_argument("--player-name", help="name to stamp on Rapsodo rows without one")
    n.add_argument("--drop-flagged", action="store_true", help="drop rows with untracked/impossible/duplicate flags")
    n.add_argument("--json", action="store_true", help="print the decision and QC as JSON")

    q = sub.add_parser("qc", help="print a QC report without writing anything")
    q.add_argument("csv")
    q.add_argument("--source", default="auto", choices=["auto", "trackman", "rapsodo", "rapsodo_hitting", "savant"])
    q.add_argument("--p-throws", choices=["R", "L"])
    q.add_argument("--json", action="store_true")

    t = sub.add_parser("tilt", help="spin axis degrees <-> clock tilt")
    t.add_argument("value")
    t.add_argument("--to-degrees", action="store_true")

    e = sub.add_parser("efficiency", help="spin efficiency / gyro from any two of total, true, efficiency")
    e.add_argument("--total", type=float)
    e.add_argument("--true", dest="true_spin", type=float)
    e.add_argument("--efficiency", type=float)

    a = ap.parse_args(argv)

    if a.cmd == "tilt":
        if a.to_degrees or ":" in a.value:
            print(json.dumps({"tilt": a.value, "spin_axis_deg": round(tilt_to_axis(a.value), 1)}))
        else:
            print(json.dumps({"spin_axis_deg": float(a.value), "tilt": axis_to_tilt(float(a.value))}))
        return
    if a.cmd == "efficiency":
        print(json.dumps(spin_efficiency(a.total, a.true_spin, a.efficiency), indent=2))
        return

    raw, hdr = read_any(a.csv)
    if a.cmd == "detect":
        det = detect(raw)
        det["header_row"] = hdr
        print(json.dumps(det, indent=2))
        return

    norm, dec = normalize(raw, a.source, getattr(a, "flip_hb", False), a.p_throws, getattr(a, "player_name", None))
    rep = qc_report(raw, norm, dec)
    if a.cmd == "qc":
        print(json.dumps(rep, indent=2, default=str) if a.json else format_qc(rep))
        return

    if a.drop_flagged:
        bad = norm["qc_flags"].fillna("").str.contains("untracked|impossible|duplicate")
        norm = norm[~bad]
        rep["rows_dropped"] = int(bad.sum())
    norm.to_csv(a.out, index=False)
    if a.json:
        print(json.dumps({"out": a.out, "rows": int(len(norm)), "decision": dec, "qc": rep}, indent=2, default=str))
    else:
        print(f"wrote {a.out}: {len(norm)} rows, {len(norm.columns)} columns (source={dec['source']})")
        print(f"horizontal sign: {dec['basis']}")
        if dec.get("pfx_fields_frame"):
            print(f"pfx/x0/vx0 fields: {dec['pfx_fields_frame']}")
        print(format_qc(rep))


if __name__ == "__main__":
    main()
