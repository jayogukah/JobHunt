# JobHunt PWA

A mobile-first progressive web app that renders the daily JobHunt pipeline
output as a scrollable, installable feed. Reads two JSON files from GitHub raw
URLs, filters and sorts them client-side, links to each job's tailored DOCX
and apply URL. No backend.

## What it is

- Frontend: React 18 + Vite + Tailwind CSS + `vite-plugin-pwa`.
- Data: two JSON files the Python pipeline emits to `reports/latest/` on every
  run. The PWA fetches them over plain HTTPS via `raw.githubusercontent.com`.
- Deploy: builds to `/docs/` at the repo root, served by GitHub Pages.

## Set your GitHub username

Open `src/config.js` and change `GH_USER` / `GH_REPO` / `GH_BRANCH` if you fork
the repo. Defaults point at `jayogukah/JobHunt@main`.

The pipeline-side URL the PWA pulls:

- `reports/latest/jobs.json` — flat list of scored jobs (produced by
  `src/report.py::write_jobs_json`)
- `reports/latest/meta.json` — run summary (source health, totals, partial-run
  reason) produced by `write_meta_json`

## Run locally

```bash
cd jobhunt-pwa
npm install
npm run dev
```

Vite will open `http://localhost:5173/JobHunt/`. The dev server still fetches
live data from GitHub raw, so you see real jobs.

## Build

```bash
npm run build
```

Output goes to `../docs/` (the repo-level `docs/` folder). Commit that folder;
GitHub Pages serves it.

## Enable GitHub Pages

Settings → Pages → Build and deployment → Source: `Deploy from a branch`. Pick
`main` / `/docs`. Save. The site becomes available at
`https://<your-github-username>.github.io/JobHunt/`.

Note the path segment is case-sensitive (`JobHunt`, not `jobhunt`). If you
rename the repo, change `base` in `vite.config.js` to match.

## What the pipeline must write

For the PWA to render anything, the Python pipeline must keep these paths
populated on the default branch:

- `reports/latest/jobs.json` — array of flat scored jobs. Shape per row:
  ```json
  {
    "source": "greenhouse",
    "source_id": "abc123",
    "run_date": "2025-04-20",
    "title": "Senior Automation Engineer",
    "company": "Anthropic",
    "location": "Remote",
    "remote": true,
    "apply_url": "https://...",
    "posted_at": "2025-04-20T10:00:00Z",
    "salary_min": 120000,
    "salary_max": 160000,
    "currency": "USD",
    "description": "...",
    "heuristic_score": 0.72,
    "fit_score": 0.88,
    "sponsorship_likely": "yes",
    "strengths": ["..."],
    "gaps": ["..."],
    "red_flags": ["..."],
    "why_apply": "...",
    "why_skip": "",
    "cv_path": "tailored/anthropic_senior-automation-engineer.docx"
  }
  ```
- `reports/latest/meta.json` — run-level summary:
  ```json
  {
    "run_date": "2025-04-20",
    "total_fetched": 143,
    "total_scored": 38,
    "top_n": 7,
    "partial_reason": null,
    "sources": { "greenhouse": {"count": 12, "status": "ok"}, ... }
  }
  ```

Both files are written automatically by `src/report.py`:
`write_jobs_json`, `write_meta_json`, and `mirror_to_latest`.

## Filtering, sorting

All client-side. Jobs are sorted by `fit_score` descending (falling back to
`heuristic_score` when Gemini did not score a job). Filters:

- Min fit: `All`, `0.6+`, `0.7+`, `0.8+`
- Sponsorship: `All`, `Yes`, `Unclear` (`No` only hides when you pick one of the others)
- Remote only: toggle

## Offline behaviour

The service worker uses a `NetworkFirst` strategy for both JSON files with an
8 s network timeout. If you lose connectivity the app still renders whatever
was cached last, tagged with that day's run date at the top of the header.

## What's intentionally missing

No auth, no write paths, no settings screen, no search, no light-mode toggle,
no push notifications. Filters are the only interaction surface. Add these
only when you have a reason to.
