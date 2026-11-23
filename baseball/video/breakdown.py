"""A hitter's home-run swings, frame by frame: what the center-field camera shows across seasons, joined to Statcast's
bat tracking on the same pitches.

Pipeline: clips.py finds MLB's clip of every home run, pose.py tracks the batter through the pitch view, measure.py
turns the joints into timing and posture, and this module puts them together by season, draws the figures from the
measured joints (no frame of MLB video is reproduced), and writes the table the report quotes.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from baseball.video import measure as M
from baseball.video.pose import IDX

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "video"
OUT = ROOT / "reports" / "outputs"
FIG = ROOT / "reports" / "figures"
MEASURES = ["down_to_contact_ms", "lift_to_contact_ms", "hip_lead_ms", "head_drop", "shoulder_tilt"]
SEQ_COLS = ["game_pk", "at_bat_number", "events", "bat_speed", "swing_length", "attack_angle", "launch_speed",
            "launch_angle", "pitch_type", "release_speed", "plate_x", "plate_z", "stand", "game_date"]
BONES = [(5, 6), (5, 7), (7, 9), (6, 8), (8, 10), (5, 11), (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16)]


def statcast_rows(batter: int) -> pd.DataFrame:
    d = pd.concat([pd.read_parquet(p, columns=SEQ_COLS) for p in sorted((ROOT / "data" / "seq").glob("seq_*.parquet"))])
    return d[(d.events == "home_run")].assign(batter=batter) if False else d[d.events == "home_run"]


def table(name: str, batter: int, stand: str = "R") -> pd.DataFrame:
    rows = json.loads((RAW / f"{name}_hr.json").read_text())
    ex_file = OUT / f"{name}_excluded_by_eye.json"
    excluded = {e["play_id"] for e in json.loads(ex_file.read_text())["excluded"]} if ex_file.exists() else set()
    sc = pd.concat([pd.read_parquet(p, columns=SEQ_COLS + ["batter"]) for p in sorted((ROOT / "data" / "seq").glob("seq_*.parquet"))])
    sc = sc[(sc.batter == batter) & (sc.events == "home_run")]
    out = []
    for r in rows:
        f = RAW / "pose" / f"{r['play_id']}.npz"
        if not f.exists():
            continue
        z = np.load(f)
        m = None if r["play_id"] in excluded else M.measure(z["keypoints"], float(z["fps"]), stand)
        s = sc[(sc.game_pk == r["game_pk"]) & (sc.at_bat_number == r["at_bat_index"] + 1)]
        rec = dict(play_id=r["play_id"], game_pk=r["game_pk"], page=r.get("page"), headline=r.get("headline"),
                   batter_px=float(z["batter_px"]), measured=m is not None)
        if len(s):
            s = s.iloc[0]
            rec.update(season=int(str(s.game_date)[:4]), date=str(s.game_date)[:10], bat_speed=s.bat_speed,
                       swing_length=s.swing_length, attack_angle=s.attack_angle, launch_speed=s.launch_speed,
                       launch_angle=s.launch_angle, pitch_type=s.pitch_type, pitch_speed=s.release_speed,
                       plate_x=s.plate_x, plate_z=s.plate_z)
        if m:
            rec.update(m)
        out.append(rec)
    return pd.DataFrame(out)


def by_season(t: pd.DataFrame) -> pd.DataFrame:
    m = t[t.measured]
    rows = []
    for s, g in m.groupby("season"):
        r = dict(season=int(s), n=int(len(g)))
        for c in MEASURES + ["bat_speed", "attack_angle", "launch_speed"]:
            v = g[c].dropna()
            r[c] = float(v.median()) if len(v) else np.nan
            r[c + "_n"] = int(len(v))
        rows.append(r)
    return pd.DataFrame(rows)


def permutation(t: pd.DataFrame, col: str, a=(2024, 2025), b=(2026,), reps: int = 20000, seed: int = 5) -> dict:
    """Median of season(s) b minus median of a, and a two-sided permutation p-value."""
    m = t[t.measured & t[col].notna()]
    x, y = m[m.season.isin(a)][col].to_numpy(), m[m.season.isin(b)][col].to_numpy()
    if len(x) < 5 or len(y) < 5:
        return dict(n_a=int(len(x)), n_b=int(len(y)))
    obs = np.median(y) - np.median(x)
    pool = np.concatenate([x, y])
    rng = np.random.default_rng(seed)
    hits = 0
    for _ in range(reps):
        rng.shuffle(pool)
        hits += abs(np.median(pool[len(x):]) - np.median(pool[:len(x)])) >= abs(obs) - 1e-12
    return dict(n_a=int(len(x)), n_b=int(len(y)), diff=float(obs), p=float(hits / reps))


def detectable(t: pd.DataFrame, col: str, a=(2024, 2025), b=(2026,), reps: int = 4000, seed: int = 1,
               frame_ms: float = 1000 / 59.94) -> float:
    """The smallest change in a median this sample would detect about 80% of the time: 2.8 times the bootstrap
    spread of the median difference, and never less than one frame."""
    m = t[t.measured & t[col].notna()]
    x, y = m[m.season.isin(a)][col].to_numpy(), m[m.season.isin(b)][col].to_numpy()
    if len(x) < 5 or len(y) < 5:
        return float("nan")
    rng = np.random.default_rng(seed)
    d = [np.median(rng.choice(y, len(y))) - np.median(rng.choice(x, len(x))) for _ in range(reps)]
    v = 2.8 * float(np.std(d))
    return max(v, frame_ms) if col.endswith("_ms") else v


def normalized(kp: np.ndarray, frame: int, height: float, stance_hips: np.ndarray, flip: bool) -> np.ndarray:
    """Joints at `frame` in batter heights, origin at the stance hip center, y up; mirrored for a left-handed hitter."""
    p = kp[frame, :, :2].copy()
    p = (p - stance_hips) / height
    p[:, 1] *= -1
    if flip:
        p[:, 0] *= -1
    return p


def average_poses(t: pd.DataFrame, seasons, stand: str = "R") -> dict[str, np.ndarray]:
    """Median skeleton at four moments (stance, foot down, hips square, contact) over the season(s)' swings."""
    moments = {"stance": [], "foot down": [], "hips square": [], "contact": []}
    for _, r in t[t.measured & t.season.isin(seasons)].iterrows():
        z = np.load(RAW / "pose" / f"{r.play_id}.npz")
        kp, fps = z["keypoints"], float(z["fps"])
        c = int(r.contact_frame)
        st = np.arange(max(0, c - int(1.25 * fps)), c - int(0.6 * fps))
        hips = np.nanmedian(np.nanmean(kp[st][:, [IDX["l_hip"], IDX["r_hip"]], :2], axis=1), axis=0)
        frames = {"stance": int(st[len(st) // 2]), "contact": c,
                  "foot down": c - int(round(r.down_to_contact_ms * fps / 1000)) if np.isfinite(r.down_to_contact_ms) else None,
                  "hips square": int(r.hips_square) if np.isfinite(r.hips_square) else None}
        for k, f in frames.items():
            if f is not None and 0 <= f < len(kp) and np.isfinite(kp[f, 0, 0]):
                moments[k].append(normalized(kp, f, r.torso_px, hips, stand == "L"))
    return {k: np.nanmedian(np.stack(v), axis=0) for k, v in moments.items() if v}


def figure(t: pd.DataFrame, name: str, path: Path, early=(2024, 2025), late=(2026,), stand: str = "R") -> Path:
    """Left: the median skeleton at four moments, early seasons vs late, drawn from the measured joints.
    Right: each home run's timing and posture by season."""
    import matplotlib.pyplot as plt
    from baseball import house
    house.apply()
    fig = plt.figure(figsize=(12, 7.2))
    gs = fig.add_gridspec(2, 4, height_ratios=[1.6, 1], hspace=0.35, wspace=0.3)
    poses = {lab: average_poses(t, s, stand) for lab, s in ((f"{early[0]}-{str(early[-1])[2:]}", early), (str(late[0]), late))}
    cols = dict(zip(poses, [house.SERIES[0], house.SERIES[1]]))
    for j, mom in enumerate(["stance", "foot down", "hips square", "contact"]):
        ax = fig.add_subplot(gs[0, j])
        for lab, P in poses.items():
            if mom not in P:
                continue
            p = P[mom]
            for a, b in BONES:
                ax.plot(p[[a, b], 0], p[[a, b], 1], color=cols[lab], lw=2.2, alpha=0.85, solid_capstyle="round")
            ax.scatter(p[0, 0], p[0, 1], s=90, color=cols[lab], zorder=3)
            if mom in ("stance", "contact"):
                ax.axhline(p[0, 1], color=cols[lab], lw=0.9, ls=(0, (3, 3)), alpha=0.8)
        ax.set_title(mom.capitalize(), fontsize=11)
        ax.set_aspect("equal")
        ax.set_xlim(-1.5, 1.5)
        ax.set_ylim(-2.9, 1.7)
        ax.axis("off")
    fig.axes[0].legend(handles=[plt.Line2D([], [], color=c, lw=2.5, label=l) for l, c in cols.items()], loc="lower left",
                       fontsize=9, frameon=False)
    fig.axes[3].text(0, -2.85, "Dashed: head height. Smaller drop in 2026;\ncamera or him, unresolved.", ha="center", fontsize=8.5,
                     color=house.MUTED)
    labels = {"down_to_contact_ms": "Foot down to contact (ms)", "hip_lead_ms": "Hips ahead of shoulders (ms)",
              "head_drop": "Head drop (torso lengths)", "shoulder_tilt": "Shoulder tilt at contact (deg)"}
    m = t[t.measured]
    seasons = sorted(m.season.dropna().unique())
    rng = np.random.default_rng(2)
    for j, (c, lab) in enumerate(labels.items()):
        ax = fig.add_subplot(gs[1, j])
        for i, s in enumerate(seasons):
            v = m[m.season == s][c].dropna()
            ax.scatter(i + rng.uniform(-0.12, 0.12, len(v)), v, s=16, alpha=0.7, lw=0,
                       color=house.SERIES[1] if s in late else house.SERIES[0])
            if len(v):
                ax.hlines(v.median(), i - 0.25, i + 0.25, color=house.INK, lw=1.4)
        ax.set_xticks(range(len(seasons)), [str(int(s)) for s in seasons])
        ax.set_title(lab, fontsize=10)
        ax.grid(True, axis="y", lw=0.5)
    fig.suptitle(f"{name}'s home-run swings from the center-field camera, measured frame by frame", x=0.02, ha="left",
                 fontsize=13, fontweight="bold")
    fig.text(0.02, 0.005, "Figures drawn from pose keypoints measured on MLB's highlight clips (59.94 fps); no video frames "
             "reproduced. Lines = medians.", fontsize=8.5, color=house.MUTED)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path


def trajectory(t: pd.DataFrame, seasons, pre: int = 60, post: int = 12, stand: str = "R") -> tuple[np.ndarray, int]:
    """Median skeleton frame by frame from `pre` frames before contact to `post` after, over the season(s)' measured
    swings, aligned on contact and normalized (torso lengths, origin at the opening hip center, y up). Returns the
    (frames, 17, 2) array and how many swings fed it."""
    stack = []
    for _, r in t[t.measured & t.season.isin(seasons)].iterrows():
        kp = np.load(RAW / "pose" / f"{r.play_id}.npz")["keypoints"]
        c = int(r.contact_frame)
        if c - pre < 0 or c + post >= len(kp):
            continue
        tracked = M.last_shot(kp)
        open_ = tracked[tracked < int(r.shoulders_square) - 20][:15]
        if not len(open_):
            continue
        hips = np.nanmedian(np.nanmean(kp[open_][:, [IDX["l_hip"], IDX["r_hip"]], :2], axis=1), axis=0)
        seg = np.stack([normalized(kp, f, r.torso_px, hips, stand == "L") for f in range(c - pre, c + post + 1)])
        seg[np.repeat((kp[c - pre:c + post + 1, :, 2] < 0.3)[..., None], 2, axis=2)] = np.nan
        stack.append(seg)
    if not stack:
        return np.full((pre + post + 1, 17, 2), np.nan), 0
    return np.nanmedian(np.stack(stack), axis=0), len(stack)


SWING_COLS = ["play_id", "page", "date", "season", "measured", "batter_px", "torso_px", "contact_frame", "down_to_contact_ms",
              "lift_to_contact_ms", "hip_lead_ms", "head_drop", "shoulder_tilt", "bat_speed", "attack_angle", "swing_length",
              "launch_speed", "launch_angle", "pitch_type", "pitch_speed"]


def save(name: str, t: pd.DataFrame) -> dict:
    """Write the per-swing table (reports/outputs/<name>_swings.json) and the season summary with its tests and
    detection limits (<name>_swing_summary.json), the files the packet's swing lab and the tests read."""
    rows = t.reindex(columns=SWING_COLS).sort_values("date")
    rows = [{k: (None if isinstance(v, float) and not np.isfinite(v) else (round(v, 4) if isinstance(v, float) else v))
             for k, v in r.items()} for r in rows.astype(object).to_dict("records")]
    (OUT / f"{name}_swings.json").write_text(json.dumps(rows, indent=1) + "\n")
    m = t[t.measured]
    hr = t.dropna(subset=["season"])
    summary = dict(
        clips=int(len(t)), measured=int(t.measured.sum()),
        by_season=by_season(t).round(4).replace({np.nan: None}).to_dict("records"),
        tests={c: permutation(t, c) for c in MEASURES},
        detectable_change={c: (None if not np.isfinite(v) else float(v)) for c, v in ((c, detectable(t, c)) for c in MEASURES)},
        n_by_measure={c: {str(int(s)): int(m[m.season == s][c].notna().sum()) for s in sorted(m.season.dropna().unique())} for c in MEASURES},
        statcast_hr_medians={str(int(s)): dict(n=int(len(g)), launch_speed=round(float(g.launch_speed.median()), 2),
                                                bat_speed=None if g.bat_speed.isna().all() else round(float(g.bat_speed.median()), 2),
                                                bat_speed_n=int(g.bat_speed.notna().sum()))
                             for s, g in hr.groupby("season")})
    (OUT / f"{name}_swing_summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    return summary
