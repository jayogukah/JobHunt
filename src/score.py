"""Scoring passes.

pass 1 (heuristic): deterministic 4-component filter, no LLM. Used to cut
the candidate list before we spend Gemini quota.

pass 2 (gemini): one LLM call per survivor. Returns a GeminiScore with a
fit score, sponsorship read, strengths / gaps / red flags, and short
reasoning in the candidate's voice.

Weights for pass 1 (sum to 1.0):
    keyword      0.4   overlap of search keywords with title + first 500 chars
    location     0.2   location match or remote match
    sponsorship  0.2   sponsorship signal in the description
    seniority    0.2   seniority match against the profile
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable

from src.llm import GeminiClient, LLMError
from src.models import GeminiScore, HeuristicScore, Job

log = logging.getLogger("jobhunt.score")

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9.+/\-]{1,}")

SENIORITY_KEYWORDS = {
    "junior": {"junior", "jr", "graduate", "entry level", "entry-level"},
    "mid": {"engineer ii", "engineer 2", "mid-level", "mid level", "intermediate"},
    "senior": {"senior", "sr.", "sr ", "staff"},
    "lead": {"lead", "principal", "head of", "director"},
}

SPONSORSHIP_POSITIVE = ("sponsorship", "visa", "relocation")
SPONSORSHIP_NEGATIVE = (
    "no sponsorship",
    "unable to sponsor",
    "do not sponsor",
    "must have the right to work",
    "must have right to work",
    "must already have the right to work",
    "authorization to work",
    "authorised to work without sponsorship",
    "citizens only",
    "green card required",
)

# ---- voice and prompt scaffolding (shared with tailor.py) ------------------

VOICE_RULES = """Writing voice rules (MANDATORY):
- No em dashes. Ever. Use commas, periods, or parentheses.
- No corporate AI-sounding phrases: do not use "leverage/leveraged",
  "spearhead/spearheaded", "passionate about", "proven track record",
  "results-driven", "dynamic", "synergy", "best-in-class".
- Natural human tone. Short, specific, factual.
- Lead with the tool or metric, not framing language.
- When mentioning a candidate's work, cite concrete tools and numbers."""

SCORE_SYSTEM = """You are a pragmatic hiring reviewer helping a candidate
decide whether a job is worth applying to. You must respond with a single
JSON object and nothing else. No prose before or after."""

MAX_JOB_DESC_CHARS = 3000

_BANNED_TOKENS = (
    "leverage",
    "leveraged",
    "spearhead",
    "spearheaded",
    "passionate about",
    "proven track record",
    "results-driven",
    "results driven",
    "dynamic team",
    "best-in-class",
    "best in class",
    "synergy",
)

_REPLACEMENTS = {
    "—": ", ",   # em dash
    "–": "-",    # en dash
    "leveraged": "used",
    "leverage": "use",
    "Leveraged": "Used",
    "Leverage": "Use",
    "spearheaded": "led",
    "Spearheaded": "Led",
    "spearhead": "lead",
    "Spearhead": "Lead",
}


def voice_scrub(text: str) -> str:
    """Last-line-of-defence scrub for banned phrases and em dashes."""
    if not text:
        return ""
    out = text
    for bad, good in _REPLACEMENTS.items():
        out = out.replace(bad, good)
    lowered = out.lower()
    if any(tok in lowered for tok in _BANNED_TOKENS):
        log.info("voice_warning remaining_bans=%s", [t for t in _BANNED_TOKENS if t in lowered])
    return out.strip()


