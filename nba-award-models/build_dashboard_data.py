"""Rebuild embedded historical top-three comparisons without changing model outputs."""
from pathlib import Path
import csv
import json
import re
import math
import ast

ROOT = Path(__file__).resolve().parent
# Load the original preprocessing/fitting functions without rerunning model selection.
namespace = {'__file__': str(ROOT / 'model.py')}
exec((ROOT / 'model.py').read_text().split('summary=[]; backtests=[];')[0], namespace)
models = json.loads((ROOT / 'models.json').read_text())
models.update(json.loads((ROOT / 'revised_awards/models.json').read_text()))
from revised_award_core import load_namespace, availability_curve, rank_curve, team_context, prior_all_star, player_quality, band, ALLSTAR_CENTRE, ALLSTAR_SPREAD, ORIGIN_CENTRE, ORIGIN_SPREAD
from exponential_availability_core import FEATURE
award_namespaces = {award:load_namespace(award) for award in ('MVP','ROY','DPOY','MIP','SMOY')}
stats = namespace['d'].copy()
standings = namespace['pd'].read_csv(ROOT / 'conference_standings/team_standings.csv')
stats = stats.merge(standings.drop(columns=['year']), on=['Season', 'Tm'], how='left', validate='many_to_one')
mvp_model = models['MVP']
mvp_namespace = award_namespaces['MVP']
expectations = namespace['pd'].read_csv(ROOT / 'data/preseason_wins/team_expectations.csv')
stats = stats.merge(expectations, on=['Season','year','Tm'], how='left', validate='many_to_one')
season_max = standings.groupby('Season').team_games.max()
stats['schedule_games'] = stats.team_games.fillna(stats.Season.map(season_max))
stats['schedule_fallback'] = stats.team_games.isna()
stats['availability_threshold'] = namespace['np'].ceil(0.85 * stats.schedule_games)
stats['games_below_threshold'] = namespace['np'].maximum(0, stats.availability_threshold - stats.G)
stats[FEATURE] = availability_curve(stats.games_below_threshold, stats.schedule_games)
stats['expected_team_wins'] = stats.preseason_win_total * stats.schedule_games / stats.preseason_schedule_games
stats['wins_above_expectation'] = stats.team_wins - stats.expected_team_wins
rank_columns = ['Season','PlayerID','ppg_qualified','ws48_qualified','ppg_rank','ws48_rank','ppg_places_below_fifth','ws48_places_below_fifth','ppg_qualified_count','ws48_qualified_count']
stats = stats.merge(mvp_namespace['rank_audit'][rank_columns],on=['Season','PlayerID'],how='left',validate='one_to_one')
for stat in ('ppg','ws48'):
    stats[stat+'_rank_exponential'] = rank_curve(stats[stat+'_rank'],stats[stat+'_qualified_count'],stat)
