"""Portfolio presentation layer: README banner and photos, the at-a-glance panel, and the
standard header and footer on every report page (see docs/report-standard.md).

    uv run python docs/build_pages.py            # rebuild assets and re-stamp every report
    uv run python docs/build_pages.py --check    # fail if a report is missing its header

The header and footer sit between marker comments, so re-running replaces them and never touches
the report's own text. Numbers in PAGES and GLANCE are copied from each report's own answer; when a
report's answer changes, change it here too (tests/test_portfolio_pages.py checks the structure).
Photos are Dylan Fanelli's own (docs/photo-credits.md).
"""
from __future__ import annotations

import argparse
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
ASSETS = ROOT / "assets"
PHOTOS = ASSETS / "photos"
REPO = "https://github.com/IForSureI/Dylan-Fanelli-Baseball-Analytics-Portfolio"

PAPER, INK, MUTED, GREEN, CLAY = "#f6f3ec", "#1f1f1f", "#6b6b6b", "#1d5c3f", "#b4532a"

# ---------------------------------------------------------------------------------------------
# Photos: Dylan Fanelli's own, from his playing and scouting years (docs/photo-credits.md).
# Sources live in assets/img/src/ (re-saved without location or camera data). Values: caption, and
# where to center the crop (x, y as fractions of the photo).
# ---------------------------------------------------------------------------------------------
PHOTO = {
    "field_day": ("Harry & David Field, Medford, Oregon, home of the Medford Rogues", (0.5, 0.47)),
    "field_dusk": ("Charting a Rogues game from the press box, Harry & David Field", (0.5, 0.46)),
    "scouting": ("With the radar gun in the stands, Medford Rogues", (0.5, 0.42)),
    "allegheny": ("Allegheny College", (0.55, 0.42)),
    "oxy": ("Occidental College", (0.55, 0.45)),
    "rogues": ("Medford Rogues", (0.5, 0.40)),
    "umass": ("UMass Amherst", (0.47, 0.45)),
}
CAREER = ["allegheny", "oxy", "rogues", "umass"]
TRIM = {"field_dusk": (0, 0, 0.91, 1)}  # (left, top, right, bottom): cut the press-box window frame

