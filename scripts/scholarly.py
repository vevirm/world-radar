"""Academic foresight DISCOVERY using abstract metadata, never full-text certification.

DOIs and abstracts are indexed leads, NOT verified papers or retrospective verdicts.
Broad date/year/topic rotation is saved between runs. Crossref works without a key;
OpenAlex is optional and uses OPENALEX_API_KEY for sustainable usage.
"""
import calendar
from itertools import zip_longest
import html
import json
import os
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

CROSSREF = 'https://api.crossref.org/works'
OPENALEX = 'https://api.openalex.org/works'
JOURNALS = ('Futures', 'Technological Forecasting and Social Change',
            'European Journal of Futures Research', 'Foresight',
            'Journal of Futures Studies', 'World Futures', 'Futures & Foresight Science')
# Pair explicitly European search phrases with futures methods and horizon concepts.
SEARCHES = (
    'European Union strategic foresight', 'Europe alternative futures scenarios',
    'European Union scenarios 2030 2050', 'Europe horizon scanning foresight',
    'European future Delphi scenarios', 'European foresight backcasting',
    'EU climate energy futures modelling', 'European labour skills future projections',
    'EU artificial intelligence futures scenarios', 'European security geopolitical futures',
    'Europe demographic futures projections', 'European public policy anticipatory governance',
    'European Union transition pathways 2050', 'Europe future of work foresight',
    'Europe technology forecasting scenarios', 'European futures research methods',
    'EU innovation R&I futures', 'European migration scenario modelling',
    'European agriculture food futures', 'European health foresight scenarios',
)
FUTURES = re.compile(r'\b(?:foresight|forecast(?:ing|s)?|scenario(?:s| planning| building)?|'
                     r'future(?:s|\s+of)?|prospective|projection(?:s)?|anticipator\w*|'
                     r'horizon scanning|backcast\w*|delphi|long.term outlook|'
                     r'pathways? (?:to|towards?) 20[2345]\d|by 20[2345]\d)\b', re.I)
EUROPE = re.compile(r'\b(?:European Union|\bEU\b|Europe|European|EU-?27|Member States|'
                    r'Eurozone|European Commission|Horizon Europe)\b', re.I)
LOW_SUBSTANCE = re.compile(r'\b(?:editorial|book review|erratum|corrigendum|commentary|'
                           r'letter to the editor|conference announcement|call for papers|'
                           r'news item|interview with)\b', re.I)
MIN_ABSTRACT_WORDS = 45
MAX_LEADS = 3500
REQUEST_TIMEOUT = (4, 13)


def strip_markup(value):
    if not value:
        return ''
    return ' '.join(BeautifulSoup(html.unescape(str(value)), 'html.parser').stripped_strings).strip()[:4500]


def unfold_abstract(inverted):
    if not isinstance(inverted, dict):
        return ''
    words = {}
    for term, positions in inverted.items():
        if not isinstance(positions, list):
            continue
        for p in positions:
            if isinstance(p, int) and 0 <= p < 3000:
                words[p] = term
    return ' '.join(word for _, word in sorted(words.items()))[:4500]


def normal_doi(value):
    if not value:
        return ''
    s = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', str(value).strip(), flags=re.I)
    s = re.sub(r'^doi:\s*', '', s, flags=re.I).strip().lower()
    return s if re.fullmatch(r'10\.\d{4,9}/[^\s<>"#]+', s, re.I) else ''


def date_parts(parts):
    if not isinstance(parts, list) or not parts or not isinstance(parts[0], list):
        return None
    p = parts[0]
    try:
        y = int(p[0]); m = int(p[1]) if len(p) > 1 else 12
        d = int(p[2]) if len(p) > 2 else calendar.monthrange(y, m)[1]
        return date(y, m, d)
    except (ValueError, IndexError, TypeError):
        return None


def crossref_lead(item):
    doi = normal_doi(item.get('DOI'))
    title = strip_markup((item.get('title') or [''])[0])
    abstract = strip_markup(item.get('abstract'))
    published = next((d for d in (
        date_parts(item.get(k, {}).get('date-parts'))
        for k in ('published-online', 'published', 'issued', 'published-print')) if d), None)
    if not doi or not title or not published:
        return None
    journal = strip_markup((item.get('container-title') or [''])[0])
    return {'doi': doi, 'title': title, 'abstract': abstract, 'date': published.isoformat(),
            'journal': journal or 'Other scholarly source', 'publisher': item.get('publisher', ''),
            'url': 'https://doi.org/' + doi, 'indexes': ['Crossref'],
            'open_access_pdf': None}


