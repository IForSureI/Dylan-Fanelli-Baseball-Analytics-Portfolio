import numpy as np
import pandas as pd

from baseball.edge.shifts import score_shifts
from baseball.edge.stuff import persistent_gaps
from baseball.stats import benjamini_hochberg


def test_bh_hand_checked():
    # p = .01, .02, .03, .5 with m = 4 -> raw .04, .04, .04, .5 -> monotone .04, .04, .04, .5
    q = benjamini_hochberg([0.01, 0.02, 0.03, 0.5])
    assert [round(x, 3) for x in q] == [0.04, 0.04, 0.04, 0.5]
    assert np.isnan(benjamini_hochberg([np.nan, 0.2])[0])


def test_score_shifts_uses_expected_whiff_on_each_side():
    shifts = pd.DataFrame({"pitcher": [1], "pitch_type": ["SL"], "split_date": ["2025-06-01"], "whiff_p": [0.2]})
    swings = pd.DataFrame({"pitcher": 1, "pitch_type": "SL", "same_hand": 1,
                           "game_date": ["2025-05-01", "2025-05-10", "2025-06-05", "2025-06-10"],
                           "x_whiff": [0.20, 0.30, 0.40, 0.40]})
    out = score_shifts(shifts, swings).iloc[0]
    assert round(out["x_whiff_before"], 1) == 25.0 and round(out["x_whiff_after"], 1) == 40.0
    assert round(out["x_whiff_change"], 1) == 15.0


def test_persistent_gaps_weights_by_swings_and_flags_sign():
    t24 = pd.DataFrame({"pitcher": [1, 2], "player_name": ["A", "B"], "pitch_type": "CH", "pitch_name": "Changeup",
                        "swings": [100, 100], "whiff_pct": [40, 30], "x_whiff_pct": [30, 30], "gap": [10.0, 0.0]})
    t25 = t24.assign(swings=[300, 100], gap=[6.0, -2.0])
    out = persistent_gaps({2024: t24, 2025: t25}).set_index("pitcher")
    assert out.loc[1, "mean_gap"] == 7.0          # (10*100 + 6*300) / 400
    assert bool(out.loc[1, "same_sign"]) and not bool(out.loc[2, "same_sign"])
    assert out.loc[1, "seasons"] == 2


def test_score_shifts_holds_batter_hand_mix_fixed():
    # Same pitch, same expected whiff by hand (40% same-hand, 20% opposite). After the split he throws it
    # mostly to opposite-handed hitters. The raw average would fall; at a fixed mix it must not move.
    shifts = pd.DataFrame({"pitcher": [1], "pitch_type": ["SL"], "split_date": ["2025-06-01"], "whiff_p": [0.5]})
    rows = [("2025-05-01", 1, 0.4)] * 8 + [("2025-05-02", 0, 0.2)] * 2 + [("2025-06-05", 1, 0.4)] * 2 + [("2025-06-06", 0, 0.2)] * 8
    swings = pd.DataFrame(rows, columns=["game_date", "same_hand", "x_whiff"]).assign(pitcher=1, pitch_type="SL")
    out = score_shifts(shifts, swings).iloc[0]
    assert abs(out["x_whiff_change"]) < 1e-9
