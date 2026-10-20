#!/usr/bin/env python3
"""EU/European foresight retrospective — credible research, not news headlines.

DISCOVER: rotate registered EU institutions, universities, independent think
tanks, research institutes, international bodies and EU-funded project sites
through a full 15-minute scan window. VERIFY new/deferred reports in a full 10-minute window. Report publication MUST be no more than 15 years old
and six calendar months old or older on the current run. Full document must
pass substantive foresight quality and evidence gates, not just a keyword/length
check. A scenario is never automatically deemed to have come true.

The two CLI stages can be tested quickly with --once without shortening
production workflow durations. Python standard library + requirements.txt.
"""
import argparse
import calendar
import hashlib
import io
import json
import math
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from scholarly import scholarly_scan
from priority import refresh as refresh_priorities
from check_priorities import check_indexed_leads

FIXED_PHASE_PROTOCOL = 5  # Continuous academic rotation + publisher scan, followed by verification.
RETRIEVAL_PROTOCOL = 2
SCHOLARLY_DISCOVERY_PROTOCOL = 1
ROOT = Path(__file__).resolve().parents[1]
AGENT = 'European-Foresight-Retrospective/3.0 (publisher and research verification)'
TIMEOUT = (5, 12)
TODAY = lambda: datetime.now(timezone.utc).date()
RESULTS = ROOT / 'findings.json'
CANDIDATES = ROOT / 'candidates.json'
AUDIT = ROOT / 'scan-report.json'
STATE = ROOT / 'radar-state.json'
ACTORS_PER_RUN = 6
PAGES_PER_ACTOR = 2
MAX_PAGES_PER_ACTOR = 36
MAX_BACKLOG = 2500
MAX_HISTORY = 12000
def earliest_date(today):
    try:
        return today.replace(year=today.year-15)
    except ValueError:  # 29 February
        return today.replace(year=today.year-15, day=28)

START_DATE = earliest_date(TODAY())
MIN_WORDS = 2600
MIN_PDF_PAGES = 8
VERIFIER_VERSION = 3
# Cellar is the EU Publications Office's official dissemination repository.
# These EXACT hosts may be followed as an EU publication download bridge;
# original publisher domain requirements still apply to candidate landing pages.
EU_DOCUMENT_HOSTS = frozenset({'op.europa.eu', 'publications.europa.eu',
                              'research-and-innovation.ec.europa.eu',
                              'ec.europa.eu', 'commission.europa.eu',
                              'data.europa.eu'})
CELLAR_ID = re.compile(r'(?i)(?:/publication/|/resource/cellar/)([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:[/?#]|$)')
# These were discovered in the supplied October 2026 audit but erroneously
# cooled down when the old verifier checked HTML catalogue summaries as papers.
# They are leads only, never preapproved findings.
REPAIR_LEADS = [
 {'actor_id': 'ec-contracts', 'title': 'Foresight on demand: Foresight towards the 2nd Strategic Plan for Horizon Europe',
  'url': 'https://research-and-innovation.ec.europa.eu/knowledge-publications-tools-and-data/publications/all-publications/foresight-demand-foresight-towards-2nd-strategic-plan-horizon-europe_en',
  'date_hint': '2023-12-14', 'topic': 'Science & technology'},
 {'actor_id': 'ec-contracts', 'title': 'After the new normal: Scenarios for Europe in the post Covid-19 world',
  'url': 'https://research-and-innovation.ec.europa.eu/knowledge-publications-tools-and-data/publications/all-publications/after-new-normal-scenarios-europe-post-covid-19-world_en',
  'date_hint': '2022-04-04', 'topic': 'EU strategic foresight'},
 {'actor_id': 'ec-contracts', 'title': 'Foresight reports for Missions in Horizon Europe',
  'url': 'https://research-and-innovation.ec.europa.eu/knowledge-publications-tools-and-data/publications/all-publications/foresight-reports-missions-horizon-europe_en',
  'date_hint': None, 'topic': 'EU strategic foresight'},
 {'actor_id': 'ec-contracts', 'title': 'Strategic foresight in the Western Balkans',
  'url': 'https://research-and-innovation.ec.europa.eu/knowledge-publications-tools-and-data/publications/all-publications/strategic-foresight-western-balkans_en',
  'date_hint': None, 'topic': 'EU strategic foresight'},
 {'actor_id': 'ec-contracts', 'title': 'Strategic Intelligence Foresight System for European Union Research and Innovation (R&I) SAFIRE',
  'url': 'https://op.europa.eu/en/publication-detail/-/publication/e436b4b6-fa50-11eb-b520-01aa75ed71a1/language-en/format-PDF/source-222702137',
  'date_hint': None, 'topic': 'EU strategic foresight'},
]

class DocumentRetrievalError(ValueError):
    """The full study could not be obtained or text-extracted: NOT a quality judgment."""


class SubstantiveQualityError(ValueError):
    """Full study is readable and fails the research-substance screen."""

ARCHIVE_HINT = re.compile(r'\b(?:foresight|outlook|megatrends?|global trends|future shocks|future of|future risks?|scenario[s]?|skills forecast|state and outlook|strategic forecast|forward look|horizon scann(?:ing)?|to 20[345]\d)\b', re.I)
STOP = {'the', 'and', 'with', 'for', 'towards', 'from', 'into', 'this', 'that', 'part', 'en', 'european', 'europe', 'report'}
MONTHS = {n.lower(): i for i, n in enumerate(calendar.month_name) if n}
MONTHS.update({n.lower(): i for i, n in enumerate(calendar.month_abbr) if n})
WORD_MONTHS = '|'.join(sorted(map(re.escape, MONTHS), key=len, reverse=True))
DATE_LONG = re.compile(r'\b(\d{1,2})\s+(' + WORD_MONTHS + r')\.?\s+(20\d\d)\b', re.I)
DATE_US = re.compile(r'\b(' + WORD_MONTHS + r')\.?\s+(\d{1,2}),?\s+(20\d\d)\b', re.I)
DATE_ISO = re.compile(r'\b(20\d\d)-(\d\d)-(\d\d)\b')
DATE_EU = re.compile(r'\b(\d{1,2})[-./](\d{1,2})[-./](20\d\d)\b')
VERDICTS = {'Observed', 'Partly observed', 'Not observed', 'Too early / unresolved', 'Scenario (not testable)'}
EVIDENCE_HOSTS = {'ec.europa.eu', 'commission.europa.eu', 'joint-research-centre.ec.europa.eu',
                  'publications.jrc.ec.europa.eu', 'www.europarl.europa.eu', 'europarl.europa.eu',
                  'www.consilium.europa.eu', 'consilium.europa.eu', 'www.eea.europa.eu', 'eea.europa.eu',
                  'www.cedefop.europa.eu', 'cedefop.europa.eu', 'www.espas.eu', 'espas.eu',
                  'www.iss.europa.eu', 'iss.europa.eu', 'www.eeas.europa.eu', 'eeas.europa.eu',
                  'ec.europa.eu', 'ec.europa.eu', 'www.eurofound.europa.eu', 'www.eurostat.ec.europa.eu',
                  'eurostat.ec.europa.eu', 'www.europarl.europa.eu', 'www.oecd.org', 'oecd.org',
                  'www.worldbank.org', 'worldbank.org', 'www.un.org', 'un.org',
                  'www.who.int', 'who.int'}


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def atomic_json(path, obj):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def cutoff(today):
    """Six CALENDAR months (not 180 days). Document date must be <= cutoff."""
    year = today.year
    month = today.month - 6
    if month <= 0:
        year -= 1
        month += 12
    return date(year, month, min(today.day, calendar.monthrange(year, month)[1]))


def trusted_host(url):
    try:
        p = urlparse(url)
        if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None, 443):
            return None
        return p.hostname.lower().rstrip('.')
    except ValueError:
        return None


