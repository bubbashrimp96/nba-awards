"""Clutch Player of the Year model (award began 2022-23).

Candidates: each season's top 30 clutch scorers (NBA.com clutch = last 5 minutes, score within 5),
captured from nba.com/stats/players/clutch-traditional (PerMode=Totals) into data/clutch/raw_chunks.json.
Voting: Basketball Reference award pages (cached by fetch_coy_clutch.py).

Features (within-season z scores): clutch points (primary signal), clutch FG%, clutch plus-minus,
clutch-game win %, team wins. Softmax over candidates, L2-regularised, prior seasons only.
With only three prior seasons available at most, coefficients are heavily regularised; the first
season (2022-23) has no prior data and falls back to ranking on clutch points alone.
"""
from pathlib import Path
import gzip, json, re, unicodedata
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup, Comment
from scipy.optimize import minimize
from scipy.special import logsumexp, softmax

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'clutch_model'; OUT.mkdir(exist_ok=True)
FEATURES = ['clutch_pts', 'clutch_fg_pct', 'clutch_plus_minus', 'clutch_win_pct', 'team_wins']
POSITIVE = set(FEATURES)  # every input should only ever help a candidate
REGULARIZATION = 1.0
TEAM_CODES = {'BKN': 'BRK', 'PHX': 'PHO', 'CHA': 'CHO'}
COLUMNS = ['player', 'team', 'gp', 'w', 'l', 'pts', 'fgm', 'fga', 'fg3m', 'ftm', 'ast', 'tov', 'plus_minus']


def key(name):
    name = re.sub(r'\s+(jr\.?|sr\.?|ii|iii|iv)$', '', name.strip(), flags=re.I)
    return re.sub('[^a-z0-9]', '', unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower())


def voting_table(year, table_id):
    path = ROOT / f'data/coy/raw/awards_{year}.html.gz'
    if not path.exists():
        return None
    soup = BeautifulSoup(gzip.decompress(path.read_bytes()), 'html.parser')
    table = soup.find('table', id=table_id)
    if table is None:
        for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
            if f'id="{table_id}"' in comment:
                table = BeautifulSoup(comment, 'html.parser').find('table', id=table_id); break
    if table is None:
        return None
    rows = []
    for tr in table.tbody.find_all('tr'):
        cells = {c.get('data-stat'): c for c in tr.find_all(['th', 'td'])}
        if 'points_won' not in cells or not cells['points_won'].text.strip():
            continue
        name_cell = cells.get('player') or cells.get('coach')
        link = name_cell.find('a')
        rows.append(dict(rank=int(re.sub(r'\D', '', cells['rank'].text) or 0), player=name_cell.text.strip(),
                         id=link['href'].split('/')[-1].split('.')[0] if link else None,
                         team=cells['team_id'].text.strip() if 'team_id' in cells else None,
                         points=float(cells['points_won'].text), vote_share=float(cells['award_share'].text or 0)))
    return dict(source=f'https://www.basketball-reference.com/awards/awards_{year}.html',
                results=[r for r in rows if r['rank'] <= 3], voting=rows)


def candidates():
    raw = json.loads((ROOT / 'data/clutch/raw_chunks.json').read_text())
    frames = []
    for season, blob in raw.items():
        rows = [r.split(',') for r in blob.split(';') if r]
        frame = pd.DataFrame(rows, columns=COLUMNS)
        for c in COLUMNS[2:]:
            frame[c] = pd.to_numeric(frame[c])
        frame.insert(0, 'season', season)
        frames.append(frame)
    data = pd.concat(frames, ignore_index=True)
    data['year'] = data.season.str[:4].astype(int) + 1
    data['player'] = data.player.str.title().str.replace(r"(?<=')[A-Z]", lambda m: m[0].upper(), regex=True)
    data['name_key'] = data.player.map(key)
    data['Tm'] = data.team.replace(TEAM_CODES)
    data['clutch_pts'] = data.pts
    data['clutch_fg_pct'] = data.fgm / data.fga
    data['clutch_plus_minus'] = data.plus_minus
    data['clutch_win_pct'] = data.w / (data.w + data.l)
    standings = pd.read_csv(ROOT / 'conference_standings/team_standings.csv')[['year', 'Tm', 'team_wins', 'team_games']]
    data = data.merge(standings, on=['year', 'Tm'], how='left', validate='many_to_one')
    # No standings for the in-progress season: team wins are NaN, imputed to a constant, so they carry no weight there.
    return data


def design(frame):
    raw = frame[FEATURES].to_numpy(float)
    raw[:, np.isnan(raw).all(axis=0)] = 0.0  # e.g. team wins for the in-progress season
    raw = np.where(np.isnan(raw), np.nanmedian(raw, axis=0), raw)
    sd = raw.std(axis=0); sd[sd < 1e-8] = 1
    return (raw - raw.mean(axis=0)) / sd


def fit(groups):
    def objective(coef):
        loss = REGULARIZATION * coef @ coef / 2; grad = REGULARIZATION * coef
        for g in groups:
            s = g['x'] @ coef
            loss += (logsumexp(s) - g['y'] @ s) / len(groups)
            grad = grad + g['x'].T @ (softmax(s) - g['y']) / len(groups)
        return loss, grad
    bounds = [(0, None) if f in POSITIVE else (None, None) for f in FEATURES]
    result = minimize(objective, np.zeros(len(FEATURES)), jac=True, method='L-BFGS-B', bounds=bounds)
    assert result.success, result.message
    return result.x


