#!/usr/bin/env python3
"""Optional bounded Radar 2 web-search research: draft-only, never publishes.

Uses *already accepted* Radar 1 originals with existing text. Requires an
OPENAI_API_KEY. By design all source claims remain unverified and the artifacts
are separate from the live research collection. No bulk scan and no commits.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

try:
    from .radar2_scope import original_claims
    from .radar2_questions import question_card
    from .retrospective_radar import retrieve_assessment, normalize
    from .radar2_evidence_review import later_than_original, credible_link
except ImportError:
    from radar2_scope import original_claims
    from radar2_questions import question_card
    from retrospective_radar import retrieve_assessment, normalize
    from radar2_evidence_review import later_than_original, credible_link

ROOT = Path(__file__).resolve().parents[1]
# Explicit diverse editorial pilot, not a ranking or automatic admission list.
PILOT_IDS = (
    'lead-726d2d4ffd64aca7',  # European hydrogen decarbonisation scenarios
    'lead-9363d7d494bf528e',  # Organic food demand scenarios
    'lead-571fb03297fcebcc',  # European migration-policy scenarios
)


def select_originals(root=ROOT, ids=PILOT_IDS):
    originals = {r['id']: r for r in original_claims(root)}
    selected = []
    for oid in ids:
        if oid not in originals:
            raise ValueError(f'Pilot original no longer accepted by Radar 1: {oid}')
        claim = dict(originals[oid])
        card = question_card(claim)
        if not claim.get('original_passage') or card['readiness'] in ('source_review_required','original_text_required'):
            raise ValueError(f'Pilot original needs better original text: {oid}')
        claim['research_question'] = card['evidence_question']
        claim['issue_anchors'] = card['issue_anchors']
        selected.append(claim)
    return selected


def research(claims, key, assessor=retrieve_assessment):
    if not key:
        raise ValueError('OPENAI_API_KEY is not configured; no live requests were made')
    results = []
    for i, claim in enumerate(claims):
        row = {'original_id': claim['id'], 'title':claim['title'],
               'original_url':claim['source_url'],
               'original_publication':claim['original_publication'],
               'original_passage':claim['original_passage'],
               'historical_question':claim['research_question'],
               'readiness':'draft_requires_original_and_evidence_review'}
        try:
            # Route through distinct source classes, not repeated title searches.
            draft = normalize(claim, assessor(claim, key, route=(4, 0, 9)[i % 3]))
            suggestions = draft['unverified_assessment_draft']
            for group in ('candidate_evidence', 'candidate_counterevidence'):
                for evidence in suggestions[group]:
                    evidence['structural_cautions'] = []
                    if not credible_link(evidence.get('url')):
                        evidence['structural_cautions'].append('not_a_credible_https_url')
                    if evidence.get('url','').rstrip('/') == claim['source_url'].rstrip('/'):
                        evidence['structural_cautions'].append('original_not_independent_later_evidence')
                    if not later_than_original(evidence.get('date'),claim['original_publication']):
                        evidence['structural_cautions'].append('publication_date_not_confirmed_after_original')
                    evidence['source_checked_independently'] = False
            valid = [e for group in ('candidate_evidence','candidate_counterevidence')
                     for e in suggestions[group] if not e['structural_cautions']]
            row['research_status'] = 'draft_collected' if valid else 'draft_no_usable_dated_source'
            row['unverified_assessment_draft'] = suggestions
            row['candidate_evidence_count'] = len(valid)
        except Exception as exc:
            # Error is preserved for diagnosis, but no fake success/observations.
            row['research_status'] = 'research_failed'
            row['failure'] = str(exc)[:280]
            row['candidate_evidence_count'] = 0
        results.append(row)
    return {'schema_version':1, 'mode':'LIVE_SOURCE_RESEARCH_DRAFT_ONLY',
            'generated_utc':datetime.now(timezone.utc).isoformat(),
            'originals_considered':len(claims),
            'drafts_collected':sum(c['research_status']=='draft_collected' for c in results),
            'publication_allowed':False,
            'warning':'Neither AI-generated summaries nor source URLs establish what happened. Review original context, every source document and its measurement before publishing.',
            'cases':results}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--output',type=Path,default=ROOT/'RADAR2-LIVE-RESEARCH-DRAFT.json')
    args=p.parse_args()
    claims=select_originals(args.root)
    output = args.output
    result=research(claims,os.getenv('OPENAI_API_KEY','').strip())
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    message=f"Radar 2 LIVE DRAFTS: {result['drafts_collected']}/{len(claims)} collected; 0 published or independently verified"
    print(message,flush=True)
    summary=os.getenv('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a',encoding='utf-8') as out:
            out.write('## Radar 2: three-study live evidence research (DRAFT ONLY)\n\n')
            out.write(f"- Drafts collected: **{result['drafts_collected']} / {len(claims)}**\n")
            out.write('- **0 source-verified outcomes; 0 publications; 0 research data changes**\n')
            out.write('- Download the JSON artifact to review citations, original questions and limitations.\n')
    if result['drafts_collected'] != len(claims):
        raise SystemExit('One or more source searches failed; saved partial draft artifact, not verified results')


if __name__=='__main__':
    main()
