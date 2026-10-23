import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from radar2_claim_evidence import assess_connection,evidence_card
CLAIM={'title':'Renewable jet fuel supply scenarios in the European Union',
 'original_passage':'Nonfood renewable jet fuel supply in the European Union could grow by 2030 with technology incentives.',
 'original_publication':'2017-01-01'}
def paper(title,description='',date='2024-04-01'):
 return {'title':title,'excerpt':description,'date':date,'url':'https://example.org/paper'}
def test_cereal_rejected():
 ok,d=assess_connection(CLAIM,paper('Supply and demand for cereals in Pakistan 2010-2030'))
 assert not ok and d['reason']=='different_core_object'
def test_aviation_synonym_accepted():
 ok,d=assess_connection(CLAIM,paper('EU sustainable aviation fuel uptake and deployment','Market penetration across Europe'))
 assert ok and 'aviation_fuel' in d['shared_concepts']
def test_reject_earlier():
 ok,d=assess_connection(CLAIM,paper('European jet fuel uptake',date='2014-01-01'))
 assert not ok and d['reason']=='not_later_than_original'
def test_unread_does_not_create_account():
 card=evidence_card({'original_id':'x','original_passage':'claim','readings':[{'status':'fetch_error'}]})
 assert card['direction']=='not_determined' and not card['evidence_sources']
def test_candidates_preserved_with_source():
 card=evidence_card({'original_id':'x','original_passage':'claim','readings':[{'status':'page_text_read','url':'https://example.org','candidate_findings':[{'text':'Observed X','kind':'reported_development'}]}]})
 assert len(card['evidence_sources'])==1 and card['direction']=='not_determined'
