"""Consensus preseason player projections (expected PTS/REB/AST per game) for the MIP model.

Sources (data/preseason_player_projections/sources/): ESPN fantasy projections 2008-09 to 2014-15 and the
ESPN fantasy API 2017-18 onward (frozen season projections), Razzball, Hashtag Basketball and FantasyPros,
all dated before opening night unless noted in the experiment report
(experiments/mip_expectations/all_years/REPORT.md). Where several sources cover a player-season the
expected line is their mean.

Writes expected_lines.csv (year, PlayerID, expected_*, n_sources, sources) and coverage.csv. A season is
`usable` when its forecasts cover at least half of that season's 13+ PPG players; unusable seasons carry
a neutral (constant) signal in the model. Run: python3 build_preseason_projections.py [--current 2027]
"""
from pathlib import Path
import argparse, json, re, unicodedata
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DIR = ROOT / 'data/preseason_player_projections'
MIN_COVERAGE = 0.5
ALIASES = {
    'Shai Gilgeous': 'Shai Gilgeous-Alexander', 'Michael Porter': 'Michael Porter Jr.', 'Otto Porter': 'Otto Porter Jr.',
    'Larry Nance': 'Larry Nance Jr.', 'Enes Kanter': 'Enes Freedom', 'Marvin Bagley': 'Marvin Bagley III',
    'Robert Willliams': 'Robert Williams', 'Spencer Dinwiddle': 'Spencer Dinwiddie', 'Moe Harkless': 'Maurice Harkless',
    'Danuel House': 'Danuel House Jr.', 'Derrick Jones': 'Derrick Jones Jr.', 'Tyrese Halibutron': 'Tyrese Haliburton',
    'Nicolas Claxton': 'Nic Claxton', 'Danilo Galinari': 'Danilo Gallinari', 'Herb Jones': 'Herbert Jones',
    'Jabari Smith': 'Jabari Smith Jr.', 'Ron Artest': 'Metta World Peace',
}
ALIASES.update(json.loads((DIR / 'aliases.json').read_text()))


def fix_mojibake(name):
    try:
        return name.encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name


def key(name):
    s = unicodedata.normalize('NFKD', fix_mojibake(str(name))).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'\b(jr|sr|ii|iii|iv)\b\.?', '', s)
    return re.sub(r'[^a-z]', '', s)


def identities(current):
    stats = pd.read_csv(ROOT / 'data/basketball_stats.csv', usecols=['PlayerID', 'Player Name', 'Season', 'PTS'], low_memory=False)
    stats['year'] = stats.Season.str[:4].astype(int) + 1
    frames = [stats[['year', 'PlayerID', 'Player Name', 'PTS']]]
    if current:
        from current_season import bbref_table
        now = bbref_table(current, 'per_game').reset_index()
        frames.append(pd.DataFrame(dict(year=current, PlayerID=now.PlayerID, **{'Player Name': now.name_display.str.replace('*', '', regex=False)},
                                        PTS=pd.to_numeric(now.pts_per_g, errors='coerce'))))
    people = pd.concat(frames, ignore_index=True)
    people['k'] = people['Player Name'].map(key)
    return people


def resolve(name, year, people, by_year, anywhere):
    if not isinstance(name, str):
        return None
    name = ALIASES.get(name, name)
    if name.startswith('id:'):
        return name[3:]
    k = key(name)
    here = by_year.get((year, k), [])
    if len(here) == 1:
        return here[0]
    ids = anywhere.get(k, [])
    return ids[0] if len(ids) == 1 else None


def main(current):
    people = identities(current)
    by_year = people.groupby(['year', 'k']).PlayerID.agg(lambda s: sorted(set(s))).to_dict()
    anywhere = people.drop_duplicates(['PlayerID', 'k']).groupby('k').PlayerID.agg(list).to_dict()
    rows = []
    for path in sorted((DIR / 'sources').glob('*.csv')):
        f = pd.read_csv(path)
        if 'PlayerID' not in f.columns:
            f['published_name'] = f.published_name.fillna(f.get('team'))
            f['PlayerID'] = [resolve(n, y, people, by_year, anywhere) for n, y in zip(f.published_name, f.year)]
        f['src'] = f.get('source', pd.Series(path.stem, index=f.index)).fillna(path.stem).astype(str).str.lower()
        f.loc[f.src.str.startswith('razzball'), 'src'] = 'razzball'
        if path.stem == 'razzball_2020_2023':
            f['src'] = 'razzball'
        rows.append(f[['year', 'PlayerID', 'src', 'expected_PTS', 'expected_TRB', 'expected_AST']])
    data = pd.concat(rows, ignore_index=True).dropna(subset=['PlayerID'])
    for c in ['expected_PTS', 'expected_TRB', 'expected_AST']:
        data[c] = pd.to_numeric(data[c], errors='coerce')
    data = data.dropna(subset=['expected_PTS'])
    # Known source typo: Razzball 2010-11 lists Dwyane Wade at 23 REB (clearly ~5); blank it, not guess.
    data.loc[(data.year == 2011) & data.PlayerID.eq('wadedw01') & data.expected_TRB.gt(15), 'expected_TRB'] = np.nan
    if current is None:
        data = data[data.year <= people.year.max()]
    data = data.drop_duplicates(['src', 'year', 'PlayerID'])
    lines = (data.groupby(['year', 'PlayerID'])
             .agg(expected_PTS=('expected_PTS', 'mean'), expected_TRB=('expected_TRB', 'mean'), expected_AST=('expected_AST', 'mean'),
                  n_sources=('src', 'nunique'), sources=('src', lambda x: '+'.join(sorted(set(x))))).reset_index())
    lines[['expected_PTS', 'expected_TRB', 'expected_AST']] = lines[['expected_PTS', 'expected_TRB', 'expected_AST']].round(2)
    lines.to_csv(DIR / 'expected_lines.csv', index=False)
    coverage = []
    for year in range(2001, people.year.max() + 1):
        pool = people[(people.year == year) & people.PTS.ge(13)].PlayerID.unique()
        have = set(lines[lines.year == year].PlayerID)
        covered = sum(p in have for p in pool)
        share = covered / len(pool) if len(pool) else 0.0
        coverage.append(dict(year=year, pool_13ppg=len(pool), covered=covered, coverage=round(share, 4), usable=share >= MIN_COVERAGE,
                             sources='+'.join(sorted(set(data[data.year == year].src)))))
    pd.DataFrame(coverage).to_csv(DIR / 'coverage.csv', index=False)
    print(pd.DataFrame(coverage)[lambda f: f.covered > 0].to_string(index=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--current', type=int, default=2027, help='in-progress season end year (0 to skip)')
    args = parser.parse_args()
    main(args.current or None)
