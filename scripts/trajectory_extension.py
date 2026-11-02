"""Additive, source-backed foresight trajectories for the VV Futures canonical outputs.

Data source: research-updates/trajectory-research-2026-11-02.json.
No pre-existing reviewed-findings.json entries or source passages are modified.
Use only after ordinary output creation; never convert candidate links into verified findings.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / 'research-updates' / 'trajectory-research-2026-11-02.json'
SHEETS = (
    'Nov26 Guide', 'Nov26 Paths', 'Nov26 Evidence', 'Nov26 Sources',
    'Nov26 Links', 'Nov26 Queue', 'Long26 Depth', 'Long26 Patterns',
)
CORE_SHEETS = {
    'Start here', 'Historical claims', 'LLM reviewed', 'Research syntheses',
    'Unreviewed source links', 'Research 2026-10',
}


def research_data():
    if not DATA_FILE.is_file():
        return None
    data = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    cases = data.get('cases', [])
    ids = [x.get('id') for x in cases]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate trajectory IDs in research data')
    if not all(data.get(k) is not None for k in ('sources', 'events', 'connections', 'queue')):
        raise ValueError('Incomplete trajectory research data')
    return data


def add_to_reviewed_document(doc):
    """Append research without editing the checked LLM accounts already written."""
    data = research_data()
    if not data:
        return
    from docx.shared import Pt
    doc.add_page_break()
    doc.add_heading('Independent forward-path research | 2 November 2026', level=1)
    doc.add_paragraph(
        'The following twelve histories supplement, rather than replace or regrade, '
        'the existing LLM-reviewed accounts. The starting question is: what did the '
        'foresight originally say, how did the subject evolve, and what does hindsight change? '
        'Institutional originals without a direct historical-claims ID are labelled as such.'
    )
    for c in data['cases']:
        doc.add_heading(f"{c['id']} | {c['title']}", level=2)
        for label, key in [
            ('Original proposition', 'original_statement'),
            ('Scope and assumptions', 'original_condition'),
            ('The path through 2026', 'path'),
            ('Later observations', 'latest'),
            ('What changed in the meaning', 'meaning'),
            ('Retrospective analysis', 'essay'),
            ('What remained, changed, or became obsolete', 'afterlife'),
            ('Other defensible interpretation', 'alternative'),
            ('Return to the original', 'lookback'),
            ('Limits and comparability', 'limits'),
        ]:
            v = str(c.get(key) or '').strip()
            if v:
                p = doc.add_paragraph()
                p.add_run(label + '.  ').bold = True
                p.add_run(v)
        doc.add_paragraph('Original source: ' + (c.get('original_url') or 'not recorded'))
        doc.add_paragraph('Provenance: ' + c.get('provenance', ''))
        urls = [s['url'] for s in data['sources'] if s.get('case_id') == c['id']]
        for url in urls:
            p = doc.add_paragraph('Evidence: ' + url)
            for run in p.runs:
                run.font.size = Pt(8)
    doc.add_heading('Cross-case relationships | proposed, not assumed causal', 1)
    for edge in data['connections']:
        doc.add_heading(f"{edge['id']}  {edge['from_id']} ↔ {edge['to_id']} — {edge['headline']}", 2)
        doc.add_paragraph(edge['interpretation'])
        doc.add_paragraph('Interpretation boundary: ' + edge['caution'])
    doc.add_heading('Method and outstanding evidence', 1)
    for rule in data.get('evidence_rules', []):
        doc.add_paragraph(rule, style='List Bullet')
    doc.add_paragraph(
        'Data and URLs: research-updates/trajectory-research-2026-11-02.json. '
        'Citations are dated to 2 November 2026. The extension is not a claim that all '
        'original studies, outcomes, or numerical series have been fully backtested.'
    )


def _column_name(n):
    out = ''
    while n:
        n, q = divmod(n - 1, 26)
        out = chr(65 + q) + out
    return out


def _write_sheet(wb, name, headers, body, widths=None):
    sh = wb.worksheets.add(name)
    width = len(headers)
    sh.get_range_by_indexes(0, 0, 1, width).values = [headers]
    for at in range(0, len(body), 200):
        portion = body[at:at + 200]
        sh.get_range_by_indexes(at + 1, 0, len(portion), width).values = portion
    last = _column_name(width)
    sh.get_range(f'A1:{last}1').format = {
        'fill': '#173B4B',
        'font': {'color': '#FFFFFF', 'bold': True},
        'row_height': 27,
    }
    if body:
        sh.get_range_by_indexes(1, 0, len(body), width).format.row_height = 40 if width > 4 else 34
    for j, val in enumerate(widths or [32] * width):
        letter = _column_name(j + 1)
        sh.get_range(f'{letter}:{letter}').format.column_width = val
    sh.freeze_panes.freeze_rows(1)
    return sh


def preserve_preexisting_research_tabs(wb, output_path):
    """Keep manual/older research sheets when an existing workbook is regenerated.

    Only previously stored supplementary sheets are copied; canonical live sheets
    are always rebuilt from JSON, and the Nov26/Long26 tabs are rebuilt from their
    committed research JSON instead of carrying stale interpretations forward.
    """
    output_path = Path(output_path)
    if not output_path.exists():
        return []
    from artifact_tool import Blob, SpreadsheetFile
    previous = SpreadsheetFile.import_xlsx(Blob.load(str(output_path)))
    imported = []
    # Non-core sheets with no central JSON builder in the repository are preserved.
    for i in range(len(previous.worksheets.items)):
        sh = previous.worksheets.get_item_at(i)
        name = sh.name
        if name in CORE_SHEETS or name in SHEETS:
            continue
        rng = sh.get_used_range()
        values = rng.values
        if not values or not values[0]:
            continue
        width = len(values[0])
        target = wb.worksheets.add(name)
        for at in range(0, len(values), 150):
            block = values[at:at + 150]
            target.get_range_by_indexes(at, 0, len(block), width).values = block
        last = _column_name(width)
        target.get_range(f'A1:{last}1').format = {
            'fill': '#173B4B',
            'font': {'color': '#FFFFFF', 'bold': True},
            'row_height': 27,
        }
        for ci in range(width):
            col = _column_name(ci + 1)
            target.get_range(f'{col}:{col}').format.column_width = 45 if ci > 0 else 26
        target.freeze_panes.freeze_rows(1)
        imported.append(name)
    return imported


def add_to_workbook(wb):
    data = research_data()
    if not data:
        return
    cases = data['cases']
    _write_sheet(wb, 'Nov26 Guide', ['Guide', 'Explanation'], [
        ['Purpose', 'Trace original foresight forward, then return to the original. Not prediction grading.'],
        ['Snapshot date', data.get('as_of', '')],
        ['Existing LLM work', '63 accounts preserved from reviewed-findings.json without reassessment'],
        ['12 new trajectories', 'Independent history; seven direct claims, five broader institutional originals'],
        ['Events', len(data['events'])], ['Sources', len(data['sources'])],
        ['Qualified links', len(data['connections'])],
        ['Source provenance', 'See Catalog Claim ID; blank when there is no direct historical catalogue match'],
        ['Research source', str(DATA_FILE.relative_to(ROOT))],
        ['Caveat', 'New forecast vintages are not observed outcomes; scenarios are not point predictions'],
        ['Caveat', 'A legal target is not measured deployment; a pilot is not market penetration'],
        ['Caveat', 'EU/UK vs EU27 figures and indicator definitions require numerical crosswalks'],
        ['Source URLs', 'Nov26 Sources and Nov26 Evidence retain dates and original URLs'],
        ['Connections', 'Nov26 Links are proposed analytical relationships; no unshown causality'],
    ] + [['Evidence rule', x] for x in data.get('evidence_rules', [])], [27, 105])
    _write_sheet(wb, 'Nov26 Paths', [
        'Case ID','Theme','Original year','Catalog Claim ID','Original row',
        'Original foresight study','Horizon','Original claim / proposition',
        'Conditions / baseline','Forward path to 2026','Latest real-world observation',
        'Meaning / scope change','Trajectory type','What the horizon allows',
        'Evidence confidence','Next hindsight question','Original DOI URL','Source IDs',
    ], [[
        c['id'],c['theme'],c['original_year'],c.get('catalog_claim_id',''),
        c.get('catalog_original_row',''),c['original_title'],c['horizon'],
        c['original_statement'],c['original_condition'],c['path'],c['latest'],
        c['meaning'],c['trajectory'],c['horizon_status'],c['confidence'],
        c['question'],c['original_url'],';'.join(c.get('source_ids',[])),
    ] for c in cases], [12,30,13,30,14,57,24,78,77,88,85,78,45,37,54,79,56,27])
    _write_sheet(wb, 'Nov26 Evidence', [
        'Case ID','Date / coverage','Stage','What happened / was proposed','Evidence class','Source ID',
    ], [[e['case_id'],e['date'],e['stage'],e['event'],e['evidence_class'],e['source_id']]
        for e in data['events']], [13,27,29,99,31,15])
    _write_sheet(wb, 'Nov26 Sources', [
        'Source ID','Case ID','Publication / data source','Source type',
        'Published / updated','Exact URL','Evidence it supports',
    ], [[s['id'],s['case_id'],s['title'],s['source_type'],s['published'],
         s['url'],s['what_this_supports']] for s in data['sources']], [13,12,60,34,25,83,102])
    _write_sheet(wb, 'Nov26 Links', [
        'Link ID','Case A','Case B','Relationship','How the paths connect',
        'Type of link','Confidence','Source IDs','Important caution',
    ], [[c['id'],c['from_id'],c['to_id'],c['headline'],c['interpretation'],
         c['link_type'],c['confidence'],c['source_ids'],c['caution']]
        for c in data['connections']], [13,13,13,54,95,36,19,36,83])
    _write_sheet(wb, 'Nov26 Queue', [
        'Original study to research next','Original year','Next question / method','Status',
    ], [[q['title'],q['year'],q['next_task'],'NOT YET STUDIED in this extension']
        for q in data['queue']], [73,18,96,37])
    _write_sheet(wb, 'Long26 Depth', [
        'Case','Original status','What unfolded / why it matters','How meaning shifted',
        'Alternative reading','Compare only if...','Return-to-original task','Provenance',
    ], [[c['id'],c['horizon_status'],c.get('essay',''),c.get('afterlife',''),
         c.get('alternative',''),c['limits'],c.get('lookback',''),c.get('provenance','')]
        for c in cases], [13,37,93,92,94,84,85,83])
    patterns = [
        ('Target realised under changed conditions','T01, T05','Target and mechanism diverge','A target proves an original model was exact','Crosswalk inputs, denominators, policy and feedstock'),
        ('Warning survives with deadline open','T02','Later measurements inform an early-warning story','The full 2030 target has already failed','Track surveillance and numerical definitions'),
        ('Word changes meaning','T03, T06','Autonomy and digitalization become regulatory constructs','A pilot or approval equals mass adoption','Separate pilot, law, use and impact'),
        ('Conditional potential and observed sink','T04','Potential is not an observed identical accounting series','441 Mt potential equals measured net sink','Rebuild sector boundary and 2050 assumptions'),
        ('Futures combine rather than selecting one','T07','Scenarios form a menu of institutional choices','One scenario had to win','Compare domains and competences'),
        ('Forecast continually re-authored','T08, T12','New model vintages update assumptions','A new forecast is a realised outcome','Archive old vintages and backtest consistent measures'),
        ('Indicators move in different directions','T09, T11','Environment and energy have multiple measures','One positive series establishes total success','Maintain consistent denominators and series'),
        ('Baseline replaced after policy changed','T10','Obsolete counterfactual remains historically informative','Outdated baseline means research is worthless','Record policy break and assumptions'),
    ]
    _write_sheet(wb, 'Long26 Patterns', [
        'Research pattern','Case examples','Meaning of development',
        'Avoid this false conclusion','Research action',
    ], [list(r) for r in patterns], [50,21,73,81,75])
