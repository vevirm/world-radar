"""Question-first discovery for Scanner 2.

Search different evidence paths and rank by continuity of the QUESTION, not
just matching title words. All automatically extracted findings are research
leads, never independently verified real-world outcomes.

No paid language model is needed. OpenAlex API calls may consume its account
credits; the pilot has hard request/time limits.
"""
from __future__ import annotations

import datetime as dt
from collections import Counter
from functools import lru_cache
from pathlib import Path
import http.client
import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

try:
    from .openalex_comparison import abstract_from_index, clean, year
    from .question_evidence import candidate, issue_terms, geographic_status
except ImportError:
    from openalex_comparison import abstract_from_index, clean, year
    from question_evidence import candidate, issue_terms, geographic_status

# Named concept families help connect changing vocabulary, but don't treat
# every paper about 'education' or 'policy' as addressing the same question.
FAMILIES = {
    'internationalization': r'internationali[sz]ation|internationali[sz]ing|cross.border (?:education|collaboration)|global engagement|international cooperation',
    'higher_education': r'higher education|universit(?:y|ies)|tertiary education|higher.education institutions|higher.education system',
    'mobility': r'student mobility|academic mobility|erasmus|exchange students|cross.border mobility',
    'pesticide': r'pesticid(?:e|es)|herbicid(?:e|es)|insecticid(?:e|es)|agrochemicals?',
    'soil_organism': r'soil organisms?|soil biota|soil biodiversity|earthworms?|soil invertebrates?',
    'exposure': r'chemical exposure|exposure assessment|exposure scenarios?|contamination',
    'energy_security': r'energy security|security of supply|energy supply resilience',
    'renewable_energy': r'renewable energy|renewables|wind energy|solar energy|clean energy',
    'carbon_emission': r'carbon emissions?|greenhouse gas emissions?|co2 emissions?|decarboni[sz]ation',
    'climate_change': r'climate change|global warming|changing climate',
    # Keep the actual research question in view: the reliability/uncertainty
    # of climate projections, rather than anything mentioning climate.
    'climate_projection_quality': r'climate (?:change )?projections?|climate model bias(?:es)?|climate model uncertainty|uncertainty (?:in|of|about) (?:large.scale )?climate|climate (?:change )?uncertainty|climate model errors?|climate model evaluation|inter.model spread',
    'flood_risk': r'flood(?:ing)? risk|flood warning|flood hazard|flood resilience',
    'employment': r'labou?r markets?|employment|unemployment|job insecurity',
    'migration': r'migration|immigration|emigration|migrants?',
    'population_ageing': r'ageing population|aging population|older adults?|elderly population|demographic ageing',
    'forest': r'forest(?:s|ry)?|woodland|silviculture|tree species',
    'biodiversity': r'biodiversity|ecosystems?|habitat diversity|species richness',
    'cybersecurity': r'cybersecurity|cyber threats?|information security|digital security',
    'hydrogen': r'hydrogen|h2 production|green hydrogen|electroly[sz]ers?|power.to.gas',
    'agriculture': r'agricultur(?:e|al)|agronom(?:y|ic)|cropland|crop production|farming|agroforestry',
    'long_term_care': r'long.term care|nursing homes?|residential care|elderly care|care needs',
    'bank_loans': r'bank loans?|loan defaults?|credit default|lending risk',
    'mosquito': r'mosquit(?:o|oes)|aedes albopictus|tiger mosquito|vector.borne mosquito',
    'ozone': r'ozone|o3 pollut(?:ant|ion)',
    'lyme': r'lyme|borreliosis|borrelia',
    'mortality': r'mortality|deaths?|fatalit(?:y|ies)',
    'mass_casualty': r'mass casualt(?:y|ies)|mass fatalit(?:y|ies)|mass injury events?',
    'energy_dependence': r'energy dependence|energy import dependence|energy imports?',
    'natural_gas': r'natural gas|gas supply|lng imports?|gas pipeline',
    'oil_supply': r'oil supplies|oil supply|crude oil|petroleum supplies|oil supply risk',
    'digital_governance': r'digital governance|e.government|digital public services|digital administration',
    'innovation_policy': r'innovation polic(?:y|ies)|r&d policy|research and innovation policy|innovation strategy',
    'food_security': r'food security|food systems?|food supply',
    'public_health': r'public health|health services?|health outcomes?|health systems?',
}
COMPILED = {k: re.compile(r'\b(?:'+p+r')\b', re.I) for k,p in FAMILIES.items()}
STOP = set('''study studies modelling modeling model models future futures foresight perspective perspectives
scenarios scenario forecasting forecast prediction projected projection projections
analysis assessing assessment european europe europeans international policy policies
methods methodological empirical research results qualitative quantitative approach approaches
review framework challenges challenge regional broad potential towards dynamics'''.split())
CONTEXT = set('''education government planning regulation scenario research institutional technology
future modelling model forecasting case cases adoption evidence evaluation design simulation
local global community society social economic sustainability machine learning algorithm algorithms selected countries country solution insights uncertainty method methods impact impacts study studies results role structural'''.split())
REGION = re.compile(r'\b(europe|european|eu|europ(?:e)?an union|member states|european higher education area|ehea)\b',re.I)
EU_STATE = re.compile(r'\b(finnish|german|swedish|dutch|danish|polish|french|italian|spanish|portuguese|norwegian|british|greek|irish|austria|belgium|bulgaria|croatia|cyprus|czechia|czech republic|denmark|estonia|finland|france|germany|greece|hungary|ireland|italy|latvia|lithuania|luxembourg|malta|netherlands|poland|portugal|romania|slovakia|slovenia|spain|sweden|norway|iceland|switzerland|uk|united kingdom|britain)\b', re.I)
# Geography in the *title* is a focus marker. Mentioning Europe in an
# unrelated study's references or introductory abstract is not enough.
OTHER_STATE = re.compile(r'\b(russia|russian|china|chinese|vietnam|vietnamese|india|indian|pakistan|pakistani|brazil|brazilian|mexico|mexican|egypt|egyptian|morocco|moroccan|thailand|thai|indonesia|indonesian|japan|japanese|south korea|korean|australia|australian|nigeria|nigerian|south africa|south african|iran|iranian|turkey|turkish|saudi arabia|united states|usa|american|canada|canadian)\b', re.I)
# Broader regional titles such as Latin America or California were slipping
# past country-only exclusions. These are contextual comparisons, not direct
# follow-up evidence about the European case.
OTHER_REGION = re.compile(r'\b(latin america|latin american|north america|south america|central america|south asia|south asian|east asia|southeast asia|south.east asia|sub.saharan africa|middle east|california|texas|brazilian amazon|iranian catchment)\b', re.I)


