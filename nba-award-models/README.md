# NBA Award Models

Five end-of-season NBA award ranking models, historical backtests, experiments, and a browser dashboard.

Current dashboard: **2000–01 through 2025–26**, with 26 seasons for each award. Active model files and the current report are in [`revised_awards/`](revised_awards/REPORT.md). Earlier figures below describe prior snapshots.

## Explore

Open `output/artifacts/nba-award-models-browser.html` in your browser. It includes award coefficients, historical picks and the full 16-page methodology guide.

The original PDF is `output/pdf/nba_award_models_explained.pdf`.

## Run

```sh
cd nba-award-models
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 model.py
python3 improve_mvp_conference.py
```

`model.py` fits the original five models. `improve_mvp_conference.py` fits the current MVP revision with team wins and league/conference standings. Other revision scripts and their saved results are included for comparison. Source statistics and cached team wins are in `data/`.

## Interpretation

The guide reports first-pick accuracy of MVP 7/11 (current PER replacement; original guide: 8/11), DPOY 6/11, ROY 7/11, Sixth Man 6/11, and MIP 2/11 across 2015–16 to 2025–26. MVP changes are retrospective; model shares are uncalibrated. Inputs use complete-season statistics and screening rules do not fully implement official award eligibility.

See `REPORT.md`, the PDF and revision reports for methodology, provenance and limitations. Temporary PDF preview images are excluded.

The award explorer has five keyboard-accessible award tabs, with all eleven seasons showing the model top three (model share scores) alongside the actual top three (voting points). Voting results and source URLs are cached in `data/award_voting/`; tied third places are retained. Direct links use fragments such as `#award-DPOY`.

Run `python3 build_dashboard_data.py` to rebuild the dashboard's embedded comparison data from the cached voting results and historical model fits. MVP keeps its saved PER-replacement top-three shares and refits that model to recover full historical ranks; all awards fit only prior seasons using saved model settings. The dashboard works directly from a local file, without a server.

The sidebar separates Summary, Model vs Actual, Methodology, and Sources & Notes into distinct views, with browser back/forward support. Results default to the latest season; the season buttons also support all seasons. Shareable links use `#results/MVP/2025-26` (older `#award-MVP` links remain supported).

Each comparison includes compact input tables with players as rows and model inputs as columns, using smaller text and wrapped headers to fit without horizontal scrolling for the union of both top threes. It shows model/actual ranks, team, all award model features, and candidate-pool eligibility. Values are before standardization; missing values use the model's season candidate-pool median and are marked. Percentage changes are shown in percentage points. MVP tables display record-based league/conference positions (average ranks for ties); the model continues to use normalized 0–1 standings internally.

Player tables show full model ranks and full award voting ranks, including finishes outside the top three. Players without award votes show “No votes”; players excluded from the model candidate pool show “Not eligible”. Run `python3 fetch_award_voting.py` to refresh the full cached voting tables (requires network access).

The active app MVP model is `mvp_per_replacement/model.json`, replacing BPM with PER. Run `python3 replace_mvp_bpm_with_per.py` followed by `python3 build_dashboard_data.py` to regenerate it. Historical results: 7/11 first picks correct, 10/11 top-three winners, mean log loss 0.964304. The original PDF and its embedded guide remain the earlier BPM snapshot, explicitly labeled in the app.

The active MVP model now adds the 85% availability penalty in `mvp_per_availability/`. Run `python3 add_mvp_availability.py` then `python3 build_dashboard_data.py`. All PER-model features including G are retained; games below ceil(85% of actual team games) incur a strictly negative fitted score contribution per game. Multi-team schedule approximations are flagged. Current MVP results: 9/11 first picks, 10/11 top-three winners, log loss 1.001177; prior PER version: 7/11, 10/11, 0.964304.

The current dashboard covers **2010–11 through 2025–26** for all five awards: 16 seasons and 80 comparisons. Summary totals are regenerated from the same predictions used by the results pages (`dashboard_backtests.csv` and `dashboard_summary.json`). Current first-pick counts: MVP 13/16, ROY 12/16, DPOY 8/16, MIP 2/16, 6MOY 10/16; total 45/80. The earlier 11-season figures above describe previous snapshots.

