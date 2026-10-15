"""Delivery and release profile from Statcast: the tracking evidence behind a scouting report's delivery notes.

A scout grades a delivery by eye: slot, extension, repeatability, deception, effort. Tracking data measures
part of that and none of the rest. This module computes the measurable part, so a report can say which
delivery notes rest on data and which still need a look:

- `vaa()`: vertical approach angle at the front of the plate, exactly, from Statcast's own kinematics
  (vy0, vz0, ay, az at y = 50 ft). `physics.approach_angle()` is the approximation for devices without them.
- `pitch_profile()`: one pitcher's pitch types: velocity band (10th-90th percentile) and top, spin, shape,
  extension, release point, arm angle, release-point scatter (SD), VAA (all pitches and upper third),
  zone and low rates, whiffs per swing.
- `slot_check()`: each pitch's arm angle and release point against his primary pitch. A pitch released from
  a different slot is a possible tell, which a hitter-side look then confirms or rules out.
- `league_context()`: where his extension and arm angle rank among the season's pitchers (same hand), and
  the league's median release-point scatter by pitcher-pitch for comparison.
- `velo_by_pitch_count()`: the primary pitch's velocity by pitch number within the outing.
- `usage_by_count()`: pitch mix by count state and batter hand.
- `first_pitch_strike()`: his 0-0 strike rate against the league's.

Grain: input rows are pitches (raw Statcast columns, any phase; every function filters to the regular
season). Each output says its grain. Rates come from summed numerators and denominators.

Conventions:
- Arm side is positive for both hands: a left-hander's arm side is +x in Statcast's catcher view, a
  right-hander's is -x, so `hb_arm_in` and `rel_x_arm_ft` flip the right-hander's sign.
- Statcast's arm angle is degrees above horizontal at release (0 = sidearm, 90 = straight over the top).
- What this can't see: tempo, effort, landing direction, arm action, time to the plate, how he fields.
  Those stay NG (no grade) in a report until someone watches him.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from baseball.evaluation.arsenal import SWINGS, WHIFFS
from baseball.phases import phase

Y0 = 50.0                 # Statcast's initial-velocity plane, ft from the back of home plate
PLATE_Y = 17 / 12         # front of home plate, ft
LABEL_SPOTS = [(-30, -75, "right"), (40, 50, "left"), (10, -55, "left"), (-25, 55, "right")]  # label offsets (points), by usage rank
BALLS = ("ball", "blocked_ball", "hit_by_pitch", "pitchout", "intent_ball", "automatic_ball")


def vaa(pitches: pd.DataFrame) -> pd.Series:
    """Vertical approach angle (degrees) at the front of the plate. Negative = descending; closer to 0 = flatter.

    Constant acceleration from y = 50 ft: vy_f = -sqrt(vy0^2 - 2 ay (50 - 17/12)), t = (vy_f - vy0) / ay,
    vz_f = vz0 + az t, VAA = -atan(vz_f / vy_f).
    """
    vy0, ay = pitches["vy0"].astype(float), pitches["ay"].astype(float)
    vz0, az = pitches["vz0"].astype(float), pitches["az"].astype(float)
    vyf = -np.sqrt(vy0**2 - 2 * ay * (Y0 - PLATE_Y))
    t = (vyf - vy0) / ay
    vzf = vz0 + az * t
    return -np.degrees(np.arctan(vzf / vyf))


def _arm_sign(p: pd.DataFrame) -> pd.Series:
    return np.where(p["p_throws"] == "L", 1.0, -1.0)


def _prep(pitches: pd.DataFrame, pitcher: int | None = None) -> pd.DataFrame:
    p = phase(pitches, "regular")
    if pitcher is not None:
        p = p[p["pitcher"] == pitcher]
    p = p[p["pitch_type"].notna()].copy()
    sign = _arm_sign(p)
    p["ivb_in"] = p["pfx_z"] * 12
    p["hb_arm_in"] = p["pfx_x"] * 12 * sign
    p["rel_x_arm_ft"] = p["release_pos_x"] * sign
    p["vaa"] = vaa(p) if {"vy0", "vz0", "ay", "az"} <= set(p.columns) else np.nan
    p["is_swing"] = p["description"].isin(SWINGS)
    p["is_whiff"] = p["description"].isin(WHIFFS)
    p["in_zone"] = p["zone"].between(1, 9)
    p["is_low"] = p["plate_z"] < 2.0
    p["is_upper"] = p["plate_z"] > 3.0
    return p


def pitch_profile(pitches: pd.DataFrame, pitcher: int) -> pd.DataFrame:
    """Grain: one row per pitch type for one pitcher, regular season. Sorted by usage."""
    p = _prep(pitches, pitcher)
    if p.empty:
        return pd.DataFrame()
    g = p.groupby("pitch_type")
    out = g.agg(
        n=("release_speed", "size"),
        velo=("release_speed", "mean"),
        velo_p10=("release_speed", lambda s: s.quantile(0.10)),
        velo_p90=("release_speed", lambda s: s.quantile(0.90)),
        velo_max=("release_speed", "max"),
        spin=("release_spin_rate", "mean"),
        ivb_in=("ivb_in", "mean"),
        hb_arm_in=("hb_arm_in", "mean"),
        ext_ft=("release_extension", "mean"),
        rel_z_ft=("release_pos_z", "mean"),
        rel_x_arm_ft=("rel_x_arm_ft", "mean"),
        arm_angle=("arm_angle", "mean"),
        sd_rel_z_ft=("release_pos_z", "std"),
        sd_rel_x_ft=("release_pos_x", "std"),
        vaa=("vaa", "mean"),
        zone_n=("in_zone", "sum"),
        low_n=("is_low", "sum"),
        swings=("is_swing", "sum"),
        whiffs=("is_whiff", "sum"),
    ).reset_index()
    upper = p[p["is_upper"]].groupby("pitch_type")["vaa"].agg(vaa_upper="mean", n_upper="size").reset_index()
    out = out.merge(upper, on="pitch_type", how="left")
    out["n_upper"] = out["n_upper"].fillna(0).astype(int)
    out["usage_pct"] = 100 * out["n"] / out["n"].sum()
    out["zone_pct"] = 100 * out["zone_n"] / out["n"]
    out["low_pct"] = 100 * out["low_n"] / out["n"]
    out["whiff_pct"] = 100 * out["whiffs"] / out["swings"].where(out["swings"] > 0)
    return out.drop(columns=["zone_n", "low_n"]).sort_values("n", ascending=False).reset_index(drop=True)


def slot_check(profile: pd.DataFrame, primary: str | None = None) -> pd.DataFrame:
    """Grain: one row per pitch type. Arm angle (degrees) and release point (inches) against the primary pitch
    (the most used, unless named). Positive d_rel_x_arm_in = released farther to the arm side."""
    if profile.empty:
        return profile
    base = profile.set_index("pitch_type").loc[primary] if primary else profile.iloc[0]
    out = profile[["pitch_type", "n"]].copy()
    out["d_arm_angle"] = profile["arm_angle"] - base["arm_angle"]
    out["d_rel_z_in"] = 12 * (profile["rel_z_ft"] - base["rel_z_ft"])
    out["d_rel_x_arm_in"] = 12 * (profile["rel_x_arm_ft"] - base["rel_x_arm_ft"])
    out["d_ext_in"] = 12 * (profile["ext_ft"] - base["ext_ft"])
    return out


def league_context(pitches: pd.DataFrame, pitcher: int, min_pitches: int = 300, min_type: int = 200) -> dict:
    """Where his extension and arm angle rank among pitchers of his hand with `min_pitches`+ (percentile =
    share of those pitchers below him), plus league medians for release scatter (pitcher-pitch rows with
    `min_type`+ pitches) and VAA by pitch type (all pitches, and upper third)."""
    p = _prep(pitches)
    hand = p.loc[p["pitcher"] == pitcher, "p_throws"].iloc[0]
    per = p[p["p_throws"] == hand].groupby("pitcher").agg(n=("release_speed", "size"), ext=("release_extension", "mean"),
                                                          arm=("arm_angle", "mean"))
    per = per[per["n"] >= min_pitches]
    me = p[p["pitcher"] == pitcher]
    my_ext, my_arm = me["release_extension"].mean(), me["arm_angle"].mean()
    scatter = p.groupby(["pitcher", "pitch_type"]).agg(n=("release_speed", "size"), sdz=("release_pos_z", "std"),
                                                       sdx=("release_pos_x", "std"))
    scatter = scatter[scatter["n"] >= min_type]
    vaa_all = p.groupby("pitch_type")["vaa"].mean()
    vaa_up = p[p["is_upper"]].groupby("pitch_type")["vaa"].mean()
    return {
        "hand": hand,
        "pitchers": int(len(per)),
        "ext_ft": my_ext, "ext_pct": 100 * float((per["ext"] < my_ext).mean()),
        "ext_league_mean": float(per["ext"].mean()),
        "arm_angle": my_arm, "arm_pct": 100 * float((per["arm"] < my_arm).mean()),
        "arm_league_mean": float(per["arm"].mean()),
        "median_sd_rel_z_ft": float(scatter["sdz"].median()), "median_sd_rel_x_ft": float(scatter["sdx"].median()),
        "scatter_rows": int(len(scatter)),
        "vaa_league": vaa_all.to_dict(), "vaa_league_upper": vaa_up.to_dict(),
    }


def velo_by_pitch_count(pitches: pd.DataFrame, pitcher: int, pitch_type: str, edges: tuple[int, ...] = (15, 25)) -> pd.DataFrame:
    """Grain: one row per bucket of pitch number within the outing (1-15, 16-25, 26+ by default)."""
    p = _prep(pitches, pitcher).sort_values(["game_pk", "at_bat_number", "pitch_number"])
    p["k"] = p.groupby("game_pk").cumcount() + 1
    bins = [0, *edges, np.inf]
    labels = [f"{a + 1}-{b}" if np.isfinite(b) else f"{a + 1}+" for a, b in zip(bins[:-1], bins[1:])]
    p["bucket"] = pd.cut(p["k"], bins=bins, labels=labels)
    t = p[p["pitch_type"] == pitch_type].groupby("bucket", observed=False)["release_speed"].agg(n="size", velo="mean")
    return t.reset_index()


def outing_lengths(pitches: pd.DataFrame, pitcher: int) -> pd.Series:
    """Grain: one value per game, his pitch count (regular season, every pitch including unlabeled ones)."""
    p = phase(pitches, "regular")
    return p[p["pitcher"] == pitcher].groupby("game_pk").size()


def count_state(balls: pd.Series, strikes: pd.Series) -> pd.Series:
    """0-0, two strikes, behind (more balls than strikes), or even/ahead."""
    return pd.Series(np.select(
        [(balls == 0) & (strikes == 0), strikes == 2, balls > strikes],
        ["0-0", "2 strikes", "behind"], "even/ahead"), index=balls.index)


def usage_by_count(pitches: pd.DataFrame, pitcher: int) -> pd.DataFrame:
    """Grain: one row per count state x batter hand x pitch type, with n and the share within the state-hand."""
    p = _prep(pitches, pitcher)
    p["count_state"] = count_state(p["balls"], p["strikes"])
    t = p.groupby(["count_state", "stand", "pitch_type"]).size().rename("n").reset_index()
    t["share_pct"] = 100 * t["n"] / t.groupby(["count_state", "stand"])["n"].transform("sum")
    return t.sort_values(["count_state", "stand", "n"], ascending=[True, True, False]).reset_index(drop=True)


def first_pitch_strike(pitches: pd.DataFrame, pitcher: int) -> dict:
    """0-0 pitches that weren't balls (called, swinging, foul or in play), his rate and the league's."""
    p = phase(pitches, "regular")
    p = p[(p["balls"] == 0) & (p["strikes"] == 0) & (p["description"] != "intent_ball")]
    strike = ~p["description"].isin(BALLS)
    mine = p["pitcher"] == pitcher
    return {"n": int(mine.sum()), "strikes": int(strike[mine].sum()), "pct": 100 * float(strike[mine].mean()),
            "league_n": int(len(p)), "league_pct": 100 * float(strike.mean())}


def release_offsets(pitches: pd.DataFrame, pitcher: int) -> pd.DataFrame:
    """Grain: one row per pitch. Release side (arm side +) and height, in inches, and arm angle (degrees), measured from the mean release
    of the same game's fastballs (FF and SI), as the release-tells detector does: subtracting each game's
    fastball mean removes park-to-park camera calibration, leaving how a pitch leaves the hand differently."""
    p = _prep(pitches, pitcher)
    fb = p[p["pitch_type"].isin(("FF", "SI"))].groupby("game_pk")[["rel_x_arm_ft", "release_pos_z", "arm_angle"]].mean()
    p = p.join(fb, on="game_pk", rsuffix="_fb").dropna(subset=["rel_x_arm_ft_fb"])
    p["d_side_in"] = 12 * (p["rel_x_arm_ft"] - p["rel_x_arm_ft_fb"])
    p["d_height_in"] = 12 * (p["release_pos_z"] - p["release_pos_z_fb"])
    p["d_arm_deg"] = p["arm_angle"] - p["arm_angle_fb"]
    return p[["game_pk", "pitch_type", "d_side_in", "d_height_in", "d_arm_deg"]]


def figure(pitches: pd.DataFrame, pitcher: int, title: str, path: str) -> str:
    """Two panels for a scouting report: pitch movement, and where each pitch leaves the hand relative to the
    same game's fastballs (hand-normalized: arm side to the right for either hand)."""
    import matplotlib.pyplot as plt

    from baseball.viz import INK, MUTED, OTHER, PITCH_COLORS, _style, movement_plot

    p = phase(pitches, "regular")
    p = p[p["pitcher"] == pitcher]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 6.2), dpi=160)
    movement_plot(p, "Movement", "One dot per pitch; ringed dot = average", ax=a1)
    off = release_offsets(p, pitcher)
    _style(a2)
    a2.axhline(0, color=MUTED, lw=0.8)
    a2.axvline(0, color=MUTED, lw=0.8)
    g_names = p.dropna(subset=["pitch_type"]).groupby("pitch_type")["pitch_name"].first().to_dict() if "pitch_name" in p else {}
    placed: list[str] = []
    for code in off["pitch_type"].value_counts().index:
        g = off[off["pitch_type"] == code]
        color = PITCH_COLORS.get(code, OTHER)
        a2.scatter(g["d_side_in"], g["d_height_in"], s=9, color=color, alpha=0.25, linewidths=0)
        mx, my = g["d_side_in"].mean(), g["d_height_in"].mean()
        a2.scatter([mx], [my], s=90, color=color, edgecolors="white", linewidths=2, zorder=3)
        name = g_names.get(code, code)
        dx, dy, ha = LABEL_SPOTS[len(placed) % len(LABEL_SPOTS)]
        placed.append(code)
        a2.annotate(f"{name}\n{mx:+.1f} in. side, {my:+.1f} in. height", (mx, my), xytext=(dx, dy), ha=ha,
                    textcoords="offset points", fontsize=8.5, color=INK, zorder=4,
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.7),
                    bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.9))
    a2.set_xlim(-10, 12)
    a2.set_ylim(-7, 7)
    a2.set_aspect("equal")
    a2.set_xlabel("Release side vs. that game's fastballs, inches (arm side +)", color=MUTED, fontsize=9)
    a2.set_ylabel("Release height vs. that game's fastballs, inches", color=MUTED, fontsize=9)
    a2.set_title("Release point", loc="left", color=INK, fontsize=12, fontweight="bold", pad=22)
    a2.text(0, 1.015, "Arm side to the right; each game centered on its own fastballs", transform=a2.transAxes, color=MUTED, fontsize=8.5)
    fig.suptitle(title, x=0.01, ha="left", color=INK, fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path
