"""Build award-candidates.json: season stats for every player named in an archived award race.

The Voting > Tendencies tab uses it to measure what each voter's picks look like
(advanced metrics, scoring, position, team wins) against the rest of the panel.
"""
import json
import math
from pathlib import Path

import pandas as pd

from build_award_ballots import ballot_key

ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / 'output/artifacts'
POSITION = {'PG': 'G', 'SG': 'G', 'SF': 'F', 'PF': 'F', 'C': 'C', 'F': 'F', 'G': 'G'}
FIELDS = {'ppg': 'PTS', 'rpg': 'TRB', 'apg': 'AST', 'mpg': 'MP', 'per': 'PER', 'ws48': 'WS/48',
          'bpm': 'BPM', 'vorp': 'VORP', 'ts': 'TS%', 'usg': 'USG%', 'dbpm': 'DBPM', 'dws': 'DWS',
          'blk': 'BLK', 'stl': 'STL', 'drb': 'DRB%', 'drtg': 'DRtg', 'age': 'Age', 'g': 'G', 'gs': 'GS'}
DELTAS = ('ppg', 'per', 'mpg', 'bpm')
ALIASES = {'Patrick Mills': 'Patty Mills', 'Enes Kanter': 'Enes Freedom', 'Maurice Williams': 'Mo Williams',
           'Dennis Schroeder': 'Dennis Schröder'}


def unmangle(name):
    try:
        return name.encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        try:
            return name.encode('cp1252').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            return name


def surname(key_name):
    parts = key_name.split()
    return parts[0][:1].lower() + ballot_key(parts[-1]) if parts else ''


def number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(value) else round(value, 3)


def build():
    races = json.loads((ARTIFACTS / 'award-ballots.json').read_text())
    stats = pd.read_csv(ROOT / 'data/basketball_stats.csv')
    stats['Player Name'] = stats['Player Name'].map(unmangle)
    stats['key'] = stats['Player Name'].map(ballot_key)
    stats['short'] = stats['Player Name'].map(surname)
    wins = json.loads((ROOT / 'data/team_wins_cache.json').read_text())
    seasons = sorted(stats['Season'].unique())
    prior = {season: seasons[i - 1] if i else None for i, season in enumerate(seasons)}
    by_season, by_short, by_id = {}, {}, {}
    for season, frame in stats.groupby('Season'):
        records = frame.to_dict('records')
        by_season[season] = {row['key']: row for row in records}
        by_id[season] = {row['PlayerID']: row for row in records}
        shorts = {}
        for row in records:
            shorts.setdefault(row['short'], []).append(row)
        by_short[season] = {k: v[0] for k, v in shorts.items() if len(v) == 1}

    def find(season, name):
        row = by_season.get(season, {}).get(ballot_key(name))
        if row is None:
            row = by_season.get(season, {}).get(ballot_key(ALIASES.get(name, name)))
        if row is None:
            row = by_short.get(season, {}).get(surname(name))
        return row

    out, missing, named = {}, set(), 0
    for race in races:
        if not race['ballots'] or race['award'] == 'COY':
            continue
        season = race['season']
        names = {name for _, name, _ in race['totals']}
        names.update(pick for ballot in race['ballots'] for pick in ballot[3])
        for name in names:
            named += 1
            row = find(season, name)
            if row is None:
                missing.add((season, race['award'], name))
                continue
            entry = out.setdefault(season, {}).setdefault(ballot_key(name), {})
            if entry:
                continue
            entry['pos'] = POSITION.get(str(row['Pos']).split('-')[0])
            entry['team'] = row['Tm']
            entry.update({field: number(row[column]) for field, column in FIELDS.items()})
            entry['wins'] = wins.get(season, {}).get(row['Tm'])
            before = by_id.get(prior.get(season), {}).get(row['PlayerID'])
            for field in DELTAS:
                if before is not None and entry[field] is not None:
                    old = number(before[FIELDS[field]])
                    entry['d_' + field] = None if old is None else round(entry[field] - old, 3)
    (ARTIFACTS / 'award-candidates.json').write_text(json.dumps(out, separators=(',', ':')) + '\n')
    print(f'{sum(map(len, out.values()))} player-seasons; {len(missing)} of {named} race names unmatched')
    for item in sorted(missing)[:25]:
        print('  unmatched:', *item)


if __name__ == '__main__':
    build()
