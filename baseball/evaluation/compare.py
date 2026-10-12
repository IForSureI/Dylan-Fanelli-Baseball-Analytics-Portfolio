"""Compare one pitcher's arsenal across two samples: two seasons, first half vs second half,
regular season vs postseason.

Grain of the output: one row per pitch type thrown at least `min_n` times in either sample.

Two tables:
- shape   : what the pitch is (usage, velo, spin, movement) in each sample and the change
- results : whiff% in each sample with its 95% Wilson interval, the change, and a verdict

Verdict on the whiff change
- "real change"  : two-proportion test p < 0.05 and at least 30 swings in each sample
- "noise"        : p >= 0.05 with at least 30 swings in each sample
- "small sample" : fewer than 30 swings in either sample; don't read anything into it
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from baseball.evaluation.arsenal import arsenal_counts
from baseball.stats import two_proportion, wilson

MIN_SWINGS = 30


def compare_arsenals(before: pd.DataFrame, after: pd.DataFrame, min_n: int = 20) -> dict[str, pd.DataFrame]:
    """Shape and results tables comparing two samples of one pitcher. Labels: `_a` = before, `_b` = after."""
    a = arsenal_counts(before).drop(columns="pitch_name").set_index("pitch_type")
    b = arsenal_counts(after)
    names = b.set_index("pitch_type")["pitch_name"].combine_first(arsenal_counts(before).set_index("pitch_type")["pitch_name"])
    b = b.drop(columns="pitch_name").set_index("pitch_type")

    keep = sorted(
        set(a.index[a["n"] >= min_n]) | set(b.index[b["n"] >= min_n]),
        key=lambda t: -(b["n"].get(t, 0) + a["n"].get(t, 0)),
    )
    a, b = a.reindex(keep), b.reindex(keep)

    shape = pd.DataFrame(index=pd.Index(keep, name="pitch_type"))
    shape["pitch_name"] = names.reindex(keep)
    for col, digits in [("usage_pct", 1), ("velo", 1), ("spin", 0), ("ivb_in", 1), ("hb_arm_in", 1)]:
        shape[f"{col}_a"] = a[col].round(digits)
        shape[f"{col}_b"] = b[col].round(digits)
        shape[f"{col}_chg"] = (b[col] - a[col]).round(digits)

    rows = []
    for t in keep:
        ka, na = int(np.nan_to_num(a.at[t, "whiffs"])), int(np.nan_to_num(a.at[t, "swings"]))
        kb, nb = int(np.nan_to_num(b.at[t, "whiffs"])), int(np.nan_to_num(b.at[t, "swings"]))
        lo_a, hi_a = wilson(ka, na)
        lo_b, hi_b = wilson(kb, nb)
        _, p = two_proportion(ka, na, kb, nb)
        if min(na, nb) < MIN_SWINGS:
            verdict = "small sample"
        else:
            verdict = "real change" if p < 0.05 else "noise"
        rows.append(
            {
                "pitch_type": t,
                "swings_a": na, "whiff_pct_a": 100 * ka / na if na else np.nan,
                "whiff_ci_a": f"{100 * lo_a:.1f}-{100 * hi_a:.1f}" if na else "",
                "swings_b": nb, "whiff_pct_b": 100 * kb / nb if nb else np.nan,
                "whiff_ci_b": f"{100 * lo_b:.1f}-{100 * hi_b:.1f}" if nb else "",
                "whiff_chg": (100 * kb / nb if nb else np.nan) - (100 * ka / na if na else np.nan),
                "p_value": p,
                "verdict": verdict,
            }
        )
    results = pd.DataFrame(rows).set_index("pitch_type")
    results = results.round({"whiff_pct_a": 1, "whiff_pct_b": 1, "whiff_chg": 1, "p_value": 3})
    return {"shape": shape.reset_index(), "results": results.reset_index()}
