#!/usr/bin/env python3
"""Radar 1 no-scan admission audit: preview by default, destructive only --apply.

The actual scholarly collection is pruned on apply. A compact DOI tombstone
registry prevents reintroduction on every scheduled/manual scholarly scan.
No Radar 2 data, findings, or retrospectives are touched.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from radar1_admission import POLICY_VERSION, START, END, decision
from radar1_traceability import trace
from scholarly import atomic_json, normal_doi

ROOT = Path(__file__).resolve().parents[1]


def rejection_data(path):
    if not Path(path).exists():
        return {'schema_version': 1, 'policy_version': POLICY_VERSION, 'rejected': {}}
    obj = json.loads(Path(path).read_text(encoding='utf-8'))
    if obj.get('schema_version') != 1 or not isinstance(obj.get('rejected'), dict):
        raise ValueError('Unsupported rejection registry: no files modified')
    return obj


def audit(leads_path, *, apply=False, report_path=None, rejects_path=None, manifest_path=None):
    path = Path(leads_path)
    rejects_path = Path(rejects_path) if rejects_path else path.parent/'radar1-rejected.json'
    manifest_path = Path(manifest_path) if manifest_path else path.parent/'radar1-active.json'
    raw = json.loads(path.read_text(encoding='utf-8'))
    if raw.get('schema_version') != 1 or not isinstance(raw.get('leads'), list):
        raise ValueError('Unexpected Radar 1 academic schema: no files modified')
    ledger = rejection_data(rejects_path)
    past = ledger['rejected']
    counts, reasons, checks, earlier = Counter(), Counter(), Counter(), Counter()
    accepted, new_rejects = [], {}
    excluded_rows = []
    seen = set()
    for row in raw['leads']:
        doi = normal_doi(row.get('doi'))
        if not doi or doi in seen:
            raise ValueError('Invalid/duplicate DOI in academic collection: no files modified')
        seen.add(doi)
        if doi in past:
            ok, why, checked = False, 'previously_rejected', 'rejection_registry'
            earlier['previously_rejected'] += 1
        else:
            ok, why, checked = decision(row)
        checks[checked] += 1
        if ok:
            # The admission result, not old tags, governs the collection.
            kept = dict(row)
            handoff, detail = trace(row)
            if not handoff:
                raise ValueError('Admitted DOI has no traceable Radar 2 question: ' + doi)
            kept['radar2_seed'] = handoff  # An original quote, NOT a Radar 2 analysis.
            kept['radar1_selection'] = 'active'
            kept['source_period'] = 'historical_original'
            kept['radar1_admission_version'] = POLICY_VERSION
            kept['radar1_admission_reason'] = why
            accepted.append(kept)
            counts['active'] += 1
        else:
            reasons[why] += 1
            counts['later_context' if why == 'outside_historical_original_period' else 'excluded'] += 1
            new_rejects[doi] = {'reason': why, 'year': str(row.get('date', ''))[:4]}
            excluded_rows.append({'doi': doi, 'title': row.get('title'),
                                  'date': row.get('date'), 'reason': why,
                                  'formerly': row.get('radar1_selection')})
    proposed_registry = dict(past)
    proposed_registry.update(new_rejects)
    stamp = datetime.now(timezone.utc).isoformat()
    report = {
        'policy_version': POLICY_VERSION, 'generated_at': stamp, 'applied': apply,
        'original_studies': len(raw['leads']), 'historical_period': {'start': str(START), 'end': str(END)},
        'selection_counts': dict(counts), 'retained_in_main_file': len(accepted),
        'removed_from_main_file': len(new_rejects),
        'prior_rejections': len(past), 'rejection_registry_after_apply': len(proposed_registry),
        'removed_by_reason': dict(sorted(reasons.items())), 'inspection_method': dict(checks),
        'already_rejected_encountered': dict(earlier),
        'examples_kept': [{'doi': r['doi'], 'title': r['title'],
                           'reason': r['radar1_admission_reason'],
                           'original_passage': r['radar2_seed']['original_passage']}
                          for r in accepted[:30]],
        'proposed_removals': excluded_rows,
        'note': 'A scope admission decision, not a scientific-quality or forecast-accuracy verdict. '
                'Preview never edits the collection, priority list, or rejection registry. '
                'A metadata-only uncertain original is removed after its available abstract is inspected.',
    }
    if apply:
        # Precondition checks are complete before starting any file changes.
        ledger['policy_version'] = POLICY_VERSION
        ledger['rejected'] = dict(sorted(proposed_registry.items()))
        newdb = dict(raw)
        newdb['updated_at'] = stamp
        newdb['leads'] = accepted
        newdb['admission_policy_version'] = POLICY_VERSION
        manifest = {'schema_version': 1, 'generated_at': stamp,
                    'historical_start': str(START), 'historical_end': str(END),
                    'original_records': len(accepted),
                    'selection_counts': {'active': len(accepted)},
                    'rejected_identifier_count': len(proposed_registry),
                    'studies': [{'doi': r['doi'], 'title': r['title'],
                                 'date': r['date'], 'selection': 'active',
                                 'admission_reason': r['radar1_admission_reason'],
                                 'original_passage': r['radar2_seed']['original_passage'],
                                 'investigation_type': r['radar2_seed']['investigation_type']}
                                for r in accepted],
                    'note': 'Accepted historical academic originals only. Radar 2 not changed.'}
        atomic_json(rejects_path, ledger)
        atomic_json(path, newdb)
        atomic_json(manifest_path, manifest)
    if report_path:
        atomic_json(Path(report_path), report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--leads', default=str(ROOT/'research-leads.json'))
    p.add_argument('--rejections', default=None)
    p.add_argument('--manifest', default=None)
    p.add_argument('--report', default=str(ROOT/'radar1-scope-report.json'))
    p.add_argument('--apply', action='store_true', help='Remove nonqualifying papers and write DOI rejections')
    args = p.parse_args()
    result = audit(args.leads, apply=args.apply, report_path=args.report,
                   rejects_path=args.rejections, manifest_path=args.manifest)
    print(json.dumps({k: result[k] for k in ('applied', 'original_studies',
          'retained_in_main_file', 'removed_from_main_file', 'selection_counts',
          'rejection_registry_after_apply', 'inspection_method')}, indent=2))


if __name__ == '__main__':
    main()
