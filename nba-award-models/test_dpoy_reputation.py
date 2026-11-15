"""Reputation must use earlier seasons and reproduce the approved experiment."""
import unittest
from pathlib import Path
import pandas as pd
import numpy as np
from revised_award_core import defensive_reputation,features_for
ROOT=Path(__file__).resolve().parent
class ReputationTests(unittest.TestCase):
    def test_first_recognition_is_not_used_in_same_season(self):
        d=defensive_reputation().set_index(['PlayerID','year'])
        # Ben Wallace first received votes in 2001 and first made All-Defense in 2002.
        self.assertEqual(d.loc[('wallabe01',2001),'prior_dpoy_votes'],0)
        self.assertEqual(d.loc[('wallabe01',2002),'prior_dpoy_votes'],1)
        self.assertEqual(d.loc[('wallabe01',2002),'prior_all_defense'],0)
        self.assertEqual(d.loc[('wallabe01',2003),'prior_all_defense'],1)
        # Cason Wallace's first selection in 2026 cannot leak into that season.
        self.assertEqual(d.loc[('wallaca01',2026),'prior_all_defense'],0)
        for col in ['prior_dpoy_votes','prior_all_defense']:
            self.assertTrue(d[col].isin([0,1]).all())
    def test_approved_backtest_reproduced(self):
        actual=pd.read_csv(ROOT/'revised_awards/historical_backtests.csv')
        actual=actual[actual.award=='DPOY'].sort_values('year')
        expected=pd.read_csv(ROOT/'experiments/dpoy_reputation/backtests.csv')
        expected=expected[expected.variant=='both_prior'].sort_values('year')
        self.assertEqual(actual.predicted.tolist(),expected.predicted.tolist())
        np.testing.assert_allclose(actual.log_loss,expected.log_loss,atol=1e-6)
        self.assertEqual(actual.top1.sum(),17)
        self.assertEqual(actual.top3.sum(),18)
    def test_no_other_award_gains_reputation(self):
        for award in ['MVP','ROY','MIP','SMOY']:
            self.assertNotIn('prior_dpoy_votes',features_for(award))
            self.assertNotIn('prior_all_defense',features_for(award))
if __name__=='__main__':unittest.main()
