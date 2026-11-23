"""Build the 2027 Offseason Decision Packet (docs/offseason/): the page from docs/offseason_template.html and its data
(docs/offseason/data.json) from this repo's outputs. Everything in it is public data.

    uv run python docs/build_offseason.py

Needs the league sequence files (data/seq) for teams and the video pose files (data/raw/video/pose) for the swing lab.
Without them it refreshes the previous data.json: ids, 2026 clubs, headshots and swing-lab figures are kept, and
everything read from market/ and reports/outputs/ is rebuilt. A clip removed by eye since the last full build is taken
out of the swing lab and its counts, medians and tests are recomputed (the median skeleton too, given the pose files).
"""
import json, glob, base64, urllib.request, sys
from pathlib import Path
import numpy as np, pandas as pd
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
OUT = REPO / "docs" / "offseason"
OUT.mkdir(parents=True, exist_ok=True)
from baseball.roster import market as mk
from baseball.video import breakdown as B

TEAMS = {  # (primary, secondary); the Rockies use black and silver (no purple, by the house rules)
 "ARI": ("#A71930", "#E3D4AD"), "AZ": ("#A71930", "#E3D4AD"), "ATL": ("#CE1141", "#13274F"), "BAL": ("#DF4601", "#27251F"),
 "BOS": ("#BD3039", "#0C2340"), "CHC": ("#0E3386", "#CC3433"), "CWS": ("#27251F", "#C4CED4"), "CIN": ("#C6011F", "#27251F"),
 "CLE": ("#00385D", "#E50022"), "COL": ("#27251F", "#C4CED4"), "DET": ("#0C2340", "#FA4616"), "HOU": ("#002D62", "#EB6E1F"),
 "KC": ("#004687", "#BD9B60"), "LAA": ("#BA0021", "#003263"), "LAD": ("#005A9C", "#EF3E42"), "MIA": ("#00A3E0", "#EF3340"),
 "MIL": ("#12284B", "#FFC52F"), "MIN": ("#002B5C", "#D31145"), "NYM": ("#002D72", "#FF5910"), "NYY": ("#0C2340", "#C4CED3"),
 "ATH": ("#003831", "#EFB21E"), "OAK": ("#003831", "#EFB21E"), "PHI": ("#E81828", "#002D72"), "PIT": ("#27251F", "#FDB827"),
 "SD": ("#2F241D", "#FFC425"), "SF": ("#FD5A1E", "#27251F"), "SEA": ("#0C2C56", "#005C5C"), "STL": ("#C41E3A", "#0C2340"),
 "TB": ("#092C5C", "#8FBCE6"), "TEX": ("#003278", "#C0111F"), "TOR": ("#134A8E", "#1D2D5C"), "WSH": ("#AB0003", "#14225A"),
}
# MLBTR's signing lines name the club by nickname; the chip shows the new club once a player signs
NICK = {"Angels": "LAA", "Astros": "HOU", "Athletics": "ATH", "A's": "ATH", "Blue Jays": "TOR", "Braves": "ATL", "Brewers": "MIL",
        "Cardinals": "STL", "Cubs": "CHC", "Diamondbacks": "AZ", "D-backs": "AZ", "Dodgers": "LAD", "Giants": "SF", "Guardians": "CLE",
        "Mariners": "SEA", "Marlins": "MIA", "Mets": "NYM", "Nationals": "WSH", "Orioles": "BAL", "Padres": "SD", "Phillies": "PHI",
        "Pirates": "PIT", "Rangers": "TEX", "Rays": "TB", "Red Sox": "BOS", "Reds": "CIN", "Rockies": "COL", "Royals": "KC",
        "Tigers": "DET", "Twins": "MIN", "White Sox": "CWS", "Yankees": "NYY"}
assert set(NICK) == set(mk.MLB_CLUBS)

SEQ = sorted(glob.glob(str(REPO / 'data/seq/seq_2026_*.parquet')))
PEOPLE = REPO / 'data/people/people.parquet'
FULL = bool(SEQ) and PEOPLE.exists()
PREV = json.loads((OUT / 'data.json').read_text()) if (OUT / 'data.json').exists() else None
if not FULL and PREV is None:
    sys.exit("needs the league files (data/seq, data/people), or a previous data.json to refresh")
