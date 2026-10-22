"""Saved source cases remain a separate, non-publishing review queue."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json

from scripts.radar2_evidence_review import audit, audit_case, evidence_role, later_than_original
from scripts.radar2_scope import original_claims
from scripts.retrospective_radar import normalize

ROOT = Path(__file__).resolve().parents[1]


def examples():
    return json.loads((ROOT/'radar2-curated-evidence-pilot.json').read_text(encoding='utf-8'))['cases']


def accepted():
    return {r['id']:r for r in original_claims(ROOT)}


def test_workflow_does_not_make_public_verdicts():
    result=audit(ROOT,ROOT/'radar2-curated-evidence-pilot.json')
    # Read the living Radar 1 admission manifest: a subsequent successful scan
    # may add eligible originals without changing Radar 2's safety contract.
    current = original_claims(ROOT)
    active = json.loads((ROOT/'radar1-active.json').read_text(encoding='utf-8'))
    academic = [c for c in current if c['source_kind'] == 'academic']
    assert len(academic) == active['original_records'] == len(active['studies'])
    assert result['accepted_originals'] == len(current)
    assert set(c['id'] for c in current) == set(accepted())
    assert result['reviewed_pilot_cases']==len(examples())
    assert not result['publication_allowed']
    assert result['structurally_usable_drafts'] == sum(c['status'].startswith('draft_') for c in result['cases'])
    assert result['blocked'] == sum(c['status'].startswith('blocked_') for c in result['cases'])
    assert any(c['original_id']=='report-3eff29ec207eb208' and c['status'].startswith('blocked_') for c in result['cases'])
    assert all(x['publication_approval'].startswith('NOT APPROVED') for x in result['cases'])
    assert all(not y['source_checked_independently'] for x in result['cases'] for y in x['evidence'])


def test_out_of_scope_original_rejected_even_with_plausible_sources():
    example=deepcopy(examples()[0]);example['original_id']='lead-fake'
    result=audit_case(example,accepted())
    assert result['status']=='rejected_original_not_accepted'


def test_identical_original_date_and_link_required():
    claim=deepcopy(examples()[0]);claim['historical_date']='2022-01-01'
    assert any('date differs' in msg for msg in audit_case(claim,accepted())['blockers'])
    claim=deepcopy(examples()[0]);claim['original_url']='https://other.invalid/source'
    assert any('URL does not match' in msg for msg in audit_case(claim,accepted())['blockers'])


def test_bad_newer_evidence_date_not_accepted():
    claim=deepcopy(examples()[1]);claim['findings'][0]['year']=2010
    result=audit_case(claim,accepted())
    assert result['status'].startswith('blocked_')
    assert result['evidence'][0]['structural_errors']
    assert not later_than_original('2011','2011-08-15')
    assert later_than_original('2012','2011-08-15')


def test_announcements_and_projections_are_not_actual_outcomes():
    assert evidence_role('documented_policy_response')!='observed_or_evaluated'
    assert evidence_role('documented_implementation')!='observed_or_evaluated'
    assert evidence_role('projection')!='observed_or_evaluated'
    assert evidence_role('market_observation')=='observed_or_evaluated'


def test_automatic_assessment_is_never_promoted_to_verified_status():
    original=accepted()[examples()[0]['original_id']]
    ai={'status':'realized','what_expected':'It will happen',
        'what_happened':'Everyone confirms it',
        'evidence':[{'url':'https://example.org/claim','date':'2025-01-01','finding':'The outcome happened.'}],
        'reasoning':'Clearly realized'}
    result=normalize(original,ai)
    assert result['status']=='not_yet_assessed'
    assert not result['evidence']
    assert result['review_required']
    assert result['unverified_assessment_draft']['proposed_status']=='realized'
    assert not result['unverified_assessment_draft']['source_reviewed']
