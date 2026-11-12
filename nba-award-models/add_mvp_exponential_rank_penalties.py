"""Refit only MVP with exponential qualified PPG and WS/48 rank penalties."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from mvp_exponential_rank_core import load_namespace,RANK_FEATURES
from exponential_availability_core import FEATURE,GROWTH_FRACTION

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'mvp_exponential_rank_penalties';OUT.mkdir(exist_ok=True)
baseline=json.loads((ROOT/'exponential_availability/models.json').read_text())['MVP']
columns=[c.replace('_places_below_fifth','_rank_exponential') if c.endswith('_places_below_fifth') else c for c in baseline['features']]
ns=load_namespace();groups=ns['make_groups'](columns)
tests=[];rankings=[];season_coefficients=[]
for group in groups:
    if group['year']<2011:continue
    train=[g for g in groups if g['year']<group['year']]
    coefficients=ns['fit'](train,baseline['half_life'],baseline['regularization'],columns)
    assert all(coefficients[columns.index(c)]<0 for c in [FEATURE,*RANK_FEATURES])
    scores=np.einsum('ij,j->i',group['x'],coefficients);shares=ns['softmax'](scores);order=np.argsort(-scores,kind='stable')
    winner_rank=min(rank for rank,index in enumerate(order,1) if group['y'][index]>0)
    tests.append(dict(award='MVP',season=group['g'].Season.iloc[0],year=group['year'],predicted=group['g'].iloc[order[0]]['Player Name'],
                      actual=' / '.join(group['g'].loc[group['y']>0,'Player Name']),winner_rank=winner_rank,top1=int(winner_rank==1),top3=int(winner_rank<=3),
                      log_loss=float(-np.log(shares[group['y']>0].sum())),latest_training_year=max(g['year'] for g in train),
                      availability_weight=float(coefficients[columns.index(FEATURE)]),
                      ppg_rank_weight=float(coefficients[columns.index('ppg_rank_exponential')]),
                      ws48_rank_weight=float(coefficients[columns.index('ws48_rank_exponential')])))
    season_coefficients.extend(dict(season=tests[-1]['season'],feature=c,coefficient=float(value)) for c,value in zip(columns,coefficients))
    for rank,index in enumerate(order,1):
        player=group['g'].iloc[index]
        row=dict(award='MVP',season=tests[-1]['season'],rank=rank,player=player['Player Name'],model_share=float(shares[index]),
                 games=float(player.G),schedule_games=float(player.schedule_games),threshold=int(player.availability_threshold),shortfall=float(player.games_below_threshold),
                 availability_exponential=float(player[FEATURE]),availability_weight=tests[-1]['availability_weight'],
                 availability_penalty=float(coefficients[columns.index(FEATURE)]*player[FEATURE]))
        for feature,stat in RANK_FEATURES.items():
            row[stat+'_rank']=int(player[stat+'_rank']);row[stat+'_qualified_count']=int(player[stat+'_qualified_count'])
            row[feature]=float(player[feature]);row[stat+'_rank_penalty']=float(coefficients[columns.index(feature)]*player[feature])
        rankings.append(row)
coefficients=ns['fit'](groups,baseline['half_life'],baseline['regularization'],columns)
model=dict(baseline,variant='MVP_exponential_availability_and_rank_penalties',features=columns,coefficients=coefficients.tolist(),
           rank_penalties='For qualified rank R and qualified leaderboard count N, d=max(0,R-5), r=log(2)/(0.10*N); penalty=negative fitted weight * expm1(r*d)/r. Zero through fifth; marginal cost doubles each further 10% of qualified field. Unqualified players remain excluded.',
           rank_growth_fraction=GROWTH_FRACTION,
           standardization='Within-season candidate-pool z scores except exponential availability, PPG rank and WS48 rank curve terms, which are uncentered raw curve values.')
(OUT/'model.json').write_text(json.dumps(model,indent=2)+'\n')
results=pd.DataFrame(tests);results.to_csv(OUT/'historical_backtests.csv',index=False)
frame=pd.DataFrame(rankings);frame.to_csv(OUT/'all_rankings.csv',index=False);frame[frame['rank']<=5].to_csv(OUT/'selected_top5.csv',index=False)
pd.DataFrame(season_coefficients).to_csv(OUT/'season_coefficients.csv',index=False)
pd.DataFrame(dict(feature=columns,coefficient=coefficients)).to_csv(OUT/'coefficients.csv',index=False)
old=pd.read_csv(ROOT/'exponential_availability/historical_backtests.csv');old=old[old.award=='MVP']
old[['season','predicted','winner_rank','log_loss']].merge(results[['season','predicted','winner_rank','log_loss']],on='season',suffixes=('_linear_ranks','_exponential_ranks'),validate='one_to_one').to_csv(OUT/'before_after.csv',index=False)
summary=dict(seasons=len(results),correct=int(results.top1.sum()),top3=int(results.top3.sum()),mean_log_loss=float(results.log_loss.mean()),
             baseline_correct=int(old.top1.sum()),baseline_top3=int(old.top3.sum()),baseline_log_loss=float(old.log_loss.mean()))
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
(OUT/'REPORT.md').write_text('''# Exponential MVP rank penalties

The same exponential shape used for availability now applies independently to
qualified PPG and WS/48 ranks below fifth. Let d=max(0,rank-5), N be the full
qualified leaderboard size, and r=ln(2)/(0.10*N). Each penalty is a strictly
negative fitted weight times expm1(r*d)/r. It is zero in the top five; marginal
cost doubles each additional 10% of the qualified field below fifth.
The growth fraction is a fixed modeling choice, not selected using later results.

Each term uses its own qualified field size, including qualified players excluded
by other MVP screening. It is not standardized or centered. Existing MVP features,
qualification exclusions, 85% exponential availability, expectations and settings
are retained; all MVP weights are refitted on prior seasons. Other award models
are unchanged. Previously hidden places-below-fifth columns remain hidden in the app.
Qualification/rank source and rounded WS48 tie limitations remain documented.
Results remain retrospective. See summary.json and before_after.csv.

Run python3 add_mvp_exponential_rank_penalties.py, then python3 build_dashboard_data.py.
''')
print(json.dumps(summary,indent=2))
