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
    # Grand: PD director at AAA, then GM of BBB: hired from outside, a player-development role, no AGM title
    assert bool(p.loc["grand", "pd_role"]) and not bool(p.loc["grand", "internal"]) and not bool(p.loc["grand", "agm"])
    assert "boss" not in p.index      # first head job before 2009


def test_club_table_counts_future_heads_once():
    wf, ran = _tables()
    b, fh = G.boss_years(wf, ran), G.first_head_year(wf, ran)
    t = G.club_table(wf, fh, b, {}, current_year=2026).set_index("club")
    # AAA: Kid (2003-2010) and Grand (2012-14) worked there before running a club; Boss's own GM years don't count
    assert t.loc["AAA", "future_heads"] == 2 and t.loc["AAA", "current_heads"] == 1
