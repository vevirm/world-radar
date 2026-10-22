#!/usr/bin/env python3
"""Rolling Radar 2 research queue. Discovery drafts; never makes verdicts or publishes.

Selects different, genuinely future-facing Radar 1 originals across repeated runs.
Only tested question families may undergo evidence search. Unmapped originals
remain in the coverage audit: no keyword-only 'evidence' is fabricated.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
import json
import os
import re
from pathlib import Path

try:
    from .radar2_broad_search import discover
    from .radar2_scope import original_claims
    from .radar2_questions import question_card
    from .radar2_then_now import route_for as official_route_for, investigate as official_investigate, markdown as official_markdown
    from .radar2_claim_links import pick_plan
    from .radar2_ten_study_pilot import (historical_focus, classified, research, markdown,
        AUTHORED_FORECAST, SOURCE_STUDY, SUBSTANTIVE_TRAJECTORY, FUTURE)
except ImportError:
    from radar2_broad_search import discover
    from radar2_scope import original_claims
    from radar2_questions import question_card
    from radar2_then_now import route_for as official_route_for, investigate as official_investigate, markdown as official_markdown
    from radar2_claim_links import pick_plan
    from radar2_ten_study_pilot import (historical_focus, classified, research, markdown,
        AUTHORED_FORECAST, SOURCE_STUDY, SUBSTANTIVE_TRAJECTORY, FUTURE)

ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = 'radar2-rolling-state.json'
REPORT_FILE = 'RADAR2-ROLLING-RESEARCH.json'
MD_FILE = 'RADAR2-ROLLING-RESEARCH.md'


def load_state(path):
    if not Path(path).exists():
        return {'schema_version':1, 'completed':{}}
    state = json.loads(Path(path).read_text(encoding='utf-8'))
    if state.get('schema_version') != 1 or not isinstance(state.get('completed'), dict):
        raise ValueError('Unrecognised rolling state; stop rather than discard history')
    return state


def is_future_facing(claim):
    """Conservative source-backed *future proposition*, not generic future vocabulary."""
    passage = claim.get('original_passage') or ''
    if not claim.get('investigation_ready') or len(passage) < 110:
        return False
    focus = historical_focus(passage)
    return bool(len(focus) >= 55 and FUTURE.search(focus)
                and AUTHORED_FORECAST.search(passage)
                and SOURCE_STUDY.search(passage)
                and SUBSTANTIVE_TRAJECTORY.search(focus))


def prepare(root=ROOT, *, broad=False):
    accepted = original_claims(root)
    supported = []
    stats = Counter()
    for claim in accepted:
        stats['accepted'] += 1
        if claim.get('original_passage'):
            stats['passage_backed'] += 1
        plan = pick_plan(claim)
        if plan:
            stats['mapped'] += 1
        else:
            stats['unmapped'] += 1
        if not is_future_facing(claim):
            continue
        stats['future_facing'] += 1
        if not plan:
            stats['future_facing_unmapped'] += 1
            if not broad:
                continue
        # A broad keyword route may match an original whose *actual future claim*
        # discusses a different variable. Never search such a false match.
        focus = historical_focus(claim['original_passage'])
        anchored = claim['title'] + ' ' + focus
        if plan and not all(re.search(pattern, anchored, re.I) for pattern in plan['must']):
            stats['route_mismatch_requires_review'] += 1
            continue
        if plan: stats['future_facing_with_route'] += 1
        card = question_card(claim)
        if card['readiness'] in ('original_text_required','source_review_required'):
            stats['needs_original_review'] += 1
            continue
        supported.append({**claim, 'question_card':card,
                          'historical_focus':focus,
                          'topic_group':classified(claim['title']),
                          'route_id':plan['id'] if plan else 'general_multi_index'})
    return supported, dict(stats)


def choose_batch(supported, state, *, n=4, today=None):
    """Novel claims first, then oldest completed ones; diversify evidence routes."""
    if not 1 <= n <= 10:
        raise ValueError('Allowed bounded batch size is 1..10')
    today = today or date.today()
    completed = state['completed']
    def order(c):
        last = completed.get(c['id'])
        return (bool(last), last or '', c['original_publication'], c['id'])
    available = sorted(supported, key=order)
    # Give already-checked claims a rest for at least 90 days.
    candidates = [c for c in available if c['id'] not in completed or
                  (today-date.fromisoformat(completed[c['id']])).days >= 90]
    chosen=[]; used_routes=set()
    for c in candidates:
        if c['route_id'] not in used_routes:
            chosen.append(c);used_routes.add(c['route_id'])
        if len(chosen)>=n:
            break
    for c in candidates:
        if len(chosen)>=n:break
        if c['id'] not in {x['id'] for x in chosen}:
            chosen.append(c)
    return chosen


def updated_state(state, report, today):
    """Checkpoint only completed searches, not network failures or unsearchable cases."""
    new={'schema_version':1,'completed':dict(state['completed'])}
    for c in report.get('cases', []):
        if c.get('status') == 'question_level_empirical_leads_unverified' or c.get('status') == 'no_same_construct_evidence_in_bounded_openalex_search':
            # Both have completed tested searches, even when none yielded a lead.
            if c.get('queries_completed') and len(c['queries_completed']) == len(c.get('queries_attempted', [])):
                new['completed'][c['original_id']] = today.isoformat()
    return new


def run(root=ROOT, *, mode='inspect', batch_size=4, today=None, researcher=research, discoverer=discover):
    root = Path(root)
    today = today or date.today()
    state = load_state(root / STATE_FILE)
    ready, stats = prepare(root, broad=True) if mode in ('broad_inspect','broad_search') else prepare(root)
    selected = choose_batch(ready,state,n=batch_size,today=today)
    overview = {
        'schema_version':1,'mode':mode,
        'generated_utc':datetime.now(timezone.utc).isoformat(),
        'coverage':stats,'previous_completed_claims':len(state['completed']),
        'selected_originals':[{'id':c['id'],'title':c['title'],
                               'date':c['original_publication'],'route':c['route_id']}
                              for c in selected],
        'publication_allowed':False, 'verified_outcomes':0,
        'limitations':'General discovery uses OpenAlex, Crossref and Europe PMC and is not a comprehensive open-web search. Matches are unverified research leads, not established developments. Original claim coverage is incomplete.'}
    if mode == 'broad_search':
        items=[discoverer(c,api_key=os.environ.get('OPENALEX_API_KEY','')) for c in selected]
        overview['broad_discovery']={'cases':items, 'verified_outcomes':0}
        overview['status']='broad_discovery_draft_completed'
        # Checkpoint only when all three APIs return successfully.
        new={'schema_version':1,'completed':dict(state['completed'])}
        for item in items:
            if len(item.get('sources_checked',[]))==3 and not item.get('errors'):
                new['completed'][item['original_id']]=today.isoformat()
        (root / STATE_FILE).write_text(json.dumps(new,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    elif mode == 'search':
        if not selected:
            overview['status']='no_eligible_claims_due_for_search'
        else:
            key=os.environ.get('OPENALEX_API_KEY','').strip()
            if not key:
                raise ValueError('OPENALEX_API_KEY missing. Use inspect or configure GitHub secret.')
            report=researcher(selected,key)
            overview['search_report']=report
            # For original questions with an independently tested official source
            # route, also read actual later publisher passages. Other subjects
            # remain abstract-level research leads only.
            official_claims = [c for c in selected if official_route_for(c)]
            if official_claims:
                try:
                    overview['official_followups'] = official_investigate(official_claims)
                except Exception as exc:
                    overview['official_followup_error'] = f'{type(exc).__name__}: {str(exc)[:240]}'
            new_state=updated_state(state,report,today)
            (root / STATE_FILE).write_text(json.dumps(new_state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            overview['newly_completed_claims']=len(new_state['completed'])-len(state['completed'])
            overview['status']='search_draft_completed'
    elif mode in ('inspect','broad_inspect'):
        overview['status']='inspect_only_no_research_requests'
    (root / REPORT_FILE).write_text(json.dumps(overview,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines = ['# Radar 2 — rolling EU future-claim research', '',
             '**Draft research queue. No published or verified outcomes.**','',
             f'Mode: **{mode}**; accepted: **{stats["accepted"]}**; passage-backed: **{stats["passage_backed"]}**;',
             f'Mapped issue routes: **{stats["mapped"]}**; future-facing with usable route: **{stats["future_facing_with_route"]}**;',
             f'Future-facing but unmapped: **{stats.get("future_facing_unmapped",0)}**;',
             f'Previously completed research claims: **{len(state["completed"])}**.', '',
             '## Selected this run', '']
    for c in selected:
        lines.append(f'- {c["title"]} ({c["original_publication"][:4]}) — `{c["route_id"]}` — {c["source_url"]}')
    if not selected:lines.append('- None due (remaining supported claims need new routes or a later refresh).')
    lines += ['', '**Search limitations:** Question-specific later research is a discovery lead only. Each source, time period, measure and connection needs subsequent verification. Repeated checked items are eligible for refresh after 90 days.', '']
    if mode == 'broad_search':
        lines.extend(['','## Multi-index research leads (unverified)',''])
        for item in overview['broad_discovery']['cases']:
            lines.append(f"### {item['original_title']} — {item['status']}")
            lines.append(f"Indexes checked: {', '.join(item['sources_checked']) or 'none'}; leads: {len(item['leads'])}")
            for lead in item['leads']:
                lines.append(f"- [{lead['title']}]({lead['url']}) ({lead['published']}; {lead['index']}) — TOPIC MATCH ONLY")
            for error in item['errors']:
                lines.append(f"- Search error: {error['index']}: {error['error']}")
    if mode == 'search' and selected:
        lines.extend(['---','',markdown(report)])
        if overview.get('official_followups'):
            lines.extend(['---','', '## Live official-source passages (where available)', '',
                          official_markdown(overview['official_followups'])])
    (root / MD_FILE).write_text('\n'.join(lines),encoding='utf-8')
    return overview


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--mode',choices=('inspect','search','broad_inspect','broad_search'),default='inspect')
    p.add_argument('--batch-size',type=int,choices=range(1,11),default=4)
    args=p.parse_args(argv)
    out=run(args.root,mode=args.mode,batch_size=args.batch_size)
    print('Rolling Radar 2: '+out['status']+'; chosen '+str(len(out['selected_originals']))+
          '; tested routes '+str(out['coverage']['mapped'])+'; verified outcomes 0; no publishing.')

if __name__=='__main__':main()
