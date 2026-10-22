"""Offline, synthetic test evidence. Nothing here is a real-world outcome."""
from copy import deepcopy
from datetime import date
from pathlib import Path

from scripts.radar2_connections import (
    OpenAlex, anchor_for, authors, date_relation, discover, drift_summary,
    merge_reviews, observed_period, study_links, time_position, validate_report,
)
from scripts.radar2_ten_study_pilot import select_ten

ROOT=Path(__file__).resolve().parents[1]
ORIGINAL=next(x for x in select_ten(ROOT) if 'flood' in x['title'].lower())
ORIGINAL_WORK={'id':'https://openalex.org/W101','doi':'https://doi.org/'+ORIGINAL['doi'],'authorships':[{'author':{'id':'https://openalex.org/A456'}}]}

def work(*,title='European river flood economic losses measured in Europe',
         abstract='Using measured river flood economic damage data in Europe between 2018 and 2022, we observed flood economic damage increased in European regions.',
         date='2024-04-01',id='W102', cites=None, author='A900'):
    return {'id':'https://openalex.org/'+id,'title':title,'doi':'https://doi.org/10.9000/'+id,
            'publication_date':date,'abstract':abstract,'referenced_works':cites or [],
            'authorships':[{'author':{'id':'https://openalex.org/'+author}}]}

def linked(w):
    return study_links(ORIGINAL,anchor_for(ORIGINAL),ORIGINAL_WORK,w)


def test_anchor_keeps_actual_original_words_and_not_model_source_as_place():
    anchor=anchor_for(ORIGINAL)
    assert anchor['original_excerpt'] in ORIGINAL['original_passage']
    assert anchor['horizon']['value']==[2050,2080]
    assert anchor['subject']['value'] and anchor['geography']['value']
    assert anchor['original_source']==ORIGINAL['source_url']
    assert anchor['conditions']['value']
    assert anchor['status']=='passage_backed_interpretation_needs_review'


def test_citation_only_when_unrelated_does_not_count_as_connected_outcome():
    w=work(title='Clinical study on human breast milk in Austria',
           abstract='Clinical breast milk samples observed in Austrian hospitals in 2021; staff collected hospital medical data. '*3,
           cites=['https://openalex.org/W101'])
    hit,reason=linked(w)
    assert reason is None
    assert hit['links']==['L1-passing']
    assert hit['research_link_status']=='citation_only_background'
    assert not hit['historical_outcome_verified']


def test_non_citing_similar_question_observations_requires_observed_period():
    hit,reason=linked(work())
    assert reason is None
    assert 'L3-empirical-question-lead' in hit['links']
    assert hit['observed_period']==[2018,2022]
    assert hit['time_relation']=='interim_look_back'
    assert hit['review_status']=='machine'
    assert hit['historical_outcome_verified'] is False
    w=work(abstract='Measured flood damage has increased in European rivers; our measurements demonstrated recorded flood costs. '*3)
    hit,_=linked(w)
    assert not hit or 'L3-empirical-question-lead' not in hit['links']


def test_2024_paper_reporting_2010_measurements_is_not_postpublication_outcome():
    w=work(abstract='We measured river flood economic losses in Europe between 2010 and 2012 using European observation stations. '*2)
    hit,_=linked(w)
    assert not hit or 'L3-empirical-question-lead' not in hit['links']


def test_shared_author_different_topic_does_not_create_lineage():
    w=work(title='Advanced medical 3D printing in Austria',
           abstract='Technology in hospitals in Austria is studied. Innovations have been described using experimental materials. '*2,
           author='A456')
    hit,reason=linked(w)
    assert hit is None and reason=='unrelated'


def test_same_author_same_topic_is_draft_lineage_not_an_outcome():
    w=work(title='Future river flood economic damage assessments for Europe',
           abstract='This simulation investigates river flood economic damage in Europe under multiple scenarios. '*3,
           author='A456')
    hit,_=linked(w)
    assert hit and 'L2-research-lineage' in hit['links']
    assert 'L3-empirical-question-lead' not in hit['links']
    assert hit['observed_period'] is None
    assert not hit['historical_outcome_verified']


def test_dates_are_full_dates_never_same_day_prior_or_undated():
    assert date_relation('2015-09-24',work(date='2015-09-24'))=='not_later'
    assert date_relation('2015-09-24',work(date='2015-09-25'))=='later'
    assert date_relation('2015-09-24',work(date='2015-09-23'))=='not_later'
    assert date_relation('2015-09-24',work(date=''))=='needs_dates'
    assert date_relation('2015-09-24',work(date='2099-01-01'))=='not_later'


