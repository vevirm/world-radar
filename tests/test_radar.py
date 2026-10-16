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
    assert radar.START_DATE == date(2015, 1, 1)
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


@pytest.mark.parametrize('report_date, expected', [('2026-08-01','Too recent'),('2014-12-31','predates 2015')])
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
    assert data['earliest_publication_date'] == '2015-01-01'
    assert all(x['id'].startswith('EUF-') and x['quality']['status'] == 'automated research-substance screen passed' for x in data['findings'])


def test_workflow_still_15_then_10_minutes_and_half_hour_schedule():
    yml = (radar.ROOT/'.github/workflows/update-radar.yml').read_text()
    assert '--minutes 15' in yml
    assert '--minutes 10' in yml
    assert "7,37 * * * *" in yml
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
