"""Dylan's design rule (Nov. 9, 2026): no accent bars down the side of a block (a thick coloured left or right border
on a quote, callout, card or tooltip). Hairline column dividers (1px) are fine. This scans every page and template."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = [p for pat in ("docs/*.html", "baseball/**/*.html") for p in ROOT.glob(pat)]
STRIPE = re.compile(r"border-(?:left|right|inline-start|inline-end)(?:-width)?\s*:\s*(?:[2-9]|\d{2,})(?:\.\d+)?px"
                    r"|box-shadow\s*:\s*inset\s+-?(?:[2-9]|\d{2,})px\s+0")


def test_pages_exist():
    assert PAGES


def test_no_side_stripes():
    hits = [f"{p.relative_to(ROOT)}: {m.group(0)}" for p in PAGES for m in STRIPE.finditer(p.read_text())]
    assert not hits, "side-stripe accent bars are banned: " + "; ".join(hits)
