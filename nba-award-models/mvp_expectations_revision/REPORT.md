# MVP: performance against preseason expectations

Adds wins_above_expectation = actual team wins - expected team wins.
Expected wins use Basketball Reference preseason market over/under lines,
scaled by actual team games / preseason schedule games (82 normally, 66 in
2011–12, 72 in 2020–21). Scaling handles uneven 2019–20 schedules fairly.
The coefficient is fitted nonnegative, so greater overperformance cannot reduce
the score holding other inputs fixed. Existing PER, games and availability rules remain.
Within-season standardized contributions may be negative for below-average overperformance.

Preseason data starts in 2002–03. Earlier training seasons have a constant neutral
zero overperformance feature; expectations are never reconstructed from actual results.
Aggregate-team rows use candidate-pool season medians, matching existing imputation.
Raw source pages, URLs and hashes are in data/preseason_wins/.

Current first picks: 13/16; winner top three:
15/16; mean log loss 0.790687.
Prior model: 13/16,
15/16, 0.802573.
Final expectation coefficient: 0.545439 per within-season z score.

2016–17 OKC: preseason 45 wins, actual 47, overperformance +2.
This feature does not guarantee a Westbrook first pick and is not tuned to do so.
All historical fits train only on prior seasons, with unchanged half-life and
regularization. All results remain retrospective; 2010–15 overlaps the earlier
configuration-selection development period.

Run python3 fetch_preseason_wins.py, python3 add_mvp_expectations.py,
then python3 build_dashboard_data.py.
