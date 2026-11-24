"""The TrackMan / Rapsodo loader (baseball.ingest.tracking), on the fictional sample files only."""
import subprocess
import sys

import numpy as np
import pytest

from baseball.ingest import tracking as tl


@pytest.fixture(scope="module")
def samples(tmp_path_factory):
    out = tmp_path_factory.mktemp("trk")
    subprocess.run([sys.executable, "-m", "baseball.ingest.sample_tracking", "--out-dir", str(out)], check=True, capture_output=True)
    return out


def test_detects_each_source(samples):
    for name, src in [("sample_trackman.csv", "trackman"), ("sample_rapsodo.csv", "rapsodo"), ("sample_rapsodo_hitting.csv", "rapsodo_hitting")]:
        raw, _ = tl.read_any(str(samples / name))
        assert tl.detect(raw)["source"] == src


def test_trackman_sign_is_flipped_to_savant_frame(samples):
    raw, _ = tl.read_any(str(samples / "sample_trackman.csv"))
    n, dec = tl.normalize(raw)
    assert dec["multiplier"] == -1
    fb = n[n["pitch_type"].isin(["FF", "SI"])]
    # Savant frame: a right-hander's arm-side run is negative pfx_x, a left-hander's positive
    assert fb.loc[fb["p_throws"] == "R", "pfx_x"].median() < 0
    assert fb.loc[fb["p_throws"] == "L", "pfx_x"].median() > 0
    assert (fb["api_break_x_arm"].median()) > 0


def test_planted_qc_problems_are_caught(samples):
    raw, _ = tl.read_any(str(samples / "sample_trackman.csv"))
    n, dec = tl.normalize(raw)
    c = tl.qc_report(raw, n, dec)["checks"]
    assert c["untracked"] == 4 and c["low_confidence"] == 5 and c["tag_disagree"] == 6
    assert c["impossible_release_speed"] == 2 and c["impossible_release_spin_rate"] == 1
    assert c["duplicate_rows_exact"] == 3 and c["bad_balls"] == 1


def test_rapsodo_needs_hand_and_has_no_swings(samples):
    raw, _ = tl.read_any(str(samples / "sample_rapsodo.csv"))
    n, dec = tl.normalize(raw, p_throws="R")
    assert (n["p_throws"] == "R").all()
    assert not n["description"].isin(["swinging_strike", "foul", "hit_into_play"]).any()
    assert np.isfinite(n["release_speed"]).all()


def test_tilt_and_efficiency_math():
    assert tl.axis_to_tilt(210) == "1:00"
    assert tl.tilt_to_axis("1:30") == 225
    eff = tl.spin_efficiency(total=2400, true=2100)
    assert abs(eff["spin_efficiency"] - 0.875) < 1e-9 and abs(eff["gyro_angle_deg"] - 28.96) < 0.01


def test_contact_hang_and_catcher_throw_fields():
    """TrackMan's contact point (X out front, Y height, Z side), hang time and catcher-throw timings survive the loader."""
    import pandas as pd
    from baseball.ingest import tracking

    df = pd.DataFrame({"PitcherThrows": ["Right"], "TaggedPitchType": ["Fastball"], "PitchCall": ["InPlay"],
                       "ContactPositionX": [2.2], "ContactPositionY": [2.4], "ContactPositionZ": [-0.3], "HangTime": [4.1],
                       "Bearing": [-12.0], "MaxHeight": [80.0], "PopTime": [1.98], "ExchangeTime": [0.75], "ThrowSpeed": [79.5]})
    out, _ = tracking.normalize_trackman(df)
    r = out.iloc[0]
    assert (r["contact_depth"], r["contact_height"], r["contact_side"]) == (2.2, 2.4, -0.3)
    assert (r["hang_time"], r["hit_bearing"], r["hit_max_height"]) == (4.1, -12.0, 80.0)
    assert (r["pop_time"], r["exchange_time"], r["throw_speed"]) == (1.98, 0.75, 79.5)


def test_pitchfx_fields_follow_x0s_frame():
    """vx0 and ax are flipped exactly when x0 is not on the release point's side in the catcher's view, for both
    HorzBreak frames (four cases)."""
    import pandas as pd
    from baseball.ingest import tracking

    def run(hb, relside, x0):
        n = 8
        df = pd.DataFrame({"PitcherThrows": ["Right"] * n, "TaggedPitchType": ["Fastball"] * n, "HorzBreak": [hb] * n,
                           "RelSide": [relside] * n, "x0": [x0] * n, "vx0": [-6.0] * n, "ax0": [-12.0] * n})
        out, dec = tracking.normalize_trackman(df)
        m = dec["multiplier"]
        return m, out["release_pos_x"].iloc[0], out["vx0"].iloc[0], out["ax"].iloc[0]

    for hb in (-15.0, 15.0):                     # a right-hander's four-seamer in both HorzBreak conventions
        for relside, x0 in ((-2.0, 1.9), (-2.0, -1.9), (2.0, -1.9), (2.0, 1.9)):
            m, rel_x, vx0, ax = run(hb, relside, x0)
            keep = (x0 > 0) == (rel_x > 0)        # x0 already on the catcher-view release side
            assert (vx0, ax) == ((-6.0, -12.0) if keep else (6.0, 12.0)), (hb, relside, x0, m)
