from scripts.forecast_screening import screen

def test_title_only_is_not_a_prediction():
    assert screen({'title':'Migration by 2030', 'abstract':''})['screening_status'] == 'full_text_required'

def test_quantified_date_forecast_is_only_a_candidate():
    s = screen({'title':'Test', 'abstract':'Research overview. We project that electricity demand will increase by 15% by 2030 under our baseline assumptions.'})
    assert s['screening_status'] == 'candidate_needs_validation'
    assert s['candidate_year'] == 2030

def test_policy_discussion_not_a_forecast():
    assert screen({'title':'Policy', 'abstract':'This paper discusses how European governance can work and what institutions might implement next.'})['screening_status'] == 'no_testable_prediction_in_metadata'
