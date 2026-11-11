# MVP revision 2: add conference standing

## Result

The development-selected model now includes team wins, league standing and conference standing, and excludes total win shares and VORP. Correct first picks increase from 5/11 in the original model and 7/11 in the first team-context revision to 8/11 (73%). Winner top-three coverage remains 10/11, compared with 11/11 originally.

The additional correct pick is Giannis Antetokounmpo in 2018-19; the earlier team-context revision picked James Harden. No previously correct pick is lost. Remaining first-pick misses are 2016-17, 2022-23 and 2025-26.

| Model | Correct first | Winner top three | Mean winner log loss |
|---|---:|---:|---:|
| Original MVP | 5/11 | 11/11 | 1.135 |
| First team-context revision | 7/11 | 10/11 | 0.876 |
| Conference revision | 8/11 | 10/11 | 0.973 |

Lower log loss is better. The conference revision improves winner selection but worsens this probability-based metric relative to the previous revision: it assigns less share to some actual winners, even though more finish first. The model shares remain uncalibrated.

## Conference standing definition

Conference membership comes directly from each historical season in ESPN's standings feed, rather than assuming current memberships. Rank teams within their conference by final regular-season win percentage, wins / (wins + losses). Average the positions for identical records: a tie for third and fourth receives rank 3.5. This is a regular-season record-based conference rank, not an official tiebreak-resolved position or postseason seed.

The input is normalized for changes in conference size: conference_standing = 1 - (conference_rank - 1) / (conference_size - 1). First place receives 1 and last place 0, before the usual candidate-pool standardization. League standing is calculated the same way across all teams using win percentage. This also improves the handling of unequal schedules in 2019-20 relative to ranking raw wins.

The source playoffSeed field is retained only in the data audit, clearly marked as unused. It is excluded from the fitted features because it can reflect play-in outcomes or historical division-seeding rules. For example, the 2025-26 feed gives Portland playoff seed 7 despite Phoenix having more regular-season wins. That postseason ordering must not enter an end-of-regular-season MVP model.

## Model coefficients

Every coefficient multiplies a within-season, within-candidate-pool z-score. Candidate filtering remains at least 20 games, and total WS remains excluded. Tied record ranks do not use arbitrary tiebreak guesses.

| Input | Final fitted coefficient |
|---|---:|
| PTS | +1.270822 |
| AST | +0.541459 |
| TRB | +0.211327 |
| BPM | +0.742119 |
| WS/48 | +0.703879 |
| TS% | -0.001005 |
| G | +1.024954 |
| team_wins | +1.352526 |
| league_standing | +1.158667 |
| conference_standing | +0.503129 |

Recency half-life: 20 seasons. L2 regularization: 0.03. The final coefficients use all available seasons through 2025-26; the backtests use separate fits restricted to earlier seasons.

Wins, league standing and conference standing are correlated. Their coefficients are conditional score weights, not independent percentages or causal effects.

## Historical picks

| Season | Previous revision | With conference standing | Actual MVP | Actual winner rank |
|---|---|---|---|---:|
| 2015-16 | Stephen Curry | Stephen Curry | Stephen Curry | 1 |
| 2016-17 | James Harden | James Harden | Russell Westbrook | 4 |
| 2017-18 | James Harden | James Harden | James Harden | 1 |
| 2018-19 | James Harden | Giannis Antetokounmpo | Giannis Antetokounmpo | 1 |
| 2019-20 | Giannis Antetokounmpo | Giannis Antetokounmpo | Giannis Antetokounmpo | 1 |
| 2020-21 | Nikola Jokić | Nikola Jokić | Nikola Jokić | 1 |
| 2021-22 | Nikola Jokić | Nikola Jokić | Nikola Jokić | 1 |
| 2022-23 | Nikola Jokić | Nikola Jokić | Joel Embiid | 3 |
| 2023-24 | Nikola Jokić | Nikola Jokić | Nikola Jokić | 1 |
| 2024-25 | Shai Gilgeous-Alexander | Shai Gilgeous-Alexander | Shai Gilgeous-Alexander | 1 |
| 2025-26 | Nikola Jokić | Nikola Jokić | Shai Gilgeous-Alexander | 2 |

