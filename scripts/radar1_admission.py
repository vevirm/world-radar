"""Conservative, reproducible admission decision for Radar 1 academic originals.

A DOI/search hit is never sufficient. The subject must concern a future development
in Europe/EU, not merely contain a future-related word. Unknown = reject after
one closer examination of the available abstract/publisher metadata. Does not
make predictions or retrospective judgements. Used both by saved-data cleanup
and by every new scholarly discovery batch.
"""
import re
from datetime import date

POLICY_VERSION = 4
START = date(2011, 1, 1)
END = date(2023, 12, 31)

EU = re.compile(r'\b(?:Europe|European|European Union|EU(?:-?27|-?28)?|Eurozone|'
                r'member states|Schengen|European Commission|E\.U\.)\b', re.I)
EU_COUNTRY = re.compile(
    r'\b(?:Austria|Belgium|Bulgaria|Croatia|Cyprus|Czech(?:ia| Republic)?|Denmark|'
    r'Estonia|Finland|France|Germany|Greece|Hungary|Ireland|Italy|Latvia|'
    r'Lithuania|Luxembourg|Malta|Netherlands|Poland|Portugal|Romania|Slovakia|'
    r'Slovenia|Spain|Sweden|Norway|Iceland|Switzerland|United Kingdom|UK|Britain|Great Britain|'
    r'British|England|Scotland|Wales|Baltic|Nordic|Scandinavi\w*|'
    r'Mediterranean|Western Balkans|Ukraine|Ukrainian|Brexit)\b', re.I)
OTHER_REGION = re.compile(
    r'\b(?:Pakistan|Patagonia|Argentina|Chile|Peru|Colombia|Mexico|China|Chinese|India|Indian|Vietnam|Iran|Brazil|Australia|'
    r'United States|USA|Canada|Japan|Russia|South Africa|East Africa|'
    r'West Africa|Latin America|Bangladesh|Indonesia|Nigeria)\b', re.I)
EU_STUDY = re.compile(
    r'\b(?:in|across|for|throughout|within|among|of|toward(?:s)?)\s+'
    r'(?:the\s+)?(?:EU|Europe|European Union|European countries|EU member states)\b|'
    r'\b(?:EU|European)\s+(?:policy|policies|economy|energy|society|climate|'
    r'labou?r|market|security|agricultur\w*|transition|electricity|transport|'
    r'migration|demograph\w*|governance|cities|regions|health|industry|'
    r'integration|institutions|population|countries|member states)\b', re.I)
FUNDING_ONLY = re.compile(r'\b(?:funded|funding|grant|supported|co.financed)\b.{0,65}'
                          r'\b(?:European Union|EU|European Commission)\b', re.I)
PARATEXT = re.compile(
    r'\b(?:corrigendum|erratum|book review|peer review report|retraction|'
    r'conference announcement|conference programme|call for papers|withdrawn|'
    r'editors? comments?|guest.editor|editors? introduction)\b|'
    r'^\s*(?:\d+[.]?[A-Z]?[.]?\s*workshop:|workshop:|preface|editorial|introduction to (?:the )?special issue|'
    r'review:|response to|issue on|letter to the editor|'
    r'\d{1,2}[.]?[A-Z][.]?\s*(?:workshop|skills building seminar))\b|'
    r'\s+[–:-]\s*preface\s*$', re.I)
FINANCE = re.compile(
    r'\b(?:futures?\s+(?:markets?|contracts?|trading|prices?|pricing|returns?|'
    r'volatility|hedging|liquidity|options?|exchange|indices|index)|'
    r'spot[\s/-]?futures?|commodity futures?|futures?\s+(?:and|versus|vs\.?)\s+spot|'
    r'(?<![-\w])(?:carbon|electricity|stock|oil|gas|wheat|grain|currency|bond|'
    r'emission\s+allowance|crude\s+oil|EUA|EU[ -]?ETS)\s+futures?\b)\b', re.I)
# Match the sense of a commodity futures contract, never "low-carbon futures"
# or "sustainable energy futures".
TRADE_CONTEXT = re.compile(r'\b(?:spot prices?|price discovery|arbitrage|'
                           r'financial derivatives?|hedging effectiveness|'
                           r'exchange traded|investment returns?|trading volumes?)\b', re.I)
CONSENSUS = re.compile(r'\b(?:Delphi|consensus)\b.{0,100}\b(?:clinical|'
                       r'guidelines?|recommendations?|competencies|curriculum|'
                       r'questionnaire|statements|diagnosis|treatment)\b|'
                       r'\b(?:clinical|guidelines?|recommendations?|competencies|'
                       r'curriculum|questionnaire|statements|diagnosis|treatment)\b'
                       r'.{0,100}\b(?:Delphi|consensus)\b', re.I)
HISTORY = re.compile(r'\b(?:ancient|medieval|archaeolog\w*|palaeoclimat\w*|'
                     r'paleoclimat\w*|prehistor\w*|Holocene|colonial|coloniz\w*|colonis\w*|'
                     r'(?:eighteenth|nineteenth|seventeenth) century|then and now|'
                     r'19(?:[0-8]\d|90)s|(?:17|18|19)\d\d[–-](?:17|18|19)\d\d)\b', re.I)
