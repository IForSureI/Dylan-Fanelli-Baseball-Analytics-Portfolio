"""The GM tree on a fictional front office (every name and club here is made up)."""
import pandas as pd
import pytest

from baseball.roster import gm_tree as G


def _tables():
    # Club AAA: Boss ran it 2000-2010 (GM title, before ran.csv coverage), then Kid ran it from 2011 (ran.csv).
    # Kid worked under Boss 2003-2010 (from intern to assistant GM); Pal was a scout there 2005-2006 and never ran a club.
    # Kid left nobody behind; Grand worked under Kid at AAA 2012-2014, then became GM of BBB in 2016.
    # Temp ran AAA as interim GM in 2011: interim titles never make a boss or a head.
    wf = pd.DataFrame([
        ("boss", "AAA", "General Manager", 2000, 2010),
        ("kid", "AAA", "Baseball operations intern", 2003, 2004),
        ("kid", "AAA", "Assistant General Manager", 2005, 2010),
        ("pal", "AAA", "Area Scout", 2005, 2006),
        ("grand", "AAA", "Director of Player Development", 2012, 2014),
        ("grand", "BBB", "General Manager", 2016, 2020),
        ("temp", "AAA", "Special Assistant to the General Manager", 2009, 2010),
    ], columns=["key", "club", "role", "start", "end"])
    ran = pd.DataFrame([
        ("kid", "AAA", "General Manager", 2011, 2026),
        ("temp", "AAA", "Interim General Manager", 2011, 2011),
        ("grand", "BBB", "General Manager", 2016, 2020),
    ], columns=["key", "club", "role", "start", "end"])
    return wf, ran


def test_titles():
    assert G.is_gm_title("Executive Vice President & General Manager")
    assert not G.is_gm_title("Assistant General Manager")
    assert not G.is_gm_title("Special Assistant to the General Manager")
    assert not G.is_gm_title("Interim co-GM (Office of the General Manager)")
    assert G.is_interim("Interim General Manager") and not G.is_interim("General Manager")


def test_bosses_fill_only_before_2009_and_skip_interim():
    wf, ran = _tables()
    b = G.boss_years(wf, ran)
    aaa = b[b["club"] == "AAA"].set_index("year")["boss"].sort_index()
    # 2000-2008 from the GM title, 2009-2010 aren't covered (title fill stops at 2009 and ran.csv starts 2011),
    # 2011 on is Kid; Temp's interim year never appears.
    assert list(aaa.loc[2000:2008].unique()) == ["boss"] and 2009 not in aaa.index
    assert set(aaa.loc[2011:].unique()) == {"kid"} and "temp" not in set(b["boss"])


def test_first_head_year():
    wf, ran = _tables()
    fh = G.first_head_year(wf, ran)
    assert fh["boss"] == 2000 and fh["kid"] == 2011 and fh["grand"] == 2016
    assert "temp" not in fh.index and "pal" not in fh.index


def test_learned_under_and_produced():
    wf, ran = _tables()
    b = G.boss_years(wf, ran)
    e = G.learned_under(wf, b).set_index(["junior", "boss"])
    # Kid under Boss: seasons 2003-2008 (the 2009-10 fill gap ends the shared run): 6 seasons
    assert e.loc[("kid", "boss"), ["first", "last", "seasons"]].tolist() == [2003, 2008, 6]
    assert e.loc[("pal", "boss"), "seasons"] == 2
    assert e.loc[("grand", "kid"), ["first", "last"]].tolist() == [2012, 2014]
    prod = G.produced(G.learned_under(wf, b), G.first_head_year(wf, ran))
    # Pal never ran a club, so only Kid (under Boss) and Grand (under Kid) count
    assert sorted(zip(prod["junior"], prod["boss"])) == [("grand", "kid"), ("kid", "boss")]
    assert G.descendants(prod) == {"boss": {"kid", "grand"}, "kid": {"grand"}}


