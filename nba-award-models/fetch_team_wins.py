"""Expected final wins per team from current US sportsbook win-total (over/under) odds, via Oddschecker.

    python3 fetch_team_wins.py [--year 2027]

For each team's "Regular Season Wins" market, every Over/Under bet at every alternate line is read from
Oddschecker's price history for US books (DraftKings, BetMGM, bet365 US, Caesars, Fanatics, BetRivers,
Borgata; FanDuel returns no history). A book's current price is its latest record, used only when
  - its status is ACTIVE (books mark a line FAILED when they move off it), and
  - it was updated in the last FRESH_DAYS days (a few books leave stale prices marked ACTIVE).
US books only list in-season win totals for some teams, so the UK books' live prices on the same Oddschecker
market (bet365, QuinnBet, BoyleSports, ...; Betfair exchange excluded) are added for every team.
For each book with both sides at one line, the lean is priced in rather than read the line as the mean:
  p_over   = (1/over) / (1/over + 1/under)                        margin removed
  expected = line + sigma * inv_normal_cdf(p_over)                 final wins ~ Normal(expected, sigma)
  sigma    = sqrt(0.25 * R + (0.05 * R)^2), R = games remaining    game-to-game luck + strength uncertainty
So 49.5 at over -150 / under +125 (p_over 0.58) gives ~50.6 wins. The team value is the median across books.
Writes data/current/{year}/team_win_totals.json, which current_season.standings() prefers over other sources.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from statistics import NormalDist, median
import argparse, json, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
import requests

ROOT = Path(__file__).resolve().parent
SEASON_GAMES = 82
FRESH_DAYS = 7
NEAR_LINES = 3.0   # only fetch history for lines within this many wins of a line the market currently quotes
WORKERS = 4
SUSPENDED_DAYS = 30     # suspended market: use each book's last quote from within this many days
TWO_WAY_MARGIN = 0.045  # assumed overround when a book prices only one side (-110/-110 is 4.76%)
BOOKS = {'U6': 'DraftKings', 'UG': 'BetMGM', 'J3': 'bet365 US', 'E6': 'Caesars', 'FNP': 'Fanatics', 'FNJ': 'Fanatics',
         'U2': 'BetRivers', 'UR': 'Borgata', 'U1': 'FanDuel'}
UK_BOOKS = {'B3': 'bet365', 'QN': 'QuinnBet', 'BY': 'BoyleSports', 'SK': 'Sky Bet', 'PP': 'Paddy Power', 'FB': 'Betfair Sportsbook',
            'WH': 'William Hill', 'LD': 'Ladbrokes', 'CE': 'Coral', 'UN': 'Unibet', 'OE': '10bet', 'VC': 'BetVictor', 'WA': 'Betway'}
MARKETS = {  # team: (oddschecker slug, "Regular Season Wins" market id)
    'ATL': ('atlanta-hawks', 3576215654), 'BOS': ('boston-celtics', 3576215657), 'BRK': ('brooklyn-nets', 3576215658),
    'CHO': ('charlotte-hornets', 3576215660), 'CHI': ('chicago-bulls', 3576215532), 'CLE': ('cleveland-cavaliers', 3576215662),
    'DAL': ('dallas-mavericks', 3576215506), 'DEN': ('denver-nuggets', 3576215667), 'DET': ('detroit-pistons', 3576215670),
    'GSW': ('golden-state-warriors', 3576215671), 'HOU': ('houston-rockets', 3576215509), 'IND': ('indiana-pacers', 3576215530),
    'LAC': ('los-angeles-clippers', 3576215548), 'LAL': ('los-angeles-lakers', 3576215537), 'MEM': ('memphis-grizzlies', 3576215531),
    'MIA': ('miami-heat', 3576215519), 'MIL': ('milwaukee-bucks', 3576215542), 'MIN': ('minnesota-timberwolves', 3576215507),
    'NOP': ('new-orleans-pelicans', 3576215515), 'NYK': ('new-york-knicks', 3576215539), 'OKC': ('oklahoma-city-thunder', 3576215540),
    'ORL': ('orlando-magic', 3576215528), 'PHI': ('philadelphia-76ers', 3576215526), 'PHO': ('phoenix-suns', 3576215522),
    'POR': ('portland-trail-blazers', 3576215520), 'SAC': ('sacramento-kings', 3576215544), 'SAS': ('san-antonio-spurs', 3576215511),
    'TOR': ('toronto-raptors', 3576215513), 'UTA': ('utah-jazz', 3576215517), 'WAS': ('washington-wizards', 3576215508),
}
_local = threading.local()


def session():
    if not hasattr(_local, 's'):  # one session per worker thread
        _local.s = requests.Session()
        _local.s.headers['User-Agent'] = 'nba-award-models research script'
    return _local.s
Z = NormalDist()


def get_json(url, params, headers, tries=3):
    for attempt in range(tries):
        r = session().get(url, params=params, headers=headers, timeout=30)
        if r.status_code == 200:
            try:
                return r.json()
            except ValueError:
                pass
        elif r.status_code == 404:  # no price records for this bet in the window: normal for old lines
            return None
        time.sleep(1.5 * (attempt + 1))  # rate limit / server error: back off and retry
    return None


def sigma(games_played):
    remaining = max(0, SEASON_GAMES - games_played)
    return max(0.5, (0.25 * remaining + (0.05 * remaining) ** 2) ** 0.5)


def team(tm, games_played, now):
    slug, market = MARKETS[tm]
    page = f'https://www.oddschecker.com/us/basketball/nba/{slug}/regular-season-wins'
    headers = {'accept': 'application/json', 'referer': page}
    data = get_json('https://www.oddschecker.com/api/markets/v2/all-odds', {'market-ids': market, 'repub': 'OC', 'country': 'US'}, headers)
    if not data:
        raise LookupError('market not found')
    prices = {}  # (book, line) -> {'Over': dec, 'Under': dec}
    cutoff = (now - timedelta(days=FRESH_DAYS)).isoformat()
    bets = [b for b in data[0]['bets'] if (b.get('betName') or '').split()[:1] in (['Over'], ['Under']) and b.get('line')]
    # Lines the market quotes right now (any book in the all-odds feed): the US books sit on or next to them.
    live = {float(b['line']) for b in bets if b.get('bestOddsDecimal')}
    live |= {float(b['line']) for b in bets for o in data[0].get('odds', []) if o.get('betId') == b['betId'] and o.get('status') == 'ACTIVE'}
    if live:
        bets = [b for b in bets if min(abs(float(b['line']) - x) for x in live) <= NEAR_LINES]
    start = (now - timedelta(days=FRESH_DAYS + 3)).strftime('%Y-%m-%dT00:00:00.000Z')
    if not live:  # nothing quoted now (market suspended): look back further for the last quotes before suspension
        start = (now - timedelta(days=SUSPENDED_DAYS)).strftime('%Y-%m-%dT00:00:00.000Z')
    last_seen = {}  # (book, line) -> {side: (timestamp, dec)}, any status
    for bet in bets:
        side = bet['betName'].split()[0]
        hist = get_json(f'https://www.oddschecker.com/api/cx/odds-history/v1/bet/{bet["betId"]}/time-range/',
                        [('bookmakerCode', c) for c in BOOKS] + [('startTime', start)], headers)
        time.sleep(0.3)
        for bk in (hist or {}).get('bookmakers', []):
            points = sorted((o['betFeedTimestamp'], o.get('oddsDecimal'), o.get('status')) for o in bk['odds'])
            if not points:
                continue
            stamp, dec, status = points[-1]
            if dec and float(dec) > 1.01:
                last_seen.setdefault((BOOKS.get(bk['bookmakerCode'], bk['bookmakerCode']), float(bet['line'])), {})[side] = (stamp, float(dec))
            if status == 'ACTIVE' and dec and float(dec) > 1.01 and stamp >= cutoff:
                prices.setdefault((BOOKS.get(bk['bookmakerCode'], bk['bookmakerCode']), float(bet['line'])), {})[side] = float(dec)
    # UK books' live prices come with the market itself (no history call). US books only offer in-season
    # win totals for some teams, so these keep every team on current prices. Betfair exchange excluded.
    by_id = {b['betId']: b for b in data[0]['bets'] if b.get('line')}
    for o in data[0].get('odds', []):
        bet = by_id.get(o.get('betId'))
        if not bet or o.get('status') != 'ACTIVE' or o.get('bookmakerCode') in ('BF', 'BD') or not o.get('oddsDecimal'):
            continue
        side = bet['betName'].split()[0]
        if side in ('Over', 'Under') and float(o['oddsDecimal']) > 1.01:
            prices.setdefault((UK_BOOKS.get(o['bookmakerCode'], o['bookmakerCode']), float(bet['line'])), {})[side] = float(o['oddsDecimal'])
    suspended = False
    if not prices and last_seen:
        # Market suspended everywhere: each book's most recent two-sided line, if both sides were updated together
        # (within a day). Using the last line keeps these teams on the same footing as the priced ones.
        for book in {b for b, _ in last_seen}:
            pairs = [(max(v['Over'][0], v['Under'][0]), line, v) for (b, line), v in last_seen.items()
                     if b == book and 'Over' in v and 'Under' in v
                     and abs((datetime.fromisoformat(v['Over'][0].replace('Z', '+00:00')) - datetime.fromisoformat(v['Under'][0].replace('Z', '+00:00'))).total_seconds()) < 86400]
            if pairs:
                stamp, line, v = max(pairs)
                prices[(book, line)] = {'Over': v['Over'][1], 'Under': v['Under'][1]}
        suspended = bool(prices)
    sd = sigma(games_played)
    quotes = []
    for (book, line), sides in sorted(prices.items()):
        if 'Over' in sides and 'Under' in sides:
            o, u = 1 / sides['Over'], 1 / sides['Under']
            p_over, two_sided = o / (o + u), True
        else:  # one side only: strip an assumed standard margin instead of the book's own
            side, dec = next(iter(sides.items()))
            p_side = min(0.99, (1 / dec) / (1 + TWO_WAY_MARGIN))
            p_over, two_sided = (p_side if side == 'Over' else 1 - p_side), False
        quotes.append(dict(book=book, line=line, over=sides.get('Over'), under=sides.get('Under'), p_over=round(p_over, 4), two_sided=two_sided,
                           expected=round(line + sd * Z.inv_cdf(min(max(p_over, 0.01), 0.99)), 2)))
    if any(q['two_sided'] for q in quotes):
        quotes = [q for q in quotes if q['two_sided']]  # one-sided quotes only when nothing better exists
    if not quotes:
        raise LookupError('no live win-total price at any book')
    lines = [q['line'] for q in quotes]
    us = {q['book'] for q in quotes if q['book'] in BOOKS.values()}
    return dict(page=page, sigma=round(sd, 2), quotes=quotes, line=median(lines), us_books=len(us),
                quality='last quote before suspension' if suspended else 'two-sided' if quotes[0]['two_sided'] else 'one-sided (assumed margin)',
                expected_wins=round(median(q['expected'] for q in quotes), 2), books=len({q['book'] for q in quotes}))


def fetch(year, games_played=None, log=print):
    now = datetime.now(timezone.utc)
    games_played = games_played or {}
    teams, errors = {}, []

    def one(tm):
        try:
            return tm, team(tm, games_played.get(tm, 0), now), None
        except Exception as error:
            return tm, None, f'{tm}: {error}'
    with ThreadPoolExecutor(WORKERS) as pool:
        for tm, result, error in pool.map(one, MARKETS):
            if error:
                errors.append(error)
                log('warning: ' + error, flush=True) if log is print else log(error)
            else:
                teams[tm] = result
                log(f"{tm} {result['expected_wins']:.1f} (line {result['line']}, {result['books']} books)", flush=True) if log is print else log(tm)
    if not teams:
        raise RuntimeError('no team win totals fetched: ' + '; '.join(errors))
    out = ROOT / f'data/current/{year}/team_win_totals.json'
    out.write_text(json.dumps(dict(fetched_at=now.isoformat(timespec='seconds'), method=__doc__.split('\n\n')[1].strip(),
                                   errors=errors, teams=teams), indent=1) + '\n')
    return teams, errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, default=2027)
    args = parser.parse_args()
    played = {}
    try:  # games played so far, for sigma; ESPN standings from fetch_current.py
        import current_season
        played = {r.Tm: int(r.wins_to_date + r.losses_to_date) for r in current_season.standings(args.year, use_odds=False).itertuples()}
    except Exception as error:
        print('warning: no standings for games played, assuming 0:', error, file=sys.stderr)
    try:
        _, errs = fetch(args.year, played)
    except Exception as error:
        print('team win totals fetch failed:', error, file=sys.stderr); sys.exit(1)
