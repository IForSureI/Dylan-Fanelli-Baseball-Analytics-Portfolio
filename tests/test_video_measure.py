"""The swing measures on a synthetic batter whose events are known: the hips open at frame 96, the shoulders at 100,
the lead foot lifts at 60 and lands at 85, and the head drops a tenth of a torso length."""
import numpy as np

from baseball.video import measure as M
from baseball.video.pose import IDX


def synthetic(n=140, hips_at=96, shoulders_at=100, lift=60, down=85, torso=60.0):
    kp = np.full((n, 17, 3), np.nan)
    t = np.arange(n)
    kp[..., 2] = 0.9
    cx, hip_y = 640.0, 400.0
    sho_y = hip_y - torso

    def gap(at):   # lead minus rear x: -10 closed, +40 open, a fast turn of 6 frames around `at`
        return np.interp(t, [0, at - 3, at + 3, n], [-10, -10, 40, 40])

    kp[:, IDX["l_shoulder"], 0], kp[:, IDX["r_shoulder"], 0] = cx + gap(shoulders_at) / 2, cx - gap(shoulders_at) / 2
    kp[:, IDX["l_shoulder"], 1] = kp[:, IDX["r_shoulder"], 1] = sho_y
    kp[:, IDX["l_hip"], 0], kp[:, IDX["r_hip"], 0] = cx + gap(hips_at) / 2, cx - gap(hips_at) / 2
    kp[:, IDX["l_hip"], 1] = kp[:, IDX["r_hip"], 1] = hip_y
    kp[:, IDX["nose"], 0] = cx
    kp[:, IDX["nose"], 1] = sho_y - 25 + np.interp(t, [0, 90, shoulders_at + 4, n], [0, 0, 0.1 * torso, 0.1 * torso])
    lift_h = np.interp(t, [0, lift, (lift + down) / 2, down, n], [0, 0, 15, 0, 0])
    kp[:, IDX["l_ankle"], 0], kp[:, IDX["r_ankle"], 0] = cx + 20, cx - 20
    kp[:, IDX["l_ankle"], 1] = hip_y + 90 - lift_h
    kp[:, IDX["r_ankle"], 1] = hip_y + 90
    for j in ("l_wrist", "r_wrist", "l_knee", "r_knee", "l_elbow", "r_elbow", "l_eye", "r_eye", "l_ear", "r_ear"):
        kp[:, IDX[j], :2] = [cx, hip_y - 20]
    return kp


def test_events_and_measures():
    m = M.measure(synthetic(), 59.94, "R")
    assert m is not None
    assert abs(m["shoulders_square"] - 100) <= 2 and abs(m["hips_square"] - 96) <= 2
    assert m["contact_frame"] == m["shoulders_square"] + M.CONTACT_OFFSET
    assert m["hip_lead_ms"] > 0
    assert abs(m["head_drop"] - 0.1) < 0.03
    assert 0 < m["down_to_contact_ms"] < m["lift_to_contact_ms"]


def test_a_batter_who_does_not_swing_is_not_measured():
    kp = synthetic()
    for j in ("l_shoulder", "r_shoulder", "l_hip", "r_hip"):
        kp[:, IDX[j], 0] = kp[0, IDX[j], 0]          # frozen: no turn
    assert M.measure(kp, 59.94, "R") is None


def test_left_handed_hitter_mirrors():
    kp = synthetic()
    m_r = M.measure(kp, 59.94, "R")
    sw = kp.copy()
    for a, b in (("l_shoulder", "r_shoulder"), ("l_hip", "r_hip"), ("l_ankle", "r_ankle")):
        sw[:, [IDX[a], IDX[b]]] = kp[:, [IDX[b], IDX[a]]]
    m_l = M.measure(sw, 59.94, "L")
    assert m_l["shoulders_square"] == m_r["shoulders_square"]
