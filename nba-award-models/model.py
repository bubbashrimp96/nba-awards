"""Reproducible season-conditional NBA award models. Run: python3 model.py."""
from pathlib import Path
import json, re, unicodedata, hashlib
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import logsumexp, softmax

OUT = Path(__file__).resolve().parent
SOURCE = (Path(__file__).resolve().parent / 'data' / 'basketball_stats.csv')
def clean(s):
    s = re.sub(r'\s*\(Tie\)', '', str(s))
    try: s = s.encode('latin1').decode('utf8')
    except (UnicodeEncodeError, UnicodeDecodeError): pass
    return s
def key(s):
    return re.sub('[^a-z0-9]', '', unicodedata.normalize('NFKD', clean(s)).encode('ascii','ignore').decode().lower())

d = pd.read_csv(SOURCE)
assert not d.duplicated(['PlayerID','Season']).any()
d['Player Name'] = d['Player Name'].map(clean)
d['name_key'] = d['Player Name'].map(key)
d['year'] = d.Season.str[:4].astype(int)+1
d = d.sort_values(['PlayerID','year']).reset_index(drop=True)
d['MPG'] = d.MP / d.G.replace(0,np.nan) # MP is total minutes, not minutes per game
d['experience'] = d.year-d.groupby('PlayerID').year.transform('min')
for c in ['PTS','AST','TRB','BPM','PER','WS','MPG','TS%','USG%']:
    prev = d.groupby('PlayerID')[c].shift()
    adjacent = d.groupby('PlayerID').year.shift().eq(d.year-1)
    d['delta_'+c] = d[c]-prev
d['prior_G'] = d.groupby('PlayerID').G.shift().where(d.groupby('PlayerID').year.shift().eq(d.year-1))
labels = pd.DataFrame(json.loads((OUT/'award_labels.json').read_text()))
labels['name_key'] = labels.player.map(key)
labels['year'] = labels.season.str[:4].astype(int)+1
features = {
 'MVP':['PTS','AST','TRB','BPM','WS','WS/48','VORP','TS%','G'],
 'DPOY':['STL','BLK','DRB','DWS','DBPM','DRtg','G','MPG'],
 'ROY':['PTS','AST','TRB','STL','BLK','BPM','WS','TS%','G'],
 'SMOY':['PTS','AST','TRB','BPM','WS','TS%','G','MPG'],
 'MIP':['PTS','BPM','WS','Age','experience','delta_PTS','delta_AST','delta_TRB','delta_BPM','delta_PER','delta_MPG','delta_TS%','delta_USG%']}

def groups(award):
    p=d[d.year.ge(1986)&d.G.ge(20)].copy()
    if award=='ROY': p=p[p.experience.eq(0)]
    if award=='SMOY': p=p[p.GS.notna() & (2*p.GS<p.G)]
    if award=='MIP': p=p[p['delta_PTS'].notna()&p.experience.ge(1)]
    result=[]
    for yr,g in p.groupby('year'):
        lab=labels[(labels.award==award)&(labels.year==yr)]
        if lab.empty: continue
        target=g.name_key.isin(lab.name_key).to_numpy(dtype=float)
        if target.sum()!=len(lab):
            raise ValueError(f'Winner missing/excluded: {award} {yr} {lab.player.tolist()}')
        target/=target.sum() # tied winners share target mass
        raw=g[features[award]].to_numpy(float)
        # Within-season eligible-pool z scores; missing values get that season's median.
        med=np.nanmedian(raw,axis=0)
        raw=np.where(np.isnan(raw),med,raw)
        mean=raw.mean(axis=0); sd=raw.std(axis=0); sd[sd<1e-8]=1
        x=(raw-mean)/sd
        assert np.isfinite(x).all()
        result.append(dict(year=int(yr),g=g,x=x,y=target,mean=mean,sd=sd,median=med))
    return result

def fit(gs,half,reg):
    latest=max(g['year'] for g in gs)
    weights=np.array([2**(-(latest-g['year'])/half) for g in gs])
    weights/=weights.sum()
    def obj(b):
        loss=reg*np.dot(b,b)/2; grad=reg*b
        for g,w in zip(gs,weights):
            z=np.einsum('ij,j->i',g['x'],b); prob=softmax(z)
            loss+=w*(logsumexp(z)-g['y']@z)
            grad=grad+w*np.einsum('ij,i->j',g['x'],prob-g['y'])
        return loss,grad
    res=minimize(obj,np.zeros(gs[0]['x'].shape[1]),jac=True,method='L-BFGS-B')
    assert res.success,res.message
    return res.x

def evaluate(g,b):
    prob=softmax(np.einsum('ij,j->i',g['x'],b)); order=np.argsort(-prob); winners=np.where(g['y']>0)[0]
    rank=min(int(np.where(order==i)[0][0])+1 for i in winners)
    return prob,order,rank,float(-np.log(prob[winners].sum()))

summary=[]; backtests=[]; coeff=[]; models={}; gridrows=[]
for award,cols in features.items():
    gs=groups(award)
    # Development uses only 2006-2015. All later years are untouched by selection.
    choices=[]
    for half in [5,10,20]:
        for reg in [.03,.1, .3]:
            losses=[]
            for g in gs:
                if 2006<=g['year']<=2015:
                    b=fit([h for h in gs if h['year']<g['year']],half,reg)
                    losses.append(evaluate(g,b)[3])
            loss=float(np.mean(losses)); choices.append((loss,half,reg))
            gridrows.append(dict(award=award,half_life=half,regularization=reg,development_log_loss=loss))
    _,half,reg=min(choices)
    for mode,h in [('recency',half),('equal_weight',1e9)]:
        rows=[]
        for g in gs:
            if g['year']<2016: continue
            b=fit([v for v in gs if v['year']<g['year']],h,reg)
            prob,order,rank,loss=evaluate(g,b)
            row=dict(award=award,weighting=mode,season=g['g'].Season.iloc[0],predicted=g['g'].iloc[order[0]]['Player Name'],actual=' / '.join(g['g'].loc[g['y']>0,'Player Name']),winner_rank=rank,top1=int(rank==1),top3=int(rank<=3),winner_log_loss=loss)
            rows.append(row);backtests.append(row)
        summary.append(dict(award=award,weighting=mode,half_life=half if mode=='recency' else 'infinite',regularization=reg,seasons=len(rows),top1=float(np.mean([r['top1'] for r in rows])),top3=float(np.mean([r['top3'] for r in rows])),mean_log_loss=float(np.mean([r['winner_log_loss'] for r in rows]))))
    b=fit(gs,half,reg)
    models[award]=dict(features=cols,coefficients=b.tolist(),half_life=half,regularization=reg,trained_through=max(g['year'] for g in gs))
    for c,v in zip(cols,b):coeff.append(dict(award=award,feature=c,coefficient=float(v)))
    print(award,summary[-2:],flush=True)

pd.DataFrame(summary).to_csv(OUT/'validation_summary.csv',index=False)
pd.DataFrame(backtests).to_csv(OUT/'historical_backtests.csv',index=False)
pd.DataFrame(coeff).to_csv(OUT/'coefficients.csv',index=False)
pd.DataFrame(gridrows).to_csv(OUT/'development_grid.csv',index=False)
models['_metadata']=dict(source=str(SOURCE),sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),training_start=1986,development='2006-2015',test='2016-2026',probabilities='Uncalibrated conditional model shares; not betting probabilities.')
(OUT/'models.json').write_text(json.dumps(models,indent=2))
