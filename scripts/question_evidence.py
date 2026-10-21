"""Issue-first, deliberately modest signals for the living futures atlas.

Classifies *published abstracts*, not truth. A paper about an unrelated country,
method, or another forecast is not an observation about the original question.
The purpose is to recover useful directional signals without requiring a verdict.
"""
from __future__ import annotations

import datetime as dt
import re
try:
    from .openalex_comparison import clean, contextual_terms, abstract_from_index, year
except ImportError:
    from openalex_comparison import clean, contextual_terms, abstract_from_index, year

# The words that distinguish the *question* from its method or genre.
METHODS = frozenset('''model modelling modeling models simulation simulations forecast forecasting predictions prediction
projected projection projections outlook scenario scenarios machine learning artificial intelligence algorithm
algorithms methods method technique techniques analysis european europe policy governance research study
assessment evaluation evaluates evaluated examining future futures long term short term regional international
impacts impact effect effects potential perspective perspectives'''.split())
NATIONAL = {
    'russia': r'\b(russia|russian)\b', 'china': r'\b(china|chinese)\b',
    'india': r'\b(india|indian)\b', 'usa': r'\b(united states|usa|u\.s\.|american)\b',
    'australia': r'\b(australia|australian)\b', 'brazil': r'\b(brazil|brazilian)\b',
    'japan': r'\b(japan|japanese)\b', 'mexico': r'\b(mexico|mexican)\b',
    'morocco': r'\b(morocco|moroccan)\b',
}
EU = re.compile(r'\b(europe|european|eu|eurozone|european union|member states)\b', re.I)
EU_COUNTRIES = re.compile(r'\b(germany|german|france|french|italy|italian|spain|spanish|finland|finnish|sweden|swedish|netherlands|dutch|poland|polish|denmark|danish|belgium|belgian|portugal|portuguese|austria|austrian|greece|greek)\b', re.I)
RETRACTED = re.compile(r'^\s*\[?(?:withdrawn|retracted|retraction|expression of concern)\b', re.I)
# Do not use "findings indicate" alone as a claim of observed change.
OBSERVED = re.compile(r'\b(observed|measured|monitor(?:ed|ing)|survey(?:ed)?|record(?:ed|s)|census|historical data|time.series|actual|retrospective|we found|we find|data show|data suggest|increased|decreased|rose|declined|grew|fell|trends? show)\b', re.I)
ACTION = re.compile(r'\b(implemented|adopted|enacted|rolled out|rollout|deployed|operational|evaluated|evaluation|regulation entered|in force|uptake|actual adoption)\b', re.I)
HYPOTHETICAL = re.compile(r'\b(project(?:ed|ion|ions)?|forecast(?:s|ed)?|scenario|simulat(?:ed|ion|ions)|might|could|would|by 20[3-9]\d|potential|hypothetical|anticipated)\b', re.I)


ABBREVIATIONS = frozenset(('ict','ccs','ets','ghg','gdp','cap'))


def issue_terms(text):
    # A three-letter field term can be the entire point of an old study.
    acronyms = {x.lower() for x in re.findall(r'\b(?:ICT|CCS|ETS|GHG|GDP|CAP)\b', clean(text), re.I)}
    return (contextual_terms(text) - METHODS) | acronyms


def geographic_status(original, newer_title, newer_abstract=''):
    """Only strong one-way mismatches are rejected; absence is not a mismatch."""
    original = clean(original)
    newer = clean(newer_title + ' ' + newer_abstract)
    old_eu = bool(EU.search(original))
    new_eu = bool(EU.search(newer) or EU_COUNTRIES.search(newer))
    # A paper explicitly titled as Russian, Chinese, etc. is cross-country
    # context, even when its abstract mentions Europe in passing.
    if old_eu and not EU.search(newer_title) and any(
            re.search(regex, newer_title, re.I) for regex in NATIONAL.values()):
        return 'other_region'
    old_nations = {key for key, regex in NATIONAL.items() if re.search(regex, original, re.I)}
    new_nations = {key for key, regex in NATIONAL.items() if re.search(regex, newer, re.I)}
    if old_eu and new_nations and not new_eu:
        return 'other_region'
    if old_nations and new_nations.isdisjoint(old_nations) and not (old_eu and new_eu):
        return 'other_region'
    return 'matching_region' if (old_eu and new_eu) or (old_nations & new_nations) else 'region_not_specified'


# Preserve specific subject words (pesticides, soil organisms), not generic
# title words (exposure, scenarios, assessment).
QUERY_GENERIC = METHODS | frozenset("""exposure exposures study studying studied forecast scenario projection
potential impact future outcome outcomes current regional europe european data changes change
trend trends role effects effect case cases comparison comparative application framework
using methodological design designing issues issue involved posed evolving linked related
strategies challenges challenge different aspects factor factors assessment approach
knowledge methods model modelling research analysis management policy making""".split())


