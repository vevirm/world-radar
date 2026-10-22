"""Radar 1 -> future Radar 2 content gate (NO Radar 2 execution).

Require indexed abstract or verifiable publisher/original description containing a
specific forward-looking development, alternative scenario, expected consequence,
or an identifiable European strategic question. Avoid converting a generic word
match or research aim into a factual prediction. Return verbatim provenance text
for later human/source checking, not a retrospective verdict.
"""
import re

VERSION = 1

FUTURE = re.compile(
    r'\b(?:futures?|foresight|horizon scanning|forecast\w*|project\w*|'
    r'anticipat\w*|expect(?:ed|ations?)?|envisag\w*|prospectiv\w*|'
    r'scenarios?|pathways?|transition\w*|2050|2030|2040|2060|2100|'
    r'20[3-9]\d|mid.century|end.of.century|long.term|forthcoming|'
    r'could|would|will|may|might|likely|possib\w*|risk\w*|'
    r'upcoming|in the coming decades|next decades?|future\s+(?:of|for|in)|envisag\w*|recommen\w*)\b', re.I)
HORIZON = re.compile(r'\b(?:20(?:2[4-9]|[3-9]\d)|2100|mid.century|end.of.century|next\s+(?:two|three|four|five|10|20|30|40|50)\s+(?:decades?|years?)|long.term)\b',re.I)
ALTERNATIVES = re.compile(
    r'\b(?:alternative|contrasting|plausible|possible|different|multiple|several|three|two|four|five|'
    r'policy|mitigation|adaptation|development|business.as.usual|baseline|'
    r'high.emission|low.emission|net.zero|decarboni\w*|RCP\d|SSP\d|'
    r'future)\b.{0,50}\b(?:scenarios?|futures?|pathways?|trajector\w*|options?)\b|'
    r'\b(?:scenarios?|pathways?|trajector\w*)\b.{0,80}\b(?:alternative|'
    r'2030|2050|different|policy|climate|energy|econom\w*|migration|'
    r'likely|future|impact|decarboni\w*|change\w*|emissions?)\b', re.I)
CHANGE = re.compile(
    r'\b(?:rise|ris\w*|increas\w*|decreas\w*|declin\w*|grow\w*|'
    r'reduc\w*|chang\w*|shift\w*|alter\w*|evolv\w*|transform\w*|'
    r'impact\w*|affect\w*|expand\w*|shrink\w*|demand|supply|'
    r'consequences?|effects?|costs?|benefits?|threats?|challenges?|'
    r'vulnerab\w*|pressur\w*|opportunit\w*|risk\w*|need\w*|'
    r'role|capacity|constrain\w*|feasib\w*|trade.?offs?|'
    r'path\w*|option\w*|policy|governance|integration|security|'
    r'decarboni\w*|neutrality|distribution|mortality|exposure|'
    r'resilien\w*|adaptation|mitigation)\b', re.I)
FORWARD_RESULT = re.compile(
    r'\b(?:we (?:find|show|project|forecast|predict|envisage|conclude|expect|estimate)|'
    r'results? (?:show|indicat\w*|suggest\w*|reveal\w*|imply)|'
    r'(?:finding\w*|projection\w*|forecast\w*|scenario\w*) (?:show|indicat\w*|suggest\w*|'
    r'assum\w*|imply|predict\w*|reveal\w*)|'
    r'(?:is|are|was|were|be) (?:projected|predicted|expected|anticipated)|'
    r'(?:will|would|could|may|might|likely|expected to|potential to|'
    r'anticipated to|predicted to|projected to)\b)', re.I)
STUDY_QUESTION = re.compile(r'\b(?:we|this (?:study|paper|report|article|research)|the (?:study|analysis|paper|model|research))\b.{0,120}\b(?:assess\w*|analy[sz]\w*|'
                            r'explor\w*|evaluat\w*|examin\w*|investigat\w*|'
                            r'compar\w*|model\w*|simulat\w*|project\w*|'
                            r'forecas\w*|develop\w*|construct\w*|estim\w*)\b',re.I)
ASIDE = re.compile(r'\b(?:future research|future studies|further research|'
    r'future work|future directions|future investigation\w*|'
    r'call for further research in the future|research in the future|'
    r'directions for future)\b', re.I)
