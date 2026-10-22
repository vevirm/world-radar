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
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup
from radar1_admission import POLICY_VERSION, decision

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
    'European Commission Joint Research Centre foresight scenarios',
    'European Parliamentary Research Service policy foresight',
    'Cedefop European skills forecast', 'Eurofound future of work scenarios',
    'European Environment Agency long term outlook',
    'ESPAS Europe strategic foresight global trends',
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

# Stage-one research-scope triage, NOT evidence validation or a truth score.
# Careful word-sense distinctions matter: traded "futures" are not futures studies,
# and reconstructing a historic scenario is not projecting a future development.
TRADING = re.compile(
    r'\b(?:futures? (?:markets?|prices?|pricing|contracts?|trading|returns?|yields?|volatility|options?)|'
    r'commodit(?:y|ies) futures?|spot.futures|'
    r'(?:hedg\w*|arbitrag\w*).{0,28}futures?|'
    r'(?:carbon|electricity|grain|stock|bond|oil|wheat|currency|gas|energy|index) futures?'
    r'(?:\s+(?:market|prices?|contract|trading|returns?|options?)))\b', re.I)
# Narrow exclusions for false friends of *foresight*. Contract-market futures
# and consensus-building Delphi are not long-term EU foresight by default.
FINANCIAL_FUTURES_TITLE = re.compile(
    r'\b(?:electricity|carbon|oil|gas|grain|stock|bond|currency|commodity|emission\s+allowances?)\s+futures?\b', re.I)
CLINICAL_CONSENSUS = re.compile(
    r'\b(?:Delphi|consensus)\b.*\b(?:guidelines?|recommendations?|curricul\w+|competencies|questionnaire|statements|clinical|care)\b|'
    r'\b(?:guidelines?|recommendations?|curricul\w+|competencies|questionnaire|statements|clinical|care)\b.*\b(?:Delphi|consensus)\b', re.I)
FUTURE_OVERRIDE = re.compile(
    r'\b(?:strategic foresight|future of|horizon scanning|scenarios? (?:for|to|of)\s+20[2345]\d|'
    r'policy pathways?|future scenarios?|by 20[2345]\d|in 20[2345]\d)\b', re.I)
RESEARCH_PREVIEW = re.compile(
    r'\b(?:foresight|horizon scanning|backcast\w*|delphi|prospectiv\w*|'
    r'forecast\w*|projections?|predict\w*|scenario\w*|'
    r'future(?:s)?|anticipat\w*|outlook|pathways?|visions?|'
    r'by 20[2345]\d|towards? 20[2345]\d|to 20[2345]\d)\b', re.I)
STRONG_FUTURE = re.compile(
    r'\b(?:foresight|scenario\w*|forecast\w*|projections?|'
    r'future of|alternative futures|future pathways?|horizon scanning|'
    r'backcast\w*|long.term outlook|anticipator\w*|'
    r'by 20[2345]\d|towards? 20[2345]\d)\b', re.I)
HISTORIC_ONLY = re.compile(
    r'\b(?:archaeolog\w*|prehistor\w*|palaeoclimat\w*|paleoclimat\w*|'
    r'colonial era|colonial southeast asia|ancient dna|genome.wide.*colonization|' 
    r'history of .*futures trad\w*|1960s.1980s|'
    r'scenarios? of (?:European )?colonization|'
    r'origin and diversification of .*breeds?)\b', re.I)
HISTORY_FORWARD = re.compile(
    r'\b(?:future climate|future distribution|climate change scenarios|'
    r'climate projections?|by 20[2345]\d|future warming)\b', re.I)
# An ordinary short-horizon prediction (for instance a loan-default classifier)
# is not automatically an EU strategic foresight scenario. Metadata-only leads
# remain reviewable rather than being destroyed.
OPERATIONAL_FORECAST = re.compile(
    r'\b(?:loan default|stock price|radiation belts?|ionospheric perturbations?|'
    r'predict(?:ing|ion) (?:the )?phenology|short.term weather forecast|'
    r'credit scoring|time.series employment|forecast time series)\b', re.I)