def main():
    data = candidates()
    groups, voting = [], {}
    for year, frame in data.groupby('year'):
        frame = frame.sort_values('clutch_pts', ascending=False).reset_index(drop=True)
        votes = voting_table(year, 'clutch_poy') if year <= 2026 else None
        if votes is None and year <= 2025:
            archive = pd.read_csv(ROOT / 'data/award_voting/historical_award_shares.csv')
            rows = archive[(archive.season == year) & (archive.award == 'nba clutch_poy')].sort_values('pts_won', ascending=False)
            ranks = rows.pts_won.rank(ascending=False, method='min').astype(int)
            votes = dict(source=f'https://www.basketball-reference.com/awards/awards_{year}.html',
                         voting=[dict(rank=int(rk), player=r.player, points=float(r.pts_won), vote_share=float(r.share)) for rk, r in zip(ranks, rows.itertuples())])
            votes['results'] = [v for v in votes['voting'] if v['rank'] <= 3]
        y = None
        if votes:
            winner = key(votes['voting'][0]['player'])
            y = frame.name_key.eq(winner).to_numpy(float)
            assert y.sum() == 1, (year, votes['voting'][0]['player'])
            voting[year] = votes
        groups.append(dict(year=int(year), season=frame.season.iloc[0], g=frame, x=design(frame), y=y))
    labelled = [g for g in groups if g['y'] is not None]
    seasons, tests = [], []
    for group in groups:
        if group['y'] is None:
            continue  # in-progress season: see project_current.py
        train = [g for g in labelled if g['year'] < group['year']]
        coef = fit(train) if train else np.eye(len(FEATURES))[0]
        scores = group['x'] @ coef; shares = softmax(scores); order = np.argsort(-scores, kind='stable')
        frame = group['g']
        model_rank = {frame.name_key[i]: r for r, i in enumerate(order, 1)}
        votes = voting.get(group['year'])
        actual_rank = {key(v['player']): v['rank'] for v in votes['voting']} if votes else {}
        if votes:
            winner_rank = model_rank[key(votes['voting'][0]['player'])]
            tests.append(dict(award='CPOY', season=group['season'], predicted=frame.player[order[0]], actual=votes['voting'][0]['player'],
                              winner_rank=winner_rank, top1=int(winner_rank == 1), top3=int(winner_rank <= 3),
                              log_loss=float(-np.log(shares[group['y'] > 0].sum())), training_seasons=len(train),
                              fallback='clutch points only (no prior seasons)' if not train else ''))
        shown = {frame.name_key[i] for i in order[:3]} | set(list(actual_rank)[:3])
        players = []
        for i in range(len(frame)):
            row = frame.iloc[i]
            if row.name_key not in shown:
                continue
            players.append(dict(player=row.player, team=row.Tm, stats={f: (None if pd.isna(row[f]) else float(row[f])) for f in FEATURES + ['gp']}, imputed=[],
                                eligible=True, model_rank=model_rank[row.name_key], actual_rank=actual_rank.get(row.name_key),
                                clutch_record=f'{int(row.w)}-{int(row.l)}', clutch_games=int(row.gp)))
        missing = shown - set(frame.name_key)
        for name in missing:
            vote = next(v for v in votes['voting'] if key(v['player']) == name)
            players.append(dict(player=vote['player'], team=vote.get('team') or '', stats={}, imputed=[], eligible=False,
                                model_rank=None, actual_rank=vote['rank']))
        seasons.append(dict(season=group['season'], in_progress=votes is None,
                            predicted=[dict(rank=r, player=frame.player[i], share=float(shares[i]), score=float(scores[i])) for r, i in enumerate(order[:3], 1)],
                            actual=votes['results'] if votes else [], source=votes['source'] if votes else 'https://www.nba.com/stats/players/clutch-traditional?PerMode=Totals',
                            features=FEATURES, display_features=['clutch_record', 'gp', *FEATURES], coefficients=coef.tolist(),
                            training_seasons=len(train), fallback=not train, players=players))
    final = fit(labelled)
    model = dict(features=FEATURES, coefficients=final.tolist(), regularization=REGULARIZATION, half_life=None,
                 trained_through=max(g['year'] for g in labelled), candidate_pool='Top 30 NBA.com clutch scorers (totals) each season',
                 clutch_definition='NBA.com: last 5 minutes of the 4th quarter or overtime, score within 5 points',
                 standardization='Within-season candidate-pool z scores',
                 constraints='All coefficients nonnegative',
                 retrospective_warning='Award began 2022-23; at most three prior seasons to fit on, so treat as a ranked shortlist, not a calibrated probability.')
    (OUT / 'model.json').write_text(json.dumps(model, indent=2) + '\n')
    (OUT / 'comparisons.json').write_text(json.dumps(seasons, ensure_ascii=False, indent=1) + '\n')
    pd.DataFrame(tests).to_csv(OUT / 'historical_backtests.csv', index=False)
    print(pd.DataFrame(tests).to_string(index=False))
    print(dict(zip(FEATURES, np.round(final, 3))))
    current = seasons[-1]
    print('current', current['season'], [(p['player'], round(p['share'], 3)) for p in current['predicted']])


if __name__ == '__main__':
    main()
