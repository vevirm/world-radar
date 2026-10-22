#!/usr/bin/env python3
"""Bounded OpenAlex follow-up discovery for three ACCEPTED Radar 1 originals.

No OpenAI key, generative model, writeback, or publishing. OpenAlex returns
bibliographic metadata and indexed abstracts, NOT verified observed outcomes.
The existing curated source review checks official/public evidence separately.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

try:
    from .radar2_scope import original_claims
    from .radar2_questions import question_card
    from .openalex_comparison import request_works, candidate_from_work, query_for
    from .radar2_evidence_review import credible_link, later_than_original
except ImportError:
    from radar2_scope import original_claims
    from radar2_questions import question_card
    from openalex_comparison import request_works, candidate_from_work, query_for
    from radar2_evidence_review import credible_link, later_than_original

ROOT = Path(__file__).resolve().parents[1]
PILOT_IDS = (
    'lead-726d2d4ffd64aca7',  # hydrogen decarbonisation scenarios
    'lead-9363d7d494bf528e',  # organic-food market futures
    'lead-571fb03297fcebcc',  # European migration-policy scenarios
)
MAX_QUERIES_PER_ORIGINAL = 2
MAX_CANDIDATES_PER_ORIGINAL = 5


def select_originals(root=ROOT, ids=PILOT_IDS):
    """Fail closed if the live Radar 1 acceptance manifest changed."""
    originals = {r['id']: r for r in original_claims(root)}
    selected = []
    for oid in ids:
        if oid not in originals:
            raise ValueError(f'Pilot original no longer accepted by Radar 1: {oid}')
        claim = dict(originals[oid])
        card = question_card(claim)
        if not claim.get('original_passage') or card['readiness'] in (
                'source_review_required', 'original_text_required'):
            raise ValueError(f'Pilot original needs better original text: {oid}')
        claim['research_question'] = card['evidence_question']
        claim['issue_anchors'] = card['issue_anchors']
        selected.append(claim)
    return selected


def discovery_queries(claim):
    """Short, distinctive issue queries from original title/passage, not claims about outcomes."""
    source = {**claim, 'candidate_excerpt': claim['original_passage']}
    queries = []
    for route in (0, 1, 2):
        query = re.sub(r'\s+', ' ', query_for(source, route=route)).strip()
        if query and query.casefold() not in {q.casefold() for q in queries}:
            queries.append(query)
        if len(queries) >= MAX_QUERIES_PER_ORIGINAL:
            break
    return queries


def filter_candidate(claim, work):
    """Bibliographic screening, explicitly NOT full-text source verification."""
    hit = candidate_from_work(claim, work, origin='openalex_live_three_pilot')
    if not hit:
        return None
    if not credible_link(hit.get('url')):
        return None
    if not later_than_original(hit.get('date'), claim.get('original_publication')):
        return None
    # Enforce an issue-bearing title overlap, not merely Europe/future/policy.
    shared = hit.get('shared_topic_terms') or []
    if len(shared) < 2:
        return None
    # OpenAlex abstract text is attributable to the paper's authors.  Even a
    # result-sounding sentence might be modelled, not an observed outcome.
    return {
        'title': hit['title'], 'url': hit['url'], 'date': hit['date'],
        'publication_year': hit['year'],
        'shared_topic_terms': shared,
        'study_type_from_abstract': hit.get('study_type'),
        'reported_sentence_from_indexed_abstract': hit.get('finding_from_abstract') or '',
        'bibliographic_source': 'OpenAlex works API',
        'same_substantive_question_verified': False,
        'observed_development_verified': False,
        'source_checked_independently': False,
        'review_status': 'candidate_for_full_source_and_outcome_review',
    }


def research(claims, key, searcher=request_works):
    """Up to 6 OpenAlex searches total; isolated artifact, no data mutation.

    `searcher` is injected in offline tests. The production OpenAlex client
    reads OPENALEX_API_KEY from the environment when building its HTTPS call.
    """
    if not key:
        raise ValueError('OPENALEX_API_KEY not configured; no live requests made')
    results = []
    for claim in claims:
        queries = discovery_queries(claim)
        row = {
            'original_id': claim['id'], 'source_kind': claim['source_kind'],
            'title': claim['title'], 'original_url': claim['source_url'],
            'original_publication': claim['original_publication'],
            'original_passage': claim['original_passage'],
            'historical_question': claim['research_question'],
            'issue_anchors': claim['issue_anchors'],
            'search_queries': queries, 'queries_completed': 0,
            'candidate_followups': [],
            'research_status': 'not_started',
            'outcome_assessment': 'NOT ASSESSED — bibliographic leads only',
            'publication_allowed': False,
        }
        matches = {}
        errors = []
        # Deliberately request works in subsequent *years*, not same-year
        # publications whose exact sequence might be ambiguous.
        since_year = int(str(claim['original_publication'])[:4]) + 1
        for query in queries:
            try:
                works = searcher(query, since_year)
                if not isinstance(works, list):
                    raise ValueError('OpenAlex returned an unexpected response')
                row['queries_completed'] += 1
                for work in works:
                    if not isinstance(work, dict):
                        continue
                    hit = filter_candidate(claim, work)
                    if hit:
                        # One record per DOI/URL, even across multiple searches.
                        key_url = hit['url'].rstrip('/').casefold()
                        prior = matches.get(key_url)
                        if not prior or (bool(hit['reported_sentence_from_indexed_abstract']),
                                         hit['publication_year']) > (
                                  bool(prior['reported_sentence_from_indexed_abstract']),
                                  prior['publication_year']):
                            matches[key_url] = hit
            except Exception as exc:
                # Preserve errors rather than misreporting unavailable searches
                # as no evidence existing in the real world.
                errors.append(f'{type(exc).__name__}: {str(exc)[:200]}')
        row['candidate_followups'] = sorted(
            matches.values(),
            key=lambda hit: (bool(hit['reported_sentence_from_indexed_abstract']),
                             len(hit['shared_topic_terms']), hit['publication_year']),
            reverse=True)[:MAX_CANDIDATES_PER_ORIGINAL]
        row['candidate_count'] = len(row['candidate_followups'])
        if errors:
            row['research_status'] = 'partial_search_error' if row['queries_completed'] else 'search_failed'
            row['search_errors'] = errors
        elif row['candidate_count']:
            row['research_status'] = 'bibliographic_candidates_for_review'
        else:
            row['research_status'] = 'no_close_candidate_in_bounded_openalex_search'
        results.append(row)

    return {
        'schema_version': 2, 'mode': 'OPENALEX_THREE_ORIGINALS_DRAFT_ONLY',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'originals_considered': len(claims),
        'queries_completed': sum(c['queries_completed'] for c in results),
        'candidate_followups_found': sum(c['candidate_count'] for c in results),
        'cases_with_search_errors': sum(c['research_status'] in ('partial_search_error', 'search_failed') for c in results),
        'source_verified_outcomes': 0, 'published_outcomes': 0,
        'publication_allowed': False,
        'warning': 'OpenAlex abstracts identify possible later research, NOT verified real-world developments. Original passage, source, geography, baseline, methodology and observed measurements all require editorial checks. No match does NOT mean no developments.',
        'cases': results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, default=Path('RADAR2-LIVE-RESEARCH-DRAFT.json'))
    args = parser.parse_args()
    claims = select_originals(args.root)
    key = os.getenv('OPENALEX_API_KEY', '').strip()
    result = research(claims, key)
    target = args.output if args.output.is_absolute() else args.root / args.output
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f"Radar 2 OpenAlex pilot: {result['candidate_followups_found']} bibliographic candidates; 0 verified outcomes", flush=True)
    summary = os.getenv('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as output:
            output.write('## Radar 2: three-original OpenAlex research (DRAFT ONLY)\n\n')
            output.write(f"- Completed OpenAlex searches: **{result['queries_completed']}**\n")
            output.write(f"- Later paper candidates: **{result['candidate_followups_found']}**\n")
            output.write('- **0 verified outcomes; no published results or dataset changes**\n')
            output.write('- Download the artifact to review source titles, DOIs and caveats.\n')
    if result['cases_with_search_errors']:
        raise SystemExit('One or more OpenAlex searches failed; partial draft artifact was retained')


if __name__ == '__main__':
    main()
