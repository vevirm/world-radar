#!/usr/bin/env python3
"""World Radar: 15-minute repeated discovery, then 10-minute repeated verification.

Publisher identity is fixed in a trusted registry, never inferred from article text.
The original URL must stay on the registered publisher's hosts through redirects.
Feed dates may be used only when the publisher's own page has no contradictory date.
This is SOURCE verification, not fact-checking every assertion in a story.
"""
import argparse
import hashlib
import json
import os
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urljoin, urlsplit, urlunsplit, parse_qsl, urlencode

import feedparser
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
START = date(2026, 10, 1)
AGENT = 'WorldRadar/1.1 (publisher attribution verification)'
TIMEOUT = (5, 12)
SOURCES = [
    dict(name='European Commission', feed='https://ec.europa.eu/commission/presscorner/api/rss?language=en', hosts=['ec.europa.eu','commission.europa.eu'], topic='Politics & governance', kind='Institutional release'),
    dict(name='NASA JPL CNEOS', feed='https://cneos.jpl.nasa.gov/feed/news.xml', hosts=['cneos.jpl.nasa.gov'], topic='Science & technology', kind='Research news'),
    dict(name='BBC News', feed='https://feeds.bbci.co.uk/news/world/rss.xml', hosts=['www.bbc.com','bbc.com','www.bbc.co.uk','bbc.co.uk'], topic='Geopolitics & security', kind='News'),
    dict(name='BBC News', feed='https://feeds.bbci.co.uk/news/business/rss.xml', hosts=['www.bbc.com','bbc.com','www.bbc.co.uk','bbc.co.uk'], topic='Economy & business', kind='News'),
    dict(name='BBC News', feed='https://feeds.bbci.co.uk/news/science_and_environment/rss.xml', hosts=['www.bbc.com','bbc.com','www.bbc.co.uk','bbc.co.uk'], topic='Climate & science', kind='News'),
]
SIGNIFICANT = re.compile(r'\b(?:report|study|research|data|evidence|finds?|warns?|new|global|world|europe|eu|climate|energy|trade|econom|security|war|health|ai|technology|government|sanction|policy|legislation|treaty|market|migration|vaccine|planet|space|scientists?|crisis|record|reform|agreement|emission|industry|food|education|election|investment|inflation|growth)\b', re.I)
STOP = {'the','a','an','and','to','of','in','on','for','with','is','are','as','at','by','from','says','said'}

def host(url):
    try:
        p=urlparse(url)
        return p.hostname.lower().rstrip('.') if p.scheme=='https' and p.hostname and not(p.username or p.password) and p.port in (None,443) else None
    except ValueError:
        return None

def canonical_url(url):
    p=urlsplit(url)
    q=urlencode([(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not(k.lower().startswith('utm_') or k.lower() in ('at_medium','at_campaign','at_link_id','fbclid','gclid'))])
    return urlunsplit((p.scheme,p.netloc,p.path,q,''))

def get_url(url, allowed):
    session=requests.Session()
    for _ in range(5):
        if host(url) not in allowed: raise ValueError('publisher/redirect host not approved: '+url[:150])
        with session.get(url,headers={'User-Agent':AGENT,'Accept':'application/rss+xml, application/xml, text/html;q=0.9'},timeout=TIMEOUT,allow_redirects=False,stream=True) as response:
            if response.status_code in (301,302,303,307,308):
                if not response.headers.get('Location'): raise ValueError('redirect without location')
                url=urljoin(url,response.headers['Location']);continue
            response.raise_for_status()
            content=bytearray()
            for block in response.iter_content(16384):
                content.extend(block)
                if len(content)>2_000_000: raise ValueError('document too large')
            return url,bytes(content),response.headers.get('Content-Type','')
    raise ValueError('too many redirects')

def date_from_text(value):
    m=re.search(r'\b(20\d\d)-(\d\d)-(\d\d)\b',str(value or ''))
    if m:
        try:return date(*map(int,m.groups()))
        except ValueError:pass
    return None

def feed_date(entry):
    for key in ('published_parsed','updated_parsed'):
        t=entry.get(key)
        if t:
            try:return date(t.tm_year,t.tm_mon,t.tm_mday)
            except ValueError:pass
    return None

def normalize(s):return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9 ]+',' ',(s or '').casefold())).strip()
def matching(a,b):
    x=set(normalize(a).split())-STOP;y=set(normalize(b).split())-STOP
    return len(x)>=2 and len(x&y)/len(x)>=0.66 and len(x&y)/max(1,len(y))>=0.35

def metadata(raw):
    soup=BeautifulSoup(raw,'html.parser')
    titles=[]
    for selector in ('h1','meta[property="og:title"]','meta[name="twitter:title"]','title'):
        item=soup.select_one(selector)
        if item:
            txt=item.get('content') or item.get_text(' ',strip=True)
            if txt:titles.append(txt.strip())
    dates=[]
    for selector in ('meta[property="article:published_time"]','meta[name="date"]','meta[name="pubdate"]','meta[name="datePublished"]','meta[itemprop="datePublished"]','time[datetime]'):
        for element in soup.select(selector):
            d=date_from_text(element.get('content') or element.get('datetime'))
            if d:dates.append(d)
    for item in soup.select('script[type="application/ld+json"]'):
        try:
            obj=json.loads(item.string or item.get_text())
            def walk(node):
                if isinstance(node,dict):
                    if node.get('datePublished'):
                        d=date_from_text(node['datePublished'])
                        if d:dates.append(d)
                    for v in node.values():walk(v)
                elif isinstance(node,list):
                    for v in node:walk(v)
            walk(obj)
        except (ValueError,TypeError,RecursionError):pass
    return titles,dates

