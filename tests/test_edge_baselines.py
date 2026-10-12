import numpy as np
import pandas as pd

from baseball.edge.baselines import changes, league_change


def _season(year, spin_bump=0.0, special_bump=0.0, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for pid in range(1, 41):
        for _ in range(150):
            bump = spin_bump + (special_bump if pid == 1 else 0)
            rows.append({"pitcher": pid, "player_name": f"P{pid}", "pitch_type": "FF",
                         "release_speed": 94 + rng.normal(0, 0.5), "release_spin_rate": 2300 + pid + bump + rng.normal(0, 20),
                         "release_extension": 6.3, "arm_angle": 45.0})
    return pd.DataFrame(rows)


def test_league_shift_is_separated_from_individual_change():
    ch = changes(_season(2024, seed=1), _season(2025, spin_bump=100, special_bump=200, seed=2))
    spin = ch[ch["metric"] == "spin"].set_index("pitcher")
    assert abs(spin["league_median_change"].iloc[0] - 100) < 10       # everyone moved ~100 rpm
    assert abs(spin.loc[1, "excess_change"] - 200) < 15                # pitcher 1 moved 200 more than the league
    assert spin.loc[1, "pctile"] == 100
    s = league_change(ch).set_index(["metric", "pitch_type"]).loc[("spin", "FF")]
    assert s["pitchers"] == 40 and s["share_up"] == 100