def clean_url(url):
    p = urlsplit(url)
    q = urlencode([(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                   if not k.lower().startswith('utm_') and k.lower() not in {'fbclid', 'gclid'}])
    return urlunsplit((p.scheme, p.netloc, p.path, q, ''))


def get_page(url, allowed):
    """No off-issuer redirects; limit downloaded bytes and reject unexpected schemes."""
    with requests.Session() as session:
        for _ in range(5):
            if trusted_host(url) not in allowed:
                raise ValueError('Unregistered publisher or off-site redirect')
            is_cellar = urlparse(url).hostname == 'publications.europa.eu' and '/resource/cellar/' in urlparse(url).path
            headers = {'User-Agent': AGENT, 'Accept': 'application/pdf' if is_cellar else 'text/html,application/pdf;q=0.8'}
            if is_cellar:
                headers['Accept-Language'] = 'eng'
            with session.get(url, headers=headers,
                             timeout=TIMEOUT, allow_redirects=False, stream=True) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    if not response.headers.get('Location'):
                        raise ValueError('Redirect has no Location header')
                    url = urljoin(url, response.headers['Location'])
                    continue
                response.raise_for_status()
                size = 40_000_000 if (is_cellar or 'pdf' in response.headers.get('Content-Type', '').lower() or url.lower().split('?')[0].endswith('.pdf')) else 3_500_000
                chunks = bytearray()
                for chunk in response.iter_content(32_768):
                    chunks.extend(chunk)
                    if len(chunks) > size:
                        raise ValueError('Document is too large for the verification budget')
                return clean_url(url), bytes(chunks), response.headers.get('Content-Type', '')
    raise ValueError('Too many redirects')


def parse_any_date(text):
    s = str(text or '')
    for pattern in (DATE_ISO, DATE_EU, DATE_LONG, DATE_US):
        m = pattern.search(s)
        if not m:
            continue
        try:
            if pattern is DATE_ISO:
                return date(*map(int, m.groups()))
            if pattern is DATE_EU:
                d, month, year = map(int, m.groups())
                return date(year, month, d)
            if pattern is DATE_US:
                month, d, year = m.groups()
                return date(int(year), MONTHS[month.lower().rstrip('.')], int(d))
            d, month, year = m.groups()
            return date(int(year), MONTHS[month.lower().rstrip('.')], int(d))
        except (ValueError, KeyError):
            continue
    return None


def normal(text):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', (text or '').casefold())).strip()


def title_match(expected, actual):
    a = set(normal(expected).split()) - STOP
    b = set(normal(actual).split()) - STOP
    return len(a) >= 2 and len(b) >= 2 and len(a & b) >= 2 and len(a & b) / min(len(a), len(b)) >= .78


def flatten_json_ld(node, dates):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in {'datePublished', 'dateCreated', 'dateIssued'}:
                parsed = parse_any_date(v)
                if parsed:
                    dates.add(parsed)
            flatten_json_ld(v, dates)
    elif isinstance(node, list):
        for v in node:
            flatten_json_ld(v, dates)


def page_info(raw, ctype='text/html', full_pdf=False):
    if raw[:4] == b'%PDF' or 'application/pdf' in ctype.lower():
        reader = PdfReader(io.BytesIO(raw), strict=False)
        # For long studies, always include the end matter: methods and
        # bibliographies may follow hundreds of pages of annexes/scenarios.
        total_pages = len(reader.pages)
        indices = (sorted(set(range(min(total_pages, 150))) |
                          set(range(max(150, total_pages - 35), total_pages)))
                   if full_pdf else list(range(min(total_pages, 3))))
        pages = [reader.pages[i].extract_text() or '' for i in indices]
        text = ' '.join(pages)[:1200000 if full_pdf else 30000]
        if full_pdf and len(text.split()) < 300 and len(reader.pages) >= MIN_PDF_PAGES:
            # A text-bearing PDF may use encodings pypdf cannot decode.
            # PyMuPDF is only a fallback; never OCR arbitrary scanned pages.
            try:
                import fitz
                with fitz.open(stream=raw, filetype='pdf') as document:
                    alternate = ' '.join(document[i].get_text('text') for i in indices)[:1200000]
                    if len(alternate.split()) > len(text.split()):
                        text = alternate
            except (ImportError, RuntimeError, ValueError):
                pass
        year_candidates = []
        year_forms = (
            r'\b(?:published|publication|copyright|©|EU|European Union)\s*(?:in\s*)?(20\d\d)\b',
            r'\bmanuscript completed\s+in\s+(?:[A-Za-z]+\s+)?(20\d\d)\b',
            r'\bLuxembourg\s*:\s*Publications Office.*?\b(20\d\d)\b',
            r'©.{0,85}?\b(20\d\d)\b',
            r'\b(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+(20\d\d)\b',
        )
        for pattern in year_forms:
            year_candidates.extend(re.findall(pattern, text[:10000], re.I))
        return {'titles': [re.sub(r'\s+', ' ', text[:1600])], 'dates': set(), 'years': {int(y) for y in year_candidates},
                'text': re.sub(r'\s+', ' ', text), 'links': [], 'pages': len(reader.pages), 'format': 'pdf'}
    soup = BeautifulSoup(raw, 'html.parser')
    titles = []
    for selector in ('h1', 'meta[property="og:title"]', 'meta[name="twitter:title"]', 'title'):
        for element in soup.select(selector)[:2]:
            title = (element.get('content') or element.get_text(' ', strip=True)).strip()
            if title:
                titles.append(title)
    for el in soup(['script', 'style', 'nav', 'footer', 'form', 'aside']):
        if el.name != 'script' or el.get('type') != 'application/ld+json':
            el.decompose()
    dates = set()
    for selector in ('meta[property="article:published_time"]', 'meta[name="date"]',
                     'meta[name="pubdate"]', 'meta[name="datePublished"]',
                     'meta[itemprop="datePublished"]', 'time[datetime]',
                     'meta[name="DC.date.issued"]', '[itemprop="datePublished"]'):
        for element in soup.select(selector):
            parsed = parse_any_date(element.get('content') or element.get('datetime') or element.get_text(' ', strip=True))
            if parsed:
                dates.add(parsed)
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            flatten_json_ld(json.loads(script.string or script.get_text()), dates)
        except (TypeError, ValueError, RecursionError):
            pass
    main = soup.select_one('main') or soup.select_one('article') or soup.body or soup
    # Dates visibly labelled by institutional publishers, rather than ANY date in a body.
    visible = main.get_text(' ', strip=True)
    for m in re.finditer(r'\b(?:published|publication date|date of publication|date issued|issue date|report date|study|news announcement)\s*[:\-]?\s*', visible, re.I):
        parsed = parse_any_date(visible[m.end():m.end() + 65])
        if parsed:
            dates.add(parsed)
    # Publishing sites frequently print "31-08-2023" or "6 July 2023" by the heading.
    heading = main.select_one('h1')
    if heading:
        early = heading.parent.get_text(' ', strip=True)[:350] if heading.parent else ''
        parsed = parse_any_date(early)
        if parsed:
            dates.add(parsed)
    # Anchor lists are only used for DISCOVERY; they are not proof of date or claim.
    links = [(a.get_text(' ', strip=True)[:190], a.get('href', '')) for a in main.select('a[href]')[:300]]
    years = set()
    for match in re.finditer(r'\b(?:publication year|published(?: in)?|released in|©)\s*:?\s*(20\d\d)\b', visible[:10000], re.I):
        years.add(int(match.group(1)))
    return {'titles': titles, 'dates': dates, 'years': years,
            'text': re.sub(r'\s+', ' ', visible)[:420000], 'links': links, 'pages': None, 'format': 'html'}


def candidates_from_archives(actor, page_url, info):
    results = []
    for title, href in info['links']:
        url = clean_url(urljoin(page_url, href))
        if not ARCHIVE_HINT.search(title) or trusted_host(url) not in actor['domain_hosts']:
            continue
        if url == page_url or not title or len(title) < 18 or len(title) > 150:
            continue
        if any(k in normal(title) for k in ('about us', 'newsletters', 'subscribe', 'working group', 'contact us', 'all publications')):
            continue
        results.append({'title': title, 'url': url, 'date_hint': None, 'topic': 'EU strategic foresight',
                        'source_mode': 'publisher archive link'})
    return results


def get_registry():
    actors = read_json(ROOT / 'actors.json')['actors']
    for a in actors:
        if not a.get('id') or not a.get('domain_hosts') or not all(trusted_host(url) in a['domain_hosts'] for url in a['archives']):
            raise ValueError('Invalid publisher registry: ' + a.get('id', '?'))
        if not all(trusted_host(s['url']) in a['domain_hosts'] for s in a.get('seeds', [])):
            raise ValueError('Seed URL outside registered publisher: ' + a['id'])
    return actors


def empty_state():
    return {'schema_version': 1, 'runs': 0, 'source_cursor': 0, 'verification_cursor': 0,
            'archive_pages': {}, 'documents': {}, 'queue': []}


def load_state():
    if not STATE.exists():
        return empty_state()
    state = read_json(STATE)
    if state.get('schema_version') != 1 or not isinstance(state.get('queue'), list):
        raise ValueError('Unknown or corrupt radar-state.json; refusing to reset scan history')
    for field in ('archive_pages', 'documents'):
        if not isinstance(state.get(field), dict):
            raise ValueError('Invalid persisted radar state: ' + field)
    return state


def interleaved_actors(actors):
    """Order categories fairly; don't let the first ten institutional actors monopolise runs."""
    buckets = {}
    for actor in actors:
        buckets.setdefault(actor['category'], []).append(actor)
    ordered = []
    while any(buckets.values()):
        for group in buckets.values():
            if group:
                ordered.append(group.pop(0))
    return ordered


def next_actor_batch(actors, state, limit=ACTORS_PER_RUN):
    ordered = interleaved_actors(actors)
    if not ordered:
        return []
    start = int(state.get('source_cursor', 0)) % len(ordered)
    selection = [ordered[(start + i) % len(ordered)] for i in range(min(limit, len(ordered)))]
    state['source_cursor'] = (start + len(selection)) % len(ordered)
    return selection


def page_queue(actor, state, current_day):
    """Pick never-scanned pages first, then oldest stale ones; roots refresh daily."""
    pages = state['archive_pages'].setdefault(actor['id'], {})
    for root in actor['archives']:
        pages.setdefault(clean_url(root), {'root': True, 'last_scan': None})
    for url in list(pages):
        if trusted_host(url) not in actor['domain_hosts']:
            del pages[url]
    available = []
    for url, record in pages.items():
        last = record.get('last_scan')
        # Landing pages get a daily refresh; deeper archive pages are
        # expensive and mostly historical, so only revisit monthly.
        interval = 1 if record.get('root') else 30
        if last and date.fromisoformat(last) + timedelta(days=interval) > current_day:
            continue
        available.append((bool(last), last or '0000-00-00', not record.get('root'), url))
    return [entry[-1] for entry in sorted(available)[:PAGES_PER_ACTOR]]


def pagination_links(actor, page_url, info):
    """Allowlisted older/archive pages (not arbitrary search-result or offsite crawls)."""
    base = urlsplit(page_url)
    links = []
    for label, href in info['links']:
        dest = clean_url(urljoin(page_url, href))
        if trusted_host(dest) not in actor['domain_hosts'] or dest == page_url:
            continue
        parsed = urlsplit(dest)
        if parsed.hostname != base.hostname:
            continue
        path = parsed.path.rstrip('/').lower()
        stem = base.path.rstrip('/').lower()
        # Only walk numerical pagination attached to the current archive path.
        same_path = path == stem
        path_page = path.startswith(stem + '/page/') and bool(re.search(r'/page/[1-9]\d*$', path))
        query_page = same_path and bool(re.search(r'(?:^|&)(?:page|p|offset)=[0-9]+(?:&|$)', parsed.query, re.I))
        if path_page or query_page:
            links.append(dest)
    return list(dict.fromkeys(links))[:12]


def archive_trail_links(actor, page_url, info, depth):
    """Follow up to two levels of publisher-owned foresight/research collections.

    A university landing page often links to its reports catalogue rather
    than to individual papers. Limit these pointers to collection-like labels,
    not endless news/articles/PDFs.
    """
    if depth >= 2:
        return []
    result = []
    for label, href in info['links']:
        dest = clean_url(urljoin(page_url, href))
        if trusted_host(dest) not in actor['domain_hosts'] or dest == page_url:
            continue
        parts = urlsplit(dest)
        if parts.path.lower().endswith(('.pdf', '.doc', '.docx', '.zip')):
            continue
        short = normal(label)
        if not 8 <= len(short) <= 54:
            continue
        if not re.search(r'\b(?:foresight|futures|scenarios|strategic reports|research publications|research reports|reports archive|publication archive|publications|research outputs|studies)\b', short):
            continue
        if re.search(r'\b(?:20[12-9]\d|subscribe|newsletter|press release)\b', short):
            continue
        result.append(dest)
    return list(dict.fromkeys(result))[:7]


def offer_candidate(state, candidate, published_urls, today):
    """Deduplicate across runs; rejected links return only after their cooldown."""
    key = clean_url(candidate['url'])
    hint = parse_any_date(candidate.get('date_hint'))
    if hint and not (START_DATE <= hint <= cutoff(today)):
        return 'outside-window'
    if key in published_urls or state['documents'].get(key, {}).get('status') == 'accepted':
        return 'already-published'
    record = state['documents'].get(key, {})
    retry = record.get('retry_after')
    # Upgrade repair: re-examine catalogue-only quality failures that were
    # incorrectly cooled down by the old PDF-only verifier. Once per version.
    previous_bad_extraction = (record.get('status') == 'rejected' and
                               record.get('reason', '').startswith('Quality gate failed') and
                               int(record.get('verifier_version', 1)) < VERIFIER_VERSION)
    if retry and retry > today.isoformat() and not previous_bad_extraction:
        return 'cooldown'
    if any(clean_url(item['url']) == key for item in state['queue']):
        return 'already-queued'
    if len(state['queue']) >= MAX_BACKLOG:
        return 'queue-full'
    state['queue'].append(dict(candidate, url=key, first_seen=today.isoformat()))
    return 'queued'


def scan_archive(actor, archive, state, today, published_urls, new, diagnostics):
    """Fetch one due archive, extend its historical trail, and mark it visited.

    Page cooldowns and domain allowlists remain enforced; a page is never
    downloaded twice in one run, even when several exploration passes occur.
    """
    info = state['archive_pages'][actor['id']][archive]
    info['last_scan'] = today.isoformat()
    queued = 0
    try:
        url, raw, ctype = get_page(archive, set(actor['domain_hosts']))
        if raw[:4] == b'%PDF' or 'application/pdf' in ctype.lower():
            raise ValueError('Archive must be HTML')
        parsed = page_info(raw, ctype)
        found = candidates_from_archives(actor, url, parsed)
        for c in found:
            candidate = dict(c, actor_id=actor['id'])
            outcome = offer_candidate(state, candidate, published_urls, today)
            if outcome == 'queued':
                queued += 1
                new.append(candidate)
        pages = state['archive_pages'][actor['id']]
        depth = info.get('depth', 0)
        for target in pagination_links(actor, url, parsed):
            if len(pages) < MAX_PAGES_PER_ACTOR:
                pages.setdefault(target, {'root': False, 'depth': depth, 'last_scan': None})
        for target in archive_trail_links(actor, url, parsed, depth):
            if len(pages) < MAX_PAGES_PER_ACTOR:
                pages.setdefault(target, {'root': False, 'depth': depth + 1, 'last_scan': None})
        diagnostics.append({'actor': actor['id'], 'archive': archive,
                            'candidate_links': len(found), 'new_queue': queued})
        print(f'SOURCE {actor["id"]}: {archive} | found {len(found)}, new {queued}, '
              f'backlog {len(state["queue"])}', flush=True)
    except Exception as exc:
        diagnostics.append({'actor': actor['id'], 'archive': archive,
                            'error': str(exc)[:170]})
        print(f'SOURCE {actor["id"]}: archive unavailable: {str(exc)[:110]}', flush=True)
    return queued


def discover(deadline, once=False):
    """Use the whole discovery phase on distinct, due publisher archive pages.

    Iterate through the registered actors, then follow fresh pagination/research
    collections discovered in earlier passes. Publisher pages under cooldown
    are never fetched again. Once no further eligible pages exist, the stage
    stays open with truthful idle heartbeats until the 15-minute deadline.
    """
    actors = get_registry()
    state = load_state()
    state['runs'] = int(state.get('runs', 0)) + 1
    today = TODAY()
    ordered = interleaved_actors(actors)
    start_cursor = int(state.get('source_cursor', 0)) % max(1, len(ordered))
    proposed = [ordered[(start_cursor + i) % len(ordered)] for i in range(len(ordered))]
    published_urls = {clean_url(x['url']) for x in read_json(RESULTS).get('findings', [])}
    diagnostics = []
    new = []
    # Hand off curated studies directly to the same persistent verification queue.
    # Publication links are candidates, not endorsed findings.
    curated_queued=0
    for source in read_json(ROOT/'priority-sources.json')['sources']:
        host=trusted_host(source['url'])
        actor=next((x for x in actors if host in x['domain_hosts']), None)
        if not actor: continue
        candidate={'url':clean_url(source['url']), 'title':source['title'],
                   'date_hint':source['date'], 'topic':source.get('topic','EU futures'),
                   'source_mode':'curated retrospective priority (unverified)',
                   'actor_id':actor['id']}
        if offer_candidate(state,candidate,published_urls,today)=='queued':
            new.append(candidate); curated_queued+=1
    print(f'CONNECTED HANDOFF: {curated_queued} publisher-linked priority candidates placed in verification queue', flush=True)
    processed = 0
    pages_attempted = 0
    passes = 0

    # One first pass across all sources, then progressively follow their
    # *unvisited* archive/pagination trails while useful time remains.
    for pass_number in range(1, MAX_PAGES_PER_ACTOR + 2):
        if not once and time.monotonic() >= deadline:
            break
        passes = pass_number
        pass_pages = 0
        for actor in proposed[:processed] if pass_number > 1 else proposed:
            if not once and time.monotonic() >= deadline:
                break
            added = 0
            skipped = 0
            if pass_number == 1:
                processed += 1
                leads = list(actor.get('seeds', []))
                if actor['id'] == 'ec-contracts':
                    leads += [dict(title=x['title'], url=x['url'], date=x.get('date_hint'), topic=x['topic'])
                              for x in REPAIR_LEADS]
                for seed in leads:
                    candidate = {'title': seed['title'], 'url': clean_url(seed['url']),
                                 'date_hint': seed.get('date'), 'topic': seed['topic'],
                                 'source_mode': 'historic catalogue seed (unverified)', 'actor_id': actor['id']}
                    outcome = offer_candidate(state, candidate, published_urls, today)
                    if outcome == 'queued':
                        added += 1
                        new.append(candidate)
                    else:
                        skipped += 1
            page_urls = page_queue(actor, state, today)
            for archive in page_urls:
                if not once and time.monotonic() >= deadline:
                    break
                pass_pages += 1
                pages_attempted += 1
                added += scan_archive(actor, archive, state, today, published_urls, new, diagnostics)
            if page_urls or (pass_number == 1 and (added or skipped)):
                print(f'ROTATION pass={pass_number} actor={actor["id"]} '
                      f'new={added} skipped_known={skipped} pages_due={len(page_urls)}', flush=True)
        print(f'DISCOVERY PASS {pass_number}: {pass_pages} distinct archive pages visited; '
              f'{len(new)} new candidates in total', flush=True)
        # Diagnostic single-pass mode and tests with unbounded deadlines don't
        # recursively browse an archive or wait for production windows.
        if once or not math.isfinite(deadline) or pass_pages == 0:
            break

    # When the first pass ran out of clock time, resume with its first unvisited
    # actor next run. When all were visited, shift the starting actor to avoid
    # favouring the first institution in the registry.
    state['source_cursor'] = (start_cursor + processed + (1 if processed == len(ordered) else 0)) % max(1, len(ordered))
    state['last_discovery_utc'] = datetime.now(timezone.utc).isoformat()
    if len(state['documents']) > MAX_HISTORY:
        excess = len(state['documents']) - MAX_HISTORY
        for key, _ in sorted(state['documents'].items(),
                             key=lambda kv: kv[1].get('last_checked', ''))[:excess]:
            del state['documents'][key]
    atomic_json(STATE, state)
    atomic_json(CANDIDATES, {'collected_at_utc': state['last_discovery_utc'],
                              'six_month_cutoff': cutoff(today).isoformat(),
                              'earliest_publication_date': START_DATE.isoformat(),
                              'actor_count': len(actors),
                              'sources_this_run': [a['id'] for a in proposed[:processed]],
                              'archive_passes': passes, 'archive_pages_visited': pages_attempted,
                              'candidates_new': new, 'backlog_count': len(state['queue']),
                              'source_status': diagnostics})
    print(f'DISCOVERED this run: {len(new)} new candidates from '
          f'{processed} rotated publishers over {passes} exploration passes, '
          f'{pages_attempted} archive pages; {len(state["queue"])} awaiting verification; '
          f'next source cursor {state["source_cursor"]}', flush=True)


def select_publication_date(info, hinted):
    """Reject contradictions; year-only records are dated conservatively 31 Dec.

    An archive-provided date is a HINT, never accepted alone: it must be
    confirmed by a publisher-page date or PDF year. Publication pages can
    legitimately include various dates (download/updated dates), so a matching
    original date is sufficient; no arbitrary dates are guessed.
    """
    available = sorted(d for d in info['dates'] if d <= TODAY())
    year_only = sorted(y for y in info['years'] if 2000 <= y <= TODAY().year)
    if hinted:
        expected = date.fromisoformat(hinted)
        if expected in available:
            return expected, 'day', 'original publisher date matches catalogue'
        if expected.year in year_only:
            return date(expected.year, 12, 31), 'year', 'original publisher explicitly confirms publication year'
        # The EU Commission and EEA often display publication dates as plain prose
        # alongside document downloads without a datePublished metadata field.
        # The seed is accepted ONLY if its exact full date is present on that same
        # institutional landing page; the catalogue alone never proves a date.
        text = info['text']
        for pattern in (DATE_LONG, DATE_ISO, DATE_EU, DATE_US):
            if any(parse_any_date(m.group(0)) == expected for m in pattern.finditer(text)):
                return expected, 'day', 'original publisher page explicitly contains the catalogue date'
        return None, None, 'publisher does not corroborate catalogue publication date'
    # Archive-only candidates: accept only if explicit publication date is available.
    if len(available) == 1:
        return available[0], 'day', 'original publisher page'
    if len(available) > 1:
        return None, None, 'publisher page presents multiple unresolvable publication dates'
    if len(year_only) == 1:
        return date(year_only[0], 12, 31), 'year', 'original publisher year-only record'
    return None, None, 'no unambiguous original publication date'


CLAIM_VERSION = 2
CLAIM_MODAL = re.compile(
    r'\b(?:will|would|could|may|might|is expected to|are expected to|'
    r'likely to|projected to|forecast to|set to|anticipated to|'
    r'will have|would lead|could lead|may lead)\b', re.I)
CLAIM_HORIZON = re.compile(
    r'\b(?:by|in|towards?|until|through|before|after)\s+20[2-9]\d\b|'
    r'\b(?:next|coming)\s+(?:few\s+)?(?:years|decades)|'
    r'\b(?:long[- ]term|mid[- ]century|over the next|future decades)\b', re.I)
CLAIM_OUTCOME = re.compile(
    r'\b(?:change|shift|increase|decrease|accelerat\w*|declin\w*|'
    r'grow|emerg\w*|transform\w*|fac\w*|reshap\w*|threat\w*|'
    r'affect|becom\w*|ris\w*|reduc\w*|fall|demand|need|'
    r'conflict|climate|energy|migration|technology|economy|security|'
    r'industr\w*|employment|population|soci\w*|policy)\b', re.I)
META_ONLY = re.compile(
    r'\b(?:understanding of the future|tomorrow will be more of today|'
    r'this report (?:explores|aims|sets out|presents)|the aim of (?:this|the) (?:study|report)|'
    r'foresight (?:is|means|can be)|(?:scenario|future) thinking)\b', re.I)


def source_excerpt(content):
    """Choose an identifiable forward-looking passage, never generic foresight rhetoric.

    Rule-based claim extraction is an index into the original document, NOT
    semantic validation of a future claim. Retrospective verdicts remain separate.
    """
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])', content[:180000])
    best = ('', 0)
    for sentence in sentences:
        s = re.sub(r'\s+', ' ', sentence).strip()
        if not 65 <= len(s) <= 460 or META_ONLY.search(s):
            continue
        modal = bool(CLAIM_MODAL.search(s))
        horizon = bool(CLAIM_HORIZON.search(s))
        outcome = bool(CLAIM_OUTCOME.search(s))
        # Avoid generic platitudes and sentences that merely say the study
        # discusses the future. Require both an outcome and a future marker.
        if not outcome or not (modal or horizon):
            continue
        score = (3 if horizon else 0) + (3 if modal else 0) + (2 if outcome else 0)
        score += (2 if re.search(r'\b(?:europe|eu|european|member states)\b', s, re.I) else 0)
        score += (1 if 105 <= len(s) <= 340 else 0)
        if re.search(r'\b(?:this (?:report|study|paper)|the authors|chapter|figure|table)\b', s, re.I):
            score -= 3
        if score > best[1]:
            best = (s, score)
    return best[0] if best[1] >= 5 else ''


