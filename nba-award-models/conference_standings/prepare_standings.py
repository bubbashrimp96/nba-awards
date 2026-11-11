"""Parse downloaded ESPN season standings into auditable regular-season ranks."""
from pathlib import Path
import json,hashlib
import pandas as pd

ROOT=Path(__file__).resolve().parent
CACHE=(Path(__file__).resolve().parent.parent / 'data' / 'team_wins_cache.json')
wins=json.loads(CACHE.read_text())

def abbreviation(tm,year):
    aliases={'GS':'GSW','NY':'NYK','SA':'SAS','UTAH':'UTA','PHX':'PHO','BKN':'BRK','NJ':'NJN'}
    if tm=='WSH':return 'WSB' if year<=1997 else 'WAS'
    if tm=='CHA':return 'CHH' if year<=2002 else ('CHA' if year<=2014 else 'CHO')
    if tm=='NO':return ('NOK' if year in [2006,2007] else 'NOH') if year<=2013 else 'NOP'
    return aliases.get(tm,tm)

rows=[];sources=[];corrections=[]
for year in range(1986,2027):
    path=ROOT/'raw'/f'{year}.json'
    j=json.loads(path.read_text());season=f'{year-1}-{str(year)[2:]}'
    assert j.get('season',{}).get('year',year)==year
    seen=set()
    for conf in j['children']:
        assert conf['name'] in ['Eastern Conference','Western Conference']
        standings=conf['standings'];assert standings['season']==year
        for e in standings['entries']:
            stats={s['name']:s.get('value') for s in e['stats']}
            tm=abbreviation(e['team']['abbreviation'],year)
            assert tm in wins[season],(year,tm,e['team'])
            assert tm not in seen;seen.add(tm)
            w,l=stats['wins'],stats['losses']
            # Preserve raw responses. Apply explicit, auditable source repairs:
            # ESPN's 2000 response is an unfinished-season snapshot; the existing
            # final-win cache and an 82-game schedule supply the final records.
            if year==2000:
                w=float(wins[season][tm]);l=82-w
                if (w,l)!=(stats['wins'],stats['losses']):
                    corrections.append(dict(year=year,Tm=tm,raw_wins=stats['wins'],raw_losses=stats['losses'],wins=w,losses=l,reason='ESPN incomplete 1999-00 snapshot; use final cached wins and 82 games',source='https://www.basketball-reference.com/leagues/NBA_2000_standings.html'))
            if (year,tm) in [(1994,'DAL'),(1998,'DEN')]:
                corrected_losses=82-w
                corrections.append(dict(year=year,Tm=tm,raw_wins=w,raw_losses=l,wins=w,losses=corrected_losses,reason='ESPN loss typo creates 83-game record; corrected against historical record',source=f'https://www.basketball-reference.com/teams/{tm}/{year}.html'))
                l=corrected_losses
            assert w==wins[season][tm],('win mismatch',season,tm,w,wins[season][tm])
            assert w>=0 and l>=0 and w+l>0
            rows.append(dict(Season=season,year=year,Tm=tm,conference=conf['name'].split()[0],team_wins=w,team_losses=l,team_games=w+l,win_percentage=w/(w+l),source_playoff_seed_not_used=stats.get('playoffSeed')))
    assert seen==set(wins[season]),(year,seen.symmetric_difference(wins[season]))
    assert sum(r['team_wins'] for r in rows if r['year']==year)==sum(r['team_losses'] for r in rows if r['year']==year)
    sources.append(dict(year=year,url=f'https://site.web.api.espn.com/apis/v2/sports/basketball/nba/standings?season={year}&type=0&level=2',sha256=hashlib.sha256(path.read_bytes()).hexdigest()))

d=pd.DataFrame(rows)
d['conference_rank']=d.groupby(['Season','conference']).win_percentage.rank(ascending=False,method='average')
d['conference_size']=d.groupby(['Season','conference']).Tm.transform('size')
d['conference_standing']=1-(d.conference_rank-1)/(d.conference_size-1)
d['league_rank']=d.groupby('Season').win_percentage.rank(ascending=False,method='average')
d['league_size']=d.groupby('Season').Tm.transform('size')
d['league_standing']=1-(d.league_rank-1)/(d.league_size-1)
assert not d.duplicated(['Season','Tm']).any()
assert d.conference_standing.between(0,1).all()
assert d.loc[(d.year==1989)&(d.Tm=='MIA'),'conference'].iloc[0]=='Western'
assert d.loc[(d.year==1990)&(d.Tm=='CHH'),'conference'].iloc[0]=='Western'
assert d.loc[(d.year==1991)&(d.Tm=='ORL'),'conference'].iloc[0]=='Western'
assert d.loc[(d.year==2004)&(d.Tm=='NOH'),'conference'].iloc[0]=='Eastern'
assert d.loc[(d.year==2005)&(d.Tm=='NOH'),'conference'].iloc[0]=='Western'
# Verify that conference record rank has not been replaced by play-in outcomes.
assert d.loc[(d.year==2026)&(d.Tm=='PHO'),'conference_rank'].iloc[0]==7
assert d.loc[(d.year==2026)&(d.Tm=='POR'),'conference_rank'].iloc[0]==8.5
d.to_csv(ROOT/'team_standings.csv',index=False)
(ROOT/'sources.json').write_text(json.dumps(dict(provider='ESPN with documented repairs',rank_definition='Regular-season W/(W+L), average ranks for tied records; excludes playoff seeding and play-in outcomes',sources=sources,corrections=corrections),indent=2))
pd.DataFrame(corrections).to_csv(ROOT/'source_corrections.csv',index=False)
print(f'Validated {len(d)} team-seasons across 41 seasons; all wins agree with original cache.')
