"""2026 Postseason Snippets: quick, sourced charts on the 2026 MLB postseason.

Question: who decided October, and how? Ten charts on every pitch of the 2026 postseason
(Wild Card Series through the World Series, Sept. 29 - Oct. 28, 40 games).

Charts (reports/2026-postseason-snippets/):
   1. world_series_wp.png       The World Series in five games: Brewers win probability, pitch by pitch
   2. team_contact.png          Teams: xwOBA on offense vs xwOBA allowed
   3. hitter_wpa.png            Hitters: win probability added, top 20 (ranked bar)
   4. pitcher_wpa.png           Pitchers: win probability added, top 20 (ranked bar)
   5. hitter_xwoba_woba.png     Hitters: results (wOBA) vs quality of contact and walks (xwOBA)
   6. hitter_swing_decisions.png  Hitters: chase rate vs whiff rate
   7. pitcher_whiff_xwoba.png   Pitchers: whiff rate vs xwOBA allowed
   8. velo_leaders.png          Hardest throwers: average fastball velocity, top 20 (ranked bar)
   9. ev_leaders.png            Hardest hitters: average exit velocity, top 20 (ranked bar)
  10. starter_depth.png         Teams: how deep the starters went (outs per start)

Data: Baseball Savant pitch-level search (game types F, D, L, W; season 2026), pulled day by day,
and the MLB Stats API for player names and the official postseason schedule. Win probability is
Savant's own (home_win_exp, delta_home_win_exp). Teams are drawn as color-coded markers with
abbreviations; no logos are used.

Run:  uv run python -m baseball.postseason            (uses the cached pull in data/raw/postseason)
      uv run python -m baseball.postseason --refresh  (re-pulls from Savant and the Stats API)
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import time
import urllib.request
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "postseason"
OUT = ROOT / "reports" / "2026-postseason-snippets"
SEASON = 2026
FIRST, LAST = dt.date(2026, 9, 29), dt.date(2026, 10, 28)

INK, MUTED, GRID = "#1f1f1f", "#6b6b6b", "#e6e6e4"
BAND, ACCENT = "#1f1f1f", "#b4532a"
BOX, BOX_EDGE = "#f6efe9", "#b4532a"
HANDLE = "Dylan Fanelli  |  github.com/IForSureI/Dylan-Fanelli-Baseball-Analytics-Portfolio"
SOURCE = "Data: Baseball Savant, MLB Stats API"

# Club colors (primary, secondary) for the twelve 2026 postseason clubs.
TEAM = {
    "ATL": ("#CE1141", "#13274F"), "BOS": ("#BD3039", "#0C2340"), "CHC": ("#0E3386", "#CC3433"),
    "CLE": ("#00385D", "#E50022"), "CWS": ("#27251F", "#C4CED4"), "HOU": ("#002D62", "#EB6E1F"),
    "LAD": ("#005A9C", "#EF3E42"), "MIL": ("#12284B", "#FFC52F"), "NYY": ("#0C2340", "#C4CED3"),
    "PHI": ("#E81828", "#002D72"), "SD": ("#2F241D", "#FFC425"), "TB": ("#092C5C", "#8FBCE6"),
}
FASTBALLS = {"FF", "SI", "FC"}
SWINGS = {"swinging_strike", "swinging_strike_blocked", "foul", "foul_tip", "hit_into_play", "foul_bunt",
          "missed_bunt", "bunt_foul_tip"}
WHIFFS = {"swinging_strike", "swinging_strike_blocked", "foul_tip", "missed_bunt"}


# ---------------------------------------------------------------- data

def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "baseball-portfolio/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def pull(refresh: bool = False) -> tuple[pd.DataFrame, dict]:
    RAW.mkdir(parents=True, exist_ok=True)
    pq, ppl = RAW / "statcast_post_2026.parquet", RAW / "people_2026_post.json"
    if refresh or not pq.exists():
        frames, d = [], FIRST
        while d <= LAST:
            u = ("https://baseballsavant.mlb.com/statcast_search/csv?all=true&hfGT=F%7CD%7CL%7CW%7C"
                 f"&hfSea={SEASON}%7C&player_type=pitcher&type=details&game_date_gt={d}&game_date_lt={d}")
            t = _get(u).decode("utf-8-sig")
            if t.strip():
                df = pd.read_csv(io.StringIO(t), low_memory=False)
                if len(df):
                    frames.append(df)
            d += dt.timedelta(days=1)
            time.sleep(0.5)
        pd.concat(frames, ignore_index=True).to_parquet(pq)
    a = pd.read_parquet(pq)
    if refresh or not ppl.exists():
        ids = sorted(set(a.batter.dropna().astype(int)) | set(a.pitcher.dropna().astype(int)))
        people = {}
        for i in range(0, len(ids), 150):
            d = json.loads(_get("https://statsapi.mlb.com/api/v1/people?personIds=" + ",".join(map(str, ids[i:i + 150]))))
            for p in d["people"]:
                people[str(p["id"])] = {"full": p["fullName"], "last": p.get("lastName", ""),
                                        "use": p.get("useName", p.get("firstName", ""))}
        ppl.write_text(json.dumps(people))
    bx = RAW / "starters_2026_post.json"
    if refresh or not bx.exists():
        sched = json.loads(_get(f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&season={SEASON}&gameType=F,D,L,W"))
        rows = []
        for d in sched["dates"]:
            for g in d["games"]:
                if g["status"]["detailedState"] != "Final":
                    continue
                b = json.loads(_get(f"https://statsapi.mlb.com/api/v1/game/{g['gamePk']}/boxscore"))
                for side in ("home", "away"):
                    t = b["teams"][side]
                    sp = t["pitchers"][0]
                    st = t["players"][f"ID{sp}"]["stats"]["pitching"]
                    rows.append({"game_pk": g["gamePk"], "team": t["team"]["abbreviation"], "pitcher": sp,
                                 "outs": int(st["outs"]), "pitches": int(st["numberOfPitches"])})
        bx.write_text(json.dumps(rows))
    return a, json.loads(ppl.read_text())


def starters() -> pd.DataFrame:
    return pd.DataFrame(json.loads((RAW / "starters_2026_post.json").read_text()))


def prep(a: pd.DataFrame) -> pd.DataFrame:
    a = a.sort_values(["game_pk", "at_bat_number", "pitch_number"]).copy()
    top = a.inning_topbot.eq("Top")
    a["bat_team"] = np.where(top, a.away_team, a.home_team)
    a["fld_team"] = np.where(top, a.home_team, a.away_team)
    a["sign"] = np.where(top, -1.0, 1.0)  # +1 when the home team bats
    a["thrown"] = a.description != "automatic_ball"  # intentional-walk and pitch-clock placeholders aren't pitches
    a["swing"] = a.description.isin(SWINGS)
    a["whiff"] = a.description.isin(WHIFFS)
    a["in_zone"] = a.zone.between(1, 9)
    return a


def plate_appearances(a: pd.DataFrame) -> pd.DataFrame:
    """One row per PA: outcome, wOBA, xwOBA, and the PA's win-probability swing for each side."""
    wpa = a.groupby(["game_pk", "at_bat_number"]).delta_home_win_exp.sum().rename("dwe")
    pa = a[a.events.notna() & (a.events != "truncated_pa")].drop_duplicates(["game_pk", "at_bat_number"], keep="last").set_index(["game_pk", "at_bat_number"])
    pa = pa.join(wpa).reset_index()
    pa["bat_wpa"] = pa.dwe * pa.sign
    pa["x"] = np.where(pa.estimated_woba_using_speedangle.notna(), pa.estimated_woba_using_speedangle, pa.woba_value)
    return pa


