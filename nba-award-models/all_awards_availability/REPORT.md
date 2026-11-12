# Availability penalty for every award

ROY, DPOY, MIP and Sixth Man now add max(0, ceil(0.85 * actual team season games) - G).
Each award fits its own strictly negative coefficient per raw game of shortfall.
The feature is uncentered and unstandardized, with exactly zero contribution at or
above the threshold. Other features, award-specific candidate pools, half-lives
and regularization are retained; all coefficients are refit. Existing G terms remain
where they existed; MIP gains only the new shortfall feature, not a standalone G term.

An 82-game season requires 70 appearances; 72 requires 62; 66 requires 57.
Known teams use their actual schedule. Aggregate multi-team rows use the season's
maximum team games, explicitly flagged as an approximation. Candidates remain eligible
below 85%; they receive a penalty rather than automatic exclusion. MVP retains its
current qualified PPG/WS48 model and existing availability penalty unchanged.

All 2010–11 through 2025–26 predictions train on prior seasons. Comparisons remain
retrospective, and the early years overlap original configuration development.
Results and before/after metrics are in summary.json and before_after.csv.

Run python3 add_award_availability.py then python3 build_dashboard_data.py.
