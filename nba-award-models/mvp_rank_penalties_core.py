"""MVP qualification and raw-place penalties using Basketball Reference source flags."""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import logsumexp, softmax
from mvp_expectations_core import load_namespace as load_previous

ROOT = Path(__file__).resolve().parent
PENALTY_FEATURES = ('games_below_threshold','ppg_places_below_fifth','ws48_places_below_fifth')

def load_namespace():
    namespace = load_previous()
    data = namespace['d']
    ranks = pd.read_csv(ROOT / 'data/qualified_ranks/qualified_ranks.csv')
    for stat in ('ppg','ws48'):
        source = ranks[ranks.stat == stat][['Season','PlayerID','qualified','rank','qualified_count']]
        source = source.rename(columns={column:stat+'_'+column for column in ('qualified','rank','qualified_count')})
        data = data.merge(source,on=['Season','PlayerID'],how='left',validate='one_to_one')
        assert data[stat+'_qualified'].notna().all(), (stat,data.loc[data[stat+'_qualified'].isna(),['Season','PlayerID']].to_dict('records'))
        # Ranks are among the entire qualified league, before MVP screening.
        data[stat+'_places_below_fifth'] = (data[stat+'_rank'] - 5).clip(lower=0)
    data['mvp_rate_qualified'] = data.ppg_qualified & data.ws48_qualified
    namespace['rank_audit'] = data.copy()
    data = data[data.mvp_rate_qualified].copy()
    namespace['d'] = data

    def make_groups(columns):
        groups = []
        for year, frame in data.groupby('year'):
            labels = namespace['labels'][namespace['labels'].year == year]
            if labels.empty:
                continue
            target = frame.name_key.isin(labels.name_key).to_numpy(float)
            assert target.sum() == len(labels), ('Winner excluded',year,labels.player.tolist())
            target /= target.sum()
            raw = frame[columns].to_numpy(float)
            raw = np.where(np.isnan(raw),np.nanmedian(raw,axis=0),raw)
            sd = raw.std(axis=0)
            sd[sd < 1e-8] = 1
            design = (raw-raw.mean(axis=0))/sd
            for feature in PENALTY_FEATURES:
                if feature in columns:
                    index = columns.index(feature)
                    design[:,index] = raw[:,index]
            assert np.isfinite(design).all()
            groups.append(dict(year=int(year),g=frame,x=design,y=target))
        return groups

    def fit(groups,half,regularization,columns,constrained=False):
        latest = max(group['year'] for group in groups)
        weights = np.array([2**(-(latest-group['year'])/half) for group in groups])
        weights /= weights.sum()
        def objective(coefficients):
            loss = regularization*np.dot(coefficients,coefficients)/2
            gradient = regularization*coefficients
            for group,weight in zip(groups,weights):
                scores = np.einsum('ij,j->i',group['x'],coefficients)
                loss += weight*(logsumexp(scores)-group['y']@scores)
                gradient = gradient+weight*np.einsum('ij,i->j',group['x'],softmax(scores)-group['y'])
            return loss,gradient
        bounds = [(None,-1e-8) if feature in PENALTY_FEATURES else (0,None) if feature=='wins_above_expectation' else (None,None) for feature in columns]
        result = minimize(objective,np.zeros(len(columns)),jac=True,method='L-BFGS-B',bounds=bounds)
        assert result.success and np.isfinite(result.x).all(),result.message
        return result.x

    namespace['make_groups'] = make_groups
    namespace['fit'] = fit
    return namespace