Refresh missing voting caches with `python3 fetch_award_voting.py`, then run `python3 add_mvp_availability.py` and `python3 build_dashboard_data.py`. Each season fits only on prior seasons, using the existing saved settings. The added 2010–11 through 2014–15 years overlap the original development period used to select those settings and must not be presented as untouched testing. The original embedded guide remains explicitly labeled as an older snapshot.

The active MVP model now includes team performance against preseason expectations (`mvp_expectations_revision/model.json`). `wins_above_expectation` is actual wins minus the preseason market win total scaled to actual team games. Only this difference is a new fitted feature; its coefficient is constrained nonnegative. Expected wins and the difference appear in the player stats table with per-season source links. PER, the 85% availability penalty, other inputs, half-life and regularization are retained.

Source win totals are cached from Basketball Reference for 2002–03 through 2025–26, with raw pages and hashes. Earlier training seasons have a neutral zero expectation feature; multi-team rows use eligible-pool median imputation. Uneven schedules use preseason expected win rate multiplied by actual team games. In 2016–17, OKC's line was 45 wins and actual wins were 47 (+2), so this feature alone does not explain Westbrook's award.

Run `python3 fetch_preseason_wins.py`, `python3 add_mvp_expectations.py`, then `python3 build_dashboard_data.py`. Run `python3 test_mvp_expectations.py` for regression checks. Current MVP results: 13/16 correct first picks, 15/16 winners in the top three, mean log loss 0.790687 (prior availability model: 13/16, 15/16, 0.802573). The new feature fixes 2010–11 and loses 2025–26. Results remain retrospective.

The active MVP model is now `mvp_top5_rank_penalties/model.json`. Candidates must qualify for both PPG and WS/48 leaderboards. Two additional unstandardized, uncentered inputs are `max(0, qualified PPG rank - 5)` and `max(0, qualified WS/48 rank - 5)`; each has its own strictly negative fitted slope. Thus positions 1–5 have no rank penalty, sixth has one unit, seventh two units, and the two penalties add together. All prior model features, preseason expectations, availability rules and training settings remain; coefficients are refitted on the newly qualified candidate pool.

`fetch_qualified_ranks.py` caches source qualification flags and full-precision sorting values where downloads are available. Basketball Reference imposed a one-hour rate limit during retrieval, so the current `--offline` build reconstructs uncached seasons using its documented season-specific qualification requirements and existing local data. PPG uses total points / games; local WS/48 is rounded, so rounded ties share the best competition rank. Exact website rankings can differ when hidden WS/48 precision breaks a tie. Source methods are recorded in `data/qualified_ranks/sources.json` and every qualified-rank row. Shortened seasons and multi-team schedule fallbacks are handled explicitly. Cached source pages are compressed with gzip.

Run `python3 fetch_qualified_ranks.py --offline`, `python3 add_mvp_rank_penalties.py`, then `python3 build_dashboard_data.py`. After the source's requested pause, `python3 fetch_qualified_ranks.py` can refresh missing exact source inputs, followed by the two model/dashboard rebuild commands. The downloader respects Retry-After and stops on waits over 60 seconds. Run `python3 test_mvp_rank_penalties.py` for qualification, ties, penalty counts/slopes, exclusions, historical cutoffs and displayed-value checks.

Current MVP results remain 13/16 first picks and 15/16 top-three winners; mean log loss rises from 0.790687 to 0.843654. The full-history PPG penalty is -0.057497 score units per place below fifth; WS/48 is -0.059978. Historical seasons use their own prior-season fitted slopes. Results remain retrospective, and changing the qualification pool and adding both penalties together does not isolate their individual effects.

