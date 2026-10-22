#!/usr/bin/env python3
"""Radar 2: source-traceable *research connections* (DRAFT ONLY).

This is a supplementary research-lineage layer, NOT a then-vs-now outcome
engine. Its citing/topic/method links cannot verify a historical prediction,
causation, scenario conditions, or observed European developments.

Live mode: up to 3 accepted, passage-backed originals; 4 API requests each.
Offline mode: no network (cached works only), with a coverage warning.
Both modes write standalone artifacts, never the live research collection.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import urllib.parse
import urllib.request

try:
    from .radar2_ten_study_pilot import select_ten
    from .radar2_claim_links import claim_card, pick_plan, plan_queries, scope_match, TITLE_GATE, assess_work
    from .openalex_comparison import abstract_from_index, tokens, MODEL, RESULTS
except ImportError:
    from radar2_ten_study_pilot import select_ten
    from radar2_claim_links import claim_card, pick_plan, plan_queries, scope_match, TITLE_GATE, assess_work
    from openalex_comparison import abstract_from_index, tokens, MODEL, RESULTS

ROOT = Path(__file__).resolve().parents[1]
YEAR = re.compile(r'\b(?:19\d\d|20\d\d|2100)\b')
MODEL_NAMES = re.compile(r'\b(?:JRC[- ]EU[- ]TIMES|PRIMES|GEM[- ]E3|UK Foresight Obesity Model)\b', re.I)
SENTENCES = re.compile(r'(?<=[.!?])\s+')
OBSERVED_YEAR = re.compile(r'\b(?:observed|measured|recorded|surveyed|collected|monitored|data from|data for|between|during|in|from)\s+(?:(?:the|years?|period|samples?)\s+){0,3}(20\d\d)(?:\s*(?:to|and|[-–])\s*(20\d\d))?\b', re.I)
TEXT_STOP = set('''actual study studies result results future futures model scenario scenarios analysis development policy europe european union results findings our the with from into would could over under that have been about through by year data research observed measuring of this for across national international report'''.split())
SELECT_FIELDS = 'id,doi,title,publication_date,authorships,referenced_works,abstract_inverted_index'


def norm_id(value):
    return str(value or '').strip().split('/')[-1].upper()


def source_text(work):
    return abstract_from_index(work.get('abstract_inverted_index')) or str(work.get('abstract') or '')


def publication_date(work):
    raw = str(work.get('publication_date') or '')[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def field(value, passage, how):
    return {'value': value, 'evidence_sentence': passage, 'method': how}


def anchor_for(original):
    """Original-source anchor; never pretend a title is a verified quote."""
    quote = ' '.join(str(original.get('historical_focus') or original.get('original_passage') or '').split())
    plan = pick_plan(original)
    year = int(original['original_publication'][:4])
    years = sorted({int(x) for x in YEAR.findall(quote) if int(x) > year})
    condition = []
    for s in SENTENCES.split(quote):
        if re.search(r'\b(?:under|provided(?: that)?|assuming|if|conditional on|without|depending on)\b',s,re.I):
            condition.append(s.strip()[:400])
    models = sorted({m.group(0) for m in MODEL_NAMES.finditer(quote)},key=str.casefold)
    geography = plan['geography'] if plan else None
    # The topic label and geographic label are *interpretations*, not quoted source facts.
    # The quotation remains beside them and no model provenance name is used as geography.
    return {
        'status': 'passage_backed_interpretation_needs_review' if quote and plan else 'needs_source_or_subject_review',
        'original_excerpt':quote,
        'original_source':original['source_url'],
        'original_source_kind':original['source_kind'],
        'original_passage_status':original.get('original_review_status','not_established'),
        'subject':field(plan['topic'] if plan else None,quote,'tested_question_family' if plan else 'unresolved'),
        'geography':field(geography,quote,'tested_question_family' if plan else 'unresolved'),
        'horizon':field(years,quote,'quoted_years_after_publication'),
        'conditions':field(condition,quote,'quoted_conditional_sentences'),
        'named_models':field(models,quote,'named_model_match'),
        'research_question':plan['question'] if plan else None,
        'measurement_warning':plan['note'] if plan else 'No tested question family; manual assessment required',
        'possible_official_evidence_routes_not_yet_searched':list(plan['sources']) if plan else [],
        'topic_plan_id':plan['id'] if plan else None,
    }


def authors(work):
    return {norm_id(a.get('author',{}).get('id')) for a in work.get('authorships',[]) if isinstance(a,dict) and isinstance(a.get('author'),dict) and a['author'].get('id')}


def date_relation(original_date, later_work):
    orig = date.fromisoformat(original_date[:10])
    when = publication_date(later_work)
    if when is None:
        return 'needs_dates'
    if when <= orig or when > date.today():
        return 'not_later'
    return 'later'


def topic_gate(original, later):
    """Narrow structural topic check; never itself establishes observed change."""
    plan = pick_plan(original)
    if plan is None:
        return False
    title = str(later.get('title') or '')
    abstract = source_text(later)
    if len(abstract) < 85 or not re.search(TITLE_GATE[plan['id']],title,re.I):
        return False
    return (scope_match(plan,title,abstract) and
            all(re.search(pattern,title+' '+abstract,re.I) for pattern in plan['must']))


def observed_period(abstract, original_year, date_of_later):
    """Extract only explicitly dated observation language (never pub year as data year)."""
    dates=[]
    for sent in SENTENCES.split(abstract):
        if not (RESULTS.search(sent) or re.search(r'\b(?:observed|measured|recorded|monitored|surveyed|data from|between)\b',sent,re.I)):
            continue
        for m in OBSERVED_YEAR.finditer(sent):
            years=[int(x) for x in m.groups() if x]
            if all(1900 <= v <= date_of_later.year for v in years):
                dates.extend(years)
    if not dates:
        return None
    # Dates must demonstrably follow the original to count as a post-publication look-back.
    return [min(dates),max(dates)] if max(dates)>original_year else None


def time_position(anchor, period):
    horizon = anchor['horizon']['value']
    if period is None:
        return 'unknown_observation_period'
    if horizon:
        if period[1]>=max(horizon):
            return 'looks_back_at_all_quoted_horizon_years'
        if period[1]>=min(horizon):
            return 'looks_back_at_an_earlier_quoted_year_later_horizon_open'
        return 'interim_look_back'
    return 'post_original_observation_no_explicit_horizon'


def study_links(original, anchor, original_work, work):
    """Classify research provenance separately from empirical relevance.

    L1-substantive, L2 and L3 are discovery links, not outcome validations.
    """
    date_status = date_relation(original['original_publication'],work)
    if date_status != 'later':
        return None,date_status
    if not work.get('title') or not work.get('id'):
        return None,'incomplete_work_metadata'
    orig_id=norm_id(original_work.get('id'))
    work_id=norm_id(work.get('id'))
    if not orig_id or orig_id==work_id:
        return None,'self_or_unresolved_original'
    same_subject = topic_gate(original,work)
    cites = orig_id in {norm_id(x) for x in work.get('referenced_works',[])}
    shared = sorted(authors(original_work) & authors(work))
    model_names=anchor['named_models']['value']
    shared_models=[name for name in model_names if re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',str(work.get('title') or '')+' '+source_text(work),re.I)]
    links=[]
    if cites:
        links.append('L1-substantive' if same_subject else 'L1-passing')
    if same_subject and (shared or shared_models):
        links.append('L2-research-lineage')
    text = source_text(work)
    later = publication_date(work)
    empiric,reason=assess_work(original,work,text,int(original['original_publication'][:4])) if same_subject else (None,'not_same_question')
    period=observed_period(text,int(original['original_publication'][:4]),later) if empiric else None
    if empiric and period:
        links.append('L3-empirical-question-lead')
    if not links:
        return None,'topic_only' if same_subject else 'unrelated'
    substantive = any(l != 'L1-passing' for l in links)
    status = ('linked_research_draft' if substantive else 'citation_only_background')
    # Human review still required for every machine-generated connection.
    record={
        'later_id':work_id,'later_title':str(work['title'])[:300],
        'later_date':later.isoformat(),'later_url':str(work.get('doi') or work['id']),
        'links':links,'primary_link':next((l for l in ['L3-empirical-question-lead','L1-substantive','L2-research-lineage','L1-passing'] if l in links),None),
        'research_link_status':status,'review_status':'machine',
        'link_evidence':{'cites_original':cites,'topic_mechanism_and_place_matched':same_subject,
                         'shared_author_ids':shared,'shared_model_names':shared_models,
                         'later_quote':(empiric or {}).get('later_indexed_abstract_observation') if empiric else None,
                         'later_abstract_available':len(text)>=85},
        'observed_period':period,'time_relation':time_position(anchor,period),
        'observation_equivalence_verified':False,'historical_outcome_verified':False,
        'comparability_warning':(empiric or {}).get('measurement_comparability') if empiric else 'research_continuation_not_an_observation',
        'interpretation':'Research lineage/possible same-question evidence, NOT an observation validated against the original',
    }
    return record,None


def title_drift(anchor, links):
    """Exploratory scholarly vocabulary only; not evidence of external change."""
    original = set(re.findall(r'[a-z][a-z-]{3,}',anchor['original_excerpt'].lower()))
    frequency = Counter()
    for link in links:
        words=set(re.findall(r'[a-z][a-z-]{3,}',link['later_title'].lower()))
        frequency.update(x for x in words if x not in original and x not in TEXT_STOP)
    return [x for x,n in frequency.most_common() if n >= 2][:5]


def drift_summary(anchor, links):
    """Cautious description, not a hallucinated 'what changed' narrative."""
    real=[x for x in links if x['research_link_status']=='linked_research_draft' and x.get('review_status')!='rejected']
    periods=Counter(str(int(l['later_date'][:4])//5*5)+'–'+str(int(l['later_date'][:4])//5*5+4) for l in real)
    horizon=anchor['horizon']['value']
    return {
        'period_counts':dict(sorted(periods.items())),
        'earliest_quoted_horizon_reached':bool(min(horizon)<=date.today().year) if horizon else None,
        'latest_quoted_horizon_reached':bool(max(horizon)<=date.today().year) if horizon else None,
        'research_connections':len(real),
        'new_title_terms_in_multiple_linked_studies_unverified': title_drift(anchor,real),
        'observed_interim_leads':sum('L3-empirical-question-lead' in x['links'] for x in real),
        'drift_verified':False,
        'note':('This is a limited publication trail, not established change in the real world. '
                'Do not infer substantive question drift from isolated abstracts or search-result vocabulary.'),
    }


def merge_reviews(previous, incoming):
    """Never overwrite a reviewer's link decision, including rejections."""
    old={x.get('original_id'):x for x in previous.get('originals',[]) if isinstance(x,dict)}
    for case in incoming.get('originals',[]):
        prior=old.get(case.get('original_id')) or {}
        reviewed={x['later_id']:x for x in prior.get('links',[]) if isinstance(x,dict) and x.get('later_id') and x.get('review_status') in ('confirmed','rejected')}
        fresh={x['later_id']:x for x in case.get('links',[]) if isinstance(x,dict) and x.get('later_id')}
        fresh.update(reviewed)
        case['links']=sorted(fresh.values(),key=lambda x:(x.get('later_date') or '',x.get('later_id') or ''), reverse=True)
        if prior.get('human_notes'):
            case['human_notes']=prior['human_notes']
        if case.get('anchor'):
            case['drift']=drift_summary(case['anchor'],case['links'])
    incoming.setdefault('summary',{})['with_research_links']=sum(
        any(l.get('research_link_status')=='linked_research_draft' and l.get('review_status')!='rejected'
            for l in c.get('links',[])) for c in incoming.get('originals',[]))
    return incoming


