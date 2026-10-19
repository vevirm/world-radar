"""Transparent, deliberately rough claim-direction score for collected evidence.

This is NOT factual validation. Only configured phrase signals in source headlines
are counted. Reviewers may enter a score after checking underlying sources.
"""
import re


def phrase_found(text, phrase):
    return bool(re.search(r'(?<!\w)' + re.escape(phrase.casefold()) + r'(?!\w)', text.casefold()))


def classify(item, idea):
    text = item.get('headline', '')
    yes = any(phrase_found(text, p) for p in idea.get('support_signals', []))
    no = any(phrase_found(text, p) for p in idea.get('refute_signals', []))
    return 'mixed' if yes and no else 'support' if yes else 'refute' if no else 'unclear'


def assess(items, idea):
    counts = {'support': 0, 'refute': 0, 'mixed': 0, 'unclear': 0}
    for item in items:
        counts[classify(item, idea)] += 1
    reviewed = idea.get('reviewed_score')
    if reviewed is not None:
        if type(reviewed) is not int or not 1 <= reviewed <= 100:
            raise ValueError(f"{idea['id']}: reviewed_score must be an integer 1–100")
        return {'score': reviewed, 'basis': 'Human-reviewed', 'counts': counts}
    # Only unambiguous directional headlines count. Cap weak headline-only
    # evidence at 10..90; repeated headlines from same story are not independent.
    score = max(10, min(90, 50 + 10 * (counts['support'] - counts['refute'])))
    basis = 'Provisional headline signals' if counts['support'] or counts['refute'] else 'No directional evidence (placeholder)'
    return {'score': score, 'basis': basis, 'counts': counts}
