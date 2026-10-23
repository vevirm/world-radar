"""Claim-specific search plans. Never substitute generic first words for the object."""
import re

PATTERNS = [
 (r'\b(?:renewable jet fuel|\brjf\b|sustainable aviation fuel|aviation biofuel)', 'renewable aviation fuel', ['sustainable aviation fuel EU deployment 2030', 'EU renewable jet fuel supply biomass policy 2030']),
 (r'\b(?:flood risk|flood damage|affected by floods|river flood)', 'flood risk', ['Europe flood damage observed trends climate change', 'European river flood exposure damages population 2050 scenarios']),
 (r'\b(?:carbon pric(?:e|es|ing)|emissions trading|eu ets|emission allowances)', 'carbon pricing', ['EU ETS carbon price emissions reductions 2030', 'European emissions trading carbon price climate policy effects']),
 (r'\b(?:energy demand|energy consumption)', 'energy demand', ['energy demand developing countries China India observed trends', 'global energy consumption trends 2040 outlook']),
]
STOP = set('here some long term outlook significant findings from report expected forecasts projected scenarios models model results demonstrate cost efficient annual amount larger range foreseen toward original study paper in the and will could might that this under between based with into'.split())

def search_plan(claim):
    passage = str(claim.get('original_passage') or (claim.get('question_card') or {}).get('original_passage') or '')
    title = str(claim.get('title') or '')
    text = title + ' ' + passage
    for pattern, obj, qs in PATTERNS:
        if re.search(pattern, text, re.I):
            return {'object':obj, 'queries':qs, 'method':'object_and_trajectory'}
    # Generic fallback: constrained to uncommon terms from the actual claim passage.
    words = re.findall(r'[a-z][a-z-]{3,}', passage.lower())
    priority = [w for w in words if w not in STOP and not w.isdigit()]
    title_words = re.findall(r'[a-z][a-z-]{3,}', title.lower())
    first = list(dict.fromkeys([w for w in title_words if w not in STOP][:3] + priority[:4]))
    query = ' '.join(first[:6])
    return {'object':'unspecified','queries':[query] if len(first)>=2 else [],'method':'fallback_needs_review'}
