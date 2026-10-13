"""Individual development plans (IDPs) as data, and a progress engine that grades them from pitch data.

The plan follows the player-development standard: 2-4 priorities, each with a metric, a dated and sourced
baseline, a target with a date, a sample floor, the mechanism, the weekly process goal, an owner,
checkpoints, and the risk with a guard metric that would show the cost. Plans are YAML files
(examples/idp-*.yaml) checked by `validate_plan()` before anything runs.

The engine computes each priority's metric from the start of the plan period to the as-of date with a
standard error (jackknife over games, because pitches in one game share a day's body, weather and
mound), compares it with the baseline and the target, and returns a verdict:

  insufficient  the sample is under the priority's floor; no call
  on_track      a real move toward the target (z >= 1.96 against the baseline, both SEs counted) and not
                clearly short of pace: the target is reached, or the 95% interval reaches the on-pace value
                (pace: linear from start to target date, or "step" for offseason changes expected in full
                from day one)
  behind        a real move toward the target, but the interval sits short of the on-pace value
  inconclusive  no move distinguishable from the baseline, AND the sample couldn't have detected a move of
                the planned size (|target - baseline| < 1.96 x the combined SE): underpowered, not flat. A
                results number on a few hundred swings often lands here; the notes say so
  flat          no move distinguishable from the baseline, though a move of the planned size would have been
  wrong_way     a real move away from the target

Before anything runs, `power_check()` warns when a priority's planned change is smaller than the minimum
detectable change at its floor (the baseline's SE plus the expected SE at the floor sample), and says what
floor would detect it, or that none would given the baseline's own uncertainty.

Guards (the risk's own measure) read: ok / watch (point estimate past the limit, interval includes it) /
breached (the interval clears the limit on the wrong side) / insufficient.

Two notes come out of the same numbers: one for the coach (plain, what to keep doing) and one for the
front office (baseline -> now with n and interval, keep / adjust / stop, recommendation and the
condition that would reverse it).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from baseball.evaluation.arsenal import SWINGS, WHIFFS

# stat: (label, unit, n counts, kind)
STATS = {
    "velo": ("velocity", "mph", "pitches", "mean"),
    "ivb_in": ("induced vertical break", "in", "pitches", "mean"),
    "hb_arm_in": ("arm-side break", "in", "pitches", "mean"),
    "hb_glove_in": ("glove-side break (sweep)", "in", "pitches", "mean"),
    "spin": ("spin", "rpm", "pitches", "mean"),
    "ext_ft": ("extension", "ft", "pitches", "mean"),
    "rel_z_ft": ("release height", "ft", "pitches", "mean"),
    "rel_x_arm_ft": ("release side (arm side +)", "ft", "pitches", "mean"),
    "arm_angle": ("arm angle", "deg", "pitches", "mean"),
    "x_whiff_pct": ("expected whiff per swing (physics)", "%", "pitches", "mean"),
    "speed_gap": ("speed gap below the reference fastball", "mph", "pitches", "relative"),
    "separation_in": ("movement separation from the reference fastball", "in", "pitches", "relative"),
    "whiff_pct": ("whiff per swing", "%", "swings", "rate"),
    "csw_pct": ("called strikes + whiffs per pitch", "%", "pitches", "rate"),
    "zone_pct": ("in-zone rate", "%", "pitches", "rate"),
    "chase_pct": ("chase (swings at out-of-zone pitches)", "%", "out-of-zone pitches", "rate"),
    "usage_pct": ("usage", "%", "pitches (all types)", "rate"),
    "rv100": ("run value per 100 pitches (pitcher's view, + is good)", "runs", "pitches", "mean"),
}
VERDICTS = ("on_track", "behind", "inconclusive", "flat", "wrong_way", "insufficient")
CALL = {"on_track": "keep", "behind": "keep, add volume or time", "flat": "adjust the method",
        "inconclusive": "hold: the sample can't detect a change of the planned size",
        "wrong_way": "stop and reassess", "insufficient": "hold: sample under the floor"}
Z = 1.96


# ---------------------------------------------------------------- the plan as data

@dataclass
class Metric:
    stat: str
    pitch_type: str | None = None
    ref_pitch_type: str | None = None     # speed_gap and separation_in: the fastball it is measured against

    def label(self) -> str:
        lab, unit, _, _ = STATS[self.stat]
        pt = f"{self.pitch_type} " if self.pitch_type else ""
        ref = f" ({self.ref_pitch_type})" if self.ref_pitch_type else ""
        return f"{pt}{lab}{ref}, {unit}"


@dataclass
class Baseline:
    value: float
    n: int
    period: str
    source: str
    se: float | None = None


@dataclass
class Guard:
    metric: Metric
    limit: float
    keep: str            # "above" or "below": the side of the limit that is safe
    floor: int


@dataclass
class Priority:
    id: int
    skill: str
    metric: Metric
    baseline: Baseline
    target: float
    target_date: date
    floor: int
    mechanism: str
    process_goal: str
    owner: str
    checkpoints: list[date]
    risk: str
    guard: Guard | None = None
    pace: str = "linear"


@dataclass
class Plan:
    player: str
    pitcher: int | str
    label: str
    level: str
    role_now: str
    role_target: str
    period_start: date
    period_end: date
    authors: list[str]
    data_source: str
    priorities: list[Priority]
    player_voice: str = ""
    season: int | None = None
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)     # power_check() output


REQUIRED_PLAN = ["player", "pitcher", "label", "level", "role_now", "role_target", "period_start", "period_end",
                 "authors", "data_source", "priorities"]
REQUIRED_PRIORITY = ["skill", "metric", "baseline", "target", "target_date", "floor", "mechanism", "process_goal",
                     "owner", "checkpoints", "risk"]


def _date(x) -> date:
    return x if isinstance(x, date) else date.fromisoformat(str(x)[:10])


def _metric_errors(m, where: str) -> list[str]:
    if not isinstance(m, dict) or "stat" not in m:
        return [f"{where}: metric needs a 'stat'"]
    err = []
    if m["stat"] not in STATS:
        err.append(f"{where}: unknown stat '{m['stat']}' (one of {', '.join(STATS)})")
    elif STATS[m["stat"]][3] == "relative" and not (m.get("pitch_type") and m.get("ref_pitch_type")):
        err.append(f"{where}: {m['stat']} needs pitch_type and ref_pitch_type")
    elif m["stat"] != "rv100" and m["stat"] not in ("csw_pct", "zone_pct") and not m.get("pitch_type"):
        err.append(f"{where}: {m['stat']} needs a pitch_type")
    return err


def validate_plan(d: dict) -> list[str]:
    """Every problem with a plan dict, as sentences. Empty list = valid."""
    err = [f"plan: missing '{k}'" for k in REQUIRED_PLAN if k not in d or d[k] in (None, "", [])]
    if err:
        return err
    pri = d["priorities"]
    if not 2 <= len(pri) <= 4:
        err.append(f"plan: {len(pri)} priorities; a plan has 2-4 (more than four and nothing moves)")
    start, end = _date(d["period_start"]), _date(d["period_end"])
    if end <= start:
        err.append("plan: period_end must be after period_start")
    if d["data_source"] not in ("statcast", "fictional"):
        err.append("plan: data_source is 'statcast' or 'fictional'")
    if d["data_source"] == "fictional" and "FICTIONAL" not in str(d["label"]).upper():
        err.append("plan: fictional data must say FICTIONAL in its label")
    for i, p in enumerate(pri, 1):
        w = f"priority {i}"
        err += [f"{w}: missing '{k}'" for k in REQUIRED_PRIORITY if k not in p or p[k] in (None, "", [])]
        if any(k not in p for k in ("metric", "baseline", "target", "target_date", "floor", "checkpoints")):
            continue
        err += _metric_errors(p["metric"], w)
        b = p["baseline"]
        if not isinstance(b, dict) or not all(k in b for k in ("value", "n", "period", "source")):
            err.append(f"{w}: baseline needs value, n, period and source")
        elif float(b["value"]) == float(p["target"]):
            err.append(f"{w}: target equals the baseline; a goal has to move something")
        td = _date(p["target_date"])
        if not start < td <= end:
            err.append(f"{w}: target_date {td} is outside the plan period")
        if int(p["floor"]) <= 0:
            err.append(f"{w}: floor must be a positive sample size")
        for c in p["checkpoints"]:
            if not start <= _date(c) <= end:
                err.append(f"{w}: checkpoint {c} is outside the plan period")
        if p.get("pace", "linear") not in ("linear", "step"):
            err.append(f"{w}: pace is 'linear' or 'step'")
        g = p.get("guard")
        if g is not None:
            if not isinstance(g, dict) or not all(k in g for k in ("metric", "limit", "keep", "floor")):
                err.append(f"{w}: guard needs metric, limit, keep (above/below) and floor")
            else:
                err += _metric_errors(g["metric"], f"{w} guard")
                if g["keep"] not in ("above", "below"):
                    err.append(f"{w} guard: keep is 'above' or 'below'")
    return err


RATE_STATS = ("whiff_pct", "csw_pct", "zone_pct", "chase_pct", "usage_pct")


def power_check(d: dict) -> list[str]:
    """Warnings (not errors) for priorities whose planned change is smaller than the minimum detectable change
    at the floor: MDC = 1.96 x sqrt(SE_baseline^2 + SE_at_floor^2).

    SE_at_floor scales the baseline's SE by sqrt(n_baseline / floor). Without a baseline SE, rate stats use the
    binomial SE at the baseline rate; other stats can't be checked and get a warning saying so. When even an
    unlimited sample can't detect the change (the baseline's own SE is too large), the warning says that;
    otherwise it gives the floor that would."""
    out = []
    for i, p in enumerate(d.get("priorities", []), 1):
        b, stat = p["baseline"], p["metric"]["stat"]
        gap = abs(float(p["target"]) - float(b["value"]))
        n_b, floor = int(b["n"]), int(p["floor"])
        if b.get("se") is not None:
            se_b = float(b["se"])
        elif stat in RATE_STATS and 0 < float(b["value"]) < 100:
            q = float(b["value"]) / 100
            se_b = 100 * math.sqrt(q * (1 - q) / n_b)
        else:
            out.append(f"priority {i}: no baseline SE, so the minimum detectable change can't be checked")
            continue
        se_floor = se_b * math.sqrt(n_b / floor)
        mdc = Z * math.sqrt(se_b**2 + se_floor**2)
        if gap >= mdc:
            continue
        room = (gap / Z) ** 2 - se_b**2
        need = (f"a floor of about {math.ceil(se_b**2 * n_b / room):,} would" if room > 0 else
                "no floor would, because the baseline's own SE is too large; set a bigger target, a better-measured "
                "baseline, or treat it as a monitoring metric")
        out.append(f"priority {i}: the planned change ({gap:.2f}) is smaller than the minimum detectable change at the "
                   f"floor of {floor:,} ({mdc:.2f}); {need}")
    return out


def plan_from_dict(d: dict) -> Plan:
    errors = validate_plan(d)
    if errors:
        raise ValueError("Invalid plan:\n- " + "\n- ".join(errors))

    def metric(m):
        return Metric(m["stat"], m.get("pitch_type"), m.get("ref_pitch_type"))

    pri = []
    for i, p in enumerate(d["priorities"], 1):
        b = p["baseline"]
        g = p.get("guard")
        pri.append(Priority(
            id=i, skill=p["skill"], metric=metric(p["metric"]),
            baseline=Baseline(float(b["value"]), int(b["n"]), str(b["period"]), str(b["source"]),
                              float(b["se"]) if b.get("se") is not None else None),
            target=float(p["target"]), target_date=_date(p["target_date"]), floor=int(p["floor"]),
            mechanism=p["mechanism"], process_goal=p["process_goal"], owner=p["owner"],
            checkpoints=[_date(c) for c in p["checkpoints"]], risk=p["risk"],
            guard=Guard(metric(g["metric"]), float(g["limit"]), g["keep"], int(g["floor"])) if g else None,
            pace=p.get("pace", "linear")))
    return Plan(player=d["player"], pitcher=d["pitcher"], label=d["label"], level=d["level"], role_now=d["role_now"],
                role_target=d["role_target"], period_start=_date(d["period_start"]), period_end=_date(d["period_end"]),
                authors=list(d["authors"]), data_source=d["data_source"], priorities=pri,
                player_voice=d.get("player_voice", ""), season=d.get("season"), notes=list(d.get("notes", [])),
                warnings=power_check(d))


def load_plan(path: str | Path) -> Plan:
    import yaml

    with open(path) as f:
        return plan_from_dict(yaml.safe_load(f))


# ---------------------------------------------------------------- metrics with uncertainty

def _prep(p: pd.DataFrame) -> pd.DataFrame:
    p = p.dropna(subset=["pitch_type"]).copy()
    arm = np.where(p["p_throws"].eq("R"), -1.0, 1.0)
    p["velo"] = p["release_speed"]
    p["ivb_in"] = p["pfx_z"] * 12
    p["hb_arm_in"] = p["pfx_x"] * 12 * arm
    p["hb_glove_in"] = -p["hb_arm_in"]
    p["spin"] = p["release_spin_rate"]
    p["ext_ft"] = p["release_extension"]
    p["rel_z_ft"] = p["release_pos_z"]
    p["rel_x_arm_ft"] = p["release_pos_x"] * arm
    p["swing"] = p["description"].isin(SWINGS).astype(float)
    p["whiff"] = p["description"].isin(WHIFFS).astype(float)
    p["csw"] = (p["description"].eq("called_strike") | p["description"].isin(WHIFFS)).astype(float)
    p["in_zone"] = (p["zone"] <= 9).astype(float)
    p["out_zone"] = (p["zone"] > 9).astype(float)
    p["chase"] = p["out_zone"] * p["swing"]
    p["rv100"] = -100 * p["delta_run_exp"]
    if "x_whiff" in p:
        p["x_whiff_pct"] = 100 * p["x_whiff"]
    return p


def _components(p: pd.DataFrame, m: Metric) -> tuple[pd.DataFrame, callable, str]:
    """Per-game sums the statistic is built from, the function of the totals, and the column that is n."""
    t = p[p["pitch_type"].eq(m.pitch_type)] if m.pitch_type else p
    kind = STATS[m.stat][3]
    if kind == "mean":
        c = t.dropna(subset=[m.stat]).groupby("game_pk")[m.stat].agg(s="sum", n="count")
        return c, lambda T: T["s"] / T["n"], "n"
    if kind == "rate":
        if m.stat == "usage_pct":
            c = pd.DataFrame({"k": t.groupby("game_pk").size(), "n": p.groupby("game_pk").size()}).fillna(0)
        else:
            num, den = {"whiff_pct": ("whiff", "swing"), "csw_pct": ("csw", None), "zone_pct": ("in_zone", None),
                        "chase_pct": ("chase", "out_zone")}[m.stat]
            g = t.groupby("game_pk")
            c = pd.DataFrame({"k": g[num].sum(), "n": g[den].sum() if den else g.size()})
        return c, lambda T: 100 * T["k"] / T["n"], "n"
    # relative to a reference fastball
    r = p[p["pitch_type"].eq(m.ref_pitch_type)]
    cols = ["velo"] if m.stat == "speed_gap" else ["ivb_in", "hb_arm_in"]
    a = t.groupby("game_pk")[cols].agg(["sum", "count"])
    b = r.groupby("game_pk")[cols].agg(["sum", "count"])
    a.columns = [f"t_{x}_{y}" for x, y in a.columns]
    b.columns = [f"r_{x}_{y}" for x, y in b.columns]
    c = a.join(b, how="outer").fillna(0)
    c["n"] = c[f"t_{cols[0]}_count"]
    if m.stat == "speed_gap":
        return c, lambda T: T["r_velo_sum"] / T["r_velo_count"] - T["t_velo_sum"] / T["t_velo_count"], "n"
    return c, lambda T: np.hypot(T["t_ivb_in_sum"] / T["t_ivb_in_count"] - T["r_ivb_in_sum"] / T["r_ivb_in_count"],
                                 T["t_hb_arm_in_sum"] / T["t_hb_arm_in_count"] - T["r_hb_arm_in_sum"] / T["r_hb_arm_in_count"]), "n"


def jackknife(c: pd.DataFrame, f) -> tuple[float, float]:
    """Statistic f(totals) and its delete-one-game jackknife SE. c: one row of sums per game."""
    total = c.sum()
    value = float(f(total))
    G = len(c)
    if G < 2:
        return value, float("nan")
    loo = np.array([float(f(total - c.iloc[i])) for i in range(G)])
    loo = loo[np.isfinite(loo)]
    se = math.sqrt((G - 1) / G * float(((loo - loo.mean()) ** 2).sum()))
    return value, se


def estimate(pitches: pd.DataFrame, m: Metric, prepared: bool = False) -> dict:
    """The metric on these pitches: value, SE (jackknife by game), 95% interval, n and games."""
    p = pitches if prepared else _prep(pitches)
    if m.stat == "x_whiff_pct" and "x_whiff_pct" not in p:
        raise ValueError("x_whiff_pct needs an x_whiff column (score the pitches with the expected-whiff model first)")
    c, f, ncol = _components(p, m)
    if c.empty or c[ncol].sum() == 0:
        return {"value": float("nan"), "se": float("nan"), "lo": float("nan"), "hi": float("nan"), "n": 0, "games": 0}
    value, se = jackknife(c, f)
    return {"value": value, "se": se, "lo": value - Z * se, "hi": value + Z * se, "n": int(c[ncol].sum()),
            "games": int((c[ncol] > 0).sum())}


# ---------------------------------------------------------------- verdicts

def verdict(baseline: float, target: float, est: float, se: float, n: int, floor: int, expected_fraction: float,
            baseline_se: float | None = None) -> dict:
    """The verdict arithmetic for one priority (see module docstring)."""
    up = target > baseline
    sign = 1.0 if up else -1.0
    change = est - baseline
    sd = math.sqrt(se**2 + (baseline_se or 0.0) ** 2) if np.isfinite(se) else float("nan")
    z = change / sd if sd and np.isfinite(sd) else float("nan")
    toward = sign * z
    gap = target - baseline
    frac = change / gap
    reached = sign * (est - target) >= 0
    pace_value = baseline + expected_fraction * gap
    # short of pace only if the interval clears the on-pace value on the short side
    short = np.isfinite(sd) and sign * (est - pace_value) + Z * sd < 0
    if n < floor:
        v = "insufficient"
    elif np.isfinite(toward) and toward >= Z:
        v = "behind" if short and not reached else "on_track"
    elif np.isfinite(toward) and toward <= -Z:
        v = "wrong_way"
    elif np.isfinite(sd) and abs(expected_fraction * gap) < Z * sd:
        v = "inconclusive"    # the move the calendar expects by now is smaller than this sample can detect
    else:
        v = "flat"            # a move of the planned size would have shown; none did
    return {"change": change, "z": z, "fraction_closed": frac, "expected_fraction": expected_fraction,
            "pace_value": pace_value, "reached": bool(reached), "clear_of_baseline": bool(np.isfinite(z) and abs(z) >= Z),
            "detectable_change": Z * sd if np.isfinite(sd) else float("nan"), "verdict": v}


def expected_fraction(start: date, target_date: date, as_of: date, pace: str = "linear") -> float:
    """How much of the gap the calendar says should be closed by as_of."""
    if pace == "step":
        return 1.0
    total = (target_date - start).days
    return float(min(max((as_of - start).days / total, 0.0), 1.0)) if total > 0 else 1.0


def guard_status(g: Guard, est: dict) -> str:
    if est["n"] < g.floor or not np.isfinite(est["value"]):
        return "insufficient"
    bad_point = est["value"] < g.limit if g.keep == "above" else est["value"] > g.limit
    bad_ci = est["hi"] < g.limit if g.keep == "above" else est["lo"] > g.limit
    return "breached" if bad_ci else "watch" if bad_point else "ok"


def progress(plan: Plan, pitches: pd.DataFrame, as_of: date | str) -> pd.DataFrame:
    """Each priority's metric from the plan's start to as_of, against baseline and target. One row per priority."""
    as_of = _date(as_of)
    p = pitches.copy()
    p["game_date"] = pd.to_datetime(p["game_date"]).dt.date
    p = _prep(p[(p["game_date"] >= plan.period_start) & (p["game_date"] <= as_of)])
    rows = []
    for pr in plan.priorities:
        e = estimate(p, pr.metric, prepared=True)
        ef = expected_fraction(plan.period_start, pr.target_date, as_of, pr.pace)
        v = verdict(pr.baseline.value, pr.target, e["value"], e["se"], e["n"], pr.floor, ef, pr.baseline.se) \
            if e["n"] else {"change": np.nan, "z": np.nan, "fraction_closed": np.nan, "expected_fraction": ef,
                            "pace_value": np.nan, "reached": False, "clear_of_baseline": False,
                            "detectable_change": np.nan, "verdict": "insufficient"}
        row = {"priority": pr.id, "skill": pr.skill, "metric": pr.metric.label(), "baseline": pr.baseline.value,
               "baseline_period": pr.baseline.period, "value": e["value"], "se": e["se"], "lo": e["lo"], "hi": e["hi"],
               "n": e["n"], "n_unit": STATS[pr.metric.stat][2], "games": e["games"], "floor": pr.floor,
               "target": pr.target, "target_date": pr.target_date.isoformat(), "as_of": as_of.isoformat(), **v,
               "call": CALL[v["verdict"]], "owner": pr.owner, "process_goal": pr.process_goal}
        if pr.guard is not None:
            ge = estimate(p, pr.guard.metric, prepared=True)
            row.update({"guard": pr.guard.metric.label(), "guard_limit": pr.guard.limit, "guard_keep": pr.guard.keep,
                        "guard_value": ge["value"], "guard_lo": ge["lo"], "guard_hi": ge["hi"], "guard_n": ge["n"],
                        "guard_status": guard_status(pr.guard, ge)})
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- notes

def _f(x: float, unit: str = "") -> str:
    if x is None or not np.isfinite(x):
        return "n/a"
    digits = 0 if unit == "rpm" else 2 if unit == "ft" else 1
    return f"{x:,.{digits}f}"


def coach_note(plan: Plan, rows: pd.DataFrame) -> str:
    """Plain language for the pitching coach: the number, the direction, what to keep doing."""
    say = {"on_track": "On track.", "behind": "Moving the right way, slower than planned.",
           "flat": "Not moving: a change this size would have shown by now.",
           "inconclusive": "Can't tell yet: the number bounces around more than the change we're after.",
           "wrong_way": "Going the wrong way.",
           "insufficient": "Not enough pitches yet to tell."}
    do = {"on_track": "Keep doing", "behind": "Keep doing, with more reps", "flat": "Time to try a different cue or grip; so far",
          "inconclusive": "Keep doing", "wrong_way": "Stop and talk it through before the next session; so far",
          "insufficient": "Keep doing"}
    out = [f"*{plan.label}*", f"**{plan.player}: where the plan stands on {rows['as_of'].iloc[0]}**", ""]
    for _, r in rows.iterrows():
        unit = STATS[plan.priorities[r["priority"] - 1].metric.stat][1]
        out.append(f"- **{r['priority']}. {r['skill']}.** {r['metric']}: {_f(r['value'], unit)} on {r['n']:,} {r['n_unit']} "
                   f"(started at {_f(r['baseline'], unit)}; goal {_f(r['target'], unit)} by {r['target_date']}). "
                   f"{say[r['verdict']]} {do[r['verdict']]}: {r['process_goal']}.")
        if isinstance(r.get("guard"), str):
            gunit = STATS[plan.priorities[r["priority"] - 1].guard.metric.stat][1]
            out.append(f"  - Watch: {r['guard']} at {_f(r['guard_value'], gunit)} (stay {r['guard_keep']} "
                       f"{_f(r['guard_limit'], gunit)}): {r['guard_status']}.")
    return "\n".join(out)


def front_office_note(plan: Plan, rows: pd.DataFrame) -> str:
    """One paragraph per priority with numbers, n and interval; keep / adjust / stop; a recommendation with
    the condition that would reverse it."""
    out = [f"*{plan.label}*", f"**Progress note: {plan.player} ({plan.level}, {plan.role_now} -> {plan.role_target}), "
           f"{plan.period_start.isoformat()} to {rows['as_of'].iloc[0]}**", ""]
    for _, r in rows.iterrows():
        pr = plan.priorities[r["priority"] - 1]
        unit = STATS[pr.metric.stat][1]
        trend = "up" if r["change"] > 0 else "down" if r["change"] < 0 else "flat"
        closed = "n/a" if not np.isfinite(r["fraction_closed"]) else f"{100 * r['fraction_closed']:.0f}%"
        line = (f"**Priority {r['priority']}: {r['skill']}.** {r['metric']}: {_f(r['baseline'], unit)} ({r['baseline_period']}) → "
                f"{_f(r['value'], unit)} (95% interval {_f(r['lo'], unit)} to {_f(r['hi'], unit)}; n = {r['n']:,} {r['n_unit']}, "
                f"{r['games']} games; floor {r['floor']:,}). Target {_f(r['target'], unit)} by {r['target_date']}. "
                f"Trend {trend} (z = {r['z']:.1f} against the baseline); {closed} of the gap closed against "
                f"{100 * r['expected_fraction']:.0f}% expected by now"
                + (" (the point estimate is at or past the target, but not yet distinguishable from the baseline)"
                   if r["reached"] and not r["clear_of_baseline"] and r["verdict"] != "insufficient" else "")
                + (f"; at this sample only a change of {_f(r['detectable_change'], unit)} or more is detectable"
                   if r["verdict"] == "inconclusive" else "")
                + f". **Verdict: {r['verdict'].replace('_', ' ')}. {r['call'].capitalize()}.**")
        if isinstance(r.get("guard"), str):
            gunit = STATS[pr.guard.metric.stat][1]
            line += (f" Guard ({pr.risk}): {r['guard']} {_f(r['guard_value'], gunit)} "
                     f"({_f(r['guard_lo'], gunit)} to {_f(r['guard_hi'], gunit)}), limit {r['guard_keep']} "
                     f"{_f(r['guard_limit'], gunit)}: {r['guard_status']}.")
        out.append(line)
        out.append("")
    v = rows["verdict"].tolist()
    g = rows.get("guard_status", pd.Series(dtype=str)).fillna("").tolist()
    if "breached" in g:
        k = rows.loc[rows["guard_status"].eq("breached"), "priority"].tolist()
        rec = (f"review priority {', '.join(map(str, k))} with the coach: its guard is breached, so the risk the plan named "
               "is showing; would change if the guard metric recovers inside its limit at the next checkpoint")
    elif "wrong_way" in v:
        k = rows.loc[rows["verdict"].eq("wrong_way"), "priority"].tolist()
        rec = f"stop priority {', '.join(map(str, k))} and reassess the mechanism; would change if the next sample at the floor returns inside the baseline's range"
    elif "flat" in v or "behind" in v:
        k = rows.loc[rows["verdict"].isin(["flat", "behind"]), "priority"].tolist()
        rec = (f"continue the plan, adjusting the method on priority {', '.join(map(str, k))}; would change to a stop if it is "
               "still flat at the next checkpoint with the sample over the floor")
    elif all(x in ("insufficient", "inconclusive") for x in v):
        rec = "no call yet; every priority is under its sample floor or can't detect a change of the planned size"
    elif "inconclusive" in v:
        k = rows.loc[rows["verdict"].eq("inconclusive"), "priority"].tolist()
        rec = (f"continue the plan; priority {', '.join(map(str, k))} can't be graded at this sample, so judge it on its "
               "process goal and the shape behind it; would change if a priority falls back inside its baseline's interval")
    else:
        rec = "continue the plan as written; would change if any priority falls back inside its baseline's interval at the next checkpoint"
    out.append(f"**Recommendation:** {rec}.")
    return "\n".join(out)


def table_md(plan: Plan, rows: pd.DataFrame) -> str:
    """Markdown progress table."""
    L = ["| # | Metric | Baseline | Now (95% interval) | n | Target by | Gap closed / expected | Verdict | Guard |",
         "|---|---|---|---|---|---|---|---|---|"]
    for _, r in rows.iterrows():
        unit = STATS[plan.priorities[r["priority"] - 1].metric.stat][1]
        closed = "n/a" if not np.isfinite(r["fraction_closed"]) else f"{100 * r['fraction_closed']:.0f}%"
        guard = f"{r['guard_status']} ({_f(r['guard_value'])})" if isinstance(r.get("guard"), str) else "-"
        L.append(f"| {r['priority']} | {r['metric']} | {_f(r['baseline'], unit)} | {_f(r['value'], unit)} "
                 f"({_f(r['lo'], unit)} to {_f(r['hi'], unit)}) | {r['n']:,} | {_f(r['target'], unit)} by {r['target_date']} | "
                 f"{closed} / {100 * r['expected_fraction']:.0f}% | **{r['verdict'].replace('_', ' ')}** | {guard} |")
    return "\n".join(L)


# ---------------------------------------------------------------- data for a plan

def fictional_pitches(season: int = 2027, seed: int = 3, pitcher_id: int = 990001) -> pd.DataFrame:
    """FICTIONAL. A made-up right-handed starter's season (Statcast columns) for the example plan:
    four-seamer whose ride climbs through April then holds (~+1.6 in), a sweeper that adds sweep slowly,
    a changeup whose speed gap doesn't move. Not real data."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(f"{season}-03-30", f"{season}-09-25", freq="5D")
    rows = []
    arsenal = [  # type, share, velo, pfx_x (ft, catcher view; RHP arm side is -), pfx_z (ft), spin, whiff
        ("FF", 0.50, 94.0, -0.65, 1.30, 2300, 0.21),
        ("ST", 0.30, 82.5, 1.05, 0.05, 2600, 0.31),
        ("CH", 0.20, 86.0, -1.20, 0.50, 1700, 0.30),
    ]
    shares = np.array([a[1] for a in arsenal])
    for gi, d in enumerate(dates):
        prog = min(gi / 5, 1.0)                                # ride arrives over the first five starts
        sweep = gi / len(dates)                                # sweep builds all season
        for k in range(int(rng.integers(85, 101))):
            i = rng.choice(3, p=shares)
            code, _, velo, px, pz, spin, wr = arsenal[i]
            if code == "FF":
                pz = pz + prog * 1.6 / 12
                wr = wr + 0.03 * prog
            if code == "ST":
                px = px + sweep * 2.0 / 12
            zone = int(rng.integers(1, 10)) if rng.random() < 0.5 else int(rng.choice([11, 12, 13, 14]))
            swing = rng.random() < (0.68 if zone <= 9 else 0.30)
            r = rng.random()
            desc = ("swinging_strike" if r < wr else "foul" if r < wr + 0.4 else "hit_into_play") if swing else \
                ("called_strike" if zone <= 9 and rng.random() < 0.55 else "ball")
            rows.append({"game_pk": 9_000_000 + gi, "game_date": d.date().isoformat(), "pitcher": pitcher_id,
                         "player_name": "Fictional, Pitcher", "p_throws": "R", "stand": "R" if rng.random() < 0.5 else "L",
                         "pitch_type": code, "description": desc, "zone": zone,
                         "release_speed": velo + rng.normal(0, 0.8), "pfx_x": px + rng.normal(0, 0.12),
                         "pfx_z": pz + rng.normal(0, 0.12), "release_spin_rate": spin + rng.normal(0, 60),
                         "release_extension": 6.4 + rng.normal(0, 0.1), "release_pos_x": -1.9 + rng.normal(0, 0.08),
                         "release_pos_z": 5.8 + rng.normal(0, 0.08), "arm_angle": 42 + rng.normal(0, 1.5),
                         "delta_run_exp": (-0.05 if desc == "swinging_strike" else 0.03 if desc == "ball" else
                                           -0.04 if desc == "called_strike" else rng.normal(0.03, 0.25))})
    return pd.DataFrame(rows)


