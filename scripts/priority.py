"""Defensible retrospective triage, NOT a machine verdict on 50 futures.

Original publisher links seeded from publication/catalogue pages. Indexed DOI
metadata is discovered separately and not promoted to a verified full study.
"""
from datetime import date, datetime, timezone
import json
import re
from pathlib import Path
from scholarly import foresight_scope, eu_connection, HISTORICAL_START, HISTORICAL_END
from radar1_admission import decision

ROOT = Path(__file__).resolve().parents[1]
TODAY = lambda: datetime.now(timezone.utc).date()

BAD = re.compile(r'\b(?:financial futures|carbon futures price|crude oil futures|future contracts|review report|editorial|commentary|conference|literature and democracy|literary|novels?|football|law and the right|peer review report|book review|responses? to|editors comments|workshop|spot.futures|macrofina\w+ linkages|an addendum|quantile local projections|students. representations|review of|fiction)\b', re.I)
CORE = re.compile(r'\b(?:scenarios?|foresight|forecast(?:s|ing)?|projections?|future(?:s)?|outlook|pathways?|by 20[2345]\d)\b', re.I)
TOPICS = {
 'climate': 'Climate and environment', 'carbon': 'Climate and environment', 'emission': 'Climate and environment',
 'energy': 'Energy transition', 'electricity': 'Energy transition', 'demograph': 'Population and ageing',
 'population': 'Population and ageing', 'skills': 'Jobs and skills', 'labour': 'Jobs and skills',
 'health': 'Health', 'migration': 'Migration', 'security': 'Security and geopolitics',
 'geopolit': 'Security and geopolitics', 'ai': 'Technology', 'technolog': 'Technology',
 'transport': 'Transport', 'agricultur': 'Food and agriculture', 'food': 'Food and agriculture',
 'governance': 'EU governance', 'integration': 'EU governance'
}

def age_bracket(date_str, today):
    age = (today - date.fromisoformat(date_str)).days / 365.2425
    if age < 0: return 'unpublished'
    if age > 15: return 'historical · 15+ years'
    return 'preferred · 5–10 years' if 5 <= age <= 10 else ('near-preferred · 4–5 years' if 4 <= age < 5 else 'exceptional · outside preferred')

def inference_topic(title):
    s = title.lower()
    for key, topic in TOPICS.items():
        if key in s: return topic
    return 'European futures'

def report_series(item):
    # Editorial variety only: never delete a source from the archive.
    if item.get('source_kind') not in ('Curated publisher report', 'Source-screened EU report'):
        return None
    name = str(item.get('title') or '').lower()
    if 'trends and projections in europe' in name:
        return 'EEA trends and projections'
    if 'eurosystem staff macroeconomic projections' in name:
        return 'ECB macro projections'
    if 'strategic foresight report' in name:
        return 'European Commission strategic foresight reports'
    if 'ageing report:' in name:
        return 'European Commission ageing reports'
    return None


def score(item, today):
    d = date.fromisoformat(item['date'])
    years = (today-d).days / 365.2425
    if not (HISTORICAL_START <= d <= HISTORICAL_END): return -999
    # Explicit, auditable weighting, not an objective impact/accuracy metric.
    # Full-source screened institutional studies should lead editorial review,
    # not a rolling series of less distinctive annual indicator bulletins.
    base = (145 if item.get('source_kind') == 'Source-screened EU report'
            else 102 if item.get('source_kind') == 'Curated publisher report' else 30)
    eu_tier = item.get('eu_connection') or eu_connection(item)[0]
    # Institutional origin is valuable, but an institutional affiliation
    # alone does not prove the EU commissioned or issued the paper.
    base += {'eu_official': 55, 'eu_institution': 28,
             'eu_focused': 24, 'eu_related': 9, 'review': -35}.get(eu_tier, 0)
    if 5 <= years <= 10: base += 17
    elif 3 <= years < 5: base += 15
    elif years > 10: base += 9
    # 2023 is still a valid historical reference; do not punish it for recency.
    if item.get('target_year') and item['target_year'] <= today.year: base += 15
    if item.get('method', '').lower().find('forecast') >= 0 or 'projection' in item.get('method', '').lower(): base += 4
    if item.get('source_kind') == 'Indexed academic lead':
        if len((item.get('abstract') or '').split()) >= 45: base += 15
        if CORE.search(item['title']): base += 7
        if re.search(r'\b(?:foresight|scenarios|scenario analysis|forecast|future projections|to 20[2345]\d|by 20[2345]\d)\b', item['title'], re.I): base += 12
        if re.search(r'\b(?:towards|to|by|in)\s+20[2345]\d\b', item['title'], re.I): base += 12
        if BAD.search(item['title']): base -= 100
        if item.get('journal','').lower() in ('futures', 'technological forecasting and social change', 'european journal of futures research'): base += 10
        if item.get('foresight_scope') == 'future_facing': base += 16
    return base

