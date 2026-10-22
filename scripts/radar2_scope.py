#!/usr/bin/env python3
"""Fail-closed Radar 1 -> Radar 2 originals gate and no-scan legacy cleanup.

Radar 1's accepted academic manifest, not keyword discovery, controls admission.
Curated institutional originals are also included. Reports without an extracted
original passage remain in an explicit extraction queue, not a fake forecast.
Old bibliographic guesses are held apart from live comparisons for review.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CUTOFF = '2023-12-31'
EARLIEST = '1900-01-01'  # curated significant older institutional foresight may qualify
LEGACY_FIELDS = ('direction_evidence','follow_up_publications','field_developments',
                 'direction_evidence_quarantine')
RESEARCH_FIELDS = ('literature_signal','tentative_assessment','tentative_direction',
                   'what_expected_literature','what_happened_literature',
                   'eu_attribution','comparison_limits', 'literature_assessed_utc',
                   'literature_search_mode','last_question_routes')


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, data):
    path = Path(path)
    tmp = path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n',encoding='utf-8')
    tmp.replace(path)


def doi_of(raw):
    raw = str(raw or '').strip().lower()
    raw = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', raw)
    return re.sub(r'^doi:', '', raw).strip().rstrip('/')


def normalize_url(raw):
    return str(raw or '').strip().rstrip('/').lower()


def valid_period(value):
    return bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(value or '')[:10])
                and EARLIEST <= str(value)[:10] <= CUTOFF)


def uid(url, *, kind):
    digest = hashlib.sha256(normalize_url(url).encode('utf-8')).hexdigest()[:16]
    return ('report-' if kind == 'institutional' else 'lead-') + digest


def original_claims(root=ROOT):
    """Load only accepted academic originals plus curated pre-2024 EU reports.

    Any stale, duplicate, or inconsistent academic handoff fails before mutation.
    Source text is required before a claim can be evaluated; institutional
    records missing excerpts remain visible only as original-text tasks.
    """
    root = Path(root)
    active = load(root/'radar1-active.json')
    leads = load(root/'research-leads.json')
    rejected_path = root/'radar1-rejected.json'
    rejected = set(load(rejected_path).get('rejected', {})) if rejected_path.exists() else set()
    studies = active.get('studies')
    records = leads.get('leads')
    if not isinstance(studies, list) or not isinstance(records,list):
        raise ValueError('Missing accepted Radar 1 manifest or research leads; refusing Radar 2')
    if active.get('original_records') != len(studies) or not studies:
        raise ValueError('Radar 1 active manifest count mismatch; refusing Radar 2')
    academic_index = {}
    for row in records:
        doi = doi_of(row.get('doi'))
        if not doi or doi in academic_index:
            raise ValueError('Duplicate or missing Radar 1 DOI; refusing Radar 2')
        academic_index[doi] = row
    manifest_index = {}
    for s in studies:
        doi = doi_of(s.get('doi'))
        if not doi or doi in manifest_index or s.get('selection') != 'active':
            raise ValueError('Invalid/duplicate accepted manifest entry; refusing Radar 2')
        manifest_index[doi] = s
    if set(academic_index) != set(manifest_index):
        raise ValueError('Radar 1 saved studies and accepted manifest disagree; run Radar 1 audit before Radar 2')
    if set(manifest_index) & rejected:
        raise ValueError('Accepted DOI is in rejected registry; refusing Radar 2')

    out = []
    for doi, s in manifest_index.items():
        row = academic_index[doi]
        if not valid_period(row.get('date')) or str(s.get('date'))[:10] != str(row['date'])[:10]:
            raise ValueError('Out-of-period or inconsistent admitted study: '+doi)
        if row.get('radar1_selection') != 'active':
            raise ValueError('Non-active study present in Radar 1 live data: '+doi)
        seed = row.get('radar2_seed') or {}
        quote = ' '.join(str(seed.get('original_passage') or '').split())
        manifest_quote = ' '.join(str(s.get('original_passage') or '').split())
        if not quote or (manifest_quote and quote != manifest_quote):
            raise ValueError('Original passage not traceable to accepted Radar 1 study: '+doi)
        url = row.get('url') or 'https://doi.org/'+doi
        out.append({'id':uid(url,kind='academic'), 'source_kind':'academic',
                    'doi':doi, 'title':row['title'], 'source_url':url,
                    'original_publication':row['date'],
                    'publisher':row.get('publisher') or row.get('journal') or '',
                    'topic':row.get('journal') or 'European futures research',
                    'expected':quote, 'original_passage':quote,
                    'original_source_field':seed.get('source_field'),
                    'original_review_status':seed.get('source_status', 'indexed_abstract_not_full_text'),
                    'investigation_type':seed.get('investigation_type','strategic_future_question'),
                    'target_year':None, 'investigation_ready':True,
                    'original_text_status':'source_passage_available',
                    'abstract':row.get('abstract') or '',
                    'is_lead':True})

    # Priority source list is editorially curated institutional research.
    # The priority list also includes important new reports (e.g. 2023 SFR).
    reports = {}
    for s in load(root/'priority-sources.json').get('sources',[]):
        if not isinstance(s,dict):continue
        url = normalize_url(s.get('url'))
        if url and valid_period(s.get('date')):
            reports[url] = s
    for s in load(root/'priority-50.json').get('items',[]):
        if not isinstance(s,dict) or s.get('source_kind') not in ('Source-screened EU report','Curated publisher report'):
            continue
        url = normalize_url(s.get('url'))
        if url and valid_period(s.get('date')):
            reports[url] = {**reports.get(url, {}), **s}
    for url, row in sorted(reports.items(),key=lambda pair:(pair[1]['date'],pair[0])):
        title = str(row.get('title') or '').strip()
        original_url = str(row.get('url') or '').strip()
        if not title or not original_url.startswith('https://'):
            continue
        # A title, target date and verification badge are not original passage.
        # A later human/source-text extraction can populate this optional field.
        original = ' '.join(str(row.get('original_passage') or '').split())
        out.append({'id':uid(original_url,kind='institutional'), 'source_kind':'institutional',
                    'title':title, 'doi':'', 'source_url':original_url,
                    'original_publication':row['date'], 'publisher':row.get('publisher') or 'EU institutional report',
                    'topic':row.get('topic') or 'European foresight',
                    'expected':original, 'original_passage':original,
                    'original_source_field':'original_passage' if original else None,
                    'original_review_status':row.get('verification_status') or 'institutional_original_curated',
                    'investigation_type':'institutional_foresight',
                    'target_year':row.get('target_year'),
                    'investigation_ready':bool(original),
                    'original_text_status':'source_passage_available' if original else 'needs_original_passage',
                    'full_text_url':row.get('full_text_url') or original_url,
                    'abstract':'', 'is_lead':True})
    urls = [normalize_url(c['source_url']) for c in out]
    if len(set(urls)) != len(out):
        raise ValueError('Duplicate original URLs across accepted studies/reports')
    return out


def fresh(c):
    """Conservative new record; never invent a prognosis for title-only reports."""
    return {**c, 'what_expected':c['original_passage'] if c['investigation_ready']
            else 'Original passage not yet extracted; no forecast attributed.',
            'what_happened':'Not yet assessed against subsequent dated evidence.',
            'status':'not_yet_assessed','evidence':[],'counterevidence':[],
            'follow_up_publications':[],'field_developments':[],'direction_evidence':[],
            'screening_status':'original_passage_for_followup' if c['investigation_ready']
            else 'original_full_text_needed',
            'screening_reason':'Accepted Radar 1 historical original; investigate its quoted question.'
            if c['investigation_ready'] else 'Curated institutional report; extract original passage before research.',
            'candidate_excerpt':'','candidate_year':None}


def reconcile(root=ROOT, *, apply=False):
    """Preview or prune live Radar 2 state; never use discarded originals.

    A prior report is retained only if its ID and original URL/date match.
    Unreviewed scholarly trails move to reversible holding, not the atlas.
    Safe archive of the WHOLE pre-apply file is also uploaded by workflow.
    """
    root = Path(root)
    claims = original_claims(root)
    raw = load(root/'retrospective-results.json')
    old = raw.get('entries') or {}
    if not isinstance(old,dict): raise ValueError('Unexpected Radar 2 database schema')
    accepted_ids = {c['id'] for c in claims}
    retained, archived = {}, {}
    rebuilt = Counter()
    for c in claims:
        p = old.get(c['id'])
        r = fresh(c)
        if isinstance(p,dict) and normalize_url(p.get('source_url'))==normalize_url(c['source_url']) and \
                str(p.get('original_publication') or '')[:10] == c['original_publication'][:10]:
            rebuilt['matching_legacy_originals'] += 1
            # Research attempt counters are useful for round-robin selection;
            # no unverified findings or status may enter the public result.
            for key in ('research_attempts','literature_attempts','literature_live_attempts'):
                try:r[key]=max(0,int(p.get(key) or 0))
                except (ValueError,TypeError):r[key]=0
            trails={k:p.get(k) for k in LEGACY_FIELDS+('evidence','counterevidence') if p.get(k)}
            if trails:
                archived[c['id']]={'original_title':c['title'], 'original_url':c['source_url'],
                                   'previous_unreviewed_trails':trails}
                rebuilt['originals_with_legacy_links_for_review']+=1
            # The real editorial review registry (verified-outcomes.json) is
            # independent and remains untouched by this action.
        elif p:
            rebuilt['mismatched_legacy_originals']+=1
        retained[c['id']] = r
    active_legacy = set(old) & accepted_ids
    rejected = sorted(set(old)-active_legacy)
    result = {'mode':'apply' if apply else 'preview', 'generated_utc':datetime.now(timezone.utc).isoformat(),
              'accepted_academic_originals':sum(c['source_kind']=='academic' for c in claims),
              'curated_institutional_originals':sum(c['source_kind']=='institutional' for c in claims),
              'institutional_needing_original_passage':sum(c['source_kind']=='institutional' and not c['investigation_ready'] for c in claims),
              'research_ready_originals':sum(c['investigation_ready'] for c in claims),
              'saved_legacy_entries':len(old), 'legacy_entries_outside_current_radar1':len(rejected),
              'matched_legacy_entries':rebuilt['matching_legacy_originals'],
              'mismatched_legacy_entries':rebuilt['mismatched_legacy_originals'],
              'matching_originals_with_old_links_held_for_review':rebuilt['originals_with_legacy_links_for_review'],
              'live_entries_after_apply':len(retained),
              'old_exclusion_examples':[{'id':key,'title':str(old[key].get('title') or '')[:130]} for key in rejected[:20]],
              'institutional_examples_needing_original_text':[{'title':c['title'],'url':c['source_url']} for c in claims if c['source_kind']=='institutional' and not c['investigation_ready']][:10],
              'method':'No API calls. Old academic link matches are separated, never treated as outcomes. '
                       'The complete pre-apply database must be backed up before apply.'}
    if apply:
        previous_holding = root/'radar2-legacy-holding.json'
        if previous_holding.exists():
            earlier = load(previous_holding).get('entries') or {}
            if not isinstance(earlier,dict):
                raise ValueError('Invalid existing legacy evidence holding file; refusing to overwrite')
            archived = {**earlier, **archived}
        save(root/'radar2-legacy-holding.json', {'schema_version':1,
             'explanation':'Unverified prior links for ACCEPTED originals only. NOT used by scanner or published reports.',
             'entries':archived})
        save(root/'retrospective-results.json', {'entries':retained})
        save(root/'radar2-original-text-queue.json', {'schema_version':1,
            'status':'Original report text to extract before assessment; titles are not forecast claims',
            'reports':[{'title':c['title'],'published':c['original_publication'],
                        'publisher':c['publisher'],'url':c['source_url'],
                        'full_text_url':c['full_text_url']} for c in claims
                       if c['source_kind']=='institutional' and not c['investigation_ready']]})
        save(root/'radar2-scope-ready.json', {'schema_version':1, 'activated_utc':result['generated_utc'],
             'policy':'Only current Radar 1 accepted academic originals and curated EU institutional reports; old links quarantined.'})
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--apply',action='store_true')
    p.add_argument('--report',type=Path,default=None)
    a=p.parse_args()
    r=reconcile(a.root,apply=a.apply)
    save(a.report or a.root/'radar2-scope-preview.json',r)
    print(json.dumps(r,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
