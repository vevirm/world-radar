"""No-scan, question-level vetting of Radar 2 later-development evidence.

This is an editorial REVIEW QUEUE, not an automatic facts verifier: a URL and
matching words never prove a source's contents. Only accepted Radar 1 originals
are eligible. Qualitative institutional foresight is allowed but needs a
traceable original passage before an outcome may be promoted.

Run: python scripts/radar2_evidence_review.py --input radar2-curated-evidence-pilot.json
Writes RADAR2-EVIDENCE-REVIEW.json and RADAR2-EVIDENCE-REVIEW.md, not active data.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]

# Do not confuse legislation / funding announcements with measured effects.
OBSERVED = {'independent_institutional_evaluation', 'market_observation',
            'retail_observation', 'independent_outcome_evaluation',
            'measurement', 'observed_outcome', 'evaluation', 'observed_development'}
ACTION = {'documented_policy_response', 'documented_implementation',
          'legislation', 'announced_project', 'funding_commitment', 'policy_action'}
MIXED = {'market_status_and_projection'}
PREDICTED = {'projection', 'forecast', 'new_scenario', 'target', 'ambition'}
NOISE = set('''about after against among around being case change changes dated
 development developments digital different during energy european europe
 europeans future futures green historical happened information into issue
 likely original possible question report research scenarios source strategic
 study studies subsequent that their them these this under union what where
 when which while with years year including further remain remains could might
 would should forecast projected potential markets systems policy policies
 future oriented original relevant assessments forecasts publication possible
 have has will then from areas into were within later look'''.split())
TOKEN = re.compile(r'[a-z][a-z0-9]{3,}', re.I)


def words(value):
    return {w for w in TOKEN.findall(str(value or '').lower()) if w not in NOISE}


def later_than_original(value, original):
    """Fail closed on undated material; year-only works only for later years."""
    m = re.fullmatch(r'(20\d\d)(?:-\d\d-\d\d)?', str(value or '').strip())
    if not m:
        return False
    try:
        o = date.fromisoformat(str(original)[:10])
        published = date.fromisoformat(value) if len(value) == 10 else None
    except ValueError:
        return False
    if published:
        return o < published <= date.today()
    return o.year < int(m.group(1)) <= date.today().year


def credible_link(url):
    try:
        u = urlparse(str(url or ''))
        return u.scheme == 'https' and bool(u.hostname) and '.' in u.hostname and not u.username
    except ValueError:
        return False


def evidence_role(kind):
    if kind in OBSERVED:
        return 'observed_or_evaluated'
    if kind in ACTION:
        return 'policy_or_implementation_action_not_outcome'
    if kind in MIXED:
        return 'mixed_observation_and_projection_needs_separation'
    if kind in PREDICTED:
        return 'later_projection_not_observed_outcome'
    return 'unclassified_needs_editorial_review'


def audit_case(case, originals):
    oid = str(case.get('original_id') or '')
    original = originals.get(oid)
    failures, cautions, checked = [], [], []
    if not original:
        return {'original_id':oid, 'title':case.get('title'), 'status':'rejected_original_not_accepted',
                'blockers':['Not in Radar 1 accepted originals'], 'warnings':[], 'evidence':[]}
    if str(case.get('original_url') or '').rstrip('/') != str(original.get('source_url') or '').rstrip('/'):
        failures.append('Pilot original URL does not match accepted source')
    if str(case.get('historical_date') or '')[:10] != str(original.get('original_publication') or '')[:10]:
        failures.append('Pilot original publication date differs from accepted source')
    if case.get('original_type') != original.get('source_kind'):
        failures.append('Original type differs from accepted manifest')
    if len(str(case.get('source_specific_proposition') or '').strip()) < 50:
        failures.append('No substantive source-specific original proposition')
    if len(str(case.get('radar2_question') or '').strip()) < 45:
        failures.append('No substantive, later-checkable question')
    if not str(case.get('scenario_condition') or '').strip():
        cautions.append('No original scenario condition or limitation recorded')
    passage = (original.get('original_passage') or '').strip()
    if not passage:
        failures.append('Accepted original lacks stored traceable passage; original source review required')
    # The saved abstract is a research starting point, not proof of a verbatim
    # forecast or of what an institutional PDF actually said.
    if original.get('source_kind') == 'academic' and passage:
        cautions.append('Original source passage from saved metadata; verify full text before final publication')
    proposition = str(case.get('source_specific_proposition') or '')
    core = words(proposition + ' ' + str(case.get('radar2_question') or ''))
    # Require continuity of an issue term with the historic title/passage,
    # not merely the word 'Europe' / 'scenario' / 'policy'.
    source_core = words((original.get('title') or '') + ' ' + passage)
    issue = core & source_core
    if not issue:
        failures.append('Proposition does not share a substantive object with accepted original title/passage')
    used = set()
    for item in case.get('findings') or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get('url') or '')
        kind = str(item.get('evidence_type') or '')
        role = evidence_role(kind)
        errs = []
        if not credible_link(url): errs.append('Invalid https source URL')
        if url.rstrip('/') == str(original.get('source_url') or '').rstrip('/'):
            errs.append('Historical original is not later independent evidence')
        if url in used: errs.append('Duplicate evidence source')
        used.add(url)
        if not later_than_original(str(item.get('year') or ''), original.get('original_publication')):
            errs.append('Evidence is not reliably dated later than the original')
        summary = str(item.get('evidence') or '').strip()
        document = str(item.get('document') or '').strip()
        if len(summary) < 35 or not document: errs.append('Insufficient source document and finding')
        shared = issue & words(document + ' ' + summary)
        if not shared:
            errs.append('Substantive continuity with source question not shown in evidence summary')
        if role == 'unclassified_needs_editorial_review':
            errs.append('Unrecognized evidence type')
        checked.append({'year':item.get('year'), 'document':document, 'url':url,
                        'finding_as_submitted':summary,'evidence_type':kind,'evidence_role':role,
                        'shared_issue_terms':sorted(shared), 'structural_errors':errs,
                        'source_checked_independently':False})
    if not checked:
        failures.append('No dated later evidence provided')
    if any(e['structural_errors'] for e in checked):
        failures.append('One or more supplied evidence records failed structural/question checks')
    valid = [e for e in checked if not e['structural_errors']]
    observed = sum(e['evidence_role'] == 'observed_or_evaluated' for e in valid)
    if not observed:
        cautions.append('No directly observed or evaluated results; policy actions and new projections are not outcomes')
    if not str(case.get('scope_caveat') or '').strip():
        cautions.append('Missing comparison scope caveat')
    if not str(case.get('assessment') or '').strip():
        cautions.append('No draft comparison narrative')
    status = ('blocked_for_original_or_evidence_review' if failures else
              'draft_has_structurally_usable_observations' if observed else
              'draft_actions_only_not_outcome')
    return {'original_id':oid, 'title':case.get('title'), 'source_kind':original.get('source_kind'),
            'original_url':original.get('source_url'),
            'question':case.get('radar2_question'), 'historical_proposition_as_submitted':proposition,
            'scenario_condition':case.get('scenario_condition'), 'draft_assessment':case.get('assessment'),
            'scope_caveat':case.get('scope_caveat'), 'status':status,
            'blockers':failures, 'warnings':cautions,
            'observed_or_evaluated_source_count':observed, 'evidence':checked,
            'publication_approval':'NOT APPROVED — editorial original/source verification required'}


def audit(root, input_path):
    try:
        from .radar2_scope import original_claims
    except ImportError:
        from radar2_scope import original_claims
    originals = {x['id']:x for x in original_claims(root)}
    raw = json.loads(Path(input_path).read_text(encoding='utf-8'))
    if not isinstance(raw, dict) or not isinstance(raw.get('cases'),list):
        raise ValueError('Expected JSON object containing cases list')
    cases = [audit_case(c,originals) for c in raw['cases']]
    ids = [x.get('original_id') for x in cases]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate original IDs in staged evidence')
    return {'schema_version':1, 'generated_utc':datetime.now(timezone.utc).isoformat(),
            'mode':'NO_SCAN_REVIEW_ONLY', 'accepted_originals':len(originals),
            'reviewed_pilot_cases':len(cases),
            'structurally_usable_drafts':sum(c['status']=='draft_has_structurally_usable_observations' for c in cases),
            'blocked':sum(c['status'].startswith(('blocked_','rejected_')) for c in cases),
            'publication_allowed':False,
            'limitations':'Automated structural and issue continuity checks do NOT fact-check the linked primary documents. All cases require human/source verification before publication.',
            'cases':cases}


def write_markdown(result, output):
    lines = ['# Radar 2 — dated evidence and original-question review', '',
             '**NO SCAN · NOT PUBLISHED · NO OUTCOMES VERIFIED BY THIS WORKFLOW**','',
             f"Accepted Radar 1 originals: **{result['accepted_originals']}** · Pilot cases: **{result['reviewed_pilot_cases']}** · Structurally usable drafts: **{result['structurally_usable_drafts']}** · Blocked: **{result['blocked']}**", '',
             result['limitations'], '']
    for c in result['cases']:
        lines.extend([f"## {c.get('title')}", '', f"**Review status:** {c['status']}", '',
                      f"**Historical question:** {c.get('historical_proposition_as_submitted','')}", '',
                      f"**What to check:** {c.get('question','')}", ''])
        for e in c['evidence']:
            lines.append(f"- {e['year']}: [{e['document']}]({e['url']}) — **{e['evidence_role']}**; {e['finding_as_submitted']}")
            if e['structural_errors']:
                lines.append('  - Needs correction: '+', '.join(e['structural_errors']))
        if c.get('draft_assessment'):
            lines.extend(['', '**Provisional comparison:** '+c['draft_assessment']])
        if c.get('scope_caveat'):
            lines.extend(['', '**Limitations:** '+c['scope_caveat']])
        if c.get('blockers'):
            lines.extend(['', '**Blocks:** '+ '; '.join(c['blockers'])])
        if c.get('warnings'):
            lines.extend(['', '**Review notes:** '+ '; '.join(c['warnings'])])
        lines.extend(['', '**Not approved for publication.**', ''])
    Path(output).write_text('\n'.join(lines)+'\n', encoding='utf-8')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--input',type=Path,default=ROOT/'radar2-curated-evidence-pilot.json')
    p.add_argument('--json-output',type=Path,default=ROOT/'RADAR2-EVIDENCE-REVIEW.json')
    p.add_argument('--md-output',type=Path,default=ROOT/'RADAR2-EVIDENCE-REVIEW.md')
    a=p.parse_args()
    result=audit(a.root,a.input)
    a.json_output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    write_markdown(result,a.md_output)
    summary = __import__('os').environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a',encoding='utf-8') as h:
            h.write(f"## Radar 2: source-evidence review (NO SCAN)\n\n- Accepted originals: **{result['accepted_originals']}**\n- Pilot cases: **{result['reviewed_pilot_cases']}**\n- Structurally usable (NOT verified): **{result['structurally_usable_drafts']}**\n- Blocked: **{result['blocked']}**\n- Not published. Download the report artifact to inspect each source.\n")
    print('No scan, no publishing:',result['reviewed_pilot_cases'],'cases,',result['blocked'],'blocked')

if __name__=='__main__': main()