def quoted(text, source_text):
    return len(text) >= 25 and normal(text) in normal(source_text)


def verify_assessment(assessment, report_date, original_text):
    if assessment.get('verdict') not in VERDICTS:
        raise ValueError('Unsupported assessment verdict')
    for field in ('original_quote', 'original_locator', 'evidence_quote', 'evidence_url', 'assessment', 'evidence_date'):
        if not str(assessment.get(field, '')).strip():
            raise ValueError('Assessment missing ' + field)
    if not quoted(assessment['original_quote'], original_text):
        raise ValueError('The supposed foresight quote was not found in the original')
    evidence_date = date.fromisoformat(assessment['evidence_date'])
    if evidence_date <= report_date or evidence_date > TODAY():
        raise ValueError('Follow-up evidence must postdate the report and not be in the future')
    ev_url = assessment['evidence_url']
    if trusted_host(ev_url) not in EVIDENCE_HOSTS:
        raise ValueError('Evidence must come from an approved official EU domain')
    url, body, ctype = get_page(ev_url, EVIDENCE_HOSTS)
    info = page_info(body, ctype, full_pdf=True)
    if not quoted(assessment['evidence_quote'], info['text']):
        raise ValueError('Quoted evidence text not confirmed on publisher page')
    # An explicit date on the evidence page must corroborate the entered date.
    if evidence_date not in info['dates'] and evidence_date.year not in info['years']:
        raise ValueError('Evidence date not corroborated by publisher page')
    return {'verdict': assessment['verdict'], 'foresight_claim': assessment['original_quote'],
            'claim_locator': assessment['original_locator'], 'assessment': assessment['assessment'],
            'evidence_url': url, 'evidence_date': evidence_date.isoformat(),
            'evidence_quote': assessment['evidence_quote'], 'evidence_title': info['titles'][0] if info['titles'] else '',
            'assessment_method': 'editorial interpretation, both quotations & dates source-checked'}


