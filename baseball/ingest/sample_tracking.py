
"""Write FICTIONAL TrackMan-format and Rapsodo-format CSVs for tests and demos.

Everything here is invented: the pitchers (Cole Marbury, RHP, Westbrook State; Tate Ridgely, LHP,
Harlow College), the teams, the stadium, the IDs. The numbers are realistic in scale and describe
no real person. Never present the output as real data.

The TrackMan file uses TrackMan's native horizontal frame (positive toward the pitcher's right /
third-base side, so a RHP's arm-side run is POSITIVE HorzBreak) for RelSide, HorzBreak,
PlateLocSide and HorzApprAngle, and the PITCHf/x (catcher's-view) frame for x0/vx0/ax0/pfxx,
which is what the TrackMan glossary's example values imply. It plants these QC problems on purpose:
  3 exact duplicate rows            4 untracked pitches (blank radar fields, PitchCall present)
  2 impossible velocities           1 impossible spin rate, 1 impossible extension
  5 Low-confidence rows             6 TaggedPitchType vs AutoPitchType disagreements
  2 Undefined TaggedPitchType       2 rows with PitcherTeam swapped
  1 row with Balls = 4              2 InPlay rows with no ExitSpeed
  late-inning rows whose UTCDate is the next calendar day

Usage:
  python -m baseball.ingest.sample_tracking                 # writes sample_trackman.csv, sample_rapsodo.csv,
                                                  # sample_rapsodo_hitting.csv in the current directory
  python -m baseball.ingest.sample_tracking --out-dir /tmp/x
  python -m baseball.ingest.sample_tracking --seed 3 --pitches 300
"""
from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

TM_COLUMNS = [
    "PitchNo", "Date", "Time", "PAofInning", "PitchofPA", "Pitcher", "PitcherId", "PitcherThrows", "PitcherTeam",
    "Batter", "BatterId", "BatterSide", "BatterTeam", "PitcherSet", "Inning", "Top/Bottom", "Outs", "Balls", "Strikes",
    "TaggedPitchType", "AutoPitchType", "PitchCall", "KorBB", "TaggedHitType", "PlayResult", "OutsOnPlay", "RunsScored",
    "Notes", "RelSpeed", "VertRelAngle", "HorzRelAngle", "SpinRate", "SpinAxis", "Tilt", "RelHeight", "RelSide",
    "Extension", "VertBreak", "InducedVertBreak", "HorzBreak", "PlateLocHeight", "PlateLocSide", "ZoneSpeed",
    "VertApprAngle", "HorzApprAngle", "ZoneTime", "ExitSpeed", "Angle", "Direction", "HitSpinRate", "PositionAt110X",
    "PositionAt110Y", "PositionAt110Z", "Distance", "LastTrackedDistance", "Bearing", "HangTime", "pfxx", "pfxz",
    "x0", "y0", "z0", "vx0", "vy0", "vz0", "ax0", "ay0", "az0", "HomeTeam", "AwayTeam", "Stadium", "Level", "League",
    "GameID", "PitchUID", "EffectiveVelo", "MaxHeight", "MeasuredDuration", "SpeedDrop", "PitchLastMeasuredX",
    "PitchLastMeasuredY", "PitchLastMeasuredZ", "ContactPositionX", "ContactPositionY", "ContactPositionZ", "GameUID",
    "UTCDate", "UTCTime", "LocalDateTime", "UTCDateTime", "AutoHitType", "System", "HomeTeamForeignID",
    "AwayTeamForeignID", "GameForeignID", "Catcher", "CatcherId", "CatcherThrows", "CatcherTeam", "PlayID",
    "PitchReleaseConfidence", "PitchLocationConfidence", "PitchMovementConfidence", "HitLaunchConfidence",
    "HitLandingConfidence", "CatcherThrowCatchConfidence", "CatcherThrowReleaseConfidence",
    "CatcherThrowLocationConfidence",
]

