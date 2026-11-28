"""The IL early-warning figures on a white surface, from the saved outputs.

1. reports/figures/2026-il-early-warning.png: arm-IL rate by the outing's velocity drop (2024-25 and 2026), and the
   2026 calibration of the naive and tracking models (reports/outputs/il-warning-2026.json).
2. reports/figures/2026-il-run-up.png: his velocity drop in each of the last six scored outings before an arm IL
   stint, against outings with no arm stint in the next 30 days (reports/outputs/il-followup-2026.json).
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT, FIG = ROOT / "reports" / "outputs", ROOT / "reports" / "figures"
INK, MUTED, RULE = "#1a1a1a", "#5f6368", "#e3e6ea"
TRAIN, TEST = "#8e96a3", "#1a1a1a"            # 2024-25 grey, 2026 ink: the held-out season is the one to read
NAIVE, TRACK = "#285d9e", "#c8392b"


def _style() -> None:
    for f in (ROOT / "assets" / "fonts").glob("RobotoCondensed-*.ttf"):
        font_manager.fontManager.addfont(str(f))
    matplotlib.rcParams.update({"font.family": "Roboto Condensed", "text.color": INK, "axes.labelcolor": INK,
                                "xtick.color": MUTED, "ytick.color": MUTED, "figure.facecolor": "white",
                                "savefig.facecolor": "white", "axes.facecolor": "white", "axes.edgecolor": RULE,
                                "legend.frameon": False})


def _ax(ax) -> None:
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(color=RULE, lw=0.8)
    ax.set_axisbelow(True)


def main_figure(S: dict, path: Path) -> None:
    fig, (a, c) = plt.subplots(1, 2, figsize=(13.5, 5.6))
    tr, te = pd.DataFrame(S["velocity_bins"]["train"]), pd.DataFrame(S["velocity_bins"]["test"])
    x = np.arange(len(te))
    for off, d, col, lab in ((-0.14, tr, TRAIN, "2024-25 (fit)"), (0.14, te, TEST, "2026 (held out)")):
        a.errorbar(x + off, 100 * d["rate"], yerr=[100 * (d["rate"] - d["lo"]), 100 * (d["hi"] - d["rate"])],
                   fmt="o", color=col, capsize=3, lw=1.5, ms=7, label=lab, mec="white", mew=1.2)
    base = 100 * S["specs"]["arm_14"]["test"]["base_rate"]
    a.axhline(base, color=MUTED, lw=1, ls="--")
    a.text(len(te) - 0.6, base, f"2026 base rate {base:.1f}%", color=MUTED, fontsize=9.5, va="bottom", ha="right")
    a.set_xticks(x)
    a.set_xticklabels([f"{b}\n(n={n:,})" for b, n in zip(te["bin"], te["n"])], fontsize=9.5)
    a.set_xlabel("This outing's fastball velocity vs his regressed baseline (mph); n = 2026 outings")
    a.set_ylabel("Arm-injury IL placement within 14 days (%)")
    a.set_title("A big velocity drop goes with arm IL soon after", loc="left", fontsize=14, fontweight="bold")
    a.legend(fontsize=10, loc="upper left")
    _ax(a)
    for name, col in (("naive", NAIVE), ("tracking", TRACK)):
        d = pd.DataFrame(S["deciles"][name])
        c.errorbar(100 * d["predicted"], 100 * d["observed"], yerr=[100 * (d["observed"] - d["lo"]), 100 * (d["hi"] - d["observed"])],
                   fmt="o-", color=col, capsize=2, lw=1.5, ms=6, mec="white", mew=1.0,
                   label=f"{name.capitalize()} model (AUC {S['specs']['arm_14']['auc'][name]:.3f})")
    hi = 100 * max(max(pd.DataFrame(S["deciles"][k])["hi"]) for k in ("naive", "tracking"))
    c.plot([0, hi], [0, hi], color="#c4c9d0", lw=1.2)
    c.text(hi * 0.97, hi * 0.97, "perfect calibration", rotation=0, ha="right", va="bottom", fontsize=9, color=MUTED)
    c.set_xlabel("Predicted risk, decile mean (%)")
    c.set_ylabel("Observed rate in 2026 (%)")
    c.set_title("2026: the tracking model ranks risk no detectably better", loc="left", fontsize=14, fontweight="bold")
    c.legend(fontsize=10, loc="upper left")
    _ax(c)
    fig.text(0.01, 0.005, "Data: Statcast via Baseball Savant (regular season); MLB Stats API transactions. 95% Wilson "
             "intervals. Fit on 2024-25, scored on 2026. Chart: Dylan Fanelli.", fontsize=8.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, dpi=170)
    plt.close(fig)


def run_up_figure(F: dict, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.4))
    R = F["run_up"]
    for split, col, lab, off in (("train", TRAIN, "2024-25 stints", -0.08), ("test", TEST, "2026 stints", 0.08)):
        d = pd.DataFrame(R["by_k"][split]).sort_values("k", ascending=False)
        x = -d["k"].to_numpy() + off
        ax.errorbar(x, d["mean_drop"], yerr=1.96 * d["se"], fmt="o-", color=col, capsize=3, lw=1.6, ms=7,
                    mec="white", mew=1.2, label=lab)
        ctrl = R["control"][split]["mean_drop"]
        ax.axhline(ctrl, color=col, lw=1, ls=":")
    ax.text(-3.55, R["control"]["train"]["mean_drop"] - 0.03, "dotted: outings with no arm IL in the next 30 days",
            fontsize=9.5, color=MUTED, va="top")
    t = {x["k"]: x for x in R["by_k"]["train"]}
    ax.set_xticks(range(-6, 0))
    ax.set_xticklabels([f"{k} before\n(~{t[k]['median_days_before']:.0f} days)" if k > 1 else f"last outing\n(~{t[k]['median_days_before']:.0f} day)"
                        for k in range(6, 0, -1)], fontsize=10)
    ax.set_ylabel("Fastball velocity below his baseline (mph)")
    ax.set_title("The drop shows up in the last outing; before that it is a tenth or two", loc="left", fontsize=14,
                 fontweight="bold")
    sd = F["outing_drop_sd_no_il"]
    ax.text(0.0, -0.17, f"For scale: one healthy outing's drop moves around by about {sd:.2f} mph (one standard deviation). "
            "Bars are 95% intervals for the mean.", transform=ax.transAxes, fontsize=9.5, color=MUTED)
    ax.legend(fontsize=10, loc="upper left")
    _ax(ax)
    fig.text(0.01, 0.005, "Data: Statcast via Baseball Savant; MLB Stats API transactions. Arm IL stints with scored outings in "
             "the 30 days before. Chart: Dylan Fanelli.", fontsize=8.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, dpi=170)
    plt.close(fig)


def main() -> None:
    _style()
    main_figure(json.loads((OUT / "il-warning-2026.json").read_text()), FIG / "2026-il-early-warning.png")
    run_up_figure(json.loads((OUT / "il-followup-2026.json").read_text()), FIG / "2026-il-run-up.png")


if __name__ == "__main__":
    main()
