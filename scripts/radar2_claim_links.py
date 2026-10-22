"""Conservative issue/measurement-based evidence routing for Radar 2.

The *source quotation* remains authoritative. These domain templates are search
plans, not restatements of a publication or verified outcome assessments. New
subject types must receive their own tested adapter; the module MUST NOT fall
back to accepting keyword overlap as evidence.
"""
from __future__ import annotations

from datetime import date
import re

# A plan describes what the original proposition would have to be compared to.
# Every family has a construct gate and an observation gate. Alternative evidence
# (e.g. total SAF purchased versus locally produced non-food RJF) can be useful
# context but is NOT treated as a directly comparable measurement.
TITLE_GATE={
 'europe_flood_damage':r'\bflood.{0,75}\b(damag|loss)|\b(damag|loss).{0,75}\bflood',
 'eu_renewable_jet_fuel':r'\b(jet fuel|aviation fuel|saf\b|rjf\b)',
 'austria_automated_mobility':r'\b(automated mobility|autonomous (vehicle|transport)|self.driving|driverless)',
 'eu_ageing':r'\b(population|demograph|ageing|aging|age structure|age distribution)',
 'eu_overseas_land':r'\b(land footprint|land demand|land.use|embodied land)',
 'ireland_obesity_cost':r'\b(obes|bmi|body mass index)',
 'eastern_europe_health_resources':r'\b(healthcare workforce|health personnel|health resources|medical workers|doctors|physicians|pharmacists|dentists|ct scanner|mri|magnetic resonance|computed tomography)',
 'eu_ghg_welfare_counterfactual':r'\b(welfare|gdp|economic (cost|benefit|impact|consequence))',
 'eu_cropland_soil_carbon':r'\b(soil organic carbon|soil carbon|soc stocks)',
 'uk_domestic_bioenergy':r'\b(bioenergy|biomass|biofuel)',
}