def pitches_for(plan: Plan) -> pd.DataFrame:
    """The plan's pitch data: the fictional generator, or the pitcher's regular-season Statcast pitches from the
    sequence copy for the plan's season."""
    if plan.data_source == "fictional":
        return fictional_pitches(plan.period_start.year)
    from baseball.development.levers import COLUMNS, load

    season = plan.season or plan.period_start.year
    p = load([season])
    return p[p["pitcher"].eq(int(plan.pitcher))][[c for c in COLUMNS if c in p.columns]].reset_index(drop=True)


def checkpoint_table(plan: Plan, pitches: pd.DataFrame, dates: list[date] | None = None) -> pd.DataFrame:
    """Progress at every checkpoint date in the plan (or the dates given), stacked."""
    ds = sorted(set(dates or [c for pr in plan.priorities for c in pr.checkpoints]))
    return pd.concat([progress(plan, pitches, d) for d in ds], ignore_index=True)


def progress_figure(plan: Plan, pitches: pd.DataFrame, out_path: str | Path) -> Path:
    """One panel per priority: the metric to date after every game (line) with its 95% interval (band), the
    baseline (dashed) and the target (solid, from the start for step pace or rising to it for linear),
    checkpoint dates as vertical rules. Dates before the floor is reached are drawn faint."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from baseball.viz import INK, MUTED, PITCH_COLORS, _style

    p = pitches.copy()
    p["game_date"] = pd.to_datetime(p["game_date"]).dt.date
    p = _prep(p[(p["game_date"] >= plan.period_start) & (p["game_date"] <= plan.period_end)])
    days = sorted(p["game_date"].unique())
    k = len(plan.priorities)
    fig, axes = plt.subplots(1, k, figsize=(4.6 * k, 3.9), squeeze=False)
    for ax, pr in zip(axes[0], plan.priorities):
        est = [estimate(p[p["game_date"] <= d], pr.metric, prepared=True) | {"date": d} for d in days]
        e = pd.DataFrame(est)
        c = PITCH_COLORS.get(pr.metric.pitch_type, MUTED)
        ok = e["n"] >= pr.floor
        x = pd.to_datetime(e["date"])
        ax.fill_between(x[ok], e.loc[ok, "lo"], e.loc[ok, "hi"], color=c, alpha=0.18, lw=0)
        ax.plot(x, e["value"], color=c, lw=0.8, alpha=0.35)
        ax.plot(x[ok], e.loc[ok, "value"], color=c, lw=2)
        ax.axhline(pr.baseline.value, color=MUTED, ls="--", lw=1)
        start, td = pd.Timestamp(plan.period_start), pd.Timestamp(pr.target_date)
        if pr.pace == "step":
            ax.axhline(pr.target, color=INK, lw=1)
        else:
            ax.plot([start, td, pd.Timestamp(plan.period_end)], [pr.baseline.value, pr.target, pr.target], color=INK, lw=1)
        for cp in pr.checkpoints:
            ax.axvline(pd.Timestamp(cp), color=MUTED, lw=0.6, ls=":")
        ax.set_title(f"{pr.id}. {pr.skill}", loc="left", fontsize=10.5, fontweight="bold", color=INK, pad=16)
        ax.text(0, 1.01, f"baseline {_f(pr.baseline.value)} (dashed) · target {_f(pr.target)} (solid)", transform=ax.transAxes,
                fontsize=7.5, color=MUTED, va="bottom")
        ax.set_ylabel(pr.metric.label(), fontsize=8.5, color=MUTED)
        ax.tick_params(axis="x", labelrotation=30, labelsize=8)
        _style(ax)
    source = ("Fictional pitches (not real data)" if plan.data_source == "fictional" else
              f"Statcast via Baseball Savant, {plan.season or plan.period_start.year} regular season")
    fig.text(0.01, 0.01, f"{plan.label}.\n{source}, {plan.period_start.isoformat()} to {plan.period_end.isoformat()}. "
             "Metric to date after each game with a 95% interval (jackknife by game); faint before the sample floor. "
             "Dotted: checkpoints.", fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    return out_path


def review(path: str | Path, as_of: date | str | None = None, pitches: pd.DataFrame | None = None) -> str:
    """The whole review as markdown: the label, verdicts at every checkpoint up to as_of (default: the plan's
    end), then the progress table and both notes as of that date."""
    plan = load_plan(path)
    as_of = _date(as_of) if as_of else plan.period_end
    p = pitches if pitches is not None else pitches_for(plan)
    cps = sorted({c for pr in plan.priorities for c in pr.checkpoints if c <= as_of} | {as_of})
    ct = checkpoint_table(plan, p, cps)
    grid = ct.pivot(index="priority", columns="as_of", values="verdict")
    L = [f"# IDP review: {plan.player}", f"*{plan.label}*", ""]
    if plan.warnings:
        L += ["## Power warnings (from the plan, before any data)", *[f"- {w}" for w in plan.warnings], ""]
    L += ["## Verdict at each checkpoint",
         "| # | " + " | ".join(grid.columns) + " |", "|---|" + "---|" * len(grid.columns)]
    for k, r in grid.iterrows():
        L.append(f"| {k} | " + " | ".join(v.replace("_", " ") for v in r) + " |")
    rows = ct[ct["as_of"].eq(as_of.isoformat())].reset_index(drop=True)
    L += ["", f"## Progress as of {as_of.isoformat()}", table_md(plan, rows), "", "## Coach note", coach_note(plan, rows),
          "", "## Front-office note", front_office_note(plan, rows)]
    return "\n".join(L)
