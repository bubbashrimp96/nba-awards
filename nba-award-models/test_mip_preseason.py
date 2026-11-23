import json
import unittest
import pandas as pd
from revised_award_core import features_for, load_namespace, preseason_lines

class MipPreseasonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns = load_namespace('MIP')
        cls.data = cls.ns['d']

    def test_feature_is_fitted_and_positive(self):
        model = json.loads(open('revised_awards/models.json').read())['MIP']
        self.assertIn('surprise_PTS', features_for('MIP'))
        self.assertEqual(model['features'], features_for('MIP'))
        self.assertGreater(model['coefficients'][model['features'].index('surprise_PTS')], 0)

    def test_unusable_seasons_are_constant_zero(self):
        _, usable = preseason_lines()
        self.assertNotIn(2014, usable)          # 2013-14: only 15 archived ESPN players
        self.assertNotIn(2005, usable)          # no published source before 2008-09
        self.assertIn(2020, usable)             # FantasyPros fills 2019-20
        for year in (2005, 2014):
            self.assertTrue(self.data.loc[self.data.year == year, 'surprise_PTS'].eq(0).all())

    def test_surprise_is_actual_minus_expected(self):
        row = self.data[(self.data.year == 2026) & (self.data.PlayerID == 'alexani01')].iloc[0]
        self.assertAlmostEqual(row.surprise_PTS, row.PTS - row.expected_PTS)
        self.assertLess(row.expected_PTS, 10)  # projected ~9.3 PPG before his 20.8 PPG season

if __name__ == '__main__':
    unittest.main()
