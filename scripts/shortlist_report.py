"""Produce a short, honest Radar 2 shortlist from its current living-atlas.json.

No API calls, no verdicts inferred from paper titles, and no changes to source data.
This is an evidence-trail shortlist until original claims and outcomes are reviewed.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from datetime import date
from pathlib import Path

STOP = set(('the a an and or of for in on to from as at by with across under into through toward towards '
            'about between within how what why when which where whose this that these those a study review '
            'studies model modelling modeling research analysis evidence impact impacts effects effect european '
            'europe eu future futures scenarios scenario potential current new recent approach approaches '
            'framework frameworks results using based assessment evaluation policy policies union european europe global national ' 
            'international challenges challenge strategic strategy conference perspective perspectives questions issue issues ' 
            'development developing role roles long term public comparative').split())


def words(value):
    return {w for w in re.findall(r"[a-zà-ÿ][a-zà-ÿ0-9-]{2,}", str(value or '').casefold())
            if w not in STOP and not w.isdigit()}


def same_subject(a, b):
    x, y = words(a), words(b)
    if not x or not y:
        return 0.0, 0
    overlap = len(x & y)
    score = 0.6 * overlap / max(1, min(len(x), len(y))) + 0.4 * overlap / len(x | y)
    return score, overlap


def year_of(value):
    m = re.search(r'\b(19\d\d|20\d\d)\b', str(value or ''))
    return int(m.group(1)) if m else 0


def links_for(r):
    year = year_of(r.get('year'))
    seen = set()
    found = []
    for f in list(r.get('followups') or []) + list(r.get('field_developments') or []):
        if not isinstance(f, dict):
            continue
        url = str(f.get('url', ''))
        title = str(f.get('title', '')).strip()
        fy = year_of(f.get('year'))
        if not url.startswith('https://') or not title or url in seen:
            continue
        if fy and (fy < year or fy > date.today().year):
            continue
        seen.add(url)
        s, shared = same_subject(r.get('title'), title)
        found.append({**f, '_score': s, '_shared': shared, '_year': fy})
    return found


def sort_data(atlas):
    today = date.today().year
    good, weak = [], []
    for r in atlas.get('records', []):
        if not isinstance(r, dict) or not r.get('title'):
            continue
        y = year_of(r.get('year'))
        # Current-year publications cannot be judged as retrospective cases.
        if not (1995 <= y <= today - 3):
            continue
        links = links_for(r)
        rated = r.get('rating') if isinstance(r.get('rating'), dict) else {}
        number = rated.get('value')
        number = number if type(number) is int and 1 <= number <= 100 else None
        valid = sorted([l for l in links if l['_year'] >= y + 2],
                       key=lambda x: (x['_score'], min(x['_year'], today), x['_shared']), reverse=True)
        strongest = valid[0] if valid else None
        close = [l for l in valid if l['_shared'] >= 3 and l['_score'] >= .34]
        newest_close = max((l['_year'] for l in close), default=0)
        recordsources = [e for e in (r.get('sources') or []) if isinstance(e, dict) and str(e.get('url','')).startswith('https://')]
        item = {'record':r, 'links':links, 'best':strongest, 'recent':newest_close,
                'rated':number, 'reviewed':bool(recordsources), 'close':len(close)}
        if (close or recordsources or number is not None):
            score = (300 if recordsources else 0) + (70 if number is not None else 0)
            score += (number / 2 if number is not None else 0) + 95 * (strongest['_score'] if strongest else 0)
            score += 12 * min(len(close), 4) + 35 * max(0, 1 - (today - newest_close) / 12) if newest_close else 0
            score += 8 if len(str(r.get('then', ''))) > 100 and 'Original title is indexed' not in str(r.get('then')) else 0
            item['rank'] = score
            good.append(item)
        # Weak list: evidence trail weak / unreviewed, not a claim of a bad original idea.
        if number is not None and number <= 40 and recordsources:
            item['weak_type'] = 'reviewed'
            item['weak_rank'] = 500 - number
        elif not links:
            item['weak_type'] = 'missing'
            item['weak_rank'] = 100 + min(today-y,25) + (10 if not r.get('sources') else 0)
        elif strongest and (strongest['_shared'] < 2 or strongest['_score'] < .16):
            item['weak_type'] = 'mismatch'
            item['weak_rank'] = 260 + 100*(.16 - strongest['_score']) + max(0, today - max(l['_year'] for l in links))/4
        elif close == [] and not recordsources:
            item['weak_type'] = 'old'
            item['weak_rank'] = 70 + max(0, today - max((l['_year'] for l in links),default=y))
        else:
            continue
        if not recordsources or item['weak_type'] == 'reviewed':
            weak.append(item)

    good.sort(key=lambda x: (x['rank'], x['recent'], x['record']['title']), reverse=True)
    weak.sort(key=lambda x: (x['weak_rank'], -year_of(x['record'].get('year')), x['record']['title']), reverse=True)

    def diverse(items, exclude=None, number=20):
        exclude = set(exclude or [])
        chosen, per_topic, used_titles = [], Counter(), set()
        for limit in (4, 7, 99):
            for item in items:
                r = item['record']; key = r.get('id') or r['title']
                if key in exclude or per_topic[r.get('topic')] >= limit or ' '.join(sorted(words(r.get('title')))) in used_titles:
                    continue
                chosen.append(item); exclude.add(key); used_titles.add(' '.join(sorted(words(r.get('title'))))); per_topic[r.get('topic')] += 1
                if len(chosen) == number: return chosen
        return chosen

    top = diverse(good)
    bottom = diverse(weak, exclude=[(x['record'].get('id') or x['record']['title']) for x in top])
    return top, bottom


def write_shortlist(atlas, target):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.opc.constants import RELATIONSHIP_TYPE
    from docx.shared import Inches, Pt, RGBColor

    top, bottom = sort_data(atlas)
    doc = Document(); sec=doc.sections[0]
    sec.top_margin=Inches(.65); sec.bottom_margin=Inches(.66)
    sec.left_margin=Inches(.77); sec.right_margin=Inches(.77)
    normal=doc.styles['Normal']; normal.font.name='Arial'; normal.font.size=Pt(9.4)
    normal.font.color.rgb=RGBColor(0,0,0)
    normal.paragraph_format.space_after=Pt(4)
    for name,size in [('Title',22),('Heading 1',15),('Heading 2',10.5)]:
        s=doc.styles[name];s.font.name='Arial';s.font.size=Pt(size);s.font.color.rgb=RGBColor(0,0,0)
        s.font.bold=True; s.paragraph_format.space_before=Pt(10);s.paragraph_format.space_after=Pt(5)
        s.paragraph_format.keep_with_next=True
    sec.header.paragraphs[0].text='WORLD RADAR   /   SHORT EDITION'
    for run in sec.header.paragraphs[0].runs:
        run.font.size=Pt(7.5);run.font.bold=True
    footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    footer.add_run('World Radar  •  ')
    fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');footer._p.append(fld)

    def para(text='', bold_label=None):
        p=doc.add_paragraph()
        if bold_label: p.add_run(bold_label).bold=True
        p.add_run(str(text or ''))
        return p

    def link(p, text, url):
        if not str(url).startswith('https://'):return
        id=p.part.relate_to(str(url), RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
        h=OxmlElement('w:hyperlink');h.set(qn('r:id'),id)
        rr=OxmlElement('w:r');pr=OxmlElement('w:rPr')
        c=OxmlElement('w:color');c.set(qn('w:val'),'000000');pr.append(c)
        u=OxmlElement('w:u');u.set(qn('w:val'),'single');pr.append(u)
        rr.append(pr);txt=OxmlElement('w:t');txt.text=text;rr.append(txt);h.append(rr);p._p.append(h)

    doc.add_heading('40 ideas to revisit', 0)
    p=para('20 strongest research trails  /  20 weakest or possibly outdated trails')
    p.runs[0].bold=True
    para(f"Based on World Radar's living atlas ({atlas.get('generated_utc', 'latest saved edition')}). "
         f"{atlas.get('summary', {}).get('total',len(atlas.get('records',[]))):,} older and newer research entries available. "
         'This shortlist updates when Radar 2 publishes new data.')
    para('IMPORTANT: "Strongest" means comparatively useful, traceable later evidence; it does NOT mean a prediction came true. '
         '"Weakest" means the saved follow-up trail is sparse, old, or potentially unrelated; it does NOT mean the original research was wrong or irrelevant. '
         'An unreviewed item is not given a fake 1–100 grade.')

    def add_entry(i, item, positive):
        r=item['record']; yr=r.get('year') or '?'; title=' '.join(str(r.get('title','')).split())
        h=doc.add_heading(f'{i:02d}.  {title}  ({yr})', level=2)
        h.paragraph_format.keep_with_next=True
        if positive:
            best=item['best'];
            if item['reviewed']:
                para(r.get('now','The saved evidence needs individual source review.'), bold_label='NOW  ')
                para('A source-linked observation is recorded. Its scope and direct connection to the original study still need checking.',bold_label='WHY HERE  ')
            elif best:
                para(f"A related study appeared in {best['_year'] or 'an undated year'}: {best['title']}.", bold_label='NOW  ')
                para(f"There are {item['close']} plausible later study link(s) in this trail, reaching {item['recent'] or 'an undated year'}. The research has moved; the real-world outcome still needs checking.",bold_label='WHY HERE  ')
            else:
                para('Original and later source reviews are recorded.',bold_label='WHY HERE  ')
            if item['rated'] is not None:
                para(f"Existing source-reviewed editorial assessment: {item['rated']}/100 (not a probability or outcome score).", bold_label='REVIEW  ')
        else:
            k=item['weak_type']; best=item['best'];
            if k=='reviewed':
                para(f"An existing editorial assessment rated this case {item['rated']}/100; consult the reasons and sources before calling it a failure.",bold_label='WHY HERE  ')
            elif k=='mismatch':
                para(f"A paper was linked ({best['_year'] or '?'}), but its title has little distinctive overlap with the original: {best['title']}.",bold_label='WHY HERE  ')
            elif k=='missing':
                para('No later publication is linked in the saved atlas. This may reflect gaps in search coverage.',bold_label='WHY HERE  ')
            else:
                para('The saved links do not yet provide a close, convincing later research trail. Relevance remains unassessed.',bold_label='WHY HERE  ')
            para('Still relevant, superseded, or simply under-researched? A source-based review is needed.',bold_label='OPEN  ')
        p=doc.add_paragraph();p.paragraph_format.space_after=Pt(8)
        link(p,'Original publication',r.get('original_url',''))
        if item['best']:
            p.add_run('   ·   ')
            link(p,'Later publication',item['best']['url'])

    doc.add_heading(f'The 20 strongest research trails ({len(top)} selected)', 1)
    para('These are the most useful follow-up connections found in the current index, with topic diversity included. They are not ranked forecasts.')
    for i,item in enumerate(top,1):add_entry(i,item,True)
    doc.add_heading(f'20 weakest / possibly outdated trails ({len(bottom)} selected)', 1)
    para('These need better verification, or the current link may be too thin. “Weak evidence” is not the same as “bad foresight.”')
    for i,item in enumerate(bottom,1):add_entry(i,item,False)
    doc.add_heading('How this list updates',1)
    para('Each successful Radar 2 run refreshes living-atlas.json. The companion Word workflow then builds this file again '
         'from those saved entries. It selects candidates by source-linked review, later-publication relevance, freshness '
         'and diversity of subjects. It does not perform an extra paid research scan.')
    para('A proper best/worst judgement requires reading the original claim and checking independent later observations. '
         'Where that review is missing, the shortlist is a research triage list rather than a verdict.')
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True);doc.save(target)
    return {'file':str(target),'strongest':len(top),'weakest':len(bottom),'records':len(atlas.get('records',[]))}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--atlas',default='living-atlas.json')
    parser.add_argument('--output',default='stuff/WORLD_RADAR_20_BEST_20_TO_RECHECK.docx')
    a=parser.parse_args()
    data=json.loads(Path(a.atlas).read_text(encoding='utf-8'))
    if not data.get('records'):
        raise SystemExit('No records found; refusing to publish an empty shortlist.')
    result=write_shortlist(data,a.output)
    print(json.dumps(result))
    if len(data['records'])>=100 and (result['strongest']<20 or result['weakest']<20):
        raise SystemExit('Large atlas but incomplete shortlist: check selection criteria.')


if __name__ == '__main__': main()
