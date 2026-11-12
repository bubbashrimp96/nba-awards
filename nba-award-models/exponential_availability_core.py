"""Exponential below-85% availability, shared by all five award models."""
import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp,softmax
from award_availability_core import load_namespace as load_other
from mvp_rank_penalties_core import load_namespace as load_mvp

FEATURE='availability_exponential'
GROWTH_FRACTION=.10
FORMULA='expm1(log(2) * shortfall / (0.10 * team_games)) / (log(2) / (0.10 * team_games))'

def exponential_shortfall(shortfall,team_games):
    """Game-equivalent curve; marginal cost doubles each additional 10% season shortfall."""
    rate=np.log(2)/(GROWTH_FRACTION*np.asarray(team_games,dtype=float))
    return np.expm1(rate*np.maximum(0,np.asarray(shortfall,dtype=float)))/rate

def load_namespace(award):
    ns=load_mvp() if award=='MVP' else load_other()
    original_make=ns['make_groups'] if award=='MVP' else ns['groups']
    ns['d'][FEATURE]=exponential_shortfall(ns['d'].games_below_threshold,ns['d'].schedule_games)
    def make_groups(columns):
        source_columns=['games_below_threshold' if c==FEATURE else c for c in columns]
        result=original_make(source_columns) if award=='MVP' else original_make(award)
        index=columns.index(FEATURE)
        for group in result:
            group['g']=group['g'].copy()
            values=exponential_shortfall(group['g'].games_below_threshold,group['g'].schedule_games)
            group['g'][FEATURE]=values
            group['x'][:,index]=values
            assert np.isfinite(group['x']).all()
        return result
    ns['make_groups']=make_groups
    ns['fit']=fit
    return ns

def fit(groups,half,regularization,columns):
    latest=max(group['year'] for group in groups)
    weights=np.array([2**(-(latest-group['year'])/half) for group in groups]);weights/=weights.sum()
    def objective(coefficients):
        loss=regularization*np.dot(coefficients,coefficients)/2;gradient=regularization*coefficients
        for group,weight in zip(groups,weights):
            scores=np.einsum('ij,j->i',group['x'],coefficients)
            loss+=weight*(logsumexp(scores)-group['y']@scores)
            gradient=gradient+weight*np.einsum('ij,i->j',group['x'],softmax(scores)-group['y'])
        return loss,gradient
    bounds=[(None,-1e-8) if feature in (FEATURE,'ppg_places_below_fifth','ws48_places_below_fifth','ppg_rank_exponential','ws48_rank_exponential') else (0,None) if feature=='wins_above_expectation' else (None,None) for feature in columns]
    result=minimize(objective,np.zeros(len(columns)),jac=True,method='L-BFGS-B',bounds=bounds,options={'maxiter':2000,'maxls':50})
    assert result.success and np.isfinite(result.x).all(),result.message
    return result.x
