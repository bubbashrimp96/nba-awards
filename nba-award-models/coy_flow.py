"""Coach-of-the-Year reputation/record/expectations flowchart interactions."""
import numpy as np

FLOW_FEATURES=['flow_moderate_or_better','flow_runaway']

def add_flow(frame):
    """Green=yes. Equal to expectations is not 'exceeded'; unknown inputs stay unknown.

    Top-four uses record-based conference rank (ties use average ranks), rather
    than historical division-based playoff seeding. Prior wins are franchise-specific.
    """
    frame=frame.copy()
    known=frame[['conference_rank','prior_coy_same_team','expected_team_wins','team_wins']].notna().all(axis=1)&frame.year.ge(2003)
    top4=frame.conference_rank.le(4)
    new=frame.prior_coy_same_team.eq(0)
    exceeded=frame.team_wins.gt(frame.expected_team_wins)
    runaway=known&top4&new&exceeded
    moderate=known&((top4&~new&exceeded)|(top4&new&~exceeded)|(~top4&new&exceeded))
    frame['flow_tier']=np.select([~known,runaway,moderate],['Unknown','Runaway','Moderate chance'],default='No chance')
    frame['flow_top4_record']=top4.astype(float).where(known)
    frame['flow_exceeded_expectations']=exceeded.astype(float).where(known)
    frame['flow_moderate_or_better']=(moderate|runaway).astype(float)
    frame['flow_runaway']=runaway.astype(float)
    return frame
