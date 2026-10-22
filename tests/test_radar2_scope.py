"""No-scan contract tests: accepted originals only, curated reports, reversible legacy holding."""
import json
import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from radar2_scope import original_claims, reconcile, load


class Radar2ScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.doi='10.5555/eurofuture.2018'
        self.source='https://doi.org/'+self.doi
        self.quote=('Our three European decarbonization scenarios show different '
                    'possible energy investment trajectories through 2050.')
        self.write('radar1-active.json',{'original_records':1,'studies':[
            {'doi':self.doi,'date':'2018-05-03','selection':'active',
             'original_passage':self.quote}]})
        self.write('research-leads.json',{'leads':[
            {'doi':self.doi,'date':'2018-05-03','title':'Europe pathways to 2050',
             'url':self.source,'publisher':'Journal', 'radar1_selection':'active',
             'radar2_seed':{'original_passage':self.quote,'investigation_type':'alternative_scenarios',
                            'source_field':'abstract'}}]})
        self.write('radar1-rejected.json',{'rejected':{'10.1111/rejected':{'reason':'irrelevant'}}})
        self.write('priority-sources.json',{'sources':[
            {'title':'Europe 2035: alternatives','date':'2021-07-01',
             'url':'https://example.eu/report','publisher':'EU Research Body'}]})
        self.write('priority-50.json',{'items':[
            {'title':'2023 EU Strategic Foresight Report','date':'2023-07-06',
             'url':'https://example.eu/2023','source_kind':'Source-screened EU report',
             'verification_status':'Full study automated quality screen passed'},
            {'title':'Rejected academic paper','date':'2017-02-03',
             'url':'https://doi.org/10.1111/rejected', 'doi':'10.1111/rejected',
             'source_kind':'Indexed academic lead'}]})
        self.write('retrospective-results.json',{'entries':{
            'lead-'+__import__('hashlib').sha256(self.source.lower().encode()).hexdigest()[:16]:{
               'title':'Europe pathways to 2050','original_publication':'2018-05-03',
               'source_url':self.source,'direction_evidence':[{'url':'https://example.org/later',
                    'title':'Unverified possible follow-up'}],
               'what_happened':'Legacy unverified opinion','status':'materializing'},
            'lead-deadbeef':{'title':'Futures trading','source_url':'https://example.com/rejected'}}})

    def write(self,path,data):
        (self.root/path).write_text(json.dumps(data),encoding='utf-8')

    def test_only_accepted_academic_and_curated_institutions(self):
        claims=original_claims(self.root)
        self.assertEqual(3,len(claims))
        self.assertEqual(1,sum(c['source_kind']=='academic' for c in claims))
        self.assertTrue(next(c for c in claims if c['source_kind']=='academic')['expected'].startswith('Our three'))
        institutional=[c for c in claims if c['source_kind']=='institutional']
        self.assertEqual(2,len(institutional))
        self.assertTrue(all(not c['investigation_ready'] and not c['expected'] for c in institutional))
        self.assertFalse(any('Rejected academic paper'==c['title'] for c in claims))

    def test_preview_does_not_modify_and_apply_separates_old_links(self):
        before=(self.root/'retrospective-results.json').read_bytes()
        preview=reconcile(self.root)
        self.assertEqual(before,(self.root/'retrospective-results.json').read_bytes())
        self.assertEqual(1,preview['legacy_entries_outside_current_radar1'])
        self.assertEqual(2,preview['institutional_needing_original_passage'])
        self.assertEqual(3,preview['live_entries_after_apply'])
        applied=reconcile(self.root,apply=True)
        self.assertEqual(3,len(load(self.root/'retrospective-results.json')['entries']))
        self.assertTrue((self.root/'radar2-scope-ready.json').exists())
        self.assertEqual(1,len(load(self.root/'radar2-legacy-holding.json')['entries']))
        for entry in load(self.root/'retrospective-results.json')['entries'].values():
            self.assertNotEqual('materializing',entry['status'])
            self.assertFalse(entry.get('direction_evidence'))
        self.assertEqual(2,len(load(self.root/'radar2-original-text-queue.json')['reports']))
        # A second explicit apply should be idempotent and retain the same corpus.
        self.assertEqual(3,reconcile(self.root)['live_entries_after_apply'])
        self.assertEqual(3,reconcile(self.root,apply=True)['live_entries_after_apply'])
        self.assertEqual(1,len(load(self.root/'radar2-legacy-holding.json')['entries']))
        self.assertEqual(3,applied['live_entries_after_apply'])

    def test_manifest_mismatch_and_rejected_doi_fail_closed(self):
        manifest=load(self.root/'radar1-active.json')
        manifest['studies'][0]['doi']='10.2222/wrong'
        self.write('radar1-active.json',manifest)
        with self.assertRaisesRegex(ValueError,'disagree'):
            original_claims(self.root)
        manifest['studies'][0]['doi']=self.doi
        self.write('radar1-active.json',manifest)
        self.write('radar1-rejected.json',{'rejected':{self.doi:{'reason':'excluded'}}})
        with self.assertRaisesRegex(ValueError,'rejected'):
            original_claims(self.root)

    def test_never_admit_2024_as_historical_original(self):
        leads=load(self.root/'research-leads.json')
        leads['leads'][0]['date']='2024-05-03'
        self.write('research-leads.json',leads)
        with self.assertRaisesRegex(ValueError,'Out-of-period'):
            original_claims(self.root)


if __name__=='__main__':unittest.main()
