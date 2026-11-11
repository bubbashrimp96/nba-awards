from pathlib import Path
import json,csv,math
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
pdfmetrics.registerFont(TTFont('ArialUnicode','/System/Library/Fonts/Supplemental/Arial.ttf'))

ROOT=Path(__file__).resolve().parent
DEST=ROOT/'output/pdf/nba_award_models_explained.pdf'
DEST.parent.mkdir(parents=True,exist_ok=True)
M=json.loads((ROOT/'models.json').read_text())
rows=list(csv.DictReader((ROOT/'validation_summary.csv').open()))
M['MVP']=json.loads((ROOT/'mvp_conference_revision/model.json').read_text())
mvp_summary=next(r for r in csv.DictReader((ROOT/'mvp_conference_revision/comparison_summary.csv').open()) if r['variant']==M['MVP']['variant'])
rows=[r for r in rows if not (r['award']=='MVP' and r['weighting']=='recency')]
rows.append(dict(award='MVP',weighting='recency',top1=int(mvp_summary['correct'])/11,top3=int(mvp_summary['top3'])/11,mean_log_loss=mvp_summary['mean_log_loss']))
mvp_points=M['MVP']['coefficients'][M['MVP']['features'].index('PTS')]
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleCustom',fontName='Helvetica-Bold',fontSize=27,leading=32,textColor=colors.HexColor('#14334A'),spaceAfter=18))
styles.add(ParagraphStyle(name='Deck',fontSize=13,leading=19,textColor=colors.HexColor('#476473'),spaceAfter=15))
styles.add(ParagraphStyle(name='BodyCustom',fontSize=10,leading=14,spaceAfter=9))
styles.add(ParagraphStyle(name='SmallCustom',fontSize=8.5,leading=11,spaceAfter=5))
styles.add(ParagraphStyle(name='CellCustom',fontName='ArialUnicode',fontSize=8.4,leading=11))
styles['Heading2'].textColor=colors.HexColor('#14334A')
styles['Heading2'].spaceBefore=10
story=[]
def p(t,style='BodyCustom'):return Paragraph(t,styles[style])
def add(t,style='BodyCustom'):story.append(p(t,style))
def title(n,t):add(f'{n:02d} / {t}','TitleCustom')
def table(data,widths):
    t=Table([[p(str(x),'CellCustom') for x in r] for r in data],colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E1EBF0')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#9AAFB9')),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#DAE2E6'))]))
    story.append(t);story.append(Spacer(1,10))
def page():story.append(PageBreak())

