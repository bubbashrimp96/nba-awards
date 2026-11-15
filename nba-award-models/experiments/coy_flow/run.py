"""Prior-season-only comparison before deploying the supplied COY tree."""
from pathlib import Path
import sys,json
import numpy as np
import pandas as pd
from scipy.special import softmax
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import build_coy as model
from revised_award_core import team_context
from coy_flow import add_flow,FLOW_FEATURES
OUT=Path(__file__).resolve().parent
baseline=json.loads((OUT/'baseline_model.json').read_text());model.FEATURES=baseline['features'];model.RAW_TERMS={'top4_seed','prior_coy_same_team'}
pool,_=model.build_pool()
if 'conference_rank' not in pool:pool=pool.merge(team_context()[['year','Tm','conference_rank']],on=['year','Tm'],how='left',validate='one_to_one')
pool=add_flow(pool)
base_features=model.FEATURES.copy();base_positive=model.POSITIVE.copy();groups=[]
for year,frame in pool[pool.year<=2026].groupby('year'):
 frame=frame.reset_index(drop=True);votes=model.voting_table(year,'coy');y=frame.coach_id.eq(votes['voting'][0]['id']).to_numpy(float);assert y.sum()==1
 groups.append(dict(year=int(year),g=frame,x=model.design(frame),y=y))
rows=[];coeffs=[]
for variant in ['baseline','learned_flow','hard_exclusions']:
 model.FEATURES=base_features+(FLOW_FEATURES if variant=='learned_flow' else [])
 model.POSITIVE=base_positive|set(FLOW_FEATURES)
 gs=[dict(g,x=np.column_stack([g['x'],g['g'][FLOW_FEATURES].to_numpy(float)])) if variant=='learned_flow' else g for g in groups]
 for g in gs:
  train=[v for v in gs if v['year']<g['year']]
  if not train:continue
  coef=model.fit(train);scores=np.einsum('ij,j->i',g['x'],coef);eligible=np.ones(len(scores),bool)
  if variant=='hard_exclusions':eligible=g['g'].flow_tier.ne('No chance').to_numpy()
  assert eligible.any()
  probs=np.zeros(len(scores));probs[eligible]=softmax(scores[eligible]);order=np.flatnonzero(eligible)[np.argsort(-scores[eligible],kind='stable')]
  ranks=[r for r,i in enumerate(order,1) if g['y'][i]>0];rank=min(ranks) if ranks else None
  winner=g['g'].loc[g['y']>0].iloc[0]
  rows.append(dict(variant=variant,year=g['year'],season=f'{g["year"]-1}-{str(g["year"])[-2:]}',predicted=g['g'].iloc[order[0]].coach,actual=winner.coach,winner_rank=rank,top1=int(rank==1),top3=int(rank is not None and rank<=3),log_loss=float(-np.log(max(probs[g['y']>0].sum(),1e-15))),winner_tier=winner.flow_tier,winner_excluded=rank is None))
  coeffs.extend(dict(variant=variant,year=g['year'],feature=f,coefficient=float(coef[i])) for i,f in enumerate(model.FEATURES))
 model.FEATURES=base_features;model.POSITIVE=base_positive
 print(variant,flush=True)
r=pd.DataFrame(rows);r.to_csv(OUT/'backtests.csv',index=False);pd.DataFrame(coeffs).to_csv(OUT/'coefficients.csv',index=False);pool.to_csv(OUT/'candidate_audit.csv',index=False)
saved=pd.read_csv(OUT/'baseline_backtests.csv');b=r[r.variant=='baseline'];assert b.predicted.tolist()==saved.predicted.tolist();np.testing.assert_allclose(b.log_loss,saved.log_loss,atol=1e-6)
summary=[]
for period,lo in [('all',2002),('expectations_available',2003)]:
 for variant in r.variant.unique():
  a=r[(r.variant==variant)&(r.year>=lo)];summary.append(dict(period=period,variant=variant,seasons=len(a),top1=int(a.top1.sum()),top3=int(a.top3.sum()),log_loss=float(a.log_loss.mean()),winners_excluded=int(a.winner_excluded.sum())))
s=pd.DataFrame(summary);s.to_csv(OUT/'summary.csv',index=False);print(s.to_string(index=False));print(r[r.variant=='baseline'][['season','actual','winner_tier']].to_string(index=False))
