#!/usr/bin/env python3
"""Build a small, source-traceable THEN -> SINCE -> NOW public comparison set.

Only editorially sourced observations from the curated registry are eligible.
OpenAlex links, automated labels and model-written summaries cannot auto-promote.
This is *not* a general-purpose automatic fact-checker.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlparse

try:
    from .radar2_scope import original_claims
except ImportError:
    from radar2_scope import original_claims

ROOT = Path(__file__).resolve().parents[1]
OBSERVED = {'independent_institutional_evaluation', 'market_observation',
            'retail_observation', 'independent_outcome_evaluation'}
IMPLEMENTATION = {'documented_policy_response', 'documented_implementation'}
PROJECTED = {'market_status_and_projection'}
ALLOWED = OBSERVED | IMPLEMENTATION | PROJECTED
SEARCH_TYPES = {'official_statistics', 'independent_evaluation', 'academic_research',
                'agency_report', 'policy_documents', 'source_archive'}
UNRESOLVED_REASONS = {'no_comparable_observations', 'original_proposition_not_operational',
                      'changed_context', 'attribution_not_established',
                      'original_horizon_not_reached', 'no_substantive_evidence_found'}
REQUIRED_INTERPRETATION = ('similarities', 'differences', 'still_unestablished', 'present_relevance')


def original_passage(case, original):
    passage = original.get('original_passage') or case.get('original_excerpt') or ''
    if len(passage.strip()) < 85:
        raise ValueError('Original source passage missing or too thin: '+original['id'])
    if not original.get('original_passage'):
        trace = case.get('passage_review') or {}
        if (trace.get('source_url') != original['source_url'] or
            trace.get('verification') != 'checked_against_original_source' or
            not trace.get('reviewed_on')):
            raise ValueError('Institutional original passage not source-checked: '+original['id'])
    return passage


def validate_original(case, originals, seen):
    oid = case.get('original_id')
    if oid not in originals or oid in seen:
        raise ValueError('Comparison not accepted by Radar 1 or duplicate: '+str(oid))
    seen.add(oid)
    original = originals[oid]
    if not https_url(original['source_url']) or original['source_url'] != case.get('original_url'):
        raise ValueError('Original URL not traceable: '+oid)
    if str(original['original_publication'])[:10] != str(case.get('historical_date'))[:10]:
        raise ValueError('Original date not traceable: '+oid)
    return oid, original, original_passage(case, original)


def validated_interpretation(case, oid):
    """Force explicit reasoning, including what still cannot be established."""
    interpretation = case.get('interpretation') or {}
    for key in REQUIRED_INTERPRETATION:
        if len(str(interpretation.get(key) or '').strip()) < 25:
            raise ValueError('Missing reasoning about '+key+': '+oid)
    return {k:interpretation[k] for k in REQUIRED_INTERPRETATION}


def reviewed_unresolved(case, oid, original, passage):
    """A no-link finding requires documented independent evidence routes.

    Missing OpenAlex hits is not sufficient to establish a genuine evidence gap.
    """
    if not all(case.get(k) for k in ('source_specific_proposition', 'radar2_question',
                                     'scope_caveat', 'unresolved_explanation')):
        raise ValueError('Unresolved case missing original question or explanation: '+oid)
    if case.get('reason') not in UNRESOLVED_REASONS:
        raise ValueError('Unresolved case requires a specific reason: '+oid)
    audit = case.get('search_audit') or {}
    period = audit.get('period_checked') or {}
    original_year = int(str(case['historical_date'])[:4])
    start, end = int(period.get('from_year') or 0), int(period.get('through_year') or 0)
    reviewed_on = str(audit.get('reviewed_on') or '')
    if (start <= original_year or end < start or end > dt.datetime.now(dt.timezone.utc).year
            or not reviewed_on or reviewed_on > dt.datetime.now(dt.timezone.utc).date().isoformat()):
        raise ValueError('Unresolved case must date its post-publication search: '+oid)
    searches = audit.get('checks') or []
    families = set()
    for check in searches:
        family = check.get('source_type')
        if (family not in SEARCH_TYPES or not https_url(check.get('url'))
                or len(str(check.get('query_or_material') or '').strip()) < 12
                or len(str(check.get('result') or '').strip()) < 35
                or not check.get('checked_on') or str(check['checked_on']) > reviewed_on):
            raise ValueError('Unresolved case lacks attributable research audit: '+oid)
        families.add(family)
    if len(searches) < 2 or len(families) < 2:
        raise ValueError('Unresolved case needs two independent evidence routes: '+oid)
    return {'id':oid, 'title':original['title'], 'historical_year':original_year,
            'type':'EU institution' if original['source_kind']=='institutional' else 'Academic foresight',
            'original_url':original['source_url'], 'original_excerpt':passage[:850],
            'original_claim':case['source_specific_proposition'],
            'question':case['radar2_question'], 'reason':case['reason'],
            'explanation':case['unresolved_explanation'], 'limitation':case['scope_caveat'],
            'search_audit':{'reviewed_on':reviewed_on, 'period_checked':period, 'checks':searches},
            'status':'Connection not established after documented research',
            'interpretation':validated_interpretation(case, oid)}


def https_url(url):
    p = urlparse(str(url or '').strip())
    return p.scheme == 'https' and bool(p.hostname)


def build(root=ROOT):
    root = Path(root)
    registry = json.loads((root/'radar2-curated-evidence-pilot.json').read_text(encoding='utf-8'))
    originals = {o['id']:o for o in original_claims(root)}
    cards = []
    seen = set()
    for case in registry.get('cases', []):
        oid, original, passage = validate_original(case, originals, seen)
        if not (case.get('source_specific_proposition') and case.get('radar2_question')
                and case.get('assessment') and case.get('scope_caveat')):
            raise ValueError('Missing substantive claim, question, finding or limitation: '+oid)
        interpretation = validated_interpretation(case, oid)
        evidence=[]
        for item in case.get('findings') or []:
            y=int(item.get('year') or 0)
            kind=item.get('evidence_type')
            if kind not in ALLOWED or not https_url(item.get('url')):
                raise ValueError('Unqualified evidence or URL: '+oid)
            if (y <= int(case['historical_date'][:4]) or y > dt.datetime.now(dt.timezone.utc).year
                    or len(item.get('evidence',''))<35 or not item.get('document')):
                raise ValueError('Evidence lacks later date or source text: '+oid)
            evidence.append({'year':y, 'document':item['document'],
                             'url':item['url'], 'finding':item['evidence'],
                             'type':('observed' if kind in OBSERVED else
                                     'policy_or_project' if kind in IMPLEMENTATION else
                                     'projection_mixed'), 'source_type':kind})
        if len(evidence) < 2 or not any(e['type']=='observed' for e in evidence):
            raise ValueError('At least two independent later leads and one observed result required: '+oid)
        evidence.sort(key=lambda e:e['year'])
        kind = 'EU institution' if original['source_kind']=='institutional' else 'Academic foresight'
        cards.append({'id':oid, 'title':original['title'],
                      'historical_year':int(case['historical_date'][:4]),
                      'type':kind, 'original_url':original['source_url'],
                      'original_excerpt':passage[:850],
                      'original_claim':case['source_specific_proposition'],
                      'condition':case['scenario_condition'],
                      'question':case['radar2_question'],
                      'subsequent_evidence':evidence,
                      'what_happened':case['assessment'],
                      'limitation':case['scope_caveat'],
                      'interpretation':interpretation,
                      'status':'Evidence-based interim assessment',
                      'source_review':'Editorial source comparison, not automated forecast scoring'})
    unresolved=[]
    for case in registry.get('unresolved_cases', []):
        oid, original, passage = validate_original(case, originals, seen)
        unresolved.append(reviewed_unresolved(case, oid, original, passage))
    return {'schema_version':2, 'as_of':registry.get('as_of'),
            'method':'Reviewed originals support either a dated then-versus-now comparison or a documented inability to establish a link after scoped source checks. These are distinct from originals not yet researched. OpenAlex leads alone are never proof of developments or of their absence.',
            'total_accepted_originals':len(originals),
            'documented_comparisons':len(cards),
            'documented_unresolved':len(unresolved),
            'unassessed_originals':len(originals)-len(cards)-len(unresolved),
            'comparisons':cards, 'unresolved':unresolved}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    data=build(args.root)
    target=args.output or args.root/'radar2-comparisons.json'
    target.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f"Documented comparisons: {data['documented_comparisons']} / {data['total_accepted_originals']} accepted originals")

if __name__=='__main__': main()