title(1,'NBA award models')
add('A detailed guide to all five models and every fitted coefficient','Deck')
add('Updated 9 November 2026 | Revised MVP with conference standings | Trained through 2025-26','SmallCustom')
add('This guide explains the models fitted to your basketball_stats.csv: Most Valuable Player (MVP), Defensive Player of the Year (DPOY), Rookie of the Year (ROY), Sixth Man of the Year (SMOY), and Most Improved Player (MIP).')
add('What these models do','Heading2')
add('They compare players within a season and learn which combinations of statistics distinguish historical award winners. Each award has its own candidate pool, inputs, coefficients and recency weighting. These are end-of-season statistical ranking models.')
add('What to take away','Heading2')
add('The revised MVP model selects 8 of 11 winners, compared with 5 of 11 originally, using team wins plus league and conference standing. The other four models retain their original versions. Across the five current models, 29 of 55 first picks are correct. MIP remains a weak first-choice predictor. Model shares are uncalibrated.')
table([['Guide','Pages'],['How scores and coefficients work','2'],['How training and recent-season weighting work','3'],['All five models and their coefficients','4-8'],['Historical validation and its limits','9'],['Data, sources and practical use','10'],['Season-by-season correct and incorrect picks','11-15'],['MVP revision comparison and standings methods','16']],[405,80])
add('Source snapshot','Heading2')
add('The analysis uses the Basketball/Data copy of basketball_stats.csv: 25,312 unique player-seasons from 1949-50 through 2025-26. Award-model training begins in 1985-86. Historical winner labels come from your existing NBA project. The source CSV was not modified.')
page()
title(2,'Scores and coefficients')
add('Step 1: compare like with like','Heading2')
add('For each award and season, first select its candidate pool. Missing feature values are replaced by that pool\'s median. Each feature is then standardized using the pool\'s mean and population standard deviation:')
add('<b>z = (player value - candidate-pool average) / candidate-pool standard deviation</b>')
add('A z-score of +1 means one standard deviation above the pool average; -1 means one below. This makes points, percentages and advanced statistics comparable and partly adjusts for changes in statistical eras. It does not remove every difference between eras.')
add('Step 2: add the weighted statistics','Heading2')
add('<b>Player score = coefficient[1] x z[1] + ... + coefficient[p] x z[p]</b>')
add('A coefficient is the score change from a one-standard-deviation increase in that feature, holding the other standardized inputs fixed. Coefficients are not percentages, raw-stat point values or causal effects. Larger absolute coefficients imply a larger conditional score change for the same standardized movement.')
add('Worked example using MVP scoring','Heading2')
add(f'The revised MVP points coefficient is {mvp_points:+.6f}. Suppose, purely for illustration, that the pool average is 12 points per game and its standard deviation is 6. A player scoring 24 points has z = (24 - 12) / 6 = 2. The scoring term adds 2 x {mvp_points:.6f} = <b>{2*mvp_points:.6f}</b> to the player\'s score. These pool statistics are hypothetical; calculations use unrounded coefficients.')
add('Step 3: convert scores into model shares','Heading2')
add('<b>Share(i) = exp(score(i)) / sum of exp(score(k)) across candidates</b>')
add('This is a softmax calculation. It preserves the score ranking and produces positive shares adding to 100%. A player\'s share changes when rivals change. A share of 40% has not been demonstrated to mean a 40% real-world chance of winning.')
add('Reading negative coefficients','Heading2')
add('A negative coefficient lowers the fitted score as that input rises, conditional on the other inputs. Lower defensive rating is desirable, so its negative DPOY coefficient is intuitive. Other negative signs may reflect overlapping statistics, limited winner samples and model specification. They do not show that worse efficiency or fewer games causes awards.')
add(f'For two players, their model-share ratio is exp(score A - score B). A one-standard-deviation scoring advantage alone gives a revised MVP ratio multiplier of exp({mvp_points:.6f}), about <b>{math.exp(mvp_points):.2f}</b>. This is a model-relative comparison, not a guaranteed probability increase.')
page()
title(3,'Training and recency')
add('What the fitting procedure learns','Heading2')
add('The feature lists were chosen by the analyst. The coefficients were then learned by minimizing weighted historical prediction loss. Each season forms one contest, so modern seasons do not receive extra training weight simply because they have larger rosters. Tied winners split the target outcome equally.')
add('<b>Objective = weighted average of -sum(target share x log(model share)) + (lambda / 2) x sum(coefficient squared)</b>')
add('The first term rewards assigning share to actual winners. The second is L2 regularization: it discourages excessively large coefficients and helps limit overfitting. There is no intercept because adding the same constant to every player\'s score in a contest cancels in softmax.')
add('How newer seasons receive more weight','Heading2')
add('<b>Season weight = 2 ^ (-(latest training year - season year) / half-life)</b>')
add('Weights are normalized to sum to one within each training run. This changes how historical outcomes influence the learned coefficients. It does not discount a current player\'s statistics or automatically place more emphasis on recent games within a season.')
data=[['Model','Half-life','10 years older','20 years older','Lambda']]
for a in ['MVP','DPOY','ROY','SMOY','MIP']:
    h=M[a]['half_life'];data.append([a,f'{h} seasons',f'{2**(-10/h):.1%}',f'{2**(-20/h):.1%}',str(M[a]['regularization'])])
