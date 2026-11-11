# NBA Award Models Explained

Converted from the 16-page guide, updated 9 November 2026.

## Page 1

01 / NBA award models
A detailed guide to all five models and every fitted coefficient
Updated 9 November 2026 | Revised MVP with conference standings | Trained through 2025-26
This guide explains the models fitted to your basketball_stats.csv: Most Valuable Player (MVP), Defensive
Player of the Year (DPOY), Rookie of the Year (ROY), Sixth Man of the Year (SMOY), and Most Improved
Player (MIP).
What these models do
They compare players within a season and learn which combinations of statistics distinguish historical
award winners. Each award has its own candidate pool, inputs, coefficients and recency weighting. These
are end-of-season statistical ranking models.
What to take away
The revised MVP model selects 8 of 11 winners, compared with 5 of 11 originally, using team wins plus
league and conference standing. The other four models retain their original versions. Across the five
current models, 29 of 55 first picks are correct. MIP remains a weak first-choice predictor. Model shares are
uncalibrated.
Guide Pages
How scores and coefficients work 2
How training and recent-season weighting work 3
All five models and their coefficients 4-8
Historical validation and its limits 9
Data, sources and practical use 10
Season-by-season correct and incorrect picks 11-15
MVP revision comparison and standings methods 16
Source snapshot
The analysis uses the Basketball/Data copy of basketball_stats.csv: 25,312 unique player-seasons from
1949-50 through 2025-26. Award-model training begins in 1985-86. Historical winner labels come from
your existing NBA project. The source CSV was not modified.
NBA AWARD MODELS | Methodology and coefficient guide 1

## Page 2

02 / Scores and coefficients
Step 1: compare like with like
For each award and season, first select its candidate pool. Missing feature values are replaced by that
pool's median. Each feature is then standardized using the pool's mean and population standard deviation:
z = (player value - candidate-pool average) / candidate-pool standard deviation
A z-score of +1 means one standard deviation above the pool average; -1 means one below. This makes
points, percentages and advanced statistics comparable and partly adjusts for changes in statistical eras. It
does not remove every difference between eras.
Step 2: add the weighted statistics
Player score = coefficient[1] x z[1] + ... + coefficient[p] x z[p]
A coefficient is the score change from a one-standard-deviation increase in that feature, holding the other
standardized inputs fixed. Coefficients are not percentages, raw-stat point values or causal effects. Larger
absolute coefficients imply a larger conditional score change for the same standardized movement.
Worked example using MVP scoring
The revised MVP points coefficient is +1.270822. Suppose, purely for illustration, that the pool average is
12 points per game and its standard deviation is 6. A player scoring 24 points has z = (24 - 12) / 6 = 2. The
scoring term adds 2 x 1.270822 = 2.541645 to the player's score. These pool statistics are hypothetical;
calculations use unrounded coefficients.
Step 3: convert scores into model shares
Share(i) = exp(score(i)) / sum of exp(score(k)) across candidates
This is a softmax calculation. It preserves the score ranking and produces positive shares adding to 100%.
A player's share changes when rivals change. A share of 40% has not been demonstrated to mean a 40%
real-world chance of winning.
Reading negative coefficients
A negative coefficient lowers the fitted score as that input rises, conditional on the other inputs. Lower
defensive rating is desirable, so its negative DPOY coefficient is intuitive. Other negative signs may reflect
overlapping statistics, limited winner samples and model specification. They do not show that worse
efficiency or fewer games causes awards.
For two players, their model-share ratio is exp(score A - score B). A one-standard-deviation scoring
advantage alone gives a revised MVP ratio multiplier of exp(1.270822), about 3.56. This is a model-relative
comparison, not a guaranteed probability increase.
NBA AWARD MODELS | Methodology and coefficient guide 2

## Page 3

