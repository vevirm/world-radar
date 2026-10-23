"""Exact group-level review decisions for VV Futures.

A group means one original claim plus at least two distinct later papers.
Never reject a paper or claim globally based on a group decision.
"""
import hashlib
import json
from pathlib import Path

STATUSES = {'rejected', 'accepted', 'uncertain'}


def group_id(claim_id, source_ids):
    ids = sorted(set(str(x).strip() for x in source_ids if str(x).strip()))
    if not claim_id or len(ids) < 2:
        raise ValueError('A group needs a claim and at least two distinct later source IDs')
    key = json.dumps([claim_id, ids], separators=(',', ':'), ensure_ascii=False)
    return 'group-' + hashlib.sha256(key.encode('utf-8')).hexdigest()[:20]


def read_decisions(path):
    path = Path(path)
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding='utf-8'))
    decisions = {}
    for record in doc.get('decisions', []):
        status = record.get('status')
        if status not in STATUSES:
            continue
        gid = group_id(record.get('claim_id'), record.get('source_ids', []))
        decisions[gid] = {'id': gid, **record}
    return decisions


def suggest_groups(claims, connections, decisions, per_claim=1):
    """Shortlist exact combinations; no relevance judgment is implied."""
    grouped = {}
    for conn in connections:
        cid = conn.get('claim_id')
        if cid not in claims or not conn.get('source_id'):
            continue
        grouped.setdefault(cid, {})[conn['source_id']] = conn
    out = []
    for cid, papers in grouped.items():
        ordered = sorted(papers.values(), key=lambda p: (
            p.get('relevance', {}).get('rank') != 'strong_candidate',
            -int(p.get('source_year') or 0), p.get('source_id', '')))
        # Disjoint small groups: a group must never be inferred as "accepted".
        for i in range(0, min(len(ordered), per_claim * 2), 2):
            pair = ordered[i:i + 2]
            if len(pair) != 2:
                continue
            gid = group_id(cid, [p['source_id'] for p in pair])
            decision = decisions.get(gid, {})
            if decision.get('status') == 'rejected':
                continue
            out.append({'id': gid, 'claim_id': cid, 'source_ids': sorted(p['source_id'] for p in pair),
                        'papers': pair, 'status': decision.get('status', 'unchecked'),
                        'reason': decision.get('reason', '')})
    return out
