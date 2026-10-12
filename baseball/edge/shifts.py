"""Hidden in-season changes: the date one pitch changed, and whether results followed.

Season averages blend the before and after of a mid-season change (a new grip, a new slider
shape, a velocity jump after an IL stint) into one number that describes neither. This detector
finds the game where a pitch's shape changed and splits the season there.

Method, per pitcher x pitch type x metric (velo, IVB, arm-side HB, spin, arm angle):
1. Game-level sufficient statistics (n, sum, sum of squares) in date order.
2. Every split with at least MIN_GAMES_SIDE games on each side is scored with Welch's t on the
   pitch-level values. The best split is kept.
3. It's a finding only if it is big (MIN_SHIFT for the metric), strong (|t| >= MIN_T, a high bar
   because many splits are tried), and persistent (most games after the split sit on the new side).
4. Isolation check: the same metric's change across the same split for his OTHER pitches.
   - "this pitch only"      : others moved < 40% as much -> a deliberate change to this pitch
   - "all pitches"          : others moved >= 60% as much, same direction -> delivery, health,
                              or a measurement change; not a pitch-design change
   - "partly shared"        : in between
5. Results before vs after for that pitch: whiff% per swing (two-proportion test), xwOBA on contact,
   and usage share (did the club lean on it more after the change?).

Grain of the output: one row per detected change (pitcher x pitch type x metric).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from baseball.evaluation.arsenal import SWINGS, WHIFFS
from baseball.stats import two_proportion

METRICS = {
    # column: (label, minimum shift worth reporting)
    "release_speed": ("velocity (mph)", 1.0),
    "ivb_in": ("induced vertical break (in)", 1.5),
    "hb_arm_in": ("arm-side break (in)", 1.5),
    "release_spin_rate": ("spin (rpm)", 125.0),
    "arm_angle": ("arm angle (deg)", 2.5),
}
MIN_GAMES_SIDE = 3
MIN_PITCHES_PER_GAME = 4
MIN_GAMES = 8
MIN_T = 6.0
MIN_PERSISTENCE = 0.75


def _prepare(p: pd.DataFrame) -> pd.DataFrame:
    p = p.dropna(subset=["pitch_type"]).copy()
    p["ivb_in"] = p["pfx_z"] * 12
    p["hb_arm_in"] = np.where(p["p_throws"].eq("R"), -p["pfx_x"], p["pfx_x"]) * 12
    p["game_date"] = pd.to_datetime(p["game_date"])
    return p


def _best_split(games: pd.DataFrame) -> tuple[int, float, float, float]:
    """games: ordered rows with n, s, ss. Returns (k = first 'after' index, shift, t, persistence)."""
    n, s, ss = games["n"].to_numpy(float), games["s"].to_numpy(float), games["ss"].to_numpy(float)
    cn, cs, css = np.cumsum(n), np.cumsum(s), np.cumsum(ss)
    N, S, SS = cn[-1], cs[-1], css[-1]
    best = (-1, 0.0, 0.0)
    for k in range(MIN_GAMES_SIDE, len(games) - MIN_GAMES_SIDE + 1):
        n1, s1, ss1 = cn[k - 1], cs[k - 1], css[k - 1]
        n2, s2, ss2 = N - n1, S - s1, SS - ss1
        m1, m2 = s1 / n1, s2 / n2
        v1 = max((ss1 - n1 * m1**2) / max(n1 - 1, 1), 1e-9)
        v2 = max((ss2 - n2 * m2**2) / max(n2 - 1, 1), 1e-9)
        t = (m2 - m1) / np.sqrt(v1 / n1 + v2 / n2)
        if abs(t) > abs(best[2]):
            best = (k, m2 - m1, t)
    k, shift, t = best
    if k < 0:
        return k, 0.0, 0.0, 0.0
    means = s / n
    m1 = cs[k - 1] / cn[k - 1]
    midpoint = m1 + shift / 2
    after = means[k:]
    persistence = float(np.mean(after > midpoint) if shift > 0 else np.mean(after < midpoint))
    return k, float(shift), float(t), persistence


def _game_stats(p: pd.DataFrame, col: str) -> pd.DataFrame:
    g = (
        p.dropna(subset=[col])
        .groupby(["game_date", "game_pk"])[col]
        .agg(n="size", s="sum", ss=lambda x: float(np.square(x).sum()))
        .reset_index()
        .sort_values(["game_date", "game_pk"])
    )
    return g[g["n"] >= MIN_PITCHES_PER_GAME].reset_index(drop=True)


SHAPE = ["release_speed", "ivb_in", "hb_arm_in"]


def _label_check(p: pd.DataFrame, pt: str, split_date) -> str:
    """Is this a real change, or Statcast relabeling another pitch as this one?

    If the pitch's shape after the split sits closer to a different pitch type's shape before the
    split than to its own, the 'change' may be a label moving between pitches. Distance is in mph and
    inches on velocity, IVB and arm-side break.
    """
    before, after = p[p["game_date"] < split_date], p[p["game_date"] >= split_date]
    own_b = before[before["pitch_type"] == pt][SHAPE].mean()
    own_a = after[after["pitch_type"] == pt][SHAPE].mean()
    if own_b.isna().any() or own_a.isna().any():
        return "ok"
    own_dist = float(np.sqrt(((own_a - own_b) ** 2).sum()))
    for other, o in before[before["pitch_type"] != pt].groupby("pitch_type"):
        if len(o) < 30:
            continue
        d = float(np.sqrt(((own_a - o[SHAPE].mean()) ** 2).sum()))
        if d < own_dist:
            return f"possible relabel from {other}"
    return "ok"


def _results(p: pd.DataFrame) -> dict:
    sw = p["description"].isin(SWINGS)
    wh = p["description"].isin(WHIFFS)
    bip = p[p["type"].eq("X")]
    return {
        "swings": int(sw.sum()),
        "whiffs": int(wh.sum()),
        "xwoba_con": float(bip["estimated_woba_using_speedangle"].mean()) if len(bip) else np.nan,
        "bip": len(bip),
    }


def pitcher_shifts(pitches: pd.DataFrame) -> pd.DataFrame:
    """Every qualifying in-season change for one pitcher-season."""
    p = _prepare(pitches)
    if p.empty:
        return pd.DataFrame()
    rows = []
    for pt, g in p.groupby("pitch_type"):
        for col, (label, min_shift) in METRICS.items():
            games = _game_stats(g, col)
            if len(games) < MIN_GAMES:
                continue
            k, shift, t, persistence = _best_split(games)
            if k < 0 or abs(shift) < min_shift or abs(t) < MIN_T or persistence < MIN_PERSISTENCE:
                continue
            split_date = games.loc[k, "game_date"]
            before_mask, after_mask = p["game_date"] < split_date, p["game_date"] >= split_date

            # Isolation: the same metric on his other pitches, across the same split
            others = p[~p["pitch_type"].eq(pt)].dropna(subset=[col])
            other_shifts, weights = [], []
            for _, o in others.groupby("pitch_type"):
                ob, oa = o[o["game_date"] < split_date][col], o[o["game_date"] >= split_date][col]
                if len(ob) >= 30 and len(oa) >= 30:
                    other_shifts.append(oa.mean() - ob.mean())
                    weights.append(min(len(ob), len(oa)))
            if other_shifts:
                ratio = float(np.average(other_shifts, weights=weights) / shift)
                scope = "this pitch only" if ratio < 0.4 else ("all pitches" if ratio >= 0.6 else "partly shared")
            else:
                ratio, scope = np.nan, "no other pitch to compare"

            label_check = _label_check(p, pt, split_date)
            b, a = _results(g[g["game_date"] < split_date]), _results(g[g["game_date"] >= split_date])
            _, p_whiff = two_proportion(b["whiffs"], b["swings"], a["whiffs"], a["swings"])
            usage_b = (p.loc[before_mask, "pitch_type"] == pt).mean()
            usage_a = (p.loc[after_mask, "pitch_type"] == pt).mean()
            rows.append(
                {
                    "pitch_type": pt,
                    "pitch_name": g["pitch_name"].iloc[0] if "pitch_name" in g else pt,
                    "metric": label,
                    "split_date": split_date.date().isoformat(),
                    "games_before": k,
                    "games_after": len(games) - k,
                    "before": (games["s"][:k].sum() / games["n"][:k].sum()),
                    "after": (games["s"][k:].sum() / games["n"][k:].sum()),
                    "shift": shift,
                    "t": t,
                    "persistence": persistence,
                    "others_ratio": ratio,
                    "scope": scope,
                    "label_check": label_check,
                    "usage_before_pct": 100 * usage_b,
                    "usage_after_pct": 100 * usage_a,
                    "swings_before": b["swings"],
                    "whiff_before_pct": 100 * b["whiffs"] / b["swings"] if b["swings"] else np.nan,
                    "swings_after": a["swings"],
                    "whiff_after_pct": 100 * a["whiffs"] / a["swings"] if a["swings"] else np.nan,
                    "whiff_p": p_whiff,
                    "xwoba_con_before": b["xwoba_con"],
                    "xwoba_con_after": a["xwoba_con"],
                }
            )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    meta = pitches.iloc[0]
    out.insert(0, "pitcher", int(meta["pitcher"]))
    out.insert(1, "player_name", meta["player_name"])
    out.insert(2, "season", int(meta["game_year"]))
    return out.sort_values("t", key=np.abs, ascending=False).reset_index(drop=True)


def league_shifts(pitches: pd.DataFrame) -> pd.DataFrame:
    parts = [s for _, g in pitches.groupby("pitcher", sort=False) if not (s := pitcher_shifts(g)).empty]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def score_shifts(shifts_df: pd.DataFrame, swings: pd.DataFrame) -> pd.DataFrame:
    """Add two judgments to each detected change.

    - x_whiff_before / _after / x_whiff_change: the stuff model's expected whiff% for the pitch on either
      side of the split. Physics-based, so far less noisy than actual whiffs: it says whether the change
      made the pitch better by its shape, before results have had time to show it.
    - whiff_q: false-discovery-rate q-value for the actual whiff change across all changes tested.
    `swings` must carry pitcher, pitch_type, game_date and x_whiff (stuff.prepare + fit_crossfit).
    """
    from baseball.stats import benjamini_hochberg

    out = shifts_df.copy()
    if out.empty:
        return out
    s = swings[["pitcher", "pitch_type", "game_date", "x_whiff"]].copy()
    s["game_date"] = pd.to_datetime(s["game_date"])
    before, after = [], []
    for row in out.itertuples():
        g = s[(s["pitcher"] == row.pitcher) & (s["pitch_type"] == row.pitch_type)]
        split = pd.Timestamp(row.split_date)
        b, a = g.loc[g["game_date"] < split, "x_whiff"], g.loc[g["game_date"] >= split, "x_whiff"]
        before.append(100 * b.mean() if len(b) else np.nan)
        after.append(100 * a.mean() if len(a) else np.nan)
    out["x_whiff_before"] = before
    out["x_whiff_after"] = after
    out["x_whiff_change"] = out["x_whiff_after"] - out["x_whiff_before"]
    out["whiff_q"] = benjamini_hochberg(out["whiff_p"])
    return out