def refresh(today=None, *, save=True):
    today = today or TODAY()
    sources = json.loads((ROOT/'priority-sources.json').read_text(encoding='utf-8'))['sources']
    verified_records = json.loads((ROOT/'findings.json').read_text(encoding='utf-8')).get('findings', [])
    verified_by_url = {f['url'].rstrip('/').lower():f for f in verified_records}
    indexed = json.loads((ROOT/'research-leads.json').read_text(encoding='utf-8')).get('leads', [])
    records = []
    for x in sources:
        item = dict(x, source_kind='Curated publisher report', verification_status='Publisher-linked candidate · original forecast not extracted', abstract='', doi='')
        item['eu_connection'], item['eu_connection_reason'] = eu_connection(item)
        records.append(item)
    # Radar 1 has fully source-screened EU publications that its fixed curated
    # bibliography missed. Promote these verified historical sources for review,
    # while leaving 2024+ findings as later context only.
    for f in verified_records:
        try:
            d = date.fromisoformat(str(f.get('date', '')))
        except ValueError:
            continue
        if not (HISTORICAL_START <= d <= HISTORICAL_END):
            continue
        if f.get('quality', {}).get('status') != 'automated research-substance screen passed':
            continue
        if f.get('source_category') != 'EU institution / agency':
            continue
        item = {
            'title': f['title'], 'date': f['date'], 'publisher': f.get('source') or 'EU institution',
            'topic': f.get('topic', 'European futures'),
            'method': 'Original EU institutional foresight · full source screened',
            'url': f['url'], 'doi': '', 'abstract': '',
            'source_kind': 'Source-screened EU report',
            'verification_status': 'Full study automated quality screen passed',
            'full_text_url': f.get('full_text_url', ''),
            'target_year': None,
        }
        item['eu_connection'], item['eu_connection_reason'] = eu_connection(item)
        records.append(item)
    for x in indexed:
        if not x.get('doi') or not x.get('date'): continue
        try:
            if not HISTORICAL_START <= date.fromisoformat(x['date']) <= HISTORICAL_END: continue
        except ValueError:
            continue
        accepted, _, _ = decision(x)
        if not accepted or x.get('radar1_selection') not in (None, 'active'):
            continue  # The same admission policy controls both archive and priorities.
        scope = 'future_facing'
        eu_tier, eu_reason = eu_connection(x)
        if eu_tier == 'review':
            continue  # Not an EU priority until its EU relevance is substantiated.
        if not CORE.search(x.get('title','')) and scope != 'future_facing':
            continue  # Vague abstract mention alone cannot lead the 50 priorities.
        item = {'title':x['title'], 'date':x['date'], 'publisher':x.get('publisher') or x.get('journal',''),
                'topic':inference_topic(x['title']), 'method':'Academic futures/forecast study · method unverified',
                'url':x['url'], 'doi':x['doi'], 'abstract':x.get('abstract',''),
                'journal':x.get('journal',''), 'source_kind':'Indexed academic lead',
                'foresight_scope':scope, 'eu_connection':eu_tier,
                'eu_connection_reason':eu_reason,
                'verification_status':x.get('verification_status') or x.get('status') or 'Metadata only · full text not checked',
                'target_year':None}
        records.append(item)
    scored = [(score(x,today), x) for x in records]
    scored = sorted(((s,x) for s,x in scored if s >= 0), key=lambda pair: (pair[0], pair[1]["date"], pair[1]["title"]), reverse=True)
    selected=[]; seen=set(); titles_seen=set(); by_topic={}; by_publisher={}; by_series={}
    def historical_identity(x):
        title = re.sub(r'[^a-z0-9]+', ' ', str(x.get('title') or '').lower()).strip()
        # A short verified EU report title and a longer curated subtitle are one work.
        strategic = re.search(r'\b(20(?:1[1-9]|2[0-3]))\s+strategic foresight report\b', title)
        return ('strategic-foresight-' + strategic.group(1)) if strategic else title
    # Blend recognised institutional reports with serious academic research;
    # avoid drowning the list with multiple same-year editions of one series.
    for _, x in scored:
        if len(selected) >= 50: break
        key = x.get('doi') or x['url'].rstrip('/').lower()
        title_key=historical_identity(x)
        if key in seen or title_key in titles_seen: continue
        topic=x.get('topic','')
        pub=x.get('publisher','')
        if by_publisher.get(pub,0) >= (6 if pub == 'European Environment Agency' else 7 if 'European Commission' in pub else 5): continue
        if by_topic.get(topic,0) >= 12: continue
        series = report_series(x)
        series_cap = {'ECB macro projections': 1, 'EEA trends and projections': 2,
                      'European Commission ageing reports': 1,
                      'European Commission strategic foresight reports': 4}.get(series, 2)
        if series and by_series.get(series, 0) >= series_cap: continue
        if series: by_series[series] = by_series.get(series, 0) + 1
        seen.add(key); titles_seen.add(title_key); by_publisher[pub]=by_publisher.get(pub,0)+1
        by_topic[topic]=by_topic.get(topic,0)+1
        x=dict(x)
        x['ranking_score'] = score(x, today)
        x['age_band'] = age_bracket(x['date'],today)
        published = verified_by_url.get(x['url'].rstrip('/').lower())
        if published:
            x['verification_status'] = 'Full study automated quality screen passed'
            previous_verdict = published.get('comparison',{}).get('verdict','Not yet assessed')
            x['accuracy_verdict'] = previous_verdict if previous_verdict != 'Not yet assessed' else 'Not evaluated'
            x['full_text_url'] = published.get('full_text_url', '')
        else:
            x['accuracy_verdict'] = 'Not evaluated'
        x['outcome_evidence_url'] = ''
        x['review_priority'] = len(selected)+1
        selected.append(x)
    result={'schema_version':1,'generated_date':today.isoformat(), 'target':50,
            'policy':'Original publications from 2011 through 2023 inclusive; newer publications belong to the Radar 2 evidence period. Shortlist is research triage, not 50 certified findings',
            'method_note':'2011–2023 EU institutional and European future-oriented originals; 2024+ only later context. Source-screened publisher reports prioritized and annual series diversified. Research priority is not forecast accuracy.',
            'count':len(selected),'items':selected}
    if save:
        target=ROOT/'priority-50.json'
        tmp=target.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        tmp.replace(target)
    return result

if __name__ == '__main__':
    p=refresh()
    print(f'Generated {p["count"]} review candidates; {sum(x["source_kind"]=="Curated publisher report" for x in p["items"])} publisher reports.')