# Report pages in reading order (the README's research table). Answers are the README's, which
# are the reports' own conclusions.
PAGES = [
    dict(slug="2026-bullpen-acquisition-memo", short="Bullpen memo", dept="GM and pro personnel",
         status="reviewed", tags=["decision memo", "contract pricing", "20-80 scouting"],
         question="Which reliever should the Rangers sign this winter, and at what price?",
         answer="Adrián Morejón. Open at 4 years, $60M; walk away above $72M, which lands him a little less than half the time. Bryan Abreu is the plan above that.",
         club="One real offseason decision made the way a front office makes it: the target, the opening offer, the walk-away and the plan if he goes elsewhere. The [one-page version](2026-bullpen-one-page.md) is what a GM reads."),
    dict(slug="2026-league-pitch-familiarity", short="Pitch familiarity", dept="Advance scouting and in-game strategy",
         status="reviewed", tags=["mixed models", "Statcast", "original question"],
         question="Does a pitch lose effectiveness on a hitter the more of it he has seen?",
         answer="Yes, and it is specific to the pitch type: an earlier changeup or splitter in his earlier plate appearances today, in place of a pitch of another type, goes with 1.87 fewer whiff points on the next one.",
         club="Tells a pitching coach which pitches spend down over a game and a series, and which ones keep their bite on the second and third look."),
    dict(slug="2026-shape-exposure", short="Shape exposure", dept="R&D",
         status="reviewed", tags=["pre-registered", "placebo test", "honest null"],
         question="Do hitters adapt to pitch shapes they have seen from other pitchers?",
         answer="The planned test can't say: the raw association replicated, then failed its own placebo. An exploratory follow-up finds a small recent effect, at most about 2 runs a club-season.",
         club="Shows how the department should handle a tempting result: write the test down first, run the placebo, and report what survives."),
    dict(slug="2026-exposure-aware-hook", short="Exposure-aware hook", dept="Manager and in-game strategy",
         status="reviewed", tags=["out-of-sample", "calibration", "decision rule"],
         question="Should what a hitter has seen change when the starter comes out?",
         answer="No. The per-pitch cost replicates out of sample but does not reach plate-appearance run value, and managers show no response to it either.",
         club="Saves a staff from adding a hook rule that would not win runs, with the calibration to show why."),
    dict(slug="2026-reliability-atlas", short="Reliability Atlas", dept="Every department that reads a number",
         status="reviewed", tags=["split-half reliability", "shrinkage", "replication"],
         question="Which numbers can you trust, and after how many pitches, swings or batted balls?",
         answer="Regressing beats raw numbers out of sample for 135 of the 147 metric groups that could be scored (of 157). Bat speed is half signal after about 3 swings; wOBA's fitted curve does not reach r = 0.5 until about 500 PA (an extrapolation).",
         club="One table every scout, coach and analyst can use to decide how much to believe a number and how far to regress it."),
    dict(slug="2026-pitch-design-levers", short="Pitch-design levers", dept="Player development",
         status="reviewed", tags=["development", "placebo test", "IDP"],
         question="Which pitch-design changes stick and pay?",
         answer="Four-seam ride is the best-supported lever (+1.62 whiff points per 2 in). Velocity's payoff fails a placebo, so selection or recovery isn't ruled out.",
         club="Points a pitching lab at the shape changes most likely to pay, and comes with an individual development plan format that tracks them."),
    dict(slug="2026-roster-cba-engine", short="Roster and CBA engine", dept="Front office and payroll",
         status="reviewed", tags=["CBA", "luxury tax", "extension pricing"],
         question="Should the Pirates extend Paul Skenes before the CBA expires on Dec. 1?",
         answer="Open at about $200M in present value and walk away above about $215M, priced under both possible rule sets. The tax engine reproduces 2025 luxury-tax bills within $1 for eight of nine clubs.",
         club="A payroll and service-time engine checked against real tax bills, and an extension price that holds up under the next agreement."),
    dict(slug="2026-trade-network-rivals", short="Trade network", dept="Pro scouting and trades",
         status="reviewed", tags=["Neo4j", "network analysis", "rate ratios"],
         question="Who trades with whom?",
         answer="Division rivals trade at 0.56 times the rate of other pairs (0.49-0.65), and 52 of 60 rival pairs fall below expectation. The deadline is the one window where they come closer to normal.",
         club="Tells a trade desk which partners are realistic and when rivals are most willing to deal."),
    dict(slug="2026-front-office-ties", short="Front-office ties", dept="Pro scouting and trades",
         status="reviewed", tags=["Poisson models", "permutation test", "Neo4j"],
         question="Do front-office ties predict trade partners?",
         answer="Yes, modestly: about 14-18% more trades in seasons when decision-makers share front-office history (1.18, 1.04-1.34). For scale, division rivalry is -45%.",
         club="Adds one more input to a trade-partner list: whose decision-makers have worked together."),
    dict(slug="2026-gm-tree", short="GM tree", dept="Front office",
         status="reviewed", tags=["Neo4j", "PageRank", "career paths"],
         question="Whose front offices did today's heads of baseball operations come through?",
         answer="More came through Cleveland than any other club: 15 worked there before their first head job. Since 2009 the median head took 14 years from his first front-office job.",
         club="A map of how front offices hire and promote, built as a graph a department can query."),
    dict(slug="2026-morejon-pro-scouting-report", short="Pro scouting report", dept="Pro scouting",
         status="reviewed", tags=["20-80 scouting", "Statcast", "role and risk"],
         question="What would a pro scout write on the top free-agent reliever?",
         answer="Adrián Morejón: OFP 60, a B1 reliever for 2027. Sinker, changeup and four-seamer grade 70; the slider is 50 now and 55 future.",
         club="The report a pro scouting director reads before a bid, with the look still needed written out."),
    dict(slug="2026-advance-packet-tb", short="Advance packet", dept="Advance scouting and coaches",
         status="reviewed", tags=["advance scouting", "coach-facing", "English and Spanish"],
         question="How should a club pitch the Rays' lineup in the ALCS?",
         answer="Pitch in the zone and get outs on weak contact: the nine regulars missed on 19.9% of swings (league 25.1%) and did little damage on contact (.331 xwOBA).",
         club="Hitter-by-hitter cards plus a one-page [coach version](2026-advance-packet-tb-coach.md), also [in Spanish](2026-advance-packet-tb-coach-es.md)."),
    dict(slug="2027-arbitration-brief-smith", short="Arbitration: Smith", dept="Front office and arbitration",
         status="reviewed", tags=["arbitration", "comp pool", "win odds"],
         question="What should a club file in Cade Smith's first arbitration case?",
         answer="$4.65M, settle at $5.0-5.1M, and go to a hearing above $5.1M. The club wins at a $5.275M midpoint about 60% of the time.",
         club="The club-side case from the comp pool to the walk point, under the CBA's criteria and what a panel can't hear."),
    dict(slug="2027-arbitration-brief-varland", short="Arbitration: Varland", dept="Front office and arbitration",
         status="reviewed", tags=["arbitration", "Super Two", "win odds"],
         question="Does the same method hold for a Super Two on another club?",
         answer="Yes. File $3.65M, settle between $3.7M and $3.8M (open at $3.7M), and go to a hearing above $3.8M; the club wins at a $3.85M midpoint about 61% of the time.",
         club="Shows the arbitration method travels: same rule, different club, a Super Two with four arbitration years."),
    dict(slug="2026-hitter-evaluation-torres", short="Hitter evaluation", dept="Pro personnel",
         status="reviewed", tags=["swing decisions", "bat tracking", "contract pricing"],
         question="Do good swing decisions last, and what is Gleyber Torres worth?",
         answer="Yes: decision value repeats year to year (r = 0.80). 1.50 WAR projected for 2027; sign at two years, $28-32M, walk away above $17M a year.",
         club="A free-agent hitter priced from the skill that repeats, with the bat-speed decline weighed against it."),
    dict(slug="2026-mlb-draft-analytics", short="Draft analytics", dept="Amateur scouting",
         status="summary", tags=["pick values", "out-of-sample", "bonus pools"],
         question="What is a draft pick worth, and does a college stat line still beat the pick?",
         answer="Pick 1 is worth about $75M before the bonus; from the second round on, the typical player returns nothing. A college-stat model no longer adds to the pick on 2020-2023 classes.",
         club="Pick values and bonus-pool math for the draft room, and an honest read on what public college lines still add."),
    dict(slug="2025-skubal-arsenal", short="Skubal arsenal", dept="Pitching and pro scouting",
         status="reviewed", tags=["arsenal analysis", "league context"],
         question="Was Tarik Skubal's 2025 change real?",
         answer="Yes, and the change was his: he ranked at the 80th-98th percentile on the changes while the league did not move. His changeup's 46.6% whiff rate is his true level.",
         club="Separates a pitcher's real change from a league-wide or measurement shift before anyone pays for it."),
    dict(slug="2026-edge-board", short="Edge Board", dept="R&D and pro scouting",
         status="Oct. 17 run", tags=["league scan", "release tells", "projections"],
         question="What changed across the league this month?",
         answer="Release tells, hidden in-season pitch changes (291 in 2026), results beyond stuff, and next-season whiff projections validated against a regressed baseline.",
         club="A list of leads for pro scouts and coaches, rebuilt by the toolkit on the 1st of each month."),
]
SUPPORT = {  # supporting pages: navigation back to their parent only
    "2026-bullpen-one-page": "2026-bullpen-acquisition-memo",
    "2026-advance-packet-tb-coach": "2026-advance-packet-tb",
    "2026-advance-packet-tb-coach-es": "2026-advance-packet-tb",
    "2026-shape-exposure-plan": "2026-shape-exposure",
    "2026-shape-exposure-followup-plan": "2026-shape-exposure",
    "2026-shape-exposure-dev-results": "2026-shape-exposure",
    "2026-shape-exposure-2026-results": "2026-shape-exposure",
}

