"""In-progress season overlay: season-to-date inputs projected to an 82-game pace.

The historical pipelines read fixed CSV/JSON files. `install(year)` patches pandas.read_csv and
Path.read_text *in this process only* so those files gain the current season's rows; nothing on disk
is modified. Run it in a fresh process (project_current.py does) before importing any model module.

Projection rule: each team's record and each player's games, minutes and counting totals (totals
columns, WS, OWS, DWS, VORP) are scaled by 82 / team games played so far. Per-game and rate stats are
unchanged. Leaderboard qualification and the availability penalty therefore apply to the projected
full season. Early in a season this is a noisy pace estimate, not a forecast of regression.
"""
from pathlib import Path
import gzip, io, json, re
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
SEASON_GAMES = 82
ESPN_ALIASES = {'GS': 'GSW', 'NY': 'NYK', 'SA': 'SAS', 'UTAH': 'UTA', 'PHX': 'PHO', 'BKN': 'BRK', 'NO': 'NOP', 'WSH': 'WAS', 'CHA': 'CHO'}
PER_GAME = {'fg_per_g': 'FG', 'fga_per_g': 'FGA', 'fg3_per_g': '3P', 'fg3a_per_g': '3PA', 'ft_per_g': 'FT', 'fta_per_g': 'FTA',
            'orb_per_g': 'ORB', 'drb_per_g': 'DRB', 'trb_per_g': 'TRB', 'ast_per_g': 'AST', 'stl_per_g': 'STL', 'blk_per_g': 'BLK',
            'tov_per_g': 'TOV', 'pf_per_g': 'PF', 'pts_per_g': 'PTS', 'fg_pct': 'FG%', 'fg2_pct': '2P%', 'fg3_pct': '3P%_S',
            'efg_pct': 'eFG%', 'ft_pct': 'FT%'}
TOTALS = {'mp': 'MP', 'fg': 'FG_T', 'fga': 'FGA_T', 'fg3': '3P_T', 'fg3a': '3PA_T', 'ft': 'FT_T', 'fta': 'FTA_T', 'orb': 'ORB_T',
          'drb': 'DRB_T', 'trb': 'TRB_T', 'ast': 'AST_T', 'stl': 'STL_T', 'blk': 'BLK_T', 'tov': 'TOV_T', 'pf': 'PF_T', 'pts': 'PTS_T',
          'tpl_dbl': 'Trp-Dbl'}
ADVANCED = {'per': 'PER', 'ts_pct': 'TS%', 'fg3a_per_fga_pct': '3PAr', 'fta_per_fga_pct': 'FTr', 'orb_pct': 'ORB%', 'drb_pct': 'DRB%',
            'trb_pct': 'TRB%', 'ast_pct': 'AST%', 'stl_pct': 'STL%', 'blk_pct': 'BLK%', 'tov_pct': 'TOV%', 'usg_pct': 'USG%',
            'ows': 'OWS', 'dws': 'DWS', 'ws': 'WS', 'ws_per_48': 'WS/48', 'obpm': 'OBPM', 'dbpm': 'DBPM', 'bpm': 'BPM', 'vorp': 'VORP'}
PER_POSS = {'off_rtg': 'ORtg', 'def_rtg': 'DRtg'}
SCALED = ['G', 'GS', 'MP', *[c for c in TOTALS.values() if c != 'MP'], 'OWS', 'DWS', 'WS', 'VORP']


def season_label(year):
    return f'{year-1}-{str(year)[-2:]}'


def raw(year, name):
    return ROOT / f'data/current/{year}/raw/{name}'


def bbref_table(year, page):
    html = gzip.decompress(raw(year, f'{page}.html.gz').read_bytes()).decode()
    soup = BeautifulSoup(html.replace('<!--', '').replace('-->', ''), 'html.parser')
    table = soup.find('table', id={'per_game': 'per_game_stats', 'totals': 'totals_stats'}.get(page, page))
    rows = []
    for tr in table.tbody.find_all('tr'):
        if 'thead' in (tr.get('class') or []):
            continue
        cells = {c.get('data-stat'): c for c in tr.find_all(['th', 'td'])}
        link = cells.get('name_display') and cells['name_display'].find('a')
        if not link:
            continue
        row = {k: c.get_text(strip=True) for k, c in cells.items()}
        row['PlayerID'] = link['href'].split('/')[-1].split('.')[0]
        rows.append(row)
    frame = pd.DataFrame(rows)
    # Traded players: Basketball Reference lists the combined (2TM/3TM) row first.
    return frame.drop_duplicates('PlayerID', keep='first').set_index('PlayerID')