# Eligibility is about research substance, not 2-page briefs with a grandiose title.
# These are conservative automated screening rules, NOT peer review. The full
# document has to be retrievable; a glossy landing-page abstract never suffices.
STRONG_METHOD = re.compile(
    r'\b(?:delphi|stakeholder (?:consultation|engagement)|expert (?:interviews?|panel|elicitation)|'
    r'participatory|workshops?|scenario (?:develop|build|design|construct|plan)|'
    r'backcasting|horizon scanning|cross.impact|trend analysis|'
    r'literature review|systematic review|qualitative (?:research|analysis)|'
    r'quantitative (?:research|analysis)|statistical model|modelling|modeling|'
    r'simulation|projections? based on|forecasting model|survey (?:of|with)|'
    r'research design|methods? section)\b', re.I)
FUTURE_OUTCOMES = re.compile(
    r'\b(?:scenarios?|plausible futures?|alternative futures?|future pathway|'
    r'by 20[2-9]\d|towards? 20[2-9]\d|in 20[2-9]\d|'
    r'long.term (?:outlook|projection)|projected (?:growth|decline|change)|'
    r'anticipat(?:ed|ing) (?:change|disruption)|future implications)\b', re.I)
RESEARCH_STRUCTURE = re.compile(r'\b(?:methodolog(?:y|ies)|research methods?|study design|'
                                r'analytical framework|research approach|data sources?)\b', re.I)