heads = {}
if FULL:
    people = pd.read_parquet(PEOPLE)
    bref2mlbam = dict(zip(people.key_bbref, people.key_mlbam))
    mlbam2name = dict(zip(people.key_mlbam, people.name))
    seq = pd.concat([pd.read_parquet(p, columns=['game_pk', 'game_date', 'game_type', 'home_team', 'away_team', 'inning_topbot', 'batter', 'pitcher', 'fielder_2'])
                     for p in SEQ])
    seq = seq[seq.game_type == 'R']
    bat_team = np.where(seq.inning_topbot == 'Bot', seq.home_team, seq.away_team)
    pit_team = np.where(seq.inning_topbot == 'Bot', seq.away_team, seq.home_team)
    team_of = {}
    for who, tm in ((seq.batter, bat_team), (seq.pitcher, pit_team), (seq.fielder_2, pit_team)):
        df = pd.DataFrame({'id': who.values, 'team': tm, 'date': seq.game_date.values}).dropna().sort_values('date')
        for i, t in df.groupby('id').team.last().items():
            team_of.setdefault(int(i), t)
else:
    # Refresh without the league files: keep the previous build's player ids, 2026 clubs, headshots and swing-lab
    # figures (they need data/seq and the pose files), and re-derive everything that comes from market/ and
    # reports/outputs/ (calls, signing lines, new clubs, WAR, scores, framing, bat-tracking numbers).
    _raw = {p['rank']: p for p in mk.load(2026)['players']}
    bref2mlbam = {_raw[b['rank']].get('bref_id'): b['mlbam'] for b in PREV['board'] if b.get('mlbam')}
    mlbam2name = {c['id']: c['name'] for c in PREV['framing']['catchers']}
    team_of = {c['id']: c['team'] for c in PREV['framing']['catchers']} | {b['mlbam']: b['team'] for b in PREV['board'] if b.get('mlbam')}
    for x in PREV['board'] + PREV['framing']['catchers'] + list(PREV['labs'].values()):
        if x.get('head'):
            heads[x.get('mlbam') or x.get('id')] = x['head']

def headshot(mid):
    if mid in heads or not FULL: return heads.get(mid)
    url = f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_120,q_auto:best/v1/people/{mid}/headshot/67/current"
    try:
        b = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=30).read()
        heads[mid] = 'data:image/png;base64,' + base64.b64encode(b).decode() if b[:4] == b'\x89PNG' else 'data:image/jpeg;base64,' + base64.b64encode(b).decode()
    except Exception:
        heads[mid] = None
    return heads[mid]

# ---------------- market board
calls = json.loads((REPO / 'market/calls_2026-27.json').read_text())
cur = mk.frame(mk.load(2026)).set_index('rank')
raw = {p['rank']: p for p in mk.load(2026)['players']}
board = []
for c in calls['calls']:
    r = cur.loc[c['rank']]; p = raw[c['rank']]
    mid = bref2mlbam.get(p.get('bref_id'))
    mid = int(mid) if mid == mid and mid is not None else None
    board.append(dict(rank=c['rank'], name={'Adrian Morejon': 'Adrián Morejón'}.get(c['name'], c['name']), pos=p['pos'], mlbam=mid, team=team_of.get(mid) if mid else None,
        age=p.get('age'), war=p.get('war'), wwar=None if r.wwar != r.wwar else round(float(r.wwar), 3), reliever=bool(p.get('reliever')),
        mlbtr=c['mlbtr'], mlbtr_years=None if r.mlbtr_years != r.mlbtr_years else int(r.mlbtr_years), mlbtr_aav=c['mlbtr_aav'],
        my_aav=c['my_aav'], p_over=c['p_over'], call=c['call'], signed=p.get('signed') or '',
        actual_aav=None if r.actual_aav != r.actual_aav else round(float(r.actual_aav), 3),
        actual_years=None if r.actual_years != r.actual_years else int(r.actual_years), first_seen=p.get('first_seen'),
        new_team=NICK.get(mk.signed_club(p.get('signed') or '')), note=mk.SIGNING_NOTES.get(c['name'])))
for b in board:
    b['head'] = headshot(b['mlbam']) if b['mlbam'] else None

# ---------------- framing
fr = pd.read_json(REPO / 'reports/outputs/framing_catchers.json')
fs = json.loads((REPO / 'reports/outputs/framing_summary.json').read_text())
fr = fr[fr.takes >= 1500].copy()
fr['nm'] = fr.catcher.map(mlbam2name)
catchers = []
for cid, g in fr.groupby('catcher'):
    seasons = {int(r.season): dict(takes=int(r.takes), adj=round(float(r.adj_runs), 1), raw=round(float(r.raw_runs), 1),
               savant=None if r.savant_runs != r.savant_runs else round(float(r.savant_runs), 1)) for r in g.itertuples()}
    catchers.append(dict(id=int(cid), name=g.nm.iloc[0], team=team_of.get(int(cid)), seasons=seasons))
