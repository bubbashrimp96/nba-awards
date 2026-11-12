"""Regression checks for exponential MVP rank penalties and active displayed values."""
from pathlib import Path
import json,re,unittest
import numpy as np
import pandas as pd
from mvp_exponential_rank_core import load_namespace,rank_curve,RANK_FEATURES
ROOT=Path(__file__).resolve().parent

class ExponentialRankTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model=json.loads((ROOT/'mvp_exponential_rank_penalties/model.json').read_text())
        cls.tests=pd.read_csv(ROOT/'mvp_exponential_rank_penalties/historical_backtests.csv')
        cls.ranks=pd.read_csv(ROOT/'mvp_exponential_rank_penalties/all_rankings.csv')

    def test_zero_through_fifth_and_increasing_curvature(self):
        self.assertTrue((rank_curve(np.arange(1,6),200)==0).all())
        values=rank_curve(np.arange(5,201),200)
        self.assertTrue(np.isfinite(values).all())
        self.assertTrue((np.diff(values)>0).all())
        self.assertTrue((np.diff(values,2)>0).all())
        for count in [50,100,200]:
            one=rank_curve(5+.1*count,count);two=rank_curve(5+.2*count,count)
            self.assertAlmostEqual(two-one,2*one)

    def test_raw_design_and_preserved_rules(self):
        previous=json.loads((ROOT/'exponential_availability/models.json').read_text())['MVP']
        self.assertEqual(self.model['features'],[c.replace('_places_below_fifth','_rank_exponential') if c.endswith('_places_below_fifth') else c for c in previous['features']])
        self.assertEqual(self.model['half_life'],previous['half_life'])
        self.assertEqual(self.model['regularization'],previous['regularization'])
        ns=load_namespace()
        self.assertTrue((ns['d'].ppg_qualified & ns['d'].ws48_qualified).all())
        for group in ns['make_groups'](self.model['features']):
            for feature,stat in RANK_FEATURES.items():
                expected=rank_curve(group['g'][stat+'_rank'],group['g'][stat+'_qualified_count'])
                self.assertTrue(np.allclose(expected,group['x'][:,self.model['features'].index(feature)]))

    def test_negative_weights_and_historical_reconciliation(self):
        self.assertEqual(len(self.tests),16)
        self.assertTrue((self.tests.latest_training_year<self.tests.year).all())
        for stat in ('ppg','ws48'):
            self.assertTrue((self.tests[stat+'_rank_weight']<0).all())
            self.assertTrue((self.ranks[stat+'_rank_penalty']<=0).all())
            self.assertTrue((self.ranks.loc[self.ranks[stat+'_rank']<=5,stat+'_rank_penalty']==0).all())
            rows=self.ranks.merge(self.tests[['season',stat+'_rank_weight']],on='season',validate='many_to_one')
            expected=rank_curve(rows[stat+'_rank'],rows[stat+'_qualified_count'])*rows[stat+'_rank_weight']
            self.assertTrue(np.allclose(rows[stat+'_rank_penalty'],expected))
        for _,group in self.ranks.groupby('season'):self.assertAlmostEqual(group.model_share.sum(),1)

    def test_dashboard_rank_deductions(self):
        html=(ROOT/'output/artifacts/nba-award-models-browser.html').read_text()
        data=json.loads(re.search(r'const awardComparisons=(.*?);\n',html)[1])
        for season in data['MVP']:
            current=pd.read_csv(ROOT/'revised_awards/historical_backtests.csv');current=current[current.award=='MVP']
            saved=current[current.season==season['season']].iloc[0]
            self.assertEqual(season['predicted'][0]['player'],saved.predicted)
            for player in season['players']:
                for feature,stat in RANK_FEATURES.items():
                    if player[stat+'_rank'] is not None:
                        from revised_award_core import rank_curve as current_curve
                        curve=current_curve(player[stat+'_rank'],player[stat+'_qualified_count'],stat)
                        self.assertAlmostEqual(player['stats'][feature],curve)
                        self.assertAlmostEqual(player[stat+'_rank_penalty'],curve*saved[stat+'_rank_weight'])

if __name__=='__main__':unittest.main()
