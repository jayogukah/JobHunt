"""Arbeitnow Job Board API (unauthenticated).

Docs: https://www.arbeitnow.com/api/job-board-api
Endpoint: https://www.arbeitnow.com/api/job-board-api
"""

from __future__ import annotations

from typing import Any

from src.models import Job
from src.normalize import clean_html, detect_remote, parse_ts, short_location

from .base import http_get_json

NAME = "arbeitnow"
BASE = "https://www.arbeitnow.com/api/job-board-api"


def fetch_all() -> list[Job]:
    data = http_get_json(BASE)
    rows = data.get("data") or []
    out: list[Job] = []
    for j in rows:
        try:
            job = _to_job(j)
        except Exception:
            continue
        if job.title and job.apply_url:
            out.append(job)
    return out


def fetch(targets: list[str], search: dict[str, Any]) -> list[Job]:  # noqa: ARG001
    """Targets ignored; the feed is global. We fetch once and let the scorer
    pass handle keyword relevance.
    """
    return fetch_all()


def _to_job(j: dict[str, Any]) -> Job:
    loc = short_location([j.get("location")])
    description = clean_html(j.get("description") or "")
    remote_flag = bool(j.get("remote")) or detect_remote(loc, description)
    return Job(
        source=NAME,
        source_id=str(j.get("slug") or j.get("url") or ""),
        title=(j.get("title") or "").strip(),
        company=(j.get("company_name") or "").strip(),
        location=loc,
        remote=remote_flag,
        description=description,
        apply_url=j.get("url") or "",
        posted_at=parse_ts(j.get("created_at")),
        raw={"tags": j.get("tags"), "job_types": j.get("job_types"), "visa_sponsorship": j.get("visa_sponsorship")},
    )