03 / Training and recency
What the fitting procedure learns
The feature lists were chosen by the analyst. The coefficients were then learned by minimizing weighted
historical prediction loss. Each season forms one contest, so modern seasons do not receive extra training
weight simply because they have larger rosters. Tied winners split the target outcome equally.
Objective = weighted average of -sum(target share x log(model share)) + (lambda / 2) x
sum(coefficient squared)
The first term rewards assigning share to actual winners. The second is L2 regularization: it discourages
excessively large coefficients and helps limit overfitting. There is no intercept because adding the same
constant to every player's score in a contest cancels in softmax.
How newer seasons receive more weight
Season weight = 2 ^ (-(latest training year - season year) / half-life)
Weights are normalized to sum to one within each training run. This changes how historical outcomes
influence the learned coefficients. It does not discount a current player's statistics or automatically place
more emphasis on recent games within a season.
Model Half-life 10 years older 20 years older Lambda
MVP 20 seasons 70.7% 50.0% 0.03
DPOY 5 seasons 25.0% 6.2% 0.1
ROY 10 seasons 50.0% 25.0% 0.03
SMOY 5 seasons 25.0% 6.2% 0.03
MIP 20 seasons 70.7% 50.0% 0.3
How the settings were selected
Half-lives of 5, 10 and 20 seasons and lambda values of 0.03, 0.1 and 0.3 were compared using rolling
predictions for 2005-06 through 2014-15. The combination with the lowest average log loss was selected
separately for each award. Log loss measures how much share the model assigns to the winner; lower is
better.
For each 2015-16 through 2025-26 prediction, coefficients were fitted using earlier seasons only. The
revised MVP family and settings were selected on the earlier development period, but the later results had
already been inspected during this project, so its improvement is retrospective. Final coefficients on pages
4-8 are refit through 2025-26 and differ from the historical fits.
NBA AWARD MODELS | Methodology and coefficient guide 3

## Page 4

04 / Most Valuable Player
Revised model: combines player production with team wins, league standing and conference standing.
Total WS and VORP are removed. Candidates still need at least 20 games.
Every fitted coefficient
All values below multiply within-season, within-candidate-pool z-scores. A +1 z change adds the signed coefficient to the
score; a -1 z change subtracts it. Values are rounded to six decimals.
Input Coefficient What the input measures
PTS +1.270822 Points scored per game.
AST +0.541459 Assists per game.
TRB +0.211327 Total rebounds per game.
BPM +0.742119 Box plus/minus: box-score estimate of impact per 100 possessions relative to an
average player.
WS/48 +0.703879 Win shares per 48 minutes: a rate measure of estimated contribution.
TS% -0.001005 True shooting percentage: scoring efficiency accounting for two-pointers,
three-pointers and free throws.
G +1.024954 Games played during the season.
Team wins +1.352526 Team regular-season wins. Each player on a known team receives that team's
total.
League standing +1.158667 League position by regular-season win percentage, normalized from 0 (last) to 1
(first). Ties share rank.
Conference
standing
+0.503129 Position within that season's Eastern or Western Conference, normalized from 0
to 1. Ties share rank.
How to interpret the combination
Team wins and both standings measures overlap; their coefficients are conditional score weights, not
independent percentages. A nearly zero negative TS% term does not establish that poor shooting helps.
Standings use regular-season win percentage, average tied ranks and historical conference membership.
Play-in outcomes are excluded. See page 16 for comparisons and source repairs.
Historical test: 8 of 11 winners ranked first; 10 of 11 ranked in the top three. Recency half-life: 20 seasons.
Lambda: 0.03.
NBA AWARD MODELS | Methodology and coefficient guide 4

## Page 5

