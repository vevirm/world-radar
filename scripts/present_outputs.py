"""VV Futures: stable reader-facing outputs. No scanning or editorial decisions."""
import json
from collections import defaultdict
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from artifact_tool import Workbook, SpreadsheetFile

ROOT=Path(__file__).resolve().parents[1]
NAVY='173B4B'

def read(path, fallback):
    p=ROOT/path
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else fallback

def setup(doc, running):
    sec=doc.sections[0]
    sec.top_margin=Inches(.76);sec.bottom_margin=Inches(.7)
    sec.left_margin=Inches(.84);sec.right_margin=Inches(.84)
    normal=doc.styles['Normal']; normal.font.name='Aptos';normal.font.size=Pt(9.5);normal.font.color.rgb=RGBColor(39,55,64)
    normal.paragraph_format.space_after=Pt(5)
    for name,size in [('Title',22),('Heading 1',12)]:
        s=doc.styles[name];s.font.name='Aptos Display';s.font.size=Pt(size);s.font.bold=True;s.font.color.rgb=RGBColor(23,59,75)
    sec.header.paragraphs[0].text='VV FUTURES  /  EUROPEAN FORESIGHT OBSERVATORY'
    sec.header.paragraphs[0].style='Caption'
    sec.footer.paragraphs[0].text=running

def lead(doc,title,subtitle):
    doc.add_paragraph(title,'Title'); doc.add_paragraph(subtitle)