table(data,[74,106,107,107,91])
add('How the settings were selected','Heading2')
add('Half-lives of 5, 10 and 20 seasons and lambda values of 0.03, 0.1 and 0.3 were compared using rolling predictions for 2005-06 through 2014-15. The combination with the lowest average log loss was selected separately for each award. Log loss measures how much share the model assigns to the winner; lower is better.')
add('For each 2015-16 through 2025-26 prediction, coefficients were fitted using earlier seasons only. The revised MVP family and settings were selected on the earlier development period, but the later results had already been inspected during this project, so its improvement is retrospective. Final coefficients on pages 4-8 are refit through 2025-26 and differ from the historical fits.')
page()

defs={
'PTS':'Points scored per game.', 'AST':'Assists per game.', 'TRB':'Total rebounds per game.',
'STL':'Steals per game.', 'BLK':'Blocks per game.', 'DRB':'Defensive rebounds per game.',
'BPM':'Box plus/minus: box-score estimate of impact per 100 possessions relative to an average player.',
'WS':'Win shares: estimated season-long contribution to team wins.',
'WS/48':'Win shares per 48 minutes: a rate measure of estimated contribution.',
'VORP':'Value over replacement player: cumulative box-score estimate relative to replacement level.',
'TS%':'True shooting percentage: scoring efficiency accounting for two-pointers, three-pointers and free throws.',
'G':'Games played during the season.',
'team_wins':'Team regular-season wins. Each player on a known team receives that team\'s total.',
'league_standing':'League position by regular-season win percentage, normalized from 0 (last) to 1 (first). Ties share rank.',
'conference_standing':'Position within that season\'s Eastern or Western Conference, normalized from 0 to 1. Ties share rank.',
'DWS':'Defensive win shares: the defensive component of estimated win contribution.',
'DBPM':'Defensive box plus/minus: box-score estimate of defensive impact per 100 possessions.',
'DRtg':'Individual defensive rating: estimated points allowed per 100 possessions; lower is better.',
'MPG':'Minutes per game, calculated as total season minutes divided by games played.',
'Age':'Player age as recorded in the source file.',
'experience':'Elapsed years since the first recorded NBA season, including any gaps.',
'delta_PTS':'Change in points per game from the previous recorded NBA season.',
'delta_AST':'Change in assists per game from the previous recorded NBA season.',
'delta_TRB':'Change in rebounds per game from the previous recorded NBA season.',
'delta_BPM':'Change in box plus/minus from the previous recorded NBA season.',
'delta_PER':'Change in player efficiency rating, a box-score production measure.',
'delta_MPG':'Change in minutes per game from the previous recorded NBA season.',
'delta_TS%':'Change in true shooting percentage from the previous recorded NBA season.',
'delta_USG%':'Change in usage rate: estimated share of team plays used through shooting, free throws or turnovers while on court.'}
names={'MVP':'Most Valuable Player','DPOY':'Defensive Player of the Year','ROY':'Rookie of the Year','SMOY':'Sixth Man of the Year','MIP':'Most Improved Player'}
intro={
'MVP':'Revised model: combines player production with team wins, league standing and conference standing. Total WS and VORP are removed. Candidates still need at least 20 games.',
'DPOY':'Favors defensive win shares, lower individual defensive rating and a substantial playing role. Candidates need at least 20 games. Team defensive ranking and tracking defense are absent.',
'ROY':'Favors scoring and broad box-score production among players in their first recorded NBA season with at least 20 games. This is a data-based rookie proxy, not a separately verified official eligibility list.',
'SMOY':'Favors scoring and win shares among bench players. Candidates need at least 20 games and known games started (GS), with 2 x GS &lt; G. A player starting exactly half their games is excluded.',
'MIP':'Combines current performance with growth from the previous recorded NBA season. Candidates need at least 20 current games and a previous observed points-per-game value. No minimum prior-season games is imposed.'}
notes={
'MVP':'Team wins and both standings measures overlap; their coefficients are conditional score weights, not independent percentages. A nearly zero negative TS% term does not establish that poor shooting helps. Standings use regular-season win percentage, average tied ranks and historical conference membership. Play-in outcomes are excluded. See page 16 for comparisons and source repairs.',
'DPOY':'DRtg is an individual box-score estimate, not direct measurement of points conceded by a player. DWS, DBPM and DRtg can reflect team context and favor what box scores capture. Negative DRB and G coefficients are conditional on the other inputs; they do not imply rebounds or availability are harmful.',
'ROY':'The negative TS%, BPM and block terms are conditional fitted relationships after accounting for scoring, assists, rebounds and win shares. In a small and correlated sample they can produce counterintuitive signs; they do not establish that poor shooting or defense helps win the award.',
'SMOY':'Scoring and win shares dominate the fitted score. Negative efficiency, minutes, assists and rebound coefficients should not be read as desirable basketball traits. The model describes the joint profile of historical winners within this candidate pool.',
'MIP':'Delta means current value minus previous recorded NBA value; a positive delta is an increase. For returnees after a gap, this is not necessarily a comparison with the immediately preceding calendar season. Usage growth can capture a larger role without proving improved skill. Tiny delta_MPG and delta_TS% terms contribute little per standardized movement.'}
for num,a in enumerate(['MVP','DPOY','ROY','SMOY','MIP'],4):
    title(num,names[a])
    add(intro[a])
    add('Every fitted coefficient','Heading2')
    add('All values below multiply within-season, within-candidate-pool z-scores. A +1 z change adds the signed coefficient to the score; a -1 z change subtracts it. Values are rounded to six decimals.','SmallCustom')
    data=[['Input','Coefficient','What the input measures']]
    labels={'team_wins':'Team wins','league_standing':'League standing','conference_standing':'Conference standing'}
    for f,b in zip(M[a]['features'],M[a]['coefficients']):data.append([labels.get(f,f),f'{b:+.6f}',defs[f]])
    table(data,[83,83,319])
    add('How to interpret the combination','Heading2');add(notes[a])
    r=next(r for r in rows if r['award']==a and r['weighting']=='recency')
    add(f"<b>Historical test:</b> {round(float(r['top1'])*11)} of 11 winners ranked first; {round(float(r['top3'])*11)} of 11 ranked in the top three. Recency half-life: {M[a]['half_life']} seasons. Lambda: {M[a]['regularization']}.")
    if a=='MIP':add('<b>Use with caution:</b> first-place accuracy was only 18%. This model needs richer career context and more flexible relationships before its top pick is dependable.','SmallCustom')
    page()

