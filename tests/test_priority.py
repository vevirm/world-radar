"""The historical top 50 is a triage shortlist, not an accuracy verdict."""
from datetime import date
from pathlib import Path
from unittest.mock import patch
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import priority
import radar

def test_top50_preferred_window_and_source_links():
    data=priority.refresh(date(2026,10,19))
    assert data['count']==50
    assert all(x['url'].startswith('https://') for x in data['items'])
    assert len({x['review_priority'] for x in data['items']})==50
    assert sum(x['age_band'].startswith('preferred') for x in data['items'])>=35
    assert all(x['accuracy_verdict'] in ('Not evaluated','Observed','Partly observed','Not observed','Too early / unresolved','Scenario (not testable)') for x in data['items'])

def test_prioritised_sources_connect_to_issuer_queue(tmp_path):
    with patch.object(radar,'STATE',tmp_path/'radar-state.json'), patch.object(radar,'CANDIDATES',tmp_path/'candidates.json'), patch.object(radar,'page_queue',return_value=[]):
        radar.discover(float('inf'),once=True)
    state=json.loads((tmp_path/'radar-state.json').read_text())
    linked=[q for q in state['queue'] if q['source_mode'].startswith('curated retrospective priority')]
    assert len(linked)>=20
    assert all(q['actor_id'] in {a['id'] for a in radar.get_registry()} for q in linked)

def test_15year_boundary_is_rolling():
    assert radar.earliest_date(date(2026,10,19))==date(2011,10,19)
    assert radar.earliest_date(date(2030,2,28))==date(2015,2,28)
