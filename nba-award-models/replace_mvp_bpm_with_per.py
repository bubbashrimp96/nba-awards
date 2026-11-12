"""Replace MVP BPM with PER, retaining the conference model's training settings."""
from pathlib import Path
import ast
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'mvp_per_replacement'
OUT.mkdir(exist_ok=True)
namespace = {'__file__': str(ROOT / 'improve_mvp_conference.py')}
tree = ast.parse((ROOT / 'improve_mvp_conference.py').read_text().split('grid=[];all_tests=[];')[0])
tree.body = [node for node in tree.body if not isinstance(node, ast.Expr)]
exec(compile(tree, str(ROOT / 'improve_mvp_conference.py'), 'exec'), namespace)
baseline = json.loads((ROOT / 'mvp_conference_revision/model.json').read_text())
features = ['PER' if feature == 'BPM' else feature for feature in baseline['features']]
assert 'BPM' not in features and len(features) == len(baseline['features'])
groups = namespace['make_groups'](features)
rows, rankings = [], []
for group in groups:
    if group['year'] < 2016:
        continue
    train = [g for g in groups if g['year'] < group['year']]
    assert max(g['year'] for g in train) < group['year']
    coefficients = namespace['fit'](train, baseline['half_life'], baseline['regularization'])
    result, shares, order = namespace['predict'](group, coefficients)
    result.update(variant='PER_replaces_BPM', latest_training_year=max(g['year'] for g in train))
    rows.append(result)
    for rank, index in enumerate(order, 1):
        player = group['g'].iloc[index]
        rankings.append(dict(season=result['season'], rank=rank, player=player['Player Name'],
                             model_share=float(shares[index]), actual_winner=result['actual']))
results = pd.DataFrame(rows)
results.to_csv(OUT / 'historical_backtests.csv', index=False)
ranked = pd.DataFrame(rankings)
ranked.to_csv(OUT / 'all_rankings.csv', index=False)
ranked[ranked['rank'] <= 5].to_csv(OUT / 'selected_top5.csv', index=False)
coefficients = namespace['fit'](groups, baseline['half_life'], baseline['regularization'])
model = dict(baseline, variant='PER_replaces_BPM', features=features, coefficients=coefficients.tolist(),
             selection='User-requested replacement; baseline half-life and regularization retained without retuning.')
(OUT / 'model.json').write_text(json.dumps(model, indent=2) + '\n')
pd.DataFrame({'feature': features, 'coefficient': coefficients}).to_csv(OUT / 'coefficients.csv', index=False)
old = pd.read_csv(ROOT / 'mvp_conference_revision/historical_backtests.csv')
old = old[old.variant == baseline['variant']]
comparison = old[['season', 'predicted', 'winner_rank', 'log_loss']].merge(
    results[['season', 'predicted', 'winner_rank', 'log_loss']], on='season', suffixes=('_BPM', '_PER'), validate='one_to_one')
comparison.to_csv(OUT / 'before_after.csv', index=False)
summary = dict(seasons=len(results), correct=int(results.top1.sum()), top3=int(results.top3.sum()),
               mean_log_loss=float(results.log_loss.mean()), baseline_correct=int(old.top1.sum()),
               baseline_top3=int(old.top3.sum()), baseline_mean_log_loss=float(old.log_loss.mean()))
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
(OUT / 'REPORT.md').write_text(f'''# MVP: PER replaces BPM

PER replaces BPM in the conference model. All other inputs, the 20-game candidate pool,
within-season standardization, half-life ({baseline['half_life']} seasons), and L2 regularization
({baseline['regularization']}) are unchanged. Coefficients are refitted. No new tuning uses later results.

2015–16 through 2025–26: {summary['correct']}/11 first picks correct, {summary['top3']}/11 winners
in the model top three, mean log loss {summary['mean_log_loss']:.6f}.
Previous BPM model: {summary['baseline_correct']}/11, {summary['baseline_top3']}/11,
mean log loss {summary['baseline_mean_log_loss']:.6f}.

Every historical fit trains only on prior seasons. This remains retrospective because these outcomes
were already inspected. The feature change is a user preference, not evidence of improved future accuracy.
Original conference outputs and the earlier PER-plus-BPM experiment are preserved.

Run `python3 replace_mvp_bpm_with_per.py`, then `python3 build_dashboard_data.py`.
''')
print(json.dumps(summary, indent=2))
print(comparison.to_string(index=False))
