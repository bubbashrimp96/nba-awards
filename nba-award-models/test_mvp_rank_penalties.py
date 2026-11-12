"""Regression checks for qualified MVP PPG/WS48 rank penalties."""
from pathlib import Path
import json,re,unittest
import numpy as np
import pandas as pd
from mvp_rank_penalties_core import load_namespace,PENALTY_FEATURES
ROOT=Path(__file__).resolve().parent

class RankPenaltyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns=load_namespace()
        cls.model=json.loads((ROOT/'mvp_top5_rank_penalties/model.json').read_text())
        cls.ranks=pd.read_csv(ROOT/'data/qualified_ranks/qualified_ranks.csv')

    def test_unqualified_players_are_excluded(self):
        audit=self.ns['rank_audit']
        self.assertTrue((self.ns['d'].ppg_qualified & self.ns['d'].ws48_qualified).all())
        self.assertEqual(len(self.ns['d']),int(audit.mvp_rate_qualified.sum()))
        player=audit[(audit.year==2025)&(audit.PlayerID=='harteis01')].iloc[0]
        self.assertFalse(player.ppg_qualified)
        self.assertTrue(player.ws48_qualified)
        self.assertFalse(player.mvp_rate_qualified)
        self.assertFalse(((self.ns['d'].year==2025)&(self.ns['d'].PlayerID=='harteis01')).any())

    def test_league_ranks_and_ties(self):
        for stat,players in [('ppg',['gilgesh01','antetgi01','jokicni01','edwaran01','tatumja01']),('ws48',['gilgesh01','jokicni01','allenja01','antetgi01','butleji01'])]:
            top=self.ranks[(self.ranks.year==2025)&(self.ranks.stat==stat)].sort_values('rank').head(5)
            self.assertEqual(top.PlayerID.tolist(),players)
        for _,group in self.ranks.groupby(['year','stat']):
            self.assertTrue(np.allclose(group['rank'],group.value.where(group.qualified).rank(method='min',ascending=False),equal_nan=True))
        self.assertEqual(pd.Series([.3,.25,.2,.2]).rank(method='min',ascending=False).tolist(),[1,2,3,3])

    def test_penalty_units_and_raw_design(self):
        self.assertEqual(np.maximum(0,np.array([1,4,5,6,7,10])-5).tolist(),[0,0,0,1,2,5])
        for group in self.ns['make_groups'](self.model['features']):
            for stat in ('ppg','ws48'):
                feature=stat+'_places_below_fifth'
                self.assertTrue(np.array_equal(group['x'][:,self.model['features'].index(feature)],(group['g'][stat+'_rank']-5).clip(lower=0).to_numpy()))
        for feature in PENALTY_FEATURES:
            weight=self.model['coefficients'][self.model['features'].index(feature)]
            self.assertLess(weight,0)
            self.assertEqual(weight*0,0)
            self.assertLess(weight*2,weight)

    def test_saved_constraints_and_training_cutoffs(self):
        tests=pd.read_csv(ROOT/'mvp_top5_rank_penalties/historical_backtests.csv')
        rankings=pd.read_csv(ROOT/'mvp_top5_rank_penalties/all_rankings.csv')
        self.assertEqual(len(tests),16)
        self.assertTrue((tests.latest_training_year<tests.year).all())
        for stat in ('ppg','ws48'):
            self.assertTrue((tests[stat+'_penalty_per_place']<0).all())
            self.assertTrue((rankings[stat+'_rank_penalty']<=0).all())
            self.assertTrue((rankings.loc[rankings[stat+'_rank']<=5,stat+'_rank_penalty']==0).all())
            joined=rankings.merge(tests[['season',stat+'_penalty_per_place']],on='season',validate='many_to_one')
            self.assertTrue(np.allclose(joined[stat+'_rank_penalty'],joined[stat+'_places_below_fifth']*joined[stat+'_penalty_per_place']))
        for season,group in rankings.groupby('season'):
            self.assertAlmostEqual(group.model_share.sum(),1)
            self.assertEqual(set(group.player),set(self.ns['d'].loc[self.ns['d'].Season==season,'Player Name']))

    def test_dashboard_values(self):
        html=(ROOT/'output/artifacts/nba-award-models-browser.html').read_text()
        data=json.loads(re.search(r'const awardComparisons=(.*?);\n',html)[1])
        tests=pd.read_csv(ROOT/'revised_awards/historical_backtests.csv');tests=tests[tests.award=='MVP']
        self.assertEqual(sum(map(len,data.values())),130)
        for result in data['MVP']:
            saved=tests[tests.season==result['season']].iloc[0]
            self.assertEqual(result['predicted'][0]['player'],saved.predicted)
            for player in result['players']:
                for stat in ('ppg','ws48'):
                    if player[stat+'_rank'] is not None:
                        units=max(0,player[stat+'_rank']-5)
                        from revised_award_core import rank_curve
                        curve=rank_curve(player[stat+'_rank'],player[stat+'_qualified_count'],stat)
                        self.assertAlmostEqual(player['stats'][stat+'_rank_exponential'],curve)
                        self.assertAlmostEqual(player[stat+'_rank_penalty'],curve*saved[stat+'_rank_weight'])

if __name__=='__main__':unittest.main()
