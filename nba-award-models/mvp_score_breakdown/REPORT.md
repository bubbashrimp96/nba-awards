# MVP top-three score breakdown: no BPM, freely learned PER/STL/BLK

## Model used

This is the latest no-BPM model with freely learned PER, steals and blocks coefficients (8/11 correct first picks), not the small-positive-defense version (7/11) and not the older conference model currently in the PDF. Inputs: PTS, AST, TRB, WS/48, TS%, G, team wins, league standing, conference standing, PER, STL, BLK. Total WS and VORP remain excluded.

Each season uses its own fitted coefficients trained only on preceding seasons, starting in 1985-86. Half-life is 20 seasons; L2 regularization is 0.03. Do not use the single full-history coefficient set to reproduce these historical scores. The experiment remains retrospective because the outcomes have already been inspected.

## How to read the scores

Each contribution = season-fitted coefficient x the player standardized value within the candidate pool for that season. Positive terms raise the score; negative terms lower it. Contributions are in model score units, not percentages or raw basketball statistics. Total score is the sum of all 12 terms. A larger total ranks higher within a season. Scores should not be compared directly across seasons, whose pools, normalizations and coefficients differ.

Model share = exp(score) divided by the sum over all candidates, not just the top three. These shares are uncalibrated and are not estimated vote shares or established win probabilities. Displayed components are rounded, so their displayed sum can differ slightly from the displayed total. Full-precision CSV files reconcile exactly.

Grouped view: Production = PTS + AST + TRB contributions; Advanced = PER + WS/48 + TS%; Defense = STL + BLK; Team = team wins + league standing + conference standing. Games is its own term. The raw-value, normalization and coefficient trail is in feature_contributions.csv.

## Grouped contributions for all seasons

### 2015-16 - actual MVP: Stephen Curry (model rank 1)

| Rank | Player | Production | Advanced | Defense | Games | Team | Total | Model share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Stephen Curry * | +8.89 | +3.69 | -0.16 | +0.89 | +7.88 | 21.19 | 96.3% |
| 2 | Russell Westbrook | +9.07 | +2.28 | -0.13 | +0.94 | +4.73 | 16.91 | 1.3% |
| 3 | LeBron James | +7.70 | +2.35 | -0.01 | +0.74 | +5.92 | 16.70 | 1.1% |

Individual contributions:

| Input | Stephen Curry | Russell Westbrook | LeBron James |
|---|---:|---:|---:|
| PTS | +6.291 | +4.313 | +4.853 |
| AST | +2.452 | +4.383 | +2.504 |
| TRB | +0.145 | +0.377 | +0.339 |
| PER | +0.117 | +0.091 | +0.091 |
| WS/48 | +3.120 | +2.120 | +2.079 |
| TS% | +0.453 | +0.073 | +0.185 |
| STL | -0.098 | -0.091 | -0.049 |
| BLK | -0.064 | -0.038 | +0.041 |
| G | +0.891 | +0.942 | +0.737 |
| Team wins | +3.331 | +1.454 | +1.663 |
| League standing | +2.135 | +1.548 | +1.841 |
| Conference standing | +2.417 | +1.732 | +2.417 |

### 2016-17 - actual MVP: Russell Westbrook (model rank 4)

| Rank | Player | Production | Advanced | Defense | Games | Team | Total | Model share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | James Harden | +10.48 | +2.56 | -0.03 | +0.98 | +5.31 | 19.29 | 66.1% |
| 2 | Stephen Curry | +6.77 | +2.35 | -0.13 | +0.88 | +7.85 | 17.71 | 13.7% |
| 3 | Kevin Durant | +6.15 | +3.15 | +0.31 | +0.02 | +7.85 | 17.47 | 10.7% |

Individual contributions:

| Input | James Harden | Stephen Curry | Kevin Durant |
|---|---:|---:|---:|
| PTS | +5.429 | +4.384 | +4.329 |
| AST | +4.669 | +2.334 | +1.420 |
| TRB | +0.379 | +0.055 | +0.397 |
| PER | +0.148 | +0.117 | +0.150 |
| WS/48 | +2.143 | +1.924 | +2.596 |
| TS% | +0.266 | +0.306 | +0.406 |
| STL | -0.049 | -0.068 | -0.025 |
| BLK | +0.021 | -0.064 | +0.333 |
| G | +0.979 | +0.878 | +0.018 |
| Team wins | +1.819 | +3.392 | +3.392 |
| League standing | +1.818 | +2.110 | +2.110 |
| Conference standing | +1.669 | +2.344 | +2.344 |

