"""Turn every research lead into an honest, searchable THEN / NOW / DIRECTION / RELEVANCE record.

No automated record may claim observed real-world change from a title or a
possibly related paper. New editorial snapshots live in editorial-directions.json
with dated independent source links. Unknowns remain explicit and visible.
"""
from __future__ import annotations
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

THEME_DESCRIPTIONS = {
 'Climate and energy': ('From climate scenarios to the challenge of implementation',
    'Many studies model possible temperatures, energy systems, emissions and responses. A later model is an evolving idea; what actually happened needs historical measurements.'),
 'Technology and digital': ('From forecasts of change to questions of adoption',
    'Novel technologies and business behaviour need separate checks: research attention, policies, rollout, and everyday use are different evidence.'),
 'Population and work': ('Demographic possibilities, jobs and social change',
    'Demography may be projected long before it can be observed. Track assumptions, migration, labour-market data and dates instead of declaring a forecast won or lost.'),
 'Environment and food': ('What the future looks like outside the laboratory',
    'Forest, farming, food and biodiversity scenarios need ecosystem observations and changing policy context; many effects play out across decades.'),
 'Health and society': ('Risks and preparedness are not simple yes-or-no bets',
    'A scenario can identify vulnerabilities before they appear in statistics. Ask whether institutions planned, adapted and learned.'),
 'Economy and finance': ('The economy keeps rewriting the assumptions',
    'Distinguish models and conditions from subsequent prices, production, finance and policy decisions.'),
 'Security and governance': ('From long-term risks to changing policy priorities',
    'The relevance of strategic foresight can change after crises. Compare the framing then with later official choices, without assuming plans equal outcomes.'),
 'Other European foresight research': ('The questions that cross the boundaries',
    'A mixed shelf with ideas that may not fit a single theme. Classification is editorial navigation, not a verdict.'),
}


def tidy(value, max_chars=None):
    value = re.sub(r'\s+', ' ', str(value or '')).strip()
    return value if not max_chars or len(value)<=max_chars else value[:max_chars-1].rstrip()+'…'


def load(path, default):
    try: return json.loads((ROOT/path).read_text(encoding='utf-8'))
    except (OSError, ValueError): return default



def editorial_score(review):
    """Source-reviewed editorial quality score; no forced prediction outcome."""
    dims=('clarity','planning','direction_fit','current_relevance')
    points={k:review.get('dimensions',{}).get(k) for k in dims}
    usable={k:v for k,v in points.items() if type(v) is int and 1 <= v <= 100}
    links=review.get('sources') or []
    if len(usable)<2 or not review.get('original_text_reviewed') or not review.get('reviewed_by'):
        return None
    if len(tidy(review.get('scope')))<10 or len(tidy(review.get('reason')))<30:
        return None
    if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',tidy(review.get('reviewed_on'))):
        return None
    if not links or any(not str(x.get('url','')).startswith('https://') for x in links):
        return None
    if ('direction_fit' in usable or 'current_relevance' in usable) and (not review.get('later_sources_reviewed') or len(links)<2):
        return None
    return {'value':round(sum(usable.values())/len(usable)),
            'label':'Editorial quality assessment, NOT an outcome probability',
            'reason':tidy(review['reason'],500),'scope':tidy(review['scope'],260),
            'dimensions':usable,'reviewed_on':review['reviewed_on'],'sources':links}