def _words(text):
    return {w for w in re.findall(r'[a-z][a-z0-9-]{3,}',clean(text).casefold())
            if w not in STOP and w not in CONTEXT and not w.isdigit()}


def _concepts(text):
    text = clean(text)
    result={k for k,p in COMPILED.items() if p.search(text)}
    # In university studies, mobility is one established form of
    # internationalization, even if the word itself never appears.
    if 'higher_education' in result and 'mobility' in result:
        result.add('internationalization')
    return result


@lru_cache(maxsize=1)
def _corpus_frequency():
    """Rare original-topic terms get more attention than 'Europe' or 'future'."""
    path=Path(__file__).resolve().parents[1]/'research-leads.json'
    try:
        leads=json.loads(path.read_text(encoding='utf-8')).get('leads',[])
    except (OSError, ValueError):
        return Counter()
    count=Counter()
    for x in leads:
        count.update(_words(x.get('title') or ''))
    return count


def distinctive_words(title):
    """Prefer subject-specific nouns without assuming a fixed discipline."""
    words=_words(title)
    discard={'europe','european','union','global','regional','national','north','south',
             'policy','policies','development','developments','analysis','change',
             'climate','energy','power','general','future','futures','impact','impacts',
             'scenarios','scenarios','economic','economy','approach','approaches',
             'systems','system','effects','effect','modelling','modeling','market',
             'markets','international','strategic','comparison','comparative',
             'data','using','between','over','years','long-term','framework'}
    words=words-discard
    c=_corpus_frequency()
    return sorted(words,key=lambda w:(c[w],-len(w),w))[:3]


