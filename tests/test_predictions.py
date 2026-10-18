"""Prediction log: validation, Brier arithmetic, calibration and rendering. Every call here is FICTIONAL and
built in the test; no data or log file is read, so this runs anywhere (CI has no data)."""
import copy
import math

import pandas as pd
import pytest
import yaml

from baseball import predictions as pr


def _call(i, p=0.5, outcome=None, category="performance"):
    return {
        "id": f"fictional-{i}",
        "category": category,
        "claim": f"FICTIONAL claim number {i} comes true.",
        "probability": p,
        "basis": "Fictional basis for a test.",
        "resolves_by": "2027-10-15",
        "resolution": "Fictional source, fictional rule.",
        "outcome": outcome,
    }


@pytest.fixture
def fifteen():
    cats = pr.CATEGORIES
    return [_call(i, 0.05 + 0.05 * (i % 19), category=cats[i % 3]) for i in range(15)]


def test_valid_log_has_no_errors(fifteen):
    assert pr.validate(fifteen, n=15) == []
    assert pr.check(fifteen) is fifteen
    assert pr.N_CALLS is None and not any(c[:1].isdigit() for c in pr.CATEGORIES)   # no year in the code


def test_validation_names_every_problem(fifteen):
    calls = copy.deepcopy(fifteen)
    calls[1]["id"] = calls[0]["id"]              # duplicate id
    calls[2]["probability"] = 0.97               # above 0.95
    calls[3]["probability"] = 0.33               # off the 0.05 grid
    calls[4]["probability"] = 0.0                # below 0.05
    calls[5]["resolves_by"] = "Oct 15 2027"      # not ISO
    calls[6]["category"] = "trade"               # unknown category
    del calls[7]["basis"]                        # missing field
    calls[8]["claim"] = "  "                     # empty field
    calls[9]["outcome"] = "maybe"                # bad outcome
    calls[10]["probability"] = True              # a bool is not a probability
    err = "\n".join(pr.validate(calls))
    assert "duplicate id" in err
    assert "0.97 is outside" in err and "0.0 is outside" in err
    assert "0.33 is not a step" in err
    assert "not an ISO date" in err
    assert "category 'trade'" in err
    assert "missing 'basis'" in err
    assert "'claim' is empty" in err
    assert "outcome must be" in err
    assert "must be a number" in err
    with pytest.raises(ValueError, match="invalid prediction log"):
        pr.check(calls)


def test_count_and_dates(fifteen):
    assert "14 calls; this log has exactly 15" in pr.validate(fifteen[:14], n=15)[0]
    assert pr.validate(fifteen[:14]) == []                  # no count unless one is given
    calls = copy.deepcopy(fifteen)
    calls[0]["resolves_by"] = "2027-02-30"       # ISO-shaped but not a real date
    assert any("not an ISO date" in e for e in pr.validate(calls))
    calls[0]["resolves_by"] = pd.Timestamp("2027-04-30").date()   # a YAML date object is fine
    assert pr.validate(calls) == []
    for p in (0.05, 0.55, 0.95):                 # the grid includes both ends
        calls[1]["probability"] = p
        assert pr.validate(calls) == []


def test_brier_by_hand():
    calls = [
        _call(1, 0.8, True),    # (0.8 - 1)^2 = 0.04
        _call(2, 0.3, False),   # (0.3 - 0)^2 = 0.09
        _call(3, 0.6, False),   # (0.6 - 0)^2 = 0.36
        _call(4, 0.9, "void"),  # left out
        _call(5, 0.1, None),    # open: left out
    ]
    # (0.04 + 0.09 + 0.36) / 3 = 0.49 / 3 = 0.163333...
    assert pr.brier(calls) == pytest.approx(0.49 / 3)
    # skill = 1 - 0.163333 / 0.25 = 1 - 0.653333 = 0.346667
    assert pr.skill(calls) == pytest.approx(1 - (0.49 / 3) / 0.25)


def test_no_skill_line_is_a_quarter():
    # Saying 0.5 scores (0.5 - 1)^2 = 0.25 when true and (0.5 - 0)^2 = 0.25 when false: always 0.25.
    calls = [_call(i, 0.5, i % 3 == 0) for i in range(9)]
    assert pr.brier(calls) == pytest.approx(0.25)
    assert pr.skill(calls) == pytest.approx(0.0)


def test_brier_with_nothing_resolved_is_nan():
    assert math.isnan(pr.brier([_call(1, 0.7), _call(2, 0.4, "void")]))
    assert math.isnan(pr.skill([]))


