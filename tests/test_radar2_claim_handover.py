import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from radar2_25min import build_case


def example():
    return {'id':'study-123', 'title':'Hydrogen transport pathways in Europe',
            'original_publication':'2010-01-01',
            'original_passage':'Under the high uptake scenario, hydrogen-powered transport could expand across Europe by 2030.',
            'question_card':{'original_source':'https://example.org/study',
                             'readiness':'scenario_or_trajectory',
                             'issue_anchors':['hydrogen','transport']}}


def test_passage_and_question_card_survive_handover():
    source = example()
    result = build_case(source)
    assert result['original_id'] == source['id']
    assert result['original_passage'] == source['original_passage']
    assert result['question_card'] == source['question_card']
    assert result['original_source'] == 'https://example.org/study'
    assert result['readings'] == []


def test_missing_original_passage_must_stop():
    source = example()
    source['original_passage'] = ''
    with pytest.raises(ValueError, match='Missing original passage'):
        build_case(source)
