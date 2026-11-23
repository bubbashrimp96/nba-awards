# MIP: preseason expected PTS/REB/AST vs actual (all sourced seasons)

Research date 2026-11-23. Exploratory only; the active MIP model and app are unchanged.

## Data

Preseason per-game projections, every snapshot dated before opening night unless noted. Where several
sources cover a player-season, the expected line is their average (`consensus_forecasts.csv`).

| Seasons | Sources |
|---|---|
| 2008-09 to 2014-15 | ESPN fantasy projections (Wayback), Razzball top 155-210 (2010-11 onward) |
| 2015-16 to 2022-23 | Razzball, Hashtag Basketball (Wayback), ESPN fantasy API (2017-18 onward), FantasyPros (2019-20) |
| 2023-24 to 2026-27 | ESPN fantasy API (frozen season projection), Hashtag Basketball |
| 2000-01 to 2007-08 | none found: ESPN's pages from those years show last season's actuals; Rotowire was paywalled |

Raw pages/JSON are in `../raw_sources/`, parsed rows in `../sourced/*.csv`, coverage in `coverage_by_source.csv`.

Coverage of the 13+ PPG MIP pool is 90-100% in 17 of 18 seasons. 2019-20 is filled by FantasyPros consensus
projections (Wayback 2019-10-14, season totals ÷ projected games; Ingram 16.5 PPG expected). One gap remains:
- 2013-14: only 15 ESPN players archived; no Razzball, Hashtag or FantasyPros projections; numberFire was premium-only;
  CBS archived only its centres page. Winner Goran Dragić is not covered.

Caveats: 2011-12 Razzball snapshots are about two weeks after opening night; the 2018-19 Razzball table is a
post-season copy of a preseason article; ESPN API values were pulled today but are stored as frozen preseason
projections; Razzball 2010-11 Dwyane Wade REB typo (23) blanked.

## Result

New features = actual per-game stat − preseason expectation, z-scored within each season's pool. Each season
is predicted from a model refit only on earlier seasons (active half-life, L2, availability and 13 PPG rule).
Full pool = all 13+ PPG candidates; players without a forecast get a neutral 0.

| Variant (full pool, 15 seasons with 3+ prior forecast seasons) | Winner 1st | Winner top 3 | Mean winner rank | Log loss |
|---|---:|---:|---:|---:|
| Baseline (active model) | 4 | 9 | 4.00 | 2.013 |
| **+ points above expectation** | **6** | 9 | 3.73 | **1.908** |
| + points, rebounds, assists above expectation | 6 | 9 | 3.80 | 1.929 |
| Replace last-year deltas with expectation deltas | 7 | 9 | 3.07 | 1.902 |

Over all 18 seasons, adding points above expectation improves log loss in 11 seasons and worsens it in 6
(mean −0.095; bootstrap probability of no improvement ≈ 0.10). Rebounds and assists add nothing
(the AST weight fits to ~0). Wins: Butler 2015 2→1, Alexander-Walker 2026 2→1, Daniels 2025 4→2,
Randle 2021 3→2. Losses: Maxey 2024 2→5 (his line was already expected to be big), Love 2011 6→7.

Every covered winner sits in the top 19% of his pool for points above expectation, and in the top 6% in
13 of 17 seasons. The model gain is smaller than that because the existing "change vs last season" inputs
already capture much of it.

## Takeaway

Points above preseason expectation is a real, consistently directional signal and the only one of the three
worth adding. The evidence is promising but not conclusive (17 covered seasons, one coverage gap, mixed sources).
For a production change: add `surprise_PTS` alongside the existing deltas, fill 2013-14 if a source turns up,
and feed the current season from the ESPN API preseason projection.

Run: `.venv/bin/python experiments/mip_expectations/run_all.py` (from `nba-award-models/`).

Note (2026-11-23): `surprise_PTS` is now in the production MIP model, so `features_for("MIP")` already includes it.
Re-running `run_all.py` therefore compares against a baseline that has the feature; the tables above are the pre-adoption results.