def test_calibration_bins():
    calls = [
        _call(1, 0.10, False), _call(2, 0.20, False),   # bin 0.00-0.20: 0 of 2 true, mean 0.15
        _call(3, 0.70, True), _call(4, 0.75, True),
        _call(5, 0.80, False),                          # bin 0.60-0.80: 2 of 3 true, mean 0.75
        _call(6, 0.95, True),                           # bin 0.80-1.00: 1 of 1
        _call(7, 0.40, None),                           # open: not counted
    ]
    cal = pr.calibration(calls)
    assert list(cal["bin"]) == ["0.00-0.20", "0.20-0.40", "0.40-0.60", "0.60-0.80", "0.80-1.00"]
    assert list(cal["n"]) == [2, 0, 0, 3, 1]
    assert cal.loc[0, "mean_probability"] == pytest.approx(0.15) and cal.loc[0, "share_true"] == 0
    assert cal.loc[3, "mean_probability"] == pytest.approx(0.75)
    assert cal.loc[3, "share_true"] == pytest.approx(2 / 3)
    assert cal.loc[3, "lo"] < 2 / 3 < cal.loc[3, "hi"]
    assert math.isnan(cal.loc[1, "share_true"])
    assert list(pr.calibration(calls, bins=2)["n"]) == [2, 4]   # 0-0.5 and 0.5-1


def test_render_open_log(fifteen):
    md = pr.render_markdown(fifteen)
    assert "No call has resolved yet" in md and "15 open" in md
    assert md.count("\n| ") >= 16                          # header + 15 rows
    assert "| 1 | " in md and "| 15 | " in md
    for cat in pr.CATEGORIES:
        assert f"### {cat[0].upper() + cat[1:]} calls" in md
    assert "**Basis:** Fictional basis" in md and "2027-10-15" in md
    assert " · " not in md


def test_render_scored_log(fifteen):
    calls = copy.deepcopy(fifteen)
    calls[0].update(probability=0.8, outcome=True, note="Fictional source says yes.")
    calls[1].update(probability=0.3, outcome=False)
    calls[2].update(outcome="void")
    md = pr.render_markdown(calls)
    # (0.04 + 0.09) / 2 = 0.065
    assert "**Brier score:** 0.065 on 2 resolved calls" in md
    assert "**Void:** 1" in md and "**Outcome:** yes. Fictional source says yes." in md
    assert "| yes |" in md and "| no |" in md and "| void |" in md
    calls[3]["claim"] = "A claim | with a pipe"
    assert "with a pipe" in pr.render_markdown(calls).split("\n| 4 |")[1].split("\n")[0]
    assert "A claim \\| with a pipe" in pr.render_markdown(calls)


def test_load_and_update_report(tmp_path, fifteen):
    log = tmp_path / "log.yaml"
    log.write_text(yaml.safe_dump({"made": "2026-10-18", "by": "FICTIONAL", "n_calls": 15, "calls": fifteen},
                                  sort_keys=False))
    calls = pr.load(log)
    assert pr.validate(calls) == [] and calls[0]["id"] == "fictional-0"
    assert pr.load_header(log) == {"made": "2026-10-18", "by": "FICTIONAL", "n_calls": 15}
    assert len(pr.check_file(log)) == 15
    short = tmp_path / "short.yaml"
    short.write_text(yaml.safe_dump({"n_calls": 15, "calls": fifteen[:14]}))
    with pytest.raises(ValueError, match="14 calls; this log has exactly 15"):
        pr.check_file(short)
    bare = tmp_path / "bare.yaml"
    bare.write_text(yaml.safe_dump(fifteen))
    assert len(pr.load(bare)) == 15

    rep = tmp_path / "report.md"
    rep.write_text(f"# Title\n\nIntro stays.\n\n{pr.MARK_START}\nold\n{pr.MARK_END}\n\n## Walk me through it\nStays.\n")
    text = pr.update_report(rep, calls)
    assert "Intro stays." in text and "## Walk me through it\nStays." in text
    assert "old" not in text and "## The calls" in text
    assert pr.update_report(rep, calls) == text            # re-rendering is stable
    (tmp_path / "plain.md").write_text("no markers")
    with pytest.raises(ValueError, match="no <!-- calls:start -->"):
        pr.update_report(tmp_path / "plain.md", calls)