def validate_report(report):
    """Do not allow undeclared source, false observation verdict or weak date link."""
    if report.get('summary',{}).get('published') or report.get('summary',{}).get('verified_outcome_assessments'):
        raise ValueError('Research connections cannot publish or verify outcomes')
    for c in report.get('originals',[]):
        if not c.get('anchor',{}).get('original_excerpt'):
            raise ValueError('Every automated research anchor needs an original quotation')
        if c.get('auto_published') or c.get('historical_outcome_verified') or c.get('meaningful_link_absence_established'):
            raise ValueError('Research connections cannot make real-world conclusions')
        for item in c.get('links',[]):
            if not item.get('later_id') or not item.get('link_evidence'):
                raise ValueError('Connection missing link identifier or mechanism')
            if not item.get('links') or item.get('primary_link') not in item['links']:
                raise ValueError('Link must explain its relationship')
            if item.get('historical_outcome_verified') or item.get('observation_equivalence_verified'):
                raise ValueError('Unverified research lead declared an outcome')
            if item.get('review_status') not in ('machine','confirmed','rejected'):
                raise ValueError('Invalid review status')
            when=date.fromisoformat(item['later_date'])
            if when<=date.fromisoformat(c['original_published']) or when>date.today():
                raise ValueError('Later research link must have a genuinely later date')
    return True