### 2017-18 - actual MVP: James Harden (model rank 1)

| Rank | Player | Production | Advanced | Defense | Games | Team | Total | Model share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | James Harden * | +9.55 | +3.34 | -0.46 | +0.61 | +6.01 | 19.05 | 92.9% |
| 2 | LeBron James | +9.51 | +2.47 | -0.36 | +1.14 | +3.03 | 15.79 | 3.6% |
| 3 | Russell Westbrook | +9.86 | +1.97 | -0.35 | +1.04 | +2.19 | 14.71 | 1.2% |

Individual contributions:

| Input | James Harden | LeBron James | Russell Westbrook |
|---|---:|---:|---:|
| PTS | +5.678 | +4.886 | +4.313 |
| AST | +3.603 | +3.765 | +4.412 |
| TRB | +0.266 | +0.857 | +1.134 |
| PER | +1.530 | +1.414 | +1.035 |
| WS/48 | +2.153 | +1.408 | +0.806 |
| TS% | -0.345 | -0.355 | +0.127 |
| STL | -0.390 | -0.247 | -0.390 |
| BLK | -0.066 | -0.117 | +0.036 |
| G | +0.612 | +1.143 | +1.037 |
| Team wins | +2.709 | +1.008 | +0.781 |
| League standing | +1.504 | +0.991 | +0.632 |
| Conference standing | +1.794 | +1.034 | +0.781 |

### 2018-19 - actual MVP: Giannis Antetokounmpo (model rank 1)

| Rank | Player | Production | Advanced | Defense | Games | Team | Total | Model share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Giannis Antetokounmpo * | +8.04 | +3.40 | -0.45 | +0.66 | +5.72 | 17.37 | 48.2% |
| 2 | James Harden | +10.06 | +3.08 | -0.52 | +0.99 | +3.66 | 17.28 | 43.9% |
| 3 | Kevin Durant | +6.54 | +1.85 | -0.15 | +0.99 | +5.12 | 14.34 | 2.3% |

Individual contributions:

| Input | Giannis Antetokounmpo | James Harden | Kevin Durant |
|---|---:|---:|---:|
| PTS | +4.672 | +6.876 | +4.226 |
| AST | +1.919 | +2.753 | +1.919 |
| TRB | +1.448 | +0.433 | +0.399 |
| PER | +1.599 | +1.570 | +0.968 |
| WS/48 | +2.251 | +1.826 | +1.268 |
| TS% | -0.450 | -0.315 | -0.388 |
| STL | -0.213 | -0.458 | -0.003 |
| BLK | -0.241 | -0.057 | -0.149 |
| G | +0.665 | +0.986 | +0.986 |
| Team wins | +2.330 | +1.446 | +1.951 |
| League standing | +1.557 | +1.059 | +1.335 |
| Conference standing | +1.834 | +1.158 | +1.834 |

### 2019-20 - actual MVP: Giannis Antetokounmpo (model rank 1)

| Rank | Player | Production | Advanced | Defense | Games | Team | Total | Model share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Giannis Antetokounmpo * | +8.13 | +3.78 | -0.20 | +0.59 | +5.85 | 18.15 | 80.5% |
| 2 | LeBron James | +8.28 | +2.38 | -0.16 | +0.82 | +5.14 | 16.46 | 14.9% |
| 3 | James Harden | +8.66 | +3.15 | -0.43 | +0.87 | +2.36 | 14.62 | 2.3% |

Individual contributions:

| Input | Giannis Antetokounmpo | LeBron James | James Harden |
|---|---:|---:|---:|
| PTS | +4.337 | +3.391 | +5.418 |
| AST | +1.727 | +4.091 | +2.703 |
| TRB | +2.069 | +0.797 | +0.534 |
| PER | +1.646 | +1.054 | +1.387 |
| WS/48 | +2.360 | +1.404 | +2.041 |
| TS% | -0.222 | -0.074 | -0.276 |
| STL | -0.089 | -0.150 | -0.333 |
| BLK | -0.115 | -0.008 | -0.093 |
| G | +0.591 | +0.818 | +0.875 |
| Team wins | +2.418 | +1.933 | +0.962 |
| League standing | +1.552 | +1.326 | +0.650 |
| Conference standing | +1.879 | +1.879 | +0.748 |

### 2020-21 - actual MVP: Nikola Jokić (model rank 1)