OTHER_REGION_TITLE = re.compile(
    r'\b(?:east africa|west africa|australia|vietnam|iran|india|china|'
    r'canada|brazil|latin america)\b', re.I)

PARATEXT_TITLE = re.compile(
    r'^(?:review:|peer review report|book review|editorial|preface|'
    r'corrigendum|erratum|retraction notice|thematic issue presentation|' 
    r'introduction to (?:the )?special issue)\b', re.I)
HISTORIC_PROJECTION_OF_POWER = re.compile(r'\bprojections of power\b', re.I)


def foresight_scope(lead):
    """Conservative (scope, reason) for whether a work belongs in Radar 1.

    Does not assess accuracy. 'needs_review' preserves potentially useful works.
    Only unambiguous false friends are excluded from future-focused priorities.
    """
    title = str(lead.get('title') or '').strip()
    abstract = str(lead.get('abstract') or '').strip()
    if not title:
        return 'needs_review', 'title_missing'
    if PARATEXT_TITLE.search(title) or re.search(r'[\s:–-]preface\s*$', title, re.I):
        return 'out_of_scope', 'review_editorial_or_correction'
    if FINANCIAL_FUTURES_TITLE.search(title) and not FUTURE_OVERRIDE.search(title):
        return 'out_of_scope', 'financial_futures_contracts_not_societal_foresight'
    if CLINICAL_CONSENSUS.search(title) and not FUTURE_OVERRIDE.search(title):
        return 'needs_review', 'clinical_delphi_consensus_not_automatically_future_foresight'
    if TRADING.search(title):
        # A long-range socioeconomic projection about market development could
        # still be pertinent, but mere carbon/electricity futures trading isn't.
        if re.search(r'\b(?:long.term|2030|2040|2050|scenario planning|' 
                     r'future of (?:energy|society|policy))\b', title, re.I):
            return 'needs_review', 'market_instrument_with_possible_forward_question'
        return 'out_of_scope', 'financial_futures_instrument_not_foresight'
    if HISTORIC_PROJECTION_OF_POWER.search(title):
        return 'out_of_scope', 'historical_projection_of_power_not_forecast'
    if OTHER_REGION_TITLE.search(title) and not EUROPE.search(title):
        return 'needs_review', 'non_european_focus_in_title'
    if OPERATIONAL_FORECAST.search(title) and not re.search(r'\b(?:2030|2040|2050|policy scenarios?|long.term)\b', title, re.I):
        return 'needs_review', 'operational_forecast_without_long_term_foresight_context'
    if HISTORIC_ONLY.search(title) and not HISTORY_FORWARD.search(title):
        # Archaeology and history can itself concern possible futures.
        # Keep it for review rather than discard it on vocabulary alone.
        return 'needs_review', 'historical_topic_future_relevance_uncertain'
    # A clear title indicates an original futures-oriented research question.
    # Scenario modelling and forecasts count even without measurable verdicts.
    if STRONG_FUTURE.search(title):
        return 'future_facing', 'future_question_in_title'
    if RESEARCH_PREVIEW.search(title):
        return 'future_facing', 'forward_looking_title'
    # Abstracts can describe futures questions even if titles do not.
    if STRONG_FUTURE.search(abstract):
        return 'needs_review', 'future_question_only_in_abstract'
    return 'needs_review', 'foresight_relevance_not_established_from_metadata'

# Radar 1 has TWO separate questions: is the work actually forward-looking,
# and what is its relationship to EU policy/geography/institutions?
# A study mentioning a EU grant, having a European-sounding journal title or
# being co-authored by an EU researcher is NOT automatically EU-issued.
EU_INSTITUTION = re.compile(
    r'\b(?:European Commission|Joint Research Centre|European Parliament|'
    r'European Parliamentary Research Service|European Council|Council of the European Union|'
    r'European Environment Agency|European Central Bank|European Investment Bank|'
    r'European Union Institute for Security Studies|EU Institute for Security Studies|'
    r'European Centre for the Development of Vocational Training|Cedefop|'
    r'European Foundation for the Improvement of Living and Working Conditions|'
    r'Eurofound|European Medicines Agency|European Food Safety Authority|'
    r'European Training Foundation|European Strategy and Policy Analysis System|'
    r'European Union Agency|ESPAS|EU Policy Lab|DG [A-Z]{2,7})\b', re.I)