def profile(claim):
    title = clean(claim.get('title'))
    description = clean(claim.get('expected') or claim.get('abstract') or '')
    # The original title defines what requires continuity; the abstract
    # clarifies meaning, but a distant abstract aside cannot take over.
    title_concepts = _concepts(title)
    extra_concepts = _concepts(description) - title_concepts
    title_words = _words(title)
    # Search terms preserve phrases (e.g. "higher education"), not arbitrary
    # partial titles like "future internationalization".
    anchors = list(dict.fromkeys(re.findall(r'[a-z][a-z0-9-]{3,}',title.casefold())))
    anchors = [a for a in anchors if a not in STOP and a not in CONTEXT]
    return {'title':title, 'description':description, 'distinctive':distinctive_words(title), 'title_concepts':title_concepts,
            'extra_concepts':extra_concepts, 'title_words':title_words,
            'anchors':anchors, 'eu':bool(REGION.search(title))}


def query_plan(claim):
    """Different discovery routes; no reliance on near-identical titles."""
    p=profile(claim)
    title=p['title']
    description=p['description']
    # Text from the real original abstract improves semantic matching; it is
    # NOT generated text and we do not invent an original forecast.
    semantic = ('Research question: '+title+'. '+description)[:1950]
    concepts=p['title_concepts']
    # Generic, non-tailored cases still get meaningful two- or three-term query.
    if {'internationalization','higher_education'} <= concepts:
        issue='internationalization higher education'
        empirical='European university internationalization mobility strategies'
    elif {'pesticide','soil_organism'} <= concepts:
        issue='pesticides soil organisms'
        empirical='pesticide exposure soil biodiversity monitoring'
    else:
        anchors=p['anchors']
        # Avoid giant AND conjunctions and rotate in the historical context.
        issue=' '.join(anchors[:3]) if anchors else ' '.join(title.split()[:3])
        empirical=' '.join(anchors[:2] + ['monitoring']) if anchors else issue
    return [('semantic',semantic),('issue',issue),('developments',empirical)]


def geography(claim, title, abstract=''):
    p=profile(claim)
    title=clean(title)
    abstract=clean(abstract)
    old_north = bool(re.search(r'\bnorth america\b',p['title'],re.I))
    if old_north and not re.search(r'\bnorth america\b',title+' '+abstract,re.I):
        return 'outside_scope'
    if p['eu']:
        # Explicitly different territory is NOT an update of Europe unless
        # Europe is named in the title as a direct comparison.
        if (OTHER_STATE.search(title) or OTHER_REGION.search(title) or re.search(r'\bUS\b',title)) and not REGION.search(title):
            return 'outside_scope'
        if REGION.search(title) or EU_STATE.search(title):
            return 'european_focus'
        if REGION.search(abstract) or EU_STATE.search(abstract):
            return 'european_context'
        return 'geography_unspecified'
    # Reuse generic geographic checks for other origination scopes.
    value=geographic_status(p['title'], title, abstract)
    return 'outside_scope' if value=='other_region' else value