def nm(people: dict, pid) -> str:
    p = people.get(str(int(pid)))
    if not p:
        return str(pid)
    return f"{p['use'][:1]}. {p['last']}"


# ---------------------------------------------------------------- drawing

def _lum(hexc: str) -> float:
    h = hexc.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _readable(c1: str, c2: str) -> str:
    if _lum(c1) < 0.62:
        return c1
    return c2 if _lum(c2) < 0.62 else INK


def canvas(figsize=(10, 8.6)):
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.edgecolor": "#9ca3af", "axes.linewidth": 1.0,
                         "xtick.color": INK, "ytick.color": INK, "axes.labelcolor": INK, "text.color": INK})
    fig = plt.figure(figsize=figsize, dpi=200, facecolor="white")
    ax = fig.add_axes([0.10, 0.12, 0.86, 0.70])
    ax.grid(True, color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    return fig, ax


def header_footer(fig, title: str, sub: str):
    fig.text(0.5, 0.93, title, ha="center", va="center", fontsize=25, fontweight="black", color=INK)
    fig.text(0.5, 0.875, sub, ha="center", va="center", fontsize=10, color=MUTED)
    fig.add_artist(Rectangle((0, 0), 1, 0.055, transform=fig.transFigure, color=BAND, zorder=0))
    fig.text(0.02, 0.0275, HANDLE, ha="left", va="center", fontsize=9.5, color="white", fontweight="bold")
    fig.text(0.98, 0.0275, SOURCE, ha="right", va="center", fontsize=9.5, color="#f4b183", fontweight="bold")


def corner(ax, text, where):
    pos = {"tl": (0.02, 0.97, "left", "top"), "tr": (0.98, 0.97, "right", "top"),
           "bl": (0.02, 0.03, "left", "bottom"), "br": (0.98, 0.03, "right", "bottom")}[where]
    ax.text(pos[0], pos[1], text, transform=ax.transAxes, ha=pos[2], va=pos[3], fontsize=11, fontweight="bold",
            color=ACCENT, bbox=dict(boxstyle="round,pad=0.35", fc=BOX, ec=BOX_EDGE, lw=1.0), zorder=6)


def pad(ax, frac=0.12):
    for get, setter in ((ax.get_xlim, ax.set_xlim), (ax.get_ylim, ax.set_ylim)):
        a, b = get()
        d = (b - a) * frac
        setter(a - d, b + d)


def mean_lines(ax, xm, ym):
    ax.axvline(xm, color=ACCENT, ls=":", lw=1.1, zorder=2)
    ax.axhline(ym, color=ACCENT, ls=":", lw=1.1, zorder=2)


def sub_line(extra: str) -> str:
    return f"2026 Postseason | Wild Card through World Series (40 games) | {extra}"


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, dpi=200, facecolor="white")
    plt.close(fig)


