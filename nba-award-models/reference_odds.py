"""Decimal reference quotes; Oddschecker comparisons stay outside the consensus."""
from datetime import datetime, timezone
from statistics import median

OC_MARKETS = {'MVP': ('regular-season-mvp', 3587448609), 'ROY': ('rookie-of-the-year', 3587313860),
              'DPOY': ('defensive-player-of-the-year', 3587313709), 'MIP': ('most-improved-player', 3587313794),
              'SMOY': ('sixth-man-of-the-year', 3587313795), 'COY': ('coach-of-the-year', 3587313683),
              'CPOY': ('clutch-player', None)}

def oddschecker_url(award):
    return f'https://www.oddschecker.com/us/basketball/nba/{OC_MARKETS[award][0]}/winner'

def parse_oddschecker(data):
    """Median active fixed-odds quote, one price per bookmaker; exclude exchanges."""
    quotes = {}
    for quote in data['odds']:
        if quote.get('status') != 'ACTIVE' or quote.get('bookmakerCode') == 'BF':
            continue
        value = float(quote.get('oddsDecimal') or 0)
        if value > 1:
            quotes.setdefault(str(quote['betId']), {})[quote['bookmakerCode']] = value
    return [dict(name=(bet.get('betName') or bet.get('name') or '').strip(),
                 decimal_odds=median(quotes[str(bet['betId'])].values()))
            for bet in data['bets'] if str(bet['betId']) in quotes]

def fetch_oddschecker(session, award, year):
    result = dict(url=oddschecker_url(award), kind='comparison', rows=[], status='unavailable',
                  checked_at=datetime.now(timezone.utc).isoformat(timespec='seconds'))
    market = OC_MARKETS[award][1]
    if year != 2027 or market is None:
        result['error'] = 'No verified current Oddschecker market ID for this award/season.'
        return result
    try:
        response = session.get('https://www.oddschecker.com/api/markets/v2/all-odds',
                               params={'market-ids': market, 'repub': 'OC', 'country': 'US'},
                               headers={'Accept': 'application/json', 'Referer': result['url']}, timeout=25)
        response.raise_for_status()
        payload = response.json()
        data = next(item for item in payload if str(item.get('marketId', item.get('id', market))) == str(market))
        result['rows'] = parse_oddschecker(data)
        if not result['rows']:
            raise LookupError('No active quotes returned.')
        result.update(status='available', fetched_at=result['checked_at'])
    except Exception as error:
        result['error'] = f'Oddschecker unavailable: {error}'
    return result

def reference_rows(market, name_key):
    rows = {}
    for player in market['players']:
        row = rows.setdefault(name_key(player['name']), dict(name=player['name']))
        for source, values in player['sources'].items():
            if values.get('decimal_odds'):
                row[source] = values['decimal_odds']
            elif source in ('polymarket', 'kalshi'):
                # Use the raw midpoint/bid, not its overround-normalised probability.
                price = values.get('price')
                if price and 0 < price <= 1:
                    row[source] = 1 / price
    for player in market.get('references', {}).get('oddschecker', {}).get('rows', []):
        rows.setdefault(name_key(player['name']), dict(name=player['name']))['oddschecker'] = player['decimal_odds']
    return sorted(rows.values(), key=lambda p: (p.get('sportsbet', float('inf')), p.get('neds', float('inf')), p['name']))


def chart_reference(history, award):
    """Use only the latest award-wide Oddschecker day saved for the chart.

    These are overround-normalised chart probabilities, so the reciprocal is a
    chart-equivalent decimal value rather than an original bookmaker quote.
    """
    item = history.get('awards', {}).get(award, {})
    days = {day for player in item.get('players', [])
            for day, value in player.get('sources', {}).get('sportsbooks', {}).items()
            if isinstance(value, (int, float)) and 0 < value <= 1}
    result = dict(url=item.get('links', {}).get('sportsbooks', oddschecker_url(award)),
                  kind='chart_snapshot', status='unavailable', rows=[], fetched_at=history.get('fetched_at'))
    if not days:
        result['error'] = 'No saved Oddschecker chart snapshot for this award.'
        return result
    latest = max(days)
    result.update(status='available', snapshot_date=latest)
    for player in item.get('players', []):
        value = player.get('sources', {}).get('sportsbooks', {}).get(latest)
        if isinstance(value, (int, float)) and 0 < value <= 1:
            result['rows'].append(dict(name=player['name'], decimal_odds=1/value))
    return result
