import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from radar2_evidence_extract import extract_findings

def test_observation_kept_as_unreviewed_candidate():
    text = 'European hydrogen passenger vehicle registrations increased between 2020 and 2024 according to new official monitoring data.'
    result = extract_findings(text, 'hydrogen passenger vehicle futures')
    assert len(result) == 1
    assert result[0]['kind'] == 'reported_development'
    assert result[0]['status'] == 'requires_source_review'

def test_future_forecast_is_not_observation():
    s = 'European hydrogen passenger vehicles could expand markedly by 2040 in the new transport scenario study.'
    assert extract_findings(s, 'hydrogen passenger vehicles')[0]['kind'] == 'future_claim'

def test_noise_unrelated_excluded():
    assert extract_findings('Please accept our privacy policy and cookie consent to continue reading the website.', 'hydrogen vehicle') == []
    assert extract_findings('New observations about urban drainage networks increased in recent surveys of the coastline.', 'hydrogen vehicle') == []

def test_empty_and_limit():
    s = 'European hydrogen passenger vehicle usage increased between 2020 and 2024 in several surveys.'
    assert extract_findings('', 'hydrogen') == []
    assert len(extract_findings(' '.join([s]*6), 'hydrogen passenger vehicle', limit=2)) <= 2
