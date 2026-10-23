#!/usr/bin/env python3
"""EU Futures Observatory: cumulative, provisional claim-to-literature discovery.
Never interprets a candidate source as evidence of a realised outcome.
"""
import argparse, hashlib, json, os, re, time, urllib.parse, urllib.request, zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

ROOT=Path(__file__).resolve().parents[1]
STOP=set('a an and are as at be been being by can could do for from had has have how if in into is it its may might more most of on or our should some such than that the their these this through to toward towards under using was were what when where which while will with would year years study studies research report paper results evidence analysis future futures forecasting forecast scenarios scenario projection projected long term eu european europe'.split())
SYNONYMS={
 'aviation':['aviation','aircraft','airline','jet','flight','saf'],
 'fuel':['fuel','biofuel','kerosene','e-fuel','saf','sustainable aviation'],
 'carbon':['carbon','co2','emissions','emission','greenhouse','ghg'],
 'pricing':['pricing','price','prices','trading','ets','allowance','tax'],
 'flood':['flood','flooding','inundation'],
 'energy':['energy','electricity','power'],
 'hydrogen':['hydrogen','h2'],
 'demographic':['demographic','population','ageing','aging'],
 'employment':['employment','labour','labor','jobs','workforce'],
 'renewable':['renewable','solar','wind','clean energy'],
}
EU_RE=re.compile(r'\b(europe|european|eu|eurostat|eu-\d+|european union|\b(?:finland|germany|france|italy|spain|sweden|poland|netherlands|belgium|portugal|ireland|greece|austria|denmark|norway|estonia|latvia|lithuania|czechia|slovakia|slovenia|croatia|romania|bulgaria|hungary|cyprus|malta|luxembourg)\b)\b',re.I)

def words(s):return re.findall(r'[a-z][a-z0-9-]{2,}',(s or '').lower())
def keywords(s,limit=12):
 result=[]
 for w in words(s):
  if w not in STOP and not w.isnumeric() and w not in result:result.append(w)
 return result[:limit]
def jsonread(path,default):
 try:return json.loads(Path(path).read_text(encoding='utf8'))
 except (FileNotFoundError,ValueError):return default

def claims():
 data=jsonread(ROOT/'research-leads.json',{}).get('leads',[])
 output=[]
 for x in data:
  date=(x.get('date') or '')[:10]
  if not ('2011-01-01'<=date<'2023-01-01'):continue
  if x.get('radar1_selection') not in ('active',None):continue
  seed=x.get('radar2_seed') or {}; passage=(seed.get('original_passage') or '').strip()
  if len(passage)<45:continue
  # Original excerpts from abstracts remain explicitly labelled as provisional excerpts.
  identity=x.get('doi') or x.get('url') or x.get('title')
  ident='claim-'+hashlib.sha256((identity+'|'+passage).encode()).hexdigest()[:16]
  output.append({'id':ident,'title':x.get('title',''),'year':int(date[:4]),'date':date,
    'original_claim':passage,'source_url':x.get('url',''),'doi':x.get('doi',''),
    'source_status':seed.get('source_status','unverified'),'theme':x.get('foresight_scope','') or '',
    'source_field':seed.get('source_field','unknown'),'review_status':'source excerpt not independently verified'})
 return output

def anchors(claim):
 raw=claim['original_claim']+' '+claim['title']
 terms=keywords(raw,32)
 # less weight to title; must have genuine anchor terms from original proposition
 base=keywords(claim['original_claim'],18)
 return list(dict.fromkeys(base+terms))[:18]

def queries(claim):
 a=anchors(claim)
 if not a:return []
 # use short, differentiated semantically meaningful fragments, not title prefixes.
 group=a[:4]; extra=[x for x in a[4:] if x not in group]
 region='Europe' if EU_RE.search(claim['original_claim']+' '+claim['title']) else ''
 one=' '.join(group[:3]+([region] if region else []))
 two=' '.join((group[0:2]+extra[0:2])+([region] if region else []))
 return list(dict.fromkeys([one.strip(),two.strip()]))

def concept_sets(s):
 tokens=set(words(s)); sets=[]
 for name,terms in SYNONYMS.items():
  if name in tokens or any(t in s.lower() for t in terms):
   sets.append((name,terms))
 return sets

