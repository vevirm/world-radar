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
    checked = [e for e in entries if e.get('checked_utc')]
    followups = [e for e in entries if e.get('follow_up_publications')]
    outlook = {
        'generated_utc': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        'headline': 'EU foresight — short outlook',
        'verdict': ('Follow-up evidence has been recorded for ' + str(len(supported)) + ' research leads.' if supported else 'European foresight research is being collected, but independently sourced follow-up developments have not yet been established.'),
        'study_count': len(leads), 'lead_count': len(leads),
        'tracked_count': len(entries), 'checked_count': len(checked), 'follow_up_count': len(followups),
        'evidence_backed_count': len(supported), 'topic_counts': dict(topics.most_common(25)),
        'themes': [{'topic': t, 'study_count': n, 'signal': 'Research lead; see the Excel catalogue.'} for t,n in topics.most_common(6)],
        'interpretation': 'This is a small overview of the research being monitored and independently observed changes, not a claim that every research lead made a testable prediction.',
        'next_step': f'Scanner 2 checked {len(checked)} leads; {len(followups)} have possible later research links. These are research trails, not observed real-world outcomes.',
    }
    OUT.write_text(json.dumps(outlook, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return outlook
