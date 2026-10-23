from scripts.radar2_claim_search import search_plan

def test_flood():
 p=search_plan({'title':'Ensemble flood risk assessment in Europe','original_passage':'A larger range is foreseen in the annual flood damage, projected to 40 B€ in 2050.'})
 assert 'flood' in p['queries'][0] and 'foreseen' not in p['queries'][0]

def test_aviation():
 p=search_plan({'title':'Renewable jet fuel supply scenarios in the European Union','original_passage':'RJF supply could increase by 2030.'})
 assert 'aviation' in p['queries'][0]

def test_carbon():
 p=search_plan({'title':'Are Carbon Prices Redundant in the EU?','original_passage':'Cost-efficient EU climate policy through 2030.'})
 assert 'ETS' in p['queries'][0]
