"""25-minute minimum draft source investigation, 4 historical future claims.

Research leads and actual page fetches are logged; no outcome is inferred.
"""
import argparse
from collections import defaultdict
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import time

from radar2_rolling import ROOT, STATE_FILE, load_state, prepare, choose_batch
from radar2_broad_search import source_queries, fetch_json, extract, later, terms, query_for
from radar2_deep_search import read_page
from radar2_source_selection import select_source

OUTPUT = 'RADAR2-25MIN-RESEARCH.json'
MARKDOWN = 'RADAR2-25MIN-RESEARCH.md'

def build_case(claim):
    """Carry the source-backed future question, unchanged, into later research."""
    card = claim.get('question_card') or {}
    passage = str(claim.get('original_passage') or card.get('original_passage') or '')
    if not passage.strip():
        raise ValueError('Missing original passage: cannot research title alone')
    return {'original_id':claim['id'], 'title':claim['title'],
            'query':query_for(claim), 'original_publication':claim['original_publication'],
            'original_passage':passage,
            'original_source':card.get('original_source') or claim.get('source_url'),
            'question_card':card,
            'readings':[], 'errors':[], 'screened_out':0,
            '_seen':set(), '_anchor':set(terms(claim['title']))}


def paged_params(source, params, page):
    p = dict(params)
    if source == 'openalex': p['page'] = page
    elif source == 'crossref': p['offset'] = (page - 1) * int(p['rows'])
    else: p['page'] = page
    return p

def save(root, report):
    report['updated_utc'] = datetime.now(timezone.utc).isoformat()
    (root / OUTPUT).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# Radar 2 — minimum 25-minute investigation', '',
             '**Unverified research draft. No outcomes published.**', '',
             f"Elapsed: {report['elapsed_seconds']/60:.1f} minutes; rounds: {report['rounds']}; source reads attempted: {report['total_reads']}; successful document reads: {report['pages_read']}.",
             '', '## Claims', '']
    for c in report['cases']:
        lines += [f"### {c['title']}", f"Original: {c['original_id']}; search: {c['query']}; attempted reads: {len(c['readings'])}", '']
        lines.append('Original source passage: ' + c['original_passage'])
        lines.append('')
        for r in c['readings']:
            lines.append(f"- {r['status']} — [{r['title']}]({r['url']}) ({r['published']}; {r['index']})")
            if r.get('excerpt'): lines.append(f"  - Extracted: {r['excerpt'][:700]}")
        for err in c['errors']:
            lines.append(f"- Search error: {err['source']} page {err['page']}: {err['error']}")
        lines.append('')
    (root / MARKDOWN).write_text('\n'.join(lines), encoding='utf-8')

def research(root=ROOT, *, minutes=25, batch_size=4, clock=time.monotonic, pause=time.sleep,
             fetcher=fetch_json, reader=read_page, max_rounds=None):
    root=Path(root)
    ready, coverage = prepare(root, broad=True)
    selected = choose_batch(ready,load_state(root/STATE_FILE),n=batch_size,today=date.today())
    if not selected: raise RuntimeError('No eligible claims to investigate')
    api_key=os.environ.get('OPENALEX_API_KEY','')
    cases=[]
    for claim in selected:
        cases.append(build_case(claim))
    started=clock()
    report={'mode':'deep_25min', 'minimum_minutes_requested':minutes, 'publication_allowed':False,
            'verified_outcomes':0, 'coverage':coverage, 'rounds':0,'elapsed_seconds':0,
            'total_reads':0, 'pages_read':0, 'cases':cases}
    # URLs are unique per claim. Paginate three independent indexes continuously;
    # source count is not capped at 50. Pace the loop to avoid hammering public APIs.
    try:
        while clock()-started < minutes*60:
            page=report['rounds']+1
            for claim, case in zip(selected,cases):
                q=case['query']
                if len(q.split())<2:
                    case['errors'].append({'source':'query','page':page,'error':'insufficient_specific_terms'})
                    continue
                for source,url,params in source_queries(q,int(claim['original_publication'][:4])+1,api_key):
                    try:
                        payload=fetcher(url,paged_params(source,params,page))
                        for item in extract(source,payload):
                            address=str(item.get('url') or '')
                            if address in case['_seen']:
                                continue
                            case['_seen'].add(address)
                            keep, reason = select_source(claim, item)
                            if not keep:
                                case['screened_out'] += 1
                                continue
                            if len(case['readings']) >= 30:
                                continue
                            outcome=reader(address)
                            row={'index':source,'url':address,'title':item.get('title'),
                                 'published':item.get('date'),'connection_status':'metadata_screened_pending_full_text',
                                 'selection_reason':reason, 'geographic_match':'not_assessed',
                                 'observed_development_confirmed':False, **outcome}
                            case['readings'].append(row)
                            report['total_reads']+=1
                            if outcome.get('status')=='page_text_read':report['pages_read']+=1
                    except Exception as exc:
                        case['errors'].append({'source':source,'page':page,'error':type(exc).__name__+': '+str(exc)[:160]})
            report['rounds']+=1
            report['elapsed_seconds']=clock()-started
            # Keep crash/restart artifacts and visibility of network failures.
            for case in cases:
                case['_seen_list']=sorted(case['_seen'])
            serializable={**report,'cases':[{k:v for k,v in c.items() if not k.startswith('_')} for c in cases]}
            save(root,serializable)
            if max_rounds is not None and report['rounds']>=max_rounds:break  # tests only
            remaining=minutes*60-(clock()-started)
            if remaining>0:pause(min(10,remaining))
    finally:
        report['elapsed_seconds']=clock()-started
        serializable={**report,'cases':[{k:v for k,v in c.items() if not k.startswith('_')} for c in cases]}
        save(root,serializable)
    return serializable

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--minutes',type=float,default=25)
    p.add_argument('--batch-size',type=int,default=4)
    a=p.parse_args()
    if a.minutes<25: p.error('Minimum research window is 25 minutes')
    if a.batch_size!=4:p.error('This pilot investigates exactly four claims')
    r=research(minutes=a.minutes,batch_size=a.batch_size)
    print(f"Research ended: {r['elapsed_seconds']/60:.1f} min, {r['total_reads']} reading attempts, {r['pages_read']} readable sources; no verification.")
