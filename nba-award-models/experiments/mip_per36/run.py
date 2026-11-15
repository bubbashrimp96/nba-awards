"""Offline MIP per-36 improvement ablation; active model files are untouched."""
from pathlib import Path
import json,sys
import numpy as np
import pandas as pd
from scipy.special import softmax
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from revised_award_core import load_namespace,features_for,fit
OUT=Path(__file__).resolve().parent
ns=load_namespace('MIP');columns=features_for('MIP');groups=ns['make_groups'](columns)
settings=json.loads((ROOT/'revised_awards/models.json').read_text())['MIP']
stats=pd.read_csv(ROOT/'data/basketball_stats.csv',low_memory=False).sort_values(['PlayerID','Season'])
stats['year']=stats.Season.str[:4].astype(int)+1
adjacent=stats.groupby('PlayerID').year.shift().eq(stats.year-1)
terms=['PTS','AST','TRB','STL','BLK']
for term in terms:
    col=term+'_36'
    stats['delta_'+col]=(stats[col]-stats.groupby('PlayerID')[col].shift()).where(adjacent)
extra=['delta_'+t+'_36' for t in terms]
variants={'baseline':([],[]),'add_points_per36':(extra[:1],[]),'add_points_rebounds_assists_per36':(extra[:3],[]),'add_five_per36':(extra,[]),'replace_per_game_deltas':(extra[:3],['delta_PTS','delta_AST','delta_TRB'])}
audit=[];by_variant={k:[] for k in variants}
for source in groups:
    frame=source['g'].merge(stats[['PlayerID','year',*extra]],on=['PlayerID','year'],how='left',validate='one_to_one')
    assert frame.PlayerID.tolist()==source['g'].PlayerID.tolist()
    for key,(add,remove) in variants.items():
        keep=[i for i,c in enumerate(columns) if c not in remove]
        raw=frame[add].to_numpy(float) if add else np.empty((len(frame),0))
        if add:
            raw=np.where(np.isnan(raw),np.nanmedian(raw,axis=0),raw)
            sd=raw.std(axis=0);sd[sd<1e-8]=1
            raw=(raw-raw.mean(axis=0))/sd
        x=np.column_stack([source['x'][:,keep],raw]);assert np.isfinite(x).all()
        by_variant[key].append(dict(source,g=frame,x=x))
    if source['year']>=2001:
        a=frame[['PlayerID','Player Name','Season','PTS',*extra]].copy();audit.append(a)
rows=[];coefficients=[]
for key,gs in by_variant.items():
    add,remove=variants[key];features=[c for c in columns if c not in remove]+add
    for group in gs:
        year=group['year']
        if year<2001:continue
        train=[g for g in gs if g['year']<year]
        coef=fit(train,settings['half_life'],settings['regularization'],features)
        scores=np.einsum('ij,j->i',group['x'],coef)
        # Same production rule: preserve training and standardization pools,
        # then exclude current-season PPG below 13 for ranking and shares.
        eligible=group['g'].PTS.ge(13).to_numpy();frame=group['g'].loc[eligible];scores=scores[eligible];target=group['y'][eligible]
        prob=softmax(scores);order=np.argsort(-scores,kind='stable');rank=min(i for i,j in enumerate(order,1) if target[j]>0)
        top=frame.iloc[order[:3]]['Player Name'].tolist()
        voting=json.loads((ROOT/f'data/award_voting/{year}.json').read_text())['MIP']
        actual={ns['key'](p['player']) for p in voting['results'] if p['rank']<=3}
        overlap=len({ns['key'](p) for p in top}&actual)/len(actual)
        rows.append(dict(variant=key,year=year,season=frame.Season.iloc[0],predicted=top[0],top3_players=' / '.join(top),actual=' / '.join(frame.loc[target>0,'Player Name']),top1=int(rank==1),top3=int(rank<=3),winner_rank=rank,overlap=overlap,log_loss=float(-np.log(prob[target>0].sum()))))
        coefficients.extend(dict(variant=key,year=year,feature=c,coefficient=float(coef[features.index(c)])) for c in add)
    print(key,flush=True)
r=pd.DataFrame(rows);r.to_csv(OUT/'backtests.csv',index=False);pd.concat(audit).to_csv(OUT/'feature_audit.csv',index=False);pd.DataFrame(coefficients).to_csv(OUT/'coefficients.csv',index=False)
b=r[r.variant=='baseline'].sort_values('year');active=pd.read_csv(ROOT/'dashboard_backtests.csv');active=active[active.award=='MIP'].sort_values('season')
assert b.predicted.tolist()==active.predicted.tolist()
np.testing.assert_allclose(b.log_loss,active.log_loss,atol=1e-6)
summary=[]
for period,lo,hi in [('all_2001_2026',2001,2026),('earlier_2001_2015',2001,2015),('later_2016_2026',2016,2026)]:
 for key in variants:
    a=r[(r.variant==key)&r.year.between(lo,hi)];weights=2**(-(hi-a.year)/5);weights/=weights.sum()
    accuracy=100*float((weights*(.5*a.top1+.25*a.top3+.25*a.overlap)).sum())
    summary.append(dict(period=period,variant=key,seasons=len(a),top1=int(a.top1.sum()),top3=int(a.top3.sum()),log_loss=float(a.log_loss.mean()),accuracy=accuracy))
s=pd.DataFrame(summary);s.to_csv(OUT/'summary.csv',index=False)
changes=r.merge(b[['year','predicted','winner_rank','log_loss']],on='year',suffixes=('','_baseline'));changes[changes.predicted!=changes.predicted_baseline].to_csv(OUT/'changed_picks.csv',index=False)
(OUT/'method.json').write_text(json.dumps(dict(formula='This season per-36 minus immediately previous season per-36. Cached per-36 columns; player-ID match; gaps remain missing, filled by candidate-season median.',variants=variants,half_life=settings['half_life'],regularization=settings['regularization'],baseline_reproduced=True,eligibility='13 PPG ranking cutoff retained; original training candidate pools retained.',warning='Retrospective comparison of five predefined variants. Chronological splits are diagnostic, not untouched validation.'),indent=2)+'\n')
print(s.to_string(index=False))
