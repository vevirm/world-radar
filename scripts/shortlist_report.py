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
try:
    from .evidence_policy import classify, substantive_excerpt, same_geographic_context
except ImportError:
    from evidence_policy import classify, substantive_excerpt, same_geographic_context

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


# Lightweight title checks are screening hints, NOT proof of scholarly relevance.
# Keep questionable sources in the archive, but do not reward them as evidence.
STATUS_RE = re.compile(r"^\s*(?:\[?retracted(?:\s+article)?\]?|\[?withdrawn\]?|retraction\s+(?:notice|of)|article\s+retracted|editorial\s+expression\s+of\s+concern)\s*[:.\-–—]?", re.I)
FUTURE_RE = re.compile(r'\b(future|foresight|forecast|projection|scenario|outlook|vision|anticipat|predict|planned|planning|prospect|transition|target)\w*\b',re.I)


def title_key(title):
    title = STATUS_RE.sub('', str(title or ''))
    return ' '.join(sorted(words(title)))


def marked_invalid(item):
    title = str(item.get('title', '')) if isinstance(item, dict) else str(item or '')
    return bool(STATUS_RE.match(title) or (isinstance(item, dict) and
        (item.get('is_retracted') is True or item.get('is_withdrawn') is True)))


def same_work(a, b):
    aa, bb = words(STATUS_RE.sub('', str(a or ''))), words(STATUS_RE.sub('', str(b or '')))
    if not aa or not bb:
        return False
    return aa == bb or (len(aa & bb) >= 4 and len(aa & bb)/len(aa | bb) >= .85)


METHOD_WORDS = set(('forecast forecasting forecasted predictor prediction predictive predicting method methods machine learning '
    'artificial intelligence algorithm algorithms neural network networks data statistical statistics statistical '
    'model models modelling modeling methodology methodologies technique techniques approach approaches '
    'using use employed applied applications application system systems simulation simulations computing '
    'scenario scenarios foresight analysis prediction').split())
NON_EU_EXAMPLES = re.compile(r'\b(morocco|india|china|brazil|mexico|australia|japan|nigeria|kenya|thailand|nepal|pakistan)\b',re.I)


def has_subject_anchor(original, newer):
    # Overlap in a technique (e.g. "machine learning") is not overlap in the issue
    # (e.g. loan defaults versus weather forecasts).
    a,b = words(original)-METHOD_WORDS, words(newer)-METHOD_WORDS
    shared=a & b
    if a and not shared:
        return False
    if re.search(r'\b(europe|european|eu|eurozone)\b',str(original),re.I) and \
       NON_EU_EXAMPLES.search(str(newer)) and not re.search(r'\b(europe|european|eu|eurozone)\b',str(newer),re.I):
        return False
    return True

def related_enough(original, newer):
    similarity, common = same_subject(original, newer)
    # For a very short, distinctive title, 2 highly specific shared terms can suffice.
    short_exception = common >= 2 and similarity >= .68 and max(len(words(original)),len(words(newer))) <= 4
    return has_subject_anchor(original,newer) and ((common >= 3 and similarity >= .38) or short_exception)


def links_for(r):
    year = year_of(r.get('year'))
    seen_urls, seen_titles = set(), set()
    found = []
    for f in list(r.get('direction_trails') or []) + list(r.get('followups') or []) + list(r.get('field_developments') or []):
        if not isinstance(f, dict):
            continue
        url = str(f.get('url', '')).strip()
        title = str(f.get('title', '')).strip()
        fy = year_of(f.get('year'))
        if not url.startswith('https://') or not title or url in seen_urls:
            continue
        if fy and (fy < year or fy > date.today().year):
            continue
        seen_urls.add(url)
        title_id = title_key(title)
        duplicate = bool(title_id and title_id in seen_titles)
        seen_titles.add(title_id)
        same_original = same_work(r.get('title'),title)
        retracted = marked_invalid(f)
        score, shared = same_subject(r.get('title'), title)
        role = f.get('evidence_role')
        # Do not trust a prior saved 'same_issue' label blindly: old scans
        # were screened using earlier, weaker versions of the policy.
        original_for_check = {'title': r.get('title'), 'original_publication': r.get('year'),
                              'source_url': r.get('original_url')}
        source_field = ('direction_evidence' if f in (r.get('direction_trails') or []) else
                        'follow_up_publications' if f in (r.get('followups') or []) else 'field_developments')
        checked, _why = classify(original_for_check, f, source_field)
        if checked != 'direct':
            role = 'related_context'
        elif role != 'related_context':
            role = 'same_issue_literature'
        # Shared screening of stored links is authoritative. Broad/indirect
        # context is retained in the atlas but never ranked as positive evidence.
        confidence = 'withdrawn' if retracted else ('repeat' if duplicate or same_original else
                        ('weak' if role == 'related_context' else
                         'candidate' if role == 'same_issue_literature' or
                         (role is None and related_enough(r.get('title'),title)) else 'weak'))
        found.append({**f, '_from_direction':bool(f.get('evidence_kind')),
                      '_score': score, '_shared': shared, '_year': fy,
                      '_status': confidence, '_independent': confidence == 'candidate'})
    return found


