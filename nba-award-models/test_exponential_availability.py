"""Tests for the shared exponential availability curve and active award models."""
from pathlib import Path
import json,re,unittest
import numpy as np
import pandas as pd
from exponential_availability_core import load_namespace,FEATURE,exponential_shortfall
ROOT=Path(__file__).resolve().parent

class ExponentialAvailabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models=json.loads((ROOT/'exponential_availability/models.json').read_text())
        cls.tests=pd.read_csv(ROOT/'exponential_availability/historical_backtests.csv')
        cls.ranks=pd.read_csv(ROOT/'exponential_availability/all_rankings.csv')

    def test_zero_increasing_and_convex_curve(self):
        curve=exponential_shortfall(np.arange(0,71),82)
        self.assertEqual(curve[0],0)
        self.assertTrue((np.diff(curve)>0).all())
        self.assertTrue((np.diff(curve,2)>0).all())
        self.assertEqual(exponential_shortfall(-5,82),0)
        for schedule in (66,72,82):
            one=exponential_shortfall(.1*schedule,schedule)
            two=exponential_shortfall(.2*schedule,schedule)
            self.assertAlmostEqual(two-one,2*one)
            self.assertAlmostEqual(one/schedule,exponential_shortfall(8.2,82)/82)

    def test_raw_design_and_preserved_features(self):
        previous=json.loads((ROOT/'all_awards_availability/models.json').read_text())
        previous['MVP']=json.loads((ROOT/'mvp_top5_rank_penalties/model.json').read_text())
        for award,model in self.models.items():
            self.assertEqual(model['features'],[FEATURE if c=='games_below_threshold' else c for c in previous[award]['features']])
            self.assertEqual(model['half_life'],previous[award]['half_life'])
            self.assertEqual(model['regularization'],previous[award]['regularization'])
            ns=load_namespace(award)
            for group in ns['make_groups'](model['features']):
                expected=exponential_shortfall(group['g'].games_below_threshold,group['g'].schedule_games)
                self.assertTrue(np.allclose(group['x'][:,model['features'].index(FEATURE)],expected))

    def test_all_historical_contributions(self):
        self.assertEqual(len(self.tests),80)
        self.assertTrue((self.tests.latest_training_year<self.tests.year).all())
        self.assertTrue((self.tests.availability_weight<0).all())
        rows=self.ranks
        self.assertTrue(np.isfinite(rows.model_share).all())
        self.assertTrue((rows.availability_penalty<=0).all())
        self.assertTrue((rows.loc[rows.shortfall==0,'availability_penalty']==0).all())
        self.assertTrue(np.allclose(rows.availability_penalty,rows.availability_weight*exponential_shortfall(rows.shortfall,rows.schedule_games)))
        for _,group in rows.groupby(['award','season']):self.assertAlmostEqual(group.model_share.sum(),1)

    def test_embiid_is_penalized_without_exclusion(self):
        rows=self.ranks[(self.ranks.award=='ROY')&(self.ranks.season=='2016-17')]
        player=rows[rows.player=='Joel Embiid'].iloc[0]
        self.assertEqual(player.games,31)
        self.assertEqual(player.shortfall,39)
        self.assertEqual(player['rank'],4)
        self.assertLess(player.availability_penalty,-7)
        self.assertEqual(rows.sort_values('rank').iloc[0].player,'Malcolm Brogdon')
        linear=pd.read_csv(ROOT/'all_awards_availability/all_rankings.csv')
        old=linear[(linear.award=='ROY')&(linear.season=='2016-17')&(linear.player=='Joel Embiid')].iloc[0]
        self.assertLess(player.availability_penalty,old.availability_penalty)

    def test_dashboard_uses_exponential_values(self):
        html=(ROOT/'output/artifacts/nba-award-models-browser.html').read_text()
        data=json.loads(re.search(r'const awardComparisons=(.*?);\n',html)[1])
        for award,seasons in data.items():
            for season in seasons:
                current=pd.read_csv(ROOT/'revised_awards/historical_backtests.csv')
                saved=current[(current.award==award)&(current.season==season['season'])].iloc[0]
                self.assertEqual(season['predicted'][0]['player'],saved.predicted)
                for player in season['players']:
                    from revised_award_core import availability_curve
                    expected=availability_curve(player['availability_shortfall'],player['schedule_games'])
                    self.assertAlmostEqual(player['stats'][FEATURE],expected)
                    self.assertAlmostEqual(player['availability_penalty'],saved.availability_weight*expected)
        self.assertIn('81 / 130',html)

if __name__=='__main__':unittest.main()
