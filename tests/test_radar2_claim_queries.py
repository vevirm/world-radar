import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from radar2_broad_search import query_for


def test_generic_title_does_not_dominate_original_proposition():
    claim = {"title": "Comments: The Long-Term Outlook",
             "historical_focus": "Here are some of the significant findings from the report: Energy demand in developing nations will rise 65% by 2040, reflecting growing prosperity and expanding economies."}
    query = query_for(claim)
    assert "energy" in query and "demand" in query
    assert "comments" not in query and "outlook" not in query
    assert "here" not in query and "some" not in query


def test_european_scope_preserved_when_claim_text_omits_region():
    claim = {"title": "European coastal flood impacts", "historical_focus": "Coastal flood damage could double by 2050 due to sea level increase"}
    assert "europe" in query_for(claim)


def test_fallback_when_focus_missing():
    claim = {"title": "Irish coastal flooding impacts", "historical_focus": ""}
    assert "coastal" in query_for(claim)