OPERATIONS = re.compile(r'\b(?:daily weather|short.term weather|stock price|'
                        r'loan default|credit scoring|intraday|next.day|thermal coal spot prices?|'
                        r'earthquake early.warning|electricity spot prices|nowcasting)\b', re.I)
SHORT_HORIZON_ABSTRACT = re.compile(r'\b(?:one.year forecast|one.week forecast|'
                                    r'one.day forecast|short.term forecast|quarter.ahead prediction)\b', re.I)
STUDENT_SIMULATION = re.compile(r'\b(?:role.playing game|teaching simulation|'
                                r'classroom exercise)\b.*\b(?:students?|undergraduates?|class)\b', re.I)
FUTURE_TITLE = re.compile(
    r'\b(?:strategic foresight|foresight(?:ing)?|horizon scanning|'
    r'backcast\w*|forecast\w*|prospective|long.term projections?|future of|future sea.level|future climate|'
    r'future\s+(?:scenarios?|developments?|pathways?|energy|climate|sea.level|'
    r'society|migration|distribution|demand|supply|skills|land.use|'
    r'transitions?|outlook|policy|urban)|futures?\s+(?:of|for|in)|'
    r'alternative futures?|low.carbon futures?|futures?\b(?!\s+(?:contracts?|markets?|prices?|trading|index))|'
    r'future.s?\s+of|scenario\w*|'
    r'projections?|pathways?\s+(?:to|towards?)|'
    r'long.term outlook|by\s+20[3-9]\d|(?:towards?|to)\s+20[3-9]\d)\b', re.I)
# A title may present a substantive long-run model with no future word.
TITLE_HORIZON = re.compile(r'\b(?:20(?:2[4-9]|[3-9]\d)|2100)\b')
FUTURE_ABSTRACT = re.compile(
    r'\b(?:foresight|horizon scanning|backcast\w*|forecast\w*|'
    r'future\s+(?:scenarios?|developments?|trends?|conditions?|'
    r'of|projections?|pathways?|demand|supply|roles?|trajector\w*|'
    r'energy|climate|generations?|distribution|impacts?|changes?|'
    r'outcomes?|polic\w*|worlds?|evolution|research agenda)|'
    r'alternative futures?|projections?|long.term (?:scenarios?|projections?|outlook|'
    r'planning|development|trajector\w*|modelling|modeling)|'
    r'project(?:ed|ing|ions?)\s+(?:forward|to|for|until|through|by|over)|'
    r'scenario(?:s| planning| building| modelling| modeling| analysis)?|'
    r'pathways?\s+(?:to|towards?)\s+20[3-9]\d|'
    r'(?:by|in|until|to|towards)\s+20[3-9]\d)\b', re.I)
# Future research recommendations are not substantive futures research.
FUTURE_ASIDE = re.compile(r'\b(?:future (?:research|studies|work|investigations)|'
                          r'need for future research|in the future we|future directions)\b', re.I)
RESEARCH_VERB = re.compile(r'\b(?:model(?:s|led|ling|ing)?|simulat\w*|'
                           r'estimat\w*|assess\w*|analys\w*|analyz\w*|'
                           r'examin\w*|explor\w*|develop\w*|evaluat\w*|'
                           r'project\w*|investigat\w*|envisag\w*|anticipat\w*|'
                           r'construct\w*|compare\w*|quantif\w*|'
                           r'predict\w*|propos\w*|identif\w*)\b', re.I)
LONG_HORIZON = re.compile(r'\b(?:20(?:2[4-9]|[3-9]\d)|2100|next\s+(?:10|15|20|30|40|50)\s+years|'
                          r'mid.century|end.of.century|long.term)\b', re.I)
CURRENT_SCENARIO = re.compile(r'\b(?:current|present|existing|real.world|case.based|legal|court|'
                              r'family reunification)\s+scenarios?\b|'
                              r'\bscenarios?\s+(?:in practice|under current law)\b', re.I)
CLINICAL_SCENARIOS = re.compile(r'\b(?:clinical|patient|case.based|real.world|'
                                 r'surgical|diagnostic|treatment)\s+scenarios?\b', re.I)


def _clean(text):
    return ' '.join(str(text or '').split())


