"""Frame-by-frame pose of the batter in the center-field shot of an MLB highlight clip.

Steps, for one clip:
1. Find the pitch view. Clips open in different ways (close-ups, replays, dissolves), so the pitch view is found,
   not assumed: every sixth frame of the first 15 seconds is scanned for people (YOLO pose, small model), and the
   pitch view is the longest run of frames with one person standing low in the frame (the pitcher, nearest the
   center-field camera) and another, taller than a catcher, standing above him (the batter).
2. Lock onto the batter: in the run's first frame, the tallest person above the pitcher and within a fifth of the
   frame's width of him.
3. Track him through every frame of the run: crop around his last box, run YOLO pose (medium model) on the crop,
   and keep the person nearest his last box. Keypoints (17, COCO order) are returned in full-frame pixels with a
   confidence each.

Needs the optional video tools: `uv pip install ultralytics opencv-python-headless` (the YOLO weights download on
first use). Keypoints are 2-D estimates from a camera behind the pitcher: good on head, shoulders, hips and knees
at a batter 150+ pixels tall, noisier on wrists and ankles, and blind to depth (toward or away from the camera).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

KP = ["nose", "l_eye", "r_eye", "l_ear", "r_ear", "l_shoulder", "r_shoulder", "l_elbow", "r_elbow", "l_wrist",
      "r_wrist", "l_hip", "r_hip", "l_knee", "r_knee", "l_ankle", "r_ankle"]
IDX = {n: i for i, n in enumerate(KP)}
SCAN_MODEL, TRACK_MODEL = "yolo11s-pose.pt", "yolo11m-pose.pt"
SCAN_STEP, SCAN_SECONDS = 6, 15.0
MIN_BATTER_PX = 110
GRASS_MIN = 0.35          # share of the lower half that must be grass for a frame to count as the pitch view        # a clip whose batter is shorter than this in the pitch view is not measured


def read_frames(path: Path, max_seconds: float = SCAN_SECONDS) -> tuple[list[np.ndarray], float]:
    import cv2
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 59.94
    frames = []
    while len(frames) < int(max_seconds * fps):
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    cap.release()
    return frames, fps


class Tracker:
    def __init__(self):
        from ultralytics import YOLO
        self.scan_model, self.track_model = YOLO(SCAN_MODEL), YOLO(TRACK_MODEL)

    def people(self, frame: np.ndarray, model=None, imgsz: int = 960, conf: float = 0.25):
        r = (model or self.scan_model)(frame, imgsz=imgsz, conf=conf, verbose=False)[0]
        if r.boxes is None or len(r.boxes) == 0:
            return np.zeros((0, 4)), np.zeros((0, 17, 3))
        k = np.concatenate([r.keypoints.xy.numpy(), r.keypoints.conf.numpy()[..., None]], axis=2)
        return r.boxes.xyxy.numpy(), k

    @staticmethod
    def grass_share(frame: np.ndarray) -> float:
        """Share of the lower half that is grass green (the center-field pitch view is mostly field; a crowd or
        dugout shot is not)."""
        import cv2
        hsv = cv2.cvtColor(frame[frame.shape[0] // 2:], cv2.COLOR_BGR2HSV)
        green = (hsv[..., 0] > 30) & (hsv[..., 0] < 90) & (hsv[..., 1] > 60) & (hsv[..., 2] > 50)
        return float(green.mean())

    def _pitch_view_frame(self, boxes: np.ndarray, H: int, W: int, frame: np.ndarray | None = None):
        if len(boxes) < 2:
            return None
        if frame is not None and self.grass_share(frame) < GRASS_MIN:
            return None
        hts = boxes[:, 3] - boxes[:, 1]
        low = int(np.argmax(boxes[:, 3]))
        if boxes[low, 3] < 0.55 * H or hts[low] < 0.15 * H or abs((boxes[low, 0] + boxes[low, 2]) / 2 - W / 2) > 0.3 * W:
            return None
        cand = [i for i in range(len(boxes)) if i != low and boxes[i, 3] < boxes[low, 1] + 0.1 * H
                and abs((boxes[i, 0] + boxes[i, 2]) / 2 - (boxes[low, 0] + boxes[low, 2]) / 2) < 0.2 * W and hts[i] > 0.12 * H]
        if not cand:
            return None
        return boxes[max(cand, key=lambda i: hts[i])]

    def pitch_view(self, frames: list[np.ndarray]) -> tuple[int, int, np.ndarray | None]:
        H, W = frames[0].shape[:2]
        hits = []
        for i in range(0, len(frames), SCAN_STEP):
            b, _ = self.people(frames[i])
            hits.append(self._pitch_view_frame(b, H, W, frames[i]))
        # a single missed scan inside a run (a blurred frame, a person hidden behind another) doesn't end it
        for k in range(1, len(hits) - 1):
            if hits[k] is None and hits[k - 1] is not None and hits[k + 1] is not None:
                hits[k] = hits[k - 1]
        best, run = (0, 0), None
        for k, h in enumerate(hits + [None]):
            if h is not None and run is None:
                run = k
            if h is None and run is not None:
                if k - run > best[1] - best[0]:
                    best = (run, k)
                run = None
        a, b = best
        return a * SCAN_STEP, min(len(frames), b * SCAN_STEP), (hits[a] if b > a else None)

    def track(self, frames: list[np.ndarray], start: int, end: int, box: np.ndarray) -> np.ndarray:
        H, W = frames[0].shape[:2]
        out = np.full((len(frames), 17, 3), np.nan)
        box = box.astype(float)
        for i in range(start, end):
            bw, bh = box[2] - box[0], box[3] - box[1]
            x0, y0 = int(max(0, box[0] - 0.9 * bw)), int(max(0, box[1] - 0.5 * bh))
            x1, y1 = int(min(W, box[2] + 0.9 * bw)), int(min(H, box[3] + 0.5 * bh))
            b, k = self.people(frames[i][y0:y1, x0:x1], self.track_model, imgsz=640, conf=0.2)
            if not len(b):
                continue
            b = b + [x0, y0, x0, y0]
            k[..., 0] += x0
            k[..., 1] += y0
            c = (box[:2] + box[2:]) / 2
            d = np.linalg.norm((b[:, :2] + b[:, 2:]) / 2 - c, axis=1) + 0.5 * np.abs((b[:, 3] - b[:, 1]) - bh)
            j = int(np.argmin(d))
            if d[j] > 0.6 * bh:
                continue
            out[i] = k[j]
            box = 0.5 * box + 0.5 * b[j]       # smooth the box so one bad frame can't jump it
        return out


def clip_pose(path: Path, tracker: Tracker | None = None) -> dict:
    frames, fps = read_frames(path)
    tr = tracker or Tracker()
    start, end, box = tr.pitch_view(frames)
    kp = np.full((len(frames), 17, 3), np.nan)
    px = float(box[3] - box[1]) if box is not None else 0.0
    if box is not None and end - start > fps and px >= MIN_BATTER_PX:
        # extend the run to the next scan step so the swing near its end isn't cut off
        kp = tr.track(frames, start, min(len(frames), end + SCAN_STEP), box)
    return dict(fps=fps, start=start, end=end, batter_px=px, frame_size=list(frames[0].shape[:2]), keypoints=kp)
