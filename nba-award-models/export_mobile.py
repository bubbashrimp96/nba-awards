"""Export the latest saved dashboard as a mobile-friendly, read-only website.

Run: .venv/bin/python export_mobile.py --output /Users/jeevie/sites/nba-awards-mobile/dist
Then ask Codex to publish the latest saved dashboard to the existing NEMO Site.
"""
import argparse
import json
from pathlib import Path
from shutil import copyfile
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent

MOBILE_STYLE = """
#header-refresh,.paste-panel,.league-refresh-link{display:none!important}
.snapshot-note{padding:12px 16px;border:1px solid var(--panel-bd);border-radius:12px;background:var(--panel);color:var(--fg-2);font-size:12px}
.snapshot-note strong{color:var(--fg-1)}
.mobile-menu{display:none}
@media(max-width:900px){
 .app{padding:10px;gap:12px}.side{position:static;width:100%;height:auto;padding:14px;border-radius:14px;display:grid;grid-template-columns:1fr auto;align-items:center}
 .side .brand{padding:0}.mobile-menu{display:block;border:1px solid var(--navy-bd);background:var(--navy-hover);color:white;padding:10px 16px;border-radius:9px;font:600 13px inherit;min-height:44px}
 .side .page-nav{display:none;margin:12px 0 0;padding:0;grid-column:1/-1;overflow:visible;flex-direction:column}
 .side.menu-open .page-nav{display:flex}.side .page-nav a.nav,.side .page-nav a.nav.sub{min-height:44px;padding:10px 12px;font-size:13px}.side .page-nav a.nav.sub{padding-left:38px}
 main{padding:0;gap:12px}.head{padding:14px;gap:12px;flex-wrap:wrap}.head h1{font-size:23px;line-height:1.35;min-width:0;overflow-wrap:anywhere}.head h1 .bar{display:none}.head h1 .vw{display:block;font-size:16px;margin-top:4px}
 .theme-toggle{margin-left:auto;min-height:44px}.results-layout{display:flex;flex-direction:column}.results-layout>.season-control{order:-1;position:static;width:100%;max-height:none;margin:0}.results-layout>.panel{width:100%}
 #season-buttons{flex-direction:row;flex-wrap:nowrap;overflow-x:auto;width:100%;padding-bottom:6px}#season-buttons button{flex:none;min-height:44px}
 .table-responsive{width:100%;max-width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch}
 table.tview{min-width:590px}table.mtop5{min-width:460px}.summary-grid{min-width:680px}.player-stats .input-matrix{min-width:700px}
 .bhead{flex-wrap:wrap;gap:12px}.bhead .picks{flex-wrap:wrap}.pick select{min-height:44px;max-width:100%}
 .split,.splitL,.splitR{min-width:0}.gcard,.sect{padding:14px}.strip{padding:12px;gap:10px}.strip .tools{margin-left:0}.mkt button,.mquick button{min-height:40px;padding:7px 12px}.mitem{min-height:44px;font-size:12px}
 .mbody{flex-direction:column}.mlegend{grid-template-columns:repeat(2,minmax(0,1fr));gap:4px}.splitL .move .cwrap{height:280px}.award-tabs button{min-height:44px}
 .allstar-conference .league-roster-table,.standings-conference .league-standings-table{min-width:430px}
}
@media(max-width:380px){.mlegend{grid-template-columns:1fr}.theme-toggle{margin-left:0}.allstar-starters{grid-template-columns:1fr}}
"""

MOBILE_SCRIPT = """
const side=document.querySelector('.side');
const menu=document.querySelector('.mobile-menu');
menu.addEventListener('click',()=>{const open=side.classList.toggle('menu-open');menu.setAttribute('aria-expanded',String(open));menu.textContent=open?'Close menu':'Menu';});
side.querySelectorAll('nav a').forEach(a=>a.addEventListener('click',()=>{side.classList.remove('menu-open');menu.setAttribute('aria-expanded','false');menu.textContent='Menu';}));
document.querySelectorAll('.table-responsive,.league-table-wrap').forEach(w=>{w.tabIndex=0;w.setAttribute('aria-label','Data table. Scroll sideways to see all columns.');});
const savedDate=document.querySelector('#snapshot-time');
savedDate.textContent=new Date(savedDate.dateTime).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'});
"""


def export(output):
    output.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'output/artifacts/nba-award-models-browser.html'
    data = json.loads((source.parent / 'projections.json').read_text())
    html = source.read_text().replace("const served=location.protocol.startsWith('http');", 'const served=false;')
    html = html.replace("if(!served)setStatus('projection-status','Opened as a file: showing the last saved projections. Run python3 serve.py from nba-award-models/ to refresh in the app.');", "if(!served)setStatus('projection-status','Saved dashboard');")
    html = html.replace("window.addEventListener('hashchange',restorePage);restorePage();", "if(!location.hash)history.replaceState(null,'','#projections/MVP');\nwindow.addEventListener('hashchange',restorePage);restorePage();")
    soup = BeautifulSoup(html, 'html.parser')
    style = soup.new_tag('style', id='mobile-saved-dashboard');style.string=MOBILE_STYLE;soup.head.append(style)
    meta = soup.new_tag('meta', attrs={'name':'description','content':'NEMO NBA award projections, team-coloured odds charts and historical results. Saved dashboard, updated from the desktop app.'});soup.head.append(meta)
    button = soup.new_tag('button', attrs={'type':'button','class':'mobile-menu','aria-expanded':'false','aria-controls':'mobile-navigation'});button.string='Menu'
    soup.select_one('.side .brand').insert_after(button);soup.select_one('.side nav')['id']='mobile-navigation'
    note = soup.new_tag('div', attrs={'class':'snapshot-note','role':'note'})
    strong = soup.new_tag('strong');strong.string='Saved dashboard';note.append(strong);note.append(' · Data generated ')
    time = soup.new_tag('time', id='snapshot-time', attrs={'datetime':data['generated_at']});time.string=data['generated_at'];note.append(time)
    note.append('. Updates are published from the desktop app.')
    soup.select_one('main .head').insert_after(note)
    soup.select_one('.side .foot').clear();soup.select_one('.side .foot').string='Saved dashboard · 7 award models'
    script=soup.new_tag('script');script.string=MOBILE_SCRIPT;soup.body.append(script)
    (output/'index.html').write_text(str(soup))
    for asset in ('award-ballots.js', 'award-ballots.json'):
        copyfile(source.parent / asset, output / asset)
    # Standalone snapshot uses embedded data so HTML and JSON cannot get out of sync.
    (output/'projections.json').write_text(json.dumps(data,ensure_ascii=False,indent=1)+'\n')
    print(f'Exported saved dashboard to {output}')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'output/mobile')
    export(parser.parse_args().output)