| Rank | Player | Production | Advanced | Defense | Games | Team | Total | Model share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Nikola Jokić * | +8.01 | +4.15 | -0.28 | +1.15 | +3.84 | 16.88 | 80.1% |
| 2 | Giannis Antetokounmpo | +7.29 | +3.26 | -0.39 | +0.57 | +3.66 | 14.37 | 6.5% |
| 3 | Joel Embiid | +5.80 | +3.64 | -0.39 | +0.04 | +5.12 | 14.21 | 5.6% |

Individual contributions:

| Input | Nikola Jokić | Giannis Antetokounmpo | Joel Embiid |
|---|---:|---:|---:|
| PTS | +3.499 | +3.864 | +3.950 |
| AST | +2.886 | +1.743 | +0.266 |
| TRB | +1.630 | +1.678 | +1.582 |
| PER | +1.780 | +1.565 | +1.677 |
| WS/48 | +2.717 | +1.981 | +2.265 |
| TS% | -0.346 | -0.289 | -0.301 |
| STL | -0.201 | -0.168 | -0.102 |
| BLK | -0.075 | -0.226 | -0.286 |
| G | +1.149 | +0.567 | +0.038 |
| Team wins | +1.505 | +1.358 | +1.797 |
| League standing | +1.133 | +0.956 | +1.429 |
| Conference standing | +1.202 | +1.341 | +1.896 |

### 2021-22 - actual MVP: Nikola Jokić (model rank 1)

| Rank | Player | Production | Advanced | Defense | Games | Team | Total | Model share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Nikola Jokić * | +8.89 | +4.57 | -0.44 | +0.96 | +1.83 | 15.81 | 34.5% |
| 2 | Giannis Antetokounmpo | +7.91 | +4.38 | -0.50 | +0.59 | +3.39 | 15.76 | 32.9% |
| 3 | Joel Embiid | +7.30 | +3.93 | -0.54 | +0.64 | +3.39 | 14.72 | 11.7% |

Individual contributions:

| Input | Nikola Jokić | Giannis Antetokounmpo | Joel Embiid |
|---|---:|---:|---:|
| PTS | +3.664 | +4.265 | +4.415 |
| AST | +2.753 | +1.730 | +0.951 |
| TRB | +2.471 | +1.912 | +1.938 |
| PER | +2.064 | +1.986 | +1.887 |
| WS/48 | +2.894 | +2.679 | +2.263 |
| TS% | -0.390 | -0.282 | -0.217 |
| STL | -0.257 | -0.129 | -0.129 |
| BLK | -0.179 | -0.373 | -0.412 |
| G | +0.960 | +0.586 | +0.640 |
| Team wins | +0.786 | +1.153 | +1.153 |
| League standing | +0.543 | +0.943 | +0.943 |
| Conference standing | +0.502 | +1.291 | +1.291 |

### 2022-23 - actual MVP: Joel Embiid (model rank 3)

| Rank | Player | Production | Advanced | Defense | Games | Team | Total | Model share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Nikola Jokić | +8.65 | +5.11 | -0.25 | +0.67 | +4.17 | 18.34 | 82.1% |
| 2 | Giannis Antetokounmpo | +7.88 | +3.30 | -0.23 | +0.32 | +5.16 | 16.42 | 12.0% |
| 3 | Joel Embiid * | +7.02 | +4.36 | -0.77 | +0.49 | +3.99 | 15.10 | 3.2% |

Individual contributions:

| Input | Nikola Jokić | Giannis Antetokounmpo | Joel Embiid |
|---|---:|---:|---:|
| PTS | +2.563 | +3.758 | +4.120 |
| AST | +3.584 | +1.623 | +0.905 |
| TRB | +2.502 | +2.502 | +1.993 |
| PER | +1.799 | +1.543 | +1.788 |
| WS/48 | +3.446 | +1.787 | +2.664 |
| TS% | -0.139 | -0.034 | -0.089 |
| STL | -0.097 | -0.021 | -0.051 |
| BLK | -0.155 | -0.211 | -0.717 |
| G | +0.669 | +0.320 | +0.494 |
| Team wins | +1.623 | +2.317 | +1.762 |
| League standing | +1.102 | +1.393 | +1.199 |
| Conference standing | +1.445 | +1.445 | +1.032 |

### 2023-24 - actual MVP: Nikola Jokić (model rank 1)

| Rank | Player | Production | Advanced | Defense | Games | Team | Total | Model share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Nikola Jokić * | +7.66 | +4.52 | -0.15 | +1.18 | +3.95 | 17.17 | 79.3% |
| 2 | Luka Dončić | +8.86 | +3.26 | -0.17 | +0.71 | +2.34 | 15.00 | 9.0% |
| 3 | Shai Gilgeous-Alexander | +5.87 | +4.04 | -0.30 | +0.97 | +3.95 | 14.55 | 5.7% |