def concrete_review(r):
    now = str(r.get('now', '')).strip()
    missing = ('No later real-world outcome established', 'No later', 'Not established',
               'potentially related later publication', 'Not yet', 'Needs an update')
    sources = [x for x in (r.get('sources') or []) if isinstance(x,dict) and
               str(x.get('url','')).startswith('https://')]
    return bool(sources and len(now)>=45 and not any(now.startswith(x) for x in missing))


def sort_data(atlas):
    today = date.today().year
    good, weak = [], []
    for r in atlas.get('records', []):
        if not isinstance(r, dict) or not r.get('title'):
            continue
        y = year_of(r.get('year'))
        if not (1995 <= y <= today - 3):
            continue
        links = links_for(r)
        rated = r.get('rating') if isinstance(r.get('rating'), dict) else {}
        number = rated.get('value')
        number = number if type(number) is int and 1 <= number <= 100 else None
        # A title-only pair is useful as a reading lead, but not sufficient
        # to headline the strongest cases. Require an actual abstract excerpt.
        credible = sorted([l for l in links if l['_independent'] and l['_year'] >= y + 2
                           and substantive_excerpt(l.get('abstract_excerpt') or l.get('finding_from_abstract'))],
                          key=lambda x: (x['_score'], x['_shared'], x['_from_direction'], x['_year']), reverse=True)
        best = credible[0] if credible else None
        reviewed = concrete_review(r)
        item = {'record': r, 'links': links, 'best': best, 'recent': max((l['_year'] for l in credible), default=0),
                'rated': number, 'reviewed': reviewed, 'close':len(credible), 'strength':'reviewed' if reviewed else 'candidate'}
        if not marked_invalid(r) and (reviewed or credible):
            score = (220 if reviewed else 0)
            score += 60 * (best['_score'] if best else 0) + 12 * min(len(credible), 3)
            if best and best['_from_direction']: score += 8
            score += 24 * max(0, 1 - (today-item['recent'])/12) if item['recent'] else 0
            score += 22 if best and same_geographic_context(r.get('title'), best.get('title'), best.get('abstract_excerpt')) else 0
            score += 8 if FUTURE_RE.search(r['title']) else 0
            if reviewed and number is not None:
                score += 0.15 * number
            # Penalize titles that are actually historical retrospective accounts.
            if re.search(r'\b(1[789]\d\d|19[0-6]\d)\s*[-–]\s*(?:1[789]\d\d|19[0-6]\d)\b',r['title']):
                score -= 90
            item['rank'] = score
            good.append(item)
        if marked_invalid(r):
            item['weak_type']='withdrawn_original';item['weak_rank']=500
        elif any(l['_status']=='withdrawn' for l in links) and not credible:
            item['weak_type']='withdrawn_followup';item['weak_rank']=430
        elif links and not credible:
            if any(l['_status']=='repeat' for l in links):
                item['weak_type']='repeat';item['weak_rank']=360
            else:
                item['weak_type']='mismatch';item['weak_rank']=340
        elif not links:
            item['weak_type']='missing';item['weak_rank']=120+min(today-y,25)
        elif number is not None and number <= 40 and reviewed:
            item['weak_type']='reviewed';item['weak_rank']=260-number
        else:
            continue
        if not reviewed or item['weak_type'] in ('withdrawn_original','reviewed'):
            weak.append(item)

    good.sort(key=lambda x: (x['rank'],x['recent'],x['record']['title']),reverse=True)
    weak.sort(key=lambda x: (x['weak_rank'],-year_of(x['record'].get('year')),x['record']['title']),reverse=True)

    def diverse(items, exclude=None, number=20):
        exclude = set(exclude or [])
        chosen, per_topic, used_titles = [], Counter(), set()
        for limit in (4, 7, 99):
            for item in items:
                r=item['record']; key=r.get('id') or r['title']; canonical=title_key(r.get('title'))
                if key in exclude or per_topic[r.get('topic')]>=limit or canonical in used_titles:
                    continue
                chosen.append(item);exclude.add(key);used_titles.add(canonical)
                per_topic[r.get('topic')]+=1
                if len(chosen)==number:return chosen
        return chosen

    top=diverse(good)
    bottom=diverse(weak,exclude=[x['record'].get('id') or x['record']['title'] for x in top])
    return top,bottom


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

    # Keep the entire DOCX monochrome, including the built-in Title border.
    for node in doc.styles.element.xpath('.//w:color'):
        node.set(qn('w:val'), '000000')
        for attr in ('themeColor','themeTint','themeShade'):
            node.attrib.pop(qn('w:' + attr), None)
    for node in doc.styles.element.xpath('.//w:bottom'):
        if node.get(qn('w:color')) is not None:
            node.set(qn('w:color'), '000000')
            node.attrib.pop(qn('w:themeColor'), None)

    doc.add_heading('40 ideas to revisit', 0)
    p=para(f'{len(top)} strongest research trails  /  {len(bottom)} research trails to recheck (maximum 20 each)')
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
                abstract = str(best.get('abstract_excerpt') or best.get('finding_from_abstract') or '').strip()
                evidence_label = best.get('evidence_kind')
                observed_wording = bool(re.search(
                    r'\b(?:results? (?:show|indicat|suggest)|data (?:show|indicat)|observed|measured|'
                    r'increased|decreased|rose|fell|we found|we find|authors (?:found|demonstrat)|'
                    r'reforms? (?:came about|were enacted))\w*', abstract, re.I))
                if evidence_label in ('measured_or_reported_change', 'implementation_or_evaluation') and abstract and observed_wording:
                    para(f"A {best['_year']} paper reports: {abstract[:270]}", bold_label='NOW  ')
                elif abstract:
                    para(f"Newer research ({best['_year']}) discusses: {abstract[:230]}", bold_label='NOW  ')
                else:
                    para(f"A later study ({best['_year'] or 'date unrecorded'}) explores: {best['title']}.", bold_label='NOW  ')
                para(f"This is a same-question research trail ({item['close']} linked publication(s)). It shows continuing work, not necessarily a measured outcome.", bold_label='WHY HERE  ')
            else:
                para('Original and later source reviews are recorded.',bold_label='WHY HERE  ')
            if item['rated'] is not None:
                para(f"Existing source-reviewed editorial assessment: {item['rated']}/100 (not a probability or outcome score).", bold_label='REVIEW  ')
        else:
            k=item['weak_type']; best=item['best'];
            if k=='reviewed':
                para(f"An existing editorial assessment rated this case {item['rated']}/100; consult the reasons and sources before calling it a failure.",bold_label='WHY HERE  ')
            elif k=='withdrawn_original':
                para('The original record is explicitly marked withdrawn or retracted. Retained for historical transparency, not treated as reliable evidence.',bold_label='WHY HERE  ')
            elif k=='withdrawn_followup':
                para('A possible follow-up is marked withdrawn or retracted and cannot support a positive ranking.',bold_label='WHY HERE  ')
            elif k=='repeat':
                para('The apparent later evidence closely repeats the original or another linked publication. An independent follow-up has not been established.',bold_label='WHY HERE  ')
            elif k=='mismatch':
                para('The available newer titles do not establish a close subject match. The link could be tangential and needs checking.',bold_label='WHY HERE  ')
            elif k=='missing':
                para('No later publication is linked in the saved atlas. This may reflect gaps in search coverage.',bold_label='WHY HERE  ')
            else:
                para('The saved links do not yet provide a close, convincing later research trail. Relevance remains unassessed.',bold_label='WHY HERE  ')
            para('Still relevant, superseded, or simply under-researched? A source-based review is needed.',bold_label='OPEN  ')
        p=doc.add_paragraph();p.paragraph_format.space_after=Pt(8)
        link(p,'Original publication',r.get('original_url',''))
        later = item['best'] or next((l for l in item['links'] if l['_status'] in ('withdrawn','repeat','weak')),None)
        if later:
            p.add_run('   ·   ')
            link(p, 'Later publication (check status)' if later['_status']!='candidate' else 'Later publication', later['url'])

    doc.add_heading(f'The strongest research trails ({len(top)} selected; maximum 20)', 1)
    para('These are the strongest automatically screened later-research trails, not verified successes. Withdrawn, retracted and repeated publications are excluded from positive evidence.')
    for i,item in enumerate(top,1):add_entry(i,item,True)
    doc.add_heading(f'Weakest / possibly outdated trails ({len(bottom)} selected; maximum 20)', 1)
    para('These are search-quality or publication-status warnings. A missing or poor link does not mean the original idea is obsolete, false or irrelevant.')
    for i,item in enumerate(bottom,1):add_entry(i,item,False)
    doc.add_heading('How this list updates',1)
    para('Each successful Radar 2 run refreshes living-atlas.json. The companion Word workflow then builds this file again '
         'from those saved entries. It selects candidates by source-linked review, same-question follow-ups, freshness '
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
    if result['strongest']<20 or result['weakest']<20:
        print('NOTICE: Fewer than 20 qualified cases in a category; refusing to pad the ranking with weak links.')


if __name__ == '__main__': main()
