"""Offline, prior-season-only reputation ablation; never writes active models."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
import pandas as pd
from scipy.special import softmax
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from revised_award_core import load_namespace,features_for,fit
OUT=Path(__file__).resolve().parent
votes=pd.read_csv(ROOT/'data/award_voting/historical_award_shares.csv')
votes=votes[(votes.award=='nba dpoy') & (votes.pts_won>0)].copy()
teams=pd.read_csv(OUT/'end_of_season_teams.csv')
teams=teams[(teams.lg=='NBA') & (teams.type=='All-Defense')].copy()
assert set(votes.season)==set(range(1983,2026))
assert set(teams.season)==set(range(1969,2026))
assert not votes.duplicated(['season','player_id']).any()
assert not teams.duplicated(['season','player_id']).any()
ns=load_namespace('DPOY');columns=[c for c in features_for('DPOY') if c not in ('prior_dpoy_votes','prior_all_defense')];base=ns['make_groups'](columns)
settings=json.loads((ROOT/'revised_awards/models.json').read_text())['DPOY']
assert columns+['prior_dpoy_votes','prior_all_defense']==settings['features']
variants={'baseline':[], 'prior_dpoy_votes':['prior_dpoy_votes'], 'prior_all_defense':['prior_all_defense'], 'both_prior':['prior_dpoy_votes','prior_all_defense'], 'recent_dpoy_share':['recent_dpoy_share'], 'recent_all_defense':['recent_all_defense'], 'both_recent':['recent_dpoy_share','recent_all_defense']}
# Two predeclared representations: ever previously recognized, or three-year
# decayed history (last season weight 1, then 1/2, then 1/4). No tuning sweep.
all_groups={k:[] for k in variants};audit=[]
for source in base:
    year=source['year'];frame=source['g'].copy()
    v=votes[votes.season<year];t=teams[teams.season<year]
    frame['prior_dpoy_votes']=frame.PlayerID.isin(v.player_id).astype(float)
    frame['prior_all_defense']=frame.PlayerID.isin(t.player_id).astype(float)
    for name,data,value in [('recent_dpoy_share',v,'share'),('recent_all_defense',t,None)]:
        recent=data[data.season>=year-3].copy()
        recent['signal']=(recent[value] if value else 1.0)*(.5**(year-1-recent.season))
        frame[name]=frame.PlayerID.map(recent.groupby('player_id').signal.sum()).fillna(0)
    for key,extra in variants.items():
        raw=frame[extra].to_numpy(float) if extra else np.empty((len(frame),0))
        scale=raw.std(axis=0);scale[scale<1e-8]=1
        x=np.column_stack([source['x'],(raw-raw.mean(axis=0))/scale])
        assert np.isfinite(x).all()
        all_groups[key].append(dict(source,g=frame,x=x))
    if year>=2001:
        for _,r in frame.iterrows():audit.append(dict(year=year,player_id=r.PlayerID,player=r['Player Name'],**{c:r[c] for c in variants['both_prior']+variants['both_recent']}))
rows=[];coefs=[]
for key,groups in all_groups.items():
    features=columns+variants[key]
    for group in groups:
        if group['year']<2001:continue
        train=[g for g in groups if g['year']<group['year']]
        assert max(g['year'] for g in train)<group['year']
        coef=fit(train,settings['half_life'],settings['regularization'],features)
        scores=np.einsum('ij,j->i',group['x'],coef);assert np.isfinite(scores).all();shares=softmax(scores);order=np.argsort(-scores,kind='stable')
        rank=min(i for i,j in enumerate(order,1) if group['y'][j]>0)
        rows.append(dict(variant=key,year=group['year'],season=group['g'].Season.iloc[0],predicted=group['g'].iloc[order[0]]['Player Name'],actual=' / '.join(group['g'].loc[group['y']>0,'Player Name']),winner_rank=rank,top1=int(rank==1),top3=int(rank<=3),log_loss=float(-np.log(shares[group['y']>0].sum()))))
        coefs.extend(dict(variant=key,year=group['year'],feature=f,coefficient=float(coef[features.index(f)])) for f in variants[key])
    print(key,flush=True)
r=pd.DataFrame(rows);r.to_csv(OUT/'backtests.csv',index=False)
pd.DataFrame(coefs).to_csv(OUT/'coefficients.csv',index=False)
pd.DataFrame(audit).to_csv(OUT/'feature_audit.csv',index=False)
summary=[]
for period,lo,hi in [('all_2001_2026',2001,2026),('earlier_2001_2015',2001,2015),('later_2016_2026',2016,2026)]:
 for key in variants:
    a=r[(r.variant==key)&r.year.between(lo,hi)]
    summary.append(dict(period=period,variant=key,seasons=len(a),top1=int(a.top1.sum()),top3=int(a.top3.sum()),log_loss=float(a.log_loss.mean())))
s=pd.DataFrame(summary);s.to_csv(OUT/'summary.csv',index=False)
old=pd.read_csv(ROOT/'revised_awards/historical_backtests.csv');old=old[old.award=='DPOY'].sort_values('year')
b=r[r.variant=='both_prior'].sort_values('year')
assert old.predicted.tolist()==b.predicted.tolist(), 'Approved reputation predictions differ from active saved backtests'
assert np.allclose(old.log_loss,b.log_loss,atol=1e-6), 'Approved reputation losses differ'
changes=r.merge(r[r.variant=='baseline'][['year','predicted','winner_rank','log_loss']],on='year',suffixes=('','_baseline'))
changes[changes.predicted!=changes.predicted_baseline].to_csv(OUT/'changed_picks.csv',index=False)
meta=dict(voting_start=1983,selection_start=1969,last_history=2025,selection_source='https://raw.githubusercontent.com/sumitrodatta/bball-reference-datasets/master/Data/End%20of%20Season%20Teams.csv',voting_source='https://raw.githubusercontent.com/sumitrodatta/bball-reference-datasets/master/Data/Player%20Award%20Shares.csv',settings=settings,variants=variants,active_reputation_variant_reproduced=True)
(OUT/'method.json').write_text(json.dumps(meta,indent=2)+'\n')
print(s.to_string(index=False))
