"""Don't accidentally turn weak follow-ups into attractive but fake grades."""
from scripts.storybook import make_stories, progress_meter, hindsight_rating


def test_editor_score_requires_explanation_and_complete_rubric():
    case = {'hindsight_review': {'clarity': 70, 'anticipation': 80, 'usefulness': 60}}
    assert hindsight_rating(case) is None
    case['hindsight_review']['reason'] = 'Original claim matches later independent measurements within the same geography.'
    assert hindsight_rating(case)['value'] == 73
    case['hindsight_review']['anticipation'] = 101
    assert hindsight_rating(case) is None


def test_source_linked_policy_goal_gets_only_separate_progress_meter():
    item = {'original_lead_title_contains':'Historic energy forecast',
            'expected': 'A policy goal', 'happened': 'Recent level was measured.',
            'topic': 'Energy', 'sources': [{'url': 'https://example.org/independent', 'date': '2025'}],
            'progress_indicator': {'value': 25.2, 'goal': 42.5, 'metric': 'EU share', 'as_of': '2024'}}
    data = make_stories([{'id':'lead-test','title':'Historic energy forecast for Europe'}], [], [item])
    story = data['stories'][0]
    assert story['hindsight_rating'] is None
    assert story['progress_meter']['value'] == 59
    assert 'NOT a hindsight grade' in story['progress_meter']['label']


def test_unsourced_outcome_and_academic_abstract_cannot_be_scored():
    lead = {'id': 'lead-1', 'title': 'We may all ride airships', 'source_url': 'https://example.org/paper',
            'literature_signal': 'later_studies_report_results', 'candidate_excerpt': 'Airships by 2040'}
    observation = {'topic': 'Not real', 'expected': 'Prediction', 'happened': 'Apparently came true', 'sources': []}
    data = make_stories([lead], [], [observation])
    assert data['stories'] == []
    assert data['summary']['reviewed_forecasts'] == 0
    assert progress_meter({'progress_indicator': {'value': 10, 'goal': 0, 'metric': 'a', 'as_of': '2024'}}) is None


def test_unlinked_policy_snapshots_do_not_enter_radar2():
    item={'original_lead_title_contains':'A discarded paper', 'topic':'Example',
          'expected':'Policy target', 'happened':'An observed figure',
          'sources':[{'url':'https://example.org/data','date':'2025'}]}
    data=make_stories([{'id':'lead-accepted','title':'Accepted future scenarios'}],[],[item])
    assert data['stories']==[]
