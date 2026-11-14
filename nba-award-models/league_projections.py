"""Conference standings and transparent statistical All-Star projections."""
import math
import numpy as np
import pandas as pd

WEIGHTS={'PTS':.30,'BPM':.25,'WS/48':.15,'AST':.10,'TRB':.10,'availability':.05,'team_record':.05}
SOURCE_LABELS={'sportsbook_win_totals':'Sportsbook win totals','bbref_projection':'Basketball Reference projection','pace':'Current-record pace'}
CONFERENCES=('Eastern','Western')

def number(value):
    try:value=float(value)
    except (ValueError,TypeError):return None
    return value if math.isfinite(value) else None

def standings(teams,names=None):
    names=names or {};result={}
    assert teams.Tm.is_unique and len(teams)==30,'Standings require all 30 teams'
    for conference in CONFERENCES:
        pool=teams[teams.conference==conference].copy()
        assert len(pool)==15,(conference,len(pool))
        pool['current_pct']=pool.wins_to_date/pool.games_to_date.replace(0,np.nan)
        current=pool.sort_values(['current_pct','wins_to_date','Tm'],ascending=[False,False,True],na_position='last')
        current_ranks={tm:i for i,tm in enumerate(current.Tm,1)}
        pool=pool.sort_values(['team_wins','current_pct','Tm'],ascending=[False,False,True],na_position='last')
        rows=[]
        for seed,(_,team) in enumerate(pool.iterrows(),1):
            wins=float(team.team_wins)
            assert 0<=wins<=82,(team.Tm,wins)
            rows.append(dict(seed=seed,team=team.Tm,name=names.get(team.Tm,team.Tm),wins=int(team.wins_to_date),losses=int(team.losses_to_date),
                             games_played=int(team.games_to_date),current_rank=current_ranks[team.Tm],seed_change=current_ranks[team.Tm]-seed,
                             projected_wins=wins,projected_losses=82-wins,projected_win_pct=wins/82,
                             source=team.team_wins_source,source_label=SOURCE_LABELS.get(team.team_wins_source,team.team_wins_source),
                             zone='Top six' if seed<=6 else 'Play-in range' if seed<=10 else 'Outside top ten'))
        result[conference]=rows
    return dict(conferences=result,method='Ranked by the same projected final wins used in the award models: sportsbook win totals first, Basketball Reference projected records second, current record pace last. Ties use current win percentage then team code; these are not official NBA tiebreakers.')

def allstars(stats,teams,names=None,current_teams=None):
    names=names or {};current_teams=current_teams or {}
    frame=stats.copy()
    assert frame.PlayerID.is_unique,'All-Star candidates must have unique player IDs'
    frame['Tm']=frame.apply(lambda row:row.Tm if row.Tm in set(teams.Tm) else current_teams.get(row.PlayerID,row.Tm),axis=1)
    frame=frame.merge(teams[['Tm','conference','team_wins','wins_to_date','losses_to_date']],on='Tm',how='left',validate='many_to_one')
    frame['availability']=(frame.games_to_date/frame.team_games_to_date.replace(0,np.nan)).clip(0,1)
    frame['mpg']=frame.MP/frame.G.replace(0,np.nan)
    frame=frame[frame.conference.isin(CONFERENCES)&frame.games_to_date.ge(5)&frame.availability.ge(.4)&frame.mpg.ge(15)].copy()
    imputed={}
    for metric in ['PTS','AST','TRB','BPM','WS/48']:
        values=pd.to_numeric(frame[metric],errors='coerce').replace([np.inf,-np.inf],np.nan)
        imputed[metric]=set(frame.loc[values.isna(),'PlayerID'])
        values=values.fillna(values.median() if values.notna().any() else 0.)
        frame[metric+'_percentile']=values.rank(method='average',pct=True)
    team_win_pct=teams.wins_to_date/(teams.wins_to_date+teams.losses_to_date).replace(0,np.nan)
    team_percentiles=pd.Series(team_win_pct.to_numpy(),index=teams.Tm).rank(method='average',pct=True)
    frame['team_record_percentile']=frame.Tm.map(team_percentiles).fillna(.5)
    frame['availability_percentile']=frame.availability
    frame['selection_score']=sum(frame[metric+'_percentile']*weight for metric,weight in WEIGHTS.items())*100
    frame=frame.sort_values(['selection_score','PTS','PlayerID'],ascending=[False,False,True],kind='stable')
    conferences={}
    for conference in CONFERENCES:
        pool=frame[frame.conference==conference]
        rows=[]
        for rank,(_,player) in enumerate(pool.head(17).iterrows(),1):
            rows.append(dict(rank=rank,player_id=player.PlayerID,player=player['Player Name'],team=player.Tm,team_name=names.get(player.Tm,player.Tm),
                             position=str(player.get('Pos','')),selection_score=round(float(player.selection_score),2),
                             games_played=int(player.games_to_date),team_games_played=int(player.team_games_to_date),minutes_per_game=number(player.mpg),
                             points=number(player.PTS),rebounds=number(player.TRB),assists=number(player.AST),bpm=number(player.BPM),ws48=number(player['WS/48']),
                             team_wins_to_date=int(player.wins_to_date),team_losses_to_date=int(player.losses_to_date),
                             team_win_pct=number(player.wins_to_date/(player.wins_to_date+player.losses_to_date)) if player.wins_to_date+player.losses_to_date else None,
                             projected_team_wins=number(player.team_wins),availability=number(player.availability),
                             imputed_inputs=[metric for metric,players in imputed.items() if player.PlayerID in players]))
        conferences[conference]=dict(starters=rows[:5],bench=rows[5:12],honourable_mentions=rows[12:17],eligible_pool=len(pool))
    return dict(conferences=conferences,weights=WEIGHTS,
                eligibility='At least 5 games played, 40% of the team’s games, and 15 minutes per game so far.',
                method='A statistical selection score, not a fitted voting probability: 30% scoring, 25% BPM, 15% WS/48, 10% assists, 10% rebounds, 5% availability and 5% current team record (win percentage). Player performance inputs use league-wide eligible-player percentiles; current team win percentage is ranked across all 30 teams; availability is the fraction of team games played. Five highest scores are starters, the next seven form the bench, and the next five are honourable mentions. No positional quotas are imposed. Missing rate inputs use the eligible-pool median. Fan/player/media voting, injuries and event-team assignments are not predicted.')
