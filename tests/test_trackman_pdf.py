"""The TrackMan session-PDF reader's length parser: feet and inches, and a sign that covers the whole length
(release side within a foot of center prints as -0'5")."""
import pytest

from baseball.ingest.trackman_pdf import feet


@pytest.mark.parametrize("text, value", [("6'4\"", 6 + 4 / 12), ("1'11\"", 1 + 11 / 12), ("11\"", 11 / 12), ("7'", 7.0),
                                         ("-0'5\"", -5 / 12), ("-11\"", -11 / 12), ("-1'6\"", -1.5), ("0'5.5\"", 5.5 / 12)])
def test_feet(text, value):
    assert feet(text) == pytest.approx(value)


def test_feet_blank_and_bad():
    assert feet("-") is None and feet("") is None
    with pytest.raises(ValueError):
        feet("six feet")
