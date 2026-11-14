"""Historical eligibility-only test using the original prior-season fitted weights."""
from pathlib import Path
import json, sys
import numpy as np
import pandas as pd
from scipy.special import softmax
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from revised_award_core import load_namespace,features_for
from fetch_odds import name_key

page=(ROOT/'output/artifacts/nba-award-models-browser.html').read_text()
baseline=json.JSONDecoder().raw_decode(page.split('const awardComparisons=',1)[1])[0]['MIP']
base={row['season']:row for row in baseline if not row.get('in_progress')}
columns=features_for('MIP')
ns=load_namespace('MIP');groups=ns['make_groups'](columns)
coefficients=pd.read_csv(ROOT/'revised_awards/season_coefficients.csv')
records=[]
for group in groups:
    frame=group['g'];season=frame.Season.iloc[0]
    if season not in base:continue
    saved=coefficients[(coefficients.award=='MIP')&(coefficients.season==season)].set_index('feature').coefficient
    scores=np.einsum('ij,j->i',group['x'],saved.loc[columns].to_numpy())
    actual=base[season]['actual']
    actual_top={name_key(row['player']) for row in actual if row['rank']<=3}
    winner={name_key(row['player']) for row in actual if row['rank']==1}
    variants={}
    for label,mask in [('original',np.ones(len(frame),dtype=bool)),('13ppg',frame.PTS.ge(13).to_numpy())]:
        pool=frame.loc[mask].copy();values=scores[mask];shares=softmax(values);order=np.argsort(-values,kind='stable')
        names=[name_key(name) for name in pool['Player Name']]
        top=pool.iloc[order[:3]]['Player Name'].tolist();keys={name_key(p) for p in top}
        winner_probability=sum(shares[i] for i,key in enumerate(names) if key in winner)
        variants[label]=dict(top=top,winner_first=int(name_key(top[0]) in winner),winner_top3=int(bool(winner&keys)),overlap=len(keys&actual_top)/len(actual_top),log_loss=float(-np.log(winner_probability)) if winner_probability>0 else None,pool_size=len(pool))
    records.append(dict(season=season,actual_winner=' / '.join(row['player'] for row in actual if row['rank']==1),**variants))
records.sort(key=lambda r:r['season'])
newest=max(int(r['season'][:4]) for r in records)
weights=np.array([2**(-(newest-int(r['season'][:4]))/5) for r in records]);weights/=weights.sum()
summary={}
for label in ('original','13ppg'):
    metrics={key:float(sum(w*r[label][key] for w,r in zip(weights,records))) for key in ('winner_first','winner_top3','overlap')}
    summary[label]=dict(seasons=len(records),winner_first=sum(r[label]['winner_first'] for r in records),winner_top3=sum(r[label]['winner_top3'] for r in records),mean_log_loss=float(np.mean([r[label]['log_loss'] for r in records])) if all(r[label]['log_loss'] is not None for r in records) else None,accuracy_score=100*(.5*metrics['winner_first']+.25*metrics['winner_top3']+.25*metrics['overlap']),weighted_metrics=metrics)
output=dict(method='Eligibility-only comparison: preserve original candidate standardisation and season-specific coefficients fitted only on prior years; exclude current-season PPG below 13 and renormalise remaining model shares. No refitting or production historical changes.',summary=summary,seasons=records)
path=Path(__file__).resolve().parent
(path/'results.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
flat=[]
for r in records:
    flat.append(dict(season=r['season'],actual_winner=r['actual_winner'],original_pick=r['original']['top'][0],test_pick=r['13ppg']['top'][0],original_top3=' / '.join(r['original']['top']),test_top3=' / '.join(r['13ppg']['top']),original_correct=r['original']['winner_first'],test_correct=r['13ppg']['winner_first'],original_winner_top3=r['original']['winner_top3'],test_winner_top3=r['13ppg']['winner_top3'],original_log_loss=r['original']['log_loss'],test_log_loss=r['13ppg']['log_loss']))
pd.DataFrame(flat).to_csv(path/'season_comparison.csv',index=False)
print(json.dumps(summary,indent=2))
print('CHANGED TOP 3:')
for r in records:
    if r['original']['top']!=r['13ppg']['top']:print(r['season'],r['actual_winner'],r['original']['top'],'->',r['13ppg']['top'])
