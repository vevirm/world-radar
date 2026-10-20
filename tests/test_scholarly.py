"""Offline tests: abstract indexing is not full-text or retrospective verification."""
from datetime import date
from pathlib import Path
from unittest.mock import patch
import json
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import scholarly

ABSTRACT = ('This research develops participatory scenario planning for the European Union and '
            'Europe by 2040. We compare alternative futures using interviews, archival data, '
            'expert elicitation and cross-impact analysis across different institutions. '
            'The study explores the potential effects of energy transition pathways on '
            'regional innovation and European climate governance, discussing uncertainty '
            'and social consequences through qualitative synthesis with linked evidence.')


def crossref_item(doi='10.1016/j.futures.2020.123456', abstract=ABSTRACT, year=2020):
    return {'DOI': doi, 'title': ['Scenario planning for the European Union to 2040'],
            'abstract': '<jats:p>'+abstract+'</jats:p>',
            'container-title': ['Futures'], 'publisher': 'Example Publisher',
            'published': {'date-parts': [[year, 6, 1]]}}


def openalex_item():
    text = ABSTRACT.split()
    index = {}
    for i, word in enumerate(text):
        index.setdefault(word, []).append(i)
    return {'doi': 'https://doi.org/10.1016/j.futures.2020.123456',
            'title': 'Scenario planning for the European Union to 2040',
            'publication_date': '2020-06-01',
            'abstract_inverted_index': index,
            'primary_location': {'source': {'display_name': 'Futures'}},
            'best_oa_location': {'pdf_url': 'https://university.example/paper.pdf'}}


def test_extracts_crossref_abstract_markup_and_date():
    lead = scholarly.crossref_lead(crossref_item())
    assert 'jats:' not in lead['abstract']
    assert scholarly.credible_abstract(lead, date(2011,10,19), date(2026,4,16))
    assert lead['journal'] == 'Futures'
    assert lead['date'] == '2020-06-01'


def test_openalex_abstract_can_enrich_a_crossref_record():
    a = scholarly.crossref_lead(crossref_item(abstract=''))
    b = scholarly.openalex_lead(openalex_item())
    result = scholarly.merge_lead(scholarly.merge_lead(None, a, '2026-10-16'), b, '2026-10-16')
    assert result['doi'] == a['doi']
    assert result['indexes'] == ['Crossref', 'OpenAlex']
    assert result['open_access_pdf'] == 'https://university.example/paper.pdf'
    assert len(result['abstract'].split()) >= scholarly.MIN_ABSTRACT_WORDS
    assert result['status'] == 'Abstract indexed — full study unverified'


def test_abstract_only_is_discovery_not_a_quality_pass():
    lead = scholarly.crossref_lead(crossref_item())
    result = scholarly.merge_lead(None, lead, '2026-10-16')
    assert 'quality' not in result
    assert 'comparison' not in result
    assert 'fulltext_verified' not in result
    assert result['claim_status'] == 'No retrospective verdict'


def test_rejects_abstract_with_no_european_or_futures_relevance():
    record = scholarly.crossref_lead(crossref_item())
    record['title'] = 'Trends in food pricing'
    record['abstract'] = 'Food market practices can influence local business conditions. ' * 14
    assert not scholarly.credible_abstract(record, date(2011,10,19), date(2026,4,16))


def test_date_window_and_undated_crossref_metadata_are_strict():
    assert scholarly.year_windows(date(2026,4,16))[-1] == ('2025-01-01', '2026-04-16')
    assert not scholarly.credible_abstract(scholarly.crossref_lead(crossref_item(year=2010)),
                                           date(2011,10,19), date(2026,4,16))
    assert not scholarly.credible_abstract(scholarly.crossref_lead(crossref_item(year=2026)),
                                           date(2011,10,19), date(2026,4,16))
    x = crossref_item()
    x.pop('published')
    assert scholarly.crossref_lead(x) is None