BIB_HEADING = re.compile(r'\b(?:references|bibliography|works cited|endnotes|sources cited)\b', re.I)
EU_FOCUS = re.compile(r'\b(?:european union|european commission|european parliament|'
                      r'eu member states|eu integration|eu policy|european (?:polic|econom|societ|industr|futur|region|security|integrat)|'
                      r'europe|eu27|eu-27|european union\s*\(eu\)|the EU)\b', re.I)


def quality_screen(full_info, actor, title):
    """Reject thin/unsupported items even when hosted by a respected institute.

    Document must contain a substantive analysis, explicit method, grounded
    sources, and a future-oriented output. PDF pages alone never earn a pass.
    The diagnostics make missing prerequisites auditable. A pass is not a claim
    that every scenario is testable, and is not a scientific peer-review verdict.
    """
    body = full_info['text']
    words = re.findall(r"\b[\wÀ-ÿ][\wÀ-ÿ'-]*\b", body)
    total = len(words)
    diverse_terms = len({w.lower() for w in words if len(w) >= 5 and not w.isdigit()})
    pages = full_info.get('pages')
    methods = set(x.lower() for x in STRONG_METHOD.findall(body))
    futures = len(FUTURE_OUTCOMES.findall(body))
    bibliography = list(BIB_HEADING.finditer(body))
    # Traceable sources beyond a statement that a study "used sources".
    # The end of a source section should contain multiple citation years,
    # author-year pairs, DOI entries or numbered sources.
    after_refs = body[bibliography[-1].end():] if bibliography else ''
    cited_years = len(re.findall(r'\b(?:19|20)\d{2}[a-z]?\b', after_refs))
    formal_cites = len(re.findall(r'\bdoi\s*[:.]|https?://|\b(?:19|20)\d{2}\)\s*[.,;]', body, re.I))
    traceable = bool(bibliography and cited_years >= 6) or formal_cites >= 10
    structure = bool(RESEARCH_STRUCTURE.search(body))
    focus = bool(actor['category']=='EU institution / agency' or
                 len(EU_FOCUS.findall((title + ' ' + body[:85000]))) >= 2)
    checks = {
        'substantial_full_text': total >= MIN_WORDS,
        'non_repetitive_analysis': diverse_terms >= 190,
        'meaningful_document_length': pages is None or pages >= MIN_PDF_PAGES,
        'explicit_research_method': structure and len(methods) >= 2,
        'traceable_evidence_and_sources': traceable,
        'actual_future_analysis': futures >= 4,
        'eu_europe_focus': focus,
    }
    detail = {'quality_version': 2, 'word_count': total, 'distinct_terms': diverse_terms, 'pdf_pages': pages,
              'method_examples': sorted(methods)[:6], 'future_signal_count': futures,
              'citation_signals': {'bibliography_detected': bool(bibliography),
                                   'reference_years': cited_years, 'formal_citations': formal_cites},
              'checks': checks, 'status': 'automated research-substance screen passed' if all(checks.values()) else 'rejected'}
    if not all(checks.values()):
        failed = ', '.join(k for k, ok in checks.items() if not ok)
        raise SubstantiveQualityError('Quality gate failed: ' + failed)
    return detail


