#!/usr/bin/env python3
"""World Radar: conservative, source-identified RSS discovery and original-page verification.

No LLM is used to assign publisher, authors, findings, or dates. Uncertain items fail closed.
Two distinct stages, each bounded by a time BUDGET, not artificial sleeps.
"""
import argparse
import calendar
import hashlib
import json
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
START = date(2026, 10, 1)
USER_AGENT = 'WorldRadar/1.0 (public source attribution checker; GitHub Actions)'
TIMEOUT = (7, 14)
# Every host is an exact match: neither oecd.org.fake.tld nor example.oecd.org passes.
# Sources are deliberately limited to primary/original publisher domains.
SOURCES = [
    dict(name='European Commission', feed='https://ec.europa.eu/commission/presscorner/api/rss?language=en', hosts=['ec.europa.eu','commission.europa.eu'], topic='Politics & governance', kind='Institutional release'),
    dict(name='NASA Jet Propulsion Laboratory', feed='https://www.jpl.nasa.gov/feeds/news/', hosts=['www.jpl.nasa.gov','jpl.nasa.gov'], topic='Science & technology', kind='Research news'),
    dict(name='NASA JPL CNEOS', feed='https://cneos.jpl.nasa.gov/feed/news.xml', hosts=['cneos.jpl.nasa.gov'], topic='Science & technology', kind='Research news'),
    dict(name='BBC News', feed='https://feeds.bbci.co.uk/news/world/rss.xml', hosts=['www.bbc.com','bbc.com','www.bbc.co.uk','bbc.co.uk'], topic='Geopolitics & security', kind='News'),
    dict(name='BBC News', feed='https://feeds.bbci.co.uk/news/business/rss.xml', hosts=['www.bbc.com','bbc.com','www.bbc.co.uk','bbc.co.uk'], topic='Economy & business', kind='News'),
    dict(name='BBC News', feed='https://feeds.bbci.co.uk/news/science_and_environment/rss.xml', hosts=['www.bbc.com','bbc.com','www.bbc.co.uk','bbc.co.uk'], topic='Climate & science', kind='News'),
]
# Discovery RSS host must match the configured feed; verified article must match the publisher's own hosts.
SIGNIFICANT = re.compile(r'\b(?:report|study|research|data|evidence|finds?|warns?|new|global|world|europe|eu|climate|energy|trade|econom|security|war|health|healthcare|ai|technology|government|sanction|policy|legislation|treaty|market|migration|vaccine|planet|space|nasa|scientists?|crisis|record|reform|agreement|emission|industry|food|education|election|investment|inflation|growth)\b', re.I)

def host(url):
    try:
        p = urlparse(url)
        if p.scheme != 'https' or p.username or p.password or p.port not in (None,443):
            return None
        return (p.hostname or '').lower().rstrip('.')
    except ValueError:
        return None

def get_url(url, permitted):
    """Enforce exact domain allowlist BEFORE each redirect; prevent cross-domain attribution."""
    s = requests.Session()
    for _ in range(5):
        if host(url) not in permitted:
            raise ValueError('unapproved hostname / redirect: '+str(url)[:180])
        res = s.get(url, headers={'User-Agent': USER_AGENT, 'Accept':'application/rss+xml, application/xml, text/html;q=0.9'}, timeout=TIMEOUT, allow_redirects=False, stream=True)
        if res.status_code in (301,302,303,307,308):
            from urllib.parse import urljoin
            url = urljoin(url, res.headers['Location'])
            res.close()
            continue
        res.raise_for_status()
        # cap download size, don't parse enormous documents
        content = bytearray()
        for chunk in res.iter_content(16384):
            content.extend(chunk)
            if len(content)>2_000_000:
                raise ValueError('document too large')
        return url, bytes(content), res.headers.get('Content-Type','')
    raise ValueError('too many redirects')

def parse_date(entry):
    for key in ('published_parsed','updated_parsed'):
        t = entry.get(key)
        if t:
            try: return date(t.tm_year,t.tm_mon,t.tm_mday)
            except ValueError: pass
    return None

def normalize(s):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]+', ' ', (s or '').casefold())).strip()

def title_agreement(a,b):
    x=set(normalize(a).split())-{'the','a','an','and','to','of','in','on','for','with'}
    y=set(normalize(b).split())-{'the','a','an','and','to','of','in','on','for','with'}
    return bool(x) and len(x & y)/len(x) >= 0.70

def webpage_metadata(doc):
    soup = BeautifulSoup(doc, 'html.parser')
    title = ''
    for selector in ('meta[property="og:title"]','meta[name="twitter:title"]'):
        tag=soup.select_one(selector)
        if tag and tag.get('content'):
            title=tag['content'].strip();break
    if not title and soup.title: title=soup.title.get_text(' ',strip=True)
    if not title and soup.h1: title=soup.h1.get_text(' ',strip=True)
    dates=[]
    for selector in ('meta[property="article:published_time"]','meta[name="date"]','meta[name="pubdate"]','meta[name="datePublished"]','meta[itemprop="datePublished"]','time[datetime]'):
        for item in soup.select(selector):
            val=item.get('content') or item.get('datetime') or ''
            m=re.search(r'\b(20\d\d)-(\d\d)-(\d\d)\b',val)
            if m:
                try: dates.append(date(*map(int,m.groups())))
                except ValueError: pass
    return title, dates

