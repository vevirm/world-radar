"""Offline tests for question-first evidence policy; no external services."""
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import radar2_auto_observations as auto


def sample(case, value=22.038, changes=None, year=None):
    expected={'freq':'A','nrg_bal':case['energy_balance'],'unit':'PC',
              'geo':case['observed_geo'],'time':str(case['year'] if year is None else year)}
    doc={'class':'dataset','version':'2.0','id':list(expected),
         'size':[1]*5,'dimension':{d:{'category':{'index':{v:0}}} for d,v in expected.items()},
         'value':{'0':value},'updated':'2026-09-15T21:00:00+0200'}
    if changes:changes(doc)
    return doc


def fetch_stub(url):
    params=parse_qs(urlsplit(url).query)
    assert params['geo']==['EU27_2020']
    year=int(params['time'][0])
    case=auto.CONTRACTS[1]
    return sample(case,value=18.029 if year==2017 else 22.038,year=year)


def test_originals_and_core_focus_are_traced():
    cases=auto.selected_originals(ROOT)
    assert len(cases)==2
    assert cases[0][0]['claim_role']=='background_context'
    assert cases[1][0]['claim_role']=='central_projection'
    assert all(original['source_kind']=='academic' for _,original in cases)


def test_reject_unsupported_quote_focus_and_original():
    c=dict(auto.CONTRACTS[0], quote='Europe will have 99% hydrogen')
    with pytest.raises(ValueError,match='cannot be traced'):
        auto.selected_originals(ROOT,(c,))
    c=dict(auto.CONTRACTS[0], central_focus_evidence='Incorrect invented study purpose')
    with pytest.raises(ValueError,match='Core study focus'):
        auto.selected_originals(ROOT,(c,))
    c=dict(auto.CONTRACTS[0],id='lead-bogus')
    with pytest.raises(ValueError,match='not in accepted'):
        auto.selected_originals(ROOT,(c,))


def test_reject_misleading_direct_link():
    c=dict(auto.CONTRACTS[1],metric_fit='direct')
    with pytest.raises(ValueError,match='Non-equivalent geography'):
        auto.selected_originals(ROOT,(c,))
    c=dict(auto.CONTRACTS[0],claim_role='central_projection')
    with pytest.raises(ValueError,match='lacks reviewed indicator mapping'):
        auto.selected_originals(ROOT,(c,))
    c=dict(auto.CONTRACTS[1],baseline_year=2019)
    with pytest.raises(ValueError,match='Baseline must precede'):
        auto.selected_originals(ROOT,(c,))


def test_eurostat_indicator_year_and_geo_validation():
    c=auto.CONTRACTS[1]
    assert auto.observation(sample(c,22.0),c)==22.0
    assert auto.observation(sample(c,18.029,year=2017),c,year=2017)==18.029
    for dim,wrong in [('time','2019'),('geo','EU28'),('nrg_bal','REN_ELC'),('unit','THS')]:
        def rewrite(d):d['dimension'][dim]['category']['index']={wrong:0}
        with pytest.raises(ValueError,match='wrong '+dim):
            auto.observation(sample(c,changes=rewrite),c)


def test_missing_invalid_and_multi_cell_values():
    c=auto.CONTRACTS[1]
    with pytest.raises(ValueError,match='No valid'):
        auto.observation(sample(c,changes=lambda d:d.update(value={})),c)
    with pytest.raises(ValueError,match='No valid'):
        auto.observation(sample(c,value=127),c)
    with pytest.raises(ValueError,match='JSON-stat'):
        auto.observation(sample(c,changes=lambda d:d.update(version='1.0')),c)
    def expand(d):
        d['size'][0]=2
        d['dimension']['freq']['category']['index']={'A':0,'Q':1}
    with pytest.raises(ValueError,match='wrong freq'):
        auto.observation(sample(c,changes=expand),c)


def test_wrong_question_rejected_before_api_call():
    called=[]
    def fail_if_any(url):
        called.append(url)
        raise AssertionError('Should never request unrelated metric')
    report=auto.run(ROOT,fetch=fail_if_any,contracts=auto.CONTRACTS[:1])
    assert not called
    assert report['excluded_wrong_question']==1
    assert report['source_errors']==0
    row=report['results'][0]
    assert row['status']=='wrong_question_no_comparison'
    assert row['evidence_search_performed'] is False
    assert 'microgrids' in row['central_question'].lower()
    assert 'not' in row['reason'].lower()


def test_live_observations_do_not_become_forecast_score_on_wrong_geo():
    report=auto.run(ROOT,fetch=fetch_stub)
    assert report['originals_checked']==2
    assert report['excluded_wrong_question']==1
    assert report['observations_with_non_equivalent_geographies']==1
    assert report['drafts_with_comparable_observations']==0
    assert report['source_errors']==0
    row=report['results'][1]
    assert row['status']=='later_development_found_but_comparison_not_established'
    assert row['comparison_grade']=='not_comparable_proxy'
    assert row['observation']['value_percent']==22.038
    assert row['observation']['baseline']['year']==2017
    assert 'changed by +4.01' in row['comparison']['what_happened']
    assert 'no forecast error' in row['comparison']['differences'].lower()
    assert 'forecast' in row['comparison']['summary'].lower() or 'historical' in row['comparison']['summary'].lower()
    assert not row['publication_allowed']
    assert not row['outcome_verified']
    assert report['published_outcomes']==0
    md=auto.as_markdown(report)
    assert 'comparison rejected before searching' in md
    assert 'not a test' in md


def test_proxy_observation_cannot_turn_into_predicted_success_or_failure():
    c=auto.CONTRACTS[1]
    original=auto.selected_originals(ROOT,(c,))[0][1]
    low=auto.analyse(c,original,12.0,auto.api_url(c),baseline_value=9.0)
    high=auto.analyse(c,original,80.0,auto.api_url(c),baseline_value=15.0)
    assert low['comparison']['summary']==high['comparison']['summary']
    for report in (low,high):
        assert report['comparison_grade']=='not_comparable_proxy'
        assert report['comparison']['similarities']=='Not determined using non-equivalent populations.'
        assert 'forecast error' in report['comparison']['differences']


def test_unavailable_official_data_is_not_invented():
    calls=[]
    def fail(u):
        calls.append(u)
        raise TimeoutError('unreachable')
    report=auto.run(ROOT,fetch=fail)
    assert len(calls)==1  # context case never requested
    assert report['source_errors']==1
    assert report['drafts_with_comparable_observations']==0
    assert report['results'][1]['status']=='source_unavailable_no_conclusion'
    assert 'No comparison' in auto.as_markdown(report)


def test_missing_baseline_is_not_silently_ignored():
    def no_baseline(url):
        if parse_qs(urlsplit(url).query)['time']==['2017']:
            raise TimeoutError('no historical baseline')
        return fetch_stub(url)
    report=auto.run(ROOT,fetch=no_baseline)
    assert report['source_errors']==1
    assert report['results'][1]['status']=='source_unavailable_no_conclusion'


def test_official_api_host_is_fixed():
    with pytest.raises(ValueError,match='Non-Eurostat'):
        auto.get_api_json('https://evil.example/eurostat/api')
