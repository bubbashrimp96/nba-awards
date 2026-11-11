# MVP ranking eligibility: top 20 points per game

## Rule implemented

A player can appear in the MVP rankings only if they rank in the top 20 in points per game among that season's players with at least 20 appearances. Points means PPG (the existing PTS field), not total season points. Rank uses competition ranking: tied scorers share the highest position they occupy. All ties at 20th qualify; 2023-24 therefore has 21 eligible candidates. This is the requested model rule, not the NBA scoring-title qualification rule.

This is a ranking-eligibility filter applied after the existing model scores players. Feature definitions, original candidate-pool normalization, recency weights, coefficients and availability penalty remain unchanged. Shares are recalculated over eligible candidates only and remain uncalibrated. A smaller denominator can lower winner log loss mechanically; that change is not evidence of a better underlying score model.

Historical training contests retain all previously used player rows and actual winners. Do not remove a historical season merely because its winner fails the new eligibility condition. The filter is outcome-independent and uses only same-season PPG and appearances.

## Results

| Version | Correct first / 11 | Actual winner top three / 11 | Mean log loss |
|---|---:|---:|---:|
| previous_availability_model | 9 | 9 | 1.069 |
| top20_PPG_85pct_penalty | 9 | 10 | 0.866 |

First-place accuracy stays 9/11. In 2022-23 Jokić is excluded because he ranks tied 24th in PPG (24.5); the model now picks Tatum, while actual winner Embiid moves from fourth to second. Westbrook in 2016-17 moves from eighth to sixth but the model still picks Curry. Other first picks are unchanged.

## Top-three rankings and score contributions

Contributions are in model-score units. Team combines wins, league standing and conference standing; Defense combines STL and BLK. Availability is the below-85%-appearances penalty. Scores are unchanged for retained candidates compared with the previous model. Compare scores within seasons.

### 2015-16 - actual MVP: Stephen Curry

| Rank | Player | PPG | Scoring rank | PTS | PER | WS/48 | TS% | Defense | Team | Availability | Total |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Stephen Curry | 30.1 | 1 | +3.33 | +2.95 | +3.26 | +0.39 | +0.43 | +7.49 | -0.00 | 17.86 |
| 2 | Kawhi Leonard | 21.2 | 15 | +1.92 | +2.03 | +2.68 | +0.24 | +0.04 | +6.50 | -0.00 | 13.40 |
| 3 | LeBron James | 25.3 | 5 | +2.57 | +2.28 | +2.18 | +0.16 | +0.11 | +5.84 | -0.00 | 13.13 |

### 2016-17 - actual MVP: Russell Westbrook

| Rank | Player | PPG | Scoring rank | PTS | PER | WS/48 | TS% | Defense | Team | Availability | Total |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Stephen Curry | 25.3 | 10 | +2.35 | +1.72 | +2.02 | +0.26 | +0.40 | +7.46 | -0.00 | 14.22 |
| 2 | Kawhi Leonard | 25.5 | 9 | +2.38 | +2.20 | +2.53 | +0.22 | +0.18 | +6.33 | -0.00 | 13.84 |
| 3 | James Harden | 29.1 | 2 | +2.91 | +2.16 | +2.25 | +0.23 | +0.19 | +5.21 | -0.00 | 12.95 |

### 2017-18 - actual MVP: James Harden

| Rank | Player | PPG | Scoring rank | PTS | PER | WS/48 | TS% | Defense | Team | Availability | Total |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | James Harden | 30.4 | 1 | +3.04 | +4.09 | +2.50 | -0.48 | -0.40 | +5.35 | -0.00 | 14.10 |
| 2 | LeBron James | 27.5 | 3 | +2.62 | +3.78 | +1.63 | -0.49 | -0.49 | +2.93 | -0.00 | 9.98 |
| 3 | Damian Lillard | 26.9 | 4 | +2.53 | +2.90 | +1.71 | -0.31 | -0.04 | +2.93 | -0.00 | 9.73 |

### 2018-19 - actual MVP: Giannis Antetokounmpo

| Rank | Player | PPG | Scoring rank | PTS | PER | WS/48 | TS% | Defense | Team | Availability | Total |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Giannis Antetokounmpo | 27.7 | 3 | +2.54 | +4.24 | +2.58 | -0.61 | -0.89 | +5.22 | -0.00 | 13.07 |
| 2 | James Harden | 36.1 | 1 | +3.74 | +4.16 | +2.09 | -0.43 | -0.40 | +3.39 | -0.00 | 12.56 |
| 3 | Kevin Durant | 26.0 | 9 | +2.30 | +2.57 | +1.45 | -0.53 | -0.49 | +4.68 | -0.00 | 9.97 |

### 2019-20 - actual MVP: Giannis Antetokounmpo

| Rank | Player | PPG | Scoring rank | PTS | PER | WS/48 | TS% | Defense | Team | Availability | Total |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Giannis Antetokounmpo | 29.5 | 5 | +2.34 | +4.45 | +2.63 | -0.31 | -0.40 | +5.24 | -0.00 | 13.94 |
| 2 | LeBron James | 25.3 | 14 | +1.83 | +2.85 | +1.56 | -0.10 | -0.11 | +4.63 | -0.00 | 10.66 |
| 3 | Anthony Davis | 26.1 | 12 | +1.92 | +3.33 | +2.22 | -0.30 | -1.33 | +4.63 | -0.00 | 10.48 |

### 2020-21 - actual MVP: Nikola Jokić

