"""One shared, conservative *relationship* policy for existing Radar 2 metadata.

This does not assess whether the original idea was true. It separates probable
same-question scholarship from comparative context and visibly bad automated
connections. The underlying original research, editorial notes and decisions
are never changed. No network requests.
"""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import urlsplit, unquote
try:
    from .question_evidence import issue_terms
except ImportError:
    from question_evidence import issue_terms

STATUS = re.compile(r'\b(?:withdrawn|retracted|retraction(?:\s+notice)?|expression of concern)\b', re.I)
EU = re.compile(r'\b(?:europe|european|eu|eurozone|european union|european countries)\b', re.I)
# Explicit *non-European* places in title: a different country is useful
# comparison, but not an answer to a specific Europe-wide question.
OTHER_REGION = re.compile(r'\b(?:russia|russian|vietnam|vietnamese|china|chinese|india|indian|'
    r'brazil|brazilian|latin america|latin american|mexico|mexican|colombia|colombian|'
    r'argentina|argentinian|peru|peruvian|australia|australian|new zealand|'
    r'japan|japanese|korea|korean|indonesia|indonesian|thailand|thai|'
    r'nigeria|nigerian|kenya|kenyan|pakistan|pakistani|morocco|moroccan|'
    r'california|united states|usa|u\.s\.|american|canada|canadian|iran|iranian|asia|asian|africa|african|southeast asia|south asia)\b', re.I)
# Very wide concepts alone are insufficient evidence that research answers the
# *particular question*. They may still be helpful when paired with real anchors.
BROAD = set('''climate change future futures technology technologies policy policies
    risk risks impacts impact sector sectors systems system model models study studies
    education higher international development global research
    environment environmental energy european europe european union economic social
    methods method approach strategies strategy trends data public university
    universities governance evaluation assessment health science
    history histories historical introduction introductory background present past
    now current recent new future futures today tomorrow yesterday during after
    previous before shaping shape challenge challenges perspective perspectives
    view views debate debates question questions review outlook sector sectors
    institution institutions relationship relationships effect effects cause causes
    consequence consequences study paper journal volume thematic topic subject
    insight insights literature theoretical practical empirical synthetic conceptual
    structural analytical policy-making political social societal cultural culture
    regulation regulatory public regional region area areas spatial temporal
    time real realtime real-time long short transformation alternative alternatives
    comparison comparing comparable comparative general particular innovative
    innovation innovative strategies strategy working work framework frameworking
    roles role implications implication impact impacts development developing
    management managing applied approaches approach result results solution solutions
    implementing implementation integration independent international cooperation
    country countries nationwide worldwide national state states governance strategy
    trends trends future historical assessment validity discussion discourse
    chance opportunities opportunity international affairs security preparedness
    emerging changing changed changes change trajectories dynamics dynamic
    performance sustainability sustainable resistance resilient resilience
    science scientific complexity complex practice practices example examples
    experience experiences use uses usage utilized using utilization
    cost costs analysis analyses problems problem adoption evaluated evaluate
    evidence forecast forecasting foresight predictions projection model models
    modelling modeling uncertainty uncertainty-related expected potentially
    applications application using methodological method methods technique
    consequences assessment evaluation conditions context contexts based
    reasons reason values value effects effect initiative perspective
    animal aspect aspects pros cons major other others three one two a few
    human people first second final related nation nations importance greater
    widespread direction effects effect opportunities possible emerging extreme
    reflection reflections issue interdisciplinary across field sector parts part
    real-world ecosystem ecosystems integration disintegration presentation
    involved intended per every
    '''.split())


def _year(raw):
    found = re.search(r'\b(?:19|20)\d\d\b', str(raw or ''))
    return int(found.group()) if found else 0


def canonical_url(url):
    url = str(url or '').strip()
    if not url.startswith('https://'):
        return ''
    p = urlsplit(url)
    host = p.netloc.casefold().removeprefix('www.')
    path = unquote(p.path).strip('/').casefold()
    if host in ('doi.org', 'dx.doi.org'):
        return 'doi:' + path
    return host + '/' + path + ('?' + p.query if p.query else '')


def _tokens(text):
    return issue_terms(str(text or ''))