def cellar_url(url):
    """Convert official Publications Office work identifiers to the Cellar PDF REST route.

    Never interpret a random UUID on an unrelated research website as a Cellar ID.
    """
    if trusted_host(url) not in {'op.europa.eu', 'publications.europa.eu'}:
        return None
    match = CELLAR_ID.search(urlparse(url).path)
    return ('https://publications.europa.eu/resource/cellar/' + match.group(1).lower()) if match else None


def publication_download_links(url, html):
    """Get explicit download links, including Commission Drupal /document/download URLs.

    EU catalogue download links generally DON'T end with .pdf; they may redirect
    through the Publications Office. Only explicit links count: no guessing URLs
    and no unrestricted off-domain crawling.
    """
    soup = BeautifulSoup(html, 'html.parser')
    choices = []
    for element in soup.select('a[href], iframe[src], embed[src], object[data], link[href]'):
        href = element.get('href') or element.get('src') or element.get('data') or ''
        if not href or href.startswith(('javascript:', 'data:', '#')):
            continue
        target = clean_url(urljoin(url, href))
        label = normal(element.get_text(' ', strip=True) + ' ' + str(element.get('title', '')) + ' ' +
                       str(element.get('aria-label', '')) + ' ' + str(element.get('type', '')))
        path = urlparse(target).path.lower()
        pdf = path.endswith('.pdf') or 'format-pdf' in path
        bridge = ('/document/download/' in path or '/publication-detail/' in path or
                  '/resource/cellar/' in path or ('/publication/' in path and trusted_host(target) == 'op.europa.eu'))
        labelled = bool(re.search(r'\b(?:download|full.text|pdf|complete (?:report|study)|read (?:report|study))\b', label))
        if pdf or bridge or (labelled and ('/document/' in path or 'op.europa.eu' == trusted_host(target))):
            score = 6 if pdf else 4 if bridge else 2
            if labelled:
                score += 3
            choices.append((score, target))
    return sorted(set(choices), reverse=True)


def full_document(url, info, raw, ctype, actor):
    """Retrieve the underlying study, including EU Commission -> OP -> Cellar.

    A *failed retrieval* must never be marked a failed academic-quality screen.
    We only evaluate a PDF/HTML study if its substantive body was retrieved.
    """
    if raw[:4] == b'%PDF' or 'application/pdf' in ctype.lower():
        try:
            parsed = page_info(raw, ctype, full_pdf=True)
        except Exception as exc:
            raise DocumentRetrievalError('Original PDF could not be text-extracted: ' + str(exc)[:100]) from exc
        if len(parsed['text'].split()) < 300:
            raise DocumentRetrievalError('PDF downloaded, but readable full text was not extracted')
        return url, parsed

    permitted = set(actor['domain_hosts']) | EU_DOCUMENT_HOSTS
    queue = []
    seen = {clean_url(url)}
    attempted = 0
    problems = []
    is_research_page = trusted_host(url) in EU_DOCUMENT_HOSTS

    def add(target, score):
        target = clean_url(target)
        host = trusted_host(target)
        if host not in permitted:
            return
        # Official EU repository is only used when actually referenced from
        # the publisher-provided landing/download page.
        if target not in seen and not any(q[1] == target for q in queue):
            queue.append((score, target))

    if is_research_page:
        c = cellar_url(url)
        if c:
            add(c, 12)
    for score, target in publication_download_links(url, raw):
        add(target, score)
        if cellar_url(target):
            add(cellar_url(target), score + 5)

    for label, href in info.get('links', []):
        target = clean_url(urljoin(url, href))
        if urlparse(target).path.lower().endswith('.pdf'):
            add(target, 7 if re.search(r'\b(?:report|study|download|full)\b', label, re.I) else 3)

    while queue and attempted < 12:
        queue.sort(reverse=True)
        score, target = queue.pop(0)
        if target in seen:
            continue
        seen.add(target)
        attempted += 1
        try:
            doc_url, doc_data, doc_type = get_page(target, permitted)
        except (requests.RequestException, ValueError) as exc:
            problems.append(f'{trusted_host(target)}: {str(exc)[:90]}')
            continue
        if doc_data[:4] == b'%PDF' or 'application/pdf' in doc_type.lower():
            try:
                doc_info = page_info(doc_data, doc_type, full_pdf=True)
            except Exception as exc:
                problems.append('PDF parsing failed: ' + str(exc)[:100])
                continue
            if len(doc_info['text'].split()) < 300:
                problems.append('PDF contains too little extractable text')
                continue
            cover = doc_info['text'][:2600]
            # Confirm the full study is related to the requested publication;
            # scenario titles may have supplementary subtitles on the cover.
            source_titles = info.get('titles', [])
            if (source_titles and not any(title_match(t, cover) for t in source_titles)
                    and not title_match(actor.get('name', ''), cover)):
                problems.append('Downloaded PDF does not corroborate requested report title')
                continue
            print(f'FULL STUDY: {doc_url} ({doc_info["pages"]} pages, '
                  f'{len(doc_info["text"].split())} extracted words)', flush=True)
            return doc_url, doc_info
        # Some EU download links lead to a second HTML catalogue page.
        if doc_data[:1] == b'<' and (trusted_host(doc_url) in EU_DOCUMENT_HOSTS):
            if cellar_url(doc_url):
                add(cellar_url(doc_url), 15)
            for rank, dest in publication_download_links(doc_url, doc_data):
                add(dest, rank)
                if cellar_url(dest):
                    add(cellar_url(dest), rank + 5)
    # Long HTML academic studies can be full documents; a catalogue abstract can't.
    if len(re.findall(r'\b[\wÀ-ÿ]+\b', info['text'])) >= MIN_WORDS:
        return url, info
    detail = '; '.join(problems[-3:]) if problems else 'no full-document link found'
    raise DocumentRetrievalError('Full study not retrieved; landing page only (' + detail[:330] + ')')


