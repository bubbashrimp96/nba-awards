# MVP revision: scoring and advanced stats, with an 85% availability threshold

## Result

The requested version removes standalone assists (AST), rebounds (TRB) and games played (G). It retains points, PER, WS/48, TS%, steals, blocks, team wins, league standing and conference standing. BPM, total WS and VORP remain excluded. A new availability penalty replaces the previous positive games coefficient.

| Model | Correct first / 11 | Actual winner top three / 11 | Mean log loss |
|---|---:|---:|---:|
| previous_no_BPM | 8 | 10 | 1.003 |
| no_AST_TRB_G_85pct_penalty | 9 | 9 | 1.069 |

This revision fixes 2025-26, selecting Shai Gilgeous-Alexander instead of Nikola Jokić, without losing any previously correct first pick. First-place accuracy rises from 73% to 82%. It misses 2016-17 (selects Curry; actual Westbrook ranks eighth) and 2022-23 (selects Jokić; actual Embiid ranks fourth). Top-three coverage falls from 10/11 to 9/11 and log loss worsens: the wrong cases receive less share, despite the additional correct first pick. It is an improvement in winner accuracy, not every metric.

## Availability rule

For a player on a known team:

`threshold = ceil(0.85 * actual team regular-season games)`

`shortfall = max(0, threshold - player games played)`

`availability contribution = negative penalty per game * shortfall`

No games coefficient remains in the standardized inputs. The shortfall is an uncentered raw count: zero above or at the threshold, with a constant negative score change for each further game below it. PER and WS/48 use the same within-season normalization as before. The penalty slope is fitted from earlier seasons, subject to a strictly negative bound (numerical upper bound -1e-8), rather than hand-picked from test outcomes.

| Team season games | Required appearances | No penalty | One-game penalty begins at |
|---:|---:|---|---:|
| 82 | 70 | 70 or more | 69 |
| 72 | 62 | 62 or more | 61 |
| 73 | 63 | 63 or more | 62 |
| 75 | 64 | 64 or more | 63 |
| 66 | 57 | 57 or more | 56 |
| 50 | 43 | 43 or more | 42 |

The ceiling follows the requested 85% rule: 70/82, 62/72 and 63/73 meet or exceed 85%. The rule is an analyst preference for this model, not an implementation of official NBA award eligibility.

## COVID and schedule handling

2020-21 uses 72 team games and a threshold of 62. The 2019-20 season was uneven: the saved final records span 64 to 75 games, including teams outside the restart. Each known team uses its own final games (wins plus losses), rather than treating the entire league as 72 or 73 games. Thus 2019-20 thresholds differ appropriately. The same mechanism handles the earlier 50- and 66-game lockout seasons and canceled games.

For aggregate 2TM/3TM player rows, the CSV does not identify the full team itinerary. Those rows use that season's maximum team schedule as an explicit fallback; availability_audit.csv flags them. It is an approximation for traded players in unequal-length seasons. No actual MVP winner in the modeled seasons has that aggregate-team issue. The original 20-game candidate screen remains unchanged to preserve comparability.

## Fitted coefficients

All terms except availability multiply within-season standardized inputs. Availability multiplies a raw number of games below the threshold; its coefficient is therefore not directly comparable in magnitude to standardized coefficients. These are conditional weights, not percentages or causal effects. The other coefficients are refit after removing AST/TRB/G.

| Feature | Final fitted coefficient |
|---|---:|
| PTS | +0.772399 |
| WS/48 | +0.924300 |
| TS% | -0.281482 |
| team_wins | +0.971642 |
| league_standing | +1.235745 |
| conference_standing | +0.384627 |
| PER | +1.265100 |
| STL | -0.091222 |
| BLK | -0.215933 |
| games_below_threshold | -0.447225 |

The full-history penalty is -0.447225 score units per game below threshold. For an 82-game team: 70 games gives 0; 69 gives -0.447; 68 gives -0.894; 65 gives -2.236. Historical predictions use their own prior-season fits, so these full-history weights do not reproduce those predictions directly.

Steals and blocks remain freely fitted, following the no-BPM 8/11 model inspected before this change. The new full-history fit gives both negative conditional coefficients. No small-positive defensive constraint has been added silently.

