"""Coach of the Year model, 2001-02 onward (2000-01 has no prior season to fit on).

Candidate pool: for every team-season, the coach with the most regular-season games for that team
(Basketball Reference season coaches pages). Voting: Basketball Reference award pages.

Features (within-season z scores unless noted):
  team_wins               actual wins
  team_net_rating         points per 100 possessions minus points allowed (NBA.com team advanced stats)
  wins_above_expectation  wins minus preseason market win total scaled to games played (0 before 2002-03)
  top4_seed               1 if the team finished a top-four conference seed (raw 0/1 indicator)
  prior_coy_same_team     1 if the coach already won COY with this franchise (raw 0/1 indicator)
Softmax over the pool, L2 regularisation, fitted on prior seasons only (same 20-season half-life as the
player awards). Team wins, expectations and top-four seed are constrained nonnegative; the prior-COY sign
is left free so the data decides whether voters reward or discount a repeat.
"""
from pathlib import Path
import gzip, json, re
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup, Comment
from scipy.optimize import minimize
from scipy.special import logsumexp, softmax
from revised_award_core import team_context
from build_clutch import voting_table

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'data/coy/raw'
OUT = ROOT / 'coy_model'; OUT.mkdir(exist_ok=True)
FEATURES = ['team_wins', 'team_net_rating', 'wins_above_expectation', 'top4_seed', 'prior_coy_same_team']
RAW_TERMS = {'top4_seed', 'prior_coy_same_team'}
POSITIVE = {'team_wins', 'team_net_rating', 'wins_above_expectation', 'top4_seed'}
HALF_LIFE, REGULARIZATION = 20, 0.3
# Relocations/renames: compare franchises, not abbreviations.
FRANCHISE = {'SEA': 'OKC', 'NJN': 'BRK', 'NOH': 'NOP', 'NOK': 'NOP', 'CHA': 'CHO', 'CHH': 'CHO', 'VAN': 'MEM'}


def table(path, table_id=None):
    soup = BeautifulSoup(gzip.decompress(path.read_bytes()), 'html.parser')
    found = soup.find('table', id=table_id) if table_id else soup.find('table')
    if found is None:
        for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
            if table_id and f'id="{table_id}"' in comment:
                found = BeautifulSoup(comment, 'html.parser').find('table', id=table_id); break
    return found


def coaches():
    rows = []
    for year in range(2001, 2028):
        path = RAW / f'coaches_{year}.html.gz'
        current = ROOT / f'data/current/{year}/raw/coaches.html.gz'  # refreshed by fetch_current.py
        if current.exists():
            path = current
        if not path.exists():
            continue
        for tr in table(path, 'NBA_coaches').tbody.find_all('tr'):
            cells = {c.get('data-stat'): c for c in tr.find_all(['th', 'td'])}
            if 'cur_g' not in cells or not cells['cur_g'].text.strip():
                continue
            link = cells['coach'].find('a')
            rows.append(dict(year=year, coach=cells['coach'].text.strip(), coach_id=link['href'].split('/')[-1].split('.')[0],
                             Tm=cells['team'].text.strip(), games=int(cells['cur_g'].text), wins=int(cells['cur_w'].text),
                             losses=int(cells['cur_l'].text)))
    data = pd.DataFrame(rows)
    # One candidate per team: the coach who ran the most games that season.
    return data.sort_values('games', ascending=False).drop_duplicates(['year', 'Tm']).sort_values(['year', 'Tm'])


def coy_winners():
    path = RAW / 'coy_winners.html.gz'
    winners = []
    if path.exists():
        soup = BeautifulSoup(gzip.decompress(path.read_bytes()), 'html.parser')
        html = str(soup) + ''.join(str(c) for c in soup.find_all(string=lambda s: isinstance(s, Comment)))
        for tr in BeautifulSoup(html, 'html.parser').find_all('tr'):
            cells = {c.get('data-stat'): c for c in tr.find_all(['th', 'td'])}
            if 'season' not in cells or 'coach' not in cells or not cells['coach'].find('a'):
                continue
            if 'lg_id' in cells and cells['lg_id'].text.strip() != 'NBA':
                continue
            year = int(cells['season'].text[:4]) + 1
            team = cells.get('team_id') or cells.get('team')
            winners.append(dict(year=year, coach_id=cells['coach'].find('a')['href'].split('/')[-1].split('.')[0],
                                Tm=team.text.strip() if team else None))
    frame = pd.DataFrame(winners).drop_duplicates(['year', 'coach_id'])
    frame['franchise'] = frame.Tm.replace(FRANCHISE)
    return frame