def test_fit_next_season_recovers_a_known_line():
    # FICTIONAL players: woba_next = 0.18 + 0.15 * woba + 0.32 * xwoba exactly, plus no noise.
    import numpy as np

    rng = np.random.default_rng(7)
    woba = rng.uniform(0.27, 0.40, 200)
    xwoba = woba + rng.normal(0, 0.02, 200)
    df = pd.DataFrame({"woba": woba, "xwoba": xwoba, "woba_next": 0.18 + 0.15 * woba + 0.32 * xwoba})
    line = pr.fit_next_season(df)
    assert line["intercept"] == pytest.approx(0.18, abs=1e-9)
    assert line["b_woba"] == pytest.approx(0.15, abs=1e-9) and line["b_xwoba"] == pytest.approx(0.32, abs=1e-9)
    assert line["sd"] == pytest.approx(0.0, abs=1e-9) and line["n"] == 200
    # .18 + .15 * .384 + .32 * .348 = .18 + .0576 + .11136 = .34896
    assert pr.project_woba(0.384, 0.348, line) == pytest.approx(0.34896)


def test_probability_helpers():
    # Normal(125, 18): P(X <= 125) = 0.5; P(X >= 125 + 1.96 * 18) = 0.025.
    assert pr.prob_beyond(125, 18, 125, above=False) == pytest.approx(0.5)
    assert pr.prob_beyond(125, 18, 125 + 1.96 * 18) == pytest.approx(0.025, abs=1e-4)
    assert pr.to_grid(0.53) == 0.55 and pr.to_grid(0.377) == 0.40 and pr.to_grid(0.41) == 0.40
    assert pr.to_grid(0.01) == 0.05 and pr.to_grid(0.99) == 0.95
    # 0.001 / (1.238 * 0.118) * 100 = 0.6845 wRC+ per point of wOBA
    assert pr.WRC_PER_WOBA_POINT == pytest.approx(0.6845, abs=1e-4)


def test_weighted_and_regressed_rates_by_hand():
    # FICTIONAL pitcher, most recent season first: 30/200, 20/250, 10/100; weights 5/4/3 scale to 1, 0.8, 0.6.
    # weighted walks 30 + 16 + 6 = 52; effective chances 200 + 200 + 60 = 460.
    r, eff = pr.weighted_rate([30, 20, 10], [200, 250, 100])
    assert eff == pytest.approx(460) and r == pytest.approx(52 / 460)
    # pulled toward .090 at 170: (52 + 15.3) / 630
    p, total = pr.regressed_rate([30, 20, 10], [200, 250, 100], 0.090, 170)
    assert total == pytest.approx(630) and p == pytest.approx(67.3 / 630)
    # one season only, weights cut to fit; empty input raises
    assert pr.weighted_rate([5], [50]) == (pytest.approx(0.1), pytest.approx(50))
    with pytest.raises(ValueError):
        pr.weighted_rate([], [])
    # spread: sqrt(p(1-p)/630 + p(1-p)/260)
    q = 67.3 / 630
    assert pr.rate_spread(q, 630, 260) == pytest.approx(math.sqrt(q * (1 - q) / 630 + q * (1 - q) / 260))


def test_abreu_walk_rate_matches_the_log():
    a = pr.abreu_walk_rate()
    assert a["seasons"] == [2026, 2025, 2024]
    # (41 + 0.8 * 31 + 0.6 * 32 + 170 * .091) / (268 + 0.8 * 296 + 0.6 * 325 + 170) = 100.47 / 869.8
    assert a["effective_bf"] == pytest.approx(869.8)
    assert a["projection"] == pytest.approx((41 + 24.8 + 19.2 + 15.47) / 869.8)
    assert round(100 * a["projection"], 1) == 11.6 and round(100 * a["sd"], 1) == 2.3
    assert a["probability"] == 0.40


def test_weighted_inputs_two_seasons():
    # FICTIONAL hitters. A: 2025 400 PA at .300 (w 120), 2026 500 PA at .350 (w 175); weights 5/4 by season and PA:
    # (5 * 175 + 4 * 120) / (5 * 500 + 4 * 400) = 1355 / 4100. B played only 2026. C played only 2025 (dropped).
    s = pd.DataFrame({"id": ["A", "A", "B", "C"], "season": [2025, 2026, 2026, 2025], "n": [400, 500, 300, 350],
                      "w": [120.0, 175.0, 96.0, 105.0], "xw": [116.0, 170.0, 93.0, 100.0]})
    x = pr.weighted_inputs(s, "id", 2026)
    assert sorted(x.index) == ["A", "B"]
    assert x.loc["A", "woba"] == pytest.approx(1355 / 4100) and x.loc["A", "n"] == 500
    assert x.loc["A", "xwoba"] == pytest.approx((5 * 170 + 4 * 116) / 4100)
    assert x.loc["B", "woba"] == pytest.approx(96 / 300)