def test_pagerank_chain():
    # grand -> kid -> boss with damping 0.85 on three nodes. Boss is dangling and spreads evenly.
    # Solving r = 0.05 + 0.85*r_boss/3 + 0.85*(in-links): r_grand = a, r_kid = a + 0.85 a, r_boss = a + 0.85 r_kid,
    # with a = 0.05 + 0.85 r_boss / 3; the three sum to 1. Order is boss > kid > grand.
    prod = pd.DataFrame({"junior": ["kid", "grand"], "boss": ["boss", "kid"]})
    pr = G.pagerank(prod)
    a = pr["grand"]
    assert pr.sum() == pytest.approx(1.0)
    assert pr["kid"] == pytest.approx(a * 1.85, rel=1e-9)
    assert pr["boss"] == pytest.approx(a + 0.85 * pr["kid"], rel=1e-9)
    assert a == pytest.approx(0.05 + 0.85 * pr["boss"] / 3, rel=1e-9)


def test_paths_internal_and_roles():
    wf, ran = _tables()
    fh = G.first_head_year(wf, ran)
    p = G.paths(wf, ran, fh, since=2009).set_index("key")
    # Kid: first job 2003, head 2011 -> 8 years, one club, intern and AGM, promoted from inside
    assert p.loc["kid", ["years_to_head", "clubs_before"]].tolist() == [8, 1]
    assert bool(p.loc["kid", "agm"]) and bool(p.loc["kid", "entry_level"]) and bool(p.loc["kid", "internal"])
    assert bool(p.loc["kid", "only_club_hired_there"])
    # Grand: PD director at AAA, then GM of BBB: hired from outside, a player-development role, no AGM title
    assert bool(p.loc["grand", "pd_role"]) and not bool(p.loc["grand", "internal"]) and not bool(p.loc["grand", "agm"])
    assert not bool(p.loc["grand", "only_club_hired_there"])     # worked only at AAA, hired by BBB
    assert "boss" not in p.index      # first head job before 2009


def test_club_table_counts_future_heads_once():
    wf, ran = _tables()
    fh = G.first_head_year(wf, ran)
    assert G.current_heads(ran) == {"kid"}          # Temp is interim; Grand's job ended in 2020
    t = G.club_table(wf, fh, G.current_heads(ran), {}).set_index("club")
    # AAA: Kid (2003-2010) and Grand (2012-14) worked there before running a club; Boss's own GM years don't count
    assert t.loc["AAA", "future_heads"] == 2 and t.loc["AAA", "current_heads"] == 1


def test_current_heads_drop_departures():
    ran = pd.DataFrame([("a", "AAA", "General Manager", 2020, 2026, None),
                        ("b", "BBB", "General Manager", 2021, 2026, "2026-08-24"),
                        ("c", "CCC", "President of Baseball Operations", 2019, 2026, "current"),
                        ("d", "AAA", "Interim General Manager", 2026, 2026, None)],
                       columns=["key", "club", "role", "start", "end", "left"])
    assert G.current_heads(ran) == {"a", "c"}


def test_interim_rules():
    # "Interim GM, then General Manager" became permanent; a co-GM committee and a plain interim did not.
    assert not G.is_interim("Interim GM, then Senior VP and General Manager")
    assert not G.is_interim("General Manager (interim, then permanent)")
    assert G.is_interim("Interim General Manager") and G.is_interim("Interim co-GM (Office of the General Manager)")


def test_baseball_reference_interims_are_not_heads():
    # Baseball-Reference lists every GM as plain "General Manager". Two cases must not become heads:
    # Lou ran BBB as interim in 2015 (ran.csv says so) and has a plain GM row for that season;
    # Mike Port's 2002 Boston season is a known interim with no ran.csv row.
    # Ron's 2005 GM row is before 2009 and not interim, so it counts; his 2012 plain row doesn't (ran.csv rules after 2009).
    wf = pd.DataFrame([("lou", "BBB", "General Manager", 2015, 2015), ("mikeport", "BOS", "General Manager", 2002, 2002),
                       ("ron", "CCC", "General Manager", 2005, 2005), ("ron", "DDD", "General Manager", 2012, 2012)],
                      columns=["key", "club", "role", "start", "end"])
    ran = pd.DataFrame([("lou", "BBB", "Interim General Manager", 2015, 2015)], columns=["key", "club", "role", "start", "end"])
    fh = G.first_head_year(wf, ran)
    assert list(fh.index) == ["ron"] and fh["ron"] == 2005
    assert set(G.boss_years(wf, ran)["year"]) == {2005}


