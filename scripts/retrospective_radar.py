"""Radar 2: source-grounded, clearly *informal* retrospective judgments.

Requires OPENAI_API_KEY for AI-assisted web research. Without it, preserves past reports
and marks newly found claims as unassessed; never manufactures outcomes/scores.
"""
import argparse
import http.client
import random
import socket
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
try:
    from forecast_screening import screen
except ModuleNotFoundError:
    from scripts.forecast_screening import screen

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
    """Every Scanner 1 research lead is eligible for Scanner 2 follow-up.

    A lead is a discovery record, not an authenticated prediction. Do not invent
    a forecast or treat a scenario as a prediction.
    """
    out = {}
    leads = read_json(ROOT / 'research-leads.json', {}).get('leads', [])
    for lead in leads:
        screening = screen(lead)
        url = concise(lead.get('url'))
        title = concise(lead.get('title'))
        if not url or not title:
            continue
        identifier = 'lead-' + hashlib.sha256(url.lower().rstrip('/').encode()).hexdigest()[:16]
        out[identifier] = {'id': identifier, 'expected': concise(lead.get('abstract')) or title,
                           'source_url': url, 'title': title, 'target_year': None,
                           'original_publication': lead.get('date') or 'Unknown',
                           'topic': lead.get('journal') or 'Foresight research',
                           'publisher': lead.get('publisher') or lead.get('journal') or '',
                           'lead_status': lead.get('status') or 'Discovered lead',
                           'is_lead': True, **screening}
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
    prompt = f'''Research route: {route_name}. Start with {route_sources}, then broaden as needed. Today: {now}.
Investigate this European foresight research LEAD and identify any subsequent real-world developments relevant to its themes. A title or abstract may describe a scenario, not a prediction. Do not invent a forecast.  Use WEB SEARCH for independently dated evidence AFTER the original publication. Search for both positive signals and counterevidence. Distinguish actual deployment or measured change from investment announcements, plans, ambitions, scenarios, and publicity. A future target date DOES NOT prevent assessment of current signals; it only prevents calling the final outcome realized prematurely.
Research lead title/abstract (NOT necessarily a prediction): {claim['expected']}
Original study: {claim['source_url']}
Original publication: {claim.get('original_publication')}
Target year: {claim.get('target_year')}

Return ONLY one JSON object with:
status: exactly one of realized, materializing, early_signals, no_clear_evidence, contradicted, too_early, insufficient_evidence.
what_expected: faithful concise description.
what_happened: concise observed developments, or clearly say none established.
evidence: list of objects with url, date, finding (dated independent sources; preferably two if feasible).
counterevidence: list of objects with url, date, finding when found.
reasoning: how evidence supports status, limitations and differences in baselines/time/geography.
watch_next: specific observable developments or measurable milestones to check.

Rules: 'realized' requires clear completed outcome with direct evidence; 'materializing' requires significant observed implementation; 'early_signals' requires credible observable indications, not mere publicity; 'contradicted' requires direct material counterevidence; 'no_clear_evidence' is only for a genuine search without convincing signals; 'too_early' means a judgment is premature AND there are no present signals sufficient to classify; 'insufficient_evidence' means research failed to establish reliable support. Future scenario narratives should not be treated as promised predictions. Never fabricate citations. Do not cite the original publication as the ONLY later evidence.'''
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


