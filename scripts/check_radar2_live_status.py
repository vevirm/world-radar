"""Check that scheduled Radar 2 really searched a live provider (OpenAlex by default)."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / 'scanner2-audit.json'


def check_live_status(audit, allow_offline=False):
    run = audit.get('run', {})
    provider = run.get('provider')
    attempts = int(run.get('attempts') or 0)
    failed = int(run.get('failed') or 0)
    if provider in ('catalogue', 'evidence', None):
        if allow_offline:
            return 'Offline Word generation approved. Only previously indexed papers were compared; no fresh OpenAlex requests.'
        raise ValueError('No live research: use OpenAlex (default); check OPENALEX_API_KEY, API response or workflow arguments. '
                         'The report was generated and uploaded but was not freshly researched.')
    if provider not in ('openalex', 'openai'):
        raise ValueError('Unknown Radar 2 research provider: ' + str(provider))
    if not attempts or failed >= attempts:
        raise ValueError(f'Live research failed or was skipped: provider={provider}, '
                         f'attempts={attempts}, failed={failed}. Check API quota, credentials, and network logs.')
    if provider == 'openalex':
        return (f'OpenAlex live study comparisons executed: {attempts - failed} successful searches, '
                f'{failed} failures. Similar studies and abstract findings are provisional, not verified outcomes.')
    return (f'Live research executed: {attempts} attempts, {failed} failures. '
            'Evidence remains provisional until verified against source documents.')


if __name__ == '__main__':
    record = json.loads(AUDIT.read_text(encoding='utf-8'))
    try:
        message = check_live_status(record, os.getenv('ALLOW_OFFLINE_REPORT', '').lower() == 'true')
    except ValueError as exc:
        print('::error title=Radar 2 research incomplete::' + str(exc))
        raise SystemExit(1) from exc
    print(message)