def _same_work(old, later):
    a, b = _tokens(old), _tokens(later)
    a_plain = re.sub(r'[^a-z0-9]+', ' ', str(old).casefold()).strip()
    b_plain = re.sub(r'[^a-z0-9]+', ' ', str(later).casefold()).strip()
    if len(a_plain) >= 35 and a_plain in b_plain and any(
            word in b_plain for word in ('peer review report', 'faculty opinion',
                'recommendation of', 'version 2 peer review')):
        return True
    # Publisher recommendation notices can reproduce the exact original title
    # with a generic prefix; they are NOT new independent studies.
    # A follow-up can legitimately reuse *all* the old issue words and add
    # "monitoring" or "evaluation". That is not the same publication.
    # Require near-identical issue vocabulary (or an actual reused DOI above).
    enriched = bool(a and b and len(a & b) >= 5 and
                    len(a & b) / len(a | b) >= .93)
    return bool(a and b and (a == b or enriched))


# The title overlap score must not replace the *object of study*. The same
# words can describe wholly different things: human population structure vs
# bird genetics, financial grain futures vs grain cultivation, or ensemble
# weather forecasts vs a dengue prediction model. These subject signatures
# are conservative downgrade-to-context checks, NOT factual verdicts.
# Titles supply the context; an abstract may clarify a newer title, but generic
# mentions elsewhere are not enough to turn a different subject into evidence.
WEATHER_FORECAST = re.compile(r'\b(?:weather|meteorolog\w*|atmospher\w*|ecmwf|'
    r'precipitation|rainfall|wind speed|weather forecasting|temperature forecast)\b', re.I)
LAND_USE = re.compile(r'\b(?:land[ -]?use|urban growth|urban expansion|residential development|'
    r'population projection|population distribution|demograph\w*|urbanization|urbanisation|'
    r'settlement|built[ -]?up area|artificial surfaces)\b', re.I)
FINANCIAL_MARKET = re.compile(r'\b(?:futures? (?:market|contract|trading|price)|commodity (?:market|trading)|'
    r'hedg\w*|derivative\w*|financial (?:market|trading)|(?:grain|wheat|corn) (?:market|price|trade)|'
    r'market (?:mechanism|economics|integration)|exchange[ -]traded|price discovery)\b', re.I)
LABORATORY = re.compile(r'\b(?:lab|labs|laborator\w*)\b',re.I)


