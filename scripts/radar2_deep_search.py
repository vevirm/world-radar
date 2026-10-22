"""Read selected online source pages after multi-index discovery; draft findings only."""
from __future__ import annotations
from html.parser import HTMLParser
import re
import urllib.request
from urllib.parse import urlparse

class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','nav','footer','header'): self.hidden+=1
    def handle_endtag(self,tag):
        if tag in ('script','style','nav','footer','header'): self.hidden=max(0,self.hidden-1)
    def handle_data(self,data):
        if not self.hidden and data.strip():self.parts.append(data.strip())

def read_page(url, *, timeout=18, opener=None):
    if not url.startswith('https://'):
        return {'status':'unsupported_url'}
    req=urllib.request.Request(url,headers={'User-Agent':'WorldRadar/6.0 (research review; contact repository owner)','Accept':'text/html, text/plain;q=0.9, application/pdf;q=0.5'})
    try:
        context=(opener or urllib.request.urlopen)(req,timeout=timeout)
        with context as res:
            ctype=res.headers.get('Content-Type','').lower()
            final=res.geturl()
            if not final.startswith('https://'):return {'status':'unsafe_redirect'}
            if 'pdf' in ctype:return {'status':'pdf_requires_separate_extraction','final_url':final}
            if 'html' not in ctype and 'text/plain' not in ctype:return {'status':'unsupported_content_type','type':ctype[:90]}
            raw=res.read(350_001)
            if len(raw)>350_000:return {'status':'document_too_large','final_url':final}
        decoded=raw.decode('utf-8',errors='replace')
        if 'html' in ctype:
            parser=VisibleText();parser.feed(decoded);content=' '.join(parser.parts)
        else:content=decoded
        content=re.sub(r'\s+',' ',content).strip()
        if len(content)<300:return {'status':'insufficient_readable_text','final_url':final,'chars':len(content)}
        return {'status':'page_text_read','final_url':final,'chars':len(content),'excerpt':content[:3500]}
    except Exception as exc:
        return {'status':'fetch_error','error':type(exc).__name__+': '+str(exc)[:130]}

def investigate(discovery, *, max_per_claim=5, reader=read_page):
    """Preserve actual fetch audit. Read pages, but never infer claim outcomes."""
    output=[]
    for case in discovery:
        reads=[]
        for lead in case.get('leads',[])[:max_per_claim]:
            result=reader(lead['url'])
            reads.append({'url':lead['url'],'title':lead['title'],'published':lead.get('published'), **result,
                          'connection_status':'not_assessed','observed_development_confirmed':False})
        output.append({'original_id':case['original_id'],'read_attempts':len(reads),
                       'pages_read':sum(x['status']=='page_text_read' for x in reads),
                       'source_readings':reads,'assessment':'source_text_collected_requires_human_or_substantive_review'})
    return output