## Selection and comparison

Three new families were defined before evaluating their later results: add conference standing to the previous lean model; use conference instead of league standing; or add conference with VORP retained. Each family was tuned using half-lives 5, 10 and 20 and L2 settings 0.03, 0.1 and 0.3, using rolling mean log loss on season-ending years 2006-2015. The conference-plus-league lean family won that earlier development comparison.

| Variant | Correct first | Winner top three | Mean test log loss |
|---|---:|---:|---:|
| original | 5/11 | 11/11 | 1.135 |
| conference_plus_league | 8/11 | 10/11 | 0.973 |
| conference_instead_of_league | 7/11 | 10/11 | 0.972 |
| conference_with_VORP | 7/11 | 10/11 | 1.001 |

Every 2015-16 through 2025-26 prediction uses only earlier seasons for fitting. Nevertheless, those seasons were already inspected during this project, so the comparison is retrospective rather than a new untouched test. We did not select the new family based on which had the best later winner count.

## Standings validation and source repairs

Downloaded ESPN responses cover 41 seasons and 1,177 team-seasons. Historical conference switches are represented in the feed and checked explicitly: Miami in the West in 1988-89, Charlotte in the West in 1989-90, Orlando in the West in 1990-91, and New Orleans switching to the West in 2004-05. All final team wins agree with the existing local wins cache after the repairs below.

Source-quality checks found three issues, repaired only in the derived table; all raw responses are preserved:

- The 1999-00 ESPN response is a late-season snapshot with incomplete records. For that season use final wins from the original cache and losses = 82 - wins. The final-record reference is https://www.basketball-reference.com/leagues/NBA_2000_standings.html . Official cross-checks include the Pacers' 56-26 record at https://www.nba.com/news/conference-finals-appearances-indiana-pacers and Utah's 55-27 record in https://ak-static-int.nba.com/wp-content/uploads/sites/3/2016/10/2016-17-Media-Guide-Jazz.pdf . The complete 29-team table was not independently re-audited team by team.
- Dallas 1993-94 is listed with 70 losses in the feed, creating an 83-game record. Corrected to 13-69; reference: https://www.basketball-reference.com/teams/DAL/1994.html .
- Denver 1997-98 is listed with 72 losses, also creating an 83-game record. Corrected to 11-71; reference: https://www.basketball-reference.com/teams/DEN/1998.html .

The derived records reconcile total league wins to total losses for every season. Canceled/unequal schedules are retained where applicable, including the 2012-13 Indiana/Boston cancellation and 2019-20 uneven schedules.

Unmatched player team labels are only multi-team aggregates: {'2TM': 1710, '3TM': 110}. Their team inputs use the current candidate-pool medians, as before. Every actual MVP winner has known team and conference data.

## Files and reproduction

Run `python3 ../conference_standings/prepare_standings.py`, then `python3 ../improve_mvp_conference.py` from this directory. No network is needed to reproduce the analysis from the cached raw responses.

- model.json and coefficients.csv: selected conference model and final fitted coefficients.
- comparison_summary.csv and historical_backtests.csv: all model-family results.
- before_after.csv: comparison against the original MVP.
- vs_previous_revision.csv: comparison against the first team-context revision.
- selected_top5.csv: each season's top five with input data and conference ranks.
- team_context_audit.csv: all candidate team/conference joins.
- ../conference_standings/team_standings.csv: complete derived standings.
- ../conference_standings/raw/: original ESPN responses.
- ../conference_standings/sources.json and source_corrections.csv: URLs, hashes and exact repairs.

ESPN feed URL pattern: https://site.web.api.espn.com/apis/v2/sports/basketball/nba/standings?season=2025&type=0&level=2 . Public standings page: https://www.espn.com/nba/standings/_/season/2025 . The original five models, first MVP revision and prior PDF remain preserved.