def net_ratings(years):
    """NBA.com team net rating: cached nightly archive files (historical) or the current-season download."""
    from fetch_team_defense import code
    frames = []
    for year in years:
        path = ROOT / f'data/current/{year}/raw/team_advanced.parquet'
        if not path.exists():
            path = ROOT / f'data/team_defense/nba_stats_{year}.parquet'
        if not path.exists():
            continue
        data = pd.read_parquet(path)
        data = data[data.season_type.isin(['regular-season', 'regular_season']) & (data.measure_type == 'advanced') & (data.per_mode == 'pergame')]
        frames.append(pd.DataFrame(dict(year=year, Tm=[code(n, year) for n in data.team_name], team_net_rating=data.net_rating.to_numpy())))
    return pd.concat(frames, ignore_index=True)


def build_pool():
    pool = coaches()
    context = team_context()[['year', 'Tm', 'team_wins', 'team_games', 'conference_seed', 'seed_fallback']]
    pool = pool.merge(context, on=['year', 'Tm'], how='left', validate='one_to_one')
    expectations = pd.read_csv(ROOT / 'data/preseason_wins/team_expectations.csv')[['year', 'Tm', 'preseason_win_total', 'preseason_schedule_games']]
    pool = pool.merge(expectations, on=['year', 'Tm'], how='left', validate='one_to_one')
    pool = pool.merge(net_ratings(sorted(pool.year.unique())), on=['year', 'Tm'], how='left', validate='one_to_one')
    pool['expected_team_wins'] = pool.preseason_win_total * pool.team_games / pool.preseason_schedule_games
    pool['wins_above_expectation'] = (pool.team_wins - pool.expected_team_wins).where(pool.year >= 2003, 0.0)
    pool['top4_seed'] = pool.conference_seed.le(4).astype(float).where(pool.conference_seed.notna())
    pool['franchise'] = pool.Tm.replace(FRANCHISE)
    winners = coy_winners()
    pool['prior_coy_same_team'] = [float(((winners.year < y) & (winners.coach_id == c) & (winners.franchise == f)).any())
                                   for y, c, f in zip(pool.year, pool.coach_id, pool.franchise)]
    pool['prior_coy_any_team'] = [float(((winners.year < y) & (winners.coach_id == c)).any()) for y, c in zip(pool.year, pool.coach_id)]
    return pool, winners


def design(frame):
    raw = frame[FEATURES].to_numpy(float)
    raw[:, np.isnan(raw).all(axis=0)] = 0.0
    raw = np.where(np.isnan(raw), np.nanmedian(raw, axis=0), raw)
    sd = raw.std(axis=0); sd[sd < 1e-8] = 1
    x = (raw - raw.mean(axis=0)) / sd
    for term in RAW_TERMS:
        x[:, FEATURES.index(term)] = raw[:, FEATURES.index(term)]
    return x


def fit(groups):
    latest = max(g['year'] for g in groups)
    weights = np.array([2 ** (-(latest - g['year']) / HALF_LIFE) for g in groups]); weights /= weights.sum()
    def objective(coef):
        loss = REGULARIZATION * coef @ coef / 2; grad = REGULARIZATION * coef
        for g, w in zip(groups, weights):
            s = g['x'] @ coef
            loss += w * (logsumexp(s) - g['y'] @ s)
            grad = grad + w * g['x'].T @ (softmax(s) - g['y'])
        return loss, grad
    bounds = [(0, None) if f in POSITIVE else (None, None) for f in FEATURES]
    result = minimize(objective, np.zeros(len(FEATURES)), jac=True, method='L-BFGS-B', bounds=bounds)
    assert result.success, result.message
    return result.x


