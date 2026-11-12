# MVP: qualified PPG and WS/48 top-five penalties

Players must qualify for both Basketball Reference PPG and WS/48 leaderboards.
Qualification comes from cached source non_qual flags where available. Under a source
rate limit, uncached seasons use the documented season-specific qualification rules.
PPG is reconstructed from total points divided by games; local WS/48 is rounded,
so tied rounded values share the best competition rank. Cached full-precision
sorting values are used for downloaded seasons. Aggregate player rows are used
for traded players. This distinction is recorded in every source record.
The ranks use the full qualified league, before MVP screening.

Two additional raw, uncentered inputs are max(0, PPG rank - 5) and
max(0, WS/48 rank - 5). Each has a strictly negative fitted coefficient:
zero penalty in the top five, one unit at sixth, two at seventh, etc.
The penalties are additive. Players unqualified for either leaderboard are
excluded, as requested. Other features and training settings are retained;
all coefficients are refitted on the newly qualified candidate pool.

Current: 13/16 first picks,
15/16 top-three winners,
log loss 0.843654. Previous expectations model:
13/16,
15/16, 0.790687.
Full-history PPG penalty per place: -0.057497.
Full-history WS/48 penalty per place: -0.059978.
Historical fits have their own slopes. Results remain retrospective.

Cached source pages, qualification flags, sorting precision and hashes:
data/qualified_ranks/. Requirement reference:
https://www.basketball-reference.com/about/rate_stat_req.html
The original NBA official award eligibility is not fully enforced; leaderboard
qualification and the separate 85% model availability penalty are distinct rules.

Run python3 fetch_qualified_ranks.py, python3 add_mvp_rank_penalties.py,
then python3 build_dashboard_data.py.
