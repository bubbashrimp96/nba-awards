"""Add a strictly negative per-game shortfall penalty to the current PER MVP model."""
from pathlib import Path
import ast
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'mvp_per_availability'
OUT.mkdir(exist_ok=True)
namespace = {'__file__': str(ROOT / 'improve_mvp_availability.py')}
tree = ast.parse((ROOT / 'improve_mvp_availability.py').read_text().split('current=json.loads')[0])
tree.body = [node for node in tree.body if not isinstance(node, ast.Expr)]
exec(compile(tree, str(ROOT / 'improve_mvp_availability.py'), 'exec'), namespace)
baseline = json.loads((ROOT / 'mvp_per_replacement/model.json').read_text())
features = baseline['features'] + ['games_below_threshold']
assert 'BPM' not in features and 'PER' in features and len(features) == len(baseline['features']) + 1
groups = namespace['make_groups'](features)
rows, rankings = [], []
for group in groups:
    if group['year'] < 2011:
        continue
    train = [g for g in groups if g['year'] < group['year']]
    assert max(g['year'] for g in train) < group['year']
    coefficients = namespace['fit'](train, baseline['half_life'], baseline['regularization'], features)
    result, shares, order = namespace['predict'](group, coefficients)
    result.update(variant='PER_85pct_availability', latest_training_year=max(g['year'] for g in train))
    assert coefficients[-1] < 0
    result['penalty_per_game'] = float(coefficients[-1])
    rows.append(result)
    for rank, index in enumerate(order, 1):
        player = group['g'].iloc[index]
        rankings.append(dict(season=result['season'], rank=rank, player=player['Player Name'],
                             model_share=float(shares[index]), actual_winner=result['actual'],
                             schedule_games=float(player.schedule_games), threshold=int(player.availability_threshold),
                             shortfall=float(player.games_below_threshold), penalty_per_game=float(coefficients[-1]),
                             availability_penalty=float(coefficients[-1]*player.games_below_threshold)))
results = pd.DataFrame(rows)
results.to_csv(OUT / 'historical_backtests.csv', index=False)
ranked = pd.DataFrame(rankings)
ranked.to_csv(OUT / 'all_rankings.csv', index=False)
ranked[ranked['rank'] <= 5].to_csv(OUT / 'selected_top5.csv', index=False)
coefficients = namespace['fit'](groups, baseline['half_life'], baseline['regularization'], features)
model = dict(baseline, variant='PER_85pct_availability', features=features, coefficients=coefficients.tolist(),
             selection='User-requested availability penalty; existing PER features and training settings retained.',
             availability='Negative fitted coefficient times max(0, ceil(0.85 * team games) - games played). Raw game units; no centering or standardization. Multi-team rows use season-max schedule.',
             standardization='Within-season candidate-pool z scores, except games_below_threshold uses raw game units.')
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
    results[['season', 'predicted', 'winner_rank', 'log_loss']], on='season', suffixes=('_before', '_availability'), validate='one_to_one')
comparison.to_csv(OUT / 'before_after.csv', index=False)
summary = dict(seasons=len(results), correct=int(results.top1.sum()), top3=int(results.top3.sum()),
               mean_log_loss=float(results.log_loss.mean()), baseline_correct=int(old.top1.sum()),
               baseline_top3=int(old.top3.sum()), baseline_mean_log_loss=float(old.log_loss.mean()))
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
namespace['d'][['Season','PlayerID','Player Name','Tm','G','schedule_games','schedule_fallback','availability_threshold','games_below_threshold']].to_csv(OUT / 'availability_audit.csv', index=False)
(OUT / 'REPORT.md').write_text(f"""# PER MVP with an 85% availability penalty

All current PER features, including G, are retained. The new unstandardized input is
max(0, ceil(0.85 * team regular-season games) - player games played).
Its coefficient is fitted on prior seasons and constrained strictly negative.
At or above the threshold its added contribution is zero. Each further game below
threshold incurs the same negative score adjustment within that fit.

82-game schedule: threshold 70. 72-game schedule: threshold 62.
Unequal seasons use each team's actual regular-season games. Aggregate multi-team
rows use the season maximum as a flagged approximation. The 20-game screen remains.
Existing G is still fitted separately, so there can also be an overall games effect.

Current results: {summary['correct']}/{summary['seasons']} first picks, {summary['top3']}/{summary['seasons']} top-three winners,
log loss {summary['mean_log_loss']:.6f}. Prior PER model: {summary['baseline_correct']}/{summary['seasons']},
{summary['baseline_top3']}/{summary['seasons']}, log loss {summary['baseline_mean_log_loss']:.6f}.
Final full-history penalty per shortfall game: {coefficients[-1]:.6f} score units.
Historical fits have their own penalty slopes. Coefficients are refit with unchanged
half-life and regularization. Results remain retrospective. 2010–11 through 2014–15 overlaps the earlier configuration-selection development period, so those seasons are not an untouched test.

Run python3 add_mvp_availability.py, then python3 build_dashboard_data.py.
""")
print(json.dumps(summary, indent=2))
print(comparison.to_string(index=False))
