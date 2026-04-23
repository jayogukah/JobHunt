"""Workable widget API (unauthenticated).

Endpoint: https://apply.workable.com/api/v1/widget/accounts/{subdomain}?details=true
Returns {jobs: [...]} with each job shallow. For the full description we
hit the per-job endpoint: /api/v1/accounts/{subdomain}/jobs/{shortcode}?details=true
"""

from __future__ import annotations

from typing import Any

from src.models import Job
from src.normalize import clean_html, detect_remote, parse_ts, short_location

from .base import http_get_json

NAME = "workable"
LIST_URL = "https://apply.workable.com/api/v1/widget/accounts/{subdomain}"
DETAIL_URL = "https://apply.workable.com/api/v1/accounts/{subdomain}/jobs/{shortcode}"


def fetch_board(subdomain: str) -> list[Job]:
    data = http_get_json(LIST_URL.format(subdomain=subdomain), params={"details": "true"})
    jobs_raw = data.get("jobs") or []
    out: list[Job] = []
    for j in jobs_raw:
        try:
            job = _to_job(subdomain, j)
        except Exception:
            continue
        if job.title and job.apply_url:
            out.append(job)
    return out


def fetch(targets: list[str], search: dict[str, Any]) -> list[Job]:  # noqa: ARG001
    out: list[Job] = []
    for sub in targets:
        out.extend(fetch_board(sub))
    return out


def _to_job(subdomain: str, j: dict[str, Any]) -> Job:
    location = j.get("location") or {}
    city, country = location.get("city"), location.get("country")
    loc = short_location([city, country])
    description = clean_html(j.get("description") or j.get("full_description") or "")
    return Job(
        source=NAME,
        source_id=str(j.get("shortcode") or j.get("id") or ""),
        title=(j.get("title") or "").strip(),
        company=(j.get("company_name") or subdomain).strip(),
        location=loc,
        remote=bool(location.get("workplace") == "remote") or detect_remote(loc, description),
        description=description,
        apply_url=j.get("application_url") or j.get("url") or "",
        posted_at=parse_ts(j.get("published_on") or j.get("created_at")),
        raw={"subdomain": subdomain, "department": j.get("department"), "employment_type": j.get("employment_type")},
    )
