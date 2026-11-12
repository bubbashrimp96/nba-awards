"""Availability preprocessing and constrained fitting for non-MVP award models."""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import logsumexp,softmax

ROOT=Path(__file__).resolve().parent
AWARDS=('ROY','DPOY','MIP','SMOY')

def load_namespace():
    ns={'__file__':str(ROOT/'model.py')}
    exec((ROOT/'model.py').read_text().split('summary=[]; backtests=[];')[0],ns)
    teams=pd.read_csv(ROOT/'conference_standings/team_standings.csv')
    data=ns['d'].merge(teams[['Season','Tm','team_games']],on=['Season','Tm'],how='left',validate='many_to_one')
    season_max=teams.groupby('Season').team_games.max()
    data['schedule_fallback']=data.team_games.isna()
    data['schedule_games']=data.team_games.fillna(data.Season.map(season_max))
    data['availability_threshold']=np.ceil(.85*data.schedule_games)
    data['games_below_threshold']=np.maximum(0,data.availability_threshold-data.G)
    assert data.loc[data.year>=1986,'schedule_games'].notna().all()
    ns['d']=data
    for award in AWARDS:
        ns['features'][award]=ns['features'][award]+['games_below_threshold']
    original_groups=ns['groups']
    def groups(award):
        result=original_groups(award)
        for group in result:
            index=ns['features'][award].index('games_below_threshold')
            group['x'][:,index]=group['g'].games_below_threshold.to_numpy(float)
        return result
    ns['groups']=groups
    ns['fit']=fit
    return ns

def fit(groups,half,regularization,columns):
    latest=max(group['year'] for group in groups)
    weights=np.array([2**(-(latest-group['year'])/half) for group in groups])
    weights/=weights.sum()
    def objective(coefficients):
        loss=regularization*np.dot(coefficients,coefficients)/2
        gradient=regularization*coefficients
        for group,weight in zip(groups,weights):
            scores=np.einsum('ij,j->i',group['x'],coefficients)
            loss+=weight*(logsumexp(scores)-group['y']@scores)
            gradient=gradient+weight*np.einsum('ij,i->j',group['x'],softmax(scores)-group['y'])
        return loss,gradient
    bounds=[(None,-1e-8) if feature=='games_below_threshold' else (None,None) for feature in columns]
    result=minimize(objective,np.zeros(len(columns)),jac=True,method='L-BFGS-B',bounds=bounds)
    assert result.success and np.isfinite(result.x).all(),result.message
    return result.x
