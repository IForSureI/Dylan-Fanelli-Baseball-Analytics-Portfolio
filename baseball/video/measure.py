"""What I measure on a batter's swing from the center-field camera, and how.

The camera sits behind the pitcher, so it sees the batter from the front-side: up-down and side-to-side in the
image are real, toward-and-away (the stride toward the pitcher) is not. Everything here uses what the view can see.
All lengths are in torso lengths (shoulder midpoint to hip midpoint, median over the second before the swing;
steady through the leg lift, unlike standing height), so a near camera and a far one compare.

Events (big joints only: wrists blur during the swing and can't be trusted frame to frame):
- Hips square and shoulders square: the frame where the lead and rear hip (shoulder) pass each other across the
  image as the batter turns, i.e. the line between them squares to the camera. The hips should get there first.
- Contact: shoulders square plus a fixed offset in frames, set by reading contact by eye on a sample of clips (the
  report gives the offset and how well it holds).
- Lift and foot down: the lead ankle rising 6% of a torso length above its opening level, and coming back
  within 4%. A clip that opens after the lift has started gets no lift time.

Measures:
- Lift to contact and foot down to contact (ms; one frame is 16.7 ms at 59.94 fps).
- Hip lead: frames from hips square to shoulders square, in ms. The kinematic sequence: hips turn before shoulders.
- Head drop: how far the nose falls from the shot's opening frames to contact (torso lengths; + = lower).
- Shoulder tilt at contact: the angle of the line between the shoulders in the image (degrees; + = rear shoulder
  lower). From center field this is the batter's side bend, the posture that tilts the swing plane uphill.
"""
from __future__ import annotations

import numpy as np

from baseball.video.pose import IDX

LEAD = {"R": "l", "L": "r"}       # a right-handed hitter's lead side is his left
LIFT, DOWN = 0.06, 0.04
MAX_LIFT_S = 1.2            # a 'lift' more than 1.2 s before contact is a pre-pitch move, not the stride
ROTATION = 0.25            # shoulder gap change (torso lengths) that makes a rotation a swing
OPEN = 0.08                 # shoulders (hips) count as open once this far apart, in heights, for 3 frames
CONTACT_OFFSET = 6          # frames from shoulders square to contact, read by eye (see the report)


def _smooth(x: np.ndarray, k: int = 5) -> np.ndarray:
    """Centered moving average that ignores NaN."""
    out = np.full_like(x, np.nan, dtype=float)
    h = k // 2
    for i in range(len(x)):
        w = x[max(0, i - h):i + h + 1]
        w = w[np.isfinite(w)]
        if len(w):
            out[i] = w.mean()
    return out


def point(kp: np.ndarray, name: str, min_conf: float = 0.3) -> np.ndarray:
    p = kp[:, IDX[name], :2].copy()
    p[kp[:, IDX[name], 2] < min_conf] = np.nan
    return p


def last_shot(kp: np.ndarray, min_frames: int = 40) -> np.ndarray:
    """Tracked frames of the last continuous shot. Broadcasts zoom or cut within the pitch view (an earlier pitch,
    then a tighter shot of the swing); a jump in the batter's hip position or body size between neighboring frames
    marks the break, and the home-run swing is the last shot."""
    tracked = np.where(np.isfinite(kp[:, 0, 0]))[0]
    if len(tracked) < min_frames:
        return tracked[:0]
    hips = np.nanmean(kp[:, [IDX["l_hip"], IDX["r_hip"]], :2], axis=1)
    size = np.nanmax(kp[:, :, 1], axis=1) - np.nanmin(kp[:, :, 1], axis=1)
    breaks = [0]
    for a, b in zip(tracked[:-1], tracked[1:]):
        jump = np.linalg.norm(hips[b] - hips[a]) / max(size[a], 1)
        ratio = size[b] / max(size[a], 1)
        if b - a > 6 or jump > 0.6 or not (0.65 < ratio < 1.5):
            breaks.append(int(np.searchsorted(tracked, b)))
    breaks.append(len(tracked))
    for a, b in reversed(list(zip(breaks[:-1], breaks[1:]))):
        if b - a >= min_frames:
            return tracked[a:b]
    return tracked[:0]


