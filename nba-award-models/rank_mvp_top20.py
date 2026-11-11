"""MVP ranking rule: top-20 PPG candidates; retain existing fitted scoring model.
Run python3 rank_mvp_top20.py. Original models and outputs remain untouched.
"""
from pathlib import Path
import json, re, unicodedata, hashlib
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import softmax, logsumexp

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'mvp_top20_revision';OUT.mkdir(exist_ok=True)
DATA=(Path(__file__).resolve().parent / 'data')

def clean(s):
    try:s=s.encode('latin1').decode('utf8')
    except (UnicodeError,AttributeError):pass
    return s
def key(s):
    return re.sub('[^a-z0-9]','',unicodedata.normalize('NFKD',clean(s)).encode('ascii','ignore').decode().lower())

d=pd.read_csv(DATA/'basketball_stats.csv')
assert not d.duplicated(['PlayerID','Season']).any()
d['Player Name']=d['Player Name'].map(clean)
d['year']=d.Season.str[:4].astype(int)+1
d['name_key']=d['Player Name'].map(key)
wins=json.loads((DATA/'team_wins_cache.json').read_text())
labels=pd.DataFrame(json.loads((ROOT/'award_labels.json').read_text()))
labels=labels[labels.award.eq('MVP')].copy()
labels['year']=labels.season.str[:4].astype(int)+1
labels['name_key']=labels.player.map(key)
original=json.loads((ROOT/'models.json').read_text())['MVP']
base=[c for c in original['features'] if c!='WS']
lean=[c for c in base if c!='VORP']
FEATURES={
 'conference_plus_league':lean+['team_wins','league_standing','conference_standing'],
 'conference_instead_of_league':lean+['team_wins','conference_standing'],
 'conference_with_VORP':base+['team_wins','league_standing','conference_standing'],
}
assert all('WS' not in v for v in FEATURES.values())

teams=pd.read_csv(ROOT/'conference_standings/team_standings.csv').drop(columns=['year'])
assert not teams.duplicated(['Season','Tm']).any()
d=d.merge(teams,on=['Season','Tm'],how='left',validate='many_to_one')
# Aggregate multi-team rows have no exact schedule: use that season's maximum
# team schedule as an explicitly marked fallback, without inventing a team.
season_max=teams.groupby('Season').team_games.max()
d['schedule_fallback']=d.team_games.isna()
d['schedule_games']=d.team_games.fillna(d.Season.map(season_max))
assert d.loc[d.year.ge(1986),'schedule_games'].notna().all()
d['availability_threshold']=np.ceil(.85*d.schedule_games).astype('Int64')
d['games_below_threshold']=np.maximum(0,d.availability_threshold.astype(float)-d.G)
d=d[d.year.ge(1986)&d.G.ge(20)].copy()
assert (d.games_below_threshold>=0).all()
assert (d.loc[d.G>=d.availability_threshold,'games_below_threshold']==0).all()
d[['Season','PlayerID','Player Name','Tm','G','schedule_games','schedule_fallback','availability_threshold','games_below_threshold']].to_csv(OUT/'availability_audit.csv',index=False)
d[['Season','PlayerID','Player Name','Tm','conference','team_wins','team_losses','league_rank','league_standing','conference_rank','conference_standing']].to_csv(OUT/'team_context_audit.csv',index=False)
teams.to_csv(OUT/'team_standings.csv',index=False)

def make_groups(cols):
    result=[]
    for year,g in d.groupby('year'):
        lab=labels[labels.year.eq(year)]
        if lab.empty:continue
        y=g.name_key.isin(lab.name_key).to_numpy(float)
        assert y.sum()==1,(year,lab.player.tolist())
        assert g.loc[y>0,['team_wins','conference_rank']].notna().all().all(),('winner team/conference missing',year)
        raw=g[cols].to_numpy(float)
        med=np.nanmedian(raw,axis=0)
        raw=np.where(np.isnan(raw),med,raw)
        sd=raw.std(axis=0);sd[sd<1e-8]=1
        x=(raw-raw.mean(axis=0))/sd
        # Keep the deficit in raw game units, uncentered: zero deficit must
        # have exactly zero contribution and no games bonus above threshold.
        if 'games_below_threshold' in cols:
            j=cols.index('games_below_threshold');x[:,j]=raw[:,j]
        assert np.isfinite(x).all()
        result.append(dict(year=int(year),g=g,x=x,y=y))
    return result

def fit(gs,half,reg,cols,constrained=False):
    latest=max(g['year'] for g in gs)
    w=np.array([2**(-(latest-g['year'])/half) for g in gs]);w/=w.sum()
    def obj(b):
        loss=reg*np.dot(b,b)/2;grad=reg*b
        for g,weight in zip(gs,w):
            z=np.einsum('ij,j->i',g['x'],b)
            loss+=weight*(logsumexp(z)-g['y']@z)
            grad=grad+weight*np.einsum('ij,i->j',g['x'],softmax(z)-g['y'])
        return loss,grad
    bounds=[(None,-1e-8) if c=='games_below_threshold' else (None,None) for c in cols]
    res=minimize(obj,np.zeros(gs[0]['x'].shape[1]),jac=True,method='L-BFGS-B',bounds=bounds)
    assert res.success and np.isfinite(res.x).all(),res.message
    return res.x

def predict(g,b):
    scores=np.einsum('ij,j->i',g['x'],b);prob=softmax(scores)
    order=np.argsort(-scores,kind='stable');winner=np.flatnonzero(g['y'])[0]
    rank=int(np.where(order==winner)[0][0])+1
    assert abs(prob.sum()-1)<1e-10
    return dict(season=g['g'].Season.iloc[0],year=g['year'],predicted=g['g'].iloc[order[0]]['Player Name'],actual=g['g'].iloc[winner]['Player Name'],winner_rank=rank,top1=int(rank==1),top3=int(rank<=3),log_loss=float(logsumexp(scores)-scores[winner])),prob,order