def run():
    data=read('observatory-data.json',{'claims':{},'connections':{}})
    claims=sorted((c for c in data.get('claims',{}).values() if 2011<=int(c.get('year',0))<=2022),key=lambda c:(-int(c.get('year',0)),c.get('title','')))
    links=list(data.get('connections',{}).values())
    by=defaultdict(list)
    for p in links:by[p.get('claim_id')].append(p)
    reviews=read('reviewed-findings.json',{'findings':[]}).get('findings',[])

    # Reader-friendly inventory of historical source excerpts, never claiming full-text verification.
    doc=Document();setup(doc,'Original future-oriented excerpts · Links point to the indexed original publication')
    lead(doc,'What was said about Europe’s future','A catalogue of future-oriented passages from studies dated 2011–2022. These are indexed excerpts, not independently checked full-text quotations or evaluated predictions.')
    doc.add_paragraph(f'{len(claims)} historical claim records  ·  2011–2022  ·  Original publication links included')
    for i,c in enumerate(claims,1):
        doc.add_paragraph(f"{i:03}.  {c.get('title','Untitled')}  ({c.get('year','')})",style='Heading 1')
        excerpt=(c.get('original_claim') or '').strip()
        doc.add_paragraph(excerpt or 'Future-related excerpt unavailable.')
        p=doc.add_paragraph();r=p.add_run('ORIGINAL STUDY   ');r.bold=True;r.font.size=Pt(8)
        r=p.add_run(c.get('source_url') or 'Source link not recorded');r.font.size=Pt(8)
        p.paragraph_format.space_after=Pt(12)
    doc.save(ROOT/'VV-FUTURES-HISTORICAL-CLAIMS.docx')

    # Editorial document: preserve supplied conclusions verbatim and mark verification clearly.
    doc=Document();setup(doc,'LLM-reviewed narratives · Source verification still required')
    lead(doc,'European futures — reviewed accounts','58 LLM-assisted interpretations supplied 23 October 2026. These are editorial research drafts. Original claims, later source alignment and cited web references have not all been independently verified.')
    doc.add_paragraph(f'{len(reviews)} research accounts · Not a prediction-accuracy scoreboard')
    for i,f in enumerate(reviews,1):
        doc.add_paragraph(f"{i:02}.  {f.get('title','Untitled')}",style='Heading 1')
        doc.add_paragraph(f.get('interpretation',''),style='Normal')
        p=doc.add_paragraph('Original publication: '+f.get('original_claim',''))
        for r in p.runs:r.font.size=Pt(8)
        for s in f.get('sources',[]):
            p=doc.add_paragraph('Later source: '+s)
            for r in p.runs:r.font.size=Pt(8)
        if f.get('web_sources_as_provided'):
            p=doc.add_paragraph('Additional references (as supplied; links may be missing): '+ '; '.join(f['web_sources_as_provided']))
            for r in p.runs:r.font.size=Pt(8)
        p=doc.add_paragraph('STATUS  ·  LLM-reviewed; awaiting source verification')
        for r in p.runs:r.font.size=Pt(8);r.italic=True
    doc.save(ROOT/'VV-FUTURES-REVIEWED-FINDINGS.docx')

    # Clean overview first; detailed candidate links kept separate for research purposes.
    wb=Workbook.create(); sh=wb.worksheets.add('Start here')
    sh.get_range('A1:B6').values=[['VV FUTURES','European foresight catalogue'],['Historical claim records',len(claims)],['Provisional claim–paper links',len(links)],['LLM-reviewed accounts',len(reviews)],['Status','Research collection; sources not independently validated'],['How to read','Claims = original source excerpts; Later sources = unchecked scanner suggestions']]
    sh.get_range('A1:B1').format={'fill':'#173B4B','font':{'bold':True,'color':'#FFFFFF'},'row_height':30}
    sh.get_range('A1:A6').format.column_width=32;sh.get_range('B1:B6').format.column_width=72
    sh.get_range('A2:A6').format.font.bold=True

    cs=wb.worksheets.add('Historical claims')
    heads=['Year','Original study','What it said about the future','Original source URL','Later source suggestions (unchecked)','Number of candidates','Claim ID']
    rows=[]
    for c in claims:
        papers=by[c['id']]
        snippets=['%s (%s) — %s'%(p.get('source_title',''),p.get('source_year',''),p.get('source_url','')) for p in papers[:3]]
        rows.append([int(c.get('year',0)),c.get('title',''),c.get('original_claim',''),c.get('source_url',''),'\n'.join(snippets),len(papers),c['id']])
    cs.get_range_by_indexes(0,0,len(rows)+1,len(heads)).values=[heads]+rows
    cs.get_range('A1:G1').format={'fill':'#173B4B','font':{'bold':True,'color':'#FFFFFF'},'row_height':30}
    for col,width in [('A',11),('B',43),('C',68),('D',43),('E',64),('F',19),('G',27)]: cs.get_range(f'{col}:{col}').format.column_width=width
    cs.freeze_panes.freeze_rows(1)
    cs.get_range_by_indexes(1,0,len(rows),7).format.row_height=30

    rs=wb.worksheets.add('LLM reviewed')
    rh=['Account','Original publication','Developmental interpretation','Cited later sources','Editorial status']
    rr=[[f.get('title',''),f.get('original_claim',''),f.get('interpretation',''),'\n'.join(f.get('sources',[])),'LLM-reviewed; source verification pending'] for f in reviews]
    rs.get_range_by_indexes(0,0,len(rr)+1,5).values=[rh]+rr
    rs.get_range('A1:E1').format={'fill':'#173B4B','font':{'bold':True,'color':'#FFFFFF'},'row_height':30}
    for col,width in [('A',36),('B',58),('C',85),('D',75),('E',40)]:rs.get_range(f'{col}:{col}').format.column_width=width
    rs.freeze_panes.freeze_rows(1)

    ls=wb.worksheets.add('Unreviewed source links')
    lh=['Original claim ID','Later paper','Year','Later paper URL','Why scanner connected them','Status']
    lr=[]
    for p in links:
        rel=p.get('relevance') or {}
        lr.append([p.get('claim_id',''),p.get('source_title',''),p.get('source_year',''),p.get('source_url',''),rel.get('reason',''),p.get('review_status','unchecked')])
    # Chunked writes limit memory pressure for large inventories.
    ls.get_range('A1:F1').values=[lh]
    for start in range(0,len(lr),300):ls.get_range_by_indexes(start+1,0,len(lr[start:start+300]),6).values=lr[start:start+300]
    ls.get_range('A1:F1').format={'fill':'#173B4B','font':{'bold':True,'color':'#FFFFFF'},'row_height':30}
    for col,width in [('A',29),('B',54),('C',12),('D',49),('E',68),('F',23)]:ls.get_range(f'{col}:{col}').format.column_width=width
    ls.freeze_panes.freeze_rows(1)
    out=ROOT/'VV-FUTURES-ALL-CLAIMS-AND-SOURCES.xlsx'; SpreadsheetFile.export_xlsx(wb).save(str(out))
    print('Presented:',len(claims),'claims,',len(links),'candidate links,',len(reviews),'LLM reviews')

if __name__=='__main__':run()
