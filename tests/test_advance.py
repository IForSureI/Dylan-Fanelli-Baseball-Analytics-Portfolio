"""Advance packet: flags, zones in the hitter's frame, regression, lineup, plan picks and figures.
Every frame here is fictional and generated in the test; no data files are read."""
import numpy as np
import pandas as pd
import pytest

from baseball.advance import packet as ap
from baseball.evaluation.reliability import load_params

SZ_TOP, SZ_BOT = 3.4, 1.6


def _zone(x: float, z: float) -> int:
    """Statcast-style zone from a location: 1-9 inside (catcher's view, 1 = top left), 11-14 outside."""
    if abs(x) <= ap.EDGE_FT and SZ_BOT <= z <= SZ_TOP:
        col = min(int((x + ap.EDGE_FT) / (2 * ap.EDGE_FT / 3)), 2)
        row = min(int((SZ_TOP - z) / ((SZ_TOP - SZ_BOT) / 3)), 2)
        return 1 + 3 * row + col
    up = z > (SZ_TOP + SZ_BOT) / 2
    return (11 if x < 0 else 12) if up else (13 if x < 0 else 14)


def _league(seed: int = 7, n: int = 9000) -> pd.DataFrame:
    """Fictional season. Tampa Bay (home, bottom of the inning) batters 100-104, Cleveland batters 200-202.
    Batter 100 (right-handed) is planted: he chases and misses breaking balls below the zone and crushes
    fastballs up in the zone. Batter 103 switch-hits."""
    rng = np.random.default_rng(seed)
    tb = [100, 101, 102, 103, 104]
    batters = rng.choice(tb + [200, 201, 202], size=n, p=[0.2, 0.12, 0.12, 0.12, 0.04, 0.14, 0.13, 0.13])
    stand = np.where(np.isin(batters, [101, 104, 201]), "L", "R")
    stand = np.where(batters == 103, rng.choice(["L", "R"], size=n), stand)
    ptype = rng.choice(["FF", "SL", "CH"], size=n, p=[0.55, 0.3, 0.15])
    x = rng.uniform(-1.6, 1.6, size=n)
    z = rng.uniform(0.6, 4.2, size=n)
    zone = np.array([_zone(a, b) for a, b in zip(x, z)])
    in_zone = zone <= 9
    below = z < SZ_BOT
    up_in_zone = in_zone & (z > SZ_TOP - (SZ_TOP - SZ_BOT) / 3)
    p_swing = np.where(in_zone, 0.65, 0.28)
    p_whiff = np.where(ptype == "FF", 0.18, 0.32)
    star = batters == 100
    p_swing = np.where(star & (ptype == "SL") & below, 0.7, p_swing)
    p_whiff = np.where(star & (ptype == "SL") & below, 0.85, p_whiff)
    swing = rng.random(n) < p_swing
    whiff = swing & (rng.random(n) < p_whiff)
    bip = swing & ~whiff & (rng.random(n) < 0.45)
    xw = np.where(bip, rng.uniform(0.1, 0.6, size=n), np.nan)
    xw = np.where(bip & star & (ptype == "FF") & up_in_zone, 0.95, xw)
    balls = rng.integers(0, 4, size=n)
    strikes = rng.integers(0, 3, size=n)
    desc = np.select([whiff, bip, swing, in_zone], ["swinging_strike", "hit_into_play", "foul", "called_strike"], "ball")
    events = np.select([bip & (xw > 0.4), bip, whiff & (strikes == 2), (desc == "ball") & (balls == 3)],
                       ["single", "field_out", "strikeout", "walk"], None)
    is_tb = np.isin(batters, tb)
    d = pd.DataFrame({
        "game_pk": 1 + np.arange(n) // 150, "game_date": "2026-06-01", "game_year": 2026,
        "home_team": "TB", "away_team": "CLE", "inning_topbot": np.where(is_tb, "Bot", "Top"),
        "at_bat_number": np.arange(n), "pitch_number": 1, "pitcher": rng.choice([900, 901], size=n),
        "batter": batters, "p_throws": rng.choice(["R", "L"], size=n, p=[0.7, 0.3]), "stand": stand,
        "pitch_type": ptype, "description": desc, "type": np.select([bip, desc == "ball"], ["X", "B"], "S"),
        "events": events, "balls": balls, "strikes": strikes,
        "release_speed": np.where(ptype == "FF", rng.uniform(91, 99, n), rng.uniform(82, 89, n)),
        "release_spin_rate": rng.uniform(2100, 2800, n), "plate_x": x, "plate_z": z, "sz_top": SZ_TOP,
        "sz_bot": SZ_BOT, "zone": zone.astype(float), "woba_value": np.where(events == "single", 0.9,
                                                                            np.where(events == "walk", 0.7, 0.0)),
        "woba_denom": np.where(pd.notna(events), 1.0, np.nan), "estimated_woba_using_speedangle": xw,
        "launch_speed": np.where(bip, rng.uniform(70, 110, n), np.nan),
        "bat_speed": np.where(swing, rng.normal(72, 4, n), np.nan),
        "swing_length": np.where(swing, rng.normal(7.3, 0.4, n), np.nan),
        "attack_angle": np.where(swing, rng.normal(10, 5, n), np.nan),
        "attack_direction": np.where(swing, rng.normal(0, 8, n), np.nan),
        "swing_path_tilt": np.where(swing, rng.normal(32, 4, n), np.nan),
    })
    d["events"] = d["events"].astype(object).where(pd.notna(d["events"]), None)
    # One walk on an automatic ball (pitch clock) to batter 101: a plate appearance with no pitch
    auto = d.iloc[[0]].copy()
    auto[["batter", "stand", "inning_topbot", "description", "type", "events", "zone", "balls", "strikes",
          "woba_value", "woba_denom", "at_bat_number"]] = [101, "L", "Bot", "automatic_ball", "B", "walk", np.nan,
                                                           3, 0, 0.7, 1.0, n + 1]
    return pd.concat([d, auto], ignore_index=True)