# pitch: (share, velo, sd, ivb_in, hb_armside_in, spin, axis_deg_for_RHP, tagged, auto)
RHP_ARSENAL = {
    "FF": (0.48, 92.8, 1.0, 16.5, 9.0, 2320, 212, "Fastball", "Four-Seam"),
    "SL": (0.27, 84.6, 1.1, 2.5, -6.5, 2510, 75, "Slider", "Slider"),
    "CU": (0.10, 78.1, 1.2, -10.0, -9.5, 2620, 30, "Curveball", "Curveball"),
    "CH": (0.15, 84.9, 1.0, 8.5, 14.5, 1740, 240, "ChangeUp", "Changeup"),
}
LHP_ARSENAL = {
    "SI": (0.50, 89.9, 1.0, 9.0, 15.5, 2080, 232, "Sinker", "Sinker"),
    "ST": (0.30, 80.2, 1.1, 0.5, -15.0, 2650, 95, "Slider", "Slider"),   # a sweeper tagged as Slider
    "CH": (0.20, 81.0, 1.0, 6.0, 14.0, 1690, 250, "ChangeUp", "Changeup"),
}
TILT_MINUTES = (0, 15, 30, 45)


def axis_to_tilt(axis: float) -> str:
    hours = ((axis - 180.0) / 30.0 + 12.0) % 12.0
    q = int(round(hours * 4)) % 48
    h, m = divmod(q, 4)
    return f"{12 if h == 0 else h}:{m * 15:02d}"


G = 32.174
PLATE_Y = 17.0 / 12.0


def kinematics(velo_mph: float, rel_h: float, rel_side_native: float, ext: float, loc_h: float,
               loc_side_native: float, ivb_in: float, hb_native_in: float, rng: np.random.Generator) -> dict:
    """Constant-acceleration flight consistent with release, plate location and full-flight break.

    Catcher's-view frame for the PITCHf/x fields (x = -native). Returns VAA/HAA at the front of the
    plate, pfx over the last 40 ft, the y = 50 ft state vector, zone speed and zone time.
    """
    x_rel, z_rel, y_rel = -rel_side_native, rel_h, 60.5 - ext
    x_p, z_p = -loc_side_native, loc_h
    v0 = velo_mph * 1.46667
    ay = float(rng.normal(27.0, 1.2))                     # drag decelerates the ball (positive ay, vy negative)
    vy_rel = -v0 * 0.997
    # flight time release -> front of plate: PLATE_Y = y_rel + vy_rel*T + 0.5*ay*T^2
    a, b, c = 0.5 * ay, vy_rel, y_rel - PLATE_Y
    T = (-b - np.sqrt(b * b - 4 * a * c)) / (2 * a)
    ax = 2 * (-hb_native_in / 12.0) / T ** 2            # full-flight break = 0.5*a*T^2
    az = -G + 2 * (ivb_in / 12.0) / T ** 2
    vx_rel = (x_p - x_rel - 0.5 * ax * T ** 2) / T
    vz_rel = (z_p - z_rel - 0.5 * az * T ** 2) / T
    # state at y = 50
    c50 = y_rel - 50.0
    t50 = (-b - np.sqrt(b * b - 4 * a * c50)) / (2 * a)
    x0 = x_rel + vx_rel * t50 + 0.5 * ax * t50 ** 2
    z0 = z_rel + vz_rel * t50 + 0.5 * az * t50 ** 2
    vx0, vy0, vz0 = vx_rel + ax * t50, vy_rel + ay * t50, vz_rel + az * t50
    # at the plate
    vx_f, vy_f, vz_f = vx_rel + ax * T, vy_rel + ay * T, vz_rel + az * T
    vaa = -np.degrees(np.arctan(vz_f / vy_f))
    haa_c = -np.degrees(np.arctan(vx_f / vy_f))
    # last 40 ft
    c40 = y_rel - (PLATE_Y + 40.0)
    t_enter = (-b - np.sqrt(b * b - 4 * a * c40)) / (2 * a)
    t40 = T - t_enter
    pfxx = 0.5 * ax * t40 ** 2 * 12.0
    pfxz = 0.5 * (az + G) * t40 ** 2 * 12.0
    return dict(vaa=float(vaa), haa_native=float(-haa_c), zone_speed=float(-vy_f / 1.46667), zone_time=float(T),
                pfxx=float(pfxx), pfxz=float(pfxz), x0=float(x0), z0=float(z0), vx0=float(vx0), vy0=float(vy0),
                vz0=float(vz0), ax=float(ax), ay=ay, az=float(az))


