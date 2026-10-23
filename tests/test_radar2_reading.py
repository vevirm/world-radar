import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from radar2_deep_search import extract_document, read_page, MAX_TEXT

def test_real_pdf_text_extraction():
    import fitz
    d=fitz.open()
    p=d.new_page()
    
    for y in range(80, 720, 24):
        p.insert_text((70,y),'Future trajectories and subsequent developments.')
    raw=d.tobytes()
    d.close()
    result=extract_document(raw,'application/pdf')
    assert result['status']=='page_text_read', result
    assert result['method']=='pdf_text'
    assert result['pdf_pages']==1
    assert 'Future trajectories' in result['excerpt']

def test_large_html_not_rejected_and_sample_bounded():
    raw=('<html><main>'+('Substantive developments described here. '*18000)+'</main></html>').encode()
    result=extract_document(raw,'text/html')
    assert result['status']=='page_text_read'
    assert result['sample_truncated']
    assert len(result['excerpt'])<MAX_TEXT+100

def test_reject_insecure_url():
    assert read_page('http://example.com')['status']=='unsupported_url'
