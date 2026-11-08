"""Hover breakdowns behind the portfolio page's number labels (docs/num-details.json): every label on the
page has one, and every number in a breakdown appears in the report it cites."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "docs" / "portfolio_template.html"
DETAILS = json.loads((ROOT / "docs" / "num-details.json").read_text())
NUM = re.compile(r"[0-9][0-9,.]*[0-9]|[0-9]")


def labels():
    return re.findall(r'<span class="num[^"]*">([^<]*)</span>', TEMPLATE.read_text())


def test_every_label_has_a_breakdown():
    have = {d["chip"] for d in DETAILS}
    assert set(labels()) <= have
    assert len(DETAILS) == len(have)


def test_every_breakdown_matches_a_label():
    assert {d["chip"] for d in DETAILS} <= set(labels())


def test_breakdown_numbers_come_from_the_report():
    for d in DETAILS:
        text = (ROOT / d["report"]).read_text()
        if "coach" in d["report"]:
            text += (ROOT / d["report"].replace(".md", "-es.md")).read_text()
        assert 1 <= len(d["rows"]) <= 6 and d["title"]
        for piece in [d["title"], d["note"], *(v for row in d["rows"] for v in row)]:
            for n in NUM.findall(piece):
                assert n in text, f"{d['chip']}: {n} not in {d['report']}"


def test_anchors_point_at_report_headings():
    for d in DETAILS:
        if not d["anchor"]:
            continue
        heads = re.findall(r"^#+\s+(.*)$", (ROOT / d["report"]).read_text(), re.M)
        slugs = {re.sub(r"\s", "-", re.sub(r"[^\w\s-]", "", h.strip().lower())) for h in heads}
        assert d["anchor"].lstrip("#") in slugs, f"{d['chip']}: {d['anchor']}"