def evaluate(claim, work, *, discovery='semantic'):
    """A substantive research connection, not a correctness assessment."""
    original=profile(claim)
    title=clean(work.get('title'))
    abstract=abstract_from_index(work.get('abstract_inverted_index')) or clean(work.get('abstract'))
    scope=geography(claim,title,abstract)
    if scope == 'outside_scope':
        return None
    value=candidate(claim, work, discovery=discovery)
    # The original lexical candidate function may reject papers whose concept
    # vocabulary evolved. Recover these ONLY with multiple subject anchors.
    if value is None:
        if not title or work.get('is_retracted') or work.get('is_withdrawn'):
            return None
        if not (work.get('doi') or work.get('url') or work.get('id')):
            return None
        ts=clean(work.get('title'))
        if re.search(r'^\s*\[?(withdrawn|retracted|retraction)',ts,re.I):
            return None
        try:
            from .question_evidence import is_later
        except ImportError:
            from question_evidence import is_later
        if not is_later(claim,work):
            return None
        url=clean(work.get('doi') or work.get('url') or work.get('id'))
        if not url.startswith('https://') or url.rstrip('/').lower()==clean(claim.get('source_url')).rstrip('/').lower():
            return None
        if _words(title)==original['title_words']:
            return None
        value={'title':title[:250], 'url':url, 'year':year(work.get('publication_date') or work.get('publication_year')),
               'date':clean(work.get('publication_date')), 'finding_from_abstract':'',
               'evidence_kind':'ongoing_research','relationship':'same_issue_published_followup_not_outcome_verified',
               'geography':scope,'shared_issue_terms':[], 'source':'openalex_publication_metadata',
               'interpretation':'Later research discusses the original issue', 'discovery':discovery}
    # Critical concrete domains must remain the same across publications.
    # 'European energy policy' is not a follow-up about hydrogen unless it
    # actually discusses hydrogen; 'demography' isn't automatically eldercare.
    CRITICAL={'hydrogen','agriculture','long_term_care','pesticide',
              'mosquito','ozone','lyme','mortality','mass_casualty',
              'energy_dependence','natural_gas','oil_supply','digital_governance',
              'population_ageing','migration',
              'soil_organism','bank_loans','innovation_policy','internationalization',
              'higher_education','flood_risk'}
    required=original['title_concepts'] & CRITICAL
    derived=_concepts(title+' '+abstract)
    if required and not required <= derived:
        return None
    # In fields without two recognised domain concept families, an actual
    # distinctive term must survive. Abstract-only generic mentions don't
    # establish continuity (mosquito != rapeseed; loans != weather).
    anchors=original['distinctive']
    if anchors and len(original['title_concepts'])<2:
        matched=set(anchors) & _words(title+' '+abstract)
        matched_title=set(anchors) & _words(title)
        # A single mention in the ABSTRACT is often just background or an
        # irrelevant shared word (e.g. 'active' in an energy policy abstract).
        if len(matched)<2 and not matched_title:
            return None
    # For titles without a recognisable subject family, require more than
    # incidental geography/common research vocabulary.
    uninformative={'union','selected','countries','country','strategic','role',
                   'impacts','impact','long-term','regional','global','european',
                   'system','systems','development','energy','climate','change',
                   'policy','future','economic','economic'}
    diagnostic=original['title_words']-uninformative
    topic_words=(_words(title+' '+abstract) & diagnostic)
    # Shared *specific* subject concepts can explain vocabulary changes (e.g.
    # climate projection uncertainty -> climate model bias) even with no exact
    # overlapping nouns. Keep the lexical gate for generic subjects.
    if not required and diagnostic and not topic_words and len(original['title_concepts'] & derived)<2:
        return None
    # Multi-aspect continuity can be apparent in the abstract, not the title.
    title_c=_concepts(title)
    all_c=_concepts(title+' '+abstract)
    shared_title=original['title_concepts'] & title_c
    shared_all=original['title_concepts'] & all_c
    words_title=original['title_words'] & _words(title)
    words_all=original['title_words'] & _words(title+' '+abstract)
    # A study of climate-projection uncertainty is not updated by just any
    # climate analysis, seasonal rainfall forecast, or hydrology model.
    if 'climate_projection_quality' in original['title_concepts'] and 'climate_projection_quality' not in all_c:
        return None
    # Generic method words cannot rescue a different subject.
    strong_subject=(len(shared_all)>=2 and bool(shared_title))
    lexical_subject=(len(words_title)>=2 and len(words_all)>=3)
    # If there are no concept families, distinctive multiword continuity
    # remains acceptable. A cited paper requires subject continuity too.
    if not (strong_subject or lexical_subject):
        return None
    if len(shared_all)==1 and len(words_all)<3:
        return None
    # Require at least a domain signal in the TITLE, not just fleeting terms
    # in the abstract, except explicit direct citation with 2 concepts.
    cited=discovery=='citation'
    if not shared_title and len(words_title)<2 and not (cited and len(shared_all)>=2):
        return None
    if value.get('evidence_kind') not in (
            'measured_or_reported_change','implementation_or_evaluation',
            'newer_scenario_or_model','ongoing_research'):
        value['evidence_kind']='ongoing_research'
    # Scenario models and modal recommendations are not historical outcomes.
    if value.get('evidence_kind')=='implementation_or_evaluation' and re.search(
            r'\b(can|could|may|might|would|should|unless|to be)\b.{0,100}\b(implemented|adopted|deployed)\b',
            abstract, re.I):
        value['evidence_kind']='ongoing_research'
        value['finding_from_abstract']=''
    # A model's projected estimate is not a recorded historical change.
    if (value.get('evidence_kind') in ('measured_or_reported_change','implementation_or_evaluation')
            and re.search(r'\b(scenarios?|projections?|simulation|modelled|modeled|modelling|modeling)\b',title,re.I)
            and not re.search(r'\b(observed|monitored|surveyed|measured|historical records|actual rollout|was implemented)\b',
                              clean(value.get('finding_from_abstract')), re.I)):
        value['evidence_kind']='newer_scenario_or_model'
    if (value.get('evidence_kind')=='ongoing_research' and re.search(
            r'\b(projects?|projected|projecting|projections?|future scenarios?|scenarios?|simulations?|forecasts?)\b',
            title+' '+abstract,re.I)):
        value['evidence_kind']='newer_scenario_or_model'
    # Avoid inflating a paper into a historical observation when candidate()
    # could not identify an applicable findings sentence.
    value.update({'geography':scope,'discovery':discovery})
    quality = (3*len(shared_title)+2*len(shared_all)+
               min(3,len(words_title)) + min(2,len(words_all)) +
               (3 if scope=='european_focus' else 1 if scope=='european_context' else 0)+
               (2 if cited else 0) + (2 if value.get('finding_from_abstract') else 0))
    quality = min(30,quality)
    value['question_fit_score']=quality
    value['question_fit_basis']=(f'{len(shared_all)} shared subject concepts, '
                                 f'{len(words_title)} substantive title terms; scope {scope}')
    return value