All five active award models now apply the below-85% availability penalty. ROY, DPOY, MIP and 6MOY models are saved in `all_awards_availability/models.json`; MVP remains `mvp_top5_rank_penalties/model.json`. Each award learns a strictly negative coefficient per raw game below `ceil(0.85 * actual team season games)`. The contribution is exactly zero at/above the threshold. Known teams use actual regular-season games; multi-team rows use a flagged season-maximum schedule approximation. Existing award-specific features, candidate pools, half-lives and regularization remain; all non-MVP coefficients are refit. MIP gains the shortfall penalty without adding a separate G coefficient; G is displayed as context.

Run `python3 add_award_availability.py` then `python3 build_dashboard_data.py`. All award pages show availability shortfalls and per-player deductions. Updated first-pick totals for 2010–11 through 2025–26: MVP 13/16 (unchanged), ROY 15/16 (was 12), DPOY 8/16 (unchanged), MIP 4/16 (was 2), 6MOY 10/16 (unchanged); combined 50/80. DPOY and 6MOY log loss worsen, so this does not improve every metric. All fits use prior seasons; results remain retrospective.

Run `python3 -m unittest test_award_availability test_mvp_rank_penalties test_mvp_expectations` for availability thresholds, shortfall units, negative historical slopes, preserved baseline reproduction, qualification, score deductions, displayed values and summary reconciliation.

All five active models now use **exponential availability** in `exponential_availability/models.json`. It replaces the linear penalty. Let `d = max(0, ceil(0.85 * team_games) - G)` and `r = log(2)/(0.10 * team_games)`. The uncentered availability feature is `expm1(r*d)/r`, multiplied by each award's strictly negative fitted coefficient. It is zero at/above threshold, and marginal cost doubles each additional 10% of the season missed. This growth rate is a fixed modeling choice, not selected against Embiid or later outcomes. Penalty strength is fitted using prior seasons; other weights are refitted with the same features/settings and candidate rules. No new below-50% exclusion is imposed. MVP PPG/WS48 rank penalties remain linear.

Run `python3 add_exponential_availability.py` then `python3 build_dashboard_data.py`. Earlier linear models remain available for comparison. Raw games below threshold remain visible in the player table; the app shows the exponential deductions and formula. For 2016–17 ROY, Embiid (31/82 games) receives -7.918637 score units instead of -3.118572, falls to fourth, and Brogdon ranks first. Current historical counts are MVP 13/16, ROY 16/16, DPOY 8/16, MIP 4/16, 6MOY 10/16: total 51/80. ROY log loss improves from 0.345610 to 0.245845; the other awards' log loss worsens slightly. Results remain retrospective and do not establish future accuracy.

Run `python3 -m unittest test_exponential_availability test_award_availability test_mvp_rank_penalties test_mvp_expectations` to verify curvature, schedule scaling, raw design values, prior-only fitting, penalties, qualifications, active display values and preserved historical baselines.

The active MVP override is now `mvp_exponential_rank_penalties/model.json`. PPG and WS/48 rank penalties also use the exponential form: `d=max(0, qualified_rank-5)`, `r=ln(2)/(0.10*qualified_leaderboard_count)`, and a strictly negative fitted weight times `expm1(r*d)/r`. Each leaderboard uses its own full qualified field size, before other MVP screening. There is no penalty through fifth, and marginal cost doubles for every additional 10% of that qualified field below fifth. Curvature is fixed in advance rather than tuned to historical winners. Existing exponential availability, candidate rules, expectations and model settings remain; MVP coefficients are refitted using prior seasons. Other award models are unchanged.

Run `python3 add_mvp_exponential_rank_penalties.py` then `python3 build_dashboard_data.py`. MVP remains 13/16 first picks and 15/16 top-three winners; log loss improves from 0.868744 to 0.853947. The app hides both rank-penalty feature columns as requested, and PPG qualified rank plus WS/48 qualified rank are the two far-right player-table columns. Displayed score deductions use each season's fitted exponential weights.

Run `python3 -m unittest test_mvp_exponential_ranks test_exponential_availability test_award_availability test_mvp_rank_penalties test_mvp_expectations` for the complete current regression suite. Earlier model snapshots and reports remain available for comparisons; historical results remain retrospective.


