"""FantasyPros 2019-20 consensus season projections (Wayback 2019-10-14), totals / GP -> per game."""
import csv, gzip, html, re
from pathlib import Path
HERE = Path(__file__).resolve().parent
TS = '20191014102713'
URL = f'http://web.archive.org/web/{TS}/https://www.fantasypros.com/nba/projections/overall.php'
s = gzip.open(HERE.parent / f'raw_sources/fantasypros/{TS}_overall.html.gz', 'rt', encoding='utf-8', errors='replace').read()
assert 'Overall 2019 Projections' in s
num = lambda v: float(v.replace(',', ''))
rows = []
for tr in re.findall(r'<tr.*?</tr>', s, re.S):
    cells = [html.unescape(re.sub(r'<[^>]+>', ' ', c)).strip() for c in re.findall(r'<td.*?</td>', tr, re.S)]
    if len(cells) != 12: continue
    m = re.match(r'(.+?)\s*\((\w+)\s*-', re.sub(r'\s+', ' ', cells[0]))
    if not m: continue
    gp = num(cells[9])
    if gp <= 0: continue
    rows.append(dict(year=2020, season='2019-20', source='fantasypros', source_url=URL, snapshot_timestamp=TS,
                     published_name=m.group(1).strip(), team=m.group(2), expected_PTS=round(num(cells[1]) / gp, 2),
                     expected_TRB=round(num(cells[2]) / gp, 2), expected_AST=round(num(cells[3]) / gp, 2),
                     expected_MPG=round(num(cells[10]) / gp, 1), expected_G=gp))
with open(HERE / 'fantasypros.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(len(rows), [r for r in rows if 'Ingram' in r['published_name']])
