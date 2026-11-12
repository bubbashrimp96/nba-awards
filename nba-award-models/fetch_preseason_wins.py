"""Cache preseason team win totals from Basketball Reference, available since 2002–03."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import re
import requests
from bs4 import BeautifulSoup
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'data/preseason_wins'
OUT.mkdir(exist_ok=True)

def fetch(year):
    path = OUT / f'{year}.html'
    url = f'https://www.basketball-reference.com/leagues/NBA_{year}_preseason_odds.html'
    if not path.exists():
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        path.write_bytes(response.content)
    raw = path.read_bytes()
    soup = BeautifulSoup(raw.decode('utf8').replace('<!--','').replace('-->',''), 'html.parser')
    table = soup.find('table', id='NBA_preseason_odds')
    assert table is not None, year
    rows = []
    for tr in table.select('tbody tr'):
        team = tr.select_one('[data-stat="team"] a')
        line = tr.select_one('[data-stat="wins_ou"]')
        if team is None:
            continue
        assert line and line.get_text(strip=True), (year, team.get_text())
        rows.append(dict(Season=f'{year-1}-{str(year)[-2:]}', year=year,
                         Tm=re.search(r'/teams/([^/]+)/', team['href'])[1],
                         preseason_win_total=float(line.get_text(strip=True)),
                         preseason_schedule_games=66 if year==2012 else 72 if year==2021 else 82,
                         source=url))
    assert len(rows) == (29 if year==2003 or year==2004 else 30), (year,len(rows))
    return rows, dict(year=year, url=url, sha256=hashlib.sha256(raw).hexdigest())

if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(fetch, range(2003,2027)))
    frame = pd.DataFrame([row for rows,_ in results for row in rows])
    assert not frame.duplicated(['Season','Tm']).any()
    frame.to_csv(OUT / 'team_expectations.csv', index=False)
    (OUT / 'sources.json').write_text(json.dumps([source for _,source in results], indent=2)+'\n')
    print('Cached',len(frame),'team-season preseason win totals.')
