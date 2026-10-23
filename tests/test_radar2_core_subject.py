import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from radar2_source_selection import select_source


def claim(title, passage):
    return {'title': title, 'original_passage': passage, 'original_publication':'2015-01-01'}


def paper(title):
    return {'title': title, 'date':'2022-01-01', 'url':'https://example.org/paper', 'excerpt':''}


def test_jet_fuel_rejects_unrelated_supply_demand():
    c=claim('Renewable jet fuel supply scenarios in the European Union', 'nonfood renewable jet fuel supply by 2030')
    assert not select_source(c,paper('Supply and demand for cereals in Pakistan, 2010-2030'))[0]


def test_jet_fuel_allows_matching_theme():
    c=claim('Renewable jet fuel supply scenarios in the European Union', 'nonfood renewable jet fuel supply by 2030')
    assert select_source(c,paper('Renewable aviation fuel supply in the European Union'))[0]


def test_flood_rejects_unrelated_climate_risk():
    c=claim('Ensemble flood risk assessment in Europe', 'annual population affected by floods')
    assert select_source(c,paper('Climate and carbon risk of tourism in Europe'))[1]=='missing_core_subject'


def test_flood_allows_flood_papers():
    c=claim('Ensemble flood risk assessment in Europe', 'annual population affected by floods')
    assert select_source(c,paper('Increasing flood risk in Europe under climate change'))[0]


def test_energy_demand_doesnt_match_labour_demand():
    c=claim('The Long-Term Outlook', 'energy demand in developing nations will rise')
    assert select_source(c,paper('Demand for healthcare workers and prosperity in Asia'))[1]=='missing_core_subject'
