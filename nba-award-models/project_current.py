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
MARKET_TOP = 10
MIP_MIN_PPG = 13.0


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
    # Every candidate's model rank and share, so market favourites outside the top five can be placed.
    full = np.argsort(-scores, kind='stable')
    ranking = [dict(rank=rank, player=str(frame.iloc[i][name_column]), team=str(frame.iloc[i].get('Tm', '')), share=float(shares[i]))
               for rank, i in enumerate(full, 1)]
    return rows, len(frame), ranking


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
        scores = np.einsum('ij,j->i', group['x'], np.array(model['coefficients']))
        frame = group['g']
        if award == 'MIP':
            eligible = frame.PTS.ge(MIP_MIN_PPG).to_numpy()
            frame, scores = frame.loc[eligible].copy(), scores[eligible]
            if frame.empty:
                result[award] = dict(error='No MIP candidates averaging at least 13 PPG yet')
                continue
        games = lambda row: dict(games_to_date=number(played.get(row['PlayerID'])))
        shown = display_columns(columns)
        rows, pool, ranking = top_rows(frame, scores, shown, extra=games)
        result[award] = dict(top=rows, pool_size=pool, features=columns, columns=shown, _ranking=ranking)
        if award == 'MIP':
            result[award]['eligibility_note'] = 'MIP eligibility: at least 13 PPG this season. Historical comparisons apply the same cutoff using the original prior-season fitted weights.'
    return result


def clutch(year):
    import build_clutch
    model = json.loads((ROOT / 'clutch_model/model.json').read_text())
    data = build_clutch.candidates()
    frame = data[data.year == year].sort_values('clutch_pts', ascending=False).reset_index(drop=True)
    if frame.empty:
        return dict(error='No clutch stats for this season yet — paste them from NBA.com')
    scores = np.einsum('ij,j->i', build_clutch.design(frame), np.array(model['coefficients']))
    rows, pool, ranking = top_rows(frame, scores, CLUTCH_COLUMNS, name_column='player',
                          extra=lambda row: dict(clutch_record=f'{int(row.w)}-{int(row.l)}', games_to_date=int(row.gp)))
    meta = json.loads((ROOT / 'data/clutch/current_meta.json').read_text()) if (ROOT / 'data/clutch/current_meta.json').exists() else {}
    return dict(top=rows, pool_size=pool, features=model['features'], columns=CLUTCH_COLUMNS, _ranking=ranking, data_as_of=meta.get('pasted_at', 'captured 2026-11-12 from nba.com'))


def coach(year):
    import build_coy
    model = json.loads((ROOT / 'coy_model/model.json').read_text())
    pool, _ = build_coy.build_pool()
    frame = pool[pool.year == year].reset_index(drop=True)
    scores = np.einsum('ij,j->i', build_coy.design(frame), np.array(model['coefficients']))
    rows, size, ranking = top_rows(frame, scores, COACH_COLUMNS, name_column='coach',
                          extra=lambda row: dict(record_to_date=f'{int(row.wins)}-{int(row.losses)}'))
    return dict(top=rows, pool_size=size, features=model['features'], columns=COACH_COLUMNS, _ranking=ranking)