def compare(claim,paper):
 text=((paper.get('title') or '')+' '+(paper.get('abstract') or '')).lower()
 if not text.strip():return None
 original=(claim['original_claim']+' '+claim['title']).lower()
 if paper.get('year',0)<=claim['year']:return None
 claim_terms=keywords(claim['original_claim'],25)
 paper_terms=set(words(text))
 hits=[w for w in claim_terms if w in paper_terms]
 groups=concept_sets(original)
 group_hits=[name for name,alts in groups if any(re.search(r'(?<!\w)'+re.escape(alt)+r'(?!\w)',text) for alt in alts)]
 # The central object must match: a generic word like costs/supply alone is insufficient.
 generic={'cost','costs','supply','demand','prices','price','policy','economic','growth','change','changes','development','impact','effects','risk','risks','global','future','market','markets','model','models','new','social','public'}
 distinctive=[w for w in hits if w not in generic]
 if len(distinctive)<2 and not (group_hits and len(distinctive)>=1):return None
 if len(hits)<3 and len(group_hits)<2:return None
 claim_eu=bool(EU_RE.search(original)); paper_eu=bool(EU_RE.search(text))
 # Require European scope for a strong link; global/missing geography is review-only.
 rank='strong_candidate' if len(distinctive)>=3 and (not claim_eu or paper_eu) else 'possible_candidate'
 if claim_eu and not paper_eu:rank='possible_candidate'
 return {'rank':rank,'matched_terms':distinctive[:12],'concepts':group_hits,
   'geography_overlap':('eu_in_later_text' if paper_eu else 'eu_not_established' if claim_eu else 'not_required'),
   'reason':'Shared claim-specific concepts: '+', '.join(distinctive[:6])+'; '+('EU scope visible' if paper_eu else 'EU scope not established')+'. This is a provisional connection, not an outcome finding.'}

def fetch_openalex(q,after_year,limit=20):
 params={'search':q,'filter':f'from_publication_date:{after_year+1}-01-01,to_publication_date:2026-10-23','per-page':str(limit),'select':'id,doi,title,display_name,publication_year,primary_location,abstract_inverted_index'}
 url='https://api.openalex.org/works?'+urllib.parse.urlencode(params)
 req=urllib.request.Request(url,headers={'User-Agent':'EU-Futures-Observatory/1.0 (research; public sources)'})
 with urllib.request.urlopen(req,timeout=25) as response:raw=json.load(response)
 results=[]
 for p in raw.get('results',[]):
  inv=p.get('abstract_inverted_index') or {}; ordered=[]
  for token,locs in inv.items():
   for i in locs:ordered.append((i,token))
  abstract=' '.join(t for _,t in sorted(ordered))[:6000]
  loc=p.get('primary_location') or {}
  results.append({'id':p.get('id',''),'title':p.get('title') or p.get('display_name') or '',
      'year':p.get('publication_year') or 0,'doi':p.get('doi') or '',
      'url':p.get('doi') or p.get('id') or '', 'abstract':abstract,
      'landing_url':loc.get('landing_page_url') or '','source':'OpenAlex'})
 return results

