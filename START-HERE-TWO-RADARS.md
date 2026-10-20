# Two radars — two runs each daily

**Radar 1** (`update-radar.yml`): 01:17 and 13:17 UTC. Runs a 14-minute discovery phase followed by a 9-minute verification phase. Only its verified predictions are automatically eligible for Radar 2; any manually provided `future-ideas.json` claim must have its original source URL.

**Radar 2** (`update-outcomes.yml`): 04:17 and 16:17 UTC. Reads source-linked claims from Radar 1 and source-linked manually curated items (excluding duplications). Searches for independent dated observations and writes `stuff/WHAT_WAS_EXPECTED_WHAT_HAPPENED.docx`. Each of the 28 forecast candidates has **WHAT WAS EXPECTED** and **WHAT ACTUALLY HAPPENED** fields, an explicit evidence gap if not reviewed, and available research timestamps and links. The separate 2 observed policy cases have documented actual observations. Entries without actual measurements are not given invented outcomes. A fresh Word file does **not** mean that new verified observations were found: when the API key is absent, requests fail, or evidence is insufficient, the report says so. No arbitrary numeric accuracy scores are assigned.

**Avoid overlap:** both workflows use the exact same GitHub Actions concurrency group with `cancel-in-progress: false`, so they cannot run concurrently even if GitHub schedules one late or you trigger runs manually. GitHub cron is best-effort; if multiple queued runs occur, GitHub Actions may not guarantee FIFO order. Times above are UTC (Finland UTC+2 winter, UTC+3 summer).

## Activate

1. Replace your repository contents with this ZIP's `world-radar-main` contents (preserve the `.github` folder). Keep GitHub Actions enabled and enable workflow **Read and write permissions** in repository Settings → Actions → General, if needed.
2. Add repository secret **`OPENAI_API_KEY`** in Settings → Secrets and variables → Actions. Radar 2 uses the Responses API with web search and may incur API/web-search charges. This is **necessary for automated evidence-based comparisons** in this implementation; without it, the document explicitly shows *unassessed* entries, never made-up scores.
3. In Actions, manually run **Radar 1** first, then **Radar 2** if you want to check them without waiting for the scheduled runs. They cannot overlap.

The **original Radar 1 discovery and verification code was preserved**. The previous headline-based scoring workflow is replaced, but its old scripts and data remain in the repo for compatibility/reference. Radar 2 does not use headlines as numeric votes. The available underlying verified findings may have projections for 2040 or later; those correctly remain unscored today. The existing short `future-ideas.json` contains manually maintained source-anchored claims; these can also be assessed, where their target year has passed.

### Cautions

Radar 1 source extraction may be imperfect, and model-assisted outcome evaluation can make mistakes. Each informal judgment must be treated as a draft for checking, not a definitive fact. Automated web citations may link to sources that are weak or do not support a result; open source URLs for high-stakes uses. GitHub Actions scheduled runs depend on GitHub availability and an active repository. The API may fail or hit quotas; in that case the previous result is retained instead of inventing evidence.
