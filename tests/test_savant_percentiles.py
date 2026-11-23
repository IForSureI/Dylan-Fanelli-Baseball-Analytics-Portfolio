"""Baseball Savant's percentile rankings saved in market/savant/: the pull keeps Savant's file as sent and
records where and when, the CSV and the player pages agree, and the packet shows Savant's ranks."""
import csv
import io
import json
from pathlib import Path

import pytest

from baseball.ingest import savant_percentiles as S

ROOT = Path(__file__).resolve().parents[1]
SV = ROOT / "market" / "savant"


def test_pull_saves_the_file_and_records_url_and_date(tmp_path):
    body = '﻿"player_name","player_id","year","xera","k_percent"\n"Morejon, Adrian","670970","2026",99,93\n'.encode("utf-8")
    seen = []
    def fake(url):
        seen.append(url)
        return body, 200
    out = S.pull(years=(2026,), kinds=("pitcher",), root=tmp_path, get=fake, pulled="2026-11-23", pause=0)
    assert out == [tmp_path / "percentile_rankings_pitcher_2026.csv"]
    assert out[0].read_bytes() == body
    assert seen == ["https://baseballsavant.mlb.com/leaderboard/percentile-rankings?type=pitcher&year=2026&csv=true"]
    m = json.loads((tmp_path / "manifest.json").read_text())["percentile_rankings_pitcher_2026.csv"]
    assert m == {"url": seen[0], "pulled": "2026-11-23", "rows": 1, "status": 200}
    assert S.load("pitcher", 2026, tmp_path)[670970]["xera"] == 99


def test_pull_refuses_a_page_that_is_not_the_table(tmp_path):
    with pytest.raises(RuntimeError):
        S.pull(years=(2026,), kinds=("pitcher",), root=tmp_path, get=lambda u: (b"<html>sign in</html>", 200), pause=0)
    assert not (tmp_path / "percentile_rankings_pitcher_2026.csv").exists()


def test_player_page_rows_are_read_by_season():
    page = 'x = [{"aggregate": "0", "year": 2026, "player_type": "pitcher", "grouping_code": "Pitcher and Year", "xera": 2.34, "percent_rank_xera": 99, "percent_rank_xera_unrounded": 0.99}];'
    rows = S.season_rows(page)
    assert rows == {"pitcher": {"2026": {"aggregate": "0", "year": 2026, "player_type": "pitcher", "grouping_code": "Pitcher and Year", "xera": 2.34, "percent_rank_xera": 99}}}


def test_every_saved_file_has_its_source_and_date():
    m = json.loads((SV / "manifest.json").read_text())
    for kind in ("pitcher", "batter"):
        for year in (2025, 2026):
            f = f"percentile_rankings_{kind}_{year}.csv"
            assert (SV / f).exists(), f
            assert m[f]["url"] == S.CSV_URL.format(kind=kind, year=year) and m[f]["pulled"] == "2026-11-23"
            with open(SV / f, encoding="utf-8-sig") as fh:
                assert sum(1 for _ in csv.DictReader(fh)) == m[f]["rows"]
    pages = json.loads((SV / "player_pages.json").read_text())
    assert all(v["url"].startswith(S.PAGE_URL.format(mlbam="")) and v["pulled"] for v in pages.values())


def test_csv_and_player_pages_agree_on_every_shared_rank():
    pages = json.loads((SV / "player_pages.json").read_text())
    n = 0
    for year in (2025, 2026):
        for kind in ("pitcher", "batter"):
            tab = S.load(kind, year)
            for mid, pg in pages.items():
                rec, row = pg["seasons"].get(kind, {}).get(str(year)), tab.get(int(mid))
                if not rec or not row:
                    continue
                for label, col, pkey, _, _ in S.METRICS[kind]:
                    if col:
                        assert row.get(col) == rec.get(pkey), (year, kind, mid, label)
                        n += 1
    assert n > 1000


def test_morejon_card_is_savants():
    c = S.card(670970, "pitcher", 2026)
    got = {r["label"]: (r["pctl"], r["value"]) for r in c["rows"]}
    assert got["xERA"] == (99, 2.34) and got["K %"] == (93, 30.4) and got["BB %"] == (57, 8.0)
    assert got["Chase %"] == (99, 38.6) and got["Extension"] == (28, 6.3)
    assert S.card(670970, "batter", 2026) is None


def test_the_packet_shows_savants_ranks_for_the_pitcher_cards():
    d = json.loads((ROOT / "docs" / "offseason" / "data.json").read_text())
    by = {b["name"]: b for b in d["board"]}
    for name in ("Adrián Morejón", "Kevin Gausman", "Bryan Abreu"):
        sv = by[name]["savant"]
        assert sv and sv["kind"] == "pitcher" and sv["season"] == 2026
        assert [r["label"] for r in sv["rows"]][:3] == ["xERA", "xBA", "xwOBA"]
    assert by["Bryan Abreu"]["savant"]["rows"][8] == {"label": "BB %", "pctl": 1, "value": 15.3, "fmt": "pct", "from_csv": True, "pctl25": 16}
    # hitters: Savant's ranks, and my computed rank only for EV90, which Savant doesn't rank
    aro = by["Randy Arozarena"]
    assert aro["savant"]["kind"] == "batter" and [r["key"] for r in aro["league"]["rows"]] == ["ev90"]
    assert d["savant"]["pulled"] == "2026-11-23"
