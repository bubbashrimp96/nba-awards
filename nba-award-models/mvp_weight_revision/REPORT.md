# MVP sensitivity: lower BPM and higher WS/48

## Outcome

Tested nine combinations of lower BPM and higher WS/48, keeping every other coefficient, the features, conference/league standings, recency half-life (20) and regularization (0.03) unchanged. For each historical season, first fit only on prior seasons, then apply the two multipliers to those fitted coefficients. This is an explicit coefficient adjustment, not a new unconstrained fit or a feature-unit rescaling.

None of the nine tested settings improves first-place accuracy beyond the current 8/11. The setting selected on the earlier 2005-06 to 2014-15 development period is BPM x0.25 and WS/48 x1.25. It slightly improves development log loss (0.825 to 0.809), but later first-place accuracy declines to 7/11 and later log loss worsens (0.973 to 1.016). It loses the correct 2021-22 Jokić pick to Giannis and fixes none of the three prior misses. This candidate is saved for inspection; the current model and PDF continue to represent the 8/11 conference model.

Less aggressive settings retain 8/11; none fixes the three remaining first-pick misses. Some improve later log loss, but those later diagnostics were not used to select the weights. All these results remain retrospective because the later outcomes were previously examined.

## Full sensitivity results

A BPM multiplier of 0.5 means half the existing fitted coefficient. A WS/48 multiplier of 1.5 means a 50% increase. Coefficients multiply within-season standardized inputs, so these multipliers do not represent percentages of total importance.

| BPM multiplier | WS/48 multiplier | Correct / 11 | Winner top 3 / 11 | Mean later log loss | Selected on earlier development |
|---:|---:|---:|---:|---:|---|
| 1.00 | 1.00 | 8 | 10 | 0.973 | False |
| 0.25 | 1.25 | 7 | 10 | 1.016 | True |
| 0.25 | 1.50 | 7 | 10 | 0.997 | False |
| 0.25 | 2.00 | 8 | 10 | 0.970 | False |
| 0.50 | 1.25 | 8 | 10 | 0.985 | False |
| 0.50 | 1.50 | 8 | 10 | 0.973 | False |
| 0.50 | 2.00 | 8 | 10 | 0.958 | False |
| 0.75 | 1.25 | 8 | 10 | 0.971 | False |
| 0.75 | 1.50 | 8 | 10 | 0.964 | False |
| 0.75 | 2.00 | 8 | 10 | 0.956 | False |

The unchanged baseline is 1.0 / 1.0. Lower log loss is better; shares are uncalibrated. No inference that the best later-scoring configuration will generalize is warranted.

## Full-history coefficient comparison for the development-selected candidate

These coefficients are refit through 2025-26 and do not reproduce historical predictions without refitting at each cutoff.

| Input | Current coefficient | Candidate coefficient |
|---|---:|---:|
| PTS | +1.270822 | +1.270822 |
| AST | +0.541459 | +0.541459 |
| TRB | +0.211327 | +0.211327 |
| BPM | +0.742119 | +0.185530 |
| WS/48 | +0.703879 | +0.879849 |
| TS% | -0.001005 | -0.001005 |
| G | +1.024954 | +1.024954 |
| team_wins | +1.352526 | +1.352526 |
| league_standing | +1.158667 | +1.158667 |
| conference_standing | +0.503129 | +0.503129 |

## Season-by-season candidate results

| Season | Current model pick | Candidate pick | Actual winner | Actual winner candidate rank |
|---|---|---|---|---:|
| 2015-16 | Stephen Curry | Stephen Curry | Stephen Curry | 1 |
| 2016-17 | James Harden | James Harden | Russell Westbrook | 4 |
| 2017-18 | James Harden | James Harden | James Harden | 1 |
| 2018-19 | Giannis Antetokounmpo | Giannis Antetokounmpo | Giannis Antetokounmpo | 1 |
| 2019-20 | Giannis Antetokounmpo | Giannis Antetokounmpo | Giannis Antetokounmpo | 1 |
| 2020-21 | Nikola Jokić | Nikola Jokić | Nikola Jokić | 1 |
| 2021-22 | Nikola Jokić | Giannis Antetokounmpo | Nikola Jokić | 2 |
| 2022-23 | Nikola Jokić | Nikola Jokić | Joel Embiid | 3 |
| 2023-24 | Nikola Jokić | Nikola Jokić | Nikola Jokić | 1 |
| 2024-25 | Shai Gilgeous-Alexander | Shai Gilgeous-Alexander | Shai Gilgeous-Alexander | 1 |
| 2025-26 | Nikola Jokić | Nikola Jokić | Shai Gilgeous-Alexander | 2 |

## Three existing misses: effect on actual-winner model share

| Season | Actual winner | Current share | Candidate share | Rank before / after |
|---|---|---:|---:|---|
| 2016-17 | Russell Westbrook | 4.7% | 3.2% | 4 / 4 |
| 2022-23 | Joel Embiid | 2.5% | 4.9% | 3 / 3 |
| 2025-26 | Shai Gilgeous-Alexander | 27.7% | 36.2% | 2 / 2 |

These shares are uncalibrated. In 2016-17 Westbrook's share decreases, while Embiid in 2022-23 and Shai in 2025-26 gain share without moving to first. Raising WS/48 is not a general solution: both Harden in 2016-17 and Jokić in 2022-23 have higher WS/48 than the actual winners in the source data.

## Reproduction and checks

Run `python3 ../adjust_mvp_weights.py`. Original model preparation is retained, and the unchanged multiplier baseline reproduces all 11 current predictions and log losses. Training cutoffs precede each prediction. Outputs store all 110 predictions (10 settings x 11 years), all 10 development summaries, selection records, final coefficients and top-five candidate rankings. Other coefficients are verified unchanged. No later accuracy result is used in the weight-selection rule.