EU_SUBJECT = re.compile(
    r'\b(?:European Union|European (?:Commission|Parliament|countries|member states|'
    r'policy|policies|integration|higher education|labour market|labor market|'
    r'energy system|economy|climate|mobility|agriculture|future|regions?)|'
    r'EU(?:-?27|-?28)?|Europe(?:an)?|Eurozone|Erasmus\+?|Horizon Europe|'
    r'EU ETS|Common Agricultural Policy|European Green Deal|Schengen)\b|'
    r'(?<![A-Za-z])E\.U\.(?![A-Za-z])', re.I)
NON_EU_TITLE = re.compile(
    r'\b(?:North America|South America|Latin America|United States|USA|'
    r'Russian Federation|Russia|Vietnam|China|India|Brazil|Australia|'
    r'Canada|Iran|East Africa|West Africa|South Africa|Japan)\b', re.I)


def _official_eu_host(url):
    try:
        host = (urlparse(str(url or '')).hostname or '').lower().rstrip('.')
    except ValueError:
        return False
    return (host == 'europa.eu' or host.endswith('.europa.eu') or
            host in {'espas.eu', 'www.espas.eu'})


def eu_connection(lead):
    """Independent Radar 1 EU-interest tier; never a quality/truth verdict.

    eu_official       original URL is on an official EU institutional site
    eu_institution    indexed publisher/affiliation reports EU institutional role;
                      not source-verified, and affiliation != commissioned study
    eu_focused        EU/Europe is central to the title
    eu_related        EU/Europe appears in the abstract or policy context
    review            absent or uncertain EU connection

    No studies are deleted by this classification.
    """
    title = str(lead.get('title') or '')
    abstract = str(lead.get('abstract') or '')
    publisher = str(lead.get('publisher') or '')
    official = _official_eu_host(lead.get('url'))
    if official:
        return 'eu_official', 'official_EU_publisher_url'
    if EU_INSTITUTION.search(publisher):
        return 'eu_institution', 'EU_issuer_named_in_publisher_metadata_unverified'
    affiliations = lead.get('institutional_affiliations') or []
    if isinstance(affiliations, str):
        affiliations = [affiliations]
    if any(EU_INSTITUTION.search(str(name)) for name in affiliations):
        return 'eu_institution', 'EU_affiliation_in_index_not_EU_issued'
    # A paper comparing EU and non-EU regions matters to EU foresight, but
    # should not be prioritized as a study exclusively focused on Europe.
    if NON_EU_TITLE.search(title):
        if EU_SUBJECT.search(title):
            return 'eu_related', 'comparative_multi_region_title_including_EU'
        return 'review', 'non_EU_title_EU_relevance_uncertain'
    if EU_SUBJECT.search(title):
        return 'eu_focused', 'EU_or_Europe_in_original_title'
    if EU_SUBJECT.search(abstract):
        return 'eu_related', 'EU_or_Europe_in_abstract_only'
    return 'review', 'no_clear_EU_link_in_indexed_metadata'


# Radar 1 originals are a FIXED historical cohort. Newer literature belongs to Radar 2.
HISTORICAL_START = date(2011, 1, 1)
HISTORICAL_END = date(2023, 12, 31)

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
    eu_affiliations = sorted({inst.get('display_name', '')
                              for author in (item.get('authorships') or [])
                              for inst in (author.get('institutions') or [])
                              if inst.get('display_name') and EU_INSTITUTION.search(inst['display_name'])})
    return {'doi': doi, 'title': strip_markup(item.get('title')),
            'abstract': unfold_abstract(item.get('abstract_inverted_index')),
            'institutional_affiliations': eu_affiliations,
            'date': published, 'journal': source.get('display_name') or 'Other scholarly source',
            'publisher': (source.get('host_organization_name') or ''),
            'url': 'https://doi.org/' + doi, 'indexes': ['OpenAlex'],
            'open_access_pdf': pdf}


