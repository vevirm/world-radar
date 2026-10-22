import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from radar2_25min import paged_params

def test_paginated_discovery_grows_past_50():
    for source, params in [('openalex',{'per_page':12}),('crossref',{'rows':12}),('europe_pmc',{'pageSize':12})]:
        p=paged_params(source,params,6)
        if source=='openalex': assert p['page']==6
        elif source=='crossref': assert p['offset']==60
        else: assert p['page']==6
