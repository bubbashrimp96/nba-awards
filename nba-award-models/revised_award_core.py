"""Gentler near-threshold availability, sharper MVP scoring ranks, and team context."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import logsumexp,softmax
from exponential_availability_core import load_namespace as load_other,FEATURE
from mvp_exponential_rank_core import load_namespace as load_mvp
ROOT=Path(__file__).resolve().parent
AVAILABILITY_GROWTH=.10
PPG_GROWTH=.05
WS48_GROWTH=.10

def availability_curve(shortfall,team_games):
    rate=np.log(2)/(AVAILABILITY_GROWTH*np.asarray(team_games,dtype=float))
    scaled=rate*np.maximum(0,np.asarray(shortfall,dtype=float))
    return (np.expm1(scaled)-scaled)/rate

def rank_curve(rank,qualified_count,stat='ppg'):
    fraction=PPG_GROWTH if stat=='ppg' else WS48_GROWTH
    rate=np.log(2)/(fraction*np.asarray(qualified_count,dtype=float))
    return np.expm1(rate*np.maximum(0,np.asarray(rank,dtype=float)-5))/rate

def previous_models():
    result=json.loads((ROOT/'exponential_availability/models.json').read_text())
    result['MVP']=json.loads((ROOT/'mvp_exponential_rank_penalties/model.json').read_text())
    return result

def team_context():
    standings=pd.read_csv(ROOT/'conference_standings/team_standings.csv')
    defense=pd.read_csv(ROOT/'data/team_defense/team_defense.csv')
    result=standings.merge(defense[['Season','Tm','team_defensive_rating','team_defensive_rank']],on=['Season','Tm'],validate='one_to_one')
    reported=result.source_playoff_seed_not_used
    valid=reported.between(1,result.conference_size)&result.year.ne(2000)
    result['conference_seed']=reported.where(valid,result.conference_rank)
    result['seed_fallback']=~valid
    return result

def features_for(award):
    columns=previous_models()[award]['features'].copy()
    if award=='DPOY':columns=[c for c in columns if c!='DRB']+['team_defensive_rank','team_wins']
    if award=='SMOY':columns+=['conference_seed']
    return columns

def load_namespace(award):
    ns=load_mvp() if award=='MVP' else load_other(award)
    previous=previous_models()[award]
    original_make=ns['make_groups']
    source_groups=original_make(previous['features'])
    context=team_context()
    def enrich(data):
        additions=[c for c in ['team_wins','team_defensive_rating','team_defensive_rank','conference_seed','seed_fallback'] if c not in data.columns]
        data=data.merge(context[['Season','Tm',*additions]],on=['Season','Tm'],how='left',validate='many_to_one')
        data[FEATURE]=availability_curve(data.games_below_threshold,data.schedule_games)
        if award=='MVP':
            for stat in ('ppg','ws48'):data[stat+'_rank_exponential']=rank_curve(data[stat+'_rank'],data[stat+'_qualified_count'],stat)
        return data
    ns['d']=enrich(ns['d'])
    def make_groups(columns):
        result=[]
        for source in source_groups:
            frame=enrich(source['g'])
            assert frame.PlayerID.tolist()==source['g'].PlayerID.tolist()
            raw=frame[columns].to_numpy(float)
            raw=np.where(np.isnan(raw),np.nanmedian(raw,axis=0),raw)
            scale=raw.std(axis=0);scale[scale<1e-8]=1
            design=(raw-raw.mean(axis=0))/scale
            for term in (FEATURE,'ppg_rank_exponential','ws48_rank_exponential'):
                if term in columns:design[:,columns.index(term)]=raw[:,columns.index(term)]
            assert np.isfinite(design).all()
            result.append(dict(source,g=frame,x=design))
        return result
    ns['make_groups']=make_groups;ns['fit']=fit
    return ns

def fit(groups,half,regularization,columns):
    latest=max(g['year'] for g in groups)
    weights=np.array([2**(-(latest-g['year'])/half) for g in groups]);weights/=weights.sum()
    def objective(coef):
        loss=regularization*np.dot(coef,coef)/2;gradient=regularization*coef
        for group,weight in zip(groups,weights):
            scores=np.einsum('ij,j->i',group['x'],coef)
            loss+=weight*(logsumexp(scores)-group['y']@scores)
            gradient=gradient+weight*np.einsum('ij,i->j',group['x'],softmax(scores)-group['y'])
        return loss,gradient
    negative={FEATURE,'ppg_rank_exponential','ws48_rank_exponential','team_defensive_rank','conference_seed'}
    positive={'wins_above_expectation','team_wins'}
    bounds=[(None,-1e-8) if c in negative else (0,None) if c in positive else (None,None) for c in columns]
    result=minimize(objective,np.zeros(len(columns)),jac=True,method='L-BFGS-B',bounds=bounds,options={'maxiter':2000,'maxls':50})
    assert result.success and np.isfinite(result.x).all(),result.message
    return result.x
