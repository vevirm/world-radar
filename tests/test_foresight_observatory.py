import sys, tempfile, json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from foresight_observatory import relationship, queries, export
CLAIM={'id':'c','title':'Sustainable aviation fuel adoption in European airlines','original_claim':'By 2030 sustainable aviation fuel becomes widely adopted by EU airlines as cost falls','year':2015,'original_url':'https://example.org/original'}
def test_queries_are_specific():
 assert 'aviation' in ' '.join(queries(CLAIM))
def test_reject_neighbouring_topic():
 p={'title':'Cereal supply in Pakistan','abstract':'Wheat production costs and supply changed across Pakistan agriculture sectors. '+('Food price analysis. '*12),'year':2021}
 assert relationship(CLAIM,p) is None
def test_keep_direct_object():
 p={'title':'Sustainable aviation fuel adoption by European airlines','abstract':'EU aviation fuel uptake across airlines is tracked with deployment statistics, production costs and incentives. '+('Aviation fuel use increased. '*10),'year':2024}
 assert relationship(CLAIM,p) is not None
def test_does_not_accept_title_only():
 p={'title':'Sustainable aviation fuel adoption in EU','abstract':'','year':2024}
 assert relationship(CLAIM,p) is None
def test_export_docs_and_json():
 with tempfile.TemporaryDirectory() as t:
  root=Path(t);(root/'observatory-reviewed.json').write_text('{"findings":[]}')
  db={'schema_version':1,'claims':[CLAIM],'connections':{},'investigations':{}}
  export(root,db)
  assert (root/'POSSIBLE-CONNECTIONS-UNCHECKED.docx').exists()
  assert json.loads((root/'observatory-claims.json').read_text())['claims'][0]['id']=='c'
