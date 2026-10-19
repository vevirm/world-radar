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
import urllib.parse
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
    """Only predictions extracted from Radar 1's verified full-text studies.

    The old implementation also read future-ideas.json, which is an unverified
    proposal list and must never be represented as verified historical research.
    """
    out = {}
    for finding in read_json(ROOT / 'findings.json', {}).get('findings', []):
        quality = finding.get('quality', {}).get('checks', {})
        if not quality.get('actual_future_analysis'):
            continue
        raw = concise(finding.get('comparison', {}).get('foresight_claim') or finding.get('finding'))
        source = finding.get('full_text_url') or finding.get('url')
        if not raw or not source or not finding.get('date'):
            continue
        for text in re.split(r'(?<=[.!?;])\s+', raw):
            text = concise(text)
            if len(text) < 35 or len(text) > 650:
                continue
            if not re.search(r'\b(projected|predicted|forecast|expected|will|would|by 20\d\d|likely to)\b', text, re.I):
                continue
            target = re.search(r'\b(?:by|in|before|until|around|through)\s+(20\d{2})\b', text, re.I)
            year = int(target.group(1)) if target else None
            key = 'finding-' + hashlib.sha256((source + text).encode()).hexdigest()[:16]
            out[key] = {'id': key, 'expected': text, 'source_url': source,
                        'title': finding.get('title', ''), 'target_year': year,
                        'original_publication': finding['date'], 'topic': finding.get('topic', ''), 'publisher': finding.get('source', '')}
    return list(out.values())


def response_text(payload):
    chunks = []
    for output in payload.get('output', []):
        if output.get('type') == 'message':
            for content in output.get('content', []):
                if content.get('type') == 'output_text':
                    chunks.append(content.get('text', ''))
    return '\n'.join(chunks)


# Different evidence paths are deliberately explored on successive runs.
# These are search *directions*, not claims that a given site contains the answer.
EVIDENCE_ROUTES = (
    ('EU data', 'Eurostat, data.europa.eu, ECB Statistical Data Warehouse, EU agencies'),
    ('Member-state data', 'national statistical offices, ministries, central banks, national regulators'),
    ('Global datasets', 'OECD Data, World Bank DataBank, IMF World Economic Outlook, UNdata'),
    ('Peer-reviewed follow-up', 'Crossref, OpenAlex, Google Scholar, scholarly longitudinal studies and replication papers'),
    ('EU policy evaluations', 'European Commission ex-post evaluations, JRC studies, European Court of Auditors'),
    ('Sector and regulator evidence', 'sector regulators, energy agencies, EEA, Eurofound, Cedefop, audited industry series'),
    ('Policy and law', 'EUR-Lex, parliamentary records, official implementation and enforcement reports'),
    ('Historical archives', 'Wayback archival material, historical annual reports, archived time-series releases'),
    ('Energy and climate', 'European Environment Agency, IEA, ENTSO-E, Copernicus and emissions inventories'),
    ('Labour and demography', 'Eurostat labour-force surveys, ILOSTAT, UN population data, national censuses'),
    ('Economy and finance', 'ECB, OECD Economic Outlook, Eurostat national accounts, national central banks'),
    ('Technology and digital', 'DESI/Digital Decade monitoring, OECD ICT statistics, patent and adoption datasets'),
    ('Health and society', 'WHO Europe, ECDC, OECD Health at a Glance, national health authorities'),
    ('Agriculture and biodiversity', 'FAOSTAT, EEA biodiversity reports, Copernicus land monitoring, Eurostat agriculture'),
    ('Transport and mobility', 'Eurostat transport statistics, ACEA, national registration agencies, EU transport observatories'),
    ('Contradictory evidence', 'independent counter-evaluations, methodological critiques, rival time series and uncertainty ranges'),
)

# Per-claim research alternates routes across runs. These are starting points,
# not a closed whitelist: the agent is told to search beyond them if necessary.


