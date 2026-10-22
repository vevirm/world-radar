"""Conservative editorial promotion of an already-found later research lead.

This is NOT a truth check, a source-review certificate, or a reason to delete a
paper. It decides whether a candidate is suitable as the headline explanation
of an older research question. Indirect papers remain in the research atlas.
"""
from __future__ import annotations

import re
from datetime import date
try:
    from .evidence_policy import classify, substantive_excerpt, same_geographic_context, canonical_url
    from .question_evidence import issue_terms
except ImportError:
    from evidence_policy import classify, substantive_excerpt, same_geographic_context, canonical_url
    from question_evidence import issue_terms

PARATEXT = re.compile(
    r'\b(?:replication (?:files?|package|materials?|code|data|dataset)|'
    r'data (?:and|&) code (?:for|of)|data (?:underlying|accompanying) (?:the|this)|'
    r'supplementary (?:files?|materials?|information|dataset)|'
    r'supporting (?:information|materials?|data)|'
    r'corrigendum|errat(?:um|a)|correction (?:to|of)|'
    r'publisher.?s note|editorial notice|peer review report|'
    r'author response|dataset (?:for|associated with|supporting))\b', re.I)
TITLE_PARATEXT = re.compile(r'\b(?:retract(?:ed|ion)|withdrawn|expression of concern)\b', re.I)

# Main object of inquiry, not generic associations such as health, policy, or
# forecast. A paper about food-chain epidemiology is not about doctors moving.
# The dictionary is intentionally small: unfamiliar topics still use the
# ordinary subject check and are never destroyed by this supplemental screen.
FOCUS = (
    (r'\b(?:physician|doctor|medical workforce|healthcare workforce|health personnel)\w*',
     r'\b(?:physician|doctor|healthcare workforce|health workforce|medical workforce|'
     r'medical staff|medical personnel|health professionals?|healthcare workers?)\w*'),
    (r'\b(?:\bgdp\b|gross domestic product)\b',
     r'\b(?:gdp|gross domestic product|economic growth|output growth|macroeconomic)\b'),
    (r'\b(?:internationali[sz]ation)\b.*\b(?:higher education|universit)',
     r'\b(?:internationali[sz]ation|student mobilit|university alliance|'
     r'international higher education|cross.border universit)\w*'),
    (r'\b(?:research|education|innovation)\b.*\b(?:research|education|innovation)\b',
     r'\b(?:universit|higher education|research infrastructure|science|'
     r'research|innovation|academic|educational collaboration|r&d)\w*'),
)

# For generic title-overlap patterns, insist that the two titles share at
# least one nontrivial object, or the abstract specifically discusses it.
GENERIC = set('''future futures foresight scenario scenarios model models modelling modeling
projection projections predict prediction forecasting forecast forecasted evaluation
analysis assessment research reviews study studies europe european european union
region regional global national policy policies impacts impact effect effects
change changes developing development new later subsequent trends directions
health care higher education international integration
technology technological digital social economics
economic environmental environment long short data textual information systems
approach approaches methods method framework strategies strategy transition
management effects evidence results work working comparative
    integrated learned lesson lessons seminar seminars skill skills building
    country countries member members state states project projects general generic
    historical theoretical professional professionals training course courses'''.split())


def _wordset(text):
    return set(issue_terms(str(text or '')))


def _year(v):
    m = re.search(r'\b(?:19|20)\d{2}\b', str(v or ''))
    return int(m.group()) if m else 0


def _normal(text):
    return ' '.join(re.findall(r'[a-z0-9]+', str(text or '').casefold()))


def _document_issue(original_title, newer_title, abstract):
    """Return a substantive objection, if present, before scoring anything."""
    a, b = str(original_title or ''), str(newer_title or '')
    body = str(abstract or '')
    # An unchanged METHOD or FORMAT is not the same historical issue.
    # Specific topical questions can be displaced by a newer article that
    # merely shares the words "integrated lessons" or "skills seminar".
    specific_conditions = ('pancreatic', 'breast', 'colorectal', 'prostate', 'lung',
                           'cervical', 'ovarian', 'gastric', 'liver', 'skin')
    for organ in specific_conditions:
        if re.search(r'\b' + organ + r'\b.*\b(?:cancer|carcinoma|tumou?r)\b',a,re.I) or \
                re.search(r'\b(?:cancer|carcinoma|tumou?r)\b.*\b' + organ + r'\b',a,re.I):
            if not re.search(r'\b' + organ + r'\b',b,re.I):
                return 'different_disease_or_organ'
    if re.search(r'\b(?:physician|doctor)\w*',a,re.I) and re.search(r'\bmobility\b',a,re.I):
        if not re.search(r'\b(?:mobilit|migrat|recruit|cross.border|international (?:movement|recruitment)|'
                         r'workforce (?:movement|flow|distribution)|health professional migration)\w*',
                         b,re.I):
            return 'missing_physician_mobility_question'
    topic_guards = (
        (r'\bprosumer\w*', r'\b(?:prosumer|renewable energy|electricity|power grid|solar|energy communit)\w*'),
        (r'\bburden of disease\b', r'\b(?:burden of disease|disease burden|mortality|morbidity|epidemiol|health burden)\w*'),
        (r'\b(?:emission allowances?|\beua\b|carbon futures?)\b',
         r'\b(?:carbon|emission|allowance|eua|eu.ets)\w*'),
    )
    for original_pat, newer_pat in topic_guards:
        if re.search(original_pat, a, re.I) and not re.search(newer_pat, b, re.I):
            return 'new_paper_only_shares_generic_method'
    if re.search(r'\b(?:livestock|dairy|cattle|poultry|barns?|pig|swine)\b',b,re.I) and not \
            re.search(r'\b(?:farm|livestock|agricult|dairy|cattle|poultry|barns?|animal)\w*',a,re.I):
        return 'different_livestock_subject'
    for original_pat, newer_pat in FOCUS:
        if re.search(original_pat, a, re.I):
            # Crucially, not just an incidental broad mention of the issue:
            # the paper title should be about that object, or a sufficiently
            # specific finding must discuss it in the abstract.
            if not re.search(newer_pat, b, re.I):
                if not re.search(newer_pat, body, re.I):
                    return 'missing_original_research_subject'
                if re.search(r'\b(?:surveillance|food chain|avian|poultry|replication files|'
                             r'gene sequence|genetic structure)\b', b, re.I):
                    return 'different_primary_subject'
    return ''


