"""Cache Basketball Reference award pages (COY + Clutch voting) and season coach tables.

Polite: 4s between requests, stops on 429. Raw pages are gzip-cached so reruns are offline.
"""
from pathlib import Path
import gzip, sys, time
import requests

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'data/coy/raw'
RAW.mkdir(parents=True, exist_ok=True)
URLS = {'coy_winners': 'https://www.basketball-reference.com/awards/coy.html'}
for year in range(2001, 2027):
    URLS[f'awards_{year}'] = f'https://www.basketball-reference.com/awards/awards_{year}.html'
for year in range(2001, 2028):
    URLS[f'coaches_{year}'] = f'https://www.basketball-reference.com/leagues/NBA_{year}_coaches.html'

session = requests.Session()
session.headers['User-Agent'] = 'nba-award-models research script'
for name, url in URLS.items():
    path = RAW / f'{name}.html.gz'
    if path.exists():
        continue
    response = session.get(url, timeout=30)
    if response.status_code == 429:
        print('Rate limited; retry later. Retry-After:', response.headers.get('Retry-After'), file=sys.stderr)
        sys.exit(1)
    response.raise_for_status()
    path.write_bytes(gzip.compress(response.content))
    print('cached', name, flush=True)
    time.sleep(4)
print('done')
