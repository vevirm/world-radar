"""Reader-facing research supplement; never promotes tentative links to verified findings."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def research_cases():
    p=ROOT/'radar2-research-notes.json'
    if not p.exists():return []
    data=json.loads(p.read_text(encoding='utf-8'))
    return [c for b in data.get('batches',[]) for c in b.get('cases',[])]

def research_records():
    records=[]
    for c in research_cases():
        s=c['synthesis']; sc=c['original_source_check']; rid=c['record_id']
        paras=['Record ID: '+rid,
          'Original source: '+sc.get('source_url',''),
          'Study interpretation: '+sc.get('interpretation_or_correction',''),
          'Connections and continuities: '+s.get('continuities',''),
          'Departures and surprises: '+s.get('departures_and_surprises',''),
          'Unresolved questions: '+s.get('unresolved','')]
        for ev in c.get('new_evidence',[]):
            paras.extend(['Later source: '+ev.get('title','')+' ('+str(ev.get('published_date',''))+') '+ev.get('url',''),
              'Observed or reported: '+ev.get('specific_observation',''),
              'Connection (proposed): '+ev.get('how_it_relates_to_original',''),
              'Limit of interpretation: '+ev.get('causality_limit','')])
        for correction in c.get('corrections_to_existing',[]):
            paras.append('Correction for further review: '+correction.get('proposed_correction','')+' '+correction.get('supporting_url',''))
        paras.append('Editorial status: Further independent checks required. Not a prediction verdict or proof of causal influence.')
        records.append(('Research case '+rid,paras))
    return records

def evidence_rows():
    rows=[]
    for c in research_cases():
        for e in c.get('new_evidence',[]):
            rows.append([c['record_id'],c['original_source_check'].get('source_url',''),e.get('evidence_id',''),e.get('title',''),str(e.get('published_date','')),e.get('publisher_or_authors',''),e.get('url',''),e.get('specific_observation',''),e.get('how_it_relates_to_original',''),e.get('causality_limit',''),e.get('verification_status',''),c['synthesis'].get('recommended_update','')])
    return rows


def add_reviewed_research(doc):
    """Documented research accounts; preserve evidence and uncertainty, without prediction grading."""
    from docx.shared import Pt
    cases=research_cases()
    if not cases:
        return
    doc.add_page_break()
    doc.add_paragraph('New research accounts — 26 October 2026',style='Heading 1')
    doc.add_paragraph('Twelve additional research accounts, developed from external LLM source investigations. These are reviewed research syntheses, not judgments of whether future scenarios came true. Sources were checked to varying depths; some original papers were accessible only as abstracts. Unresolved questions are part of the findings.')
    for i,c in enumerate(cases,1):
        s=c['synthesis']; original=c['original_source_check']
        doc.add_paragraph(f"NEW {i:02}.  {c['record_id']}", style='Heading 1')
        for label,key in [('What continues','continuities'),('What changed or surprised','departures_and_surprises'),('Open questions','unresolved')]:
            p=doc.add_paragraph();p.add_run(label+': ').bold=True;p.add_run(s.get(key,''))
        p=doc.add_paragraph();p.add_run('Original study and scope: ').bold=True;p.add_run(original.get('interpretation_or_correction',''))
        doc.add_paragraph('Original study: '+original.get('source_url',''))
        for e in c.get('new_evidence',[]):
            p=doc.add_paragraph();p.add_run('Later evidence — ').bold=True;p.add_run(e.get('title','')+' ('+str(e.get('published_date',''))+')')
            doc.add_paragraph(e.get('url',''))
            doc.add_paragraph('Reported: '+e.get('specific_observation',''))
            doc.add_paragraph('Relevance: '+e.get('how_it_relates_to_original',''))
            doc.add_paragraph('Limit: '+e.get('causality_limit',''))
        for correction in c.get('corrections_to_existing',[]):
            doc.add_paragraph('Research correction or caveat: '+correction.get('proposed_correction',''))
        status='Research account with outstanding source/numeric review' if s.get('recommended_update')=='needs_human_review' else 'LLM-researched account, source-check limitations retained'
        p=doc.add_paragraph('RESEARCH STATUS  ·  '+status)
        for r in p.runs:r.italic=True;r.font.size=Pt(8)
