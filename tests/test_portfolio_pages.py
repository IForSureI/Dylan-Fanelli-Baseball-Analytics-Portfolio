"""The portfolio pages hold together: every link and image on the front page and the report
pages resolves, and every report carries the standard header (docs/report-standard.md)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs"))

import build_pages  # noqa: E402

LINK = re.compile(r"(?:\]\(|src=\"|href=\")([^)\"#]+)")


def _local_targets(md: Path):
    for target in LINK.findall(md.read_text()):
        if target.startswith(("http://", "https://", "mailto:")) or target.startswith("../../issues"):
            continue
        yield target


def test_front_page_links_and_images_resolve():
    readme = ROOT / "README.md"
    missing = [t for t in _local_targets(readme) if not (ROOT / t).exists()]
    assert not missing, missing


def test_report_pages_links_and_images_resolve():
    missing = []
    for md in (ROOT / "reports").glob("*.md"):
        missing += [f"{md.name}: {t}" for t in _local_targets(md) if not (md.parent / t).resolve().exists()]
    assert not missing, missing


def test_every_report_meets_the_standard():
    assert build_pages.check() == []


def test_every_photo_has_a_source_and_no_location_data():
    from PIL import Image
    for key in build_pages.PHOTO:
        src = ROOT / "assets" / "img" / "src" / f"{key}.jpg"
        assert src.exists(), key
        exif = Image.open(src).getexif()
        assert 0x8825 not in exif, f"{key}: GPS data in the published photo"
