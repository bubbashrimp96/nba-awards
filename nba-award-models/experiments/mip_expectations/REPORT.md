# Published preseason expectations: exploratory MIP test

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

| Variant | Seasons | Winner first | Winner top three | Mean log loss |
|---|---:|---:|---:|---:|
| baseline | 2 | 1 | 1 | 1.671693 |
| add_expected_points | 2 | 1 | 1 | 1.630498 |
| add_expected_points_rebounds_assists | 2 | 1 | 1 | 2.048915 |
| replace_previous_year_deltas | 2 | 1 | 1 | 2.185446 |

## Full-pool robustness check

Retain all MIP candidates scoring at least 13 PPG. Missing forecasts get neutral
standardized expectation features; no actual stats are substituted as forecasts.

| Variant | Seasons | Winner first | Winner top three | Mean log loss |
|---|---:|---:|---:|---:|
| baseline | 2 | 1 | 1 | 1.852783 |
| add_expected_points | 2 | 1 | 1 | 1.784099 |
| add_expected_points_rebounds_assists | 2 | 1 | 1 | 2.138497 |
| replace_previous_year_deltas | 2 | 1 | 1 | 2.278967 |

## Coverage

 year  published  eligible  covered  coverage  winner_covered  voted_players  voted_with_projection
 2020        155        99       85  0.858586           False             15                     10
 2021        155       114       96  0.842105            True             25                     20
 2022        155       111       93  0.837838            True             12                      6
 2023        155       113      102  0.902655            True             13                      9

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
