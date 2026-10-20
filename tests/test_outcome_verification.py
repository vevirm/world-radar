from scripts.outcome_verification import verify_case, assemble

LEAD = {'lead-1': {'source_url': 'https://doi.org/10.1234/original'}}
BASE = {
    'lead_id': 'lead-1', 'source_reviewed_by': 'Reviewer', 'reviewed_on': '2026-10-19', 'verdict': 'partially_realized',
    'limitations': 'Different sampling periods; exact comparison uncertain.',
    'original': {'url': 'https://doi.org/10.1234/original', 'verbatim_passage': 'We forecast a 20 percent increase in energy use by 2020.', 'published_on':'2010-01-01', 'geography':'European Union', 'observable':'Energy use percentage', 'target_date':'2020-12-31'},
    'observation': {'what_happened':'Energy use changed by 10 percent.', 'measured_on':'2021-02-01', 'same_metric_and_geography_explained':'Comparable EU totals and reference years adjusted.', 'sources':[{'url':'https://ec.europa.eu/eurostat/official', 'date':'2021-02-01','finding':'Reported measurement'}]}
}

def test_structurally_reviewed_case_passes():
    assert verify_case(BASE, LEAD) is None

def test_bibliography_is_not_evidence():
    broken = {**BASE, 'observation': {**BASE['observation'], 'sources': []}}
    assert 'evidence' in verify_case(broken, LEAD)

def test_original_cannot_prove_itself():
    broken = {**BASE, 'observation': {**BASE['observation'], 'sources': [{'url':LEAD['lead-1']['source_url'],'date':'2021-02-01','finding':'Same study'}]}}
    assert 'Original study' in verify_case(broken, LEAD)

def test_no_unreviewed_auto_verdict():
    broken = {**BASE, 'source_reviewed_by': ''}
    assert 'reviewer' in verify_case(broken, LEAD)

def test_early_realization_rejected():
    broken = {**BASE, 'verdict': 'realized', 'observation':{**BASE['observation'], 'measured_on':'2018-02-01'}}
    assert 'Premature' in verify_case(broken, LEAD)
