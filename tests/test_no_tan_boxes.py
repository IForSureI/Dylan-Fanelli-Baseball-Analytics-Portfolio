"""My packet never uses tan or cream callout boxes; panels stay white like the rest of the page."""
import colorsys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = [ROOT / "docs" / "offseason_template.html", ROOT / "docs" / "offseason" / "index.html"]


def _warm_tint(hexcode: str) -> bool:
    r, g, b = (int(hexcode[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hue, light, sat = colorsys.rgb_to_hls(r, g, b)
    return 0.07 < hue < 0.17 and light > 0.80 and sat > 0.15


def test_no_tan_or_cream_fills_on_the_packet():
    for page in PAGES:
        if not page.exists():
            continue
        text = page.read_text(encoding="utf-8", errors="ignore")
        css = " ".join(re.findall(r"<style[^>]*>(.*?)</style>", text, flags=re.S)) + " ".join(re.findall(r'style="([^"]*)"', text))
        tints = sorted({h for h in re.findall(r"#([0-9a-fA-F]{6})\b", css) if _warm_tint(h)})
        assert not tints, f"{page.name} uses tan/cream colors: {tints}"
        assert "class=\"callout\"" not in text, f"{page.name} still has a callout box"