05 / Defensive Player of the Year
Favors defensive win shares, lower individual defensive rating and a substantial playing role. Candidates
need at least 20 games. Team defensive ranking and tracking defense are absent.
Every fitted coefficient
All values below multiply within-season, within-candidate-pool z-scores. A +1 z change adds the signed coefficient to the
score; a -1 z change subtracts it. Values are rounded to six decimals.
Input Coefficient What the input measures
STL +0.097607 Steals per game.
BLK +0.294052 Blocks per game.
DRB -0.186261 Defensive rebounds per game.
DWS +1.240996 Defensive win shares: the defensive component of estimated win contribution.
DBPM +0.393506 Defensive box plus/minus: box-score estimate of defensive impact per 100
possessions.
DRtg -1.223341 Individual defensive rating: estimated points allowed per 100 possessions; lower
is better.
G -0.172386 Games played during the season.
MPG +0.414545 Minutes per game, calculated as total season minutes divided by games played.
How to interpret the combination
DRtg is an individual box-score estimate, not direct measurement of points conceded by a player. DWS,
DBPM and DRtg can reflect team context and favor what box scores capture. Negative DRB and G
coefficients are conditional on the other inputs; they do not imply rebounds or availability are harmful.
Historical test: 6 of 11 winners ranked first; 8 of 11 ranked in the top three. Recency half-life: 5 seasons.
Lambda: 0.1.
NBA AWARD MODELS | Methodology and coefficient guide 5

## Page 6

06 / Rookie of the Year
Favors scoring and broad box-score production among players in their first recorded NBA season with at
least 20 games. This is a data-based rookie proxy, not a separately verified official eligibility list.
Every fitted coefficient
All values below multiply within-season, within-candidate-pool z-scores. A +1 z change adds the signed coefficient to the
score; a -1 z change subtracts it. Values are rounded to six decimals.
Input Coefficient What the input measures
PTS +2.088508 Points scored per game.
AST +1.057386 Assists per game.
TRB +0.856856 Total rebounds per game.
STL +0.175030 Steals per game.
BLK -0.232121 Blocks per game.
BPM -0.379764 Box plus/minus: box-score estimate of impact per 100 possessions relative to an
average player.
WS +1.128551 Win shares: estimated season-long contribution to team wins.
TS% -0.756536 True shooting percentage: scoring efficiency accounting for two-pointers,
three-pointers and free throws.
G +0.564534 Games played during the season.
How to interpret the combination
The negative TS%, BPM and block terms are conditional fitted relationships after accounting for scoring,
assists, rebounds and win shares. In a small and correlated sample they can produce counterintuitive
signs; they do not establish that poor shooting or defense helps win the award.
Historical test: 7 of 11 winners ranked first; 11 of 11 ranked in the top three. Recency half-life: 10 seasons.
Lambda: 0.03.
NBA AWARD MODELS | Methodology and coefficient guide 6

## Page 7

07 / Sixth Man of the Year
Favors scoring and win shares among bench players. Candidates need at least 20 games and known
games started (GS), with 2 x GS < G. A player starting exactly half their games is excluded.
Every fitted coefficient
All values below multiply within-season, within-candidate-pool z-scores. A +1 z change adds the signed coefficient to the
score; a -1 z change subtracts it. Values are rounded to six decimals.
Input Coefficient What the input measures
PTS +2.442105 Points scored per game.
AST -0.196720 Assists per game.
TRB -0.216726 Total rebounds per game.
BPM +0.021052 Box plus/minus: box-score estimate of impact per 100 possessions relative to an
average player.
WS +1.551453 Win shares: estimated season-long contribution to team wins.
TS% -0.730302 True shooting percentage: scoring efficiency accounting for two-pointers,
three-pointers and free throws.
G +0.582436 Games played during the season.
MPG -0.390955 Minutes per game, calculated as total season minutes divided by games played.
How to interpret the combination
Scoring and win shares dominate the fitted score. Negative efficiency, minutes, assists and rebound
coefficients should not be read as desirable basketball traits. The model describes the joint profile of
historical winners within this candidate pool.
Historical test: 6 of 11 winners ranked first; 8 of 11 ranked in the top three. Recency half-life: 5 seasons.
Lambda: 0.03.
NBA AWARD MODELS | Methodology and coefficient guide 7

## Page 8

