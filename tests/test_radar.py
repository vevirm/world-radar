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


def test_previous_joke_findings_remain_blank():
    data = radar.read_json(radar.RESULTS)
    assert data['schema_version'] == 2
    assert data['earliest_publication_date'] == '2015-01-01'
    assert data['findings'] == []


def test_workflow_still_15_then_10_minutes_and_half_hour_schedule():
    yml = (radar.ROOT/'.github/workflows/update-radar.yml').read_text()
    assert '--minutes 15' in yml
    assert '--minutes 10' in yml
    assert "7,37 * * * *" in yml
