"""Source-passage-led questions for Radar 2 (no inference of historical predictions).

The original passage is an attributed *research seed*. It may contain an
assumption, a conditional scenario, a question, or a numerical prediction. This
module only labels its evidence readiness and constructs transparent research
facets. It never claims an outcome and makes no network calls.
"""
from __future__ import annotations

from collections import Counter
import datetime as dt
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
WORDS = re.compile(r"[a-z][a-z0-9]+(?:[-'][a-z0-9]+)*", re.I)
STOP = set('''the and for with from into that this these those over under between
about based using used use study studies research results result analysis analyses
scenario scenarios forecast forecasting projections projection projected predict
predicted prediction potential possible possibility future futures foresight
change changes impacts impact effect effects european europe europeans union
member states authors paper examines explore explored exploring model modelling
modeling models approach approaches methodology method methods report reports
show shows indicate suggests suggest important new different comparative
assess assessment evaluation investigate investigated what which when where
would could might likely expected expect anticipated perhaps proposed propose
should will may can were was are been being have has had its their they them
than then also some often an in on of a to as at by or is it be we our
long term years year aim objective purpose target perspective considerations
development developments developing how over across more less during within
proposed expected measured compare compared compares scenarios case cases
policy policies strategic strategies challenges dynamics trend trends shifts
find findings outlook outlooks wider context future oriented'''.split())
DOMAIN_WORDS = set('''electricity renewable renewables wind solar gas oil coal emissions
carbon methane hydrogen biomethane transport rail freight road aviation fuel
forest forests forestry trees species migration mobility population demographic
fertility mortality morbidity life healthcare health disease infection mosquito
pesticide pesticides soil land agriculture crop wheat yield drought flood
water biodiversity ecosystem ecosystems energy consumer demand food organic
internationalization university universities higher education employment wages
labour labor jobs inequality investment industry manufacturing digital ai
technologies connectivity habitat temperature warming precipitation air
pollution ozone particulate cancer cancers incinerator incinerators exposure
cohort organic conventional expansion demand prices agricultural greenhouse
soil ecology ecosystems ecoregions rights governance integration enlargement defence defense
security exports imports trade housing buildings households urban cities
urbanisation urbanization public services finance banking taxes productivity
research innovation adaptation mitigation climate fisheries ocean logistics
infrastructure tourism tourism exchange tourism visitors visitors landscape'''.split())
# We only infer that a passage is investigable, not that it *predicted* an outcome.
SPECIFIC = re.compile(r'\b(?:will|would|could|might|may|likely|expected|predict(?:ed|s|ion)?|project(?:ed|ion)?|forecast(?:ed|s)?|simulate(?:d|s)?|scenarios?|pathways?|alternative futures?|uncertain(?:ty)?|what if|2030|2040|2050|2060|2070|2100|increas\w*|declin\w*|reduc\w*|shifts?|decreas\w*)\b',re.I)
DATED = re.compile(r'\b(?:20(?:2\d|3\d|4\d|5\d|6\d|7\d|8\d|9\d)|2100)\b')
NUMERIC = re.compile(r'(?<!\w)\d+(?:[.,]\d+)?(?:\s*(?:%|percent|million|billion|tonnes?|gigawatts?|terawatt|pj|mt|deaths?|cases?|years?)\b|\s+(?:by|in|until|at)\s+20\d\d\b)', re.I)
SCENARIOS = re.compile(r'\b(?:under (?:the |an? )?\w+(?: \w+){0,3} scenario|alternative scenarios?|\d+ scenarios?|baseline|business.as.usual|reference scenario|low.emission|high.emission|best.case|worst.case|pathways?)\b', re.I)
DESCRIPTIVE_ONLY = re.compile(r'\b(?:introduces? a framework|methodology|organis(?:ation|ation)|methods for|recommendations for measures|describes? the factors|reviews? the literature)\b', re.I)
EU = re.compile(r'\b(?:europe|european|eu|union|member states|finland|finnish|germany|german|france|french|italy|italian|poland|polish|netherlands|dutch|spain|spanish|sweden|swedish|norway|norwegian|slovenia|slovenian|belgium|belgian)\b', re.I)


def tokens(text):
    return [t.casefold() for t in WORDS.findall(str(text or '')) if len(t) >= 4]


def source_anchors(claim):
    """Traceable concepts occurring in a source title OR its original passage.

    They guide discovery, not proof. A source passage may describe a question
    without a unique scientific measurement, so generic words are excluded.
    """
    title = [t for t in tokens(claim.get('title')) if t not in STOP]
    passage = [t for t in tokens(claim.get('original_passage') or claim.get('expected')) if t not in STOP]
    counts = Counter(passage)
    anchors=[]
    for w in title:
        if w not in anchors:
            anchors.append(w)
    # Include source-text concepts, but prefer known substantive objects rather
    # than incidental methodology or context (and cap to avoid noisy searches).
    extras=[w for w in passage if w not in anchors and (w in DOMAIN_WORDS or counts[w] >= 2)]
    for w in extras:
        if w not in anchors:
            anchors.append(w)
    return anchors[:12]


