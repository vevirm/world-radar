"""No-network test cases for incremental scholarly comparison and provenance."""
from datetime import date
import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
import pytest
from scripts.openalex_comparison import (
    abstract_from_index, candidate_from_work, local_catalogue,
    assess, query_for, related, request_works,
)
from scripts.check_radar2_live_status import check_live_status

CLAIM = {
    'title': 'European coastal flooding and sea level rise projections',
    'expected': 'Flooding might rise in European coastal regions by 2035.',
    'candidate_excerpt': 'Flooding is projected to rise by 2035 in European coastal regions.',
    'screening_status': 'candidate_needs_validation',
    'original_publication': '2014-06-12',
    'source_url': 'https://doi.org/10.5555/original',
    'publisher': 'Journal of Studies',
}


def paper(when='2022-05-14', title='Sea level rise and coastal flooding across European regions', abstract=None, doi='https://doi.org/10.5555/new'):
    return {'title': title, 'publication_date': when, 'doi': doi,
            'abstract': abstract or 'Empirical records were evaluated. We found that coastal flooding increased across European regions.',
            'cited_by_count': 17}


def test_openalex_reconstructs_inverted_abstract_and_extracts_later_result():
    work = paper()
    work.pop('abstract')
    work['abstract_inverted_index'] = {'We': [0], 'found': [1], 'that': [2], 'coastal': [3],
                                      'flooding': [4], 'increased': [5], 'across': [6],
                                      'European': [7], 'regions.': [8]}
    assert abstract_from_index(work['abstract_inverted_index']).startswith('We found')
    c = candidate_from_work(CLAIM, work)
    assert c['source'] == 'openalex_live'
    assert c['study_type'] == 'abstract_reports_results'
    assert c['year'] == 2022
    assert 'We found' in c['finding_from_abstract']


def test_older_same_and_unrelated_papers_not_mistaken_for_followups():
    works = [paper(when='2011-01-01'), paper(doi=CLAIM['source_url']),
             paper(title='Cooking lentil soup', doi='https://doi.org/10.5555/soup'), paper()]
    hits = related(CLAIM, works)
    assert len(hits) == 1
    assert hits[0]['url'] == 'https://doi.org/10.5555/new'


def test_conclusion_is_explicitly_tentative_even_with_similar_results():
    evidence = related(CLAIM, [paper()])
    result = assess(CLAIM, evidence)
    assert result['literature_signal'] == 'later_studies_report_results'
    assert 'not established' in result['tentative_assessment']
    assert 'unverified' in result['comparison_limits']
    assert 'NOT established' in result['eu_attribution']
    assert evidence[0]['url'] in str(result['follow_up_publications'])


def test_catalogue_mode_reuses_saved_papers_without_fabricated_openalex_requests():
    records = [dict(title='Sea level rise and coastal flooding across European regions',
                    date='2022-05-14', url='https://doi.org/10.5555/new',
                    abstract='We found that flooding increased in European coastal regions.')]
    evidence = local_catalogue(CLAIM, records)
    assert evidence[0]['source'] == 'existing_scanner_catalogue'
    assessment = assess(CLAIM, evidence, search_mode='catalogue')
    assert assessment['literature_search_mode'] == 'catalogue'
    assert not assessment.get('verified_outcome')


def test_openalex_query_with_key_and_year_filter():
    requests = []
    class Reply:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'{"results": []}'
    def fetch(req, timeout=20):
        requests.append(parse_qs(urlparse(req.full_url).query))
        return Reply()
    with patch('scripts.openalex_comparison.urllib.request.urlopen', side_effect=fetch), \
         patch.dict('os.environ', {'OPENALEX_API_KEY': 'test-key', 'MAILTO': 'reader@example.org'}):
        assert request_works(query_for(CLAIM), 2015) == []
    assert requests[0]['api_key'] == ['test-key']
    assert requests[0]['filter'] == ['from_publication_date:2015-01-01']
    assert 'coastal' in requests[0]['search'][0]