for c in catchers:
    if 2026 in c['seasons'] and (abs(c['seasons'][2026]['adj']) >= 5 or c['name'] in ('Patrick Bailey', 'Cal Raleigh', 'Tyler Stephenson', 'Carson Kelly')):
        c['head'] = headshot(c['id'])

# ---------------- swing lab
def lab(name, mlbam, stand, title):
    t = B.table(name, mlbam, stand)
    early, ne = B.trajectory(t, (2024, 2025), stand=stand)
    late, nl = B.trajectory(t, (2026,), stand=stand)
    swings = t.replace({np.nan: None}).to_dict('records')
    keep = ['play_id', 'page', 'date', 'season', 'measured', 'contact_frame', 'down_to_contact_ms', 'lift_to_contact_ms', 'hip_lead_ms',
            'head_drop', 'shoulder_tilt', 'bat_speed', 'attack_angle', 'launch_speed', 'launch_angle', 'pitch_type', 'pitch_speed', 'headline']
    swings = [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items() if k in keep} for s in swings]
    tests = {c: B.permutation(t, c) for c in B.MEASURES}
    rnd = lambda a: [[[None if not np.isfinite(v) else round(float(v), 3) for v in j] for j in f] for f in a]
    m = t[t.measured]
    nbm = {c: {str(int(s)): int(m[m.season == s][c].notna().sum()) for s in sorted(m.season.dropna().unique())} for c in B.MEASURES}
    eye_file = REPO / 'reports/outputs' / f'{name}_contact_by_eye.json'
    eye = [e['offset_frames'] for e in json.loads(eye_file.read_text())['offsets']] if eye_file.exists() else []
    return dict(name=title, mlbam=mlbam, stand=stand, head=headshot(mlbam), clips=int(len(t)), measured=int(t.measured.sum()), n_by_measure=nbm,
                eye=dict(n=len(eye), lo=min(eye) if eye else None, hi=max(eye) if eye else None),
                by_season=B.by_season(t).round(4).replace({np.nan: None}).to_dict('records'), tests=tests,
                traj=dict(early=rnd(early), late=rnd(late), n_early=ne, n_late=nl, pre=60, post=12, fps=59.94), swings=swings)

def refresh_lab(name, L, stand='R'):
    """Refresh a swing lab without the league files when clips have been removed by eye since the last full build:
    take them out of the previous build's swing table and recompute the counts, medians and tests the way lab()
    does. With the pose files (data/raw/video/pose) for every measured swing the median skeleton is recomputed too;
    without them the previous skeleton is kept."""
    from baseball.video import measure as M
    ex_file = REPO / 'reports/outputs' / f'{name}_excluded_by_eye.json'
    excluded = {e['play_id'] for e in json.loads(ex_file.read_text())['excluded']} if ex_file.exists() else set()
    newly = [s for s in L['swings'] if s['play_id'] in excluded and s.get('measured')]
    if not newly:
        return L
    for s in newly:
        s['measured'] = False
        for c in ['contact_frame'] + B.MEASURES:
            s[c] = None
    t = pd.DataFrame(L['swings'])
    for c in ['contact_frame'] + B.MEASURES + ['bat_speed', 'attack_angle', 'launch_speed']:
        t[c] = pd.to_numeric(t[c], errors='coerce')
    t['measured'] = t.measured.astype(bool)
    if all((B.RAW / 'pose' / f'{p}.npz').exists() for p in t[t.measured].play_id):
        for i in t.index[t.measured]:
            z = np.load(B.RAW / 'pose' / f'{t.at[i, "play_id"]}.npz')
            m = M.measure(z['keypoints'], float(z['fps']), stand)
            assert m and m['contact_frame'] == t.at[i, 'contact_frame'], t.at[i, 'play_id']
            for k in ('shoulders_square', 'hips_square', 'torso_px'):     # what the skeleton needs beyond the table
                t.loc[i, k] = m[k]
        early, ne = B.trajectory(t, (2024, 2025), stand=stand)
        late, nl = B.trajectory(t, (2026,), stand=stand)
        rnd = lambda a: [[[None if not np.isfinite(v) else round(float(v), 3) for v in j] for j in f] for f in a]
        L['traj'] = dict(L['traj'], early=rnd(early), late=rnd(late), n_early=ne, n_late=nl)
    else:
        print(f'{name}: no pose files here, so the median skeleton is kept from the last full build')
    m = t[t.measured]
    L['measured'] = int(t.measured.sum())
    L['n_by_measure'] = {c: {str(int(s)): int(m[m.season == s][c].notna().sum()) for s in sorted(m.season.dropna().unique())} for c in B.MEASURES}
    # a season that lost no clip keeps its row (the table is stored to four places, the full build used more)
    hit = {s.get('season') for s in newly}
    prev = {r['season']: r for r in L['by_season']}
    L['by_season'] = [prev[r['season']] if r['season'] not in hit and r['season'] in prev else r
                      for r in B.by_season(t).round(4).replace({np.nan: None}).to_dict('records')]
    L['tests'] = {c: B.permutation(t, c) for c in B.MEASURES}
    return L

