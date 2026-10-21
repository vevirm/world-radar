"""One shared, conservative *relationship* policy for existing Radar 2 metadata.

This does not assess whether the original idea was true. It separates probable
same-question scholarship from comparative context and visibly bad automated
connections. The underlying original research, editorial notes and decisions
are never changed. No network requests.
"""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import urlsplit, unquote
try:
    from .question_evidence import issue_terms
except ImportError:
    from question_evidence import issue_terms

STATUS = re.compile(r'\b(?:withdrawn|retracted|retraction(?:\s+notice)?|expression of concern)\b', re.I)
EU = re.compile(r'\b(?:europe|european|eu|eurozone|european union|european countries)\b', re.I)
# Explicit *non-European* places in title: a different country is useful
# comparison, but not an answer to a specific Europe-wide question.
OTHER_REGION = re.compile(r'\b(?:russia|russian|vietnam|vietnamese|china|chinese|india|indian|'
    r'brazil|brazilian|latin america|latin american|mexico|mexican|colombia|colombian|'
    r'argentina|argentinian|peru|peruvian|australia|australian|new zealand|'
    r'japan|japanese|korea|korean|indonesia|indonesian|thailand|thai|'
    r'nigeria|nigerian|kenya|kenyan|pakistan|pakistani|morocco|moroccan|'
    r'california|united states|usa|u\.s\.|american|canada|canadian|iran|iranian)\b', re.I)
# Very wide concepts alone are insufficient evidence that research answers the
# *particular question*. They may still be helpful when paired with real anchors.
BROAD = set('''climate change future futures technology technologies policy policies
    risk risks impacts impact sector sectors systems system model models study studies
    education higher international development global research
    environment environmental energy european europe european union economic social
    methods method approach strategies strategy trends data public university
    universities governance evaluation assessment health science
    history histories historical introduction introductory background present past
    now current recent new future futures today tomorrow yesterday during after
    previous before shaping shape challenge challenges perspective perspectives
    view views debate debates question questions review outlook sector sectors
    institution institutions relationship relationships effect effects cause causes
    consequence consequences study paper journal volume thematic topic subject
    insight insights literature theoretical practical empirical synthetic conceptual
    structural analytical policy-making political social societal cultural culture
    regulation regulatory public regional region area areas spatial temporal
    time real realtime real-time long short transformation alternative alternatives
    comparison comparing comparable comparative general particular innovative
    innovation innovative strategies strategy working work framework frameworking
    roles role implications implication impact impacts development developing
    management managing applied approaches approach result results solution solutions
    implementing implementation integration independent international cooperation
    country countries nationwide worldwide national state states governance strategy
    trends trends future historical assessment validity discussion discourse
    chance opportunities opportunity international affairs security preparedness
    emerging changing changed changes change trajectories dynamics dynamic
    performance sustainability sustainable resistance resilient resilience
    science scientific complexity complex practice practices example examples
    experience experiences use uses usage utilized using utilization
    cost costs analysis analyses problems problem adoption evaluated evaluate
    evidence forecast forecasting foresight predictions projection model models
    modelling modeling uncertainty uncertainty-related expected potentially
    applications application using methodological method methods technique
    consequences assessment evaluation conditions context contexts based
    reasons reason values value effects effect initiative perspective
    animal aspect aspects pros cons major other others three one two a few
    human people first second final related nation nations importance greater
    widespread direction effects effect opportunities possible emerging extreme
    reflection reflections issue interdisciplinary across field sector parts part
    real-world ecosystem ecosystems integration disintegration presentation
    involved intended per every
    '''.split())


def _year(raw):
    found = re.search(r'\b(?:19|20)\d\d\b', str(raw or ''))
    return int(found.group()) if found else 0


def canonical_url(url):
    url = str(url or '').strip()
    if not url.startswith('https://'):
        return ''
    p = urlsplit(url)
    host = p.netloc.casefold().removeprefix('www.')
    path = unquote(p.path).strip('/').casefold()
    if host in ('doi.org', 'dx.doi.org'):
        return 'doi:' + path
    return host + '/' + path + ('?' + p.query if p.query else '')


def _tokens(text):
    return issue_terms(str(text or ''))


def _same_work(old, later):
    a, b = _tokens(old), _tokens(later)
    a_plain = re.sub(r'[^a-z0-9]+', ' ', str(old).casefold()).strip()
    b_plain = re.sub(r'[^a-z0-9]+', ' ', str(later).casefold()).strip()
    if len(a_plain) >= 35 and a_plain in b_plain and any(
            word in b_plain for word in ('peer review report', 'faculty opinion',
                'recommendation of', 'version 2 peer review')):
        return True
    # Publisher recommendation notices can reproduce the exact original title
    # with a generic prefix; they are NOT new independent studies.
    enriched = bool(a and b and len(a & b) >= 4 and
                    (len(a & b) / len(a) >= .9 and len(b - a) <= 4))
    return bool(a and b and (a == b or enriched or
                (len(a & b) >= 5 and len(a & b) / len(a | b) >= .88)))


