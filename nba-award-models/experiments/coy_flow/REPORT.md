# Supplied Coach of the Year flowchart

Implemented as nonnegative fitted nested bonuses: Moderate chance or better,
plus an additional Runaway bonus. No hard exclusions in production.

Top four means record-based conference rank <= 4; tied records use average rank.
Prior COY wins are coach/franchise specific and strictly earlier than the season.
Exceeding expectations means wins strictly greater than schedule-adjusted preseason
market wins. Missing expectations or record rank yields Unknown, with zero bonuses.
The chart's No chance label is a low tier, not zero modeled probability.

All eight paths are covered by tests. The existing five features, 20-year half-life,
and L2=0.3 remain. Every historical fit uses only earlier seasons. 2001-02 has no
preseason expectations; its tier is Unknown. For 2002-03 through 2025-26 all actual
winners are Moderate chance or Runaway. The hard-exclusion variant was tested for
comparison only; the user selected fitted adjustments and universal eligibility.

Results:

                period         variant  seasons  top1  top3  log_loss  winners_excluded
                   all        baseline       25    11    21  1.577016                 0
                   all    learned_flow       25    12    21  1.557906                 0
                   all hard_exclusions       25    11    21  1.515168                 0
expectations_available        baseline       24    11    21  1.522010                 0
expectations_available    learned_flow       24    12    21  1.502104                 0
expectations_available hard_exclusions       24    11    21  1.457585                 0

These results are retrospective and modest: winner picks 11/25 -> 12/25, top-three
coverage 21/25 unchanged, mean log loss 1.577016 -> 1.557906. Rule labels are not
calibrated outcome probabilities. Full source chart is the user-provided file
/Users/jeevie/Downloads/892557684_1820587172522016_6243970763382729959_n.png.

Raw candidate conditions, classifications, backtests and fitted season coefficients
are saved beside this report. baseline_model.json and baseline_backtests.csv freeze
the original model for reproducibility after deployment.
