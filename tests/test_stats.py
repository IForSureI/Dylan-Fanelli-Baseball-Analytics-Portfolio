import math

from baseball.stats import two_proportion, wilson


def test_wilson_hand_checked():
    lo, hi = wilson(252, 538)            # Skubal 2025 changeup whiffs / swings
    assert round(lo, 4) == 0.4266 and round(hi, 4) == 0.5106
    assert all(math.isnan(x) for x in wilson(0, 0))  # empty sample


def test_wilson_stays_inside_0_1():
    lo, hi = wilson(0, 5)
    assert lo >= 0 and hi < 1
    lo, hi = wilson(5, 5)
    assert hi <= 1 and lo > 0


def test_two_proportion_hand_checked():
    # 30/100 vs 50/100: pooled 0.4, se = sqrt(0.4*0.6*0.02) = 0.069282, z = 0.2/0.069282 = 2.8868
    z, p = two_proportion(30, 100, 50, 100)
    assert round(z, 4) == 2.8868
    assert round(p, 5) == 0.00389
    z, p = two_proportion(30, 100, 30, 100)
    assert z == 0 and p == 1
