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