PLANS = (
    dict(id='europe_flood_damage', detect=(r'\bflood', r'\bdamag|\bloss'),
         question='How have observed European annual FLOOD-ONLY economic losses changed, and how do exposure/adaptation and price bases compare with the original scenarios?',
         searches=('European flood economic losses observed annual', 'European flood damage insurance claims measured'),
         must=(r'\bflood|\binundation', r'\bdamag|\bloss|\bcost'),
         outcome=(r'\b(economic|financial|insured|monetary|annual|billion|million|euros|eur)\b|€',),
         topic='Flood-only economic loss', geography='Europe',
         sources=('EEA loss indicator with hazard filter', 'European flood-loss databases', 'national loss datasets'),
         note='Road damage, total weather losses and river discharge are not equivalent to all-sector flood-only annual economic losses.'),
    dict(id='eu_renewable_jet_fuel', detect=(r'\bjet fuel|\baviation fuel|\brjf\b', r'\bsupply|\bproduction|\bfeedstock'),
         question='Has non-food renewable jet-fuel production/supply for EU aviation developed, and were the assumed incentives and technologies realised?',
         searches=('EU renewable jet fuel production actual volumes', 'Europe sustainable aviation fuel nonfood feedstock production'),
         must=(r'\b(aviation fuel|jet fuel|saf\b|rjf\b)', r'\b(supply|supplied|production|produced|deliveries|delivered|volume|tonnes|tonne|pj\b|capacity)'),
         outcome=(r'\b(fuel|saf\b|rjf\b)',),
         topic='EU non-food RJF production', geography='European Union',
         sources=('EASA ReFuelEU implementation monitoring', 'EU biofuel production statistics', 'Commission project/technology reports'),
         note='SAF supplied at airports is not the same variable as EU-produced non-food RJF; record feedstock, geography and units.'),
    dict(id='austria_automated_mobility', detect=(r'\bautomat\w* mobil|\bautonom\w* (?:vehicl|transport)', r'\baustria'),
         question='Was automated mobility deployed in Austria under the relevant policy conditions, and did road traffic and modal shares change?',
         searches=('Austria automated vehicle deployment traffic modal share measured', 'Austria autonomous mobility walking cycling public transport observed'),
         must=(r'\b(automat\w*|autonom\w*|self.driving|driverless)', r'\b(traffic|modal|ridership|walking|cycling|transit|public transport|car trips|journeys)'),
         outcome=(r'\b(transport|traffic|mobil|vehicl|modal|walking|cycling|transit|ridership)',),
         topic='Automated mobility effect on transport mode and traffic', geography='Austria',
         sources=('Austrian transport statistics', 'national AV pilot assessments', 'national modal-split surveys'),
         note='A modal-share change without demonstrated AV deployment cannot test the conditional AV scenario.'),
    dict(id='eu_ageing', detect=(r'\bpopulation|\bdemograph', r'\b(elderly|ageing|aging|young|population size|member states)'),
         question='How have member-state populations and the elderly/youth age shares changed relative to the 2050 Eurostat projection?',
         searches=('Eurostat EU population age 65 share observed 2025', 'EU member states demographic ageing population count observed'),
         must=(r'\b(population|demograph|ageing|aging|65\+|elderly)', r'\b(age|65|elderly|youth|young|population|demograph)'),
         outcome=(r'\b(share|percent|population|size|aged|65|proportion)',),
         topic='Population size and age structure', geography='European Union member states',
         sources=('Eurostat population age series', 'Eurostat national population totals', 'Eurostat demographic methodology'),
         note='A projection update is not an observed change; EU aggregate ageing does not verify each member-state direction.'),
    dict(id='eu_overseas_land', detect=(r'\bland demand|\bland footprint|\bextensif', r'\b(europe|eu\s?27|outside europe|diet|farming)'),
         question='Were the assumed diet/agricultural changes implemented and did EU-related overseas agricultural land demand decline?',
         searches=('EU food consumption embodied overseas land footprint measured', 'Europe agricultural imports land footprint diet changes empirical'),
         must=(r'\b(land|hectare|footprint)', r'\b(import|overseas|outside europe|embodied|diet|consumption|agricultur)'),
         outcome=(r'\b(land|footprint|hectare)',),
         topic='EU overseas embodied agricultural land demand', geography='European Union',
         sources=('EEA consumption footprint accounts', 'Eurostat trade/land-use statistics', 'empirical land-footprint studies'),
         note='A nitrogen-emission study does not measure overseas land footprint. The scenario requires diet/farming conditions.'),
    dict(id='ireland_obesity_cost', detect=(r'\bobes|\bbmi\b', r'\bireland|\birish'),
         question='Did BMI change in Ireland as assumed and did measured obesity-attributable health expenditure follow the conditional scenario?',
         searches=('obesity BMI prevalence observed health costs Ireland', 'obesity attributable healthcare expenditure empirical Ireland'),
         must=(r'\b(obes|bmi|body mass index|overweight)', r'\b(healthcare|health care|expenditure|spending|medical cost|treatment cost|economic burden|bmi)'),
         outcome=(r'\b(bmi|obes|cost|expenditure|spending)',),
         topic='Irish BMI reduction and obesity-attributable healthcare costs', geography='Ireland',
         sources=('Irish health surveys', 'Irish obesity-related expenditure evaluations', 'OECD health profiles'),
         note='CVD expenses alone do not measure obesity-attributable savings; a modelled counterfactual is not an observation.'),
    dict(id='eastern_europe_health_resources', detect=(r'\b(medical workers|medical technology|general practitioners|scanners|magnetic resonance)', r'\b(eastern europe|balkan|medical)'),
         question='Did the stated eastern/southeastern European countries increase numbers of healthcare professionals and CT/MRI devices by 2025?',
         searches=('Eurostat eastern Europe doctors pharmacists CT MRI scanners 2025', 'Balkan countries healthcare personnel MRI CT units statistics'),
         must=(r'\b(doctor|physician|general practitioner|pharmacist|dentist|health (?:care )?(?:worker|personnel|professional)|ct scanner|computed tomography|computerized tomography|mri\b|magnetic resonance)',),
         outcome=(r'\b(number|count|density|per 100|per 1,000|rate|units|scanner|practitioner|dentist|pharmacist|personnel)',),
         topic='Healthcare workforce and CT/MRI equipment counts', geography='Eastern/southeastern European countries',
         sources=('Eurostat healthcare resources series', 'OECD/WHO health-resource counts', 'national health inventories'),
         note='A general paper about digital medical technology, 3D printing or workforce training does not measure workforce/CT/MRI counts.'),
    dict(id='eu_ghg_welfare_counterfactual', detect=(r'\b(carbon prices|carbon pricing|ghg emissions)', r'\bwelfare|\bgdp\b|\b2030'),
         question='Was the specific GHG policy implemented and what causal welfare evaluation, if any, measures its effect relative to the model reference?',
         searches=('EU greenhouse gas 2030 policy economic welfare evaluation realised', 'Europe climate policy welfare GDP counterfactual evaluation observed'),
         must=(r'\b(ghg|greenhouse gas|climate policy|carbon (?:price|pricing))', r'\b(welfare|gdp|economic benefit|economic cost|gross domestic)'),
         outcome=(r'\b(welfare|gdp|economic)',),
         topic='Economic welfare effect of a specific EU climate-policy scenario', geography='European Union',
         sources=('Commission policy implementation/evaluation', 'EEA GHG observations', 'peer-reviewed causal policy-impact studies'),
         note='Observed GDP and emissions separately cannot establish a counterfactual 0.6%-of-GDP welfare gain.'),
    dict(id='eu_cropland_soil_carbon', detect=(r'\bsoil (?:organic )?carbon|\bsoc stocks', r'\b(residue|tillage|cropland)'),
         question='Were residue retention and reduced tillage adopted and how did comparable soil organic-carbon stocks respond?',
         searches=('European cropland soil carbon residue retention reduced tillage measured', 'EU soil carbon stocks field experiment conservation tillage residues'),
         must=(r'\b(soil organic carbon|soc\b|soil carbon|carbon stock)', r'\b(residue|tillage|cropland|conservation agriculture|retention)'),
         outcome=(r'\b(carbon|soc\b|stock|soil)',),
         topic='EU soil-carbon stock under residue-retention and reduced-tillage conditions', geography='European cropland',
         sources=('LUCAS soil survey', 'field studies of tillage/residue interventions', 'JRC soil-carbon assessments'),
         note='A soil measurement without evidence of the stipulated practices can inform context but not verify their causal effect.'),
    dict(id='uk_domestic_bioenergy', detect=(r'\bbioenergy|\bbiomass', r'\b(imports?|indigenous|domestic|primary energy|uk\b)'),
         question='What share of UK primary energy was supplied by indigenous biomass, versus imports, and did the no-import scenario conditions occur?',
         searches=('UK indigenous domestic biomass supply share energy imports statistics', 'UK bioenergy domestic feedstock 2050 scenario observed'),
         must=(r'\b(biomass|bioenergy|biofuel|biogenic)', r'\b(domestic|indigenous|import|feedstock|energy supply|primary energy)'),
         outcome=(r'\b(energy|fuel|biomass|feedstock|supply)',),
         topic='UK indigenous biomass share of primary energy', geography='United Kingdom',
         sources=('UK DESNZ energy statistics', 'UK biomass supply monitoring', 'UK bioenergy feedstock imports'),
         note='General forestry governance and social innovations do not measure UK domestic biomass contribution.'),
)

