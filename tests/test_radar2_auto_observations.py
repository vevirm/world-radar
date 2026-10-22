"""Offline contract tests. No API keys or network needed."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import radar2_auto_observations as auto


def sample(case, value=22.038, changes=None):
    expected = {'freq': 'A', 'nrg_bal': case['energy_balance'], 'unit': 'PC',
                'geo': case['observed_geo'], 'time': str(case['year'])}
    doc = {'class': 'dataset', 'version': '2.0', 'id': list(expected),
           'size': [1] * 5, 'dimension': {d: {'category': {'index': {v: 0}}} for d, v in expected.items()},
           'value': {'0': value}, 'updated': '2026-09-15T21:00:00+0200'}
    if changes:
        changes(doc)
    return doc


def test_actual_originals_and_passages_accepted():
    originals = auto.selected_originals(ROOT)
    assert len(originals) == 2
    assert all(o['source_kind'] == 'academic' and o['original_passage'] for _, o in originals)


def test_original_quote_cannot_be_substituted():
    c = dict(auto.CONTRACTS[0], quote='By 2020 Europe will have 99% hydrogen')
    with pytest.raises(ValueError, match='cannot be traced'):
        auto.selected_originals(ROOT, (c,))


def test_refuse_unknown_original():
    c = dict(auto.CONTRACTS[0], id='lead-bogus')
    with pytest.raises(ValueError, match='not in accepted'):
        auto.selected_originals(ROOT, (c,))


def test_eurostat_indicator_and_year_validation():
    c = auto.CONTRACTS[0]
    assert auto.observation(sample(c, 37.5), c) == 37.5
    for dim, wrong in [('time', '2019'), ('geo','EU28'), ('nrg_bal', 'REN'), ('unit','THS')]:
        def rewrite(d):
            d['dimension'][dim]['category']['index'] = {wrong: 0}
        with pytest.raises(ValueError, match='wrong '+dim):
            auto.observation(sample(c, changes=rewrite), c)


def test_missing_value_does_not_turn_into_zero():
    c = auto.CONTRACTS[0]
    with pytest.raises(ValueError, match='No valid'):
        auto.observation(sample(c, changes=lambda d: d.update(value={})), c)


def test_reject_multi_cell_payload():
    c = auto.CONTRACTS[0]
    def expand(d):
        d['size'][0] = 2
        d['dimension']['freq']['category']['index'] = {'A':0, 'Q':1}
    with pytest.raises(ValueError, match='wrong freq'):
        auto.observation(sample(c, changes=expand), c)


def test_bad_schema_and_nonpercentage_rejected():
    c = auto.CONTRACTS[0]
    with pytest.raises(ValueError, match='JSON-stat'):
        auto.observation(sample(c,changes=lambda d:d.update(version='1.0')),c)
    with pytest.raises(ValueError,match='No valid'):
        auto.observation(sample(c,value=127),c)


def test_genuine_numeric_comparison_with_mismatch_caveat():
    stats = {auto.CONTRACTS[0]['energy_balance']: 37.5, auto.CONTRACTS[1]['energy_balance']:22.038}
    def fetch(url):
        c = next(c for c in auto.CONTRACTS if c['energy_balance'] in url)
        return sample(c, stats[c['energy_balance']])
    report = auto.run(ROOT, fetch=fetch)
    assert report['drafts_with_observations'] == 2
    assert report['source_errors'] == 0
    a, b = report['results']
    assert a['observation']['value_percent'] == 37.5
    assert '17.50 percentage points above' in a['comparison']['similarities']
    assert a['outcome_verified'] is False
    assert 'microgrid-resilience' in a['comparison']['still_unestablished']
    assert 'EU-28' in b['comparison']['differences']
    assert 'NOT a valid measure' in b['comparison']['differences']
    assert b['comparison_grade'] == 'provisional_proxy'
    assert report['published_outcomes'] == 0
    assert not report['publication_allowed']
    md=auto.as_markdown(report)
    assert 'Then' in md and 'Observed' in md and 'What remains unresolved' in md


def test_no_network_data_never_claims_finding():
    def broken(_): raise TimeoutError('unreachable')
    report = auto.run(ROOT, fetch=broken)
    assert report['source_errors'] == 2
    assert report['drafts_with_observations'] == 0
    assert all(r['status']=='source_unavailable_no_conclusion' for r in report['results'])
    assert 'No comparison' in auto.as_markdown(report)


def test_future_stat_value_automatically_changes_the_comparison():
    c = auto.CONTRACTS[0]
    _, o = auto.selected_originals(ROOT)[0]
    low = auto.analyse(c,o,18.0,auto.api_url(c))
    high = auto.analyse(c,o,36.0,auto.api_url(c))
    assert 'Lower than' in low['comparison']['summary']
    assert 'Broadly similar' in high['comparison']['summary']
    assert low['comparison']['similarities'] != high['comparison']['similarities']


def test_api_must_be_exact_official_dataset():
    with pytest.raises(ValueError,match='Non-Eurostat'):
        auto.get_api_json('https://evil.example/eurostat/api')
