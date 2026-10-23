"""Claim-centred evidence matching and auditable draft cards.

A match is a research lead, not proof of a trajectory. Keep direct and
explanatory/reframing evidence separate; never turn absence into an outcome.
"""
import re
from radar2_broad_search import terms, later

CONCEPTS = {
 'aviation_fuel': ('aviation fuel','jet fuel','renewable jet','sustainable aviation','saf','aviation biofuel','aircraft fuel','rjf'),
 'flood_risk': ('flood risk','flooding','river flood','flood exposure','flood damage','flood hazard'),
 'carbon_pricing': ('carbon price','carbon pricing','emissions trading','eu ets','emission trading','carbon tax','allowance price'),
 'energy_demand': ('energy demand','energy consumption','energy use','electricity demand'),
 'hydrogen': ('hydrogen','h2 fuel'),
}
GENERIC = set('long term outlook comments renewable supply scenarios scenario model modelling climate annual policy percent year years million developing development results report energy global world forecast future demand study studies evidence'.split())
EU = re.compile(r'\b(?:eu|europe|european|european union|eu member states|eu-27)\b', re.I)
FOREIGN = re.compile(r'\b(?:pakistan|indonesia|united states|american|usa|wales|australia|india|china)\b', re.I)

def concept_matches(text):
    s = re.sub(r'\s+', ' ', str(text or '').lower())
    return {key for key, aliases in CONCEPTS.items() if any(re.search(r'(?<!\w)'+re.escape(a)+r'(?!\w)',s) for a in aliases)}

def claim_subject(claim):
    # Trust the explicit original passage, not incidental article-title language.
    passage = claim.get('original_passage') or (claim.get('question_card') or {}).get('original_passage','')
    return str(passage) + ' ' + str(claim.get('title') or '')

def assess_connection(claim, candidate):
    if not later(claim.get('original_publication'),candidate.get('date')):
        return False, {'reason':'not_later_than_original'}
    if not str(candidate.get('url') or '').startswith('https://'):
        return False, {'reason':'unsupported_url'}
    title = str(candidate.get('title') or '')
    if not title.strip(): return False, {'reason':'missing_title'}
    abstract = str(candidate.get('excerpt') or '')
    source = claim_subject(claim)
    original_concepts = concept_matches(source)
    candidate_concepts = concept_matches(title+' '+abstract)
    shared = sorted(original_concepts & candidate_concepts)
    if original_concepts and not shared:
        return False, {'reason':'different_core_object','original_concepts':sorted(original_concepts),'candidate_concepts':sorted(candidate_concepts)}
    anchor = {t for t in terms(source) if t not in GENERIC}
    candidate_terms = set(terms(title+' '+abstract))
    overlap = sorted(anchor & candidate_terms)
    if not shared and len(overlap) < 2:
        return False, {'reason':'weak_claim_connection','shared_terms':overlap}
    # Region flag is a review signal, not a conclusive exclusion: abstracts may omit scope.
    eu_claim = bool(EU.search(source))
    eu_candidate = bool(EU.search(title+' '+abstract))
    foreign_only = eu_claim and bool(FOREIGN.search(title+' '+abstract)) and not eu_candidate
    if foreign_only: return False, {'reason':'explicit_different_geography','shared_concepts':shared}
    if shared:
        kind='direct_or_explanatory_candidate'
        reason='shared_specific_claim_object'
    else:
        kind='explanatory_candidate'
        reason='claim_passage_term_overlap'
    return True, {'reason':reason,'relationship':kind,'shared_concepts':shared,
                  'shared_terms':overlap[:10],
                  'geography':'europe_mentioned' if eu_candidate else ('requires_check' if eu_claim else 'not_specified'),
                  'question_overlap':'requires_full_text_review',
                  'trajectory_status':'not_determined'}

def evidence_card(case):
    selected=[]
    for row in case.get('readings',[]):
        if row.get('status')!='page_text_read':continue
        findings=row.get('candidate_findings') or []
        if not findings:continue
        selected.append({'title':row.get('title'),'url':row.get('url'),'date':row.get('published'),
                         'connection':row.get('selection_detail',{}),'findings':findings[:3],
                         'status':'candidate_requires_source_review'})
    return {'original_id':case['original_id'],'original_passage':case['original_passage'],
            'source':case.get('original_source'), 'research_question':case.get('question_card',{}).get('evidence_question'),
            'direction':'not_determined', 'status':'evidence_candidates_need_reasoned_review' if selected else 'no_extracted_evidence_yet',
            'evidence_sources':selected[:5], 'limitations':'No claim-level developmental conclusion has been established.'}