context = team_context()
stats = stats.merge(context[['Season','Tm','team_defensive_rating','team_defensive_rank','conference_seed','seed_fallback']],on=['Season','Tm'],how='left',validate='many_to_one')
stats.loc[stats.year<2003,'wins_above_expectation'] = 0.0
stats = stats.merge(prior_all_star(), on=['PlayerID','year'], how='left', validate='many_to_one')
stats['prior_all_star'] = stats.prior_all_star.fillna(0)
stats = stats.merge(player_quality(), on=['PlayerID','year'], how='left', validate='many_to_one')
stats['second_year'] = stats.experience.eq(1).astype(float)
stats['allstar_jump_fit'] = band(stats.quality, ALLSTAR_CENTRE, ALLSTAR_SPREAD)
stats['origin_fit'] = band(stats.quality_prior, ORIGIN_CENTRE, ORIGIN_SPREAD)
mvp_groups = mvp_namespace['make_groups'](mvp_model['features'])
comparisons = {}
metrics = {}
backtests = []
for award in ('MVP', 'DPOY', 'ROY', 'SMOY', 'MIP'):
    seasons = []
    award_tests = []
    if award == 'MVP':
        with (ROOT / 'revised_awards/selected_top5.csv').open() as handle:
            saved = [row for row in csv.DictReader(handle) if row['award']=='MVP']
    else:
        settings = models[award]
        award_namespace = award_namespaces[award]
        groups = award_namespace['make_groups'](settings['features'])
    for year in range(2001, 2027):
        season = f'{year-1}-{str(year)[-2:]}'
        if award == 'MVP':
            group = next(g for g in mvp_groups if g['year'] == year)
            coefficients = mvp_namespace['fit']([g for g in mvp_groups if g['year'] < year],
                                                  mvp_model['half_life'], mvp_model['regularization'], mvp_model['features'])
            _, probabilities, order = mvp_namespace['predict'](group, coefficients)
            predicted = [dict(rank=int(r['rank']), player=r['player'], share=float(r['model_share']))
                         for r in saved if r['season'] == season and int(r['rank']) <= 3]
        else:
            group = next(g for g in groups if g['year'] == year)
            coefficients = award_namespace['fit']([g for g in groups if g['year'] < year],
                                            settings['half_life'], settings['regularization'], settings['features'])
            probabilities, order, _, _ = namespace['evaluate'](group, coefficients)
            predicted = [dict(rank=i+1, player=group['g'].iloc[index]['Player Name'],
                              share=float(probabilities[index]), score=float(namespace['np'].einsum('i,i->',group['x'][index],coefficients)))
                         for i, index in enumerate(order[:3])]
        winner_share = float(probabilities[group['y'] > 0].sum())
        winner_rank = min(rank for rank, index in enumerate(order, 1) if group['y'][index] > 0)
        test = dict(award=award, season=season, latest_training_year=max(g['year'] for g in (mvp_groups if award == 'MVP' else groups) if g['year'] < year),
                    predicted=group['g'].iloc[order[0]]['Player Name'], winner_rank=winner_rank,
                    top1=int(winner_rank == 1), top3=int(winner_rank <= 3), log_loss=float(-math.log(winner_share)))
        award_tests.append(test)
        backtests.append(test)
        model_ranks = {namespace['key'](group['g'].iloc[index]['Player Name']): rank
                       for rank, index in enumerate(order, 1)}
        if award == 'MVP':
            for player in predicted:
                assert model_ranks[namespace['key'](player['player'])] == player['rank']
        actual = json.loads((ROOT / f'data/award_voting/{year}.json').read_text())[award]
        actual_ranks = {namespace['key'](p['player']): p['rank'] for p in actual['voting']}
        assert len(predicted) == 3
        columns = (mvp_model if award == 'MVP' else models[award])['features']
        pool = group['g']
        season_stats = stats[stats.year == year]
        players = {}
        for player in predicted + actual['results']:
            identity = namespace['key'](player['player'])
            if identity in players:
                continue
            matches = season_stats[season_stats.name_key == identity]
            assert len(matches) == 1, (award, season, player['player'], len(matches))
            row = matches.iloc[0]
            values, imputed = {}, []
            for column in columns:
                value = float(row[column])
                if not math.isfinite(value):
                    value = float(pool[column].median())
                    imputed.append(column)
                values[column] = value
            players[identity] = dict(player=row['Player Name'], team=row.Tm, stats=values,
                                     imputed=imputed, eligible=bool(pool.name_key.eq(identity).any()),
                                     league_rank=float(row.league_rank) if math.isfinite(float(row.league_rank)) else None,
                                     conference_rank=float(row.conference_rank) if math.isfinite(float(row.conference_rank)) else None,
                                     model_rank=model_ranks.get(identity),
                                     actual_rank=actual_ranks.get(identity),
                                     team_defensive_rating=float(row.team_defensive_rating) if math.isfinite(float(row.team_defensive_rating)) else None,
                                     seed_fallback=bool(row.seed_fallback),
                                     games_played=float(row.G),
                                     schedule_games=float(row.schedule_games),
                                     availability_threshold=int(row.availability_threshold),
                                     schedule_fallback=bool(row.schedule_fallback),
                                     preseason_win_total=float(row.preseason_win_total) if math.isfinite(float(row.preseason_win_total)) else None,
                                     expected_team_wins=float(row.expected_team_wins) if math.isfinite(float(row.expected_team_wins)) else None,
                                     ppg_rank=int(row.ppg_rank) if math.isfinite(float(row.ppg_rank)) else None,
                                     ws48_rank=int(row.ws48_rank) if math.isfinite(float(row.ws48_rank)) else None,
                                     ppg_qualified_count=int(row.ppg_qualified_count) if math.isfinite(float(row.ppg_qualified_count)) else None,
                                     ws48_qualified_count=int(row.ws48_qualified_count) if math.isfinite(float(row.ws48_qualified_count)) else None,
                                     ppg_rank_penalty=float(coefficients[mvp_model['features'].index('ppg_rank_exponential')] * row.ppg_rank_exponential) if award == 'MVP' and math.isfinite(float(row.ppg_rank)) else None,
                                     ws48_rank_penalty=float(coefficients[mvp_model['features'].index('ws48_rank_exponential')] * row.ws48_rank_exponential) if award == 'MVP' and math.isfinite(float(row.ws48_rank)) else None,
                                     availability_shortfall=float(row.games_below_threshold),
                                     availability_penalty=float(coefficients[columns.index(FEATURE)] * row[FEATURE]))
        seasons.append(dict(season=season, predicted=predicted, actual=actual['results'], source=actual['source'],
                            features=columns, players=list(players.values())))
    comparisons[award] = seasons
    metrics[award] = dict(seasons=len(seasons), correct=sum(r['top1'] for r in award_tests),
                          top3=sum(r['top3'] for r in award_tests),
                          mean_log_loss=sum(r['log_loss'] for r in award_tests) / len(award_tests))