def test_scholarly_scan_remembers_cursor_and_doi_between_runs(tmp_path):
    state_path = tmp_path/'radar-state.json'
    leads_path = tmp_path/'research-leads.json'
    found = scholarly.crossref_lead(crossref_item())
    with patch.object(scholarly, 'fetch_index', return_value=[found]):
        first = scholarly.scholarly_scan(state_path, leads_path, date(2026,4,16),
                                          time.monotonic()+100, max_queries=4)
        second = scholarly.scholarly_scan(state_path, leads_path, date(2026,4,16),
                                           time.monotonic()+100, max_queries=3)
    assert first['new_leads'] == 1
    assert second['new_leads'] == 0
    assert second['total_leads'] == 1
    state = json.loads(state_path.read_text())
    assert state['scholarly_cursor'] == 7
    assert state['scholarly_queries_completed'] == 7
    assert len(json.loads(leads_path.read_text())['leads']) == 1


def test_crossref_and_journal_specific_search_parameters():
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'message': {'items': [crossref_item()]}}
    with patch.object(scholarly.requests, 'get', return_value=Response()) as get:
        hits = scholarly.fetch_index('Crossref', 'Europe scenarios', '2019-01-01',
                                     '2020-12-31', journal='Futures')
    assert len(hits) == 1
    assert 'container-title:Futures' in get.call_args.kwargs['params']['filter']
    assert get.call_args.kwargs['params']['rows'] == 35


def test_openalex_query_uses_optional_key():
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'results': [openalex_item()]}
    with patch.object(scholarly.requests, 'get', return_value=Response()) as get:
        hits = scholarly.fetch_index('OpenAlex', 'Europe scenarios', '2019-01-01',
                                     '2020-12-31', key='test-key')
    assert len(hits) == 1
    assert get.call_args.kwargs['params']['api_key'] == 'test-key'


def test_journals_and_abstracts_visible_separate_from_findings():
    page = (Path(__file__).resolve().parents[1] / 'index.html').read_text()
    assert 'id="research"' in page and 'id="lead-list"' in page
    assert "load('research-leads.json')" in page
    assert 'full study and retrospective outcome NOT verified' in page.lower() or 'Full study and retrospective outcome NOT verified' in page
    workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/update-radar.yml').read_text()
    assert 'git add findings.json radar-state.json research-leads.json' in workflow
    assert 'OPENALEX_API_KEY: ${{ secrets.OPENALEX_API_KEY }}' in workflow
    assert 'elapsed < 835' in workflow and 'elapsed < 535' in workflow


def test_title_only_doi_lead_remains_unverified():
    record = scholarly.crossref_lead(crossref_item(abstract=''))
    assert scholarly.credible_bibliographic_lead(record, date(2011,10,19), date(2026,4,16))
    assert not scholarly.credible_abstract(record, date(2011,10,19), date(2026,4,16))
    stored = scholarly.merge_lead(None, record, '2026-10-16')
    assert stored['status'] == 'DOI/title indexed — abstract not in metadata'
    assert stored['claim_status'] == 'No retrospective verdict'


def test_abstract_enrichment_upgrades_metadata_only_lead():
    from_metadata = scholarly.merge_lead(None, scholarly.crossref_lead(crossref_item(abstract='')), '2026-10-16')
    enriched = scholarly.merge_lead(from_metadata, scholarly.openalex_lead(openalex_item()), '2026-10-16')
    assert enriched['status'] == 'Abstract indexed — full study unverified'


def test_weak_title_does_not_enter_metadata_only_discovery():
    candidate = scholarly.crossref_lead(crossref_item(abstract=''))
    candidate['title'] = 'New EU Policy'
    assert not scholarly.credible_bibliographic_lead(candidate, date(2011,10,19), date(2026,4,16))


def test_page_can_show_title_only_leads_and_browse_more_than_40():
    html = (Path(__file__).resolve().parents[1] / 'index.html').read_text()
    assert 'research-leads.json' in html
    assert 'This index has not supplied an abstract' in html
    assert 'const perPage=20' in html and "$('next').onclick" in html
    assert 'Full study and retrospective outcome NOT verified' in html
