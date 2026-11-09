"""House style for every chart this package draws, matching the interactive pages.

Warm paper and plate surfaces, Be Vietnam Pro for titles and Bricolage Grotesque for everything else (both in
assets/fonts, OFL), words in ink, and a four-colour series order checked with the dataviz validator (lightness band,
chroma, colour-blind and normal-vision separation, contrast against the plate): blue, stitch red, green, ochre. Loaded with the package, so a
study picks it up the next time it runs; a chart that sets its own colours keeps them.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
from cycler import cycler
from matplotlib import font_manager
from matplotlib.figure import Figure

FONTS = Path(__file__).resolve().parents[1] / "assets" / "fonts"
DISPLAY, TEXT = "Be Vietnam Pro", "Bricolage Grotesque"
PAPER, PLATE = "#f7f4ec", "#fffdf8"
INK, MUTED, SOFT, GRID = "#1a1a1a", "#5b5a55", "#8e8c85", "#e8e4da"
SERIES = ["#285d9e", "#c8392b", "#2a8a6a", "#b5811a"]
ACCENT = SERIES[1]

_applied = False


def apply() -> None:
    """Register the fonts and set matplotlib's defaults. Safe to call more than once."""
    global _applied
    if _applied:
        return
    for f in sorted(FONTS.glob("*.ttf")):
        font_manager.fontManager.addfont(str(f))
    matplotlib.rcParams.update({
        "font.family": TEXT, "text.color": INK, "axes.labelcolor": INK, "axes.titlecolor": INK,
        "axes.titleweight": "bold", "axes.titlelocation": "left",
        "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": SOFT,
        "figure.facecolor": PAPER, "savefig.facecolor": PAPER, "axes.facecolor": PLATE,
        "grid.color": GRID, "axes.prop_cycle": cycler(color=SERIES),
        "legend.frameon": False,
    })
    _save = Figure.savefig

    def savefig(self, *args, **kwargs):
        # titles and suptitles in the display face where they fit; the paper colour unless the chart asked for another
        r = self.canvas.get_renderer()
        titles = [(ax, t) for ax in self.axes for t in (ax.title, ax._left_title, ax._right_title) if t.get_text()]
        for _, t in titles:
            t.set_fontfamily(DISPLAY)
        if any(t.get_window_extent(r).width > ax.get_window_extent(r).width for ax, t in titles):
            for _, t in titles:  # one face per figure: if any title outgrows its panel, all stay in the text face
                t.set_fontfamily(TEXT); t.set_fontweight("semibold")
        if self._suptitle is not None:
            self._suptitle.set_fontfamily(DISPLAY)
        kwargs.setdefault("facecolor", PAPER)
        if kwargs.get("facecolor") in ("white", "#ffffff", "w"):
            kwargs["facecolor"] = PAPER
        return _save(self, *args, **kwargs)

    Figure.savefig = savefig
    _applied = True
