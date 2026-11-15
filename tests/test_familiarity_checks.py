"""The two checks on the familiarity estimate: the shuffle null and leave-own-game-out. Fictional pitches."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from baseball.edge import familiarity as f
from baseball.edge import familiarity_checks as c

ROOT = Path(__file__).resolve().parent.parent


def _season(seed, effect=0.0, feedback=0.0, pitchers=40, games=6, lineup=9, batters=60):
    """A fictional season. Each pitcher starts `games` games against `lineup` hitters, three times through,
    three to five pitches a plate appearance, fastball or changeup. Every pitch is a swing with outcome y.

    effect: change in y per earlier pitch of the same type the hitter has seen from this pitcher today.
    feedback: selection. After a changeup beats (or misses) expectation, the pitcher throws this hitter more
    (or fewer) changeups for the rest of the game. With effect=0 exposure does nothing to y.
    """
    rng = np.random.default_rng(seed)
    rows, game = [], 0
    for p in range(pitchers):
        level = rng.normal(0, 0.05)
        for _ in range(games):
            game += 1
            hitters = rng.choice(batters, lineup, replace=False)
            lean = {b: 0.5 for b in hitters}
            seen = {b: {"FF": 0, "CH": 0} for b in hitters}
            ab = 0
            for _pa in range(3):
                for b in hitters:
                    ab += 1
                    thrown = []
                    for k in range(int(rng.integers(3, 6))):
                        t = "CH" if rng.random() < lean[b] else "FF"
                        noise = rng.normal(0, 0.4)
                        if t == "CH":
                            lean[b] = float(np.clip(lean[b] + feedback * noise, 0.1, 0.9))
                        thrown.append(t)
                        rows.append((game, ab, k + 1, p, b, t, 0.3 + level + effect * seen[b][t] + noise))
                    for t in thrown:
                        seen[b][t] += 1
    d = pd.DataFrame(rows, columns=["game_pk", "at_bat_number", "pitch_number", "pitcher", "batter", "pitch_type", "y"])
    n = len(d)
    d["game_date"], d["game_year"], d["p_throws"], d["inning"] = "2026-05-01", 2026, "R", 1
    d["stand"] = np.where(rng.random(n) < 0.5, "R", "L")
    d["balls"], d["strikes"] = rng.integers(0, 4, n), rng.integers(0, 3, n)
    d["release_speed"], d["pfx_z"], d["pfx_x"] = rng.normal(93, 2, n), rng.normal(1.2, 0.2, n), rng.normal(-0.6, 0.2, n)
    d["release_spin_rate"] = rng.normal(2300, 100, n)
    d["plate_x"], d["plate_z"], d["sz_top"], d["sz_bot"] = rng.normal(0, 0.8, n), rng.normal(2.5, 0.8, n), 3.4, 1.6
    d["zone"] = rng.choice([1.0, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14], n)
    d = f.keys(f.exposures(d))
    d["bkey"] = (d["batter"] % 5).astype(str)          # five big hitter groups
    return d


def _nulls(d, n_shuffles=200, seed=7):
    """The three shuffle designs on the changeups of a fictional season."""
    ch = d["pitch_type"].eq("CH")
    sw = d[ch]
    out = {}
    for name, (strata, _) in c.DESIGNS.items():
        pool, mask = (sw, pd.Series(True, index=sw.index)) if name == "across_hitters" else (d, ch)
        out[name] = c.null_summary(c.null_shuffle(pool, mask, strata, "y", n_shuffles, seed), scale=1)
    return out


def test_permute_within_only_moves_rows_inside_their_group():
    rng = np.random.default_rng(0)
    codes = rng.integers(0, 40, 500)
    perm = c.permute_within(codes, rng)
    assert sorted(perm) == list(range(500))                       # a permutation: every row used once
    assert (codes[perm] == codes).all()                           # and never across groups
    assert (perm != np.arange(500)).mean() > 0.5                  # it does move rows
    alone = np.array([3, 1, 2])                                   # groups of one can't move
    assert (c.permute_within(alone, rng) == np.arange(3)).all()


def test_shuffle_keeps_each_stratums_counts():
    d = _season(1, pitchers=6, games=2)
    codes = c.group_codes(d, c.WITHIN_PA)
    perm = c.permute_within(codes, np.random.default_rng(2))
    before = d.groupby(list(c.WITHIN_PA))["prev_same"].apply(sorted)
    after = d.assign(prev_same=d["prev_same"].to_numpy()[perm]).groupby(list(c.WITHIN_PA))["prev_same"].apply(sorted)
    assert before.equals(after)
    # the total seen is the same on every pitch of a plate appearance, so this design leaves it untouched
    total = (d["prev_same"] + d["prev_other"]).to_numpy()
    assert (total[perm] == total).all()


def test_fast_refit_equals_the_full_fit():
    d = _season(3, effect=-0.02, pitchers=12, games=4)
    sw = d[d["pitch_type"].eq("CH")]
    full = f.fit_pairs(sw, "y").set_index("term")["coef"]
    res = c.null_shuffle(d, d["pitch_type"].eq("CH"), c.WITHIN_HITTER, "y", n_shuffles=1, seed=0)
    assert res["observed"] == pytest.approx(full["prev: same - other"], abs=1e-9)
    assert res["observed_other"] == pytest.approx(full["prev: other type"], abs=1e-9)


def test_null_is_centered_on_zero_when_nothing_is_planted():
    for name, s in _nulls(_season(11)).items():
        assert abs(s["null_mean"]) < 2 * s["null_sd"], name
        assert abs(s["observed"] - s["null_mean"]) < 3 * s["null_sd"], name      # the real fit looks like a shuffle
        assert s["p_two_sided"] > 0.01, name


def test_null_separates_a_planted_effect():
    for name, s in _nulls(_season(11, effect=-0.03)).items():
        assert s["observed"] == pytest.approx(-0.03, abs=0.008), name
        assert s["observed"] < s["null_min"], name                               # no shuffle reaches it
        assert s["p_lower"] == pytest.approx(1 / 201), name
        if name != "within_hitter":
            # a shuffle inside a cell keeps the cell's average, so part of a real effect survives it:
            # the null mean is not a no-effect benchmark
            assert s["null_mean"] < 0, name


def test_p_values_count_the_real_fit_as_a_draw():
    res = {"null": np.array([-0.3, -0.1, 0.0, 0.1, 0.3]), "observed": -0.2, "n_shuffles": 5, "seed": 0, "n": 9,
           "strata": 3, "share_moved": 0.5, "share_alone": 0.1}
    s = c.null_summary(res, scale=1)
    assert s["null_mean"] == pytest.approx(0.0)
    assert s["p_lower"] == pytest.approx(2 / 6)                   # one shuffle at or below -0.2, plus the real fit
    assert s["p_two_sided"] == pytest.approx(3 / 6)               # two shuffles at least 0.2 from the mean


def test_leave_game_out_mean_by_hand():
    d = pd.DataFrame({"k": ["a", "a", "a", "a", "b", "b"], "game_pk": [1, 1, 2, 3, 1, 1], "y": [1.0, 0.0, 1.0, 0.0, 1.0, 1.0]})
    m = c.leave_game_out_mean(d, "y", "k")
    # key a, game 1: the other games hold 1 and 0 -> 0.5. game 2: 1, 0, 0 -> 1/3. game 3: 1, 0, 1 -> 2/3
    assert m.iloc[:4].tolist() == pytest.approx([0.5, 0.5, 1 / 3, 2 / 3])
    assert m.iloc[4:].isna().all()                                # key b has no other game


def test_leave_own_game_out_removes_the_selection_bias_of_fixed_effects():
    """Nothing is planted, but the pitcher repeats what just worked and each pitcher has only two games.
    The ordinary fixed-effect fit then reads a wear-out that isn't there. Leaving the own game out doesn't."""
    d = _season(1, feedback=1.5, pitchers=2000, games=2, lineup=5, batters=40)
    ch = d[d["pitch_type"].eq("CH")]
    t = c.fit_leave_game_out(ch, "y").set_index("term").loc["prev: same - other"]
    assert t["coef_in"] < -3 * t["se_in"]                         # biased below zero
    assert abs(t["coef"]) < 2 * t["se"]                           # fixed
    lv = c.fit_levels(ch, "y").set_index("term").loc["prev: same - other"]
    assert abs(lv["coef"]) < 2 * lv["se"]


def test_leave_own_game_out_recovers_a_planted_effect():
    d = _season(5, effect=-0.03, pitchers=60, games=6)
    ch = d[d["pitch_type"].eq("CH")]
    t = c.fit_leave_game_out(ch, "y").set_index("term").loc["prev: same - other"]
    assert t["coef"] == pytest.approx(-0.03, abs=3 * t["se"])
    assert t["coef"] < -3 * t["se"]
    lv = c.fit_levels(ch, "y").set_index("term").loc["prev: same - other"]
    assert lv["coef"] == pytest.approx(-0.03, abs=3 * lv["se"])


def test_leave_own_game_out_drops_keys_with_one_game():
    d = _season(6, pitchers=10, games=3)
    d.loc[d["pitcher"].eq(0) & d["game_pk"].ne(d.loc[d["pitcher"].eq(0), "game_pk"].min()), "pitcher"] = 99
    d = f.keys(d).assign(bkey=d["bkey"])                          # pitcher 0 is left with one game
    ch = d[d["pitch_type"].eq("CH")]
    t = c.fit_leave_game_out(ch, "y")
    assert t["n"].iloc[0] == len(ch) - int(ch["pitcher"].eq(0).sum())


# ---------------------------------------------------------------- the report against the saved run

def _m(x, nd=2):
    return f"{x:+.{nd}f}".replace("-", "\u2212")


def test_report_matches_the_saved_checks():
    out = json.loads((ROOT / "reports" / "outputs" / "familiarity-checks-2024-26.json").read_text())
    rep = (ROOT / "reports" / "2026-league-pitch-familiarity.md").read_text()
    groups = ["fastball", "breaking", "offspeed", "cutter"]
    null = {(r["group"], r["design"]): r for r in out["null"]["results"]}
    lgo = {(r["group"], r["spec"]): r for r in out["leave_game_out"] if r["term"] == "prev: same - other"}
    n = out["null"]["n_shuffles"]
    assert n == 1000 and f"seed {out['null']['seed']}" in rep
    for design, label in [("within_hitter", "Shuffled within the hitter's game"), ("within_pa", "Shuffled within the plate appearance"),
                          ("across_hitters", "Shuffled across hitters")]:
        cells = " | ".join(f"{_m(null[(g, design)]['null_mean'])} ({null[(g, design)]['null_sd']:.2f})" for g in groups)
        assert f"| {label}: mean (SD) | {cells} |" in rep
        # the saved summary is the saved draws
        for g in groups:
            draws = np.array(out["null"]["draws"][f"{g}|{design}"])
            r = null[(g, design)]
            assert len(draws) == n and draws.mean() == pytest.approx(r["null_mean"], abs=2e-4)
            # the draws are saved to four places, so a draw next to the real coefficient can land either side
            assert (1 + (draws <= r["observed"]).sum()) / (n + 1) == pytest.approx(r["p_lower"], abs=1.5 / (n + 1))
    # no shuffle reaches the real coefficient in the three main groups; cutters fail the across-hitters test
    assert all(null[(g, d)]["p_lower"] == pytest.approx(1 / (n + 1), abs=1e-4) for g in groups[:3] for d in c.DESIGNS)
    cut = null[("cutter", "across_hitters")]
    assert f"{round(cut['p_lower'] * (n + 1)) - 1} of 1,000 across-hitter shuffles" in rep and f"(p = {cut['p_lower']:.2f})" in rep
    for spec, label in [("fixed effects (published)", "Published (fixed effects)"),
                        ("fixed effects, rows with another game", "Fixed effects, rows with another game"),
                        ("fixed effects, own game left out", "Fixed effects, own game left out"),
                        ("levels, own game included", "Levels as columns, own game included"),
                        ("levels, own game left out", "Levels as columns, own game left out")]:
        cells = " | ".join(f"{_m(lgo[(g, spec)]['coef'])} ({lgo[(g, spec)]['se']:.2f})" for g in groups)
        assert f"| {label} | {cells} |" in rep
    left = " / ".join(_m(lgo[(g, "fixed effects, own game left out")]["coef"]) for g in groups[:3])
    assert f"The estimates become {left}" in rep
    assert all(lgo[(g, s)]["p"] < 0.001 for g in groups[:3] for s in ("fixed effects, own game left out", "levels, own game left out"))
    assert lgo[("cutter", "fixed effects, own game left out")]["p"] > 0.05
    # the published column is the published table
    pub = json.loads((ROOT / "reports" / "outputs" / "familiarity-2024-26.json").read_text())
    for r in pub["coefficients"]:
        if r["outcome"].startswith("whiff") and r["term"] == "prev: same - other":
            mine = lgo[(r["group"], "fixed effects (published)")]
            assert (mine["coef"], mine["se"], mine["n"]) == (r["coef"], r["se"], r["n"])
            assert null[(r["group"], "within_pa")]["observed"] == pytest.approx(r["coef"], abs=1e-4)
