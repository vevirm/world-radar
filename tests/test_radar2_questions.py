"""No-scan source-question and direct evidence continuity guard tests."""
import json
from pathlib import Path
from scripts.radar2_questions import question_card, audit
from scripts.evidence_engine import original_question_alignment
from scripts.evidence_pilot import claim_from


def base(**overrides):
    case={'id':'lead-abc','title':'Health impact assessment of waste management facilities in three European countries',
            'source_kind':'academic','source_url':'https://doi.org/10.5555/original',
            'original_publication':'2012-02-01',
            'original_passage':('Assuming the incinerators continue operating until 2020, '
                                'the annual number of cancer cases due to exposure was expected '
                                'to reach 11 in 2020 and decline by 2050.'),
            'investigation_type':'projection_or_forecast'}
    return {**case,**overrides}


def test_specific_projection_is_not_lost_and_generates_reviewable_question():
    item=question_card(base())
    assert item['readiness']=='quantified_future_proposition'
    assert '2012' in item['original_publication']
    assert item['target_year_mentions']==[2020,2050]
    assert item['status']=='not_assessed'
    assert item['original_passage'].startswith('Assuming')
    assert item['evidence_question'].startswith('What has subsequently')


def test_institutional_without_source_is_not_a_fake_forecast():
    item=question_card(base(original_passage='',source_kind='institutional'))
    assert item['readiness']=='original_text_required'
    assert not item['issue_anchors']
    assert not item['evidence_question']


def test_weak_methods_fragment_needs_review_before_automatic_research():
    item=question_card(base(original_passage='This paper introduces a framework for improving foresight research and its organisational structure in Europe.'))
    assert item['readiness']=='source_review_required'


def test_same_title_keywords_do_not_make_clinical_waste_an_outcome():
    claim=base()
    good,why=original_question_alignment(claim,'Hospital waste management and disposal practices in health care facilities',
         'This hospital study reports clinical waste sorting procedures.')
    assert not good and 'passage-specific object' in why
    good,why=original_question_alignment(claim,'European incinerator emissions and cancer risk',
         'Measured cancer incidence related to incinerator exposure in European municipalities.')
    assert good


def test_scenario_is_not_asserted_as_inevitable_prediction():
    item=question_card(base(
        title='Possible European electricity futures under alternative scenarios',
        original_passage='We consider three alternative scenarios of electricity demand in Europe by 2050, ranging from high renewable to fossil fuel paths.',
        investigation_type='alternative_scenarios'))
    assert item['scenario_is_not_prediction']
    assert item['status']=='not_assessed'
    assert item['readiness'] in ('scenario_or_trajectory','quantified_future_proposition')


def test_pilot_uses_saved_original_passage_not_fuzzy_abstract():
    seed=base(); lead={'title':seed['title'],'date':seed['original_publication'],
        'url':seed['source_url'],'original_id':seed['id'],
        'original_passage':seed['original_passage'],
        'abstract':'Unrelated abstract about a generic health framework.'}
    claim=claim_from(lead)
    assert 'incinerators' in claim['expected']
    assert 'generic health framework' not in claim['expected']


def test_full_repo_preview_is_pure_and_follows_accepted_handoff(tmp_path):
    # No file writes, no API or URL requests. The data is an inspectable report.
    root=Path(__file__).resolve().parents[1]
    before=(root/'retrospective-results.json').read_bytes()
    report=audit(root)
    assert report['academic']==369 and report['institutional']==29
    assert len(report['cards'])==398
    assert report['readiness_counts']['original_text_required']==29
    assert before==(root/'retrospective-results.json').read_bytes()