def broader_context(claim,work,*,discovery='semantic'):
    """Related institutional/field research, NOT evidence of this exact question.

    Only semantic/citation retrievals can propose these and only with clear
    geographic and domain continuity. It never enters direct evidence.
    """
    if discovery not in ('semantic','citation'):
        return None
    p=profile(claim)
    if len(p['title_concepts'])<2:
        return None
    title=clean(work.get('title'))
    abstract=abstract_from_index(work.get('abstract_inverted_index')) or clean(work.get('abstract'))
    scope=geography(claim,title,abstract)
    if scope not in ('european_focus','european_context','matching_region'):
        return None
    if len(abstract)<120:
        return None
    if not p['title_concepts'] & _concepts(title):
        return None
    if work.get('is_retracted') or work.get('is_withdrawn'):
        return None
    try:
        from .question_evidence import is_later
    except ImportError:
        from question_evidence import is_later
    if not is_later(claim,work):
        return None
    url=clean(work.get('doi') or work.get('url') or work.get('id'))
    if not url.startswith('https://') or url==clean(claim.get('source_url')):
        return None
    return {'title':title[:250], 'url':url,
            'year':year(work.get('publication_date') or work.get('publication_year')),
            'source':'semantic_broader_context', 'topic_relation':'broader_context_not_direct_followup',
            'finding_from_abstract':'',
            'geography':scope, 'caveat':'Broader field context; cannot infer an answer to the original question from available metadata.'}


