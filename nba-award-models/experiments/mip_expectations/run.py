"""Exploratory published-preseason projection backtest; production untouched."""
from pathlib import Path
import json,sys
import numpy as np
import pandas as pd
from scipy.special import softmax
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from revised_award_core import load_namespace,features_for,fit
OUT=Path(__file__).resolve().parent
ns=load_namespace('MIP');columns=features_for('MIP');groups=ns['make_groups'](columns);stats=ns['d'];key=ns['key']
settings=json.loads((ROOT/'revised_awards/models.json').read_text())['MIP']
aliases={'Shai Gilgeous':'Shai Gilgeous-Alexander','Michael Porter':'Michael Porter Jr.','Otto Porter':'Otto Porter Jr.','Larry Nance':'Larry Nance Jr.','Enes Kanter':'Enes Freedom','Marvin Bagley':'Marvin Bagley III','Robert Willliams':'Robert Williams','Spencer Dinwiddle':'Spencer Dinwiddie','Moe Harkless':'Maurice Harkless','Danuel House':'Danuel House Jr.','Derrick Jones':'Derrick Jones Jr.','Tyrese Halibutron':'Tyrese Haliburton','Nicolas Claxton':'Nic Claxton','Danilo Galinari':'Danilo Gallinari','Herb Jones':'Herbert Jones','Jabari Smith':'Jabari Smith Jr.'}
# Resolve identities using all years, including injured players with no season row.
identities=stats[['name_key','PlayerID']].drop_duplicates();ids=identities.groupby('name_key').PlayerID.agg(list)
forecasts=[];unmatched=[]
urls={2020:'fantasy-basketball-top-155-roto-projections-for-2019',2021:'2020-2021-top-155-roto-projections-for-fantasy-basketball',2022:'2021-22-top-155-roto-projections',2023:'2022-23-top-155-roto-projections'}
for year in range(2020,2024):
 rows=json.loads((OUT/f'raw_{year}.json').read_text());assert len(rows)==155 and {r[0] for r in rows}==set(range(1,156))
 for row in rows:
  assert len(row)==14,(year,row)
  name=aliases.get(row[1],row[1]);matches=ids.get(key(name),[])
  if len(matches)!=1:unmatched.append(dict(year=year,name=row[1],resolved=name,matches=matches));continue
  values=[float(str(v).replace('%','').replace('−','-')) for v in row[2:]]
  forecasts.append(dict(year=year,PlayerID=matches[0],published_name=row[1],expected_PTS=values[1],expected_TRB=values[3],expected_AST=values[4],expected_STL=values[5],expected_BLK=values[6],source='https://basketball.razzball.com/'+urls[year]+'/'))
pd.DataFrame(unmatched).to_json(OUT/'unmatched.json',orient='records',indent=2)
assert not unmatched,unmatched
f=pd.DataFrame(forecasts);assert not f.duplicated(['year','PlayerID']).any();f.to_csv(OUT/'forecasts.csv',index=False)
extra=['surprise_PTS','surprise_AST','surprise_TRB'];coverage=[];audit=[];enriched=[]
for source in groups:
 frame=source['g'].merge(f,on=['year','PlayerID'],how='left',validate='one_to_one');assert frame.PlayerID.tolist()==source['g'].PlayerID.tolist()
 for stat in ['PTS','AST','TRB']:frame['surprise_'+stat]=frame[stat]-frame['expected_'+stat]
 available=frame.expected_PTS.notna().to_numpy();z=np.zeros((len(frame),3))
 if available.any() and available[source['y']>0].all():
  raw=frame.loc[available,extra].to_numpy(float);sd=raw.std(axis=0);sd[sd<1e-8]=1;z[available]=(raw-raw.mean(axis=0))/sd
 # Missing publications/candidates have zero standardized surprise (neutral),
 # not invented expected stats. Scores compared only on matched forecast coverage.
 enriched.append(dict(source,g=frame,z=z,available=available))
 if source['year'] in urls:
  eligible=frame.PTS.ge(13);covered=eligible&available
  votes=json.loads((ROOT/f'data/award_voting/{source["year"]}.json').read_text())['MIP']['voting'];vote_keys={key(v['player']) for v in votes}
  missing=frame.loc[eligible&~available,'Player Name'].tolist()
  coverage.append(dict(year=source['year'],published=155,eligible=int(eligible.sum()),covered=int(covered.sum()),coverage=float(covered.sum()/eligible.sum()),winner_covered=bool(available[source['y']>0].all()),missing_candidates=' / '.join(missing),voted_players=len(vote_keys),voted_with_projection=sum(k in set(frame.loc[available,'name_key']) for k in vote_keys)))
  audit.append(frame[['year','PlayerID','Player Name','PTS','AST','TRB','expected_PTS','expected_AST','expected_TRB',*extra]])
