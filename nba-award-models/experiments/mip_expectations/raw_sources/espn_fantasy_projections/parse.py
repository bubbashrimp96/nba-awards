import re,html,glob,json,os,sys
from collections import Counter
def text(s):
  t=re.sub(r'<script.*?</script>|<style.*?</style>','',s,flags=re.S|re.I)
  t=html.unescape(re.sub(r'<[^>]+>','|',t)); t=re.sub(r'\|\s*(\|\s*)+','|',t); return re.sub(r'[ \t\r\n]+',' ',t)
NUM=re.compile(r'^(--|-?[\d.]+)$')
def parse(path):
  s=open(path,encoding='utf-8',errors='replace').read(); t=text(s)
  m=re.search(r'Complete (\d{4}) Projections',t) or re.search(r'(\d{4}) SEASON PROJECTIONS',t) or re.search(r'PROJECTED (\d{4}) SEASON',t) or re.search(r'(\d{4}) SEASON Statistics PROJECTIONS',t)
  hy=int(m.group(1)) if m else None
  toks=[x.strip() for x in t.split('|')]
  rows=[]
  # alt blocks
  for i,x in enumerate(toks):
    if x=='YEAR' and i>=2:
      # name/team: look back for ', Tm POS' token
      j=i-1
      while j>0 and not toks[j].startswith(','): j-=1
      if i-j>3: continue
      name=toks[j-1].rstrip('*').strip()
      if name=='*': name=toks[j-2].strip()
      tm=toks[j][1:].strip().split(' ')[0]
      hdr=[];k=i+1
      while k<len(toks) and not re.match(r'\d{4} (Statistics|Projections)',toks[k]): hdr.append(toks[k]);k+=1
      # find projections line
      while k<len(toks) and k<i+80 and not re.match(r'\d{4} Projections',toks[k]): k+=1
      if k>=len(toks) or not re.match(r'\d{4} Projections',toks[k]): continue
      py=int(toks[k][:4]); vals=toks[k+1:k+1+len(hdr)]
      if len(vals)<len(hdr) or not all(NUM.match(v) for v in vals): continue
      d=dict(zip(hdr,vals))
      if d.get('PTS','--')=='--': continue
      rows.append(dict(fmt='alt',published_name=name,team=tm,proj_year=py,G=d.get('GP'),MPG=d.get('MIN'),PTS=d.get('PTS'),TRB=d.get('REB'),AST=d.get('AST')))
  if rows: return hy,rows,t
  # default table
  try: i=toks.index('RNK')
  except ValueError: return hy,rows,t
  hdr=[];k=i+1
  while k<len(toks) and not re.match(r'^\d+$',toks[k]): hdr.append(toks[k]);k+=1
  stat_hdr=[h for h in hdr if h not in('PLAYER',', TEAM POS','EVALUATION','PLAYER, TEAM POS')]
  while k<len(toks):
    if re.match(r'^\d+$',toks[k]) and k+2<len(toks) and toks[k+2].startswith(','):
      name=toks[k+1].rstrip('*').strip(); tm=toks[k+2][1:].strip().split(' ')[0]; m2=k+3
      if toks[m2] in ('DTD','O','SSPD','IR','Q','D','SUSP','GTD','P'): m2+=1
      vals=toks[m2:m2+len(stat_hdr)]
      if len(vals)==len(stat_hdr) and all(re.match(r'^-?[\d.]+$',v) for v in vals):
        d=dict(zip(stat_hdr,vals)); rows.append(dict(fmt='default',published_name=name,team=tm,proj_year=hy,G=d.get('GP'),MPG=d.get('MIN'),PTS=d.get('PTS'),TRB=d.get('REB'),AST=d.get('AST')))
        k=m2+len(stat_hdr); continue
    k+=1
  return hy,rows,t
if __name__=='__main__':
  c=Counter()
  for f in sorted(glob.glob('pages/*.html')):
    hy,rows,t=parse(f); y=int(os.path.basename(f)[:4])
    c[(y,os.path.basename(f).split('_')[1],hy,len(rows)>0, rows[0]['fmt'] if rows else '')]+=1
  for k,v in sorted(c.items(),key=str): print(k,v)