current=json.loads((ROOT/'mvp_availability_revision/model.json').read_text())
cols=current['features'];gs=make_groups(cols)
# Candidate selection is a ranking rule after scoring. Preserve the existing
# training contests and feature normalization; do not delete excluded winners
# from historical training seasons or silently alter the fitted coefficients.
d['ppg_rank']=d.groupby('Season').PTS.rank(method='min',ascending=False)
d['eligible_top20']=d.ppg_rank.le(20)
d[['Season','PlayerID','Player Name','PTS','G','ppg_rank','eligible_top20']].to_csv(OUT/'eligibility_audit.csv',index=False)
results=[];top5=[];allrankings=[];winner_coverage=[]
expected=pd.read_csv(ROOT/'mvp_availability_revision/historical_backtests.csv').set_index('season')
for g in gs:
    season=g['g'].Season.iloc[0]
    ranks=g['g'].PTS.rank(method='min',ascending=False).to_numpy()
    mask=ranks<=20
    winner=np.flatnonzero(g['y'])[0]
    winner_coverage.append(dict(season=season,actual=g['g'].iloc[winner]['Player Name'],PPG=float(g['g'].iloc[winner].PTS),scoring_rank=int(ranks[winner]),eligible=bool(mask[winner])))
    if g['year']<2016:continue
    train=[h for h in gs if h['year']<g['year']]
    assert max(h['year'] for h in train)<g['year']
    b=fit(train,current['half_life'],current['regularization'],cols)
    old,_,_=predict(g,b)
    assert old['predicted']==expected.loc[season,'predicted']
    assert old['winner_rank']==expected.loc[season,'winner_rank']
    assert abs(old['log_loss']-expected.loc[season,'log_loss'])<1e-6
    score=np.einsum('ij,j->i',g['x'],b)
    eligible_indices=np.flatnonzero(mask)
    eligible_scores=score[eligible_indices]
    order=eligible_indices[np.argsort(-eligible_scores,kind='stable')]
    share=softmax(eligible_scores)
    share_by_index=dict(zip(eligible_indices,share))
    assert len(order)>=20 and (ranks[order]<=20).all()
    assert abs(sum(share_by_index.values())-1)<1e-10
    if mask[winner]:
        winner_rank=int(np.where(order==winner)[0][0])+1
        loss=float(logsumexp(eligible_scores)-score[winner])
    else:winner_rank=None;loss=float('inf')
    results.append(dict(season=season,predicted=g['g'].iloc[order[0]]['Player Name'],actual=old['actual'],winner_rank=winner_rank,winner_eligible=bool(mask[winner]),top1=int(winner_rank==1),top3=int(winner_rank is not None and winner_rank<=3),log_loss=loss,candidates=len(order),latest_training_year=max(h['year'] for h in train)))
    for rank,i in enumerate(order,1):
        v=g['g'].iloc[i];terms=g['x'][i]*b
        row=dict(season=season,rank=rank,player=v['Player Name'],actual_winner=old['actual'],PPG=v.PTS,ppg_rank=int(ranks[i]),score=float(score[i]),model_share=float(share_by_index[i]),games=v.G,team_games=v.schedule_games,threshold=int(v.availability_threshold),shortfall=v.games_below_threshold,**{f:float(terms[j]) for j,f in enumerate(cols)})
        assert abs(sum(float(terms[j]) for j in range(len(cols)))-score[i])<1e-9
        allrankings.append(row)
        if rank<=5:top5.append(row)
results=pd.DataFrame(results);results.to_csv(OUT/'historical_backtests.csv',index=False)
pd.DataFrame(top5).to_csv(OUT/'selected_top5.csv',index=False)
pd.DataFrame(allrankings).to_csv(OUT/'all_eligible_rankings.csv',index=False)
pd.DataFrame(winner_coverage).to_csv(OUT/'historical_winner_eligibility.csv',index=False)
old=expected.reset_index()
comparison=old[['season','predicted','winner_rank','top1','log_loss']].merge(results,on='season',suffixes=('_previous','_top20'),validate='one_to_one')
assert len(comparison)==11
comparison.to_csv(OUT/'before_after.csv',index=False)
model=dict(current,variant='top20_PPG_85pct_penalty',ranking_eligibility='PPG rank <=20 among players with >=20 games in season; competition ranking (min) includes all ties at 20th',normalization='Existing all-players-with-20-games pool, unchanged. Filter only after scoring; softmax shares renormalized over eligible players.',training='Unchanged training and fitted coefficients; keep historical winners even if ineligible under ranking rule.')
(OUT/'model.json').write_text(json.dumps(model,indent=2))
pd.DataFrame(dict(feature=cols,coefficient=current['coefficients'])).to_csv(OUT/'coefficients.csv',index=False)
summary=pd.DataFrame([dict(variant='previous_availability_model',correct=int(old.top1.sum()),top3=int(old.top3.sum()),mean_log_loss=float(old.log_loss.mean())),dict(variant=model['variant'],correct=int(results.top1.sum()),top3=int(results.top3.sum()),mean_log_loss=float(results.log_loss.mean()))])
summary.to_csv(OUT/'comparison_summary.csv',index=False)
print(summary.to_string(index=False),flush=True)
print(comparison[['season','predicted_previous','predicted_top20','actual','winner_rank_top20','candidates']].to_string(index=False),flush=True)
print('Historical winners excluded by this rule:',[r for r in winner_coverage if not r['eligible']],flush=True)