def openalex_lead(item):
    doi = normal_doi(item.get('doi'))
    published = item.get('publication_date')
    try:
        date.fromisoformat(published)
    except (TypeError, ValueError):
        return None
    if not doi:
        # Index-only IDs can be retained, but cannot be mistaken for a DOI.
        return None
    location = item.get('primary_location') or {}
    source = location.get('source') or {}
    oa = item.get('best_oa_location') or {}
    pdf = oa.get('pdf_url') if str(oa.get('pdf_url') or '').startswith('https://') else None
    return {'doi': doi, 'title': strip_markup(item.get('title')),
            'abstract': unfold_abstract(item.get('abstract_inverted_index')),
            'date': published, 'journal': source.get('display_name') or 'Other scholarly source',
            'publisher': (source.get('host_organization_name') or ''),
            'url': 'https://doi.org/' + doi, 'indexes': ['OpenAlex'],
            'open_access_pdf': pdf}


def credible_abstract(lead, earliest, latest):
    try:
        published = date.fromisoformat(lead['date'])
    except (KeyError, ValueError, TypeError):
        return False
    if not earliest <= published <= latest:
        return False
    title = lead.get('title') or ''
    abstract = lead.get('abstract') or ''
    combined = title + ' ' + abstract
    # Journal standing or an API search hit is NOT evidence of topical relevance.
    if not EUROPE.search(combined) or not FUTURES.search(combined):
        return False
    if LOW_SUBSTANCE.search(title):
        return False
    if len(abstract.split()) < MIN_ABSTRACT_WORDS:
        return False
    return True


def credible_bibliographic_lead(lead, earliest, latest):
    """Retain convincing DOI/title leads when bibliographic APIs omit abstracts.

    This is intentionally a separate, lower-confidence discovery status. Many
    publishers show an abstract on their site but do not deposit it in Crossref.
    No methodological, full-text, or retrospective claim is made from a title.
    """
    try:
        published = date.fromisoformat(lead['date'])
    except (KeyError, ValueError, TypeError):
        return False
    title = lead.get('title') or ''
    if not earliest <= published <= latest or LOW_SUBSTANCE.search(title):
        return False
    if len(title.split()) < 6 or not normal_doi(lead.get('doi')):
        return False
    return bool(EUROPE.search(title) and FUTURES.search(title))


def lead_status(lead):
    return ('Abstract indexed — full study unverified'
            if len((lead.get('abstract') or '').split()) >= MIN_ABSTRACT_WORDS
            else 'DOI/title indexed — abstract not in metadata')


def year_windows(latest):
    # The upper bound is a rolling six-calendar-month cutoff supplied by radar.
    result = []
    for y in range(latest.year - 15, latest.year + 1, 2):
        start = date(y, 1, 1)
        end = min(date(y + 1, 12, 31), latest)
        if start <= end:
            result.append((start.isoformat(), end.isoformat()))
    return result


def merge_lead(existing, new, now):
    if not existing:
        obj = dict(new)
        obj['first_seen'] = now
        obj['last_seen'] = now
        obj['status'] = lead_status(obj)
        obj['claim_status'] = 'No retrospective verdict'
        return obj
    obj = dict(existing)
    obj['last_seen'] = now
    obj['indexes'] = sorted(set(obj.get('indexes', [])) | set(new['indexes']))
    if len(new.get('abstract', '')) > len(existing.get('abstract', '')):
        obj['abstract'] = new['abstract']
    if not obj.get('open_access_pdf') and new.get('open_access_pdf'):
        obj['open_access_pdf'] = new['open_access_pdf']
    if obj.get('journal') == 'Other scholarly source' and new.get('journal'):
        obj['journal'] = new['journal']
    obj['status'] = lead_status(obj)
    return obj