def make_atlas(entries, *, leads=None, notes=None, observations=None, ratings=None, reviewed=None, generated_utc=None):
    if leads is None: leads = load('research-leads.json', {}).get('leads', [])
    if notes is None: notes = load('editorial-directions.json', {}).get('items', [])
    if observations is None: observations = load('outcome-observations.json', {}).get('observations', [])
    if ratings is None: ratings = load('editorial-assessments.json', {}).get('assessments', [])
    ratings_by_id = {x.get('lead_id'):x for x in ratings if x.get('lead_id')}
    notes = list(notes)
    for number, observation in enumerate(observations):
        sources = [x for x in observation.get('sources',[]) if str(x.get('url','')).startswith('https://')]
        if not (sources and observation.get('expected') and observation.get('happened')):
            continue
        topic = tidy(observation.get('topic','')).casefold()
        # Supersession is explicit rather than a topic-wide heuristic: adding
        # any NEW climate observation must not silently hide it from the atlas.
        if any(topic in [tidy(x).casefold() for x in n.get('supersedes_observation_topics', [])] for n in notes):
            continue
        notes.append({'id':f'policy-observation-{number}', 'title':observation['topic'],
            'tag':'Documented policy progress', 'then':observation['expected'],
            'now':observation['happened'],
            'direction':tidy(observation.get('verdict')) or 'The later direction has not been established.',
            'relevance':'This policy aim is still tracked; current relevance beyond the measured goal has not been separately reviewed.',
            'open_question':'How does the next comparable measurement change this picture?',
            'status':'Source-linked policy snapshot; not a prediction test', 'score':None, 'sources':sources})
    lookup = {tidy(e.get('source_url')).rstrip('/').lower(): e for e in entries if e.get('source_url')}
    # ONLY the separately source-reviewed registry can authorize claims of
    # observed real-world results. Automated evidence-search output is not
    # automatically reliable just because it has a URL or a status label.
    reviewed_by_id = {case.get('lead_id'): case for case in (reviewed or [])}
    records=[]
    for n, lead in enumerate(leads):
        source = tidy(lead.get('url'))
        entry = lookup.get(source.rstrip('/').lower(), {})
        title = tidy(lead.get('title') or entry.get('title'), 210)
        followups = []
        for f in entry.get('follow_up_publications') or []:
            if not str(f.get('url','')).startswith('https://'): continue
            followups.append({'title':tidy(f.get('title'),180), 'year':f.get('year'), 'url':f['url'],
                              'abstract_excerpt':tidy(f.get('finding_from_abstract'),300)})
        # Broader follow-on scholarship is useful for "where research is
        # going", but is NOT evidence that a specific scenario happened.
        developments = []
        direct_urls = {f['url'].rstrip('/').lower() for f in followups}
        for f in entry.get('field_developments') or []:
            link = str(f.get('url') or '').strip()
            if not link.startswith('https://') or link.rstrip('/').lower() in direct_urls:
                continue
            developments.append({'title':tidy(f.get('title'),180), 'year':f.get('year'),
                                 'url':link, 'source':f.get('source'),
                                 'abstract_excerpt':tidy(f.get('finding_from_abstract'),300)})
        # A separate issue-first trail: later abstracts may describe observed
        # change, practical implementation or merely an evolving research
        # question. Never confuse these with source-reviewed real-world facts.
        directions = []
        for f in entry.get('direction_evidence') or []:
            link = tidy(f.get('url'))
            if not link.startswith('https://'):
                continue
            directions.append({'title':tidy(f.get('title'),180), 'year':f.get('year'),
                               'url':link, 'abstract_excerpt':tidy(f.get('finding_from_abstract'),330),
                               'evidence_kind':f.get('evidence_kind'),
                               'interpretation':tidy(f.get('interpretation'),130),
                               'geography':f.get('geography'),
                               'source':f.get('source'), 'relationship':f.get('relationship')})
        # Scanner-proposed URLs remain in the private research logs. They are
        # NOT public real-world evidence until a source review accepts them.
        evidence = []
        approved = reviewed_by_id.get(entry.get('id'))
        verified_observation = bool(approved)
        thematic = tidy(entry.get('topic_cluster') or 'Other European foresight research')
        if thematic not in THEME_DESCRIPTIONS: thematic = 'Other European foresight research'
        if verified_observation:
            evidence = approved['observation']['sources']
            now = tidy(approved['observation']['what_happened'], 540)
            direction = tidy(approved.get('limitations'), 480) or 'Dated evidence is linked. Further direction has not been independently established.'
            relevance = 'Current relevance has not yet received a separate editorial review.'
            knowledge='Evidence recorded; full comparison still requires review'
        elif directions:
            # A plausible same-issue paper's abstract is a useful sign of
            # direction, not automatically an independently verified outcome.
            strongest = next((d for d in directions if d.get('evidence_kind') in
                              ('measured_or_reported_change','implementation_or_evaluation')), directions[0])
            y = strongest.get('year') or 'later'
            excerpt = tidy(strongest.get('abstract_excerpt'),250)
            kind = strongest.get('evidence_kind')
            # Readers need the actual later claim, not a boilerplate sentence.
            # Still attribute it to its published abstract: this is not an
            # independently verified historical verdict.
            if kind in ('implementation_or_evaluation', 'measured_or_reported_change'):
                if excerpt:
                    now = f'A {y} publication reports: “{excerpt}”'
                else:
                    now = f'A {y} publication discusses observed or implemented changes to this issue.'
                direction = ('An implementation or evaluation signal in later research.'
                             if kind == 'implementation_or_evaluation' else
                             'An observed or measured direction reported by later researchers.')
            elif kind == 'newer_scenario_or_model':
                now = f'A {y} study explores another possible direction: “{excerpt}”' if excerpt else f'A {y} study models further possibilities.'
                direction = 'The question is still evolving; the newer scenario is not an observed outcome.'
            else:
                now = f'A {y} study continues this research question: “{excerpt}”' if excerpt else f'A {y} study keeps this issue under discussion.'
                direction = 'Continued work on the subject, without a clear observed outcome in the available abstracts.'
            if strongest.get('geography') == 'region_not_specified':
                direction += ' Comparable geographic scope has not been established.'
            direction += ' The publication is a source-linked clue, not a final accuracy verdict.'
            relevance = f'The issue remains visible in research through {max((d.get("year") or 0) for d in directions)}; practical relevance may vary.'
            knowledge = 'Same-issue research trail; direction is provisional'
        elif followups or developments:
            combined = followups + developments
            n = len(combined)
            now = f'{n} newer publication(s) on a related subject identified. Their findings do not by themselves establish what happened in the world.'
            # Give the reader a dated academic trajectory, not a misleading
            # claim that a 2015 follow-up is "current" in 2026.
            reference = max(combined, key=lambda f: int(f.get('year') or 0))
            latest_year = max(int(f.get('year') or 0) for f in combined)
            direction = ('Newer research ('+str(reference.get('year') or 'date unknown')+') explores: '
                         + tidy(reference['title'], 165)+'. '
                         'This is the direction of scholarly discussion, not verified real-world change.')
            if latest_year >= datetime.now(timezone.utc).year - 3:
                relevance = (f'The question still appears in related research as recently as {latest_year}. '
                             'Its actual policy and practical relevance has not been independently reassessed.')
            else:
                relevance = ('Later academic discussion exists, but the current relevance of the original question '
                             'has not been checked.')
            knowledge = 'Newer research found; real-world direction not established'
        else:
            now = 'No later real-world outcome established in the saved research.'
            direction = 'Not established yet. The archive has not checked a comparable current indicator.'
            relevance = 'Not reassessed yet; this does not mean the topic is irrelevant.'
            knowledge = 'Needs an update'
        abstract=tidy(lead.get('abstract'),500)
        then = abstract or ('Original title is indexed, but the original argument is not available in the saved abstract. Read the source before attributing a position to its authors.')
        grade=editorial_score(ratings_by_id.get(entry.get('id'),{}))
        records.append({'id':entry.get('id') or f'catalogue-{n:04d}', 'title':title, 'year':tidy(lead.get('date') or entry.get('original_publication'))[:4],
            'topic':thematic,'journal':tidy(lead.get('journal') or lead.get('publisher'),90), 'original_url':source,
            'then':then,'now':now,'direction':direction,'relevance':relevance,'next_question':tidy(entry.get('watch_next')) or 'What independent dated data would show whether the idea still applies?',
            'knowledge':knowledge, 'screening':entry.get('screening_status',''), 'followups':followups, 'later_count':len(followups),
            'field_developments':developments, 'development_count':len(developments),
            'direction_trails':directions, 'direction_count':len(directions),
            'sources':evidence,'rating':grade,'kind':'indexed_research'})
    buckets=defaultdict(list)
    for r in records: buckets[r['topic']].append(r)
    themes=[]
    for topic,(headline,description) in THEME_DESCRIPTIONS.items():
        items=buckets.get(topic,[])
        themes.append({'topic':topic,'headline':headline,'intro':description,'count':len(items),
            'later_reading':sum(x['later_count']>0 or x['development_count']>0 for x in items),
            'related_field_updates':sum(x['development_count']>0 for x in items), 'outcome_evidence':sum(bool(x['sources']) for x in items),
            'example_titles':[x['title'] for x in items if x['later_count']][:4]})
    return {'generated_utc':generated_utc or datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        'editorial_as_of':load('editorial-directions.json',{}).get('reviewed_on',''),
        'method': 'Every indexed paper remains visible. Descriptions of later research are not real-world outcomes. Direction and relevance can be open questions. Editorial context snapshots are independent EU policy developments, not retroactively attributed to those papers.',
        'summary':{'total':len(records),'themes':len(themes),'compared_with_literature':sum(bool(x.get('literature_assessed_utc')) for x in entries),
            'with_later_reading':sum(x['later_count']>0 or x['development_count']>0 for x in records),
            'with_field_developments':sum(x['development_count']>0 for x in records),
            'with_same_issue_trails':sum(x['direction_count']>0 for x in records),
            'with_direct_later_reading':sum(x['later_count']>0 for x in records),
            'with_later_abstract_finding':sum(x.get('literature_signal')=='later_studies_report_results' for x in entries),
            'editorial_contexts':len(notes), 'original_abstracts':sum(bool(tidy(x.get('abstract'))) for x in leads)},
        'themes':themes,'editorial_context':notes,'records':records}


def write_atlas(entries, *, path=None, leads=None, notes=None, observations=None, ratings=None, reviewed=None):
    data=make_atlas(entries, leads=leads, notes=notes, observations=observations, ratings=ratings, reviewed=reviewed)
    target=Path(path) if path else ROOT/'living-atlas.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return data

if __name__=='__main__':
    source=load('retrospective-results.json',{}).get('entries',{})
    atlas=write_atlas(list(source.values()))
    print('Atlas built:',atlas['summary'])
