"""Lever postings API.

Docs: https://github.com/lever/postings-api
Endpoint: https://api.lever.co/v0/postings/{company}?mode=json
"""

from __future__ import annotations

from typing import Any

from src.models import Job
from src.normalize import clean_html, detect_remote, parse_ts, short_location

from .base import http_get_json

NAME = "lever"
BASE = "https://api.lever.co/v0/postings/{slug}"


def fetch_company(slug: str) -> list[Job]:
    data = http_get_json(BASE.format(slug=slug), params={"mode": "json"})
    if not isinstance(data, list):
        return []
    out: list[Job] = []
    for p in data:
        try:
            job = _to_job(slug, p)
        except Exception:
            continue
        if job.title and job.apply_url:
            out.append(job)
    return out


def fetch(targets: list[str], search: dict[str, Any]) -> list[Job]:  # noqa: ARG001
    out: list[Job] = []
    for slug in targets:
        out.extend(fetch_company(slug))
    return out


def _to_job(company_slug: str, p: dict[str, Any]) -> Job:
    categories = p.get("categories") or {}
    location = categories.get("location")
    commitment = categories.get("commitment")
    team = categories.get("team")

    # Lever description is split: descriptionPlain (intro), lists[] (bullets),
    # additionalPlain (closing). Concatenate the plain variants.
    parts: list[str] = []
    if p.get("descriptionPlain"):
        parts.append(str(p["descriptionPlain"]))
    for lst in p.get("lists") or []:
        if not isinstance(lst, dict):
            continue
        heading = lst.get("text") or ""
        content = clean_html(lst.get("content") or "")
        if heading or content:
            parts.append(f"{heading}\n{content}".strip())
    if p.get("additionalPlain"):
        parts.append(str(p["additionalPlain"]))
    description = "\n\n".join(s for s in parts if s).strip()
    if not description:
        # fall back to the html-y "description" field
        description = clean_html(p.get("description") or "")

    loc_display = short_location([location, commitment, team])

    return Job(
        source=NAME,
        source_id=str(p.get("id")),
        title=(p.get("text") or "").strip(),
        company=company_slug,
        location=loc_display,
        remote=detect_remote(location, description),
        description=description,
        apply_url=p.get("hostedUrl") or p.get("applyUrl") or "",
        posted_at=parse_ts(p.get("createdAt")),
        raw={
            "slug": company_slug,
            "team": team,
            "commitment": commitment,
            "workplaceType": p.get("workplaceType"),
        },
    )
