"""Front offices: page parsing, names, stints, ties and the fixed-effects model (fictional people and pages)."""
import itertools
import json

import numpy as np
import pandas as pd
import pytest

from baseball.roster import front_office as fo

PAGE = """
<p><strong>President:</strong>
    Ann Example
 (President, Baseball Operations)</p>
<p><strong>General Manager:</strong>
    <a href="/register/player.fcgi?id=exampl001bob">Bob Example</a> (Fired 6/1/2020), Cal Sample (Interim)</p>
<p><strong>Farm Director:</strong> Dee Fic&eacute;</p>
<p><strong>Scouting Director:</strong> Ed Other</p>
<p><strong>Ballpark:</strong> Nowhere Field</p>
"""


def test_parse_page_roles_people_notes_and_links():
    rows = fo.parse_page(PAGE)
    got = [(r["role"], r["name"], r["bbref_id"], r["note"]) for r in rows]
    assert got == [
        ("President", "Ann Example", "", "President, Baseball Operations"),
        ("General Manager", "Bob Example", "exampl001bob", "Fired 6/1/2020"),
        ("General Manager", "Cal Sample", "", "Interim"),
        ("Farm Director", "Dee Ficé", "", ""),
        ("Scouting Director", "Ed Other", "", ""),
    ]


def test_bbref_codes_follow_renames():
    assert [fo.bbref_code("LAA", y) for y in (2004, 2005)] == ["ANA", "LAA"]
    assert [fo.bbref_code("ATH", y) for y in (2024, 2025)] == ["OAK", "ATH"]
    assert fo.bbref_code("MIA", 2011) == "FLA" and fo.bbref_code("WSN", 2004) == "MON"


def test_normalize_matches_name_variants():
    assert fo.normalize("A.J. Preller") == fo.normalize("AJ Preller") == "ajpreller"
    assert fo.normalize("Fred Uhlman Jr.") == fo.normalize("Fred Uhlman")
    assert fo.normalize("Andrés Giménez") == "andresgimenez"


def test_panel_spans_split_gaps():
    panel = pd.DataFrame({"club": ["ATL"] * 4, "season": [2010, 2011, 2013, 2014], "role": ["General Manager"] * 4,
                          "name": ["Ann Example"] * 4})
    s = fo.panel_spans(panel)
    assert s[["start", "end"]].values.tolist() == [[2010, 2011], [2013, 2014]]
    seasons = fo.stints_from_panel(panel)
    assert seasons.season.tolist() == [2010, 2011, 2013, 2014] and seasons.decision.all()


def _careers(tmp_path):
    data = {"people": [
        {"name": "Boss One", "decision_roles": [{"club": "ATL", "role": "GM", "start": 2015, "end": 2026, "hired": "2014-10-20"}],
         "stints": [{"club": "TOR", "role": "Assistant GM", "start": 2005, "end": 2014, "source": "x"}]},
        {"name": "Pupil Two", "decision_roles": [{"club": "LAA", "role": "GM", "start": 2020, "end": 2026, "hired": "2020-11-12"}],
         "stints": [{"club": "TOR", "role": "Scout", "start": 2009, "end": 2014, "source": "x"},
                    {"club": "ATL", "role": "Assistant GM", "start": 2015, "end": 2020, "source": "x"},
                    {"club": "SEA", "role": "Public Relations Director", "start": 2001, "end": 2003, "source": "x"},
                    {"club": "BOS", "role": "Consultant (advisory role)", "start": 2004, "end": 2004, "source": "x"}]},
        {"name": "Successor Three", "decision_roles": [{"club": "SEA", "role": "GM", "start": 2009, "end": 2026},
                                                       {"club": "BOS", "role": "GM", "start": 2004, "end": 2004}],
         "stints": []},
        {"name": "Winter Interim", "decision_roles": [{"club": "NYM", "role": "Interim GM", "start": 2019, "end": 2019,
                                                       "hired": "2019-10-28", "left": "2019-11-18"}], "stints": []},
    ]}
    p = tmp_path / "careers.json"
    p.write_text(json.dumps(data))
    return p


def test_role_seasons_follow_the_season_rule():
    assert list(fo.role_seasons(2020, 2026, "2020-11-12", "2026-06-26")) == list(range(2021, 2027))   # Nov hire: next season
    assert list(fo.role_seasons(2015, 2020, "2015-06-28", "2020-02-01")) == list(range(2015, 2020))   # left before April
    assert list(fo.role_seasons(2024, 2026, "2024-09-30")) == [2025, 2026]                              # September hire: next season
    assert list(fo.role_seasons(2024, 2026, "2024-09-30", hire_cutoff=10)) == [2024, 2025, 2026]       # the sensitivity rule
    assert list(fo.role_seasons(2019, 2019, "2019-10-28", "2019-11-18")) == []                          # offseason only
    assert list(fo.role_seasons(2010, 2012)) == [2010, 2011, 2012]                                       # no dates: as given


def test_business_jobs_and_consulting_are_flagged():
    assert not fo.is_baseball_ops("Public Relations Director")
    assert fo.is_baseball_ops("Media relations, then baseball operations")
    assert fo.is_baseball_ops("Director of Professional Scouting")


