#!/usr/bin/env python3
"""Radar 2: source-question-first official-data pilot (drafts only).

A number in a historical study is not necessarily that study's foresight.
All contracts require source-traceable evidence for their *central question*;
background figures are excluded before network access.  Observations from
non-equivalent geographies/definitions are reported as context, never scored
as support for or failure of a forecast.

This intentionally remains a narrow, reviewed mapping, NOT general automated
understanding of the 398 originals. It never edits publication data.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
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

# Each case's status is established from the original passage and question,
# not from a match between one keyword and an indicator name.
CONTRACTS = (
    {
        'id': 'lead-616c0b7511591643',
        'quote': 'By 2020, 20% of the European electricity demand will be met by renewable generation',
        'central_focus_evidence': 'Microgrids: Enhancing the Resilience of the European Megagrid',
        'central_question': 'How can microgrids enhance the resilience of the European electricity grid?',
        'claim_role': 'background_context',
        'reason_for_role': 'The 20% statement introduces the changing electricity system; it does not measure microgrid resilience, the paper’s central question.',
        'year': 2020, 'observed_geo': 'EU27_2020', 'original_geo': 'Europe, boundaries unspecified',
        'energy_balance': 'REN_ELC', 'measure': 'renewable share in gross electricity consumption',
        'original_measure': 'renewable generation as share of electricity demand',
        'bound_type': 'at_least', 'expected': 20.0,
        'metric_fit': 'not_central',
    },
    {
        'id': 'lead-ceb54d6064f5f1af',
        'quote': 'The share of REs in GFEC in EU 28 varies from 19.4% to 21.8% in future trajectories towards 2020',
        'central_focus_evidence': 'this work proposes future trajectories towards 2020',
        'central_question': 'How did the renewable share of EU-28 gross final energy consumption develop toward 2020 compared with modelled trajectories?',
        'claim_role': 'central_projection',
        'reason_for_role': 'The saved original passage explicitly describes mathematical forecasts of this exact indicator.',
        'year': 2020, 'baseline_year': 2017,
        'observed_geo': 'EU27_2020', 'original_geo': 'EU-28',
        'energy_balance': 'REN', 'measure': 'share of renewable energy in gross final energy consumption',
        'original_measure': 'share of renewables in gross final energy consumption',
        'bound_type': 'range', 'expected': (19.4, 21.8),
        'metric_fit': 'same_indicator_different_geography',
    },
)


def api_url(case, *, year=None):
    params = {'lang': 'EN', 'freq': 'A', 'unit': 'PC',
              'nrg_bal': case['energy_balance'], 'geo': case['observed_geo'],
              'time': str(case['year'] if year is None else year)}
    return API_HOST + DATASET + '?' + urlencode(params)


def get_api_json(url):
    if not url.startswith(API_HOST) or url.split('?', 1)[0] != API_HOST + DATASET:
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


def observation(data, case, *, year=None):
    """Decode exactly one JSON-stat percentage cell, checking all dimensions."""
    if data.get('class') != 'dataset' or data.get('version') != '2.0':
        raise ValueError('Eurostat response is not JSON-stat dataset 2.0')
    ids, sizes, dims = data.get('id'), data.get('size'), data.get('dimension') or {}
    if not isinstance(ids, list) or not isinstance(sizes, list) or len(ids) != len(sizes):
        raise ValueError('Invalid Eurostat dimension array')
    expected = {'freq': 'A', 'unit': 'PC', 'nrg_bal': case['energy_balance'],
                'geo': case['observed_geo'], 'time': str(case['year'] if year is None else year)}
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
    for c in contracts:
        o = accepted.get(c['id'])
        if not o or o.get('source_kind') != 'academic':
            raise ValueError('Original is not in accepted Radar 1: '+c['id'])
        if not o.get('investigation_ready') or not o.get('source_url', '').startswith('https://'):
            raise ValueError('Original source not ready: '+c['id'])
        passage = ' '.join(o['original_passage'].split()).casefold()
        quote = ' '.join(c['quote'].split()).casefold()
        if quote not in passage:
            raise ValueError('Original proposition cannot be traced verbatim: '+c['id'])
        focus = ' '.join(c.get('central_focus_evidence', '').split()).casefold()
        if not focus or focus not in (passage + ' ' + o['title'].casefold()):
            raise ValueError('Core study focus not traceable to original: '+c['id'])
        if not str(c.get('central_question', '')).strip():
            raise ValueError('Missing central question: '+c['id'])
        if c.get('claim_role') not in ('background_context', 'central_projection'):
            raise ValueError('Unreviewed role of historical claim: '+c['id'])
        if c.get('claim_role') == 'background_context' and c.get('metric_fit') != 'not_central':
            raise ValueError('Background quote cannot be scored as central: '+c['id'])
        if c.get('claim_role') == 'central_projection' and c.get('metric_fit') not in ('direct', 'same_indicator_different_geography'):
            raise ValueError('Central projection lacks reviewed indicator mapping: '+c['id'])
        if c.get('metric_fit') == 'direct' and c.get('original_geo') != c.get('observed_geo'):
            raise ValueError('Non-equivalent geography falsely marked direct: '+c['id'])
        if c.get('metric_fit') == 'direct' and c.get('original_measure') != c.get('measure'):
            raise ValueError('Non-equivalent measure falsely marked direct: '+c['id'])
        if int(o['original_publication'][:4]) >= c['year']:
            raise ValueError('Observation must follow publication: '+c['id'])
        if c.get('baseline_year') is not None and int(c['baseline_year']) >= int(o['original_publication'][:4]):
            raise ValueError('Baseline must precede publication: '+c['id'])
        found.append((c, o))
    return found


def excluded_background(case, original):
    return {
        'original_id': original['id'], 'title': original['title'],
        'original_publication': original['original_publication'],
        'original_url': original['source_url'], 'original_passage': original['original_passage'],
        'historical_proposition': case['quote'],
        'central_question': case['central_question'],
        'status': 'wrong_question_no_comparison',
        'reason': case['reason_for_role'],
        'evidence_search_performed': False,
        'comparison_grade': 'not_assessed',
        'outcome_verified': False, 'publication_allowed': False,
    }


def analyse(case, original, value, url, *, baseline_value=None):
    if case['claim_role'] != 'central_projection':
        raise ValueError('Cannot analyse background quote as a forecast')
    comparable = case['metric_fit'] == 'direct'
    obs = {'value_percent': value, 'year': case['year'],
           'geography': 'EU-27 (2020 composition)' if case['observed_geo']=='EU27_2020' else case['observed_geo'],
           'indicator': case['measure'], 'dataset': DATASET, 'dataset_url': BROWSER,
           'api_url': url, 'data_updated': None, 'unit': 'percent'}
    if baseline_value is not None:
        obs['baseline'] = {'value_percent': baseline_value, 'year': case['baseline_year'],
                           'api_url': api_url(case, year=case['baseline_year']),
                           'note': 'Same indicator and EU-27 boundary as observed value, not necessarily the original EU-28 boundary.'}

    if not comparable:
        # No arithmetic forecast-error or 'similarity' conclusion on different EU populations.
        if baseline_value is not None:
            trend = round(value-baseline_value, 3)
            trend_text = (f'Within the EU-27 series, the renewable share changed by {trend:+.2f} '
                          f'percentage points between {case["baseline_year"]} and {case["year"]}. '
                          'This is a documented later development, not a test of the EU-28 forecast.')
        else:
            trend_text = 'A pre-publication baseline for this identical indicator is not available.'
        status = 'later_development_found_but_comparison_not_established'
        comparison = {
            'summary': 'Exact comparison not established: the historical model covers EU-28, but the official observation covers EU-27.',
            'what_happened': f'Eurostat reports {value:.2f}% for EU-27 in {case["year"]}. '+trend_text,
            'similarities': 'Not determined using non-equivalent populations.',
            'differences': 'The historical EU-28 and later EU-27 geographic bases are different. No forecast error or match can be inferred.',
            'still_unestablished': 'A valid EU-28 figure for the same 2020 denominator, or a defensible reconstruction, is needed.',
            'present_relevance': 'The published EU-27 series documents the transition, not whether the original EU-28 scenario was accurate.',
        }
    else:
        # Only exact matches can ever receive numerical forecast-distance language.
        if case['bound_type']=='range':
            low, high = case['expected']
            delta = round(value-high if value>high else low-value if value<low else 0, 3)
            result = 'within' if low <= value <= high else 'outside'
            similarity = f'Comparable observed value {value:.2f}% is {result} the historical {low:.1f}–{high:.1f}% range (distance {delta:.2f} points).'
        elif case['bound_type']=='at_least':
            expected = float(case['expected'])
            similarity = f'Comparable observed value {value:.2f}% is {value-expected:+.2f} points from the historical {expected:.1f}% threshold.'
        else:
            raise ValueError('Unsupported quantitative claim')
        status = 'automated_comparable_evidence_draft'
        comparison = {'summary': 'Statistical comparison possible; historical assumptions and interpretation still require review.',
                      'what_happened': f'Eurostat reports {value:.2f}% in {case["year"]}.',
                      'similarities':similarity, 'differences':'A numerical fit does not establish the original mechanism or scenario assumptions.',
                      'still_unestablished':'Whether the observed outcome arose for the reasons anticipated by the original study.',
                      'present_relevance':'A single indicator should not stand in for the entire study.'}

    return {'original_id':original['id'], 'title':original['title'],
            'original_publication':original['original_publication'],
            'original_url':original['source_url'], 'original_passage':original['original_passage'],
            'historical_proposition':case['quote'], 'central_question':case['central_question'],
            'original_geography':case['original_geo'], 'historical_measure':case['original_measure'],
            'observation':obs, 'comparison':comparison, 'comparison_grade':'provisional_direct' if comparable else 'not_comparable_proxy',
            'evidence_search_performed':True, 'outcome_verified':False, 'publication_allowed':False, 'status':status}


def run(root=ROOT, fetch=get_api_json, contracts=CONTRACTS):
    rows=[]
    for case, original in selected_originals(root, contracts):
        if case['claim_role']=='background_context':
            rows.append(excluded_background(case, original))
            continue
        url = api_url(case)
        try:
            data = fetch(url)
            value = observation(data, case)
            baseline_value = None
            if case.get('baseline_year') is not None:
                baseline_doc = fetch(api_url(case, year=case['baseline_year']))
                baseline_value = observation(baseline_doc, case, year=case['baseline_year'])
            item = analyse(case, original, value, url, baseline_value=baseline_value)
            item['observation']['data_updated'] = data.get('updated')
        except Exception as exc:
            item={'original_id': original['id'], 'title': original['title'],
                  'central_question':case['central_question'], 'historical_proposition':case['quote'],
                  'evidence_api_url':url, 'status':'source_unavailable_no_conclusion',
                  'error':type(exc).__name__+': '+str(exc)[:250],
                  'outcome_verified':False, 'publication_allowed':False}
        rows.append(item)
    return {'schema_version':2, 'mode':'LIVE_EUROSTAT_QUESTION_FIRST_BOUNDED',
            'generated_utc':datetime.now(timezone.utc).isoformat(),
            'originals_checked':len(rows),
            'excluded_wrong_question':sum(r['status']=='wrong_question_no_comparison' for r in rows),
            'observations_with_non_equivalent_geographies':sum(r['status']=='later_development_found_but_comparison_not_established' for r in rows),
            'drafts_with_comparable_observations':sum(r['status']=='automated_comparable_evidence_draft' for r in rows),
            'source_errors':sum(r['status']=='source_unavailable_no_conclusion' for r in rows),
            'published_outcomes':0, 'publication_allowed':False,
            'method': 'Review the original central question first. Reject a background numeric claim. Fetch official evidence only for a central question. Compare numerically only if geography, period and measure match. Preserve non-equivalent later observations without declaring prediction success/failure. Drafts only.',
            'results':rows}


def as_markdown(report):
    lines=['# Radar 2 — question-first automatic evidence pilot', '',
           'Draft research observations, NOT published conclusions.', '',
           f'- Original studies checked: {report["originals_checked"]}',
           f'- Misleading background quotes excluded before search: {report["excluded_wrong_question"]}',
           f'- Later developments found, but no equivalent comparison: {report["observations_with_non_equivalent_geographies"]}',
           f'- Directly comparable observation drafts: {report["drafts_with_comparable_observations"]}',
           f'- Source failures: {report["source_errors"]}',
           '- Published conclusions: **0**', '']
    for row in report['results']:
        lines += ['## '+row['title'], '', '**Central study question:** '+row['central_question'], '',
                  '**Original passage:** '+row['historical_proposition'], '']
        if row['status']=='wrong_question_no_comparison':
            lines += ['**Result: comparison rejected before searching.** '+row['reason'], '',
                      '**Research status:** The actual central question remains uninvestigated. No evidence-gap finding has been established.', '']
        elif 'observation' in row:
            obs=row['observation']
            lines += [f'**Later observed figure:** {obs["value_percent"]:.2f}% ({obs["year"]}, {obs["geography"]}).',
                      f'**Source:** [Eurostat {obs["dataset"]}]({obs["api_url"]})', '',
                      '**What happened:** '+row['comparison']['what_happened'], '',
                      '**Relationship to historical thinking:** '+row['comparison']['summary'], '',
                      '**What remains unresolved:** '+row['comparison']['still_unestablished'], '']
        else:
            lines += ['**No comparison:** Official data unavailable; no conclusion drawn.',
                      'Error: '+row['error'], '']
    lines += ['---', 'A rejected comparison is NOT evidence that the original foresight was wrong. An unavailable equivalent statistic is NOT evidence that the question has been thoroughly investigated.', '']
    return '\n'.join(lines)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output-prefix', type=Path, default=None)
    args=parser.parse_args(argv)
    report=run(args.root)
    base=args.output_prefix or args.root/'RADAR2-AUTOMATED-OBSERVATIONS'
    base.with_suffix('.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    base.with_suffix('.md').write_text(as_markdown(report),encoding='utf-8')
    print(f'Question-first pilot: {report["excluded_wrong_question"]} wrong-question, '
          f'{report["observations_with_non_equivalent_geographies"]} observed but not comparable, '
          f'{report["drafts_with_comparable_observations"]} comparable draft, '
          f'{report["source_errors"]} source errors, 0 published')
    if report['source_errors']:
        print('Source data unavailable; pilot not counted as fully successful',file=sys.stderr)
        return 1
    return 0

if __name__=='__main__':
    raise SystemExit(main())
