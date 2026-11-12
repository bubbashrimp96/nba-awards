"""MVP exponential PPG and WS/48 rank penalties, with exponential availability retained."""
import numpy as np
from exponential_availability_core import load_namespace as load_previous,exponential_shortfall,fit

RANK_FEATURES={'ppg_rank_exponential':'ppg','ws48_rank_exponential':'ws48'}

def rank_curve(rank,qualified_count):
    """Same field-normalized curve as availability; zero through fifth place."""
    return exponential_shortfall(np.maximum(0,np.asarray(rank,dtype=float)-5),qualified_count)

def load_namespace():
    ns=load_previous('MVP')
    original_make=ns['make_groups']
    for feature,stat in RANK_FEATURES.items():
        ns['d'][feature]=rank_curve(ns['d'][stat+'_rank'],ns['d'][stat+'_qualified_count'])
    def make_groups(columns):
        source_columns=[RANK_FEATURES[c]+'_places_below_fifth' if c in RANK_FEATURES else c for c in columns]
        groups=original_make(source_columns)
        for group in groups:
            for feature,stat in RANK_FEATURES.items():
                index=columns.index(feature)
                values=rank_curve(group['g'][stat+'_rank'],group['g'][stat+'_qualified_count'])
                group['g'][feature]=values
                group['x'][:,index]=values
            assert np.isfinite(group['x']).all()
        return groups
    ns['make_groups']=make_groups
    ns['fit']=fit
    return ns
