#!/usr/bin/env python3
"""Release guard for published serious European foresight reports."""
import sys
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import radar

report = radar.read_json(radar.RESULTS)
actors = {a['id']: a for a in radar.get_registry()}
assert report['schema_version'] == 2
assert report['scope'] in (
    'EU and independent European foresight retrospective (rolling 15 years; prioritise 5–10 years old)',
    'EU and independent European foresight retrospective (originals 2011–2023; 2024+ only later context)')
assert report['earliest_publication_date'] == radar.START_DATE.isoformat()
seen = set()
for finding in report['findings']:
    assert finding['id'].startswith('EUF-'), finding['id']
    assert finding['actor_id'] in actors, finding['id']
    actor = actors[finding['actor_id']]
    assert radar.trusted_host(finding['url']) in actor['domain_hosts'], finding['id']
    assert radar.trusted_host(finding['full_text_url']) in actor['domain_hosts'], finding['id']
    pub_date = date.fromisoformat(finding['date'])
    assert radar.START_DATE <= pub_date <= radar.TODAY(), finding['id']
    if pub_date > radar.HISTORICAL_END:
        assert finding.get('source_period', 'later_context') == 'later_context', finding['id']
    else:
        assert finding.get('source_period', 'historical_original') == 'historical_original', finding['id']
    assert finding['id'] not in seen, finding['id']
    seen.add(finding['id'])
    quality = finding['quality']
    assert quality['status'] == 'automated research-substance screen passed', finding['id']
    assert all(quality['checks'].values()), finding['id']
    assert quality['word_count'] >= radar.MIN_WORDS, finding['id']
    assert quality['pdf_pages'] is None or quality['pdf_pages'] >= radar.MIN_PDF_PAGES
    assert finding['source_category'] == actor['category'], finding['id']
    cmp = finding['comparison']
    assert cmp['verdict'] == 'Not yet assessed' or cmp['evidence_url'], finding['id']
print(f'Data check passed: {len(seen)} source-screened studies; Radar 1 originals restricted to 2011–2023 and later records retained only as context.')