The active build is now `revised_awards/models.json`. Run `python3 fetch_award_voting.py` to populate missing voting caches; run `python3 fetch_team_defense.py` (requires pyarrow) to refresh team ratings; then run `python3 build_revised_awards.py` and `python3 build_dashboard_data.py`. The app includes 130 comparisons across 2000–01 to 2025–26, complete model and voting ranks, source links, model-input tables, and the existing sidebar/award/season navigation.

Availability now uses `(expm1(r*d)-r*d)/r`, where `d=max(0, ceil(0.85*S)-G)` and `r=ln(2)/(0.10*S)`. Removing the linear component gives a gentle start for small shortfalls while retaining exponential growth for larger absences. MVP PPG rank curvature doubles its marginal cost over 5% of its qualified field (previously 10%); WS/48 remains at 10%. Each strength and other model coefficients are refitted using prior seasons. In 2022–23, Embiid is now third and Sabonis fourth; Embiid's availability deduction is -0.342724, previously -3.752039. Brogdon remains first for 2016–17 ROY and Embiid's large absence is still penalized severely.

DPOY removes player `DRB` and adds `team_defensive_rank` (negative fitted coefficient) and `team_wins` (nonnegative fitted coefficient). Team defensive ratings come from NBA **Regular Season / Advanced** team data for 1996–97 onward, cached through sportsdataverse's published NBA Stats archive. Pre-1997 training ratings use a historical Basketball Reference team archive. All 1,177 source records reconcile exactly to cached regular-season wins/losses. Team defensive rank is distinct from player DRtg. There is no top-five team eligibility cutoff.

Sixth Man adds `conference_seed` with a negative fitted coefficient. This uses the reported seed in the existing ESPN standings cache. Missing/zero reported seeds, and the incomplete 1999–00 feed, fall back to record-based conference rank and are flagged. There is no top-four eligibility cutoff. Multi-team team-context inputs use season candidate-pool medians, and schedule approximations remain flagged.

Current 26-season first-pick counts: MVP 17/26, ROY 24/26, DPOY 15/26, MIP 8/26, Sixth Man 17/26 (81/130 combined). Against the preceding rules on the same 26 seasons, Sixth Man rises from 14/26 to 17/26; the other first-pick counts are unchanged. Log loss improves for DPOY and Sixth Man, and worsens for MVP over the full expanded window; top-three coverage also changes. See `revised_awards/summary.json` and `before_after.csv`. These rule changes were requested after reviewing known historical cases, so results remain retrospective rather than fresh validation. Preseason win expectations begin in 2002–03; 2000–01 and 2001–02 correctly show unavailable expected wins and contribute no expectation signal.

Run `python3 -m unittest test_revised_awards test_mvp_exponential_ranks test_exponential_availability test_award_availability test_mvp_rank_penalties test_mvp_expectations` for the current 29-test regression suite.

## MIP team context, Clutch Player of the Year, Coach of the Year (2026-11-12)

**MIP** adds team wins, expected team wins (preseason market total scaled to games played), wins above expectation and a prior All-Star flag (`revised_award_core.py`). Prior All-Star = any earlier All-Star Game *appearance* (`AS_G`); injured selections who never played are not captured. Expectations start in 2002–03 and are neutral before that. Team wins and wins above expectation are constrained nonnegative. Result over 26 seasons: first picks 8 (unchanged), top three 11 → 12, log loss 2.821 → 2.595. Fitted weights: prior All-Star −0.66, wins above expectation +0.20, team wins +0.17.

**Clutch Player of the Year** (`build_clutch.py` → `clutch_model/`). Candidates are each season's top 30 NBA.com clutch scorers (totals), captured from nba.com/stats into `data/clutch/raw_chunks.json`, including the current season to date. Inputs: clutch points, clutch FG%, clutch +/-, clutch-game win %, team wins, all nonnegative with L2 1.0. 2022–23 has no earlier season to fit on, so it ranks on clutch points only. Picks: 4/4 (Fox, Curry, Brunson, SGA). With at most three training seasons, treat it as a shortlist.