# The at-a-glance panel: one headline number per study, with the study's own figure behind it.
GLANCE = [
    ("Bullpen memo", "$60M", "Open for Morejón at 4 years; walk away above $72M", "2026-bullpen-acquisition-memo.png"),
    ("Reliability Atlas", "135 of 147", "metric groups where regressing beats raw numbers out of sample", "2026-reliability-atlas.png"),
    ("Pitch familiarity", "-1.87", "whiff points on the next changeup or splitter when an earlier one today replaced another pitch", "2026-league-pitch-familiarity.png"),
    ("Pitch-design levers", "+1.62", "whiff points per 2 in of four-seam ride, the best-supported lever", "2026-pitch-design-levers.png"),
    ("Skenes extension", "$200M", "opening offer in present value; walk away above about $215M", "2026-skenes-extension-band.png"),
    ("Trade network", "0.56x", "how often division rivals trade, relative to other pairs", "2026-trade-network-rivals.png"),
    ("GM tree", "15", "future heads of baseball operations worked in Cleveland before their first head job", "2026-gm-tree.png"),
    ("Arbitration", "60%", "club's chance at a hearing at a $5.275M midpoint (Cade Smith; player's $5.9M filing inferred)", "2027-arbitration-brief-smith.png"),
]

H0, H1 = "<!-- portfolio:header -->", "<!-- /portfolio:header -->"
G0, G1 = "<!-- portfolio:glance -->", "<!-- /portfolio:glance -->"
F0, F1 = "<!-- portfolio:footer -->", "<!-- /portfolio:footer -->"