def scan(minutes=10,max_claims=8,max_papers=20):
 start=time.monotonic(); pool=claims(); store=jsonread(ROOT/'observatory-data.json',{'schema_version':1,'claims':{},'connections':{},'history':[],'cursor':0})
 current={x['id']:x for x in pool};store['claims'].update(current)
 if not pool:raise RuntimeError('No eligible historical claim excerpts')
 cursor=int(store.get('cursor') or 0)%len(pool); processed=[]; errors=[]; tried=0; retained=0
 while len(processed)<max_claims and time.monotonic()-start<minutes*60-5:
  claim=pool[cursor];cursor=(cursor+1)%len(pool);processed.append(claim['id'])
  known={c.get('source_id') for c in store['connections'].values() if c.get('claim_id')==claim['id']}
  for q in queries(claim):
   if time.monotonic()-start>minutes*60-5:break
   try:candidates=fetch_openalex(q,claim['year'],max_papers)
   except Exception as e:errors.append({'claim_id':claim['id'],'query':q,'error':str(e)[:240]});continue
   tried+=len(candidates)
   for p in candidates:
    if p['id'] in known:continue
    rel=compare(claim,p)
    if rel is None:continue
    ident='link-'+hashlib.sha256((claim['id']+'|'+p['id']).encode()).hexdigest()[:18]
    store['connections'][ident]={'id':ident,'claim_id':claim['id'],'source_id':p['id'],'source_title':p['title'],
      'source_year':p['year'],'source_url':p['url'],'source_doi':p['doi'],'abstract':p['abstract'],
      'retrieved_by':q,'relevance':rel,'review_status':'unchecked','editorial_note':'',
      'collected_at':datetime.now(timezone.utc).isoformat()}
    known.add(p['id']);retained+=1
  if len(processed)>=len(pool):break
 store['cursor']=cursor
 store['history'].append({'at':datetime.now(timezone.utc).isoformat(),'processed_claims':len(processed),'candidates_seen':tried,'new_connections':retained,'errors':errors[:15]})
 store['history']=store['history'][-150:]
 (ROOT/'observatory-data.json').write_text(json.dumps(store,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print(json.dumps(store['history'][-1],indent=2))
 return store

def make_docx(path,title,subtitle,records):
 from docx import Document
 from docx.shared import Pt,Inches,RGBColor
 d=Document();sec=d.sections[0];sec.header.paragraphs[0].text='VV FUTURES  /  EUROPEAN FORESIGHT OBSERVATORY'
 d.add_heading(title,0);d.add_paragraph(subtitle)
 for head,paragraphs in records:
  d.add_heading(head,level=2)
  for text in paragraphs:d.add_paragraph(str(text))
 sec.footer.paragraphs[0].text='Research collection · Sources should be checked before publication as findings'
 d.save(path)

def build():
 store=jsonread(ROOT/'observatory-data.json',{'claims':{},'connections':{},'history':[]})
 store['claims'].update({x['id']:x for x in claims()})
 (ROOT/'observatory-data.json').write_text(json.dumps(store,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 claims0=list(store.get('claims',{}).values()); links=list(store.get('connections',{}).values())
 claims0.sort(key=lambda a:(-a['year'],a['title']));links.sort(key=lambda x:(x['claim_id'],-x['source_year']))
 from collections import defaultdict
 by=defaultdict(list)
 for p in links:by[p['claim_id']].append(p)
 # Do not put unchecked material into the editorial findings Word.
 reviewed=jsonread(ROOT/'reviewed-findings.json',{'findings':[]}).get('findings',[])
 make_docx(ROOT/'VV-FUTURES-REVIEWED-FINDINGS.docx','European futures: reviewed accounts',
   'Only manually reviewed, LLM-assisted narratives belong here. An empty collection is intentional: scanners never manufacture final interpretations.',
   [(f.get('title','Reviewed claim'),[f.get('original_claim',''),f.get('interpretation',''), 'Sources: '+', '.join(f.get('sources',[]))]) for f in reviewed] or [('No reviewed findings yet',['Upload the possible-connections dossier to an LLM, assess original and later sources, then add approved findings to reviewed-findings.json.'])])
 possible=[]
 for c in claims0:
  match=by[c['id']]
  if not match:continue
  paras=['Original source ('+str(c['year'])+'): '+c['source_url'], 'Original wording ('+c['source_field']+'; '+c['source_status']+'): '+c['original_claim']]
  for p in match[:12]:paras.extend([f"POSSIBLE {p['source_year']}: {p['source_title']} — {p['source_url']}",p['relevance']['reason'], 'Available abstract (not full text): '+(p['abstract'][:1400] or 'Unavailable')])
  possible.append((c['title'],paras))
 make_docx(ROOT/'VV-FUTURES-POSSIBLE-CONNECTIONS.docx','Possible connections — not checked',
   'Automatically collected claim-to-publication leads. These are NOT verified outcomes or final findings. Some may be irrelevant. Check original sources, scope and later evidence before interpretation.',
   possible or [('No candidate connections yet',['The automatic scanner has not yet retained candidate sources.'])])
 # Excel OOXML with two worksheets using standard library; URLs and originals kept.
 sheets=[('Claims',['Claim ID','Year','Original study','Original future wording','Original URL','Source status','Candidate count'],
  [[c['id'],c['year'],c['title'],c['original_claim'],c['source_url'],c['source_status'],len(by[c['id']])] for c in claims0]),
 ('Possible connections',['Connection ID','Claim ID','Original claim','Later publication','Year','URL','Ranking','EU scope','Reason for match','Abstract available','Review status','Search query'],
  [[p['id'],p['claim_id'],store['claims'].get(p['claim_id'],{}).get('original_claim',''),p['source_title'],p['source_year'],p['source_url'],p['relevance']['rank'],p['relevance']['geography_overlap'],p['relevance']['reason'],p['abstract'],p['review_status'],p['retrieved_by']] for p in links])]
 def cell(col,row,value):
  name='';k=col
  while True:
   name=chr(65+k%26)+name;k=k//26-1
   if k<0:break
  # Excel guard against formula injection
  val=str(value or '')
  if val.startswith(('=','+','-','@')):val="'"+val
  return f'<c r="{name}{row}" t="inlineStr"><is><t>{escape(val[:30000])}</t></is></c>'
 def xmlsheet(header,rows):
  rlist=[header]+rows
  body=''.join(f'<row r="{i}">'+''.join(cell(j,i,v) for j,v in enumerate(row))+'</row>' for i,row in enumerate(rlist,1))
  return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"/></sheetViews><sheetData>'+body+'</sheetData></worksheet>'
 with zipfile.ZipFile(ROOT/'VV-FUTURES-ALL-CLAIMS-AND-SOURCES.xlsx','w',zipfile.ZIP_DEFLATED) as z:
  z.writestr('[Content_Types].xml','<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'+''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in (1,2))+'</Types>')
  z.writestr('_rels/.rels','<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
  z.writestr('xl/workbook.xml','<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Claims" sheetId="1" r:id="rId1"/><sheet name="Possible connections" sheetId="2" r:id="rId2"/></sheets></workbook>')
  z.writestr('xl/_rels/workbook.xml.rels','<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/></Relationships>')
  for i,(_,head,rows) in enumerate(sheets,1):z.writestr(f'xl/worksheets/sheet{i}.xml',xmlsheet(head,rows))
 print('Built',len(claims0),'claims,',len(links),'candidate connections,',len(reviewed),'reviewed accounts')

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('command',choices=['scan','build']);parser.add_argument('--minutes',type=float,default=10);parser.add_argument('--claims',type=int,default=8)
 args=parser.parse_args()
 if args.command=='scan':scan(args.minutes,args.claims);build()
 else:build()