## Every historical first pick

| Season | Revised pick | Actual MVP | Actual winner model rank | Correct |
|---|---|---|---:|---|
| 2015-16 | Stephen Curry | Stephen Curry | 1 | True |
| 2016-17 | Stephen Curry | Russell Westbrook | 8 | False |
| 2017-18 | James Harden | James Harden | 1 | True |
| 2018-19 | Giannis Antetokounmpo | Giannis Antetokounmpo | 1 | True |
| 2019-20 | Giannis Antetokounmpo | Giannis Antetokounmpo | 1 | True |
| 2020-21 | Nikola Jokić | Nikola Jokić | 1 | True |
| 2021-22 | Nikola Jokić | Nikola Jokić | 1 | True |
| 2022-23 | Nikola Jokić | Joel Embiid | 4 | False |
| 2023-24 | Nikola Jokić | Nikola Jokić | 1 | True |
| 2024-25 | Shai Gilgeous-Alexander | Shai Gilgeous-Alexander | 1 | True |
| 2025-26 | Shai Gilgeous-Alexander | Shai Gilgeous-Alexander | 1 | True |

## Revised top-three score breakdown

Each season uses only earlier seasons to fit coefficients. Team contribution is team wins + league standing + conference standing. Defense is STL + BLK. All values below are score contributions rather than raw statistics. Scores compare players within a season; they are not percentages. Shares remain uncalibrated.

### 2015-16

| Player | PTS | PER | WS/48 | TS% | Defense | Team | Availability | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Stephen Curry | +3.33 | +2.95 | +3.26 | +0.39 | +0.43 | +7.49 | -0.00 | 17.86 |
| Kawhi Leonard | +1.92 | +2.03 | +2.68 | +0.24 | +0.04 | +6.50 | -0.00 | 13.40 |
| LeBron James | +2.57 | +2.28 | +2.18 | +0.16 | +0.11 | +5.84 | -0.00 | 13.13 |

### 2016-17

| Player | PTS | PER | WS/48 | TS% | Defense | Team | Availability | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Stephen Curry | +2.35 | +1.72 | +2.02 | +0.26 | +0.40 | +7.46 | -0.00 | 14.22 |
| Kawhi Leonard | +2.38 | +2.20 | +2.53 | +0.22 | +0.18 | +6.33 | -0.00 | 13.84 |
| James Harden | +2.91 | +2.16 | +2.25 | +0.23 | +0.19 | +5.21 | -0.00 | 12.95 |

### 2017-18

| Player | PTS | PER | WS/48 | TS% | Defense | Team | Availability | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| James Harden | +3.04 | +4.09 | +2.50 | -0.48 | -0.40 | +5.35 | -0.00 | 14.10 |
| LeBron James | +2.62 | +3.78 | +1.63 | -0.49 | -0.49 | +2.93 | -0.00 | 9.98 |
| Damian Lillard | +2.53 | +2.90 | +1.71 | -0.31 | -0.04 | +2.93 | -0.00 | 9.73 |

### 2018-19

| Player | PTS | PER | WS/48 | TS% | Defense | Team | Availability | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Giannis Antetokounmpo | +2.54 | +4.24 | +2.58 | -0.61 | -0.89 | +5.22 | -0.00 | 13.07 |
| James Harden | +3.74 | +4.16 | +2.09 | -0.43 | -0.40 | +3.39 | -0.00 | 12.56 |
| Kevin Durant | +2.30 | +2.57 | +1.45 | -0.53 | -0.49 | +4.68 | -0.00 | 9.97 |

### 2019-20

| Player | PTS | PER | WS/48 | TS% | Defense | Team | Availability | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Giannis Antetokounmpo | +2.34 | +4.45 | +2.63 | -0.31 | -0.40 | +5.24 | -0.00 | 13.94 |
| LeBron James | +1.83 | +2.85 | +1.56 | -0.10 | -0.11 | +4.63 | -0.00 | 10.66 |
| Anthony Davis | +1.92 | +3.33 | +2.22 | -0.30 | -1.33 | +4.63 | -0.00 | 10.48 |

### 2020-21