# Clutch Player of the Year and Coach of the Year are built by their own scripts (build_clutch.py, build_coy.py).
for award, folder in (('CPOY', 'clutch_model'), ('COY', 'coy_model')):
    extra = json.loads((ROOT / folder / 'comparisons.json').read_text())
    models[award] = json.loads((ROOT / folder / 'model.json').read_text())
    comparisons[award] = extra
    tests = namespace['pd'].read_csv(ROOT / folder / 'historical_backtests.csv').to_dict('records')
    backtests.extend(tests)
    metrics[award] = dict(seasons=len(tests), correct=sum(r['top1'] for r in tests), top3=sum(r['top3'] for r in tests),
                          mean_log_loss=sum(r['log_loss'] for r in tests) / len(tests))
namespace['pd'].DataFrame(backtests).to_csv(ROOT / 'dashboard_backtests.csv', index=False)
(ROOT / 'dashboard_summary.json').write_text(json.dumps(metrics, indent=2) + '\n')
page = ROOT / 'output/artifacts/nba-award-models-browser.html'
html = page.read_text()
# Keep the displayed coefficients and summary aligned with the active MVP model.
active_models = dict(models)
active_models.pop('_metadata', None)
active_models['MVP'] = mvp_model
html = re.sub(r'const awardModels=.*?;\n', 'const awardModels=' + json.dumps(active_models, ensure_ascii=False) + ';\n', html)
# Render every overview total from the same expanded predictions as the result pages.
labels = {'MVP': 'MVP · revised penalties', 'ROY': 'ROY', 'DPOY': 'DPOY', 'MIP': 'MIP', 'SMOY': '6MOY', 'CPOY': 'Clutch POY', 'COY': 'Coach of the Year'}
rows = ''.join(f"<tr><td>{labels[award]}</td><td>{metrics[award]['correct']}/{metrics[award]['seasons']}</td><td>{metrics[award]['top3']}/{metrics[award]['seasons']}</td><td>{metrics[award]['mean_log_loss']:.3f}</td></tr>" for award in labels)
html = re.sub(r'(<table class="table"><thead>.*?</thead><tbody>).*?(</tbody>)', lambda match: match[1] + rows + match[2], html, count=1)
total_correct = sum(m['correct'] for m in metrics.values())
total_predictions = sum(m['seasons'] for m in metrics.values())
html = re.sub(r'(<label>Correct first picks</label><strong>).*?(</strong>)', lambda match: match[1] + f'{total_correct} / {total_predictions}' + match[2], html)
html = re.sub(r'(<label>Historical (?:test )?seasons</label><strong>).*?(</strong>)', lambda match: match[1] + str(metrics['MVP']['seasons']) + match[2], html)

embedded = 'const awardComparisons=' + json.dumps(comparisons, ensure_ascii=False, separators=(',', ':')) + ';\n'
html = re.sub(r'const awardComparisons=.*?;\n', '', html)
html = html.replace('const guideRoot=', embedded + 'const guideRoot=')
page.write_text(html)
print(f'Embedded {total_predictions} award/season comparisons, {total_correct} correct first picks.')
