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


def test_clustered_se_grows_when_rows_are_duplicated():
    import numpy as np

    from baseball.stats import clustered_wls

    rng = np.random.default_rng(0)
    x = rng.normal(size=100)
    y = 2 * x + rng.normal(size=100)
    X = np.column_stack([np.ones(100), x])
    b1, se1 = clustered_wls(y, X, np.ones(100), np.arange(100))
    # the same 100 rows three times: naive SEs would shrink by sqrt(3); clustered SEs must not
    b3, se3 = clustered_wls(np.tile(y, 3), np.tile(X, (3, 1)), np.ones(300), np.tile(np.arange(100), 3))
    assert abs(b1[1] - 2) < 0.3 and abs(b3[1] - b1[1]) < 1e-9
    assert se3[1] > 0.9 * se1[1]


def test_loo_rmse_exceeds_in_sample():
    import numpy as np

    from baseball.stats import wls_loo_rmse

    rng = np.random.default_rng(1)
    X = np.column_stack([np.ones(50), rng.normal(size=(50, 3))])
    y = X @ np.array([1, 0.5, 0, 0]) + rng.normal(size=50)
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    in_rmse = float(np.sqrt(np.mean((y - X @ beta) ** 2)))
    assert wls_loo_rmse(y, X, np.ones(50)) > in_rmse
