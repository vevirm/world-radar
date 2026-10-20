"""Regression tests for truncated OpenAlex responses in Radar 2."""
import http.client
import importlib.util
import json
from pathlib import Path
from unittest import TestCase, mock

spec = importlib.util.spec_from_file_location('radar2', Path(__file__).resolve().parents[1] / 'scripts' / 'retrospective_radar.py')
radar2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(radar2)


class Response:
    def __init__(self, value=None, broken=False):
        self.value, self.broken = value, broken
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self):
        if self.broken:
            raise http.client.IncompleteRead(b'partial', 100)
        return json.dumps({'results': self.value}).encode()


class OpenAlexResilienceTests(TestCase):
    lead = {'title': 'European green technology transition analysis',
            'original_publication': '2020',
            'source_url': 'https://example.org/source'}

    def test_truncated_download_retried_then_successful(self):
        with mock.patch.object(radar2.urllib.request, 'urlopen', side_effect=[Response(broken=True), Response([])]) as req, \
             mock.patch.object(radar2.time, 'sleep'):
            self.assertEqual(radar2.free_follow_up(self.lead), [])
            self.assertEqual(req.call_count, 2)

    def test_repeated_truncation_raises_controlled_error(self):
        with mock.patch.object(radar2.urllib.request, 'urlopen', return_value=Response(broken=True)) as req, \
             mock.patch.object(radar2.time, 'sleep'):
            with self.assertRaises(ConnectionError):
                radar2.free_follow_up(self.lead)
            self.assertEqual(req.call_count, 4)