def credible_abstract(lead, earliest, latest):
    try:
        published = date.fromisoformat(lead['date'])
    except (KeyError, ValueError, TypeError):
        return False
    if not max(earliest, HISTORICAL_START) <= published <= min(latest, HISTORICAL_END):
        return False
    title = lead.get('title') or ''
    abstract = lead.get('abstract') or ''
    combined = title + ' ' + abstract
    # Journal standing or an API search hit is NOT evidence of topical relevance.
    if not EUROPE.search(combined) or not FUTURES.search(combined):
        return False
    if LOW_SUBSTANCE.search(title) or foresight_scope(lead)[0] == 'out_of_scope':
        return False
    if len(abstract.split()) < MIN_ABSTRACT_WORDS:
        return False
    # Do not keep admitting new non-EU studies solely because a generic abstract
    # mentions Europe while the actual title is about a different jurisdiction.
    return eu_connection(lead)[0] != 'review'


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
    if not max(earliest, HISTORICAL_START) <= published <= min(latest, HISTORICAL_END) or LOW_SUBSTANCE.search(title) or foresight_scope(lead)[0] == 'out_of_scope':
        return False
    if len(title.split()) < 6 or not normal_doi(lead.get('doi')):
        return False
    return bool(EUROPE.search(title) and FUTURES.search(title)
                and eu_connection(lead)[0] != 'review')


def lead_status(lead):
    return ('Abstract indexed — full study unverified'
            if len((lead.get('abstract') or '').split()) >= MIN_ABSTRACT_WORDS
            else 'DOI/title indexed — abstract not in metadata')


def year_windows(latest):
    # Fixed historical period. Do not slowly drift into 2024, 2025, etc.
    latest = min(latest, HISTORICAL_END)
    result = []
    for y in range(HISTORICAL_START.year, latest.year + 1, 2):
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
    if new.get('institutional_affiliations'):
        obj['institutional_affiliations'] = sorted(set(obj.get('institutional_affiliations', [])) |
                                                set(new['institutional_affiliations']))
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


def load_rejection_registry(path):
    """Small persistent DOI registry shared with the no-scan audit workflow."""
    if not path.exists():
        return {'schema_version': 1, 'policy_version': POLICY_VERSION, 'rejected': {}}
    saved = json.loads(path.read_text(encoding='utf-8'))
    if saved.get('schema_version') != 1 or not isinstance(saved.get('rejected'), dict):
        raise ValueError('Unsupported Radar 1 DOI rejection registry; refusing to scan')
    return saved


def closer_abstract_check(lead, key=None):
    """One bounded follow-up lookup when an otherwise plausible title is unclear.

    Crossref often lacks a deposited abstract even where OpenAlex has one.
    Never substitutes generic web snippets or publisher names for study content.
    Network problems leave the work uncertain and therefore not admitted.
    """
    doi = normal_doi(lead.get('doi'))
    if not doi or lead.get('abstract'):
        return lead
    params = {'filter': f'doi:https://doi.org/{doi}', 'per_page': 1}
    if key:
        params['api_key'] = key
    try:
        r = requests.get(OPENALEX, params=params, timeout=REQUEST_TIMEOUT,
                         headers={'User-Agent': 'European-Foresight-Radar/4.0 (DOI abstract check)'})
        r.raise_for_status()
        results = r.json().get('results') or []
        if results:
            desc = unfold_abstract(results[0].get('abstract_inverted_index'))
            if desc:
                updated = dict(lead)
                updated['abstract'] = desc
                updated['indexes'] = sorted(set(lead.get('indexes') or []) | {'OpenAlex'})
                return updated
    except (requests.RequestException, ValueError, TypeError, KeyError):
        pass
    return lead


