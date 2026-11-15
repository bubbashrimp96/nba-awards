# MIP changes in per-36 stats

Offline experiment across 2000–01 through 2025–26. Active model unchanged.
Every prediction fits only earlier seasons with the active half-life (20), L2
regularization (0.3), original candidate standardization and 13 PPG ranking cutoff.
Baseline predictions and log losses reproduce the active dashboard.

Per-36 delta = current-season cached per-36 value minus immediately previous
season's value, matched by PlayerID. Missing adjacent seasons remain missing and
use that season's candidate-pool median. Cached PTS_36 agrees with 36*PTS_T/MP
to the expected one-decimal rounding precision. Prior small-minute samples are
not separately downweighted; this remains a limitation.

| Variant | Winner first | Winner top three | Mean log loss | App accuracy |
|---|---:|---:|---:|---:|
| Current baseline | 8/26 | 14/26 | 2.027679 | 45.05 |
| Add change in points/36 | 8/26 | 15/26 | 2.018670 | 47.85 |
| Add changes in points, assists, rebounds/36 | 8/26 | 15/26 | 2.028078 | 47.85 |
| Add changes in points, assists, rebounds, steals, blocks/36 | 8/26 | 16/26 | 2.037313 | 44.83 |
| Replace per-game PTS/AST/TRB changes with per-36 changes | 9/26 | 15/26 | 2.243046 | 46.63 |

Adding points/36 alone leaves every first pick unchanged. Dyson Daniels (2024–25)
improves from fourth to third, while Ivica Zubac remains first. Its fitted delta
coefficient is positive in every historical fit (0.120 to 0.234). Mean log-loss
improvement is about 0.4%, too small to establish a robust forecasting gain.

The app accuracy metric recency-weights first picks (50%), winner top three
(25%), and overlap with the official top three (25%) using a five-season half-life.
This differs from unweighted season counts and mean log loss. Five variants were
examined retrospectively; chronological diagnostic splits are not fresh holdouts.

Recommendation: if adopting a per-36 signal, add points/36 change alongside the
existing per-game change and minutes change. Do not replace per-game improvement
on this evidence: replacing it improves first-pick count but worsens log loss.

Run `.venv/bin/python experiments/mip_per36/run.py`. See summary.csv,
backtests.csv, changed_picks.csv, coefficients.csv, feature_audit.csv, and method.json.