def issue_scope_conflict(original_title, later_title, later_finding=''):
    """Reason a seemingly similar title is not direct evidence on this issue.

    Different-topic results are *context*, never deleted merely for drift.
    The fallback leaves unfamiliar fields to the ordinary relevance check.
    """
    old = str(original_title or '').casefold()
    new_title = str(later_title or '').casefold()
    new = new_title + ' ' + str(later_finding or '').casefold()
    if re.search(r'\b(?:ensemble|numerical)\b', old) and WEATHER_FORECAST.search(old) and \
            re.search(r'\b(?:forecast|predict|weather)\w*\b', old):
        if not WEATHER_FORECAST.search(new):
            return 'different_forecasting_subject'
    if re.search(r'\bpopulation (?:structure|projection|distribution|dynamics)\b', old) and \
            re.search(r'\b(?:urban|land[ -]?use|land cover)\b', old):
        if not LAND_USE.search(new):
            return 'different_population_subject'
        # 'Urban goshawk population genetics' is not human urbanization, even
        # though it contains urban + population. Demand land-use / demographic
        # continuity rather than one 'urban' word.
        if re.search(r'\b(?:genetic|genom\w*|allelic|heterozygosity|goshawk|raptor)\b', new_title) and \
                not re.search(r'\b(?:land[ -]?use|demograph\w*|urban (?:growth|expansion)|population projection)\b', new_title):
            return 'different_population_subject'
    if re.search(r'\b(?:grain|wheat|commodity)\b', old) and \
            re.search(r'\b(?:futures?|hedg\w*|market|exchange|trading)\b', old):
        if not FINANCIAL_MARKET.search(new):
            return 'different_grain_market_subject'
    if re.search(r'\bforensic\b', old) and LABORATORY.search(old):
        if not LABORATORY.search(new) or not re.search(r'\b(?:forensic|public health|crime|criminal)\b', new):
            return 'different_forensic_laboratory_subject'
    if re.search(r'\b(?:perception|public use|use and perception|weather information)\b', old) and WEATHER_FORECAST.search(old):
        # People using forecasts != algorithms predicting solar power, lidar
        # perception, or remote sensing. "perception" is ambiguous in ML.
        people = re.search(r'\b(?:user|survey|respondent|stakeholder|household|farmer|fisher|'
                           r'public opinion|public perception|weather information use|weather information uptake|'
                           r'communicat|trust in|decision[- ]making|behavior|behaviour)\w*\b', new_title)
        if not WEATHER_FORECAST.search(new) or not people:
            return 'different_weather_information_subject'
    if re.search(r'\b(?:transition pathways|pathways to sustainability)\b',old) and \
            re.search(r'\b(?:climate|2.*°c|2.*degrees)\b',old):
        if re.search(r'\b(?:montreal|quebec|california|australia|iran|china|india|usa|canada)\b',new_title) and \
                not EU.search(new_title):
            return 'different_transition_geography'
        if not re.search(r'\b(?:climate|decarbon|emissions|mitigat|adaptation|sustainab)\w*\b',new_title):
            return 'different_climate_transition_subject'
    if re.search(r'\b(?:special needs|eaccessibility|special educational needs)\b',old) and \
            re.search(r'\b(?:educational|education)\b',old):
        if re.search(r'\b(?:combat operations|armed conflict|military|martial law)\b',new_title):
            return 'different_special_education_context'
    if re.search(r'\b(?:health inequalities|health inequities|health disparity|population health inequalities)\b', old):
        if not re.search(r'\b(?:inequal|inequit|disparit|equity|social determinant|health gap)\w*\b', new):
            return 'different_health_inequality_subject'
    if re.search(r'\b(?:employment supply|employment demand|labou?r (?:market|supply|demand)|workforce supply)\b',old):
        if not re.search(r'\b(?:employ|labou?r|workforce|job|occupation|unemploy)\w*\b',new_title):
            return 'different_labor_market_subject'
    if re.search(r'\b(?:energy infrastructure|power infrastructure|electricity infrastructure)\b',old):
        if not re.search(r'\b(?:energy|power|electricity|grid|renewable|decarbon|transmission|carbon neutral|fossil)\w*\b',new_title) or \
                not re.search(r'\b(?:infrastructure|network|grid|capacity|deployment|transition|generation|investment|system)\w*\b',new_title):
            return 'different_energy_infrastructure_subject'
        # Social effects of an existing oil project can be context, but aren't
        # in themselves an answer to projected *European 2050 infrastructure needs*.
        if re.search(r'\b(?:violence|elite capture|community resistance|state harm)\b',new_title) and \
                not re.search(r'\b(?:planning|projection|needs|demand|capacity|decarbon|electricity|grid)\w*\b',new_title):
            return 'energy_social_context_not_planning'
    if re.search(r'\b(?:landscape development|landscape developments|ecosystem services)\b',old) and \
            re.search(r'\b(?:scenario|landscape)\b',old):
        if not re.search(r'\b(?:ecosystem service|landscape (?:scenario|change|development|pattern)|'
                         r'land[ -]?use (?:scenario|change)|biodiversity)\w*\b',new):
            return 'different_landscape_ecosystem_subject'
    if re.search(r'\b(?:agricultural land|arable land|food production)\b',old) and \
            re.search(r'\bwater scarcity\b',old):
        if not re.search(r'\b(?:scarcity|drought|irrigat|water shortage|water stress|water availability|'
                         r'water resource|soil moisture|precipitation deficit|dry spell)\w*\b',new):
            return 'different_agricultural_water_subject'
    # A close title resemblance is not enough if the *object being studied* is
    # absent. Keep these papers as comparative/contextual reading, never as a
    # principal "what happened with this?" finding. Check the later TITLE:
    # generic mentions in an abstract should not override its main topic.
    focus_families = (
        ('fashion_supply_chain', r'\b(?:fashion|apparel|garment|textile|clothing)\b',
         r'\b(?:fashion|apparel|garment|textile|clothing)\b'),
        ('turbine_blade_waste', r'\b(?:turbine|wind power|wind energy)\b.*\b(?:blade|waste|recycl|disposal)\w*',
         r'\b(?:blade|waste|recycl|disposal|decommission|end.of.life|composite|circular)\w*'),
        ('carbon_futures_market', r'\b(?:carbon|emissions?|eua|eu.ets|emission allowance)\b.*\b(?:future|volatil|market|price|trad|garch)\w*',
         r'\b(?:carbon|emissions?|eua|eu.ets|ets|emission allowance|greenhouse gas|cap.and.trade|allowance market)\b'),
        ('soil_pesticide_exposure', r'\b(?:soil organisms?|soil biota|soil invertebrates?)\b.*\b(?:pesticide|insecticide|herbicide)\w*|\b(?:pesticide|insecticide|herbicide)\w*.*\b(?:soil organisms?|soil biota|soil invertebrates?)\b',
         r'\b(?:pesticide|insecticide|herbicide|soil ecotox|soil organisms?)\w*'),
        ('urban_land_population', r'\b(?:urban|land.use|land cover)\b.*\b(?:population|demograph)\w*|\b(?:population|demograph)\w*.*\b(?:urban|land.use|land cover)\b',
         r'\b(?:demograph|urbanization|urbanisation|urban population|urban growth|land.use|settlement)\w*'),
        ('climate_air_quality', r'\b(?:air quality|atmospher)\w*.*\b(?:climate|scenario|projection|cmip)\w*',
         r'\b(?:air quality|air pollution|ozone|particulate|pollutant|air quality model|regional climate)\w*'),
    )
    for name, old_pattern, later_pattern in focus_families:
        if re.search(old_pattern, old, re.I) and not re.search(later_pattern, new_title, re.I):
            return 'missing_original_focus_' + name

    # A policy's measured emissions reductions are not a follow-up on the
    # price behaviour of emission-allowance futures. Conversely, general
    # decarbonisation papers are not evidence about carbon capture/storage.
    if re.search(r'\b(?:futures?|volatilit|price discovery|risk premium|hedg)\w*',old) and \
            re.search(r'\b(?:carbon|emissions?|eua|eu.ets|allowance)\w*', old) and \
            not re.search(r'\b(?:futures?|volatilit|price|premiums?|hedg|derivative|markets?|auction)\w*',new_title):
        return 'different_carbon_financial_question'
    if re.search(r'\b(?:carbon capture|carbon storage|\bccs\b|\bbeccs\b|sequestration)\b',old) and \
            not re.search(r'\b(?:carbon capture|carbon storage|\bccs\b|\bbeccs\b|sequestration|direct air capture)\b',new_title):
        return 'missing_carbon_capture_focus'

    # A sector-specific paper can illuminate a general question, but it is
    # not automatically evidence about the trajectory of the whole sector.
    if re.search(r'\b(?:employ|labou?r)\w*', old) and not \
            re.search(r'\b(?:transport|mobility|freight|road traffic|logistics)\w*',old) and \
            re.search(r'\b(?:transport|mobility|freight|road traffic|logistics|engineering industry|aviation industry|manufacturing industry)\w*',new_title):
        return 'sector_case_not_economy_wide_employment'
    if re.search(r'\b(?:organic farm|organic agricultur)\w*',old) and \
            re.search(r'\b(?:phosphor|nutrient removal|fertiliz|soil amendment)\w*',new_title) and \
            not re.search(r'\b(?:phosphor|nutrient|fertiliz|soil amendment)\w*',old):
        return 'specific_input_not_farming_trajectory'

    # A question about policy *effects* is not answered by statistics on the
    # issue alone: immigration and employment growing together does not show
    # what the immigration-policy scenarios caused or changed.
    if re.search(r'\b(?:immigration|migration)\b', old) and \
            re.search(r'\b(?:polic|legislation|regulation)\w*', old) and \
            re.search(r'\b(?:effect|impact|scenario|projection)\w*', old) and \
            not re.search(r'\b(?:polic|legislation|regulation|policy evaluation|policy reform|causal|counterfactual)\w*',new_title):
        return 'missing_policy_effect_focus'
    # Endoscopy-specific guideline updates are not identical to generic IBD
    # malignancy updates, even when the latter may be useful clinical context.
    if re.search(r'\bendoscop\w*', old) and \
            not re.search(r'\b(?:endoscop|colonoscopy|endoscopic)\w*', new_title):
        return 'missing_endoscopy_focus'

    # Do not promote a domain-specific illustrative application into an answer
    # about a genuinely *general* issue (AI acceptance => AI in hospitals;
    # digital governance => food-safety controls). It may still be context.
    narrower_fields = (
        ('healthcare', r'\b(?:patient|clinical|hospital|healthcare|medical|disease|cancer|diagnos)\w*\b',
         r'\b(?:patient|clinical|hospital|healthcare|health|medical|disease|cancer|diagnos|mortality|wellbeing|epidem|inequal|inequit)\w*\b'),
        ('food_agriculture', r'\b(?:food safety|food processing|chicken|poultry|antibiotic|crop breeding|pesticide|livestock)\b',
         r'\b(?:food|agricult|farm|crop|pesticide|animal|livestock|poultry|antibiotic)\w*'),
        ('genetics_wildlife', r'\b(?:goshawk|raptor|genom|population genetics|genetic structure|mitochondrial)\w*',
         r'\b(?:genetic|genom|goshawk|raptor|bird|wildlife|mitochondrial)\w*'),
        ('education_case', r'\b(?:higher education|universit|school|student|teacher|classroom|educational)\w*',
         r'\b(?:education|universit|school|student|teacher|classroom|academic)\w*'),
        ('financial_markets', r'\b(?:gold futures?|oil futures?|commodity futures?|share prices?|stock market)\b',
         r'\b(?:futures?|commodity|market|stock|gold|financial|trading)\w*'),
    )
    for name, later_pattern, original_pattern in narrower_fields:
        if re.search(later_pattern, new_title, re.I) and not re.search(original_pattern, old, re.I):
            return 'different_main_subject_' + name

    # Major topic shifts which can easily evade word-overlap screens:
    if re.search(r'\b(?:carbon|eua|emission allowances?|carbon market)\b', old) and \
            re.search(r'\b(?:gold|silver|precious metals?)\b', new_title) and \
            not re.search(r'\b(?:carbon|eua|emission allowances?)\b', new_title):
        return 'different_commodity_market'
    if re.search(r'\b(?:climate|carbon|decarbon|emissions?)\b', old) and \
            re.search(r'\b(?:antibiotic resistance|poultry|chicken disease)\b',new_title) and \
            not re.search(r'\b(?:climate|emissions?|decarbon)\b',new_title):
        return 'different_climate_policy_subject'
    return ''