def decision(lead):
    """Return (accepted: bool, reason: str, check: str).

    check records whether title alone sufficed or abstract was examined. There is
    no long-lived undecided status, and rejection is not a claim of poor science.
    """
    title = _clean(lead.get('title'))
    abstract = _clean(lead.get('abstract'))
    try:
        published = date.fromisoformat(str(lead.get('date', '')))
    except (ValueError, TypeError):
        return False, 'invalid_publication_date', 'metadata'
    if not START <= published <= END:
        return False, 'outside_historical_original_period', 'metadata'
    if not title or len(title.split()) < 4:
        return False, 'no_substantive_title', 'metadata'
    if PARATEXT.search(title):
        return False, 'editorial_review_or_not_original_study', 'title'
    if FINANCE.search(title) or (TRADE_CONTEXT.search(title) and re.search(r'\bfutures?\b', title, re.I)):
        return False, 'financial_futures_not_foresight', 'title'
    if CONSENSUS.search(title) and not (LONG_HORIZON.search(title) or re.search(r'\b(?:foresight|future of|future scenarios?)\b', title, re.I)):
        return False, 'consensus_delphi_not_future_study', 'title_plus_abstract'
    if CURRENT_SCENARIO.search(title) and not LONG_HORIZON.search(title) and not re.search(r'\b(?:future|foresight|projection|forecast|20[3-9]\d)\b', title, re.I):
        return False, 'scenario_is_present_day_context', 'title'
    if CLINICAL_SCENARIOS.search(title) and not LONG_HORIZON.search(title):
        return False, 'clinical_scenarios_not_foresight', 'title'
    if HISTORY.search(title) and not (FUTURE_TITLE.search(title) and LONG_HORIZON.search(title)):
        return False, 'historical_reconstruction_not_forward_looking', 'title'
    if OPERATIONS.search(title) and not LONG_HORIZON.search(title):
        return False, 'short_horizon_operational_prediction', 'title'
    if STUDENT_SIMULATION.search(title) and not (EU.search(title) and LONG_HORIZON.search(title)):
        return False, 'classroom_scenario_not_european_futures_research', 'title'
    if SHORT_HORIZON_ABSTRACT.search(abstract) and not LONG_HORIZON.search(title + ' ' + abstract):
        return False, 'short_horizon_operational_prediction', 'abstract'

    title_europe = bool(EU.search(title) or EU_COUNTRY.search(title))
    abstract_europe = bool(EU_STUDY.search(abstract))
    # Specific European country studies can be relevant if actual future pathways
    # are modelled; project funding or a stray European mention is insufficient.
    country_in_abstract = bool(EU_COUNTRY.search(abstract))
    if OTHER_REGION.search(title) and not title_europe:
        return False, 'non_european_subject', 'title_plus_abstract'
    if not title_europe and not abstract_europe and not country_in_abstract:
        return False, 'european_subject_not_established', 'title_plus_abstract'
    if not title_europe and (abstract_europe or country_in_abstract):
        # Abstract-only EU connection must describe the area being analysed,
        # not merely name an EU grant or a research institution.
        meaningful = bool(EU_STUDY.search(abstract) or re.search(
            r'\b(?:in|across|for|among|within|of)\s+(?:the\s+)?' +
            EU_COUNTRY.pattern, abstract, re.I))
        if not meaningful or (FUNDING_ONLY.search(abstract) and not EU_STUDY.search(abstract)):
            return False, 'incidental_european_mention_only', 'abstract'

    title_future = bool(FUTURE_TITLE.search(title))
    title_horizon = bool(TITLE_HORIZON.search(title))
    # Horizon+topic alone is weaker than true future study, but can be supported
    # by a model-based scenario in the abstract.
    abstract_future = FUTURE_ABSTRACT.search(FUTURE_ASIDE.sub(' ', abstract))
    research = bool(RESEARCH_VERB.search(abstract))
    horizon = bool(LONG_HORIZON.search(title + ' ' + abstract))
    scope = 'title_plus_abstract' if abstract else 'title'
    if not abstract:
        if title_future and title_europe and (horizon or re.search(
                r'\b(?:foresight|scenarios? (?:for|of|towards?|by)|projections?|strategic forecasts?|prospective|'
                r'future of|future pathways?|futures? of|alternative futures?|low.carbon futures?|'
                r'parking futures?|territorial futures?|(?:European|Europe|EU).*?futures?)\b', title, re.I)):
            return True, 'clear_european_forward_question_in_title', 'title_only_clear'
        return False, 'ambiguous_title_no_supporting_abstract', 'title_only_unclear'
    # Explicit future-policy analyses count even when scenarios are qualitative;
    # not all work needs a falsifiable point prediction.
    if title_future and title_europe:
        if abstract_future or (horizon and research) or re.search(r'\b(?:foresight|future of|alternative futures?|futures? of)\b', title, re.I):
            return True, 'european_future_question_substantiated', scope
        return False, 'title_future_term_not_substantive_in_abstract', scope
    if title_future and horizon and research and title_europe:
        return True, 'explicit_long_horizon_with_european_model_or_analysis', 'abstract'
    if abstract_future and research and (horizon or len(list(FUTURE_ABSTRACT.finditer(abstract))) >= 2):
        return True, 'future_analysis_confirmed_by_abstract', 'abstract'
    if title_future and abstract_future and research and title_europe:
        return True, 'future_method_with_european_scope', 'abstract'
    if title_horizon and abstract_future and research and title_europe:
        return True, 'future_horizon_confirmed_by_abstract', 'abstract'
    return False, 'future_facing_research_question_not_established', 'abstract'
