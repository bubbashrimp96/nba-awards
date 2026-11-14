"""Download current award odds for the in-progress season from Polymarket and Kalshi.

    python3 fetch_odds.py [--year 2027]

Both are public prediction-market APIs (no key, no browser). For every award market:
  price  = bid/ask midpoint when the spread is within max(2c, half the midpoint); otherwise the bid.
           Thin longshot markets quote e.g. 1c/8c, and ~45 midpoints of 4.5% would add up to a field
           of 200%; the bid is the only firm price there.
  prob   = raw implied probability, with no bookmaker margin adjustment.
  market = equal-weight mean of raw probabilities from the sources listing each player.
           Neither source fields nor the combined field are scaled to 100%.
Writes data/current/{year}/odds.json (latest snapshot, read by project_current.py) and appends
the snapshot to data/current/{year}/odds_history.csv for later movement charts.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, csv, json, re, sys, time, unicodedata
import requests
from australian_odds import fetch_book
from reference_odds import chart_reference

ROOT = Path(__file__).resolve().parent
AWARDS = {  # app code: (Polymarket event title suffix, Kalshi series)
    'MVP': ('MVP', 'KXNBAMVP'),
    'ROY': ('Rookie of the Year', 'KXNBAROY'),
    'DPOY': ('Defensive Player of the Year', 'KXNBADPOY'),
    'MIP': ('Most Improved Player', 'KXNBAMIMP'),
    'SMOY': ('Sixth Man of the Year', 'KXNBASIXTH'),
    'CPOY': ('Clutch Player of the Year', 'KXNBACLUTCH'),
    'COY': ('Coach of the Year', 'KXNBACOY'),
}
KALSHI = 'https://api.elections.kalshi.com/trade-api/v2'
POLY = 'https://gamma-api.polymarket.com'
S = requests.Session()
S.headers['User-Agent'] = 'nba-award-models research script'


def name_key(name):
    """Accent-, case- and suffix-insensitive key, so 'Luka Doncic' matches 'Luka Dončić'."""
    text = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    text = re.sub(r"[.'’`-]", '', text)
    text = re.sub(r'\b(jr|sr|ii|iii|iv)\b', '', text)
    return ' '.join(text.split())


def price(bid, ask, last):
    """Returns (price, wide). `last` is kept for reference only: stale tail trades distort the field."""
    bid, ask = (float(x) if x not in (None, '') else None for x in (bid, ask))
    if ask is None or ask <= 0:
        return bid, True
    bid = bid or 0.0
    mid = (bid + ask) / 2
    if ask - bid <= max(0.02, 0.5 * mid):
        return mid, False
    return bid, True


def normalise(rows):
    for r in rows:
        r['prob'] = r['price'] or 0
    return rows


def polymarket(year, title):
    season = f'{year - 1}-{str(year)[-2:]}'
    wanted = f'NBA: {season} {title}'
    found = S.get(f'{POLY}/public-search', params={'q': wanted, 'limit_per_type': 20}, timeout=30).json()
    event = next((e for e in found.get('events') or [] if e.get('title', '').strip().lower() == wanted.lower() and not e.get('closed')), None)
    if event is None:
        raise LookupError(f'no open Polymarket event titled "{wanted}"')
    event = S.get(f'{POLY}/events', params={'slug': event['slug']}, timeout=30).json()[0]
    rows = []
    for m in event['markets']:
        if m.get('closed') or not m.get('active'):
            continue
        p, wide = price(m.get('bestBid'), m.get('bestAsk'), m.get('lastTradePrice'))
        rows.append(dict(name=(m.get('groupItemTitle') or m['question']).strip(), price=p, wide=wide,
                         bid=m.get('bestBid'), ask=m.get('bestAsk')))
    return dict(url=f'https://polymarket.com/event/{event["slug"]}', volume=float(event.get('volume') or 0), rows=normalise(rows))


def kalshi(year, series):
    event = f'{series}-{str(year)[-2:]}'
    markets = S.get(f'{KALSHI}/markets', params={'event_ticker': event, 'limit': 1000}, timeout=30).json().get('markets', [])
    markets = [m for m in markets if m.get('status') in ('active', 'open', None)]
    if not markets:
        raise LookupError(f'no open Kalshi markets for {event}')
    rows = []
    for m in markets:
        p, wide = price(m.get('yes_bid_dollars'), m.get('yes_ask_dollars'), m.get('last_price_dollars'))
        rows.append(dict(name=(m.get('yes_sub_title') or m['ticker']).strip(), price=p, wide=wide,
                         bid=m.get('yes_bid_dollars'), ask=m.get('yes_ask_dollars')))
    volume = sum(float(m.get('volume_fp') or 0) for m in markets)
    return dict(url=f'https://kalshi.com/markets/{series.lower()}', volume=volume, rows=normalise(rows))


def combine(sources):
    players = {}
    for source, data in sources.items():
        for r in data['rows']:
            raw = r.get('price', r.get('prob'))
            if not raw:
                continue
            p = players.setdefault(name_key(r['name']), dict(name=r['name'], sources={}))
            p['sources'][source] = dict(prob=raw, price=raw, wide=r['wide'], **({"decimal_odds": r['decimal_odds']} if 'decimal_odds' in r else {}))
    for p in players.values():
        probs = [s['prob'] for s in p['sources'].values()]
        # Average only sources that quote this player; missing listings are not zeroes.
        p['market'] = sum(probs) / len(probs)
        p['wide'] = all(s['wide'] for s in p['sources'].values())
    return sorted(players.values(), key=lambda p: -p['market'])


def fetch(year):
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    awards, errors = {}, []
    chart_path = ROOT / f'data/current/{year}/odds_movement.json'
    chart_history = json.loads(chart_path.read_text()) if chart_path.exists() else {}
    for award, (title, series) in AWARDS.items():
        sources = {}
        for source, call in (('sportsbet', lambda: fetch_book(S, 'sportsbet', award, year)), ('neds', lambda: fetch_book(S, 'neds', award, year)), ('polymarket', lambda: polymarket(year, title)), ('kalshi', lambda: kalshi(year, series))):
            try:
                sources[source] = call()
                sources[source].setdefault('fetched_at', datetime.now(timezone.utc).isoformat(timespec='seconds'))
            except Exception as error:  # one market down should not block the other
                errors.append(f'{award} {source}: {error}')
            time.sleep(0.2)
        if sources:
            awards[award] = dict(players=combine(sources),
                                 sources={k: {key: value for key, value in v.items() if key != 'rows'} for k, v in sources.items()},
                                 references={'oddschecker': chart_reference(chart_history, award)})
    if not awards:
        raise RuntimeError('no odds fetched: ' + '; '.join(errors))
    snapshot = dict(fetched_at=stamp, method='Equal-weight mean of available Sportsbet, Neds, Polymarket and Kalshi implied probabilities; raw implied probabilities are used with no margin adjustment or field normalisation. Decimal bookmaker prices are retained separately. Sportsbet is the primary displayed bookmaker reference; sources are not assumed to move simultaneously.', errors=errors, awards=awards)
    out = ROOT / f'data/current/{year}'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'odds.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=1) + '\n')
    history = out / 'odds_history.csv'
    new = not history.exists()
    with history.open('a', newline='') as f:
        writer = csv.writer(f)
        if new:
            writer.writerow(['fetched_at', 'award', 'name', 'market', 'polymarket', 'kalshi'])
        for award, item in awards.items():
            for p in item['players']:
                if p['market'] >= 0.001:
                    writer.writerow([stamp, award, p['name'], round(p['market'], 4),
                                     *[round(p['sources'][s]['prob'], 4) if s in p['sources'] else '' for s in ('polymarket', 'kalshi')]])
    quotes = out / 'bookmaker_odds_history.csv'
    new_quotes = not quotes.exists()
    with quotes.open('a', newline='') as f:
        writer = csv.writer(f)
        if new_quotes:
            writer.writerow(['fetched_at', 'award', 'source', 'name', 'decimal_odds', 'prob'])
        for award, item in awards.items():
            for player in item['players']:
                for source, values in player['sources'].items():
                    if 'decimal_odds' in values:
                        writer.writerow([item['sources'][source]['fetched_at'], award, source, player['name'], values['decimal_odds'], values['prob']])
    return snapshot


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, default=2027)
    args = parser.parse_args()
    try:
        snap = fetch(args.year)
    except Exception as error:
        print('odds fetch failed:', error, file=sys.stderr); sys.exit(1)
    for award, item in snap['awards'].items():
        print(award, ', '.join(f"{p['name']} {p['market']:.0%}" for p in item['players'][:4]))
    for e in snap['errors']:
        print('warning:', e, file=sys.stderr)
