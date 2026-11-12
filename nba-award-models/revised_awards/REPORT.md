# Current revised award models, 2000–01 through 2025–26

All five awards replace the previous availability curve with (expm1(r*d)-r*d)/r,
r=ln(2)/(0.10*team_games), d=max(0,ceil(85%*team_games)-G). Removing the linear
component softens small deficits without adding a grace period; larger deficits
remain exponential. Each award fits a strictly negative strength on prior seasons.

MVP PPG rank growth doubles over 5% of the qualified field, previously 10%.
WS48 rank growth remains 10%. Qualifications, zero penalty through fifth and
other MVP inputs remain. DPOY removes player DRB, adds team defensive-rating
rank (negative coefficient) and team wins (nonnegative coefficient). Sixth Man
adds conference seed (negative coefficient), with documented historical fallback
to record-based rank when reported seeds are missing/zero or from the incomplete
1999–00 feed. These are fitted inputs, not hard top-five/top-four eligibility cuts.

Data: NBA regular-season advanced team ratings via the sportsdataverse archive
for 1996–97 onward; Basketball Reference archive for earlier training. All 1,177
team records match cached standings. Voting covers every award from 2000–01 onward.
Preseason expectations begin in 2002–03; earlier seasons have no expectation signal.
Multi-team rows use candidate-pool medians for missing team context; schedules use
the flagged season maximum approximation. Team ratings are not player DRtg.

All historical fits use only prior seasons, with existing half-lives and L2 values.
The changes were requested after inspecting 2016–17 ROY and 2022–23 MVP, so these
are retrospective results, not fresh external validation. See summary.json and
before_after.csv for all 26 seasons, not only the cases motivating the changes.

Run python3 build_revised_awards.py then python3 build_dashboard_data.py.
