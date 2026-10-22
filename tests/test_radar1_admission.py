"""Offline regression checks: selective historical European originals and Radar 2 handoff.

No real scanner, API, deletion or Radar 2 job is invoked by these tests.
"""
from datetime import date
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from radar1_admission import decision, POLICY_VERSION
from radar1_scope_audit import audit
from radar1_traceability import trace
from scholarly import scholarly_scan

# A qualitative foresight exercise contains a substantively revisitable question;
# it does not need a precise numerical or falsifiable single-point forecast.
SCENARIO_TEXT = (
    'This study develops three alternative scenarios for the future of industrial '
    'relations in the European Union. The first scenario projects continuing '
    'erosion of national industrial relations systems and worker protections. '
    'The second scenario envisages a major policy reform led by EU institutions '
    'that could strengthen workers rights and shared standards. The third scenario '
    'explores how workers and unions might organize a grassroots counter-movement '
    'in response to economic disruption. These alternatives have important '
    'implications for European employment policy, collective bargaining and the '
    'future of the European social model.'
)
CLIMATE_TEXT = (
    'Using European land-use datasets and spatial simulation models, this study '
    'compares several alternative futures for European agriculture in 2050. '
    'The scenarios model a high-bioenergy pathway, an agricultural productivity '
    'pathway and a biodiversity-protection pathway. Results show that forest and '
    'agricultural land area could shift substantially under different climate '
    'mitigation policies. We estimate how these futures affect food production, '
    'carbon storage and habitat conservation across Europe. We discuss '
    'the trade-offs involved in choosing each policy strategy for the next '
    'three decades of European land-use planning.'
)
NOT_FUTURES = (
    'This paper reviews the history and theory of European integration. Many '
    'issues remain unresolved and the authors call for further research in '
    'the future. Based on current EU legislation, the work examines existing '
    'policy implementation in five member states and summarizes case law. '
    'Our descriptive account does not compare prospective trajectories or '
    'alternatives to current regulation; this article documents legal changes '
    'between 2003 and 2014.'
)


def lead(doi, title, abstract='', published='2021-05-04'):
    return {'doi':doi,'title':title,'abstract':abstract,'date':published,
            'journal':'Futures','publisher':'Academic publisher',
            'indexes':['Crossref'],'url':'https://doi.org/'+doi,
            'open_access_pdf':''}


