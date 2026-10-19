"""Connect indexed discovery to the 10-minute checking phase.

Checks scholarly DOI/title/publication metadata against Crossref. This is an
actual recorded check, not a claim to have read a paywalled full paper, nor a
judgement that a future claim landed. Fulltext quality remains in radar.py.
"""
from datetime import datetime, timezone, timedelta, date
import re
import time
from pathlib import Path
from urllib.parse import quote
import requests
import json
from scholarly import normal_doi

ROOT=Path(__file__).resolve().parents[1]

def normal_title(s):
    return set(re.findall(r'[a-z0-9]{4,}', (s or '').lower()))

def check_indexed_leads(deadline, *, max_checks=28):
    p=ROOT/'research-leads.json'
    q=ROOT/'priority-50.json'
    if not p.exists() or not q.exists(): return {'checked':0,'reason':'no discovery records'}
    db=json.loads(p.read_text(encoding='utf-8'))
    shortlist=json.loads(q.read_text(encoding='utf-8'))['items']
    leads={x['doi']:x for x in db['leads'] if x.get('doi')}
    checked=0; passed=0; failed=0
    now=datetime.now(timezone.utc)
    # The ranking is the handoff: every shortlisted indexed DOI is a check job.
    for candidate in shortlist:
        if checked >= max_checks or time.monotonic() >= deadline-8: break
        doi=normal_doi(candidate.get('doi'))
        if not doi or doi not in leads: continue
        lead=leads[doi]
        last=lead.get('metadata_checked_at')
        if last:
            try:
                if datetime.fromisoformat(last) > now-timedelta(days=60): continue
            except ValueError: pass
        checked+=1
        try:
            response=requests.get('https://api.crossref.org/works/'+quote(doi,safe=''),
                timeout=(4,9), headers={'User-Agent':'European-Foresight-Radar/5.0 (historical DOI verification)'})
            response.raise_for_status()
            item=response.json()['message']
            title=(item.get('title') or [''])[0]
            overlap=normal_title(title)&normal_title(lead['title'])
            if len(overlap) < max(2,min(5,len(normal_title(lead['title']))//2)):
                raise ValueError('DOI resolves, but indexed and publisher titles differ')
            published=((item.get('published') or item.get('issued') or {}).get('date-parts') or [[]])[0]
            if not published or int(published[0]) != int(lead['date'][:4]):
                raise ValueError('DOI publication year disagrees with indexed year')
            lead['verification_status']='DOI + title + year cross-checked · full text not yet verified'
            lead['metadata_check_result']='passed'
            lead['metadata_error']=''
            passed+=1
        except (requests.RequestException, ValueError, KeyError, TypeError, IndexError) as exc:
            lead['verification_status']='Metadata cross-check inconclusive · full text unverified'
            lead['metadata_check_result']='inconclusive'
            lead['metadata_error']=str(exc)[:200]
            failed+=1
        lead['metadata_checked_at']=datetime.now(timezone.utc).isoformat()
        lead['metadata_check_attempts']=int(lead.get('metadata_check_attempts',0))+1
    if checked:
        db['leads']=list(leads.values())
        db['updated_at']=datetime.now(timezone.utc).isoformat()
        tmp=p.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(db,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        tmp.replace(p)
    return {'checked':checked,'passed':passed,'inconclusive':failed,'metadata_only':True}