title(9,'Historical validation')
add('The test contains 11 seasons, from 2015-16 through 2025-26. Each was predicted using coefficients fitted to earlier seasons only. Top-one accuracy counts first-ranked winners; top-three accuracy counts winners ranked anywhere in the first three.')
data=[['Award','Winner first','Winner top 3','Equal-weight first**','Log loss*']]
for a in names:
 r=next(r for r in rows if r['award']==a and r['weighting']=='recency');e=next(r for r in rows if r['award']==a and r['weighting']=='equal_weight')
 equal='Not evaluated' if a=='MVP' else f"{round(float(e['top1'])*11)}/11 ({float(e['top1']):.0%})"
 data.append([a,f"{round(float(r['top1'])*11)}/11 ({float(r['top1']):.0%})",f"{round(float(r['top3'])*11)}/11 ({float(r['top3']):.0%})",equal,f"{float(r['mean_log_loss']):.3f}"])
table(data,[58,108,108,125,86])
add('*Mean test log loss for the recency model. Lower is better. Candidate pools differ by award, so comparisons across awards are affected by contest difficulty and pool size.','SmallCustom')
add('**The revised MVP has no equal-weight comparison yet. Other awards use their original same-feature equal-weight baselines. Across current models: 29 correct / 26 incorrect first picks.','SmallCustom')
add('What recency changed','Heading2')
add('In the original versions, recency weighting improved DPOY from four to six winners and Sixth Man from five to six. MIP stayed at two and Rookie dropped from eight to seven. The revised MVP improves from five to eight through feature changes; that gain cannot be attributed to recency weighting alone.')
add('What the comparison controls','Heading2')
add('For the four unchanged awards, equal-weight baselines use the same features and selected regularization while replacing decaying season weights with approximately equal weights. The MVP revision comparison on page 16 instead changes features and retunes settings; it does not isolate a single input\'s causal effect.')
add('What the test does not establish','Heading2')
add('Eleven seasons is a small sample: one winner changes accuracy by about nine percentage points. MVP revisions were designed after inspecting these seasons, so their improvements are retrospective. These results are exploratory historical evidence, not fresh external validation or a guarantee of future performance.')
add('The inputs are complete-season statistics. Results do not measure performance with December statistics, partial seasons or projected future games. A realistic in-season model would need historical snapshots at comparable dates.')
add('Calibration is also untested. High shortlist accuracy does not make the softmax shares calibrated probabilities. The saved full-history coefficients must not be used to claim historical out-of-sample performance; use the expanding-window backtest records for that purpose.')
page()
title(10,'Data and practical use')
add('Data preparation and eligibility','Heading2')
add('PlayerID plus Season is unique in the selected CSV. Traded-player records were not summed; some team labels denote multiple teams. MP is total minutes, so minutes per game is MP/G. Corrupted character encoding in names was repaired in memory, then accents and punctuation normalized for winner matching. Every winner in each modeled season was required to appear in the candidate pool.')
add('The 20-game minimum is an analyst screening rule. Official award-specific games/minutes requirements, exceptions and appeals are not fully implemented. Current eligibility needs a separate check before treating a ranking as an actionable forecast.')
add('Main limitations','Heading2')
add('MVP now includes team wins and league/conference standing. Team defensive ranking, tracking defense, injuries, reputation, voting narratives, prior award voting and market odds remain absent. Correlated inputs can produce unintuitive coefficients. There are no missing-value indicator features; median imputation assigns neutral within-pool values without identifying missingness.')
add('Using the models on another season','Heading2')
add('Apply the same candidate filters and calculate every feature with the same units. Calculate pool medians, means and population standard deviations for that season, then standardize. If a feature is constant, the implementation uses a standard deviation of one. Multiply by the saved coefficients, add the terms and apply stable softmax. Rank shares from highest to lowest. New-season ranking accuracy remains unproven until evaluated.')
add('Sources and model files','Heading2')
add('<b>Primary statistics:</b> basketball_stats.csv, Basketball/Data copy. Source SHA-256:','SmallCustom')
sha=M['_metadata']['sha256'];add(sha[:32]+'<br/>'+sha[32:],'SmallCustom')
add('<b>Historical labels:</b> award-winners.ts in the existing nba-story-lab project. Its header attributes the snapshot to Basketball Reference, transcribed 2026-09-01. Winner joins and candidate coverage were checked; all labels were not independently audited against external records.','SmallCustom')
add('Reference pages: basketball-reference.com/awards/mvp.html; /dpoy.html; /roy.html; /smoy.html; /mip.html. Official award-history index: nba.com/news/history-all-time-awards. These references describe source provenance; this document does not claim a new source audit.','SmallCustom')
add('<b>Current MVP:</b> improve_mvp_conference.py and mvp_conference_revision/model.json hold the revised fit and settings. conference_standings/prepare_standings.py creates the derived ranks from cached ESPN responses; sources.json records provenance and repairs (page 16). Other awards retain model.py, models.json and the original backtests. award_labels.json stores the shared winner labels.','SmallCustom')

