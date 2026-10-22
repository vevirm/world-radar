#!/usr/bin/env python3
"""Non-destructive Radar 1 subject-scope preview and optional tagging.

This changes annotations on existing scholarly leads, not their identity, DOI,
original title, abstract or publication date. Radar 2 is deliberately unchanged.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from scholarly import foresight_scope, eu_connection, atomic_json

ROOT = Path(__file__).resolve().parents[1]
VERSION = 1


def audit(leads_path, *, apply=False, report_path=None):
    path = Path(leads_path)
    raw = json.loads(path.read_text(encoding='utf-8'))
    if raw.get('schema_version') != 1 or not isinstance(raw.get('leads'), list):
        raise ValueError('Unexpected Radar 1 research-leads schema; leaving file unchanged')
    leads = raw['leads']
    original_keys = [(row.get('doi'), row.get('title'), row.get('date')) for row in leads]
    if len(set(x[0] for x in original_keys)) != len(leads):
        raise ValueError('Duplicate or missing DOIs: refuse to classify this file automatically')
    counts = Counter()
    examples = {'future_facing': [], 'needs_review': [], 'out_of_scope': []}
    eu_examples = {k: [] for k in ('eu_official', 'eu_institution', 'eu_focused', 'eu_related', 'review')}
    eu_counts = Counter()
    cross_tab = Counter()
    by_reason = Counter()
    new_tags = 0
    for row in leads:
        label, reason = foresight_scope(row)
        counts[label] += 1
        by_reason[reason] += 1
        eu_tier, eu_reason = eu_connection(row)
        eu_counts[eu_tier] += 1
        cross_tab[f'{label} / {eu_tier}'] += 1
        if len(eu_examples[eu_tier]) < 12:
            eu_examples[eu_tier].append({'doi': row.get('doi'), 'title': row.get('title'), 'eu_reason': eu_reason})
        if (row.get('foresight_scope') != label or row.get('foresight_scope_reason') != reason
                or row.get('eu_connection') != eu_tier or row.get('eu_connection_reason') != eu_reason):
            new_tags += 1
        if len(examples[label]) < 15:
            examples[label].append({'doi': row.get('doi'), 'title': row.get('title'), 'reason': reason})
        if apply:
            row['foresight_scope'] = label
            row['foresight_scope_reason'] = reason
            row['foresight_scope_version'] = VERSION
            row['eu_connection'] = eu_tier
            row['eu_connection_reason'] = eu_reason
            row['eu_connection_version'] = VERSION
    if len(leads) != len(original_keys) or [
        (row.get('doi'), row.get('title'), row.get('date')) for row in leads
    ] != original_keys:
        raise AssertionError('Original research changed during screening; aborting')
    report = {'screen_version': VERSION, 'generated_at': datetime.now(timezone.utc).isoformat(),
              'applied': apply, 'original_studies': len(leads),
              'classification_counts': dict(counts), 'eu_connection_counts': dict(eu_counts),
              'future_by_eu_connection': dict(cross_tab), 'eu_examples': eu_examples,
              'reason_counts': dict(by_reason),
              'tags_added_or_changed': new_tags,
              'meaning': {
                  'future_facing': 'Explicitly addresses possible future developments; not a verified forecast',
                  'needs_review': 'Potentially relevant but metadata does not establish a central foresight question',
                  'out_of_scope': 'Clear title-level non-foresight use, retained only in history',
                  'eu_official': 'Official EU publisher URL in the source metadata',
                  'eu_institution': 'An EU institutional publisher or affiliation appears in index metadata, not independently verified',
                  'eu_focused': 'Europe/EU central to the original paper title',
                  'eu_related': 'Europe/EU mentioned in the abstract but not central in the title',
                  'review': 'EU connection not yet demonstrated; record remains archived'
              }, 'examples': examples,
              'next_stage': 'Radar 2 continues unchanged until its lead selection is explicitly aligned with this scope.'}
    if report_path:
        atomic_json(Path(report_path), report)
    if apply:
        atomic_json(path, raw)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--leads', default=str(ROOT/'research-leads.json'))
    parser.add_argument('--report', default=str(ROOT/'radar1-scope-report.json'))
    parser.add_argument('--apply', action='store_true', help='Tag leads without deleting any originals')
    args = parser.parse_args()
    report = audit(args.leads, apply=args.apply, report_path=args.report)
    print(json.dumps({'applied': report['applied'], 'studies': report['original_studies'],
                      'future': report['classification_counts'],
                      'eu_connection': report['eu_connection_counts'],
                      'changed': report['tags_added_or_changed']},
                     indent=2))


if __name__ == '__main__':
    main()
