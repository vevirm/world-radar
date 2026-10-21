"""Screen existing Radar 2 literature trails before publication; no API calls.

The original papers, manual observations and verified outcomes are never deleted.
Suspect automated links are quarantined with a reason, not erased from history.
Run without --apply for a preview; --apply writes vetted data and rebuilds the atlas.
"""
from __future__ import annotations
import argparse
import copy
import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path

TRAIL_FIELDS = ('direction_evidence', 'follow_up_publications', 'field_developments')
# Terms describing methods, venues, and paper genres, not an actual ISSUE.
GENERIC = set('''the and with from into over under around among versus between within through
its their for this that these those europe european union eu global national international
research study studies paper papers authors review report reports analysis modelling modeling
models model simulated simulations simulation scenarios scenario forecast forecasting foresight
prediction predictions projection projections future futures expected potential prospects
assessing assessment evaluation evaluating impacts impact effects effect method methods
machine learning artificial intelligence statistical using approach approaches framework
frameworks applications application policy policies strategy strategies implications
case results evidence findings perspective perspectives patterns changes change new
recent past current regional broad scale large small term long short some one two three
what how where when which associated role roles part parts field fields overview
investigation implications technology technologies data dataset issues issue response
'''.split())
# The method-only terms above exclude words that distinguish actual research
# subjects: climate, emissions, migration, cybersecurity, pesticides, etc.
EU = re.compile(r'\b(?:europe|european|european union|\beu\b|eurozone)\b', re.I)
OUTSIDE = re.compile(r'\b(?:russia|russian|china|chinese|india|indian|brazil|brazilian|'
                     r'australia|australian|japan|japanese|morocco|moroccan|'
                     r'mexico|mexican|belarus|belarusian|nigeria|nigerian|'
                     r'pakistan|pakistani|turkey|turkish|nepal|nepalese)\b', re.I)
COUNTRIES = re.compile(r'\b(?:germany|german|france|french|finland|finnish|'
                       r'poland|polish|italy|italian|sweden|swedish|spain|spanish|'
                       r'denmark|danish|netherlands|dutch|belgium|belgian|'
                       r'portugal|portuguese|austria|austrian|greece|greek|'
                       r'ireland|irish|estonia|estonian|uk|britain|british)\b', re.I)
WITHDRAWN = re.compile(r'(?:\bwithdrawn\b|\bretracted\b|\bretraction\b|\bexpression of concern\b)', re.I)


def tokenize(text):
    raw = re.findall(r'[a-zà-ÿ][a-zà-ÿ0-9-]{2,}', str(text or '').casefold())
    output = set()
    for w in raw:
        if w in GENERIC or w.isdigit():
            continue
        if len(w) > 5 and w.endswith('ies'):
            w = w[:-3]+'y'
        elif len(w) > 5 and w.endswith('s') and not w.endswith(('ss','us','is')):
            w = w[:-1]
        output.add(w)
    return output


def normalize_url(url):
    return str(url or '').strip().casefold().rstrip('/')


def published_year(value):
    m = re.search(r'\b(?:19|20)\d{2}\b', str(value or ''))
    return int(m.group()) if m else 0


def scope_mismatch(original, newer_title):
    # Cross-country comparisons are useful as context, but do not establish
    # the original region's trajectory. Screen only explicit mismatches.
    return bool(EU.search(original) and OUTSIDE.search(newer_title) and
                not EU.search(newer_title) and not OUTSIDE.search(original) and
                not COUNTRIES.search(newer_title))


def same_work(original, later):
    a,b = tokenize(original),tokenize(later)
    if a and a == b:
        return True
    return len(a & b) >= 4 and len(a & b)/max(1,len(a | b)) >= .89


def screen_one(entry, item, field):
    if not isinstance(item,dict):
        return 'malformed_connection'
    original = str(entry.get('title') or entry.get('expected') or '')
    newer = str(item.get('title') or '')
    url = normalize_url(item.get('url'))
    if not newer.strip() or not url.startswith('https://'):
        return 'missing_title_or_valid_link'
    if item.get('is_retracted') is True or item.get('is_withdrawn') is True or WITHDRAWN.search(newer):
        return 'withdrawn_or_retracted'
    if url == normalize_url(entry.get('source_url')) or same_work(original,newer):
        return 'same_work_or_republication'
    oldyear = published_year(entry.get('original_publication')) or published_year(entry.get('year'))
    newyear = published_year(item.get('date')) or published_year(item.get('year'))
    if newyear and (newyear > dt.date.today().year or (oldyear and newyear < oldyear)):
        return 'not_a_later_publication'
    if newyear and oldyear and newyear==oldyear:
        old_date=str(entry.get('original_publication') or '')[:10]
        new_date=str(item.get('date') or '')[:10]
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}',old_date) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',new_date) and new_date<=old_date:
            return 'not_a_later_publication'
    if scope_mismatch(original,newer) or item.get('geography') == 'other_region':
        return 'different_geographic_scope'
    base = tokenize(original)
    newer_tokens = tokenize(newer)
    common = base & newer_tokens
    # Issue-first OpenAlex hits may use new wording in the title. In that case
    # accept relevant abstract anchors, but not merely a model/forecast method.
    if field == 'direction_evidence':
        claimed = set(tokenize(' '.join(item.get('shared_issue_terms') or [])))
        abstract = tokenize(item.get('finding_from_abstract'))
        anchor = base & (newer_tokens | abstract | claimed)
        if len(anchor) >= 2 or (common and len(anchor) >= 1 and
                               item.get('relationship') == 'same_issue_published_followup_not_outcome_verified'):
            return None
        return 'no_specific_issue_in_common'
    if len(common) >= 2:
        return None
    # Sometimes a distinctive issue anchors a short title; use one anchor only
    # when additional abstract information supports the same issue.
    abstract = tokenize(item.get('finding_from_abstract'))
    if len(common)==1 and len(next(iter(common)))>=9 and len(base & abstract)>=2:
        return None
    return 'topic_connection_too_weak'