def classify(entry, item, field):
    """Return (direct|context|quarantine, reason).

    `direct` still means *candidate same-issue research*, never proven reality.
    `context` means the study may help comparison but must NOT drive NOW/ranks.
    """
    if not isinstance(item, dict):
        return 'quarantine', 'malformed_link'
    title = str(item.get('title') or '').strip()
    url = canonical_url(item.get('url'))
    if not title or not url:
        return 'quarantine', 'missing_title_or_url'
    if item.get('is_retracted') is True or item.get('is_withdrawn') is True or STATUS.search(title):
        return 'quarantine', 'retracted_or_withdrawn'
    old_title = str(entry.get('title') or entry.get('expected') or '')
    explicitly_different_region = bool(EU.search(old_title) and OTHER_REGION.search(title) and not EU.search(title))
    if canonical_url(entry.get('source_url')) == url or (_same_work(old_title, title) and not explicitly_different_region):
        return 'quarantine', 'same_original_or_republication'
    original_year = _year(entry.get('original_publication') or entry.get('year'))
    new_year = _year(item.get('date') or item.get('year'))
    if new_year and (new_year > date.today().year or (original_year and new_year < original_year)):
        return 'quarantine', 'wrong_publication_date'
    if new_year and new_year == original_year:
        old_date = str(entry.get('original_publication') or '')[:10]
        new_date = str(item.get('date') or '')[:10]
        if not (re.fullmatch(r'\d{4}-\d\d-\d\d', old_date) and
                re.fullmatch(r'\d{4}-\d\d-\d\d', new_date) and new_date > old_date):
            return 'quarantine', 'not_demonstrably_later'
    original = _tokens(old_title)
    title_terms = _tokens(title)
    finding = str(item.get('finding_from_abstract') or item.get('abstract_excerpt') or '')
    subject_conflict = issue_scope_conflict(old_title, title, finding)
    if subject_conflict:
        return 'context', subject_conflict
    full_terms = title_terms | _tokens(finding)
    shared_title = original & title_terms
    shared = original & full_terms
    specific_title = shared_title - BROAD
    specific_full = shared - BROAD

    mismatch = bool(EU.search(old_title) and OTHER_REGION.search(title) and
                    not EU.search(title))
    # A non-EU region named in the *later title* cannot be rescued by an
    # incidental mention of the EU in the later abstract.
    if mismatch:
        if specific_full and len(shared) >= 2:
            return 'context', 'different_geography'
        return 'quarantine', 'different_geography_and_weak_topic'
    if item.get('geography') == 'other_region':
        return 'context', 'different_geography'

    # This field explicitly collects wider/indirect reading. Don't upgrade it
    # automatically to observed change just because it has a shared title.
    if field == 'field_developments':
        # A preceding run may have downgraded this to context. Keep the
        # decision stable, provided publication status/date remain valid.
        if item.get('evidence_role') == 'related_context' and item.get('context_reason'):
            return 'context', item['context_reason']
        if (specific_title and len(shared) >= 2) or len(specific_full) >= 2:
            return 'context', 'broader_field_development'
        return 'quarantine', 'too_loose_for_field_context'

    # Domain abbreviations and expanded names are equivalent issue anchors:
    # EUA (European emission allowances) and carbon-futures pricing need not
    # repeat the exact same words to represent the same financial question.
    if re.search(r'\b(?:eua|eu.ets|emission allowance)\b', old_title, re.I) and \
            re.search(r'\b(?:carbon|emission allowance|eua|ets)\b',title,re.I) and \
            re.search(r'\b(?:future|volatil|price|market|hedg)\w*',old_title,re.I) and \
            re.search(r'\b(?:future|volatil|price|market|hedg)\w*',title,re.I):
        return 'direct', 'equivalent_carbon_market_vocabulary'

    # Require a topic-specific anchor, not only a research method or words
    # like "higher education" or "climate change".
    if not specific_full:
        if len(shared_title) >= 2:
            return 'context', 'same_broad_subject_only'
        return 'quarantine', 'no_specific_shared_issue'
    original_specific = original - BROAD
    shared_specific_title = original_specific & title_terms
    strong_coverage = len(shared_specific_title) / max(1, len(original_specific))
    # A concise one-topic question can be followed by another concise title;
    # wider, multi-part questions need at least two real subject anchors.
    close_question = ((len(original_specific) <= 2 and len(shared_specific_title) >= 1)
                      or (len(shared_specific_title) >= 2 and strong_coverage >= .35)
                      or len(shared_specific_title) >= 4)
    if close_question and (len(shared_title) >= 2 or len(shared_specific_title) >= 2):
        return 'direct', 'same_issue_title'
    if (len(shared_specific_title) >= 1 and len(shared) >= 2 and
        len(shared_specific_title) >= min(2, len(original_specific)) and strong_coverage >= .4):
        return 'direct', 'same_issue_title_and_abstract'
    if len(specific_full) >= 2 and len(shared) >= 3:
        return 'context', 'issue_only_in_abstract'
    if specific_title:
        return 'context', 'one_topic_anchor'
    return 'quarantine', 'insufficient_topic_connection'


