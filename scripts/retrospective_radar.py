"""Radar 2: source-grounded, clearly *informal* retrospective judgments.

Requires OPENAI_API_KEY for new research. Without it, preserves past reports
and marks newly found claims as unassessed; never manufactures outcomes/scores.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'retrospective-results.json'
REPORT = ROOT / 'stuff' / 'WHAT_WAS_EXPECTED_WHAT_HAPPENED.docx'
MODEL = os.getenv('RADAR_OUTCOME_MODEL', 'gpt-4.1-mini')


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default


def concise(sentence):
    return re.sub(r'\s+', ' ', str(sentence or '')).strip()


def claims():
    """Only traceable extracted predictions, not titles or bibliographic leads."""
    out = {}
    for item in read_json(ROOT / 'future-ideas.json', []):
        if item.get('claim') and item.get('source_url'):
            out[item['id']] = {'id': item['id'], 'expected': concise(item['claim']),
                               'source_url': item['source_url'], 'title': item.get('title', ''),
                               'target_year': item.get('target_year')}
    for finding in read_json(ROOT / 'findings.json', {}).get('findings', []):
        text = concise(finding.get('comparison', {}).get('foresight_claim') or finding.get('finding'))
        # Never treat a research title or topical lead as an original forecast.
        if not text or not re.search(r'\b(projected|predicted|forecast|expected|will|would|by 20\d\d)\b', text, re.I):
            continue
        url = finding.get('full_text_url') or finding.get('url')
        if not url:
            continue
        key = 'finding-' + hashlib.sha256((url + text).encode()).hexdigest()[:16]
        out[key] = {'id': key, 'expected': text, 'source_url': url,
                    'title': finding.get('title', ''), 'target_year': None}
    return list(out.values())


def response_text(payload):
    chunks = []
    for output in payload.get('output', []):
        if output.get('type') == 'message':
            for content in output.get('content', []):
                if content.get('type') == 'output_text':
                    chunks.append(content.get('text', ''))
    return '\n'.join(chunks)


def retrieve_assessment(claim, key):
    now = dt.date.today().isoformat()
    prompt = f'''Today: {now}. Investigate this historical European forecast using WEB SEARCH and reliable, independently dated evidence (Eurostat, ECB, OECD, national statistics, institutional publications first). Use outcome evidence for the ORIGINAL target time, including years before 2026; don't limit yourself to recent news. Do not treat re-statements of the forecast, predictions, headlines alone, or unverified secondary guesses as outcomes. Do not fabricate citations.\n\nOriginal claim: {claim['expected']}\nOriginal research: {claim['source_url']}\nTarget year if known: {claim.get('target_year')}\n\nReturn ONLY a JSON object with fields: status (assessed / too_early / insufficient_evidence), what_expected (ONE sentence faithful to the original; don't invent specificity), what_happened (ONE sentence summarizing demonstrable outcome, or clearly saying not yet known), score (integer 1-100 ONLY for assessed, otherwise null), evidence (array of objects each with url, date, finding; at least one trustworthy URL for assessed), reasoning (brief). Score is an informal rough judgment of foresight accuracy, NOT a rigorous numeric metric. 1 means completely wrong, 100 means exceptionally accurate. Do not score an uncompleted forecast or evidence too thin to compare. Do not use the original forecast source as sole outcome evidence. If ambiguous or non-testable, return insufficient_evidence.''' 
    request = {'model': MODEL, 'tools': [{'type': 'web_search_preview'}],
               'input': prompt, 'max_output_tokens': 1100}
    req = urllib.request.Request('https://api.openai.com/v1/responses',
        data=json.dumps(request).encode('utf-8'),
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=100) as response:
        data = json.load(response)
    raw = response_text(data)
    match = re.search(r'\{[\s\S]*\}', raw)
    if not match:
        raise ValueError('No structured assessment in response')
    return json.loads(match.group())


def normalize(claim, result):
    status = result.get('status', 'insufficient_evidence')
    if status not in ('assessed', 'too_early', 'insufficient_evidence'):
        status = 'insufficient_evidence'
    evidence = [e for e in result.get('evidence', []) if isinstance(e, dict)
                and re.match(r'^https?://', str(e.get('url', '')))]
    score = result.get('score')
    target = claim.get('target_year')
    if target is not None and str(target).isdigit() and int(target) > dt.date.today().year:
        status = 'too_early'
    if not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 100 or not evidence:
        status = 'insufficient_evidence' if status == 'assessed' else status
    if status != 'assessed':
        score = None
    return {**claim, 'what_expected': concise(result.get('what_expected') or claim['expected']),
            'what_happened': concise(result.get('what_happened') or 'No independently verified outcome yet.'),
            'status': status, 'score': score, 'evidence': evidence,
            'reasoning': concise(result.get('reasoning', '')),
            'checked_utc': dt.datetime.now(dt.timezone.utc).isoformat()}


def build_word(entries):
    from docx import Document
    from docx.shared import Inches, Pt
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = sec.bottom_margin = Inches(.75)
    doc.add_heading('What was expected — what happened', 0)
    doc.add_paragraph('Radar 2 | Informal historical foresight review | ' + dt.date.today().isoformat())
    doc.add_paragraph('Scores are rough editorial estimates, not scientific measurements. Unresolved predictions receive no score.')
    if not entries:
        doc.add_paragraph('No source-linked predictions are available from Radar 1 yet.')
    for n, item in enumerate(entries, 1):
        doc.add_heading(f'{n}. {item.get("title") or "Prediction"}', level=2)
        doc.add_paragraph('What was expected: ' + concise(item.get('what_expected') or item['expected']).rstrip('. ') + '.')
        doc.add_paragraph('What happened: ' + concise(item.get('what_happened') or 'Not yet assessed.').rstrip('. ') + '.')
        doc.add_paragraph('Foresight score: ' + (f"{item['score']}/100 (rough estimate)" if item.get('score') is not None else 'Not scored — ' + item.get('status', 'not yet assessed').replace('_', ' ')))
        p = doc.add_paragraph('Original: ' + item['source_url']); p.style = 'Caption'
        for e in item.get('evidence', [])[:3]:
            p = doc.add_paragraph('Outcome evidence: ' + e['url'] + (' (' + str(e.get('date')) + ')' if e.get('date') else ''))
            p.style = 'Caption'
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(REPORT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--minutes', type=float, default=18)
    ap.add_argument('--max-claims', type=int, default=16)
    ap.add_argument('--offline', action='store_true')
    args = ap.parse_args()
    stored = read_json(OUTPUT, {'entries': {}})
    entries = stored.setdefault('entries', {})
    found = claims()
    key = os.getenv('OPENAI_API_KEY', '')
    deadline = time.monotonic() + max(0, args.minutes) * 60
    worked = 0
    for claim in found:
        if claim['id'] not in entries:
            entries[claim['id']] = {**claim, 'what_expected': claim['expected'],
                                   'what_happened': 'No independently verified outcome yet.',
                                   'score': None, 'status': 'not_yet_assessed', 'evidence': []}
    # Rotate oldest checked first; maintain history instead of resetting the report.
    queue = sorted(found, key=lambda c: entries[c['id']].get('checked_utc', ''))
    for claim in queue:
        if claim.get('target_year') is not None and str(claim['target_year']).isdigit() and int(claim['target_year']) > dt.date.today().year:
            entries[claim['id']].update(status='too_early', score=None, what_happened='The forecast year has not arrived, so the outcome is not yet known.')
            continue
        if args.offline or not key or worked >= args.max_claims or time.monotonic() >= deadline - 110:
            break
        try:
            result = retrieve_assessment(claim, key)
            entries[claim['id']] = normalize(claim, result)
            worked += 1
            print('Assessed:', claim['id'], entries[claim['id']]['status'], flush=True)
        except (urllib.error.URLError, ValueError, KeyError, json.JSONDecodeError) as exc:
            print('Assessment failed; prior result kept:', claim['id'], str(exc)[:250], flush=True)
            # Do not repeatedly select the same failing record within a subsequent run.
            entries[claim['id']]['checked_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    OUTPUT.write_text(json.dumps(stored, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    build_word([entries[c['id']] for c in found])
    print(f'Radar 2: {len(found)} source-anchored predictions, {worked} assessed this run; Word: {REPORT}', flush=True)
    if not key and not args.offline:
        print('OPENAI_API_KEY missing: generated honest unassessed report; automatic outcome verification requires key.', flush=True)


if __name__ == '__main__':
    main()
