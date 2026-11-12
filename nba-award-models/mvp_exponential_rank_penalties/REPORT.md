# Exponential MVP rank penalties

The same exponential shape used for availability now applies independently to
qualified PPG and WS/48 ranks below fifth. Let d=max(0,rank-5), N be the full
qualified leaderboard size, and r=ln(2)/(0.10*N). Each penalty is a strictly
negative fitted weight times expm1(r*d)/r. It is zero in the top five; marginal
cost doubles each additional 10% of the qualified field below fifth.
The growth fraction is a fixed modeling choice, not selected using later results.

Each term uses its own qualified field size, including qualified players excluded
by other MVP screening. It is not standardized or centered. Existing MVP features,
qualification exclusions, 85% exponential availability, expectations and settings
are retained; all MVP weights are refitted on prior seasons. Other award models
are unchanged. Previously hidden places-below-fifth columns remain hidden in the app.
Qualification/rank source and rounded WS48 tie limitations remain documented.
Results remain retrospective. See summary.json and before_after.csv.

Run python3 add_mvp_exponential_rank_penalties.py, then python3 build_dashboard_data.py.
