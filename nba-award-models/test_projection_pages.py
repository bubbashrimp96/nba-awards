"""Checks for conference projections and recency-weighted model scoring."""
import json
import subprocess
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent

class ProjectionPagesTests(unittest.TestCase):
    def test_conference_projections(self):
        data = json.loads((ROOT / 'output/artifacts/projections.json').read_text())
        teams = set()
        players = set()
        for conference in ('Eastern', 'Western'):
            standings = data['conference_standings']['conferences'][conference]
            self.assertEqual([r['seed'] for r in standings], list(range(1, 16)))
            self.assertEqual([r['projected_wins'] for r in standings], sorted((r['projected_wins'] for r in standings), reverse=True))
            teams.update(r['team'] for r in standings)
            roster = data['all_stars']['conferences'][conference]
            for role, count in [('starters', 5), ('bench', 7), ('honourable_mentions', 5)]:
                self.assertEqual(len(roster[role]), count)
                for player in roster[role]:
                    self.assertNotIn(player['player_id'], players)
                    players.add(player['player_id'])
                    self.assertGreaterEqual(player['games_played'], 5)
                    self.assertGreaterEqual(player['availability'], .4)
                    self.assertGreaterEqual(player['minutes_per_game'], 15)
        self.assertEqual(len(teams), 30)

    def test_allstar_team_record_affects_selection(self):
        import pandas as pd
        from league_projections import allstars
        teams = pd.DataFrame([dict(Tm='A', conference='Western', team_wins=20, wins_to_date=9, losses_to_date=1),
                              dict(Tm='B', conference='Western', team_wins=60, wins_to_date=1, losses_to_date=9)])
        stats = pd.DataFrame([dict(PlayerID=team, **{'Player Name': team, 'Tm': team, 'PTS':20, 'AST':5, 'TRB':5, 'BPM':3, 'WS/48':.15,
                                                   'games_to_date':10,'team_games_to_date':10,'G':82,'MP':2460}) for team in ['A','B']])
        data = allstars(stats, teams)
        players = data['conferences']['Western']['starters']
        self.assertEqual(players[0]['team'], 'A')
        self.assertGreater(players[0]['selection_score'], players[1]['selection_score'])
        self.assertEqual(players[0]['team_wins_to_date'], 9)
        self.assertEqual(players[0]['team_losses_to_date'], 1)
        self.assertAlmostEqual(players[0]['team_win_pct'], .9)
        self.assertEqual(data['weights']['team_record'], .05)

    def test_accuracy_and_summary(self):
        soup = BeautifulSoup((ROOT / 'output/artifacts/nba-award-models-browser.html').read_text(), 'html.parser')
        summary = soup.select_one('[data-view="summary"]')
        self.assertLess(str(summary).index('id="overview"'), str(summary).index('class="season-scorecard"'))
        self.assertNotIn('MVP · revised penalties', summary.text)
        script = '\n'.join(s.get_text() for s in soup.find_all('script'))
        function = script[script.index('function modelAccuracy('):script.index('function accuracyTitle(')]
        fixture = """
let rows=[]; const completed=()=>rows;
""" + function + """
const season=(year,correct)=>({season:year+'-'+String(year+1).slice(-2),actual:[{rank:1,player:'A'},{rank:2,player:'B'},{rank:3,player:'C'}],predicted:(correct?['A','B','C']:['D','E','F']).map((player,i)=>({player,rank:i+1}))});
rows=[season(2025,true)];if(modelAccuracy('MVP').score!==100)throw Error('perfect');
rows=[season(2025,false)];if(modelAccuracy('MVP').score!==0)throw Error('miss');
rows=[season(2020,false),season(2025,true)];if(Math.abs(modelAccuracy('MVP').score-200/3)>1e-8)throw Error('half-life');
rows=[season(2025,true)]; rows[0].predicted.reverse().forEach((p,i)=>p.rank=i+1);if(modelAccuracy('MVP').score!==50)throw Error('order: winner first alone should change');
"""
        subprocess.run(['node', '-e', fixture], check=True, capture_output=True, text=True)

if __name__ == '__main__':
    unittest.main()
