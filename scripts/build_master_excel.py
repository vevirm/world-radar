"""Regenerate downloadable master workbook from persistent radar JSON after each scan."""
import json
from pathlib import Path
import xlsxwriter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'stuff' / 'WORLD_RADAR_MASTER.xlsx'

def load(filename, key, default):
    path = ROOT / filename
    return json.loads(path.read_text(encoding='utf-8')).get(key, default) if path.exists() else default

def safe(value):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    value = '' if value is None else str(value)
    # Never allow untrusted source text to be evaluated as a spreadsheet formula.
    if value.lstrip().startswith(('=', '+', '-', '@')):
        value = "'" + value
    return value[:32767]

def create():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    priorities = load('priority-50.json', 'items', [])
    leads = load('research-leads.json', 'leads', [])
    actors = load('actors.json', 'actors', [])
    assessments = load('assessments.json', 'assessments', [])
    state = load('radar-state.json', 'documents', {})
    queue = load('radar-state.json', 'queue', [])
    merged = {}
    for url, doc in state.items():
        if not url.startswith('https://'): continue
        merged[url.rstrip('/').lower()] = dict(title=doc.get('title', url), type='Scanned document', date=doc.get('date', ''), publisher=doc.get('actor_id', ''), status=doc.get('status', 'Scanned'), detail=doc.get('reason', ''), url=url)
    for q in queue:
        url = q.get('url', '')
        if not url.startswith('https://'): continue
        merged[url.rstrip('/').lower()] = dict(title=q.get('title', url), type='Scanned document', date=q.get('date_hint', ''), publisher=q.get('actor_id', ''), status='Awaiting verification', detail=q.get('source_mode', ''), url=url)
    for lead in leads:
        url = lead.get('url', '')
        if url:
            merged[url.rstrip('/').lower()] = dict(title=lead.get('title',''), type='Research lead', date=lead.get('date',''), publisher=lead.get('publisher') or lead.get('journal',''), status=lead.get('status','Full study unverified'), detail=lead.get('abstract',''),url=url)
    items = sorted(merged.values(),key=lambda x:(x['date'],x['title']),reverse=True)
    wb = xlsxwriter.Workbook(str(OUT), {'strings_to_urls':False})
    header = wb.add_format({'bold':True,'font_color':'#FFFFFF','bg_color':'#16324F','text_wrap':True,'valign':'vcenter'})
    normal = wb.add_format({'valign':'top'})
    def tab(name, rows):
        sh=wb.add_worksheet(name)
        if not rows: rows=[{'Information':'No entries yet'}]
        cols=list(dict.fromkeys(k for row in rows for k in row.keys()))
        sh.write_row(0,0,cols,header)
        sh.set_row(0,30)
        sh.freeze_panes(1,0)
        for i,c in enumerate(cols):
            sh.set_column(i,i,55 if c in ('title','detail','abstract','finding','url') else 23)
        for j,row in enumerate(rows,1):
            for i,c in enumerate(cols): sh.write_string(j,i,safe(row.get(c)),normal)
        sh.autofilter(0,0,len(rows),len(cols)-1)
    tab('Scanner 1 All Leads', leads)
    tab('Top 50 Priorities', priorities)
    tab('Retrospective Checks', [{'rank': x['review_priority'], 'title': x['title'], 'publication': x['date'], 'target_year': x.get('target_year',''), 'type': x.get('method',''), 'original_claim': '', 'exact_original_quote': '', 'source_url': x['url'], 'actual_observation': '', 'later_evidence_url': '', 'verdict': 'Not evaluated', 'confidence': '', 'explanation': ''} for x in priorities])
    tab('Everything Collected',items)
    tab('Metadata Checks', [x for x in leads if x.get('metadata_checked_at')])
    tab('Scanned Documents',[{'url':url,**obj} for url,obj in state.items()])
    tab('Verification Queue',queue)
    tab('Research Sources',actors)
    tab('Assessments',assessments)
    wb.close()
    print(f'Built {OUT.name}: {len(items)} unique URLs, {len(leads)} leads')

if __name__=='__main__': create()
