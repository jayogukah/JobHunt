"""Ashby job board API (unauthenticated).

Docs: https://developers.ashbyhq.com/reference/jobpostinglist
Endpoint: https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=true
"""

from __future__ import annotations

from typing import Any

from src.models import Job
from src.normalize import clean_html, detect_remote, parse_ts, short_location

from .base import http_get_json

NAME = "ashby"
BASE = "https://api.ashbyhq.com/posting-api/job-board/{org}"


def fetch_board(org: str) -> list[Job]:
    data = http_get_json(BASE.format(org=org), params={"includeCompensation": "true"})
    postings = data.get("jobs") or data.get("jobPostings") or []
    out: list[Job] = []
    for p in postings:
        try:
            job = _to_job(org, p)
        except Exception:
            continue
        if job.title and job.apply_url:
            out.append(job)
    return out


def fetch(targets: list[str], search: dict[str, Any]) -> list[Job]:  # noqa: ARG001
    out: list[Job] = []
    for org in targets:
        out.extend(fetch_board(org))
    return out


def _to_job(org: str, p: dict[str, Any]) -> Job:
    location_name = p.get("locationName") or (p.get("location") or {}).get("name") if isinstance(p.get("location"), dict) else p.get("location")
    description = clean_html(p.get("descriptionHtml") or p.get("description") or "")
    secondary = p.get("secondaryLocations") or []
    sec_names = [s.get("locationName") or s.get("name") for s in secondary if isinstance(s, dict)]
    loc = short_location([location_name, *sec_names[:1]])
    remote_flag = p.get("isRemote")
    if remote_flag is None:
        remote_flag = detect_remote(loc, description)

    comp = p.get("compensation") or {}
    salary_min = salary_max = None
    currency = None
    # Ashby's compensation shape: {compensationTierSummary: {...}, summaryComponents: [...]}
    if isinstance(comp, dict):
        for comp_item in comp.get("summaryComponents") or []:
            if not isinstance(comp_item, dict):
                continue
            tier = comp_item.get("compensationTierSummary") or comp_item.get("summary") or ""
            if "-" in str(tier) and not currency:
                # we don't parse here; it's unreliable across orgs. Keep the tier
                # string in raw for reference and skip typed salary.
                break

    return Job(
        source=NAME,
        source_id=str(p.get("id") or p.get("jobId") or ""),
        title=(p.get("title") or "").strip(),
        company=(p.get("teamName") or org).strip(),
        location=loc,
        remote=remote_flag,
        description=description,
        apply_url=p.get("jobUrl") or p.get("applyUrl") or "",
        posted_at=parse_ts(p.get("publishedAt") or p.get("updatedAt")),
        salary_min=salary_min,
        salary_max=salary_max,
        currency=currency,
        raw={"org": org, "employmentType": p.get("employmentType"), "department": p.get("departmentName")},
    )