class OpenAlex:
    def __init__(self, key=None, email=None, fetch=None):
        self.key=key or ''
        self.email=email or ''
        self.fetch=fetch or self._fetch
        self.requests=0

    def _fetch(self,params):
        args={**params,'api_key':self.key}
        if '@' in self.email:
            args['mailto']=self.email
        url='https://api.openalex.org/works?'+urllib.parse.urlencode(args)
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'WorldRadar-Radar2-ResearchConnections/1.0'}),timeout=25) as rsp:
            payload=json.loads(rsp.read())
        if not isinstance(payload,dict) or not isinstance(payload.get('results'),list):
            raise ValueError('Invalid OpenAlex works response')
        return payload['results']

    def query(self,params):
        if self.requests>=12:
            raise RuntimeError('OpenAlex request budget reached (12)')
        self.requests+=1
        return self.fetch(params)

    def resolve(self,doi):
        found=self.query({'filter':'doi:https://doi.org/'+doi.lower(),'per_page':1,'select':SELECT_FIELDS})
        if not found:
            return None
        requested=doi.casefold().removeprefix('https://doi.org/').strip()
        actual=str(found[0].get('doi') or '').casefold().removeprefix('https://doi.org/').strip()
        if actual!=requested:
            raise ValueError('OpenAlex DOI resolution did not match original DOI')
        return found[0]

    def citing(self,openalex_id,after):
        return self.query({'filter':'cites:'+norm_id(openalex_id)+',from_publication_date:'+after,
                           'per_page':25,'select':SELECT_FIELDS})

    def search(self,query,after):
        return self.query({'search':query,'filter':'from_publication_date:'+after,
                           'per_page':25,'select':SELECT_FIELDS})