@dataclass
class SearchBudget:
    max_requests: int = 5
    deadline: float | None = None
    calls: int = 0
    successful_calls: int = 0
    returned_works: int = 0
    errors: list = field(default_factory=list)

    def available(self):
        return self.calls < self.max_requests and (self.deadline is None or time.monotonic() < self.deadline - 5)


def _request(params,budget,timeout=18):
    """Query OpenAlex and keep diagnostics: errors must never look like 0 matches.

    Never print URLs, since they can contain the user's API key.
    """
    if not budget.available():
        return []
    budget.calls += 1
    key=os.getenv('OPENALEX_API_KEY','').strip()
    email=os.getenv('MAILTO','').strip() or os.getenv('OPENALEX_EMAIL','').strip()
    params=dict(params)   # don't modify the caller's query object
    if key: params['api_key']=key
    if '@' in email: params['mailto']=email
    url='https://api.openalex.org/works?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={'User-Agent':f'WorldRadar-QuestionFirst/5.1 ({email})',
                                           'Accept':'application/json'})
    route = 'semantic' if 'search.semantic' in params else ('keyword' if 'search' in params else 'filter')
    try:
        with urllib.request.urlopen(req,timeout=timeout) as resp:
            payload=json.load(resp)
        if not isinstance(payload,dict) or not isinstance(payload.get('results'),list):
            raise ValueError('Unexpected OpenAlex results format')
        works=payload['results']
        budget.successful_calls += 1
        budget.returned_works += len(works)
        print(f'OpenAlex {route}: HTTP 200, {len(works)} works returned',flush=True)
        return works
    except urllib.error.HTTPError as exc:
        # Don't turn invalid select fields, bad keys, or credits into
        # misleading "no evidence" findings. Save a short, key-safe reason.
        detail=''
        try:
            raw=exc.read(800).decode('utf-8','replace')
            parsed=json.loads(raw)
            detail=str(parsed.get('message') or parsed.get('error') or '')[:180]
        except (ValueError,UnicodeError,AttributeError):
            pass
        diagnostic={'route':route,'status':f'HTTP {exc.code}','reason':detail}
        budget.errors.append(diagnostic)
        print(f'OpenAlex {route} ERROR: HTTP {exc.code} {detail}',flush=True)
        if exc.code in (400,401,403,429):
            return []
        raise
    except (urllib.error.URLError,TimeoutError,socket.timeout,ConnectionError,
            http.client.IncompleteRead,ValueError) as exc:
        diagnostic={'route':route,'status':type(exc).__name__,'reason':str(exc)[:160]}
        budget.errors.append(diagnostic)
        print(f'OpenAlex {route} ERROR: {diagnostic["status"]} {diagnostic["reason"]}',flush=True)
        return []


def _dated_filters(claim):
    y=year(claim.get('original_publication'))
    return f'from_publication_date:{y}-01-01' if y else ''