08 / Most Improved Player
Combines current performance with growth from the previous recorded NBA season. Candidates need at
least 20 current games and a previous observed points-per-game value. No minimum prior-season games
is imposed.
Every fitted coefficient
All values below multiply within-season, within-candidate-pool z-scores. A +1 z change adds the signed coefficient to the
score; a -1 z change subtracts it. Values are rounded to six decimals.
Input Coefficient What the input measures
PTS +0.490198 Points scored per game.
BPM -0.084982 Box plus/minus: box-score estimate of impact per 100 possessions relative to an
average player.
WS +0.529193 Win shares: estimated season-long contribution to team wins.
Age -0.268630 Player age as recorded in the source file.
experience -0.209871 Elapsed years since the first recorded NBA season, including any gaps.
delta_PTS +1.016606 Change in points per game from the previous recorded NBA season.
delta_AST +0.265161 Change in assists per game from the previous recorded NBA season.
delta_TRB +0.253113 Change in rebounds per game from the previous recorded NBA season.
delta_BPM +0.155679 Change in box plus/minus from the previous recorded NBA season.
delta_PER +0.095627 Change in player efficiency rating, a box-score production measure.
delta_MPG -0.005388 Change in minutes per game from the previous recorded NBA season.
delta_TS% -0.056925 Change in true shooting percentage from the previous recorded NBA season.
delta_USG% +0.449482 Change in usage rate: estimated share of team plays used through shooting, free
throws or turnovers while on court.
How to interpret the combination
Delta means current value minus previous recorded NBA value; a positive delta is an increase. For
returnees after a gap, this is not necessarily a comparison with the immediately preceding calendar season.
Usage growth can capture a larger role without proving improved skill. Tiny delta_MPG and delta_TS%
terms contribute little per standardized movement.
Historical test: 2 of 11 winners ranked first; 7 of 11 ranked in the top three. Recency half-life: 20 seasons.
Lambda: 0.3.
Use with caution: first-place accuracy was only 18%. This model needs richer career context and more flexible relationships
before its top pick is dependable.
NBA AWARD MODELS | Methodology and coefficient guide 8

## Page 9

09 / Historical validation
The test contains 11 seasons, from 2015-16 through 2025-26. Each was predicted using coefficients fitted
to earlier seasons only. Top-one accuracy counts first-ranked winners; top-three accuracy counts winners
ranked anywhere in the first three.
Award Winner first Winner top 3 Equal-weight first** Log loss*
MVP 8/11 (73%) 10/11 (91%) Not evaluated 0.973
DPOY 6/11 (55%) 8/11 (73%) 4/11 (36%) 1.813
ROY 7/11 (64%) 11/11 (100%) 8/11 (73%) 0.697
SMOY 6/11 (55%) 8/11 (73%) 5/11 (45%) 1.571
MIP 2/11 (18%) 7/11 (64%) 2/11 (18%) 2.591
*Mean test log loss for the recency model. Lower is better. Candidate pools differ by award, so comparisons across awards
are affected by contest difficulty and pool size.
**The revised MVP has no equal-weight comparison yet. Other awards use their original same-feature equal-weight baselines.
Across current models: 29 correct / 26 incorrect first picks.
What recency changed
In the original versions, recency weighting improved DPOY from four to six winners and Sixth Man from five
to six. MIP stayed at two and Rookie dropped from eight to seven. The revised MVP improves from five to
eight through feature changes; that gain cannot be attributed to recency weighting alone.
What the comparison controls
For the four unchanged awards, equal-weight baselines use the same features and selected regularization
while replacing decaying season weights with approximately equal weights. The MVP revision comparison
on page 16 instead changes features and retunes settings; it does not isolate a single input's causal effect.
What the test does not establish
Eleven seasons is a small sample: one winner changes accuracy by about nine percentage points. MVP
revisions were designed after inspecting these seasons, so their improvements are retrospective. These
results are exploratory historical evidence, not fresh external validation or a guarantee of future
performance.
The inputs are complete-season statistics. Results do not measure performance with December statistics,
partial seasons or projected future games. A realistic in-season model would need historical snapshots at
comparable dates.
Calibration is also untested. High shortlist accuracy does not make the softmax shares calibrated
probabilities. The saved full-history coefficients must not be used to claim historical out-of-sample
performance; use the expanding-window backtest records for that purpose.
NBA AWARD MODELS | Methodology and coefficient guide 9

