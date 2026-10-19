"""Radar 2: assess Radar 1's verified, source-anchored claims against later evidence.

Requires OPENAI_API_KEY for automatic research with web_search. No API key means
no invented assessments: existing reviewed results remain and Word is regenerated.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib import request, error

from docx import Document
from docx.shared import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'stuff' / 'WHAT_WAS_EXPECTED_VS_WHAT_HAPPENED.docx'
STORE = ROOT / 'outcome-assessments.json'
MODEL = os.getenv('OUTCOME_MODEL', 'gpt-4.1')


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default


def write_json(path, content):
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def single_sentence(text):
    text = re.sub(r'\s+', ' ', str(text or '')).strip()
    if not text:
        return ''
    # Keep one sentence, while retaining decimals and common acronyms in the text.
    return re.split(r'(?<=[.!?])\s+(?=[A-Z])', text, maxsplit=1)[0].rstrip('.!?') + '.'


def get_claims():
    """Use source-verified Radar 1 findings, not unverified shortlist titles."""
    records = read_json(ROOT / 'findings.json', {}).get('findings', [])
    claims = []
    for row in records:
        if not row.get('url') or not row.get('date') or not row.get('quality', {}).get('checks', {}).get('actual_future_analysis'):
            continue
        raw = (row.get('comparison') or {}).get('foresight_claim') or row.get('finding') or ''
        # Only statements with observable, future-oriented assertions can be assessed.
        sentences = re.split(r'(?<=[.!?;])\s+', re.sub(r'\s+', ' ', raw))
        for sentence in sentences:
            if len(sentence) < 35 or not re.search(r'\b(will|projected|forecast|expected|predicted|by 20\d\d|set to|likely to)\b', sentence, re.I):
                continue
            if len(sentence) > 650:  # avoid submitting undifferentiated paragraphs
                continue
            uid = hashlib.sha256((row['url'] + '|' + sentence).encode()).hexdigest()[:16]
            claims.append({'id': uid, 'title': row.get('title', ''), 'published': row['date'],
                           'claim': single_sentence(sentence), 'source_url': row['url'],
                           'source_document': row.get('full_text_url') or row['url']})
    # Deduplicate without changing stable IDs.
    return list({c['id']: c for c in claims}.values())


def responses_request(claim):
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        raise RuntimeError('OPENAI_API_KEY is not configured')
    today = dt.date.today().isoformat()
    prompt = f'''Today's date: {today}. Original research publication date: {claim['published']}.
Source: {claim['source_document']}
Forecast statement (from source-verified Radar 1): {claim['claim']}
Investigate whether the projected event or measured quantity happened by its stated deadline.
Search for date-appropriate INDEPENDENT primary evidence (Eurostat, ECB, OECD, EC statistical reports, official national statistics, other original records). Historic evidence from BEFORE 2026 is welcome; do not limit searches to recent news. Do not treat reporting a projection as proof it occurred. Cite only real URLs you found and checked. If the prediction is future-dated, too vague, or data is insufficient, return status 'unresolved' with score null; never turn lack of evidence into 50/100. For measurable forecasts compare predicted and observed values and units explicitly, using an appropriately documented error metric. If no precise quantitative comparison is possible, score only when outcome is clearly established and justify cautiously. 1 means wholly wrong; 100 exactly correct. Respond with ONLY a JSON object containing keys status ('assessed' or 'unresolved'), score (integer 1..100 or null), expected (ONE sentence), happened (ONE sentence, or 'Not yet established.'), explanation (short factual justification including numerical calculation where available), evidence (array of 1..4 objects with url, published_date, publisher, finding). The evidence must establish observed reality, not another forecast.'''
    body = {'model': MODEL, 'tools': [{'type': 'web_search'}],
            'input': [{'role': 'system', 'content': 'You are a careful retrospective forecasting auditor. Never invent evidence, scores, or sources. Return only valid JSON without code fences.'},
                      {'role': 'user', 'content': prompt}], 'max_output_tokens': 1700}
    req = request.Request('https://api.openai.com/v1/responses', data=json.dumps(body).encode(),
                          headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}, method='POST')
    with request.urlopen(req, timeout=115) as response:
        result = json.load(response)
    texts = [part.get('text', '') for item in result.get('output', []) for part in item.get('content', []) if part.get('type') == 'output_text']
    answer = '\n'.join(texts).strip()
    if answer.startswith('```'):
        answer = re.sub(r'^```(?:json)?\s*|\s*```$', '', answer)
    return json.loads(answer)


def validate(candidate, claim):
    if candidate.get('status') not in ('assessed', 'unresolved'):
        raise ValueError('Invalid status')
    evidence = candidate.get('evidence', [])
    valid_evidence = [e for e in evidence if isinstance(e, dict) and re.match(r'^https?://\S+$', str(e.get('url', ''))) and e.get('finding')]
    assessed = candidate['status'] == 'assessed'
    score = candidate.get('score')
    if assessed and (type(score) is not int or not 1 <= score <= 100 or not valid_evidence):
        raise ValueError('Assessed claims require a 1–100 score and traceable evidence')
    if not assessed:
        score = None
    if not candidate.get('expected') or not candidate.get('happened'):
        raise ValueError('Missing expected or happened sentence')
    return {'id': claim['id'], 'source_url': claim['source_url'], 'title': claim['title'],
            'published': claim['published'], 'original_claim': claim['claim'],
            'expected': single_sentence(candidate['expected']), 'happened': single_sentence(candidate['happened']),
            'status': candidate['status'], 'score': score,
            'explanation': str(candidate.get('explanation', ''))[:1200],
            'evidence': valid_evidence[:4], 'checked_at': dt.datetime.now(dt.timezone.utc).isoformat()}


def make_report(claims, stored):
    doc = Document()
    section = doc.sections[0]
    section.top_margin = section.bottom_margin = Inches(.75)
    doc.add_heading('What was expected vs. what happened', 0)
    doc.add_paragraph('Radar 2 | Assessed against independent evidence | Updated ' + dt.date.today().isoformat(), style='Subtitle')
    doc.add_paragraph('Scores: 1 = entirely incorrect; 100 = fully accurate. A missing score means the outcome cannot yet be responsibly established. Scores are evidence-based estimates, not objective guarantees.')
    entries = stored.get('assessments', {})
    if not claims:
        doc.add_paragraph('No source-verified, testable predictions are currently available from Radar 1.')
    for number, claim in enumerate(claims, 1):
        result = entries.get(claim['id'], {})
        doc.add_heading(f'{number}. {claim["title"]}', level=2)
        doc.add_paragraph('What was expected: ' + (result.get('expected') or claim['claim']))
        doc.add_paragraph('What happened: ' + (result.get('happened') or 'Not yet established.'))
        doc.add_paragraph('Accuracy: ' + (str(result['score']) + '/100' if result.get('status') == 'assessed' and type(result.get('score')) is int else 'Not yet assessable'))
        if result.get('explanation'):
            doc.add_paragraph('Basis: ' + result['explanation'])
        p = doc.add_paragraph('Original research: ' + claim['source_url'])
        p.style = 'Caption'
        for source in result.get('evidence', []):
            p = doc.add_paragraph(f"Outcome evidence ({source.get('published_date', 'date unknown')}; {source.get('publisher', 'source')}): {source['url']}")
            p.style = 'Caption'
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-claims', type=int, default=12, help='Maximum assessments per run to control API expense')
    parser.add_argument('--offline', action='store_true', help='Create Word from saved assessments without network calls')
    args = parser.parse_args()
    claims = get_claims()
    state = read_json(STORE, {'schema_version': 1, 'assessments': {}})
    state.setdefault('assessments', {})
    # Rotate through claims with oldest check first; rerun unresolved cases when new evidence may exist.
    ordered = sorted(claims, key=lambda c: state['assessments'].get(c['id'], {}).get('checked_at', ''))
    errors = 0
    if not args.offline and not os.environ.get('OPENAI_API_KEY'):
        raise SystemExit('OPENAI_API_KEY missing: refusing to invent outcome scores; use --offline to export existing assessments.')
    for claim in ([] if args.offline else ordered[:max(0, args.max_claims)]):
        try:
            result = validate(responses_request(claim), claim)
            state['assessments'][claim['id']] = result
            write_json(STORE, state)
            print(f"{claim['id']}: {result['status']} {result['score']}", flush=True)
        except (Exception) as exc:
            errors += 1
            print(f"{claim['id']}: assessment FAILED: {exc}", flush=True)
    write_json(STORE, state)
    make_report(claims, state)
    print(f'Report: {OUTPUT} | claims {len(claims)} | assessed {sum(x.get("status") == "assessed" for x in state["assessments"].values())} | errors {errors}')
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
