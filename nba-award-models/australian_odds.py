"""Public Australian bookmaker award quotes, scoped to the supplied 2026–27 events."""
import json
import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup

EVENTS = {
 'MVP': ('nba-regular-season-mvp', '10506613', 'c0be7688-41c6-42d5-b476-3f58fc5bfbd9'),
 'ROY': ('nba-rookie-of-the-year', '10626677', '2e3161ab-bec9-41c5-bcf3-de95a1df89a0'),
 'DPOY': ('nba-defensive-player-of-the-year', '10644895', '693d161d-62da-4570-be12-e9bdf725c47e'),
 'MIP': ('nba-most-improved-player', '10703151', '6ec3d314-892f-4d41-93e9-65c83135649e'),
 'SMOY': ('nba-sixth-man-of-the-year', '10703145', '31f2f4ce-18e5-499b-9fbf-b7b13eb932f6'),
 'CPOY': ('nba-clutch-player-of-the-year', '10740405', '457f9120-6ba4-4068-81ae-b35e82a1ab39'),
 'COY': ('nba-coach-of-the-year', '10672371', 'a5a866d1-9f84-44bc-8798-0ae24392d040'),
}

def urls(award):
    slug, sb, neds = EVENTS[award]
    return {'sportsbet': f'https://www.sportsbet.com.au/betting/basketball-us/nba-player-awards/{slug}-2026-27-{sb}',
            'neds': f'https://www.neds.com.au/sports/basketball/usa/nba-awards/{slug}-2026-27/{neds}'}

def quote(name, numerator, denominator):
    decimal = 1 + float(numerator) / float(denominator)
    if decimal <= 1:
        raise ValueError('invalid decimal odds')
    return dict(name=re.sub(r'\s+\([^)]*\)$', '', name).strip(), decimal_odds=decimal,
                price=1 / decimal, wide=False)

def sportsbet_rows(html, event_id):
    soup = BeautifulSoup(html, 'html.parser')
    marker = 'window.__PRELOADED_STATE__ ='
    script = next(s.get_text() for s in soup.find_all('script') if marker in s.get_text())
    state = json.JSONDecoder().raw_decode(script.split(marker, 1)[1].lstrip())[0]
    book = state['entities']['sportsbook']
    event = book['events'][str(event_id)]
    rows = []
    for mid in event['marketIds']:
        market = book['markets'][str(mid)]
        if not market.get('active') or not market.get('displayed'):
            continue
        for oid in market['outcomeIds']:
            row = book['outcomes'][str(oid)]
            p = row.get('winPrice')
            if row.get('active') and row.get('displayed') and p and p.get('den'):
                rows.append(quote(row['name'], p['num'], p['den']))
    return rows

def neds_rows(card, event_id):
    event = card['events'][event_id]
    if not event.get('visible') or event.get('match_status') != 'BettingOpen':
        return []
    prices = {key.split(':')[0]: value for key, value in card.get('prices', {}).items()}
    rows = []
    for mid in event['market_ids']:
        market = card['markets'][mid]
        if not market.get('visible') or market.get('is_suspended'):
            continue
        for eid in market['entrant_ids']:
            entrant = card['entrants'][eid]
            p = prices.get(eid, {}).get('odds', {})
            if entrant.get('visible') and not entrant.get('is_suspended') and p.get('denominator'):
                rows.append(quote(entrant['name'], p['numerator'], p['denominator']))
    return rows

def fetch_book(session, source, award, year):
    if year != 2027:
        raise LookupError('supplied bookmaker event links cover 2026–27 only')
    url = urls(award)[source]
    _, sb, nid = EVENTS[award]
    if source == 'sportsbet':
        response = session.get(url, timeout=35)
        response.raise_for_status()
        rows = sportsbet_rows(response.text, sb)
    else:
        response = session.get('https://api.neds.com.au/v2/sport/event-card', params={'id': nid},
                               headers={'Content-Type': 'application/json', 'Accept': 'application/json', 'From': 'sportsbook'}, timeout=35)
        response.raise_for_status()
        rows = neds_rows(response.json(), nid)
    if not rows:
        raise LookupError('no open priced selections')
    for row in rows:
        row['prob'] = row['price']
    return dict(url=url, kind='bookmaker', fetched_at=datetime.now(timezone.utc).isoformat(timespec='seconds'), rows=rows)