# Editorial promotion only: absence of geographic metadata is not a rejection.
# It simply means the shortlist should favor a clearly comparable setting.
EU_LOCATION = re.compile(
    r'\b(?:europe|european|eu|europ(?:e|ean) union|germany|german|france|french|'
    r'finland|finnish|italy|italian|spain|spanish|sweden|swedish|'
    r'netherlands|dutch|poland|polish|denmark|danish|belgium|belgian|'
    r'austria|austrian|portugal|portuguese|ireland|irish|'
    r'britain|british|england|uk|united kingdom|romania|romanian)\b',re.I)


def same_geographic_context(original_title, newer_title, abstract=''):
    if not EU.search(str(original_title or '')):
        return False
    # Named European location in the later title is the strongest sign.
    if EU_LOCATION.search(str(newer_title or '')):
        return True
    # Explicit place in the summary is helpful, but not a requirement.
    return bool(EU_LOCATION.search(str(abstract or '')))


def substantive_excerpt(value):
    """Avoid promoting abstracts that consist of metadata rather than findings.

    This is NOT a test for whether a publication is correct. A real scenario,
    policy discussion, or unresolved debate is still substantive research.
    """
    text=' '.join(str(value or '').split()).strip()
    if len(text) < 65 or len(text.split()) < 10:
        return False
    if re.match(r'^(?:temporal coverage|geographic coverage|unit of observation|'
                r'file format|dataset (?:covers|contains)|country.year records|'
                r'data availability|download the data)\b',text,re.I):
        return False
    return True
