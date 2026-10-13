import numpy as np
import pandas as pd

from baseball.edge.stuff import fit_crossfit, pitch_table, prepare, project, validate


def _league(n_pitchers=60, seed=5, season=2025, talent=None):
    """Fictional league. Whiff chance on a swing rises with the speed gap to the fastball (offspeed)
    and with fastball rise. One pitcher (id 1) is planted to whiff far more than his stuff says."""
    rng = np.random.default_rng(seed)
    rows = []
    for pid in range(1, n_pitchers + 1):
        fb_velo = rng.normal(94, 2)
        fb_ivb = rng.normal(16, 2)
        ch_gap = rng.normal(9, 2)
        bonus = 0.25 if pid == 1 else 0.0
        for pt, n in [("FF", 400), ("CH", 200)]:
            for _ in range(n):
                velo = fb_velo - (ch_gap if pt == "CH" else 0) + rng.normal(0, 0.8)
                ivb = (fb_ivb if pt == "FF" else 6) + rng.normal(0, 1.5)
                logit = -1.6 + 0.12 * (fb_velo - velo) + (0.08 * (ivb - 16) if pt == "FF" else 0)
                p_whiff = 1 / (1 + np.exp(-logit)) + bonus
                desc = "swinging_strike" if rng.random() < min(p_whiff, 0.95) else "foul"
                rows.append({
                    "pitcher": pid, "player_name": f"Pitcher {pid}", "p_throws": "R", "stand": "L",
                    "game_year": season, "pitch_type": pt, "pitch_name": pt, "release_speed": velo,
                    "pfx_z": ivb / 12, "pfx_x": -0.6, "release_spin_rate": 2300, "release_extension": 6.3,
                    "release_pos_z": 5.9, "release_pos_x": -1.8, "arm_angle": 40, "description": desc,
                })
    return pd.DataFrame(rows)


def test_model_learns_physics_and_finds_planted_outperformer():
    swings = prepare(_league())
    x, diag = fit_crossfit(swings)
    assert diag["auc"] > 0.6 and diag["log_loss"] < diag["log_loss_baseline"]
    t = pitch_table(swings, x)
    top = t.sort_values("gap", ascending=False).iloc[0]
    assert top["pitcher"] == 1 and top["gap"] > 15 and bool(top["gap_clear"])


def test_offspeed_gets_higher_expected_whiff_than_fastball():
    swings = prepare(_league())
    x, _ = fit_crossfit(swings)
    t = pitch_table(swings, x)
    by = t.groupby("pitch_type")["x_whiff_pct"].mean()
    assert by["CH"] > by["FF"]


def test_validate_and_project_shapes():
    s24, s25 = prepare(_league(seed=5, season=2024)), prepare(_league(seed=6, season=2025))
    t24 = pitch_table(s24, fit_crossfit(s24)[0])
    t25 = pitch_table(s25, fit_crossfit(s25)[0])
    v = validate(t24, t25)
    assert v["matched_pitches"] > 50
    assert set(v["blend"]) == {"intercept", "actual", "x_whiff"}
    proj = project(t25, v["blend"])
    assert proj["proj_whiff_pct"].notna().all()


def test_two_year_validation_and_projection():
    from baseball.edge.stuff import project_two_year, validate_two_year

    tabs = {}
    for season, seed in [(2024, 5), (2025, 6), (2026, 7)]:
        s = prepare(_league(seed=seed, season=season))
        tabs[season] = pitch_table(s, fit_crossfit(s)[0])
    v = validate_two_year(tabs[2024], tabs[2025], tabs[2026])
    assert v["matched_pitches"] > 50 and set(v["weights"]) == {"intercept", "actual_last", "actual_prior", "x_whiff_last"}
    assert set(v["loo_rmse"]) == {"last_season", "two_seasons", "last_plus_expected", "two_seasons_plus_expected"}
    one = validate(tabs[2025], tabs[2026])["blend"]
    p = project_two_year(tabs[2025], tabs[2026], v["weights"], one)
    assert (p["proj_basis"] == "two seasons").mean() > 0.9 and p["proj_whiff_pct"].notna().all()


def test_portable_model_scores_device_data_without_arm_angle_or_ids(tmp_path):
    from baseball.edge.stuff import build_portable, load_portable, mlb_percentile, save_portable, score_portable

    bundle = build_portable(_league(), 2025)
    assert "arm_angle" not in bundle["features"] and bundle["reference"]["CH"]
    save_portable(bundle, tmp_path / "m.joblib")
    b = load_portable(tmp_path / "m.joblib")
    pen = _league(n_pitchers=2, seed=9).drop(columns=["arm_angle", "stand"]).assign(pitcher=float("nan"))
    scored = score_portable(pen, b)
    assert scored["x_whiff_same"].between(0, 1).all() and scored["x_whiff_opp"].between(0, 1).all()
    assert set(scored["pitcher"]) == {"Pitcher 1", "Pitcher 2"}            # falls back to player_name
    lo, hi = mlb_percentile(b, "CH", 0.0), mlb_percentile(b, "CH", 100.0)
    assert lo == 0.0 and hi == 100.0 and mlb_percentile(b, "ZZ", 30.0) is None
