"""Defensible retrospective triage, NOT a machine verdict on 50 futures.

Original publisher links seeded from publication/catalogue pages. Indexed DOI
metadata is discovered separately and not promoted to a verified full study.
"""
from datetime import date, datetime, timezone
import json
import re
from pathlib import Path

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
    if age < 0 or age > 15: return 'outside 15-year limit'
    return 'preferred · 5–10 years' if 5 <= age <= 10 else ('near-preferred · 4–5 years' if 4 <= age < 5 else 'exceptional · outside preferred')

def inference_topic(title):
    s = title.lower()
    for key, topic in TOPICS.items():
        if key in s: return topic
    return 'European futures'

def score(item, today):
    d = date.fromisoformat(item['date'])
    years = (today-d).days / 365.2425
    if not (0 <= years <= 15): return -999
    # Explicit, auditable weighting, not an objective impact/accuracy metric.
    base = 95 if item.get('source_kind') == 'Curated publisher report' else 30
    if 5 <= years <= 10: base += 30
    elif 4 <= years < 5: base += 22
    elif years > 10: base += 9
    elif years < 3: base -= 10
    if item.get('target_year') and item['target_year'] <= today.year: base += 15
    if item.get('method', '').lower().find('forecast') >= 0 or 'projection' in item.get('method', '').lower(): base += 4
    if item.get('source_kind') == 'Indexed academic lead':
        if len((item.get('abstract') or '').split()) >= 45: base += 15
        if CORE.search(item['title']): base += 7
        if re.search(r'\b(?:foresight|scenarios|scenario analysis|forecast|future projections|to 20[2345]\d|by 20[2345]\d)\b', item['title'], re.I): base += 12
        if re.search(r'\b(?:towards|to|by|in)\s+20[2345]\d\b', item['title'], re.I): base += 12
        if BAD.search(item['title']): base -= 100
        if item.get('journal','').lower() in ('futures', 'technological forecasting and social change', 'european journal of futures research'): base += 10
    return base

def refresh(today=None):
    today = today or TODAY()
    sources = json.loads((ROOT/'priority-sources.json').read_text(encoding='utf-8'))['sources']
    verified_records = json.loads((ROOT/'findings.json').read_text(encoding='utf-8')).get('findings', [])
    verified_by_url = {f['url'].rstrip('/').lower():f for f in verified_records}
    indexed = json.loads((ROOT/'research-leads.json').read_text(encoding='utf-8')).get('leads', [])
    records = []
    for x in sources:
        item = dict(x, source_kind='Curated publisher report', verification_status='Publisher-linked candidate · original forecast not extracted', abstract='', doi='')
        records.append(item)
    for x in indexed:
        if not x.get('doi') or not x.get('date') or not CORE.search(x.get('title','')): continue
        item = {'title':x['title'], 'date':x['date'], 'publisher':x.get('publisher') or x.get('journal',''),
                'topic':inference_topic(x['title']), 'method':'Academic futures/forecast study · method unverified',
                'url':x['url'], 'doi':x['doi'], 'abstract':x.get('abstract',''),
                'journal':x.get('journal',''), 'source_kind':'Indexed academic lead',
                'verification_status':x.get('verification_status') or x.get('status') or 'Metadata only · full text not checked',
                'target_year':None}
        records.append(item)
    scored = [(score(x,today), x) for x in records]
    scored = sorted(((s,x) for s,x in scored if s >= 0), key=lambda pair: (pair[0], pair[1]["date"], pair[1]["title"]), reverse=True)
    selected=[]; seen=set(); by_topic={}; by_publisher={}
    # Blend recognised institutional reports with serious academic research;
    # avoid drowning the list with multiple same-year editions of one series.
    for _, x in scored:
        if len(selected) >= 50: break
        key = x.get('doi') or x['url'].rstrip('/').lower()
        if key in seen: continue
        topic=x.get('topic','')
        pub=x.get('publisher','')
        if by_publisher.get(pub,0) >= (8 if pub == 'European Environment Agency' else 5): continue
        if by_topic.get(topic,0) >= 12: continue
        seen.add(key); by_publisher[pub]=by_publisher.get(pub,0)+1
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
            'policy':'15-year maximum, preferentially 5–10 years old; shortlist is priority for verification, not 50 certified findings',
            'method_note':'Editorial publisher seeds plus ranked DOI/abstract leads; full-text quality and retrospective accuracy are separate checks',
            'count':len(selected),'items':selected}
    target=ROOT/'priority-50.json'
    tmp=target.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    tmp.replace(target)
    return result

if __name__ == '__main__':
    p=refresh()
    print(f'Generated {p["count"]} review candidates; {sum(x["source_kind"]=="Curated publisher report" for x in p["items"])} publisher reports.')
