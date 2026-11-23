"""Build the voting tab snapshot from local totals and HoopsMatic reporter JSON."""
import argparse
from collections import Counter
import json
from pathlib import Path

from build_clutch import key, voting_table

ROOT = Path(__file__).resolve().parent
AWARDS = ('MVP', 'ROY', 'DPOY', 'MIP', 'SMOY', 'CPOY', 'COY')


def ballot_key(name):
    normalized = key(name)
    return {'louiswilliams': 'louwilliams'}.get(normalized, normalized)


def race_totals():
    races = {}
    for year in range(2001, 2027):
        season = f'{year - 1}-{year % 100:02}'
        raw = json.loads((ROOT / f'data/award_voting/{year}.json').read_text())
        for award in ('COY', 'CPOY'):
            if award == 'CPOY' and year < 2023:
                continue
            table = voting_table(year, {'COY': 'coy', 'CPOY': 'clutch_poy'}[award])
            if table:
                raw[award] = table
        for award in AWARDS:
            if award not in raw:
                continue
            data = raw[award]
            totals = [[row['rank'], row['player'], row['points']] for row in data['voting']]
            winner = next(name for rank, name, _ in totals if rank == 1)
            races[(season, award)] = dict(season=season, award=award, winner=winner,
                                         totals=totals, source=data['source'], ballots=[])
    return races


def build(reporter_dir):
    races = race_totals()
    for path in sorted(reporter_dir.glob('*.json')):
        reporter = json.loads(path.read_text())
        outlets = {season: job['outlet'] for job in reporter['outlet_history']
                   for season in job['seasons']}
        for ballot in reporter['ballots']:
            race = races.get((ballot['season'], ballot['award']))
            if race is None:
                continue
            picks = sorted(ballot['picks'], key=lambda pick: int(pick['slot']))
            race['ballots'].append([
                reporter['slug'], reporter['voter'], outlets.get(ballot['season'], ''),
                [pick['player'] for pick in picks], [pick['pts'] for pick in picks],
            ])
    for race in races.values():
        ballots = race['ballots']
        if not ballots:
            continue
        aggregate = Counter()
        for _, _, _, names, points in ballots:
            for name, value in zip(names, points):
                aggregate[ballot_key(name)] += value
        reported = Counter({ballot_key(name): points for _, name, points in race['totals']})
        race['points_match'] = aggregate == reported
        winner_key = ballot_key(race['winner'])
        race['winner_ranks'] = [
            next((index for index, name in enumerate(names, 1)
                  if ballot_key(name) == winner_key), 0)
            for _, _, _, names, _ in ballots
        ]
    return list(races.values())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reporter_dir', type=Path, help='Directory of reporter/<slug>.json files')
    args = parser.parse_args()
    snapshot = build(args.reporter_dir)
    (ROOT / 'output/artifacts/award-ballots.json').write_text(
        json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')) + '\n'
    )
