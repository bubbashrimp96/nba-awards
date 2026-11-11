"""MVP revision: remove BPM and include PER, steals and blocks.
Run python3 improve_mvp_no_bpm.py. Original models and outputs remain untouched.
"""
from pathlib import Path
import json, re, unicodedata, hashlib
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import softmax, logsumexp

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'mvp_no_bpm_revision';OUT.mkdir(exist_ok=True)
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
    bounds=[(.05,.25) if constrained and c in ['STL','BLK'] else (None,None) for c in cols]
    res=minimize(obj,np.zeros(gs[0]['x'].shape[1]),jac=True,method='L-BFGS-B',bounds=bounds)
    assert res.success and np.isfinite(res.x).all(),res.message
    return res.x

def predict(g,b):
    scores=np.einsum('ij,j->i',g['x'],b);prob=softmax(scores)
    order=np.argsort(-scores,kind='stable');winner=np.flatnonzero(g['y'])[0]
    rank=int(np.where(order==winner)[0][0])+1
    assert abs(prob.sum()-1)<1e-10
    return dict(season=g['g'].Season.iloc[0],year=g['year'],predicted=g['g'].iloc[order[0]]['Player Name'],actual=g['g'].iloc[winner]['Player Name'],winner_rank=rank,top1=int(rank==1),top3=int(rank<=3),log_loss=float(logsumexp(scores)-scores[winner])),prob,order


current=json.loads((ROOT/'mvp_conference_revision/model.json').read_text())
basecols=current['features']
variants={
 'no_BPM_PER_STL_BLK_learned':dict(cols=[c for c in basecols if c!='BPM']+['PER','STL','BLK'],constrained=False),
 'no_BPM_PER_STL_BLK_small_positive':dict(cols=[c for c in basecols if c!='BPM']+['PER','STL','BLK'],constrained=True),
}
assert all('BPM' not in v['cols'] and all(c in v['cols'] for c in ['PER','STL','BLK']) for v in variants.values())
allgrid=[];configs={};group_cache={}
for name,spec in variants.items():
    cols=spec['cols'];gs=make_groups(cols);group_cache[name]=gs
    settings=[]
    for half in [5,10,20]:
        for reg in [.03,.1,.3]:
            results=[]
            for g in gs:
                if not 2006<=g['year']<=2015:continue
                train=[h for h in gs if h['year']<g['year']]
                assert max(h['year'] for h in train)<g['year']
                b=fit(train,half,reg,cols,spec['constrained'])
                r,_,_=predict(g,b);results.append(r)
            row=dict(variant=name,half_life=half,regularization=reg,development_log_loss=float(np.mean([r['log_loss'] for r in results])),development_correct=sum(r['top1'] for r in results))
            allgrid.append(row);settings.append(row)
    configs[name]=min(settings,key=lambda r:(r['development_log_loss'],r['half_life'],r['regularization']))
    print('DEVELOPMENT',configs[name],flush=True)
selected=min(configs,key=lambda n:configs[n]['development_log_loss'])
(OUT/'selection_frozen.json').write_text(json.dumps(dict(selected=selected,configs=configs,criterion='2006-2015 rolling mean log loss, before evaluating revised 2016-2026 outputs',defensive_bound='Small-positive family constrains STL and BLK coefficients each to [0.05,0.25] score units per standardized input'),indent=2))
pd.DataFrame(allgrid).to_csv(OUT/'development_grid.csv',index=False)
results=[];top5=[];coefficients=[];models={}
for name in ['baseline']+list(variants):
    if name=='baseline':
        cols=basecols;gs=make_groups(cols);half=current['half_life'];reg=current['regularization'];constrained=False
    else:
        cols=variants[name]['cols'];gs=group_cache[name];half=configs[name]['half_life'];reg=configs[name]['regularization'];constrained=variants[name]['constrained']
    for g in gs:
        if g['year']<2016:continue
        train=[h for h in gs if h['year']<g['year']]
        assert max(h['year'] for h in train)<g['year']
        b=fit(train,half,reg,cols,constrained)
        if constrained:
            for f in ['STL','BLK']:assert .04999999<=b[cols.index(f)]<=.25000001
        r,prob,order=predict(g,b)
        r.update(variant=name,half_life=half,regularization=reg,latest_training_year=max(h['year'] for h in train));results.append(r)
        if name==selected:
            for rank,i in enumerate(order[:5],1):
                v=g['g'].iloc[i]
                top5.append(dict(season=r['season'],rank=rank,player=v['Player Name'],actual_winner=r['actual'],model_share=float(prob[i]),PER=v.PER,STL=v.STL,BLK=v.BLK,BPM=v.BPM,WS48=v['WS/48'],team_wins=v.team_wins,conference_rank=v.conference_rank))
    b=fit(gs,half,reg,cols,constrained)
    for f,c in zip(cols,b):coefficients.append(dict(variant=name,feature=f,coefficient=float(c)))
    models[name]=dict(current,variant=name,features=cols,coefficients=b.tolist(),half_life=half,regularization=reg,defensive_bounds=[.05,.25] if constrained else None)
results=pd.DataFrame(results)
baseline=results[results.variant.eq('baseline')]
old=pd.read_csv(ROOT/'mvp_conference_revision/historical_backtests.csv');old=old[old.variant.eq(current['variant'])]
check=baseline.merge(old,on='season',suffixes=('_new','_old'),validate='one_to_one')
assert len(check)==11 and (check.predicted_new==check.predicted_old).all()
assert np.allclose(check.log_loss_new,check.log_loss_old,atol=1e-6)
summary=results.groupby('variant',sort=False).agg(correct=('top1','sum'),top3=('top3','sum'),mean_log_loss=('log_loss','mean')).reset_index()
summary['selected_on_development']=summary.variant.eq(selected)
summary.to_csv(OUT/'comparison_summary.csv',index=False)
results.to_csv(OUT/'historical_backtests.csv',index=False)
pd.DataFrame(top5).to_csv(OUT/'selected_top5.csv',index=False)
pd.DataFrame(coefficients).to_csv(OUT/'all_coefficients.csv',index=False)
pd.DataFrame([r for r in coefficients if r['variant']==selected]).to_csv(OUT/'coefficients.csv',index=False)
(OUT/'model.json').write_text(json.dumps(models[selected],indent=2))
(OUT/'all_models.json').write_text(json.dumps(models,indent=2))
revised=results[results.variant.eq(selected)]
comparison=baseline[['season','predicted','winner_rank','top1','log_loss']].merge(revised[['season','predicted','actual','winner_rank','top1','log_loss']],on='season',suffixes=('_baseline','_revised'),validate='one_to_one')
comparison.to_csv(OUT/'before_after.csv',index=False)
print('SELECTED',selected,flush=True)
print(summary.to_string(index=False),flush=True)
print(comparison.to_string(index=False),flush=True)
