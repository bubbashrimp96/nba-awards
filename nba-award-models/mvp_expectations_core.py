"""Shared MVP preprocessing for preseason expectations and availability."""
from pathlib import Path
import ast
import pandas as pd

ROOT = Path(__file__).resolve().parent

def load_namespace():
    source = (ROOT / 'improve_mvp_availability.py').read_text().split('current=json.loads')[0]
    # Reward exceeding expectations; retain the strictly negative availability slope.
    source = source.replace("(None,-1e-8) if c=='games_below_threshold' else (None,None)",
                            "(None,-1e-8) if c=='games_below_threshold' else (0,None) if c=='wins_above_expectation' else (None,None)")
    tree = ast.parse(source)
    tree.body = [node for node in tree.body if not isinstance(node, ast.Expr)]
    namespace = {'__file__': str(ROOT / 'improve_mvp_availability.py')}
    exec(compile(tree, str(ROOT / 'improve_mvp_availability.py'), 'exec'), namespace)
    data = namespace['d'].merge(pd.read_csv(ROOT / 'data/preseason_wins/team_expectations.csv'),
                                on=['Season','year','Tm'], how='left', validate='many_to_one')
    data['expected_team_wins'] = data.preseason_win_total * data.schedule_games / data.preseason_schedule_games
    data['wins_above_expectation'] = data.team_wins - data.expected_team_wins
    data['expectations_available'] = data.preseason_win_total.notna()
    # Pre-2003 seasons have no market data; a constant zero feature adds no information
    # after within-season standardization. Never backfill expectations from actual wins.
    data.loc[data.year < 2003, 'wins_above_expectation'] = 0.0
    namespace['d'] = data
    return namespace