backtests=[r for r in csv.DictReader((ROOT/'historical_backtests.csv').open()) if r['weighting']=='recency']
backtests=[r for r in backtests if r['award']!='MVP']
for r in csv.DictReader((ROOT/'mvp_conference_revision/historical_backtests.csv').open()):
    if r['variant']==M['MVP']['variant']:backtests.append(dict(r,award='MVP',weighting='recency'))
assert len(backtests)==55
for num,a in enumerate(names,11):
    page()
    title(num,names[a]+' results')
    picks=[r for r in backtests if r['award']==a]
    correct=sum(int(r['top1']) for r in picks)
    add(f'<b>{correct} correct / {11-correct} incorrect.</b> These are the recency-weighted model results for all 11 test seasons. Each pick was made using earlier seasons only.')
    add('Correct means the first-ranked player matched the recorded winner. Winner rank is where the actual winner appeared in the model ranking; a second- or third-ranked winner still counts as an incorrect first pick.','SmallCustom')
    data=[['Season','Model pick','Actual winner','Result','Winner rank']]
    for r in picks:
        data.append([r['season'],escape(r['predicted']),escape(r['actual']),'Correct' if int(r['top1']) else 'Incorrect',r['winner_rank']])
    table(data,[56,152,152,66,59])
    if a=='MVP':
        add('Current version: revised MVP with team wins, league standing and conference standing. The original achieved 5/11; this version achieves 8/11. Revisions are retrospective comparisons. Page 16 explains the standings and model progression.','SmallCustom')
    else:
        add('Original model version, retained for this award. Results use the recorded winner labels on page 10. Equal-weight comparison picks are excluded here; aggregate comparisons appear on page 9.','SmallCustom')
    expected=next(r for r in rows if r['award']==a and r['weighting']=='recency')
    assert correct==round(float(expected['top1'])*11)

