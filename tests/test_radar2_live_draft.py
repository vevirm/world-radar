"""Live pilot is bounded and never publishes; no network needed for tests."""
from pathlib import Path
import pytest
from scripts.radar2_live_draft import select_originals, research, PILOT_IDS

ROOT=Path(__file__).resolve().parents[1]


def test_three_real_accepted_originals_with_researchable_passages():
    claims=select_originals(ROOT)
    assert [c['id'] for c in claims]==list(PILOT_IDS)
    assert len(claims)==3
    assert all(len(c['original_passage'])>70 for c in claims)
    assert all(c['research_question'] and c['issue_anchors'] for c in claims)


def test_rejects_any_original_not_in_live_radar1():
    with pytest.raises(ValueError,match='no longer accepted'):
        select_originals(ROOT,ids=['lead-not-in-radar1'])


def test_no_api_key_no_live_requests():
    with pytest.raises(ValueError,match='OPENAI_API_KEY'):
        research(select_originals(ROOT), '')


def test_ai_suggestions_remain_drafts_even_if_it_claims_realized():
    calls=[]
    def assessor(claim,key,route):
        calls.append((claim['id'],route))
        return {'status':'realized','what_expected':'Prediction',
                'what_happened':'This happened','evidence':[{'url':'https://example.org/official-report',
                'date':'2024-12-31','finding':'Test data'}]}
    results=research(select_originals(ROOT),'test-key',assessor)
    assert results['drafts_collected']==3
    assert results['publication_allowed'] is False
    assert len(calls)==3
    for row in results['cases']:
        assert 'status' not in row
        assert row['readiness'].startswith('draft_')
        assert row['unverified_assessment_draft']['proposed_status']=='realized'
        assert row['unverified_assessment_draft']['source_reviewed'] is False
        assert row['unverified_assessment_draft']['candidate_evidence'][0]['source_checked_independently'] is False


def test_failed_request_does_not_publish_or_claim_success():
    def assessor(claim,key,route):
        raise TimeoutError('source timeout')
    result=research(select_originals(ROOT),'test-key',assessor)
    assert result['drafts_collected']==0
    assert not result['publication_allowed']
    assert all(c['candidate_evidence_count']==0 for c in result['cases'])
