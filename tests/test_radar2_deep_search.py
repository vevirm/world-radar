import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from radar2_deep_search import investigate,read_page

def test_reading_audit():
    reports=[{'original_id':'abc','leads':[{'url':'https://example.org/doc','title':'Study','published':'2021'}]}]
    actual=investigate(reports,reader=lambda url:{'status':'page_text_read','excerpt':'Something happened'})
    assert actual[0]['pages_read']==1
    assert actual[0]['source_readings'][0]['connection_status']=='not_assessed'
    assert not actual[0]['source_readings'][0]['observed_development_confirmed']

def test_bad_url_is_not_read():
    assert read_page('http://example.com')['status']=='unsupported_url'

def test_bounded():
    reports=[{'original_id':'a','leads':[{'url':'https://example.org','title':'t'} for _ in range(10)]}]
    assert investigate(reports,max_per_claim=3,reader=lambda x:{'status':'fetch_error'})[0]['read_attempts']==3