def _surface_terms(title):
    tokens = re.findall(r'[a-z][a-z0-9-]{2,}', clean(title).lower())
    answer, seen = [], set()
    for token in tokens:
        # Compare singularized concepts with singularized concepts; raw plural
        # comparison previously discarded 'organisms' and 'pesticides'.
        root = (token if token in ABBREVIATIONS else next(iter(contextual_terms(token)), ''))
        if not root or root in seen or root in QUERY_GENERIC:
            continue
        seen.add(root)
        answer.append((root, token))
    return answer


def questions_for(claim, *, term_frequency=None, rotation=0):
    """Search for *this issue*, not an arbitrarily shortened old title.

    Rank distinctive 2-3 concepts using frequency in the indexed archive.
    An alternate facet can be tried on a subsequent research run.
    """
    pairs = _surface_terms(claim.get('title'))
    if len(pairs) < 2:
        present = {p[0] for p in pairs}
        pairs.extend((root, surface) for root, surface in
                     _surface_terms(claim.get('expected') or '')
                     if root not in present)
    if not pairs:
        return ''
    freq = term_frequency or {}
    ranked = sorted(enumerate(pairs), key=lambda item:
                    (freq.get(item[1][0], 1) + item[0] * .12, item[0]))
    chosen = [pair for _, pair in ranked]
    if rotation % 3 == 1 and len(chosen) >= 4:
        chosen = chosen[1:4]
    elif rotation % 3 == 2 and len(chosen) >= 5:
        chosen = chosen[2:5]
    return ' '.join(surface for _, surface in chosen[:3])



def developments_query_for(claim, *, term_frequency=None, rotation=0):
    """One optional query aimed at change/adoption, not more forecasts.

    The two distinctive anchors keep the topic precise; the third term is
    deliberately mild. Publication metadata still needs issue screening.
    """
    core = questions_for(claim, term_frequency=term_frequency, rotation=rotation).split()
    if len(core) < 2:
        return ''
    title = clean(claim.get('title')).lower()
    if re.search(r'\b(polic(?:y|ies)|governance|regulation|strategies|planning|security)\b',title):
        cue = ('implementation', 'evaluation', 'adoption')[rotation % 3]
    elif re.search(r'\b(digital|technology|electricity|energy|innovation|hydrogen)\b',title):
        cue = ('adoption', 'deployment', 'evaluation')[rotation % 3]
    elif re.search(r'\b(mortality|disease|health|migration|demograph|population)\b',title):
        cue = ('trends', 'observed', 'evaluation')[rotation % 3]
    else:
        cue = ('monitoring', 'evaluation', 'trends')[rotation % 3]
    if cue in core:
        return ''
    return ' '.join(core[:2] + [cue])


def corpus_frequency(leads):
    """Calculate corpus-specific term frequency once per scan, offline."""
    from collections import Counter
    count = Counter()
    for lead in leads:
        count.update(root for root, _ in _surface_terms(lead.get('title')))
    return count


def is_later(claim, work):
    earlier = year(claim.get('original_publication'))
    date = clean(work.get('publication_date') or work.get('date'))
    later = year(date or work.get('publication_year'))
    if not earlier or not later or later < earlier or later > dt.date.today().year:
        return False
    if len(date) >= 10:
        try:
            if dt.date.fromisoformat(date[:10]) > dt.date.today():
                return False
        except ValueError:
            return False
    if later == earlier:
        original = clean(claim.get('original_publication'))
        if len(original) < 10 or len(date) < 10:
            return False
        try:
            return dt.date.fromisoformat(date[:10]) > dt.date.fromisoformat(original[:10])
        except ValueError:
            return False
    return True


