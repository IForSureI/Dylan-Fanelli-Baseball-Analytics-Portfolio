"""My pages never use tan, cream or warm-paper fills; every page is white with cool neutral rules, like the packet.

Covers every page under docs/ and the template each one is built from. Embedded data (club colors include
Arizona's sand) and inlined images are left out: only the page's own CSS, inline styles and drawing code are checked."""
import colorsys
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
TEMPLATES = [DOCS / "offseason_template.html", DOCS / "portfolio_template.html",
             ROOT / "baseball" / "postseason_web.html", ROOT / "baseball" / "edge" / "board_web.html"]
PAGES = sorted(DOCS.glob("*.html")) + sorted(DOCS.glob("*/*.html")) + [t for t in TEMPLATES if t.parent != DOCS]
# the warm paper the postseason page and the Edge Board used to sit on
OLD_PAPER = {"fffdf8", "f7f4ec", "efe9dc", "ebe7dd", "ddd8cc"}


def _warm_tint(hexcode: str) -> bool:
    r, g, b = (int(hexcode[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hue, light, sat = colorsys.rgb_to_hls(r, g, b)
    return 0.07 < hue < 0.17 and light > 0.80 and sat > 0.15


def _own_code(text: str) -> str:
    """The page without its embedded data (the JSON after `const DATA = ` or `const D = `) and inlined images."""
    for marker in ("const DATA = ", "const D = "):
        i = text.find(marker)
        if i >= 0 and text[i + len(marker)] in "{[":
            try:
                _, end = json.JSONDecoder().raw_decode(text, i + len(marker))
                text = text[:i] + text[end:]
            except ValueError:
                pass
    return re.sub(r"data:image/[a-z]+;base64,[A-Za-z0-9+/=]+", "", text)


def test_every_docs_page_and_template_is_covered():
    names = {p.name for p in PAGES}
    for need in ("postseason.html", "edge-board.html", "portfolio.html", "index.html", "offseason_template.html",
                 "portfolio_template.html", "postseason_web.html", "board_web.html"):
        assert need in names, need


def test_no_tan_or_cream_fills_on_any_page():
    for page in PAGES:
        text = _own_code(page.read_text(encoding="utf-8", errors="ignore"))
        hexes = {h.lower() for h in re.findall(r"#([0-9a-fA-F]{6})\b", text)}
        tints = sorted(h for h in hexes if _warm_tint(h))
        assert not tints, f"{page.name} uses tan/cream colors: {tints}"
        assert not OLD_PAPER & hexes, f"{page.name} keeps the warm paper: {sorted(OLD_PAPER & hexes)}"
        assert "class=\"callout\"" not in text, f"{page.name} still has a callout box"


def test_postseason_and_edge_board_sit_on_white():
    for page in (DOCS / "postseason.html", DOCS / "edge-board.html"):
        css = page.read_text(encoding="utf-8")
        assert re.search(r"--paper:\s*#ffffff", css) and re.search(r"--plate:\s*#ffffff", css), page.name
        assert re.search(r"body \{[^}]*background: #ffffff", css), page.name
