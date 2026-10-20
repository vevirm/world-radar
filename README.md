# European Foresight Radar

A simple EU foresight research observatory.

- **Scanner 1** discovers research leads and writes `research-leads.json` and `stuff/WORLD_RADAR_MASTER.xlsx`. A lead is enough to enter the library; it is not automatically a verified forecast.
- **Scanner 2** reads those leads, seeks independently sourced subsequent developments, and writes `retrospective-results.json`, `outlook-summary.json` and `stuff/WHAT_WAS_EXPECTED_WHAT_HAPPENED.docx`.
- **Website** (`index.html`) presents the outlook, searchable research library, reality checks and downloads. It is a static GitHub Pages site.

## Start

1. Upload the entire extracted repository, including `.github/workflows`, to a GitHub repository on branch `main`.
2. Under **Settings → Secrets and variables → Actions**, add `OPENAI_API_KEY` for Scanner 2. Optional: `OPENALEX_API_KEY` for scholarly discovery.
3. Under **Settings → Actions → General**, allow workflows to read and write repository contents. Enable GitHub Pages with **GitHub Actions** as source.
4. Run **European Foresight Radar — Scholarly Discovery and Retrospective Verification** (Scanner 1), then **Radar 2 - outcomes and Word report** (Scanner 2). Run **Publish radar website (controlled)** if needed.

## Notes

GitHub's scheduled Actions are best effort. Scanner 1 takes ~25 minutes, Scanner 2 takes ~25 minutes. Scanners require network/API access and have not been validated live here. Excel and Word contain saved results and will be refreshed when workflows succeed. GitHub Pages is public: the site and JSON source data are publicly accessible.

Some legacy supporting scripts/data remain deliberately because removing them without a live integration test could break scanning. They are not shown on the website.
