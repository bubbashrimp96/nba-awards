import unittest
from australian_odds import quote, neds_rows, urls, EVENTS
from fetch_odds import combine

class BookmakerTests(unittest.TestCase):
    def test_fractional_quote_and_name(self):
        row = quote('Nikola Jokic (Denver Nuggets)', 30, 1)
        self.assertEqual(row['name'], 'Nikola Jokic')
        self.assertEqual(row['decimal_odds'], 31)
        self.assertAlmostEqual(row['price'], 1/31)

    def test_neds_scopes_event_and_visibility(self):
        card = {'events': {'target': {'visible': True, 'match_status': 'BettingOpen', 'market_ids': ['m']}},
                'markets': {'m': {'visible': True, 'entrant_ids': ['a', 'b']}},
                'entrants': {'a': {'name': 'A (Team)', 'visible': True}, 'b': {'name': 'B', 'visible': False}},
                'prices': {'a:win:': {'odds': {'numerator': 7, 'denominator': 1}}, 'b:win:': {'odds': {'numerator': 1, 'denominator': 1}}}}
        self.assertEqual([r['name'] for r in neds_rows(card, 'target')], ['A'])
        card['events']['target']['match_status'] = 'Closed'
        self.assertEqual(neds_rows(card, 'target'), [])

    def test_consensus_keeps_raw_prices_and_overround(self):
        sources = {'sportsbet': {'rows': [dict(name='Victor',price=.82,prob=.65,wide=False),dict(name='Other',price=.4,prob=.35,wide=False)]},
                   'neds': {'rows': [dict(name='Victor',price=.80,prob=.66,wide=False)]}}
        rows = combine(sources)
        self.assertAlmostEqual(rows[0]['market'], .81)
        self.assertAlmostEqual(rows[0]['sources']['sportsbet']['prob'], .82)
        self.assertGreater(sum(p['market'] for p in rows), 1)

    def test_quotes_survive_consensus(self):
        rows = [dict(quote('A', 7, 1), prob=.1)]
        p = combine({'sportsbet': {'rows': rows}})[0]
        self.assertEqual(p['sources']['sportsbet']['decimal_odds'], 8)
        self.assertEqual(p['market'], .125)
        self.assertEqual(len(EVENTS), 7)
        self.assertTrue(all(set(urls(a)) == {'sportsbet', 'neds'} for a in EVENTS))

if __name__ == '__main__':
    unittest.main()
