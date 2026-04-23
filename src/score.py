"""Heuristic prefilter score (pass 1 of 2).

Deliberately simple and deterministic. No LLM calls. The goal is to cut
the job list down before we spend Gemini quota on deep scoring.

Weights (sum to 1.0):
    keyword      0.4   overlap of search keywords with title + first 500 chars
    location     0.2   location match or remote match
    sponsorship  0.2   sponsorship signal in the description
    seniority    0.2   seniority match against the profile
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from src.models import HeuristicScore, Job

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


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _WORD_RE.findall(text or "")}


def _keyword_score(job: Job, keywords: Iterable[str]) -> tuple[float, list[str]]:
    hay = f"{job.title}\n{(job.description or '')[:500]}".lower()
    hits: list[str] = []
    for kw in keywords:
        kw_lower = kw.strip().lower()
        if not kw_lower:
            continue
        if kw_lower in hay:
            hits.append(kw)
    # full-phrase hit is worth a lot; tail hits saturate to avoid over-
    # rewarding long keyword lists
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
    # 'remote' in the location string still counts even if job.remote is None
    if remote_ok and "remote" in loc:
        return 1.0, True
    return 0.0, False


def _sponsorship_score(job: Job, require_sponsorship: bool, current_country: str | None) -> tuple[float, str]:
    """Return (score, signal) where signal is 'positive'|'negative'|'unknown'."""
    desc = (job.description or "").lower()
    # negative first: if they explicitly rule out sponsorship, it's disqualifying
    if any(phrase in desc for phrase in SPONSORSHIP_NEGATIVE):
        # but if the job is in the candidate's country, they don't need sponsorship
        loc = (job.location or "").lower()
        if current_country and current_country.lower() in loc:
            return 0.8, "negative"
        return 0.0 if require_sponsorship else 0.5, "negative"
    if any(phrase in desc for phrase in SPONSORSHIP_POSITIVE):
        return 1.0, "positive"
    # no mention either way — neutral
    return 0.5, "unknown"


def _seniority_score(job: Job, target_level: str) -> tuple[float, bool]:
    target_level = (target_level or "").lower().strip()
    hay = f"{job.title.lower()} {(job.description or '')[:300].lower()}"
    # Exact match in title is the strongest signal.
    target_terms = SENIORITY_KEYWORDS.get(target_level, set())
    if any(term in job.title.lower() for term in target_terms):
        return 1.0, True
    if any(term in hay for term in target_terms):
        return 0.7, True
    # Penalize clear mismatches (e.g. senior candidate seeing a junior job).
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
