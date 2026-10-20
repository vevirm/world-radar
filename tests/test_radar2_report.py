"""Regression tests for Radar 2's unambiguous Word/audit contract."""
import json
import importlib
from pathlib import Path

from docx import Document

from scripts import retrospective_radar, outcome_verification, outlook_summary


def test_word_separates_candidate_from_observed_outcome(tmp_path, monkeypatch):
    """Both directions are present, but forecasts are not claimed verified."""
    monkeypatch.setattr(retrospective_radar, 'ROOT', tmp_path)
    monkeypatch.setattr(retrospective_radar, 'REPORT', tmp_path/'stuff'/'WHAT_WAS_EXPECTED_WHAT_HAPPENED.docx')
    imported_verification = importlib.import_module('outcome_verification')
    imported_outlook = importlib.import_module('outlook_summary')
    monkeypatch.setattr(imported_verification, 'QUEUE', tmp_path/'outcome-review-queue.json')
    monkeypatch.setattr(imported_verification, 'REGISTRY', tmp_path/'verified-outcomes.json')
    monkeypatch.setattr(imported_outlook, 'ROOT', tmp_path)
    monkeypatch.setattr(imported_outlook, 'OUT', tmp_path/'outlook-summary.json')
    (tmp_path/'research-leads.json').write_text(json.dumps({'leads': []}))
    (tmp_path/'verified-outcomes.json').write_text(json.dumps({'cases': []}))
    (tmp_path/'outcome-observations.json').write_text(json.dumps({'observations': [{
        'topic': 'Emissions', 'expected': 'Policy target by 2030',
        'happened': 'Measured progress reported for 2024.', 'verdict': 'Target not due',
        'sources': [{'date': '2025-01-01', 'finding': 'Official measurement', 'url': 'https://example.org/source'}]
    }]}))
    item = {'id': 'lead-123', 'title': 'Growth forecast', 'source_url': 'https://example.org/original',
            'screening_status': 'candidate_needs_validation',
            'candidate_excerpt': 'Employment will rise by 10% by 2030.', 'candidate_year': 2030,
            'original_publication': '2020-01-01', 'status': 'not_yet_assessed', 'evidence': []}
    retrospective_radar.build_word([item], run={
        'provider': 'evidence', 'attempts': 0, 'failed': 0,
        'new_evidence_assessments': 0, 'note': 'Offline'} )
    text = '\n'.join(p.text for p in Document(retrospective_radar.REPORT).paragraphs)
    assert 'Research requests this run: 0' in text
    assert 'Source-reviewed expected-vs-actual outcomes: 0' in text
    assert 'WHAT WAS EXPECTED (unverified abstract excerpt): Employment will rise' in text
    assert 'WHAT ACTUALLY HAPPENED: Not established by independent' in text
    assert 'WHAT WAS EXPECTED / TARGETED: Policy target by 2030' in text
    assert 'WHAT ACTUALLY HAPPENED: Measured progress reported for 2024' in text
    assert json.loads((tmp_path/'outcome-review-queue.json').read_text())['candidate_count'] == 1


def test_radar2_scheduled_only_twice_with_secret_and_auto_provider():
    root = Path(__file__).resolve().parents[1]
    workflow = (root/'.github/workflows/update-outcomes.yml').read_text()
    assert "17 4,16 * * *" in workflow
    assert 'workflow_run:' not in workflow, 'Workflow-run plus cron triggers 4 times/day, not 2'
    assert 'OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}' in workflow
    assert '--provider auto' in workflow
    assert 'stuff/WHAT_WAS_EXPECTED_WHAT_HAPPENED.docx' in workflow