def build_trackman(rng: np.random.Generator, n_pitches: int) -> pd.DataFrame:
    home, away, stadium = "WES_STA", "HAR_COL", "Fictional Field"
    game_id, game_uid = "20260314-FictionalField-1", str(uuid.uuid4())
    start_local = datetime(2026, 3, 14, 19, 2, 0)   # 7:02 pm local, UTC-4 -> UTC rolls past midnight ~8 pm
    utc_offset = timedelta(hours=4)
    rhp = dict(name="Marbury, Cole", id=9001001, hand="Right", team=home)   # home pitcher
    lhp = dict(name="Ridgely, Tate", id=9001002, hand="Left", team=away)    # away pitcher
    batters_home = [(f"Home Hitter {i}", 9100100 + i, rng.choice(["Right", "Left"], p=[0.6, 0.4])) for i in range(1, 10)]
    batters_away = [(f"Away Hitter {i}", 9100200 + i, rng.choice(["Right", "Left"], p=[0.6, 0.4])) for i in range(1, 10)]

    rows, pitch_no, t = [], 0, start_local
    inning, half = 1, "Top"
    lineup_idx = {"Top": 0, "Bottom": 0}
    while pitch_no < n_pitches:
        pitcher = rhp if half == "Top" else lhp          # Top: away bats, home (RHP) pitches
        arsenal = RHP_ARSENAL if pitcher is rhp else LHP_ARSENAL
        lineup = batters_away if half == "Top" else batters_home
        outs = 0
        pa_of_inning = 0
        while outs < 3 and pitch_no < n_pitches:
            pa_of_inning += 1
            bname, bid, bside = lineup[lineup_idx[half] % 9]
            lineup_idx[half] += 1
            balls = strikes = 0
            pitch_of_pa = 0
            while True:
                pitch_of_pa += 1
                pitch_no += 1
                t += timedelta(seconds=int(rng.integers(14, 26)))
                keys = list(arsenal)
                pt = rng.choice(keys, p=[arsenal[k][0] for k in keys])
                share, v, sd, ivb, hb_arm, spin, axis, tagged, auto = arsenal[pt]
                velo = rng.normal(v, sd)
                ivb_i = rng.normal(ivb, 1.4)
                hb_arm_i = rng.normal(hb_arm, 1.6)
                hand_sign = 1.0 if pitcher is rhp else -1.0     # TrackMan native: RHP arm side positive
                hb_native = hand_sign * hb_arm_i
                spin_i = rng.normal(spin, 70)
                axis_i = (axis if pitcher is rhp else (360 - axis)) + rng.normal(0, 6)
                axis_i %= 360
                rel_h = rng.normal(5.85 if pitcher is rhp else 5.6, 0.07)
                rel_side_native = hand_sign * rng.normal(2.1 if pitcher is rhp else 2.4, 0.08)
                ext = rng.normal(6.6 if pitcher is rhp else 6.2, 0.15)
                # location (native frame); fastballs more often in zone
                in_zone = rng.random() < (0.55 if pt in ("FF", "SI") else 0.43)
                if in_zone:
                    loc_side_native = rng.uniform(-0.7, 0.7)
                    loc_h = rng.uniform(1.6, 3.4)
                else:
                    loc_side_native = rng.choice([rng.uniform(-1.7, -0.8), rng.uniform(0.8, 1.7), rng.uniform(-0.9, 0.9)])
                    loc_h = rng.choice([rng.uniform(0.3, 1.4), rng.uniform(3.6, 4.5), rng.uniform(1.5, 3.5)])
                kin = kinematics(velo, rel_h, rel_side_native, ext, loc_h, loc_side_native, ivb_i, hb_native, rng)
                vaa, haa_native, zone_speed, zone_time = kin["vaa"], kin["haa_native"], kin["zone_speed"], kin["zone_time"]
                vert_break = ivb_i - rng.normal(34, 2.5)   # gravity adds ~ -30 to -40 in over the flight

                # outcome
                swing_p = 0.68 if in_zone else 0.28
                exit_speed = angle = direction = hit_spin = dist = np.nan
                tagged_hit = play = korbb = "Undefined"
                outs_on_play = runs = 0
                if rng.random() < swing_p:
                    whiff_p = {"FF": 0.20, "SI": 0.14, "SL": 0.36, "ST": 0.40, "CU": 0.33, "CH": 0.30}[pt] * (0.8 if in_zone else 1.5)
                    r = rng.random()
                    if r < whiff_p:
                        call = "StrikeSwinging"
                    elif r < whiff_p + 0.45:
                        call = "FoulBall"
                    else:
                        call = "InPlay"
                        exit_speed = float(np.clip(rng.normal(86, 11), 45, 112))
                        angle = float(rng.normal(11, 22))
                        direction = float(rng.normal(0, 25))
                        hit_spin = float(rng.normal(2200, 600))
                        tagged_hit = "GroundBall" if angle < 8 else ("LineDrive" if angle < 25 else ("FlyBall" if angle < 50 else "Popup"))
                        dist = float(max(5, 0.012 * exit_speed ** 2 * np.sin(np.radians(max(2 * angle, 1))) + rng.normal(0, 15)))
                        hit_prob = 0.68 if tagged_hit == "LineDrive" else (0.24 if tagged_hit == "GroundBall" else 0.18)
                        if rng.random() < hit_prob:
                            play = rng.choice(["Single", "Double", "Triple", "HomeRun"], p=[0.68, 0.22, 0.02, 0.08])
                            runs = 1 if play == "HomeRun" else 0
                        else:
                            play = rng.choice(["Out", "Error", "FieldersChoice"], p=[0.9, 0.05, 0.05])
                            outs_on_play = 1 if play != "Error" else 0
                else:
                    if in_zone:
                        call = "StrikeCalled"
                    else:
                        call = rng.choice(["BallCalled", "BallinDirt", "HitByPitch"], p=[0.9, 0.08, 0.02])

                catcher = ("Fictional Catcher H", 9200001, home) if pitcher is rhp else ("Fictional Catcher A", 9200002, away)
                utc = t + utc_offset
                row = dict(
                    PitchNo=pitch_no, Date=t.strftime("%m/%d/%Y"), Time=t.strftime("%H:%M:%S.%f")[:-4],
                    PAofInning=pa_of_inning, PitchofPA=pitch_of_pa, Pitcher=pitcher["name"], PitcherId=pitcher["id"],
                    PitcherThrows=pitcher["hand"], PitcherTeam=pitcher["team"], Batter=bname, BatterId=bid,
                    BatterSide=bside, BatterTeam=away if half == "Top" else home, PitcherSet="Undefined",
                    Inning=inning, **{"Top/Bottom": half}, Outs=outs, Balls=balls, Strikes=strikes,
                    TaggedPitchType=tagged, AutoPitchType=auto, PitchCall=call, KorBB=korbb,
                    TaggedHitType=tagged_hit, PlayResult=play, OutsOnPlay=outs_on_play, RunsScored=runs, Notes="",
                    RelSpeed=round(velo, 2), VertRelAngle=round(rng.normal(-1.8, 0.5), 2),
                    HorzRelAngle=round(hand_sign * rng.normal(-2.2, 0.5), 2), SpinRate=round(spin_i, 1),
                    SpinAxis=round(axis_i, 1), Tilt=axis_to_tilt(axis_i), RelHeight=round(rel_h, 3),
                    RelSide=round(rel_side_native, 3), Extension=round(ext, 3), VertBreak=round(vert_break, 2),
                    InducedVertBreak=round(ivb_i, 2), HorzBreak=round(hb_native, 2), PlateLocHeight=round(loc_h, 3),
                    PlateLocSide=round(loc_side_native, 3), ZoneSpeed=round(zone_speed, 2), VertApprAngle=round(vaa, 2),
                    HorzApprAngle=round(haa_native, 2), ZoneTime=round(zone_time, 4),
                    ExitSpeed=round(exit_speed, 2) if not np.isnan(exit_speed) else np.nan,
                    Angle=round(angle, 2) if not np.isnan(angle) else np.nan,
                    Direction=round(direction, 2) if not np.isnan(direction) else np.nan,
                    HitSpinRate=round(hit_spin, 1) if not np.isnan(hit_spin) else np.nan,
                    PositionAt110X=np.nan, PositionAt110Y=np.nan, PositionAt110Z=np.nan,
                    Distance=round(dist, 1) if not np.isnan(dist) else np.nan,
                    LastTrackedDistance=round(dist * 0.9, 1) if not np.isnan(dist) else np.nan,
                    Bearing=round(direction * 0.9, 2) if not np.isnan(direction) else np.nan,
                    HangTime=round(max(0.3, angle / 12), 2) if not np.isnan(angle) else np.nan,
                    # PITCHf/x-style fields in the catcher's view (x opposite to the native frame), physically
                    # consistent with the release point, plate location and break above
                    pfxx=round(kin["pfxx"], 2), pfxz=round(kin["pfxz"], 2),
                    x0=round(kin["x0"], 3), y0=50.0, z0=round(kin["z0"], 3),
                    vx0=round(kin["vx0"], 2), vy0=round(kin["vy0"], 2), vz0=round(kin["vz0"], 2),
                    ax0=round(kin["ax"], 2), ay0=round(kin["ay"], 2), az0=round(kin["az"], 2),
                    HomeTeam=home, AwayTeam=away, Stadium=stadium, Level="D1", League="FICT", GameID=game_id,
                    PitchUID=str(uuid.uuid4()), EffectiveVelo=round(velo + (ext - 6.5) * 1.5, 2),
                    MaxHeight=np.nan, MeasuredDuration=np.nan, SpeedDrop=round(zone_speed - velo, 2),
                    PitchLastMeasuredX=np.nan, PitchLastMeasuredY=np.nan, PitchLastMeasuredZ=np.nan,
                    ContactPositionX=np.nan, ContactPositionY=np.nan, ContactPositionZ=np.nan, GameUID=game_uid,
                    UTCDate=utc.strftime("%m/%d/%Y"), UTCTime=utc.strftime("%H:%M:%S.%f")[:-4],
                    LocalDateTime=t.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4], UTCDateTime=utc.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + "Z",
                    AutoHitType=tagged_hit if tagged_hit != "Undefined" else "", System="v3",
                    HomeTeamForeignID="", AwayTeamForeignID="", GameForeignID="",
                    Catcher=catcher[0], CatcherId=catcher[1], CatcherThrows="Right", CatcherTeam=catcher[2],
                    PlayID=str(uuid.uuid4()), PitchReleaseConfidence="High", PitchLocationConfidence="High",
                    PitchMovementConfidence="High", HitLaunchConfidence="High" if call == "InPlay" else "",
                    HitLandingConfidence="Medium" if call == "InPlay" else "", CatcherThrowCatchConfidence="",
                    CatcherThrowReleaseConfidence="", CatcherThrowLocationConfidence="",
                )
                rows.append(row)

                # advance the count / PA
                if call in ("BallCalled", "BallinDirt"):
                    balls += 1
                    if balls == 4:
                        row["KorBB"] = "Walk"
                        break
                elif call == "HitByPitch":
                    break
                elif call in ("StrikeCalled", "StrikeSwinging"):
                    strikes += 1
                    if strikes == 3:
                        row["KorBB"] = "Strikeout"
                        outs += 1
                        break
                elif call == "FoulBall":
                    strikes = min(2, strikes + 1)
                else:  # InPlay
                    outs += outs_on_play
                    break
            if outs >= 3:
                break
        half = "Bottom" if half == "Top" else "Top"
        if half == "Top":
            inning += 1

    df = pd.DataFrame(rows, columns=TM_COLUMNS)
    df = plant_problems(df, rng)
    return df


