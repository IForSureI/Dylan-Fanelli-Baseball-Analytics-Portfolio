"""Approximate pitch physics for devices that don't export full trajectories (TrackMan reports, Rapsodo).

approach_angle(): vertical approach angle at the front of the plate from release speed, release height,
extension, induced vertical break and the plate height the pitch arrives at. Constant drag (the ball loses
`speed_loss` of its speed by the plate) and constant lift solved from IVB over the full flight.

Checked against Statcast's own kinematics (vz0, az, ...) on 2,849 Tarik Skubal pitches (2025): within 0.1
degree on average for four-seamers, changeups and sliders at every zone height, when IVB (Statcast
pfx_z * 12, or TrackMan InducedVertBreak) is treated as full-flight movement. Treating it as last-40-ft
movement was about 1 degree too flat, so "full" is the default.
"""
from __future__ import annotations

import math

G = 32.174          # ft/s^2
PLATE_Y = 17 / 12   # front of home plate, ft
MOUND_Y = 60.5


def approach_angle(velo_mph: float, release_height_ft: float, extension_ft: float, ivb_in: float,
                   plate_z_ft: float, ivb_window: str = "full", speed_loss: float = 0.08) -> float:
    """Vertical approach angle in degrees (negative = descending; closer to 0 = flatter)."""
    v0 = velo_mph * 5280 / 3600
    vf = v0 * (1 - speed_loss)
    dist = (MOUND_Y - extension_ft) - PLATE_Y
    decel = (v0**2 - vf**2) / (2 * dist)

    def time_over(d: float, v_start: float) -> float:
        v_end = math.sqrt(max(v_start**2 - 2 * decel * d, 1e-9))
        return (v_start - v_end) / decel if decel > 0 else d / v_start

    T = time_over(dist, v0)
    if ivb_window == "full":
        t_window = T
    else:  # last 40 ft before the front of the plate
        v_at_40 = math.sqrt(v0**2 - 2 * decel * (dist - 40))
        t_window = time_over(40, v_at_40)
    a_lift = 2 * (ivb_in / 12) / t_window**2
    az = -G + a_lift
    vz0 = (plate_z_ft - release_height_ft - 0.5 * az * T**2) / T
    vz_f = vz0 + az * T
    return -math.degrees(math.atan2(-vz_f, vf))


def flight_time(velo_mph: float, extension_ft: float, speed_loss: float = 0.08) -> float:
    """Seconds from release to the front of the plate."""
    v0 = velo_mph * 5280 / 3600
    vf = v0 * (1 - speed_loss)
    dist = (MOUND_Y - extension_ft) - PLATE_Y
    return 2 * dist / (v0 + vf)


def lift_accel(velo_mph: float, extension_ft: float, ivb_in: float, speed_loss: float = 0.08) -> float:
    """Spin-induced vertical acceleration (ft/s^2) behind an IVB reading.

    IVB grows with flight time, so slower pitches show more IVB for the same lift. Lift acceleration
    removes that: it's the speed-free measure of how much the spin holds the ball up."""
    T = flight_time(velo_mph, extension_ft, speed_loss)
    return 2 * (ivb_in / 12) / T**2