def test_openalex_live_success_does_not_require_openai_key():
    assert 'OpenAlex live' in check_live_status({'run': {'provider': 'openalex', 'attempts': 3, 'failed': 1}})
    with pytest.raises(ValueError, match='failed'):
        check_live_status({'run': {'provider': 'openalex', 'attempts': 1, 'failed': 1}})
    with pytest.raises(ValueError, match='No live research'):
        check_live_status({'run': {'provider': 'catalogue', 'attempts': 10, 'failed': 0}})
    assert 'Offline' in check_live_status({'run': {'provider': 'catalogue', 'attempts': 10, 'failed': 0}}, allow_offline=True)


def test_shared_forecast_direction_stays_low_confidence():
    from scripts.openalex_comparison import tentative_direction
    matches = related(CLAIM, [paper()])
    label, note = tentative_direction(CLAIM, matches)
    assert label == 'tentatively_consistent_direction'
    assert 'LOW-CONFIDENCE' in note
    contrary = [dict(matches[0], finding_from_abstract='We found that coastal flooding decreased in Europe.')]
    assert tentative_direction(CLAIM, contrary)[0] == 'tentatively_in_tension'
    ambiguous = [dict(matches[0], finding_from_abstract='In future scenarios flooding could increase in Europe.')]
    assert tentative_direction(CLAIM, ambiguous)[0] == 'insufficient_comparability'


def test_radar2_auto_uses_openalex_and_writes_new_word_without_openai(tmp_path, monkeypatch):
    import importlib
    import sys
    from scripts import retrospective_radar as radar
    from docx import Document
    verification = importlib.import_module('outcome_verification')
    outlook = importlib.import_module('outlook_summary')
    lead = {
        'title': 'European coastal flooding and sea level rise projections',
        'date': '2014-06-12', 'url': 'https://doi.org/10.5555/original',
        'abstract': 'Flooding is projected to increase by 10% across European coastal regions by 2035. '
                    'This original research analyzes future sea level rise and European flood risk.',
        'journal': 'European Foresight Studies',
    }
    (tmp_path / 'research-leads.json').write_text(json.dumps({'leads': [lead]}))
    (tmp_path / 'verified-outcomes.json').write_text(json.dumps({'cases': []}))
    (tmp_path / 'outcome-observations.json').write_text(json.dumps({'observations': []}))
    monkeypatch.setattr(radar, 'ROOT', tmp_path)
    monkeypatch.setattr(radar, 'OUTPUT', tmp_path / 'retrospective-results.json')
    monkeypatch.setattr(radar, 'REPORT', tmp_path / 'stuff' / 'WHAT_WAS_EXPECTED_WHAT_HAPPENED.docx')
    monkeypatch.setattr(verification, 'QUEUE', tmp_path / 'outcome-review-queue.json')
    monkeypatch.setattr(verification, 'REGISTRY', tmp_path / 'verified-outcomes.json')
    monkeypatch.setattr(outlook, 'ROOT', tmp_path)
    monkeypatch.setattr(outlook, 'OUT', tmp_path / 'outlook-summary.json')
    monkeypatch.setattr(radar, 'request_works', lambda query, since: [paper()])
    monkeypatch.setattr(radar.time, 'sleep', lambda x: None)
    monkeypatch.setenv('OPENAI_API_KEY', '')
    monkeypatch.delenv('GITHUB_STEP_SUMMARY', raising=False)
    monkeypatch.setattr(sys, 'argv', ['radar2', '--provider', 'auto', '--minutes', '2', '--max-claims', '1'])
    radar.main()
    audit = json.loads((tmp_path / 'scanner2-audit.json').read_text())
    assert audit['run']['provider'] == 'openalex'
    assert audit['run']['literature_comparisons'] == 1
    assert audit['run']['failed'] == 0
    text = '\n'.join(p.text for p in Document(radar.REPORT).paragraphs)
    assert 'LATER STUDIES / WHAT THEY REPORT' in text
    assert 'Sea level rise and coastal flooding across European regions' in text
    assert 'Source-reviewed expected-vs-actual outcomes: 0' in text
