"""Fictional Statcast-shaped pitch data for offline work and tests.

Not real data. Use it when Baseball Savant is down or slow, or to test code without a network.
The pitcher is a made-up right-hander with a four-seamer, slider, changeup and curveball.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# pitch_type, pitch_name, share, velo, spin, pfx_x (ft, catcher view), pfx_z (ft), whiff rate on swings
_ARSENAL = [
    ("FF", "4-Seam Fastball", 0.48, 95.5, 2350, -0.70, 1.35, 0.20),
    ("SL", "Slider", 0.27, 86.0, 2550, 0.40, 0.15, 0.36),
    ("CH", "Changeup", 0.15, 87.5, 1750, -1.20, 0.55, 0.32),
    ("CU", "Curveball", 0.10, 79.0, 2700, 0.70, -0.90, 0.30),
]


def fictional_pitcher(n_pitches: int = 2500, seed: int = 7, pitcher_id: int = 999001, season: int = 2025) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    shares = np.array([a[2] for a in _ARSENAL])
    idx = rng.choice(len(_ARSENAL), size=n_pitches, p=shares / shares.sum())

    rows = []
    for k, i in enumerate(idx):
        code, name, _, velo, spin, px, pz, whiff_rate = _ARSENAL[i]
        zone = int(rng.integers(1, 10)) if rng.random() < 0.5 else int(rng.choice([11, 12, 13, 14]))
        in_zone = zone <= 9
        swing = rng.random() < (0.68 if in_zone else 0.30)
        bip = False
        if swing:
            r = rng.random()
            if r < whiff_rate:
                desc = "swinging_strike"
            elif r < whiff_rate + 0.40:
                desc = "foul"
            else:
                desc, bip = "hit_into_play", True
        else:
            desc = "called_strike" if in_zone and rng.random() < 0.6 else "ball"
        ev = round(rng.normal(88, 10), 1) if bip else np.nan
        rows.append(
            {
                "game_pk": 900000 + (pitcher_id % 1000) * 1000 + k // 95,  # each fictional pitcher gets his own games
                "game_date": str((pd.Timestamp(f"{season}-04-01") + pd.Timedelta(days=5 * (k // 95))).date()),
                "game_year": season,
                "game_type": "R",
                "at_bat_number": (k % 95) // 4 + 1,
                "pitch_number": (k % 95) % 4 + 1,
                "pitcher": pitcher_id,
                "player_name": "Example, Fictional",
                "p_throws": "R",
                "stand": "L" if rng.random() < 0.45 else "R",
                "pitch_type": code,
                "pitch_name": name,
                "release_speed": round(rng.normal(velo, 0.9), 1),
                "release_spin_rate": round(rng.normal(spin, 60)),
                "release_extension": round(rng.normal(6.3, 0.1), 2),
                "pfx_x": round(rng.normal(px, 0.12), 2),
                "pfx_z": round(rng.normal(pz, 0.12), 2),
                "zone": zone,
                "description": desc,
                "type": "X" if bip else ("B" if desc == "ball" else "S"),
                "launch_speed": ev,
                "estimated_woba_using_speedangle": round(float(np.clip((ev - 70) / 60, 0, 1.8)), 3) if bip else np.nan,
                "delta_run_exp": round(rng.normal(0.03, 0.05) if (desc == "ball" or bip) else rng.normal(-0.05, 0.02), 3),
            }
        )
    return pd.DataFrame(rows)
