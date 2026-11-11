"""MVP revision: no total WS; evaluate explicit team wins and league standing.
Run python3 improve_mvp.py. Original models and outputs remain untouched.
"""
from pathlib import Path
import json, re, unicodedata, hashlib
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import softmax, logsumexp

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'mvp_revision';OUT.mkdir(exist_ok=True)
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
 'no_total_WS':base,
 'team_wins':base+['team_wins'],
 'team_wins_standing':base+['team_wins','league_standing'],
 'lean_team_context':lean+['team_wins','league_standing'],
}
assert all('WS' not in v for v in FEATURES.values())

team_rows=[]
for season,win_map in wins.items():
    vals=pd.Series(win_map,dtype=float)
    # Average ranks for tied win totals. No conference or head-to-head tiebreaks.
    ranks=vals.rank(ascending=False,method='average')
    for tm,w in vals.items():team_rows.append(dict(Season=season,Tm=tm,team_wins=w,league_rank=float(ranks[tm]),league_standing=1-(ranks[tm]-1)/(len(vals)-1)))
teams=pd.DataFrame(team_rows)
d=d.merge(teams,on=['Season','Tm'],how='left',validate='many_to_one')
d=d[d.year.ge(1986)&d.G.ge(20)].copy()
d[['Season','PlayerID','Player Name','Tm','team_wins','league_rank','league_standing']].to_csv(OUT/'team_context_audit.csv',index=False)
teams.to_csv(OUT/'team_standings.csv',index=False)

def make_groups(cols):
    result=[]
    for year,g in d.groupby('year'):
        lab=labels[labels.year.eq(year)]
        if lab.empty:continue
        y=g.name_key.isin(lab.name_key).to_numpy(float)
        assert y.sum()==1,(year,lab.player.tolist())
        assert g.loc[y>0,'team_wins'].notna().all(),('winner team missing',year)
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

grid=[];all_tests=[];configs={};cache={};audits=[]
for name,cols in FEATURES.items():
    gs=make_groups(cols);cache[name]=gs
    settings=[]
    for half in [5,10,20]:
        for reg in [.03,.1,.3]:
            results=[]
            for g in gs:
                if not 2006<=g['year']<=2015:continue
                train=[h for h in gs if h['year']<g['year']]
                b=fit(train,half,reg)
                r,_,_=predict(g,b);results.append(r)
            row=dict(variant=name,half_life=half,regularization=reg,development_log_loss=float(np.mean([r['log_loss'] for r in results])),development_top1=sum(r['top1'] for r in results))
            grid.append(row);settings.append(row)
    best=min(settings,key=lambda r:(r['development_log_loss'],r['half_life'],r['regularization']))
    configs[name]=best
    print('DEVELOPMENT',best,flush=True)

# Select the feature family before evaluating any revised model on 2016-2026.
selected=min(configs,key=lambda n:configs[n]['development_log_loss'])
(OUT/'selection_frozen.json').write_text(json.dumps(dict(selected_variant=selected,configs=configs,selection='Lowest mean rolling development log loss, season-ending years 2006-2015'),indent=2))
pd.DataFrame(grid).to_csv(OUT/'development_grid.csv',index=False)

for name in ['original']+list(FEATURES):
    if name=='original':gs=make_groups(original['features']);half=original['half_life'];reg=original['regularization']
    else:gs=cache[name];half=configs[name]['half_life'];reg=configs[name]['regularization']
    for g in gs:
        if g['year']<2016:continue
        train=[h for h in gs if h['year']<g['year']]
        assert max(h['year'] for h in train)<g['year']
        b=fit(train,half,reg);r,prob,order=predict(g,b)
        r.update(variant=name,half_life=half,regularization=reg,latest_training_year=max(h['year'] for h in train));all_tests.append(r)
        if name==selected:
            for rank,i in enumerate(order[:5],1):
                row=g['g'].iloc[i]
                audits.append(dict(season=r['season'],rank=rank,player=row['Player Name'],model_share=float(prob[i]),team=row.Tm,team_wins=row.team_wins,league_rank=row.league_rank,actual_winner=r['actual'],**{c:row[c] for c in FEATURES[selected] if c not in ['team_wins','league_standing']}))

tests=pd.DataFrame(all_tests)
# Verify faithful reproduction of the original held-out MVP baseline.
old=pd.read_csv(ROOT/'historical_backtests.csv');old=old[(old.award=='MVP')&(old.weighting=='recency')]
check=tests[tests.variant=='original'].merge(old,on='season',suffixes=('_new','_old'),validate='one_to_one')
assert len(check)==11 and (check.predicted_new==check.predicted_old).all() and (check.winner_rank_new==check.winner_rank_old).all()
assert np.allclose(check.log_loss,check.winner_log_loss,atol=1e-7)
summary=tests.groupby('variant',sort=False).agg(seasons=('top1','size'),correct=('top1','sum'),top3=('top3','sum'),mean_log_loss=('log_loss','mean')).reset_index()
summary['selected_on_development']=summary.variant.eq(selected)
summary.to_csv(OUT/'comparison_summary.csv',index=False)
tests.to_csv(OUT/'historical_backtests.csv',index=False)
pd.DataFrame(audits).to_csv(OUT/'selected_top5.csv',index=False)
cols=FEATURES[selected];best=configs[selected];gs=cache[selected]
b=fit(gs,best['half_life'],best['regularization'])
pd.DataFrame(dict(feature=cols,coefficient=b)).to_csv(OUT/'coefficients.csv',index=False)
model=dict(variant=selected,features=cols,coefficients=b.tolist(),half_life=best['half_life'],regularization=best['regularization'],trained_through=2026,minimum_games=20,standardization='Within season and candidate pool, population standard deviation; season-pool median imputation',standings='League-wide wins rank with average ties; normalized to 0-1; no conference or official tiebreakers',sources={f:hashlib.sha256((DATA/f).read_bytes()).hexdigest() for f in ['basketball_stats.csv','team_wins_cache.json']},validation_warning='2016-2026 results previously inspected; retrospective comparison, not a fresh untouched test.')
(OUT/'model.json').write_text(json.dumps(model,indent=2))
print('SELECTED',selected,flush=True)
print(summary.to_string(index=False),flush=True)
baseline=tests[tests.variant=='original'];revised=tests[tests.variant==selected]
comparison=baseline[['season','predicted','winner_rank','top1']].merge(revised[['season','predicted','actual','winner_rank','top1']],on='season',suffixes=('_original','_revised'),validate='one_to_one')
comparison.to_csv(OUT/'before_after.csv',index=False)
print(comparison.to_string(index=False),flush=True)