## Page 10

10 / Data and practical use
Data preparation and eligibility
PlayerID plus Season is unique in the selected CSV. Traded-player records were not summed; some team
labels denote multiple teams. MP is total minutes, so minutes per game is MP/G. Corrupted character
encoding in names was repaired in memory, then accents and punctuation normalized for winner matching.
Every winner in each modeled season was required to appear in the candidate pool.
The 20-game minimum is an analyst screening rule. Official award-specific games/minutes requirements,
exceptions and appeals are not fully implemented. Current eligibility needs a separate check before treating
a ranking as an actionable forecast.
Main limitations
MVP now includes team wins and league/conference standing. Team defensive ranking, tracking defense,
injuries, reputation, voting narratives, prior award voting and market odds remain absent. Correlated inputs
can produce unintuitive coefficients. There are no missing-value indicator features; median imputation
assigns neutral within-pool values without identifying missingness.
Using the models on another season
Apply the same candidate filters and calculate every feature with the same units. Calculate pool medians,
means and population standard deviations for that season, then standardize. If a feature is constant, the
implementation uses a standard deviation of one. Multiply by the saved coefficients, add the terms and
apply stable softmax. Rank shares from highest to lowest. New-season ranking accuracy remains
unproven until evaluated.
Sources and model files
Primary statistics: basketball_stats.csv, Basketball/Data copy. Source SHA-256:
a2c34a0c1e60a137b59f70d5701740d3
62d974f3a9f0bba23becec65007826b6
Historical labels: award-winners.ts in the existing nba-story-lab project. Its header attributes the snapshot to Basketball
Reference, transcribed 2026-09-01. Winner joins and candidate coverage were checked; all labels were not independently
audited against external records.
Reference pages: basketball-reference.com/awards/mvp.html; /dpoy.html; /roy.html; /smoy.html; /mip.html. Official
award-history index: nba.com/news/history-all-time-awards. These references describe source provenance; this document
does not claim a new source audit.
Current MVP: improve_mvp_conference.py and mvp_conference_revision/model.json hold the revised fit and settings.
conference_standings/prepare_standings.py creates the derived ranks from cached ESPN responses; sources.json records
provenance and repairs (page 16). Other awards retain model.py, models.json and the original backtests. award_labels.json
stores the shared winner labels.
NBA AWARD MODELS | Methodology and coefficient guide 10

## Page 11

11 / Most Valuable Player results
8 correct / 3 incorrect. These are the recency-weighted model results for all 11 test seasons. Each pick
was made using earlier seasons only.
Correct means the first-ranked player matched the recorded winner. Winner rank is where the actual winner appeared in the
model ranking; a second- or third-ranked winner still counts as an incorrect first pick.
Season Model pick Actual winner Result Winner
rank
2015-16 Stephen Curry Stephen Curry Correct 1
2016-17 James Harden Russell Westbrook Incorrect 4
2017-18 James Harden James Harden Correct 1
2018-19 Giannis Antetokounmpo Giannis Antetokounmpo Correct 1
2019-20 Giannis Antetokounmpo Giannis Antetokounmpo Correct 1
2020-21 Nikola Jokić Nikola Jokić Correct 1
2021-22 Nikola Jokić Nikola Jokić Correct 1
2022-23 Nikola Jokić Joel Embiid Incorrect 3
2023-24 Nikola Jokić Nikola Jokić Correct 1
2024-25 Shai Gilgeous-Alexander Shai Gilgeous-Alexander Correct 1
2025-26 Nikola Jokić Shai Gilgeous-Alexander Incorrect 2
Current version: revised MVP with team wins, league standing and conference standing. The original achieved 5/11; this
version achieves 8/11. Revisions are retrospective comparisons. Page 16 explains the standings and model progression.
NBA AWARD MODELS | Methodology and coefficient guide 11

## Page 12

