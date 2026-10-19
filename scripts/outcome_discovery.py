"""Discover real-world developments published since June 2026.

Radar 1 supplies historical ideas and topic clues; Radar 2 searches for actual
outcomes (events, measurements, observed changes). Headlines are only leads.
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import quote

from outcome_tracker import ROOT, SINCE, fetch_rss, load, make_report, save
from outcome_scoring import assess

STOP = set('the and for from with into over under that this will would could might have been about future europe european union report study analysis research towards years year policy scenario scenarios foresight projection projections expected economic economy trends 2020 2021 2022 2023 2024 2025 2026 2030 2040 2050'.split())
TOPICS = [
    'EU population demographic projections', 'EU energy demand renewable transition forecasts',
    'EU employment labour market trends', 'EU artificial intelligence regulation impact',
    'EU climate adaptation impacts scenarios', 'EU migration projections',
    'European industry competitiveness forecasts', 'Europe defence spending projections',
    'Euro area economic outlook inflation projections', 'EU agriculture food supply forecasts',
    'European housing affordability projections', 'European health ageing demographic forecasts',
    'European education skills future labour market', 'European transport electric vehicles forecasts',
    'European digital transformation futures', 'European biodiversity environmental outlook',
]
DIRECTION = ('will ', 'project', 'forecast', 'expect', 'predict', 'by 20', 'could ', 'likely ', 'may ', 'risk of', 'scenario', 'anticipat')


def keywords(text, n=7):
    terms = re.findall(r"[a-zA-Z][a-zA-Z'-]{3,}", text.lower())
    out = []
    for term in terms:
        term = term.strip("-'")
        if term not in STOP and term not in out:
            out.append(term)
    return out[:n]


def discovered_ideas():
    """Import anchored original claims, distinguish leads without an extracted claim."""
    ideas = {x['id']: x for x in load(ROOT / 'future-ideas.json', [])}
    findings = load(ROOT / 'findings.json', {}).get('findings', [])
    for record in findings:
        text = record.get('comparison', {}).get('foresight_claim') or record.get('finding', '')
        bits = re.split(r'(?<=[.;])\s+', re.sub(r'\s+', ' ', text))
        claim = next((x.strip() for x in bits if any(k in x.lower() for k in DIRECTION) and len(x) >= 55), '')
        if not claim:
            continue
        key = 'auto-' + hashlib.sha256((record.get('url', '') + claim).encode()).hexdigest()[:15]
        if key in ideas:
            continue
        terms = keywords(claim + ' ' + record.get('topic', ''))
        if not terms:
            continue
        ideas[key] = dict(id=key, target_year='Unspecified', title=record.get('title', 'Research claim'),
            claim=claim[:450], source_url=record.get('full_text_url') or record.get('url', ''),
            search_query='EU Europe ' + ' '.join(terms[:5]), match_phrases=terms[:4],
            support_signals=[], refute_signals=[], origin='Existing verified foresight finding',
            assessment_note='No directional phrases configured; a human must interpret the new evidence.')
    # Priority-50 entries are original-source leads only; do not make up predictions.
    priority = load(ROOT / 'priority-50.json', {}).get('items', [])
    return list(ideas.values()), priority


def lookup_queries(idea):
    base = idea.get('search_query', '')
    terms = keywords(idea.get('claim', '') + ' ' + idea.get('title', ''))
    phrase = ' '.join(terms[:6])
    for s in (base, f'"{phrase}" EU data 2026' if phrase else '',
              f'EU {" ".join(terms[:4])} actual statistics 2026',
              f'EU {" ".join(terms[:4])} latest report 2026',
              f'EU {" ".join(terms[:4])} forecast revised'):
        if s.strip():
            yield s.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--minutes', type=float, default=19, help='Network scan budget in minutes (default 19; workflow cap 22)')
    ap.add_argument('--max-queries', type=int, default=500)
    ap.add_argument('--offline', action='store_true')
    args = ap.parse_args()
    start = time.monotonic()
    deadline = start + max(0, args.minutes) * 60
    ideas, priority = discovered_ideas()
    state_path = ROOT / 'outcome-history.json'
    state = load(state_path, {'since': SINCE.isoformat(), 'ideas': {}})
    state.setdefault('ideas', {})
    state.setdefault('discoveries', [])
    state.setdefault('query_log', {})
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    seen_new = {x['url'] for x in state['discoveries']}
    tasks = []
    # Radar 2 finds what ACTUALLY HAPPENED, not new historical predictions.
    # Each independent topic is covered through measured changes and events.
    for topic in TOPICS:
        for outcome_type in ('2026 official statistics measured results',
                             '2026 new data developments evidence',
                             '2026 actual changes events reported'):
            tasks.append(('discover', None, f'EU Europe {topic} {outcome_type}'))
    # Search dynamically from ALL imported claims, and independently from priority research.
    for idea in ideas:
        for q in lookup_queries(idea):
            tasks.append(('idea', idea, q))
    for record in priority:
        terms = keywords(record.get('title', ''), 5)
        if terms:
            tasks.append(('discover', None, f'EU {" ".join(terms)} outcomes 2026'))
    # Broaden discovery using scholarly-lead subject terms; leads provide search
    # vocabulary only, never automatically count as verified predictions.
    for lead in load(ROOT / 'research-leads.json', {}).get('leads', [])[:350]:
        terms = keywords(lead.get('title', '') + ' ' + lead.get('abstract', ''), 6)
        if len(terms) >= 3:
            tasks.append(('discover', None, f'EU Europe {" ".join(terms[:5])} actual outcomes data 2026'))
    # Broader, fresh real-world coverage even where Radar 1 has no matching idea.
    for subject in ('industry jobs', 'AI deployment', 'electricity generation',
                    'migration flows', 'births deaths population', 'trade imports exports',
                    'climate extreme weather', 'public health', 'European defence',
                    'energy prices', 'housing construction', 'agriculture production'):
        tasks.append(('discover', None, f'EU Europe {subject} actual 2026 data report'))
    # Rotate starting query across runs to avoid always sampling the same first page.
    cursor = int(state.get('query_cursor', 0)) % max(1, len(tasks))
    tasks = tasks[cursor:] + tasks[:cursor]
    performed = 0
    failed = 0
    added = 0
    for i, (mode, idea, query) in enumerate(tasks[:max(0, args.max_queries)]):
        if args.offline or time.monotonic() >= deadline - 16:
            break
        try:
            items = list(fetch_rss(query, timeout=min(12, max(2, int(deadline - time.monotonic() - 1)))))
            for item in items:
                item['collected_utc'] = now
                item['query'] = query
                if mode == 'discover':
                    if item['url'] not in seen_new:
                        item['status'] = 'Potential real-world development — not yet independently verified'
                        state['discoveries'].append(item)
                        seen_new.add(item['url'])
                        added += 1
                else:
                    # relevance based on topic keywords; headlines alone do not prove outcomes.
                    terms = keywords(idea.get('claim', '') + ' ' + idea.get('title', ''))
                    if terms and not any(t in item['headline'].lower() for t in terms[:6]):
                        continue
                    entry = state['ideas'].setdefault(idea['id'], {'evidence': []})
                    known = {v['url'] for v in entry['evidence']}
                    if item['url'] not in known:
                        entry['evidence'].append(item)
                        added += 1
            performed += 1
            state['query_log'][query] = {'last_checked_utc': now, 'returned': len(items)}
        except Exception as exc:
            failed += 1
            print(f'RSS failed for {query[:60]}: {exc}', flush=True)
        if (i + 1) % 15 == 0:
            print(f'Progress: {i+1} queries; +{added} evidence/discovery leads', flush=True)
            save(state_path, state)
    state['query_cursor'] = (cursor + performed + failed) % max(1, len(tasks))
    state['last_run_utc'] = now
    state['last_scan'] = {'attempted_queries': performed + failed, 'successful_queries': performed,
                          'failed_queries': failed, 'new_items': added,
                          'seconds': round(time.monotonic() - start, 1),
                          'ideas': len(ideas), 'unverified_discoveries': len(state['discoveries'])}
    state['discoveries'] = state['discoveries'][-12000:]
    for entry in state['ideas'].values():
        entry['evidence'] = sorted(entry.get('evidence', []), key=lambda e: (e['date'], e['url']))[-800:]
    save(state_path, state)
    save(ROOT / 'outcome-ideas-auto.json', {'generated_utc': now, 'ideas': ideas,
         'description': 'Automatically imported source-anchored claims; do not treat scenarios as confirmed predictions.'})
    make_report(ideas, state, ROOT / 'stuff' / 'FUTURE_IDEAS_WHAT_HAPPENED.docx')
    print(json.dumps(state['last_scan'], indent=2), flush=True)


if __name__ == '__main__':
    main()
