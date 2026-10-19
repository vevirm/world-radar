# Two radars — two runs each daily

**Radar 1** (`update-radar.yml`): 01:17 and 13:17 UTC. Runs the existing 15-minute discovery phase followed immediately by the existing 10-minute verification phase. Only its verified predictions are automatically eligible for Radar 2; any manually provided `future-ideas.json` claim must have its original source URL.

**Radar 2** (`update-outcomes.yml`): 04:17 and 16:17 UTC. Reads Radar 1 source-anchored claims, searches the web for evidence of what actually happened in the relevant historical period, and saves `stuff/WHAT_WAS_EXPECTED_WHAT_HAPPENED.docx`. Every entry uses one **What was expected** sentence, one **What happened** sentence, and an optional **rough 1–100 score**. 1 = entirely wrong; 100 = exceptionally accurate. These are subjective summaries, **not academic metrics**. Without outcome evidence or when the target date has not arrived, **no number is assigned**. Supporting URLs are included for checking.

**Avoid overlap:** both workflows use the exact same GitHub Actions concurrency group with `cancel-in-progress: false`, so they cannot run concurrently even if GitHub schedules one late or you trigger runs manually. GitHub cron is best-effort; if multiple queued runs occur, GitHub Actions may not guarantee FIFO order. Times above are UTC (Finland UTC+2 winter, UTC+3 summer).

## Activate

1. Replace your repository contents with this ZIP's `world-radar-main` contents (preserve the `.github` folder). Keep GitHub Actions enabled and enable workflow **Read and write permissions** in repository Settings → Actions → General, if needed.
2. Add repository secret **`OPENAI_API_KEY`** in Settings → Secrets and variables → Actions. Radar 2 uses the Responses API with web search and may incur API/web-search charges. This is **necessary for automated evidence-based comparisons** in this implementation; without it, the document explicitly shows *unassessed* entries, never made-up scores.
3. In Actions, manually run **Radar 1** first, then **Radar 2** if you want to check them without waiting for the scheduled runs. They cannot overlap.

The **original Radar 1 discovery and verification code was preserved**. The previous headline-based scoring workflow is replaced, but its old scripts and data remain in the repo for compatibility/reference. Radar 2 does not use headlines as numeric votes. The available underlying verified findings may have projections for 2040 or later; those correctly remain unscored today. The existing short `future-ideas.json` contains manually maintained source-anchored claims; these can also be assessed, where their target year has passed.

### Cautions

Radar 1 source extraction may be imperfect, and model-assisted outcome evaluation can make mistakes. Each informal judgment must be treated as a draft for checking, not a definitive fact. Automated web citations may link to sources that are weak or do not support a result; open source URLs for high-stakes uses. GitHub Actions scheduled runs depend on GitHub availability and an active repository. The API may fail or hit quotas; in that case the previous result is retained instead of inventing evidence.
