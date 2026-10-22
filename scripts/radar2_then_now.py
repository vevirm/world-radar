#!/usr/bin/env python3
"""Radar 2: ONE accepted Radar 1 claim -> TWO later official sources -> warranted link.

A deliberately small, audit-friendly, *live page reading* pilot. It does not
publish, does not invent evidence, and does not treat adjacent measures as the
forecast outcome. New subjects need new tested source routes. This is not an LLM.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.request
from urllib.parse import urlsplit

try:
    from .radar2_scope import original_claims
except ImportError:
    from radar2_scope import original_claims

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 2_000_000
ALLOWED_HOSTS = frozenset({'www.eea.europa.eu', 'www.easa.europa.eu',
                           'www.austriatech.at', 'austriatech.at', 'eea.europa.eu', 'easa.europa.eu', 'atech-web04.austriatech.at'})

# Small, explicit, source-VERIFIED connector catalogue: the pilot selects its
# ORIGINALS automatically from Radar 1. It then follows two known official
# observation sources for each matching *question family*.
# This is not an arbitrary web keyword search, nor a general 629-study engine.
ROUTES = (
    {
      'id':'europe_flood_damage',
      'original_gate':(r'\bflood',r'\bdamag|\bloss'),
      'question':'How do observed European flood-related economic losses develop relative to the earlier flood-damage scenarios?',
      'source_gate':(r'\bflood|\bhydrolog',r'\bloss|\bdamag|\bkosten'),
      'observed_gate':r'\b(?:1980|202[0-6]|floods account|hydrological hazards|hydrological events|annual economic losses|observed)\b',
      'scope':'EEA estimates cover observed hazards and particular price/territorial definitions; flood-only economic loss must be distinguished from ALL-weather losses. The 2050/2080 projections remain in the future; scenario assumptions and EUR price base are not checked here.',
      'relation':'related_observed_development_not_comparable_projection',
      'sources':(
         ('EEA economic-loss indicator','2025','https://www.eea.europa.eu/en/analysis/indicators/economic-losses-from-climate-related'),
         ('EEA economic-loss briefing','2025','https://www.eea.europa.eu/en/analysis/publications/economic-losses-from-climate-extremes'),
      )},
    {
      'id':'eu_renewable_jet_fuel',
      'original_gate':(r'\b(?:jet fuel|aviation fuel|rjf)\b',r'\b(?:supply|production|feedstock)\b'),
      'question':'How did actual EU sustainable aviation fuel supply and production develop relative to scenarios for non-food renewable jet-fuel production?',
      'source_gate':(r'\b(?:aviation fuel|jet fuel|SAF|renewable fuel)\b',r'\b(?:suppli|supply|supplied|production|produced|tonnes|kilotonnes)\b'),
      'observed_gate':r'\b(?:2024|2025|supply rose|reported|supplied|purchased|produced)\b',
      'scope':'SAF supplied at Union airports is not equivalent to EU-produced non-food RJF; feedstock origin, technology, energy units, geography and the still-future 2030 horizon differ. Policy mandates are not evidence the original conditional supply projection occurred.',
      'relation':'observed_sector_development_different_metric',
      'sources':(
         ('EASA ReFuelEU 2026 monitoring','2026-09-17','https://www.easa.europa.eu/en/newsroom-and-events/press-releases/eu-sustainable-aviation-fuel-supply-exceeds-2025-refueleu-aviation-target'),
         ('EASA ReFuelEU 2025 baseline','2025-10-22','https://www.easa.europa.eu/en/newsroom-and-events/press-releases/easa-publishes-report-sustainable-aviation-fuel-scale-progress'),
      )},
    {
      'id':'austria_automated_mobility',
      'original_gate':(r'\b(?:automated mobility|autonomous (?:vehicle|transport))\b',r'\baustria'),
      'question':'Was automated mobility actually trialled or deployed in Austria, and is there evidence of the predicted shift in private traffic and transport modes?',
      'source_gate':(r'\b(?:automatisier\w*|automated|autonomous|testfahrten|testantr.ge)\b',r'\b(?:mobilit.t|mobility|fahrzeug\w*|vehicles|test\w*|shuttle|verkehr\w*)\b'),
      'observed_gate':r'\b(?:2024|2025|2026|testfahrten|testantr.ge|testfahrten|testbetrieb|trial|tested)\b',
      'scope':'Austrian automated-vehicle trials establish technological activity, NOT nationwide increases in car travel or displacement of walking, cycling or transit. Those modal outcomes and the original policy conditions require separate post-deployment measurements.',
      'relation':'implementation_observed_central_traffic_effect_unestablished',
      'sources':(
         ('AustriaTech automated mobility monitoring 2025','2026-03-05','https://www.austriatech.at/de/monitoringbericht-2025-automatisierte-mobilitaet-in-oesterreich/'),
         ('AustriaTech automated mobility monitoring 2024','2025-03-14','https://atech-web04.austriatech.at/de/automatisierte-mobilitaet-in-oesterreich-monitoringbericht-2024/'),
      )},
)


class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.current=[]; self.paragraphs=[]; self.depth=0; self.ignored=0
        self.title=[]; self.title_depth=0
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style','nav','footer','aside','noscript','svg'}:
            self.ignored+=1
        if tag in {'p','li','h1','h2','h3'} and not self.ignored:
            self.depth+=1
        if tag=='title':self.title_depth+=1
    def handle_endtag(self,tag):
        if tag in {'script','style','nav','footer','aside','noscript','svg'} and self.ignored:
            self.ignored-=1
        if tag in {'p','li','h1','h2','h3'} and self.depth:
            self.depth-=1
            if not self.depth:
                text=re.sub(r'\s+',' ',''.join(self.current)).strip()
                if len(text)>45:self.paragraphs.append(text[:1400])
                self.current=[]
        if tag=='title' and self.title_depth:self.title_depth-=1
    def handle_data(self,data):
        if self.title_depth:self.title.append(data)
        if self.depth and not self.ignored:self.current.append(data)


def read_page(url, *, opener=None):
    """Read actual official body text; fail closed on unknown hosts, redirects, PDFs."""
    if urlsplit(url).scheme!='https' or urlsplit(url).hostname not in ALLOWED_HOSTS:
        raise ValueError('non-whitelisted evidence URL')
    if opener is None:
        opener=lambda u: urllib.request.urlopen(urllib.request.Request(u,headers={
            'User-Agent':'WorldRadar/2.0 evidence-review (+https://github.com/vevirm/world-radar)',
            'Accept':'text/html'}), timeout=18)
    with opener(url) as response:
        final=getattr(response,'geturl',lambda:url)()
        if urlsplit(final).hostname not in ALLOWED_HOSTS:
            raise ValueError('source redirected outside trusted publishers')
        content_type=response.headers.get('Content-Type','text/html')
        if 'html' not in content_type.lower():
            raise ValueError('source not extractable HTML')
        content=response.read(MAX_BYTES+1)
        if len(content)>MAX_BYTES:raise ValueError('page exceeds bounded extraction size')
        charset=re.search(r'charset=([\w-]+)',content_type,re.I)
        html=content.decode(charset.group(1) if charset else 'utf-8',errors='replace')
    parser=PageText();parser.feed(html)
    if not parser.paragraphs:raise ValueError('no source paragraphs obtained')
    return {'title':re.sub(r'\s+',' ',''.join(parser.title)).strip(),
            'paragraphs':parser.paragraphs}


def matching_excerpt(page, route):
    """Require claim-relevant topic AND observed-development in SAME passage."""
    candidates=[]
    for para in page['paragraphs']:
        if not 75 <= len(para) <= 1350:continue
        if not all(re.search(g,para,re.I) for g in route['source_gate']):continue
        if not re.search(route['observed_gate'],para,re.I):continue
        # Do not turn a future-only paragraph into an observed development.
        if re.search(r'\b(?:might|could|would|will|projected|forecast|expected to)\b',para,re.I) and not re.search(
                r'\b(?:reported|recorded|observed|measured|account(?:ed|s)? for|increased|decreased|supplied|were supplied|was supplied|stattgefunden|begleitet|tested|testfahrten|showed)\b',para,re.I):
            continue
        # One short extracted passage, verbatim (source traceability).
        numeric=bool(re.search(r'\b(?:20[12]\d|\d+[.,]\d*\s*(?:%|tonnes|million|billion|Mt|PJ))\b',para,re.I))
        direct=bool(re.search(r'\b(?:measur|report|found|observ|test|suppl|produced|record|account|loss|monitor|begleit|stattgefund)\w*',para,re.I))
        candidates.append((int(numeric)*2+int(direct),para))
    if not candidates:return None
    candidates.sort(key=lambda x:(-x[0],len(x[1])))
    return candidates[0][1][:850]


def route_for(original):
    text=original['title']+' '+original['original_passage']
    matching=[r for r in ROUTES if all(re.search(p,text,re.I) for p in r['original_gate'])]
    return matching[0] if len(matching)==1 else None


def choose_originals(root=ROOT, n=3):
    """Automatically choose ACCEPTED source-text originals; one per supported issue."""
    by_route={}; all_claims=original_claims(root)
    for claim in all_claims:
        if claim.get('kind')!='academic' and claim.get('source_kind')!='academic':
            # Institutional reports are legitimate, but no text means no claim.
            if not claim.get('original_passage'):continue
        r=route_for(claim)
        if not r or r['id'] in by_route:continue
        if not claim.get('original_passage'):continue
        by_route[r['id']]=claim
        if len(by_route)>=n:break
    return list(by_route.values())


def investigate(originals, *, reader=read_page):
    cases=[]
    for original in originals:
        route=route_for(original)
        if not route:continue
        later=[];failed=[]
        for publisher, published, url in route['sources']:
            if published <= original['original_publication'][:10]:
                failed.append({'url':url,'reason':'not_later_than_original'});continue
            try:
                page=reader(url)
                excerpt=matching_excerpt(page,route)
                if not excerpt:
                    failed.append({'url':url,'reason':'no_relevant_observed_passage_in_live_source'});continue
                later.append({'source_title':page['title'] or publisher,'publisher':publisher,
                              'published':published,'url':url,'source_passage':excerpt,
                              'why_linked':route['question'],
                              'relationship':route['relation'],
                              'directly_comparable':False})
            except Exception as exc:
                failed.append({'url':url,'reason':f'{type(exc).__name__}: {str(exc)[:160]}'})
        if len(later)>=2:
            state='two_later_sources_read_provisional_connection'
        elif later:
            state='one_later_source_read_provisional_connection'
        else:state='official_source_check_incomplete'
        cases.append({'original_id':original['id'], 'original_title':original['title'],
            'original_date':original['original_publication'],
            'original_url':original.get('source_url',''),
            'what_was_anticipated_original_quote':original['original_passage'][:1600],
            'question_followed':route['question'],
            'later_sources':later,'sources_not_usable':failed,
            'relationship_status':state,
            'what_we_can_say':(
                {'europe_flood_damage':'The later evidence documents European economic losses from climate hazards, including flooding; it informs the trajectory but does not yet measure the exact projected flood-only 2050 annual damages.',
                 'eu_renewable_jet_fuel':'The later evidence documents actual SAF supplied at EU airports; this is relevant market development but a different measure from modeled EU non-food renewable jet-fuel output.',
                 'austria_automated_mobility':'The later evidence documents Austrian automated-vehicle trials and initiatives; it shows implementation activity, but cannot establish the predicted changes in traffic and modal share.'}[route['id']]
                if later else 'No later official passage could be substantiated in this bounded run.'),
            'what_we_cannot_say':route['scope'],
            'original_forecast_verified':False,'review_status':'machine_draft',
            'publish':False})
    return {'schema_version':1,'mode':'ONE_ORIGINAL_TWO_LATER_OFFICIAL_SOURCES',
            'generated_utc':datetime.now(timezone.utc).isoformat(),
            'originals_investigated':len(cases),
            'cases_with_two_sources':sum(len(c['later_sources'])>=2 for c in cases),
            'sources_read':sum(len(c['later_sources']) for c in cases),
            'verified_outcomes':0, 'publish':False,
            'limitations':'Bounded official-source connector pilot for three issue families; no claim that all subjects have automatic evidence coverage, no equivalence unless independently established, no public findings.',
            'cases':cases}


def markdown(report):
    lines=['# Radar 2 — original → two later sources → connection', '',
           '**Machine research draft. No confirmed forecasts or website publication.**', '',
           f'Accepted originals investigated: **{report["originals_investigated"]}**; '
           f'official source passages retrieved: **{report["sources_read"]}**; '
           f'cases with two: **{report["cases_with_two_sources"]}**.', '']
    for idx,c in enumerate(report['cases'],1):
        lines += [f'## {idx}. {c["original_title"]}', '',
                  f'**Then ({c["original_date"]}):** {c["what_was_anticipated_original_quote"]}', '',
                  f'**Question carried forward:** {c["question_followed"]}', '']
        for n,s in enumerate(c['later_sources'],1):
            lines += [f'**Later source {n} ({s["published"]}):** [{s["source_title"]}]({s["url"]})',
                      f'> {s["source_passage"]}', '']
        lines += [f'**Connection:** {c["what_we_can_say"]}',
                  f'**What cannot yet be concluded:** {c["what_we_cannot_say"]}',
                  f'**Status:** {c["relationship_status"]}. Unverified draft.', '']
        for e in c['sources_not_usable']:
            lines.append(f'- Could not use {e["url"]}: {e["reason"]}')
    return '\n'.join(lines)+'\n'


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--max-originals',type=int,default=3,choices=(1,2,3))
    p.add_argument('--root',type=Path,default=ROOT)
    args=p.parse_args(argv)
    originals=choose_originals(args.root,args.max_originals)
    if not originals:raise SystemExit('No accepted source-text original matched the 3 audited evidence families.')
    report=investigate(originals)
    (args.root/'RADAR2-THEN-NOW-AUTO.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (args.root/'RADAR2-THEN-NOW-AUTO.md').write_text(markdown(report),encoding='utf-8')
    print(f"Draft: {report['originals_investigated']} accepted originals; "
          f"{report['sources_read']} extracted later official passages; "
          f"{report['cases_with_two_sources']} with two. No automatic publication.")

if __name__=='__main__':main()
