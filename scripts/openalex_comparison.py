"""OpenAlex literature-to-foresight comparisons, without an LLM subscription.

This is *not* automatic forecast verification: scholarly publications may evaluate
models, present scenarios or report empirical observations. We summarize only
explicitly published metadata/abstract text and keep the interpretation modest.
Research is built up incrementally; source links and missing evidence are retained.
"""
from __future__ import annotations

import datetime as dt
from collections import Counter, defaultdict
import http.client
import json
import os
import random
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

STOP = frozenset('''potential possible challenges challenge perspectives broad insights assessing impacts modelling modeled modelled implications towards evidence changes studies conceptual results consequences background review'''.split()) | frozenset('''the and for with from into this that these those their about among between after before over under of in on at by to a an is are was were as or how may might will can could study studies paper papers using use based results result effect effects assessment assessing towards toward developing development developed future futures scenario scenarios forecasting forecast projections projection foresight europe european europeans eu union impact impacts changes change dynamics long term novel new approach analysis policy policies research role perspective perspectives modelling modeling evidence possible review exploring investigation prospects challenge challenges looking through towards decades strategies strategic'''.split())
EU_WORDS = re.compile(r'\b(europe|european|eu|eu-27|eurostat|member states|european commission|european parliament|eur-lex)\b', re.I)
RESULTS = re.compile(r'\b(we find|we found|results (?:show|indicate|suggest|reveal)|our findings|our results|we observe|observed|measured|data show|has increased|have increased|has declined|have declined|we report|empirical (?:data|evidence)|has grown|have grown|we demonstrate)\b', re.I)
MODEL = re.compile(r'\b(scenario|projection|simulation|model(?:ling|ing)?|forecast|potential|might|could|hypothetical|possible pathways|expected to|by 20[2-9]\d)\b', re.I)
GENERIC_TERMS = frozenset('economic growth energy climate carbon market markets development sustainability environmental environment technology innovation modelling policies european Europe scenarios society systems system strategy regional international'.lower().split())
INSTITUTION = re.compile(r'\b(european commission|joint research centre|jrc|european environment agency|european parliament|european central bank|eurofound|ce[d]?efop|eu council|european court of auditors)\b', re.I)


