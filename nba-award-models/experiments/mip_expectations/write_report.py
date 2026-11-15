from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
OUT=Path(__file__).resolve().parent
r=pd.read_csv(OUT/'backtests.csv');coverage=pd.read_csv(OUT/'coverage.csv');summary=pd.read_csv(OUT/'summary.csv');f=pd.read_csv(OUT/'forecasts.csv')
assert len(f)==620 and not f.duplicated(['year','PlayerID']).any()
assert len(r)==28
assert np.isfinite(r.log_loss).all()
assert r[r.year>=2022].training_forecast_seasons.ge(1).all()
assert (r[(r.variant=='add_expected_points')&(r.year==2021)].training_forecast_seasons==0).all()
primary=summary[(summary.scope=='matched_forecasts')&(summary.period=='two_with_usable_prior_forecast_training')]
full=summary[(summary.scope=='full_pool_neutral_missing')&(summary.period=='two_with_usable_prior_forecast_training')]
method=dict(extracted_player_forecasts=620,publication_seasons=['2019-20','2020-21','2021-22','2022-23'],primary_test_seasons=['2021-22','2022-23'],half_life=20,regularization=.3,cutoff_ppg=13,forecast_training='Only seasons earlier than predicted year. Surprise terms are zero for years with no publication or without a forecast for the actual winner. Other missing candidates receive neutral standardized surprise. Existing training pools and baseline features retained.',matched_pool='At least 13 actual PPG, original MIP pool, and published forecast. Baseline and variants use identical matched scoring pools.',full_pool='All original MIP candidates with at least 13 PPG; missing forecasts receive neutral standardized surprise.',source_dates={2020:'2019-08-30',2021:'2020-12-02',2022:'2021-09-17',2023:'2022-09-12'},raw_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob('raw_*.json')},warning='Recovered current copies of dated historical publications; independent opening-night snapshot verification unavailable. Very small test: only one then two prior usable expectation seasons. Forecast coverage incomplete, especially among lower-ranked candidates. No active model change.')
(OUT/'method.json').write_text(json.dumps(method,indent=2)+'\n')
def table(df):
 lines=['| Variant | Seasons | Winner first | Winner top three | Mean log loss |','|---|---:|---:|---:|---:|']
 for _,v in df.iterrows():lines.append(f'| {v.variant} | {v.seasons} | {v.top1} | {v.top3} | {v.log_loss:.6f} |')
 return '\n'.join(lines)
report='''# Published preseason expectations: exploratory MIP test

Recovered all 155 ranked forecasts for each of four publication seasons,
620 player-season forecasts in total. Names were reconciled to player IDs with
explicit aliases; no unresolved identities remain. Original tables and their
source URLs are preserved. Active app models and projections are unchanged.

## Main comparison

2020-21 supplies the first usable training season. Test seasons are 2021-22
and 2022-23, with only one then two earlier usable forecast seasons. Full model
coefficients are refit only on earlier years, retaining the active half-life,
regularization, availability terms and 13 PPG scoring cutoff. New expectation
features are actual PPG/APG/RPG minus published preseason forecasts, standardized
within each season's covered original candidate pool. Forecast-free training
years have zero standardized expectation features, retaining baseline learning.

A publication missing the eventual winner cannot teach reliable expectation
weights, so its expectation features are zero for training. The 2019-20 list
omits Brandon Ingram; that year is unavailable for the matched-pool evaluation.
2020-21 is a warm-up for expectation learning and is not counted in the primary
comparison. Replacement variants still remove existing per-game deltas throughout
training; comparisons are not frozen-weight feature swaps.

Both baseline and variants rank the exact same players with published forecasts.

'''+table(primary)+'''

## Full-pool robustness check

Retain all MIP candidates scoring at least 13 PPG. Missing forecasts get neutral
standardized expectation features; no actual stats are substituted as forecasts.

'''+table(full)+'''

## Coverage

'''+coverage.drop(columns='missing_candidates').to_string(index=False)+'''

The source provides 155 fantasy-relevant players, not every NBA player. Candidate
coverage is 84-90%; vote-recipient coverage is lower. See coverage.csv for all
excluded names. All primary-test winners have forecasts. A missing forecast is
not equivalent to a low preseason expectation.

## Limits and validation

- Four complete source tables, 155 unique ranks each, 620 unique player-seasons.
- Explicit player-name aliases including typographical errors; no fuzzy guessing.
- Validated positive numeric counting-stat ranges and finite backtest losses.
- Reproduced deployed first picks independently for all four seasons on the full pool.
- No future season enters coefficient fitting; no tuning sweep.
- Dated original articles were recovered, but no independent opening-night snapshot
  was recovered. These are exploratory results, not a verified point-in-time backtest.
- Two test seasons are far too few for a confident adoption decision.

Run `.venv/bin/python experiments/mip_expectations/run.py` and then
`.venv/bin/python experiments/mip_expectations/write_report.py`.
See summary.csv, backtests.csv, coverage.csv, forecasts.csv, feature_audit.csv,
coefficients.csv, full_baseline_check.csv and method.json.
'''
(OUT/'REPORT.md').write_text(report)
print(table(primary));print('\nFull pool:\n'+table(full))
print('\nSeason details:\n'+r[(r.scope=='matched_forecasts')&(r.year>=2022)].to_string(index=False))
