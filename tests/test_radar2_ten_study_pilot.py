"""Offline contract tests. No API access and no data mutation."""
import copy
from pathlib import Path
import pytest
from scripts.radar2_ten_study_pilot import (
    select_ten, discovery_queries, candidate_for, research, markdown, historical_focus
)

ROOT=Path(__file__).resolve().parents[1]


def sample(original, **overrides):
    return {**original, **overrides}


def work(*,title='European flood damage from river floods has increased in many regions',
         abstract='Using measured European flood loss data, we found that flood damage increased by 18 percent between 2010 and 2020 in Europe.',
         year='2024-05-12',doi='https://doi.org/10.1234/empirical'):
    return {'title':title,'abstract':abstract,'publication_date':year,'doi':doi}


def test_selects_ten_distinct_accepted_across_subjects_not_prior_comparisons():
    chosen=select_ten(ROOT)
    assert len(chosen)==10
    assert len(set(c['id'] for c in chosen))==10
    assert len(set(c['topic_group'] for c in chosen))>=4
    assert all(c['source_kind']=='academic' and c['original_passage'] for c in chosen)
    assert all(c['original_publication'][:4] <= '2023' for c in chosen)
    assert all(c['historical_focus'] and c['question_card']['evidence_question'] for c in chosen)
    published=__import__('json').loads((ROOT/'radar2-comparisons.json').read_text())
    excluded={c['id'] for c in published.get('comparisons',[])}
    assert not ({c['id'] for c in chosen} & excluded)
    assert all(1 <= len(discovery_queries(c))<=2 for c in chosen)
    with pytest.raises(ValueError,match='maximum'):
        select_ten(ROOT,11)


def test_focus_chooses_original_substantive_scenario_not_later_policy_background():
    passage=('We estimate that flooding damages could rise to 20 billion euros by 2050 under the reference scenario. '
             'The European Union released an updated policy in 2030.')
    assert 'flooding damages' in historical_focus(passage)


def test_accepts_attributed_later_observation_but_never_verifies_outcome():
    claim=next(c for c in select_ten(ROOT) if 'flood' in c['title'].lower())
    hit=candidate_for(claim,work())
    assert hit is not None
    assert hit['reported_by_later_paper_not_independently_verified']
    assert hit['outcome_verified'] is False
    assert 'flood damage increased' in hit['later_indexed_abstract_observation']


def test_wrong_geography_old_date_scenarios_and_no_abstract_get_rejected():
    claim=next(c for c in select_ten(ROOT) if 'flood' in c['title'].lower())
    assert candidate_for(claim,work(title='Brazilian flood damages across regions')) is None
    assert candidate_for(claim,work(year='2011-01-01')) is None
    assert candidate_for(claim,work(abstract='We modelled how European river floods might increase by 2050 in future scenarios without observing any events.')) is None
    assert candidate_for(claim,work(abstract='A short description.')) is None
    assert candidate_for(claim,work(title='Economic growth and technology in Europe', abstract='Measured changes in gross domestic product are observed throughout European cities.')) is None


def test_searches_are_bounded_do_not_write_and_no_automatic_verdict(tmp_path):
    selected=select_ten(ROOT)
    def fake_search(query,since_year):
        assert 2012 <= since_year <= 2024
        return [work(), work()]  # deliberate duplicate
    before=(ROOT/'retrospective-results.json').read_bytes()
    report=research(selected, 'openalex-key-present', fake_search)
    assert report['originals_selected']==10
    assert report['openalex_queries_completed'] <=20
    assert report['verified_outcomes']==report['published_outcomes']==0
    assert report['publication_allowed'] is False
    assert all(c['publish'] is False and not c['fully_investigated_evidence_gap'] for c in report['cases'])
    assert all(not c['verified_outcome'] for c in report['cases'])
    assert (ROOT/'retrospective-results.json').read_bytes()==before
    assert 'ten-study' in markdown(report)
    assert not (tmp_path/'index.html').exists()


def test_openalex_empty_not_a_conclusive_evidence_gap():
    report=research(select_ten(ROOT), 'configured', lambda *_: [])
    assert all(c['status']=='no_usable_evidence_in_bounded_openalex_search' for c in report['cases'])
    assert all(c['no_meaningful_link_established'] and not c['fully_investigated_evidence_gap'] for c in report['cases'])
    assert 'NOT proof' in report['cases'][0]['interpretation']


def test_search_error_is_reported_not_mislabeled_no_evidence():
    def broken(*args):
        raise TimeoutError('OpenAlex unavailable')
    report=research(select_ten(ROOT), 'configured', broken)
    assert report['search_failed_or_partial']==10
    assert all(c['status']=='search_failed_or_partial' for c in report['cases'])
    assert all(c['errors'] for c in report['cases'])


def test_requires_existing_key():
    with pytest.raises(ValueError,match='OPENALEX_API_KEY'):
        research(select_ten(ROOT), '', lambda *_:pytest.fail('unexpected live search'))
