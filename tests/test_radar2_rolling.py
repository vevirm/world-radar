"""Safeguards for the rotating Radar 2 queue (no network)."""
import json
from datetime import date
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import radar2_rolling as m


def test_real_manifest_has_routed_future_claims():
    ready,stat=m.prepare(ROOT)
    assert stat['accepted']>=100
    assert stat['unmapped']>0  # Never conceal coverage gaps.
    assert len(ready)>=3
    assert stat['route_mismatch_requires_review']>=1
    assert not any('Developments in Energy use for Transport' in x['title'] for x in ready)
    assert all(x['original_passage'] and x['route_id'] for x in ready)


def test_rotation_does_not_select_same_claim_next_run():
    ready,stat=m.prepare(ROOT)
    state={'schema_version':1,'completed':{}}
    first=m.choose_batch(ready,state,n=3,today=date(2026,10,23))
    assert len(first)==3
    assert len({x['route_id'] for x in first})==3
    state['completed'].update({x['id']:'2026-10-23' for x in first})
    second=m.choose_batch(ready,state,n=3,today=date(2026,10,24))
    assert set(x['id'] for x in first).isdisjoint(x['id'] for x in second)


def test_cannot_mark_failed_search_complete():
    state={'schema_version':1,'completed':{}}
    rep={'cases':[{'original_id':'1','status':'search_failed_or_partial','queries_attempted':['a'],'queries_completed':[]},
                  {'original_id':'2','status':'question_level_empirical_leads_unverified','queries_attempted':['a'],'queries_completed':['a']},
                  {'original_id':'3','status':'no_same_construct_evidence_in_bounded_openalex_search','queries_attempted':['a'],'queries_completed':['a']} ]}
    new=m.updated_state(state,rep,date(2026,10,23))
    assert '1' not in new['completed']
    assert set(new['completed']) == {'2','3'}


def test_inspect_does_not_search_or_change_checkpoint(tmp_path):
    # The real manifest is needed for selection, so use its root; inspect writes
    # reports in an isolated directory only in this test with a mock prepare.
    orig=m.prepare
    try:
        m.prepare=lambda root:([{'id':'claim1','title':'Scenario','original_publication':'2011-01-01',
          'route_id':'eu_ageing','source_url':'https://example.org','original_passage':'ex'}],
          {'accepted':1,'passage_backed':1,'mapped':1,'future_facing_with_route':1,'unmapped':0})
        result=m.run(tmp_path,mode='inspect',batch_size=1,researcher=lambda *_: (_ for _ in ()).throw(AssertionError('search attempted')))
        assert result['status']=='inspect_only_no_research_requests'
        assert not (tmp_path/m.STATE_FILE).exists()
        assert json.loads((tmp_path/m.REPORT_FILE).read_text())['publication_allowed'] is False
    finally:
        m.prepare=orig


def test_state_bad_schema_is_not_discarded(tmp_path):
    p=tmp_path/m.STATE_FILE
    p.write_text('{"schema_version":99,"completed":{"x":"2026-01-01"}}')
    import pytest
    with pytest.raises(ValueError):m.load_state(p)


def test_search_persists_only_completed_cases_without_publishing(tmp_path, monkeypatch):
    claim={'id':'claim7','title':'EU forecast about floods','original_publication':'2015-01-01',
           'route_id':'europe_flood_damage','source_url':'https://example.org/source',
           'original_passage':'A documented future-facing quote', 'question_card':{},
           'historical_focus':'scenario','topic_group':'climate_ecosystems'}
    monkeypatch.setattr(m,'prepare',lambda root: ([claim],{
        'accepted':1,'passage_backed':1,'mapped':1,'future_facing_with_route':1,'unmapped':0}))
    monkeypatch.setattr(m,'official_route_for',lambda c: None)
    monkeypatch.setattr(m,'markdown',lambda report: '# Later research leads (mocked)')
    monkeypatch.setenv('OPENALEX_API_KEY','test-placeholder')
    fake=lambda claims,key: {'cases':[{'original_id':'claim7','status':'question_level_empirical_leads_unverified',
        'queries_attempted':['a'],'queries_completed':['a']}],
        'verified_outcomes':0,'published_outcomes':0}
    report=m.run(tmp_path,mode='search',batch_size=1,today=date(2026,10,23),researcher=fake)
    assert report['verified_outcomes']==0
    assert report['publication_allowed'] is False
    assert json.loads((tmp_path/m.STATE_FILE).read_text())['completed']=={'claim7':'2026-10-23'}