def assess_followup(record, paper, source='follow_up_publications'):
    """Return (promotion_score or None, reason).

    A non-None result means candidate same-question *literature*, not observed
    outcome. Missing/irrelevant links must not be used for headline NOW text.
    """
    if not isinstance(record, dict) or not isinstance(paper, dict):
        return None, 'missing_record'
    old = str(record.get('title') or '')
    title = str(paper.get('title') or '')
    abstract = ' '.join(str(paper.get('abstract_excerpt') or paper.get('finding_from_abstract') or '').split())
    if not old or not title:
        return None, 'missing_title'
    if paper.get('evidence_role') == 'related_context' and paper.get('context_reason'):
        return None, 'previously_downgraded_to_context'
    if TITLE_PARATEXT.search(title) or paper.get('is_retracted') is True or paper.get('is_withdrawn') is True:
        return None, 'retracted_or_withdrawn'
    if PARATEXT.search(title) or (PARATEXT.search(abstract[:180]) and
                                    re.search(r'\b(?:replication|supplementary|dataset|code)\b', title, re.I)):
        return None, 'replication_or_supplement_not_independent_evidence'
    if canonical_url(record.get('original_url') or record.get('source_url')) == canonical_url(paper.get('url')):
        return None, 'original_publication_repeated'
    if _normal(title) == _normal(old) or (len(_normal(old)) > 24 and
                                             _normal(old) in _normal(title)):
        return None, 'original_publication_repeated'
    if not substantive_excerpt(abstract):
        return None, 'abstract_lacks_substantive_content'
    original_y, new_y = _year(record.get('year') or record.get('original_publication')), _year(paper.get('year') or paper.get('date'))
    if original_y and (not new_y or new_y <= original_y or new_y > date.today().year):
        return None, 'not_clearly_newer'
    # A previously stored role is never sufficient on its own to promote a
    # candidate: recheck it against the shared policy every regeneration.
    category, reason = classify({'title': old, 'original_publication': record.get('year'),
                                   'source_url': record.get('original_url')},paper,source)
    if category != 'direct':
        return None, 'policy_' + reason
    issue = _document_issue(old,title,abstract)
    if issue:
        return None, issue
    old_words, newer_title_words, newer_abs_words = _wordset(old),_wordset(title),_wordset(abstract)
    old_specific = old_words - GENERIC
    title_overlap = old_specific & newer_title_words
    abstract_overlap = old_specific & newer_abs_words
    # The original question must survive in the later TITLE or its substantive
    # summary. Shared methodological terms / country words cannot carry a match.
    geographic_only = set(('polish','ukrainian','german','french','european','europe',
                           'global','british','spanish','italian','romanian','swedish'))
    object_title = title_overlap - geographic_only
    object_abstract = abstract_overlap - geographic_only
    if old_specific and not (object_title or len(object_abstract) >= 2):
        return None, 'original_subject_not_in_new_evidence'
    # Penalize an abstract that switches the principal object entirely.
    if not object_title and len(object_abstract) < 2:
        return None, 'unconnected_main_subject'
    # Favour subject continuity and an informative result over publication count
    # or date; never automatically rank 2026 over a better 2021 explanation.
    overlap_count = len(object_title)
    abstract_count = len(object_abstract)
    score = min(60, 17 * overlap_count + 5 * min(abstract_count,4))
    score += 16 if same_geographic_context(old,title,abstract) else 0
    if re.search(r'\b(?:results? (?:show|indicat|suggest)|we (?:found|find)|observed|'
                 r'evaluat|measur|implement|policy reform|monitor|increased|decreased)\w*',abstract,re.I):
        score += 12
    if paper.get('evidence_kind') in ('measured_or_reported_change','implementation_or_evaluation'):
        score += 8
    if new_y >= date.today().year - 5:
        score += 4  # Tie-breaker only, not the main reason
    return score, 'substantive_same_issue_literature'
