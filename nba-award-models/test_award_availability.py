"""Regression checks for below-85% availability across all award models."""
from pathlib import Path
import json,re,unittest
import numpy as np
import pandas as pd
from award_availability_core import load_namespace,AWARDS
ROOT=Path(__file__).resolve().parent

class AvailabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns=load_namespace()
        cls.models=json.loads((ROOT/'all_awards_availability/models.json').read_text())
        cls.baseline=json.loads((ROOT/'models.json').read_text())
        cls.tests=pd.read_csv(ROOT/'all_awards_availability/historical_backtests.csv')
        cls.rankings=pd.read_csv(ROOT/'all_awards_availability/all_rankings.csv')

    def test_thresholds_and_shortened_schedules(self):
        self.assertEqual(np.ceil(.85*np.array([82,72,66])).tolist(),[70,62,57])
        data=self.ns['d'];data=data[data.year>=1986]
        self.assertTrue((data.availability_threshold==np.ceil(.85*data.schedule_games)).all())
        self.assertTrue((data.games_below_threshold==(data.availability_threshold-data.G).clip(lower=0)).all())
        for year,games in [(2012,66),(2021,72)]:
            self.assertTrue((data.loc[data.year==year,'schedule_games']==games).all())

    def test_only_shortfall_feature_is_added(self):
        for award in AWARDS:
            model=self.models[award];baseline=self.baseline[award]
            self.assertEqual(model['features'],baseline['features']+['games_below_threshold'])
            self.assertEqual(model['half_life'],baseline['half_life'])
            self.assertEqual(model['regularization'],baseline['regularization'])
            self.assertLess(model['coefficients'][-1],0)
            for group in self.ns['groups'](award):
                self.assertTrue(np.array_equal(group['x'][:,-1],group['g'].games_below_threshold.to_numpy()))
        self.assertNotIn('G',self.models['MIP']['features'])

    def test_historical_penalty_slopes_and_zero_above_threshold(self):
        self.assertEqual(len(self.tests),64)
        self.assertTrue((self.tests.latest_training_year<self.tests.year).all())
        self.assertTrue((self.tests.penalty_per_game<0).all())
        rows=self.rankings
        self.assertTrue((rows.availability_penalty<=0).all())
        self.assertTrue((rows.loc[rows.shortfall==0,'availability_penalty']==0).all())
        self.assertTrue(np.allclose(rows.availability_penalty,rows.shortfall*rows.penalty_per_game))
        for _,season in rows.groupby(['award','season']):self.assertAlmostEqual(season.model_share.sum(),1)

    def test_original_season_baselines_are_reproduced(self):
        original=pd.read_csv(ROOT/'historical_backtests.csv')
        before=pd.read_csv(ROOT/'all_awards_availability/before_after.csv')
        original=original[(original.award!='MVP')&(original.weighting=='recency')]
        merged=before.merge(original,on=['award','season'],validate='one_to_one')
        self.assertEqual(len(merged),44)
        self.assertTrue((merged.predicted_before==merged.predicted).all())
        self.assertTrue(np.allclose(merged.log_loss_before,merged.winner_log_loss,atol=1e-6))

    def test_every_displayed_award_has_correct_availability(self):
        html=(ROOT/'output/artifacts/nba-award-models-browser.html').read_text()
        comparisons=json.loads(re.search(r'const awardComparisons=(.*?);\n',html)[1])
        models=json.loads(re.search(r'const awardModels=(.*?);\n',html)[1])
        self.assertEqual(sum(map(len,comparisons.values())),130)
        for award,seasons in comparisons.items():
            self.assertIn('availability_exponential',models[award]['features'])
            saved=pd.read_csv(ROOT/'revised_awards/historical_backtests.csv')
            current=saved[saved.award==award]
            for season in seasons:
                fit=current[current.season==season['season']].iloc[0]
                self.assertEqual(season['predicted'][0]['player'],fit.predicted)
                for player in season['players']:
                    shortfall=max(0,player['availability_threshold']-player['games_played'])
                    self.assertEqual(player['availability_shortfall'],shortfall)
                    from revised_award_core import availability_curve
                    self.assertAlmostEqual(player['availability_penalty'],fit.availability_weight*availability_curve(shortfall,player['schedule_games']))
        self.assertIn('81 / 130',html)

if __name__=='__main__':unittest.main()