| Player | PTS | PER | WS/48 | TS% | Defense | Team | Availability | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Nikola Jokić | +1.92 | +4.49 | +2.98 | -0.52 | -0.32 | +3.50 | -0.00 | 12.06 |
| Giannis Antetokounmpo | +2.12 | +3.95 | +2.17 | -0.43 | -0.64 | +3.30 | -0.76 | 9.71 |
| Chris Paul | +0.74 | +1.93 | +1.57 | -0.22 | -0.06 | +4.78 | -0.00 | 8.73 |

### 2021-22

| Player | PTS | PER | WS/48 | TS% | Defense | Team | Availability | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Nikola Jokić | +2.00 | +5.19 | +3.24 | -0.60 | -0.57 | +1.65 | -0.00 | 10.89 |
| Joel Embiid | +2.41 | +4.74 | +2.53 | -0.34 | -0.96 | +3.11 | -1.59 | 9.91 |
| Giannis Antetokounmpo | +2.33 | +4.99 | +3.00 | -0.44 | -0.88 | +3.11 | -2.38 | 9.72 |

### 2022-23

| Player | PTS | PER | WS/48 | TS% | Defense | Team | Availability | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Nikola Jokić | +1.38 | +4.86 | +3.72 | -0.54 | -0.37 | +3.93 | -1.09 | 11.89 |
| Jayson Tatum | +1.92 | +2.70 | +1.60 | -0.14 | -0.33 | +4.34 | -0.00 | 10.10 |
| Domantas Sabonis | +0.85 | +2.65 | +2.22 | -0.40 | -0.09 | +2.70 | -0.00 | 7.93 |

### 2023-24

| Player | PTS | PER | WS/48 | TS% | Defense | Team | Availability | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Nikola Jokić | +1.97 | +4.58 | +2.72 | -0.30 | -0.29 | +3.90 | -0.00 | 12.57 |
| Shai Gilgeous-Alexander | +2.41 | +4.13 | +2.40 | -0.25 | -0.35 | +3.90 | -0.00 | 12.24 |
| Luka Dončić | +2.86 | +3.81 | +1.69 | -0.18 | -0.10 | +2.38 | -0.00 | 10.47 |

### 2024-25

| Player | PTS | PER | WS/48 | TS% | Defense | Team | Availability | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Shai Gilgeous-Alexander | +2.54 | +5.09 | +3.31 | -0.33 | -0.55 | +4.87 | -0.00 | 14.93 |
| Nikola Jokić | +2.19 | +5.49 | +3.28 | -0.45 | -0.35 | +2.24 | -0.00 | 12.40 |
| Jayson Tatum | +1.88 | +2.34 | +1.25 | -0.07 | -0.12 | +3.94 | -0.00 | 9.22 |

### 2025-26

| Player | PTS | PER | WS/48 | TS% | Defense | Team | Availability | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Shai Gilgeous-Alexander | +2.44 | +4.98 | +3.49 | -0.44 | -0.37 | +4.48 | -0.88 | 13.70 |
| Nikola Jokić | +2.04 | +5.43 | +3.39 | -0.46 | -0.37 | +2.93 | -2.21 | 10.74 |
| Jalen Duren | +1.08 | +3.58 | +2.63 | -0.55 | -0.22 | +3.87 | -0.00 | 10.40 |

## Validation and reproduction

Half-lives 5, 10 and 20 and L2 settings 0.03, 0.1 and 0.3 were compared using rolling mean log loss on 2005-06 through 2014-15. The selected settings remain half-life 20 and L2 0.03. Later 2015-16 through 2025-26 predictions use only earlier seasons for fitting. These later outcomes have already been inspected, so results remain retrospective and need future validation. This experiment changes several inputs together and does not isolate the effect of removing AST versus removing TRB versus changing availability.

Run `python3 ../improve_mvp_availability.py`. Tests verify all schedule thresholds, zero contribution at/above threshold, constant negative slope for additional shortfall, 72-game schedules in 2020-21, score reconciliation, negative historical slopes, required feature removals and all aggregate accuracy counts.

model.json and coefficients.csv hold the requested revision. historical_backtests.csv and before_after.csv hold the 11 season results. selected_top5.csv includes score contributions for the first five in every season. availability_audit.csv exposes every threshold and schedule fallback. Existing earlier revisions and the PDF are preserved; this report reflects the new experiment.
