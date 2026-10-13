"""Build the portfolio page (docs/portfolio.html) from docs/portfolio_template.html.

Figures from reports/figures/ are inlined as data URIs so the page is one self-contained file.

    uv run python docs/build_portfolio.py
"""
from __future__ import annotations

import base64
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/IForSureI/Baseball/blob/main"


def build(out: Path = ROOT / "docs" / "portfolio.html") -> Path:
    html = (ROOT / "docs" / "portfolio_template.html").read_text()

    def img(m: re.Match) -> str:
        data = (ROOT / "reports" / "figures" / m.group(1)).read_bytes()
        return "data:image/png;base64," + base64.b64encode(data).decode()

    html = re.sub(r"\{\{IMG:([^}]+)\}\}", img, html)
    html = html.replace("{{REPO}}", REPO).replace("{{DATE}}", date.today().strftime("%B %-d, %Y"))
    out.write_text(html)
    return out


if __name__ == "__main__":
    print(build())
