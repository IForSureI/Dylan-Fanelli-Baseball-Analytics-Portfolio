"""The hole-map figure in the Arozarena breakdown, drawn from reports/outputs/arozarena_approach.json: whiff per
swing and expected wOBA on contact in each Statcast zone, 2025 against 2026.

White surface, ink text, one sequential hue per measure (blue for whiffs, orange for damage). The season-over-season
tests are a table in the report, not a chart: each has its own unit, and one shared axis would flatten them.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "outputs"
FIG = ROOT / "reports" / "figures"
FONTS = ROOT / "assets" / "fonts"
INK, MUTED, RULE = "#1a1a1a", "#5f6368", "#d9dde3"
BLUES = LinearSegmentedColormap.from_list("b", ["#f4f8fe", "#b6d5f8", "#519ced", "#1b64be", "#0e3d7e"])
ORANGES = LinearSegmentedColormap.from_list("o", ["#fff6f0", "#fbc8a8", "#f47230", "#c4521a", "#7a300c"])


def _style() -> None:
    for f in FONTS.glob("RobotoCondensed-*.ttf"):
        font_manager.fontManager.addfont(str(f))
    matplotlib.rcParams.update({"font.family": "Roboto Condensed", "text.color": INK, "axes.labelcolor": INK,
                                "xtick.color": MUTED, "ytick.color": MUTED, "figure.facecolor": "white",
                                "savefig.facecolor": "white", "axes.facecolor": "white"})


# Statcast zones from the catcher's view: 1-9 inside, 11-14 the four outer corners
INNER = {z: ((z - 1) % 3 + 1, 3 - (z - 1) // 3) for z in range(1, 10)}       # (column, row) on a 5x5 board
OUTER = {11: (0, 2.5), 12: (2.5, 2.5), 13: (0, 0), 14: (2.5, 0)}


def _zone_board(ax, zones: dict, key: str, cmap, lo: float, hi: float, fmt) -> None:
    def val(z):
        v = zones.get(str(z), {}).get(key)
        return v["pct"] if isinstance(v, dict) else v

    def colour(v):
        return cmap(min(max((v - lo) / (hi - lo), 0), 1)) if v is not None else "#ffffff"

    def ink(v):
        return "white" if v is not None and (v - lo) / (hi - lo) > 0.62 else INK

    for z, (x, y) in OUTER.items():
        v = val(z)
        ax.add_patch(Rectangle((x, y), 2.5, 2.5, facecolor=colour(v), edgecolor="white", linewidth=2))
        tx, ty = x + (0.45 if x == 0 else 2.05), y + (0.45 if y == 0 else 2.05)
        ax.text(tx, ty, fmt(v), ha="center", va="center", fontsize=10, color=ink(v))
    for z, (c, r) in INNER.items():
        v = val(z)
        ax.add_patch(Rectangle((c, r), 1, 1, facecolor=colour(v), edgecolor="white", linewidth=2))
        ax.text(c + 0.5, r + 0.5, fmt(v), ha="center", va="center", fontsize=10.5, color=ink(v), fontweight="bold")
    ax.add_patch(Rectangle((1, 1), 3, 3, fill=False, edgecolor=INK, linewidth=1.2))
    ax.set_xlim(-0.05, 5.05)
    ax.set_ylim(-0.05, 5.05)
    ax.set_aspect("equal")
    ax.axis("off")


def hole_map(res: dict, path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(7.6, 8.2))
    rows = [("whiff", BLUES, 10, 50, lambda v: "" if v is None else f"{v:.0f}%", "Whiff per swing"),
            ("xwoba_con", ORANGES, 0.20, 0.60, lambda v: "" if v is None else f"{v:.3f}"[1:],
             "Expected wOBA on contact")]
    for i, (key, cmap, lo, hi, fmt, label) in enumerate(rows):
        for j, season in enumerate(("first", "second")):
            ax = axes[i, j]
            _zone_board(ax, res[season]["zones"], key, cmap, lo, hi, fmt)
            ax.set_title(f"{label}, {res['seasons'][j]}", loc="left", fontsize=12, fontweight="bold", color=INK, pad=6)
    fig.text(0.06, 0.965, "Where Arozarena misses and where he does damage", fontsize=16, fontweight="bold", color=INK)
    fig.text(0.06, 0.94, "Statcast zones from the catcher's view; he hits right-handed, so the right side is away from him. "
             "Box = strike zone.", fontsize=10, color=MUTED)
    fig.text(0.06, 0.018, "Data: Statcast pitch-level data, regular seasons, via Baseball Savant. Chart: Dylan Fanelli.",
             fontsize=8.5, color=MUTED)
    fig.subplots_adjust(left=0.05, right=0.97, top=0.9, bottom=0.05, hspace=0.18, wspace=0.08)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main() -> None:
    _style()
    res = json.loads((OUT / "arozarena_approach.json").read_text())
    hole_map(res, FIG / "2026-arozarena-holes.png")


if __name__ == "__main__":
    main()
