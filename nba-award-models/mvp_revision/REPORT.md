# MVP revision 1: team success without total win shares

## Result

The development-selected revision increases retrospective first-place accuracy from 5/11 (45%) to 7/11 (64%) over 2015-16 through 2025-26. Mean winner log loss improves from 1.135 to 0.876. Top-three coverage declines from 11/11 to 10/11, because the actual 2016-17 winner, Russell Westbrook, moves from second to fourth. No previously correct first-place pick becomes incorrect.

This is a candidate improvement, not evidence of a newly validated forecasting system. The later seasons were already examined when discussing the original errors. Each season is still predicted from earlier seasons only, and feature/settings selection uses 2005-06 through 2014-15 only, but the design process has retrospective knowledge. A genuinely untouched test requires future seasons or another precommitted evaluation.

## Changes

- Remove total win shares (WS), as requested.
- Keep WS/48 and games played (G).
- Add team regular-season wins and normalized league-wide standing based on wins.
- Compare versions with and without VORP; the earlier validation period selects the version without VORP.
- Keep candidate screening at 20 games so the before/after comparison uses the same pool.
- Retain recent-season weighting. The selected half-life is 20 seasons and L2 regularization is 0.03. The original uses half-life 20 and L2 0.1.

Total WS overlaps with WS/48 and playing time, but is not exactly reproduced by WS/48 and games played: total minutes are approximately the missing exposure term, since WS is approximately WS/48 times total minutes divided by 48 (subject to rounding). Team wins is a separate team-outcome input. The removal is a useful simplification rather than proof that all of WS information was already present.

## Comparison of the defined variants

Every revised family gets the same half-life grid (5, 10, 20) and regularization grid (0.03, 0.1, 0.3), selected on earlier development seasons by rolling mean log loss. Feature-family selection also uses development log loss. The family winner is lean_team_context. Later results for the alternatives are diagnostic, not a reason to switch the selected family. Because settings are retuned, the differences are not solely fixed-coefficient effects.

| Variant | Correct first | Winner top three | Mean log loss | Selected on development |
|---|---:|---:|---:|---|
| original | 5/11 | 11/11 | 1.135 | False |
| no_total_WS | 6/11 | 11/11 | 1.090 | False |
| team_wins | 7/11 | 11/11 | 0.872 | False |
| team_wins_standing | 7/11 | 10/11 | 0.898 | False |
| lean_team_context | 7/11 | 10/11 | 0.876 | True |

The team-wins-only version ties the selected version in first-place accuracy and retains 11/11 top-three coverage. Adding standing is therefore not an unqualified win in the later comparison. It remains in the selected candidate because it was favored by the pre-test development criterion, not because it won every test metric.

## Revised score

Standardize each input within the season and candidate pool after replacing missing values with the pool median. Multiply each z-score by the corresponding coefficient and sum. Positive league-standing values mean better standing. These are conditional fitted score coefficients, not percentages of importance.

| Input | Final coefficient |
|---|---:|
| PTS | +1.253038 |
| AST | +0.539329 |
| TRB | +0.209999 |
| BPM | +0.714597 |
| WS/48 | +0.737894 |
| TS% | +0.003924 |
| G | +1.001840 |
| team_wins | +1.486628 |
| league_standing | +1.347731 |

The final coefficients use all available seasons through 2025-26. Historical predictions used separate fits on earlier seasons only. Softmax shares remain uncalibrated model shares.

## Team wins and standing definitions

The local team-wins cache has all single-team mappings for the modeled seasons. Standing is league-wide rank of wins with average ranks for tied win totals. For N teams, normalized standing = 1 - (rank - 1)/(N - 1). First place is 1; last place is 0. Conference standings and official tiebreakers are not available in this cache and are not implied. Wins and standing are correlated; L2 regularization stabilizes the fit but does not make their effects independent.

Within-season standardization handles common differences in season length. In 2019-20, teams played unequal schedules; raw wins rank is not a verified ranking by win percentage. True team games, losses and official standings would improve this input.

Players with aggregate 2TM or 3TM team identifiers do not have a direct team match. Their team features receive the current candidate-pool median; no final team is guessed and no current award outcome is used for this mapping. All historical MVP winners match a known single team. Coverage is 13823/15643 candidate rows; all 1820 missing team matches are aggregate multi-team rows.

## Every test season

| Season | Original pick | Revised pick | Actual winner | Revised winner rank |
|---|---|---|---|---:|
| 2015-16 | Stephen Curry | Stephen Curry | Stephen Curry | 1 |
| 2016-17 | James Harden | James Harden | Russell Westbrook | 4 |
| 2017-18 | James Harden | James Harden | James Harden | 1 |
| 2018-19 | James Harden | James Harden | Giannis Antetokounmpo | 2 |
| 2019-20 | James Harden | Giannis Antetokounmpo | Giannis Antetokounmpo | 1 |
| 2020-21 | Nikola Jokić | Nikola Jokić | Nikola Jokić | 1 |
| 2021-22 | Nikola Jokić | Nikola Jokić | Nikola Jokić | 1 |
| 2022-23 | Nikola Jokić | Nikola Jokić | Joel Embiid | 3 |
| 2023-24 | Nikola Jokić | Nikola Jokić | Nikola Jokić | 1 |
| 2024-25 | Nikola Jokić | Shai Gilgeous-Alexander | Shai Gilgeous-Alexander | 1 |
| 2025-26 | Nikola Jokić | Nikola Jokić | Shai Gilgeous-Alexander | 2 |

## Checks and reproducibility

The script independently reproduces all 11 original MVP first picks and winner ranks, with original log losses matching within numerical tolerance. It asserts unique player-season keys, finite transformed inputs and coefficients, normalized softmax shares, complete winner joins, known team context for winners, and training cutoffs before each predicted season.

Run `python3 ../improve_mvp.py` from this directory. The original five models, original backtests and existing PDF are preserved. Revision outputs live only in mvp_revision. `selection_frozen.json` records development-only selection; `development_grid.csv` records all configurations; `historical_backtests.csv` records all compared test variants; `before_after.csv` compares the chosen revision with the original; `selected_top5.csv` exposes the leading candidates and inputs; `team_context_audit.csv` and `team_standings.csv` expose the team join and rank calculations. `model.json` stores source hashes and final settings.

## Remaining MVP misses

The revised first picks still miss 2016-17, 2018-19, 2022-23 and 2025-26. Potential future hypotheses include richer team context, player availability relative to season length, teammate strength and prior MVP history. These should be specified and validated in a disciplined chronological design rather than assigning special-case bonuses to force these four known outcomes.