12 / Defensive Player of the Year
results
6 correct / 5 incorrect. These are the recency-weighted model results for all 11 test seasons. Each pick
was made using earlier seasons only.
Correct means the first-ranked player matched the recorded winner. Winner rank is where the actual winner appeared in the
model ranking; a second- or third-ranked winner still counts as an incorrect first pick.
Season Model pick Actual winner Result Winner
rank
2015-16 Paul Millsap Kawhi Leonard Incorrect 3
2016-17 Draymond Green Draymond Green Correct 1
2017-18 Andre Drummond Rudy Gobert Incorrect 4
2018-19 Giannis Antetokounmpo Rudy Gobert Incorrect 2
2019-20 Giannis Antetokounmpo Giannis Antetokounmpo Correct 1
2020-21 Rudy Gobert Rudy Gobert Correct 1
2021-22 Nikola Jokić Marcus Smart Incorrect 16
2022-23 Jaren Jackson Jr. Jaren Jackson Jr. Correct 1
2023-24 Rudy Gobert Rudy Gobert Correct 1
2024-25 Shai Gilgeous-Alexander Evan Mobley Incorrect 16
2025-26 Victor Wembanyama Victor Wembanyama Correct 1
Original model version, retained for this award. Results use the recorded winner labels on page 10. Equal-weight comparison
picks are excluded here; aggregate comparisons appear on page 9.
NBA AWARD MODELS | Methodology and coefficient guide 12

## Page 13

13 / Rookie of the Year results
7 correct / 4 incorrect. These are the recency-weighted model results for all 11 test seasons. Each pick
was made using earlier seasons only.
Correct means the first-ranked player matched the recorded winner. Winner rank is where the actual winner appeared in the
model ranking; a second- or third-ranked winner still counts as an incorrect first pick.
Season Model pick Actual winner Result Winner
rank
2015-16 Karl-Anthony Towns Karl-Anthony Towns Correct 1
2016-17 Joel Embiid Malcolm Brogdon Incorrect 2
2017-18 Ben Simmons Ben Simmons Correct 1
2018-19 Trae Young Luka Dončić Incorrect 2
2019-20 Ja Morant Ja Morant Correct 1
2020-21 LaMelo Ball LaMelo Ball Correct 1
2021-22 Scottie Barnes Scottie Barnes Correct 1
2022-23 Paolo Banchero Paolo Banchero Correct 1
2023-24 Chet Holmgren Victor Wembanyama Incorrect 2
2024-25 Stephon Castle Stephon Castle Correct 1
2025-26 Kon Knueppel Cooper Flagg Incorrect 2
Original model version, retained for this award. Results use the recorded winner labels on page 10. Equal-weight comparison
picks are excluded here; aggregate comparisons appear on page 9.
NBA AWARD MODELS | Methodology and coefficient guide 13

## Page 14

14 / Sixth Man of the Year results
6 correct / 5 incorrect. These are the recency-weighted model results for all 11 test seasons. Each pick
was made using earlier seasons only.
Correct means the first-ranked player matched the recorded winner. Winner rank is where the actual winner appeared in the
model ranking; a second- or third-ranked winner still counts as an incorrect first pick.
Season Model pick Actual winner Result Winner
rank
2015-16 Ryan Anderson Jamal Crawford Incorrect 6
2016-17 Lou Williams Eric Gordon Incorrect 2
2017-18 Lou Williams Lou Williams Correct 1
2018-19 Lou Williams Lou Williams Correct 1
2019-20 Montrezl Harrell Montrezl Harrell Correct 1
2020-21 Jordan Clarkson Jordan Clarkson Correct 1
2021-22 Tyler Herro Tyler Herro Correct 1
2022-23 Immanuel Quickley Malcolm Brogdon Incorrect 5
2023-24 Bogdan Bogdanović Naz Reid Incorrect 6
2024-25 Payton Pritchard Payton Pritchard Correct 1
2025-26 Reed Sheppard Keldon Johnson Incorrect 2
Original model version, retained for this award. Results use the recorded winner labels on page 10. Equal-weight comparison
picks are excluded here; aggregate comparisons appear on page 9.
NBA AWARD MODELS | Methodology and coefficient guide 14

