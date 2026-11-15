# Historical preseason player projection source audit

Research date: 2026-11-15. No active model changes.

## Best first extraction target

Razzball's original preseason articles retain actual projected per-game stat
lines. The 2018-19 through 2022-23 Top 155 series provides five consecutive
seasons of candidate sources. Article publication dates are preseason; complete
extraction, candidate coverage, revision history and independent archived-snapshot
verification remain outstanding. A current copy of an old article is not proof
that no later edits occurred.

| Season | Source | Status |
|---|---|---|
| 2012-13 | https://basketball.razzball.com/2012-2013-fantasy-basketball-rankings-the-top-100/ | Search index includes projected stat lines; direct fetch 403 |
| 2014-15 | https://basketball.razzball.com/official-razzball-2014-2015-fantasy-basketball-rankings/ | Original Top 200 page; text states projections for each player |
| 2015-16 | https://basketball.razzball.com/official-razzball-2015-2016-fantasy-basketball-rankings/ | Search index includes projected stat lines; direct fetch 403 |
| 2016-17 | https://basketball.razzball.com/official-razzball-2016-2017-fantasy-basketball-rankings/ | Search index includes stat-line key and projections including MPG |
| 2017-18 | https://basketball.razzball.com/fantasy-basketball-updated-top-200-with-sortable-stats/ | Dated 2017-10-16, but embedded table now reports missing Basketball_Preseason_2017 database table; not extraction-ready |
| 2018-19 | https://basketball.razzball.com/fantasy-basketball-top-155-roto-projections/ | Dated 2018-09-07; visible PTS/REB/AST/STL/BLK, percentages, attempts and turnovers |
| 2019-20 | https://basketball.razzball.com/fantasy-basketball-top-155-roto-projections-for-2019/ | Dated 2019-08-30; visible projected per-game statistics |
| 2020-21 | https://basketball.razzball.com/2020-2021-top-155-roto-projections-for-fantasy-basketball/ | Dated 2020-12-02; full visible projected-stat table |
| 2021-22 | https://basketball.razzball.com/2021-22-top-155-roto-projections/ | Dated 2021-09-17; full visible projected-stat table |
| 2022-23 | https://basketball.razzball.com/2022-23-top-155-roto-projections/ | Dated 2022-09-12; visible projected-stat table |

## Other findings

- ESPN 2015-16 cheat sheet (https://g.espncdn.com/s/fbadraftkit/16/NBADK2K15_CS.pdf) contains rankings/auction values, not the box-score projection matrix required here.
- ESPN 2014-15 and 2016-17 draft-kit PDFs were located, but a complete numeric preseason stat matrix has not been verified.
- 2021-22 NBC preview (https://www.nbcsports.com/fantasy/basketball/news/article-draft-guide-preview-preview-interactive-top-200-projectionsranks) documents a 250+ player projection product; complete accessible dataset not verified.
- Razzball 2023-24 and 2024-25 retrospective reviews reproduce projections for selected misses, not all candidates. Do not train using only these selected cases.
- https://basketball.razzball.com/top-155-roto-projections-review-2024-25/ lists Dyson Daniels' original forecast as 7.74 PPG, 5.4 RPG, 3.3 APG and 1.6 SPG, alongside subsequent actual statistics. This is a useful example, not independently verified preseason-snapshot evidence.
- https://www.khokibernier.com/jekyll/update/2020/07/28/NBA-STAT-PREDICTOR.html describes a saved ESPN 2019-20 preseason CSV, but this is a lead, not a recovered/verified source dataset.

## Requirements before testing

Match by player identity and season; preserve raw forecast values and source/date;
normalize percentage scales and names; audit missing MIP candidates and all actual
vote recipients; avoid filling missing forecasts with actual outcomes. Compare
baseline and test on identical coverage. Report how much candidate coverage is
lost. Use actual per-game statistics against projected per-game statistics, not
fantasy ranks or z-score values. Freeze current preseason expectations rather
than replacing them with updated rest-of-season projections.