def classify(entry, item, field):
    """Return (direct|context|quarantine, reason).

    `direct` still means *candidate same-issue research*, never proven reality.
    `context` means the study may help comparison but must NOT drive NOW/ranks.
    """
    if not isinstance(item, dict):
        return 'quarantine', 'malformed_link'
    title = str(item.get('title') or '').strip()
    url = canonical_url(item.get('url'))
    if not title or not url:
        return 'quarantine', 'missing_title_or_url'
    if item.get('is_retracted') is True or item.get('is_withdrawn') is True or STATUS.search(title):
        return 'quarantine', 'retracted_or_withdrawn'
    old_title = str(entry.get('title') or entry.get('expected') or '')
    explicitly_different_region = bool(EU.search(old_title) and OTHER_REGION.search(title) and not EU.search(title))
    if canonical_url(entry.get('source_url')) == url or (_same_work(old_title, title) and not explicitly_different_region):
        return 'quarantine', 'same_original_or_republication'
    original_year = _year(entry.get('original_publication') or entry.get('year'))
    new_year = _year(item.get('date') or item.get('year'))
    if new_year and (new_year > date.today().year or (original_year and new_year < original_year)):
        return 'quarantine', 'wrong_publication_date'
    if new_year and new_year == original_year:
        old_date = str(entry.get('original_publication') or '')[:10]
        new_date = str(item.get('date') or '')[:10]
        if not (re.fullmatch(r'\d{4}-\d\d-\d\d', old_date) and
                re.fullmatch(r'\d{4}-\d\d-\d\d', new_date) and new_date > old_date):
            return 'quarantine', 'not_demonstrably_later'
    original = _tokens(old_title)
    title_terms = _tokens(title)
    finding = str(item.get('finding_from_abstract') or item.get('abstract_excerpt') or '')
    full_terms = title_terms | _tokens(finding)
    shared_title = original & title_terms
    shared = original & full_terms
    specific_title = shared_title - BROAD
    specific_full = shared - BROAD

    mismatch = bool(EU.search(old_title) and OTHER_REGION.search(title) and
                    not EU.search(title))
    # A non-EU region named in the *later title* cannot be rescued by an
    # incidental mention of the EU in the later abstract.
    if mismatch:
        if specific_full and len(shared) >= 2:
            return 'context', 'different_geography'
        return 'quarantine', 'different_geography_and_weak_topic'
    if item.get('geography') == 'other_region':
        return 'context', 'different_geography'

    # This field explicitly collects wider/indirect reading. Don't upgrade it
    # automatically to observed change just because it has a shared title.
    if field == 'field_developments':
        # A preceding run may have downgraded this to context. Keep the
        # decision stable, provided publication status/date remain valid.
        if item.get('evidence_role') == 'related_context' and item.get('context_reason'):
            return 'context', item['context_reason']
        if (specific_title and len(shared) >= 2) or len(specific_full) >= 2:
            return 'context', 'broader_field_development'
        return 'quarantine', 'too_loose_for_field_context'

    # Require a topic-specific anchor, not only a research method or words
    # like "higher education" or "climate change".
    if not specific_full:
        if len(shared_title) >= 2:
            return 'context', 'same_broad_subject_only'
        return 'quarantine', 'no_specific_shared_issue'
    original_specific = original - BROAD
    shared_specific_title = original_specific & title_terms
    strong_coverage = len(shared_specific_title) / max(1, len(original_specific))
    # A concise one-topic question can be followed by another concise title;
    # wider, multi-part questions need at least two real subject anchors.
    close_question = ((len(original_specific) <= 2 and len(shared_specific_title) >= 1)
                      or (len(shared_specific_title) >= 2 and strong_coverage >= .35)
                      or len(shared_specific_title) >= 4)
    if close_question and (len(shared_title) >= 2 or len(shared_specific_title) >= 2):
        return 'direct', 'same_issue_title'
    if (len(shared_specific_title) >= 1 and len(shared) >= 2 and
        len(shared_specific_title) >= min(2, len(original_specific)) and strong_coverage >= .4):
        return 'direct', 'same_issue_title_and_abstract'
    if len(specific_full) >= 2 and len(shared) >= 3:
        return 'context', 'issue_only_in_abstract'
    if specific_title:
        return 'context', 'one_topic_anchor'
    return 'quarantine', 'insufficient_topic_connection'
