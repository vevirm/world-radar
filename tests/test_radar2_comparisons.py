"""Pure local acceptance tests for the public then/since comparison gate."""
import copy
import json
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import radar2_comparisons as subject
from radar2_scope import original_claims
import radar2_live_draft as live


def test_all_comparisons_have_accepted_originals_and_observed_evidence():
    data=subject.build(ROOT)
    assert data['total_accepted_originals']==len(original_claims(ROOT))
    curated=json.loads((ROOT/'radar2-curated-evidence-pilot.json').read_text())
    assert len(data['comparisons'])==len(curated['cases'])
    assert data['unassessed_originals']==data['total_accepted_originals']-len(curated['cases'])-len(curated.get('unresolved_cases', []))
    for c in data['comparisons']:
        assert len(c['original_excerpt']) >= 85
        assert c['historical_year'] < min(s['year'] for s in c['subsequent_evidence'])
        assert any(x['type']=='observed' for x in c['subsequent_evidence'])
        assert c['limitation'] and c['condition']
        assert all(x['url'].startswith('https://') for x in c['subsequent_evidence'])


def test_unaccepted_and_unsourced_original_fail_closed(tmp_path,monkeypatch):
    from shutil import copyfile
    # Use the real manifest reader on the stable checked-in originals and a
    # temporary independent copy of just the editable editorial registry.
    original_data=json.loads((ROOT/'radar2-curated-evidence-pilot.json').read_text())
    monkeypatch.setattr(subject,'original_claims',lambda root: [{
        'id':c['original_id'], 'source_url':c['original_url'],
        'original_publication':c['historical_date'],
        'original_passage':('An original evidence source passage that is long enough to qualify as a traced original projection or strategic question.' if c['original_type']=='academic' else ''),
        'title':c['title'], 'source_kind':c['original_type']}
        for c in original_data['cases']])
    def case_with(modifier):
        d=copy.deepcopy(original_data)
        modifier(d)
        (tmp_path/'radar2-curated-evidence-pilot.json').write_text(json.dumps(d))
        return d
    case_with(lambda d: d['cases'][0].update(original_id='a-rejected-lead'))
    with pytest.raises(ValueError,match='not accepted'):
        subject.build(tmp_path)
    case_with(lambda d: d['cases'][2].update(original_excerpt=''))
    with pytest.raises(ValueError,match='passage missing'):
        subject.build(tmp_path)
    case_with(lambda d: d['cases'][0].update(findings=[{'year':2025,'document':'Unreviewed policy press release','url':'https://example.org/','evidence':'The EU adopted rules in 2025 but real-world performance is completely unspecified.','evidence_type':'documented_policy_response'}]))
    with pytest.raises(ValueError,match='At least two'):
        subject.build(tmp_path)


def test_live_openalex_search_remains_bibliographic_only():
    """The current live discovery API does not certify observed real-world outcomes."""
    claims=live.select_originals(ROOT)
    assert [c['id'] for c in claims]==list(live.PILOT_IDS)
    assert all(1 <= len(live.discovery_queries(c)) <= 2 for c in claims)
    for claim in claims:
        assert live.filter_candidate(claim, {
            'title':'Trading financial futures on the Tokyo Stock Exchange',
            'doi':'https://doi.org/10.1234/unrelated',
            'publication_date':'2025-04-01',
            'abstract':'Japanese financial derivatives, unrelated to European foresight.'
        }) is None
    result=live.research(claims,'existing-openalex-key',lambda *_: [])
    assert result['publication_allowed'] is False
    assert result['source_verified_outcomes']==0


def test_site_does_not_advertise_old_archive_or_unverified_verdicts():
    html=(ROOT/'index.html').read_text()
    assert '1,366' not in html
    assert 'radar2-comparisons.json' in html
    assert 'living-atlas.json' in html
    assert 'Then' in html and 'SINCE' in html


def test_researched_but_unestablished_is_not_unassessed(tmp_path, monkeypatch):
    """A documented research gap is itself a first-class outcome; mere absence is not."""
    registry = json.loads((ROOT/'radar2-curated-evidence-pilot.json').read_text())
    original_case = registry['cases'].pop()
    report = copy.deepcopy(original_case)
    report.update(
        unresolved_explanation='A dated review of public reports and scholarly research did not establish whether the warning was resolved through measurable diversification.',
        reason='no_comparable_observations',
        search_audit={
            'period_checked': {'from_year': 2023, 'through_year': 2026},
            'reviewed_on': '2026-10-21',
            'checks': [
                {'source_type': 'official_statistics', 'query_or_material': 'Relevant EU supply indicators 2023–2026',
                 'url': 'https://example.org/statistics', 'checked_on': '2026-10-20',
                 'result': 'The published indicators do not establish the counterfactual dependency trajectory required by this question.'},
                {'source_type': 'academic_research', 'query_or_material': 'European supply diversification outcome evaluations',
                 'url': 'https://example.org/research', 'checked_on': '2026-10-21',
                 'result': 'The reviewed studies discuss risks and interventions but do not supply comparable realised dependency measurements.'}
            ]
        }
    )
    registry['unresolved_cases'] = [report]
    (tmp_path/'radar2-curated-evidence-pilot.json').write_text(json.dumps(registry))
    all_cases = registry['cases'] + [original_case]
    monkeypatch.setattr(subject, 'original_claims', lambda root: [{
        'id':c['original_id'], 'source_url':c['original_url'],
        'original_publication':c['historical_date'],
        'original_passage':('Original source passage for a verified historical European development assessment with sufficient substantive content and scope.' if c['original_type']=='academic' else ''),
        'title':c['title'], 'source_kind':c['original_type']}
        for c in all_cases])
    built=subject.build(tmp_path)
    assert len(built['comparisons'])==len(registry['cases'])
    assert len(built['unresolved'])==1
    assert built['unassessed_originals']==0
    assert built['unresolved'][0]['reason']=='no_comparable_observations'
    assert len(built['unresolved'][0]['search_audit']['checks'])==2
    # One OpenAlex-style search route is not enough to claim a real evidence gap.
    report['search_audit']['checks'] = report['search_audit']['checks'][:1]
    (tmp_path/'radar2-curated-evidence-pilot.json').write_text(json.dumps(registry))
    with pytest.raises(ValueError,match='two independent evidence routes'):
        subject.build(tmp_path)
    report['search_audit']['checks'] = []
    report['reason'] = 'nothing_found_in_openalex'
    (tmp_path/'radar2-curated-evidence-pilot.json').write_text(json.dumps(registry))
    with pytest.raises(ValueError,match='specific reason'):
        subject.build(tmp_path)


def test_explicit_reasoning_is_required_for_each_published_comparison(tmp_path,monkeypatch):
    data=json.loads((ROOT/'radar2-curated-evidence-pilot.json').read_text())
    monkeypatch.setattr(subject,'original_claims',lambda root:[{
        'id':c['original_id'], 'source_url':c['original_url'],
        'original_publication':c['historical_date'],
        'original_passage':('A traced original passage identifying a meaningful future-oriented European question and its conditions for subsequent research.' if c['original_type']=='academic' else ''),
        'title':c['title'], 'source_kind':c['original_type']}
        for c in data['cases']])
    data['cases'][0]['interpretation'].pop('still_unestablished')
    (tmp_path/'radar2-curated-evidence-pilot.json').write_text(json.dumps(data))
    with pytest.raises(ValueError,match='Missing reasoning about still_unestablished'):
        subject.build(tmp_path)
