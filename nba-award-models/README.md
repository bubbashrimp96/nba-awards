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
