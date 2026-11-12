"""Current 26-season models, balanced curves, and DPOY/Sixth-Man team inputs."""
from pathlib import Path
import json,re,unittest
import numpy as np
import pandas as pd
from revised_award_core import load_namespace,features_for,availability_curve,rank_curve,team_context
from exponential_availability_core import exponential_shortfall
from mvp_exponential_rank_core import rank_curve as prior_rank_curve
ROOT=Path(__file__).resolve().parent

class RevisedAwardsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models=json.loads((ROOT/'revised_awards/models.json').read_text())
        cls.tests=pd.read_csv(ROOT/'revised_awards/historical_backtests.csv')
        cls.coefficients=pd.read_csv(ROOT/'revised_awards/season_coefficients.csv')
        cls.rankings=pd.read_csv(ROOT/'revised_awards/all_rankings.csv')

    def test_gentle_start_and_exponential_large_shortfalls(self):
        for schedule in (50,66,72,82):
            values=availability_curve(np.arange(0,42),schedule)
            self.assertEqual(values[0],0)
            self.assertTrue((np.diff(values)>0).all())
            self.assertTrue((np.diff(values,2)>0).all())
            self.assertTrue((values[1:]<exponential_shortfall(np.arange(1,42),schedule)).all())
        small=availability_curve(4,82)/exponential_shortfall(4,82)
        large=availability_curve(39,82)/exponential_shortfall(39,82)
        self.assertLess(small,large)
        self.assertLess(small,.2)
        self.assertGreater(large,.8)

    def test_only_scoring_rank_curve_is_steeper(self):
        ranks=np.arange(1,201)
        self.assertTrue((rank_curve(np.arange(1,6),200,'ppg')==0).all())
        self.assertGreater(rank_curve(48,245,'ppg'),prior_rank_curve(48,245))
        self.assertTrue(np.allclose(rank_curve(ranks,200,'ws48'),prior_rank_curve(ranks,200)))

    def test_team_rating_records_and_seed_fallbacks(self):
        context=team_context()
        self.assertEqual(len(context),1177)
        defense=pd.read_csv(ROOT/'data/team_defense/team_defense.csv')
        merged=context.merge(defense,on=['Season','Tm'],suffixes=('_context','_source'),validate='one_to_one')
        self.assertTrue((merged.team_wins==merged.source_wins).all())
        self.assertTrue((merged.team_losses==merged.source_losses).all())
        self.assertTrue(defense[defense.year>=1997].provider.str.startswith('NBA Stats').all())
        self.assertTrue(context.conference_seed.between(1,context.conference_size).all())
        self.assertTrue((context.loc[context.seed_fallback,'conference_seed']==context.loc[context.seed_fallback,'conference_rank']).all())
        for _,group in defense.groupby('Season'):
            ordered=group.sort_values(['team_defensive_rating','team_defensive_rank'])
            self.assertTrue((np.diff(ordered.team_defensive_rank)>=0).all())

    def test_award_features_and_favorable_team_directions(self):
        self.assertNotIn('DRB',self.models['DPOY']['features'])
        self.assertIn('DRtg',self.models['DPOY']['features'])
        self.assertIn('team_defensive_rank',self.models['DPOY']['features'])
        self.assertIn('team_wins',self.models['DPOY']['features'])
        self.assertIn('conference_seed',self.models['SMOY']['features'])
        for award,feature in [('DPOY','team_defensive_rank'),('SMOY','conference_seed')]:
            rows=self.coefficients[(self.coefficients.award==award)&(self.coefficients.feature==feature)]
            self.assertEqual(len(rows),26)
            self.assertTrue((rows.coefficient<0).all())
        rows=self.coefficients[(self.coefficients.award=='DPOY')&(self.coefficients.feature=='team_wins')]
        self.assertTrue((rows.coefficient>=0).all())

    def test_130_prior_only_comparisons_and_raw_curve_design(self):
        self.assertEqual(len(self.tests),130)
        self.assertTrue((self.tests.latest_training_year<self.tests.year).all())
        self.assertTrue((self.tests.availability_weight<0).all())
        for award,rows in self.tests.groupby('award'):
            self.assertEqual(len(rows),26)
            self.assertEqual(rows.year.min(),2001);self.assertEqual(rows.year.max(),2026)
            ns=load_namespace(award);columns=features_for(award)
            for group in ns['make_groups'](columns):
                expected=availability_curve(group['g'].games_below_threshold,group['g'].schedule_games)
                self.assertTrue(np.allclose(group['x'][:,columns.index('availability_exponential')],expected))
        for _,rows in self.rankings.groupby(['award','season']):self.assertAlmostEqual(rows.model_share.sum(),1)

    def test_motivating_cases_and_all_display_values(self):
        mvp=self.rankings[(self.rankings.award=='MVP')&(self.rankings.season=='2022-23')]
        embiid=mvp[mvp.player=='Joel Embiid'].iloc[0];sabonis=mvp[mvp.player=='Domantas Sabonis'].iloc[0]
        self.assertLess(embiid['rank'],sabonis['rank']);self.assertGreater(embiid.availability_penalty,-1)
        roy=self.rankings[(self.rankings.award=='ROY')&(self.rankings.season=='2016-17')]
        self.assertEqual(roy.sort_values('rank').iloc[0].player,'Malcolm Brogdon')
        self.assertLess(roy[roy.player=='Joel Embiid'].iloc[0].availability_penalty,-7)
        html=(ROOT/'output/artifacts/nba-award-models-browser.html').read_text()
        data=json.loads(re.search(r'const awardComparisons=(.*?);\n',html)[1])
        summary=json.loads((ROOT/'dashboard_summary.json').read_text())
        for award,seasons in data.items():
            self.assertEqual(len(seasons),26)
            self.assertEqual(seasons[0]['season'],'2000-01')
            self.assertEqual(seasons[-1]['season'],'2025-26')
            for result in seasons:
                year=int(result['season'][:4])+1
                voting=json.loads((ROOT/f'data/award_voting/{year}.json').read_text())[award]
                self.assertEqual(result['actual'],voting['results'])
                saved=self.tests[(self.tests.award==award)&(self.tests.season==result['season'])].iloc[0]
                self.assertEqual(saved.predicted,result['predicted'][0]['player'])
                for player in result['players']:
                    curve=availability_curve(player['availability_shortfall'],player['schedule_games'])
                    self.assertAlmostEqual(player['stats']['availability_exponential'],curve)
                    self.assertAlmostEqual(player['availability_penalty'],saved.availability_weight*curve)
            self.assertEqual(summary[award]['correct'],sum(any(p['actual_rank']==1 and p['model_rank']==1 for p in r['players']) for r in seasons))
        self.assertIn('81 / 130',html)

if __name__=='__main__':unittest.main()
