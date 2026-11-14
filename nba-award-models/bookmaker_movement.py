"""Merge observed bookmaker snapshots into historical chart data, without backfilling."""
import csv
import json
from copy import deepcopy

def merge_bookmaker_history(data, history_path, odds_path):
    from fetch_odds import name_key
    result = deepcopy(data)
    if not history_path.exists():
        return result
    snapshot = json.loads(odds_path.read_text()) if odds_path.exists() else {'awards': {}}
    latest = {}
    with history_path.open(newline='') as handle:
        for row in csv.DictReader(handle):
            if row['source'] not in ('sportsbet', 'neds'):
                continue
            key = row['award'], row['source'], name_key(row['name']), row['fetched_at'][:10]
            if key not in latest or row['fetched_at'] > latest[key]['fetched_at']:
                latest[key] = row
    for (award, source, player_key, day), row in latest.items():
        decimal = float(row['decimal_odds'])
        if decimal <= 1:
            continue
        item = result['awards'].setdefault(award, dict(players=[], links={}, books=[]))
        player = next((p for p in item['players'] if name_key(p['name']) == player_key), None)
        if player is None:
            player = dict(name=row['name'], sources={})
            item['players'].append(player)
        player['sources'].setdefault(source, {})[day] = 1 / decimal
        metadata = snapshot['awards'].get(award, {}).get('sources', {}).get(source)
        if metadata:
            item.setdefault('links', {})[source] = metadata['url']
    result['method'] += ' Sportsbet/Neds use the last observed decimal quote per UTC day; no invented pre-snapshot history.'
    return result


CONSENSUS_SOURCES = ('sportsbet', 'neds', 'polymarket', 'kalshi')


def merge_latest_market_snapshot(data, snapshot):
    """Make the latest chart observation the same snapshot as Market top ten.

    Oddschecker remains selectable separately; it is not a fifth consensus vote.
    Clear same-day historical prices before inserting the snapshot so a missing
    source listing cannot silently contribute an old quote.
    """
    from fetch_odds import name_key
    result = deepcopy(data)
    if not snapshot.get('fetched_at'):
        return result
    day = snapshot['fetched_at'][:10]
    for award, market in snapshot.get('awards', {}).items():
        item = result['awards'].setdefault(award, dict(players=[], links={}, books=[]))
        indexed = {name_key(player['name']): player for player in item['players']}
        for player in item['players']:
            for source in CONSENSUS_SOURCES:
                player['sources'].get(source, {}).pop(day, None)
        for player in market['players']:
            key = name_key(player['name'])
            if key not in indexed:
                indexed[key] = dict(name=player['name'], sources={})
                item['players'].append(indexed[key])
            for source, values in player['sources'].items():
                raw = values.get('price')
                if source in CONSENSUS_SOURCES and raw is not None and raw > 0:
                    indexed[key]['sources'].setdefault(source, {})[day] = raw
        for source, metadata in market.get('sources', {}).items():
            if source in CONSENSUS_SOURCES:
                item.setdefault('links', {})[source] = metadata['url']
        item['snapshot_date'] = day
        item['snapshot_market'] = {name_key(p['name']): p['market'] for p in market['players']}
        item['snapshot_top'] = [name_key(p['name']) for p in market['players'][:10]]
    return result