def projected_wins(year):
    """Basketball Reference's projected final wins/losses per team (friv/playoff_prob.html), or None if not fetched."""
    path = raw(year, 'playoff_prob.html.gz')
    if not path.exists():
        return None
    soup = BeautifulSoup(gzip.decompress(path.read_bytes()).decode(), 'html.parser')
    rows = []
    for table_id in ('projected_standings_e', 'projected_standings_w'):
        table = soup.find('table', id=table_id)
        for tr in (table.tbody.find_all('tr') if table and table.tbody else []):
            cells = {c.get('data-stat'): c for c in tr.find_all(['th', 'td'])}
            link = cells.get('team_name') and cells['team_name'].find('a')
            if not link or f'/{year}.html' not in link['href']:
                continue
            rows.append(dict(Tm=link['href'].split('/')[2], projected_wins=float(cells['wins_avg'].get_text(strip=True)),
                             projected_losses=float(cells['losses_avg'].get_text(strip=True)),
                             projected_record_basis=cells['win_loss_current'].get_text(strip=True)))
    frame = pd.DataFrame(rows)
    return frame if len(frame) == 30 and frame.Tm.is_unique else None


def odds_wins(year):
    """Expected final wins from sportsbook over/under win totals (fetch_team_wins.py), or None if not fetched."""
    path = ROOT / f'data/current/{year}/team_win_totals.json'
    if not path.exists():
        return None
    teams = json.loads(path.read_text())['teams']
    return pd.DataFrame([dict(Tm=tm, odds_wins=t['expected_wins'], odds_line=t['line']) for tm, t in teams.items()])


def standings(year, use_odds=True):
    data = json.loads(raw(year, 'espn_standings.json').read_text())
    rows = []
    for conference in data['children']:
        for entry in conference['standings']['entries']:
            stats = {s['name']: s.get('value') for s in entry['stats']}
            tm = ESPN_ALIASES.get(entry['team']['abbreviation'], entry['team']['abbreviation'])
            rows.append(dict(Tm=tm, conference=conference['name'].split()[0], wins_to_date=stats['wins'], losses_to_date=stats['losses'],
                             source_playoff_seed_not_used=stats.get('playoffSeed')))
    frame = pd.DataFrame(rows)
    assert len(frame) == 30 and frame.Tm.is_unique, frame.Tm.tolist()
    frame['games_to_date'] = frame.wins_to_date + frame.losses_to_date
    scale = SEASON_GAMES / frame.games_to_date
    frame['Season'] = season_label(year); frame['year'] = year
    frame['team_wins'] = frame.wins_to_date * scale
    frame['team_losses'] = frame.losses_to_date * scale
    frame['team_wins_source'] = 'pace'
    # Prefer Basketball Reference's simulated final record over a straight-line 82-game pace.
    projected = projected_wins(year)
    if projected is not None:
        frame = frame.merge(projected, on='Tm', how='left')
        have = frame.projected_wins.notna()
        frame.loc[have, 'team_wins'] = frame.loc[have, 'projected_wins']
        frame.loc[have, 'team_losses'] = frame.loc[have, 'projected_losses']
        frame.loc[have, 'team_wins_source'] = 'bbref_projection'
    # First choice: the betting market's expected final wins (over/under lines with the price lean priced in).
    odds = odds_wins(year) if use_odds else None
    if odds is not None:
        frame = frame.merge(odds, on='Tm', how='left')
        have = frame.odds_wins.notna()
        frame.loc[have, 'team_wins'] = frame.loc[have, 'odds_wins']
        frame.loc[have, 'team_losses'] = SEASON_GAMES - frame.loc[have, 'odds_wins']
        frame.loc[have, 'team_wins_source'] = 'sportsbook_win_totals'
    frame['team_games'] = float(SEASON_GAMES)
    frame['win_percentage'] = frame.wins_to_date / frame.games_to_date
    # Positions and seeds follow the projected final record (team_wins), like the end-of-season standings
    # the models were trained on; ties broken by the current record.
    order = frame.team_wins + frame.win_percentage * 1e-3
    frame['projected_win_pct'] = order
    frame['source_playoff_seed_not_used'] = frame.groupby('conference').projected_win_pct.rank(ascending=False, method='first')
    frame['conference_rank'] = frame.groupby('conference').team_wins.rank(ascending=False, method='average')
    frame['conference_size'] = frame.groupby('conference').Tm.transform('size')
    frame['conference_standing'] = 1 - (frame.conference_rank - 1) / (frame.conference_size - 1)
    frame['league_rank'] = frame.team_wins.rank(ascending=False, method='average')
    frame['league_size'] = len(frame)
    frame['league_standing'] = 1 - (frame.league_rank - 1) / (frame.league_size - 1)
    return frame


