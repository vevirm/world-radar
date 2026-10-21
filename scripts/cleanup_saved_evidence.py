"""Re-screen saved literature links using one shared evidence policy (NO API calls).

No original research records, source-reviewed outcomes or policy snapshots are
removed. Direct topic trails are kept, indirect context is separated, and
clear errors/duplicates are quarantined with reversible metadata. Dry-run is
always the default. Applies to the latest saved Radar 2 research after it has
been backed up by the GitHub workflow.
"""
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path

try:
    from .evidence_policy import classify, canonical_url
except ImportError:
    from evidence_policy import classify, canonical_url

FIELDS = ('direction_evidence', 'follow_up_publications', 'field_developments')


def clean_entries(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get('entries'), dict):
        raise ValueError('Expected a research database with entries.')
    cleaned = copy.deepcopy(raw)
    quarantine = []
    stats = Counter()
    for lead_id, entry in cleaned['entries'].items():
        if not isinstance(entry, dict):
            continue
        existing_count = sum(len(entry.get(field) or []) for field in FIELDS if isinstance(entry.get(field), list))
        direct, related = {'direction_evidence': [], 'follow_up_publications': []}, []
        seen_urls = set()
        for field in FIELDS:
            items = entry.get(field) or []
            if not isinstance(items, list):
                items = []
            for item in items:
                stats['examined'] += 1
                role, reason = classify(entry, item, field)
                url = canonical_url(item.get('url')) if isinstance(item, dict) else ''
                if url and url in seen_urls:
                    role, reason = 'quarantine', 'duplicate_link_across_trails'
                if url:
                    seen_urls.add(url)
                if role == 'quarantine':
                    stats['quarantined'] += 1
                    stats['reason:' + reason] += 1
                    quarantine.append({'lead_id': lead_id, 'original_title': entry.get('title'),
                                       'field': field, 'reason': reason, 'publication': item})
                    continue
                new = dict(item)
                new['evidence_role'] = 'same_issue_literature' if role == 'direct' else 'related_context'
                if role == 'context':
                    new['context_reason'] = reason
                    related.append(new)
                    stats['context'] += 1
                    stats['reason:' + reason] += 1
                else:
                    direct[field].append(new)
                    stats['direct'] += 1
        entry['direction_evidence'] = direct['direction_evidence']
        entry['follow_up_publications'] = direct['follow_up_publications']
        entry['field_developments'] = related
        good = len(direct['direction_evidence']) + len(direct['follow_up_publications'])
        if existing_count and not good:
            # Only update scanner-generated status text; verified human evidence
            # and concrete observations must never be rewritten.
            entry['what_happened_literature'] = (
                'No direct same-question publication remains in the screened saved links. '
                'Broader context may still be available.')
            entry['literature_signal'] = 'no_direct_same_issue_link_retained'
        elif existing_count and good:
            entry['what_happened_literature'] = (
                f'{good} later publication(s) remain as candidate research on this question. '
                'Related context is kept separately; no observed outcome is implied.')
    return cleaned, quarantine, stats


def run(root: Path, apply=False):
    root = Path(root)
    src = root / 'retrospective-results.json'
    raw = json.loads(src.read_text(encoding='utf-8'))
    if not raw.get('entries'):
        raise ValueError('Empty research database: refusing to clean.')
    cleaned, newly_excluded, stats = clean_entries(raw)
    report = {
        'original_records': len(raw['entries']),
        'examined': stats['examined'],
        'same_issue_literature': stats['direct'],
        'related_context_not_direct_evidence': stats['context'],
        'quarantined_this_run': stats['quarantined'],
        'reasons': {key[7:]: value for key, value in sorted(stats.items()) if key.startswith('reason:')},
        'method': 'Research link screening only; not fact-checking or prediction grading',
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not apply:
        print('DRY RUN: no data changed. --apply saves cleaned evidence and rebuilds atlas.')
        return report
    if len(cleaned['entries']) != len(raw['entries']):
        raise ValueError('Record loss: no changes published.')
    if stats['examined'] >= 20 and stats['quarantined'] / stats['examined'] > .95:
        raise ValueError('Over 95% screened out: refusing unsafe cleanup.')

    # Validate the atlas in memory before touching any output, including the
    # archive registry. Existing approval/observation files remain unchanged.
    try:
        from .living_atlas import make_atlas
    except ImportError:
        from living_atlas import make_atlas
    leads = json.loads((root / 'research-leads.json').read_text(encoding='utf-8')).get('leads') or []
    if not leads:
        raise ValueError('Empty original research catalogue: refusing cleanup.')
    atlas = make_atlas(list(cleaned['entries'].values()), leads=leads)
    if len(atlas['records']) != len(leads):
        raise ValueError('Atlas lost original studies: refusing cleanup.')
    quarantine_file = root / 'evidence-quarantine.json'
    old_quarantine = json.loads(quarantine_file.read_text(encoding='utf-8')) if quarantine_file.exists() else {'links': []}
    excluded = list(old_quarantine.get('links') or [])
    known = {(item.get('lead_id'), canonical_url((item.get('publication') or {}).get('url')),
              item.get('field')) for item in excluded if isinstance(item, dict)}
    for item in newly_excluded:
        ident = (item.get('lead_id'), canonical_url((item.get('publication') or {}).get('url')),
                 item.get('field'))
        if ident not in known:
            excluded.append(item)
            known.add(ident)

    # All calculations above are validation-only. The caller's GitHub workflow
    # uploads the ORIGINAL files before this stage so changes can be reverted.
    src.write_text(json.dumps(cleaned, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (root / 'living-atlas.json').write_text(json.dumps(atlas, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    quarantine_file.write_text(json.dumps({
        'method': 'Quarantined automatic links; original studies and verified outcomes retained.',
        'links': excluded}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (root / 'evidence-cleanup-summary.json').write_text(json.dumps({**report,
        'quarantine_history_total': len(excluded)}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"PUBLISHED: {len(atlas['records'])} original studies, {stats['direct']} same-issue links, "
          f"{stats['context']} context links, {len(excluded)} quarantine history links")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    run(args.root.resolve(), apply=args.apply)

if __name__ == '__main__':
    main()
