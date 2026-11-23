"""Find and download MLB's own highlight clip of a play.

Every MLB game has a public content feed (MLB Stats API, /api/v1/game/{game_pk}/content) listing its highlight
clips, each with an MP4 at 1280x720 and 59.94 frames a second. A clip's `guid` is the play's Statcast play id, the
same id the live feed (/api/v1.1/game/{game_pk}/feed/live) gives every pitch, so a play can be matched to its clip
exactly. Not every play has a clip; home runs nearly always do.

Clips are MLB's property: they are downloaded to data/raw/video/ (never committed) and every report links the clip
on MLB.com instead of reproducing frames. What is committed is what I measured from them.
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "video"
API = "https://statsapi.mlb.com/api"
UA = {"User-Agent": "Mozilla/5.0"}


def _get_json(url: str, cache: Path | None = None) -> dict:
    if cache and cache.exists():
        return json.loads(cache.read_text())
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                data = json.loads(r.read())
            break
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data))
    return data


def plays(game_pk: int, batter: int, event: str = "home_run") -> list[dict]:
    """The batter's plays of one event type in a game, with the play id of the pitch that ended each."""
    feed = _get_json(f"{API}/v1.1/game/{game_pk}/feed/live", RAW / "feeds" / f"{game_pk}.json")
    out = []
    for p in feed["liveData"]["plays"]["allPlays"]:
        if p["result"].get("eventType") == event and p["matchup"]["batter"]["id"] == batter:
            pitches = [e for e in p["playEvents"] if e.get("isPitch")]
            if pitches:
                last = pitches[-1]
                out.append(dict(game_pk=game_pk, at_bat_index=p["about"]["atBatIndex"], inning=p["about"]["inning"],
                                play_id=last.get("playId"), pitcher=p["matchup"]["pitcher"]["id"],
                                pitcher_name=p["matchup"]["pitcher"]["fullName"], description=p["result"].get("description", "")))
    return out


def clip_for(game_pk: int, play_id: str) -> dict | None:
    content = _get_json(f"{API}/v1/game/{game_pk}/content", RAW / "content" / f"{game_pk}.json")
    for it in content.get("highlights", {}).get("highlights", {}).get("items", []):
        if it.get("guid") == play_id:
            mp4 = next((p["url"] for p in it.get("playbacks", []) if p.get("name") == "mp4Avc"), None)
            if mp4:
                return dict(headline=it.get("headline"), slug=it.get("slug"), date=it.get("date"),
                            page=f"https://www.mlb.com/video/{it.get('slug')}", mp4=mp4)
    return None


def download(play_id: str, url: str, raw: Path = RAW) -> Path:
    p = raw / "clips" / f"{play_id}.mp4"
    if p.exists() and p.stat().st_size > 100_000:
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        p.write_bytes(r.read())
    return p
