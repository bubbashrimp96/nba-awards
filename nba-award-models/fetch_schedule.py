"""Download the regular-season calendar (Basketball Reference monthly schedule pages, October to April).

    python3 fetch_schedule.py [--year 2027] [--max-age-days 7]

Writes data/current/<year>/schedule.json: {fetched_at, games: [{date, away, home}], team_games: {Tm: n}}.
Used to turn an injury date range into games missed for the player's team (current_season.absence_games).
Pages are spaced 4 seconds apart (Basketball Reference allows ~20 requests/minute). A month with no page
yet (404) is skipped. NBA Cup knockout games are added by the league in December, so a team can show
fewer than 82 scheduled games until then.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, json, re, sys, time
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
MONTHS = ['october', 'november', 'december', 'january', 'february', 'march', 'april']


def path(year):
    return ROOT / f'data/current/{year}/schedule.json'


def parse(html):
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table', id='schedule')
    games = []
    for tr in (table.tbody.find_all('tr') if table and table.tbody else []):
        date = tr.find('th', attrs={'data-stat': 'date_game'})
        away = tr.find('td', attrs={'data-stat': 'visitor_team_name'})
        home = tr.find('td', attrs={'data-stat': 'home_team_name'})
        if not (date and away and home and date.get('csk')):
            continue
        code = lambda cell: re.search(r'/teams/([A-Z]{3})/', str(cell)).group(1)
        stamp = date['csk'][:8]
        games.append(dict(date=f'{stamp[:4]}-{stamp[4:6]}-{stamp[6:]}', away=code(away), home=code(home)))
    return games


def fetch(year, max_age_days=7, log=print):
    out = path(year)
    if out.exists() and max_age_days > 0:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(json.loads(out.read_text())['fetched_at'])
        if age.total_seconds() < max_age_days * 86400:
            log('schedule cached'); return json.loads(out.read_text())
    session = requests.Session()
    session.headers['User-Agent'] = 'nba-award-models research script'
    games = []
    for i, month in enumerate(MONTHS):
        if i:
            time.sleep(4)
        url = f'https://www.basketball-reference.com/leagues/NBA_{year}_games-{month}.html'
        response = session.get(url, timeout=40)
        if response.status_code == 404:
            log(f'no schedule page for {month}'); continue
        if response.status_code == 429:
            raise RuntimeError('Basketball Reference rate limit hit; try again later')
        response.raise_for_status()
        month_games = parse(response.text)
        games += month_games
        log(f'fetched schedule {month} ({len(month_games)} games)')
    games = sorted({(g['date'], g['away'], g['home']): g for g in games}.values(), key=lambda g: (g['date'], g['home']))
    counts = {}
    for g in games:
        for tm in (g['away'], g['home']):
            counts[tm] = counts.get(tm, 0) + 1
    if len(counts) != 30:
        raise RuntimeError(f'Schedule has {len(counts)} teams; expected 30')
    data = dict(season=f'{year-1}-{str(year)[-2:]}', fetched_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                source=f'https://www.basketball-reference.com/leagues/NBA_{year}_games.html', games=games, team_games=dict(sorted(counts.items())))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=0) + '\n')
    log(f'saved {len(games)} games')
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, default=2027)
    parser.add_argument('--max-age-days', type=float, default=7)
    args = parser.parse_args()
    try:
        fetch(args.year, args.max_age_days)
    except Exception as error:
        print('schedule fetch failed:', error, file=sys.stderr); sys.exit(1)
