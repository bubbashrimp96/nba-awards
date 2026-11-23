"""Parse preseason projection sources (2015-16 .. 2026-27) into sourced/*.csv.

Raw inputs live in ../raw_sources/{hashtagbasketball,espn_api,razzball}. No player-ID matching here.
Run: python3 -I sourced/parse_forkC.py   (from experiments/mip_expectations)
"""
import csv, html, json, re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
RAW = BASE / 'raw_sources'
OUT = BASE / 'sourced'
COLS = ['year', 'season', 'source', 'source_url', 'snapshot_timestamp', 'published_name', 'team',
        'expected_PTS', 'expected_TRB', 'expected_AST', 'expected_MPG', 'expected_G']


def season(y):
    return f'{y-1}-{str(y)[2:]}'


def num(v):
    v = (v or '').strip().replace('%', '')
    try:
        return float(v)
    except ValueError:
        return ''


def text(c):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', c)).split())


def write(name, rows):
    with open(OUT / name, 'w', newline='') as f:
        w = csv.DictWriter(f, COLS)
        w.writeheader()
        w.writerows(rows)


# ---- Hashtag Basketball (Wayback). Only snapshots verified as preseason, full-season projections.
HB_URL = 'https://hashtagbasketball.com/fantasy-basketball-projections'
HB = {  # snapshot -> season end year
    '20161006153711': 2017, '20171003210327': 2018, '20191018020957': 2020, '20201203111140': 2021,
    '20211006155355': 2022, '20221005221236': 2023, '20231005030405': 2024, '20251009174024': 2026,
    '20260927201109': 2027,
}
rows = []
for ts, year in HB.items():
    s = (RAW / 'hashtagbasketball' / f'{ts}.html').read_text(encoding='utf-8', errors='replace')
    header = None
    for tr in re.findall(r'<tr.*?</tr>', s, flags=re.S):
        cells = re.findall(r'<t([dh])[^>]*>(.*?)</t[dh]>', tr, flags=re.S)
        vals = [text(c) for _, c in cells]
        if header is None:
            if ('PTS' in vals) and ('NAME' in vals or 'PLAYER' in vals):
                header = vals
                # 2021 layout labels the TEAM column as a second 'GP'
                if header.count('GP') == 2:
                    header[header.index('GP')] = 'TEAM'
                header = ['NAME' if h == 'PLAYER' else 'REB' if h == 'TREB' else 'G' if h in ('GP', 'GTP') else h for h in header]
            continue
        if len(vals) != len(header) or not re.fullmatch(r'\d+', vals[0]):
            continue
        r = dict(zip(header, vals))
        raw_name = cells[header.index('NAME')][1]
        m = re.search(r'>([^<>]*[A-Za-z][^<>]*)<', '>' + raw_name + '<')  # first text node = full name
        name = html.unescape(m.group(1)).strip()
        rows.append(dict(year=year, season=season(year), source='hashtagbasketball', source_url=f'http://web.archive.org/web/{ts}/{HB_URL}',
                         snapshot_timestamp=ts, published_name=name, team=r.get('TEAM', ''), expected_PTS=num(r['PTS']),
                         expected_TRB=num(r['REB']), expected_AST=num(r['AST']), expected_MPG=num(r.get('MPG')), expected_G=num(r.get('G'))))
write('hashtagbasketball.csv', rows)
print('hashtag', len(rows))

# ---- ESPN fantasy API season projections (statSourceId=1, split 0, id '10<year>').
# 2020: only partial stat ids stored (no PTS/REB) -> unusable. 2023: mid-season rest-of-season (median GP 39) -> excluded.
ESPN_YEARS = [2018, 2019, 2021, 2022, 2024, 2025, 2026, 2027]
rows = []
for year in ESPN_YEARS:
    d = json.loads((RAW / 'espn_api' / f'{year}.json').read_text())
    for p in d['players']:
        pl = p['player']
        for st in pl.get('stats', []):
            a = st.get('averageStats') or {}
            if st.get('id') != f'10{year}' or not a.get('0'):
                continue
            rows.append(dict(year=year, season=season(year), source='espn_fantasy_api',
                             source_url=f'https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/{year}/segments/0/leaguedefaults/1?view=kona_player_info',
                             snapshot_timestamp='20261123 (API pull)', published_name=pl['fullName'], team='',
                             expected_PTS=round(a['0'], 2), expected_TRB=round(a.get('6', 0), 2), expected_AST=round(a.get('3', 0), 2),
                             expected_MPG=round(a['40'], 1) if a.get('40') else '', expected_G=a.get('42', '')))
write('espn_fantasy_api.csv', rows)
print('espn', len(rows))

# ---- Razzball 2015-16 official top 200 (Slim's projections), Wayback 2015-10-20.
ts = '20151020033151'
f = RAW / 'razzball' / f'{ts}_official-razzball-2015-2016-fantasy-basketball-rankings.html'
t = f.read_text(encoding='utf-8', errors='replace')
t = re.sub(r'<script.*?</script>|<style.*?</style>', '', t, flags=re.S)
t = html.unescape(re.sub(r'<[^>]+>', '\n', t))
lines = [l.strip() for l in t.split('\n') if l.strip()]
rows = []
for i, l in enumerate(lines):
    if not l.startswith("Slim") or 'Projection' not in l:
        continue
    proj = lines[i + 1] if l.endswith(':') else l.split(':', 1)[1]
    m = re.match(r'([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)\s*:\s*(\d+)', proj.strip())
    if not m:
        continue
    # walk back to the "Name, TEAM" line that follows a numeric rank line
    for j in range(i - 1, max(0, i - 12), -1):
        if re.fullmatch(r'\d{1,3}', lines[j - 1]) and ',' in lines[j]:
            name, team = [x.strip() for x in lines[j].rsplit(',', 1)]
            break
    else:
        continue
    g = m.groups()
    rows.append(dict(year=2016, season='2015-16', source='razzball', source_url=f'http://web.archive.org/web/{ts}/http://basketball.razzball.com/official-razzball-2015-2016-fantasy-basketball-rankings',
                     snapshot_timestamp=ts, published_name=name, team=team, expected_PTS=float(g[3]), expected_TRB=float(g[4]),
                     expected_AST=float(g[5]), expected_MPG=float(g[9]), expected_G=''))
write('razzball_2015_16.csv', rows)
print('razzball 2015-16', len(rows))