def discover(originals, openalex=None, offline_catalogue=None):
    """Produce a review artifact. Network absent unless a client is passed."""
    if len(originals)>3:
        raise ValueError('This pilot is capped at three accepted originals')
    all_cases=[]
    for original in originals:
        anchor=anchor_for(original)
        start=original['original_publication'][:10]
        after=(date.fromisoformat(start)+timedelta(days=1)).isoformat()
        queries=[]; issues=[]; pool={}; resolved={}
        if openalex:
            if not original.get('doi'):
                issues.append('Original has no DOI: citation lineage cannot be resolved automatically')
            else:
                try:
                    resolved=openalex.resolve(original['doi']) or {}
                    queries.append('OpenAlex DOI resolution')
                except Exception as exc:
                    issues.append('DOI resolution error: '+str(exc)[:160])
            if resolved.get('id'):
                try:
                    for w in openalex.citing(resolved['id'],after):
                        if w.get('id'):pool[norm_id(w['id'])]=w
                    queries.append('OpenAlex direct citations (first 25)')
                except Exception as exc:
                    issues.append('Citation lookup error: '+str(exc)[:160])
            if anchor['status']=='passage_backed_interpretation_needs_review':
                for q in plan_queries(original)[:2]:
                    try:
                        for w in openalex.search(q,after):
                            if w.get('id'):pool[norm_id(w['id'])]=w
                        queries.append('OpenAlex scoped question search: '+q)
                    except Exception as exc:
                        issues.append('Question query error: '+str(exc)[:160])
        else:
            records=(offline_catalogue or {}).get(original['id'],{})
            resolved=records.get('original') or {}
            pool={norm_id(w['id']):w for w in records.get('works',[]) if isinstance(w,dict) and w.get('id')}
            queries=['offline supplied catalogue (NOT a live search)']
        matched=[]; background=[]; reasons=Counter()
        if resolved.get('id'):
            for work in pool.values():
                entry,reason=study_links(original,anchor,resolved,work)
                if entry:
                    (matched if entry['research_link_status']=='linked_research_draft' else background).append(entry)
                else:
                    reasons[reason]+=1
        else:
            issues.append('No validated OpenAlex original ID: graph connections cannot be checked')
        matched.sort(key=lambda x:(x['later_date'],x['later_id']),reverse=True)
        # Research discovery may expose up to eight plausible draft links; never auto-publish.
        case={'original_id':original['id'],'title':original['title'],'original_published':start,
              'source_kind':original['source_kind'],'original_url':original['source_url'],
              'anchor':anchor,'links':matched[:8]+background[:3],
              'drift':drift_summary(anchor,matched[:8]),
              'coverage':{'mode':'live_openalex_limited' if openalex else 'offline_catalogue_only',
                          'queries':queries,'unique_later_works_examined':len(pool),
                          'candidates_rejected':dict(reasons),'errors':issues,
                          'search_exhaustive':False},
              'finding':'Research links only. Later-world developments NOT assessed.',
              'meaningful_link_absence_established':False,
              'historical_outcome_verified':False,'auto_published':False}
        all_cases.append(case)
    return {'schema_version':1,'mode':'RADAR2_RESEARCH_CONNECTIONS_DRAFT',
            'as_of':date.today().isoformat(),'originals':all_cases,
            'summary':{'originals_examined':len(all_cases),
                       'with_research_links':sum(any(x['research_link_status']=='linked_research_draft' for x in c['links']) for c in all_cases),
                       'verified_outcome_assessments':0,'published':0},
            'limitations':'Citations and topic continuations track research, not historical fulfilment. Independent official observations and source review are required.'}


