"""Validate the supplied flowchart's eight paths, ties, and unknown inputs."""
import itertools,unittest
import numpy as np
import pandas as pd
from coy_flow import add_flow
class CoachFlowTests(unittest.TestCase):
    def test_all_eight_flowchart_paths(self):
        rows=[];expected=[]
        for top4,new,exceeded in itertools.product([False,True],repeat=3):
            rows.append(dict(year=2026,conference_rank=4 if top4 else 5,prior_coy_same_team=0 if new else 1,expected_team_wins=40,team_wins=41 if exceeded else 40))
            expected.append('Runaway' if top4 and new and exceeded else 'Moderate chance' if (top4 and new) or (exceeded and (top4 or new)) else 'No chance')
        result=add_flow(pd.DataFrame(rows))
        self.assertEqual(result.flow_tier.tolist(),expected)
        self.assertEqual(result.flow_moderate_or_better.tolist(),[float(x!='No chance') for x in expected])
        self.assertEqual(result.flow_runaway.tolist(),[float(x=='Runaway') for x in expected])
    def test_missing_expectations_and_pre_archive_are_unknown(self):
        rows=[dict(year=y,conference_rank=1,prior_coy_same_team=0,expected_team_wins=e,team_wins=60) for y,e in [(2002,0),(2026,np.nan)]]
        result=add_flow(pd.DataFrame(rows))
        self.assertEqual(result.flow_tier.tolist(),['Unknown','Unknown'])
        self.assertTrue(result.flow_top4_record.isna().all())
        self.assertTrue(result.flow_moderate_or_better.eq(0).all())
    def test_record_boundary_and_exact_expectation(self):
        result=add_flow(pd.DataFrame([dict(year=2026,conference_rank=rank,prior_coy_same_team=0,expected_team_wins=40,team_wins=wins) for rank,wins in [(4,40),(4,40.01),(4.5,40.01)]]))
        self.assertEqual(result.flow_tier.tolist(),['Moderate chance','Runaway','Moderate chance'])
    def test_saved_model_reproduces_flow_experiment(self):
        from pathlib import Path
        import json
        root=Path(__file__).resolve().parent
        actual=pd.read_csv(root/'coy_model/historical_backtests.csv')
        expected=pd.read_csv(root/'experiments/coy_flow/backtests.csv')
        expected=expected[expected.variant=='learned_flow']
        self.assertEqual(actual.predicted.tolist(),expected.predicted.tolist())
        np.testing.assert_allclose(actual.log_loss,expected.log_loss,atol=1e-6)
        model=json.loads((root/'coy_model/model.json').read_text())
        for feature in ['flow_moderate_or_better','flow_runaway']:
            self.assertGreaterEqual(model['coefficients'][model['features'].index(feature)],0)
if __name__=='__main__':unittest.main()
