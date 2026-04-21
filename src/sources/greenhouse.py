"""Greenhouse boards API.

Docs: https://developers.greenhouse.io/job-board.html
Endpoint is unauthenticated per board token (e.g. "stripe", "anthropic").
"""

from __future__ import annotations

from typing import Any

from src.models import Job
from src.normalize import clean_html, detect_remote, parse_ts, short_location

from .base import http_get_json

NAME = "greenhouse"
BASE = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def fetch_board(token: str) -> list[Job]:
    data = http_get_json(BASE.format(token=token), params={"content": "true"})
    jobs_raw = data.get("jobs") or []
    out: list[Job] = []
    for j in jobs_raw:
        try:
            job = _to_job(token, j)
        except Exception:
            # A bad record should not kill the whole board pull.
            continue
        if job.title and job.apply_url:
            out.append(job)
    return out


def fetch(targets: list[str], search: dict[str, Any]) -> list[Job]:  # noqa: ARG001
    out: list[Job] = []
    for token in targets:
        out.extend(fetch_board(token))
    return out


def _to_job(board_token: str, j: dict[str, Any]) -> Job:
    description = clean_html(j.get("content") or "")
    location = (j.get("location") or {}).get("name")
    # Greenhouse offices are a list; grab the first for context.
    offices = j.get("offices") or []
    office_names = [o.get("name") for o in offices if isinstance(o, dict)]
    loc_display = short_location([location, *office_names[:1]]) if location else short_location(office_names)
    # Department name for a clearer title downstream (optional metadata).
    departments = j.get("departments") or []

    return Job(
        source=NAME,
        source_id=str(j.get("id")),
        title=(j.get("title") or "").strip(),
        company=(j.get("company_name") or board_token).strip(),
        location=loc_display,
        remote=detect_remote(loc_display, description),
        description=description,
        apply_url=j.get("absolute_url") or "",
        posted_at=parse_ts(j.get("updated_at") or j.get("first_published")),
        raw={
            "board_token": board_token,
            "departments": [d.get("name") for d in departments if isinstance(d, dict)],
            "requisition_id": j.get("requisition_id"),
        },
    )
