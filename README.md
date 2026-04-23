# JobHunt

A daily job discovery and CV tailoring pipeline. It pulls fresh listings from
free job board APIs, scores them against your profile, generates a tailored
DOCX CV for the top picks, and writes a markdown brief with reasoning per
recommendation.

## What it does

- Fetches from 9 sources: Greenhouse, Lever, Ashby, Workable, Personio,
  Remotive, Arbeitnow, Adzuna, and Hacker News "Who is hiring?".
- Normalizes every job to a single schema.
- Deduplicates against a local sqlite of previously-seen jobs.
- Runs a two-pass score: a deterministic heuristic prefilter, then Gemini
  2.5 Flash for the survivors.
- For the top N ranked jobs, calls Gemini again to produce a tailored CV
  (reordered competencies, rewritten bullets, kept-honest).
- Writes `reports/{YYYY-MM-DD}/brief.md`, `jobs.json`, and tailored
  `.docx` files per top pick. Optionally emails the brief.

## What it does NOT do

- It does not submit applications. Ever. You review and send yourself.
- It does not scrape LinkedIn, Indeed, Glassdoor, or any site whose ToS
  forbids automation. Every source is an official public API or feed.
- It does not log in to anything, render JavaScript, solve captchas, or
  create accounts on your behalf.
- It does not guarantee sponsorship. Verify UK claims on the
  [GOV.UK Licensed Sponsor Register](https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers)
  before applying.

## Requirements

- Python 3.11
- A Google AI Studio account (free) for Gemini: https://aistudio.google.com
- Optional: an Adzuna developer account (free, 250 calls/month): https://developer.adzuna.com
- Optional: a Gmail app password if you want the brief emailed:
  https://support.google.com/accounts/answer/185833

## Setup

```bash
git clone <this-repo> && cd JobHunt
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set at minimum `GEMINI_API_KEY`. Adzuna and Gmail keys are
optional; without them those sources/features are skipped.

Then populate the three YAML configs in `config/`:

- **`profile.yaml`** — your master CV as structured data. Identity, summary,
  competencies, experience (with bulletised metrics), education,
  certifications, projects, languages, and a `context` block with
  `current_country`, `seniority`, `needs_sponsorship`, `open_to_relocation`.
- **`targets.yaml`** — companies you actively want to target, grouped by the
  ATS they use. Greenhouse expects board tokens (`anthropic`, `stripe`);
  Lever expects slugs; Ashby expects orgs; Workable expects subdomains;
  Personio expects `{company}` from `{company}.jobs.personio.com`.
- **`search.yaml`** — keywords, locations, Adzuna country codes, exclusion
  terms, and scoring thresholds.

For any company slug marked `VERIFY` in `targets.yaml`, confirm by hitting
the ATS directly, e.g.
`https://boards-api.greenhouse.io/v1/boards/{token}/jobs`.

## Run locally

Dry run — fetches, runs the heuristic prefilter, writes the brief, but
does not call Gemini or generate DOCX:

```bash
python -m src.main --dry-run
```

Narrow to one or two sources while iterating:

```bash
python -m src.main --only greenhouse,lever --limit 10 --dry-run
```

Full run (needs `GEMINI_API_KEY`):

```bash
python -m src.main
```

Outputs land in `reports/{YYYY-MM-DD}/`:
- `brief.md` — the daily brief with per-job detail
- `jobs.json` — every scored job, for later analysis
- `tailored/{company}_{role}.docx` — one per top pick

And `reports/run_log.csv` accumulates run-over-run stats.

## Scoring, in plain language

Every job goes through two scorers.

1. **Heuristic prefilter** (no LLM). A number between 0 and 1:
   - 40% keyword overlap between your search keywords and the job
     title + first 500 chars of description.
   - 20% location match (a target country, or remote if `remote_ok: true`).
   - 20% sponsorship signal. A positive hit on "sponsorship / visa /
     relocation" pushes it up. A hit on "must have the right to work" or
     "no sponsorship" pushes it down unless the job is in your country.
   - 20% seniority match. "Senior" vs your profile level.
   Anything below `scoring.min_heuristic_score` is dropped.

2. **Gemini deep score**. The survivors get one Gemini call each. Gemini
   returns `{fit_score, sponsorship_likely, strengths, gaps, red_flags,
   why_apply, why_skip}` in strict JSON. We rank by `fit_score` and the
   top `scoring.top_n_for_tailoring` with `fit_score >=
   min_final_score_for_apply` go to tailoring.

3. **Tailoring** (still Gemini). The tailoring prompt is restricted: it
   may reorder, re-emphasise, and rephrase bullets from your profile, but
   it may NOT invent experience, tools, employers, or certifications. A
   post-hoc guard drops any fabricated (company, role) pair.

Writing voice rules (enforced by the prompt and scrubbed on the way out):

- No em dashes. Ever.
- No corporate AI phrases: leverage/leveraged, spearhead/spearheaded,
  passionate about, proven track record, results-driven, dynamic, synergy,
  best-in-class.
- Natural human tone. Bullets lead with the tool or metric.

## Using your own CV template

Put a styled DOCX at `templates/cv_template.docx`. Use Jinja-style
placeholders inside paragraphs (including table cells):

- `{{ name }}`, `{{ email }}`, `{{ phone }}`, `{{ location }}`,
  `{{ linkedin }}`, `{{ github }}`, `{{ portfolio }}`
- `{{ summary }}`
- `{{ competencies }}` — comma-separated string
- `{{ experience }}` — multi-line block of role headings and bullets
- `{{ education }}`, `{{ certifications }}`, `{{ projects }}`

Keep the template single-column and avoid text boxes / columns / graphics
so the output stays ATS-safe. If the template is missing or fails to
render, the pipeline falls back to a clean programmatic template.

## GitHub Actions

The workflow at `.github/workflows/daily.yml` runs at 06:00 UTC daily.
Before enabling it, add these repo secrets (Settings > Secrets and
variables > Actions):

- `GEMINI_API_KEY` (required)
- `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` (optional)
- `GMAIL_APP_PASSWORD`, `GMAIL_FROM_ADDRESS`, `GMAIL_TO_ADDRESS` (optional)

The workflow commits `reports/{date}/` and `db/seen.sqlite` back to the
branch so dedupe state and run history accumulate across days.

You can trigger a one-off run from the Actions tab with `workflow_dispatch`;
it accepts `dry_run` and `only` inputs.

## Tests

```bash
pip install pytest
python -m pytest -q
```

All tests mock the network boundary, so they run offline.

## Disclaimers

This is a discovery and tailoring assistant. It does not submit
applications, guarantee interviews, or guarantee visa sponsorship. It
relies on what companies publish in their job descriptions; descriptions
can be wrong, out of date, or silent on sponsorship. Always verify before
applying.
