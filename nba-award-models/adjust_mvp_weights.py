"""MVP coefficient sensitivity: reduce BPM and increase WS/48 after fitting.
Run python3 adjust_mvp_weights.py. Original models and outputs remain untouched.
"""
from pathlib import Path
import json, re, unicodedata, hashlib
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import softmax, logsumexp

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'mvp_weight_revision';OUT.mkdir(exist_ok=True)
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
d=d[d.year.ge(1986)&d.G.ge(20)].copy()
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
        assert np.isfinite(x).all()
        result.append(dict(year=int(year),g=g,x=x,y=y))
    return result

def fit(gs,half,reg):
    latest=max(g['year'] for g in gs)
    w=np.array([2**(-(latest-g['year'])/half) for g in gs]);w/=w.sum()
    def obj(b):
        loss=reg*np.dot(b,b)/2;grad=reg*b
        for g,weight in zip(gs,w):
            z=np.einsum('ij,j->i',g['x'],b)
            loss+=weight*(logsumexp(z)-g['y']@z)
            grad=grad+weight*np.einsum('ij,i->j',g['x'],softmax(z)-g['y'])
        return loss,grad
    res=minimize(obj,np.zeros(gs[0]['x'].shape[1]),jac=True,method='L-BFGS-B')
    assert res.success and np.isfinite(res.x).all(),res.message
    return res.x

def predict(g,b):
    scores=np.einsum('ij,j->i',g['x'],b);prob=softmax(scores)
    order=np.argsort(-scores,kind='stable');winner=np.flatnonzero(g['y'])[0]
    rank=int(np.where(order==winner)[0][0])+1
    assert abs(prob.sum()-1)<1e-10
    return dict(season=g['g'].Season.iloc[0],year=g['year'],predicted=g['g'].iloc[order[0]]['Player Name'],actual=g['g'].iloc[winner]['Player Name'],winner_rank=rank,top1=int(rank==1),top3=int(rank<=3),log_loss=float(logsumexp(scores)-scores[winner])),prob,order


current=json.loads((ROOT/'mvp_conference_revision/model.json').read_text())
cols=current['features'];gs=make_groups(cols)
half=current['half_life'];reg=current['regularization']
ib=cols.index('BPM');iw=cols.index('WS/48')
# Fit once per cutoff. Multipliers are applied AFTER fitting so refitting does
# not simply undo a feature rescaling. Every other coefficient stays fixed.
fits={}
for g in gs:
    if g['year']>=2006:
        train=[h for h in gs if h['year']<g['year']]
        assert max(h['year'] for h in train)<g['year']
        fits[g['year']]=fit(train,half,reg)

def adjusted(b,bpm,ws):
    v=b.copy();v[ib]*=bpm;v[iw]*=ws;return v

settings=[(1.,1.)]+[(b,w) for b in [.25,.5,.75] for w in [1.25,1.5,2.]]
development=[]
for bpm,ws in settings:
    results=[predict(g,adjusted(fits[g['year']],bpm,ws))[0] for g in gs if 2006<=g['year']<=2015]
    development.append(dict(bpm_multiplier=bpm,ws48_multiplier=ws,correct=sum(r['top1'] for r in results),mean_log_loss=float(np.mean([r['log_loss'] for r in results]))))
# Choose only among the user's lower-BPM/higher-WS48 variants. Also retain
# the unchanged baseline to show if the requested constraint harms development.
chosen=min(development[1:],key=lambda r:(r['mean_log_loss'],r['bpm_multiplier'],r['ws48_multiplier']))
(OUT/'selection_frozen.json').write_text(json.dumps(dict(chosen=chosen,criterion='2006-2015 rolling mean log loss; constrained to lower BPM and higher WS/48',settings=development),indent=2))
pd.DataFrame(development).to_csv(OUT/'development_grid.csv',index=False)
print('DEVELOPMENT',development,flush=True)
print('CHOSEN',chosen,flush=True)
allrows=[];top5=[]
for bpm,ws in settings:
    selected=bpm==chosen['bpm_multiplier'] and ws==chosen['ws48_multiplier']
    for g in gs:
        if g['year']<2016:continue
        b=adjusted(fits[g['year']],bpm,ws)
        row,prob,order=predict(g,b)
        row.update(bpm_multiplier=bpm,ws48_multiplier=ws,selected=selected)
        allrows.append(row)
        if selected:
            for rank,i in enumerate(order[:5],1):
                r=g['g'].iloc[i]
                top5.append(dict(season=row['season'],rank=rank,player=r['Player Name'],actual_winner=row['actual'],model_share=float(prob[i]),BPM=r.BPM,WS48=r['WS/48'],team_wins=r.team_wins,conference_rank=r.conference_rank))
results=pd.DataFrame(allrows)
baseline=results[(results.bpm_multiplier==1)&(results.ws48_multiplier==1)]
old=pd.read_csv(ROOT/'mvp_conference_revision/historical_backtests.csv');old=old[old.variant.eq(current['variant'])]
check=baseline.merge(old,on='season',suffixes=('_new','_old'),validate='one_to_one')
assert len(check)==11 and (check.predicted_new==check.predicted_old).all()
assert np.allclose(check.log_loss_new,check.log_loss_old,atol=1e-7)
summary=results.groupby(['bpm_multiplier','ws48_multiplier'],sort=False).agg(correct=('top1','sum'),top3=('top3','sum'),mean_log_loss=('log_loss','mean'),selected=('selected','first')).reset_index()
summary.to_csv(OUT/'sensitivity_summary.csv',index=False)
results.to_csv(OUT/'historical_backtests.csv',index=False)
pd.DataFrame(top5).to_csv(OUT/'selected_top5.csv',index=False)
revised=results[results.selected]
comparison=baseline[['season','predicted','winner_rank','top1','log_loss']].merge(revised[['season','predicted','actual','winner_rank','top1','log_loss']],on='season',suffixes=('_baseline','_revised'),validate='one_to_one')
comparison.to_csv(OUT/'before_after.csv',index=False)
final_b=adjusted(np.array(current['coefficients']),chosen['bpm_multiplier'],chosen['ws48_multiplier'])
pd.DataFrame(dict(feature=cols,baseline_coefficient=current['coefficients'],revised_coefficient=final_b)).to_csv(OUT/'coefficients.csv',index=False)
model=dict(current)
model.update(variant='conference_plus_league_adjusted',coefficients=final_b.tolist(),bpm_multiplier=chosen['bpm_multiplier'],ws48_multiplier=chosen['ws48_multiplier'],coefficient_method='Fit existing regularized model then apply multipliers only to BPM and WS/48; other coefficients unchanged')
(OUT/'model.json').write_text(json.dumps(model,indent=2))
print(summary.to_string(index=False),flush=True)
print(comparison.to_string(index=False),flush=True)
