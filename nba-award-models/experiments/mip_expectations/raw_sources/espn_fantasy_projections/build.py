import glob,os,csv,json,re
import parse
SEASON=lambda y:f'{y-1}-{str(y)[2:]}'
urlmap={}
for l in open('jobs.txt'): t,u,f=l.split(); urlmap[f]=(t,u)
for l in open('jobs2.txt'): t,u,f=l.split(); urlmap[f]=(t,u)
best={}; stats={}
for f in sorted(glob.glob('pages/*.html')):
  y=int(os.path.basename(f)[:4])+1  # preseason year -> season end year
  hy,rows,_=parse.parse(f)
  t,u=urlmap.get(f,(os.path.basename(f).split('_')[2],''))
  for r in rows:
    if r['proj_year']!=y: continue
    pts=float(r['PTS'])
    totals = r['fmt']=='default' and pts>60
    rank=(1 if r['fmt']=='alt' else 0, 0 if totals else 1, t)
    k=(y,r['published_name'])
    rec=dict(year=y,season=SEASON(y),source='espn_fantasy_projections',source_url='http://web.archive.org/web/'+t+'/'+u,snapshot_timestamp=t,published_name=r['published_name'],team=r['team'],
      expected_PTS=r['PTS'],expected_TRB=r['TRB'],expected_AST=r['AST'],expected_MPG=r['MPG'] or '',expected_G=(r['G'] if r['G'] not in (None,'0','--') else ''),_totals=totals,_fmt=r['fmt'])
    if k not in best or rank>best[k][0]: best[k]=(rank,rec)
out=[];skipped={}
for (y,n),(rank,rec) in sorted(best.items()):
  if rec['_totals']:
    if rec['expected_G']:
      g=float(rec['expected_G'])
      for c in ('expected_PTS','expected_TRB','expected_AST'): rec[c]=f'{float(rec[c])/g:.2f}'
    else:
      skipped[y]=skipped.get(y,0)+1; continue
  out.append(rec)
os.makedirs(os.path.dirname(os.environ['OUT']),exist_ok=True)
cols=['year','season','source','source_url','snapshot_timestamp','published_name','team','expected_PTS','expected_TRB','expected_AST','expected_MPG','expected_G']
with open(os.environ['OUT'],'w',newline='') as fh:
  w=csv.DictWriter(fh,cols,extrasaction='ignore'); w.writeheader(); w.writerows(out)
from collections import Counter
c=Counter(r['year'] for r in out); fm=Counter((r['year'],r['_fmt']) for r in out)
for y in sorted(c): print(y,SEASON(y),c[y],dict((k[1],v) for k,v in fm.items() if k[0]==y),'snapshots',min(r['snapshot_timestamp'] for r in out if r['year']==y)[:8],'-',max(r['snapshot_timestamp'] for r in out if r['year']==y)[:8],'skipped_totals_noG',skipped.get(y,0))