def collect(deadline):
    all_candidates={}; stats=[];cycle=0
    while True:
        cycle+=1
        for source in SOURCES:
            if time.monotonic()>=deadline-5: break
            try:
                feedhost=host(source['feed'])
                _,raw,_=get_url(source['feed'],{feedhost})
                parsed=feedparser.parse(raw)
                if not parsed.entries:raise ValueError('no RSS entries')
                accepted=0
                for entry in parsed.entries[:60]:
                    pub=feed_date(entry);url=canonical_url(entry.get('link',''))
                    title=BeautifulSoup(entry.get('title',''),'html.parser').get_text(' ',strip=True)
                    if not pub or pub<START or pub>datetime.now(timezone.utc).date() or not title or host(url) not in source['hosts']:continue
                    if not SIGNIFICANT.search(title):continue
                    all_candidates[url]={'url':url,'title':title,'date':pub.isoformat(),'publisher':source['name'],'allowed_hosts':source['hosts'],'type':source['kind'],'topic':source['topic'],'feed':source['feed']}
                    accepted+=1
                stats.append({'cycle':cycle,'feed':source['feed'],'candidates':accepted})
            except Exception as ex:stats.append({'cycle':cycle,'feed':source['feed'],'error':str(ex)[:180]})
        remaining=deadline-time.monotonic()
        if remaining<=0:break
        # Poll sources repeatedly for the requested 15-minute discovery period.
        time.sleep(min(90,remaining))
    result={'candidates':list(all_candidates.values()),'feed_status':stats,'discovery_utc':datetime.now(timezone.utc).isoformat(),'cycles':cycle}
    (ROOT/'candidates.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print('DISCOVERY candidates:',len(all_candidates),'cycles:',cycle,flush=True)
    for row in stats:print(row,flush=True)

def verify(c):
    url,raw,contenttype=get_url(c['url'],set(c['allowed_hosts']))
    if raw[:4]==b'%PDF' or 'pdf' in contenttype.lower():raise ValueError('PDF validation not implemented')
    if 'html' not in contenttype.lower() and not raw.lstrip().startswith((b'<!',b'<html')):raise ValueError('not HTML')
    titles,dates=metadata(raw)
    if not any(matching(c['title'],t) for t in titles):raise ValueError('original publisher page headline mismatch')
    expected=date.fromisoformat(c['date'])
    # A contradictory publisher-page date rejects. Missing page date is acceptable
    # only if the publication date was supplied by the verified publisher RSS feed.
    if dates and expected not in dates:raise ValueError('publisher-page publication date conflicts with original publisher feed')
    date_basis='publisher page + official RSS' if dates else 'official publisher RSS (page date unavailable)'
    stable=canonical_url(url)
    key='WR-'+hashlib.sha256(stable.encode()).hexdigest()[:14]
    return {'id':key,'date':expected.isoformat(),'title':c['title'],'source':c['publisher'],'authors':'','type':c['type'],'topic':c['topic'],
            'finding':'Publisher-confirmed publication: '+c['title'].rstrip('.'),
            'context':'Headline and publisher checked against the original site. The article\'s factual assertions have not been independently fact-checked.',
            'url':stable,'status':'Publisher URL and headline verified; date basis: '+date_basis,
            'verification':{'method':'registered-publisher-feed+original-domain+headline','date_basis':date_basis,'feed_url':c['feed'],'checked_utc':datetime.now(timezone.utc).isoformat()}}

def verify_until(deadline):
    raw=json.loads((ROOT/'candidates.json').read_text());db=ROOT/'findings.json';data=json.loads(db.read_text())
    data.setdefault('findings',[])
    existing={x.get('url') for x in data['findings']}|{x.get('id') for x in data['findings']}
    found=[];fails=[];pending=raw.get('candidates',[]);attempted=set();passes=0
    while time.monotonic()<deadline:
        passes+=1
        for c in pending:
            if time.monotonic()>=deadline-4:break
            url=canonical_url(c['url']);key='WR-'+hashlib.sha256(url.encode()).hexdigest()[:14]
            if url in existing or key in existing or url in attempted:continue
            attempted.add(url)
            try:
                item=verify(c)
                if item['id'] not in existing and item['url'] not in existing:
                    found.append(item);existing.update((item['id'],item['url']))
            except Exception as ex:fails.append({'title':c['title'][:130],'source':c['publisher'],'url':url,'reason':str(ex)[:200]})
        remaining=deadline-time.monotonic()
        if remaining<=0:break
        time.sleep(min(20,remaining))
    if found:
        data['findings'].extend(found)
        data['updated_at']=datetime.now(timezone.utc).date().isoformat()
        tmp=db.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n');os.replace(tmp,db)
    (ROOT/'scan-report.json').write_text(json.dumps({'checked_utc':datetime.now(timezone.utc).isoformat(),'discovery':raw.get('feed_status',[]),'verified_added':len(found),'rejected':fails,'entries':found,'verification_passes':passes},indent=2,ensure_ascii=False)+'\n')
    print('VERIFICATION added:',len(found),'rejected:',len(fails),'passes:',passes,flush=True)
    for f in fails[:35]:print('REJECT:',f['source'],f['reason'],f['url'],flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['discover','verify']);parser.add_argument('--minutes',type=float,default=15)
    args=parser.parse_args();deadline=time.monotonic()+max(0,args.minutes)*60
    if args.stage=='discover':collect(deadline)
    else:verify_until(deadline)
