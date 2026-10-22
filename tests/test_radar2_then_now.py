"""The core three-step flow, including negatives, needs to be reliably repeatable."""
import sys
from pathlib import Path
from types import SimpleNamespace
import json
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import radar2_then_now as m


def source_html(paragraph):
    return '<html><head><title>Official observations</title></head><body><nav><p>Navigation links</p></nav><main><p>'+paragraph+'</p></main></body></html>'

class Response:
    def __init__(self,url,data,content_type='text/html'):
        self.url=url;self.data=data.encode();self.headers={'Content-Type':content_type}
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def geturl(self):return self.url
    def read(self,n):return self.data[:n]


def sample_claim(route):
    original=[o for o in m.choose_originals(ROOT,3) if m.route_for(o)['id']==route]
    assert len(original)==1
    return original[0]


def test_manifest_claims_are_actually_accepted():
    studies=json.loads((ROOT/'radar1-active.json').read_text())['studies']
    dois={s['doi'].lower() for s in studies}
    selected=m.choose_originals(ROOT)
    assert len(selected)==3
    assert len({r['id'] for r in selected})==3
    assert all(x['doi'].lower() in dois for x in selected)


def test_official_source_reading_not_just_link_titles():
    text='In 2025 the supply of sustainable aviation fuel (SAF) at European Union airports was 1.1 million tonnes, as officially reported.'
    route=next(r for r in m.ROUTES if r['id']=='eu_renewable_jet_fuel')
    source=m.read_page(route['sources'][0][2],opener=lambda u:Response(u,source_html(text)))
    assert m.matching_excerpt(source,route)==text
    assert source['title']=='Official observations'


def test_reading_fails_closed_on_offtopic_and_forecast_only():
    r=next(r for r in m.ROUTES if r['id']=='eu_renewable_jet_fuel')
    assert m.matching_excerpt({'paragraphs':['In 2025 the Japanese bioenergy market reported solar panel investments, with aviation research mentioned in passing.']},r) is None
    assert m.matching_excerpt({'paragraphs':['Researchers might produce renewable aviation fuel in 2050 by developing new production capacity.']},r) is None


def test_website_not_trusted_by_default():
    with pytest.raises(ValueError,match='non-whitelisted'):
        m.read_page('https://example.com/anything')


def test_redirect_not_trusted():
    r=m.ROUTES[1]
    with pytest.raises(ValueError,match='redirected'):
        m.read_page(r['sources'][0][2],opener=lambda u:Response('https://example.com/redirect',source_html('2025 sustainable aviation fuel was supplied in 2025.')))


def test_ten_to_two_workflow_observations_and_caveats():
    samples={
      'europe_flood_damage':'Hydrological hazards (floods) account for 47% of total economic losses from weather and climate extremes in Europe between 1980 and 2024.',
      'eu_renewable_jet_fuel':'Aviation fuel suppliers reported supplying 39.3 million tonnes of aviation fuel at Union airports in 2025, of which 1.1 million tonnes was sustainable aviation fuel (SAF).',
      'austria_automated_mobility':'Im Jahr 2025 haben zahlreiche Testfahrten in Österreich stattgefunden. Unter anderem wurden automatisierte Fahrzeuge im Testbetrieb eingesetzt und Verkehrspiloten untersucht.'
    }
    lookup={src[2]:route['id'] for route in m.ROUTES for src in route['sources']}
    def reader(url):
        return {'title':'Official monitoring','paragraphs':[samples[lookup[url]]]}
    report=m.investigate(m.choose_originals(ROOT,3),reader=reader)
    assert report['originals_investigated']==3
    assert report['sources_read']==6
    assert report['cases_with_two_sources']==3
    assert report['verified_outcomes']==0
    assert report['publish'] is False
    for c in report['cases']:
        assert len(c['later_sources'])==2
        assert all('source_passage' in x and x['published']>c['original_date'][:4] for x in c['later_sources'])
        assert 'not equivalent' in c['what_we_cannot_say'] or 'not' in c['what_we_cannot_say'].lower()
        assert c['review_status']=='machine_draft'
        assert not c['original_forecast_verified']
    md=m.markdown(report)
    assert 'Later source 2' in md
    assert 'cannot yet' in md


def test_missing_actual_passage_not_a_connection():
    r=m.ROUTES[0]
    orig=sample_claim(r['id'])
    result=m.investigate([orig],reader=lambda _: {'title':'Official','paragraphs':['Wind speeds and water levels are under investigation in coastal regions.']})
    assert result['cases_with_two_sources']==0
    assert result['sources_read']==0
    assert result['cases'][0]['relationship_status']=='official_source_check_incomplete'
    assert len(result['cases'][0]['sources_not_usable'])==2


def test_partial_network_failure_does_not_claim_completeness():
    original=sample_claim('eu_renewable_jet_fuel')
    def reader(url):
        if url==m.ROUTES[1]['sources'][1][2]:raise TimeoutError('publisher unavailable')
        return {'title':'EASA','paragraphs':['EU aviation fuel suppliers reported supplying 1.1 million tonnes of sustainable aviation fuel in 2025 at Union airports.']}
    r=m.investigate([original],reader=reader)
    assert r['sources_read']==1
    assert len(r['cases'][0]['sources_not_usable'])==1
    assert r['cases'][0]['relationship_status']=='one_later_source_read_provisional_connection'


def test_sources_always_later_and_official():
    for route in m.ROUTES:
        for source in route['sources']:
            assert source[1][:4] in {'2025','2026'}
            assert m.urlsplit(source[2]).hostname in m.ALLOWED_HOSTS


def test_no_manual_report_data_writes():
    m.choose_originals(ROOT)
    assert m.ROOT==ROOT