def _badge(label, msg, color):
    enc = lambda t: t.replace("-", "--").replace("_", "__").replace(" ", "%20").replace("/", "%2F").replace("+", "%2B")
    return f'<img src="https://img.shields.io/badge/{enc(label)}-{enc(msg)}-{color}" alt="{label}: {msg}">'


def _strip_blocks(text: str) -> str:
    for a, b in ((H0, H1), (G0, G1), (F0, F1)):
        text = re.sub(re.escape(a) + r".*?" + re.escape(b) + r"\n*", "", text, flags=re.S)
    return text.rstrip() + "\n"


def _money(s: str) -> str:
    """GitHub reads '$4.65M ... $5.0M' on one line as inline math; escape currency dollar signs."""
    return re.sub(r"(?<!\\)\$(?=\d)", r"\\$", s)


def stamp_reports() -> None:
    order = [p["slug"] for p in PAGES]
    for i, p in enumerate(PAGES):
        path = REPORTS / f"{p['slug']}.md"
        text = _strip_blocks(path.read_text())
        nav = ["[← Portfolio](../README.md)"]
        if i > 0:
            nav.append(f"[← {PAGES[i - 1]['short']}]({order[i - 1]}.md)")
        if i + 1 < len(PAGES):
            nav.append(f"[{PAGES[i + 1]['short']} →]({order[i + 1]}.md)")
        navline = "<sub>" + " &nbsp;|&nbsp; ".join(nav) + "</sub>"
        title = next(ln[2:].strip() for ln in text.split("\n") if ln.startswith("# "))
        header = f"{H0}\n{navline}\n{H1}\n\n"
        badges = " ".join([_badge("status", p["status"], "1d5c3f"), _badge("data", "public", "1f1f1f"),
                           _badge("for", p["dept"], "6b6b6b")] + [_badge("method", t, "b4532a") for t in p["tags"]])
        glance = (f"{G0}\n<p>{badges}</p>\n\n> **At a glance**\n> - **The question:** {p['question']}\n"
                  f"> - **The answer:** {_money(p['answer'])}\n> - **For a club:** {_money(p['club'])}\n{G1}\n\n")
        footer = (f"\n{F0}\n---\n{navline}\n\n<sub>© 2026 Dylan Fanelli. All rights reserved. To cite: Fanelli, D. (2026). "
                  f"*{title}*. Dylan Fanelli Baseball Analytics Portfolio. {REPO}/blob/main/reports/{p['slug']}.md</sub>\n{F1}\n")
        lines = text.split("\n")
        h = next(k for k, ln in enumerate(lines) if ln.startswith("# "))
        body = "\n".join(lines[:h + 1]) + "\n\n" + glance + "\n".join(lines[h + 1:]).lstrip("\n")
        path.write_text(header + body.rstrip() + "\n" + footer)
    for slug, parent in SUPPORT.items():
        path = REPORTS / f"{slug}.md"
        if not path.exists():
            continue
        text = _strip_blocks(path.read_text())
        pshort = next(p["short"] for p in PAGES if p["slug"] == parent)
        navline = f"<sub>[← Portfolio](../README.md) &nbsp;|&nbsp; Part of: [{pshort}]({parent}.md)</sub>"
        path.write_text(f"{H0}\n{navline}\n{H1}\n\n" + text + f"\n{F0}\n---\n{navline}\n{F1}\n")