def scholarly_scan(state_path, leads_path, latest, deadline, *, max_queries=24):
    """Search distinct topic/year/index combinations; persist state each run.

    Queries may fail independently; a response error never masquerades as a
    scientifically rejected document. The original state history is preserved.
    """
    from_date = HISTORICAL_START
    latest = min(latest, HISTORICAL_END)
    state = json.loads(Path(state_path).read_text(encoding='utf-8')) if Path(state_path).exists() else {
        'schema_version': 1, 'runs': 0, 'source_cursor': 0, 'verification_cursor': 0,
        'archive_pages': {}, 'documents': {}, 'queue': []}
    saved = load_leads(Path(leads_path))
    reject_path = Path(leads_path).with_name('radar1-rejected.json')
    registry = load_rejection_registry(reject_path)
    excluded = registry['rejected']
    records = {}
    for row in saved['leads']:
        doi = normal_doi(row.get('doi'))
        if not doi or doi in excluded:
            continue
        accepted, reason, _ = decision(row)
        if accepted:
            records[doi] = row
        else:
            excluded[doi] = {'reason': reason, 'year': str(row.get('date', ''))[:4]}
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
    rejected_count = 0
    closer_checks = 0
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
                doi = normal_doi(lead.get('doi'))
                if not doi or doi in excluded:
                    continue
                accepted, reason, check = decision(lead)
                # Check a plausible unknown once more, without making each
                # scheduled run spend its full duration chasing weak titles.
                if (not accepted and not lead.get('abstract') and
                        reason == 'ambiguous_title_no_supporting_abstract' and
                        closer_checks < 8 and time.monotonic() < deadline - 25):
                    closer_checks += 1
                    lead = closer_abstract_check(lead, key)
                    accepted, reason, check = decision(lead)
                if not accepted:
                    excluded[doi] = {'reason': reason, 'year': str(lead.get('date', ''))[:4]}
                    rejected_count += 1
                    topic_or_date_filtered += 1
                    continue
                if check == 'title_only_clear':
                    title_only_count += 1
                if doi not in records:
                    new += 1
                merged = merge_lead(records.get(doi), lead, now)
                accepted, reason, check = decision(merged)
                if not accepted:
                    excluded[doi] = {'reason': reason, 'year': str(merged.get('date', ''))[:4]}
                    records.pop(doi, None)
                    rejected_count += 1
                    continue
                merged['radar1_selection'] = 'active'
                merged['radar1_admission_version'] = POLICY_VERSION
                merged['radar1_admission_reason'] = reason
                merged['source_period'] = 'historical_original'
                records[doi] = merged
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
    # Only admitted historical originals are physically present in Radar 1.
    # Rejections persist, preventing later rediscovery from re-adding the junk.
    newest = sorted(records.values(), key=lambda r: (r.get('last_seen', ''), r['doi']), reverse=True)[:MAX_LEADS]
    leads = sorted(newest, key=lambda r: (r['date'], r['doi']))
    for row in leads:
        row['source_period'] = 'historical_original'
        row['radar1_selection'] = 'active'
        row['radar1_admission_version'] = POLICY_VERSION
        row['foresight_scope'], row['foresight_scope_reason'] = foresight_scope(row)
        row['foresight_scope_version'] = 1
        row['eu_connection'], row['eu_connection_reason'] = eu_connection(row)
        row['eu_connection_version'] = 1
    registry['policy_version'] = POLICY_VERSION
    registry['rejected'] = dict(sorted(excluded.items()))
    atomic_json(reject_path, registry)
    atomic_json(Path(leads_path), {'schema_version': 1, 'updated_at': now,
                'status': 'Journal leads from DOI/title and available abstracts; full text and forecasts unverified',
                'admission_policy_version': POLICY_VERSION, 'leads': leads})
    result = {'queries': requests_made, 'indexed_records_examined': examined,
              'records_without_abstract': abstract_missing,
              'records_outside_topic_or_date': topic_or_date_filtered,
              'title_only_leads': title_only_count,
              'closer_abstract_checks': closer_checks, 'newly_rejected_dois': rejected_count,
              'total_rejected_dois': len(excluded),
              'new_leads': new, 'total_leads': len(leads),
              'provider_errors': errors[:20], 'openalex_configured': bool(key),
              'next_query_cursor': state['scholarly_cursor']}
    print(f'SCHOLAR SUMMARY: {result}', flush=True)
    return result
