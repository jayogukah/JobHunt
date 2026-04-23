"""Gemini tailoring pass (step 8).

One LLM call per top-N job. Returns a TailoredCV — rewritten summary,
reordered competencies, and rewritten bullets per existing role. Does NOT
invent experience, employers, or certifications: a post-hoc guard drops
any fabricated rows.

Reuses voice rules + banned-phrase scrub from score.py so scoring and
tailoring speak with the same voice.
"""

from __future__ import annotations

import logging
from typing import Any

import yaml

from src.llm import GeminiClient
from src.models import Job, TailoredCV, TailoredExperience
from src.score import MAX_JOB_DESC_CHARS, VOICE_RULES, voice_scrub

log = logging.getLogger("jobhunt.tailor")

TAILOR_SYSTEM = """You are a resume editor. You never invent experience,
tools, certifications, employers, or dates. You only reorder, re-emphasize,
and rephrase content already present in the candidate's profile to match a
specific job description. You must respond with a single JSON object."""

TAILOR_CONSTRAINTS = """Constraints (MANDATORY):
- Do NOT invent experience, tools, employers, dates, or certifications that
  are not present in the candidate's profile YAML below.
- You may reorder, re-emphasize, and rephrase. You may NOT add new facts.
- Match the job's specific tools and acronyms ONLY when the candidate
  actually has them in their profile.
- Each bullet must lead with the tool or metric, not with framing language.
- Bullets MUST be under 25 words each.
- Keep every company + role pair from the profile, in the same order."""

TAILOR_JSON_SCHEMA_HINT = """Return JSON in exactly this shape:
{
  "summary": "<3 to 4 sentences in the candidate's voice>",
  "competencies_ordered": ["<string>", ...],
  "experience": [
    {"company": "<existing company>", "role": "<existing role>", "bullets": ["<rewritten bullet>", ...]},
    ...
  ],
  "keywords_added": ["<string>", ...]
}"""


def _profile_for_tailor(profile: dict[str, Any]) -> str:
    keep = {
        k: profile.get(k)
        for k in ("summary", "competencies", "experience", "education", "certifications", "projects")
    }
    return yaml.safe_dump(keep, sort_keys=False, allow_unicode=True).strip()


def tailor_cv(client: GeminiClient, job: Job, profile: dict[str, Any]) -> TailoredCV:
    desc = (job.description or "")[:MAX_JOB_DESC_CHARS]
    profile_yaml = _profile_for_tailor(profile)
    prompt = f"""{VOICE_RULES}

{TAILOR_CONSTRAINTS}

{TAILOR_JSON_SCHEMA_HINT}

Candidate profile (authoritative source of facts, YAML):
---
{profile_yaml}
---

Job posting:
- Title: {job.title}
- Company: {job.company}
- Location: {job.location or 'unspecified'}

Job description:
{desc}

Rewrite the candidate's summary, reorder competencies, and rewrite bullets
to emphasize what this specific job wants. Keep every employer. Do not
fabricate."""
    raw = client.generate_json(prompt, system=TAILOR_SYSTEM)

    experiences: list[TailoredExperience] = []
    for item in raw.get("experience") or []:
        if not isinstance(item, dict):
            continue
        experiences.append(
            TailoredExperience(
                company=str(item.get("company", "")).strip(),
                role=str(item.get("role", "")).strip(),
                bullets=[voice_scrub(str(b)) for b in (item.get("bullets") or []) if str(b).strip()],
            )
        )

    tailored = TailoredCV(
        summary=voice_scrub(raw.get("summary") or ""),
        competencies_ordered=[voice_scrub(str(s)) for s in (raw.get("competencies_ordered") or []) if str(s).strip()],
        experience=experiences,
        keywords_added=[str(s).strip() for s in (raw.get("keywords_added") or []) if str(s).strip()],
    )
    _guard_no_fabrication(tailored, profile)
    _enforce_bullet_length(tailored)
    return tailored


def _guard_no_fabrication(tailored: TailoredCV, profile: dict[str, Any]) -> None:
    """Every (company, role) in the tailored CV must appear in the profile."""
    real: set[tuple[str, str]] = set()
    for e in profile.get("experience") or []:
        real.add(((e.get("company") or "").strip().lower(), (e.get("role") or "").strip().lower()))
    kept: list[TailoredExperience] = []
    for e in tailored.experience:
        if (e.company.lower(), e.role.lower()) in real:
            kept.append(e)
        else:
            log.warning("dropping fabricated experience: %s @ %s", e.role, e.company)
    tailored.experience = kept


def _enforce_bullet_length(tailored: TailoredCV, max_words: int = 25) -> None:
    """Trim bullets that exceed the word limit. Don't fail; the renderer
    shouldn't produce a CV that looks padded because one bullet ran long.
    """
    for e in tailored.experience:
        trimmed: list[str] = []
        for b in e.bullets:
            words = b.split()
            if len(words) <= max_words:
                trimmed.append(b)
            else:
                trimmed.append(" ".join(words[:max_words]).rstrip(",;:") + ".")
        e.bullets = trimmed