def discover(claim,*,budget=None):
    """Discover and rank evidence over multiple independent paths.

    Default: 4-5 calls maximum (semantic, compact lexical, direction, DOI,
    direct citations). No publishing or old-data deletions occur here.
    """
    budget=budget or SearchBudget()
    context={}
    seen={}
    routes=[]
    # 'is_withdrawn' is not a selectable OpenAlex Works field. Selecting it
    # makes the entire request fail with HTTP 400 (not zero search results).
    select='id,doi,title,publication_year,publication_date,abstract_inverted_index,is_retracted,referenced_works'
    for name,query in query_plan(claim):
        if not budget.available(): break
        params={'per_page':25,'select':select}
        params['search.semantic' if name=='semantic' else 'search']=query
        filt=_dated_filters(claim)
        # OpenAlex semantic search rejects from_publication_date (HTTP 400).
        # Date relevance is enforced by evaluate()/is_later() after retrieval.
        if filt and name != 'semantic': params['filter']=filt
        works=_request(params,budget)
        routes.append({'route':name,'results':len(works)})
        for w in works:
            result=evaluate(claim,w,discovery=name)
            if result:
                k=result['url'].casefold().rstrip('/')
                if k not in seen or result['question_fit_score']>seen[k]['question_fit_score']:
                    seen[k]=result
            else:
                broad=broader_context(claim,w,discovery=name)
                if broad:
                    context[broad['url'].casefold().rstrip('/')]=broad
    # Follow references to the ORIGINAL work, not just papers mentioning its
    # keywords. Citations are retrieval hints, not proof of substantive match.
    if budget.available():
        doi=clean(claim.get('source_url'))
        if doi.startswith('https://doi.org/'):
            found=_request({'filter':'doi:'+doi, 'per_page':1, 'select':'id,title'},budget)
            if found and budget.available():
                work_id=clean(found[0].get('id')).split('/')[-1]
                if re.fullmatch(r'W\d+',work_id):
                    cited=_request({'filter':f'cites:{work_id},'+_dated_filters(claim),
                                    'per_page':25,'select':select},budget)
                    routes.append({'route':'citations','results':len(cited)})
                    for w in cited:
                        result=evaluate(claim,w,discovery='citation')
                        if result:
                            k=result['url'].casefold().rstrip('/')
                            if k not in seen or result['question_fit_score']>seen[k]['question_fit_score']:
                                seen[k]=result
                        else:
                            broad=broader_context(claim,w,discovery='citation')
                            if broad:
                                context[broad['url'].casefold().rstrip('/')]=broad
    # Distinguish relation to original question from speculation that it came true.
    evidence_pref={'implementation_or_evaluation':2,'measured_or_reported_change':2,
                   'ongoing_research':1,'newer_scenario_or_model':0}
    results=sorted(seen.values(),key=lambda x:(x['question_fit_score'],
                   evidence_pref.get(x.get('evidence_kind'),0),x.get('year') or 0),reverse=True)
    # Never count a good direct link again as vague context.
    context_results=[x for k,x in context.items() if k not in seen]
    context_results=sorted(context_results,key=lambda x:x.get('year') or 0,reverse=True)[:3]
    return {'results':results[:8], 'context':context_results, 'routes':routes, 'requests':budget.calls,
            'successful_requests':budget.successful_calls, 'raw_works_returned':budget.returned_works,
            'question':profile(claim)['title'], 'query_plan':query_plan(claim)}


def rescreen_existing(claim,items):
    """Do not re-promote old bad matches; keep excluded links recoverable."""
    kept=[]; excluded=[]
    for item in items or []:
        if not isinstance(item,dict) or not item.get('url'):
            continue
        work={'title':item.get('title'),'abstract':item.get('finding_from_abstract'),
              'doi':item.get('url'), 'publication_year':item.get('year'),
              'publication_date':item.get('date') or str(item.get('year') or ''),
              'is_retracted':False}
        found=evaluate(claim,work,discovery=item.get('discovery','saved_recheck'))
        if found:
            # Retain the richer saved abstract; new screen supplied confidence.
            kept.append({**item,'question_fit_score':found['question_fit_score'],
                         'question_fit_basis':found['question_fit_basis'],
                         'geography':found['geography']})
        else:
            excluded.append({**item,'excluded_reason':'Question/scope continuity could not be established from saved metadata'})
    return kept,excluded
