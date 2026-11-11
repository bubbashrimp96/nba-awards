# NBA Award Models

Five end-of-season NBA award ranking models, historical backtests, experiments, and a browser dashboard.

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

The guide reports first-pick accuracy of MVP 8/11, DPOY 6/11, ROY 7/11, Sixth Man 6/11, and MIP 2/11 across 2015–16 to 2025–26. MVP changes are retrospective; model shares are uncalibrated. Inputs use complete-season statistics and screening rules do not fully implement official award eligibility.

See `REPORT.md`, the PDF and revision reports for methodology, provenance and limitations. Temporary PDF preview images are excluded.