Individual contributions:

| Input | Nikola Jokić | Luka Dončić | Shai Gilgeous-Alexander |
|---|---:|---:|---:|
| PTS | +3.180 | +4.630 | +3.895 |
| AST | +2.881 | +3.226 | +1.671 |
| TRB | +1.602 | +1.002 | +0.309 |
| PER | +2.131 | +1.774 | +1.921 |
| WS/48 | +2.482 | +1.542 | +2.196 |
| TS% | -0.090 | -0.054 | -0.074 |
| STL | -0.176 | -0.176 | -0.320 |
| BLK | +0.022 | +0.002 | +0.022 |
| G | +1.185 | +0.705 | +0.972 |
| Team wins | +1.691 | +0.902 | +1.691 |
| League standing | +1.697 | +1.182 | +1.697 |
| Conference standing | +0.566 | +0.262 | +0.566 |

### 2024-25 - actual MVP: Shai Gilgeous-Alexander (model rank 1)

| Rank | Player | Production | Advanced | Defense | Games | Team | Total | Model share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Shai Gilgeous-Alexander * | +6.41 | +5.06 | -0.19 | +1.16 | +5.39 | 17.82 | 64.7% |
| 2 | Nikola Jokić | +9.04 | +5.17 | -0.22 | +0.82 | +2.32 | 17.14 | 32.8% |
| 3 | Giannis Antetokounmpo | +7.38 | +4.16 | -0.01 | +0.65 | +1.44 | 13.62 | 1.0% |

Individual contributions:

| Input | Shai Gilgeous-Alexander | Nikola Jokić | Giannis Antetokounmpo |
|---|---:|---:|---:|
| PTS | +4.392 | +3.789 | +3.944 |
| AST | +1.807 | +3.506 | +1.852 |
| TRB | +0.207 | +1.747 | +1.587 |
| PER | +2.331 | +2.512 | +2.303 |
| WS/48 | +2.826 | +2.800 | +1.938 |
| TS% | -0.101 | -0.138 | -0.083 |
| STL | -0.206 | -0.228 | -0.034 |
| BLK | +0.016 | +0.004 | +0.021 |
| G | +1.157 | +0.820 | +0.652 |
| Team wins | +2.906 | +0.955 | +0.739 |
| League standing | +1.818 | +0.994 | +0.423 |
| Conference standing | +0.665 | +0.375 | +0.279 |

### 2025-26 - actual MVP: Shai Gilgeous-Alexander (model rank 2)

| Rank | Player | Production | Advanced | Defense | Games | Team | Total | Model share |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Nikola Jokić | +8.47 | +5.51 | -0.12 | +0.55 | +3.13 | 17.52 | 61.1% |
| 2 | Shai Gilgeous-Alexander * | +5.98 | +5.38 | -0.12 | +0.74 | +4.94 | 16.91 | 33.3% |
| 3 | Luka Dončić | +7.72 | +3.40 | -0.22 | +0.48 | +2.72 | 14.11 | 2.0% |

Individual contributions:

| Input | Nikola Jokić | Shai Gilgeous-Alexander | Luka Dončić |
|---|---:|---:|---:|
| PTS | +3.386 | +4.047 | +4.513 |
| AST | +3.677 | +1.866 | +2.616 |
| TRB | +1.408 | +0.063 | +0.595 |
| PER | +2.739 | +2.514 | +2.079 |
| WS/48 | +2.967 | +3.060 | +1.414 |
| TS% | -0.200 | -0.190 | -0.089 |
| STL | -0.177 | -0.177 | -0.231 |
| BLK | +0.052 | +0.052 | +0.010 |
| G | +0.546 | +0.739 | +0.482 |
| Team wins | +1.347 | +2.451 | +1.236 |
| League standing | +1.292 | +1.802 | +1.101 |
| Conference standing | +0.487 | +0.687 | +0.386 |

* Marks the actual MVP when present in the top three. The 2016-17 winner Westbrook is outside the top three.

## Reproduction

Run `python3 ../explain_mvp_top3.py`. All 11 first picks, winner ranks and log losses are checked against the saved no-BPM learned-weight backtest. All 33 score totals are verified against the sum of their 12 contributions, as are their grouped subtotals. Source CSV and model definitions remain unchanged.
