"""Hard cases, independent of OpenAlex availability or paid API usage."""
from scripts.evidence_engine import evaluate, profile, query_plan, rescreen_existing, geography
from scripts.question_evidence import candidate

UNI={'title':'The Future of Internationalization of Higher Education in Europe',
     'expected':'A European Parliament study redefines internationalization and discusses digital learning, national reports and future universities.',
     'original_publication':'2015-12-02',
     'source_url':'https://doi.org/10.6017/ihe.2015.83.9073'}
SOIL={'title':'European scenarios for exposure of soil organisms to pesticides',
      'expected':'Research exploring the effects of pesticides on European soil organisms.',
      'original_publication':'2013-01-12','source_url':'https://doi.org/10.5555/orig'}

def w(title,abstract,when='2026-04-12',doi='https://doi.org/10.9999/other'):
    return {'title':title,'abstract':abstract,'publication_date':when,'doi':doi}


def test_vietnam_is_not_european_direction():
    assert evaluate(UNI,w('Internationalization of Higher Education in Vietnam',
             'Vietnamese universities have adopted internationalization models previously proposed in Europe.')) is None


def test_university_futures_paper_without_title_match_can_be_connected():
    example=w('University Futures: Insights from a Dialectic Delphi Study',
       'We study university futures and how internationalization can be defined and implemented in higher education; a Delphi approach identifies conflicting university priorities.')
    c=evaluate(UNI,example,discovery='semantic')
    assert c and c['evidence_kind'] in ('ongoing_research','newer_scenario_or_model')
    assert c['question_fit_score']>=8


def test_european_university_mobility_counts_as_changed_vocabulary():
    example=w('The European Universities initiative and international student mobility',
              'The study examines international mobility in European university alliances and the experiences of students.')
    c=evaluate(UNI,example,discovery='semantic')
    assert c and 'european' in c['geography']


def test_american_bank_loan_methods_are_not_european_forecasts():
    b={'title':'Machine learning forecasts of bank loan defaults in Europe',
       'original_publication':'2017-01-01','source_url':'https://doi.org/10.4444/loans'}
    assert evaluate(b,w('Machine learning forecasts of US hurricanes',
                              'A simulation predicts extreme US rainfall and hurricane events.')) is None


def test_pesticides_russia_outside_scope():
    assert evaluate(SOIL,w('Russian scenarios for exposure assessment of pesticides to soil organisms',
                           'Discusses pesticides for soil organisms in Russia, referencing European law.')) is None


def test_actual_soil_monitoring_is_a_direction():
    c=evaluate(SOIL,w('European monitoring of pesticide impacts on soil organisms',
            'We monitored pesticide exposure in soils in European farmland and found increased impacts on soil organisms.'))
    assert c and c['evidence_kind']=='measured_or_reported_change'


def test_scenario_is_not_claimed_as_actual_event():
    c=evaluate(SOIL,w('European pesticide exposure to soil organisms: 2050 scenarios',
            'This paper projects possible pesticide exposure to soil organisms under future policy scenarios.'))
    assert c and c['evidence_kind']=='newer_scenario_or_model'


def test_original_context_informs_semantic_query():
    s=query_plan(UNI)
    assert s[0][0]=='semantic'
    assert 'internationalization' in s[0][1].lower()
    assert 'higher education' in s[1][1]
    assert 'Vietnam' not in s[1][1]


def test_saved_links_quarantined_not_deleted():
    old=[{'title':'Internationalization of Higher Education in Vietnam',
         'finding_from_abstract':'Internationalization in Vietnam','url':'https://doi.org/10.1/foo',
         'year':2026,'date':'2026-04-12','evidence_kind':'ongoing_research'}]
    good,bad=rescreen_existing(UNI,old)
    assert not good and len(bad)==1 and 'excluded_reason' in bad[0]


def test_future_and_withdrawn_rejected():
    assert evaluate(UNI,w('[WITHDRAWN] University Internationalization in Europe',
                         'University internationalization in Europe is debated.')) is None
    assert evaluate(UNI,w('University internationalization in Europe',
                         'The issue continues.',when='2038-04-12')) is None

def test_virmajoki_actual_abstract_as_broader_university_context_not_direct_evidence():
    from scripts.evidence_engine import broader_context
    w0=w('University futures: Insights from a dialectic delphi study',
         'The future of universities is unclear. They face increasing pressures from market forces, political influence and societal expectations. '
         'Using a novel dialectic Delphi methodology, this study examined how members of a Finnish university conceptualized and analyzed potential futures extending to 2040. '
         'We identified dimensions of university futures, such as purpose, organisational structure and teaching models.',
         doi='https://doi.org/10.1016/j.futures.2026.103816')
    assert evaluate(UNI,w0) is None  # abstract does not address internationalization
    broad=broader_context(UNI,w0)
    assert broad and broad['topic_relation']=='broader_context_not_direct_followup'


def test_broader_context_excludes_different_region():
    from scripts.evidence_engine import broader_context
    w0=w('Vietnamese university futures and strategic management',
         'A Vietnamese university study examines institutional future choices in Vietnam using Delphi foresight interviews and surveys with administrators.')
    assert broader_context(UNI,w0) is None

def test_discover_combines_semantic_lexical_and_citations_without_requiring_accuracy(monkeypatch):
    import scripts.evidence_engine as eng
    work= w('European universities: internationalization strategy in 2026',
            'This study of internationalization in European universities finds different approaches to mobility and institutional cooperation.',
            doi='https://doi.org/10.7777/strong')
    parent={'id':'https://openalex.org/W555','title':UNI['title']}
    other=w('Internationalization of Higher Education in Vietnam',
            'Vietnam institutions use internationalization strategies from Europe.',
            doi='https://doi.org/10.7777/bad')
    related=w('University Futures: Insights from a Dialectic Delphi Study',
              'A Finnish university study of possible futures describes decision making, institutional roles, and governance under political uncertainty.',
              doi='https://doi.org/10.1016/j.futures.2026.103816')
    seen=[]
    def fake_request(params,budget,timeout=18):
        if not budget.available():return []
        budget.calls+=1
        seen.append(params)
        if params.get('filter','').startswith('doi:'):return [parent]
        if params.get('filter','').startswith('cites:'):return [work]
        return [work,other,related]
    monkeypatch.setattr(eng,'_request',fake_request)
    ans=eng.discover(UNI,budget=eng.SearchBudget(max_requests=5))
    assert any('strong' in x['url'] for x in ans['results'])
    assert all('Vietnam' not in x['title'] for x in ans['results'])
    assert any('University Futures' in x['title'] for x in ans['context'])
    assert ans['requests']<=5
    assert any('search.semantic' in q for q in seen)
    assert any('cites:' in q.get('filter','') for q in seen)
