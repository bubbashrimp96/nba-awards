"""Top-three MVP score contributions using the no-BPM freely learned model.
Run python3 explain_mvp_top3.py. Original models and outputs remain untouched.
"""
from pathlib import Path
import json, re, unicodedata, hashlib
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import softmax, logsumexp

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'mvp_score_breakdown';OUT.mkdir(exist_ok=True)
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



variant='no_BPM_PER_STL_BLK_learned'
model=json.loads((ROOT/'mvp_no_bpm_revision/all_models.json').read_text())[variant]
cols=model['features'];gs=make_groups(cols)
assert 'BPM' not in cols
summary=[];detail=[];coefficients=[];winner_rows=[]
expected=pd.read_csv(ROOT/'mvp_no_bpm_revision/historical_backtests.csv')
expected=expected[expected.variant.eq(variant)].set_index('season')
for g in gs:
    if g['year']<2016:continue
    train=[h for h in gs if h['year']<g['year']]
    b=fit(train,model['half_life'],model['regularization'],cols,False)
    r,prob,order=predict(g,b)
    assert r['predicted']==expected.loc[r['season'],'predicted']
    assert r['winner_rank']==expected.loc[r['season'],'winner_rank']
    assert abs(r['log_loss']-expected.loc[r['season'],'log_loss'])<1e-6
    raw=g['g'][cols].to_numpy(float);med=np.nanmedian(raw,axis=0)
    imputed=np.where(np.isnan(raw),med,raw);mean=imputed.mean(axis=0);sd=imputed.std(axis=0);sd[sd<1e-8]=1
    assert np.allclose((imputed-mean)/sd,g['x'])
    for f,v in zip(cols,b):coefficients.append(dict(season=r['season'],feature=f,coefficient=float(v),latest_training_year=max(h['year'] for h in train)))
    for rank,i in enumerate(order[:3],1):
        player=g['g'].iloc[i];terms=g['x'][i]*b
        term=dict(zip(cols,terms))
        total=float(terms.sum())
        assert abs(total-float(np.einsum('j,j->',g['x'][i],b)))<1e-9
        row=dict(season=r['season'],rank=rank,player=player['Player Name'],actual_mvp=r['actual'],is_actual_winner=bool(g['y'][i]),score=total,model_share=float(prob[i]),points=term['PTS'],assists=term['AST'],rebounds=term['TRB'],PER=term['PER'],WS48=term['WS/48'],TS=term['TS%'],steals=term['STL'],blocks=term['BLK'],games=term['G'],team_wins=term['team_wins'],league_standing=term['league_standing'],conference_standing=term['conference_standing'])
        row['production']=term['PTS']+term['AST']+term['TRB']
        row['advanced']=term['PER']+term['WS/48']+term['TS%']
        row['defense']=term['STL']+term['BLK']
        row['team_success']=term['team_wins']+term['league_standing']+term['conference_standing']
        assert abs(sum(row[k] for k in ['production','advanced','defense','games','team_success'])-total)<1e-9
        summary.append(row)
        for j,f in enumerate(cols):detail.append(dict(season=r['season'],rank=rank,player=player['Player Name'],feature=f,raw_value=raw[i,j],imputed_value=imputed[i,j],pool_mean=mean[j],pool_std=sd[j],standardized_value=g['x'][i,j],coefficient=b[j],score_contribution=terms[j]))
    winner_rows.append(dict(season=r['season'],actual_mvp=r['actual'],winner_rank=r['winner_rank']))
pd.DataFrame(summary).to_csv(OUT/'top3_scores.csv',index=False)
pd.DataFrame(detail).to_csv(OUT/'feature_contributions.csv',index=False)
pd.DataFrame(coefficients).to_csv(OUT/'season_coefficients.csv',index=False)
assert len(summary)==33 and len(detail)==33*12
lines=['# MVP top-three score breakdown: no BPM, freely learned PER/STL/BLK','','## Model used','','This is the latest no-BPM model with freely learned PER, steals and blocks coefficients (8/11 correct first picks), not the small-positive-defense version (7/11) and not the older conference model currently in the PDF. Inputs: PTS, AST, TRB, WS/48, TS%, G, team wins, league standing, conference standing, PER, STL, BLK. Total WS and VORP remain excluded.','','Each season uses its own fitted coefficients trained only on preceding seasons, starting in 1985-86. Half-life is 20 seasons; L2 regularization is 0.03. Do not use the single full-history coefficient set to reproduce these historical scores. The experiment remains retrospective because the outcomes have already been inspected.','','## How to read the scores','','Each contribution = season-fitted coefficient x the player standardized value within the candidate pool for that season. Positive terms raise the score; negative terms lower it. Contributions are in model score units, not percentages or raw basketball statistics. Total score is the sum of all 12 terms. A larger total ranks higher within a season. Scores should not be compared directly across seasons, whose pools, normalizations and coefficients differ.','','Model share = exp(score) divided by the sum over all candidates, not just the top three. These shares are uncalibrated and are not estimated vote shares or established win probabilities. Displayed components are rounded, so their displayed sum can differ slightly from the displayed total. Full-precision CSV files reconcile exactly.','','Grouped view: Production = PTS + AST + TRB contributions; Advanced = PER + WS/48 + TS%; Defense = STL + BLK; Team = team wins + league standing + conference standing. Games is its own term. The raw-value, normalization and coefficient trail is in feature_contributions.csv.','','## Grouped contributions for all seasons','']
for season in sorted({r['season'] for r in summary}):
    rs=[r for r in summary if r['season']==season];winner=next(r for r in winner_rows if r['season']==season)
    lines+=[f"### {season} - actual MVP: {winner['actual_mvp']} (model rank {winner['winner_rank']})",'','| Rank | Player | Production | Advanced | Defense | Games | Team | Total | Model share |','|---:|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in rs:lines.append(f"| {r['rank']} | {r['player']}{' *' if r['is_actual_winner'] else ''} | {r['production']:+.2f} | {r['advanced']:+.2f} | {r['defense']:+.2f} | {r['games']:+.2f} | {r['team_success']:+.2f} | {r['score']:.2f} | {r['model_share']:.1%} |")
    lines+=['','Individual contributions:','','| Input | '+ ' | '.join(r['player'] for r in rs)+' |','|---|---:|---:|---:|']
    for field,label in [('points','PTS'),('assists','AST'),('rebounds','TRB'),('PER','PER'),('WS48','WS/48'),('TS','TS%'),('steals','STL'),('blocks','BLK'),('games','G'),('team_wins','Team wins'),('league_standing','League standing'),('conference_standing','Conference standing')]:
        lines.append('| '+label+' | '+' | '.join(f"{r[field]:+.3f}" for r in rs)+' |')
    lines+=['']
lines+=['* Marks the actual MVP when present in the top three. The 2016-17 winner Westbrook is outside the top three.','','## Reproduction','','Run `python3 ../explain_mvp_top3.py`. All 11 first picks, winner ranks and log losses are checked against the saved no-BPM learned-weight backtest. All 33 score totals are verified against the sum of their 12 contributions, as are their grouped subtotals. Source CSV and model definitions remain unchanged.']
(OUT/'REPORT.md').write_text('\n'.join(lines)+'\n')
print(pd.DataFrame(summary)[['season','rank','player','production','advanced','defense','games','team_success','score','model_share']].round(4).to_string(index=False))
print('Verified 33 players, 396 contributions, and all historical backtest matches.')
