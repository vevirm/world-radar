"""Bounded multi-index discovery for later work on historical future claims.

Returns research leads, never confirmed real-world developments.
"""
from __future__ import annotations
import datetime as dt
import json
import re
import urllib.parse
import urllib.request

STOP = set('the and that with from into across europe european union future futures scenarios scenario forecasts forecast estimates estimate results report study studies about between under after before could would should will might their there these those potential impact impacts possible projected expected research development policy policies towards changes change assessment model models analysis during over using based'.split())
WORD = re.compile(r'[a-z][a-z-]{3,}')

def terms(value):
    return list(dict.fromkeys(w for w in WORD.findall(str(value or '').lower()) if w not in STOP))

# Generic prose words can otherwise crowd out the actual research subject.
QUERY_FILLER = set("comments long-term outlook significant findings here some many most major various other factors results conclusions introduction summary paper article authors report reports show shows showing due depending which would could should therefore avoided increase increases decreased decrease rise rises reflecting growing projected projection projections scenario scenarios".split())


def query_for(claim):
    """Search subsequent evidence using the historical claim, not a generic title.

    The handed-over historical_focus is the original future proposition. The
    title is only a fallback when the focus contains too little information.
    No claim about relevance or an observed outcome is implied by this query.
    """
    focus = [w for w in terms(claim.get('historical_focus') or claim.get('original_passage'))
             if w not in QUERY_FILLER]
    title = [w for w in terms(claim.get('title')) if w not in QUERY_FILLER]
    chosen = list(dict.fromkeys(focus))[:5]
    if len(chosen) < 3:
        chosen = list(dict.fromkeys(chosen + title))[:5]
    # A geographic anchor matters when the original proposition is about Europe.
    # Don't add Europe to claims about other regions or global developments.
    combined = (str(claim.get('title') or '') + ' ' + str(claim.get('historical_focus') or '')).lower()
    if any(w in combined for w in ('europe', 'european', ' eu ', 'european union')) and not any(
        w in chosen for w in ('europe', 'european')):
        chosen = chosen[:4] + ['europe']
    return ' '.join(chosen)

def fetch_json(base, params, timeout=15):
    url = base + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url,headers={'User-Agent':'WorldRadar-Radar2/5.0 (research lead discovery)', 'Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as f:
        data = f.read(2_000_000)
    return json.loads(data)

def source_queries(query, since_year, api_key=''):
    oa = {'search':query,'filter':f'from_publication_date:{since_year}-01-01','per_page':12,
          'select':'id,doi,title,publication_date,abstract_inverted_index,primary_location'}
    if api_key:oa['api_key']=api_key
    return [
      ('openalex','https://api.openalex.org/works',oa),
      ('crossref','https://api.crossref.org/works',{'query.bibliographic':query,'filter':f'from-pub-date:{since_year}-01-01','rows':12,'select':'DOI,title,published,URL,abstract'}),
      ('europe_pmc','https://www.ebi.ac.uk/europepmc/webservices/rest/search',{'query':f'({query}) AND FIRST_PDATE:[{since_year}-01-01 TO *]','format':'json','pageSize':12})]

def extract(source, payload):
    if source=='openalex':
        from openalex_comparison import abstract_from_index
        for w in payload.get('results',[]):
            yield {'title':w.get('title'),'date':w.get('publication_date'),'url':w.get('doi') or w.get('id'), 'excerpt':abstract_from_index(w.get('abstract_inverted_index'))}
    elif source=='crossref':
        for w in payload.get('message',{}).get('items',[]):
            parts=(w.get('published',{}) or {}).get('date-parts', [[]])[0]
            date='-'.join(str(x).zfill(2) if i else str(x) for i,x in enumerate(parts))
            yield {'title':' '.join(w.get('title',[])), 'date':date,'url':w.get('URL'),'excerpt':re.sub('<[^>]*>',' ',w.get('abstract') or '')}
    else:
        for w in payload.get('resultList',{}).get('result',[]):
            yield {'title':w.get('title'),'date':w.get('firstPublicationDate'),'url':f"https://europepmc.org/article/{w.get('source','MED')}/{w.get('id','')}", 'excerpt':w.get('authorString') or ''}

def later(original_date, found_date):
    if not str(found_date)[:4].isdigit() or not str(original_date)[:4].isdigit():return False
    if int(str(found_date)[:4]) > dt.date.today().year:return False
    if int(str(found_date)[:4]) > int(str(original_date)[:4]):return True
    # In same year require full dates to establish sequence.
    if len(str(found_date))<10 or len(str(original_date))<10:return False
    try:return dt.date.fromisoformat(str(found_date)[:10]) > dt.date.fromisoformat(str(original_date)[:10])
    except ValueError:return False

def discover(claim, *, fetcher=fetch_json, api_key=''):
    q=query_for(claim)
    report={'original_id':claim['id'],'original_title':claim.get('title'), 'query':q,
            'status':'unverified_discovery_leads', 'sources_checked':[], 'leads':[], 'errors':[], 'verified_outcomes':0}
    if len(q.split())<2:
        report['status']='insufficient_specific_terms'
        return report
    seen=set(); anchor=set(terms(claim.get('title')))
    original=claim.get('original_publication','')
    year=int(str(original)[:4])+1
    for source,url,params in source_queries(q,year,api_key):
        try:
            payload=fetcher(url,params)
            report['sources_checked'].append(source)
            for item in extract(source,payload):
                if not later(original,item.get('date')):continue
                address=str(item.get('url') or '')
                if not address.startswith('https://') or address in seen:continue
                overlap=anchor.intersection(terms(item.get('title')))
                if len(overlap)<2:continue
                seen.add(address)
                report['leads'].append({'index':source,'title':item['title'],'published':item.get('date'),
                    'url':address,'abstract_or_excerpt':(item.get('excerpt') or '')[:800],
                    'matching_subject_terms':sorted(overlap),'connection_status':'topic_match_unreviewed',
                    'observed_development_confirmed':False})
        except Exception as exc:
            report['errors'].append({'index':source,'error':type(exc).__name__ + ': ' + str(exc)[:160]})
    report['leads']=report['leads'][:24]
    if report['errors']:report['status']='partial_discovery_errors'
    elif not report['leads']:report['status']='no_leads_in_bounded_search'
    return report