def attach_odds(year, awards):
    """Merge the latest fetch_odds.py snapshot: a market price on each model row, and the market's own top five."""
    path = ROOT / f'data/current/{year}/odds.json'
    if not path.exists():
        return None
    from fetch_odds import name_key
    odds = json.loads(path.read_text())
    from reference_odds import chart_reference
    chart_path = ROOT / f'data/current/{year}/odds_movement.json'
    chart_history = json.loads(chart_path.read_text()) if chart_path.exists() else {}
    for award, item in awards.items():
        ranking = item.pop('_ranking', [])
        market = odds['awards'].get(award)
        if not market or item.get('error'):
            continue
        market.setdefault('references', {})['oddschecker'] = chart_reference(chart_history, award)
        priced = {name_key(p['name']): p for p in market['players']}
        def sources(p):
            return {k: round(v['prob'], 4) for k, v in p['sources'].items()}
        for row in item['top']:
            p = priced.get(name_key(row['player']))
            row['market'] = p['market'] if p else None
            row['market_sources'] = sources(p) if p else {}
        model = {name_key(r['player']): r for r in ranking}
        item['market_top'] = [dict(rank=i, player=model[name_key(p['name'])]['player'] if name_key(p['name']) in model else p['name'], market=p['market'], market_sources=sources(p), wide=p['wide'],
                                   model_rank=model[name_key(p['name'])]['rank'] if name_key(p['name']) in model else None,
                                   model_share=model[name_key(p['name'])]['share'] if name_key(p['name']) in model else None,
                                   team=model[name_key(p['name'])]['team'] if name_key(p['name']) in model else None)
                              for i, p in enumerate(market['players'][:MARKET_TOP], 1)]
        item['market_links'] = market['sources']
        from reference_odds import reference_rows
        item['bookmaker_quotes'] = reference_rows(market, name_key)
        item['reference_links'] = market.get('references', {})
    return dict(fetched_at=odds['fetched_at'], method=odds['method'], errors=odds.get('errors', []))


MOVEMENT_PLAYERS = 10