def test_wrong_measure_and_geography_cannot_count_as_observation():
    w=work(title='Brazilian coastal roadway flood risk 2020',
           abstract='We measured road disruption following flash floods in Rio, Brazil between 2018 and 2022. '*3)
    hit,_=linked(w)
    assert hit is None


def test_drift_counts_bibliography_not_historical_verdict():
    anchor=anchor_for(ORIGINAL)
    l,_=linked(work())
    summary=drift_summary(anchor,[l])
    assert summary['latest_quoted_horizon_reached'] is False
    assert summary['research_connections']==1
    assert summary['observed_interim_leads']==1
    assert summary['drift_verified'] is False
    assert time_position(anchor,[2018,2050])=='looks_back_at_an_earlier_quoted_year_later_horizon_open'
    assert time_position(anchor,None)=='unknown_observation_period'
    assert time_position(anchor,[2018,2080])=='looks_back_at_all_quoted_horizon_years'


def test_reviewed_decisions_survive_disappearance_and_machine_replacement():
    old={'originals':[{'original_id':'one','links':[
        {'later_id':'W2','review_status':'rejected','later_date':'2020-01-01'},
        {'later_id':'W3','review_status':'confirmed','later_date':'2021-01-01'}],
        'human_notes':'Researcher checked the original full text'}]}
    new={'originals':[{'original_id':'one','links':[
        {'later_id':'W2','review_status':'machine','later_date':'2024-01-01'},
        {'later_id':'W4','review_status':'machine','later_date':'2024-05-01'}]}]}
    result=merge_reviews(old,new)['originals'][0]
    keyed={x['later_id']:x for x in result['links']}
    assert keyed['W2']['review_status']=='rejected'
    assert keyed['W3']['review_status']=='confirmed'
    assert keyed['W4']['review_status']=='machine'
    assert result['human_notes']=='Researcher checked the original full text'


def test_offline_no_network_and_no_false_absence_conclusion():
    result=discover([ORIGINAL],None,{})
    assert result['summary']['verified_outcome_assessments']==0
    assert result['summary']['published']==0
    case=result['originals'][0]
    assert case['coverage']['mode']=='offline_catalogue_only'
    assert case['coverage']['search_exhaustive'] is False
    assert case['meaningful_link_absence_established'] is False
    assert case['historical_outcome_verified'] is False


def test_fake_openalex_client_budget_and_live_structural_links():
    calls=[]
    citing=work(cites=['https://openalex.org/W101'])
    def fetch(params):
        calls.append(params)
        if params['filter'].startswith('doi:'): return [ORIGINAL_WORK]
        if params.get('filter','').startswith('cites:'): return [citing]
        return [citing]
    api=OpenAlex('mock-token',fetch=fetch)
    report=discover([ORIGINAL],api)
    assert api.requests==4
    assert report['summary']['with_research_links']==1
    assert len(report['originals'][0]['links'])==1
    assert report['originals'][0]['links'][0]['review_status']=='machine'
    assert report['summary']['verified_outcome_assessments']==0
    assert report['originals'][0]['coverage']['mode']=='live_openalex_limited'
    assert calls[0]['filter'].startswith('doi:https://doi.org/')
    assert calls[1]['filter'].startswith('cites:W101')


def test_limit_and_api_budget_fail_closed():
    import pytest
    with pytest.raises(ValueError,match='capped'):
        discover([ORIGINAL]*4,None)
    api=OpenAlex('mock',fetch=lambda p: [])
    for _ in range(12): api.query({'search':'x'})
    with pytest.raises(RuntimeError,match='budget'):
        api.query({'search':'x'})


def test_multi_original_question_geography_not_model_location():
    ireland=next(x for x in select_ten(ROOT) if 'Obesity Model in Ireland' in x['title'])
    a=anchor_for(ireland)
    assert a['geography']['value']=='Ireland'
    assert not a['named_models']['value']  # A model named in the title is not automatically part of the quoted claim


def test_validator_rejects_false_outcome_and_bad_dates():
    import pytest
    report=discover([ORIGINAL],None,{ORIGINAL['id']:{'original':ORIGINAL_WORK,'works':[work()]}})
    assert validate_report(report)
    bad=deepcopy(report)
    bad['summary']['verified_outcome_assessments']=1
    with pytest.raises(ValueError,match='cannot publish or verify'):
        validate_report(bad)
    bad=deepcopy(report)
    bad['originals'][0]['links'][0]['later_date']='2010-01-01'
    with pytest.raises(ValueError,match='genuinely later'):
        validate_report(bad)


def test_openalex_resolution_must_match_requested_doi():
    import pytest
    api=OpenAlex('mock',fetch=lambda params:[{**ORIGINAL_WORK,'doi':'https://doi.org/10.1234/different'}])
    with pytest.raises(ValueError,match='did not match'):
        api.resolve(ORIGINAL['doi'])
