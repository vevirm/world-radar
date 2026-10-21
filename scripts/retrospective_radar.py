"""Radar 2: source-grounded, clearly *informal* retrospective judgments.

Uses OpenAlex scholarly metadata by default (no OpenAI dependency). Compares
later studies with the original research and labels all conclusions provisional.
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
try:
    from openalex_comparison import (request_works, related, local_catalogue, assess, query_for,
        SavedLiteratureIndex, field_updates, merge_publications)
except ModuleNotFoundError:
    from scripts.openalex_comparison import (request_works, related, local_catalogue, assess, query_for,
        SavedLiteratureIndex, field_updates, merge_publications)

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
    return re.sub(r'\s+', ' ', str(sentence if sentence is not None else '')).strip()


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


def build_word(entries, run=None):
    """Build the short hindsight digest and separate, machine-readable stories.

    Detailed research logs remain in existing JSON and the review queue, never
    in the human-facing Word digest.
    """
    try:
        from scripts.outlook_summary import create
        from scripts.outcome_verification import assemble, write_queue
        from scripts.storybook import write_stories, write_word
    except ModuleNotFoundError:
        # python scripts/retrospective_radar.py does not put repo root on sys.path.
        from outlook_summary import create
        from outcome_verification import assemble, write_queue
        from storybook import write_stories, write_word
    create(entries)
    reviewed, _rejected = assemble(entries)
    write_queue(entries)
    observations = read_json(ROOT / 'outcome-observations.json', {}).get('observations', [])
    payload = write_stories(entries, reviewed, observations, path=ROOT / 'hindsight-stories.json')
    write_word(payload, REPORT, run=run)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--minutes', type=float, default=25,
                    help='Maximum wall-clock minutes for research in this run.')
    ap.add_argument('--max-claims', type=int, default=0,
                    help='Optional per-run entry limit; 0 (default) means no count cap.')
    ap.add_argument('--offline', action='store_true')
    ap.add_argument('--provider', choices=['auto', 'openalex', 'catalogue', 'free', 'openai', 'evidence'], default='auto')
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
    key = os.getenv('OPENAI_API_KEY', '').strip()
    if args.provider == 'auto':
        args.provider = 'catalogue' if args.offline else 'openalex'
    if args.provider == 'free':
        args.provider = 'openalex'  # backwards-compatible flag, now meaningful comparisons
    if args.offline and args.provider == 'openalex':
        args.provider = 'catalogue'
    if args.provider == 'openai' and not args.offline and not key:
        raise SystemExit('OpenAI provider explicitly selected but OPENAI_API_KEY is missing.')
    print(f'Radar 2 start: {len(found)} research leads; provider={args.provider}; OpenAlex API key configured={bool(os.getenv("OPENALEX_API_KEY", "").strip())}', flush=True)
    started = time.monotonic()
    deadline = started + max(0, args.minutes) * 60
    print(f'Research budget: {args.minutes:g} minutes, ' +
          ('no entry-count cap' if args.max_claims <= 0 else f'entry-count cap {args.max_claims}'), flush=True)
    worked = 0
    completed = 0
    failed = 0
    throttled = False
    successful_evidence = 0
    literature_comparisons = 0
    literature_studies_found = 0
    saved_leads = read_json(ROOT / "research-leads.json", {}).get("leads", [])
    # Every run makes use of *all already indexed later literature*, rather
    # than only the 12-45 papers whose live API requests fit this run's clock.
    saved_index = SavedLiteratureIndex(saved_leads) if args.provider in ('openalex', 'catalogue') else None
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
    # Fill the separate, weaker "newer work on the same field" trail for the
    # ENTIRE corpus from real saved papers. It is not an observed outcome.
    catalogue_field_enriched = 0
    if saved_index is not None:
        for claim in found:
            previous = entries[claim['id']]
            current = previous.get('field_developments') or []
            new = saved_index.find(claim)
            merged = merge_publications(current, new, max_items=6)
            previous['field_developments'] = merged
            if new and not current:
                catalogue_field_enriched += 1
        print(f'Saved-catalogue context: {catalogue_field_enriched} additional leads with newer related field literature.', flush=True)
    # Prioritize real forecast candidates before general EU-related scholarship.
    # Rotate on the number of *literature checks*, not failed OpenAI requests.
    def priority(c):
        e = entries[c['id']]
        return (int(e.get('literature_live_attempts') or 0) if args.provider == 'openalex' else int(e.get('literature_attempts') or 0),
                0 if c.get('screening_status') == 'candidate_needs_validation' else 1,
                e.get('literature_assessed_utc', ''), c['id'])
    ordered = [] if args.provider == 'evidence' else sorted(found, key=priority)
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
        # Time and provider quotas decide throughput; no arbitrary 55-entry stop.
        if (args.max_claims > 0 and worked >= args.max_claims) or time.monotonic() >= deadline - 8:
            break
        previous = entries[claim['id']]
        try:
            route = route_for(previous)
            print('Research:', args.provider, claim['id'], flush=True)
            previous['research_attempts'] = int(previous.get('research_attempts') or 0) + 1
            if args.provider in ('openalex', 'catalogue'):
                previous['literature_attempts'] = int(previous.get('literature_attempts') or 0) + 1
                if args.provider == 'openalex':
                    previous['literature_live_attempts'] = int(previous.get('literature_live_attempts') or 0) + 1
                if args.provider == 'catalogue':
                    studies = local_catalogue(claim, saved_leads)
                    live_context = []
                    research_mode = 'existing_scanner_catalogue (saved OpenAlex/Crossref records)'
                else:
                    search_round = previous['literature_live_attempts'] - 1
                    query = query_for(claim, search_round)
                    if len(query) < 4:
                        raise ValueError('Not enough substantive terms for a meaningful OpenAlex query')
                    since = int(claim.get('original_publication','')[:4])
                    works = request_works(query, since)
                    studies = related(claim, works)
                    live_context = field_updates(claim, works)
                    # A less title-dependent follow-up search, at most one
                    # extra call when the first search returns almost nothing.
                    # Failed fallback does not destroy a successful first query.
                    if len({item["url"] for item in studies + live_context}) < 2 and time.monotonic() < deadline - 40:
                        alternate = query_for(claim, search_round + 1)
                        if alternate and alternate != query:
                            try:
                                alternate_works = request_works(alternate, since)
                                studies = merge_publications(studies, related(claim, alternate_works), max_items=6)
                                live_context = merge_publications(live_context, field_updates(claim, alternate_works), max_items=5)
                            except (ConnectionError, urllib.error.URLError, ValueError, TimeoutError) as retry_error:
                                print('Alternative search unavailable:', str(retry_error)[:120], flush=True)
                    # A saved local paper is labelled differently from a live result.
                    if len(studies) < 2:
                        studies = merge_publications(studies, local_catalogue(claim, saved_leads), max_items=6)
                    research_mode = 'openalex_live + saved catalog (when needed)'
                # Keep previous successful links instead of resetting them
                # after an unsuccessful / different query on a later run.
                studies = merge_publications(previous.get('follow_up_publications'), studies, max_items=8)
                previous_context = previous.get('field_developments') or []
                context = merge_publications(previous_context, live_context, max_items=6)
                new_assessment = assess(claim, studies, research_mode)
                new_assessment['field_developments'] = context
                previous.update(new_assessment)
                previous.pop('last_error', None)
                previous['bibliography_checked_utc'] = previous['literature_assessed_utc']
                worked += 1
                literature_comparisons += 1
                literature_studies_found += len(studies)
                print('Compared:', claim['id'], 'later studies:', len(studies),
                      'abstract-result snippets:', sum(bool(x.get('finding_from_abstract')) for x in studies), flush=True)
                if args.provider == 'openalex':
                    time.sleep(.3)
            elif args.provider == 'openai':
                result = retrieve_assessment(claim, key, route=route)
                assessed = normalize(claim, result)
                if assessed.get('evidence') or assessed.get('counterevidence'):
                    successful_evidence += 1
                assessed['research_attempts'] = previous['research_attempts']
                assessed['last_route'] = EVIDENCE_ROUTES[route][0]
                if previous.get('literature_assessed_utc'):
                    for k in ('literature_assessed_utc', 'literature_search_mode', 'literature_signal',
                              'what_expected_literature', 'what_happened_literature', 'tentative_assessment',
                              'comparison_limits', 'eu_attribution', 'follow_up_publications', 'literature_attempts', 'literature_live_attempts', 'tentative_direction', 'topic_cluster', 'field_developments'):
                        if k in previous:
                            assessed[k] = previous[k]
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
            entries[claim['id']]['last_attempt_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
            entries[claim['id']]['last_route'] = ('OpenAlex similar-study comparison' if args.provider in ('openalex', 'catalogue') else EVIDENCE_ROUTES[route][0])
            failed += 1
            entries[claim['id']]['last_error'] = str(exc)[:250]
            worked += 1
            OUTPUT.write_text(json.dumps(stored, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            if isinstance(exc, urllib.error.HTTPError) and exc.code in (401, 403, 429):
                throttled = True
                print('OpenAlex rejected credentials / quota: stopping so future runs can retry.', flush=True)
                break
        if worked and worked % 10 == 0:
            OUTPUT.write_text(json.dumps(stored, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            target = len(queue) if args.max_claims <= 0 else min(len(queue), args.max_claims)
            print(f'Progress: {worked}/{target} attempts, {failed} failed; ' +
                  f'{max(0, int(deadline - time.monotonic()))}s left in research budget', flush=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(stored, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    time_spent = round(time.monotonic() - started, 1)
    stop_reason = ('api_quota_or_credentials' if throttled else
                   'claim_limit' if args.max_claims > 0 and worked >= args.max_claims else
                   'research_time_budget' if worked < len(queue) else 'all_available_leads_checked')
    print(f'Research finished: {worked}/{len(queue)} entries attempted in {time_spent:.1f}s; ' +
          f'reason={stop_reason}. Generating Word and audit now.', flush=True)
    run = {'provider': args.provider, 'attempts': worked, 'failed': failed,
           'research_budget_minutes': args.minutes,
           'research_elapsed_seconds': time_spent,
           'stop_reason': stop_reason,
           'new_evidence_assessments': successful_evidence,
           'literature_comparisons': literature_comparisons,
           'literature_studies_found': literature_studies_found,
           'catalogue_field_enriched_this_run': catalogue_field_enriched,
           'field_context_count_total': sum(bool(e.get('field_developments')) for e in entries.values()),
           'note': ('OpenAlex similar-study comparisons; academic abstracts are provisional, not verified outcomes.'
                    if args.provider == 'openalex' else
                    'Compared genuine existing scholarly records offline; no new external request.'
                    if args.provider == 'catalogue' else
                    'No external research performed.' if args.provider == 'evidence' else
                    'AI-assisted research; citations require original-source checking.')}
    build_word([entries[c['id']] for c in found], run=run)
    try:
        from scripts.outcome_verification import assemble
    except ModuleNotFoundError:
        from outcome_verification import assemble
    valid_cases, invalid_cases = assemble([entries[c['id']] for c in found])
    audit = {'research_leads': len(found), 'candidate_forecasts': sum(c.get('screening_status') == 'candidate_needs_validation' for c in found), 'reviewed_verdicts': len(valid_cases), 'invalid_cases': invalid_cases, 'outcome_verification_complete': bool(valid_cases), 'run': run, 'literature_compared_total': sum(bool(e.get('literature_assessed_utc')) for e in entries.values()),
             'field_development_trails_total': sum(bool(e.get('field_developments')) for e in entries.values()),
             'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat()}
    (ROOT / 'scanner2-audit.json').write_text(json.dumps(audit, indent=2)+'\n', encoding='utf-8')
    print('OUTCOME AUDIT:', json.dumps(audit), flush=True)
    print(f'Radar 2: {len(found)} source records, {worked} bibliography attempts, {failed} failures, {sum(bool(x.get("evidence") or x.get("counterevidence")) for x in entries.values())} entries with dated evidence; Word: {REPORT}', flush=True)
    summary_file = os.getenv('GITHUB_STEP_SUMMARY')
    if summary_file:
        with open(summary_file, 'a', encoding='utf-8') as summary:
            summary.write(f'## Radar 2 follow-up\n\n- Leads: {len(found)}\n- Attempts this run: {worked}\n- Failed this run: {failed}\n- Successful checks saved: {sum(bool(x.get("checked_utc")) for x in entries.values())}\n- OpenAlex throttled: {throttled}\n- Source-reviewed forecast comparisons: {len(valid_cases)}\n- Outcome verification complete: {bool(valid_cases)}\n- Word report generated: {REPORT}\n')
    if not args.offline and args.provider not in ('catalogue', 'evidence') and (worked == 0 or worked == failed) and queue:
        print('::warning::No successful research checks; an honest Word audit was still generated and will be committed.', flush=True)


if __name__ == '__main__':
    main()
