# World Radar — Findings & Bibliography

A small static website with **two sections only**: Findings and Bibliography. This is a **global developments radar viewed from Europe**, not an R&I-only or EU-institutions-only tracker.

## What belongs here

Scan the whole world for important, *new* and well-evidenced developments: geopolitics, defence and security, democracy and governance, economy, trade and finance, business and industry, energy and resources, climate and environment, society and demographics, health, science and technology, digital infrastructure, and other globally significant events. Topic boundaries are open; **do not require an R&I angle**. Include non-European events when they have European implications or broad global significance.

Use a **European lens**, not an EU-only scope: explain relevance to Europe's security, prosperity, resilience, institutions, industry, environment or people where material. Differentiate evidence, analysis and uncertainty. Do not use an EU relevance keyword as a hard gate.

## Source standard

Prefer substantial primary sources such as international organisations, statistical agencies, regulators, universities, peer-reviewed papers and major institutional reports. Include high-quality news media for consequential developments not yet documented in papers or reports; attribute their reporting explicitly and cross-check disputed stories. Prioritise what has changed and why it matters, not general background or speculative hot takes. Do not list every headline; select the strongest signals. Avoid partisan advocacy.

## Timing and accumulation

Start **1 October 2026**. Do not backfill history. Date items by the actual publication or event date, clearly distinguishing these if needed. Keep qualifying findings cumulatively, even as new items arrive. Newest first. Avoid duplicates; update or link related findings if appropriate.

## Open

Host this folder on GitHub Pages, Netlify or another static host. For a local preview, run `python -m http.server 8000` in the folder and visit http://localhost:8000/. Direct `file://` opening may block loading the JSON.

## Data model

Append entries to `findings.json`, using `id`, `date` (YYYY-MM-DD), `title`, `source`, `type`, `finding`, `topic`, `url`, and optionally `authors`, `context`, `status`. The page filters out records dated before 2026-10-01. Update `updated_at` with each editorial refresh.

Suggested topic labels: `Geopolitics & security`, `Politics & governance`, `Economy & trade`, `Business & industry`, `Climate & environment`, `Energy & resources`, `Society & demographics`, `Health`, `Science & technology`, `Digital & AI`, `Research & innovation`, `Other global developments`.

Each finding should say **what is new**, why the evidence matters, and ideally its **European implications**, while avoiding exaggerated causality. Bibliography links to the underlying sources.

## Important limitation of current seed data

The 12 entries in `findings.json` were inherited from the uploaded older **R&I × Geopolitics** radar. **They are a narrow test dataset, not a credible survey of all major world developments since 1 October 2026.** Their source dates and details were not newly verified and should be reviewed before publication. Expanding coverage requires new global source discovery and editorial selection. This ZIP is a static site, **not an automated scanner**.
