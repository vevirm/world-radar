"""Conservative metadata screen before downloading later research.

A pass means 'worth reading', never evidence that a development occurred.
"""
from radar2_broad_search import terms, later

# Require an actual subject connection, not just incidental words such as
# "supply", "demand", "risk", or "Europe". These topic families are deliberately
# permissive: they allow different terminology for the same issue.
TOPIC_FAMILIES = (
    ({'aviation', 'jet', 'aircraft', 'airline', 'airlines', 'flight', 'flights'},
     {'aviation', 'jet', 'aircraft', 'airline', 'airlines', 'flight', 'flights', 'saf'}),
    ({'flood', 'floods', 'flooding', 'inundation'},
     {'flood', 'floods', 'flooding', 'inundation', 'river', 'rivers'}),
    ({'carbon', 'emission', 'emissions', 'ghg'},
     {'carbon', 'emission', 'emissions', 'ghg', 'co2', 'decarbonization'}),
    ({'hydrogen'}, {'hydrogen', 'h2'}),
)


def subject_connection(claim, candidate):
    original = set(terms((claim.get('title') or '') + ' ' + (claim.get('original_passage') or '')))
    found = set(terms((candidate.get('title') or '') + ' ' + (candidate.get('excerpt') or '')))
    for trigger, related in TOPIC_FAMILIES:
        if trigger & original and not (related & found):
            return False
    # Energy is a broad domain, but research on other kinds of "demand" is not.
    energy = {'energy', 'electricity', 'power', 'fuel', 'fuels', 'petroleum', 'oil', 'gas'}
    if 'energy' in original and not (energy & found):
        return False
    return True


METHOD_ONLY = ('forecast accuracy', 'forecasting accuracy', 'prediction accuracy',
               'forecast evaluation', 'forecasting methods', 'bibliometric analysis')


def select_source(claim, candidate):
    """Return (keep, reason). Reject obvious mismatches before expensive fetching."""
    if not later(claim.get('original_publication'), candidate.get('date')):
        return False, 'not_later_than_original'
    url = str(candidate.get('url') or '')
    if not url.startswith('https://'):
        return False, 'unsupported_url'
    title = str(candidate.get('title') or '')
    abstract = str(candidate.get('excerpt') or '')
    if not title.strip():
        return False, 'missing_title'
    subject = set(terms(claim.get('title')))
    candidate_title = set(terms(title))
    candidate_text = set(terms(title + ' ' + abstract))
    title_overlap = subject & candidate_title
    if not subject_connection(claim, candidate):
        return False, 'missing_core_subject'
    if len(title_overlap) < 2:
        return False, 'insufficient_subject_connection'
    lower = title.lower()
    if any(phrase in lower for phrase in METHOD_ONLY) and not len(subject & candidate_text) >= 4:
        return False, 'likely_methods_only'
    # Do not infer European relevance solely from absence/presence of 'Europe':
    # geography is recorded as unknown until the candidate is actually read.
    return True, 'matching_subject_in_title_requires_full_text_review'
