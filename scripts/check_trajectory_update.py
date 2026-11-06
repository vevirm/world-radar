"""Read-only checker for the November 2026 GitHub update package."""
import json
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'research-updates' / 'trajectory-research-2026-11-02.json'

def check():
    data = json.loads(DATA.read_text(encoding='utf-8'))
    assert (len(data['cases']), len(data['events']), len(data['sources']),
            len(data['connections'])) == (12, 40, 37, 16)
    ids = {c['id'] for c in data['cases']}
    source_ids = {s['id'] for s in data['sources']}
    assert len(ids) == 12 and len(source_ids) == 37
    assert all(e['case_id'] in ids and e['source_id'] in source_ids for e in data['events'])
    assert all(e['from_id'] in ids and e['to_id'] in ids for e in data['connections'])
    p = ROOT / 'VV-FUTURES-ALL-CLAIMS-AND-SOURCES.xlsx'
    with ZipFile(p) as z:
        doc = ET.fromstring(z.read('xl/workbook.xml'))
        ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        names = {s.get('name') for s in doc.findall('s:sheets/s:sheet', ns)}
        assert len(names) >= 22 and {'LLM reviewed', 'Nov26 Paths', 'Long26 Depth'} <= names
        assert z.testzip() is None
    for filename in ['VV-FUTURES-REVIEWED-FINDINGS.docx',
                     'VV-FUTURES-WHAT-BECAME-OF-THE-FUTURE.docx']:
        with ZipFile(ROOT/filename) as z:
            assert z.testzip() is None
            assert 'word/document.xml' in z.namelist()
    assert 'VV-FUTURES-WHAT-BECAME-OF-THE-FUTURE.docx' in (ROOT/'index.html').read_text(encoding='utf-8')
    html = (ROOT/'index.html').read_text(encoding='utf-8')
    assert all(f'id="{field}"' in html for field in
               ('trajectory-total','milestone-total','sources-total','connections-total'))
    assert 'research-updates/trajectory-research-2026-11-02.json' in html
    print('PASS: 12 trajectories; 40 dated milestones; 37 sources; 16 links')
    print('PASS: existing + extended workbook, Word files, and website link present')
    assert len(data['deep_tracking_followup_2026_11_05']['sources']) == 6
    assert len(data['deep_tracking_followup_2026_11_05']['events']) == 6
    newer = data['deep_tracking_followup_2026_11_06']
    assert len(newer['new_cases']) == 1 and newer['new_cases'][0]['id'] == 'T13'
    assert newer['new_cases'][0]['catalog_claim_id'] == 'claim-4bbf4f842de012c2'
    assert (len(newer['events']), len(newer['sources']), len(newer['connections'])) == (8,6,2)
    assert (ROOT/'research-updates/trajectory-followup-2026-11-06.json').is_file()
    assert {x['id'] for x in newer['sources']} == {f'S{i}' for i in range(44,50)}
    all_sources = {s['id'] for s in data['sources']}
    all_sources |= {s['id'] for s in data['deep_tracking_followup_2026_11_05']['sources']}
    all_sources |= {s['id'] for s in newer['sources']}
    all_cases = ids | {c['id'] for c in newer['new_cases']}
    assert len(all_sources) == 49 and len(all_cases) == 13
    for part in (data['deep_tracking_followup_2026_11_05'], newer):
        assert all(e['case_id'] in all_cases and e['source_id'] in all_sources for e in part['events'])
    assert all(link['from_id'] in all_cases and link['to_id'] in all_cases for link in newer['connections'])
    with ZipFile(ROOT/'VV-FUTURES-ALL-CLAIMS-AND-SOURCES.xlsx') as z:
        workbook = ET.fromstring(z.read('xl/workbook.xml'))
        sheet_names = {s.get('name') for s in workbook.findall('s:sheets/s:sheet', {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'})}
        assert 'Nov06 Recheck' in sheet_names
    assert 'deep_tracking_followup_2026_11_06' in html
    print('PASS: dated 5/6 November layers; 13 trajectories, 54 milestones, 49 sources, 18 links')


if __name__ == '__main__':
    check()
