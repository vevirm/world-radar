"""Offline tests for historical range, non-EU actors and substantive foresight gates."""
import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import radar


def full_study(eu=True, word_count=3500, pages=25, bibliography=True):
    intro = ('The European Union faces multiple transitions in Europe. ' if eu else 'This global economy faces multiple transitions. ')
    body = ('Research methodology: Our Delphi expert interviews and participatory scenario building '
            'used stakeholder workshops, a literature review and horizon scanning to create '
            'alternative future scenarios in Europe by 2035. We compare baseline trajectories '
            'and explore possible outcomes and implications of EU policy choices. '
            'Scenarios in 2040 could reshape institutions; several trends may interact. ')
    if not eu:
        body = body.replace('in Europe', 'globally').replace('EU policy', 'local policy')
    content = intro + body * (word_count // len(body.split()) + 1)
    if word_count >= 2600:
        content += ' '.join(f'Investigation subsection thematic dimension_{i} considers heterogeneous regional challenges.' for i in range(240))
    if bibliography:
        content += ' References ' + ' '.join(f'Scholar {i} (20{10 + i}) Journal of Futures Studies, doi:10.1/ABC{i}.' for i in range(12))
    return {'titles': ['European Futures Foresight Report 2035'], 'dates': {date(2020, 9, 9)},
            'years': set(), 'text': content, 'links': [], 'pages': pages, 'format': 'pdf'}


def test_calendar_window_and_hard_start():
    assert radar.START_DATE == radar.earliest_date(radar.TODAY())
    assert radar.cutoff(date(2026, 10, 16)) == date(2026, 4, 16)
    assert radar.cutoff(date(2026, 8, 31)) == date(2026, 2, 28)
    assert radar.cutoff(date(2026, 3, 31)) == date(2025, 9, 30)


def test_registry_encompasses_academia_and_independents():
    registry = radar.get_registry()
    assert len(registry) >= 17
    categories = {actor['category'] for actor in registry}
    for category in ('EU institution / agency', 'Independent think tank', 'University / research centre',
                     'Research institute', 'International organisation', 'EU-funded research consortium'):
        assert category in categories
    assert all(radar.trusted_host(s['url']) in a['domain_hosts'] for a in registry for s in a['seeds'])
    assert radar.trusted_host('https://commission.europa.eu/foresight') == 'commission.europa.eu'
    assert radar.trusted_host('http://commission.europa.eu/foresight') is None
    assert radar.trusted_host('https://ceps.eu.evil.com/paper') not in next(a for a in registry if a['id']=='ceps')['domain_hosts']


def test_quality_screen_substantial_eu_university_study():
    actor = next(a for a in radar.get_registry() if a['id'] == 'utu-ffrc')
    result = radar.quality_screen(full_study(), actor, 'European Futures Foresight Report 2035')
    assert result['word_count'] >= 3000
    assert result['pdf_pages'] == 25
    assert all(result['checks'].values())


def test_quality_screen_rejects_2_pager_even_if_dense():
    actor = next(a for a in radar.get_registry() if a['id'] == 'ec')
    with pytest.raises(ValueError, match='meaningful_document_length'):
        radar.quality_screen(full_study(pages=2), actor, 'European Futures Report')


def test_quality_screen_rejects_sparse_ten_page_paper():
    actor = next(a for a in radar.get_registry() if a['id'] == 'ec')
    with pytest.raises(ValueError, match='substantial_full_text'):
        radar.quality_screen(full_study(word_count=300, pages=10), actor, 'European Foresight Report')


def test_quality_screen_rejects_long_but_unsourced_paper():
    actor = next(a for a in radar.get_registry() if a['id'] == 'ec')
    with pytest.raises(ValueError, match='traceable_evidence_and_sources'):
        radar.quality_screen(full_study(bibliography=False), actor, 'European Futures Report')


def test_quality_screen_rejects_unrelated_external_paper():
    actor = next(a for a in radar.get_registry() if a['id'] == 'oecd')
    with pytest.raises(ValueError, match='eu_europe_focus'):
        radar.quality_screen(full_study(eu=False), actor, 'Global Futures Foresight Report')


def fake_verify_candidate(date_hint='2020-09-09', actor_id='ceps'):
    return {'actor_id': actor_id, 'title': 'European Futures Foresight Report 2035',
            'date_hint': date_hint, 'topic': 'EU governance',
            'source_mode': 'historic catalogue seed (unverified)',
            'url': 'https://www.ceps.eu/foresight-paper/'}


def test_non_eu_full_report_passes_without_unproven_actualization():
    actors = {a['id']: a for a in radar.get_registry()}
    candidate = fake_verify_candidate()
    landing = b'''<html><head><meta property="article:published_time" content="2020-09-09"></head>
        <body><main><h1>European Futures Foresight Report 2035</h1>
        <p>Report 9 September 2020. A 2040 scenario analysis of EU policy options.</p>
        </main></body></html>'''
    mockdoc = full_study()
    with patch.object(radar, 'get_page', return_value=(candidate['url'], landing, 'text/html')):
        with patch.object(radar, 'full_document', return_value=(candidate['url']+'full.pdf', mockdoc)):
            result = radar.verify_report(candidate, actors, {})
    assert result['date'] == '2020-09-09'
    assert result['source_category'] == 'Independent think tank'
    assert result['relationship_to_eu'] == 'External research about EU/Europe'
    assert result['comparison']['verdict'] == 'Not yet assessed'
    assert result['quality']['word_count'] > 2600
    assert result['full_text_url'].endswith('full.pdf')


@pytest.mark.parametrize('report_date, expected', [('2026-08-01','Too recent'),('2010-12-31','predates rolling 15-year')])
def test_window_bounds_reject(report_date, expected):
    actors = {a['id']: a for a in radar.get_registry()}
    candidate = fake_verify_candidate(date_hint=report_date)
    landing = f'''<html><head><meta name="datePublished" content="{report_date}"></head>
        <body><main><h1>European Futures Foresight Report 2035</h1></main></body></html>'''.encode()
    with patch.object(radar, 'get_page', return_value=(candidate['url'], landing, 'text/html')):
        with pytest.raises(ValueError, match=expected):
            radar.verify_report(candidate, actors, {})


def test_no_unverified_edits_and_no_hinted_date_only():
    info = {'dates': set(), 'years': set(), 'text': 'Some horizon to 2030.'}
    assert radar.select_publication_date(info, '2020-01-01')[0] is None
    with pytest.raises(ValueError, match='Assessment missing'):
        radar.verify_assessment({'verdict': 'Observed'}, date(2020, 1, 1), 'original')


def test_source_date_from_publisher_document_download():
    html = b'''<html><body><main><h1>2022 Strategic Foresight Report</h1>
    <p>Full study on Europe in 2040.</p><h2>Documents</h2>
    <p>Strategic Foresight Report 2022 - 21 June 2022 - English Download</p>
    </main></body></html>'''
    info = radar.page_info(html)
    assert radar.select_publication_date(info, '2022-06-21')[0] == date(2022, 6, 21)


def test_previous_joke_findings_cannot_reenter_published_data():
    data = radar.read_json(radar.RESULTS)
    assert data['schema_version'] == 2
    assert data['earliest_publication_date'] == radar.START_DATE.isoformat()
    assert all(x['id'].startswith('EUF-') and x['quality']['status'] == 'automated research-substance screen passed' for x in data['findings'])


def test_workflow_still_enforces_14_then_9_minutes_and_twice_daily_schedule():
    yml = (radar.ROOT/'.github/workflows/update-radar.yml').read_text()
    assert '--minutes 14' in yml
    assert '--minutes 9' in yml
    assert "17 1,13 * * *" in yml
    assert 'git add findings.json radar-state.json' in yml


def test_source_rotation_covers_every_group_before_repeating():
    actors = radar.get_registry()
    state = radar.empty_state()
    batches = [radar.next_actor_batch(actors, state) for _ in range(4)]
    ids = [a['id'] for batch in batches for a in batch]
    assert len(set(ids[:len(actors)])) == len(actors)
    assert ids[0] != ids[radar.ACTORS_PER_RUN]
    assert {a['category'] for a in batches[0]} >= {
        'EU institution / agency', 'Independent think tank', 'University / research centre'}


def test_archive_pages_cooldown_and_next_page():
    actor = {'id': 'test', 'archives': ['https://example.org/reports'],
             'domain_hosts': ['example.org']}
    state = radar.empty_state()
    d = date(2026, 10, 16)
    assert radar.page_queue(actor, state, d) == ['https://example.org/reports']
    state['archive_pages']['test']['https://example.org/reports']['last_scan'] = d.isoformat()
    html = {'links': [('Next page', '/reports?page=2'), ('Page 3', '/reports/page/3'),
                      ('External reports', 'https://evil.example/reports?page=4'),
                      ('Foresight publications', '/reports/archive')]}
    assert radar.pagination_links(actor, 'https://example.org/reports', html) == [
        'https://example.org/reports?page=2', 'https://example.org/reports/page/3']
    assert radar.archive_trail_links(actor, 'https://example.org/reports', html, 0) == [
        'https://example.org/reports/archive']
    state['archive_pages']['test']['https://example.org/reports?page=2'] = {
        'root': False, 'last_scan': None, 'depth': 0}
    assert radar.page_queue(actor, state, d) == ['https://example.org/reports?page=2']
    state['archive_pages']['test']['https://example.org/reports?page=2']['last_scan'] = d.isoformat()
    assert radar.page_queue(actor, state, d) == []
    assert radar.page_queue(actor, state, date(2026, 10, 17)) == ['https://example.org/reports']


def test_rejected_and_accepted_reports_not_rescanned_each_run():
    state = radar.empty_state()
    today = date(2026, 10, 16)
    c = fake_verify_candidate()
    c['url'] = 'https://www.ceps.eu/foresight-paper/?utm_campaign=x'
    assert radar.offer_candidate(state, c, set(), today) == 'queued'
    assert radar.offer_candidate(state, c, set(), today) == 'already-queued'
    key = radar.clean_url(c['url'])
    state['queue'] = []
    state['documents'][key] = {'status': 'rejected', 'retry_after': '2026-12-01'}
    assert radar.offer_candidate(state, c, set(), today) == 'cooldown'
    assert radar.offer_candidate(state, c, set(), date(2026, 12, 1)) == 'queued'
    state['queue'] = []
    state['documents'][key] = {'status': 'accepted'}
    assert radar.offer_candidate(state, c, set(), today) == 'already-published'
    assert radar.offer_candidate(state, fake_verify_candidate(date_hint='2026-07-01'), set(), today) == 'outside-window'


def test_discovery_state_survives_runs(tmp_path):
    from unittest.mock import patch
    actor = {'id': 'foo', 'category': 'University / research centre',
             'archives': ['https://example.org/foresight'], 'domain_hosts': ['example.org'],
             'seeds': []}
    html = b'<main><a href="/foresight/report-2035">Foresight scenarios for 2035</a>' \
           b'<a href="/foresight?page=2">Next</a></main>'
    (tmp_path/'findings.json').write_text('{"findings": []}')
    paths = {'RESULTS': tmp_path/'findings.json', 'STATE': tmp_path/'radar-state.json',
             'CANDIDATES': tmp_path/'candidates.json'}
    with patch.multiple(radar, **paths), \
         patch.object(radar, 'get_registry', return_value=[actor]), \
         patch.object(radar, 'get_page', return_value=('https://example.org/foresight', html, 'text/html')) as fetch, \
         patch.object(radar, 'TODAY', return_value=date(2026, 10, 16)):
        radar.discover(float('inf'))
        state = radar.load_state()
        assert len(state['queue']) == 1
        assert len(state['archive_pages']['foo']) == 2
        assert fetch.call_count == 1
        radar.discover(float('inf'))
        state2 = radar.load_state()
        assert state2['runs'] == 2
        assert len(state2['queue']) == 1
        assert fetch.call_count == 2  # second run examines unseen pagination, NOT root
        assert fetch.call_args[0][0] == 'https://example.org/foresight?page=2'
        radar.discover(float('inf'))
        assert fetch.call_count == 2  # no repeated pages within cooldown


def test_verification_persists_failed_cooldown_and_next_item(tmp_path):
    actor = next(a for a in radar.get_registry() if a['id'] == 'ceps')
    state = radar.empty_state()
    c1 = fake_verify_candidate()
    c2 = dict(c1, url='https://www.ceps.eu/another-report/', title='Another report')
    state['queue'] = [c1, c2]
    (tmp_path/'radar-state.json').write_text(json.dumps(state))
    (tmp_path/'findings.json').write_text((radar.ROOT/'findings.json').read_text())
    (tmp_path/'assessments.json').write_text('{"assessments": []}')
    (tmp_path/'candidates.json').write_text('{"sources_this_run": ["ceps"]}')
    def fake_verify(candidate, _actors, _review):
        raise ValueError('Missing credible research methodology')
    with patch.multiple(radar, STATE=tmp_path/'radar-state.json', RESULTS=tmp_path/'findings.json',
                        AUDIT=tmp_path/'scan-report.json', CANDIDATES=tmp_path/'candidates.json',
                        ROOT=tmp_path), \
         patch.object(radar, 'get_registry', return_value=[actor]), \
         patch.object(radar, 'verify_report', side_effect=fake_verify) as verify, \
         patch.object(radar, 'TODAY', return_value=date(2026, 10, 16)):
        radar.verify_until(float('inf'))
        assert verify.call_count == 2
        assert radar.load_state()['queue'] == []
        for doc in radar.load_state()['documents'].values():
            assert doc['status'] == 'rejected'
            assert doc['retry_after'] == '2026-11-30'
        radar.verify_until(float('inf'))
        assert verify.call_count == 2  # not reprocessed on subsequent run


def test_extracts_future_claim_not_generic_foresight_rhetoric():
    content = ('Mainstream bureaucracy’s implicit understanding of the future is linear '
               '– essentially, that tomorrow will be more of today. '
               'By 2035, Europe could face rising energy import dependencies and '
               'increased migration pressures if climate disruptions accelerate. '
               'This report explores different foresight methodologies.')
    assert 'By 2035' in radar.source_excerpt(content)
    assert 'tomorrow will' not in radar.source_excerpt(content)


def test_no_vague_sentence_passes_as_forecast():
    assert radar.source_excerpt('The future may be complicated. Tomorrow will be more of today. ') == ''


def test_pdf_original_year_can_confirm_undated_publisher_landing():
    actors = {a['id']: a for a in radar.get_registry()}
    candidate = fake_verify_candidate(date_hint=None)
    landing = b'<html><body><h1>European Futures Foresight Report 2035</h1>' \
              b'<p>Download the full foresight research.</p></body></html>'
    full = full_study()
    full['years'] = {2020}
    full['dates'] = set()
    with patch.object(radar, 'get_page', return_value=(candidate['url'], landing, 'text/html')):
        with patch.object(radar, 'full_document', return_value=(candidate['url']+'full.pdf', full)):
            result = radar.verify_report(candidate, actors, {})
    assert result['date'] == '2020-12-31'
    assert result['date_precision'] == 'year'


def test_full_window_waits_until_deadline_and_emits_progress(capsys):
    """Production phase clocks cannot silently turn 15+10 into up-to 15+10."""
    current = [100.0]
    sleeps = []
    def fake_sleep(seconds):
        assert 0 < seconds <= 30
        sleeps.append(seconds)
        current[0] += seconds
    with patch.object(radar.time, 'monotonic', side_effect=lambda: current[0]), \
         patch.object(radar.time, 'sleep', side_effect=fake_sleep):
        radar.hold_open_until(100 + 15*60, 'discover')
        assert current[0] == 100 + 15*60
        assert len(sleeps) == 30
        radar.hold_open_until(current[0] + 10*60, 'verify')
        assert current[0] == 100 + 25*60
        assert len(sleeps) == 50
    output = capsys.readouterr().out
    assert 'DISCOVER window completed (fixed duration)' in output
    assert 'VERIFY window completed (fixed duration)' in output
    assert 'waiting, not repeating downloads' in output


def test_once_diagnostic_does_not_sleep():
    with patch.object(radar.time, 'sleep') as sleeper:
        radar.hold_open_until(float('inf'), 'discover', once=True)
        sleeper.assert_not_called()


def test_discover_attempts_all_rotated_sources_before_idle(tmp_path):
    """Don't finish the active search after just six publishers."""
    actors = [{'id': f'a{i}', 'category': 'University / research centre',
               'archives': [f'https://site{i}.example/reports'],
               'domain_hosts': [f'site{i}.example'], 'seeds': []} for i in range(8)]
    (tmp_path/'findings.json').write_text('{"findings": []}')
    pages = [f'https://site{i}.example/reports' for i in range(8)]
    def fake_page(url, allowed):
        assert url in pages
        return (url, b'<html><main><h1>Foresight archive</h1></main></html>', 'text/html')
    with patch.multiple(radar, RESULTS=tmp_path/'findings.json',
                        STATE=tmp_path/'radar-state.json', CANDIDATES=tmp_path/'candidates.json'), \
         patch.object(radar, 'get_registry', return_value=actors), \
         patch.object(radar, 'get_page', side_effect=fake_page) as fetch, \
         patch.object(radar, 'TODAY', return_value=date(2026, 10, 16)):
        radar.discover(float('inf'))
        assert fetch.call_count == 8
        assert len(radar.read_json(tmp_path/'candidates.json')['sources_this_run']) == 8
        # Archives get cooldowns. The next run does not hammer these pages.
        radar.discover(float('inf'))
        assert fetch.call_count == 8
        assert radar.load_state()['runs'] == 2


def test_active_scan_follows_new_pagination_in_same_full_window(tmp_path):
    """The full 15-minute phase explores new pages instead of idling after roots."""
    actor = {'id': 'a', 'category': 'University / research centre',
             'archives': ['https://example.org/foresight'],
             'domain_hosts': ['example.org'], 'seeds': []}
    (tmp_path/'findings.json').write_text('{"findings": []}')
    visited = []
    def fake_page(url, allowed):
        visited.append(url)
        if url.endswith('/foresight'):
            html = b'<main><a href="/foresight?page=2">Next</a></main>'
        else:
            html = b'<main><p>No further archives</p></main>'
        return (url, html, 'text/html')
    with patch.multiple(radar, RESULTS=tmp_path/'findings.json',
                        STATE=tmp_path/'radar-state.json', CANDIDATES=tmp_path/'candidates.json'), \
         patch.object(radar, 'get_registry', return_value=[actor]), \
         patch.object(radar, 'get_page', side_effect=fake_page), \
         patch.object(radar, 'TODAY', return_value=date(2026, 10, 16)), \
         patch.object(radar.time, 'monotonic', return_value=0):
        radar.discover(100)
        assert visited == ['https://example.org/foresight',
                           'https://example.org/foresight?page=2']
        audit = radar.read_json(tmp_path/'candidates.json')
        assert audit['archive_passes'] == 3
        assert audit['archive_pages_visited'] == 2
        radar.discover(100)
        assert len(visited) == 2  # neither page re-fetched during cooldown


def test_workflow_fails_fast_if_old_python_file_still_deployed():
    from pathlib import Path
    workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/update-radar.yml').read_text()
    assert radar.FIXED_PHASE_PROTOCOL == 5
    assert "getattr(radar, 'FIXED_PHASE_PROTOCOL', None) != 5" in workflow
    assert 'python -u scripts/radar.py discover --minutes 14' in workflow
    assert 'python -u scripts/radar.py verify --minutes 9' in workflow
    assert 'elapsed < 835' in workflow
    assert 'elapsed < 535' in workflow

# Cellar / EU Publications Office recovery tests: the October audit recorded
# Commission HTML catalogue summaries incorrectly assessed as full studies.
def test_cellar_url_is_an_official_work_identifier_not_any_uuid():
    uuid = '7c3efc86-9a39-11ee-b164-01aa75ed71a1'
    official = 'https://op.europa.eu/en/publication-detail/-/publication/' + uuid + '/language-en/format-PDF'
    assert radar.cellar_url(official) == 'https://publications.europa.eu/resource/cellar/' + uuid
    assert radar.cellar_url('https://example.org/publication/' + uuid) is None
    assert radar.cellar_url('https://op.europa.eu/en/publication/no-uuid') is None


def test_commission_html_download_not_restricted_to_pdf_extension():
    url = 'https://research-and-innovation.ec.europa.eu/knowledge-publications/report_en'
    landing = b'''<html><main><a href="/document/download/5f6e541e-c99a-407c-8971-0c1ba03eacd8_en">Download (391.3 KB - HTML)</a></main></html>'''
    links = radar.publication_download_links(url, landing)
    assert any('/document/download/5f6e' in u for _, u in links)


def test_full_document_follows_commission_to_publications_office_to_cellar():
    actor = next(a for a in radar.get_registry() if a['id'] == 'ec-contracts')
    title = 'Foresight on demand: Foresight towards the 2nd Strategic Plan for Horizon Europe'
    source = 'https://research-and-innovation.ec.europa.eu/knowledge-publications/report_en'
    download = 'https://research-and-innovation.ec.europa.eu/document/download/5f6e541e-c99a-407c-8971-0c1ba03eacd8_en'
    op = 'https://op.europa.eu/en/web/eu-law-and-publications/publication-detail/-/publication/7c3efc86-9a39-11ee-b164-01aa75ed71a1'
    cellar = 'https://publications.europa.eu/resource/cellar/7c3efc86-9a39-11ee-b164-01aa75ed71a1'
    landing = f'<html><main><h1>{title}</h1><a href="{download}">Download (HTML)</a></main></html>'.encode()
    op_page = f'<html><main><h1>{title}</h1><p>PDF available in English</p></main></html>'.encode()
    extracted = radar.page_info(landing)
    study = full_study()
    study['text'] = title + ' ' + study['text']
    called = []
    def mock_get(url, allowed):
        called.append((url, allowed))
        if url == download:
            assert 'op.europa.eu' in allowed and 'publications.europa.eu' in allowed
            return op, op_page, 'text/html'
        if url == cellar:
            return cellar, b'%PDF pretend bytes', 'application/pdf'
        raise AssertionError('Unexpected URL '+url)
    real_info = radar.page_info
    def mock_info(data, ctype='text/html', full_pdf=False):
        if data.startswith(b'%PDF'):
            return study
        return real_info(data, ctype, full_pdf)
    with patch.object(radar, 'get_page', side_effect=mock_get), patch.object(radar, 'page_info', side_effect=mock_info):
        target, result = radar.full_document(source, extracted, landing, 'text/html', actor)
    assert target == cellar
    assert result['format'] == 'pdf'
    assert [u for u, _ in called] == [download, cellar]


def test_html_abstract_is_retrieval_failure_not_low_quality_study():
    actor = next(a for a in radar.get_registry() if a['id'] == 'ec-contracts')
    url = 'https://research-and-innovation.ec.europa.eu/report'
    landing = b'<html><main><h1>EU Foresight Scenarios</h1><p>Summary only.</p></main></html>'
    with pytest.raises(radar.DocumentRetrievalError, match='landing page only'):
        radar.full_document(url, radar.page_info(landing), landing, 'text/html', actor)


def test_earlier_catalogue_rejections_get_one_upgrade_retry():
    state = radar.empty_state()
    candidate = next(x for x in radar.REPAIR_LEADS if 'After the new normal' in x['title'])
    state['documents'][candidate['url']] = {
        'status': 'rejected', 'reason': 'Quality gate failed: substantial_full_text',
        'retry_after': '2026-11-30', 'last_checked': '2026-10-16'}
    assert radar.offer_candidate(state, candidate, set(), date(2026, 10, 16)) == 'queued'
    state['queue'] = []
    state['documents'][candidate['url']]['verifier_version'] = radar.VERIFIER_VERSION
    assert radar.offer_candidate(state, candidate, set(), date(2026, 10, 16)) == 'cooldown'


def test_retrieval_error_does_not_become_quality_rejection(tmp_path):
    from unittest.mock import patch
    actor = next(a for a in radar.get_registry() if a['id'] == 'ec-contracts')
    state = radar.empty_state()
    candidate = dict(radar.REPAIR_LEADS[0], source_mode='publisher archive link')
    state['queue'] = [candidate]
    (tmp_path / 'radar-state.json').write_text(json.dumps(state))
    (tmp_path / 'findings.json').write_text((radar.ROOT / 'findings.json').read_text())
    (tmp_path / 'assessments.json').write_text('{"assessments": []}')
    (tmp_path / 'candidates.json').write_text('{"sources_this_run": ["ec-contracts"]}')
    with patch.multiple(radar, STATE=tmp_path/'radar-state.json', RESULTS=tmp_path/'findings.json',
                        AUDIT=tmp_path/'scan-report.json', CANDIDATES=tmp_path/'candidates.json', ROOT=tmp_path), \
         patch.object(radar, 'get_registry', return_value=[actor]), \
         patch.object(radar, 'verify_report', side_effect=radar.DocumentRetrievalError('Full study not retrieved')), \
         patch.object(radar, 'TODAY', return_value=date(2026, 10, 16)):
        radar.verify_until(float('inf'))
        item = radar.load_state()['documents'][candidate['url']]
        report = json.loads((tmp_path/'scan-report.json').read_text())
    assert item['status'] == 'retrieval_failed'
    assert item['retry_after'] == '2026-10-18'
    assert report['outcome_counts']['retrieval_failed'] == 1
    assert report['new_reports'] == 0


def test_full_study_quality_still_rejects_thin_reports():
    actor = next(a for a in radar.get_registry() if a['id'] == 'ec')
    with pytest.raises(radar.SubstantiveQualityError, match='substantial_full_text'):
        radar.quality_screen(full_study(word_count=400), actor, 'EU Scenarios 2035')


def test_cellar_api_requests_english_pdf_by_content_negotiation():
    from unittest.mock import patch
    cellar = 'https://publications.europa.eu/resource/cellar/7c3efc86-9a39-11ee-b164-01aa75ed71a1'
    class Response:
        status_code = 200
        headers = {'Content-Type': 'application/pdf'}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def raise_for_status(self): pass
        def iter_content(self, size): yield b'%PDF-1.4\nknown bytes'
    class Session:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, url, headers, **kwargs):
            assert url == cellar
            assert headers['Accept'] == 'application/pdf'
            assert headers['Accept-Language'] == 'eng'
            assert not kwargs['allow_redirects']
            return Response()
    with patch.object(radar.requests, 'Session', return_value=Session()):
        out_url, content, mime = radar.get_page(cellar, {'publications.europa.eu'})
    assert out_url == cellar
    assert content.startswith(b'%PDF')
    assert mime == 'application/pdf'


def test_pdfs_include_final_bibliography_even_in_long_reports():
    from unittest.mock import patch
    class Page:
        def __init__(self, num): self.num = num
        def extract_text(self):
            return ('Title of the study and executive summary 2020' if self.num == 0 else
                    'References 2019 2020 2021 2022 2023 2024 2025' if self.num == 344 else
                    'Scenario futures 2040 and research methodology')
    class Reader:
        pages = [Page(i) for i in range(345)]
        def __init__(self, *args, **kwargs): pass
    with patch.object(radar, 'PdfReader', Reader):
        info = radar.page_info(b'%PDF fake', 'application/pdf', full_pdf=True)
    assert info['pages'] == 345
    assert 'References 2019' in info['text']
    assert 'Title of the study' in info['text']
