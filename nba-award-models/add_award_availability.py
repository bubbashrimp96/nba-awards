"""Add the below-85% availability penalty to ROY, DPOY, MIP and Sixth Man."""
from pathlib import Path
import json
import pandas as pd
from award_availability_core import load_namespace,AWARDS

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'all_awards_availability'
OUT.mkdir(exist_ok=True)
ns=load_namespace()
original=json.loads((ROOT/'models.json').read_text())
models={};tests=[];rankings=[];before=[];coefficients=[];summaries={}
for award in AWARDS:
    baseline=original[award]
    columns=ns['features'][award]
    groups=ns['groups'](award)
    for group in groups:
        if group['year']<2011:continue
        train=[g for g in groups if g['year']<group['year']]
        assert max(g['year'] for g in train)<group['year']
        fitted=ns['fit'](train,baseline['half_life'],baseline['regularization'],columns)
        assert fitted[-1]<0
        shares,order,winner_rank,loss=ns['evaluate'](group,fitted)
        result=dict(award=award,season=group['g'].Season.iloc[0],year=group['year'],
                    predicted=group['g'].iloc[order[0]]['Player Name'],
                    actual=' / '.join(group['g'].loc[group['y']>0,'Player Name']),
                    winner_rank=winner_rank,top1=int(winner_rank==1),top3=int(winner_rank<=3),log_loss=loss,
                    latest_training_year=max(g['year'] for g in train),penalty_per_game=float(fitted[-1]))
        tests.append(result)
        base_train=[dict(g,x=g['x'][:,:-1]) for g in train]
        base_group=dict(group,x=group['x'][:,:-1])
        base_fit=ns['fit'](base_train,baseline['half_life'],baseline['regularization'],baseline['features'])
        _,base_order,base_rank,base_loss=ns['evaluate'](base_group,base_fit)
        before.append(dict(award=award,season=result['season'],predicted_before=group['g'].iloc[base_order[0]]['Player Name'],
                           predicted_after=result['predicted'],winner_rank_before=base_rank,winner_rank_after=winner_rank,
                           log_loss_before=base_loss,log_loss_after=loss))
        for rank,index in enumerate(order,1):
            player=group['g'].iloc[index]
            rankings.append(dict(award=award,season=result['season'],rank=rank,player=player['Player Name'],
                                 model_share=float(shares[index]),games=float(player.G),schedule_games=float(player.schedule_games),
                                 threshold=int(player.availability_threshold),shortfall=float(player.games_below_threshold),
                                 penalty_per_game=float(fitted[-1]),availability_penalty=float(fitted[-1]*player.games_below_threshold)))
    final_fit=ns['fit'](groups,baseline['half_life'],baseline['regularization'],columns)
    models[award]=dict(baseline,variant='85pct_availability',features=columns,coefficients=final_fit.tolist(),
                       availability='Strictly negative fitted weight per raw game below ceil(85% of team regular-season games). Multi-team rows use season maximum schedule, flagged as an approximation.',
                       standardization='Within-season candidate-pool z scores except games_below_threshold, which uses raw uncentered game counts.')
    coefficients.extend(dict(award=award,feature=feature,coefficient=float(value)) for feature,value in zip(columns,final_fit))
    current=[r for r in tests if r['award']==award]
    previous=[r for r in before if r['award']==award]
    summaries[award]=dict(seasons=len(current),correct=sum(r['top1'] for r in current),top3=sum(r['top3'] for r in current),
                          mean_log_loss=sum(r['log_loss'] for r in current)/len(current),
                          baseline_correct=sum(r['winner_rank_before']==1 for r in previous),
                          baseline_top3=sum(r['winner_rank_before']<=3 for r in previous),
                          baseline_log_loss=sum(r['log_loss_before'] for r in previous)/len(previous))
    print(award,summaries[award],flush=True)
(OUT/'models.json').write_text(json.dumps(models,indent=2)+'\n')
(OUT/'summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
pd.DataFrame(tests).to_csv(OUT/'historical_backtests.csv',index=False)
pd.DataFrame(rankings).to_csv(OUT/'all_rankings.csv',index=False)
pd.DataFrame(rankings).query('rank <= 5').to_csv(OUT/'selected_top5.csv',index=False)
pd.DataFrame(before).to_csv(OUT/'before_after.csv',index=False)
pd.DataFrame(coefficients).to_csv(OUT/'coefficients.csv',index=False)
ns['d'][ns['d'].year>=1986][['Season','PlayerID','Player Name','Tm','G','schedule_games','schedule_fallback','availability_threshold','games_below_threshold']].to_csv(OUT/'availability_audit.csv',index=False)
(OUT/'REPORT.md').write_text('''# Availability penalty for every award

ROY, DPOY, MIP and Sixth Man now add max(0, ceil(0.85 * actual team season games) - G).
Each award fits its own strictly negative coefficient per raw game of shortfall.
The feature is uncentered and unstandardized, with exactly zero contribution at or
above the threshold. Other features, award-specific candidate pools, half-lives
and regularization are retained; all coefficients are refit. Existing G terms remain
where they existed; MIP gains only the new shortfall feature, not a standalone G term.

An 82-game season requires 70 appearances; 72 requires 62; 66 requires 57.
Known teams use their actual schedule. Aggregate multi-team rows use the season's
maximum team games, explicitly flagged as an approximation. Candidates remain eligible
below 85%; they receive a penalty rather than automatic exclusion. MVP retains its
current qualified PPG/WS48 model and existing availability penalty unchanged.

All 2010–11 through 2025–26 predictions train on prior seasons. Comparisons remain
retrospective, and the early years overlap original configuration development.
Results and before/after metrics are in summary.json and before_after.csv.

Run python3 add_award_availability.py then python3 build_dashboard_data.py.
''')