def team_dots(ax, t, xcol, ycol, size=520):
    xs, ys = t[xcol].to_numpy(float), t[ycol].to_numpy(float)
    xr, yr = (xs.max() - xs.min()) or 1, (ys.max() - ys.min()) or 1
    u, v = (xs - xs.min()) / xr, (ys - ys.min()) / yr
    pu, pv = u.copy(), v.copy()
    rad = 0.06
    for _ in range(400):
        moved = False
        for i in range(len(pu)):
            for j in range(i + 1, len(pu)):
                du, dv = pu[j] - pu[i], pv[j] - pv[i]
                d = np.hypot(du, dv)
                if d < rad:
                    if d < 1e-9:
                        du, dv, d = 1e-3, 0.0, 1e-3
                    push = (rad - d) / 2
                    pu[i] -= du / d * push; pv[i] -= dv / d * push
                    pu[j] += du / d * push; pv[j] += dv / d * push
                    moved = True
        if not moved:
            break
    px, py = xs.min() + pu * xr, ys.min() + pv * yr
    for k, abbr in enumerate(t.index):
        c1, c2 = TEAM[abbr]
        if np.hypot(pu[k] - u[k], pv[k] - v[k]) > 0.004:
            ax.plot([xs[k], px[k]], [ys[k], py[k]], color="#9ca3af", lw=0.8, zorder=4)
            ax.scatter([xs[k]], [ys[k]], s=10, color=c1, zorder=4)
        ax.scatter([px[k]], [py[k]], s=size, color=c1, edgecolor=c2, linewidth=2.2, zorder=5)
        ax.text(px[k], py[k], abbr, ha="center", va="center", fontsize=8, fontweight="bold",
                color="white" if _lum(c1) < 0.55 else INK, zorder=6)


def player_points(ax, df, x, y, label, team, size_col=None):
    from adjustText import adjust_text
    ax.scatter(df[x], df[y], s=0)
    ax.margins(0.04)
    pad(ax, 0.10)
    if size_col is None:
        sizes = np.full(len(df), 70.0)
    else:
        s = df[size_col].astype(float)
        sizes = 40 + 160 * (s - s.min()) / max(1.0, s.max() - s.min())
    dots = []
    for (_, r), sz in zip(df.iterrows(), sizes):
        c1, c2 = TEAM[r[team]]
        dots.append(ax.scatter(r[x], r[y], s=sz, color=c1, edgecolor=c2, linewidth=1.6, zorder=5))
    texts = [ax.text(r[x], r[y], r[label], fontsize=8.6, fontweight="bold", color=_readable(*TEAM[r[team]]), zorder=7)
             for _, r in df.iterrows()]
    adjust_text(texts, x=df[x].to_numpy(float), y=df[y].to_numpy(float), ax=ax, expand=(1.3, 1.7),
                force_text=(0.4, 0.6), force_static=(0.5, 0.8),
                arrowprops=dict(arrowstyle="-", color="#9ca3af", lw=0.6))