def verify_report(candidate, actors, reviews):
    actor = actors[candidate['actor_id']]
    if trusted_host(candidate['url']) not in actor['domain_hosts']:
        raise ValueError('Candidate is not published on the registered author/publisher domain')
    url, raw, ctype = get_page(candidate['url'], set(actor['domain_hosts']) | EU_DOCUMENT_HOSTS)
    known_review = reviews.get(url) or reviews.get(candidate['url'])
    try:
        info = page_info(raw, ctype)
    except Exception as exc:
        raise DocumentRetrievalError('Original publisher document could not be parsed: ' + str(exc)[:100]) from exc
    if not any(title_match(candidate['title'], t) for t in info['titles']):
        raise ValueError('Title not corroborated by original publisher landing page or full text')
    published, precision, basis = select_publication_date(info, candidate.get('date_hint'))
    doc_url, full = None, None
    if not published:
        # Many EU repositories omit a date on their landing page, but the
        # linked original PDF has a clear title-page publication year. Check
        # that original document before labelling a substantive study undated.
        doc_url, full = full_document(url, info, raw, ctype, actor)
        if full is not info:
            published, precision, basis = select_publication_date(full, candidate.get('date_hint'))
    if not published:
        if full is info:
            raise DocumentRetrievalError('Publisher date not verifiable; no original document corroboration: ' + basis)
        raise ValueError(basis)
    if published > cutoff(TODAY()):
        raise ValueError(f'Too recent: {published} (must be on/before {cutoff(TODAY())})')
    if published < START_DATE:
        raise ValueError(f'Publication predates rolling 15-year minimum {START_DATE}')
    if not (ARCHIVE_HINT.search(candidate['title']) or candidate.get('source_mode') == 'historic catalogue seed (unverified)'):
        raise ValueError('Not a discoverable foresight/futures-oriented study')
    if full is None:
        doc_url, full = full_document(url, info, raw, ctype, actor)
    quality = quality_screen(full, actor, candidate['title'])
    excerpt = source_excerpt(full['text'])
    if not excerpt:
        raise ValueError('No directly quotable future-facing passage in full paper')
    comparison = {'verdict': 'Not yet assessed', 'assessment': 'No independently verified later evidence has been linked yet.'}
    if known_review:
        comparison = verify_assessment(known_review, published, full['text'])
    relationship = ('EU institutional publication' if actor['category'] == 'EU institution / agency'
                    else 'External research about EU/Europe')
    if actor['category'] != 'EU institution / agency':
        front = full['text'][:12000]
        if re.search(r'\b(?:funded by the European Union|funded by (?:the )?EU|European Union.{0,120}grant agreement|Horizon Europe.{0,100}grant agreement)\b', front, re.I):
            relationship = 'EU-funded research (declared in document)'
        elif re.search(r'\b(?:commissioned by|prepared for|contracted by)\s+(?:the )?(?:European Commission|European Parliament|Council of the European Union|European Union)\b', front, re.I):
            relationship = 'External research commissioned for EU institution'
    stable_id = 'EUF-' + hashlib.sha256(url.encode()).hexdigest()[:14]
    return {'id': stable_id, 'date': published.isoformat(), 'date_precision': precision,
            'title': candidate['title'], 'source': actor['name'], 'actor_id': actor['id'],
            'source_category': actor['category'], 'relationship_to_eu': relationship,
            'authors': '', 'type': 'Substantive foresight / futures study', 'topic': candidate['topic'],
            'finding': excerpt, 'claim_extraction_version': CLAIM_VERSION, 'context': basis, 'url': url, 'full_text_url': doc_url,
            'quality': quality, 'comparison': comparison,
            'checked_utc': datetime.now(timezone.utc).isoformat(),
            'status': 'Full research source, original age, relevance and quality-screen verified; verdict separate'}

def verification_order(queue, actors, state):
    """Interleave publisher queues so one large archive cannot monopolise verification."""
    actor_order = [a['id'] for a in interleaved_actors(list(actors.values()))]
    buckets = {name: [] for name in actor_order}
    for c in queue:
        if c.get('actor_id') in buckets:
            buckets[c['actor_id']].append(c)
    for bucket in buckets.values():
        # Prefer queued historical priority sources from the 15-minute stage;
        # otherwise favour 5–10-year-old work with other years still eligible.
        def priority_key(c):
            year=int((c.get('date_hint') or '0000')[:4]) if str(c.get('date_hint') or '')[:4].isdigit() else 0
            age=TODAY().year-year if year else 0
            preferred=5 <= age <= 10
            return (0 if c.get('source_mode','').startswith('curated retrospective priority') else 1,
                    0 if preferred else 1, abs(age-8) if age else 99, c.get('first_seen',''))
        bucket.sort(key=priority_key)
    offset = int(state.get('verification_cursor', 0)) % max(1, len(actor_order))
    ordered = actor_order[offset:] + actor_order[:offset]
    state['verification_cursor'] = (offset + 1) % max(1, len(actor_order))
    output = []
    while any(buckets.values()):
        for key in ordered:
            if buckets[key]:
                output.append(buckets[key].pop(0))
    return output


def retry_after(exc, today):
    """Short cooldown for network failures, longer for substantive rejections."""
    reason = str(exc).lower()
    transient = isinstance(exc, requests.RequestException) or any(
        word in reason for word in ('timed out', 'connection', 'http 429', 'http 502', 'http 503', 'http 504', 'too many redirects'))
    return (today + timedelta(days=2 if transient else 45)).isoformat()


