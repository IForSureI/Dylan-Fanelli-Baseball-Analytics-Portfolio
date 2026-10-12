"""Shared chart styling so every chart in the repo reads the same way.

Pitch colors are fixed per pitch type (color follows the pitch, never its rank), checked for
color-blind separation with the dataviz validator. Three of them are light against white, so
every chart also labels each pitch directly; color is never the only cue.
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PITCH_COLORS = {
    "FF": "#2a78d6",  # four-seamer: blue
    "SI": "#eb6834",  # sinker: orange
    "FC": "#008300",  # cutter: green
    "CH": "#1baf7a",  # changeup: aqua
    "FS": "#1baf7a",  # splitter: shares the changeup's color (same job)
    "SL": "#eda100",  # slider: yellow
    "ST": "#c98500",  # sweeper: dark yellow (slider family)
    "CU": "#e87ba4",  # curveball: magenta
    "KC": "#d55181",  # knuckle curve: dark magenta (curveball family)
    "SV": "#d55181",  # slurve
}
OTHER = "#8a8a8a"
INK, MUTED, GRID = "#1f1f1f", "#6b6b6b", "#e6e6e4"


def _style(ax: plt.Axes) -> None:
    ax.set_facecolor("#fcfcfb")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def movement_plot(pitches: pd.DataFrame, title: str, subtitle: str = "", min_n: int = 20, ax: plt.Axes | None = None) -> plt.Figure:
    """Pitch movement from the pitcher's view: arm side to the right, rise up. One dot per pitch,
    a ringed marker at each pitch type's average, and a direct label beside it."""
    p = pitches.dropna(subset=["pitch_type", "pfx_x", "pfx_z"]).copy()
    keep = p["pitch_type"].value_counts().loc[lambda s: s >= min_n].index
    p = p[p["pitch_type"].isin(keep)]
    p["ivb_in"] = p["pfx_z"] * 12
    p["hb_arm_in"] = np.where(p["p_throws"].eq("R"), -p["pfx_x"], p["pfx_x"]) * 12

    fig, ax = (ax.figure, ax) if ax is not None else plt.subplots(figsize=(7.5, 7.5), dpi=150)
    _style(ax)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.axvline(0, color=MUTED, lw=0.8)

    order = p["pitch_type"].value_counts().index
    for code in order:
        g = p[p["pitch_type"] == code]
        color = PITCH_COLORS.get(code, OTHER)
        name = g["pitch_name"].iloc[0] if "pitch_name" in g else code
        ax.scatter(g["hb_arm_in"], g["ivb_in"], s=9, color=color, alpha=0.28, linewidths=0, label=f"{name} ({len(g):,})")
        mx, my = g["hb_arm_in"].mean(), g["ivb_in"].mean()
        ax.scatter([mx], [my], s=90, color=color, edgecolors="white", linewidths=2, zorder=3)
        ax.annotate(f"{name}\n{g['release_speed'].mean():.1f} mph", (mx, my), xytext=(10, 6), textcoords="offset points",
                    fontsize=8.5, color=INK, zorder=4,
                    bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.85))

    ax.set_xlim(-25, 25)
    ax.set_ylim(-25, 25)
    ax.set_aspect("equal")
    ax.set_xlabel("Horizontal break, inches (arm side +)", color=MUTED, fontsize=9)
    ax.set_ylabel("Induced vertical break, inches", color=MUTED, fontsize=9)
    ax.set_title(title, loc="left", color=INK, fontsize=12, fontweight="bold", pad=22)
    if subtitle:
        ax.text(0, 1.015, subtitle, transform=ax.transAxes, color=MUTED, fontsize=8.5)
    leg = ax.legend(loc="lower left", fontsize=8, frameon=False, markerscale=2.5, labelcolor=INK)
    for handle in leg.legend_handles:
        handle.set_alpha(1)
    fig.tight_layout()
    return fig