def fetch_index(provider, query, start, end, key=None, journal=None):
    if provider == 'Crossref':
        filters = f'from-pub-date:{start},until-pub-date:{end},type:journal-article'
        if journal:
            filters += ',container-title:' + journal
        response = requests.get(CROSSREF, params={
            'query.bibliographic': query,
            'filter': filters,
            'rows': 35, 'select': 'DOI,title,abstract,container-title,publisher,published,published-online,issued,published-print',
        }, headers={'User-Agent': 'European-Foresight-Radar/4.0 (scholarly metadata indexing; polite rate)'},
            timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return [r for x in response.json().get('message', {}).get('items', []) if (r := crossref_lead(x))]
    if provider == 'OpenAlex':
        params = {'search': query,
                  'filter': f'from_publication_date:{start},to_publication_date:{end},type:article',
                  'per_page': 35}
        if key:
            params['api_key'] = key
        response = requests.get(OPENALEX, params=params, headers={
            'User-Agent': 'European-Foresight-Radar/4.0 (abstract indexing)'},
            timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return [r for x in response.json().get('results', []) if (r := openalex_lead(x))]
    raise ValueError('Unknown bibliographic provider')


def load_leads(path):
    if not path.exists():
        return {'schema_version': 1, 'updated_at': None, 'leads': []}
    obj = json.loads(path.read_text(encoding='utf-8'))
    if obj.get('schema_version') != 1 or not isinstance(obj.get('leads'), list):
        raise ValueError('Research leads file has an unsupported schema')
    return obj


def atomic_json(path, payload):
    t = path.with_suffix(path.suffix + '.tmp')
    t.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    os.replace(t, path)


def scholarly_scan(state_path, leads_path, latest, deadline, *, max_queries=24):
    """Search distinct topic/year/index combinations; persist state each run.

    Queries may fail independently; a response error never masquerades as a
    scientifically rejected document. The original state history is preserved.
    """
    try:
        from_date = latest.replace(year=latest.year-15)
    except ValueError:
        from_date = latest.replace(year=latest.year-15, day=28)
    state = json.loads(Path(state_path).read_text(encoding='utf-8')) if Path(state_path).exists() else {
        'schema_version': 1, 'runs': 0, 'source_cursor': 0, 'verification_cursor': 0,
        'archive_pages': {}, 'documents': {}, 'queue': []}
    saved = load_leads(Path(leads_path))
    records = {l['doi']: l for l in saved['leads'] if l.get('doi')}
    windows = year_windows(latest)
    key = os.getenv('OPENALEX_API_KEY', '').strip()
    providers = ('Crossref', 'OpenAlex') if key else ('Crossref',)
    # Each run starts at the next slot; rotate through every year/topic pair.
    broad = [(p, term, start, end, None) for term in SEARCHES for start, end in windows for p in providers]
    targeted = [('Crossref', term, start, end, journal)
                for journal in JOURNALS for term in ('European futures', 'Europe scenarios', 'EU foresight')
                for start, end in windows]
    # Put 5–10-year-old publications first in each rotation, without excluding
    # exceptional work from the wider (rolling) 15-year period.
    def preferred_year(job):
        midpoint = (int(job[2][:4])+int(job[3][:4]))/2
        age = latest.year-midpoint
        return (0 if 5 <= age <= 10 else 1, abs(age-7.5))
    broad.sort(key=preferred_year)
    targeted.sort(key=preferred_year)
    # Alternate general research discovery with journal-specific discovery;
    # a search must not depend on a publisher linking to its own catalogue.
    tasks = [job for pair in zip_longest(broad, targeted) for job in pair if job]
    cursor = int(state.get('scholarly_cursor', 0)) % max(1, len(tasks))
    new = 0
    requests_made = 0
    errors = []
    examined = 0
    abstract_missing = 0
    topic_or_date_filtered = 0
    title_only_count = 0
    now = datetime.now(timezone.utc).isoformat()
    for i in range(min(max_queries, len(tasks))):
        if time.monotonic() >= deadline - 10:
            break
        provider, phrase, start, end, journal = tasks[(cursor + i) % len(tasks)]
        requests_made += 1
        try:
            hits = fetch_index(provider, phrase, start, end, key, journal)
            examined += len(hits)
            valid = 0
            for lead in hits:
                if not lead.get('abstract'):
                    abstract_missing += 1
                abstract_ok = credible_abstract(lead, from_date, latest)
                if not abstract_ok and not credible_bibliographic_lead(lead, from_date, latest):
                    topic_or_date_filtered += 1
                    continue
                if not abstract_ok:
                    title_only_count += 1
                doi = lead['doi']
                if doi not in records:
                    new += 1
                records[doi] = merge_lead(records.get(doi), lead, now)
                valid += 1
            print(f'SCHOLAR {provider} {start}:{end} {journal or "all journals"} {phrase!r} | results={len(hits)} '
                  f'eligible_research_leads={valid} new_total={new}', flush=True)
        except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
            errors.append(f'{provider} {start} {phrase}: {str(exc)[:120]}')
            print(f'SCHOLAR ERROR {provider} | {str(exc)[:150]}', flush=True)
    state['scholarly_cursor'] = (cursor + requests_made) % max(1, len(tasks))
    state['last_scholarly_scan_utc'] = now
    if requests_made:
        state['scholarly_queries_completed'] = int(state.get('scholarly_queries_completed', 0)) + requests_made
    atomic_json(Path(state_path), state)
    # Date selection uses original publication year, prioritising older studies
    # useful for retrospection, but retaining newer eligible articles too.
    # Preserve recently rediscovered work across years, not only the oldest 2015 cohort.
    newest = sorted(records.values(), key=lambda r: (r.get('last_seen', ''), r['doi']), reverse=True)[:MAX_LEADS]
    leads = sorted(newest, key=lambda r: (r['date'], r['doi']))
    atomic_json(Path(leads_path), {'schema_version': 1, 'updated_at': now,
                'status': 'Journal leads from DOI/title and available abstracts; full text and forecasts unverified',
                'leads': leads})
    result = {'queries': requests_made, 'indexed_records_examined': examined,
              'records_without_abstract': abstract_missing,
              'records_outside_topic_or_date': topic_or_date_filtered,
              'title_only_leads': title_only_count,
              'new_leads': new, 'total_leads': len(leads),
              'provider_errors': errors[:20], 'openalex_configured': bool(key),
              'next_query_cursor': state['scholarly_cursor']}
    print(f'SCHOLAR SUMMARY: {result}', flush=True)
    return result