page()
title(16,'MVP revision and standings')
add('The MVP model now includes team wins plus league and conference standing, retaining WS/48 and games played while removing total WS and VORP. The other four award models retain their original versions.')
table([['MVP version','Winner first','Winner top 3','Mean log loss'],['Original','5/11','11/11','1.135'],['Team wins + league standing','7/11','10/11','0.876'],['Plus conference standing (current)','8/11','10/11','0.973']],[221,88,88,88])
add('The current model fixes Giannis in 2018-19, Giannis in 2019-20 and Shai in 2024-25 relative to the original. It still misses Westbrook in 2016-17, Embiid in 2022-23 and Shai in 2025-26. Its log loss worsens versus the first team-context revision despite improving first picks. Lower log loss is better.')
add('How conference standing is calculated','Heading2')
add('ESPN historical feeds supply conference membership and team records for all 41 modeled seasons (1,177 team-seasons). Rank teams by regular-season W/(W+L) within their own conference. Tied records share their average rank. Normalize as 1 - (rank - 1)/(number of teams - 1). First place is 1 and last place 0, before candidate-pool standardization.')
add('League standing uses the same method across all teams. These are record-based positions, not official tiebreak-resolved ranks. Playoff-seed fields are excluded because play-in outcomes and historical division rules can alter them. Multi-team player rows receive candidate-pool median team inputs; every actual MVP has a known team and conference.')
add('Selection and source checks','Heading2')
add('The lean model with both standings measures won the earlier 2005-06 through 2014-15 development comparison. Each later prediction trains only on prior seasons, but those later outcomes had already been inspected, so the revision is retrospective. The selected recency half-life remains 20; lambda changes from 0.1 originally to 0.03.')
add('Raw ESPN responses are preserved. The 1999-00 feed is incomplete: derived records use final wins from the existing cache and an 82-game schedule. Dallas 1993-94 and Denver 1997-98 each have an extra loss in the feed; corrected to 13-69 and 11-71. All derived seasons reconcile total league wins to losses. Historical conference switches were checked.','SmallCustom')
add('Sources: ESPN standings feed, site.web.api.espn.com/apis/v2/sports/basketball/nba/standings?season=2025&amp;type=0&amp;level=2 (season is the ending year). Repairs: basketball-reference.com/leagues/NBA_2000_standings.html; /teams/DAL/1994.html; /teams/DEN/1998.html. Final 1999-00 records were also spot-checked against NBA historical material; the full 29-team table was not independently re-audited. Exact repairs and hashes are in conference_standings/sources.json.','SmallCustom')

def footer(canvas,doc):
    canvas.setStrokeColor(colors.HexColor('#C7D5DC'));canvas.line(55,43,540,43)
    canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#526C7A'))
    canvas.drawString(55,30,'NBA AWARD MODELS | Methodology and coefficient guide')
    canvas.drawRightString(540,30,str(doc.page))
doc=SimpleDocTemplate(str(DEST),pagesize=(595.28,841.89),rightMargin=55,leftMargin=55,topMargin=49,bottomMargin=58,title='NBA Award Models: Methodology and Coefficient Guide',author='NBA statistical analysis')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(DEST)
