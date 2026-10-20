"""Conservative metadata-level forecast screening.

No source title alone is accepted as an explicit prediction. A forecast candidate
is *not* an extracted, validated prediction until a human/full-text evaluator
has reviewed the original document.
"""
import re

YEAR = re.compile(r'\b(20[2-5][0-9])\b')
FORECAST = re.compile(r'\b(project(?:s|ed|ions)?|forecast(?:s|ed|ing)?|predict(?:s|ed|ion)?|expect(?:s|ed)?|estim(?:ate|ates|ated)|will (?:rise|fall|increase|decrease|reach|exceed|grow|decline|double|halve)|by 20[2-5][0-9])\b', re.I)
METRIC = re.compile(r'\b(\d+(?:\.\d+)?\s?%|\d+(?:\.\d+)?\s?(?:million|billion|gigatonnes?|tonnes?|degrees?|gw|mw|twh|years?)|emissions?|population|mortality|employment|gdp|temperature|sea.level|renewable|capacity|demand|production|costs?|prices?|migration|energy|pollution)\b', re.I)

def screen(lead):
    title = str(lead.get('title') or '').strip()
    abstract = str(lead.get('abstract') or '').strip()
    if not abstract or len(abstract) < 70:
        return {'screening_status': 'full_text_required', 'screening_reason': 'No sufficiently detailed original abstract; title is not a prediction.', 'candidate_excerpt': '', 'candidate_year': None}
    candidates = re.split(r'(?<=[.!?])\s+', abstract)
    qualifying = [s.strip() for s in candidates if YEAR.search(s) and FORECAST.search(s) and METRIC.search(s)]
    if qualifying:
        phrase = min(qualifying, key=len)[:650]
        year = YEAR.search(phrase)
        return {'screening_status': 'candidate_needs_validation', 'screening_reason': 'Original abstract includes date, forward-looking wording and an observable theme; full-text validation still required.', 'candidate_excerpt': phrase, 'candidate_year': int(year.group(1)) if year else None}
    return {'screening_status': 'no_testable_prediction_in_metadata', 'screening_reason': 'Available abstract does not state a clearly dated, measurable forecast.', 'candidate_excerpt': '', 'candidate_year': None}