def players(year, teams):
    per_game, totals, advanced, per_poss = (bbref_table(year, page) for page in ('per_game', 'totals', 'advanced', 'per_poss'))
    frame = pd.DataFrame(index=per_game.index)
    frame['Player Name'] = per_game.name_display.str.replace('*', '', regex=False)
    frame['Season'] = season_label(year)
    frame['Age'] = pd.to_numeric(per_game.age, errors='coerce')
    frame['Tm'] = per_game.team_name_abbr
    frame['Pos'] = per_game.pos
    frame['G'] = pd.to_numeric(per_game.games, errors='coerce')
    frame['GS'] = pd.to_numeric(per_game.games_started, errors='coerce')
    for source, mapping in ((per_game, PER_GAME), (totals, TOTALS), (advanced, ADVANCED), (per_poss, PER_POSS)):
        for column, target in mapping.items():
            values = source.reindex(frame.index)[column] if column in source.columns else np.nan
            frame[target] = pd.to_numeric(values, errors='coerce')
    frame['AS_G'] = 0.0; frame['AS_GS'] = 0.0  # no All-Star Game yet this season
    team_games = frame.Tm.map(teams.set_index('Tm').games_to_date)
    # Multi-team rows have no single schedule: use the league's average games played.
    team_games = team_games.fillna(teams.games_to_date.mean())
    frame['games_to_date'] = frame.G
    frame['team_games_to_date'] = team_games
    scale = SEASON_GAMES / team_games
    for column in SCALED:
        frame[column] = frame[column] * scale
    frame['G'] = frame.G.clip(upper=SEASON_GAMES); frame['GS'] = frame.GS.clip(upper=SEASON_GAMES)
    return frame.reset_index()


def team_defense(year):
    from fetch_team_defense import code
    data = pd.read_parquet(raw(year, 'team_advanced.parquet'))
    data = data[(data.season_type.isin(['regular-season', 'regular_season'])) & (data.measure_type == 'advanced') & (data.per_mode == 'pergame')].copy()
    data['Tm'] = [code(name, year) for name in data.team_name]
    data = data.rename(columns={'def_rating': 'team_defensive_rating', 'def_rating_rank': 'team_defensive_rank', 'w': 'source_wins', 'l': 'source_losses'})
    data['year'] = year; data['Season'] = season_label(year)
    data['source'] = f'https://www.nba.com/stats/teams/advanced?Season={season_label(year)}&SeasonType=Regular%20Season'
    data['provider'] = 'NBA Stats via sportsdataverse archive (season to date)'
    return data[['Season', 'year', 'Tm', 'team_defensive_rating', 'team_defensive_rank', 'source_wins', 'source_losses', 'source', 'provider']]


def expectations(year, teams):
    """Preseason market win totals: pasted totals if present, else a labelled proxy."""
    pasted = ROOT / f'data/current/{year}/preseason_wins.csv'
    if pasted.exists():
        frame = pd.read_csv(pasted)
        frame['source'] = 'Entered in the app (preseason market win totals)'
        frame['proxy'] = False
    else:
        history = pd.read_csv(ROOT / 'conference_standings/team_standings.csv')
        last = history[history.year == year - 1].set_index('Tm')
        prior = (last.team_wins / last.team_games * SEASON_GAMES).reindex(teams.Tm).fillna(41)
        frame = pd.DataFrame(dict(Tm=teams.Tm.to_numpy(), preseason_win_total=(41 + 0.6 * (prior - 41)).round(1).to_numpy()))
        frame['source'] = 'Proxy: last season wins regressed 40% to 41 (no published totals entered)'
        frame['proxy'] = True
    frame['Season'] = season_label(year); frame['year'] = year
    frame['preseason_schedule_games'] = SEASON_GAMES
    return frame[['Season', 'year', 'Tm', 'preseason_win_total', 'preseason_schedule_games', 'source', 'proxy']]