def clean_entries(raw):
    cleaned = copy.deepcopy(raw)
    quarantine=[]
    reasons=Counter()
    counts=Counter()
    for record_id, entry in cleaned['entries'].items():
        if not isinstance(entry,dict):
            continue
        initial_links=sum(len(entry.get(k) or []) for k in TRAIL_FIELDS if isinstance(entry.get(k) or [],list))
        seen_urls=set()
        for field in TRAIL_FIELDS:
            originals = entry.get(field) or []
            if not isinstance(originals,list):
                continue
            kept=[]
            for candidate in originals:
                counts['examined'] += 1
                reason = screen_one(entry,candidate,field)
                if reason is None:
                    url=normalize_url(candidate.get('url'))
                    if url in seen_urls:
                        reason='duplicate_link_across_trails'
                    else:
                        seen_urls.add(url)
                if reason:
                    reasons[reason]+=1
                    quarantine.append({'lead_id':record_id, 'original_title':entry.get('title'),
                                       'field':field, 'reason':reason, 'publication':candidate})
                else:
                    kept.append(candidate)
                    counts['kept']+=1
            if field in entry or originals:
                entry[field]=kept
        # Recompute generic publication-derived text that may refer to removed links.
        remaining=sum(len(entry.get(k) or []) for k in TRAIL_FIELDS)
        if remaining == 0 and initial_links and initial_links > remaining:
            if re.match(r'Found \d+ potential',str(entry.get('what_happened') or ''),re.I):
                entry['what_happened']='No sufficiently relevant later publication is currently retained; this does not mean the issue stopped developing.'
            entry['what_happened_literature']='No convincing same-issue follow-up remains in the screened saved links. More evidence may exist.'
            entry['literature_signal']='no_screened_followup_kept'
        elif remaining and initial_links > remaining:
            entry['what_happened_literature']=(f'{remaining} candidate later publication(s) remain after screening. '
                 'They suggest possible research directions, not a verified outcome.')
    return cleaned,quarantine,reasons,counts


def run(root, apply):
    src=root/'retrospective-results.json'
    if not src.is_file():
        raise SystemExit(f'Missing {src}; cleanup did not run.')
    original=json.loads(src.read_text(encoding='utf-8'))
    if not isinstance(original.get('entries'),dict) or not original['entries']:
        raise SystemExit('Missing or empty entries; refusing cleanup.')
    cleaned, excluded, reasons, counts=clean_entries(original)
    report={'original_records':len(original['entries']), 'original_links':counts['examined'],
            'kept_links':counts['kept'], 'quarantined_links':len(excluded),
            'reasons':dict(sorted(reasons.items()))}
    print(json.dumps(report, indent=2))
    if not apply:
        print('PREVIEW ONLY: no file changed. Use --apply to publish cleaned results.')
        return report
    if len(cleaned['entries']) != len(original['entries']):
        raise SystemExit('Record loss detected: refusing cleanup.')
    if counts['examined'] >= 20 and len(excluded)/counts['examined'] > .95:
        raise SystemExit('Screen rejected over 95% of links; refusing broad cleanup pending review.')
    # A score/verification table is never touched. No destructive deletions:
    # every excluded relationship is retained in the quarantine registry.
    quarantined_path=root/'evidence-quarantine.json'
    previous={'links':[]}
    if quarantined_path.is_file():
        previous=json.loads(quarantined_path.read_text(encoding='utf-8'))
    prev=previous.get('links',[])
    lookup={(v.get('lead_id'),v.get('field'),normalize_url((v.get('publication') or {}).get('url')))
            for v in prev if isinstance(v,dict)}
    for e in excluded:
        k=(e['lead_id'],e['field'],normalize_url((e.get('publication') or {}).get('url')))
        if k not in lookup:
            prev.append(e);lookup.add(k)
    # Rebuild the atlas in memory before writing ANY files. The source file
    # and atlas both need to be consistent for report generators.
    import sys
    sys.path.insert(0,str(root))
    from scripts.living_atlas import make_atlas
    leads=json.loads((root/'research-leads.json').read_text(encoding='utf-8')).get('leads',[])
    if not leads:
        raise SystemExit('Empty research-leads.json; no files modified.')
    atlas=make_atlas(list(cleaned['entries'].values()),leads=leads)
    if len(atlas['records'])!=len(leads):
        raise SystemExit('Atlas does not preserve the research catalogue; no files modified.')
    # The workflow uploads a copy of the original inputs before this step.
    src.write_text(json.dumps(cleaned,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (root/'living-atlas.json').write_text(json.dumps(atlas,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    quarantined_path.write_text(json.dumps({'method':'Excluded automated links, not discarded original studies or outcomes.',
        'links':prev},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'REBUILT: {len(atlas["records"])} original records, {len(prev)} quarantined links retained for review.')
    return report


def main():
    parser=argparse.ArgumentParser(description='No-API screening of saved Radar 2 evidence')
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    run(args.root.resolve(),args.apply)

if __name__=='__main__':
    main()