def route_for(entry):
    """Cycle evidence sources for each claim without repeatedly trying one route."""
    attempts = max(0, int(entry.get('research_attempts', 0)))
    # A stable claim-specific offset spreads source categories across a single run.
    offset = int(hashlib.sha256(str(entry.get('id', '')).encode()).hexdigest()[:8], 16)
    return (offset + attempts) % len(EVIDENCE_ROUTES)


def retrieve_assessment(claim, key, route=0):
    now = dt.date.today().isoformat()
    route_name, route_sources = EVIDENCE_ROUTES[route % len(EVIDENCE_ROUTES)]
    prompt = f'''Evidence discovery route: {route_name}. Start with {route_sources}. If they do not cover the claim, widen to other independently dated primary evidence rather than returning a weak verdict. Seek at least two independent evidence sources where feasible; don't fabricate a second citation. Cross-check conflicting evidence and identify incompatible geographies, units, baselines, or definitions. Rotate search terms across exact quantities, topic synonyms, locations, time periods, and actual observed series. For projected percentages or amounts, find real comparable values and distinguish absolute vs relative changes. Do not infer that a forecast was correct just because later articles repeat it.

Today: {now}. Investigate this historical European forecast using WEB SEARCH and reliable, independently dated evidence (Eurostat, ECB, OECD, national statistics, institutional publications first). Use outcome evidence for the ORIGINAL target time, including years before 2026; don't limit yourself to recent news. Do not treat re-statements of the forecast, predictions, headlines alone, or unverified secondary guesses as outcomes. Do not fabricate citations.\n\nOriginal claim: {claim['expected']}\nOriginal research: {claim['source_url']}\nTarget year if known: {claim.get('target_year')}\n\nSearch for the exact target year and outcome, not just current headlines. Use the original publication date to establish what was actually predicted before the event. Prefer dated independent statistical series and primary reporting; cite what was observed, with its year. Return ONLY a JSON object with fields: status (assessed / too_early / insufficient_evidence), what_expected (ONE sentence faithful to the original; don't invent specificity), what_happened (ONE sentence summarizing demonstrable outcome, or clearly saying not yet known), score (integer 1-100 ONLY for assessed, otherwise null), evidence (array of objects each with url, date, finding; at least one trustworthy URL for assessed), reasoning (brief). Score is an informal rough judgment of foresight accuracy, NOT a rigorous numeric metric. 1 means completely wrong, 100 means exceptionally accurate. Do not score an uncompleted forecast or evidence too thin to compare. Do not use the original forecast source as sole outcome evidence. If ambiguous or non-testable, return insufficient_evidence.''' 
    request = {'model': MODEL, 'tools': [{'type': 'web_search'}],
               'input': prompt, 'max_output_tokens': 1800}
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


def single_sentence(value):
    value = concise(value)
    if not value:
        return ''
    # Avoid a multi-sentence narrative where the Word report requires one sentence.
    return re.split(r'(?<=[.!?])\s+(?=[A-Z])', value, maxsplit=1)[0].rstrip('.!?') + '.'


