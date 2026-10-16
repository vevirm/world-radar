#!/usr/bin/env python3
"""EU/European foresight retrospective — credible research, not news headlines.

DISCOVER: re-scan registered EU institutions, universities, independent think
tanks, research institutes, international bodies and EU-funded project sites
for 15 minutes. VERIFY for 10 minutes. Report publication MUST be 2015 or later
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
import os
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
AGENT = 'European-Foresight-Retrospective/3.0 (publisher and research verification)'
TIMEOUT = (5, 12)
TODAY = lambda: datetime.now(timezone.utc).date()
RESULTS = ROOT / 'findings.json'
CANDIDATES = ROOT / 'candidates.json'
AUDIT = ROOT / 'scan-report.json'
START_DATE = date(2015, 1, 1)
MIN_WORDS = 2600
MIN_PDF_PAGES = 8
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
            with session.get(url, headers={'User-Agent': AGENT, 'Accept': 'text/html,application/pdf;q=0.8'},
                             timeout=TIMEOUT, allow_redirects=False, stream=True) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    if not response.headers.get('Location'):
                        raise ValueError('Redirect has no Location header')
                    url = urljoin(url, response.headers['Location'])
                    continue
                response.raise_for_status()
                size = 12_000_000 if 'pdf' in response.headers.get('Content-Type', '').lower() or url.lower().split('?')[0].endswith('.pdf') else 2_500_000
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
        # Read the cover quickly for routine cataloguing; read deeper only when
        # a specific retrospective quote must be verified on another page.
        limit = min(len(reader.pages), 180 if full_pdf else 3)
        pages = [p.extract_text() or '' for p in reader.pages[:limit]]
        text = ' '.join(pages)[:1200000 if full_pdf else 30000]
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
    for match in re.finditer(r'\b(?:publication year|published in|©)\s*:?\s*(20\d\d)\b', visible[:10000], re.I):
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


def discovery_pass(actors, candidates, diagnostics, cycle, deadline):
    for actor in actors:
        if time.monotonic() >= deadline:
            break
        count = 0
        for seed in actor.get('seeds', []):
            d = parse_any_date(seed.get('date'))
            if (d is None or START_DATE <= d <= cutoff(TODAY())):
                c = {'title': seed['title'], 'url': clean_url(seed['url']), 'date_hint': d.isoformat() if d else None,
                     'topic': seed['topic'], 'source_mode': 'historic catalogue seed (unverified)'}
                candidates.setdefault(c['url'], dict(c, actor_id=actor['id']))
                count += 1
        for archive in actor['archives']:
            if time.monotonic() >= deadline:
                break
            try:
                url, raw, ctype = get_page(archive, set(actor['domain_hosts']))
                if raw[:4] == b'%PDF' or 'application/pdf' in ctype.lower():
                    raise ValueError('Archive must be HTML')
                found = candidates_from_archives(actor, url, page_info(raw, ctype))
                for c in found:
                    candidates.setdefault(c['url'], dict(c, actor_id=actor['id']))
                count += len(found)
                diagnostics.append({'cycle': cycle, 'actor': actor['id'], 'archive': archive, 'candidate_links': len(found)})
            except Exception as e:
                diagnostics.append({'cycle': cycle, 'actor': actor['id'], 'archive': archive, 'error': str(e)[:170]})
        diagnostics.append({'cycle': cycle, 'actor': actor['id'], 'listed_candidates': count})


def discover(deadline, once=False):
    actors = get_registry()
    candidates = {}
    diagnostics = []
    cycles = 0
    while time.monotonic() < deadline or (once and cycles == 0):
        cycles += 1
        discovery_pass(actors, candidates, diagnostics, cycles, deadline if not once else float('inf'))
        if once:
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(80, remaining))
    atomic_json(CANDIDATES, {'collected_at_utc': datetime.now(timezone.utc).isoformat(),
                              'six_month_cutoff': cutoff(TODAY()).isoformat(), 'earliest_publication_date': START_DATE.isoformat(), 'actor_count': len(actors),
                              'cycles': cycles, 'candidates': list(candidates.values()), 'source_status': diagnostics})
    print(f'DISCOVERED: {len(candidates)} possible historical reports from {len(actors)} EU/external registered publishers ({cycles} passes)', flush=True)


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


def source_excerpt(content):
    """Exact historical wording for readers, never an invented forecast."""
    phrases = re.split(r'(?<=[.!?])\s+(?=[A-Z])', content[:14000])
    cues = re.compile(r'\b(?:by 20[345]\d|until 20[345]\d|towards 20[345]\d|could|may|might|likely|expected to|projected|will (?:be|have|face|need)|scenario|outlook|future risks?)\b', re.I)
    for phrase in phrases:
        p = phrase.strip()
        if 65 <= len(p) <= 410 and cues.search(p) and not p.lower().startswith(('cookie', 'download')):
            return p
    return ''


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
    detail = {'quality_version': 1, 'word_count': total, 'distinct_terms': diverse_terms, 'pdf_pages': pages,
              'method_examples': sorted(methods)[:6], 'future_signal_count': futures,
              'citation_signals': {'bibliography_detected': bool(bibliography),
                                   'reference_years': cited_years, 'formal_citations': formal_cites},
              'checks': checks, 'status': 'automated research-substance screen passed' if all(checks.values()) else 'rejected'}
    if not all(checks.values()):
        failed = ', '.join(k for k, ok in checks.items() if not ok)
        raise ValueError('Quality gate failed: ' + failed)
    return detail


def full_document(url, info, raw, ctype, actor):
    """Obtain an actual research study, not its short news/marketing landing page.

    PDF links are host-allowlisted and tried individually. No arbitrary offsite
    redirects. If no accessible PDF exists a long, fully documented HTML
    research paper may pass independently.
    """
    if raw[:4] == b'%PDF' or 'application/pdf' in ctype.lower():
        return url, page_info(raw, ctype, full_pdf=True)
    choices = []
    for label, href in info['links']:
        target = clean_url(urljoin(url, href))
        if trusted_host(target) not in actor['domain_hosts']:
            continue
        path = urlparse(target).path.lower()
        if not path.endswith('.pdf'):
            continue
        # Prefer report full texts, then other linked PDFs; full-text quality
        # determines acceptance. URLs shown as sources must still pass checks.
        label_text = normal(label)
        rank = (4 if any(x in label_text for x in ('download', 'report', 'publication', 'full text', 'study')) else 0)
        rank += 3 if len(set(normal(info['titles'][0]).split()) & set(normal(label).split())) >= 2 else 0
        choices.append((rank, target))
    for _, target in sorted(set(choices), reverse=True)[:5]:
        try:
            doc_url, doc_data, doc_type = get_page(target, set(actor['domain_hosts']))
            if doc_data[:4] != b'%PDF':
                continue
            doc_info = page_info(doc_data, doc_type, full_pdf=True)
            # Don't attach arbitrary PDF downloads that happen to contain
            # generic method/citation language from an unrelated study.
            title_text = ' '.join(doc_info['titles'])
            if not title_match(info['titles'][0], title_text) and not title_match(info['titles'][0], doc_info['text'][:1400]):
                continue
            return doc_url, doc_info
        except Exception:
            continue
    # Full HTML analysis itself can qualify, but snippets never pass word/source gates.
    return url, info


def verify_report(candidate, actors, reviews):
    actor = actors[candidate['actor_id']]
    if trusted_host(candidate['url']) not in actor['domain_hosts']:
        raise ValueError('Candidate is not published on the registered author/publisher domain')
    url, raw, ctype = get_page(candidate['url'], set(actor['domain_hosts']))
    known_review = reviews.get(url) or reviews.get(candidate['url'])
    info = page_info(raw, ctype)
    if not any(title_match(candidate['title'], t) for t in info['titles']):
        raise ValueError('Title not corroborated by original publisher landing page or full text')
    published, precision, basis = select_publication_date(info, candidate.get('date_hint'))
    if not published:
        raise ValueError(basis)
    if published > cutoff(TODAY()):
        raise ValueError(f'Too recent: {published} (must be on/before {cutoff(TODAY())})')
    if published < START_DATE:
        raise ValueError('Publication predates 2015 minimum')
    if not (ARCHIVE_HINT.search(candidate['title']) or candidate.get('source_mode') == 'historic catalogue seed (unverified)'):
        raise ValueError('Not a discoverable foresight/futures-oriented study')
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
            'finding': excerpt, 'context': basis, 'url': url, 'full_text_url': doc_url,
            'quality': quality, 'comparison': comparison,
            'checked_utc': datetime.now(timezone.utc).isoformat(),
            'status': 'Full research source, original age, relevance and quality-screen verified; verdict separate'}

def verify_until(deadline, once=False):
    actors = {a['id']: a for a in get_registry()}
    contents = read_json(CANDIDATES)
    database = read_json(RESULTS)
    reviews = read_json(ROOT / 'assessments.json')['assessments']
    review_map = {clean_url(r['report_url']): r for r in reviews}
    old = {clean_url(item['url']): item for item in database.get('findings', [])}
    rejections = []
    checked = set()
    added = 0
    passes = 0
    pending = contents.get('candidates', [])
    # Prioritise 2+ year reports (the purpose is to look back).
    pending = sorted(pending, key=lambda c: (c.get('date_hint') is None,
                          c.get('date_hint') or '9999', c.get('actor_id', '')))
    while time.monotonic() < deadline or (once and passes == 0):
        passes += 1
        for candidate in pending:
            if not once and time.monotonic() >= deadline - 2:
                break
            key = clean_url(candidate['url'])
            # Re-check old findings only when there is a new editorial evidence comparison.
            if key in checked or (key in old and key not in review_map):
                continue
            checked.add(key)
            try:
                report = verify_report(candidate, actors, review_map)
                old[clean_url(report['url'])] = report
                if key not in {clean_url(x['url']) for x in database.get('findings', [])}:
                    added += 1
            except Exception as exc:
                rejections.append({'actor': candidate.get('actor_id'), 'title': candidate.get('title'),
                                   'url': key, 'reason': str(exc)[:250]})
        if once:
            break
        if time.monotonic() >= deadline:
            break
        time.sleep(min(50, deadline - time.monotonic()))
    # Permanently drop any old out-of-window / unqualified records before writing.
    # Age-cutoff changes daily; never allow a stale invalid item to survive.
    old = {k: x for k, x in old.items() if (START_DATE <= date.fromisoformat(x['date']) <= cutoff(TODAY())
           and x.get('quality', {}).get('status') == 'automated research-substance screen passed'
           and x.get('actor_id') in actors)}
    results = sorted(old.values(), key=lambda x: (x['date'], x['id']), reverse=True)
    if results != database.get('findings', []):
        database['findings'] = results
        database['updated_at'] = TODAY().isoformat()
        database['schema_version'] = 2
        database['scope'] = 'EU and independent European foresight retrospective (2015 onward)'
        database['minimum_age_months'] = 6
        database['earliest_publication_date'] = START_DATE.isoformat()
        atomic_json(RESULTS, database)
    atomic_json(AUDIT, {'checked_utc': datetime.now(timezone.utc).isoformat(),
                        'cutoff': cutoff(TODAY()).isoformat(), 'earliest_publication_date': START_DATE.isoformat(), 'passes': passes,
                        'candidate_count': len(pending), 'checked_count': len(checked),
                        'new_reports': added, 'total_reports': len(results), 'rejected': rejections,
                        'discovery_source_status': contents.get('source_status', [])})
    print(f'VERIFIED: {added} new historical reports; {len(results)} total; {len(rejections)} rejected; {passes} verification passes', flush=True)


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
        discover(limit, args.once)
    else:
        verify_until(limit, args.once)