def free_follow_up(claim, timeout=12):
    """Look for subsequent scholarship in OpenAlex (free; not outcome verification).

    A discovered paper is a research follow-up, NOT evidence a scenario happened.
    """
    original = claim.get('original_publication', '')[:4]
    year = int(original) if original.isdigit() else 0
    if not year:
        return []
    title = concise(claim['title'])[:150]
    if not title:
        return []
    # A simpler OpenAlex query avoids invalid select/filter combinations on
    # heterogeneous records. Filter the dates locally, including future years.
    params = {'search': title, 'per_page': 5}
    email = os.getenv('MAILTO', '').strip() or os.getenv('OPENALEX_EMAIL', '').strip()
    if email and '@' in email:
        params['mailto'] = email
    api_key = os.getenv('OPENALEX_API_KEY', '').strip()
    if api_key:
        params['api_key'] = api_key
    def fetch_works(query_params):
        """Retry transport failures, but never retry authorization/quota failures blindly."""
        url = 'https://api.openalex.org/works?' + urllib.parse.urlencode(query_params)
        req = urllib.request.Request(url, headers={
            'User-Agent': f'WorldRadar/3.1 (mailto:{email})' if '@' in email else 'WorldRadar/3.1',
            'Accept': 'application/json', 'Accept-Encoding': 'identity'})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    # Read the entire response inside the protected retry block.
                    payload = response.read()
                data = json.loads(payload)
                if not isinstance(data, dict) or not isinstance(data.get('results'), list):
                    raise ValueError('OpenAlex returned an unexpected results payload')
                return data['results']
            except urllib.error.HTTPError as exc:
                # A 400 may be fixed by the simplified search below. A 429 may
                # indicate daily quota exhaustion: do not spend requests retrying.
                if exc.code not in (408, 500, 502, 503, 504):
                    raise
            except (http.client.IncompleteRead, http.client.RemoteDisconnected,
                    ConnectionResetError, BrokenPipeError, TimeoutError,
                    socket.timeout, urllib.error.URLError) as exc:
                print(f'OpenAlex transient transport error ({type(exc).__name__}); retry {attempt + 1}/4', flush=True)
            if attempt == 3:
                break
            time.sleep(min(8, 1.5 * (2 ** attempt)) + random.uniform(0, 0.3))
        raise ConnectionError('OpenAlex response incomplete or unavailable after 4 attempts')

    try:
        items = fetch_works(params)
    except urllib.error.HTTPError as exc:
        if exc.code != 400:
            raise
        fallback = {'search': ' '.join(title.split()[:8]), 'per_page': 5}
        if email and '@' in email:
            fallback['mailto'] = email
        if api_key:
            fallback['api_key'] = api_key
        items = fetch_works(fallback)
    stopwords = {'study','research','scenarios','europe','european','future','towards','policy','analysis','perspective','development','modelling'}
    def tokens(t):
        return {w for w in re.findall(r'[a-z]{4,}', t.lower()) if w not in stopwords}
    original_tokens = tokens(title)
    found = []
    for work in items:
        if (work.get('publication_year') or 0) <= year:
            continue
        wtitle = concise(work.get('title'))
        if not wtitle or wtitle.lower() == title.lower():
            continue
        terms = tokens(wtitle)
        overlap = len(terms & original_tokens)
        # Conservative relatedness: do not treat generic papers as follow-ups.
        if overlap < 3 or overlap / max(1, min(len(terms), len(original_tokens))) < .35:
            continue
        link = work.get('doi') or work.get('id')
        if not link or not link.startswith('https://') or link.rstrip('/') == claim['source_url'].rstrip('/'):
            continue
        found.append({'title': wtitle, 'url': link, 'year': work.get('publication_year'),
                      'note': 'Potentially related later publication; outcome not independently verified'})
        if len(found) >= 3:
            break
    return found


def single_sentence(value):
    value = concise(value)
    if not value:
        return ''
    # Avoid a multi-sentence narrative where the Word report requires one sentence.
    return re.split(r'(?<=[.!?])\s+(?=[A-Z])', value, maxsplit=1)[0].rstrip('.!?') + '.'


STATUS_LABELS = {
    'realized': 'Realized', 'materializing': 'Materializing',
    'early_signals': 'Early signals', 'no_clear_evidence': 'No clear evidence',
    'contradicted': 'Contradicted', 'too_early': 'Too early to tell',
    'insufficient_evidence': 'Insufficient evidence',
    'not_yet_assessed': 'Not yet investigated',
}


def clean_evidence(claim, values):
    sources = []
    for e in values if isinstance(values, list) else []:
        if not isinstance(e, dict):
            continue
        url = str(e.get('url', '')).strip()
        if (not re.match(r'^https?://[^\s/]+', url)
                or url.rstrip('/') == claim['source_url'].rstrip('/')
                or not e.get('finding') or not e.get('date')):
            continue
        sources.append({'url': url, 'date': str(e['date'])[:40], 'finding': concise(e['finding'])[:500]})
    return sources[:8]


