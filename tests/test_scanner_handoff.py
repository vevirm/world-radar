"""No-network contract tests for scanner handoff and free provider."""
import json
import sys
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import retrospective_radar as radar


class HandoffTests(TestCase):
    def test_reads_leads_from_scanner_one(self):
        leads = radar.claims()
        self.assertGreater(len(leads), 0)
        self.assertTrue(leads[0]['id'].startswith('lead-'))
        self.assertTrue(leads[0]['source_url'].startswith('https://'))

    def test_free_follow_up_filters_unrelated_papers(self):
        claim = {'title': 'Long-term projections of European coastal flooding and sea level',
                 'source_url': 'https://doi.org/10.1234/original', 'original_publication': '2011-01-01'}
        mock_results = {'results': [
            {'title': 'European coastal flooding projections and sea level rise',
             'publication_year': 2022, 'doi': 'https://doi.org/10.1234/later'},
            {'title': 'A guide to cooking soup', 'publication_year': 2023,
             'doi': 'https://doi.org/10.1234/soup'}]}
        class Reply:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return json.dumps(mock_results).encode()
        with patch.object(radar.urllib.request, 'urlopen', return_value=Reply()):
            result = radar.free_follow_up(claim)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['year'], 2022)
        self.assertIn('not independently verified', result[0]['note'])

    def test_word_creation_offline(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(radar, 'REPORT', Path(td) / 'report.docx'):
                import outlook_summary
                with patch.object(outlook_summary, 'OUT', Path(td) / 'outlook.json'):
                    radar.build_word([])
                    self.assertGreater((Path(td) / 'report.docx').stat().st_size, 10000)
                    self.assertTrue((Path(td) / 'outlook.json').exists())

    def test_openalex_key_is_attached_to_follow_up_request(self):
        from urllib.parse import parse_qs, urlparse
        claim = {'title': 'Long-term projections of European coastal flooding and sea level',
                 'source_url': 'https://doi.org/10.1234/original', 'original_publication': '2011-01-01'}
        captured = []
        class Reply:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return b'{"results": []}'
        def fake_open(req, timeout=12):
            captured.append(parse_qs(urlparse(req.full_url).query))
            return Reply()
        with patch.dict(radar.os.environ, {'OPENALEX_API_KEY': 'dummy-test-key'}):
            with patch.object(radar.urllib.request, 'urlopen', side_effect=fake_open):
                radar.free_follow_up(claim)
        self.assertEqual(captured[0]['api_key'], ['dummy-test-key'])
