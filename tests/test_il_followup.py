"""IL follow-up (Nov. 28, 2026): the fade, the secondary-pitch drop, the run-up index and the repeat rules on
hand-built fictional data, and the report's follow-up and broadcast numbers against the saved outputs."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from baseball.health import il_followup as F

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "outputs"
REPORT = (ROOT / "reports" / "2026-il-early-warning.md").read_text()


def _outing(game, date, velos, pitcher=1, pt="FF"):
    return [dict(pitcher=pitcher, game_pk=game, game_date=pd.Timestamp(date), game_year=2026, pitch_type=pt,
                 release_speed=v, at_bat_number=i // 4, pitch_number=i % 4) for i, v in enumerate(velos)]


def _apps(games):
    return pd.DataFrame([dict(pitcher=1, game_pk=g, game_date=pd.Timestamp(d), season=2026, starter=1) for g, d in games])


def test_fade_is_last_ten_minus_first_ten_against_his_own_usual():
    # four outings: three that fade 1 mph (95 -> 94), then one that fades 3 mph (95 -> 92)
    rows, games = [], []
    for k, late in enumerate([94.0, 94.0, 94.0, 92.0]):
        g, d = 100 + k, f"2026-05-{1 + 5 * k:02d}"
        rows += _outing(g, d, [95.0] * 10 + [94.5] * 5 + [late] * 10)
        games.append((g, d))
    f = F.fade_features(pd.DataFrame(rows), _apps(games)).set_index("game_pk")
    assert f.loc[100, "fade"] == pytest.approx(-1.0) and f.loc[103, "fade"] == pytest.approx(-3.0)
    # his usual fade before the fourth outing is -1.0, so he lost 2.0 mph more than usual
    assert f.loc[103, "fade_base"] == pytest.approx(-1.0) and f.loc[103, "fade_drop"] == pytest.approx(2.0)
    # the first three have fewer than three earlier outings: the base is the league mean by role
    assert f.loc[100, "fade_base"] == pytest.approx(np.mean([-1, -1, -1, -3]))


def test_fade_needs_twenty_fastballs():
    f = F.fade_features(pd.DataFrame(_outing(1, "2026-05-01", [95.0] * 19)), _apps([(1, "2026-05-01")]))
    assert f["fade"].isna().all()


def test_secondary_drop_against_earlier_outings():
    rows, games = [], []
    for k, v in enumerate([85.0, 85.0, 85.0, 83.0]):
        g, d = 200 + k, f"2026-06-{1 + 5 * k:02d}"
        rows += _outing(g, d, [v] * 6, pt="SL")
        games.append((g, d))
    s = F.secondary_features(pd.DataFrame(rows), _apps(games)).set_index("game_pk")
    assert np.isnan(s.loc[202, "drop_secondary"])               # only two earlier games of the class
    assert s.loc[203, "drop_secondary"] == pytest.approx(2.0)   # 85 baseline, 83 today


def test_streak_rule_counts_consecutive_outings_within_a_season():
    d = pd.DataFrame(dict(pitcher=[1] * 4 + [2] * 2, season=[2024] * 6, game_pk=range(6),
                          game_date=pd.date_range("2024-05-01", periods=6, freq="5D"),
                          drop_velo_1=[2.5, 2.1, 0.0, 2.2, 2.4, 0.3], y=[0, 1, 0, 0, 0, 0],
                          y_days=[np.nan, 3, np.nan, np.nan, np.nan, np.nan],
                          y_effective=[pd.NaT, pd.Timestamp("2024-05-09"), pd.NaT, pd.NaT, pd.NaT, pd.NaT],
                          y_lead_announced=[np.nan, 4, np.nan, np.nan, np.nan, np.nan]))
    d = pd.concat([d, d.assign(season=2026, game_pk=d["game_pk"] + 10)])
    r = F.streak_rules(d)
    assert r["streak_2.0"]["train"]["alerts"] == 1 and r["streak_2.0"]["train"]["true_alerts"] == 1   # outing 2 only
    assert r["single_2.0"]["train"]["alerts"] == 4


FU = json.loads((OUT / "il-followup-2026.json").read_text())
V = json.loads((OUT / "il-video-coding-2026.json").read_text())["cases"]


def test_run_up_matches_the_report():
    k = {x["k"]: x for x in FU["run_up"]["by_k"]["test"]}
    assert f"averaged {k[1]['mean_drop']:.2f} mph below his baseline in 2026" in REPORT
    assert k[1]["mean_drop"] > 4 * k[2]["mean_drop"]
    assert f"about {FU['outing_drop_sd_no_il']:.2f} mph" in REPORT


def test_new_signals_are_null_and_reported():
    for t in FU["terms"].values():
        assert t["fit_2024_25"]["p"] > 0.05 and t["fit_2024_25"]["q_bh"] > 0.05
        assert t["vs_velocity"]["auc"]["lo"] < 0 < t["vs_velocity"]["auc"]["hi"]
    s = FU["streak_rules"]["streak_2.0"]
    assert f"{s['train']['true_alerts']} of {s['train']['alerts']}" in REPORT and f"{s['test']['true_alerts']} of {s['test']['alerts']} on 2026" in REPORT


def test_broadcast_sample_is_balanced_and_matches_the_table():
    assert len(V) == 34 and sum(x["arm_il_within_14_days"] for x in V) == 17
    t = [x for x in V if x["arm_il_within_14_days"]]
    f = [x for x in V if not x["arm_il_within_14_days"]]
    assert sum(x["role"] == "starter" for x in t) == sum(x["role"] == "starter" for x in f)    # matched on role
    yes = lambda g, k, v="yes": sum(1 for x in g if x[k] == v)  # noqa: E731
    assert (yes(t, "viewer_call"), yes(f, "viewer_call")) == (4, 0)
    assert (yes(t, "announcer_concern"), yes(f, "announcer_concern")) == (7, 2)
    assert "| A viewer would think something was wrong: yes | 4 | 0 |" in REPORT
    obvious = [x for x in t if x["viewer_call"] == "yes"]
    assert all(x["days_to_il"] == 1 for x in obvious)
    quiet = sorted(x["days_to_il"] for x in t if x["viewer_call"] != "yes")
    assert len(quiet) == 13 and np.median(quiet) == 6 and "a median 6 days later" in REPORT
    assert REPORT.count("mlb.com/gameday/") == 34