NEGATED_PROSPECT = re.compile(
    r'\b(?:does not|do not|did not|doesn.t|without|no)\b.{0,55}'
    r'\b(?:forecast|predict|project|compare|prospective|future|scenarios?|'
    r'alternatives?|modelling|modeling)\b', re.I)
METHOD_COMMENT = re.compile(
    r'\b(?:methodolog\w*|future\s+research\s+agenda|bibliometric\w*|'
    r'systematic (?:literature )?review|bibliograph\w*|meta.analysis|'
    r'current state of (?:research|the art)|compar\w* (?:methods?|techniques?)|'
    r'forecasting (?:accuracy|methods?|tools?|model performance)|'
    r'foresight\s+(?:practice\w*|method\w*|activities|capabilit\w*))\b', re.I)
NON_STUDY = re.compile(
    r'\b(?:retracted (?:article|paper)|retraction notice|withdrawn|'
    r'conference (?:announcement|abstracts?|programme)|special issue|'
    r'skills building seminar|summer seminar|faculty seminar|'
    r'symposium (?:programme|announcement)|'
    r'book review|response to|editorial|publisher.?s note|commentary on|'
    r'erratum|corrigendum|letters? to the editor|review of the book)\b|'
    r'^\s*review (?:of|on)\b|^\s*a review of\b', re.I)
OPERATIONAL = re.compile(
    r'\b(?:chemical weather forecast\w*|ionospheric perturbation\w*|'
    r'short.term weather forecast\w*|real.time prediction|'
    r'near.term predictions?|nowcasting|day.ahead|'
    r'daily load forecast\w*|week.ahead|intraday|'
    r'forecasting (?:model|performance|techniques?|algorithms?))\b', re.I)


def content(lead):
    for field in ('original_excerpt', 'publisher_description', 'abstract'):
        txt=' '.join(str(lead.get(field) or '').split())
        if len(txt.split()) >= 55:
            return txt, field
    return '', ''