def build(year):
    teams = standings(year)
    stats = players(year, teams)
    return dict(teams=teams, stats=stats, defense=team_defense(year), expectations=expectations(year, teams))


def dummy_labels(year, stats, teams):
    """Model groups are only built for seasons with a winner; tag one pool member per award (ignored when scoring)."""
    history = pd.read_csv(ROOT / 'data/basketball_stats.csv', usecols=['PlayerID', 'Season', 'PTS'])
    veteran = stats.PlayerID.isin(history.PlayerID)
    last = history[history.Season == season_label(year - 1)].set_index('PlayerID').PTS
    single_team = stats.Tm.isin(teams.Tm)
    base = stats[stats.G.ge(20) & single_team]
    picks = {
        'MVP': base[base.G.ge(58) & base.MP.ge(1500)],
        'ROY': base[~base.PlayerID.isin(history.PlayerID)],
        'DPOY': base,
        'SMOY': base[base.GS.notna() & (2 * base.GS < base.G)],
        'MIP': base[base.PlayerID.isin(last.index)].assign(PTS=lambda f: f.PTS - f.PlayerID.map(last)),
    }
    labels = []
    for award, pool in picks.items():
        if pool.empty:
            continue
        labels.append(dict(award=award, season=season_label(year), player=pool.sort_values('PTS', ascending=False).iloc[0]['Player Name']))
    return labels


def install(year):
    """Patch file reads in this process so every model pipeline sees the current season."""
    overlay = build(year)
    stats, teams = overlay['stats'], overlay['teams']
    import fetch_qualified_ranks
    original_read_csv = pd.read_csv
    original_read_text = Path.read_text

    def with_rows(frame, extra, keys):
        extra = extra.reindex(columns=frame.columns)
        frame = frame[~frame.set_index(keys).index.isin(extra.set_index(keys).index)]
        return pd.concat([frame, extra], ignore_index=True)

    labels_now = dummy_labels(year, stats, teams)  # before patching: compares against true history
    qualified = {}

    def read_csv(path, *args, **kwargs):
        name = str(path)
        frame = original_read_csv(path, *args, **kwargs)
        if not isinstance(path, (str, Path)):
            return frame
        if kwargs.get('usecols') is not None:
            if name.endswith('data/basketball_stats.csv'):
                return pd.concat([frame, stats[list(kwargs['usecols'])]], ignore_index=True)
            return frame
        if name.endswith('data/basketball_stats.csv'):
            return with_rows(frame, stats, ['PlayerID', 'Season'])
        if name.endswith('conference_standings/team_standings.csv'):
            return with_rows(frame, teams, ['Season', 'Tm'])
        if name.endswith('data/team_defense/team_defense.csv'):
            return with_rows(frame, overlay['defense'], ['Season', 'Tm'])
        if name.endswith('data/preseason_wins/team_expectations.csv'):
            return with_rows(frame, overlay['expectations'], ['Season', 'Tm'])
        if name.endswith('data/qualified_ranks/qualified_ranks.csv'):
            if not qualified:
                parts = [fetch_qualified_ranks.reconstruct(year, kind)[0] for kind in ('per_game', 'advanced')]
                qualified['frame'] = pd.concat(parts, ignore_index=True)
            return with_rows(frame, qualified['frame'], ['year', 'PlayerID', 'stat'])
        return frame

    def read_text(self, *args, **kwargs):
        text = original_read_text(self, *args, **kwargs)
        name = str(self)
        if name.endswith('award_labels.json'):
            labels = [row for row in json.loads(text) if row['season'] != season_label(year)]
            return json.dumps(labels + labels_now)
        if name.endswith('data/team_wins_cache.json'):
            wins = json.loads(text)
            wins[season_label(year)] = {r.Tm: float(r.team_wins) for r in teams.itertuples()}
            return json.dumps(wins)
        return text

    pd.read_csv = read_csv
    Path.read_text = read_text
    return overlay