def _square(kp: np.ndarray, part: str, lead: str, lo: int, hi: int) -> int | None:
    """The frame where the lead and rear joint pass each other across the image during the turn: the zero crossing
    of their horizontal gap nearest the gap's fastest change between frames lo and hi. Sign-free, because pose
    models can swap left and right on a side-on stance."""
    rear = "r" if lead == "l" else "l"
    dx = _smooth(point(kp, f"{lead}_{part}")[:, 0] - point(kp, f"{rear}_{part}")[:, 0], 3)
    v = np.abs(np.gradient(dx))
    idx = np.arange(max(lo, 1), min(hi, len(dx) - 1))
    idx = idx[np.isfinite(v[idx])]
    if not len(idx):
        return None
    peak = int(idx[np.nanargmax(v[idx])])
    best = None
    for j in range(peak - 8, peak + 4):
        if 0 < j < len(dx) and np.isfinite(dx[j]) and np.isfinite(dx[j - 1]) and np.sign(dx[j]) != np.sign(dx[j - 1]):
            if best is None or abs(j - peak) < abs(best - peak):
                best = j
    return best if best is not None else peak


def measure(kp: np.ndarray, fps: float, stand: str = "R") -> dict | None:
    tracked = last_shot(kp)
    if len(tracked) < 40:
        return None
    lead = LEAD[stand]
    sh = _square(kp, "shoulder", lead, int(tracked[0]) + 20, int(tracked[-1]) - 8)
    if sh is None:
        return None
    # a swing opens the shoulders: their gap must change by at least ROTATION torso lengths around the event
    rear_ = "r" if lead == "l" else "l"
    gap = point(kp, f"{lead}_shoulder")[:, 0] - point(kp, f"{rear_}_shoulder")[:, 0]
    torso0 = np.nanmedian(np.nanmean(kp[tracked, 11:13, 1], axis=1) - np.nanmean(kp[tracked, 5:7, 1], axis=1))
    w0, w1 = gap[max(0, sh - 12):sh - 2], gap[sh + 2:sh + 12]
    if not (len(w0) and len(w1)) or not np.isfinite(torso0) or abs(np.nanmedian(w1) - np.nanmedian(w0)) < ROTATION * torso0:
        return None
    hp = _square(kp, "hip", lead, sh - 25, sh + 4)
    contact = sh + CONTACT_OFFSET
    nose = point(kp, "nose")
    st = tracked[tracked < sh - 20][:15]               # the shot's opening frames, before the swing starts
    if len(st) < 6:
        return None
    sho = np.nanmean(np.stack([point(kp, "l_shoulder"), point(kp, "r_shoulder")]), axis=0)
    hip = np.nanmean(np.stack([point(kp, "l_hip"), point(kp, "r_hip")]), axis=0)
    pre = tracked[(tracked >= sh - 60) & (tracked <= sh - 5)]
    height = float(np.nanmedian(hip[pre, 1] - sho[pre, 1]))    # torso length: steady through the load
    if not np.isfinite(height) or height < 20:
        return None
    la = _smooth(point(kp, f"{lead}_ankle")[:, 1])
    base = float(np.nanmedian(la[st]))
    before = np.arange(st[0], contact + 1)
    lifted = before[(base - la[before]) / height > LIFT]
    lift = int(lifted[0]) if len(lifted) else None
    down = None
    if lift is not None:
        after = np.arange(int(lifted[-1]), contact + 1)
        back = after[np.abs(la[after] - base) / height < DOWN]
        down = int(back[0]) if len(back) else None
    if lift is not None and (contact - lift) / fps > MAX_LIFT_S:
        lift = None                                   # an earlier move (a step out, a timing tap), not the stride
    rear = "r" if lead == "l" else "l"
    ls, rs = point(kp, f"{lead}_shoulder"), point(kp, f"{rear}_shoulder")
    c = slice(max(0, contact - 1), contact + 2)
    dy = np.nanmean(rs[c, 1] - ls[c, 1])
    span = np.nanmean(np.hypot(rs[c, 0] - ls[c, 0], rs[c, 1] - ls[c, 1]))
    tilt = float(np.degrees(np.arcsin(np.clip(dy / span, -1, 1)))) if np.isfinite(dy) and span > 0 else np.nan
    ms = 1000.0 / fps
    return dict(
        contact_frame=contact, shoulders_square=sh, hips_square=hp if hp is not None else np.nan, torso_px=height,
        lift_to_contact_ms=(contact - lift) * ms if lift is not None else np.nan,
        down_to_contact_ms=(contact - down) * ms if down is not None else np.nan,
        hip_lead_ms=(sh - hp) * ms if hp is not None else np.nan,
        head_drop=float((np.nanmean(nose[c, 1]) - np.nanmedian(nose[st, 1])) / height),
        shoulder_tilt=tilt,
    )
