"""Cache regular-season NBA Stats defensive ratings; archive fallback for pre-1997 training."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib,io,json,re
import pandas as pd
import requests

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'data/team_defense';OUT.mkdir(exist_ok=True)
ARCHIVE='https://raw.githubusercontent.com/ramvibhakar/basketball-analytics/master/data/team_stats.csv'
NBA_ARCHIVE='https://github.com/sportsdataverse/sportsdataverse-data/releases/download/nba_stats_team_season_stats/team_season_stats_{year}.parquet'
NAME_CODES={'Atlanta Hawks':'ATL','Boston Celtics':'BOS','Brooklyn Nets':'BRK','New Jersey Nets':'NJN','Charlotte Bobcats':'CHA','Chicago Bulls':'CHI','Cleveland Cavaliers':'CLE','Dallas Mavericks':'DAL','Denver Nuggets':'DEN','Detroit Pistons':'DET','Golden State Warriors':'GSW','Houston Rockets':'HOU','Indiana Pacers':'IND','Los Angeles Clippers':'LAC','LA Clippers':'LAC','Los Angeles Lakers':'LAL','Memphis Grizzlies':'MEM','Vancouver Grizzlies':'VAN','Miami Heat':'MIA','Milwaukee Bucks':'MIL','Minnesota Timberwolves':'MIN','New Orleans Hornets':'NOH','New Orleans/Oklahoma City Hornets':'NOK','New Orleans Pelicans':'NOP','New York Knicks':'NYK','Oklahoma City Thunder':'OKC','Orlando Magic':'ORL','Philadelphia 76ers':'PHI','Phoenix Suns':'PHO','Portland Trail Blazers':'POR','Sacramento Kings':'SAC','San Antonio Spurs':'SAS','Seattle SuperSonics':'SEA','Toronto Raptors':'TOR','Utah Jazz':'UTA','Washington Bullets':'WSB','Washington Wizards':'WAS'}
def code(name,year):
    name=name.rstrip('*').strip()
    if name=='Charlotte Hornets':return 'CHH' if year<=2002 else 'CHO'
    return NAME_CODES[name]
def cache(url,path):
    if not path.exists():
        r=requests.get(url,timeout=40);r.raise_for_status();path.write_bytes(r.content)
    return path.read_bytes()
def current(year):
    url=NBA_ARCHIVE.format(year=year);raw=cache(url,OUT/f'nba_stats_{year}.parquet')
    data=pd.read_parquet(io.BytesIO(raw))
    data=data[(data.season_type.isin(['regular-season','regular_season']))&(data.measure_type=='advanced')&(data.per_mode=='pergame')].copy()
    assert len(data)==30 if year>=2005 else len(data)==29,(year,len(data))
    data['Tm']=[code(name,year) for name in data.team_name]
    data=data.rename(columns={'def_rating':'team_defensive_rating','def_rating_rank':'team_defensive_rank','w':'source_wins','l':'source_losses'})
    data['year']=year;data['Season']=f'{year-1}-{str(year)[-2:]}'
    data['source']=f'https://www.nba.com/stats/teams/advanced?Season={year-1}-{str(year)[-2:]}&SeasonType=Regular%20Season'
    data['provider']='NBA Stats via sportsdataverse archive'
    return data[['Season','year','Tm','team_defensive_rating','team_defensive_rank','source_wins','source_losses','source','provider']],dict(year=year,url=url,sha256=hashlib.sha256(raw).hexdigest())

if __name__=='__main__':
    raw=cache(ARCHIVE,OUT/'historical_team_stats.csv');old=pd.read_csv(io.BytesIO(raw));old['year']=old.Season.str[:4].astype(int)+1
    old=old[(old.year>=1986)&(old.year<=1996)&old.Lg.eq('NBA')].copy()
    old['Tm']=[code(name,year) for name,year in zip(old.Team,old.year)]
    old=old.rename(columns={'DRtg':'team_defensive_rating','W':'source_wins','L':'source_losses'})
    old['team_defensive_rank']=old.groupby('Season').team_defensive_rating.rank(ascending=True,method='min')
    old['source']=ARCHIVE;old['provider']='Historical Basketball Reference team archive'
    sources=[dict(years='1986-1996',url=ARCHIVE,sha256=hashlib.sha256(raw).hexdigest())]
    with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(current,range(1997,2027)))
    data=pd.concat([old[results[0][0].columns]]+[frame for frame,_ in results],ignore_index=True)
    sources.extend(source for _,source in results)
    standings=pd.read_csv(ROOT/'conference_standings/team_standings.csv')
    merged=standings.merge(data,on=['Season','year','Tm'],how='outer',validate='one_to_one',indicator=True)
    assert merged._merge.eq('both').all(),merged.loc[merged._merge!='both',['Season','Tm','_merge']].to_dict('records')
    assert (merged.team_wins==merged.source_wins).all(),merged.loc[merged.team_wins!=merged.source_wins,['Season','Tm','team_wins','source_wins']].to_dict('records')
    assert (merged.team_losses==merged.source_losses).all(),merged.loc[merged.team_losses!=merged.source_losses,['Season','Tm','team_losses','source_losses']].to_dict('records')
    assert merged.team_defensive_rating.notna().all() and merged.team_defensive_rank.notna().all()
    data.to_csv(OUT/'team_defense.csv',index=False)
    (OUT/'sources.json').write_text(json.dumps(sources,indent=2)+'\n')
    print('Validated',len(data),'regular-season team ratings, 1985–86 through 2025–26; all records match cached standings.')
