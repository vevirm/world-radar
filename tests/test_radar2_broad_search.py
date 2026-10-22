import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import radar2_broad_search as s

def test_query_from_original_not_fixed_topic():
    a={'title':'European coastal flood damage projections','historical_focus':'Sea level increases might damage coastal infrastructure'}
    b={'title':'European workforce ageing forecast','historical_focus':'Older employees may increase employment participation'}
    assert s.query_for(a)!=s.query_for(b)

def test_three_independent_indices():
    assert {name for name,_,_ in s.source_queries('flood damage',2021)}=={'openalex','crossref','europe_pmc'}

def test_leads_not_outcomes_and_dates():
    claim={'id':'x','title':'European coastal flood damage projections','historical_focus':'Coastal flood damage rises','original_publication':'2010-01-01'}
    def fake(url, params):
        if 'openalex' in url:return {'results':[{'title':'European coastal flood damage observations','publication_date':'2020-01-01','doi':'https://doi.org/10.123/a'}]}
        if 'crossref' in url:return {'message':{'items':[{'title':['European coastal flood damage studies'],'published':{'date-parts':[[2021,1,1]]},'URL':'https://doi.org/10.123/b'}]}}
        return {'resultList':{'result':[{'title':'European coastal flood damage comparison','firstPublicationDate':'2022-01-01','source':'MED','id':'123'}]}}
    report=s.discover(claim,fetcher=fake)
    assert len(report['leads'])==3
    assert all(not x['observed_development_confirmed'] for x in report['leads'])
    assert report['verified_outcomes']==0

def test_partial_failures_not_hidden():
    c={'id':'x','title':'European coastal flood damage projections','original_publication':'2010-01-01'}
    r=s.discover(c,fetcher=lambda *_: (_ for _ in ()).throw(ConnectionError('down')))
    assert r['status']=='partial_discovery_errors' and len(r['errors'])==3