def build_images() -> None:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    def font(names, size):
        for n in names:
            try:
                return ImageFont.truetype(n, size)
            except OSError:
                continue
        return ImageFont.load_default()

    from matplotlib import font_manager as fm
    def find(family, weight="normal"):
        try:
            return fm.findfont(fm.FontProperties(family=family, weight=weight), fallback_to_default=True)
        except Exception:
            return fm.findfont("DejaVu Sans")
    black = find("Inter Display", "black")
    reg = find("Inter")
    semi = find("Inter", "semibold")

    IMG = ASSETS / "img"
    SRC = IMG / "src"

    def open_src(key):
        im = Image.open(SRC / f"{key}.jpg").convert("RGB")
        if key in TRIM:
            l, t, r, b = TRIM[key]
            im = im.crop((int(l * im.width), int(t * im.height), int(r * im.width), int(b * im.height)))
        return im

    def crop(im, w, h, cx, cy):
        """Scale to cover w x h, then crop around (cx, cy)."""
        im = im.convert("RGB")
        s = max(w / im.width, h / im.height)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        x = int(max(0, min(im.width - w, cx * im.width - w / 2)))
        y = int(max(0, min(im.height - h, cy * im.height - h / 2)))
        return im.crop((x, y, x + w, y + h))

    # wide strips for the README
    for key in ("field_dusk", "scouting"):
        cap, (cx, cy) = PHOTO[key]
        crop(open_src(key), 1600, 420, cx, cy).save(IMG / f"strip-{key}.jpg", quality=84, optimize=True)
    # career tiles
    for key in CAREER:
        cap, (cx, cy) = PHOTO[key]
        crop(open_src(key), 600, 760, cx, cy).save(IMG / f"tile-{key}.jpg", quality=84, optimize=True)

    # banner: Harry & David Field, darkened on the left for the title
    W, H = 2000, 620
    cap, (cx, cy) = PHOTO["field_day"]
    im = crop(open_src("field_day"), W, H, cx, cy)
    shade = Image.new("L", (W, H))
    sd = ImageDraw.Draw(shade)
    for x in range(W):
        a = int(245 * max(0.0, 1 - x / (W * 0.80)) ** 0.9)
        sd.line([(x, 0), (x, H)], fill=a)
    dark = Image.new("RGB", (W, H), (14, 26, 20))
    im = Image.composite(dark, im, shade)
    d = ImageDraw.Draw(im, "RGBA")
    d.text((80, 150), "Baseball Analytics", font=font([black], 108), fill=(250, 248, 242))
    d.text((84, 290), "Front-office decisions, built on every public pitch of 2024-2026", font=font([reg], 38), fill=(235, 232, 222))
    d.text((84, 350), "and every MLB trade since 2009.", font=font([reg], 38), fill=(235, 232, 222))
    d.text((84, 440), "Dylan Fanelli  |  Python, SQL, Neo4j, R  |  Statcast", font=font([semi], 28), fill=(214, 168, 120))
    im.save(ASSETS / "banner.jpg", quality=86, optimize=True)

    # at-a-glance: 2 x 4 cards, headline number over the study's own figure
    CW, CH, PAD, TOP = 470, 420, 26, 150
    sheet = Image.new("RGB", (4 * CW + 5 * PAD, TOP + 2 * CH + 3 * PAD + 40), PAPER)
    d = ImageDraw.Draw(sheet)
    d.text((PAD, 40), "Selected studies at a glance", font=font([black], 46), fill=INK)
    d.text((PAD + 2, 102), "The headline number from each study, over the study's own figure.", font=font([reg], 24), fill=MUTED)
    for k, (name, big, label, fig) in enumerate(GLANCE):
        x = PAD + (k % 4) * (CW + PAD)
        y = TOP + (k // 4) * (CH + PAD)
        d.rounded_rectangle([x, y, x + CW, y + CH], 14, fill="white", outline="#e3ded2", width=2)
        d.text((x + 22, y + 18), name.upper(), font=font([semi], 19), fill=MUTED)
        d.text((x + 20, y + 46), big, font=font([black], 58), fill=GREEN)
        ly = y + 122
        for line in textwrap.wrap(label, 40):
            d.text((x + 22, ly), line, font=font([reg], 20), fill=INK)
            ly += 26
        th = Image.open(REPORTS / "figures" / fig).convert("RGB")
        th.thumbnail((CW - 40, CH - (ly - y) - 30), Image.LANCZOS)
        sheet.paste(th, (x + (CW - th.width) // 2, ly + 12))
    d.text((PAD, sheet.height - 36), "Data: Statcast via Baseball Savant, MLB Stats API, Baseball-Reference, Retrosheet, Chadwick register. Figures: Dylan Fanelli",
           font=font([reg], 18), fill=MUTED)
    sheet.save(ASSETS / "at-a-glance.png", optimize=True)


def check() -> list[str]:
    bad = []
    for p in PAGES:
        t = (REPORTS / f"{p['slug']}.md").read_text()
        for m in (H0, G0, F0, "**At a glance**"):
            if m not in t:
                bad.append(f"{p['slug']}: missing {m}")
    return bad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--no-images", action="store_true")
    a = ap.parse_args()
    if a.check:
        bad = check()
        print("\n".join(bad) or "all report pages meet the standard")
        sys.exit(1 if bad else 0)
    if not a.no_images:
        build_images()
    stamp_reports()
    print("pages stamped")


if __name__ == "__main__":
    main()