EU_REGION = re.compile(r'\b(?:europe|european|eu\b|eu\s?27|eu\s?28|european union|member states|eurostat|easa|eea|jrc)\b', re.I)
SPECIFIC_GEO = {
    'Austria':re.compile(r'\baustria|\baustrian\b',re.I),
    'Ireland':re.compile(r'\bireland|\birish\b',re.I),
    'United Kingdom':re.compile(r'\buk\b|\bu\.k\.\b|\bunited kingdom|\bbritain|\bbritish\b',re.I),
    'Eastern/southeastern European countries':re.compile(r'\b(eastern europe|southeastern europe|balkan|bulgaria|romania|serbia|croatia|slovenia|hungary|slovakia|bosnia|albania|north macedonia|montenegro)\b',re.I),
}
NON_EU_GEO = re.compile(r'\b(?:japan|japanese|brazil|brazilian|china|chinese|india|indian|usa|u\.s\.|united states|australia|australian)\b',re.I)
OBSERVATION = re.compile(r'\b(?:observed|measured|recorded|statistics|data (?:show|indicate|reveal|confirm)|survey (?:data|found)|we (?:found|observed|measured)|(?:has|have|had) (?:risen|fallen|increased|decreased|declined|grown)|(?:increased|decreased|rose|fell|grew|declined) (?:by|from|to|between|in|over)|annual (?:figures|data)|reported (?:a|an|the) (?:rise|decline))\b',re.I)
EXPLICIT_NO_MEASURE = re.compile(r'\b(?:without (?:measuring|reporting|assessing)|not measured|no data on|did not measure)\b',re.I)
FUTURE_ONLY = re.compile(r'\b(?:we (?:model|project|forecast|simulate|predict)|modelled|modeled|projected|forecast|predicted|scenario|would|could|may|might|expected|by 20[3456789][0-9])\b',re.I)
SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')


