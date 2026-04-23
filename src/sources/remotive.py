"""Remotive remote-jobs API (unauthenticated).

Docs: https://remotive.com/api-documentation
Endpoint: https://remotive.com/api/remote-jobs?search={kw}&limit=50
"""

from __future__ import annotations

from typing import Any

from src.models import Job
from src.normalize import clean_html, detect_remote, parse_ts, short_location

from .base import http_get_json

NAME = "remotive"
BASE = "https://remotive.com/api/remote-jobs"


def fetch_keyword(keyword: str, limit: int = 50) -> list[Job]:
    data = http_get_json(BASE, params={"search": keyword, "limit": str(limit)})
    jobs_raw = data.get("jobs") or []
    out: list[Job] = []
    for j in jobs_raw:
        try:
            job = _to_job(j)
        except Exception:
            continue
        if job.title and job.apply_url:
            out.append(job)
    return out


def fetch(targets: list[str], search: dict[str, Any]) -> list[Job]:  # noqa: ARG001
    """Targets are ignored here; Remotive is keyword-based. We pull for every
    keyword in search.yaml and let the dedup pass handle overlap.
    """
    out: list[Job] = []
    seen_ids: set[str] = set()
    for kw in search.get("keywords") or []:
        for j in fetch_keyword(kw):
            if j.source_id in seen_ids:
                continue
            seen_ids.add(j.source_id)
            out.append(j)
    return out


def _to_job(j: dict[str, Any]) -> Job:
    loc = short_location([j.get("candidate_required_location")])
    description = clean_html(j.get("description") or "")
    return Job(
        source=NAME,
        source_id=str(j.get("id") or j.get("url") or ""),
        title=(j.get("title") or "").strip(),
        company=(j.get("company_name") or "").strip(),
        location=loc,
        remote=True,  # whole site is remote-only
        description=description,
        apply_url=j.get("url") or "",
        posted_at=parse_ts(j.get("publication_date")),
        salary_min=_parse_salary_min(j.get("salary")),
        salary_max=_parse_salary_max(j.get("salary")),
        currency=None,
        raw={"category": j.get("category"), "tags": j.get("tags"), "job_type": j.get("job_type")},
    )


def _parse_salary_min(raw: Any) -> float | None:
    return _parse_salary(raw, index=0)


def _parse_salary_max(raw: Any) -> float | None:
    return _parse_salary(raw, index=1)


def _parse_salary(raw: Any, index: int) -> float | None:
    if not raw or not isinstance(raw, str):
        return None
    digits = "".join(c if c.isdigit() or c in ",." else " " for c in raw).split()
    if not digits:
        return None
    try:
        numbers = [float(d.replace(",", "")) for d in digits]
    except ValueError:
        return None
    if index < len(numbers):
        return numbers[index]
    return None