| Rank | Player | PPG | Scoring rank | PTS | PER | WS/48 | TS% | Defense | Team | Availability | Total |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Nikola Jokić | 26.4 | 11 | +1.92 | +4.49 | +2.98 | -0.52 | -0.32 | +3.50 | -0.00 | 12.06 |
| 2 | Giannis Antetokounmpo | 28.1 | 5 | +2.12 | +3.95 | +2.17 | -0.43 | -0.64 | +3.30 | -0.76 | 9.71 |
| 3 | Damian Lillard | 28.8 | 3 | +2.21 | +3.02 | +1.68 | -0.37 | +0.05 | +1.88 | -0.00 | 8.47 |

### 2021-22 - actual MVP: Nikola Jokić

| Rank | Player | PPG | Scoring rank | PTS | PER | WS/48 | TS% | Defense | Team | Availability | Total |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Nikola Jokić | 27.1 | 10 | +2.00 | +5.19 | +3.24 | -0.60 | -0.57 | +1.65 | -0.00 | 10.89 |
| 2 | Joel Embiid | 30.6 | 1 | +2.41 | +4.74 | +2.53 | -0.34 | -0.96 | +3.11 | -1.59 | 9.91 |
| 3 | Giannis Antetokounmpo | 29.9 | 3 | +2.33 | +4.99 | +3.00 | -0.44 | -0.88 | +3.11 | -2.38 | 9.72 |

### 2022-23 - actual MVP: Joel Embiid

| Rank | Player | PPG | Scoring rank | PTS | PER | WS/48 | TS% | Defense | Team | Availability | Total |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Jayson Tatum | 30.1 | 6 | +1.92 | +2.70 | +1.60 | -0.14 | -0.33 | +4.34 | -0.00 | 10.10 |
| 2 | Joel Embiid | 33.1 | 1 | +2.21 | +4.83 | +2.88 | -0.35 | -1.15 | +3.75 | -4.37 | 7.81 |
| 3 | De'Aaron Fox | 25.0 | 20 | +1.43 | +2.18 | +0.93 | -0.11 | +0.01 | +2.70 | -0.00 | 7.14 |

### 2023-24 - actual MVP: Nikola Jokić

| Rank | Player | PPG | Scoring rank | PTS | PER | WS/48 | TS% | Defense | Team | Availability | Total |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Nikola Jokić | 26.4 | 11 | +1.97 | +4.58 | +2.72 | -0.30 | -0.29 | +3.90 | -0.00 | 12.57 |
| 2 | Shai Gilgeous-Alexander | 30.1 | 4 | +2.41 | +4.13 | +2.40 | -0.25 | -0.35 | +3.90 | -0.00 | 12.24 |
| 3 | Luka Dončić | 33.9 | 2 | +2.86 | +3.81 | +1.69 | -0.18 | -0.10 | +2.38 | -0.00 | 10.47 |

### 2024-25 - actual MVP: Shai Gilgeous-Alexander

| Rank | Player | PPG | Scoring rank | PTS | PER | WS/48 | TS% | Defense | Team | Availability | Total |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Shai Gilgeous-Alexander | 32.7 | 1 | +2.54 | +5.09 | +3.31 | -0.33 | -0.55 | +4.87 | -0.00 | 14.93 |
| 2 | Nikola Jokić | 29.6 | 3 | +2.19 | +5.49 | +3.28 | -0.45 | -0.35 | +2.24 | -0.00 | 12.40 |
| 3 | Jayson Tatum | 26.8 | 6 | +1.88 | +2.34 | +1.25 | -0.07 | -0.12 | +3.94 | -0.00 | 9.22 |

### 2025-26 - actual MVP: Shai Gilgeous-Alexander

| Rank | Player | PPG | Scoring rank | PTS | PER | WS/48 | TS% | Defense | Team | Availability | Total |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Shai Gilgeous-Alexander | 31.1 | 2 | +2.44 | +4.98 | +3.49 | -0.44 | -0.37 | +4.48 | -0.88 | 13.70 |
| 2 | Nikola Jokić | 27.7 | 8 | +2.04 | +5.43 | +3.39 | -0.46 | -0.37 | +2.93 | -2.21 | 10.74 |
| 3 | Victor Wembanyama | 25.0 | 17 | +1.72 | +4.71 | +2.49 | -0.25 | -1.54 | +4.08 | -2.65 | 8.57 |

## Historical winner coverage

All actual MVP winners in the 2015-16 through 2025-26 evaluation window meet the new top-20 PPG rule. Across the full 1985-86 through 2025-26 history, these actual winners would be unranked under it:

| Season | Actual MVP | PPG | Scoring rank |
|---|---|---:|---:|
| 1989-90 | Magic Johnson | 22.3 | 21 |
| 2004-05 | Steve Nash | 15.5 | 60 |
| 2005-06 | Steve Nash | 18.8 | 33 |

## Saved files and checks

Run `python3 ../rank_mvp_top20.py`. all_eligible_rankings.csv gives the complete filtered leaderboard, PPG ranks and score contributions for every evaluated season; selected_top5.csv contains the top five; eligibility_audit.csv shows all eligibility decisions. historical_winner_eligibility.csv covers all 41 historical winners. model.json records the rule alongside the unchanged scoring coefficients.

Checks confirm every ranked player satisfies top-20 PPG and the 20-game minimum, every tied qualifying player is retained, model shares sum to one among eligible players, coefficients are unchanged, score totals reconcile, original historical scores reproduce the saved baseline, and all 11 evaluation-year winners remain eligible. Each season's fit uses earlier seasons only; comparisons remain retrospective. Earlier model versions and the existing PDF are preserved.
