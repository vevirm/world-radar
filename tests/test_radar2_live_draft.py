"""No-network tests of the OpenAlex-only, bounded, nonpublishing live pilot."""
from pathlib import Path
import pytest

from scripts.radar2_live_draft import (
    PILOT_IDS, discovery_queries, filter_candidate, research, select_originals,
)

ROOT = Path(__file__).resolve().parents[1]


def test_three_real_accepted_originals_are_substantive():
    claims = select_originals(ROOT)
    assert [c['id'] for c in claims] == list(PILOT_IDS)
    assert len(claims) == 3
    assert all(len(c['original_passage']) > 70 for c in claims)
    assert all(c['research_question'] and len(c['issue_anchors']) >= 2 for c in claims)
    assert all(1 <= len(discovery_queries(c)) <= 2 for c in claims)


def test_rejects_original_not_accepted_in_radar1():
    with pytest.raises(ValueError, match='no longer accepted'):
        select_originals(ROOT, ids=['lead-not-in-radar1'])


def test_no_openalex_key_no_live_requests():
    with pytest.raises(ValueError, match='OPENALEX_API_KEY'):
        research(select_originals(ROOT), '', lambda *_: pytest.fail('request made'))


def test_openalex_returns_bibliographic_candidates_never_outcomes():
    claims = select_originals(ROOT)
    def searcher(query, since_year):
        assert isinstance(query, str) and query
        assert since_year >= 2012
        return [
            {'title': 'Hydrogen decarbonisation of European energy system and development',
             'doi': 'https://doi.org/10.1234/later-hydrogen',
             'publication_date': '2024-04-22',
             'abstract': 'We found European hydrogen energy system deployments differ from scenarios.'},
            {'title': 'Unrelated financial futures trading',
             'doi': 'https://doi.org/10.1234/not-on-topic',
             'publication_date': '2024-01-01',
             'abstract': 'Prices for stock market futures.'},
            {'title': 'Hydrogen decarbonisation of European energy system and development',
             'doi': 'https://doi.org/10.1234/earlier',
             'publication_date': '2010-01-01',
             'abstract': 'European hydrogen systems.'},
        ]
    report = research(claims, 'existing-openalex-key', searcher)
    assert report['originals_considered'] == 3
    assert report['queries_completed'] <= 6
    assert report['cases_with_search_errors'] == 0
    assert report['published_outcomes'] == report['source_verified_outcomes'] == 0
    assert report['publication_allowed'] is False
    for case in report['cases']:
        assert case['outcome_assessment'].startswith('NOT ASSESSED')
        assert case['publication_allowed'] is False
        for candidate in case['candidate_followups']:
            assert not candidate['source_checked_independently']
            assert not candidate['observed_development_verified']
            assert not candidate['same_substantive_question_verified']
            assert candidate['publication_year'] >= 2012
            assert candidate['url'] != 'https://doi.org/10.1234/earlier'
            assert candidate['url'] != 'https://doi.org/10.1234/not-on-topic'


def test_dated_same_original_and_weak_abstract_do_not_pass():
    claim = select_originals(ROOT)[0]
    assert filter_candidate(claim, {
        'title': 'Hydrogen decarbonisation European energy system',
        'doi': 'https://doi.org/10.1234/old', 'publication_date': '2014-01-01',
        'abstract': 'This is a European hydrogen energy case'}) is None
    assert filter_candidate(claim, {
        'title': 'Financial Futures Trading European energy markets',
        'doi': 'https://doi.org/10.1234/trades', 'publication_date': '2025-01-01',
        'abstract': 'This concerns capital markets, not hydrogen.'}) is None


def test_search_error_not_misrepresented_as_zero_evidence():
    claims = select_originals(ROOT)
    def blocked(query, since_year):
        raise TimeoutError('test simulated API outage')
    report = research(claims, 'existing-openalex-key', blocked)
    assert report['cases_with_search_errors'] == 3
    assert all(c['research_status'] == 'search_failed' for c in report['cases'])
    assert all(c['search_errors'] for c in report['cases'])
    assert report['publication_allowed'] is False


def test_empty_openalex_search_is_not_future_prediction_failure():
    report = research(select_originals(ROOT), 'existing-openalex-key', lambda *_: [])
    assert all(c['research_status'] == 'no_close_candidate_in_bounded_openalex_search'
               for c in report['cases'])
    assert report['source_verified_outcomes'] == 0
    assert 'No match does NOT mean no developments' in report['warning']