**Coach of the Year** (`build_coy.py` → `coy_model/`). Candidates are one coach per team: whoever coached the most regular-season games. Inputs: team wins, wins above expectation, top-four conference seed and prior COY with the same franchise (relocations mapped). Prior-season fitting, 20-season half-life, L2 0.3. 2001–02 to 2025–26: 13/25 first picks, 22/25 in the top three, log loss 1.590. Dropping wins above expectation falls to 7/25; dropping top-four seed or prior COY worsens log loss.

Refresh: `python3 fetch_coy_clutch.py` (Basketball Reference award pages, season coaches pages and the COY winners list, 4 s between requests), then `python3 build_clutch.py`, `python3 build_coy.py` and `python3 build_dashboard_data.py`.

## Live 2026–27 projections (in-app refresh)

```sh
cd nba-award-models
python3 serve.py          # opens http://127.0.0.1:8000/ on the Projections page (localhost only)
```

The **2026–27 Projections** page shows a projected top five for all seven awards. Its buttons do three things:

- **Refresh data** runs `fetch_current.py` then `project_current.py`, which takes about 40 seconds. Sources: Basketball Reference per-game, totals, advanced, per-100 and coaches pages (4 s apart); ESPN standings; NBA.com team defensive ratings via the sportsdataverse nightly archive.
- **Update clutch stats** takes the NBA.com clutch-traditional table, copied with rows per page set to All. NBA.com blocks scripted downloads (403), so clutch data is pasted in rather than fetched.
- **Enter preseason win totals** takes 30 `TEAM total` lines. Basketball Reference has not published 2026–27 totals, so until they are entered, expected wins use a labelled proxy: last season's wins regressed 40% toward 41.

Method (`current_season.py`): season-to-date stats are scaled to an 82-game pace. Team records, player games, minutes and counting totals (including WS, DWS and VORP) are multiplied by 82 / team games played; per-game and rate stats are unchanged. The scaled rows are added to the historical inputs **in memory only**, by patching file reads in the projection process, and each award's final saved coefficients score them. Nothing is refitted and no historical file is modified. Leaderboard qualification and the availability penalty apply to the projected full season. Shares are within-pool model shares, not calibrated odds, and early-season paces are noisy.

Opened directly as a file, the page shows the last saved projections; refreshing needs `serve.py`.

### MIP archetype and COY net rating (2026-11-12, later)

**MIP** adds three fitted inputs; none of them excludes anyone:
- `second_year`: weight constrained negative, fitted at −0.37.
- `allstar_jump_fit`: a Gaussian band on this season's quality, centred at borderline All-Star level (0.896, spread 0.06).
- `origin_fit`: a band on last season's quality, centred at the median non-All-Star starter (0.673, spread 0.14).

Quality is the mean of a player's league percentiles for PPG and BPM among players with 250+ minutes. The band centres come from All-Stars and starters, not from MIP winners. Winners do sit there: a median of 0.88 in their award season, up from 0.62. The band weights are constrained positive (+0.25 and +0.39). This is how the model rewards good-to-borderline-All-Star jumps over fringe-to-rotation or star-to-MVP jumps.

Result over 26 seasons: log loss 2.595 → 2.391, top three 12/26 (unchanged), first picks 8 → 7. Dropping `second_year` alone worsens log loss to 2.481. `allstar_jump_fit` adds almost nothing measurable but is kept as requested.

**COY** adds `team_net_rating` (NBA.com team advanced stats, constrained positive, +0.47). Log loss 1.590 → 1.577, but first picks fall 13 → 11 and top three 22 → 21: it moves 2020-21 to Snyder over Thibodeau and 2023-24 to Mazzulla over Daigneault.

## Refresh dependencies and progress indicator

