import math

from baseball.evaluation.physics import G, MOUND_Y, PLATE_Y, approach_angle


def _simulate(velo_mph, rel_h, ext, lift, plate_target, loss=0.08):
    """Exact constant-acceleration flight; returns (IVB full flight in inches, plate height, true VAA)."""
    v0 = velo_mph * 5280 / 3600
    vf = v0 * (1 - loss)
    d = (MOUND_Y - ext) - PLATE_Y
    decel = (v0**2 - vf**2) / (2 * d)
    T = (v0 - vf) / decel
    az = -G + lift
    vz0 = (plate_target - rel_h - 0.5 * az * T**2) / T
    ivb_in = 0.5 * lift * T**2 * 12
    vzf = vz0 + az * T
    return ivb_in, plate_target, -math.degrees(math.atan2(-vzf, vf))


def test_recovers_simulated_flight():
    for velo, rel, ext, lift, z in [(95, 5.9, 6.4, 18, 2.5), (83, 5.33, 6.7, 22, 3.3), (86, 5.6, 6.3, 6, 1.8)]:
        ivb, pz, true_vaa = _simulate(velo, rel, ext, lift, z)
        assert abs(approach_angle(velo, rel, ext, ivb, pz) - true_vaa) < 0.05


def test_directions():
    base = approach_angle(94, 6.0, 6.4, 16, 3.0)
    assert approach_angle(94, 6.0, 6.4, 20, 3.0) > base      # more carry -> flatter
    assert approach_angle(94, 5.3, 6.4, 16, 3.0) > base      # lower release -> flatter
    assert approach_angle(94, 6.0, 6.4, 16, 3.5) > base      # higher in the zone -> flatter
    assert -8 < base < -3


def test_lift_removes_the_speed_effect():
    from baseball.evaluation.physics import flight_time, lift_accel

    # same lift, slower pitch -> more IVB, but the same lift acceleration back out
    T_slow, T_fast = flight_time(83, 6.7), flight_time(95, 6.7)
    ivb_slow, ivb_fast = 0.5 * 16 * T_slow**2 * 12, 0.5 * 16 * T_fast**2 * 12
    assert ivb_slow > ivb_fast
    assert abs(lift_accel(83, 6.7, ivb_slow) - 16) < 1e-9 and abs(lift_accel(95, 6.7, ivb_fast) - 16) < 1e-9