def pick_plan(claim):
    """Find an observable issue family, otherwise explicitly decline to guess."""
    title=str(claim.get('title',''))
    original=str(claim.get('historical_focus') or claim.get('original_passage') or '')
    whole=title+' '+original
    for p in PLANS:
        if all(re.search(pattern,whole,re.I) for pattern in p['detect']):
            return p
    return None


def claim_card(claim):
    p=pick_plan(claim)
    quotation=str(claim.get('historical_focus') or claim.get('original_passage') or '')
    orig_year=int(str(claim.get('original_publication') or '1900')[:4])
    mentioned_years=sorted({int(v) for v in re.findall(r'\b20\d{2}\b',quotation) if int(v)>orig_year})
    numbers=list(dict.fromkeys(re.findall(
        r'\b\d+(?:[.,]\d+)?(?:\s*[–-]\s*\d+(?:[.,]\d+)?)?\s*(?:%|percent|PJ(?:/year)?|Mt(?:/year)?|million|billion|ha|hectares?|B€|€)',
        quotation,re.I)))[:8]
    explicit_conditions=[m.group(0).strip() for m in re.finditer(
        r'\b(?:if|provided|without|depending on|under|conditional on)\b[^.,;]{8,110}',quotation,re.I)][:4]
    return {
        'original_id': claim.get('id'),
        'source_quote': quotation,
        'years_mentioned_in_original_quote':mentioned_years,
        'quantified_markers_from_original_quote':numbers,
        'conditions_quoted_from_original':explicit_conditions,
        'question_for_research':p['question'] if p else None,
        'observable_construct':p['topic'] if p else None,
        'geographical_scope':p['geography'] if p else None,
        'reference_sources_to_check':list(p['sources']) if p else [],
        'scope_and_assumption_warning':p['note'] if p else 'No tested subject-specific evidence plan; original-source and domain review required.',
        'plan_id':p['id'] if p else None,
        'ready_for_automatic_search':bool(p),
        'claim_not_yet_fully_interpreted':True,
    }


def plan_queries(claim):
    p=pick_plan(claim)
    return list(p['searches'])[:2] if p else []


def scope_match(plan, title, abstract):
    content=title+' '+abstract
    place=plan['geography']
    pat=SPECIFIC_GEO.get(place)
    if pat is not None:
        return bool(pat.search(content))
    if place=='Europe' or place.startswith('European') or place.startswith('EU'):
        return bool(EU_REGION.search(content))
    return False


