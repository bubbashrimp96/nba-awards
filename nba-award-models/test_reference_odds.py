import csv
import json
import tempfile
import unittest
from pathlib import Path
from reference_odds import reference_rows, parse_oddschecker, chart_reference
from bookmaker_movement import merge_bookmaker_history, merge_latest_market_snapshot
from fetch_odds import name_key

class ReferenceOddsTests(unittest.TestCase):
    def test_exchange_uses_raw_price_and_keeps_exchange_only_players(self):
        market = {'players': [dict(name='Luka Doncic', sources={'polymarket': {'price': .25, 'prob': .2}, 'kalshi': {'price': .2, 'prob': .15}})],
                  'references': {'oddschecker': {'rows': [{'name': 'Luka Dončić', 'decimal_odds': 5}]}}}
        rows = reference_rows(market, name_key)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['polymarket'], 4)
        self.assertEqual(rows[0]['kalshi'], 5)
        self.assertEqual(rows[0]['oddschecker'], 5)
        market['players'][0]['sources']['kalshi']['price'] = 0
        self.assertNotIn('kalshi', reference_rows(market, name_key)[0])

    def test_chart_latest_snapshot_replaces_old_sources(self):
        data = {'awards': {'MVP': {'players': [{'name': 'A', 'sources': {
            'kalshi': {'2026-11-14': .1}, 'sportsbooks': {'2026-11-14': .9}}}], 'links': {}, 'books': []}}}
        snapshot = {'fetched_at': '2026-11-14T13:00:00Z', 'awards': {'MVP': {
            'players': [{'name': 'A', 'market': .8, 'sources': {'sportsbet': {'price': .8}}}],
            'sources': {'sportsbet': {'url': 'https://example.test'}}}}}
        merged = merge_latest_market_snapshot(data, snapshot)['awards']['MVP']
        player = merged['players'][0]
        self.assertEqual(player['sources']['sportsbet'], {'2026-11-14': .8})
        self.assertNotIn('2026-11-14', player['sources']['kalshi'])
        self.assertEqual(player['sources']['sportsbooks'], {'2026-11-14': .9})
        self.assertEqual(merged['snapshot_market'], {'a': .8})
        self.assertEqual(merged['snapshot_top'], ['a'])

    def test_oddschecker_uses_latest_chart_snapshot_only(self):
        history = {'fetched_at': '2026-11-14T12:00:00Z', 'awards': {'MVP': {
            'players': [{'name': 'A', 'sources': {'sportsbooks': {'2026-11-13': .2, '2026-11-14': .25}}},
                        {'name': 'B', 'sources': {'sportsbooks': {'2026-11-13': .5}}}], 'links': {}}}}
        reference = chart_reference(history, 'MVP')
        self.assertEqual(reference['snapshot_date'], '2026-11-14')
        self.assertEqual(reference['rows'], [{'name': 'A', 'decimal_odds': 4}])
        self.assertEqual(chart_reference(history, 'CPOY')['status'], 'unavailable')

    def test_oddschecker_uses_active_books_and_median(self):
        data = {'bets': [{'betId': 1, 'betName': 'A'}], 'odds': [
            {'betId': 1, 'bookmakerCode': 'X', 'status': 'ACTIVE', 'oddsDecimal': 4},
            {'betId': 1, 'bookmakerCode': 'Y', 'status': 'ACTIVE', 'oddsDecimal': 6},
            {'betId': 1, 'bookmakerCode': 'BF', 'status': 'ACTIVE', 'oddsDecimal': 100},
            {'betId': 1, 'bookmakerCode': 'Z', 'status': 'SUSPENDED', 'oddsDecimal': 100}]}
        self.assertEqual(parse_oddschecker(data), [{'name': 'A', 'decimal_odds': 5}])

    def test_observed_history_latest_quote_without_backfilling(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            history = root/'history.csv'
            with history.open('w', newline='') as f:
                writer = csv.writer(f);writer.writerow(['fetched_at','award','source','name','decimal_odds','prob'])
                writer.writerows([['2026-11-14T12:00:00Z','MVP','sportsbet','Luka Doncic',4,.2],
                                  ['2026-11-14T13:00:00Z','MVP','sportsbet','Luka Dončić',5,.15],
                                  ['2026-11-16T12:00:00Z','MVP','neds','Luka Doncic',6,.1]])
            data = {'awards': {'MVP': {'players': [{'name': 'Luka Doncic','sources': {'kalshi': {'2026-11-01': .1}}}], 'links': {},'books': []}}, 'method': 'History'}
            merged = merge_bookmaker_history(data, history, root/'missing.json')
            players = merged['awards']['MVP']['players']
            self.assertEqual(len(players), 1)
            self.assertEqual(players[0]['sources']['sportsbet'], {'2026-11-14': .2})
            self.assertEqual(players[0]['sources']['neds'], {'2026-11-16': 1/6})
            self.assertNotIn('sportsbet', data['awards']['MVP']['players'][0]['sources'])

if __name__ == '__main__':
    unittest.main()
