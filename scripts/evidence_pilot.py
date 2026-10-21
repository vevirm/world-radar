"""Safe, non-publishing 30-case quality pilot for Radar 2.

Usage:
  python scripts/evidence_pilot.py --mode offline  # no API calls
  python scripts/evidence_pilot.py --mode live     # at most 12 requests / 3 cases

Writes only EVIDENCE-PILOT*.md/json. Never touches the atlas or Word reports.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import time
try:
    from .evidence_engine import discover,evaluate,SearchBudget,profile,_concepts,_words
except ImportError:
    from evidence_engine import discover,evaluate,SearchBudget,profile,_concepts,_words

ROOT=Path(__file__).resolve().parents[1]
TARGETS=[
    'The Future of Internationalization of Higher Education in Europe',
    'European scenarios for exposure of soil organisms to pesticides',
    'Analysis of uncertainty in large scale climate change projections over Europe',
    'Active ageing: A strategic policy solution to demographic ageing',
    'Forest policy in Europe and 2020 scenarios',
    'Carbon capture & storage in power generation',
    'Foresight and “grand challenges” within research',
    'How far away is hydrogen?',
    'Long-term projections and acclimatization scenarios of temperature-related mortality',
    'Security of Supply in European Electricity Markets',
    'Lyme borreliosis in Europe',
    'Ocean energy development in Europe',
    'Suitability of European climate for the Asian tiger mosquito',
    'Scenarios on European energy security',
    'Digital Europe 2030: Designing scenarios',
    'Impact of climate change on ozone-related mortality',
    'European scenarios for exposure of soil organisms',
    'Foresight of evolving security threats',
    'Modelling the Economic Impacts of Climate Change on Global and European Agriculture',
    'Flood risk and climate change: global and regional perspectives',
    'The impact of EU Climate/Energy policies on Belgium',
    'Demographic Epidemiologic Projections of Long-Term Care Needs',
    'Innovation Policy and Evaluating Their Performance',
    'European scenarios for exposure of soil organisms',
    'Population and Demographic Trends',
    'A comparison of oil supply risks in EU',
    'How climate, migration ability and habitat fragmentation',
    'The CIRCE Simulations: Regional Climate Change Projections',
    'Regional Economic Performance and Wage Distribution',
    'Management of Mass Casualties and Associated Health Effects',
    'Climate change, extreme weather events, air pollution',
]

def claim_from(lead):
    url=lead.get('url') or lead.get('doi') or ''
    return {'id':'lead-'+hashlib.sha256(url.lower().rstrip('/').encode()).hexdigest()[:16],
            'title':lead.get('title') or '', 'expected':lead.get('abstract') or lead.get('title') or '',
            'source_url':url, 'original_publication':lead.get('date') or ''}


def cases(leads,n=30):
    found=[]; used=set()
    for needle in TARGETS:
        for lead in leads:
            if needle.casefold() in (lead.get('title') or '').casefold():
                u=lead.get('url')
                if u not in used:
                    found.append(lead);used.add(u)
                    break
        if len(found)>=n: return found
    # Finish with a stable spread of original years instead of just 2011.
    for lead in sorted(leads,key=lambda a:(a.get('date') or '', a.get('title') or '')):
        u=lead.get('url')
        if u and u not in used:
            found.append(lead);used.add(u)
        if len(found)>=n:break
    return found


def compact(item):
    return {'title':item.get('title'), 'year':item.get('year'), 'url':item.get('url'),
            'route':item.get('discovery'), 'kind':item.get('evidence_kind'),
            'fit':item.get('question_fit_score'),
            'why':item.get('question_fit_basis'),
            'finding':item.get('finding_from_abstract')}


def build_report(mode,selected,leads,budget):
    results=[]
    live=mode=='live'
    # Cache the fast prefilter so a 30-case pilot won't compare 40,000 full
    # abstract/title pairs. This is a screening preview, not exhaustive recall.
    prefiltered=[(lead, _concepts((lead.get('title') or '')+' '+(lead.get('abstract') or '')),
                    _words(lead.get('title') or ''),
                    (lead.get('date') or '')[:4]) for lead in leads] if not live else []
    for k,lead in enumerate(selected,1):
        claim=claim_from(lead)
        if live:
            if not budget.available():break
            answer=discover(claim,budget=budget)
            matching=answer['results']
            routes=answer['routes']
        else:
            # Corpus-only comparison of existing indexed publications. This
            # helps test screening but is not a simulation of semantic API.
            matching=[]
            p=profile(claim)
            original_year=(claim['original_publication'] or '')[:4]
            for other,concepts,terms,new_year in prefiltered:
                if other.get('url')==lead.get('url') or new_year<=original_year:continue
                if not (p['title_concepts'] & concepts or len(p['title_words'] & terms)>=2):
                    continue
                w={'title':other.get('title'),'abstract':other.get('abstract'),
                   'doi':other.get('url'),'publication_date':other.get('date')}
                x=evaluate(claim,w,discovery='indexed_catalogue_pilot')
                if x:matching.append(x)
            matching=sorted(matching,key=lambda r:(r.get('question_fit_score') or 0,r.get('year') or 0),reverse=True)[:5]
            routes=[{'route':'already_indexed_catalogue','results':len(leads)}]
        results.append({'case':k,'original':claim['title'],
                        'year':claim['original_publication'][:4],
                        'original_url':claim['source_url'],
                        'profile_concepts':sorted(profile(claim)['title_concepts']),
                        'routes':routes,'matches':[compact(v) for v in matching[:5]]})
        print(f'{mode} pilot {k}: {claim["title"][:65]} → {len(matching)} relevant trails',flush=True)
    return {'generated_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'mode':mode, 'method':'question-first, abstract/title metadata screening only',
            'live_api_calls':budget.calls if live else 0,
            'live_successful_calls':budget.successful_calls if live else 0,
            'raw_openalex_works_returned':budget.returned_works if live else 0,
            'api_errors':budget.errors if live else [],
            'records_tested':len(results),
            'records_with_matches':sum(bool(v['matches']) for v in results),
            'caveat':('Live OpenAlex retrieval, NOT verification of historical outcomes.' if live else
                'Existing indexed publications only; this cannot establish live retrieval coverage.'),
            'items':results}


def write_report(result,mode):
    out=ROOT/('EVIDENCE-PILOT-LIVE' if mode=='live' else 'EVIDENCE-PILOT-OFFLINE')
    out.with_suffix('.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    lines=['# Radar 2: question-first evidence pilot','',
           f"**Mode:** {mode} · **Cases:** {result['records_tested']} · **With possible trails:** {result['records_with_matches']} · **API calls:** {result['live_api_calls']}",
           f"**Raw OpenAlex results:** {result['raw_openalex_works_returned']} · **Successful API responses:** {result['live_successful_calls']} · **API errors:** {len(result['api_errors'])}",
           '', '**Important:** matches are developments in *published research*, not proven real-world outcomes.',
           result['caveat'],'']
    if result['api_errors']:
        lines.extend(['', '## OpenAlex errors (not missing research)', ''])
        for e in result['api_errors'][:15]:
            lines.append(f"- {e['route']}: {e['status']} — {e['reason']}")
        lines.append('')
    for record in result['items']:
        lines.append(f"## {record['case']:02d}. {record['original']} ({record['year']})")
        lines.append(f"Original: {record['original_url']}")
        if record['matches']:
            for item in record['matches'][:3]:
                lines.append(f"- **{item['year']}: {item['title']}** — {item['kind']}; question fit {item['fit']} (not an accuracy rating). [{item['route']}] {item['url']}")
                if item.get('finding'):lines.append('  - Reported by abstract: '+item['finding'][:260])
        else:
            lines.append('- No sufficiently connected paper in this search; not evidence the topic has expired.')
        lines.append('')
    out.with_suffix('.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    path=os.environ.get('GITHUB_STEP_SUMMARY')
    if path:
        with open(path,'a',encoding='utf-8') as f:
            f.write('\n'.join(lines[:7])+f'\nFull cases are in the **EVIDENCE-PILOT** artifact.\n')
    print('Wrote',out.with_suffix('.md'))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--mode',choices=('offline','live'),default='offline')
    p.add_argument('--max-cases',type=int,default=30)
    a=p.parse_args()
    leads=json.loads((ROOT/'research-leads.json').read_text(encoding='utf-8')).get('leads',[])
    if a.mode=='live':
        if a.max_cases>3:raise SystemExit('The live pilot is deliberately capped at 3 cases.')
        # Hard time/request cap; deliberately never runs 25 minutes.
        budget=SearchBudget(max_requests=12,deadline=time.monotonic()+150)
    else:
        budget=SearchBudget(max_requests=0)
    selected=cases(leads,min(max(1,a.max_cases), 3 if a.mode=='live' else 30))
    result=build_report(a.mode,selected,leads,budget)
    write_report(result,a.mode)
    if a.mode=='live' and any(e.get('status') == 'HTTP 400' for e in result['api_errors']):
        raise SystemExit('PILOT FAILED: OpenAlex rejected at least one search parameter (HTTP 400). Review EVIDENCE-PILOT-LIVE.md; do NOT activate the scanner.')
    if a.mode=='live' and result['raw_openalex_works_returned']==0:
        raise SystemExit('PILOT FAILED: OpenAlex returned zero raw works across all routes. Check API errors in EVIDENCE-PILOT-LIVE.md and Actions log; do NOT activate the scanner.')
    if a.mode=='live' and result['records_with_matches']==0:
        raise SystemExit('PILOT INCONCLUSIVE: OpenAlex returned publications, but none were sufficiently connected to the three questions. Review EVIDENCE-PILOT-LIVE.md before activating Scanner 2.')

if __name__=='__main__': main()
