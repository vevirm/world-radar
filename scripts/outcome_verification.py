"""Strict, machine-checkable retrospective comparison registry.

An OpenAlex paper match alone cannot produce a verified outcome. Evidence records
must be reviewed and connected to the original text and observed measurements.
"""
import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / 'verified-outcomes.json'
QUEUE = ROOT / 'outcome-review-queue.json'
VALID = {'realized', 'materializing', 'contradicted', 'partially_realized', 'not_yet_due'}

def valid_url(value):
    try:
        p = urlparse(str(value))
        return p.scheme == 'https' and bool(p.netloc) and '.' in p.netloc
    except ValueError:
        return False

def verify_case(case, leads, today=None):
    """Return a reason for rejection, or None for structurally complete case.

    Structural checks are NOT proof the underlying source statements are correct.
    Human source review is required before a case is labelled verified.
    """
    today = today or dt.date.today()
    lead = leads.get(case.get('lead_id'))
    if not lead:
        return 'Unknown Scanner 1 lead ID'
    original = case.get('original') or {}
    observation = case.get('observation') or {}
    if not case.get('source_reviewed_by') or not case.get('reviewed_on'):
        return 'Original and observed sources require a named reviewer and review date'
    if not original.get('verbatim_passage') or len(original['verbatim_passage'].strip()) < 35:
        return 'Missing original verbatim forecast passage'
    if not valid_url(original.get('url')) or original['url'].rstrip('/') != lead['source_url'].rstrip('/'):
        return 'Original URL must match Scanner 1 source'
    if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}', str(original.get('published_on', ''))):
        return 'Missing full original publication date'
    if not original.get('geography') or not original.get('observable') or not original.get('target_date'):
        return 'Missing forecast geography, observable or target date'
    if not observation.get('what_happened') or not observation.get('measured_on'):
        return 'Missing observed result or measurement date'
    try:
        published = dt.date.fromisoformat(original['published_on'])
        measured = dt.date.fromisoformat(observation['measured_on'])
        reviewed = dt.date.fromisoformat(case['reviewed_on'])
        target = dt.date.fromisoformat(original['target_date'])
    except (ValueError, TypeError):
        return 'Invalid source, target, observation or review date'
    if published > measured or measured > today or reviewed > today:
        return 'Observation must follow original publication and cannot be in the future'
    if not observation.get('same_metric_and_geography_explained'):
        return 'Comparison must explain metrics, geography and baselines'
    sources = observation.get('sources') or []
    if not sources or not all(valid_url(s.get('url')) and s.get('finding') and s.get('date') for s in sources):
        return 'Dated independent evidence source missing'
    if any(s['url'].rstrip('/') == original['url'].rstrip('/') for s in sources):
        return 'Original study cannot be its own independent observation'
    if case.get('verdict') not in VALID:
        return 'Unknown verdict'
    if case.get('verdict') == 'realized' and target > measured:
        return 'Premature realization before target date requires a separately evidenced early completion case'
    if not case.get('limitations'):
        return 'Missing limitations / counterevidence discussion'
    return None

def assemble(entries, registry=None):
    registry = registry if registry is not None else json.loads(REGISTRY.read_text(encoding='utf-8')).get('cases', [])
    leads = {e['id']: e for e in entries}
    accepted, rejected = [], []
    for case in registry:
        reason = verify_case(case, leads)
        if reason:
            rejected.append({'lead_id': case.get('lead_id'), 'reason': reason})
        else:
            accepted.append(case)
    return accepted, rejected

def write_queue(entries):
    candidates = []
    for e in entries:
        if e.get('screening_status') != 'candidate_needs_validation':
            continue
        candidates.append({'lead_id': e['id'], 'title': e['title'], 'source_url': e['source_url'],
                           'original_publication': e.get('original_publication'),
                           'candidate_excerpt': e.get('candidate_excerpt'),
                           'target_year_candidate': e.get('candidate_year'),
                           'next_action': 'Read original text and verify exact prediction, geography, metric and date; then obtain independent official outcome measurement.',
                           'state': 'requires_original_and_evidence_review'})
    QUEUE.write_text(json.dumps({'schema_version': 1, 'candidate_count': len(candidates), 'candidates': candidates}, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    return candidates
