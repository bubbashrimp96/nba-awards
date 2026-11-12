"""Cache Basketball Reference qualification flags and exact sorting values for MVP inputs."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import gzip
import argparse
import numpy as np
import hashlib
import json
import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'data/qualified_ranks'
OUT.mkdir(exist_ok=True)

def fetch(task):
    year, kind = task
    url = f'https://www.basketball-reference.com/leagues/NBA_{year}_{kind}.html'
    cache = OUT / f'{year}_{kind}.html.gz'
    if not cache.exists():
        for attempt in range(4):
            response = requests.get(url, timeout=45)
            if response.status_code != 429:
                break
            delay = max(30, int(response.headers.get('Retry-After','30')) if response.headers.get('Retry-After','30').isdigit() else 30)
            if delay > 60:
                raise RuntimeError(f'Source requests a {delay}-second pause; use --offline or retry after that interval.')
            print('Rate limited; pausing', delay, 'seconds before retry.', flush=True)
            time.sleep(delay)
        response.raise_for_status()
        cache.write_bytes(gzip.compress(response.content, mtime=0))
    raw = gzip.decompress(cache.read_bytes())
    soup = BeautifulSoup(raw.decode('utf8').replace('<!--','').replace('-->',''), 'html.parser')
    stat = 'pts_per_g' if kind == 'per_game' else 'ws_per_48'
    table = soup.find('table', id='per_game_stats' if kind == 'per_game' else 'advanced') or soup.find('table', id='advanced_stats')
    assert table is not None, (year,kind)
    rows = []
    for tr in table.select('tbody tr'):
        cell = tr.find(['th','td'], attrs={'data-stat':stat})
        player = tr.select_one('a[href^="/players/"]')
        if cell is None or player is None or not cell.get_text(strip=True):
            continue
        team = tr.find(['th','td'], attrs={'data-stat':'team_name_abbr'}) or tr.find(['th','td'], attrs={'data-stat':'team_id'})
        rows.append(dict(PlayerID=re.search(r'/([^/]+)\.html',player['href'])[1], player=player.get_text(strip=True),
                         team=team.get_text(strip=True), qualified='non_qual' not in cell.get('class',[]),
                         value=float(cell.get('csk',cell.get_text(strip=True))), displayed=cell.get_text(strip=True)))
    frame = pd.DataFrame(rows)
    selected = []
    for player_id, group in frame.groupby('PlayerID',sort=False):
        if len(group)>1:
            aggregate = group[group.team.eq('TOT') | group.team.str.fullmatch(r'\d+TM')]
            assert len(aggregate)==1, (year,kind,player_id,group.team.tolist())
            selected.append(aggregate.iloc[0])
        else:
            selected.append(group.iloc[0])
    frame = pd.DataFrame(selected)
    frame['rank'] = frame.value.where(frame.qualified).rank(method='min',ascending=False)
    frame['qualified_count'] = int(frame.qualified.sum())
    frame['year'] = year
    frame['Season'] = f'{year-1}-{str(year)[-2:]}'
    frame['stat'] = 'ppg' if kind=='per_game' else 'ws48'
    frame['source'] = url
    frame['rank_method'] = 'Source qualification flags and full-precision sorting values'
    assert frame.qualified.sum()>=5
    return frame, dict(year=year, kind=kind,url=url,sha256=hashlib.sha256(raw).hexdigest())

def reconstruct(year,kind):
    """Use the documented season-specific requirements without further network requests."""
    stats = pd.read_csv(ROOT / 'data/basketball_stats.csv')
    season = f'{year-1}-{str(year)[-2:]}'
    stats = stats[stats.Season == season].copy()
    teams = pd.read_csv(ROOT / 'conference_standings/team_standings.csv')
    teams = teams[teams.Season == season]
    stats = stats.merge(teams[['Tm','team_games']],on='Tm',how='left',validate='many_to_one')
    schedule = stats.team_games.fillna(teams.team_games.max())
    if kind == 'per_game':
        if year <= 2011 or year == 2013:
            games, points = (43,854) if year == 1999 else (70,1400)
            qualified = (stats.G >= games) | (stats.PTS_T >= points)
        elif year == 2012:
            qualified = (stats.G >= 56) | (stats.PTS_T >= 1127)
        elif year in (2020,2021):
            qualified = stats.G >= np.ceil(58 * schedule / 82)
        else:
            qualified = stats.G >= 58
        value = stats.PTS_T / stats.G.replace(0,np.nan)
        displayed = stats.PTS
        stat = 'ppg'
    else:
        minimum = 915 if year==1999 else 1207 if year==2012 else 1500
        if year in (2020,2021):
            minimum = np.ceil(1500 * schedule / 82)
        qualified = stats.MP >= minimum
        value = stats['WS/48']
        displayed = stats['WS/48']
        stat = 'ws48'
    qualified = qualified & value.notna()
    frame = pd.DataFrame(dict(PlayerID=stats.PlayerID,player=stats['Player Name'],team=stats.Tm,
                              qualified=qualified,value=value,displayed=displayed))
    frame['rank'] = value.where(qualified).rank(method='min',ascending=False)
    frame['qualified_count'] = int(qualified.sum())
    frame['year'] = year
    frame['Season'] = season
    frame['stat'] = stat
    frame['source'] = 'https://www.basketball-reference.com/about/rate_stat_req.html'
    frame['rank_method'] = 'Documented qualification rules; local total points/games; rounded WS/48 ties share rank'
    return frame,dict(year=year,kind=kind,url=frame.source.iloc[0],method='Local reconstruction under source rate limit',
                       sha256=hashlib.sha256((ROOT / 'data/basketball_stats.csv').read_bytes()).hexdigest())

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--offline',action='store_true',help='Use cached pages and reconstruct uncached seasons from documented requirements.')
    args = parser.parse_args()
    results = []
    tasks = [(year,kind) for year in range(1986,2027) for kind in ('per_game','advanced')]
    for year,kind in tasks:
        missing = not (OUT / f'{year}_{kind}.html.gz').exists()
        if missing and args.offline:
            results.append(reconstruct(year,kind))
        else:
            if missing:
                time.sleep(4.2)
            results.append(fetch((year,kind)))
            if missing:
                print('Cached',year,kind,flush=True)
    data = pd.concat([frame for frame,_ in results],ignore_index=True)
    assert not data.duplicated(['year','PlayerID','stat']).any()
    data.to_csv(OUT / 'qualified_ranks.csv',index=False)
    (OUT / 'sources.json').write_text(json.dumps([source for _,source in results],indent=2)+'\n')
    print('Prepared qualified leaderboard inputs:',len(data),'player/stat/season rows.')
    print(data.groupby(['stat','rank_method']).size().to_string())