def sentences(text):
    # Academic abstracts contain decimal values, acronyms and abbreviations;
    # splitting is best effort and never used as a correctness claim.
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+(?=[A-Z(])', text) if s.strip()]


def trace(lead):
    """Return (handoff dict | None, exclusion reason). Caller already tests EU/date.

    A source quote is always required; never fabricate a forecast from the title.
    """
    title=' '.join(str(lead.get('title') or '').split())
    try: published=int(str(lead.get('date',''))[:4])
    except ValueError: published=2023
    if NON_STUDY.search(title):
        return None, 'non_original_editorial_or_retracted'
    abstract, field = content(lead)
    if not abstract:
        return None, 'no_substantive_source_text_for_radar2'
    # Many non-foresight papers use the words future, risk, 'scenario', etc.
    # They must provide a forward *European development* or named alternative.
    title_future=bool(re.search(r'\b(?:foresight\w*|scenarios?|futures?|future of|'
                   r'forecast\w*|projections?|outlook|2030|2050|2040|'
                   r'transition\w*|pathways?)\b', title,re.I))
    if OPERATIONAL.search(title) and not HORIZON.search(title):
        return None, 'operational_or_methods_forecast_not_european_futures'
    if METHOD_COMMENT.search(title) and not HORIZON.search(title) and not re.search(
            r'\b(?:future of|scenarios? for|alternative futures|pathways to)\b',title,re.I):
        return None, 'foresight_method_or_background_not_future_development'
    if NON_STUDY.search(abstract[:130]):
        return None, 'non_original_editorial_or_retracted'
    eligible=[]
    sents=sentences(abstract)
    for idx, original in enumerate(sents):
        trimmed=ASIDE.sub(' ', original)
        if (len(original.split()) < 8 or len(original)>1200 or
                NEGATED_PROSPECT.search(trimmed) or not FUTURE.search(trimmed)):
            continue
        future=bool(re.search(r'\b(?:future|foresight|forecast\w*|project\w*|'
                         r'anticipat\w*|prospectiv\w*|scenarios?|pathways?|envisag\w*|'
                         r'20(?:2[4-9]|[3-9]\d)|2100|will|would|could|may|might|likely|should|recommends?)\b',trimmed,re.I))
        if not future:
            continue
        horizon=bool(HORIZON.search(trimmed))
        alternatives=bool(ALTERNATIVES.search(trimmed))
        change=bool(CHANGE.search(trimmed))
        result=bool(FORWARD_RESULT.search(trimmed))
        research=bool(STUDY_QUESTION.search(trimmed))
        # Score a *meaningful forward proposition* rather than generic mentions.
        # Two complementary routes: development/outcome claim, or explicit
        # alternative future/scenario with a European question and timeframe.
        score=0
        if horizon: score+=2
        if alternatives: score+=2
        if change: score+=1
        if result: score+=2
        if research: score+=1
        named_options=bool(re.search(r'\b(?:two|three|four|five|several|different|alternative)\s+(?:scenarios?|futures?|pathways?|options?)\b|\b(?:first|second|third)\s+(?:scenario|option|pathway)\b', trimmed, re.I))
        if named_options: score+=2
        strategy=bool(re.search(r'\b(?:should|ought to|must|need to|recommend\w*|'
                    r'policy options?|decision makers?|strategic (?:choices?|plans?|options?)|'
                    r'future roles?|will depend|could (?:be|lead|change))\b', trimmed, re.I))
        if strategy and (title_future or horizon or alternatives): score+=2
        if title_future and (alternatives or result or horizon) and change: score+=1
        if re.search(r'\b(?:2030|2040|2050|2060|2100)\b', trimmed): score+=1
        # Independent specific verbs override an incidental 'future research' hit.
        if re.search(r'\b(?:we (?:project|anticipate|estimate|model|simulate)|'
                     r'(?:results?|findings?) (?:suggest|indicate|show)|'
                     r'(?:may|might|could|would|will) (?:increase|decline|'
                     r'change|shape|affect|reduce|grow|drive|lead|result)|'
                     r'(?:policy|climate|economic|energy|population|migration|'
                     r'agricultural|security|employment|health) scenarios?)\b',trimmed,re.I):
            score+=2
        if score>=4 and (change or alternatives or strategy or named_options or (horizon and research)):
            # Source should describe future alternatives/consequences, not solely
            # an instrument for carrying out foresight.
            if METHOD_COMMENT.search(trimmed) and not (result or named_options or strategy or (horizon and change)):
                continue
            eligible.append((score,idx,original))
    if not eligible:
        # Some real scenarios distribute their question, alternatives and results
        # across different sentences rather than repeating "future" in each one.
        # Preserve such originals only if the whole description specifies the
        # investigation AND its forward object, alternatives or substantive stakes.
        abstract=' '.join(s for s in sents if not NEGATED_PROSPECT.search(s) and
                          not ASIDE.search(s))
        year_forward=any(int(y)>published for y in re.findall(r'\b20\d\d\b',title+' '+abstract))
        exact_future=bool(re.search(r'\b(?:project(?:ed|ions?|ing|s)?|'
            r'forecast(?:s|ed|ing)?|future|foresight\w*|horizon scanning|outlook|'
            r'scenarios?|pathways?|envisages?|anticipated|'
            r'prospective|visions?|2030|2050|2040|futur\w*|scénarios?|expected impact)\b',abstract,re.I))
        outputs=bool(re.search(r'\b(?:we (?:find|show|conclude|propose|estimate|project|model)|'
            r'(?:this|the) (?:study|paper|report|analysis) (?:finds|shows|concludes|'
            r'projects|models|estimates|proposes)|'
            r'findings?|results?|project(?:s|ed|ions?)|'
            r'forecast(?:s|ed|ing)?|future (?:role|development|trajectory|impact)|'
            r'expected impact|envisages?|scenario (?:analysis|framework|approach)|'
            r'multiple (?:scenarios|pathways)|'
            r'vision(?:s|ing)?|implications?|trade.?offs?|'
            r'risks?|alternative|2050|2030|2040)\b',abstract,re.I))
        meaningful_alternatives=bool(re.search(
            r'\b(?:two|three|four|five|six|several|different|alternative|'
            r'contrasting|plural|multiple)\s+(?:(?:food|energy|policy|climate)\s+)?'
            r'(?:futures?|scenarios?|pathways?|visions?|options?)\b|'
            r'\b(?:best|medium|worst|high|low|optimistic|pessimistic)[ -]case\b|'
            r'\b(?:first|second|third)\s+(?:scenario|option|pathway)\b|'
            r'\b(?:deux|trois|deux)\s+scénarios\b',abstract,re.I))
        outcome_or_stakes=bool(re.search(
            r'\b(?:emissions?|decarboni\w*|biodiversity|agricultur\w*|'
            r'food systems?|economic|growth|jobs?|employment|industrial|'
            r'energy|security|power|climat\w*|migration|demograph\w*|'
            r'health|disease|mortality|pensions?|integration|policy|'
            r'regulation|renewab\w*|trade|transport|mobility|'
            r'manufactur\w*|future roles?|impacts?|governance|technology|'
            r'innovations?|sustainab\w*|futur\w*|énergétique|'
            r'économ\w*|dépendance|renewable|investments?|'
            r'consumption|resilience|development|pollution|'
            r'medicines?|regulators?)\b',abstract,re.I))
        coherent_implicit_future=bool(year_forward and
            re.search(r'\b(?:models?|scenarios?|framework|inter.comparison)\b',abstract,re.I) and
            re.search(r'\b(?:2030|2040|2050|future|emissions?|climate|security)\b',abstract,re.I))
        target=bool((title_future or coherent_implicit_future) and exact_future and outcome_or_stakes and
            ((meaningful_alternatives and outputs) or
             (year_forward and outputs) or
             (title_future and re.search(r'\b(?:possible new roles|expected impact|25 technological trends|foresight exercise)\b',abstract,re.I) and outputs) or
             (re.search(r'\b(?:projections?|forecasts?|forecasted?|'
              r'projected|expected impact|futures?)\b',abstract,re.I) and
              re.search(r'\b(?:results?|findings?|we find|this paper|'
              r'conclud\w*|three|six|25 technological trends|'
              r'policy choices|implications?)\b',abstract,re.I))))
        if target:
            # Select the best *literal text* from the original description.
            # Never derive an unsupported new claim from its title.
            ranked=[]
            for idx, original in enumerate(sents):
                if len(original.split())<8 or NEGATED_PROSPECT.search(original): continue
                anchor=bool(FUTURE.search(original) or re.search(
                    r'\b(?:futur\w*|scénarios?|projected|forecas\w*|'
                    r'findings?|results?|we find|implications?)\b',original,re.I))
                if not anchor: continue
                strength=int(bool(FORWARD_RESULT.search(original)))*2
                strength+=int(bool(CHANGE.search(original)))
                strength+=int(bool(re.search(r'\b20\d\d\b',original)))*2
                strength+=int(bool(ALTERNATIVES.search(original)))*2
                strength+=int(bool(re.search(r'\b(?:two|three|four|five|six|'
                                 r'alternative|plausible|possible|different)\s+'
                                 r'(?:food )?(?:futures?|scenarios?|pathways?)\b',original,re.I)))*2
                ranked.append((strength,idx,original))
            if ranked:
                ranked.sort(key=lambda x:(-x[0],x[1]))
                eligible=[ranked[0]]
                for candidate in ranked[1:]:
                    if candidate[1]!=eligible[0][1] and len(eligible[0][2])+len(candidate[2])<900:
                        eligible.append(candidate)
                        break
    if not eligible:
        return None, 'no_traceable_european_future_proposition' 
    eligible.sort(key=lambda x:(-x[0],x[1]))
    primary=eligible[0]
    # Keep no more than two original sentences; never synthesize a prediction.
    excerpts=[primary[2]]
    if len(eligible)>1:
        second=next((row for row in eligible[1:] if row[1]!=primary[1]),None)
        if second and len(primary[2])+len(second[2])<1050:
            excerpts.append(second[2])
    quote=' '.join(excerpts)
    years=sorted({int(y) for y in re.findall(r'\b(?:20\d{2}|2100)\b', title+' '+quote) if int(y)>published})
    label=('alternative_scenarios' if ALTERNATIVES.search(quote) else
           'projection_or_forecast' if re.search(r'forecast|projec\w*|estimate|predict',quote,re.I) else
           'strategic_future_question')
    return {'source_field':field, 'source_status':'indexed_source_text_not_full_document_verified',
            'original_passage':quote, 'anticipated_horizons':years[:8],
            'investigation_type':label, 'traceability_version':VERSION}, 'checkable_forward_question_in_source_text'
