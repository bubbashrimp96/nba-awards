"""MIP backtest with preseason expected PTS/REB/AST from every sourced season.

Reads sourced/*.csv (one file per source, written by the sourcing step) plus the
earlier Razzball forecasts.csv (2020-2023), matches names to Basketball Reference
PlayerIDs, picks one source per season (best coverage of the 13+ PPG MIP pool),
then refits the active MIP model on prior seasons only, with and without the
"actual minus expected" features. Production models are untouched.
"""
from pathlib import Path
import json, re, sys, unicodedata
import numpy as np
import pandas as pd
from scipy.special import softmax

ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from revised_award_core import load_namespace, features_for, fit

HERE = Path(__file__).resolve().parent
OUT = HERE / 'all_years'; OUT.mkdir(exist_ok=True)
ns = load_namespace('MIP'); columns = features_for('MIP'); groups = ns['make_groups'](columns)
stats = ns['d']; key = ns['key']
settings = json.loads((ROOT / 'revised_awards/models.json').read_text())['MIP']
CUTOFF = 13

ALIASES = {
    'Shai Gilgeous': 'Shai Gilgeous-Alexander', 'Michael Porter': 'Michael Porter Jr.', 'Otto Porter': 'Otto Porter Jr.',
    'Larry Nance': 'Larry Nance Jr.', 'Enes Kanter': 'Enes Freedom', 'Marvin Bagley': 'Marvin Bagley III',
    'Robert Willliams': 'Robert Williams', 'Spencer Dinwiddle': 'Spencer Dinwiddie', 'Moe Harkless': 'Maurice Harkless',
    'Danuel House': 'Danuel House Jr.', 'Derrick Jones': 'Derrick Jones Jr.', 'Tyrese Halibutron': 'Tyrese Haliburton',
    'Nicolas Claxton': 'Nic Claxton', 'Danilo Galinari': 'Danilo Gallinari', 'Herb Jones': 'Herbert Jones',
    'Jabari Smith': 'Jabari Smith Jr.', 'Ron Artest': 'Metta World Peace', 'Lou Williams': 'Lou Williams',
}
ALIASES.update(json.loads((HERE / 'aliases_extra.json').read_text()) if (HERE / 'aliases_extra.json').exists() else {})


def loose(name):
    """Looser key: strip accents, suffixes, punctuation."""
    s = unicodedata.normalize('NFKD', str(name)).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'\b(jr|sr|ii|iii|iv)\b\.?', '', s)
    return re.sub(r'[^a-z]', '', s)


# Identities: prefer players with a row in that season; fall back to any season.
season_rows = stats[['year', 'PlayerID', 'Player Name']].drop_duplicates()
season_rows['k'] = season_rows['Player Name'].map(key); season_rows['l'] = season_rows['Player Name'].map(loose)
all_ids = season_rows.drop_duplicates(['PlayerID', 'k'])


def resolve(name, year):
    if not isinstance(name, str): return None
    name = ALIASES.get(name, name)
    if name.startswith('id:'): return name[3:]
    for col, val in (('k', key(name)), ('l', loose(name))):
        here = season_rows[(season_rows.year == year) & (season_rows[col] == val)].PlayerID.unique()
        if len(here) == 1: return here[0]
        anywhere = all_ids[all_ids[col] == val].PlayerID.unique()
        if len(anywhere) == 1: return anywhere[0]
    return None


frames = []
for path in sorted((HERE / 'sourced').glob('*.csv')):
    f = pd.read_csv(path); f['source_file'] = path.stem; frames.append(f)
old = pd.read_csv(HERE / 'forecasts.csv')  # earlier Razzball 2020-2023 extraction, already matched
old = old.assign(season=old.year.map(lambda y: f'{y-1}-{str(y)[2:]}'), source='razzball', source_file='razzball_2020_2023',
                 snapshot_timestamp='', team='', expected_MPG=np.nan, expected_G=np.nan)
raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=list(old.columns))
for c in ['expected_PTS', 'expected_TRB', 'expected_AST']:
    raw[c] = pd.to_numeric(raw[c], errors='coerce')
