import re,html,csv,sys,gzip,shutil,os
S=sys.argv[1]; OUT=sys.argv[2]; RAW=sys.argv[3]
def text(f):
    t=open(os.path.join(S,f),encoding='utf-8',errors='replace').read()
    t=re.sub(r'(?s)<script.*?</script>|<style.*?</style>','',t)
    t=re.sub(r'<br\s*/?>|</p>|</tr>|</td>|</th>|</div>|</li>|</h\d>','\n',t)
    t=html.unescape(re.sub(r'<[^>]+>','',t)); t=re.sub(r'[ \t\xa0]+',' ',t)
    return [l.strip() for l in t.split('\n') if l.strip()]
def num(s):
    m=re.search(r'\d*\.?\d+',s); return float(m.group(0)) if m else None
def stat_line(s):
    """Return (pts,reb,ast,mpg) from a slash projection line; label-aware."""
    mpg=None
    m=re.search(r':\s*(\d+(\.\d+)?)\s*$',s)
    if m: mpg=float(m.group(1)); s=s[:m.start()]
    parts=[p.strip() for p in s.split('/')]
    lab={}
    for p in parts:
        mm=re.match(r'([\d.]+)\s*([a-z%]+)',p.lower())
        if mm: lab[mm.group(2)]=float(mm.group(1))
    if 'pts' in lab:
        return lab.get('pts'),lab.get('rbd',lab.get('reb')),lab.get('ast'),mpg
    v=[num(p) for p in parts]
    if len(v)<6: return None,None,None,mpg
    return v[3],v[4],v[5],mpg
rows=[]
def add(year,url,ts,name,team,pts,reb,ast,mpg=None,g=None,rank=None):
    rows.append(dict(year=year,season=f'{year-1}-{str(year)[2:]}',source='Razzball',source_url=url,snapshot_timestamp=ts,
        published_name=name.strip(' –-'),team=team or '',expected_PTS=pts,expected_TRB=reb,expected_AST=ast,
        expected_MPG='' if mpg is None else mpg,expected_G='' if g is None else g,published_rank=rank or ''))
R='http://basketball.razzball.com/'
# 2010-11: roto top-100 table + top 101-200 page
L=text('2011_roto100.htm'); i=L.index('TOV')+1
while i+12<len(L):
    rank=re.match(r'(\d+)',L[i]).group(1); name=L[i+2]; v=L[i+4:i+13]
    add(2011,R+'files/2010/09/2010-Roto-Fantasy-Top-100-10-16-10.htm','20150913 (file dated 2010-10-16)',name,'',float(v[3]),float(v[4]),float(v[5]),rank=rank); i+=13
def numbered(year,f,url,ts):
    L=text(f); pend=None
    for l in L:
        m=re.match(r'^(\d{1,3})\s*\.\s*\d?\s*(.*)$',l)
        if m and re.match(r'[A-Z]',m.group(2)):
            rank,body=m.groups()
            sm=re.match(r'^(.+?)(?:\s*–\s*|\s+-\s*|\s*:\s+)(.*)$',body)
            if sm and len(sm.group(1).split())<=4: name,rest=sm.groups()
            else: name=' '.join(body.split()[:2]); rest=body
            pend=(rank,name)
            name=re.sub(r'\s*\(.*?\)','',name)
            pm=re.search(r'(?:Projections?|Predictions?):\s*(.+)$',rest) or re.search(r'(\.\d{3}\s*fg\s*/.+)$',rest)
            if pm: add(year,url,ts,name,'',*stat_line(pm.group(1)),rank=rank); pend=None
        elif pend and re.match(r'^Season (Projections?|Predictions?):',l):
            add(year,url,ts,pend[1],'',*stat_line(l.split(':',1)[1]),rank=pend[0]); pend=None
numbered(2011,'2011_top200.html',R+'fantasy-basketball-2010-top-200','20100928')
numbered(2012,'2012_top100.html',R+'2011-fantasy-basketball-top-100','20120110231349')
numbered(2012,'2012_top200.html',R+'2011-top-200-fantasy-basketball-rankings','20120111005247')
numbered(2013,'2013_top100.html',R+'2012-2013-fantasy-basketball-rankings-the-top-100','20121025010340')
numbered(2013,'2013_top200.html',R+'2012-2013-fantasy-basketball-rankings-the-top-200','20121024024015')
# 2014-15..2016-17 official top 200 with Slim's projection
for year,f,u,ts in [(2015,'2015_official.html','official-razzball-2014-2015-fantasy-basketball-rankings','20141020100353'),
                    (2016,'2016_official.html','official-razzball-2015-2016-fantasy-basketball-rankings','20151026054643'),
                    (2017,'2017_official.html','official-razzball-2016-2017-fantasy-basketball-rankings','20161023062357')]:
    L=text(f)
    for k,l in enumerate(L):
        if l.startswith('Slim’s Projection:') and k+1<len(L):
            j=k-1
            while j>k-10 and not re.match(r'^[↑↓⇑⇓]?\s*\d{1,3}\s*[↑↓⇑⇓]?$',L[j]): j-=1
            if not re.match(r'^[↑↓⇑⇓]?\s*\d{1,3}\s*[↑↓⇑⇓]?$',L[j]): continue
            nm=re.sub(r'\s*\(\d+\)$','',L[j+1]); name,_,team=nm.rpartition(',')
            add(year,R+u,ts,name,team.strip(),*stat_line(L[k+1]),rank=re.sub(r'\D','',L[j]))
# tables
def table(f):
    t=open(os.path.join(S,f),encoding='utf-8',errors='replace').read()
    out=[]
    for tr in re.findall(r'(?s)<tr.*?</tr>',t):
        out.append([html.unescape(re.sub(r'<[^>]+>','',c)).strip() for c in re.findall(r'(?s)<t[dh][^>]*>(.*?)</t[dh]>',tr)])
    return out
T=table('2018_sortable.html'); hdr=None
for r in T:
    if 'PTS' in r and 'Name' in r: hdr=r; continue
    if hdr and len(r)==len(hdr) and r[hdr.index('Name')]:
        d=dict(zip(hdr,r)); add(2018,R+'fantasy-basketball-updated-top-200-with-sortable-stats','20171011031019',d['Name'],'',float(d['PTS']),float(d['TRB']),float(d['AST']),float(d['MP']) if d['MP'] else None,rank=d.get('#') or str(sum(1 for x in rows if x['year']==2018)+1))
T=table('2019_top155.html'); hdr=None
for r in T:
    if 'PTS' in r and 'NAME' in r: hdr=r; continue
    if hdr and len(r)==len(hdr) and r[1]:
        d=dict(zip(hdr,r)); add(2019,'https://basketball.razzball.com/fantasy-basketball-top-155-roto-projections','20190721170740 (article dated 2018-09-07)',d['NAME'],'',float(d['PTS']),float(d['REB']),float(d['AST']),rank=d['#'])
# dedupe within year (keep first = best rank list order)
seen=set(); final=[]
for r in rows:
    if r['expected_PTS'] is None: continue
    k=(r['year'],r['published_name'].lower())
    if k in seen: continue
    seen.add(k); final.append(r)
with open(OUT,'w',newline='') as fh:
    w=csv.DictWriter(fh,fieldnames=list(final[0])); w.writeheader(); w.writerows(final)
from collections import Counter
print(Counter(r['year'] for r in final), 'dupes dropped', len(rows)-len(final))
