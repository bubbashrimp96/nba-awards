# Exponential availability for all five awards

The availability shortfall remains max(0, ceil(0.85 * actual team games) - G).
The new uncentered feature is expm1(rate * shortfall) / rate,
where rate = log(2) / (0.10 * actual team games). At threshold it is zero;
its marginal cost doubles for each additional 10% of the season missed.
Its initial slope is one game-equivalent unit per shortfall game, and curvature
is a fixed modeling choice, not selected using Embiid or later results.
Each award learns a strictly negative coefficient using only prior seasons.
Other weights are refit; candidate pools, hyperparameters, G terms, MVP
qualifications, expectations and linear rank penalties remain as before.

The exponential replaces the linear availability term rather than stacking
both penalties. Players are not newly excluded below 50%; sufficiently large
shortfalls incur increasingly large deductions. Multi-team schedule fallbacks
remain flagged. Earlier linear versions are preserved for comparison.

Results remain retrospective; the early display years overlap the original
configuration-selection period. See summary.json and before_after.csv.
Run python3 add_exponential_availability.py then python3 build_dashboard_data.py.