def ranked_bars(rows, value, label, team, fmt, xlabel, title, sub, fname, right=None, right_head="",
                diverging=False, ref=None, ref_label="", names_left=False):
    fig = plt.figure(figsize=(10, 9.8 if len(rows) <= 20 else 12.5), dpi=200, facecolor="white")
    ax = fig.add_axes([0.27 if names_left else 0.07, 0.11, 0.64 if names_left else 0.80, 0.71])
    ax.grid(True, axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    n = len(rows)
    y = np.arange(n)[::-1]
    vals = rows[value].to_numpy(float)
    if diverging:
        span = np.abs(vals).max()
        base, lo, hi = 0.0, -span * 1.45, span * 1.45
    else:
        lo = 0.0 if names_left else vals.min() - (vals.max() - vals.min()) * 0.9
        lo = max(lo, 0.0) if vals.min() > 0 else lo
        base, hi = lo, vals.max() + (vals.max() - lo) * 0.12
    for yi, (_, r) in zip(y, rows.iterrows()):
        c1, c2 = TEAM[r[team]]
        v = r[value]
        ax.barh(yi, v - base, left=base, color=c1, edgecolor=c2, lw=1.4, height=0.8, zorder=3)
        if diverging:
            ax.text(-0.01 * span if v >= 0 else 0.01 * span, yi, r[label], ha="right" if v >= 0 else "left", va="center",
                    fontsize=9.5, fontweight="bold", color=_readable(c1, c2), zorder=4)
            ax.text(v + (0.02 * span if v >= 0 else -0.02 * span), yi, fmt(v), ha="left" if v >= 0 else "right",
                    va="center", fontsize=10, fontweight="bold", color=INK, zorder=4)
        elif names_left:
            ax.text(lo - (hi - lo) * 0.02, yi, r[label], ha="right", va="center", fontsize=10, fontweight="bold",
                    color=_readable(c1, c2), zorder=4)
            ax.text(v + (hi - lo) * 0.006, yi, fmt(v), ha="left", va="center", fontsize=10, fontweight="bold",
                    color=INK, zorder=4)
        else:
            ax.text(v - (hi - lo) * 0.006, yi, r[label], ha="right", va="center", fontsize=9.5, fontweight="bold",
                    color="white" if _lum(c1) < 0.55 else INK, zorder=4)
            ax.text(v + (hi - lo) * 0.006, yi, fmt(v), ha="left", va="center", fontsize=10, fontweight="bold",
                    color=INK, zorder=4)
        if right is not None:
            ax.text(1.005, yi, right(r), transform=ax.get_yaxis_transform(), va="center", ha="left", fontsize=9, color=MUTED)
    if right is not None:
        ax.text(1.005, n - 0.2, right_head, transform=ax.get_yaxis_transform(), va="bottom", ha="left", fontsize=8.5,
                color=MUTED, fontweight="bold")
    if diverging:
        ax.axvline(0, color=INK, lw=1, zorder=2)
    if ref is not None:
        ax.axvline(ref, color=ACCENT, ls="--", lw=1.3, zorder=2)
        ax.text(ref, n - 0.1, f" {ref_label}", color=ACCENT, fontsize=9, fontweight="bold", va="bottom", ha="left")
    ax.set_yticks(y)
    ax.set_yticklabels(range(1, n + 1), fontsize=9)
    if names_left:
        ax.tick_params(axis="y", length=0, pad=2)
        ax.set_yticklabels([])
        for yi, k in zip(y, range(1, n + 1)):
            ax.text(-0.36, yi, f"{k}", transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=9, color=MUTED)
    ax.set_xlim(lo, hi)
    ax.set_ylim(-0.7, n + 0.6)
    ax.set_xlabel(xlabel, fontsize=12, fontweight="bold")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    header_footer(fig, title, sub)
    save(fig, fname)


# ---------------------------------------------------------------- charts

def chart_world_series(a, f):
    plt.rcParams.update({"font.family": "DejaVu Sans"})
    ws = a[a.game_type == "W"]
    games = sorted(ws.game_pk.unique(), key=lambda g: ws.loc[ws.game_pk == g, "game_date"].iloc[0])
    fig = plt.figure(figsize=(10, 9.4), dpi=200, facecolor="white")
    mil_c, tb_c = TEAM["MIL"][0], TEAM["TB"][0]
    summary = []
    for i, g in enumerate(games):
        d = ws[ws.game_pk == g]
        home = d.home_team.iloc[0]
        # win probability after each pitch, from the Brewers' side
        hw = (d.home_win_exp + d.delta_home_win_exp.fillna(0)).to_numpy()
        mil = hw if home == "MIL" else 1 - hw
        mil = np.r_[0.5, mil]
        ax = fig.add_axes([0.08, 0.715 - i * 0.135, 0.84, 0.098])
        xs = np.arange(len(mil))
        ax.fill_between(xs, 0.5, mil, where=mil >= 0.5, color=TEAM["MIL"][1], alpha=0.55, lw=0, interpolate=True)
        ax.fill_between(xs, 0.5, mil, where=mil < 0.5, color=TEAM["TB"][1], alpha=0.55, lw=0, interpolate=True)
        ax.plot(xs, mil, color=mil_c, lw=1.6)
        ax.axhline(0.5, color=MUTED, lw=0.8)
        ax.set_ylim(0, 1)
        ax.set_xlim(0, len(mil) - 1)
        ax.set_yticks([0, 0.5, 1])
        ax.set_yticklabels(["0%", "50%", "100%"], fontsize=8, color=MUTED)
        ax.set_xticks([])
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        hs, as_ = int(d.post_home_score.max()), int(d.post_away_score.max())
        away = d.away_team.iloc[0]
        winner = home if hs > as_ else away
        date = pd.to_datetime(d.game_date.iloc[0]).strftime("%b %-d")
        ax.text(0.0, 1.06, f"Game {i + 1}  |  {date}  |  {away} {as_}, {home} {hs}", transform=ax.transAxes,
                fontsize=11, fontweight="bold", color=INK, va="bottom")
        ax.text(1.0, 1.06, f"{winner} wins", transform=ax.transAxes, fontsize=10.5, fontweight="bold",
                color=TEAM[winner][0], va="bottom", ha="right")
        # the biggest single swing of the game
        dd = d.assign(mil_d=np.where(d.home_team == "MIL", 1, -1) * d.delta_home_win_exp.fillna(0))
        k = dd.mil_d.abs().idxmax()
        pos = list(d.index).index(k) + 1
        ax.scatter([pos], [mil[pos]], s=30, color=ACCENT, zorder=5, clip_on=False)
        summary.append({"game": i + 1, "date": str(d.game_date.iloc[0])[:10], "away": away, "away_runs": as_,
                        "home": home, "home_runs": hs, "winner": winner,
                        "biggest_swing_mil": round(float(dd.loc[k, "mil_d"]), 3),
                        "biggest_swing_inning": int(d.loc[k, "inning"]), "biggest_swing_event": str(d.loc[k, "events"])})
    fig.text(0.08, 0.072, "Line = Brewers' win probability after every pitch (Savant win expectancy).\n"
             "Gold = Brewers favored, light blue = Rays favored. Dot = the game's biggest single swing.",
             fontsize=8.5, color=MUTED)
    mil_w = sum(s["winner"] == "MIL" for s in summary)
    header_footer(fig, "The World Series in Five", f"2026 World Series | Brewers {mil_w}, Rays {len(summary) - mil_w} | Win probability, pitch by pitch")
    save(fig, "world_series_wp.png")
    f["world_series"] = {"games": summary, "mil_wins": int(mil_w)}


def chart_team_contact(pa, f):
    den = pa[pa.woba_denom == 1]
    off = den.groupby("bat_team").agg(x_for=("x", "mean"), pa=("x", "size"))
    dfn = den.groupby("fld_team").agg(x_against=("x", "mean"))
    t = off.join(dfn)
    fig, ax = canvas()
    team_dots(ax, t, "x_for", "x_against")
    pad(ax)
    ax.invert_yaxis()
    mean_lines(ax, den.x.mean(), den.x.mean())
    corner(ax, "Hit hard, allowed little", "tr")
    corner(ax, "Outplayed on contact", "bl")
    ax.xaxis.set_major_formatter(mtick.FormatStrFormatter("%.3f"))
    ax.yaxis.set_major_formatter(mtick.FormatStrFormatter("%.3f"))
    ax.set_xlabel("Offense: xwOBA", fontsize=12, fontweight="bold")
    ax.set_ylabel("Pitching and defense: xwOBA allowed (better is up)", fontsize=12, fontweight="bold")
    header_footer(fig, "Postseason Teams: Contact Quality", sub_line("xwOBA = expected wOBA from exit velocity, launch angle, walks and K's"))
    save(fig, "team_contact.png")
    t["net"] = t.x_for - t.x_against
    f["team_contact"] = {"league_xwoba": round(float(den.x.mean()), 3),
                         "teams": t.round(3).reset_index().rename(columns={"index": "team"}).sort_values("net", ascending=False).to_dict("records")}


def chart_wpa(pa, people, f):
    b = pa.groupby("batter").agg(team=("bat_team", lambda s: s.mode().iat[0]), pa=("bat_wpa", "size"), wpa=("bat_wpa", "sum")).reset_index()
    b["lab"] = [f"{nm(people, i)} ({t})" for i, t in zip(b.batter, b.team)]
    q = b.sort_values("wpa", ascending=False).head(20).reset_index(drop=True)
    ranked_bars(q, "wpa", "lab", "team", lambda v: f"{v:+.2f}", "Win probability added (sum over plate appearances)",
                "October's Biggest Bats: WPA", sub_line("Top 20 hitters | WPA = change in win probability on his plate appearances"),
                "hitter_wpa.png", right=lambda r: f"{int(r.pa)}", right_head="PA", names_left=True)
    p = pa.groupby("pitcher").agg(team=("fld_team", lambda s: s.mode().iat[0]), bf=("bat_wpa", "size"), wpa=("bat_wpa", lambda s: -s.sum())).reset_index()
    p["lab"] = [f"{nm(people, i)} ({t})" for i, t in zip(p.pitcher, p.team)]
    qp = p.sort_values("wpa", ascending=False).head(20).reset_index(drop=True)
    ranked_bars(qp, "wpa", "lab", "team", lambda v: f"{v:+.2f}", "Win probability added (sum over batters faced)",
                "October's Biggest Arms: WPA", sub_line("Top 20 pitchers | WPA = change in win probability on the batters he faced"),
                "pitcher_wpa.png", right=lambda r: f"{int(r.bf)}", right_head="BF", names_left=True)
    f["hitter_wpa"] = {"top5": q.head(5)[["lab", "pa", "wpa"]].round(3).to_dict("records"),
                       "bottom3": b.sort_values("wpa").head(3)[["lab", "pa", "wpa"]].round(3).to_dict("records")}
    f["pitcher_wpa"] = {"top5": qp.head(5)[["lab", "bf", "wpa"]].round(3).to_dict("records"),
                        "bottom3": p.sort_values("wpa").head(3)[["lab", "bf", "wpa"]].round(3).to_dict("records")}


def chart_hitter_xwoba(pa, people, f, min_pa=25):
    den = pa[pa.woba_denom == 1]
    h = den.groupby("batter").agg(team=("bat_team", lambda s: s.mode().iat[0]), pa=("x", "size"),
                                  woba=("woba_value", "mean"), xwoba=("x", "mean")).reset_index()
    q = h[h.pa >= min_pa].copy()
    q["name"] = [nm(people, i) for i in q.batter]
    fig, ax = canvas()
    player_points(ax, q, "xwoba", "woba", "name", "team", size_col="pa")
    lo = min(q.xwoba.min(), q.woba.min()) - 0.03
    hi = max(q.xwoba.max(), q.woba.max()) + 0.03
    ax.plot([lo, hi], [lo, hi], color="#9ca3af", ls="--", lw=1, zorder=1)
    corner(ax, "Results ran ahead of contact", "tl")
    corner(ax, "Hit it well, little to show", "br")
    for axis in (ax.xaxis, ax.yaxis):
        axis.set_major_formatter(mtick.FormatStrFormatter("%.3f"))
    ax.set_xlabel("xwOBA (quality of contact, walks and strikeouts)", fontsize=12, fontweight="bold")
    ax.set_ylabel("wOBA (actual results)", fontsize=12, fontweight="bold")
    header_footer(fig, "Hitters: Results vs. Quality of Contact", sub_line(f"Min. {min_pa} PA | Dashed line = results equal to contact | Bubble size = PA"))
    save(fig, "hitter_xwoba_woba.png")
    q["gap"] = q.woba - q.xwoba
    f["hitter_xwoba_woba"] = {"n": int(len(q)), "min_pa": min_pa,
                              "top_xwoba": q.sort_values("xwoba", ascending=False).head(3)[["name", "team", "pa", "woba", "xwoba"]].round(3).to_dict("records"),
                              "most_above": q.sort_values("gap", ascending=False).head(3)[["name", "team", "woba", "xwoba"]].round(3).to_dict("records"),
                              "most_below": q.sort_values("gap").head(3)[["name", "team", "woba", "xwoba"]].round(3).to_dict("records")}


def chart_swing_decisions(a, pa, people, f, min_pa=25):
    pcount = pa.groupby("batter").size()
    keep = pcount[pcount >= min_pa].index
    d = a[a.batter.isin(keep)]
    o = d[~d.in_zone & d.zone.notna()]
    g = pd.DataFrame({
        "team": d.groupby("batter").bat_team.agg(lambda s: s.mode().iat[0]),
        "chase": o.groupby("batter").swing.mean(),
        "whiff": d[d.swing].groupby("batter").whiff.mean(),
        "pa": pcount.reindex(keep),
    }).dropna().reset_index()
    g["name"] = [nm(people, i) for i in g.batter]
    lg_chase = float(a[~a.in_zone & a.zone.notna()].swing.mean())
    lg_whiff = float(a[a.swing].whiff.mean())
    fig, ax = canvas()
    player_points(ax, g, "chase", "whiff", "name", "team")
    ax.invert_yaxis()
    mean_lines(ax, lg_chase, lg_whiff)
    corner(ax, "Disciplined and hard to miss", "tl")
    corner(ax, "Chased and missed", "br")
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Chase rate (swings at pitches outside the zone)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Whiff rate per swing (better is up)", fontsize=12, fontweight="bold")
    header_footer(fig, "Hitters: Swing Decisions", sub_line(f"Min. {min_pa} PA | Zone = Savant zones 1-9 | Dotted lines = postseason average"))
    save(fig, "hitter_swing_decisions.png")
    f["hitter_swing_decisions"] = {"n": int(len(g)), "league_chase": round(lg_chase, 3), "league_whiff": round(lg_whiff, 3),
                                   "lowest_chase": g.nsmallest(3, "chase")[["name", "team", "chase", "whiff"]].round(3).to_dict("records"),
                                   "lowest_whiff": g.nsmallest(3, "whiff")[["name", "team", "chase", "whiff"]].round(3).to_dict("records")}


def chart_pitcher_whiff(a, pa, people, f, min_pitches=100):
    n = a[a.thrown].groupby("pitcher").size()
    keep = n[n >= min_pitches].index
    d = a[a.pitcher.isin(keep) & a.thrown]
    den = pa[(pa.woba_denom == 1) & pa.pitcher.isin(keep)]
    g = pd.DataFrame({
        "team": d.groupby("pitcher").fld_team.agg(lambda s: s.mode().iat[0]),
        "whiff": d[d.swing].groupby("pitcher").whiff.mean(),
        "xwoba": den.groupby("pitcher").x.mean(),
        "pitches": n.reindex(keep),
    }).dropna().reset_index()
    g["name"] = [nm(people, i) for i in g.pitcher]
    fig, ax = canvas()
    player_points(ax, g, "whiff", "xwoba", "name", "team", size_col="pitches")
    ax.invert_yaxis()
    mean_lines(ax, float(a[a.swing].whiff.mean()), float(pa[pa.woba_denom == 1].x.mean()))
    corner(ax, "Missed bats, limited damage", "tr")
    corner(ax, "Hittable", "bl")
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.yaxis.set_major_formatter(mtick.FormatStrFormatter("%.3f"))
    ax.set_xlabel("Whiff rate per swing", fontsize=12, fontweight="bold")
    ax.set_ylabel("xwOBA allowed (better is up)", fontsize=12, fontweight="bold")
    header_footer(fig, "Pitchers: Whiffs vs. Damage", sub_line(f"Min. {min_pitches} pitches | Bubble size = pitches | Dotted lines = postseason average"))
    save(fig, "pitcher_whiff_xwoba.png")
    f["pitcher_whiff_xwoba"] = {"n": int(len(g)), "min_pitches": min_pitches,
                                "top_whiff": g.nlargest(3, "whiff")[["name", "team", "pitches", "whiff", "xwoba"]].round(3).to_dict("records"),
                                "best_xwoba": g.nsmallest(3, "xwoba")[["name", "team", "pitches", "whiff", "xwoba"]].round(3).to_dict("records")}


def chart_velo(a, people, f, min_fb=15):
    fb = a[a.pitch_type.isin(FASTBALLS - {"FC"}) & a.release_speed.notna()]
    g = fb.groupby("pitcher").agg(team=("fld_team", lambda s: s.mode().iat[0]), n=("release_speed", "size"),
                                  velo=("release_speed", "mean"), top=("release_speed", "max")).reset_index()
    q = g[g.n >= min_fb].sort_values("velo", ascending=False).head(20).reset_index(drop=True)
    q["lab"] = [f"{nm(people, i)} ({t})" for i, t in zip(q.pitcher, q.team)]
    lg = float(fb.release_speed.mean())
    ranked_bars(q, "velo", "lab", "team", lambda v: f"{v:.1f}", "Average four-seam and sinker velocity (mph)",
                "October Velocity Leaders", sub_line(f"Top 20, min. {min_fb} four-seamers or sinkers | Fastest pitch at right"),
                "velo_leaders.png", right=lambda r: f"{r.top:.1f}", right_head="Max", ref=lg, ref_label=f"Postseason avg {lg:.1f}")
    f["velo_leaders"] = {"league_fb_velo": round(lg, 2), "top5": q.head(5)[["lab", "n", "velo", "top"]].round(2).to_dict("records"),
                         "fastest_pitch": {"mph": float(fb.release_speed.max()),
                                           "pitcher": nm(people, fb.loc[fb.release_speed.idxmax(), "pitcher"])}}


def chart_ev(a, people, f, min_bip=15):
    b = a[a.type.eq("X") & a.launch_speed.notna()]
    g = b.groupby("batter").agg(team=("bat_team", lambda s: s.mode().iat[0]), n=("launch_speed", "size"),
                                ev=("launch_speed", "mean"), top=("launch_speed", "max"),
                                hard=("launch_speed", lambda s: (s >= 95).mean())).reset_index()
    q = g[g.n >= min_bip].sort_values("ev", ascending=False).head(20).reset_index(drop=True)
    q["lab"] = [f"{nm(people, i)} ({t})" for i, t in zip(q.batter, q.team)]
    lg = float(b.launch_speed.mean())
    ranked_bars(q, "ev", "lab", "team", lambda v: f"{v:.1f}", "Average exit velocity (mph)",
                "October's Hardest Hitters", sub_line(f"Top 20, min. {min_bip} batted balls | Hardest-hit ball at right"),
                "ev_leaders.png", right=lambda r: f"{r.top:.1f}", right_head="Max", ref=lg, ref_label=f"Postseason avg {lg:.1f}")
    f["ev_leaders"] = {"league_ev": round(lg, 2), "top5": q.head(5)[["lab", "n", "ev", "top", "hard"]].round(3).to_dict("records"),
                       "hardest_ball": {"mph": float(b.launch_speed.max()), "batter": nm(people, b.loc[b.launch_speed.idxmax(), "batter"])}}


def chart_starters(a, f):
    """Starter depth from the official MLB box scores (outs and pitches as scored)."""
    rows = starters()
    t = rows.groupby("team").agg(outs=("outs", "mean"), pitches=("pitches", "mean"), games=("outs", "size"))
    t = t.sort_values("outs", ascending=False).reset_index()
    t["lab"] = t.team
    t["ip"] = t.outs / 3
    ranked_bars(t, "ip", "lab", "team", lambda v: f"{v:.1f}",
                "Average innings per start (outs recorded / 3)",
                "How Deep the Starters Went", sub_line("Official box-score starter lines | Right: pitches per start, games"),
                "starter_depth.png", right=lambda r: f"{r.pitches:.0f} p, {int(r.games)} g", right_head="Per start")
    f["starter_depth"] = {"teams": t[["team", "games", "outs", "pitches"]].round(2).to_dict("records")}


def write_readme(f: dict) -> None:
    """The folder's README; every number comes from findings.json."""
    ws = f["world_series"]
    g = ws["games"]
    score = ", ".join(f"Game {x['game']} {x['winner']} {max(x['away_runs'], x['home_runs'])}-{min(x['away_runs'], x['home_runs'])}" for x in g)
    tc = f["team_contact"]["teams"]
    hw, pw = f["hitter_wpa"]["top5"], f["pitcher_wpa"]["top5"]
    hx, sd, pwx = f["hitter_xwoba_woba"], f["hitter_swing_decisions"], f["pitcher_whiff_xwoba"]
    v, e, st = f["velo_leaders"], f["ev_leaders"], f["starter_depth"]["teams"]
    pct = lambda x: f"{100 * x:.1f}%"
    ip = lambda outs: f"{outs / 3:.1f}"
    md = f"""# 2026 Postseason Snippets

Ten quick charts on the 2026 postseason, the kind a front office passes around the morning after the World Series. Every pitch from the Wild Card Series through the World Series: {f['games']} games, {f['pitches']:,} thrown pitches and {f['plate_appearances']:,} plate appearances ({f['first_date']} to {f['last_date']}). Small samples by design: these describe October; they don't project 2027.

| | |
|---|---|
| <img src="world_series_wp.png" width="100%"> | <img src="team_contact.png" width="100%"> |
| <img src="hitter_wpa.png" width="100%"> | <img src="pitcher_wpa.png" width="100%"> |
| <img src="hitter_xwoba_woba.png" width="100%"> | <img src="hitter_swing_decisions.png" width="100%"> |
| <img src="pitcher_whiff_xwoba.png" width="100%"> | <img src="starter_depth.png" width="100%"> |
| <img src="velo_leaders.png" width="100%"> | <img src="ev_leaders.png" width="100%"> |

## What each one says

1. **The World Series in Five** ([chart](world_series_wp.png)). The Brewers beat the Rays {ws['mil_wins']} games to {len(g) - ws['mil_wins']} ({score}). Tampa Bay's only win was Game 4, which went 12 innings: Milwaukee scored in the top of the 12th to lead 3-2, and the Rays answered with two in the bottom half.
2. **Teams: Contact Quality** ([chart](team_contact.png)). {tc[0]['bat_team']} had the best gap between the contact it made and the contact it allowed: {tc[0]['x_for']:.3f} xwOBA on offense, {tc[0]['x_against']:.3f} allowed. The postseason average was {f['team_contact']['league_xwoba']:.3f}.
3. **October's Biggest Bats: WPA** ([chart](hitter_wpa.png)). {hw[0]['lab']} added {hw[0]['wpa']:+.2f} WPA over {hw[0]['pa']} plate appearances, ahead of {hw[1]['lab']} ({hw[1]['wpa']:+.2f}).
4. **October's Biggest Arms: WPA** ([chart](pitcher_wpa.png)). {pw[0]['lab']} led every pitcher at {pw[0]['wpa']:+.2f} over {pw[0]['bf']} batters in relief, most of them from the seventh inning on; next was {pw[1]['lab']} ({pw[1]['wpa']:+.2f}).
5. **Hitters: Results vs. Quality of Contact** ([chart](hitter_xwoba_woba.png)). Among {hx['n']} hitters with {hx['min_pa']}+ plate appearances, {hx['most_below'][0]['name']} ({hx['most_below'][0]['team']}) had the biggest gap the wrong way: {hx['most_below'][0]['xwoba']:.3f} xwOBA, {hx['most_below'][0]['woba']:.3f} wOBA. {hx['most_above'][0]['name']} ({hx['most_above'][0]['team']}) ran furthest ahead of his contact ({hx['most_above'][0]['woba']:.3f} vs {hx['most_above'][0]['xwoba']:.3f}).
6. **Hitters: Swing Decisions** ([chart](hitter_swing_decisions.png)). {sd['lowest_chase'][0]['name']} ({sd['lowest_chase'][0]['team']}) chased {pct(sd['lowest_chase'][0]['chase'])} of pitches outside the zone (postseason average {pct(sd['league_chase'])}); {sd['lowest_whiff'][0]['name']} ({sd['lowest_whiff'][0]['team']}) missed on {pct(sd['lowest_whiff'][0]['whiff'])} of swings (average {pct(sd['league_whiff'])}).
7. **Pitchers: Whiffs vs. Damage** ([chart](pitcher_whiff_xwoba.png)). {pwx['top_whiff'][0]['name']} ({pwx['top_whiff'][0]['team']}) got a whiff on {pct(pwx['top_whiff'][0]['whiff'])} of swings over {pwx['top_whiff'][0]['pitches']} pitches and allowed a {pwx['top_whiff'][0]['xwoba']:.3f} xwOBA.
8. **October Velocity Leaders** ([chart](velo_leaders.png)). {v['top5'][0]['lab']} averaged {v['top5'][0]['velo']:.1f} mph on his four-seamers and sinkers; the fastest pitch of the postseason was {v['fastest_pitch']['pitcher']}'s {v['fastest_pitch']['mph']:.1f}. The postseason average was {v['league_fb_velo']:.1f}.
9. **October's Hardest Hitters** ([chart](ev_leaders.png)). {e['top5'][0]['lab']} averaged {e['top5'][0]['ev']:.1f} mph on {e['top5'][0]['n']} batted balls, with {e['top5'][1]['lab']} right behind ({e['top5'][1]['ev']:.1f} on {e['top5'][1]['n']}). The hardest-hit ball was {e['hardest_ball']['batter']}'s {e['hardest_ball']['mph']:.1f}.
10. **How Deep the Starters Went** ([chart](starter_depth.png)). {st[0]['team']} starters averaged {ip(st[0]['outs'])} innings a start ({st[0]['outs']:.1f} outs); {st[-1]['team']} starters averaged {ip(st[-1]['outs'])} ({st[-1]['outs']:.1f} outs) over {st[-1]['games']} games. The lines come from the official MLB box scores.

## Method notes

- Data: Baseball Savant pitch-level search for 2026 game types F, D, L and W (Wild Card, Division Series, League Championship Series, World Series), pulled one day at a time; names from the MLB Stats API. The official schedule lists 40 completed postseason games, and all 40 are in the pull.
- Win probability is Savant's win expectancy. A plate appearance's WPA is the sum of Savant's pitch-by-pitch changes during it, credited to the batter and to the pitcher who threw the last pitch (Savant's convention). Changes between pitches, such as pickoffs and caught stealings, aren't in Savant's pitch deltas and aren't credited to anyone, so a game's changes fall short of its result by up to about 0.06 and a club's total by up to about 0.08.
- Plate appearances cut short by the end of an inning (Savant's `truncated_pa`) are left out, and automatic balls (intentional walks, pitch-clock violations) are left out of pitch counts and pitch rates.
- xwOBA uses Savant's expected wOBA on balls in play and the actual value on walks, hit-by-pitches and strikeouts.
- Zone = Savant zones 1-9. Whiff rate = swinging strikes and foul tips per swing.
- Starter depth uses the official MLB box scores (outs recorded and pitches thrown by each club's first pitcher). Houston's starters recorded two outs in each of its two games. Innings are shown as outs divided by three (5.5 = 16.5 outs), not box-score notation.
- Velocity and exit-velocity bars start near the leaders' range, not at zero, so read the numbers, not the bar lengths.

## Reproduce

```bash
uv run python -m baseball.postseason --refresh   # re-pulls from Savant and the Stats API
```

Code: [`baseball/postseason.py`](../../baseball/postseason.py). Numbers: [`findings.json`](findings.json).
"""
    (OUT / "README.md").write_text(md)


def main(refresh: bool = False):
    a, people = pull(refresh)
    a = prep(a)
    pa = plate_appearances(a)
    f = {"season": SEASON, "games": int(a.game_pk.nunique()), "pitches": int(a.thrown.sum()), "plate_appearances": int(len(pa)),
         "first_date": str(a.game_date.min())[:10], "last_date": str(a.game_date.max())[:10], "built": dt.date.today().isoformat()}
    chart_world_series(a, f)
    chart_team_contact(pa, f)
    chart_wpa(pa, people, f)
    chart_hitter_xwoba(pa, people, f)
    chart_swing_decisions(a, pa, people, f)
    chart_pitcher_whiff(a, pa, people, f)
    chart_velo(a, people, f)
    chart_ev(a, people, f)
    chart_starters(a, f)
    (OUT / "findings.json").write_text(json.dumps(f, indent=1, default=float))
    write_readme(json.loads((OUT / "findings.json").read_text()))
    print(json.dumps(f, indent=1, default=float)[:4000])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    main(ap.parse_args().refresh)
