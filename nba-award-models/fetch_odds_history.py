"""Download daily odds movement for the in-progress season's awards since their markets opened.

    python3 fetch_odds_history.py [--year 2027]

Sources (public JSON endpoints, plain requests):
  Oddschecker (US)  price-change history per bookmaker for each runner (FanDuel, DraftKings, BetMGM,
                    bet365 US, Caesars, Fanatics, BetRivers, Borgata). Prices persist until changed, so each
                    book is carried forward day by day while it stays ACTIVE. Implied prob = 1 / decimal odds;
                    the daily sportsbook figure is the median across books, then the field is scaled to 100%.
                    No Clutch Player of the Year market is listed there.
  Polymarket        clob prices-history, daily.
  Kalshi            daily candlesticks: bid/ask midpoint when tight, otherwise the bid (as fetch_odds.py).
Only runners priced at 0.5% or more somewhere today are fetched (a full run takes a few minutes).
Writes data/current/{year}/odds_movement.json, read by project_current.py.
"""
from pathlib import Path
from datetime import datetime, timezone, date, timedelta
import argparse, json, sys, time
import requests

from fetch_odds import AWARDS, KALSHI, POLY, name_key, price, polymarket as poly_event_rows

ROOT = Path(__file__).resolve().parent
S = requests.Session()
S.headers['User-Agent'] = 'nba-award-models research script'
OC_MARKETS = {'MVP': ('regular-season-mvp', 3587448609), 'ROY': ('rookie-of-the-year', 3587313860),
              'DPOY': ('defensive-player-of-the-year', 3587313709), 'MIP': ('most-improved-player', 3587313794),
              'SMOY': ('sixth-man-of-the-year', 3587313795), 'COY': ('coach-of-the-year', 3587313683)}
OC_BOOKS = {'U1': 'FanDuel', 'U6': 'DraftKings', 'UG': 'BetMGM', 'J3': 'bet365 US', 'E6': 'Caesars',
            'FNP': 'Fanatics', 'FNJ': 'Fanatics', 'U2': 'BetRivers', 'UR': 'Borgata'}
MIN_PROB = 0.005
START = '2026-05-01T00:00:00.000Z'


def day(ts):
    return datetime.fromtimestamp(ts, timezone.utc).date().isoformat()


def oddschecker(award, today):
    slug, market = OC_MARKETS[award]
    page = f'https://www.oddschecker.com/us/basketball/nba/{slug}/winner'
    headers = {'accept': 'application/json', 'referer': page}
    data = S.get('https://www.oddschecker.com/api/markets/v2/all-odds', params={'market-ids': market, 'repub': 'OC', 'country': 'US'},
                 headers=headers, timeout=30).json()[0]
    # skip runners every book prices longer than 200/1 (under 0.5%): they cannot move the chart
    best = {}
    for o in data['odds']:
        if o.get('status') == 'ACTIVE' and o.get('bookmakerCode') != 'BF' and o.get('oddsDecimal'):
            best[o['betId']] = min(best.get(o['betId'], 1e9), float(o['oddsDecimal']))
    series = {}
    for bet in data['bets']:
        if best.get(bet['betId'], 1e9) > 1 / MIN_PROB:
            continue
        name = (bet.get('betName') or bet.get('name') or '').strip()
        r = S.get(f'https://www.oddschecker.com/api/cx/odds-history/v1/bet/{bet["betId"]}/time-range/',
                  params=[('bookmakerCode', c) for c in OC_BOOKS] + [('startTime', START)], headers=headers, timeout=30)
        time.sleep(0.35)
        if r.status_code != 200:
            continue
        books = {}
        for bk in r.json().get('bookmakers', []):
            points = sorted((o['betFeedTimestamp'], float(o['oddsDecimal']), o.get('status')) for o in bk['odds'] if o.get('oddsDecimal'))
            if not points:
                continue
            daily = {}
            for t, dec, status in points:
                daily[t[:10]] = (dec, status)
            # carry each price forward until it changes; stop where the book suspends the runner
            d, end, last, filled = date.fromisoformat(min(daily)), today, None, {}
            while d <= end:
                key = d.isoformat()
                last = daily.get(key, last)
                if last and last[1] == 'ACTIVE' and last[0] > 1.01:
                    filled[key] = 1 / last[0]
                d += timedelta(days=1)
            books[OC_BOOKS.get(bk['bookmakerCode'], bk['bookmakerCode'])] = filled
        if books and any(today.isoformat() in b for b in books.values()):
            series[name] = books
    # daily median across books, then the field scaled to 100% each day (bookmaker overround removed)
    days = sorted({d for books in series.values() for b in books.values() for d in b})
    out = {name: {} for name in series}
    for d in days:
        med = {}
        for name, books in series.items():
            vals = sorted(b[d] for b in books.values() if d in b)
            if vals:
                n = len(vals)
                med[name] = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
        total = max(1.0, sum(med.values()))
        for name, v in med.items():
            out[name][d] = v / total
    return dict(url=page, books=sorted({b for books in series.values() for b in books}), series=out)