def candidate(claim, work, *, discovery='issue_search'):
    """Find a plausible *answering trail* from a later publication's metadata.

    This is an inclusive screen: it prefers issue continuity over proof and
    retains ongoing research, provided the topic really matches.
    """
    if not isinstance(work, dict) or not is_later(claim, work):
        return None
    title = clean(work.get('title'))
    abstract = abstract_from_index(work.get('abstract_inverted_index')) or clean(work.get('abstract'))
    url = clean(work.get('doi') or work.get('url') or work.get('id'))
    original_title = clean(claim.get('title'))
    if (not url.startswith('https://') or not title or RETRACTED.match(title)
            or RETRACTED.match(original_title) or work.get('is_retracted') is True
            or work.get('is_withdrawn') is True):
        return None
    if url.rstrip('/').casefold() == clean(claim.get('source_url')).rstrip('/').casefold():
        return None
    if re.sub(r'\W+', '', title.casefold()) == re.sub(r'\W+', '', original_title.casefold()):
        return None
    old_title_terms, new_title_terms = (set(re.findall(r'[a-z]{4,}', original_title.casefold())),
                                         set(re.findall(r'[a-z]{4,}', title.casefold())))
    if (len(old_title_terms & new_title_terms) >= 4 and
            len(old_title_terms & new_title_terms) / max(1,len(old_title_terms | new_title_terms)) >= .85):
        return None  # likely same work or republished metadata, not an independent update
    scope = geographic_status(original_title, title, abstract)
    if scope == 'other_region':
        return None
    old = issue_terms(original_title)
    new_title = issue_terms(title)
    newer = issue_terms(title + ' ' + abstract)
    shared = old & newer
    in_title = old & new_title
    # Two issue concepts, or one very distinctive issue in the title together
    # with a second concept in the abstract. Method-only overlap never counts.
    # A direct citation is a useful discovery route but not sufficient by itself.
    # A single distinctive named issue is enough for *continuing research*
    # when the geography matches explicitly. It is never enough for calling
    # an observed historical change established.
    one_distinctive = (len(shared) == 1 and bool(in_title) and
                       max(map(len,shared)) >= 10 and scope == 'matching_region')
    if not one_distinctive and (len(shared) < 2 or (not in_title and len(shared) < 3)):
        return None
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', abstract)
    selected = ''
    evidence_type = 'ongoing_research'
    factual = []
    for sentence in sentences:
        if not (issue_terms(sentence) & shared) or HYPOTHETICAL.search(sentence):
            continue
        kind = ('implementation_or_evaluation' if ACTION.search(sentence) else
                'measured_or_reported_change' if OBSERVED.search(sentence) else '')
        if kind:
            # Prefer a reported RESULT over a mere description of methodology.
            result_words = bool(re.search(r'\b(we found|we find|data (?:show|suggest)|increased|decreased|rose|declined|grew|fell|implemented|adopted|deployed)\b',sentence,re.I))
            factual.append((int(result_words),sentence,kind))
    if factual:
        _, selected, evidence_type = sorted(factual,key=lambda x:x[0],reverse=True)[0]
    if not selected:
        for sentence in sentences:
            if (issue_terms(sentence) & shared) and len(sentence) >= 35:
                selected = sentence
                break
    if evidence_type == 'ongoing_research' and selected and HYPOTHETICAL.search(selected):
        evidence_type = 'newer_scenario_or_model'
    if (evidence_type == 'measured_or_reported_change' and HYPOTHETICAL.search(title)
            and not re.search(r'\b(measured|observed|monitored|historical data|surveyed)\b', selected,re.I)):
        evidence_type = 'newer_scenario_or_model'  # model results are not historical measurements
    # A single anchor is a weak link even when result-like verbs occur.
    if one_distinctive:
        evidence_type = 'ongoing_research'
    # Excerpts are attributed to the paper, not independently verified.
    label = {
        'implementation_or_evaluation': 'A later paper describes implementation or evaluation',
        'measured_or_reported_change': 'A later paper reports measured or observed developments',
        'newer_scenario_or_model': 'Later research explores further possible futures',
        'ongoing_research': 'Later research continues the same issue',
    }[evidence_type]
    return {'title': title[:250], 'url': url, 'date': clean(work.get('publication_date') or work.get('date')),
            'year': year(work.get('publication_date') or work.get('date') or work.get('publication_year')),
            'evidence_kind': evidence_type, 'finding_from_abstract': clean(selected)[:340],
            'relationship': 'same_issue_published_followup_not_outcome_verified',
            'geography': scope, 'shared_issue_terms': sorted(shared), 'discovery': discovery,
            'interpretation': label, 'source': 'openalex_publication_metadata'}


def collect(claim, works, *, discovery='issue_search', limit=5):
    values = {}
    for w in works:
        match = candidate(claim, w, discovery=discovery)
        if match:
            key = match['url'].casefold().rstrip('/')
            if key not in values or (len(match['finding_from_abstract']) > len(values[key]['finding_from_abstract'])):
                values[key] = match
    order = {'implementation_or_evaluation':3,'measured_or_reported_change':3,
             'newer_scenario_or_model':2,'ongoing_research':1}
    return sorted(values.values(), key=lambda v:(order[v['evidence_kind']],v['year']), reverse=True)[:limit]


def merge(old, new, limit=8):
    keep = {}
    for item in (old or []) + (new or []):
        if not isinstance(item, dict) or not item.get('url'):
            continue
        key = item['url'].casefold().rstrip('/')
        if key not in keep or (bool(item.get('finding_from_abstract')) and not keep[key].get('finding_from_abstract')):
            keep[key] = item
    prio = {'implementation_or_evaluation':3,'measured_or_reported_change':3,
            'newer_scenario_or_model':2,'ongoing_research':1}
    return sorted(keep.values(), key=lambda x:(prio.get(x.get('evidence_kind'),0),x.get('year') or 0), reverse=True)[:limit]
