"""Apply WS/48 > 0.200 for top-three positions to the saved top-25-PPG model."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.special import softmax, logsumexp

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'mvp_ws48_top3_revision';OUT.mkdir(exist_ok=True)
PREV=ROOT/'mvp_top25_revision'
def clean(s):
    try:return s.encode('latin1').decode('utf8')
    except UnicodeError:return s

stats=pd.read_csv(Path(__file__).resolve().parent / 'data' / 'basketball_stats.csv')
stats['player']=stats['Player Name'].map(clean)
raw=stats[['Season','player','WS/48']].rename(columns={'Season':'season','WS/48':'raw_WS48'})
previous=pd.read_csv(PREV/'all_eligible_rankings.csv')
raw=raw.merge(previous[['season','player']],on=['season','player'],how='inner',validate='many_to_one')
assert not raw.duplicated(['season','player']).any()
d=previous.rename(columns={'rank':'previous_rank','model_share':'previous_score_share'}).merge(raw,on=['season','player'],how='left',validate='one_to_one')
d['top3_eligible']=d.raw_WS48.gt(.200)
assert pd.Series([.199,.200,.201,np.nan]).gt(.200).tolist()==[False,False,True,False]
allrows=[];results=[]
for season,g in d.groupby('season'):
    g=g.sort_values('score',ascending=False,kind='stable').copy()
    qualified=g[g.top3_eligible]
    first=qualified.head(3)
    rest=g.drop(first.index)
    g=pd.concat([first,rest])
    # Leave any unfillable top-three position vacant rather than bypassing rule.
    g['rank']=list(range(1,len(first)+1))+list(range(4,4+len(rest)))
    assert g.loc[g['rank']<=3,'raw_WS48'].gt(.2).all()
    assert g.ppg_rank.le(25).all() and g.games.ge(20).all()
    assert len(g)==len(previous[previous.season.eq(season)])
    assert np.allclose(g.score,g[[c for c in json.loads((PREV/'model.json').read_text())['features']]].sum(axis=1))
    # Only qualifying WS/48 candidates can rank first. These are uncalibrated
    # conditional model shares; lower WS/48 players get zero winner share.
    g['model_share']=0.
    if len(qualified):g.loc[qualified.index,'model_share']=softmax(qualified.score.to_numpy())
    assert abs(g.model_share.sum()-1)<1e-10
    actual=g.actual_winner.iloc[0]
    winner=g[g.player.eq(actual)]
    if len(winner):
        wr=int(winner['rank'].iloc[0]);we=bool(winner.top3_eligible.iloc[0])
        loss=float(logsumexp(qualified.score.to_numpy())-winner.score.iloc[0]) if we else float('inf')
    else:wr=None;we=False;loss=float('inf')
    results.append(dict(season=season,predicted=first.player.iloc[0] if len(first) else None,actual=actual,winner_rank=wr,winner_top3_eligible=we,top1=int(wr==1),top3=int(wr is not None and wr<=3),log_loss=loss,top3_eligible_candidates=len(qualified),filled_top3=len(first)))
    allrows.append(g)
ranked=pd.concat(allrows,ignore_index=True)
results=pd.DataFrame(results)
ranked.to_csv(OUT/'all_eligible_rankings.csv',index=False)
ranked[ranked['rank']<=5].to_csv(OUT/'selected_top5.csv',index=False)
results.to_csv(OUT/'historical_backtests.csv',index=False)
before=pd.read_csv(PREV/'historical_backtests.csv')
comparison=before[['season','predicted','winner_rank','top1','top3']].merge(results,on='season',suffixes=('_previous','_revised'),validate='one_to_one')
comparison.to_csv(OUT/'before_after.csv',index=False)
model=json.loads((PREV/'model.json').read_text())
model.update(variant='top25_PPG_WS48_above_0200_top3',top3_rule='Only top-25 PPG candidates whose raw WS/48 is strictly >0.200 may occupy positions 1-3. Fill those positions by existing score; rank remaining candidates from fourth by existing score. Exactly 0.200 or missing WS/48 does not qualify.',model_share_definition='Softmax over all top-25 PPG candidates with WS/48 >0.200; other candidates have zero first-place model share. Uncalibrated.')
(OUT/'model.json').write_text(json.dumps(model,indent=2))
pd.DataFrame([dict(version='previous_top25',correct=int(before.top1.sum()),top3=int(before.top3.sum())),dict(version=model['variant'],correct=int(results.top1.sum()),top3=int(results.top3.sum()))]).to_csv(OUT/'comparison_summary.csv',index=False)
print(comparison[['season','predicted_previous','predicted_revised','actual','winner_rank_revised','filled_top3']].to_string(index=False))
print('New totals:',results.top1.sum(),'correct;',results.top3.sum(),'winner in top 3')
print(ranked[ranked['rank']<=3][['season','rank','player','raw_WS48','score']].to_string(index=False))