def summarize_profile(profile: dict[str, Any]) -> str:
    """Compact profile view for the scoring prompt."""
    ident = profile.get("identity") or {}
    ctx = profile.get("context") or {}
    lines: list[str] = []
    lines.append(f"Name: {ident.get('name', '')}")
    lines.append(f"Current country: {ctx.get('current_country', 'unknown')}")
    lines.append(f"Seniority: {ctx.get('seniority', 'unknown')}")
    lines.append(f"Needs sponsorship: {bool(ctx.get('needs_sponsorship'))}")
    lines.append(f"Open to relocation: {bool(ctx.get('open_to_relocation'))}")
    summary = (profile.get("summary") or "").strip()
    if summary:
        lines.append(f"\nSummary:\n{summary}")
    comps = profile.get("competencies") or []
    if comps:
        lines.append(f"\nCompetencies: {', '.join(comps[:40])}")
    exps = profile.get("experience") or []
    if exps:
        lines.append("\nExperience:")
        for e in exps[:4]:
            start = e.get("start", "")
            end = e.get("end", "")
            lines.append(f"- {e.get('role', '')} @ {e.get('company', '')} ({start} to {end})")
            for b in (e.get("bullets") or [])[:3]:
                lines.append(f"  * {b}")
    certs = profile.get("certifications") or []
    if certs:
        active = [c for c in certs if c.get("status") == "active"]
        if active:
            lines.append("\nActive certifications: " + ", ".join(c.get("name", "") for c in active))
    return "\n".join(lines)


# ---- pass 1: heuristic -----------------------------------------------------


def _keyword_score(job: Job, keywords: Iterable[str]) -> tuple[float, list[str]]:
    hay = f"{job.title}\n{(job.description or '')[:500]}".lower()
    hits: list[str] = []
    for kw in keywords:
        kw_lower = kw.strip().lower()
        if not kw_lower:
            continue
        if kw_lower in hay:
            hits.append(kw)
    if not hits:
        return 0.0, []
    return min(1.0, 0.5 + 0.15 * len(hits)), hits


def _location_score(job: Job, locations: list[str], remote_ok: bool) -> tuple[float, bool]:
    if remote_ok and job.remote:
        return 1.0, True
    loc = (job.location or "").lower()
    if not loc:
        return 0.3, False
    for target in locations:
        t = target.strip().lower()
        if not t or t == "remote":
            continue
        if t in loc:
            return 1.0, True
    if remote_ok and "remote" in loc:
        return 1.0, True
    return 0.0, False


def _sponsorship_score(job: Job, require_sponsorship: bool, current_country: str | None) -> tuple[float, str]:
    desc = (job.description or "").lower()
    if any(phrase in desc for phrase in SPONSORSHIP_NEGATIVE):
        loc = (job.location or "").lower()
        if current_country and current_country.lower() in loc:
            return 0.8, "negative"
        return 0.0 if require_sponsorship else 0.5, "negative"
    if any(phrase in desc for phrase in SPONSORSHIP_POSITIVE):
        return 1.0, "positive"
    return 0.5, "unknown"


def _seniority_score(job: Job, target_level: str) -> tuple[float, bool]:
    target_level = (target_level or "").lower().strip()
    hay = f"{job.title.lower()} {(job.description or '')[:300].lower()}"
    target_terms = SENIORITY_KEYWORDS.get(target_level, set())
    if any(term in job.title.lower() for term in target_terms):
        return 1.0, True
    if any(term in hay for term in target_terms):
        return 0.7, True
    for level, terms in SENIORITY_KEYWORDS.items():
        if level == target_level:
            continue
        if any(term in job.title.lower() for term in terms):
            return 0.1, False
    return 0.5, False


def _has_exclusions(job: Job, excludes: list[str]) -> str | None:
    hay = f"{job.title}\n{job.description or ''}".lower()
    for kw in excludes:
        k = kw.strip().lower()
        if k and k in hay:
            return kw
    return None


