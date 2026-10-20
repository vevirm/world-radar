"""Compact, evidence-honest radar overview for Word and website."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outlook-summary.json'


def load(path, default):
    try:
        return json.loads((ROOT / path).read_text(encoding='utf-8'))
    except (FileNotFoundError, ValueError):
        return default


def create(entries):
    leads = load('research-leads.json', {}).get('leads', [])
    topics = Counter((lead.get('journal') or lead.get('publisher') or 'Unclassified') for lead in leads)
    supported = [e for e in entries if e.get('evidence') or e.get('counterevidence')]
    checked = [e for e in entries if e.get('evidence') or e.get('counterevidence') or e.get('literature_assessed_utc')]
    bibliography_checked = [e for e in entries if e.get('bibliography_checked_utc') or e.get('checked_utc')]
    candidates = [e for e in entries if e.get('screening_status') == 'candidate_needs_validation']
    followups = [e for e in entries if e.get('follow_up_publications')]
    compared = [e for e in entries if e.get('literature_assessed_utc')]
    empirical = [e for e in compared if e.get('literature_signal') == 'later_studies_report_results']
    topic_coverage = Counter(e.get('topic_cluster', 'Unclassified') for e in compared)
    topic_followups = Counter(e.get('topic_cluster', 'Unclassified') for e in compared if e.get('follow_up_publications'))
    topic_result_passages = Counter(e.get('topic_cluster', 'Unclassified') for e in empirical)
    outlook = {
        'generated_utc': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        'headline': 'EU foresight — evidence review',
        'verdict': (f'{len(compared)} European research leads compared with later scholarship; {len(followups)} have related papers, {len(empirical)} contain later abstract-reported results. No verified EU-foresight accuracy score yet.' if compared else 'European foresight research is being collected; no literature comparison has been completed yet.'),
        'literature_compared_count': len(compared),
        'later_abstract_result_count': len(empirical),
        'later_empirical_abstract_count': len(empirical),  # legacy key, not a verification count
        'theme_comparisons': [
            {'topic': name, 'compared': n, 'with_related_later_study': topic_followups[name],
             'with_later_abstract_result': topic_result_passages[name]}
            for name, n in topic_coverage.most_common()],
        'study_count': len(leads), 'lead_count': len(leads),
        'tracked_count': len(entries), 'checked_count': len(checked), 'bibliography_checked_count': len(bibliography_checked), 'forecast_candidate_count': len(candidates), 'follow_up_count': len(followups),
        'evidence_backed_count': len(supported), 'topic_counts': dict(topics.most_common(25)),
        'themes': [{'topic': t, 'study_count': n, 'signal': 'Research lead; see the Excel catalogue.'} for t,n in topics.most_common(6)],
        'interpretation': 'Thematic comparisons are from scientific abstracts; some describe modeled futures, not observed real-world outcomes. Research about Europe is not necessarily EU-institution-authored foresight. Neither topic matches nor abstract results are forecast accuracy verdicts.',
        'next_step': f'{len(compared)} records now have qualitative comparisons with later scholarly papers, including {len(empirical)} with a result-like passage in a later abstract. No EU-foresight accuracy score is justified yet. {len(candidates)} original abstracts contain potential forecast passages requiring validation. {len(bibliography_checked)} leads received bibliographic searches; {len(supported)} have separately dated outcome evidence. Bibliographic searches are not outcome verification.',
    }
    OUT.write_text(json.dumps(outlook, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return outlook