def normalize(claim, result):
    status = result.get('status', 'insufficient_evidence')
    if status not in ('assessed', 'too_early', 'insufficient_evidence'):
        status = 'insufficient_evidence'
    evidence = []
    for e in result.get('evidence', []):
        if not isinstance(e, dict):
            continue
        url = str(e.get('url', '')).strip()
        if not re.match(r'^https://[^\s/]+/', url) or url.rstrip('/') == claim['source_url'].rstrip('/'):
            continue
        if not e.get('finding') or not e.get('date'):
            continue
        evidence.append({'url': url, 'date': str(e['date'])[:40],
                         'finding': concise(e['finding'])[:500]})
    score = result.get('score')
    target = claim.get('target_year')
    if target is not None and target > dt.date.today().year:
        status = 'too_early'
    if not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 100 or not evidence:
        status = 'insufficient_evidence' if status == 'assessed' else status
    if status != 'assessed':
        score = None
        result['what_happened'] = ('The forecast horizon has not been reached.' if status == 'too_early'
                                   else 'The observed outcome is not independently established.')
    return {**claim, 'what_expected': single_sentence(result.get('what_expected') or claim['expected']),
            'what_happened': single_sentence(result.get('what_happened') or 'No independently established outcome yet.'),
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
        doc.add_paragraph('What was expected: ' + single_sentence(item.get('what_expected') or item['expected']))
        doc.add_paragraph('What happened: ' + single_sentence(item.get('what_happened') or 'Not yet assessed.'))
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
    completed = 0
    for claim in found:
        if claim['id'] not in entries:
            entries[claim['id']] = {**claim, 'what_expected': single_sentence(claim['expected']),
                                   'what_happened': 'No independently verified outcome yet.',
                                   'score': None, 'status': 'not_yet_assessed', 'evidence': []}
    # First cover unassessed claims; then revisit old/weak assessments.
    # Tie-breakers rotate fairly across source organisations and forecast years,
    # rather than allowing one publisher to fill the entire time budget.
    def priority(c):
        e = entries[c['id']]
        status = e.get('status')
        tier = 0 if status in ('not_yet_assessed', 'insufficient_evidence') else 1
        return (tier, e.get('checked_utc', ''), c['id'])
    ordered = sorted(found, key=priority)
    groups = {}
    for claim in ordered:
        host = urllib.parse.urlparse(claim['source_url']).hostname or ''
        groups.setdefault(host, []).append(claim)
    queue = []
    while any(groups.values()):
        for host in sorted(groups):
            if groups[host]:
                queue.append(groups[host].pop(0))
    for claim in queue:
        if claim.get('target_year') is not None and str(claim['target_year']).isdigit() and int(claim['target_year']) > dt.date.today().year:
            entries[claim['id']].update(status='too_early', score=None, what_happened='The forecast year has not arrived, so the outcome is not yet known.')
            continue
        if args.offline or not key or worked >= args.max_claims or time.monotonic() >= deadline - 110:
            break
        try:
            previous = entries[claim['id']]
            route = route_for(previous)
            print('Research route:', EVIDENCE_ROUTES[route][0], 'for', claim['id'], flush=True)
            # Increment even on errors so next scan explores different sources.
            previous['research_attempts'] = int(previous.get('research_attempts', 0)) + 1
            result = retrieve_assessment(claim, key, route=route)
            assessed = normalize(claim, result)
            assessed['research_attempts'] = previous['research_attempts']
            assessed['last_route'] = EVIDENCE_ROUTES[route][0]
            # Do not replace a supported previous outcome with an unsupported one.
            if previous.get('status') == 'assessed' and assessed['status'] != 'assessed':
                previous['checked_utc'] = assessed['checked_utc']
                previous['last_route'] = assessed['last_route']
            else:
                entries[claim['id']] = assessed
            worked += 1
            if entries[claim['id']]['status'] == 'assessed':
                completed += 1
            print('Assessed:', claim['id'], entries[claim['id']]['status'], flush=True)
        except (urllib.error.URLError, ValueError, KeyError, json.JSONDecodeError, TimeoutError) as exc:
            print('Assessment failed; prior result kept:', claim['id'], str(exc)[:250], flush=True)
            # Do not repeatedly select the same failing record within a subsequent run.
            entries[claim['id']]['checked_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
            entries[claim['id']]['last_route'] = EVIDENCE_ROUTES[route][0]
            worked += 1
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(stored, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    build_word([entries[c['id']] for c in found])
    print(f'Radar 2: {len(found)} source-anchored predictions, {worked} research attempts, {completed} scored outcomes this run; Word: {REPORT}', flush=True)
    if not key and not args.offline:
        print('OPENAI_API_KEY missing: generated honest unassessed report; automatic outcome verification requires key.', flush=True)


if __name__ == '__main__':
    main()
