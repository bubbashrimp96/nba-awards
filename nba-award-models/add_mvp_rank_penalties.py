"""Add qualified PPG and WS/48 places-below-fifth penalties to MVP."""
from pathlib import Path
import ast
import hashlib
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'mvp_top5_rank_penalties'
OUT.mkdir(exist_ok=True)
from mvp_rank_penalties_core import load_namespace, PENALTY_FEATURES
namespace = load_namespace()
baseline = json.loads((ROOT / 'mvp_expectations_revision/model.json').read_text())
features = baseline['features'] + ['ppg_places_below_fifth','ws48_places_below_fifth']
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
    result.update(variant='qualified_PPG_WS48_top5_penalties', latest_training_year=max(g['year'] for g in train))
    assert all(coefficients[features.index(feature)] < 0 for feature in PENALTY_FEATURES)
    result['penalty_per_game'] = float(coefficients[penalty_index])
    result['ppg_penalty_per_place'] = float(coefficients[features.index('ppg_places_below_fifth')])
    result['ws48_penalty_per_place'] = float(coefficients[features.index('ws48_places_below_fifth')])
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
                             expectation_contribution=float(coefficients[features.index('wins_above_expectation')]*group['x'][index,features.index('wins_above_expectation')]),
                             ppg_rank=int(player.ppg_rank),ws48_rank=int(player.ws48_rank),
                             ppg_places_below_fifth=int(player.ppg_places_below_fifth),
                             ws48_places_below_fifth=int(player.ws48_places_below_fifth),
                             ppg_rank_penalty=float(coefficients[features.index('ppg_places_below_fifth')]*player.ppg_places_below_fifth),
                             ws48_rank_penalty=float(coefficients[features.index('ws48_places_below_fifth')]*player.ws48_places_below_fifth)))
results = pd.DataFrame(rows)
results.to_csv(OUT / 'historical_backtests.csv', index=False)
ranked = pd.DataFrame(rankings)
ranked.to_csv(OUT / 'all_rankings.csv', index=False)
ranked[ranked['rank'] <= 5].to_csv(OUT / 'selected_top5.csv', index=False)
coefficients = namespace['fit'](groups, baseline['half_life'], baseline['regularization'], features)
model = dict(baseline, variant='qualified_PPG_WS48_top5_penalties', features=features, coefficients=coefficients.tolist(),
             selection='User-requested qualified PPG and WS/48 top-five penalties; existing model inputs and settings retained.',
             rank_penalties='Exclude players unqualified for either Basketball Reference leaderboard. Add strictly negative fitted slopes times max(0, qualified rank - 5), separately for PPG and WS/48. Raw-place inputs, uncentered and unstandardized. Cached source flags and sorting values are used where available; other seasons use documented qualification rules and local statistics, with rounded WS/48 ties sharing rank.',
             expectations='Preseason win-total market line scaled to actual team games / planned preseason schedule; actual wins minus scaled expected wins. Coefficient constrained nonnegative. Pre-2003 training seasons are neutral; aggregate-team rows use season-pool median inputs.',
             availability='Negative fitted coefficient times max(0, ceil(0.85 * team games) - games played). Raw game units; no centering or standardization. Multi-team rows use season-max schedule.',
             standardization='Within-season qualified MVP candidate-pool z scores; games_below_threshold and both places-below-fifth terms use uncentered raw counts.')
model['sources'] = dict(model['sources'], qualified_leaderboard_ranks=hashlib.sha256((ROOT / 'data/qualified_ranks/qualified_ranks.csv').read_bytes()).hexdigest())
(OUT / 'model.json').write_text(json.dumps(model, indent=2) + '\n')
pd.DataFrame({'feature': features, 'coefficient': coefficients}).to_csv(OUT / 'coefficients.csv', index=False)
old = pd.read_csv(ROOT / 'mvp_expectations_revision/historical_backtests.csv')
comparison = old[['season', 'predicted', 'winner_rank', 'log_loss']].merge(
    results[['season', 'predicted', 'winner_rank', 'log_loss']], on='season', suffixes=('_before', '_top5_penalties'), validate='one_to_one')
comparison.to_csv(OUT / 'before_after.csv', index=False)
summary = dict(seasons=len(results), correct=int(results.top1.sum()), top3=int(results.top3.sum()),
               mean_log_loss=float(results.log_loss.mean()), baseline_correct=int(old.top1.sum()),
               baseline_top3=int(old.top3.sum()), baseline_mean_log_loss=float(old.log_loss.mean()))
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
namespace['d'][['Season','PlayerID','Player Name','Tm','G','schedule_games','schedule_fallback','availability_threshold','games_below_threshold']].to_csv(OUT / 'availability_audit.csv', index=False)
namespace['d'][['Season','PlayerID','Player Name','Tm','team_wins','schedule_games','preseason_win_total','preseason_schedule_games','expected_team_wins','wins_above_expectation','expectations_available']].to_csv(OUT / 'expectations_audit.csv', index=False)
namespace['rank_audit'].to_csv(OUT / 'qualification_audit.csv',index=False)
(OUT / 'REPORT.md').write_text(f"""# MVP: qualified PPG and WS/48 top-five penalties

Players must qualify for both Basketball Reference PPG and WS/48 leaderboards.
Qualification comes from cached source non_qual flags where available. Under a source
rate limit, uncached seasons use the documented season-specific qualification rules.
PPG is reconstructed from total points divided by games; local WS/48 is rounded,
so tied rounded values share the best competition rank. Cached full-precision
sorting values are used for downloaded seasons. Aggregate player rows are used
for traded players. This distinction is recorded in every source record.
The ranks use the full qualified league, before MVP screening.

Two additional raw, uncentered inputs are max(0, PPG rank - 5) and
max(0, WS/48 rank - 5). Each has a strictly negative fitted coefficient:
zero penalty in the top five, one unit at sixth, two at seventh, etc.
The penalties are additive. Players unqualified for either leaderboard are
excluded, as requested. Other features and training settings are retained;
all coefficients are refitted on the newly qualified candidate pool.

Current: {summary['correct']}/{summary['seasons']} first picks,
{summary['top3']}/{summary['seasons']} top-three winners,
log loss {summary['mean_log_loss']:.6f}. Previous expectations model:
{summary['baseline_correct']}/{summary['seasons']},
{summary['baseline_top3']}/{summary['seasons']}, {summary['baseline_mean_log_loss']:.6f}.
Full-history PPG penalty per place: {coefficients[features.index('ppg_places_below_fifth')]:.6f}.
Full-history WS/48 penalty per place: {coefficients[features.index('ws48_places_below_fifth')]:.6f}.
Historical fits have their own slopes. Results remain retrospective.

Cached source pages, qualification flags, sorting precision and hashes:
data/qualified_ranks/. Requirement reference:
https://www.basketball-reference.com/about/rate_stat_req.html
The original NBA official award eligibility is not fully enforced; leaderboard
qualification and the separate 85% model availability penalty are distinct rules.

Run python3 fetch_qualified_ranks.py, python3 add_mvp_rank_penalties.py,
then python3 build_dashboard_data.py.
""")
print(json.dumps(summary, indent=2))
print(comparison.to_string(index=False))
