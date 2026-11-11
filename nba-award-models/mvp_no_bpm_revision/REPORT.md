# MVP experiment: remove BPM, include PER, steals and blocks

## Results

Retains team wins, league standing, conference standing, WS/48, points, assists, rebounds, TS% and games played. Removes BPM completely and includes PER, steals per game and blocks per game. No post-fit BPM or WS/48 multipliers are applied.

| Version | Correct first / 11 | Winner top three / 11 | Mean log loss |
|---|---:|---:|---:|
| baseline | 8 | 10 | 0.973342 |
| no_BPM_PER_STL_BLK_learned | 8 | 10 | 1.003452 |
| no_BPM_PER_STL_BLK_small_positive | 7 | 10 | 0.985796 |

The freely learned version retains 8/11 correct winners. The small-positive defensive version declines to 7/11, replacing the correct 2021-22 Jokić pick with Giannis. Neither fixes the three original remaining misses: Westbrook in 2016-17, Embiid in 2022-23, or Shai in 2025-26. Lower log loss is better; neither new version improves that later metric relative to the baseline.

## Defensive coefficient interpretation

The small-positive version restricts both STL and BLK coefficients to [+0.05,+0.25] on within-season standardized inputs. These bounds impose modest positive contributions as requested; they are not evidence that historical fitting independently favors such contributions. Freely learned signs are conditional relationships among correlated inputs, not causal effects.

| Version | PER | STL | BLK | WS/48 |
|---|---:|---:|---:|---:|
| no_BPM_PER_STL_BLK_learned | +0.708729 | -0.166125 | +0.058031 | +0.911909 |
| no_BPM_PER_STL_BLK_small_positive | +0.667043 | +0.050000 | +0.101473 | +0.815561 |

## All first picks

| Season | Baseline | No BPM, learned defense | No BPM, small positive defense | Actual MVP |
|---|---|---|---|---|
| 2015-16 | Stephen Curry | Stephen Curry | Stephen Curry | Stephen Curry |
| 2016-17 | James Harden | James Harden | James Harden | Russell Westbrook |
| 2017-18 | James Harden | James Harden | James Harden | James Harden |
| 2018-19 | Giannis Antetokounmpo | Giannis Antetokounmpo | Giannis Antetokounmpo | Giannis Antetokounmpo |
| 2019-20 | Giannis Antetokounmpo | Giannis Antetokounmpo | Giannis Antetokounmpo | Giannis Antetokounmpo |
| 2020-21 | Nikola Jokić | Nikola Jokić | Nikola Jokić | Nikola Jokić |
| 2021-22 | Nikola Jokić | Nikola Jokić | Giannis Antetokounmpo | Nikola Jokić |
| 2022-23 | Nikola Jokić | Nikola Jokić | Nikola Jokić | Joel Embiid |
| 2023-24 | Nikola Jokić | Nikola Jokić | Nikola Jokić | Nikola Jokić |
| 2024-25 | Shai Gilgeous-Alexander | Shai Gilgeous-Alexander | Shai Gilgeous-Alexander | Shai Gilgeous-Alexander |
| 2025-26 | Nikola Jokić | Nikola Jokić | Nikola Jokić | Shai Gilgeous-Alexander |

## Validation and saved status

For each proposed family, half-lives 5, 10 and 20 and regularization 0.03, 0.1 and 0.3 were compared using rolling log loss on 2005-06 through 2014-15. Both selected half-life 20 and regularization 0.03. Small-positive defense won that earlier family comparison, despite performing worse on later winner counts. model.json and coefficients.csv store that development-selected candidate; all_models.json and all_coefficients.csv retain both candidates and the baseline. Selection was not changed after seeing later accuracy.

All 2015-16 through 2025-26 predictions use earlier seasons only. This remains a retrospective experiment because those later outcomes have already been inspected. Checks reproduce the 8/11 baseline, verify chronological cutoffs and coefficient bounds, and reconcile all 33 saved predictions to the summary. BPM may appear in the top-five audit as source context but is absent from both proposed models' feature lists.

Run `python3 ../improve_mvp_no_bpm.py`. Existing baseline model and PDF remain unchanged: this experiment does not demonstrate an overall improvement.