variants={'baseline':([],[]),'add_expected_points':(extra[:1],[]),'add_expected_points_rebounds_assists':(extra,[]),'replace_previous_year_deltas':(extra,['delta_PTS','delta_AST','delta_TRB'])}
rows=[];coefs=[]
for variant,(add,remove) in variants.items():
 features=[c for c in columns if c not in remove]+add;gs=[]
 for source in enriched:
  keep=[i for i,c in enumerate(columns) if c not in remove];zi=[extra.index(c) for c in add]
  gs.append(dict(source,x=np.column_stack([source['x'][:,keep],source['z'][:,zi]])))
 for group in gs:
  year=group['year']
  if year not in urls:continue
  train=[g for g in gs if g['year']<year];coef=fit(train,settings['half_life'],settings['regularization'],features)
  eligible=group['g'].PTS.ge(13).to_numpy()
  for scope,mask in [('matched_forecasts',eligible & group['available']),('full_pool_neutral_missing',eligible)]:
   frame=group['g'].loc[mask];target=group['y'][mask]
   if target.sum()==0:continue # Coverage failure: cannot evaluate a winner excluded from every compared pool.
   scores=np.einsum('ij,j->i',group['x'][mask],coef);prob=softmax(scores);order=np.argsort(-scores,kind='stable');rank=min(i for i,j in enumerate(order,1) if target[j]>0)
   rows.append(dict(scope=scope,variant=variant,year=year,season=frame.Season.iloc[0],predicted=frame.iloc[order[0]]['Player Name'],actual=' / '.join(frame.loc[target>0,'Player Name']),winner_rank=rank,top1=int(rank==1),top3=int(rank<=3),log_loss=float(-np.log(prob[target>0].sum())),training_forecast_seasons=sum(g['year'] in urls and g['available'][g['y']>0].all() for g in train)))
  coefs.extend(dict(variant=variant,year=year,feature=c,coefficient=float(coef[features.index(c)])) for c in add)
 print(variant,flush=True)
r=pd.DataFrame(rows);r.to_csv(OUT/'backtests.csv',index=False);pd.DataFrame(coverage).to_csv(OUT/'coverage.csv',index=False);pd.concat(audit).to_csv(OUT/'feature_audit.csv',index=False);pd.DataFrame(coefs).to_csv(OUT/'coefficients.csv',index=False)
# Reproduce deployed predictions on its full eligible pool as an independent baseline check.
active=pd.read_csv(ROOT/'dashboard_backtests.csv');active=active[active.award=='MIP']
full=[]
for group in groups:
 if group['year'] not in urls:continue
 coef=fit([g for g in groups if g['year']<group['year']],settings['half_life'],settings['regularization'],columns);mask=group['g'].PTS.ge(13).to_numpy();frame=group['g'].loc[mask];target=group['y'][mask];scores=np.einsum('ij,j->i',group['x'][mask],coef);order=np.argsort(-scores,kind='stable');prob=softmax(scores)
 assert frame.iloc[order[0]]['Player Name']==active[active.season==frame.Season.iloc[0]].iloc[0].predicted
 full.append(dict(year=group['year'],predicted=frame.iloc[order[0]]['Player Name'],log_loss=float(-np.log(prob[target>0].sum()))))
pd.DataFrame(full).to_csv(OUT/'full_baseline_check.csv',index=False)
summary=[]
for scope in r.scope.unique():
 for period,lo in [('four_archive_years',2020),('two_with_usable_prior_forecast_training',2022)]:
  for variant in variants:
   a=r[(r.scope==scope)&(r.variant==variant)&(r.year>=lo)]
   summary.append(dict(scope=scope,period=period,variant=variant,seasons=len(a),top1=int(a.top1.sum()),top3=int(a.top3.sum()),log_loss=float(a.log_loss.mean())))
s=pd.DataFrame(summary);s.to_csv(OUT/'summary.csv',index=False)
print(pd.DataFrame(coverage).drop(columns='missing_candidates').to_string(index=False));print(s.to_string(index=False));print(r.to_string(index=False))