def discovery(out, seconds, per_source=35):
    started=time.monotonic(); candidates=[]; stats=[]
    for source in SOURCES:
        if time.monotonic()-started>seconds-5: break
        try:
            feed_host=host(source['feed'])
            final, raw, _=get_url(source['feed'],{feed_host})
            parsed=feedparser.parse(raw)
            if not parsed.entries: raise ValueError('no RSS entries')
            added=0
            for entry in parsed.entries[:per_source]:
                pub=parse_date(entry)
                url=entry.get('link','')
                title=BeautifulSoup(entry.get('title',''),'html.parser').get_text(' ',strip=True)
                if not pub or pub<START or pub>datetime.now(timezone.utc).date() or not title or host(url) not in source['hosts']: continue
                if not SIGNIFICANT.search(title): continue
                candidates.append({'url':url,'title':title,'date':pub.isoformat(),'publisher':source['name'],'allowed_hosts':source['hosts'],'type':source['kind'],'topic':source['topic'],'feed':source['feed']})
                added+=1
            stats.append({'feed':source['feed'],'candidates':added})
        except Exception as exc:
            stats.append({'feed':source['feed'],'error':str(exc)[:180]})
    unique={x['url'].split('#')[0]:x for x in candidates}
    out.write_text(json.dumps({'candidates':list(unique.values()),'feed_status':stats,'discovery_utc':datetime.now(timezone.utc).isoformat()},indent=2,ensure_ascii=False)+'\n')
    print('discovery:',len(unique),'candidates;',len(stats),'feeds',flush=True)
    for s in stats: print(s,flush=True)

def verify(candidate):
    url, raw, content_type=get_url(candidate['url'],set(candidate['allowed_hosts']))
    if 'pdf' in content_type.lower() or raw[:4]==b'%PDF': raise ValueError('PDF requires dedicated validation; reject')
    if 'html' not in content_type.lower() and not raw.lstrip().startswith((b'<!',b'<html')): raise ValueError('not HTML')
    title, dates=webpage_metadata(raw)
    if not title_agreement(candidate['title'],title): raise ValueError('original page headline mismatch')
    expected=date.fromisoformat(candidate['date'])
    if not dates or expected not in dates: raise ValueError('original page date missing/different')
    # Claim is specifically the verifiable fact that THIS publisher published THIS headline.
    # No invented numeric claims or factual inferences; reader follows primary source.
    key='WR-'+hashlib.sha256(url.encode()).hexdigest()[:14]
    return {'id':key,'date':expected.isoformat(),'title':candidate['title'],
            'source':candidate['publisher'],'authors':'','type':candidate['type'],
            'topic':candidate['topic'], 'finding':'Source-verified publication: '+candidate['title'].rstrip('.'),
            'context':'Original publisher page and its publication date independently matched the feed. Read the original for evidence and interpretation.',
            'url':url,'status':'Original-source identity, title and date verified',
            'verification':{'method':'feed-to-original-page-domain-title-date','feed_url':candidate['feed'],'checked_utc':datetime.now(timezone.utc).isoformat()}}

def verification(inp, db, log, seconds, limit=80):
    raw=json.loads(inp.read_text()); data=json.loads(db.read_text())
    data.setdefault('findings',[])
    current={x.get('url') for x in data['findings']}|{x.get('id') for x in data['findings']}
    successes=[]; failures=[]; start=time.monotonic()
    for c in raw.get('candidates',[])[:limit]:
        if time.monotonic()-start>seconds-17: break
        key='WR-'+hashlib.sha256(c['url'].encode()).hexdigest()[:14]
        if c['url'] in current or key in current: continue
        try:
            item=verify(c);successes.append(item)
            current.add(item['id']);current.add(item['url'])
        except Exception as exc:
            failures.append({'title':c['title'][:130],'source':c['publisher'],'url':c['url'],'reason':str(exc)[:200]})
    # Only write after all verified candidates are processed; preserve all existing entries.
    if successes:
        data['findings'].extend(successes)
        data['updated_at']=datetime.now(timezone.utc).date().isoformat()
        temporary=db.with_suffix('.tmp')
        temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
        os.replace(temporary,db)
    log.write_text(json.dumps({'checked_utc':datetime.now(timezone.utc).isoformat(),'discovery':raw.get('feed_status',[]),'published':len(successes),'rejected':failures,'new_entries':successes},ensure_ascii=False,indent=2)+'\n')
    print('verified & added:',len(successes),'rejected:',len(failures),flush=True)
    for item in failures[:30]:print('REJECT',item['source'],item['reason'],item['url'],flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['discover','verify'])
    parser.add_argument('--minutes',type=float,default=15)
    args=parser.parse_args()
    if args.stage=='discover': discovery(ROOT/'candidates.json',max(30,args.minutes*60))
    else: verification(ROOT/'candidates.json',ROOT/'findings.json',ROOT/'scan-report.json',max(30,args.minutes*60))