class RelevanceTests(unittest.TestCase):
    def test_substantive_qualitative_scenarios_have_exact_original_passages(self):
        x=lead('10.1234/qual','Three scenarios for industrial relations in Europe', SCENARIO_TEXT)
        self.assertTrue(decision(x)[0],decision(x))
        handoff,reason=trace(x)
        self.assertIn('scenario',handoff['original_passage'].lower())
        self.assertIn(handoff['original_passage'].split('.')[0],SCENARIO_TEXT)
        self.assertEqual(handoff['source_field'],'abstract')
        self.assertEqual(handoff['source_status'],'indexed_source_text_not_full_document_verified')
        y=lead('10.1234/climate','Land-use futures for Europe in 2050',CLIMATE_TEXT)
        self.assertTrue(decision(y)[0],decision(y))
        self.assertIn(2050,trace(y)[0]['anticipated_horizons'])

    def test_no_saved_content_is_not_admitted_even_for_promising_titles(self):
        for name in ('Parking futures: Preparing European cities for automated vehicles',
                     'The future of European defence: Alternative scenarios for 2030',
                     'Low-carbon futures for the European energy transition'):
            with self.subTest(name=name):
                self.assertEqual(decision(lead('10.1234/empty',name))[1],
                                 'no_substantive_source_text_for_radar2')
        evidence=lead('10.1234/desc','Land-use futures for Europe in 2050')
        evidence['publisher_description']=CLIMATE_TEXT
        self.assertTrue(decision(evidence)[0],decision(evidence))
        self.assertEqual(trace(evidence)[0]['source_field'],'publisher_description')

    def test_title_keyword_and_incidental_future_mention_do_not_admit(self):
        x=lead('10.1234/history','Alternative scenarios for European energy policy towards 2050',NOT_FUTURES)
        self.assertFalse(decision(x)[0],decision(x))
        for name in ('European carbon futures market price volatility and trading',
                     'Delphi consensus on European surgical clinical guidelines',
                     'Scenarios of European colonization in the eighteenth century',
                     'RETRACTED ARTICLE: EU energy transition forecasts for 2050',
                     'A review of European futures models',
                     'DAAD Faculty Summer Seminar 2012: Futures of Europe'):
            with self.subTest(name=name):
                self.assertFalse(decision(lead('10.1234/no',name,SCENARIO_TEXT))[0])
        self.assertFalse(decision(lead('10.1234/new','Energy futures for Europe',
                       CLIMATE_TEXT,published='2024-01-01'))[0])

    def test_preview_no_deletion_and_apply_removes_from_actual_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'research-leads.json'
            good=lead('10.1234/g','Three scenarios for industrial relations in Europe',SCENARIO_TEXT)
            weak=lead('10.1234/w','Future of European education and society: scenarios for 2050',NOT_FUTURES)
            no_source=lead('10.1234/unknown','Strategic futures scenarios for European cities in 2050')
            newer=lead('10.1234/n','Land-use futures for Europe in 2050',CLIMATE_TEXT,published='2025-03-01')
            original={'schema_version':1,'leads':[good,weak,no_source,newer]}
            path.write_text(json.dumps(original))
            before=path.read_bytes()
            report=audit(path,apply=False)
            self.assertEqual(report['retained_in_main_file'],1)
            self.assertEqual(report['removed_from_main_file'],3)
            self.assertEqual(before,path.read_bytes())
            self.assertFalse((Path(tmp)/'radar1-rejected.json').exists())
            report=audit(path,apply=True)
            self.assertTrue(report['applied'])
            saved=json.loads(path.read_text())['leads']
            self.assertEqual([x['doi'] for x in saved],[good['doi']])
            self.assertIn('industrial relations',saved[0]['radar2_seed']['original_passage'])
            self.assertEqual(saved[0]['radar1_admission_version'],POLICY_VERSION)
            rejected=json.loads((Path(tmp)/'radar1-rejected.json').read_text())['rejected']
            self.assertEqual(set(rejected),{'10.1234/w','10.1234/unknown','10.1234/n'})
            manifest=json.loads((Path(tmp)/'radar1-active.json').read_text())
            self.assertEqual(manifest['original_records'],1)
            self.assertIn('original_passage',manifest['studies'][0])
            self.assertEqual(audit(path)['removed_from_main_file'],0)

    def test_every_new_scan_requires_source_and_avoids_rediscovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=Path(tmp)/'radar-state.json'
            path=Path(tmp)/'research-leads.json'
            good=lead('10.1234/g','Three scenarios for industrial relations in Europe',SCENARIO_TEXT)
            empty_good=dict(good,abstract='')
            bad=lead('10.1234/b','EU carbon futures market volatility',SCENARIO_TEXT)
            responses=[[good,bad],[empty_good,bad]]
            with patch('scholarly.fetch_index',side_effect=responses),patch('scholarly.closer_abstract_check') as close:
                first=scholarly_scan(state,path,date(2023,12,31),time.monotonic()+100,max_queries=1)
                second=scholarly_scan(state,path,date(2023,12,31),time.monotonic()+100,max_queries=1)
            self.assertEqual(first['new_leads'],1)
            self.assertEqual(second['new_leads'],0)
            saved=json.loads(path.read_text())['leads']
            self.assertEqual([x['doi'] for x in saved],[good['doi']])
            self.assertIsNotNone(saved[0]['radar2_seed'])
            self.assertIn(bad['doi'],json.loads((Path(tmp)/'radar1-rejected.json').read_text())['rejected'])
            close.assert_not_called()

    def test_missing_abstract_is_checked_once_and_deferred_if_quota_full(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=Path(tmp)/'radar-state.json'
            path=Path(tmp)/'research-leads.json'
            hits=[lead(f'10.1234/uncertain{i}',
                  f'Alternative European energy futures scenarios {i} towards 2050') for i in range(10)]
            with patch('scholarly.fetch_index',return_value=hits),\
                 patch('scholarly.closer_abstract_check',side_effect=lambda x,key=None:x) as closer:
                result=scholarly_scan(state,path,date(2023,12,31),time.monotonic()+100,max_queries=1)
            self.assertEqual(result['new_leads'],0)
            self.assertEqual(closer.call_count,8)
            self.assertEqual(result['deferred_title_only_checks'],2)
            rejected=json.loads((Path(tmp)/'radar1-rejected.json').read_text())['rejected']
            self.assertEqual(len(rejected),8)
            self.assertNotIn('10.1234/uncertain8',rejected)
            self.assertNotIn('10.1234/uncertain9',rejected)


if __name__=='__main__':
    unittest.main()
