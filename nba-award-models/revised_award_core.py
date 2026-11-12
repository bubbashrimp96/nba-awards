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

MIP_TEAM_FEATURES=['team_wins','expected_team_wins','wins_above_expectation','prior_all_star']
MIP_ARCHETYPE_FEATURES=['second_year','allstar_jump_fit','origin_fit']
# Quality = mean of league percentiles of PPG and BPM among players with 250+ minutes (others = 0, fringe).
# Band centres come from the general player population, not from MIP winners:
#   destination = borderline All-Star (25th-percentile All-Star Game player, 1990+), spread = half the All-Star p10-p50 gap
#   origin      = median non-All-Star starter (41+ games, started half), spread = half that group's interquartile range
ALLSTAR_CENTRE,ALLSTAR_SPREAD=0.896,0.06
ORIGIN_CENTRE,ORIGIN_SPREAD=0.673,0.14

def player_quality():
    stats=pd.read_csv(ROOT/'data/basketball_stats.csv',low_memory=False)[['PlayerID','Season','PTS','BPM','MP']].copy()
    stats['year']=stats.Season.str[:4].astype(int)+1
    eligible=stats.MP>=250
    ranks=stats[eligible].groupby('year')[['PTS','BPM']].rank(pct=True)
    stats['quality']=0.0
    stats.loc[eligible,'quality']=ranks.mean(axis=1)
    stats=stats.sort_values(['PlayerID','year'])
    stats['quality_prior']=stats.groupby('PlayerID').quality.shift()
    return stats[['PlayerID','year','quality','quality_prior']]

def band(value,centre,spread):
    return np.exp(-0.5*((np.asarray(value,dtype=float)-centre)/spread)**2)

def prior_all_star():
    """1 if the player appeared in any All-Star Game in an earlier season (AS_G counts games played, so
    injured selections who never played are not captured)."""
    stats=pd.read_csv(ROOT/'data/basketball_stats.csv',usecols=['PlayerID','Season','AS_G'],low_memory=False)
    stats['year']=stats.Season.str[:4].astype(int)+1
    stats=stats.sort_values(['PlayerID','year'])
    seasons=stats.groupby(['PlayerID','year']).AS_G.max().fillna(0).gt(0).astype(int).reset_index()
    seasons['prior_all_star']=seasons.groupby('PlayerID').AS_G.transform(lambda s:s.shift(fill_value=0).cummax())
    return seasons[['PlayerID','year','prior_all_star']]

def expectations():
    data=pd.read_csv(ROOT/'data/preseason_wins/team_expectations.csv')
    return data[['Season','Tm','preseason_win_total','preseason_schedule_games']]

def add_mip_context(data):
    data=data.drop(columns=[c for c in ['prior_all_star','preseason_win_total','preseason_schedule_games','expected_team_wins','wins_above_expectation'] if c in data.columns])
    data=data.merge(expectations(),on=['Season','Tm'],how='left',validate='many_to_one')
    data['expected_team_wins']=data.preseason_win_total*data.schedule_games/data.preseason_schedule_games
    data['wins_above_expectation']=data.team_wins-data.expected_team_wins
    # No market totals before 2002-03: neutral (constant) signal rather than backfilling from actual wins.
    data.loc[data.year<2003,'wins_above_expectation']=0.0
    data.loc[data.year<2003,'expected_team_wins']=0.0
    data=data.merge(prior_all_star(),on=['PlayerID','year'],how='left',validate='many_to_one')
    data['prior_all_star']=data.prior_all_star.fillna(0)
    data=data.drop(columns=[c for c in ['quality','quality_prior'] if c in data.columns])
    data=data.merge(player_quality(),on=['PlayerID','year'],how='left',validate='many_to_one')
    data['second_year']=data.experience.eq(1).astype(float)
    data['allstar_jump_fit']=band(data.quality,ALLSTAR_CENTRE,ALLSTAR_SPREAD)
    data['origin_fit']=band(data.quality_prior,ORIGIN_CENTRE,ORIGIN_SPREAD)
    return data

def features_for(award):
    columns=previous_models()[award]['features'].copy()
    if award=='DPOY':columns=[c for c in columns if c!='DRB']+['team_defensive_rank','team_wins']
    if award=='SMOY':columns+=['conference_seed']
    if award=='MIP':columns=[c for c in columns if c!='availability_exponential']+MIP_TEAM_FEATURES+MIP_ARCHETYPE_FEATURES+['availability_exponential']
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
        if award=='MIP':data=add_mip_context(data)
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
    negative={FEATURE,'ppg_rank_exponential','ws48_rank_exponential','team_defensive_rank','conference_seed','second_year'}
    positive={'wins_above_expectation','team_wins','allstar_jump_fit','origin_fit'}
    bounds=[(None,-1e-8) if c in negative else (0,None) if c in positive else (None,None) for c in columns]
    result=minimize(objective,np.zeros(len(columns)),jac=True,method='L-BFGS-B',bounds=bounds,options={'maxiter':2000,'maxls':50})
    assert result.success and np.isfinite(result.x).all(),result.message
    return result.x