def polymarket(award, year):
    title = AWARDS[award][0]
    season = f'{year - 1}-{str(year)[-2:]}'
    wanted = f'NBA: {season} {title}'
    found = S.get(f'{POLY}/public-search', params={'q': wanted, 'limit_per_type': 20}, timeout=30).json()
    event = next(e for e in found.get('events') or [] if e.get('title', '').strip().lower() == wanted.lower() and not e.get('closed'))
    event = S.get(f'{POLY}/events', params={'slug': event['slug']}, timeout=30).json()[0]
    series = {}
    for m in event['markets']:
        if m.get('closed') or not m.get('active'):
            continue
        p, _ = price(m.get('bestBid'), m.get('bestAsk'), None)
        if not p or p < MIN_PROB:
            continue
        token = json.loads(m['clobTokenIds'])[0]
        h = S.get('https://clob.polymarket.com/prices-history', params={'market': token, 'interval': 'max', 'fidelity': 1440}, timeout=30).json()
        time.sleep(0.2)
        series[(m.get('groupItemTitle') or m['question']).strip()] = {day(pt['t']): float(pt['p']) for pt in h.get('history', [])}
    return dict(url=f'https://polymarket.com/event/{event["slug"]}', series=series)


def kalshi(award, year):
    code = AWARDS[award][1]
    event = f'{code}-{str(year)[-2:]}'
    markets = S.get(f'{KALSHI}/markets', params={'event_ticker': event, 'limit': 1000}, timeout=30).json().get('markets', [])
    now = int(time.time())
    series = {}
    for m in markets:
        p, _ = price(m.get('yes_bid_dollars'), m.get('yes_ask_dollars'), None)
        if not p or p < MIN_PROB:
            continue
        start = int(datetime.fromisoformat(m['open_time'].replace('Z', '+00:00')).timestamp())
        c = S.get(f'{KALSHI}/series/{code}/markets/{m["ticker"]}/candlesticks',
                  params={'start_ts': start, 'end_ts': now, 'period_interval': 1440}, timeout=30).json()
        time.sleep(0.2)
        points = {}
        for k in c.get('candlesticks', []):
            v, _ = price((k.get('yes_bid') or {}).get('close_dollars'), (k.get('yes_ask') or {}).get('close_dollars'), None)
            if v is not None:
                points[day(k['end_period_ts'])] = v
        series[(m.get('yes_sub_title') or m['ticker']).strip()] = points
    return dict(url=f'https://kalshi.com/markets/{code.lower()}', series=series)


def fetch(year, log=print):
    today = datetime.now(timezone.utc).date()
    result, errors = {}, []
    for award in AWARDS:
        sources = {}
        calls = [('polymarket', lambda: polymarket(award, year)), ('kalshi', lambda: kalshi(award, year))]
        if award in OC_MARKETS:
            calls.insert(0, ('sportsbooks', lambda: oddschecker(award, today)))
        for source, call in calls:
            try:
                sources[source] = call()
                log(f'{award} {source}: {len(sources[source]["series"])} runners')
            except Exception as error:
                errors.append(f'{award} {source}: {error!r}')
        # one name per player across sources (accent/suffix-insensitive), keeping the longest spelling seen
        players = {}
        for source, data in sources.items():
            for name, points in data['series'].items():
                key = name_key(name)
                entry = players.setdefault(key, dict(name=name, sources={}))
                if len(name) > len(entry['name']) or not name.isascii():
                    entry['name'] = name
                entry['sources'][source] = {d: round(v, 4) for d, v in sorted(points.items())}
        result[award] = dict(players=list(players.values()),
                             links={s: d['url'] for s, d in sources.items()},
                             books=sources.get('sportsbooks', {}).get('books', []))
    snapshot = dict(fetched_at=datetime.now(timezone.utc).isoformat(timespec='seconds'), method=__doc__.split('\n\n')[1].strip(),
                    errors=errors, awards=result)
    out = ROOT / f'data/current/{year}/odds_movement.json'
    out.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')) + '\n')
    return snapshot


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, default=2027)
    args = parser.parse_args()
    try:
        snap = fetch(args.year)
    except Exception as error:
        print('odds history fetch failed:', error, file=sys.stderr); sys.exit(1)
    for e in snap['errors']:
        print('warning:', e, file=sys.stderr)
