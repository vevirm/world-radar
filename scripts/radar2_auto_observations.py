#!/usr/bin/env python3
"""Small, real, reproducible then-vs-observed Radar 2 automation pilot.

Uses two Radar-1-accepted originals, exact historical passages, and the free
Eurostat Statistics API.  The pre-reviewed observation contracts are a mapping
from *substantive question* to official statistical indicator, not keyword
searches. Produces DRAFTS only. Never edits the live dataset or website.

The important negative control is an EU-28 forecast compared with an EU-27
series: describe the proxy and difference but DO NOT call it a verified test.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    from .radar2_scope import original_claims
except ImportError:
    from radar2_scope import original_claims

ROOT = Path(__file__).resolve().parents[1]
API_HOST = 'https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/'
BROWSER = 'https://ec.europa.eu/eurostat/databrowser/view/nrg_ind_ren/default/table?lang=en'
DATASET = 'nrg_ind_ren'
MAX_BODY_BYTES = 350_000

# Adding a future case requires an attributable passage and an explicitly
# reviewed indicator mapping; it cannot be selected by vague word similarity.
CONTRACTS = (
    {
        'id': 'lead-616c0b7511591643',
        'quote': 'By 2020, 20% of the European electricity demand will be met by renewable generation',
        'year': 2020, 'observed_geo': 'EU27_2020', 'original_geo': 'Europe (not defined as EU-27)',
        'energy_balance': 'REN_ELC',
        'measure': 'share of renewable energy in gross electricity consumption',
        'original_measure': 'share of European electricity demand met by renewable generation',
        'bound_type': 'at_least', 'expected': 20.0,
        'question': 'Did the proportion of electricity from renewables reach approximately 20% by 2020?',
        'remaining': 'The observation does not test the paper’s microgrid-resilience thesis or its longer-range 2030 and 2050 discussion.',
    },
    {
        'id': 'lead-ceb54d6064f5f1af',
        'quote': 'The share of REs in GFEC in EU 28 varies from 19.4% to 21.8% in future trajectories towards 2020',
        'year': 2020, 'observed_geo': 'EU27_2020', 'original_geo': 'EU-28',
        'energy_balance': 'REN',
        'measure': 'share of renewable energy in gross final energy consumption',
        'original_measure': 'share of renewables in gross final energy consumption',
        'bound_type': 'range', 'expected': (19.4, 21.8),
        'question': 'How closely did renewable-energy consumption in 2020 resemble the modelled EU-28 trajectory range?',
        'remaining': 'This is NOT an exact EU-28 evaluation: the readily available Eurostat EU-27 series excludes the United Kingdom. A like-for-like EU-28 observation is needed before judging forecast accuracy.',
    },
)


def api_url(case):
    params = {'lang': 'EN', 'freq': 'A', 'unit': 'PC',
              'nrg_bal': case['energy_balance'], 'geo': case['observed_geo'],
              'time': str(case['year'])}
    return API_HOST + DATASET + '?' + urlencode(params)


def get_api_json(url):
    """Query a fixed official API only; protect against hangs or huge payloads."""
    if not url.startswith(API_HOST) or not url.split('?', 1)[0] == API_HOST + DATASET:
        raise ValueError('Non-Eurostat data URL refused')
    req = Request(url, headers={'User-Agent': 'WorldRadarResearchPilot/1.0 (+https://github.com/vevirm/world-radar)',
                                'Accept': 'application/json'})
    with urlopen(req, timeout=22) as response:
        if response.status != 200:
            raise ValueError('Eurostat HTTP status ' + str(response.status))
        raw = response.read(MAX_BODY_BYTES + 1)
    if len(raw) > MAX_BODY_BYTES:
        raise ValueError('Unexpectedly large API response')
    return json.loads(raw)


def observation(data, contract):
    """Decode JSON-stat 2.0 single statistical cell, validating EVERY dimension.

    Do not rely on value[0] without checking the geo, time, balance and unit.
    A changed API query or wrong dimension would otherwise yield false findings.
    """
    if data.get('class') != 'dataset' or data.get('version') != '2.0':
        raise ValueError('Eurostat response is not JSON-stat dataset 2.0')
    ids, sizes, dims = data.get('id'), data.get('size'), data.get('dimension') or {}
    if not isinstance(ids, list) or not isinstance(sizes, list) or len(ids) != len(sizes):
        raise ValueError('Invalid Eurostat dimension array')
    expected = {'freq': 'A', 'unit': 'PC', 'nrg_bal': contract['energy_balance'],
                'geo': contract['observed_geo'], 'time': str(contract['year'])}
    for key, code in expected.items():
        if key not in ids:
            raise ValueError('Required indicator dimension missing: ' + key)
        dim = dims.get(key) or {}
        index = (dim.get('category') or {}).get('index') or {}
        if sizes[ids.index(key)] != 1 or index.get(code) != 0 or len(index) != 1:
            raise ValueError('Eurostat response wrong ' + key + ': wanted ' + code)
    if any(size != 1 for size in sizes):
        raise ValueError('Eurostat response includes multiple cells')
    vals = data.get('value') or {}
    value = vals.get('0') if isinstance(vals, dict) else vals[0] if isinstance(vals, list) and len(vals) == 1 else None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
        raise ValueError('No valid observed percentage in Eurostat response')
    return round(float(value), 3)


def selected_originals(root=ROOT, contracts=CONTRACTS):
    accepted = {c['id']: c for c in original_claims(Path(root))}
    found = []
    for case in contracts:
        o = accepted.get(case['id'])
        if not o or o.get('source_kind') != 'academic':
            raise ValueError('Original is not in accepted Radar 1: '+case['id'])
        if not o.get('investigation_ready') or not o.get('source_url', '').startswith('https://'):
            raise ValueError('Original source not ready: ' + case['id'])
        passage = ' '.join(o['original_passage'].split()).casefold().rstrip('.')
        quote = ' '.join(case['quote'].split()).casefold()
        if quote not in passage:
            raise ValueError('Original proposition cannot be traced verbatim: ' + case['id'])
        if int(o['original_publication'][:4]) >= case['year']:
            raise ValueError('Observed year must follow original publication: ' + case['id'])
        found.append((case, o))
    return found


def analyse(case, original, value, url):
    original_geo = case['original_geo']
    geo_exact = original_geo == 'EU27_2020'
    boundary = case['expected']
    if case['bound_type'] == 'at_least':
        delta = round(value - boundary, 3)
        relation = ('above' if delta > 0 else 'below' if delta < 0 else 'at')
        similarity = (f'Observed EU-27 renewable electricity share was {value:.2f}% in 2020, '
                      f'{abs(delta):.2f} percentage points {relation} the historical 20% reference.')
        difference = ('The original refers to European electricity demand; the measured series is '
                      'EU-27 gross electricity consumption. Geography and measurement boundaries are '
                      'not demonstrably identical. The number alone does not show the effect of microgrids.')
        finding = 'Broadly similar direction, using an imperfect statistical proxy' if delta >= 0 else 'Lower than the historical reference, using an imperfect statistical proxy'
    else:
        lo, hi = boundary
        within = lo <= value <= hi
        relation = 'within' if within else 'above' if value > hi else 'below'
        difference_size = round(value - hi if value > hi else lo - value if value < lo else 0, 3)
        similarity = (f'Eurostat reports {value:.2f}% for the EU-27 in 2020; this is {relation} '
                      f'the original EU-28 trajectory range {lo:.1f}–{hi:.1f}% '
                      f'(distance to the nearest range boundary: {difference_size:.2f} percentage points).')
        difference = ('The historical model covered the EU-28 including the United Kingdom, but the observed '
                      'series covers the EU-27. These are different populations: the calculated range difference '
                      'is NOT a valid measure of the original forecast error.')
        finding = 'Approximate proxy found; exact historical forecast comparison remains unestablished'
    return {
        'original_id': original['id'], 'title': original['title'],
        'original_publication': original['original_publication'],
        'original_url': original['source_url'], 'original_passage': original['original_passage'],
        'historical_proposition': case['quote'], 'historical_question': case['question'],
        'original_geography': original_geo, 'historical_measure': case['original_measure'],
        'observation': {'value_percent': value, 'year': case['year'], 'geography': 'EU-27 (2020 composition)',
                        'indicator': case['measure'], 'dataset': DATASET, 'dataset_url': BROWSER,
                        'api_url': url, 'data_updated': None, 'unit': 'percent'},
        'comparison': {'summary': finding, 'similarities': similarity,
                       'differences': difference, 'still_unestablished': case['remaining'],
                       'present_relevance': 'The recorded 2020 observation helps revisit the historical pathway, but newer trends and the original assumptions require separate investigation.'},
        'comparison_grade': 'provisional_proxy' if not geo_exact else 'potentially_direct',
        'outcome_verified': False, 'publication_allowed': False,
        'status': 'automated_evidence_draft_for_human_source_review',
    }


def run(root=ROOT, fetch=get_api_json, contracts=CONTRACTS):
    selected = selected_originals(root, contracts)
    rows = []
    for case, original in selected:
        url = api_url(case)
        try:
            data = fetch(url)
            value = observation(data, case)
            item = analyse(case, original, value, url)
            item['observation']['data_updated'] = data.get('updated')
        except Exception as exc:
            item = {'original_id': original['id'], 'title': original['title'],
                    'historical_proposition': case['quote'], 'historical_question': case['question'],
                    'evidence_api_url': url, 'status': 'source_unavailable_no_conclusion',
                    'error': type(exc).__name__ + ': ' + str(exc)[:250],
                    'outcome_verified': False, 'publication_allowed': False}
        rows.append(item)
    return {'schema_version': 1, 'mode': 'LIVE_EUROSTAT_THEN_VS_NOW_BOUNDED',
            'generated_utc': datetime.now(timezone.utc).isoformat(),
            'originals_checked': len(rows),
            'drafts_with_observations': sum(r['status'].startswith('automated_evidence_draft') for r in rows),
            'source_errors': sum(r['status'] == 'source_unavailable_no_conclusion' for r in rows),
            'published_outcomes': 0, 'publication_allowed': False,
            'method': 'Accepted Radar 1 original and attributable passage -> explicitly pre-reviewed official-statistics metric -> live data retrieval -> programmatic range/direction comparison -> limitations. This is NOT automatic full-text understanding or publication verification.',
            'results': rows}


def as_markdown(report):
    lines = ['# Radar 2 — automatic then-versus-observed pilot',
             '', 'Live official observations, NOT published conclusions.',
             '', f"- Accepted originals tested: {report['originals_checked']}",
             f"- Draft comparisons with observed figures: {report['drafts_with_observations']}",
             f"- Data retrieval/validation failures: {report['source_errors']}",
             '- Outcome findings published: **0**', '']
    for row in report['results']:
        lines += ['## ' + row['title'], '', '**Then:** ' + row['historical_proposition'], '',
                  '**Research question:** ' + row['historical_question'], '']
        if 'observation' in row:
            obs = row['observation']
            lines += [f"**Observed:** {obs['value_percent']:.2f}% ({obs['year']}, {obs['geography']}).",
                      f"**Official source:** [Eurostat {obs['dataset']}]({obs['api_url']})",'',
                      '**Similarity:** '+row['comparison']['similarities'], '',
                      '**Difference/limitations:** '+row['comparison']['differences'], '',
                      '**What remains unresolved:** '+row['comparison']['still_unestablished'], '',
                      '**Assessment:** '+row['comparison']['summary'], '']
        else:
            lines += ['**No comparison:** The official data request failed; no conclusion may be drawn.',
                      'Error: '+row['error'], '']
    lines += ['---', 'An EU-27 series is not an exact EU-28 measure; a lexical match is not evidence. Neither result is eligible for automatic website publication.', '']
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output-prefix', type=Path, default=None)
    args = parser.parse_args(argv)
    report = run(args.root)
    base = args.output_prefix or args.root / 'RADAR2-AUTOMATED-OBSERVATIONS'
    base.with_suffix('.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    base.with_suffix('.md').write_text(as_markdown(report), encoding='utf-8')
    print(f"Eurostat live pilot: {report['drafts_with_observations']}/{report['originals_checked']} new observation drafts; {report['source_errors']} source errors; 0 published")
    if report['source_errors']:
        print('Official data unavailable or not verifiable; pilot not counted as successful', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
