"""Build the current 2000–01+ models with balanced penalties and team context."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
from revised_award_core import load_namespace,previous_models,features_for,team_context,AVAILABILITY_GROWTH,PPG_GROWTH,WS48_GROWTH
from exponential_availability_core import load_namespace as load_old_other,FEATURE
from mvp_exponential_rank_core import load_namespace as load_old_mvp

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'revised_awards';OUT.mkdir(exist_ok=True)
previous=previous_models();models={};tests=[];rankings=[];comparisons=[];summaries={};coefficients_by_season=[]
for award in ('MVP','ROY','DPOY','MIP','SMOY'):
    ns=load_namespace(award);baseline=previous[award];columns=features_for(award);groups=ns['make_groups'](columns)
    old_ns=load_old_mvp() if award=='MVP' else load_old_other(award);old_groups=old_ns['make_groups'](baseline['features'])
    for group in groups:
        if group['year']<2001:continue
        train=[g for g in groups if g['year']<group['year']]
        fitted=ns['fit'](train,baseline['half_life'],baseline['regularization'],columns)
        scores=np.einsum('ij,j->i',group['x'],fitted);shares=ns['softmax'](scores);order=np.argsort(-scores,kind='stable')
        winner_rank=min(rank for rank,index in enumerate(order,1) if group['y'][index]>0)
        test=dict(award=award,season=group['g'].Season.iloc[0],year=group['year'],predicted=group['g'].iloc[order[0]]['Player Name'],
                  actual=' / '.join(group['g'].loc[group['y']>0,'Player Name']),winner_rank=winner_rank,top1=int(winner_rank==1),top3=int(winner_rank<=3),
                  log_loss=float(-np.log(shares[group['y']>0].sum())),latest_training_year=max(g['year'] for g in train),
                  availability_weight=float(fitted[columns.index(FEATURE)]))
        if award=='MVP':
            for stat in ('ppg','ws48'):test[stat+'_rank_weight']=float(fitted[columns.index(stat+'_rank_exponential')])
        tests.append(test)
        coefficients_by_season.extend(dict(award=award,season=test['season'],feature=c,coefficient=float(v)) for c,v in zip(columns,fitted))
        old_group=next(g for g in old_groups if g['year']==group['year']);old_train=[g for g in old_groups if g['year']<group['year']]
        old_fit=old_ns['fit'](old_train,baseline['half_life'],baseline['regularization'],baseline['features'])
        old_scores=np.einsum('ij,j->i',old_group['x'],old_fit);old_shares=old_ns['softmax'](old_scores);old_order=np.argsort(-old_scores,kind='stable')
        old_rank=min(rank for rank,index in enumerate(old_order,1) if old_group['y'][index]>0)
        comparisons.append(dict(award=award,season=test['season'],predicted_before=old_group['g'].iloc[old_order[0]]['Player Name'],predicted_after=test['predicted'],
                                winner_rank_before=old_rank,winner_rank_after=winner_rank,log_loss_before=float(-np.log(old_shares[old_group['y']>0].sum())),log_loss_after=test['log_loss']))
        for rank,index in enumerate(order,1):
            player=group['g'].iloc[index]
            row=dict(award=award,season=test['season'],rank=rank,player=player['Player Name'],model_share=float(shares[index]),
                     games=float(player.G),schedule_games=float(player.schedule_games),threshold=int(player.availability_threshold),shortfall=float(player.games_below_threshold),
                     availability_exponential=float(player[FEATURE]),availability_weight=test['availability_weight'],availability_penalty=float(fitted[columns.index(FEATURE)]*player[FEATURE]))
            if award=='MVP':
                for stat in ('ppg','ws48'):
                    feature=stat+'_rank_exponential';row[stat+'_rank']=int(player[stat+'_rank']);row[stat+'_qualified_count']=int(player[stat+'_qualified_count'])
                    row[feature]=float(player[feature]);row[stat+'_rank_penalty']=float(fitted[columns.index(feature)]*player[feature])
            if award=='DPOY':
                row['team_defensive_rank']=float(player.team_defensive_rank);row['team_wins']=float(player.team_wins)
            if award=='SMOY':row['conference_seed']=float(player.conference_seed)
            rankings.append(row)
    final=ns['fit'](groups,baseline['half_life'],baseline['regularization'],columns)
    model=dict(baseline,variant='revised_2000_01_balanced_penalties_and_team_context',features=columns,coefficients=final.tolist(),
               availability='d=max(0,ceil(0.85*S)-G), r=ln(2)/(0.10*S); negative fitted weight * (expm1(r*d)-r*d)/r. No linear component; gentler for small deficits and exponential for large deficits.',
               availability_growth_fraction=AVAILABILITY_GROWTH,availability_curve='exponential_minus_linear',
               standardization='Within-season candidate-pool z scores except uncentered availability and MVP rank curve terms.',
               retrospective_warning='Rules revised after examining 2016–17 ROY and 2022–23 MVP. Historical fits use prior seasons, but these are retrospective comparisons; display now covers 2000–01 to 2025–26.')
    if award=='MVP':
        model['rank_penalties']='PPG marginal penalty doubles each 5% of qualified field below fifth; WS48 remains 10%. Both exponential, zero through fifth; unqualified players excluded.'
        model['ppg_rank_growth_fraction']=PPG_GROWTH;model['ws48_rank_growth_fraction']=WS48_GROWTH
    if award=='DPOY':
        model['team_context']='Player DRB removed. Add team defensive rating rank (negative fitted coefficient) and team wins (nonnegative fitted coefficient). NBA regular-season advanced ratings from 1996–97 onward; historical Basketball Reference team-rating archive for earlier training.'
        model['sources']=dict(model.get('sources',{}),team_defense=hashlib.sha256((ROOT/'data/team_defense/team_defense.csv').read_bytes()).hexdigest())
    if award=='SMOY':model['team_context']='Add reported conference seed with negative fitted coefficient; missing/zero historical seeds and the incomplete 1999–00 feed use record-based conference rank, flagged. No top-four cutoff.'
    models[award]=model
    now=[r for r in tests if r['award']==award];before=[r for r in comparisons if r['award']==award]
    summaries[award]=dict(seasons=len(now),correct=sum(r['top1'] for r in now),top3=sum(r['top3'] for r in now),mean_log_loss=sum(r['log_loss'] for r in now)/len(now),
                          baseline_correct=sum(r['winner_rank_before']==1 for r in before),baseline_top3=sum(r['winner_rank_before']<=3 for r in before),baseline_log_loss=sum(r['log_loss_before'] for r in before)/len(before))
    print(award,summaries[award],flush=True)
(OUT/'models.json').write_text(json.dumps(models,indent=2)+'\n');(OUT/'summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
pd.DataFrame(tests).to_csv(OUT/'historical_backtests.csv',index=False);pd.DataFrame(comparisons).to_csv(OUT/'before_after.csv',index=False)
frame=pd.DataFrame(rankings);frame.to_csv(OUT/'all_rankings.csv',index=False);frame[frame['rank']<=5].to_csv(OUT/'selected_top5.csv',index=False)
pd.DataFrame(coefficients_by_season).to_csv(OUT/'season_coefficients.csv',index=False)
team_context().to_csv(OUT/'team_context.csv',index=False)
(OUT/'REPORT.md').write_text('''# Current revised award models, 2000–01 through 2025–26

All five awards replace the previous availability curve with (expm1(r*d)-r*d)/r,
r=ln(2)/(0.10*team_games), d=max(0,ceil(85%*team_games)-G). Removing the linear
component softens small deficits without adding a grace period; larger deficits
remain exponential. Each award fits a strictly negative strength on prior seasons.

MVP PPG rank growth doubles over 5% of the qualified field, previously 10%.
WS48 rank growth remains 10%. Qualifications, zero penalty through fifth and
other MVP inputs remain. DPOY removes player DRB, adds team defensive-rating
rank (negative coefficient) and team wins (nonnegative coefficient). Sixth Man
adds conference seed (negative coefficient), with documented historical fallback
to record-based rank when reported seeds are missing/zero or from the incomplete
1999–00 feed. These are fitted inputs, not hard top-five/top-four eligibility cuts.

Data: NBA regular-season advanced team ratings via the sportsdataverse archive
for 1996–97 onward; Basketball Reference archive for earlier training. All 1,177
team records match cached standings. Voting covers every award from 2000–01 onward.
Preseason expectations begin in 2002–03; earlier seasons have no expectation signal.
Multi-team rows use candidate-pool medians for missing team context; schedules use
the flagged season maximum approximation. Team ratings are not player DRtg.

All historical fits use only prior seasons, with existing half-lives and L2 values.
The changes were requested after inspecting 2016–17 ROY and 2022–23 MVP, so these
are retrospective results, not fresh external validation. See summary.json and
before_after.csv for all 26 seasons, not only the cases motivating the changes.

Run python3 build_revised_awards.py then python3 build_dashboard_data.py.
''')