def main():
    pool, winners = build_pool()
    groups = []
    for year, frame in pool.groupby('year'):
        frame = frame.reset_index(drop=True)
        votes = voting_table(year, 'coy') if year <= 2026 else None
        y = None
        if votes:
            top = votes['voting'][0]
            y = frame.coach_id.eq(top['id']).to_numpy(float)
            assert y.sum() == 1, (year, top)
        groups.append(dict(year=int(year), season=f'{year-1}-{str(year)[-2:]}', g=frame, x=design(frame), y=y, votes=votes))
    labelled = [g for g in groups if g['y'] is not None]
    seasons, tests = [], []
    for group in groups:
        train = [g for g in labelled if g['year'] < group['year']]
        if not train:
            continue
        coef = fit(train)
        scores = group['x'] @ coef; shares = softmax(scores); order = np.argsort(-scores, kind='stable')
        frame, votes = group['g'], group['votes']
        model_rank = {frame.coach_id[i]: r for r, i in enumerate(order, 1)}
        actual_rank = {v['id']: v['rank'] for v in votes['voting']} if votes else {}
        if votes:
            winner = votes['voting'][0]
            rank = model_rank[winner['id']]
            tests.append(dict(award='COY', season=group['season'], predicted=frame.coach[order[0]], actual=winner['player'],
                              winner_rank=rank, top1=int(rank == 1), top3=int(rank <= 3),
                              log_loss=float(-np.log(shares[group['y'] > 0].sum()))))
        shown = [frame.coach_id[i] for i in order[:3]] + [v['id'] for v in (votes['results'] if votes else [])]
        players = []
        for cid in dict.fromkeys(shown):
            row = frame[frame.coach_id == cid]
            if row.empty:
                vote = next(v for v in votes['voting'] if v['id'] == cid)
                players.append(dict(player=vote['player'], team=vote['team'], stats={}, imputed=[], eligible=False, model_rank=None, actual_rank=vote['rank']))
                continue
            row = row.iloc[0]
            players.append(dict(player=row.coach, team=row.Tm, eligible=True, model_rank=model_rank[cid], actual_rank=actual_rank.get(cid),
                                stats={f: (None if pd.isna(row[f]) else float(row[f])) for f in FEATURES + ['conference_seed']}, imputed=[],
                                expected_team_wins=None if pd.isna(row.expected_team_wins) else float(row.expected_team_wins),
                                conference_seed=None if pd.isna(row.conference_seed) else float(row.conference_seed),
                                coach_record=f'{row.wins}-{row.losses}'))
        seasons.append(dict(season=group['season'], in_progress=votes is None,
                            predicted=[dict(rank=r, player=frame.coach[i], share=float(shares[i]), score=float(scores[i])) for r, i in enumerate(order[:3], 1)],
                            actual=votes['results'] if votes else [], source=votes['source'] if votes else '',
                            features=FEATURES, display_features=['coach_record', 'team_wins', 'team_net_rating', 'expected_team_wins', 'wins_above_expectation', 'conference_seed', 'top4_seed', 'prior_coy_same_team'],
                            coefficients=coef.tolist(), players=players))
    final = fit(labelled)
    model = dict(features=FEATURES, coefficients=final.tolist(), half_life=HALF_LIFE, regularization=REGULARIZATION,
                 trained_through=max(g['year'] for g in labelled),
                 candidate_pool='One coach per team-season: the coach with the most regular-season games for that team',
                 standardization='Within-season z scores, except raw 0/1 top-four seed and prior-COY indicators',
                 constraints='Team wins, net rating, wins above expectation and top-four seed nonnegative; prior COY with same team unconstrained',
                 expectations='Preseason market win totals from 2002-03; earlier seasons carry a neutral zero',
                 retrospective_warning='Features chosen by hand after the fact; prior-season fitting only, but not an untouched test.')
    (OUT / 'model.json').write_text(json.dumps(model, indent=2) + '\n')
    (OUT / 'comparisons.json').write_text(json.dumps(seasons, ensure_ascii=False, indent=1) + '\n')
    tests = pd.DataFrame(tests); tests.to_csv(OUT / 'historical_backtests.csv', index=False)
    print(tests.to_string(index=False))
    print('first picks', tests.top1.sum(), '/', len(tests), 'top3', tests.top3.sum(), 'log loss', round(tests.log_loss.mean(), 3))
    print(dict(zip(FEATURES, np.round(final, 3))))
    return tests


if __name__ == '__main__':
    main()