if FULL:
    labs = {'arozarena': lab('arozarena', 668227, 'R', 'Randy Arozarena')}
    summary_aro = json.loads((REPO / 'reports/outputs/arozarena_swing_summary.json').read_text())
    labs['arozarena']['detectable'] = summary_aro.get('detectable_change')
    _sz = REPO / 'data/raw/video/suzuki_hr.json'
    if _sz.exists() and all((REPO / 'data/raw/video/pose' / f"{r['play_id']}.npz").exists() for r in json.loads(_sz.read_text()) if 'mp4' in r):
        labs['suzuki'] = lab('suzuki', 673548, 'R', 'Seiya Suzuki')
else:
    labs = {k: refresh_lab(k, v, v.get('stand', 'R')) for k, v in PREV['labs'].items()}
# Hitters added to the swing lab after the first two. Each is built in full whenever its pose files and the pitch files
# are here (and its swing table and summary written to reports/outputs/); otherwise it is refreshed like the others.
LATER_LABS = {'chisholm': (665862, 'L', 'Jazz Chisholm Jr.'), 'lowe': (664040, 'L', 'Brandon Lowe')}
for k, (mid, stand, title) in LATER_LABS.items():
    hr = REPO / 'data/raw/video' / f'{k}_hr.json'
    if (REPO / 'data/seq').exists() and hr.exists() and all((REPO / 'data/raw/video/pose' / f"{r['play_id']}.npz").exists()
                                                             for r in json.loads(hr.read_text()) if 'mp4' in r):
        labs[k] = lab(k, mid, stand, title)
        _t = B.table(k, mid, stand)
        labs[k]['detectable'] = B.save(k, _t)['detectable_change']
for k, v in labs.items():   # clips removed by eye after looking at the frame (counted on the method view)
    ex = REPO / 'reports/outputs' / f'{k}_excluded_by_eye.json'
    v['excluded_by_eye'] = len(json.loads(ex.read_text())['excluded']) if ex.exists() else 0

bp = json.loads((REPO / 'reports/outputs/bat_power_summary.json').read_text())
bps = pd.read_json(REPO / 'reports/outputs/bat_power_seasons.json')
def bat_row(mid):
    g = bps[bps.batter == mid].sort_values('season')
    return [dict(season=int(r.season), pa=int(r.pa), iso=round(r.iso, 3), barrel=round(r.barrel, 3), ev90=round(r.ev90, 1),
                 bat_speed=None if r.bat_speed != r.bat_speed else round(r.bat_speed, 1),
                 swing_length=None if r.swing_length != r.swing_length else round(r.swing_length, 2),
                 attack_angle=None if r.attack_angle != r.attack_angle else round(r.attack_angle, 1)) for r in g.itertuples()]
for k, v in labs.items():
    v['statcast'] = bat_row(v['mlbam'])
    pr = bp['projections'].get(str(v['mlbam']), {})
    fits = [pr[f] for f in ('train_2024_25', 'both_pairs', 'pair_2025_26') if f in pr]
    v['iso_range'] = [round(min(fits), 3), round(max(fits), 3)] if fits else None
    v['p_match'] = [round(min(pr['p_match'].values()), 2), round(max(pr['p_match'].values()), 2)] if fits else None
    v['iso_sd'] = round(pr.get('resid_sd', 0), 3)
    v['iso_2026'] = round(pr.get('iso_2026', 0), 3)

def groupless(b):  # pitchers have no batting line to rank
    return bool(__import__('re').search(r'HP$|^RHP|^LHP', b['pos'] or ''))

# Savant-style percentile rows: each called hitter's 2026 Statcast numbers ranked against the qualified hitters
# (502+ PA) in reports/outputs/bat_power_seasons.json; K% is reversed so a high percentile is always the good end.
QUAL = 502
PCT_ROWS = (('xwobacon', 'xwOBA on contact', False), ('ev90', 'EV90', False), ('barrel', 'Barrel %', False), ('iso', 'ISO', False),
            ('bat_speed', 'Bat speed', False), ('squared_up', 'Squared-up %', False), ('k_rate', 'K %', True))
