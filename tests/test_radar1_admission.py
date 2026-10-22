"""Offline regression tests for the selective Radar 1 historic collection."""
from datetime import date
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from radar1_admission import decision
from radar1_scope_audit import audit
from scholarly import scholarly_scan


def lead(doi, title, abstract='', published='2021-05-04'):
    return {'doi': doi, 'title': title, 'abstract': abstract, 'date': published,
            'journal': 'Futures', 'publisher': 'Academic publisher',
            'indexes': ['Crossref'], 'url': 'https://doi.org/' + doi,
            'open_access_pdf': ''}


class RelevanceTests(unittest.TestCase):
    def test_accept_meaningful_futures_even_without_testable_numerical_forecast(self):
        examples = [
            lead('10.1234/a', 'Parking futures: Preparing European cities for the advent of automated vehicles'),
            lead('10.1234/b', 'Future of the European Union: Alternative institutional scenarios'),
            lead('10.1234/c', 'Low-carbon futures for the European energy transition'),
            lead('10.1234/d', 'EU land use futures: modelling food, bioenergy and carbon dynamics',
                 'This study models European agriculture and explores land-use options to meet the EU 2050 climate objectives.'),
            lead('10.1234/e', 'Public health air pollution impacts of pathway options to meet the 2050 UK Climate Change Act target: a modelling study',
                 'The model quantifies health implications of four alternative policy scenarios and emissions reductions to 2050.'),
        ]
        for x in examples:
            with self.subTest(title=x['title']):
                self.assertTrue(decision(x)[0], decision(x))

    def test_reject_unrelated_word_matches(self):
        examples = [
            lead('10.1234/t', 'EU carbon futures market price volatility and trading'),
            lead('10.1234/u', 'Comparison of Futures Pricing Models for Carbon Assets and Traditional Energy Commodities in Europe'),
            lead('10.1234/v', 'Delphi consensus on European surgical clinical guidelines and treatment'),
            lead('10.1234/w', 'Scenarios of European colonization in the eighteenth century'),
            lead('10.1234/x', 'The unlawfulness of existing integration conditions applied in family reunification scenarios in the EU'),
            lead('10.1234/y', 'Forecasting exports across Europe: best short-term survey indicators'),
            lead('10.1234/z', 'Energy futures pathways for European cities by 2050', published='2025-01-01'),
            lead('10.1234/p', 'EU waste management editorial'),
            lead('10.1234/q', '28.G. Workshop: foresight studies at the European and national level'),
        ]
        for x in examples:
            with self.subTest(title=x['title']):
                self.assertFalse(decision(x)[0], decision(x))

    def test_examine_abstract_for_title_uncertainty(self):
        bare = lead('10.1234/a', 'European smart infrastructure scenarios')
        with_detail = dict(bare, abstract='We model alternative infrastructure investment scenarios '
                           'in European metropolitan regions through 2040, quantifying policy tradeoffs.')
        self.assertFalse(decision(bare)[0])
        self.assertTrue(decision(with_detail)[0])

    def test_preview_never_alters_saved_data_and_apply_prunes_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'research-leads.json'
            good = lead('10.1234/g', 'Foresight on the future of European migration to 2050')
            bad = lead('10.1234/b', 'EU carbon futures market volatility')
            new = lead('10.1234/n', 'Future scenarios for European fisheries by 2030', published='2024-03-01')
            path.write_text(json.dumps({'schema_version': 1, 'leads': [good,bad,new]}))
            before=path.read_bytes()
            result=audit(path, apply=False)
            self.assertEqual(result['retained_in_main_file'], 1)
            self.assertEqual(result['removed_from_main_file'], 2)
            self.assertEqual(path.read_bytes(), before)
            self.assertFalse((Path(tmp)/'radar1-rejected.json').exists())
            result=audit(path, apply=True)
            self.assertEqual(result['removed_from_main_file'], 2)
            self.assertEqual([x['doi'] for x in json.loads(path.read_text())['leads']], [good['doi']])
            rejects=json.loads((Path(tmp)/'radar1-rejected.json').read_text())['rejected']
            self.assertEqual(set(rejects), {bad['doi'],new['doi']})
            self.assertEqual(json.loads((Path(tmp)/'radar1-active.json').read_text())['original_records'],1)
            # Future previews cannot resurrect old DOI rejections.
            self.assertEqual(audit(path, apply=False)['retained_in_main_file'],1)

    def test_scheduled_scan_screens_before_admission_and_blocks_rediscovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            state=directory/'radar-state.json'
            path=directory/'research-leads.json'
            good=lead('10.1234/a', 'European energy system scenarios towards 2050')
            bad=lead('10.1234/b', 'EU carbon futures trading volatility')
            fetch=lambda *args, **kwargs: [good,bad]
            with patch('scholarly.fetch_index',side_effect=fetch), patch('scholarly.closer_abstract_check') as check:
                first=scholarly_scan(state,path,date(2023,12,31),time.monotonic()+100,max_queries=1)
                second=scholarly_scan(state,path,date(2023,12,31),time.monotonic()+100,max_queries=1)
            self.assertEqual(first['new_leads'],1)
            self.assertEqual(second['new_leads'],0)
            self.assertEqual([x['doi'] for x in json.loads(path.read_text())['leads']], [good['doi']])
            self.assertIn(bad['doi'], json.loads((directory/'radar1-rejected.json').read_text())['rejected'])
            check.assert_not_called()


if __name__ == '__main__':
    unittest.main()
