"""MVP revision: remove AST/TRB/G terms; add a below-85%-availability penalty.
Run python3 improve_mvp_availability.py. Original models and outputs remain untouched.
"""
from pathlib import Path
import json, re, unicodedata, hashlib
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import softmax, logsumexp

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'mvp_availability_revision';OUT.mkdir(exist_ok=True)
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



current=json.loads((ROOT/'mvp_no_bpm_revision/all_models.json').read_text())['no_BPM_PER_STL_BLK_learned']
cols=[c for c in current['features'] if c not in ['AST','TRB','G']]+['games_below_threshold']
assert all(c not in cols for c in ['BPM','AST','TRB','G','WS','VORP'])
assert all(c in cols for c in ['PTS','PER','WS/48','STL','BLK','team_wins','league_standing','conference_standing'])
gs=make_groups(cols);settings=[]
for half in [5,10,20]:
    for reg in [.03,.1,.3]:
        rs=[]
        for g in gs:
            if not 2006<=g['year']<=2015:continue
            train=[h for h in gs if h['year']<g['year']]
            assert max(h['year'] for h in train)<g['year']
            b=fit(train,half,reg,cols);r,_,_=predict(g,b);rs.append(r)
        settings.append(dict(half_life=half,regularization=reg,development_log_loss=float(np.mean([r['log_loss'] for r in rs])),development_correct=sum(r['top1'] for r in rs)))
best=min(settings,key=lambda r:(r['development_log_loss'],r['half_life'],r['regularization']))
(OUT/'selection_frozen.json').write_text(json.dumps(dict(chosen=best,criterion='2006-2015 rolling log loss, selected before later evaluation'),indent=2))
pd.DataFrame(settings).to_csv(OUT/'development_grid.csv',index=False)
results=[];top5=[];season_betas=[]
for g in gs:
    if g['year']<2016:continue
    train=[h for h in gs if h['year']<g['year']]
    assert max(h['year'] for h in train)<g['year']
    b=fit(train,best['half_life'],best['regularization'],cols)
    r,prob,order=predict(g,b);r['latest_training_year']=max(h['year'] for h in train);results.append(r)
    penalty=float(b[cols.index('games_below_threshold')]);assert penalty<0
    assert np.allclose(g['x'][:,cols.index('games_below_threshold')],g['g'].games_below_threshold)
    for f,v in zip(cols,b):season_betas.append(dict(season=r['season'],feature=f,coefficient=float(v)))
    for rank,i in enumerate(order[:5],1):
        v=g['g'].iloc[i];contributions=g['x'][i]*b
        top5.append(dict(season=r['season'],rank=rank,player=v['Player Name'],actual_winner=r['actual'],score=float(contributions.sum()),model_share=float(prob[i]),games=v.G,team_games=v.schedule_games,threshold=int(v.availability_threshold),deficit=v.games_below_threshold,penalty_per_game=penalty,availability_contribution=float(penalty*v.games_below_threshold),**{f:float(contributions[j]) for j,f in enumerate(cols) if f!='games_below_threshold'}))
results=pd.DataFrame(results);results.to_csv(OUT/'historical_backtests.csv',index=False)
pd.DataFrame(top5).to_csv(OUT/'selected_top5.csv',index=False)
pd.DataFrame(season_betas).to_csv(OUT/'season_coefficients.csv',index=False)
old=pd.read_csv(ROOT/'mvp_no_bpm_revision/historical_backtests.csv');old=old[old.variant.eq(current['variant'])]
comparison=old[['season','predicted','winner_rank','top1','log_loss']].merge(results[['season','predicted','actual','winner_rank','top1','log_loss']],on='season',suffixes=('_previous','_revised'),validate='one_to_one')
assert len(comparison)==11
comparison.to_csv(OUT/'before_after.csv',index=False)
final_b=fit(gs,best['half_life'],best['regularization'],cols)
assert final_b[cols.index('games_below_threshold')]<0
model=dict(current,variant='no_AST_TRB_G_85pct_penalty',features=cols,coefficients=final_b.tolist(),half_life=best['half_life'],regularization=best['regularization'],availability='Penalty coefficient times max(0, ceil(0.85 * actual team games) - player games). Deficit is not standardized or centered. Coefficient constrained strictly negative (upper numerical bound -1e-8). Multi-team rows use season-max team schedule as marked fallback.',defensive_bounds=None)
(OUT/'model.json').write_text(json.dumps(model,indent=2))
pd.DataFrame(dict(feature=cols,coefficient=final_b)).to_csv(OUT/'coefficients.csv',index=False)
summary=pd.DataFrame([dict(variant='previous_no_BPM',correct=int(old.top1.sum()),top3=int(old.top3.sum()),mean_log_loss=float(old.log_loss.mean())),dict(variant=model['variant'],correct=int(results.top1.sum()),top3=int(results.top3.sum()),mean_log_loss=float(results.log_loss.mean()))])
summary.to_csv(OUT/'comparison_summary.csv',index=False)
print('CHOSEN',best,flush=True)
print(summary.to_string(index=False),flush=True)
print(comparison.to_string(index=False),flush=True)
print('FINAL COEFFICIENTS',dict(zip(cols,final_b)),flush=True)