def attach_movement(year, awards):
    """Daily odds movement from fetch_odds_history.py, as aligned arrays per player and source.

    combined = mean of the sources pricing the player that day (each source carried forward within its own range),
    with no additional field scaling or margin adjustment. Keeps the current top players plus anyone who led.
    """
    path = ROOT / f'data/current/{year}/odds_movement.json'
    from fetch_odds import name_key
    from datetime import date, timedelta
    from bookmaker_movement import merge_bookmaker_history, merge_latest_market_snapshot, CONSENSUS_SOURCES
    data = json.loads(path.read_text()) if path.exists() else dict(awards={}, fetched_at=None, method='Saved odds snapshots', errors=[])
    data = merge_bookmaker_history(data, ROOT / f'data/current/{year}/bookmaker_odds_history.csv', ROOT / f'data/current/{year}/odds.json')
    odds_path = ROOT / f'data/current/{year}/odds.json'
    if odds_path.exists():
        data = merge_latest_market_snapshot(data, json.loads(odds_path.read_text()))
    for award, item in awards.items():
        source = data['awards'].get(award)
        if not source or item.get('error') or not source['players']:
            continue
        days = sorted({d for p in source['players'] for s in p['sources'].values() for d in s})
        if not days:
            continue
        axis, d = [], date.fromisoformat(days[0])
        while d <= date.fromisoformat(days[-1]):
            axis.append(d.isoformat()); d += timedelta(days=1)
        names = sorted({s for p in source['players'] for s in p['sources']}, key=lambda s: ['sportsbet', 'neds', 'sportsbooks', 'polymarket', 'kalshi'].index(s) if s in ['sportsbet', 'neds', 'sportsbooks', 'polymarket', 'kalshi'] else 99)
        filled = []
        for p in source['players']:
            series = {}
            for s, points in p['sources'].items():
                if not points:
                    continue
                start, end, last, out = min(points), max(points), None, []
                for day in axis:
                    last = points.get(day) if s in ('sportsbet', 'neds') or day == source.get('snapshot_date') else points.get(day, last) if start <= day <= end else None
                    out.append(last)
                series[s] = out
            # the model's spelling (Dončić, not the exchanges' Doncic) when the player is in its pool
            model_names = {name_key(r['player']): r['player'] for r in item.get('_ranking', [])}
            filled.append((model_names.get(name_key(p['name']), p['name']), series))
        combined = []
        for i in range(len(axis)):
            raw = []
            for _, series in filled:
                vals = [v[i] for s, v in series.items() if s in CONSENSUS_SOURCES and v[i] is not None]
                raw.append(sum(vals) / len(vals) if vals else None)
            combined.append(raw)
        rows = []
        for j, (name, series) in enumerate(filled):
            comb = [combined[i][j] for i in range(len(axis))]
            if source.get('snapshot_date') in axis:
                comb[axis.index(source['snapshot_date'])] = source.get('snapshot_market', {}).get(name_key(name))
            rows.append(dict(player=name, combined=comb, **{k: series.get(k) for k in names}))
        last = lambda r: next((v for v in reversed(r['combined']) if v is not None), 0)
        leaders = set()
        for i in range(len(axis)):
            j = max(range(len(rows)), key=lambda j: rows[j]['combined'][i] or 0)
            if (rows[j]['combined'][i] or 0) >= 0.05:  # a 'leader' among an all-1% opening field is noise
                leaders.add(j)
        keep = sorted(rows, key=lambda r: -last(r))[:MOVEMENT_PLAYERS]
        keep += [rows[j] for j in leaders if rows[j] not in keep]
        model_top = {name_key(r['player']) for r in item.get('top', [])}
        required = model_top | set(source.get('snapshot_top', []))
        keep += [r for r in rows if name_key(r['player']) in required and r not in keep]
        round4 = lambda xs: [round(x, 4) if x is not None else None for x in xs] if xs else None
        item['movement'] = dict(dates=axis, sources=names, links=source['links'], books=source['books'],
                                snapshot_date=source.get('snapshot_date'), players=keep)
    return dict(fetched_at=data['fetched_at'], method=data['method'], errors=data.get('errors', []))


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
    from league_projections import standings as build_standings, allstars as build_allstars
    espn = json.loads(current_season.raw(year, 'espn_standings.json').read_text())
    team_names = {current_season.ESPN_ALIASES.get(entry['team']['abbreviation'],entry['team']['abbreviation']):entry['team'].get('displayName',entry['team'].get('name','')) for conference in espn['children'] for entry in conference['standings']['entries']}
    # Combined traded-player stats remain combined; assign their last listed team stint.
    from bs4 import BeautifulSoup
    import gzip
    page=BeautifulSoup(gzip.decompress(current_season.raw(year,'per_game.html.gz').read_bytes()).decode(),'html.parser')
    current_teams={}
    for row in page.select('tbody tr'):
        player=row.select_one('[data-stat="name_display"] a');team=row.select_one('[data-stat="team_name_abbr"]')
        if player and team and team.get_text(strip=True) in set(teams.Tm):current_teams[player['href'].split('/')[-1].split('.')[0]]=team.get_text(strip=True)
    league_standings=build_standings(teams,team_names)
    team_totals=ROOT/f'data/current/{year}/team_win_totals.json'
    if team_totals.exists():league_standings['market_fetched_at']=json.loads(team_totals.read_text()).get('fetched_at')
    all_stars=build_allstars(stats,teams,team_names,current_teams)
    awards = player_awards(year, stats)
    awards['CPOY'] = clutch(year)
    awards['COY'] = coach(year)
    movement = attach_movement(year, awards)  # before attach_odds, which drops the internal rankings
    odds = attach_odds(year, awards)
    for item in awards.values():
        item.pop('_ranking', None)
    manifest_path = ROOT / f'data/current/{year}/raw/manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    projections = dict(
        season=current_season.season_label(year), generated_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
        team_games=dict(min=int(teams.games_to_date.min()), max=int(teams.games_to_date.max())),
        team_wins_sources={k: sorted(teams.Tm[teams.team_wins_source == k]) for k in teams.team_wins_source.unique()},
        sources={name: dict(url=item['url'], fetched_at=item['fetched_at']) for name, item in manifest.items()},
        expectations_proxy=bool(overlay['expectations'].proxy.all()),
        expectations_source=str(overlay['expectations'].source.iloc[0]),
        method='Player stats projected to an 82-game pace (games, minutes and counting totals scaled by 82 / team games). '
               'Projected team wins = the betting market’s expected final wins from sportsbook over/under win totals (lean priced in); '
               'league and conference positions and seeds rank teams by those wins. '
               'Scored with each award’s final model fitted on all completed seasons. Shares are model shares within the candidate pool, not calibrated odds.',
        odds=odds, movement=movement, awards=awards, conference_standings=league_standings, all_stars=all_stars)
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
