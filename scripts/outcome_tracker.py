"""Lightweight cumulative post-June-2026 evidence watcher for past foresight ideas.

Run: python scripts/outcome_tracker.py
Uses Google News RSS as a discovery channel (not as proof); stores distinct dated
headlines across runs and exports a short Word document. No LLM/API key needed.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from outcome_scoring import assess, classify

ROOT = Path(__file__).resolve().parents[1]
SINCE = dt.date(2026, 6, 1)


def load(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def parse_day(raw):
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(raw).date()
    except (TypeError, ValueError, IndexError):
        return None


def fetch_rss(query, timeout=16):
    query = f'{query} after:{SINCE.isoformat()}'
    url = 'https://news.google.com/rss/search?' + urllib.parse.urlencode({
        'q': query, 'hl': 'en', 'gl': 'EU', 'ceid': 'EU:en'
    })
    req = urllib.request.Request(url, headers={'User-Agent': 'WorldRadarOutcomeTracker/1.0 (+research; RSS)'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        root = ET.fromstring(response.read(1_500_000))
    for item in root.findall('./channel/item'):
        title = (item.findtext('title') or '').strip()
        link = (item.findtext('link') or '').strip()
        date = parse_day(item.findtext('pubDate'))
        if title and link and date and SINCE <= date <= dt.date.today():
            yield {'date': date.isoformat(), 'headline': title, 'url': link}


def relevant(item, idea):
    title = item['headline'].casefold()
    # At least two identifying words or one configured exact phrase must occur;
    # this filters irrelevant RSS matches without pretending to understand claims.
    phrases = [p.casefold() for p in idea.get('match_phrases', []) if p.strip()]
    return any(p in title for p in phrases) if phrases else True


def short_verdict(result):
    score = result['score']
    if result['basis'] == 'No directional evidence (placeholder)':
        return 'Unclear (insufficient evidence)'
    return ('Mostly contradicted' if score <= 25 else 'Leaning contradicted' if score < 45
            else 'Mixed / unresolved' if score <= 55 else 'Leaning supported' if score < 75
            else 'Mostly supported')


def make_report(ideas, state, path):
    from docx import Document
    from docx.shared import Pt, Inches
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(.8)
    section.bottom_margin = Inches(.8)
    doc.add_heading('Future ideas — what happened?', 0)
    p = doc.add_paragraph(f'Evidence collected from {SINCE.isoformat()} through {dt.date.today().isoformat()}; cumulative across runs.')
    p.style = 'Subtitle'
    for idea in ideas:
        evidence = state.get('ideas', {}).get(idea['id'], {}).get('evidence', [])
        evidence = sorted(evidence, key=lambda x: x['date'], reverse=True)
        doc.add_heading(f"{idea['target_year']} · {idea['title']}", level=2)
        doc.add_paragraph('Idea: ' + idea['claim'].strip().rstrip('.') + '.')
        result = assess(evidence, idea)
        counts = result['counts']
        label = short_verdict(result)
        doc.add_paragraph(f"What happened: {result['score']}/100 — {label}; {counts['support']} supporting, {counts['refute']} contradicting and {counts['mixed']} mixed headline signals since June 2026.")
        doc.add_paragraph('Basis: ' + result['basis'] + '. ' + (idea.get('reviewed_note', '') if result['basis'] == 'Human-reviewed' else 'Signal matches do not establish facts; open the underlying sources before trusting this score.'))
        if evidence:
            # Show the most recent source from each direction when available.
            for direction in ('support', 'refute', 'mixed'):
                match = next((x for x in evidence if classify(x, idea) == direction), None)
                if match:
                    p = doc.add_paragraph(f"{direction.title()} lead ({match['date']}): {match['headline']} — {match['url']}")
                    p.style = 'Caption'
        if evidence:
            p = doc.add_paragraph()
            run = p.add_run('Latest source: ' + evidence[0]['url'])
            run.font.size = Pt(8)
        if idea.get('source_url'):
            p = doc.add_paragraph()
            run = p.add_run('Original idea: ' + idea['source_url'])
            run.font.size = Pt(8)
    doc.add_paragraph('Method: 1 = contradicted, 100 = fully supported, 50 = unknown/mixed. Automatic scores are provisional: start at 50, add 10 per supporting headline and subtract 10 per contradicting headline (range 10–90). Headlines are discovery leads, not verified outcomes; repeated reporting may bias scores. For reviewed primary-source assessments, set reviewed_score (1–100) and reviewed_note in future-ideas.json. A future target year can only be provisionally assessed today.')
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--offline', action='store_true', help='Rebuild Word report without fetching RSS')
    args = parser.parse_args()
    ideas = load(ROOT / 'future-ideas.json', [])
    state_file = ROOT / 'outcome-history.json'
    state = load(state_file, {'since': SINCE.isoformat(), 'ideas': {}})
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    for idea in ideas:
        entry = state.setdefault('ideas', {}).setdefault(idea['id'], {'evidence': []})
        seen = {x['url'] for x in entry['evidence']}
        added = 0
        if not args.offline:
            try:
                for item in fetch_rss(idea['search_query']):
                    if item['url'] not in seen and relevant(item, idea):
                        item['collected_utc'] = now
                        entry['evidence'].append(item)
                        seen.add(item['url'])
                        added += 1
            except Exception as exc:
                print(f"{idea['id']}: RSS unavailable ({exc}); preserving saved evidence")
        entry['evidence'].sort(key=lambda x: (x['date'], x['url']))
        entry['last_checked_utc'] = now if not args.offline else entry.get('last_checked_utc')
        print(f"{idea['id']}: +{added}, {len(entry['evidence'])} total; {assess(entry['evidence'], idea)['score']}/100")
    save(state_file, state)
    target = ROOT / 'stuff' / 'FUTURE_IDEAS_WHAT_HAPPENED.docx'
    make_report(ideas, state, target)
    print('Created', target)


if __name__ == '__main__':
    main()