lg26 = bps[(bps.season == 2026) & (bps.pa >= QUAL)]
def league_pct(mid):
    r = bps[(bps.batter == mid) & (bps.season == 2026)]
    if mid is None or r.empty or r.pa.iloc[0] < QUAL:
        return None
    rows = []
    for col, label, low in PCT_ROWS:
        v, pool = r[col].iloc[0], lg26[col].dropna()
        if v != v:
            continue
        p = ((pool < v).sum() + 0.5 * (pool == v).sum()) / len(pool)
        rows.append(dict(key=col, label=label, value=round(float(v), 4), pctl=int(min(100, max(1, round(100 * (1 - p if low else p)))))))
    return dict(season=2026, n=int(len(lg26)), min_pa=QUAL, rows=rows)
for b in board:
    b['league'] = None if b['reliever'] or groupless(b) else league_pct(b['mlbam'])

# Baseball Savant's own percentile rankings (market/savant/, pulled by baseball.ingest.savant_percentiles):
# the official ranks for every called pitcher and hitter Savant ranks, 2026 with the 2025 rank beside it.
# The hitters' computed ranks above stay only where Savant has no rank of its own (EV90).
from baseball.ingest import savant_percentiles as SP
SV_MAN = json.loads((REPO / 'market/savant/manifest.json').read_text())
for b in board:
    kind = 'pitcher' if b['reliever'] or groupless(b) else 'batter'
    c = SP.card(b['mlbam'], kind, 2026) if b['mlbam'] else None
    if c:
        prev = SP.card(b['mlbam'], kind, 2025) or {'rows': []}
        p25 = {r['label']: r['pctl'] for r in prev['rows']}
        c['rows'] = [dict(r, pctl25=p25.get(r['label'])) for r in c['rows']]
        del c['csv'], c['page']
    b['savant'] = c
    if b['league']:
        b['league']['rows'] = [r for r in b['league']['rows'] if r['key'] == 'ev90']
savant = dict(pulled=SV_MAN['percentile_rankings_pitcher_2026.csv']['pulled'],
              csv=SP.CSV_URL.format(kind='pitcher', year=2026), csv_batter=SP.CSV_URL.format(kind='batter', year=2026),
              page=SP.PAGE_URL.replace('{mlbam}', ''),
              pools={'pitcher': SP.pool_size('pitcher', 2026, 'xera'), 'batter': SP.pool_size('batter', 2026, 'xwoba')},
              page_only={k: [m[0] for m in v if m[1] is None] for k, v in SP.METRICS.items()})

robust = mk.robustness(mk.frame(mk.load(2025)))
projections = {k: v for k, v in bp['projections'].items()}
data = dict(built='2026-11-23', teams=TEAMS, board=board, backtest=calls['backtest'], robust=robust, projections=projections, model=calls['model'], made=calls['made'],
            framing=dict(summary=fs, catchers=catchers), labs=labs, savant=savant,
            bat_power=dict(n_train=bp['n_train'], n_test=bp['n_test'], best=bp['best_ball'], change=bp['bat_speed_change'], ball={k: dict(r2=round(v['r2_out'], 3), rmse=round(v['rmse_out'], 4)) for k, v in bp['ball'].items()},
                           bat_alone={k: dict(r2=round(v['r2_out'], 3), rmse=round(v['rmse_out'], 4)) for k, v in bp['bat_alone'].items()},
                           adds={k: dict(gain=round(v['gain'], 4), lo=round(v['gain_lo'], 4), hi=round(v['gain_hi'], 4),
                                                pct=round(100 * v['gain'] / v['rmse_base'], 2)) for k, v in bp['adds'].items()},
                           stability={k: round(v['r'], 3) for k, v in bp['stability'].items()}))
(OUT / 'data.json').write_text(json.dumps(data, separators=(',', ':'), default=lambda o: None if o != o else float(o)))
print('board', len(board), 'heads', sum(1 for b in board if b['head']), 'catchers', len(catchers), 'labs', list(labs), 'bytes', (OUT / 'data.json').stat().st_size)

# the page: the template wrapped in a full document (GitHub Pages serves it as is)
tpl = (REPO / "docs" / "offseason_template.html").read_text(encoding="utf-8")
(OUT / "index.html").write_text("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
    + tpl.replace("\n<style>", "\n<style>\n:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}", 1)
      .replace("<header class=\"mast\">", "</head>\n<body>\n<header class=\"mast\">", 1)
    + "\n</body>\n</html>\n", encoding="utf-8")
print("wrote", OUT / "index.html")