## Page 15

15 / Most Improved Player results
2 correct / 9 incorrect. These are the recency-weighted model results for all 11 test seasons. Each pick
was made using earlier seasons only.
Correct means the first-ranked player matched the recorded winner. Winner rank is where the actual winner appeared in the
model ranking; a second- or third-ranked winner still counts as an incorrect first pick.
Season Model pick Actual winner Result Winner
rank
2015-16 Paul George CJ McCollum Incorrect 2
2016-17 Russell Westbrook Giannis Antetokounmpo Incorrect 4
2017-18 Kris Dunn Victor Oladipo Incorrect 2
2018-19 Pascal Siakam Pascal Siakam Correct 1
2019-20 Devonte' Graham Brandon Ingram Incorrect 10
2020-21 Nikola Jokić Julius Randle Incorrect 7
2021-22 Desmond Bane Ja Morant Incorrect 2
2022-23 Lauri Markkanen Lauri Markkanen Correct 1
2023-24 Jalen Johnson Tyrese Maxey Incorrect 5
2024-25 Ty Jerome Dyson Daniels Incorrect 2
2025-26 Ryan Rollins Nickeil Alexander-Walker Incorrect 2
Original model version, retained for this award. Results use the recorded winner labels on page 10. Equal-weight comparison
picks are excluded here; aggregate comparisons appear on page 9.
NBA AWARD MODELS | Methodology and coefficient guide 15

## Page 16

16 / MVP revision and standings
The MVP model now includes team wins plus league and conference standing, retaining WS/48 and games
played while removing total WS and VORP. The other four award models retain their original versions.
MVP version Winner first Winner top 3 Mean log loss
Original 5/11 11/11 1.135
Team wins + league standing 7/11 10/11 0.876
Plus conference standing (current) 8/11 10/11 0.973
The current model fixes Giannis in 2018-19, Giannis in 2019-20 and Shai in 2024-25 relative to the original.
It still misses Westbrook in 2016-17, Embiid in 2022-23 and Shai in 2025-26. Its log loss worsens versus
the first team-context revision despite improving first picks. Lower log loss is better.
How conference standing is calculated
ESPN historical feeds supply conference membership and team records for all 41 modeled seasons (1,177
team-seasons). Rank teams by regular-season W/(W+L) within their own conference. Tied records share
their average rank. Normalize as 1 - (rank - 1)/(number of teams - 1). First place is 1 and last place 0,
before candidate-pool standardization.
League standing uses the same method across all teams. These are record-based positions, not official
tiebreak-resolved ranks. Playoff-seed fields are excluded because play-in outcomes and historical division
rules can alter them. Multi-team player rows receive candidate-pool median team inputs; every actual MVP
has a known team and conference.
Selection and source checks
The lean model with both standings measures won the earlier 2005-06 through 2014-15 development
comparison. Each later prediction trains only on prior seasons, but those later outcomes had already been
inspected, so the revision is retrospective. The selected recency half-life remains 20; lambda changes from
0.1 originally to 0.03.
Raw ESPN responses are preserved. The 1999-00 feed is incomplete: derived records use final wins from the existing cache
and an 82-game schedule. Dallas 1993-94 and Denver 1997-98 each have an extra loss in the feed; corrected to 13-69 and
11-71. All derived seasons reconcile total league wins to losses. Historical conference switches were checked.
Sources: ESPN standings feed,
site.web.api.espn.com/apis/v2/sports/basketball/nba/standings?season=2025&type=0&level=2 (season is the ending year).
Repairs: basketball-reference.com/leagues/NBA_2000_standings.html; /teams/DAL/1994.html; /teams/DEN/1998.html. Final
1999-00 records were also spot-checked against NBA historical material; the full 29-team table was not independently
re-audited. Exact repairs and hashes are in conference_standings/sources.json.
NBA AWARD MODELS | Methodology and coefficient guide 16