raw = raw.dropna(subset=['expected_PTS'])
# One Razzball 2015-16 row has the name shifted into the team column.
raw['published_name'] = raw.published_name.fillna(raw.team)
# Known source typo: Razzball 2010-11 lists Dwyane Wade at 23 REB (clearly ~5); blank it, not guess.
raw.loc[(raw.year == 2011) & raw.published_name.str.contains('Wade', na=False) & (raw.expected_TRB > 15), 'expected_TRB'] = np.nan
raw['PlayerID'] = [resolve(n, y) for n, y in zip(raw.published_name, raw.year)]
unmatched = raw[raw.PlayerID.isna()]
unmatched[['year', 'source_file', 'published_name', 'team', 'expected_PTS']].to_csv(OUT / 'unmatched.csv', index=False)
matched = pd.concat([raw.dropna(subset=['PlayerID']), old], ignore_index=True)
# A player listed twice in one source/year (e.g. traded, or duplicate page) keeps the first listing.
matched['src'] = matched.source.str.lower().str.replace('razzball.*', 'razzball', regex=True)
matched = matched.drop_duplicates(['src', 'year', 'PlayerID'])

# Coverage of the MIP scoring pool per source/year; choose the best source each year.
group_by_year = {g['year']: g for g in groups}
cov = []
for (src, year), f in matched.groupby(['src', 'year']):
    if year not in group_by_year: continue
    g = group_by_year[year]; pool = g['g'][g['g'].PTS.ge(CUTOFF)]
    winners = set(g['g'].PlayerID[g['y'] > 0])
    ids = set(f.PlayerID)
    cov.append(dict(year=year, source_file=src, rows=len(f), pool=len(pool), covered=int(pool.PlayerID.isin(ids).sum()),
                    coverage=float(pool.PlayerID.isin(ids).mean()), winner_covered=winners <= ids,
                    snapshot=str(f.snapshot_timestamp.dropna().astype(str).min()) if f.snapshot_timestamp.notna().any() else ''))
cov = pd.DataFrame(cov).sort_values(['year', 'winner_covered', 'coverage'], ascending=[True, False, False])
cov.to_csv(OUT / 'coverage_by_source.csv', index=False)
# Consensus: average every source covering a player-season (more coverage, less single-source noise).
f = (matched.groupby(['year', 'PlayerID'])
     .agg(expected_PTS=('expected_PTS', 'mean'), expected_TRB=('expected_TRB', 'mean'), expected_AST=('expected_AST', 'mean'),
          n_sources=('src', 'nunique'), source_file=('src', lambda x: '+'.join(sorted(set(x))))).reset_index())
f.to_csv(OUT / 'consensus_forecasts.csv', index=False)
chosen = {y: 'consensus(' + '+'.join(sorted(matched[matched.year == y].src.unique())) + ')' for y in sorted(f.year.unique())}
for year in chosen:
    if year not in group_by_year: continue
    g = group_by_year[year]; pool = g['g'][g['g'].PTS.ge(CUTOFF)]; ids = set(f[f.year == year].PlayerID)
    cov = pd.concat([cov, pd.DataFrame([dict(year=year, source_file='CONSENSUS', rows=len(ids), pool=len(pool), covered=int(pool.PlayerID.isin(ids).sum()),
                     coverage=float(pool.PlayerID.isin(ids).mean()), winner_covered=set(g['g'].PlayerID[g['y'] > 0]) <= ids, snapshot='')])])
cov.to_csv(OUT / 'coverage_by_source.csv', index=False)