def score(job: Job, search: dict[str, Any], profile_context: dict[str, Any] | None = None) -> HeuristicScore:
    ctx = profile_context or {}
    excluded = _has_exclusions(job, search.get("exclude_keywords") or [])
    if excluded:
        return HeuristicScore(score=0.0, excluded_by=excluded)

    kw_score, kw_hits = _keyword_score(job, search.get("keywords") or [])
    loc_score, loc_match = _location_score(
        job, search.get("locations") or [], bool(search.get("remote_ok", True))
    )
    spon_score, spon_signal = _sponsorship_score(
        job,
        require_sponsorship=bool(search.get("visa_sponsorship_required")) or bool(ctx.get("needs_sponsorship")),
        current_country=ctx.get("current_country"),
    )
    sen_score, sen_match = _seniority_score(job, ctx.get("seniority", "senior"))

    total = 0.4 * kw_score + 0.2 * loc_score + 0.2 * spon_score + 0.2 * sen_score
    return HeuristicScore(
        score=round(total, 4),
        keyword_hits=kw_hits,
        location_match=loc_match,
        sponsorship_signal=spon_signal,
        seniority_match=sen_match,
    )


def filter_and_score(
    jobs: list[Job],
    search: dict[str, Any],
    profile_context: dict[str, Any] | None = None,
) -> list[tuple[Job, HeuristicScore]]:
    """Score every job; callers apply min_heuristic_score themselves."""
    return [(j, score(j, search, profile_context)) for j in jobs]


# ---- pass 2: Gemini deep scoring -------------------------------------------


SCORE_JSON_SCHEMA_HINT = """Return JSON in exactly this shape:
{
  "fit_score": <float 0.0 to 1.0>,
  "sponsorship_likely": "yes" | "no" | "unclear",
  "strengths": [<short string>, ...],
  "gaps": [<short string>, ...],
  "red_flags": [<short string>, ...],
  "why_apply": "<2 to 3 sentences, natural voice, no em dashes>",
  "why_skip": "<empty string if fit_score >= 0.6, else 1 to 2 sentences>"
}"""


def score_job_llm(client: GeminiClient, job: Job, profile: dict[str, Any]) -> GeminiScore:
    """One Gemini call per job. Returns a validated GeminiScore."""
    desc = (job.description or "")[:MAX_JOB_DESC_CHARS]
    profile_summary = summarize_profile(profile)
    prompt = f"""{VOICE_RULES}

{SCORE_JSON_SCHEMA_HINT}

Candidate profile:
{profile_summary}

Job posting:
- Title: {job.title}
- Company: {job.company}
- Location: {job.location or 'unspecified'}
- Remote: {job.remote}
- Source: {job.source}

Description:
{desc}

Score this job for the candidate. Key concerns:
- Does the job description mention visa sponsorship, relocation, or global hiring?
- Is the candidate's seniority a match?
- Does their toolchain (UiPath, Power Automate, Python, Gemini API, SWIFT, Bloomberg) actually show up as a want, not just as adjacent?
- Any hard red flags (citizens-only, no remote outside one country, etc.)?
"""
    raw = client.generate_json(prompt, system=SCORE_SYSTEM)
    try:
        return GeminiScore(
            fit_score=max(0.0, min(1.0, float(raw.get("fit_score") or 0.0))),
            sponsorship_likely=_normalise_sponsorship(raw.get("sponsorship_likely")),
            strengths=_as_str_list(raw.get("strengths")),
            gaps=_as_str_list(raw.get("gaps")),
            red_flags=_as_str_list(raw.get("red_flags")),
            why_apply=voice_scrub(raw.get("why_apply") or ""),
            why_skip=voice_scrub(raw.get("why_skip") or ""),
        )
    except (ValueError, TypeError) as e:
        raise LLMError(f"Could not build GeminiScore from payload: {e}; raw keys={list(raw.keys())}") from e


def _as_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    out: list[str] = []
    for item in value:
        s = str(item).strip()
        if s:
            out.append(voice_scrub(s))
    return out


def _normalise_sponsorship(raw: Any) -> str:
    v = str(raw or "unclear").strip().lower()
    if v in {"yes", "no", "unclear"}:
        return v
    if v in {"true", "likely", "probably"}:
        return "yes"
    if v in {"false", "unlikely"}:
        return "no"
    return "unclear"