def question_card(claim):
    passage=' '.join(str(claim.get('original_passage') or '').split())
    kind=claim.get('investigation_type') or 'strategic_future_question'
    title=claim.get('title') or ''
    if not passage:
        readiness='original_text_required'
        reason='No traceable passage from the historical original; title is not a forecast.'
    elif len(passage) < 70:
        readiness='source_review_required'
        reason='Passage is too short to establish the historical question reliably.'
    elif not SPECIFIC.search(passage):
        readiness='source_review_required'
        reason='Saved passage does not state a clear future question, conditional scenario, or trajectory.'
    elif DESCRIPTIVE_ONLY.search(passage) and not (SCENARIOS.search(passage) or DATED.search(passage) or NUMERIC.search(passage)):
        readiness='source_review_required'
        reason='Passage describes a research method or background, not a revisitable future development.'
    elif NUMERIC.search(passage) and (DATED.search(passage) or 'projection' in kind or 'forecast' in kind):
        readiness='quantified_future_proposition'
        reason='A conditional or numerical future proposition is visible in saved original text; its assumptions still require review.'
    elif SCENARIOS.search(passage) or (DATED.search(passage) and SPECIFIC.search(passage)):
        readiness='scenario_or_trajectory'
        reason='A scenario, trajectory or dated future question is identified; it is not automatically a prediction.'
    else:
        readiness='qualitative_future_question'
        reason='An investigable future-oriented issue is present; avoid inventing a measurable target.'
    anchors=source_anchors(claim) if passage else []
    if readiness != 'original_text_required' and len(anchors)<2:
        readiness='source_review_required'
        reason='Original title and passage provide too few concrete issue anchors for selective evidence searching.'
    # Inquiry, not a claim that the future actually unfolded in any particular way.
    return {'original_id':claim['id'], 'title':title, 'source_kind':claim.get('source_kind'),
            'original_publication':claim.get('original_publication'),
            'original_source':claim.get('source_url'),
            'original_passage':passage,
            'original_source_field':claim.get('original_source_field'),
            'investigation_type':kind,
            'readiness':readiness,'reason':reason,
            'issue_anchors':anchors,
            'scenario_is_not_prediction':kind in ('alternative_scenarios','institutional_foresight') or bool(SCENARIOS.search(passage)),
            'target_year_mentions':sorted({int(y) for y in DATED.findall(passage)}),
            'evidence_question':('What has subsequently been observed, evaluated or revised about the original issue: '+title.rstrip(' .?')+'?') if passage else '',
            'later_evidence_requirements':['Publication or observation later than original',
                 'Same substantive issue and geographical population',
                 'Observed result or documented policy implementation, not merely a new scenario',
                 'Original assumptions, baseline and uncertainty kept distinct from later evidence'],
            'status':'not_assessed'}


def audit(root=ROOT):
    try:
        from radar2_scope import original_claims
    except ModuleNotFoundError:
        from scripts.radar2_scope import original_claims
    claims=original_claims(root)
    cards=[question_card(c) for c in claims]
    counts=dict(sorted(Counter(c['readiness'] for c in cards).items()))
    return {'schema_version':1,'mode':'no_scan_question_audit',
            'policy':'Question anchors must derive from the original text; no later event or forecast success is inferred.',
            'original_count':len(cards), 'academic':sum(c['source_kind']=='academic' for c in cards),
            'institutional':sum(c['source_kind']=='institutional' for c in cards),
            'readiness_counts':counts, 'cards':cards}


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--output',type=Path,default=Path('RADAR2-QUESTION-PREVIEW.json'))
    args=parser.parse_args()
    report=audit(args.root)
    output=args.output if args.output.is_absolute() else args.root/args.output
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Question audit (NO SCAN):',report['original_count'],'accepted originals')
    print('Academic:',report['academic'],'Institutional:',report['institutional'])
    for key,value in report['readiness_counts'].items():print(f'{key}: {value}')
    print('Review original passages for low-specificity cases; no outcomes attributed, no data modified.')
    import os
    path=os.environ.get('GITHUB_STEP_SUMMARY')
    if path:
        with open(path,'a',encoding='utf-8') as f:
            f.write('## Radar 2: question readiness (NO SCAN)\n\n')
            for key,value in report['readiness_counts'].items():f.write(f'- **{key}:** {value}\n')
            f.write('\nThis is a source-text audit, not an outcome assessment. Original reports without passages remain queued.\n')

if __name__=='__main__':main()
