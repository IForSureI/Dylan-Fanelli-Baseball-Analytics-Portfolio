import math

import numpy as np

from baseball.edge.shape_exposure import _group_exposure


def test_windows_pitcher_exclusion_and_kernel():
    # One hitter, one family. Days and pitchers in date order; shapes in standardized units (2 dims used, rest 0).
    day = np.array([0, 5, 20, 31, 40, 40, 45])
    pitcher = np.array([1, 2, 3, 4, 5, 1, 6])
    Z = np.zeros((7, 6), np.float32)
    Z[:, 0] = [0, 1, 0, 3, 0, 0, 2]
    e = _group_exposure(day, pitcher, Z)
    # Target row 4 (day 40, pitcher 5, shape 0):
    #   1-30 days back = days 10..39 -> rows 2 (day 20) and 3 (day 31); row 5 is the same day, so it never counts.
    assert e["N30"][4] == 2
    #   kernel h=1: exp(-0/2) + exp(-9/2)
    assert math.isclose(e["K30_h1.0"][4], 1 + math.exp(-4.5), rel_tol=1e-5)
    #   1-7 days back = days 33..39 -> none; 8-30 = days 10..32 -> rows 2 and 3; 31-90 = days -50..9 -> rows 0 and 1
    assert e["N7"][4] == 0 and e["N8_30"][4] == 2 and e["N31_90"][4] == 2
    #   lead: 1-30 days ahead = days 41..70 -> row 6 (shape 2): kernel exp(-4/2)
    assert e["Nlead30"][4] == 1
    assert math.isclose(e["Klead30_h1.0"][4], math.exp(-2.0), rel_tol=1e-5)
    # Target row 5 (day 40, pitcher 1): the day-0 pitch is also pitcher 1 but 40 days back, outside 1-30;
    # in 31-90 it is excluded because it's the same pitcher -> only row 1 (pitcher 2, day 5) counts there.
    assert e["N31_90"][5] == 1
    # bandwidth 0.5 on row 4: exp(-0) + exp(-9 / 0.5)
    assert math.isclose(e["K30_h0.5"][4], 1 + math.exp(-18.0), rel_tol=1e-5)
