# MVP: PER replaces BPM

PER replaces BPM in the conference model. All other inputs, the 20-game candidate pool,
within-season standardization, half-life (20 seasons), and L2 regularization
(0.03) are unchanged. Coefficients are refitted. No new tuning uses later results.

2015–16 through 2025–26: 7/11 first picks correct, 10/11 winners
in the model top three, mean log loss 0.964304.
Previous BPM model: 8/11, 10/11,
mean log loss 0.973342.

Every historical fit trains only on prior seasons. This remains retrospective because these outcomes
were already inspected. The feature change is a user preference, not evidence of improved future accuracy.
Original conference outputs and the earlier PER-plus-BPM experiment are preserved.

Run `python3 replace_mvp_bpm_with_per.py`, then `python3 build_dashboard_data.py`.
