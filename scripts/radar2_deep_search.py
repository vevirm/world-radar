"""Fetch and extract readable source text for draft research, without assessing claims."""
from __future__ import annotations
from html.parser import HTMLParser
import re
import urllib.request

MAX_DOWNLOAD = 12_000_000
MAX_TEXT = 25_000

# Publisher protection and login pages are not research full text, even when
# their visible text is long enough to pass the character-count threshold.
ACCESS_CHALLENGES = (
    'client challenge',
    'enable javascript to proceed',
    'checking your browser before accessing',
    'verify you are human',
    'just a moment... checking your browser',
    'access denied',
    'please complete the security check',
)

def access_challenge(content):
    # Test only the start: research articles can legitimately discuss blocked
    # access in their body without themselves being a challenge page.
    beginning = str(content or '')[:1800].lower()
    return any(phrase in beginning for phrase in ACCESS_CHALLENGES)


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','nav','footer','header'): self.hidden+=1
    def handle_endtag(self,tag):
        if tag in ('script','style','nav','footer','header'): self.hidden=max(0,self.hidden-1)
    def handle_data(self,data):
        if not self.hidden and data.strip():self.parts.append(data.strip())

def extract_document(raw, content_type, url=''):
    """Return a bounded reading sample with explicit extraction status."""
    kind = (content_type or '').lower()
    is_pdf = ('pdf' in kind or raw.startswith(b'%PDF-'))
    if is_pdf:
        try:
            import fitz
            with fitz.open(stream=raw, filetype='pdf') as doc:
                pages=len(doc)
                # Read beginning and ending; conclusions often appear toward the end.
                indices=list(range(min(pages, 16)))
                if pages>16:
                    indices+=list(range(max(16,pages-8),pages))
                parts=[doc.load_page(i).get_text('text') for i in indices]
            content='\n'.join(parts)
            method='pdf_text'
        except Exception as exc:
            return {'status':'pdf_extraction_error','error':type(exc).__name__+': '+str(exc)[:160]}
    elif 'html' in kind or (not kind and b'<html' in raw[:1000].lower()):
        parser=VisibleText()
        parser.feed(raw.decode('utf-8',errors='replace'))
        content='\n'.join(parser.parts)
        method='html_text'
        pages=None
    elif 'text/plain' in kind:
        content=raw.decode('utf-8',errors='replace')
        method='plain_text'
        pages=None
    else:
        return {'status':'unsupported_content_type','type':kind[:90]}
    content=re.sub(r'[ \t]+',' ',content)
    content=re.sub(r'\n{3,}','\n\n',content).strip()
    if method == 'html_text' and access_challenge(content):
        return {'status':'access_challenge_not_read', 'method':method, 'chars':len(content)}
    if len(content)<300:
        return {'status':'insufficient_readable_text','chars':len(content),'method':method}
    # The sample is not evidence of a finding. Retain both start and end for review.
    half=MAX_TEXT//2
    sample=content if len(content)<=MAX_TEXT else content[:half]+'\n\n[...middle omitted for bounded research sample...]\n\n'+content[-half:]
    result={'status':'page_text_read','method':method,'chars':len(content),'excerpt':sample,
            'sample_truncated':len(content)>MAX_TEXT}
    if is_pdf:result['pdf_pages']=pages
    return result

def read_page(url, *, timeout=18, opener=None):
    if not url.startswith('https://'):
        return {'status':'unsupported_url'}
    req=urllib.request.Request(url,headers={'User-Agent':'WorldRadar/6.1 (research review; contact repository owner)',
        'Accept':'text/html, text/plain;q=0.9, application/pdf;q=0.8'})
    try:
        with (opener or urllib.request.urlopen)(req,timeout=timeout) as res:
            ctype=res.headers.get('Content-Type','').lower()
            final=res.geturl()
            if not final.startswith('https://'):return {'status':'unsafe_redirect'}
            raw=res.read(MAX_DOWNLOAD+1)
            if len(raw)>MAX_DOWNLOAD:
                return {'status':'document_too_large','final_url':final,'limit_bytes':MAX_DOWNLOAD}
        return {'final_url':final,**extract_document(raw,ctype,final)}
    except Exception as exc:
        return {'status':'fetch_error','error':type(exc).__name__+': '+str(exc)[:130]}

def investigate(discovery, *, max_per_claim=5, reader=read_page):
    """Preserve actual fetch audit. Reading does not itself establish an outcome."""
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