@pytest.fixture(scope="module")
def built():
    raw = _league()
    d = ap.prepare(raw)
    lg = ap.league_tables(d)
    return raw, d, lg


def test_batting_team_and_automatic_ball(built):
    raw, d, _ = built
    assert set(d.loc[d["batter"] >= 200, "bat_team"]) == {"CLE"}
    assert set(d.loc[d["batter"] < 200, "bat_team"]) == {"TB"}
    auto = d[d["description"] == "automatic_ball"]
    assert len(auto) == 1 and auto["pa"].all() and auto["bb"].all()
    assert not auto["thrown"].any() and auto["cell"].astype(str).eq("").all()
    s = ap.sums(d[d["batter"] == 101])
    assert int(s["pitches"].iloc[0]) == int((raw["batter"] == 101).sum()) - 1     # the automatic ball isn't a pitch
    assert int(s["pa"].iloc[0]) == int(raw.loc[raw["batter"] == 101, "events"].notna().sum())


def test_zones_in_the_hitters_frame():
    base = dict(game_pk=1, game_date="2026-06-01", game_year=2026, home_team="TB", away_team="CLE",
                inning_topbot="Bot", pitch_number=1, pitcher=9, p_throws="R", pitch_type="FF",
                description="ball", type="B", events=None, balls=0, strikes=0, release_speed=95.0,
                release_spin_rate=2300.0, sz_top=SZ_TOP, sz_bot=SZ_BOT, woba_value=np.nan, woba_denom=np.nan,
                estimated_woba_using_speedangle=np.nan, launch_speed=np.nan, bat_speed=np.nan, swing_length=np.nan,
                attack_angle=np.nan, attack_direction=np.nan, swing_path_tilt=np.nan)
    rows = [  # (stand, zone, plate_x, plate_z) -> expected cell, out-of-zone direction
        ("R", 1, -0.6, 3.2, "up-in", ""), ("L", 1, -0.6, 3.2, "up-away", ""),
        ("R", 9, 0.6, 1.8, "down-away", ""), ("L", 9, 0.6, 1.8, "down-in", ""),
        ("R", 5, 0.0, 2.5, "mid-mid", ""),
        ("R", 13, -0.2, 1.0, "chase down-in", "below"), ("L", 13, -1.5, 2.0, "chase down-away", "away"),
        ("R", 12, 1.0, 3.9, "chase up-away", "above"), ("R", 11, -1.4, 2.8, "chase up-in", "in"),
    ]
    p = pd.DataFrame([base | dict(at_bat_number=i, batter=10 + i, stand=s, zone=float(z), plate_x=x, plate_z=zz)
                      for i, (s, z, x, zz, _, _) in enumerate(rows)])
    d = ap.prepare(p)
    assert d["cell"].astype(str).tolist() == [r[4] for r in rows]
    assert d["odir"].astype(str).tolist() == [r[5] for r in rows]


def test_shrink_matches_the_atlas_formula():
    M = float(load_params().loc["hitter/whiff", "M"])
    obs, n, league = 0.40, 30, 0.25
    assert ap.shrink("whiff", obs, n, league) == pytest.approx((n * obs + M * league) / (n + M))
    assert ap.shrink("whiff", np.nan, 0, league) == pytest.approx(league)          # no sample: the league
    big = ap.shrink("chase", 0.40, 1e6, 0.30)
    assert big == pytest.approx(0.40, abs=1e-3)                                     # huge sample: his own


def test_lineup_counts_pa_with_the_club(built):
    _, d, _ = built
    lu = ap.lineup(d, "TB", n=3)
    assert lu["batter"].iloc[0] == 100                       # the most-used Tampa Bay hitter
    assert set(lu["batter"]) <= {100, 101, 102, 103, 104}
    assert (lu["pa_team"] <= lu["pa_total"]).all()
    assert lu["pa_team"].is_monotonic_decreasing


