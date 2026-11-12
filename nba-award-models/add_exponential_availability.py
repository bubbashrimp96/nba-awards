"""Refit all five awards with an exponential availability penalty; preserve linear models."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from exponential_availability_core import load_namespace,FEATURE,FORMULA,GROWTH_FRACTION

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'exponential_availability';OUT.mkdir(exist_ok=True)
previous=json.loads((ROOT/'all_awards_availability/models.json').read_text())
previous['MVP']=json.loads((ROOT/'mvp_top5_rank_penalties/model.json').read_text())
models={};tests=[];rankings=[];summaries={};before=[]
for award in ('MVP','ROY','DPOY','MIP','SMOY'):
    ns=load_namespace(award);baseline=previous[award]
    columns=[FEATURE if c=='games_below_threshold' else c for c in baseline['features']]
    index=columns.index(FEATURE);groups=ns['make_groups'](columns)
    for group in groups:
        if group['year']<2011:continue
        train=[g for g in groups if g['year']<group['year']]
        coefficients=ns['fit'](train,baseline['half_life'],baseline['regularization'],columns)
        scores=np.einsum('ij,j->i',group['x'],coefficients);shares=ns['softmax'](scores);order=np.argsort(-scores,kind='stable')
        winner_rank=min(rank for rank,i in enumerate(order,1) if group['y'][i]>0)
        tests.append(dict(award=award,season=group['g'].Season.iloc[0],year=group['year'],
                          predicted=group['g'].iloc[order[0]]['Player Name'],actual=' / '.join(group['g'].loc[group['y']>0,'Player Name']),
                          winner_rank=winner_rank,top1=int(winner_rank==1),top3=int(winner_rank<=3),
                          log_loss=float(-np.log(shares[group['y']>0].sum())),
                          latest_training_year=max(g['year'] for g in train),availability_weight=float(coefficients[index])))
        if award=='MVP':
            for stat in ('ppg','ws48'):
                tests[-1][stat+'_penalty_per_place']=float(coefficients[columns.index(stat+'_places_below_fifth')])
        for rank,i in enumerate(order,1):
            player=group['g'].iloc[i]
            row=dict(award=award,season=group['g'].Season.iloc[0],rank=rank,player=player['Player Name'],model_share=float(shares[i]),
                     games=float(player.G),schedule_games=float(player.schedule_games),threshold=int(player.availability_threshold),
                     shortfall=float(player.games_below_threshold),availability_exponential=float(player[FEATURE]),
                     availability_weight=float(coefficients[index]),availability_penalty=float(coefficients[index]*player[FEATURE]))
            if award=='MVP':
                for stat in ('ppg','ws48'):
                    row[stat+'_rank']=int(player[stat+'_rank'])
                    row[stat+'_places_below_fifth']=int(player[stat+'_places_below_fifth'])
                    row[stat+'_rank_penalty']=float(coefficients[columns.index(stat+'_places_below_fifth')]*player[stat+'_places_below_fifth'])
            rankings.append(row)
    fitted=ns['fit'](groups,baseline['half_life'],baseline['regularization'],columns)
    models[award]=dict(baseline,variant=baseline['variant']+'_exponential_availability',features=columns,coefficients=fitted.tolist(),
                       availability='Strictly negative fitted weight times '+FORMULA+'. shortfall=max(0, ceil(0.85*team_games)-G). Zero above threshold; marginal cost doubles each extra 10% season shortfall.',
                       availability_growth_fraction=GROWTH_FRACTION,
                       standardization='Within-season candidate-pool z scores, except exponential availability and MVP places-below-fifth inputs, which are uncentered raw terms.')
    path=ROOT/('mvp_top5_rank_penalties' if award=='MVP' else 'all_awards_availability')/'historical_backtests.csv'
    old=pd.read_csv(path)
    if 'award' in old:old=old[old.award==award]
    current=pd.DataFrame([r for r in tests if r['award']==award])
    comparison=old[['season','predicted','winner_rank','log_loss']].merge(current[['season','predicted','winner_rank','log_loss']],on='season',suffixes=('_linear','_exponential'),validate='one_to_one')
    comparison.insert(0,'award',award);before.append(comparison)
    summaries[award]=dict(seasons=len(current),correct=int(current.top1.sum()),top3=int(current.top3.sum()),mean_log_loss=float(current.log_loss.mean()),
                          baseline_correct=int(old.top1.sum()),baseline_top3=int(old.top3.sum()),baseline_log_loss=float(old.log_loss.mean()))
    print(award,summaries[award],flush=True)
(OUT/'models.json').write_text(json.dumps(models,indent=2)+'\n')
(OUT/'summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
pd.DataFrame(tests).to_csv(OUT/'historical_backtests.csv',index=False)
frame=pd.DataFrame(rankings);frame.to_csv(OUT/'all_rankings.csv',index=False)
frame[frame['rank']<=5].to_csv(OUT/'selected_top5.csv',index=False)
pd.concat(before).to_csv(OUT/'before_after.csv',index=False)
(OUT/'REPORT.md').write_text('''# Exponential availability for all five awards

The availability shortfall remains max(0, ceil(0.85 * actual team games) - G).
The new uncentered feature is expm1(rate * shortfall) / rate,
where rate = log(2) / (0.10 * actual team games). At threshold it is zero;
its marginal cost doubles for each additional 10% of the season missed.
Its initial slope is one game-equivalent unit per shortfall game, and curvature
is a fixed modeling choice, not selected using Embiid or later results.
Each award learns a strictly negative coefficient using only prior seasons.
Other weights are refit; candidate pools, hyperparameters, G terms, MVP
qualifications, expectations and linear rank penalties remain as before.

The exponential replaces the linear availability term rather than stacking
both penalties. Players are not newly excluded below 50%; sufficiently large
shortfalls incur increasingly large deductions. Multi-team schedule fallbacks
remain flagged. Earlier linear versions are preserved for comparison.

Results remain retrospective; the early display years overlap the original
configuration-selection period. See summary.json and before_after.csv.
Run python3 add_exponential_availability.py then python3 build_dashboard_data.py.
''')
