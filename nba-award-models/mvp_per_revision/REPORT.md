# MVP: PER, steals and blocks experiment

## Findings

PER alone is selected by the earlier development-period mean log loss. It preserves 8/11 correct MVP first picks and 10/11 winner top-three appearances, with a small improvement in later mean log loss from 0.973342 to 0.966694. It does not fix any of the three existing misses, and the modest change is not evidence of a substantial forecasting gain.

Adding PER, steals and blocks with all coefficients freely learned produces 7/11 correct picks. Requiring small positive steals and blocks coefficients preserves 8/11 but increases later log loss to 0.987645. The positive version follows the proposed basketball preference; the constraints are imposed, not discovered by the data.

## Comparisons

| Variant | Correct first / 11 | Winner top three / 11 | Mean log loss |
|---|---:|---:|---:|
| baseline | 8 | 10 | 0.973342 |
| PER_only | 8 | 10 | 0.966694 |
| PER_STL_BLK_learned | 7 | 10 | 0.987582 |
| PER_STL_BLK_small_positive | 8 | 10 | 0.987645 |

Lower log loss is better. Candidate pools and team-context inputs remain fixed. All models exclude total WS and VORP and retain wins, conference standing and league standing. The earlier lower-BPM/higher-WS48 sensitivity adjustments were not carried into this experiment; the baseline is the currently documented 8/11 conference model.

## Coefficients for the requested inputs

All coefficients multiply within-season standardized input values. A coefficient is a conditional score change per one standard deviation, not a percentage of importance. PER is player efficiency rating; STL and BLK are per-game figures in the source CSV.

| Variant | PER | Steals | Blocks |
|---|---:|---:|---:|
| PER_only | +0.489898 | Not included | Not included |
| PER_STL_BLK_learned | +0.443973 | -0.270462 | +0.070811 |
| PER_STL_BLK_small_positive | +0.434657 | +0.050000 | +0.131060 |

The small-positive version bounds each defensive coefficient between +0.05 and +0.25 score units per standardized input. Its steals coefficient sits at the minimum, meaning the fit does not want to increase it further under that constraint. A negative freely learned steals coefficient is a conditional relationship in a correlated model; it does not demonstrate that steals are undesirable or cause fewer MVP votes.

PER is fitted alongside the existing advanced statistics, so all coefficients are refit. Some existing terms shrink when PER is included. These are not independent percentage contributions, and the feature should not receive an arbitrary bonus because it is well known.

## Final selected coefficients

| Feature | Coefficient |
|---|---:|
| PTS | +1.112518 |
| AST | +0.542330 |
| TRB | +0.159563 |
| BPM | +0.601063 |
| WS/48 | +0.522870 |
| TS% | -0.031346 |
| G | +1.073295 |
| team_wins | +1.363161 |
| league_standing | +1.173684 |
| conference_standing | +0.512599 |
| PER | +0.489898 |

## Selection and checks

Three proposed families were defined: PER alone; PER plus freely fitted STL and BLK; PER plus small-positive STL and BLK. For each family, half-lives 5, 10 and 20 and L2 settings 0.03, 0.1 and 0.3 are evaluated using rolling mean log loss on 2005-06 through 2014-15. All choose half-life 20 and L2 0.03. PER alone wins the family comparison. The positive-coefficient bounds were specified as a modeling preference and were not tuned to later results.

Each 2015-16 through 2025-26 prediction trains on earlier seasons only. The experiment remains retrospective because those later outcomes were previously examined during the project. The small advantage for PER alone should be treated as tentative.

The unchanged baseline reproduces the existing 11 MVP predictions and log losses. Checks validate unique records, finite inputs and fitted coefficients, complete winner joins, prior-only training cutoffs, normalized model shares, and the defensive coefficient bounds for every rolling positive-constrained fit. Saved aggregate accuracy reconciles to all 44 test rows.

## Files

Run `python3 ../improve_mvp_per.py`. model.json and coefficients.csv contain the earlier-development-selected PER-only candidate. all_models.json and all_coefficients.csv include the requested PER-plus-small-positive-defense candidate as well. comparison_summary.csv, development_grid.csv and historical_backtests.csv contain full comparisons. Existing conference model and PDF remain the published baseline; this experiment does not overwrite them.
