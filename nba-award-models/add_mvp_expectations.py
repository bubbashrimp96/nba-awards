"""Add preseason team overperformance to the current PER and availability MVP model."""
from pathlib import Path
import ast
import hashlib
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'mvp_expectations_revision'
OUT.mkdir(exist_ok=True)
from mvp_expectations_core import load_namespace
namespace = load_namespace()
baseline = json.loads((ROOT / 'mvp_per_availability/model.json').read_text())
features = baseline['features'] + ['wins_above_expectation']
penalty_index = features.index('games_below_threshold')
groups = namespace['make_groups'](features)
rows, rankings = [], []
for group in groups:
    if group['year'] < 2011:
        continue
    train = [g for g in groups if g['year'] < group['year']]
    assert max(g['year'] for g in train) < group['year']
    coefficients = namespace['fit'](train, baseline['half_life'], baseline['regularization'], features)
    result, shares, order = namespace['predict'](group, coefficients)
    result.update(variant='PER_availability_expectations', latest_training_year=max(g['year'] for g in train))
    assert coefficients[penalty_index] < 0
    result['penalty_per_game'] = float(coefficients[penalty_index])
    rows.append(result)
    for rank, index in enumerate(order, 1):
        player = group['g'].iloc[index]
        rankings.append(dict(season=result['season'], rank=rank, player=player['Player Name'],
                             model_share=float(shares[index]), actual_winner=result['actual'],
                             schedule_games=float(player.schedule_games), threshold=int(player.availability_threshold),
                             shortfall=float(player.games_below_threshold), penalty_per_game=float(coefficients[penalty_index]),
                             availability_penalty=float(coefficients[penalty_index]*player.games_below_threshold),
                             preseason_win_total=float(player.preseason_win_total),
                             expected_team_wins=float(player.expected_team_wins),
                             wins_above_expectation=float(player.wins_above_expectation),
                             expectation_contribution=float(coefficients[-1]*group['x'][index,-1])))
results = pd.DataFrame(rows)
results.to_csv(OUT / 'historical_backtests.csv', index=False)
ranked = pd.DataFrame(rankings)
ranked.to_csv(OUT / 'all_rankings.csv', index=False)
ranked[ranked['rank'] <= 5].to_csv(OUT / 'selected_top5.csv', index=False)
coefficients = namespace['fit'](groups, baseline['half_life'], baseline['regularization'], features)
model = dict(baseline, variant='PER_availability_expectations', features=features, coefficients=coefficients.tolist(),
             selection='User-requested team overperformance feature; existing inputs and settings retained.',
             expectations='Preseason win-total market line scaled to actual team games / planned preseason schedule; actual wins minus scaled expected wins. Coefficient constrained nonnegative. Pre-2003 training seasons are neutral; aggregate-team rows use season-pool median inputs.',
             availability='Negative fitted coefficient times max(0, ceil(0.85 * team games) - games played). Raw game units; no centering or standardization. Multi-team rows use season-max schedule.',
             standardization='Within-season candidate-pool z scores, except games_below_threshold uses raw game units.')
model['sources'] = dict(model['sources'], preseason_win_totals=hashlib.sha256((ROOT / 'data/preseason_wins/team_expectations.csv').read_bytes()).hexdigest())
(OUT / 'model.json').write_text(json.dumps(model, indent=2) + '\n')
pd.DataFrame({'feature': features, 'coefficient': coefficients}).to_csv(OUT / 'coefficients.csv', index=False)
# Compare the prior PER model on exactly the same expanded season range.
baseline_groups = namespace['make_groups'](baseline['features'])
baseline_results = []
for group in baseline_groups:
    if group['year'] < 2011:
        continue
    train = [g for g in baseline_groups if g['year'] < group['year']]
    fitted = namespace['fit'](train, baseline['half_life'], baseline['regularization'], baseline['features'])
    result, _, _ = namespace['predict'](group, fitted)
    baseline_results.append(result)
old = pd.DataFrame(baseline_results)
comparison = old[['season', 'predicted', 'winner_rank', 'log_loss']].merge(
    results[['season', 'predicted', 'winner_rank', 'log_loss']], on='season', suffixes=('_before', '_expectations'), validate='one_to_one')
comparison.to_csv(OUT / 'before_after.csv', index=False)
summary = dict(seasons=len(results), correct=int(results.top1.sum()), top3=int(results.top3.sum()),
               mean_log_loss=float(results.log_loss.mean()), baseline_correct=int(old.top1.sum()),
               baseline_top3=int(old.top3.sum()), baseline_mean_log_loss=float(old.log_loss.mean()))
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
namespace['d'][['Season','PlayerID','Player Name','Tm','G','schedule_games','schedule_fallback','availability_threshold','games_below_threshold']].to_csv(OUT / 'availability_audit.csv', index=False)
namespace['d'][['Season','PlayerID','Player Name','Tm','team_wins','schedule_games','preseason_win_total','preseason_schedule_games','expected_team_wins','wins_above_expectation','expectations_available']].to_csv(OUT / 'expectations_audit.csv', index=False)
(OUT / 'REPORT.md').write_text(f"""# MVP: performance against preseason expectations

Adds wins_above_expectation = actual team wins - expected team wins.
Expected wins use Basketball Reference preseason market over/under lines,
scaled by actual team games / preseason schedule games (82 normally, 66 in
2011–12, 72 in 2020–21). Scaling handles uneven 2019–20 schedules fairly.
The coefficient is fitted nonnegative, so greater overperformance cannot reduce
the score holding other inputs fixed. Existing PER, games and availability rules remain.
Within-season standardized contributions may be negative for below-average overperformance.

Preseason data starts in 2002–03. Earlier training seasons have a constant neutral
zero overperformance feature; expectations are never reconstructed from actual results.
Aggregate-team rows use candidate-pool season medians, matching existing imputation.
Raw source pages, URLs and hashes are in data/preseason_wins/.

Current first picks: {summary['correct']}/{summary['seasons']}; winner top three:
{summary['top3']}/{summary['seasons']}; mean log loss {summary['mean_log_loss']:.6f}.
Prior model: {summary['baseline_correct']}/{summary['seasons']},
{summary['baseline_top3']}/{summary['seasons']}, {summary['baseline_mean_log_loss']:.6f}.
Final expectation coefficient: {coefficients[-1]:.6f} per within-season z score.

2016–17 OKC: preseason 45 wins, actual 47, overperformance +2.
This feature does not guarantee a Westbrook first pick and is not tuned to do so.
All historical fits train only on prior seasons, with unchanged half-life and
regularization. All results remain retrospective; 2010–15 overlaps the earlier
configuration-selection development period.

Run python3 fetch_preseason_wins.py, python3 add_mvp_expectations.py,
then python3 build_dashboard_data.py.
""")
print(json.dumps(summary, indent=2))
print(comparison.to_string(index=False))