def normalize(claim, result):
    status = result.get('status', 'insufficient_evidence')
    if status not in STATUS_LABELS or status == 'not_yet_assessed':
        status = 'insufficient_evidence'
    evidence = clean_evidence(claim, result.get('evidence'))
    counter = clean_evidence(claim, result.get('counterevidence'))
    # No definite conclusion without independently dated supporting evidence.
    if status in ('realized', 'materializing', 'early_signals', 'contradicted') and not evidence and not counter:
        status = 'insufficient_evidence'
    target = claim.get('target_year')
    if target and int(target) > dt.date.today().year and status == 'realized':
        # Only allow realization if the research actually demonstrates early completion.
        if not evidence:
            status = 'insufficient_evidence'
    return {**claim, 'what_expected': concise(result.get('what_expected') or claim['expected']),
            'what_happened': concise(result.get('what_happened') or 'No independently established observations yet.'),
            'status': status, 'evidence': evidence, 'counterevidence': counter,
            'reasoning': concise(result.get('reasoning', '')),
            'watch_next': concise(result.get('watch_next', '')),
            'checked_utc': dt.datetime.now(dt.timezone.utc).isoformat()}


def build_word(entries):
    """Publish an honest decision-oriented report, NOT a 90-page bibliography."""
    from collections import Counter
    from docx import Document
    from docx.shared import Inches, Pt
    from outlook_summary import create
    outlook = create(entries)
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = sec.bottom_margin = Inches(.8)
    doc.styles['Normal'].font.size = Pt(10)
    doc.add_heading('What was expected — what actually happened?', 0)
    doc.add_paragraph('EU foresight | Evidence review | ' + dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))
    doc.add_paragraph('Scope: indexed sources are research leads, not necessarily predictions. No title similarity or later scholarly publication alone counts as evidence that an outcome occurred.')
    screening = Counter(e.get('screening_status', 'unscreened') for e in entries)
    verified = [e for e in entries if e.get('status') in ('realized','materializing','early_signals','contradicted') and (e.get('evidence') or e.get('counterevidence'))]
    candidates = [e for e in entries if e.get('screening_status') == 'candidate_needs_validation']
    doc.add_heading('Research audit', 1)
    doc.add_paragraph(f"Scanner 1 leads: {len(entries)} | Forecast candidates requiring validation: {len(candidates)} | Full text needed: {screening['full_text_required']} | No testable prediction in metadata: {screening['no_testable_prediction_in_metadata']} | Evidence-backed assessments: {len(verified)}.")
    if not verified:
        doc.add_paragraph('No verified Expected → Happened comparisons are available from the current evidence. The report does not manufacture them or equate bibliographic searches with observed outcomes.')
    else:
        doc.add_heading('Expected → Happened | independently sourced', 1)
        for e in verified[:30]:
            doc.add_heading(concise(e.get('title'))[:140], 2)
            doc.add_paragraph('Expected: ' + concise(e.get('what_expected'))[:600])
            doc.add_paragraph('Happened: ' + concise(e.get('what_happened'))[:600])
            doc.add_paragraph('Verdict: ' + STATUS_LABELS.get(e.get('status'), 'Unverified'))
            for source in (e.get('evidence') or [])[:3] + (e.get('counterevidence') or [])[:2]:
                doc.add_paragraph('Evidence (' + concise(source.get('date')) + '): ' + concise(source.get('finding'))[:260] + ' — ' + concise(source.get('url')))
    observations = read_json(ROOT / 'outcome-observations.json', {}).get('observations', [])
    if observations:
        doc.add_heading('Observed developments | primary sources', 1)
        doc.add_paragraph('These are documented real-world observations relevant to Scanner 1 topics. A policy target is not a scientific prediction, and progress toward a future target is not proof of future success.')
        for item in observations:
            doc.add_heading(concise(item.get('topic')), 2)
            matching = next((e for e in entries if item.get('original_lead_title_contains', '').lower() in e.get('title', '').lower()), None)
            if matching:
                doc.add_paragraph('Original monitored research: ' + concise(matching.get('title')) + ' — ' + concise(matching.get('source_url')))
            doc.add_paragraph('Expected / target: ' + concise(item.get('expected')))
            doc.add_paragraph('Actually observed: ' + concise(item.get('happened')))
            doc.add_paragraph('Assessment: ' + concise(item.get('verdict')))
            for src in item.get('sources', []):
                doc.add_paragraph('Source (' + concise(src.get('date')) + '): ' + concise(src.get('finding')) + ' — ' + concise(src.get('url')))
    doc.add_heading('Original-source forecast candidates — not verified', 1)
    doc.add_paragraph('These phrases are copied from indexed abstracts, not independently validated against full original publications. They are NOT outcome verdicts. Full-text review and later independent observations are required.')
    for e in candidates[:30]:
        doc.add_heading(concise(e.get('title'))[:130], 2)
        doc.add_paragraph('Candidate original wording: ' + concise(e.get('candidate_excerpt'))[:650])
        doc.add_paragraph('Original source: ' + concise(e.get('source_url')))
        doc.add_paragraph('Observed outcome: Not established. Next: verify full source and locate an official dated measurement or evaluation.')
    if len(candidates)>30:
        doc.add_paragraph(f'{len(candidates)-30} additional candidates are saved in retrospective-results.json for separate validation.')
    doc.add_heading('What is needed for real retrospective findings', 1)
    doc.add_paragraph('For each candidate: original document passage; publication date; quantified or observable prediction, geography and target date; then independent dated outcome evidence with direct source links and contrary evidence when available. Unverified items must remain unverified.')
    doc.add_paragraph('The entire collection remains available in research-leads.json and retrospective-results.json. Unverified entries are intentionally excluded from this Word report rather than expanded into hundreds of empty verdicts.')
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(REPORT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--minutes', type=float, default=18)
    ap.add_argument('--max-claims', type=int, default=515)
    ap.add_argument('--offline', action='store_true')
    ap.add_argument('--provider', choices=['free', 'openai'], default='free')
    args = ap.parse_args()
    stored = read_json(OUTPUT, {'entries': {}})
    entries = stored.setdefault('entries', {})
    found = claims()
    # Legacy numeric scores are not evidence of realization; migrate safely.
    for entry in entries.values():
        entry.pop('score', None)
        if entry.get('status') == 'assessed':
            entry['status'] = 'not_yet_assessed'
            entry['what_happened'] = 'Legacy numerical judgment removed; awaiting evidence-based review.'
            entry['reasoning'] = ''
        entry.setdefault('counterevidence', [])
    key = os.getenv('OPENAI_API_KEY', '')
    if args.provider == 'openai' and not args.offline and not key:
        raise SystemExit('OpenAI provider explicitly selected but OPENAI_API_KEY is missing.')
    print(f'Radar 2 start: {len(found)} research leads; provider={args.provider}; OpenAlex API key configured={bool(os.getenv("OPENALEX_API_KEY", "").strip())}', flush=True)
    deadline = time.monotonic() + max(0, args.minutes) * 60
    worked = 0
    completed = 0
    failed = 0
    throttled = False
    for claim in found:
        if claim['id'] not in entries:
            entries[claim['id']] = {**claim, 'what_expected': single_sentence(claim['expected']),
                                   'what_happened': 'No independently verified outcome yet.',
                                   'status': 'not_yet_assessed', 'evidence': [], 'counterevidence': []}
    # Keep the JSON limited to current candidates: legacy/orphaned entries previously
    # made the stored report appear more complete than its live extraction pipeline.
    active_ids = {claim['id'] for claim in found}
    entries = {key: value for key, value in entries.items() if key in active_ids}
    stored['entries'] = entries
    for claim in found:
        entries[claim['id']].update({k: claim[k] for k in ('screening_status','screening_reason','candidate_excerpt','candidate_year')})
    # First cover unassessed claims; then revisit old/weak assessments.
    # Tie-breakers rotate fairly across source organisations and forecast years,
    # rather than allowing one publisher to fill the entire time budget.
    def priority(c):
        e = entries[c['id']]
        status = e.get('status')
        tier = 0 if status in ('not_yet_assessed', 'insufficient_evidence', 'too_early', 'no_clear_evidence') else 1
        return (tier, e.get('checked_utc', ''), c['id'])
    ordered = sorted((c for c in found if c.get('screening_status') == 'candidate_needs_validation'), key=priority) if args.provider == 'free' else sorted(found, key=priority)
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
        if args.offline or worked >= args.max_claims or time.monotonic() >= deadline - 8:
            break
        try:
            previous = entries[claim['id']]
            route = route_for(previous)
            print('Research:', args.provider, claim['id'], flush=True)
            # Increment even on errors so next scan explores different sources.
            previous['research_attempts'] = int(previous.get('research_attempts', 0)) + 1
            if args.provider == 'free':
                related = free_follow_up(claim)
                previous['follow_up_publications'] = related
                previous['bibliography_checked_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
                previous.pop('last_error', None)
                previous['last_route'] = 'OpenAlex later-publication discovery'
                # Later papers do not constitute an outcome check.
                if previous.get('status') in ('not_yet_assessed', 'insufficient_evidence'):
                    previous['status'] = 'not_yet_assessed'
                previous['what_happened'] = 'No independently verified outcome. Bibliography is stored separately.'
                worked += 1
                print('Checked:', claim['id'], 'follow-up publications:', len(related), flush=True)
                # Successful free-provider results must also reach the checkpoint block.
                if worked % 20 == 0:
                    OUTPUT.write_text(json.dumps(stored, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
                    print(f'Progress: {worked}/{min(len(found), args.max_claims)} attempts, {failed} failed', flush=True)
                # Avoid exhausting the account's requests-per-second allowance.
                time.sleep(0.45)
                continue
            result = retrieve_assessment(claim, key, route=route)
            assessed = normalize(claim, result)
            assessed['research_attempts'] = previous['research_attempts']
            assessed['last_route'] = EVIDENCE_ROUTES[route][0]
            # Do not replace a supported previous outcome with an unsupported one.
            if previous.get('status') in ('realized', 'materializing', 'early_signals', 'contradicted') and assessed['status'] == 'insufficient_evidence':
                previous['checked_utc'] = assessed['checked_utc']
                previous['last_route'] = assessed['last_route']
            else:
                entries[claim['id']] = assessed
            worked += 1
            if entries[claim['id']]['status'] in ('realized', 'materializing', 'early_signals', 'contradicted'):
                completed += 1
            print('Assessed:', claim['id'], entries[claim['id']]['status'], flush=True)
        except (urllib.error.URLError, ValueError, KeyError, json.JSONDecodeError, TimeoutError, ConnectionError, http.client.IncompleteRead, http.client.RemoteDisconnected, ConnectionResetError) as exc:
            print('Assessment failed; prior result kept:', claim['id'], str(exc)[:250], flush=True)
            # Do not repeatedly select the same failing record within a subsequent run.
            entries[claim['id']]['last_attempt_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
            entries[claim['id']]['last_route'] = ('OpenAlex later-publication discovery' if args.provider == 'free' else EVIDENCE_ROUTES[route][0])
            failed += 1
            entries[claim['id']]['last_error'] = str(exc)[:250]
            worked += 1
            # Checkpoint immediately on failure, even when halting on rate limits.
            OUTPUT.write_text(json.dumps(stored, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            if isinstance(exc, urllib.error.HTTPError) and exc.code == 429:
                throttled = True
                print('OPENALEX RATE LIMIT: stopping early, preserving results; check account quota and rerun after reset.', flush=True)
                break
        if worked and worked % 20 == 0:
            OUTPUT.write_text(json.dumps(stored, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            print(f'Progress: {worked}/{min(len(found), args.max_claims)} attempts, {failed} failed', flush=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(stored, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    build_word([entries[c['id']] for c in found])
    print(f'Radar 2: {len(found)} source records, {worked} bibliography attempts, {failed} failures, {sum(bool(x.get("evidence") or x.get("counterevidence")) for x in entries.values())} entries with dated evidence; Word: {REPORT}', flush=True)
    summary_file = os.getenv('GITHUB_STEP_SUMMARY')
    if summary_file:
        with open(summary_file, 'a', encoding='utf-8') as summary:
            summary.write(f'## Radar 2 follow-up\n\n- Leads: {len(found)}\n- Attempts this run: {worked}\n- Failed this run: {failed}\n- Successful checks saved: {sum(bool(x.get("checked_utc")) for x in entries.values())}\n- OpenAlex throttled: {throttled}\n- Word report generated: {REPORT}\n')
    if not args.offline and (worked == 0 or worked == failed) and found:
        raise SystemExit('RADAR 2 FAILED: no successful research checks; Word report preserved. Review API key/quota logs.')


if __name__ == '__main__':
    main()
