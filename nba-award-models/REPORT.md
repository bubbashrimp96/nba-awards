# NBA award models

Built from `Documents/Claude/Basketball/Data/basketball_stats.csv` (25,312 player-seasons, 1949–50 through 2025–26). The original file is unchanged. Four copies were found; the Basketball/Data and Backup copies match, while the two lab copies differ. This analysis uses Basketball/Data consistently.

## Results on unseen seasons

Each of the 11 seasons from 2015–16 through 2025–26 was predicted using earlier seasons only. Feature and model-family choices are analyst choices, so these are exploratory historical results, not a final external validation.

| Award | Correct winner | Winner in top 3 | Equal-weight correct winner | Half-life |
|---|---:|---:|---:|---:|
| MVP | 5/11 (45%) | 11/11 (100%) | 5/11 (45%) | 20 seasons |
| DPOY | 6/11 (55%) | 8/11 (73%) | 4/11 (36%) | 5 seasons |
| ROY | 7/11 (64%) | 11/11 (100%) | 8/11 (73%) | 10 seasons |
| SMOY | 6/11 (55%) | 8/11 (73%) | 5/11 (45%) | 5 seasons |
| MIP | 2/11 (18%) | 7/11 (64%) | 2/11 (18%) | 20 seasons |

MIP is a weak winner predictor in this test. MVP and ROY work better as shortlists. DPOY and Sixth Man benefit most in winner accuracy from recency weighting. Eleven test seasons is a small sample, so differences of one or two winners are uncertain.

## Model and recent-season weights

Each award uses a separate L2-regularized conditional logistic model. For player i in season t:

`score(i,t) = sum(coefficient[j] * z_score(i,t,j))`

`model_share(i,t) = exp(score(i,t)) / sum(exp(score(k,t)))`

The denominator includes the eligible candidate pool for that award and season. Use stable softmax in computation. Shares sum to one but have not been calibrated as real-world winning probabilities.

`season_weight(t) = 2 ** (-(latest_training_year - t) / half_life)`

A season one half-life old has 50% of the latest season’s training weight; two half-lives old has 25%. Weights are normalized across training seasons. Each season contributes one target outcome, so larger modern rosters do not automatically give a season more training weight. Tied winners share target mass.

Training starts in 1985–86, when all five awards exist. Half-lives 5, 10 and 20 and regularization strengths 0.03, 0.1 and 0.3 were compared on rolling predictions for 2005–06 through 2014–15, using mean log loss. Those choices were frozen for the 2015–16 through 2025–26 tests. The equal-weight baseline uses the same selected regularization, isolating the weighting change; it was not independently optimized. Final saved coefficients are refit through 2025–26 and must not be used to reproduce historical out-of-sample results.

## Inputs and fitted coefficients

All features are standardized within each season and award candidate pool, using population standard deviation. Missing inputs receive that season’s candidate-pool median before standardization. A positive coefficient increases the score holding other inputs fixed. Correlated inputs mean these coefficients are not causal effects or percentages of importance. Exact coefficients are in coefficients.csv and models.json.

### MVP

PTS: +0.537, AST: +0.184, TRB: -0.027, BPM: +0.384, WS: +0.723, WS/48: +0.932, VORP: +0.149, TS%: +0.088, G: +0.252

### DPOY

STL: +0.098, BLK: +0.294, DRB: -0.186, DWS: +1.241, DBPM: +0.394, DRtg: -1.223, G: -0.172, MPG: +0.415

### ROY

PTS: +2.089, AST: +1.057, TRB: +0.857, STL: +0.175, BLK: -0.232, BPM: -0.380, WS: +1.129, TS%: -0.757, G: +0.565

### SMOY

PTS: +2.442, AST: -0.197, TRB: -0.217, BPM: +0.021, WS: +1.551, TS%: -0.730, G: +0.582, MPG: -0.391

### MIP

PTS: +0.490, BPM: -0.085, WS: +0.529, Age: -0.269, experience: -0.210, delta_PTS: +1.017, delta_AST: +0.265, delta_TRB: +0.253, delta_BPM: +0.156, delta_PER: +0.096, delta_MPG: -0.005, delta_TS%: -0.057, delta_USG%: +0.449

## Candidate rules and data handling

- All award pools require at least 20 games as an analyst screening rule. This is not an official eligibility rule.
- ROY: first recorded NBA season for that PlayerID. The file starts decades before the training window. Official rookie eligibility is not separately verified.
- Sixth Man: games started must be available and strictly fewer than half of games played.
- MIP: requires a previous recorded NBA season. Deltas compare with the previous recorded NBA season, which can precede a gap outside the NBA. No minimum previous-season games is imposed. Experience is elapsed years since the first recorded season.
- MP is total season minutes. MPG = MP/G. PTS, AST, TRB, STL, BLK and DRB are per game as supplied.
- PlayerID/Season is unique, so no traded-player rows are summed or double-counted. Some team identifiers are aggregate multi-team labels.
- Mojibake in names is repaired in memory and accents/punctuation normalized for award joins. All award winners in every training/evaluation pool are required to match; execution fails on a missing winner.

## Limits and improvements

These are end-of-season statistics models. They do not establish how well an early-season forecast will work. Team wins, team defensive ranking, tracking defense, injuries, narratives, prior award voting and market odds are absent. Modern official games/minutes eligibility, appeals and exceptions are not enforced; games alone cannot resolve all cases. These omissions particularly affect MVP and DPOY. MIP needs richer prior-career context and non-linear development signals before relying on its first-ranked player.

Historical award labels come from the existing local `nba-story-lab/src/data/award-winners.ts`, whose header attributes them to Basketball Reference, transcribed 2026-09-01. They were joined and checked for candidate coverage, not independently re-audited winner by winner. NBA’s official award-history index is available at https://www.nba.com/news/history-all-time-awards .

## Files and reproduction

- model.py: full preparation, fitting, tuning and expanding-window evaluation. Run `python3 model.py` with numpy, pandas and scipy installed.
- models.json: final feature lists, coefficients, recency settings and source SHA-256.
- historical_backtests.csv: each held-out season’s prediction, actual winner and winner rank, for recency and equal weighting.
- validation_summary.csv: aggregated test results and log loss.
- development_grid.csv: all tuning results from the development period.
- coefficients.csv: final coefficients in a readable table.
- award_labels.json: local label snapshot used by the run.
