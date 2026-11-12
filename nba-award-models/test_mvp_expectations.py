"""Regression checks for market expectation inputs and the generated MVP dashboard."""
from pathlib import Path
import json
import re
import unittest
import numpy as np
import pandas as pd
from mvp_expectations_core import load_namespace

ROOT = Path(__file__).resolve().parent

class ExpectationsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns = load_namespace()
        cls.data = cls.ns['d']
        cls.model = json.loads((ROOT / 'mvp_expectations_revision/model.json').read_text())

    def test_observed_team_coverage_and_okc_example(self):
        known = self.data[(self.data.year >= 2003) & self.data.team_games.notna()]
        self.assertTrue(known.preseason_win_total.notna().all())
        okc = known[(known.year == 2017) & (known.Tm == 'OKC')].iloc[0]
        self.assertEqual(okc.preseason_win_total, 45)
        self.assertEqual(okc.team_wins, 47)
        self.assertEqual(okc.wins_above_expectation, 2)

    def test_schedule_scaling_and_neutral_missing_history(self):
        for year, games in [(2012,66),(2021,72)]:
            season = self.data[(self.data.year == year) & self.data.expectations_available]
            self.assertTrue((season.preseason_schedule_games == games).all())
            self.assertTrue(np.allclose(season.expected_team_wins, season.preseason_win_total * season.schedule_games / games))
        uneven = self.data[(self.data.year == 2020) & self.data.expectations_available]
        self.assertTrue(np.allclose(uneven.expected_team_wins, uneven.preseason_win_total * uneven.schedule_games / 82))
        self.assertTrue((self.data[self.data.year < 2003].wins_above_expectation == 0).all())
        for group in self.ns['make_groups'](self.model['features']):
            if group['year'] < 2003:
                self.assertTrue((group['x'][:,-1] == 0).all())

    def test_historical_constraints_and_rankings(self):
        tests = pd.read_csv(ROOT / 'mvp_expectations_revision/historical_backtests.csv')
        rankings = pd.read_csv(ROOT / 'mvp_expectations_revision/all_rankings.csv')
        self.assertEqual(len(tests),16)
        self.assertTrue((tests.latest_training_year < tests.year).all())
        self.assertTrue((rankings.penalty_per_game < 0).all())
        self.assertTrue((rankings.availability_penalty <= 0).all())
        for season, rows in rankings.groupby('season'):
            self.assertAlmostEqual(rows.model_share.sum(),1)
            self.assertEqual(rows['rank'].tolist(), list(range(1,len(rows)+1)))
        self.assertGreaterEqual(self.model['coefficients'][-1],0)
        baseline = json.loads((ROOT / 'mvp_per_availability/model.json').read_text())
        self.assertEqual(self.model['features'],baseline['features'] + ['wins_above_expectation'])
        self.assertEqual(self.model['half_life'],baseline['half_life'])
        self.assertEqual(self.model['regularization'],baseline['regularization'])

    def test_dashboard_values_and_summary(self):
        html = (ROOT / 'output/artifacts/nba-award-models-browser.html').read_text()
        embedded = json.loads(re.search(r'const awardComparisons=(.*?);\n',html)[1])
        self.assertEqual(sum(map(len,embedded.values())),130)
        for season in embedded['MVP']:
            for player in season['players']:
                if player['expected_team_wins'] is not None:
                    self.assertAlmostEqual(player['stats']['wins_above_expectation'], player['stats']['team_wins']-player['expected_team_wins'])
                self.assertLessEqual(player['availability_penalty'],0)
        summary = json.loads((ROOT / 'dashboard_summary.json').read_text())
        for award,seasons in embedded.items():
            correct = sum(any(p['actual_rank']==1 and p['model_rank']==1 for p in season['players']) for season in seasons)
            self.assertEqual(correct,summary[award]['correct'])

if __name__ == '__main__':
    unittest.main()