def clean(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def tokens(text):
    return set(w for w in re.findall(r'[a-z][a-z0-9-]{3,}', clean(text).lower()) if w not in STOP)


def year(value):
    m = re.match(r'^((?:19|20)\d\d)', str(value or ''))
    return int(m.group(1)) if m else 0


def abstract_from_index(index):
    if not isinstance(index, dict):
        return ''
    positions = {}
    for word, offsets in index.items():
        if isinstance(offsets, list):
            for pos in offsets:
                if isinstance(pos, int) and 0 <= pos < 6000:
                    positions[pos] = word
    return clean(' '.join(word for _, word in sorted(positions.items())))[:5000]


def query_for(claim, route=0):
    """Use distinctive topic terms, not entire 250-character paper titles."""
    title = clean(claim.get('title'))
    terms = [w for w in re.findall(r'[a-z][a-z0-9-]{3,}', title.lower()) if w not in STOP]
    unique = list(dict.fromkeys(terms))
    # OpenAlex treats a plain multiword search essentially as AND. Six
    # arbitrary title words (the old default) overconstrain the search, so
    # try two compact topical routes instead of a nearly exact title search.
    distinctive = [w for w in unique if w not in GENERIC_TERMS]
    focus = distinctive or unique
    if route % 3 == 0:
        selected = focus[:4]
    elif route % 3 == 1:
        # A later paper may emphasize another part of a long original title.
        selected = (focus[-3:] if len(focus) > 3 else focus)
    else:
        extras = [w for w in re.findall(r'[a-z][a-z0-9-]{3,}',
                  clean(claim.get('candidate_excerpt') or claim.get('expected')).lower())
                  if w not in STOP and w not in GENERIC_TERMS]
        selected = list(dict.fromkeys((focus[:2] + extras[:3])))[:4]
    return ' '.join(selected) or ' '.join(title.split()[:5])


def request_works(query, since_year, timeout=20):
    """One modest OpenAlex API call, retries only transient failures."""
    if not query:
        return []
    params = {'search': query, 'per_page': 30,
              'filter': f'from_publication_date:{since_year}-01-01',
              'select': 'id,doi,title,publication_date,publication_year,abstract_inverted_index,cited_by_count,primary_location'}
    email = os.getenv('MAILTO', '').strip() or os.getenv('OPENALEX_EMAIL', '').strip()
    if '@' in email:
        params['mailto'] = email
    key = os.getenv('OPENALEX_API_KEY', '').strip()
    if key:
        params['api_key'] = key
    url = 'https://api.openalex.org/works?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        'User-Agent': f'WorldRadar-Radar2/4.0 ({email})' if '@' in email else 'WorldRadar-Radar2/4.0',
        'Accept': 'application/json', 'Accept-Encoding': 'identity'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                payload = json.loads(response.read())
            if not isinstance(payload.get('results'), list):
                raise ValueError('OpenAlex response has no results list')
            return payload['results']
        except urllib.error.HTTPError as exc:
            if exc.code not in (408, 500, 502, 503, 504):
                raise  # 400/401/403/429: surface configuration/quota issues
        except (http.client.IncompleteRead, http.client.RemoteDisconnected, ConnectionResetError,
                BrokenPipeError, socket.timeout, TimeoutError, urllib.error.URLError):
            pass
        if attempt < 2:
            time.sleep(min(5, 1.2 * 2**attempt) + random.uniform(0, .2))
    raise ConnectionError('OpenAlex was unavailable after three attempts')


def candidate_from_work(claim, work, origin='openalex_live'):
    """Return a related later study, or None when relationship is weak/unknown."""
    original_year = year(claim.get('original_publication'))
    pubyear = year(work.get('publication_date') or work.get('publication_year'))
    pub_date_string = clean(work.get('publication_date'))
    if len(pub_date_string) >= 10:
        try:
            if dt.date.fromisoformat(pub_date_string[:10]) > dt.date.today():
                return None
        except ValueError:
            return None
    if not original_year or not pubyear or pubyear < original_year or pubyear > dt.date.today().year:
        return None
    # Same-year later work is useful, especially for recent 2025/2026 papers.
    # Only permit it when both exact dates are available and chronologically
    # ordered; year-only metadata is not enough to establish what came later.
    if pubyear == original_year:
        original_stamp = clean(claim.get('original_publication'))
        if len(original_stamp) < 10 or len(pub_date_string) < 10:
            return None
        try:
            if dt.date.fromisoformat(pub_date_string[:10]) <= dt.date.fromisoformat(original_stamp[:10]):
                return None
        except ValueError:
            return None
    title = clean(work.get('title'))
    url = clean(work.get('doi') or work.get('url') or work.get('id'))
    original_url = clean(claim.get('source_url'))
    if not title or not url.startswith('https://') or url.rstrip('/').lower() == original_url.rstrip('/').lower():
        return None
    if title.casefold() == clean(claim.get('title')).casefold():
        return None
    abstract = abstract_from_index(work.get('abstract_inverted_index')) or clean(work.get('abstract'))
    # The query is topical; overlap must involve substantive *title* terms,
    # rather than repeated filler words such as "European" or "scenario".
    source_terms = tokens(claim.get('title'))
    found_terms = tokens(title)
    common = source_terms & found_terms
    if (len(common) < 2 or not (common - GENERIC_TERMS) or
            (len(common) < 3 and len(common) / max(1, min(len(source_terms), len(found_terms))) < .35)):
        return None
    euroness = bool(EU_WORDS.search(title + ' ' + abstract))
    # Require some evidence of European geographic relevance, unless the
    # original contains the identical substantive, highly specific subject.
    if not euroness and len(common) < 3:
        return None
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', abstract)
    observed = [s for s in sentences if RESULTS.search(s) and
                len((tokens(s) & source_terms) - GENERIC_TERMS) >= 1]
    # Do not quote an unrelated result merely because the paper title overlaps.
    # E.g. a study of carbon emissions could mention economic growth without
    # providing observed GDP evidence for an economic-growth projection.
    # This text is copied from the academic abstract. It is a claim made by
    # researchers, not a fact independently established by Radar 2.
    finding = clean(observed[0])[:360] if observed else ''
    kind = 'abstract_reports_results' if finding else 'related_study_or_model'
    date = clean(work.get('publication_date')) or str(pubyear)
    return {'title': title[:250], 'url': url, 'year': pubyear, 'date': date,
            'finding_from_abstract': finding,
            'study_type': kind, 'europe_mentioned': euroness,
            'shared_topic_terms': sorted(common),
            'source': origin,
            'cited_by_count': int(work.get('cited_by_count') or 0)}


def related(claim, works, origin='openalex_live', max_items=4):
    candidates = []
    seen = set()
    for work in works:
        item = candidate_from_work(claim, work, origin)
        if item and item['url'].rstrip('/').lower() not in seen:
            candidates.append(item)
            seen.add(item['url'].rstrip('/').lower())
    # Prefer direct topical overlap and studies reporting findings over models.
    candidates.sort(key=lambda x: (x['study_type'] == 'abstract_reports_results',
                    len(x['shared_topic_terms']), x['europe_mentioned'], x['year']), reverse=True)
    return candidates[:max_items]


def local_catalogue(claim, leads, max_items=4):
    """Reuse real indexed studies already in Scanner 1 (no live lookup claimed)."""
    works = ({'title': lead.get('title'), 'doi': lead.get('url'),
              'publication_date': lead.get('date'), 'abstract': lead.get('abstract'),
              'cited_by_count': 0} for lead in leads)
    return related(claim, works, origin='existing_scanner_catalogue', max_items=max_items)


# A later paper about the SAME ISSUE can be useful even if it does not reuse
# the original title. Keep these "field developments" separate from stronger
# title-matched candidate follow-ups and from observed real-world outcomes.
# Deliberately do not use a general theme ("climate", "technology") alone.
CONTEXT_STOP = frozenset("""what which who whom whose where when while also although however though moreover given may can could should shall would not very much more some other another any all each few many most only such these those within across through toward towards due since because for as with despite against impact impacts affecting affect associated including include use used using based known unknown data new emerging study studies studying case cases research result results effect effects influence influenced analysing analysis model models modeling modelling projections projected scenario scenarios future futures problem problems focus focuses explore exploring evaluate evaluated examination evidence method methodology findings finding found purpose aims aim factor factors general broad approach approaches current recent need needs make makes made both further important key associated perspective perspectives addition authors paper academic report reports preliminary assess assessing assessed compare comparison challenge challenges opportunities benefit benefits possible potential towards policy governance consider consideration have has had been being was were will would could should may might your there here where which whose when each any some many few very upon after before about global north south east west america american northern eastern southern western public private relative management security activity culture future situation significant performance role world state society examines examined investigation involved significant level levels several examples area areas concept concepts term terms state states country countries europe european union research publication publications associated future longterm long time period one two three four five data information complex existing proposed suggest suggests""".split())
# These are broad domains; a match needs more specificity than one of them.
CONTEXT_GENERIC = GENERIC_TERMS | CONTEXT_STOP

def contextual_terms(text):
    """Lightweight singularization to catch policies/policy, risks/risk etc."""
    result = set()
    for token in tokens(text):
        if token.endswith('ies') and len(token) > 5:
            token = token[:-3] + 'y'
        elif token.endswith('s') and not token.endswith(('ss', 'us', 'is')) and len(token) > 5:
            token = token[:-1]
        result.add(token)
    return result


def field_candidate(claim, work, *, origin='openalex_live', counts=None):
    """A plausible NEWER thematic paper. Not proof of a prediction or impact."""
    baseline = year(claim.get('original_publication'))
    pub_year = year(work.get('publication_date') or work.get('publication_year') or work.get('date'))
    if not baseline or not pub_year or pub_year < baseline or pub_year > dt.date.today().year:
        return None
    stamp = clean(work.get('publication_date') or work.get('date'))
    if len(stamp) >= 10:
        try:
            if dt.date.fromisoformat(stamp[:10]) > dt.date.today():
                return None
        except ValueError:
            return None
    if pub_year == baseline:
        original_stamp = clean(claim.get('original_publication'))
        if len(original_stamp) < 10 or len(stamp) < 10:
            return None
        try:
            if dt.date.fromisoformat(stamp[:10]) <= dt.date.fromisoformat(original_stamp[:10]):
                return None
        except ValueError:
            return None
    title = clean(work.get('title'))
    link = clean(work.get('doi') or work.get('url') or work.get('id'))
    if (not title or not link.startswith('https://') or
            link.lower().rstrip('/') == clean(claim.get('source_url')).lower().rstrip('/') or
            title.casefold() == clean(claim.get('title')).casefold()):
        return None
    source_title = contextual_terms(claim.get('title')) - CONTEXT_GENERIC
    candidate_title = contextual_terms(title) - CONTEXT_GENERIC
    source_subject = contextual_terms(claim.get('expected') or claim.get('abstract')) - CONTEXT_GENERIC
    abstract = abstract_from_index(work.get('abstract_inverted_index')) or clean(work.get('abstract'))
    candidate_subject = candidate_title | (contextual_terms(abstract) - CONTEXT_GENERIC)
    title_overlap = source_title & candidate_title
    topic_overlap = (source_title | source_subject) & candidate_subject
    # Minimum one distinctive term visible in both TITLES, two substantive
    # concepts spanning the texts. Avoid a single "climate" or "economic" word.
    # For unrelated papers about generic EU policy, no link is made.
    if len(title_overlap) < 2 or len(topic_overlap) < 2:
        return None
    # With only two shared title concepts, require an actual consecutive
    # subject phrase (e.g. "organic food", "carbon capture") rather than two
    # scattered terms like "power" and "Northern" in unrelated work.
    if len(title_overlap) == 2:
        def adjacent_pairs(text):
            words = re.findall(r'[a-z][a-z0-9-]{3,}', clean(text).lower())
            norm = lambda w: next(iter(contextual_terms(w)), w)
            return {(norm(a), norm(b)) for a, b in zip(words, words[1:])
                    if norm(a) in title_overlap and norm(b) in title_overlap}
        if not (adjacent_pairs(claim.get('title')) & adjacent_pairs(title)):
            return None
    original_theme, newer_theme = topic_cluster(claim), topic_cluster({'title': title})
    if (original_theme != 'Other European foresight research' and
            newer_theme != 'Other European foresight research' and original_theme != newer_theme
            and len(title_overlap) < 3):
        return None
    # Corpus frequency is useful when comparing a thousand saved entries; a
    # word appearing in almost every lead is a weak anchor.
    rare = title_overlap if counts is None else {w for w in title_overlap if counts.get(w, 0) <= 12}
    if not rare:
        return None
    # For topic-level updates, no requirement for European geography: a
    # worldwide development may help contextualize a Europe-focused question.
    # The user-facing label explicitly makes that distinction.
    finding = ''
    for sentence in re.split(r'(?<=[.!?])\s+(?=[A-Z])', abstract):
        if RESULTS.search(sentence) and len(contextual_terms(sentence) & topic_overlap) >= 1:
            finding = clean(sentence)[:320]
            break
    return {'title': title[:230], 'year': pub_year, 'date': stamp or str(pub_year),
            'url': link, 'finding_from_abstract': finding,
            'europe_mentioned': bool(EU_WORDS.search(title + ' ' + abstract)),
            'shared_topic_terms': sorted(topic_overlap), 'source': origin,
            'relationship': 'thematic_field_development_not_a_direct_followup',
            'study_type': 'abstract_reports_results' if finding else 'related_study_or_model',
            'relevance_strength': len(rare) * 3 + min(4, len(topic_overlap))}


def field_updates(claim, works, *, origin='openalex_live', max_items=4, counts=None):
    matches = {}
    for work in works:
        hit = field_candidate(claim, work, origin=origin, counts=counts)
        if hit:
            key = hit['url'].rstrip('/').casefold()
            prior = matches.get(key)
            if not prior or (hit['relevance_strength'], hit['year']) > (prior['relevance_strength'], prior['year']):
                matches[key] = hit
    ordered = sorted(matches.values(), key=lambda x: (x['relevance_strength'], x['year']), reverse=True)
    return ordered[:max_items]


class SavedLiteratureIndex:
    """One-time inverted index for thematic updates across all Scanner-1 leads."""
    def __init__(self, leads):
        self.works = []
        self.by_title_term = defaultdict(set)
        counts = Counter()
        for lead in leads:
            term_set = contextual_terms(lead.get('title')) - CONTEXT_GENERIC
            counts.update(term_set)
            i = len(self.works)
            self.works.append({'title': lead.get('title'), 'doi': lead.get('url'),
                               'publication_date': lead.get('date'), 'abstract': lead.get('abstract')})
            for term in term_set:
                self.by_title_term[term].add(i)
        self.counts = counts

    def find(self, claim, max_items=3):
        anchors = contextual_terms(claim.get('title')) - CONTEXT_GENERIC
        ids = set()
        for token in anchors:
            if self.counts.get(token, 0) <= 35:
                ids.update(self.by_title_term.get(token, ()))
        # Prefilter before abstract comparison; never search the entire
        # catalogue per item, and retain genuinely later papers only.
        return field_updates(claim, (self.works[i] for i in ids),
                             origin='existing_scanner_catalogue',
                             max_items=max_items, counts=self.counts)


def merge_publications(previous, incoming, *, max_items=6):
    """Do not erase an earlier good result because a later query was empty."""
    merged = {}
    for item in (previous or []) + (incoming or []):
        if not isinstance(item, dict) or not item.get('url'):
            continue
        key = item['url'].rstrip('/').casefold()
        old = merged.get(key)
        if not old or (bool(item.get('finding_from_abstract')), item.get('year') or 0) > (bool(old.get('finding_from_abstract')), old.get('year') or 0):
            merged[key] = item
    return sorted(merged.values(), key=lambda x: (bool(x.get('finding_from_abstract')), x.get('year') or 0), reverse=True)[:max_items]


# Narrow, explicitly low-confidence check for shared observable direction.
# This deliberately *does not* assign accuracy or success/failure scores.
MEASURES = {
    'flooding': r'\bflood(?:ing|s)?\b',
    'sea level': r'\bsea.level\b',
    'emissions': r'\bemissions?\b|\bco2\b',
    'employment': r'\bemployment\b|\bjobs?\b',
    'population': r'\bpopulation\b',
    'mortality': r'\bmortality\b|\bdeaths?\b',
    'temperature': r'\btemperatures?\b|\bwarming\b',
    'migration': r'\bmigration\b|\bimmigration\b',
    'renewables': r'\brenewable\b',
    'prices': r'\bprices?\b',
}
UP = re.compile(r'\b(increas(?:e|es|ed|ing)|r(?:ise|ises|ose|ising)|grew|grow(?:th|s|ing)?|higher|expanded?)\b', re.I)
DOWN = re.compile(r'\b(decreas(?:e|es|ed|ing)|declin(?:e|es|ed|ing)|fall(?:s|ing)?|fell|lower|reduc(?:e|es|ed|ing)|shrink)\b', re.I)
FORECAST_PHRASE = re.compile(r'\b(will|expect(?:ed)? to|project(?:ed)? to|forecast(?:s|ed)? to|predict(?:ed)? to)\b', re.I)


def direction(text):
    up, down = bool(UP.search(text)), bool(DOWN.search(text))
    return 1 if up and not down else -1 if down and not up else 0


def tentative_direction(claim, studies):
    """Find a *possible* agreement/tension in reported directions, not proof."""
    if claim.get('screening_status') != 'candidate_needs_validation':
        return 'not_a_validated_forecast', ''
    excerpt = clean(claim.get('candidate_excerpt'))
    expected_direction = direction(excerpt)
    if not FORECAST_PHRASE.search(excerpt) or not expected_direction:
        return 'insufficient_comparability', ''
    measures = {k for k, pat in MEASURES.items() if re.search(pat, excerpt, re.I)}
    if not measures:
        return 'insufficient_comparability', ''
    supported = []
    for study in studies:
        observed = clean(study.get('finding_from_abstract'))
        # Results of another projection are not observed historical change.
        if not observed or MODEL.search(observed):
            continue
        matched = [k for k in measures if re.search(MEASURES[k], observed, re.I)]
        later_direction = direction(observed)
        if later_direction and matched:
            supported.append((expected_direction == later_direction, study, matched))
    if not supported:
        return 'insufficient_comparability', ''
    aligned = sum(yes for yes, _, _ in supported)
    if 0 < aligned < len(supported):
        label = 'mixed_directional_clues'
    elif aligned:
        label = 'tentatively_consistent_direction'
    else:
        label = 'tentatively_in_tension'
    measures_used = ', '.join(sorted({m for _, _, ms in supported for m in ms}))
    return label, (f'{len(supported)} later scholarly abstract(s) use a similar directional term for '
                   f'{measures_used}. This is a LOW-CONFIDENCE wording comparison only; '
                   'methods, location, time period and real-world observation status have not been verified.')


TOPICS = (
    ('Climate and energy', r'\b(climate|carbon|emission|renewable|electricity|energy|solar|wind power|hydrogen|fossil|decarbon|ets)\b'),
    ('Economy and finance', r'\b(economic|economy|gdp|productivity|financial|inflation|investments?|trade|competitiveness|market|price)\b'),
    ('Population and work', r'\b(population|migration|immigration|demographic|workforce|employment|jobs|labou?r|aging|ageing)\b'),
    ('Technology and digital', r'\b(artificial intelligence|digital|robotic|information technology|ai governance|cyber|internet|innovation|ict)\b'),
    ('Environment and food', r'\b(water|flood|agricultur|food|biodivers|forest|ecosystem|soil|land use)\b'),
    ('Health and society', r'\b(health|mortality|hospital|disease|medical|education|wellbeing|poverty)\b'),
    ('Security and governance', r'\b(security|defen[cs]e|geopolitic|democra|foreign policy|public governance|regulation|strategic autonomy)\b'),
)


def topic_cluster(claim):
    text = clean(claim.get('title')).lower()
    for name, regex in TOPICS:
        if re.search(regex, text, re.I):
            return name
    return 'Other European foresight research'


def assess(claim, studies, search_mode='openalex_live'):
    """Provisional comparison, explicitly different from an accuracy verdict."""
    original = clean(claim.get('candidate_excerpt') or claim.get('expected') or claim.get('title'))
    has_pred = claim.get('screening_status') == 'candidate_needs_validation'
    relevant = len(studies)
    empirical = [x for x in studies if x.get('study_type') == 'abstract_reports_results' and x.get('finding_from_abstract')]
    if empirical:
        sample = empirical[:2]
        what_happened = ('Later scholarly abstracts report: ' + ' | '.join(
            f"{x['year']}: {x['finding_from_abstract']}" for x in sample))[:1050]
        signal = 'later_studies_report_results'
        assessment = (f'{relevant} related later studies found; {len(empirical)} contain result-like '
                      'abstract passages (which may describe models rather than real-world measurements). This suggests follow-up, but direction and comparability '
                      'with the earlier claim are not established.')
    elif studies:
        what_happened = (f'{relevant} related later studies were identified on this subject. '
                         'Their available abstracts do not provide directly comparable measured outcomes.')
        signal = 'later_research_without_comparable_outcome'
        assessment = 'The subject remains under research; no supported accuracy judgment can be drawn from these papers alone.'
    else:
        what_happened = 'No sufficiently close later study was identified in the available search results.'
        signal = 'no_comparable_study_found'
        assessment = 'OpenAlex coverage and query matching are incomplete; this is not evidence that a prediction failed.'
    directional_label, directional_note = tentative_direction(claim, studies)
    if directional_note:
        assessment += ' ' + directional_note
    if not has_pred:
        comparison = 'Original record is a research lead, not a validated dated forecast. This is a topic-level comparison.'
    else:
        comparison = ('Potential forecast excerpt is unverified. Related abstracts may use different baselines, '
                      'geographies, dates, methods and outcomes; no forecast-accuracy verdict is assigned.')
    institution_text = ' '.join((clean(claim.get('publisher')), clean(claim.get('title'))))
    origin = ('EU-institution attribution suggested by metadata; inspect source'
              if INSTITUTION.search(institution_text) else
              'EU institutional authorship NOT established (EU-related research is not necessarily EU Commission foresight)')
    return {
        'topic_cluster': topic_cluster(claim),
        'what_expected_literature': original[:1100],
        'what_happened_literature': what_happened,
        'literature_signal': signal,
        'tentative_direction': directional_label,
        'tentative_assessment': assessment,
        'comparison_limits': comparison,
        'eu_attribution': origin,
        'follow_up_publications': studies,
        'field_developments': [],  # populated separately; not direct matches
        'literature_search_mode': search_mode,
        'literature_assessed_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
    }
