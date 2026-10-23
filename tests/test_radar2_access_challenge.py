"""Avoid reporting publisher access blocks as read scientific papers."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from radar2_deep_search import extract_document


def test_challenge_page_is_not_read():
    html = '<html><body><h1>Client Challenge</h1><p>JavaScript is disabled in your browser. Please enable JavaScript to proceed.</p>' + ('<p>Required part of this site could not load.</p>' * 25) + '</body></html>'
    result = extract_document(html.encode(), 'text/html')
    assert result['status'] == 'access_challenge_not_read'
    assert 'excerpt' not in result


def test_actual_research_page_still_read():
    html = '<html><body><h1>European flood risk assessment</h1><p>' + ('The study reports changes in observed river flooding in Europe. ' * 12) + '</p></body></html>'
    result = extract_document(html.encode(), 'text/html')
    assert result['status'] == 'page_text_read'
    assert 'flood' in result['excerpt']


def test_small_text_still_insufficient():
    assert extract_document(b'<html><body>hello</body></html>', 'text/html')['status'] == 'insufficient_readable_text'