def assess_work(claim, work, abstract, original_year):
    """Return (candidate, exclusion reason). Never assert a verified outcome."""
    p=pick_plan(claim)
    if p is None:
        return None,'original_question_not_mapped_to_tested_evidence_plan'
    title=str(work.get('title') or '').strip()
    dated=str(work.get('publication_date') or '').strip()
    link=str(work.get('doi') or work.get('id') or '').strip()
    try:
        y=int(dated[:4])
    except (ValueError, TypeError):
        return None,'missing_publication_date'
    if y <= original_year or dated[:10]>date.today().isoformat() or not link.startswith('https://'):
        return None,'not_a_later_dated_citable_source'
    if not title or title.casefold()==claim.get('title','').casefold() or link.casefold().rstrip('/')==str(claim.get('source_url','')).casefold().rstrip('/'):
        return None,'original_or_missing_later_source'
    if not abstract or len(abstract)<90:
        return None,'insufficient_later_source_text'
    if not re.search(TITLE_GATE[p['id']],title,re.I):
        return None,'later_paper_title_not_about_claim_measure'
    if NON_EU_GEO.search(title) and not EU_REGION.search(title):
        return None,'later_study_about_different_geography'
    if not scope_match(p,title,abstract):
        return None,'later_geography_not_demonstrated'
    if not all(re.search(pattern,title+' '+abstract,re.I) for pattern in p['must']):
        return None,'different_outcome_or_mechanism'
    if not all(re.search(pattern,title+' '+abstract,re.I) for pattern in p['outcome']):
        return None,'required_measure_not_discussed'
    # The observed statement must itself mention the object of measurement,
    # not an unrelated finding in the same abstract.
    excerpts=[]
    for s in SENTENCE_SPLIT.split(abstract):
        if len(s)<40 or not OBSERVATION.search(s):
            continue
        if not all(re.search(pattern,s,re.I) for pattern in p['must']):
            continue
        if not all(re.search(pattern,s,re.I) for pattern in p['outcome']):
            continue
        if EXPLICIT_NO_MEASURE.search(s):
            continue
        if FUTURE_ONLY.search(s) and not re.search(r'\b(?:observed|measured|recorded|survey data|we found)\b',s,re.I):
            continue
        excerpts.append(' '.join(s.split())[:500])
    if not excerpts:
        return None,'no_observed_same_construct_passage_in_abstract'
    # Publication year is not observation year. Where the quoted result gives
    # *only* years preceding the original, it cannot document developments
    # afterwards, even if it was published later.
    observation_years=[int(y) for y in re.findall(r'\b(?:19|20)\d{2}\b',excerpts[0])]
    if observation_years and max(observation_years)<=original_year:
        return None,'observation_period_does_not_follow_original'
    # E.g. SAF airport consumption is useful but distinct from local production.
    comparability='unknown_needs_original_units_scope_baseline_and_full_text'
    if p['id']=='eu_renewable_jet_fuel' and re.search(r'\bairport|\bconsum|\bblended|\bdelivered\b',title+' '+abstract,re.I):
        comparability='proxy_airport_supply_not_eu_nonfood_rjf_production'
    if p['id']=='eu_cropland_soil_carbon' and not (re.search('residue',title+' '+abstract,re.I) and re.search('tillage',title+' '+abstract,re.I)):
        comparability='partial_conditions_not_both_management_practices'
    if p['id']=='eu_ghg_welfare_counterfactual':
        comparability='policy_counterfactual_requires_causal_evaluation'
    return {
        'later_title':title,'later_url':link,'later_date':dated,
        'later_indexed_abstract_observation':excerpts[0],
        'plan_id':p['id'],'claimed_subject':p['topic'],'later_source_role':'empirical_abstract_lead',
        'geography_match':'geography_mentioned_not_equivalence_verified',
        'measurement_comparability':comparability,
        'link_warrant':('The quoted later abstract discusses an observation concerning '+p['topic'].lower() +
            ' in a relevant geographical context. Its measurement basis and observation period still need source review.'),
        'original_and_later_geography_equivalent':None,
        'original_and_later_measure_equivalent':None,
        'original_and_later_baseline_equivalent':None,
        'observation_period_after_original_verified':False,
        'outcome_verified':False,'reported_by_later_paper_not_independently_verified':True,
        'source_review_required':True,
    },None