def test_plan_finds_the_planted_tendencies(built):
    _, d, lg = built
    prof = ap.hitter_profile(d, 100, lg, "Fictional Hitter", "TB")
    lines = ap.plan(prof)
    assert (lines["put_away"]["family"], lines["put_away"]["loc"]) == ("breaking", "chase below")
    assert lines["put_away"]["r_swstr"] > lines["put_away"]["lg_swstr"]
    assert lines["avoid"]["family"] == "fastball" and lines["avoid"]["loc"] == "zone up" and lines["avoid"]["clear"]
    # regressed values sit between the raw value and the league's
    fl = prof["famloc"].set_index(["family", "loc"]).loc[("breaking", "chase below")]
    assert min(fl["whiff"], fl["lg_whiff"]) <= fl["r_whiff"] <= max(fl["whiff"], fl["lg_whiff"])
    text = "\n".join(ap.plan_text(prof, lines))
    assert "n = " in text and "Put-away" in text and "Avoid" in text


def test_switch_hitter_and_platoon_regression(built):
    _, d, lg = built
    assert ap.hitter_side(d[d["batter"] == 103]).iloc[0] == "S"
    prof = ap.hitter_profile(d, 103, lg, "Switch", "TB")
    pl = prof["platoon"]
    w = pl["pa_vs_l"] / (pl["pa_vs_l"] + ap.PLATOON_M["S"])
    assert pl["regressed_split"] == pytest.approx(pl["league_split"] + w * (pl["observed_split"] - pl["league_split"]))
    # 13 zones, every one present even when empty
    assert prof["cell"]["cell"].tolist() == ap.CELLS


def test_markdown_and_figure(built, tmp_path):
    _, d, lg = built
    profs = [ap.hitter_profile(d, b, lg, f"Fictional {b}", "TB") for b in (100, 101, 103)]
    md = ap.hitter_markdown(profs[0])
    assert md.startswith("### Fictional 100") and "Bat tracking" in md and "Platoon split" in md
    out = ap.zone_figure(profs, "whiff", tmp_path / "w.png", "Fictional", "fictional data")
    assert out.exists() and out.stat().st_size > 10_000
    out = ap.zone_figure(profs, "xwcon", tmp_path / "x.png", "Fictional", "fictional data")
    assert out.exists()


def test_build_end_to_end_on_fictional_data(tmp_path):
    r = ap.build("TB", 2026, n=3, out_dir=tmp_path, data=_league(seed=3, n=4000), names={})
    assert len(r["profiles"]) == 3
    assert (tmp_path / "tables-TB-2026.md").exists() and (tmp_path / "profiles-TB-2026.json").exists()
    tt = r["team_table"]
    assert tt["pa_team"].is_monotonic_decreasing


def test_switch_hitter_main_side(built):
    _, d, lg = built
    prof = ap.hitter_profile(d, 103, lg, "Switch", "TB")
    h = d[(d["batter"] == 103) & d["pa"]]
    assert prof["main_side"] == h["stand"].astype(str).value_counts().index[0]
    assert ap.hitter_profile(d, 101, lg, "Lefty", "TB")["main_side"] == "L"


def _panel_texts(cells: pd.DataFrame, side: str) -> dict:
    """Draw one panel and return {text: x position} for the IN/AWAY labels and the up-in cell value."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    ap.zone_panel(ax, cells, "r_whiff", "lg_whiff", "swings", 0, 0.1, plt.get_cmap("RdBu"),
                  lambda v: f"{100 * v:.0f}", side, "t")
    out = {t.get_text(): t.get_position()[0] for t in ax.texts}
    plt.close(fig)
    return out


def test_zone_panel_draws_inside_on_the_hitters_side():
    cells = pd.DataFrame({"cell": ap.CELLS, "r_whiff": 0.20, "lg_whiff": 0.20, "swings": 50})
    cells.loc[cells["cell"] == "up-in", "r_whiff"] = 0.77            # a marker value in the up-in cell
    r, left = _panel_texts(cells, "R"), _panel_texts(cells, "L")
    # catcher's view: a right-handed hitter's inside is on the left, a left-handed hitter's on the right
    assert r["IN"] < r["AWAY"] and r["77"] < 1.5
    assert left["IN"] > left["AWAY"] and left["77"] > 1.5


def test_plan_text_verdict_thresholds():
    def fp(gap):
        return {"first_pitch": dict(swing=0.3 + gap, r_swing=0.3 + gap, lg_swing=0.3, pitches=100,
                                    r_zone_swing=0.5, lg_zone_swing=0.5)}

    def tk(gap):
        return {"two_strikes": dict(r_chase=0.41 + gap, lg_chase=0.41, out_pitches=200, r_whiff=0.24,
                                    lg_whiff=0.24, swings=150)}

    assert "aggressive early" in ap.plan_text({}, fp(0.07))[0]
    assert "average on 0-0" in ap.plan_text({}, fp(0.05))[0]
    assert "takes early" in ap.plan_text({}, fp(-0.07))[0]
    assert "expands" in ap.plan_text({}, tk(0.05))[0]
    assert "league-average expansion" in ap.plan_text({}, tk(0.03))[0]
    assert "won't expand" in ap.plan_text({}, tk(-0.05))[0]
    avoid = dict(family="fastball", loc="zone up", r_xwcon=0.40, lg_xwcon=0.39, bip=20, pitches=60, clear=False)
    assert "no in-zone spot" in ap.plan_text({}, {"avoid": avoid})[0]