def markdown(result):
    out=['# Radar 2 — research connections (draft, not outcomes)','',
         'All links are machine-discovered and provisional. **No then-versus-now verdicts were generated.**','']
    for c in result['originals']:
        a=c['anchor'];out += ['## '+c['title'],'',
          '**Original:** '+c['original_url']+' ('+c['original_published']+')',
          '**Original passage:** '+(a['original_excerpt'] or 'UNAVAILABLE'),
          '**Question:** '+str(a['research_question'] or 'Needs original/source review'),
          '**Horizon:** '+str(a['horizon']['value']),
          '**Conditions:** '+str(a['conditions']['value']),
          '**Other evidence routes still needed:** '+str(a['possible_official_evidence_routes_not_yet_searched']),
          '**Search coverage:** '+c['coverage']['mode']+', '+str(c['coverage']['unique_later_works_examined'])+' candidates reviewed; incomplete.','']
        for l in c['links']:
            out += ['- ['+l['later_title']+']('+l['later_url']+') — '+l['later_date']+
                   ', '+', '.join(l['links'])+'; **machine draft, not an outcome**']
            if l['link_evidence']['later_quote']:
                out += ['  - Later abstract passage: '+l['link_evidence']['later_quote']]
            out += ['  - Comparability: '+str(l['comparability_warning'])]
        if not c['links']:
            out += ['**No research connection survived this limited search. This is not evidence that nothing happened.**']
        out += ['','**Interpretation:** '+c['finding'],'']
        if c['coverage']['errors']:
            out += ['**Unresolved/search problems:** '+'; '.join(c['coverage']['errors']),'']
    return '\n'.join(out)+'\n'


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--max-originals',type=int,default=3)
    p.add_argument('--offline',action='store_true')
    p.add_argument('--catalogue',type=Path,help='Optional cached OpenAlex work records; offline only')
    p.add_argument('--previous',type=Path,help='Previous connection review file, preserves confirmed/rejected links')
    p.add_argument('--output-prefix',type=Path,default=Path('RADAR2-CONNECTIONS-DRAFT'))
    args=p.parse_args(argv)
    if not 1<=args.max_originals<=3:
        p.error('pilot max is three originals')
    originals=select_ten(args.root)[:args.max_originals]
    client=None
    if not args.offline:
        key=os.getenv('OPENALEX_API_KEY','').strip()
        if not key:
            p.error('OPENALEX_API_KEY required for live; choose --offline for a no-network preview')
        client=OpenAlex(key,os.getenv('MAILTO') or os.getenv('OPENALEX_EMAIL'))
    catalogue=json.loads(args.catalogue.read_text()) if args.catalogue else {}
    result=discover(originals,client,catalogue)
    if args.previous and args.previous.exists():
        result=merge_reviews(json.loads(args.previous.read_text()),result)
    validate_report(result)
    target=args.output_prefix if args.output_prefix.is_absolute() else args.root/args.output_prefix
    target.with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    target.with_suffix('.md').write_text(markdown(result),encoding='utf-8')
    print(f'Radar 2 research connections: originals={len(originals)}, OpenAlex requests={client.requests if client else 0}; published=0')
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:
            f.write('## Radar 2 research connections (DRAFT ONLY)\n\n')
            f.write(f'- Accepted originals examined: **{len(originals)}**\n')
            f.write(f'- OpenAlex requests: **{client.requests if client else 0}**\n')
            f.write(f'- Original studies with candidate research links: **{result["summary"]["with_research_links"]}**\n')
            f.write('- Verified outcomes: **0**; published: **0**\n')
    # Report any network failure as failed workflow but still upload artifact.
    if any(c['coverage']['errors'] and any('error:' in x.lower() for x in c['coverage']['errors']) for c in result['originals']):
        raise SystemExit('Incomplete OpenAlex requests; review artifact saved')


if __name__=='__main__':
    main()