extra = ['surprise_PTS', 'surprise_AST', 'surprise_TRB']
enriched, audit = [], []
for source in groups:
    frame = source['g'].merge(f[['year', 'PlayerID', 'expected_PTS', 'expected_TRB', 'expected_AST', 'source_file']],
                              on=['year', 'PlayerID'], how='left', validate='one_to_one')
    for stat in ['PTS', 'AST', 'TRB']: frame['surprise_' + stat] = frame[stat] - frame['expected_' + stat]
    available = frame.expected_PTS.notna().to_numpy(); z = np.zeros((len(frame), 3))
    usable = available.any() and bool(available[source['y'] > 0].all())
    if usable:
        vals = frame.loc[available, extra].to_numpy(float)
        vals = np.where(np.isnan(vals), np.nanmedian(vals, axis=0), vals)  # a source missing REB/AST for a player
        sd = vals.std(axis=0); sd[sd < 1e-8] = 1; z[available] = (vals - vals.mean(axis=0)) / sd
    enriched.append(dict(source, g=frame, z=z, available=available, usable=usable))
    if source['year'] in chosen:
        audit.append(frame.loc[frame.PTS.ge(CUTOFF), ['year', 'PlayerID', 'Player Name', 'Tm', 'PTS', 'TRB', 'AST',
                                                       'expected_PTS', 'expected_TRB', 'expected_AST', *extra, 'source_file']]
                     .assign(won=source['y'][frame.PTS.ge(CUTOFF).to_numpy()] > 0))
pd.concat(audit).to_csv(OUT / 'feature_audit.csv', index=False)

variants = {
    'baseline': ([], []),
    'add_surprise_PTS': (extra[:1], []),
    'add_surprise_PTS_REB_AST': (extra, []),
    'replace_prior_year_deltas': (extra, ['delta_PTS', 'delta_AST', 'delta_TRB']),
}
rows, coefs = [], []
for variant, (add, remove) in variants.items():
    feats = [c for c in columns if c not in remove] + add
    keep = [i for i, c in enumerate(columns) if c not in remove]; zi = [extra.index(c) for c in add]
    gs = [dict(s, x=np.column_stack([s['x'][:, keep], np.where(s['usable'], 1, 0) * s['z'][:, zi]])) for s in enriched]
    for group in gs:
        year = group['year']
        if year not in chosen or year < 2001: continue
        train = [g for g in gs if g['year'] < year]
        coef = fit(train, settings['half_life'], settings['regularization'], feats)
        elig = group['g'].PTS.ge(CUTOFF).to_numpy()
        for scope, mask in [('matched_forecasts', elig & group['available']), ('full_pool', elig)]:
            frame = group['g'].loc[mask]; target = group['y'][mask]
            if target.sum() == 0: continue
            scores = group['x'][mask] @ coef; prob = softmax(scores); order = np.argsort(-scores, kind='stable')
            rank = min(i for i, j in enumerate(order, 1) if target[j] > 0)
            rows.append(dict(scope=scope, variant=variant, year=year, season=frame.Season.iloc[0],
                             predicted=frame.iloc[order[0]]['Player Name'], actual=' / '.join(frame.loc[target > 0, 'Player Name']),
                             winner_rank=rank, top1=int(rank == 1), top3=int(rank <= 3), log_loss=float(-np.log(prob[target > 0].sum())),
                             prior_forecast_seasons=sum(g['usable'] for g in train), source=chosen[year]))
        coefs.extend(dict(variant=variant, year=year, feature=c, coefficient=float(coef[feats.index(c)])) for c in add)
    print('done', variant, flush=True)

r = pd.DataFrame(rows); r.to_csv(OUT / 'backtests.csv', index=False); pd.DataFrame(coefs).to_csv(OUT / 'coefficients.csv', index=False)
summary = []
for scope in r.scope.unique():
    for label, min_prior in [('all_forecast_years', 0), ('3+_prior_forecast_seasons', 3)]:
        for variant in variants:
            a = r[(r.scope == scope) & (r.variant == variant) & (r.prior_forecast_seasons >= min_prior)]
            summary.append(dict(scope=scope, period=label, variant=variant, seasons=len(a), top1=int(a.top1.sum()),
                                top3=int(a.top3.sum()), mean_winner_rank=float(a.winner_rank.mean()), log_loss=float(a.log_loss.mean())))
s = pd.DataFrame(summary); s.to_csv(OUT / 'summary.csv', index=False)
print(cov[cov.source_file == 'CONSENSUS'].to_string(index=False))
print('unmatched rows:', len(unmatched))
print(s.to_string(index=False))
print(r[r.scope == 'full_pool'].pivot_table(index=['year', 'actual'], columns='variant', values='winner_rank').to_string())
