"""Refresh cached full award voting tables. Run separately from the offline dashboard build."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import requests
import pandas as pd
from bs4 import BeautifulSoup

OUT = Path(__file__).resolve().parent / 'data/award_voting'

def historical(year):
    archive_url='https://raw.githubusercontent.com/sumitrodatta/bball-reference-datasets/master/Data/Player%20Award%20Shares.csv'
    cache=OUT/'historical_award_shares.csv'
    if not cache.exists():
        response=requests.get(archive_url,timeout=30);response.raise_for_status();cache.write_bytes(response.content)
    data=pd.read_csv(cache);result={}
    for award in ('MVP','ROY','DPOY','MIP','SMOY'):
        rows=data[(data.season==year)&(data.award=='nba '+award.lower())].copy()
        assert len(rows)>=3,(year,award)
        rows['rank']=rows.pts_won.rank(method='min',ascending=False).astype(int)
        rows=rows.sort_values(['rank','player'])
        voting=[dict(rank=int(row['rank']),player=row.player,points=float(row.pts_won),vote_share=float(row.share)) for _,row in rows.iterrows()]
        result[award]=dict(source=f'https://www.basketball-reference.com/awards/awards_{year}.html',archive=archive_url,results=[row for row in voting if row['rank']<=3],voting=voting)
    (OUT/f'{year}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return year

def fetch(year):
    if year<=2010:return historical(year)
    url = f'https://www.basketball-reference.com/awards/awards_{year}.html'
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.content.decode('utf-8').replace('<!--', '').replace('-->', ''), 'html.parser')
    data = {}
    for award in ('MVP', 'ROY', 'DPOY', 'MIP', 'SMOY'):
        table = soup.find('table', id=award.lower())
        if table is None:
            raise ValueError((year, award, 'Missing voting table'))
        rows = []
        for row in table.select('tbody tr'):
            cells = {c.get('data-stat'): c.get_text(' ', strip=True) for c in row.select('th,td')}
            if not cells.get('player'):
                continue
            rows.append(dict(rank=int(cells['rank'].rstrip('T')), player=cells['player'],
                             points=float(cells['points_won']), vote_share=float(cells['award_share'])))
        assert len(rows) >= 3, (year, award)
        data[award] = dict(source=url, results=[r for r in rows if r['rank'] <= 3], voting=rows)
    (OUT / f'{year}.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    return year

if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=3) as pool:
        for year in pool.map(fetch, [year for year in range(2001, 2027) if not (OUT / f'{year}.json').exists()]):
            print('Saved full voting results:', year)