def test_pre_2009_gm_counts_beside_a_president():
    # A president (ran.csv) and a GM (title only) ran EEE in 2000: both are bosses, so the GM isn't the president's junior.
    wf = pd.DataFrame([("gm", "EEE", "General Manager", 2000, 2000), ("kid", "EEE", "Scout", 2000, 2000)],
                      columns=["key", "club", "role", "start", "end"])
    ran = pd.DataFrame([("pres", "EEE", "President", 2000, 2000)], columns=["key", "club", "role", "start", "end"])
    b = G.boss_years(wf, ran)
    assert set(b["boss"]) == {"gm", "pres"}
    e = G.learned_under(wf, b)
    assert set(zip(e["junior"], e["boss"])) == {("kid", "gm"), ("kid", "pres")}


def test_role_patterns():
    assert G._AGM.search("Vice President of Baseball Operations / Assistant GM")
    assert not G._ENTRY.search("Director of international operations") and G._ENTRY.search("Baseball operations intern")
    assert G._amateur_director("Scouting Director") and G._amateur_director("Director of Amateur Scouting")
    assert not G._amateur_director("Assistant Scouting Director") and not G._amateur_director("Director of Professional Scouting")
    assert G._pro_director("Director of Professional Scouting")


def test_boss_table_two_plus_seasons():
    # Kid shared 6 seasons with Boss; Grand shared 3 with Kid; One shared a single season with Boss.
    prod = pd.DataFrame({"junior": ["kid", "grand", "one"], "boss": ["boss", "kid", "boss"], "club": "AAA",
                         "seasons": [6, 3, 1]})
    t = G.boss_table(prod, {}).set_index("boss")
    assert t.loc["boss", ["direct", "direct_2plus", "tree"]].tolist() == [2, 1, 3]


def test_head_table_and_obsidian_export(tmp_path, monkeypatch):
    # The fictional front office from _tables(), written as graph tables, then exported as notes.
    wf, ran = _tables()
    wf = wf.assign(uncertain=False, source="https://example.com/source")
    ran = ran.assign(hired="", left=None)
    g = tmp_path / "graph"
    g.mkdir()
    wf.to_csv(g / "worked_for.csv", index=False)
    ran.to_csv(g / "ran.csv", index=False)
    pd.DataFrame({"key": ["boss", "kid", "pal", "grand", "temp", "johnhart"],
                  "name": ["Boss Man", "Kid Smith", "Pal", "Grand Kid", "Temp", "John Hart"]}).to_csv(g / "executives.csv", index=False)
    monkeypatch.setattr(G, "CLUBS", {"AAA": "Alpha Club", "BBB": "Beta Club", "CLE": "Cleveland"})
    ht = G.head_table(pd.read_csv(g / "worked_for.csv"), pd.read_csv(g / "ran.csv")).set_index("key")
    assert ht.loc["kid", ["first_head", "head_club", "current", "current_job"]].tolist() == [2011, "AAA", True, "General Manager, AAA"]
    assert not ht.loc["grand", "current"] and ht.loc["boss", "head_club"] == "AAA"
    out = tmp_path / "vault"
    n = G.export_obsidian(out, graph=g)
    assert n == {"executives": 3, "clubs": 3}
    kid = (out / "Executives" / "Kid Smith.md").read_text()
    assert "current_head: true" in kid and "- [[Boss Man]] at [[Alpha Club (AAA)]], 2003-2008 (6 seasons)" in kid
    assert "- [[Grand Kid]] at [[Alpha Club (AAA)]], 2012-2014 (first head job 2016)" in kid
    club = (out / "Clubs" / "Alpha Club (AAA).md").read_text()
    assert "future_heads: 2" in club and "[[Kid Smith]] (first head job 2011; in a top job today)" in club
    assert (out / "GM Tree.md").exists()
