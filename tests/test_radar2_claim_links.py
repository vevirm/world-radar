"""Evidence-link regression corpus; all excerpts are synthetic test fixtures.

The negative titles recreate the failure MODES in the earlier 10-study artifact;
no fixture is presented as a genuine empirical finding or verified outcome.
"""
from pathlib import Path
from scripts.radar2_ten_study_pilot import select_ten, candidate_for, research
from scripts.radar2_claim_links import claim_card, assess_work, plan_queries

ROOT=Path(__file__).resolve().parents[1]
SELECTED=select_ten(ROOT)

def original(plan):
    return next(c for c in SELECTED if claim_card(c)['plan_id']==plan)

def work(title,abstract,year='2025-01-01',suffix='test'):
    return dict(title=title,abstract=abstract,publication_date=year,
                doi=f'https://doi.org/10.9999/{suffix}')

def decision(plan, title, abstract, year='2025-01-01'):
    c=original(plan);w=work(title,abstract,year)
    return assess_work(c,w,abstract,int(c['original_publication'][:4]))


def test_ten_claims_get_distinct_questions_and_non_keyword_search_plans():
    ids=[claim_card(c)['plan_id'] for c in SELECTED]
    assert len(ids)==len(set(ids))==10
    assert all(claim_card(c)['question_for_research'] for c in SELECTED)
    assert all(len(plan_queries(c))==2 for c in SELECTED)
    assert all('What has subsequently been observed' not in claim_card(c)['question_for_research'] for c in SELECTED)
    assert all(claim_card(c)['claim_not_yet_fully_interpreted'] for c in SELECTED)


def test_austria_breast_milk_is_not_mobility_evidence():
    hit, reason=decision('austria_automated_mobility',
        'Persistent Organic Pollutants in Austrian Human Breast Milk',
        'In Austria samples from breast milk were collected and pollutants were measured between 2015 and 2019. ' * 2)
    assert hit is None and reason in ('different_outcome_or_mechanism','later_paper_title_not_about_claim_measure')


def test_eastern_europe_3d_printing_is_not_staff_and_scanner_counts():
    hit,reason=decision('eastern_europe_health_resources',
        'Medical 3D printing using material jetting in Eastern Europe',
        'Observed advances in digital technology for surgical implants in Eastern Europe. New digital 3D printing methods are widely studied.' * 2)
    assert hit is None


def test_jet_fuel_timber_governance_is_not_rjf_supply():
    hit,reason=decision('eu_renewable_jet_fuel',
       'European EU governance in timber and biofuel supply chains',
       'Our study observed that timber governance for biofuel supply had changed in Europe, without measuring aviation jet fuel volumes.' * 2)
    assert hit is None


def test_flood_road_event_damage_not_european_economic_loss():
    hit,reason=decision('europe_flood_damage',
       'Flood risk of the European road network',
       'We observed flood damage to roads in Germany in a 2020 event, including disruption of traffic and road mobility. ' * 2)
    assert hit is None


def test_bioenergy_forestry_governance_not_domestic_uk_energy_share():
    hit,reason=decision('uk_domestic_bioenergy',
       'Social innovation and sustainable forestry across Europe',
       'We observed changes in regional forest management governance and forest social innovation in British communities. ' * 2)
    assert hit is None


def test_same_construct_empirical_flood_lead_is_still_unverified():
    hit,reason=decision('europe_flood_damage',
       'European observed flood economic losses by year',
       'From European economic flood damage data collected between 2018 and 2023, we observed an increase in annual flood financial losses in several regions. ' * 2)
    assert reason is None and hit is not None
    assert 'flood-only' in hit['link_warrant']
    assert hit['outcome_verified'] is False
    assert hit['observation_period_after_original_verified'] is False


def test_airport_saf_supply_is_explicitly_not_eu_nonfood_rjf_production():
    hit,reason=decision('eu_renewable_jet_fuel',
       'EU airport sustainable aviation fuel supply monitoring',
       'We measured sustainable aviation fuel supplied at EU airports in 2025 and observed growth in airport deliveries of SAF aviation fuel. ' * 2)
    assert reason is None
    assert hit['measurement_comparability']=='proxy_airport_supply_not_eu_nonfood_rjf_production'
    assert not hit['outcome_verified']


def test_eu_ageing_observation_can_be_proposed_not_concluded():
    hit,reason=decision('eu_ageing',
       'Observed Eurostat European Union population ageing',
       'We observed the population aged 65 and over increase in EU member states using Eurostat annual demographic statistics through 2024. ' * 2)
    assert hit is not None and reason is None
    assert hit['later_source_role']=='empirical_abstract_lead'


def test_older_observation_replication_published_later_is_not_later_event():
    hit,reason=decision('europe_flood_damage',
       'European flood losses in 1990-2005, published in 2025',
       'Our reanalysis of European annual economic flood damage measured from 1990 to 2005 observed a decline in economic flood loss during that earlier period. ' * 2)
    assert hit is None and reason=='observation_period_does_not_follow_original'



def test_unrelated_clinical_review_with_incidental_ageing_claim_is_rejected():
    hit,reason=decision('eu_ageing',
        'Literature review of polypharmacotherapy for elderly people in Poland and Europe',
        'In recent years Europe has observed demographic ageing of the population, but this review studies neurological treatment and medications in old age. ' * 2)
    assert hit is None and reason=='later_paper_title_not_about_claim_measure'


def test_no_safe_fallback_for_unmapped_question():
    c={'id':'toy','title':'The future of underwater music in Europe',
       'historical_focus':'We envision underwater music streaming by the year 2050.'}
    card=claim_card(c)
    assert not card['ready_for_automatic_search']
    assert plan_queries(c)==[]


def test_bounded_run_keeps_search_absence_separate_from_substantive_evidence_gap():
    report=research(SELECTED,'key-present',lambda query,year:[])
    assert report['verified_outcomes']==report['published_outcomes']==0
    assert report['openalex_queries_completed']==20
    assert not any(c['no_meaningful_link_established'] for c in report['cases'])
    assert not any(c['fully_investigated_evidence_gap'] for c in report['cases'])
    assert all(c['claim_evidence_plan']['observable_construct'] for c in report['cases'])
