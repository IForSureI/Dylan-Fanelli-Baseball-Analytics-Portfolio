"""The packet is ready to hand a club: link preview tags, a byline, a print layout, keyboard and contrast
basics, and the portfolio page leads with it."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "docs" / "offseason" / "index.html").read_text(encoding="utf-8")
URL = "https://iforsurei.github.io/Dylan-Fanelli-Baseball-Analytics-Portfolio/offseason/"


def _meta(attr, key):
    m = re.search(rf'<meta {attr}="{re.escape(key)}" content="([^"]+)"', PAGE)
    return m.group(1) if m else None


def test_head_has_title_description_and_link_preview():
    assert "<title>2027 Offseason Decision Packet | Dylan Fanelli</title>" in PAGE
    assert PAGE.index("<title>") < PAGE.index("</head>")
    assert _meta("name", "description")
    assert _meta("property", "og:url") == URL
    assert _meta("property", "og:image") == URL + "og.png"
    assert _meta("name", "twitter:card") == "summary_large_image"
    assert 'rel="icon"' in PAGE
    from PIL import Image
    assert Image.open(ROOT / "docs" / "offseason" / "og.png").size == (1200, 630)


def test_footer_byline_has_linkedin_and_portfolio_and_no_email():
    foot = PAGE[PAGE.index("<footer"):PAGE.index("</footer>")]
    assert "https://www.linkedin.com/in/dylanfanelli/" in foot
    assert "github.com/IForSureI/Dylan-Fanelli-Baseball-Analytics-Portfolio" in foot
    assert "mailto:" not in PAGE and "@" not in foot


def test_print_stylesheet_prints_every_view_with_a_page_header():
    css = PAGE[PAGE.index("<style>"):PAGE.index("</style>")]
    assert "@media print" in css and "@page" in css and "@top-left" in css
    assert "break-inside:avoid" in css and "table-header-group" in css
    assert "function buildPrint()" in PAGE and 'id="print"' in PAGE


def test_headshots_have_alt_text_and_tabs_answer_the_keyboard():
    assert 'alt="${esc(p.name)} headshot"' in PAGE
    assert "ArrowRight" in PAGE and 'tabindex="0"' in PAGE


def _lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def test_text_colors_meet_aa_on_white():
    tokens = dict(re.findall(r"--([a-z-]+):(#[0-9a-f]{6})", PAGE[:PAGE.index("</style>")]))
    for t in ("ink", "muted", "teal-ink", "blue", "red", "green"):
        l = _lum(tokens[t])
        assert 1.05 / (l + 0.05) >= 4.5, t
    for fg, bg in (("green", "green-soft"), ("blue", "blue-soft"), ("muted", "grid")):
        a, b = _lum(tokens[fg]), _lum(tokens[bg])
        assert (max(a, b) + 0.05) / (min(a, b) + 0.05) >= 4.5, (fg, bg)


def test_decisions_open_with_what_id_do():
    assert "What I'd do" in PAGE and "function whatIdDo()" in PAGE


def test_portfolio_page_leads_with_the_packet():
    html = (ROOT / "docs" / "portfolio.html").read_text(encoding="utf-8")
    first_section = html.index("<section")
    assert html.index('href="offseason/"') < first_section
    assert 'id="offseason-packet"' in html[first_section:first_section + 200]
    assert URL in (ROOT / "README.md").read_text(encoding="utf-8")
