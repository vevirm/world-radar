#!/usr/bin/env python3
"""Ten-original, question-led Radar 2 discovery pilot (DRAFT ONLY).

This is a controlled test of *independent selection* and later-evidence search.
The historical question is grounded in the accepted original passage; the later
material is attributed to an OpenAlex-indexed abstract, never called a verified
real-world outcome. The pilot does not change the published site or any data.

With OpenAlex alone, a full 'then vs now' assessment is NOT yet established.
That limitation is made explicit for every case rather than inventing verdicts.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

try:
    from .radar2_scope import original_claims
    from .radar2_questions import question_card, SPECIFIC
    from .openalex_comparison import request_works, abstract_from_index
except ImportError:
    from radar2_scope import original_claims
    from radar2_questions import question_card, SPECIFIC
    from openalex_comparison import request_works, abstract_from_index

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = (
    ('climate_ecosystems', r'\b(?:forest|trees|species|climate|biodiversity|drought|flood|mosquito|ecolog|habitat)\w*\b'),
    ('energy_transition', r'\b(?:renewable|hydrogen|electricity|energy|decarbon|solar|wind|power plant|gas supply)\w*\b'),
    ('transport', r'\b(?:rail|freight|transport|mobility|aviation|shipping|maritime)\w*\b'),
    ('migration_population', r'\b(?:immigrat|demograph|population|migrat|fertility|refugee)\w*\b'),
    ('agriculture_food', r'\b(?:agricultur|organic food|farm|crop|food market|land.use)\w*\b'),
    ('industry_jobs', r'\b(?:industrial|employment|labour|labor|jobs|workforce|manufactur|chemical industr)\w*\b'),
    ('security_governance', r'\b(?:security|defence|defense|integration|enlargement|eurozone|governance)\w*\b'),
    ('health', r'\b(?:health|mortality|morbidity|hospital|cancer|disease|public health)\w*\b'),
    ('trade_economy', r'\b(?:economic|trade|market|bank|finance|investment|productivity)\w*\b'),
    ('technology_digital', r'\b(?:technology|digital|internet|innovation|robot|artificial intelligence|telecommunication)\w*\b'),
)
QUERY_EXCLUDE = set('''actual affect effects impacts result question paper study assessment
analysis implications potential possible scenarios scenario european europe union
future futures forecast forecasts projected forecasting trends trend towards
expected model simulations modelling evaluating evaluation developing developed
following current recent role approach exploring considered how does what
would could climate change new proposed european-based'''.split())
TOPICAL_GENERIC = set('''climate change energy systems system policy impact effects mitigation nearly unveiling hidden actual global according demonstrate reference observed chosen individual scenario under candidate derived experience results context selected
countries country regional global europe european sustainability sustainable
future scenarios study analysis development environment research policy'''.split())
EXPLICIT_EU = re.compile(r'\b(?:Europe|European|EU[ -]?(?:27|28)?|Eurostat|Eurozone|member states|Finland|Finnish|Sweden|Swedish|Germany|German|France|French|Italy|Italian|Spain|Spanish|Poland|Polish|Netherlands|Dutch|Belgium|Belgian|Denmark|Danish|Portugal|Portuguese|Ireland|Irish|Greece|Greek|Austria|Austrian|Norway|Norwegian|Switzerland|Swiss|Czech|Romania|Romanian|Baltic|Mediterranean|UK|Britain|British)\b', re.I)
NON_EU_IN_TITLE = re.compile(r'\b(?:Brazil|Brazilian|Japan|Japanese|United States|U\.S\.|USA|American|China|Chinese|India|Indian|Australia|Australian|Pakistan|Pakistani|Nigeria|Nigerian)\b', re.I)
OBSERVED = re.compile(r'\b(?:we (?:found|find|observed|measured|recorded)|observations? (?:show|indicate)|data (?:show|reveal|indicate)|(?:has|have|had) (?:risen|increased|fallen|declined|decreased|expanded|grown)|(?:increased|decreased|declined|rose|fell|expanded|contracted) (?:by|from|to|between|in|over)|empirical (?:evidence|results)|survey (?:data|results)|measured|recorded|observed|statistics show|was (?:measured|recorded|observed))\b',re.I)
MODEL_ONLY = re.compile(r'\b(?:is predicted|are projected|we project|we forecast|might|could|would|may|hypothesiz\w*|is expected|are expected|is likely to|we modelled|we modeled|simulation shows)\b', re.I)
AUTHORED_FORECAST = re.compile(r'\b(?:we (?:forecast|project|predict|estimate|simulate|model|anticipate|expect|explore)|our (?:scenarios?|models?|projections?|forecasts?|results?)|(?:model|scenario|projection|forecast|simulation)s? (?:show|indicate|suggest|predict|project)|(?:projected|estimated|expected|forecast|predicted) (?:to|that|by)|(?:may|might|could|will|would) (?:increase|decrease|fall|rise|reach|become|double|exceed|decline|expand|reduce|produce|continue)|by 20[2-9]\d[^.!?]{0,140}(?:will|would|could|may|reach|increase|decrease|decline|fall|rise)|20[2-9]\d scenarios?|an? 20[2-9]\d scenario|scenarios? for 20[2-9]\d)\b',re.I)
POLICY_ONLY = re.compile(r'\b(?:eu leaders have agreed|european union declares|eu (?:aims|plans|targets)|green deal to become climate neutral|commission (?:proposes|proposed|adopted))\b',re.I)
FOCUSED_TERMS = set('''damage welfare supply prices refineries renewables floods flood drought water pollutants carbon jet biojet cost jobs agriculture dairy milk yields technology scanners fuel forestry population elderly youth social spending vulnerability imports feedstocks forests forestry trees drought floods rainfall incinerator incinerators cancer mortality fertility ageing aging biomass nitrogen hydrogen jet fuel biofuel biofuels power electricity freight railways rail road aviation wind solar mosquito mosquitos disease infection biodiversity species coastal inland digital broadband gigabit transport ocean tidal marine migration migrants immigrant immigration poverty exclusion industry industrial agriculture farming crop crops food organic biological invasions alien energetic investment emissions land-use land-cover decarbonisation decarbonization'''.split())
SUBSTANTIVE_TRAJECTORY = re.compile(r'\b(?:\d+(?:[.,]\d+)?\s*(?:%|percent|million|billion|mt|gigawatt|tonne)|(?:would|could|will|may|might|is projected to|are projected to|we project|we predict|results indicate|models show|model scenarios show|simulations suggest|projections show|models predict|was predicted to)\s+(?:\w+\s+){0,5}(?:increase|decrease|rise|fall|reduce|grow|decline|double|expand|reach|become|shift|exceed)|(?:projected|forecast|predicted)\s+(?:increase|decrease|growth|decline|rise|fall|loss|impact|expansion)|(?:scenarios?|pathways?)\s+(?:show|indicate|suggest))\b',re.I)
SOURCE_STUDY = re.compile(r'\b(?:scenarios?|models?|simulations?|projections?|forecasts?|projected|predict(?:ed|ions?)?|we (?:estimate|project|simulate|predict|anticipate|find|demonstrate)|(?:\d+(?:[.,]\d+)?\s*%|million|billion|tonnes?|gigawatts?))\b',re.I)
FUTURE = re.compile(r'\b(?:20(?:2[0-9]|3[0-9]|4[0-9]|5[0-9]|6[0-9]|7[0-9]|8[0-9]|9[0-9])|2100|might|could|will|would|expected|projection|scenarios?|forecast|pathways?|alternative)\b', re.I)
WORD = re.compile(r"[A-Za-z][A-Za-z0-9-]{2,}")


def wordset(s):
    """Simple stable token normalization; no fuzzy-similarity outcome inference."""
    words = set()
    for w in WORD.findall(str(s or '').casefold()):
        if w.endswith('ies') and len(w) > 5:
            w = w[:-3] + 'y'
        elif w.endswith('s') and len(w) > 5 and not w.endswith(('ss', 'us', 'is')):
            w = w[:-1]
        if w not in QUERY_EXCLUDE and w not in TOPICAL_GENERIC:
            words.add(w)
    return words


def historical_focus(passage):
    """Extract a *quote* containing the future-facing content, not a prediction paraphrase."""
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', passage) if s.strip()]
    choices = [s for s in sentences if len(s) >= 55 and FUTURE.search(s)]
    return max(choices, key=lambda s: (bool(SUBSTANTIVE_TRAJECTORY.search(s)),
                                       bool(AUTHORED_FORECAST.search(s)),
                                       bool(re.search(r'\b(?:2030|2040|2050|2100)\b', s)),min(len(s), 360)))[:550] if choices else passage[:550]


def classified(title):
    for category, pattern in CATEGORIES:
        if re.search(pattern, title, re.I):
            return category
    return 'other'


def select_ten(root=ROOT, n=10):
    """Deterministically select up to ten *different issue areas*, not fixed IDs."""
    if not 1 <= n <= 10:
        raise ValueError('Pilot maximum is ten originals')
    root=Path(root)
    already = json.loads((root/'radar2-comparisons.json').read_text(encoding='utf-8'))
    excluded={c['id'] for c in already.get('comparisons',[])} | {c['id'] for c in already.get('unresolved',[])}
    candidates=[]
    for claim in original_claims(root):
        card=question_card(claim)
        passage=card['original_passage']
        if claim['id'] in excluded or card['readiness'] in ('original_text_required','source_review_required'):
            continue
        if claim['source_kind']!='academic' or len(passage)<110 or len(card['issue_anchors'])<3:
            continue  # institutional originals without a verified quote are not safe to research
        focus=historical_focus(passage)
        if len(focus)<55 or not FUTURE.search(focus):
            continue
        if not AUTHORED_FORECAST.search(passage) or not SOURCE_STUDY.search(passage):
            continue  # a generic EU target or contextual future mention is not an authored finding
        if not SUBSTANTIVE_TRAJECTORY.search(focus):
            continue  # future policy background and method-only scenarios are not an actual proposition
        if POLICY_ONLY.search(focus) and not AUTHORED_FORECAST.search(focus):
            continue
        # Earlier publications provide a longer observation window, other things equal.
        score=(int(card['readiness']=='quantified_future_proposition')*3+
               int(bool(re.search(r'20[3-9]\d|2100',focus)))*2+
               int(len(focus)>=110)+min(len(card['issue_anchors']),8)/10)
        candidates.append((score, claim['original_publication'], claim['id'], claim, card, focus))
    candidates.sort(key=lambda x:(-x[0],x[1],x[2]))
    chosen=[]; used=set()
    for category,_ in CATEGORIES:
        for _,_,_,claim,card,focus in candidates:
            if claim['id'] not in used and classified(claim['title'])==category:
                chosen.append({**claim,'question_card':card,'historical_focus':focus,'topic_group':category})
                used.add(claim['id']);break
        if len(chosen)==n:
            break
    for _,_,_,claim,card,focus in candidates:
        if len(chosen)>=n:
            break
        if claim['id'] not in used:
            chosen.append({**claim,'question_card':card,'historical_focus':focus,
                           'topic_group':classified(claim['title'])})
            used.add(claim['id'])
    if len(chosen)!=n:
        raise ValueError(f'Only {len(chosen)} source-ready originals found, expected {n}')
    return chosen


def discovery_queries(claim):
    """Two compact searches from source issues, not manually mapped statistics."""
    title=claim['title']
    full=title+' '+claim['historical_focus']
    title_terms=wordset(title)
    passage_terms=wordset(claim['historical_focus'])
    all_terms=list(dict.fromkeys(w.casefold() for w in WORD.findall(full)))
    unique=[w for w in all_terms if w in (title_terms|passage_terms) and (len(w)>4 or w in FOCUSED_TERMS)]
    def rank(w):
        return (int(w in FOCUSED_TERMS or w.rstrip('s') in FOCUSED_TERMS)*6+
                int(w in title_terms and w in passage_terms)*3+
                int(w in title_terms)*3+int(len(w)>8))
    unique.sort(key=lambda w:-rank(w))
    if not (title_terms & passage_terms):
        # When the title uses a different language or vocabulary, use the
        # actual saved projection instead of an unrelated title-word query.
        unique=[w for w in all_terms if w in passage_terms and (len(w)>4 or w in FOCUSED_TERMS)]
        unique.sort(key=lambda w:-rank(w))
    concepts=unique[:7]
    if len(concepts)<2:
        return []
    geo='Europe'
    m=EXPLICIT_EU.search(title)
    if m and m.group().strip().lower() not in ('eu','europe','european','eu-27','eu-28'):
        geo=m.group().strip()
    # First query uses the subject and original mechanism, the second is looser.
    searches=[f'{concepts[0]} {concepts[1]} {geo}',
              f'{concepts[0]} {concepts[2]} {geo}' if len(concepts)>2 else f'{concepts[0]} {geo}']
    return list(dict.fromkeys(s for s in searches if s))[:2]


def candidate_for(claim, work):
    """Provisional *source-attributed* observations; never verified outcomes."""
    title=str(work.get('title') or '').strip()
    url=str(work.get('doi') or work.get('id') or '').strip()
    date=str(work.get('publication_date') or '').strip()
    try:
        yr=int(date[:4])
        original_year=int(claim['original_publication'][:4])
    except (TypeError, ValueError):
        return None
    this_year=datetime.now(timezone.utc).year
    if not (original_year < yr <= this_year) or (date and len(date)>=10 and date[:10]>datetime.now(timezone.utc).date().isoformat()):
        return None
    if not url.startswith('https://') or not title or url.lower().rstrip('/')==claim['source_url'].lower().rstrip('/'):
        return None
    if title.casefold()==claim['title'].casefold():
        return None
    abstract=abstract_from_index(work.get('abstract_inverted_index')) or str(work.get('abstract') or '')
    if len(abstract)<90 or NON_EU_IN_TITLE.search(title):
        return None
    # Europe must be part of the subsequent work's own subject, not inferred
    # from the source paper or the mere OpenAlex query.
    if not EXPLICIT_EU.search(title+' '+abstract):
        return None
    title_anchors=wordset(claim['title'])
    source_anchors=title_anchors|wordset(claim['historical_focus'])
    hit_anchors=wordset(title+' '+abstract)
    overlap=sorted(source_anchors & hit_anchors)
    in_title=sorted(source_anchors & wordset(title))
    in_futures=sorted(wordset(claim['historical_focus']) & wordset(title+' '+abstract))
    if len(overlap)<2 or len(in_title)<1 or len(in_futures)<1:
        return None
    observed=[]
    for s in re.split(r'(?<=[.!?])\s+', abstract):
        if not 40 <= len(s) <= 650 or not OBSERVED.search(s) or MODEL_ONLY.search(s):
            continue
        if len(wordset(s)&source_anchors)>=2:
            observed.append(' '.join(s.split())[:450])
    if not observed:
        return None
    return {'later_title':title, 'later_url':url, 'later_date':date,
            'later_indexed_abstract_observation':observed[0],
            'overlapping_subject_terms':overlap[:12],
            'title_subject_terms':in_title[:7],
            'context_europe_visible':True,
            'original_and_later_geography_equivalent':None,
            'original_and_later_measure_equivalent':None,
            'original_and_later_baseline_equivalent':None,
            'reported_by_later_paper_not_independently_verified':True,
            'source_review_required':True,
            'outcome_verified':False,
            'score_for_order_only':len(in_title)*3+len(overlap)}


def research(claims, api_key, searcher=request_works):
    """Small live search; all outputs are reviewable artifacts only."""
    if not api_key:
        raise ValueError('OPENALEX_API_KEY is required; live search was not attempted')
    cases=[]
    for claim in claims:
        searches=discovery_queries(claim)
        hits={};errors=[];done=[]
        for query in searches:
            try:
                works=searcher(query,int(claim['original_publication'][:4])+1)
                if not isinstance(works,list):
                    raise ValueError('Unexpected OpenAlex result')
                done.append(query)
                for work in works:
                    if not isinstance(work,dict):continue
                    hit=candidate_for(claim,work)
                    if hit:
                        key=hit['later_url'].casefold().rstrip('/')
                        if key not in hits or hits[key]['score_for_order_only']<hit['score_for_order_only']:
                            hits[key]=hit
            except Exception as exc:
                errors.append(f'{type(exc).__name__}: {str(exc)[:180]}')
        citations=sorted(hits.values(),key=lambda c:(-c['score_for_order_only'],c['later_date']))[:3]
        for c in citations:c.pop('score_for_order_only',None)
        if errors:
            status='search_failed_or_partial'
            interpretation='At least one query failed. An evidence absence cannot be inferred.'
        elif citations:
            status='later_empirical_abstract_candidates_unverified'
            interpretation=('Later European research reports an observation about a partially overlapping issue. '
                'The match to the original scenario, population, assumptions, and metric is NOT established. '
                'No conclusion about whether the original thinking materialised can yet be drawn.')
        else:
            status='no_usable_evidence_in_bounded_openalex_search'
            interpretation=('No defensible later observation was identified by THESE limited OpenAlex searches. '
                'This is a logged search outcome, NOT proof that the development never happened or a completed evidence-gap assessment.')
        horizon_years=[y for y in claim['question_card']['target_year_mentions'] if y > int(claim['original_publication'][:4])]
        horizon_status=('future_horizon_not_reached' if horizon_years and min(horizon_years)>datetime.now(timezone.utc).year
                        else 'at_least_one_target_year_reached_or_unspecified')
        cases.append({
            'target_horizon_years':horizon_years,'target_horizon_status':horizon_status,
            'original_id':claim['id'],'topic_group':claim['topic_group'],
            'historical_title':claim['title'],'historical_date':claim['original_publication'],
            'historical_source':claim['source_url'], 'original_source_passage':claim['original_passage'],
            'historical_future_facing_excerpt':claim['historical_focus'],
            'question_for_research':claim['question_card']['evidence_question'],
            'question_type':claim['question_card']['readiness'],
            'queries_attempted':searches,'queries_completed':done,
            'later_paper_observations_for_source_review':citations,
            'status':status,'interpretation':interpretation,
            'missing_for_then_vs_now':('Original assumptions and an independent, context-equivalent later source '
                'or a reviewed empirical observation, with a documented relationship to the exact historical proposition.'),
            'errors':errors,'no_meaningful_link_established':True,
            'fully_investigated_evidence_gap':False,
            'verified_outcome':False,'publish':False})
    return {'schema_version':1,'mode':'AUTONOMOUS_QUESTION_DISCOVERY_TEN_DRAFT_ONLY',
            'generated_utc':datetime.now(timezone.utc).isoformat(),
            'originals_selected':len(claims),
            'openalex_queries_completed':sum(len(c['queries_completed']) for c in cases),
            'with_later_empirical_abstract_candidates':sum(bool(c['later_paper_observations_for_source_review']) for c in cases),
            'search_failed_or_partial':sum(c['status']=='search_failed_or_partial' for c in cases),
            'verified_outcomes':0,'published_outcomes':0,'publication_allowed':False,
            'limitations':'OpenAlex abstracts are leads, not verified outcomes. The system autonomously chooses originals, passages and search terms, but cannot independently establish a then-vs-now relationship from OpenAlex abstracts alone.',
            'cases':cases}


def markdown(report):
    lines=['# Radar 2 — ten-study automatic question-led test', '',
           'Draft, not published research. No prior selection of indicator, DOI or later source.','',
           f'**Accepted historical originals selected:** {report["originals_selected"]}',
           f'**Completed OpenAlex searches:** {report["openalex_queries_completed"]}',
           f'**Cases with possible subsequent observed evidence:** {report["with_later_empirical_abstract_candidates"]}',
           f'**Cases with search errors:** {report["search_failed_or_partial"]}',
           '**Verified comparisons: 0** (not claimed by this test)', '',
           'Candidate papers are attributed research excerpts, not proven developments.','']
    for i,c in enumerate(report['cases'],1):
        lines.extend([f'## {i}. {c["historical_title"]} ({c["historical_date"][:4]})','',
                      f'**Original:** {c["historical_source"]}',
                      f'**What the original said:** {c["historical_future_facing_excerpt"]}',
                      f'**Question:** {c["question_for_research"]}',
                      f'**Historical horizon:** {c["target_horizon_years"] or "Not explicit"}; {c["target_horizon_status"]}',
                      f'**Searches:** {", ".join(c["queries_completed"])}',''])
        for e in c['later_paper_observations_for_source_review']:
            lines.extend([f'- **Later paper ({e["later_date"]}):** [{e["later_title"]}]({e["later_url"]})',
                          f'  - Reported in its abstract: {e["later_indexed_abstract_observation"]}'])
        lines.extend(['', '**Finding:** '+c['interpretation'],
                      '**Unresolved:** '+c['missing_for_then_vs_now'],''])
        if c['errors']:
            lines.extend(['**Errors:** '+('; '.join(c['errors'])),''])
    lines.extend(['---','**Important:** A completed OpenAlex search with no usable result is a documented *search limitation*, '
                  'not a finding that a scenario failed or an established research-level absence of a meaningful link.'])
    return '\n'.join(lines)+'\n'


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--output-prefix',type=Path,default=Path('RADAR2-TEN-QUESTION-PILOT'))
    args=parser.parse_args(argv)
    claims=select_ten(args.root)
    report=research(claims,os.environ.get('OPENALEX_API_KEY','').strip())
    prefix=args.output_prefix if args.output_prefix.is_absolute() else args.root/args.output_prefix
    prefix.with_suffix('.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    prefix.with_suffix('.md').write_text(markdown(report),encoding='utf-8')
    msg=(f'Radar 2 question-led 10 study pilot: {report["openalex_queries_completed"]} OpenAlex searches, '
         f'{report["with_later_empirical_abstract_candidates"]} cases with empirical abstract leads; 0 verified outcomes')
    print(msg,flush=True)
    summary=os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a',encoding='utf-8') as f:
            f.write('## Radar 2 — ten-original question-led pilot (NO PUBLISH)\n\n')
            f.write(f'- Accepted originals selected: **{report["originals_selected"]}**\n')
            f.write(f'- OpenAlex searches completed: **{report["openalex_queries_completed"]}**\n')
            f.write(f'- Cases with empirical abstract leads: **{report["with_later_empirical_abstract_candidates"]}**\n')
            f.write(f'- Search failures: **{report["search_failed_or_partial"]}**\n')
            f.write('- Verified outcomes: **0** (review required); published: **0**\n')
    if report['search_failed_or_partial']:
        raise SystemExit('Some OpenAlex queries failed; partial pilot artifact is available for review')


if __name__=='__main__':
    main()
