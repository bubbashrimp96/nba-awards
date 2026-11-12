# PER MVP with an 85% availability penalty

All current PER features, including G, are retained. The new unstandardized input is
max(0, ceil(0.85 * team regular-season games) - player games played).
Its coefficient is fitted on prior seasons and constrained strictly negative.
At or above the threshold its added contribution is zero. Each further game below
threshold incurs the same negative score adjustment within that fit.

82-game schedule: threshold 70. 72-game schedule: threshold 62.
Unequal seasons use each team's actual regular-season games. Aggregate multi-team
rows use the season maximum as a flagged approximation. The 20-game screen remains.
Existing G is still fitted separately, so there can also be an overall games effect.

Current results: 13/16 first picks, 15/16 top-three winners,
log loss 0.802573. Prior PER model: 11/16,
15/16, log loss 0.782498.
Final full-history penalty per shortfall game: -0.382434 score units.
Historical fits have their own penalty slopes. Coefficients are refit with unchanged
half-life and regularization. Results remain retrospective. 2010–11 through 2014–15 overlaps the earlier configuration-selection development period, so those seasons are not an untouched test.

Run python3 add_mvp_availability.py, then python3 build_dashboard_data.py.