Use the project's local Python environment so in-app refresh can read the NBA team-stat Parquet files:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python serve.py
```

`pyarrow` is the declared Parquet reader; installing the requirements resolves Pandas' optional-engine error. The server uses `.venv/bin/python` for refresh subprocesses when that environment exists.

Refresh data now has a donut indicator beside the button with a percentage and current stage. Progress counts completed source downloads, then team win expectations, market odds, and projection scoring. It is progress through those steps, not a prediction of remaining time. A per-request ID prevents a previous refresh or a late poll from overwriting the current indicator; failures remain visibly incomplete and controls are restored for retry. `/api/status` exposes the current refresh snapshot for polling.

Run `.venv/bin/python -m unittest test_refresh_progress` to verify source progress, stage transitions, success/failure recovery, subprocess output streaming, and reading the cached Parquet data.

## League projections and accuracy scores

Projected All-Stars and Projected Standings show West on the left and East on the
right, stacking West first on smaller screens. Tables use red/blue conference
colours, contrasting headers and bold coloured projection scores or wins.
All-Stars includes five starters, seven reserves and five honourable mentions
per conference, all in tables with team W–L records. Statistical selection scores
use league percentiles: 30% PPG, 25% BPM, 15% WS/48, 10% assists, 10% rebounds,
5% availability and 5% current team win percentage. Eligibility requires at least
five games, 40% team-game availability and 15 minutes per game. This is not a
fitted voting probability. Standings reuse the award models' projected final wins
and identify the market/BBRef/record-pace source.

The Summary page puts Award by award first. Accuracy scores combine 50%
winner-first accuracy, 25% winner-in-top-three accuracy and 25% actual/model
top-three overlap (order ignored). Each component uses a five-season recency
half-life over completed seasons. Summary and each Model top five card show the
score; it measures retrospective agreement, not a forecast probability. Clutch
currently has only four completed seasons.

## Market quotes and charts

Each award projection shows a chart above Market top ten on the left and Model
top five above a separate reference-odds card on the right. The model table's
Market row shows only the combined value. The odds-format control applies across
the page, including all reference columns: percentage, decimal and American.

`fetch_odds.py` reads the supplied 2026–27 Sportsbet and Neds event links for all
seven awards alongside Polymarket and Kalshi. The consensus is the equal-weight
mean of raw implied probabilities from sources listing that player. There is no
margin adjustment or field normalisation; probabilities can sum above 100%.
Bookmaker decimal prices are retained exactly; exchange decimal equivalents use
1 / raw midpoint-or-bid, excluding fees. Per-source retrieval times remain visible.
Sportsbet is the first reference; Neds stays separate because prices can lag.
Failed sources are reported rather than relabelled as freshly fetched. TAB is
not automated because its public page rejects this client.

Decimal bookmaker snapshots append to `bookmaker_odds_history.csv`. Sportsbet and
Neds chart sources use the last observed quote per UTC day, without inventing
past observations; single observations have visible points. Combined uses the
same four sources as Market top ten, excluding Oddschecker, and inserts the
latest odds snapshot so each current top-ten endpoint exactly matches the table.

Oddschecker reference values come exclusively from each award's latest saved
Oddschecker chart date. They are chart-equivalent odds converted from the saved
margin-normalised probabilities, not raw bookmaker quotes. The date is shown;
players absent on that date and awards without history show a dash. Oddschecker
remains separately selectable in the chart.

Run the focused checks with:

```sh
.venv/bin/python -m unittest test_refresh_progress test_projection_pages test_australian_odds test_reference_odds
```

MIP candidates must average at least 13 PPG in the season being scored. The rule
applies to current projections and historical comparisons. It is an eligibility-only
change: original within-season standardisation and prior-season fitted weights are
preserved, then model shares are recalculated over eligible players. The 2000–01
through 2025–26 comparison is 8/26 winner first, 14/26 winner top three and 2.028
mean log loss; the recency-weighted Accuracy Score is 45.0. The isolated experiment
and season comparison are saved in `experiments/mip_13ppg`. Rebuild just these
historical results with `.venv/bin/python build_dashboard_data.py --award MIP`.
