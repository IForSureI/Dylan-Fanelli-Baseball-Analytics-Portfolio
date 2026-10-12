"""Fictional Statcast-shaped pitch data for offline work and tests.

Not real data. Use it when Baseball Savant is down or slow, or to test code without a network.
The pitcher is a made-up right-hander with a four-seamer, slider, changeup and curveball.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# pitch_type, pitch_name, share, velo, spin, pfx_x (ft, catcher view), pfx_z (ft), whiff-prone
_ARSENAL = [
    ("FF", "4-Seam Fastball", 0.48, 95.5, 2350, -0.70, 1.35, 0.20),
    ("SL", "Slider", 0.27, 86.0, 2550, 0.40, 0.15, 0.36),
    ("CH", "Changeup", 0.15, 87.5, 1750, -1.20, 0.55, 0.32),
    ("CU", "Curveball", 0.10, 79.0, 2700, 0.70, -0.90, 0.30),
]


def fictional_pitcher(n_pitches: int = 2500, seed: int = 7, pitcher_id: int = 999001) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    shares = np.array([a[2] for a in _ARSENAL])
    idx = rng.choice(len(_ARSENAL), size=n_pitches, p=shares / shares.sum())

    rows = []
    for i in idx:
        code, name, _, velo, spin, px, pz, whiff_rate = _ARSENAL[i]
        swing = rng.random() < 0.47
        if swing:
            r = rng.random()
            if r < whiff_rate:
                desc = "swinging_strike"
            elif r < whiff_rate + 0.40:
                desc = "foul"
            else:
                desc = "hit_into_play"
        else:
            desc = "called_strike" if rng.random() < 0.33 else "ball"
        rows.append(
            {
                "pitcher": pitcher_id,
                "player_name": "Example, Fictional",
                "p_throws": "R",
                "pitch_type": code,
                "pitch_name": name,
                "release_speed": round(rng.normal(velo, 0.9), 1),
                "release_spin_rate": round(rng.normal(spin, 60)),
                "pfx_x": round(rng.normal(px, 0.12), 2),
                "pfx_z": round(rng.normal(pz, 0.12), 2),
                "description": desc,
            }
        )
    return pd.DataFrame(rows)