def test_division_follows_houstons_move():
    assert fo.division("HOU", 2012) == "NL Central" and fo.division("HOU", 2013) == "AL West"
    assert fo.division("STL", 2010) == "NL Central"


def test_baseball_year_boundary_is_october_first():
    assert fo.baseball_year(pd.Series(["2023-09-30", "2023-10-01", "2023-12-20"])).tolist() == [2023, 2024, 2024]


def test_ties_definitions(tmp_path):
    path = _careers(tmp_path)
    dm = fo.decision_makers_from_careers(path, range(2020, 2023))
    assert not ((dm.club == "NYM")).any()                                # offseason-only interim never counts
    assert dm[(dm.club == "LAA")].season.tolist() == [2021, 2022]          # Nov 2020 hire starts in 2021
    st = fo.stints_from_careers(path)
    assert not ((st.person == "pupiltwo") & (st.club == "SEA")).any()      # PR job dropped
    assert st[(st.person == "pupiltwo") & (st.club == "BOS")].consultant.all()
    t = fo.tie_panel(dm, st, range(2020, 2023)).set_index(["pair", "season"])
    r = t.loc[("ATL-LAA", 2021)]
    assert r.former_employer and r.former_colleagues and r.protege        # under Boss at ATL 2015-20; colleagues at TOR and ATL
    assert "pupiltwo under bossone at ATL" in r.who
    assert "bossone under pupiltwo" not in r.who                          # the boss is never the protégé
    assert not t.loc[("LAA-SEA", 2021)].tied                              # PR job at SEA isn't a former employer


def test_same_person_at_both_clubs_is_not_a_tie(tmp_path):
    data = {"people": [{"name": "Mover", "decision_roles": [{"club": "DET", "role": "GM", "start": 2010, "end": 2015, "left": "2015-08-04"},
                                                             {"club": "BOS", "role": "President", "start": 2015, "end": 2019, "hired": "2015-08-18"}],
                        "stints": []}]}
    p = tmp_path / "c.json"
    p.write_text(json.dumps(data))
    dm = fo.decision_makers_from_careers(p, range(2015, 2016))
    t = fo.tie_panel(dm, fo.stints_from_careers(p), range(2015, 2016)).set_index(["pair", "season"])
    assert not t.loc[("BOS-DET", 2015)].tied


def test_event_time_terms():
    d = pd.DataFrame({"pair": ["A-B"] * 8, "season": range(2010, 2018),
                      "protege": [False, False, False, True, True, False, False, False]})
    e = fo.add_event_time(d, "protege").set_index("season")
    assert e.loc[2010, "lead_3"] and e.loc[2012, "lead_1"] and e.loc[2013, "on_0"] and e.loc[2014, "on_1"]
    assert e.loc[2015, "ended"] and not e.loc[2015, ["on_0", "on_1", "on_2", "on_3plus"]].any()


def _sim_panel(effect=2.0, seed=3):
    rng = np.random.default_rng(seed)
    clubs = sorted(a for a, _ in fo.TEAMS.values())[:12]
    pe = {p: rng.normal(0, 0.5) for p in itertools.combinations(clubs, 2)}
    ce = {(c, s): rng.normal(0, 0.3) for c in clubs for s in range(2009, 2027)}
    rows = []
    for s in range(2009, 2027):
        for a, b in itertools.combinations(clubs, 2):
            tie = rng.random() < 0.15
            mu = np.exp(-1.0 + pe[(a, b)] + ce[(a, s)] + ce[(b, s)] + np.log(effect) * tie)
            rows.append({"pair": f"{a}-{b}", "a": a, "b": b, "season": s, "trades": rng.poisson(mu), "tied": tie})
    return pd.DataFrame(rows)


def test_fe_poisson_recovers_a_known_tie_effect():
    d = _sim_panel()
    r = fo.fe_poisson(d, ["tied"]).iloc[0]
    assert r.ci_low < 2.0 < r.ci_high and 1.6 < r.rate_ratio < 2.4
    s = fo.fe_poisson(d, ["tied"], stricter=True).iloc[0]
    assert s.rate_ratio == pytest.approx(r.rate_ratio) and s.ci_high - s.ci_low > r.ci_high - r.ci_low


def test_permutation_p_finds_a_strong_effect():
    r = fo.permutation_p(_sim_panel(), "tied", draws=19)
    assert r["p_two_sided"] == r["p_one_sided"] == pytest.approx(1 / 20)      # no rotation beats a doubling
    assert 0.6 < r["null_median"] < 1.6 and r["share_below_observed"] == 1.0


def test_staff_panel_merges_pages_over_cache(tmp_path):
    pd.DataFrame([{"club": "BOS", "season": 2010, "role": "General Manager", "name": "Old Cache", "bbref_id": "", "note": ""},
                  {"club": "NYY", "season": 2010, "role": "General Manager", "name": "Kept Row", "bbref_id": "", "note": ""}]
                 ).to_csv(tmp_path / "staff_panel.csv", index=False)
    (tmp_path / "BOS_2010.html").write_text(PAGE)
    p = fo.staff_panel(tmp_path)
    assert "Old Cache" not in set(p.name)                             # the page replaces the cached BOS 2010 rows
    assert "Kept Row" in set(p.name) and (p.club == "BOS").sum() == 5
    assert len(pd.read_csv(tmp_path / "staff_panel.csv")) == 6        # cache rewritten
