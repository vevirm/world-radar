import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from radar2_source_selection import select_source

CLAIM = {'title': 'Hydrogen passenger transport infrastructure in Europe', 'original_publication': '2012-01-01'}

def candidate(title, date='2022-05-01', url='https://example.org/article'):
    return {'title': title, 'date': date, 'url': url, 'excerpt': ''}

def test_accepts_plausible_later_study_with_reason():
    keep, reason = select_source(CLAIM, candidate('Hydrogen transport infrastructure review'))
    assert keep and 'review' in reason

def test_rejects_earlier_paper():
    assert select_source(CLAIM, candidate('Hydrogen transport infrastructure review', '2010-01-01'))[1] == 'not_later_than_original'

def test_rejects_unrelated_title():
    assert not select_source(CLAIM, candidate('Sustainable urban housing investment'))[0]

def test_rejects_unsafe_url():
    assert select_source(CLAIM, candidate('Hydrogen transport infrastructure review', url='http://example.org'))[1] == 'unsupported_url'

def test_acceptance_is_not_evidence_of_outcome():
    keep, reason = select_source(CLAIM, candidate('Hydrogen transport infrastructure review'))
    assert keep and 'full_text' in reason