def plant_problems(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    n = len(df)
    radar_cols = ["RelSpeed", "VertRelAngle", "HorzRelAngle", "SpinRate", "SpinAxis", "Tilt", "RelHeight", "RelSide",
                  "Extension", "VertBreak", "InducedVertBreak", "HorzBreak", "PlateLocHeight", "PlateLocSide",
                  "ZoneSpeed", "VertApprAngle", "HorzApprAngle", "ZoneTime", "pfxx", "pfxz", "x0", "y0", "z0",
                  "vx0", "vy0", "vz0", "ax0", "ay0", "az0", "EffectiveVelo", "SpeedDrop"]
    pool = np.array([i for i in range(10, n - 10) if not 38 <= i <= 45])   # keep clear of the duplicated block
    idx = rng.choice(pool, size=26, replace=False)
    untracked, impossible_v, spin_i, ext_i, lowconf, disagree, undefined, teamswap, balls4, bip = (
        idx[0:4], idx[4:6], idx[6], idx[7], idx[8:13], idx[13:19], idx[19:21], idx[21:23], idx[23], idx[24:26])
    df.loc[untracked, radar_cols] = np.nan
    df.loc[untracked, ["PitchReleaseConfidence", "PitchLocationConfidence", "PitchMovementConfidence"]] = ""
    df.loc[impossible_v[0], "RelSpeed"] = 125.3
    df.loc[impossible_v[1], "RelSpeed"] = 38.2
    df.loc[spin_i, "SpinRate"] = 4100.0
    df.loc[ext_i, "Extension"] = 9.4
    df.loc[lowconf, "PitchMovementConfidence"] = "Low"
    df.loc[lowconf[:2], "PitchLocationConfidence"] = "Low"
    for i in disagree:
        df.loc[i, "AutoPitchType"] = "Cutter" if df.loc[i, "TaggedPitchType"] in ("Fastball", "Sinker") else "Four-Seam"
    df.loc[undefined, "TaggedPitchType"] = "Undefined"
    df.loc[teamswap, "PitcherTeam"] = np.where(df.loc[teamswap, "PitcherTeam"] == "WES_STA", "HAR_COL", "WES_STA")
    df.loc[balls4, "Balls"] = 4
    # two balls in play the radar did not pick up
    inplay = df.index[df["PitchCall"] == "InPlay"]
    if len(inplay) >= 2:
        pick = rng.choice(inplay, size=2, replace=False)
        df.loc[pick, ["ExitSpeed", "Angle", "Direction", "HitSpinRate", "Distance", "LastTrackedDistance", "Bearing", "HangTime"]] = np.nan
        df.loc[pick, "HitLaunchConfidence"] = ""
    # three exact duplicate rows (an operator re-uploaded a chunk)
    dup = df.iloc[[40, 41, 42]].copy()
    df = pd.concat([df.iloc[:43], dup, df.iloc[43:]], ignore_index=True)
    return df


def build_rapsodo(rng: np.random.Generator, n: int = 45) -> str:
    """Rapsodo Pitching 2.0-style export: metadata lines, then a header, then rows. Returns CSV text."""
    arsenal = {  # label: (share, velo, sd, total_spin, eff, dir_hours, vb_in, hb_in_pitcher_view, gyro)
        "Fastball": (0.45, 91.6, 1.0, 2280, 0.93, 1.0, 16.0, 9.5, 22),
        "Slider": (0.25, 83.9, 1.0, 2450, 0.45, 9.0, 1.5, -7.0, 63),
        "Curveball": (0.10, 77.5, 1.1, 2600, 0.82, 7.0, -11.0, -8.0, 35),
        "ChangeUp": (0.20, 84.2, 1.0, 1720, 0.90, 2.0, 7.5, 15.0, 26),
    }
    rows = []
    base = datetime(2026, 2, 20, 15, 10)
    for i in range(1, n + 1):
        keys = list(arsenal)
        pt = rng.choice(keys, p=[arsenal[k][0] for k in keys])
        _, v, sd, spin, eff, hours, vb, hb, gyro = arsenal[pt]
        total = rng.normal(spin, 80)
        eff_i = float(np.clip(rng.normal(eff, 0.04), 0.05, 1.0))
        h = (hours + rng.normal(0, 0.25)) % 12
        hh, mm = int(h), int(round((h - int(h)) * 60 / 15) * 15) % 60
        hh = 12 if hh == 0 else hh
        side_in = rng.normal(0, 7)
        height_in = rng.normal(30, 7)
        rows.append({
            "No": i, "Date": (base + timedelta(seconds=25 * i)).strftime("%m/%d/%Y %H:%M:%S"),
            "Pitch ID": f"RP-{200000 + i}", "Pitch Type": pt,
            "Is Strike": "TRUE" if (abs(side_in) <= 8.5 and 18 <= height_in <= 42) else "FALSE",
            "Strike Zone Side": round(side_in, 1), "Strike Zone Height": round(height_in, 1),
            "Velocity": round(rng.normal(v, sd), 1), "Total Spin": round(total),
            "True Spin": round(total * eff_i), "Spin Efficiency (release)": round(100 * eff_i, 1),
            "Spin Direction": f"{hh}:{mm:02d}", "Spin Confidence": round(float(np.clip(rng.normal(0.9, 0.08), 0.3, 1.0)), 2),
            "VB (trajectory)": round(rng.normal(vb, 1.5), 1), "HB (trajectory)": round(rng.normal(hb, 1.6), 1),
            "SSW VB": round(rng.normal(0.5, 0.8), 1), "SSW HB": round(rng.normal(1.0 if pt == "ChangeUp" else 0.2, 0.8), 1),
            "Horizontal Angle": round(rng.normal(-2.0, 0.6), 1), "Release Angle": round(rng.normal(-1.5, 0.5), 1),
            "Release Height": round(rng.normal(5.8, 0.08), 2), "Release Side": round(rng.normal(2.0, 0.08), 2),
            "Release Extension": round(rng.normal(6.4, 0.15), 2),
            "Gyro Degree (deg)": round(np.degrees(np.arccos(eff_i)), 1), "Unique ID": f"u-{uuid.uuid4().hex[:12]}",
            "Device Serial Number": "RP2-FICT-0001", "Session Name": "Pen 2/20 (fictional)", "Player Name": "Marbury, Cole",
        })
    # plant: one spin-confidence problem and one impossible velocity
    rows[7]["Spin Confidence"] = 0.31
    rows[19]["Velocity"] = 118.4
    df = pd.DataFrame(rows)
    meta = ["Rapsodo Pitching export (FICTIONAL sample for tests)", "Player Name,Marbury\\, Cole", "Session,Pen 2/20 (fictional)", ""]
    return "\n".join(meta) + "\n" + df.to_csv(index=False)


def build_rapsodo_hitting(rng: np.random.Generator, n: int = 30) -> str:
    rows = []
    base = datetime(2026, 2, 21, 14, 0)
    for i in range(1, n + 1):
        ev = float(np.clip(rng.normal(88, 8), 55, 110))
        la = float(rng.normal(12, 18))
        rows.append({
            "No": i, "Date": (base + timedelta(seconds=20 * i)).strftime("%m/%d/%Y %H:%M:%S"),
            "Hit ID": f"RH-{300000 + i}", "Player Name": "Fictional Hitter A", "Pitch Type": "Fastball",
            "Pitch Velocity": round(rng.normal(70, 3), 1), "Exit Velocity": round(ev, 1), "Launch Angle": round(la, 1),
            "Exit Direction": round(rng.normal(0, 20), 1),
            "Distance": round(max(5, 0.012 * ev ** 2 * np.sin(np.radians(max(2 * la, 1))) + rng.normal(0, 12)), 0),
            "Spin": round(rng.normal(2100, 500)), "Spin Axis": round(rng.normal(180, 40)),
            "Hit Type": "GroundBall" if la < 8 else ("LineDrive" if la < 25 else ("FlyBall" if la < 50 else "PopUp")),
            "Session Name": "BP 2/21 (fictional)", "Device Serial Number": "RH2-FICT-0002",
        })
    df = pd.DataFrame(rows)
    meta = ["Rapsodo Hitting export (FICTIONAL sample for tests)", "Player Name,Fictional Hitter A", ""]
    return "\n".join(meta) + "\n" + df.to_csv(index=False)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--pitches", type=int, default=215)
    a = ap.parse_args()
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(a.seed)
    tm = build_trackman(rng, a.pitches)
    tm.to_csv(out / "sample_trackman.csv", index=False)
    (out / "sample_rapsodo.csv").write_text(build_rapsodo(rng), encoding="utf-8")
    (out / "sample_rapsodo_hitting.csv").write_text(build_rapsodo_hitting(rng), encoding="utf-8")
    print(f"wrote {out / 'sample_trackman.csv'} ({len(tm)} rows, fictional)")
    print(f"wrote {out / 'sample_rapsodo.csv'} (fictional)")
    print(f"wrote {out / 'sample_rapsodo_hitting.csv'} (fictional)")


if __name__ == "__main__":
    main()
