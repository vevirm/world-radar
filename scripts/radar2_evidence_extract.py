"""Auditable candidate findings in actually downloaded text; never declare trajectories."""
import re

OBSERVED = ('increased', 'decreased', 'rose', 'fell', 'declined', 'grew', 'reached',
            'recorded', 'observed', 'measured', 'reported', 'between', 'since',
            'statistics show', 'data show', 'has risen', 'has fallen')
FORWARD = ('will ', 'could ', 'may ', 'might ', 'projected', 'forecast',
           'scenario', 'expected', 'by 2030', 'by 2040', 'by 2050')
NOISE = ('cookie', 'privacy policy', 'subscribe', 'all rights reserved', 'sign in')

def extract_findings(text, subject, *, limit=3):
    """Return shortlist of *candidate* sentences, not verified observations.

    Full text is required; summaries and fragments must remain traceable to URL
    stored by the caller. Classifications are tentative, never verdicts.
    """
    if not isinstance(text, str) or not text.strip():
        return []
    tokens = {x.lower() for x in re.findall(r'[a-zA-Z]{4,}', str(subject))}
    tokens -= {'study', 'future', 'europe', 'european', 'about', 'research', 'report', 'scenario', 'scenarios'}
    chunks = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])', re.sub(r'\s+', ' ', text))
    candidates = []
    for pos, sentence in enumerate(chunks):
        s = sentence.strip()
        if len(s) < 65 or len(s) > 650 or any(n in s.lower() for n in NOISE):
            continue
        words = set(re.findall(r'[a-zA-Z]{4,}', s.lower()))
        overlap = len(tokens & words)
        if tokens and overlap < min(2, len(tokens)):
            continue
        lower = s.lower()
        observed = any(p in lower for p in OBSERVED)
        future = any(p in lower for p in FORWARD)
        if not (observed or future):
            continue
        kind = 'mixed_or_unclear' if observed and future else ('reported_development' if observed else 'future_claim')
        candidates.append((overlap * 3 + (2 if observed else 0), pos,
                           {'text': s, 'kind': kind, 'status': 'requires_source_review'}))
    candidates.sort(key=lambda r: (-r[0], r[1]))
    return [c[2] for c in candidates[:limit]]
