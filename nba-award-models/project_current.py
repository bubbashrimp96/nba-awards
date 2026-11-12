"""Project the in-progress season's top five for every award and embed them in the dashboard.

Run after fetch_current.py:  python3 project_current.py [--year 2027]
Uses each award's final fitted coefficients (trained on every completed season); nothing is refitted.
Must run in its own process: current_season.install() patches file reads before models load.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, json, re, sys
import numpy as np

ROOT = Path(__file__).resolve().parent
PAGE = ROOT / 'output/artifacts/nba-award-models-browser.html'
OUTPUT = ROOT / 'output/artifacts/projections.json'
TOP = 5


DISPLAY_SWAP = {'availability_exponential': 'games_below_threshold', 'ppg_rank_exponential': 'ppg_rank', 'ws48_rank_exponential': 'ws48_rank',
                'league_standing': 'league_rank', 'conference_standing': 'conference_rank'}
CLUTCH_COLUMNS = ['clutch_record', 'gp', 'clutch_pts', 'clutch_fg_pct', 'clutch_plus_minus', 'clutch_win_pct', 'team_wins']
COACH_COLUMNS = ['record_to_date', 'team_wins', 'team_net_rating', 'expected_team_wins', 'wins_above_expectation', 'conference_seed', 'top4_seed', 'prior_coy_same_team']


def display_columns(features):
    """Every model input, shown in readable units (as on the Model vs Actual player tables)."""
    columns = ['games_to_date']
    for feature in features:
        shown = DISPLAY_SWAP.get(feature, feature)
        for item in {'allstar_jump_fit': ['quality', shown], 'origin_fit': ['quality_prior', shown]}.get(feature, [shown]):
            if item not in columns:
                columns.append(item)
        if feature == 'team_wins' and 'wins_above_expectation' in features and 'expected_team_wins' not in features:
            columns.append('expected_team_wins')
    front = ['games_to_date', 'G', 'team_wins', 'expected_team_wins', 'wins_above_expectation', 'team_defensive_rank', 'conference_seed', 'league_rank', 'conference_rank']
    back = ['games_below_threshold', 'ppg_rank', 'ws48_rank']
    return [c for c in front if c in columns] + [c for c in columns if c not in front + back] + [c for c in back if c in columns]


def number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if np.isfinite(value) else None


def top_rows(frame, scores, columns, name_column='Player Name', extra=None):
    from scipy.special import softmax
    shares = softmax(scores)
    order = np.argsort(-scores, kind='stable')[:TOP]
    rows = []
    for rank, index in enumerate(order, 1):
        row = frame.iloc[index]
        item = dict(rank=rank, player=str(row[name_column]), team=str(row.get('Tm', '')), share=float(shares[index]),
                    inputs={})
        if extra:
            item.update(extra(row))
        for c in columns:
            if c in item:
                item['inputs'][c] = item[c]
            elif c in row.index:
                item['inputs'][c] = row[c] if isinstance(row[c], str) else number(row[c])
            else:
                item['inputs'][c] = None
        rows.append(item)
    return rows, len(frame)


def player_awards(year, stats):
    played = stats.set_index('PlayerID').games_to_date
    from revised_award_core import load_namespace, features_for
    models = json.loads((ROOT / 'revised_awards/models.json').read_text())
    result = {}
    for award in ('MVP', 'ROY', 'DPOY', 'MIP', 'SMOY'):
        model = models[award]
        ns = load_namespace(award)
        columns = features_for(award)
        assert columns == model['features'], (award, columns, model['features'])
        groups = ns['make_groups'](columns)
        group = next((g for g in groups if g['year'] == year), None)
        if group is None:
            result[award] = dict(error='No eligible candidates yet (needs a 20-game projected pace)')
            continue
        scores = group['x'] @ np.array(model['coefficients'])
        frame = group['g']
        games = lambda row: dict(games_to_date=number(played.get(row['PlayerID'])))
        shown = display_columns(columns)
        rows, pool = top_rows(frame, scores, shown, extra=games)
        result[award] = dict(top=rows, pool_size=pool, features=columns, columns=shown)
    return result


def clutch(year):
    import build_clutch
    model = json.loads((ROOT / 'clutch_model/model.json').read_text())
    data = build_clutch.candidates()
    frame = data[data.year == year].sort_values('clutch_pts', ascending=False).reset_index(drop=True)
    if frame.empty:
        return dict(error='No clutch stats for this season yet — paste them from NBA.com')
    scores = build_clutch.design(frame) @ np.array(model['coefficients'])
    rows, pool = top_rows(frame, scores, CLUTCH_COLUMNS, name_column='player',
                          extra=lambda row: dict(clutch_record=f'{int(row.w)}-{int(row.l)}', games_to_date=int(row.gp)))
    meta = json.loads((ROOT / 'data/clutch/current_meta.json').read_text()) if (ROOT / 'data/clutch/current_meta.json').exists() else {}
    return dict(top=rows, pool_size=pool, features=model['features'], columns=CLUTCH_COLUMNS, data_as_of=meta.get('pasted_at', 'captured 2026-11-12 from nba.com'))


def coach(year):
    import build_coy
    model = json.loads((ROOT / 'coy_model/model.json').read_text())
    pool, _ = build_coy.build_pool()
    frame = pool[pool.year == year].reset_index(drop=True)
    scores = build_coy.design(frame) @ np.array(model['coefficients'])
    rows, size = top_rows(frame, scores, COACH_COLUMNS, name_column='coach',
                          extra=lambda row: dict(record_to_date=f'{int(row.wins)}-{int(row.losses)}'))
    return dict(top=rows, pool_size=size, features=model['features'], columns=COACH_COLUMNS)


def embed(projections):
    html = PAGE.read_text()
    blob = 'const awardProjections=' + json.dumps(projections, ensure_ascii=False, separators=(',', ':')) + ';\n'
    html = re.sub(r'const awardProjections=.*?;\n', '', html)
    html = html.replace('const guideRoot=', blob + 'const guideRoot=', 1)
    PAGE.write_text(html)


def main(year):
    import current_season
    overlay = current_season.install(year)
    teams, stats = overlay['teams'], overlay['stats']
    awards = player_awards(year, stats)
    awards['CPOY'] = clutch(year)
    awards['COY'] = coach(year)
    manifest_path = ROOT / f'data/current/{year}/raw/manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    projections = dict(
        season=current_season.season_label(year), generated_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
        team_games=dict(min=int(teams.games_to_date.min()), max=int(teams.games_to_date.max())),
        sources={name: dict(url=item['url'], fetched_at=item['fetched_at']) for name, item in manifest.items()},
        expectations_proxy=bool(overlay['expectations'].proxy.all()),
        expectations_source=str(overlay['expectations'].source.iloc[0]),
        method='Season-to-date stats projected to an 82-game pace (records, games, minutes and counting totals scaled by 82 / team games). '
               'Scored with each award’s final model fitted on all completed seasons. Shares are model shares within the candidate pool, not calibrated odds.',
        awards=awards)
    OUTPUT.write_text(json.dumps(projections, ensure_ascii=False, indent=1) + '\n')
    embed(projections)
    for award, item in awards.items():
        print(award, item.get('error') or [(r['player'], round(r['share'], 3)) for r in item['top']])
    return projections


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, default=2027)
    args = parser.parse_args()
    try:
        main(args.year)
    except Exception as error:
        import traceback; traceback.print_exc(); sys.exit(1)