def verify_until(deadline, once=False):
    actors = {a['id']: a for a in get_registry()}
    state = load_state()
    discovery = read_json(CANDIDATES) if CANDIDATES.exists() else {}
    database = read_json(RESULTS)
    reviews = read_json(ROOT / 'assessments.json')['assessments']
    review_map = {clean_url(r['report_url']): r for r in reviews}
    old = {clean_url(item['url']): item for item in database.get('findings', [])}
    rejections = []
    added = 0
    checked = 0
    today = TODAY()
    # The 15-minute phase produced a ranked, DOI-backed shortlist.
    # Spend real verification time on those academic leads before the publisher backlog.
    # Metadata checking does not certify the full study or a forecast's accuracy.
    priority_check_stats = {'checked': 0}
    if not once and (ROOT/'priority-50.json').exists():
        priority_check_stats = check_indexed_leads(min(deadline-60, time.monotonic()+200))
        refresh_priorities(today)
    # New human-supplied retrospective assessments are the one reason to
    # revisit an already accepted study: verify the exact original quotation.
    queued_urls = {clean_url(c['url']) for c in state['queue']}
    for key, report in old.items():
        needs_refresh = report.get('claim_extraction_version', 0) < CLAIM_VERSION
        needs_review = key in review_map and report.get('comparison', {}).get('verdict') == 'Not yet assessed'
        if (needs_refresh or needs_review) and key not in queued_urls:
            state['queue'].append({'url': key, 'actor_id': report['actor_id'],
                                   'title': report['title'], 'date_hint': report['date'],
                                   'topic': report.get('topic', 'EU strategic foresight'),
                                   'source_mode': 'historic catalogue seed (unverified)',
                                   'first_seen': today.isoformat()})
    # Keep unexamined reports in the queue for the next run, rather than
    # recreating the same candidate pool and starting from its first report.
    pending = verification_order(state['queue'], actors, state)
    remaining = []
    for index, candidate in enumerate(pending):
        if not once and time.monotonic() >= deadline - 2:
            remaining.extend(pending[index:])
            break
        key = clean_url(candidate['url'])
        previous = state['documents'].get(key, {})
        # Previously accepted papers are only revisited if a NEW editorial
        # assessment is available; the same PDF need not be downloaded again.
        needs_refresh = key in old and old[key].get('claim_extraction_version', 0) < CLAIM_VERSION
        if key in old and not needs_refresh and (key not in review_map or old[key].get('comparison', {}).get('verdict') != 'Not yet assessed'):
            state['documents'][key] = {'status': 'accepted', 'last_checked': today.isoformat(),
                                       'verifier_version': VERIFIER_VERSION}
            continue
        cooldown = previous.get('retry_after')
        # Editorial follow-up should not be blocked by an earlier network cooldown.
        editorial_update = key in old and key in review_map
        upgraded_recheck = (previous.get('status') == 'rejected' and
                            previous.get('reason', '').startswith('Quality gate failed') and
                            int(previous.get('verifier_version', 1)) < VERIFIER_VERSION)
        if cooldown and cooldown > today.isoformat() and not (editorial_update or upgraded_recheck):
            remaining.append(candidate)
            continue
        checked += 1
        print(f'VERIFY {checked}: {candidate.get("actor_id")} | {candidate.get("title", "")[:100]}', flush=True)
        try:
            report = verify_report(candidate, actors, review_map)
            if key not in old:
                added += 1
            old[clean_url(report['url'])] = report
            state['documents'][key] = {'status': 'accepted', 'last_checked': today.isoformat(),
                                       'verifier_version': VERIFIER_VERSION}
            print(f'ACCEPTED {candidate.get("actor_id")}: {candidate.get("title", "")[:100]}', flush=True)
        except Exception as exc:
            is_retrieval = isinstance(exc, (DocumentRetrievalError, requests.RequestException))
            retry = (today + timedelta(days=2)).isoformat() if is_retrieval else retry_after(exc, today)
            status = 'retrieval_failed' if is_retrieval else 'rejected'
            state['documents'][key] = {'status': status, 'last_checked': today.isoformat(),
                                       'retry_after': retry, 'reason': str(exc)[:250],
                                       'verifier_version': VERIFIER_VERSION}
            rejections.append({'actor': candidate.get('actor_id'), 'title': candidate.get('title'),
                               'url': key, 'reason': str(exc)[:250], 'retry_after': retry,
                               'status': status})
            print(f'{status.upper()} {candidate.get("actor_id")}: {str(exc)[:160]} '
                  f'(recheck after {retry})', flush=True)
    state['queue'] = remaining
    state['last_verification_utc'] = datetime.now(timezone.utc).isoformat()
    # Permanently drop any old out-of-window / unqualified records before writing.
    old = {k: x for k, x in old.items() if (START_DATE <= date.fromisoformat(x['date']) <= cutoff(today)
           and x.get('quality', {}).get('status') == 'automated research-substance screen passed'
           and x.get('actor_id') in actors)}
    results = sorted(old.values(), key=lambda x: (x['date'], x['id']), reverse=True)
    if (results != database.get('findings', [])
            or database.get('earliest_publication_date') != START_DATE.isoformat()):
        database['findings'] = results
        database['updated_at'] = today.isoformat()
        database['schema_version'] = 2
        database['scope'] = 'EU and independent European foresight retrospective (rolling 15 years; prioritise 5–10 years old)'
        database['minimum_age_months'] = 6
        database['earliest_publication_date'] = START_DATE.isoformat()
        atomic_json(RESULTS, database)
    atomic_json(STATE, state)
    reason_counts = {}
    status_counts = {}
    for rejected in rejections:
        reason = rejected['reason'].split(':')[0].strip()
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        status_counts[rejected['status']] = status_counts.get(rejected['status'], 0) + 1
    atomic_json(AUDIT, {'checked_utc': state['last_verification_utc'],
                        'cutoff': cutoff(today).isoformat(), 'earliest_publication_date': START_DATE.isoformat(),
                        'sources_scanned': discovery.get('sources_this_run', []),
                        'candidates_new': len(discovery.get('candidates_new', [])),
                        'checked_count': checked, 'backlog_remaining': len(state['queue']),
                        'new_reports': added, 'total_reports': len(results), 'rejected': rejections,
                        'rejection_reason_counts': reason_counts, 'outcome_counts': status_counts,
                        'discovery_source_status': discovery.get('source_status', []),
                        'scholarly_discovery': discovery.get('scholarly_discovery', {}),
                        'priority_metadata_checks': priority_check_stats,
                        'abstract_leads_total': len(read_json(ROOT / 'research-leads.json').get('leads', []))
                        if (ROOT / 'research-leads.json').exists() else 0})
    print(f'VERIFIED: {added} new historical reports; {len(results)} total; {checked} reviewed; '
          f'{len(rejections)} rejected; {len(state["queue"])} queued for future runs', flush=True)


def hold_open_until(deadline, stage, once=False, heartbeat_seconds=30):
    """Honor the full phase clock without retrying the same cooled-down URLs.

    The 15/10-minute stage durations are mandatory, not an 'up to' option.
    If unique work is exhausted early, we explicitly report that the phase is
    idle and remain open until its deadline. This is *not* fake discovery.
    Tests and manual diagnostic --once runs never sleep.
    """
    if once or not math.isfinite(deadline):
        return
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        print(f'{stage.upper()} window: {remaining:.0f}s remaining; '
              'eligible unique work exhausted; waiting, not repeating downloads.', flush=True)
        time.sleep(min(heartbeat_seconds, remaining))
    print(f'{stage.upper()} window completed (fixed duration).', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['discover', 'verify'])
    parser.add_argument('--minutes', type=float, default=None)
    parser.add_argument('--once', action='store_true', help='one pass for local test/diagnostics; production always uses timed cycles')
    args = parser.parse_args()
    minutes = args.minutes if args.minutes is not None else (15 if args.stage == 'discover' else 10)
    if minutes < 0:
        parser.error('--minutes cannot be negative')
    limit = time.monotonic() + minutes * 60
    if args.stage == 'discover':
        scholarly_stats = {}
        if not args.once:
            # Reserve up to 4 minutes within (not in addition to) 15-minute
            # scanning window for rotating bibliographic indexes.
            scholarly_stats = scholarly_scan(STATE, ROOT / 'research-leads.json', cutoff(TODAY()),
                                             min(limit, time.monotonic() + 240), max_queries=24)
        discover(limit, args.once)
        # Continue rotating distinct scholarly topic/year/journal combinations after
        # the publisher archives have exhausted their due URLs. Previously the
        # process merely slept for the remainder of the 15-minute phase.
        # scholarly_scan persists its cursor after each batch and never treats
        # abstract-index leads as verified research.
        if not args.once:
            batches = 0
            while time.monotonic() < limit - 25:
                before = time.monotonic()
                more = scholarly_scan(STATE, ROOT / 'research-leads.json',
                                     cutoff(TODAY()), min(limit - 8, before + 135),
                                     max_queries=16)
                batches += 1
                for field in ('queries', 'indexed_records_examined', 'new_leads', 'provider_errors'):
                    if field == 'provider_errors':
                        scholarly_stats.setdefault(field, []).extend(more.get(field, []))
                    else:
                        scholarly_stats[field] = scholarly_stats.get(field, 0) + more.get(field, 0)
                scholarly_stats['total_leads'] = more.get('total_leads', scholarly_stats.get('total_leads', 0))
                scholarly_stats['next_query_cursor'] = more.get('next_query_cursor')
                if not more.get('queries'):
                    print('No further index queries completed this batch; keeping a short retry delay.', flush=True)
                    time.sleep(min(12, max(0, limit - time.monotonic())))
                # A failed upstream index must not induce a rapid flood of requests.
                if more.get('provider_errors') and len(more['provider_errors']) >= more.get('queries', 0):
                    time.sleep(min(15, max(0, limit - time.monotonic())))
            scholarly_stats['additional_batches'] = batches
        refresh_priorities(TODAY())
        if scholarly_stats and CANDIDATES.exists():
            audit_discovery = read_json(CANDIDATES)
            audit_discovery['scholarly_discovery'] = scholarly_stats
            atomic_json(CANDIDATES, audit_discovery)
    else:
        verify_until(limit, args.once)
        refresh_priorities(TODAY())
    hold_open_until(limit, args.stage, args.once)
