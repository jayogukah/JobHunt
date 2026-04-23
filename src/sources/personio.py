"""Personio XML feed (unauthenticated).

Endpoint: https://{company}.jobs.personio.com/xml
We parse with stdlib ElementTree — no lxml dep.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from src.models import Job
from src.normalize import clean_html, detect_remote, parse_ts, short_location

from .base import http_get_text

NAME = "personio"
BASE = "https://{company}.jobs.personio.com/xml"


def fetch_board(company: str) -> list[Job]:
    xml = http_get_text(BASE.format(company=company))
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    out: list[Job] = []
    for position in root.findall(".//position"):
        try:
            job = _to_job(company, position)
        except Exception:
            continue
        if job.title and job.apply_url:
            out.append(job)
    return out


def fetch(targets: list[str], search: dict[str, Any]) -> list[Job]:  # noqa: ARG001
    out: list[Job] = []
    for c in targets:
        out.extend(fetch_board(c))
    return out


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return (el.text or "").strip()


def _to_job(company: str, p: ET.Element) -> Job:
    title = _text(p.find("name"))
    pid = _text(p.find("id"))
    office = _text(p.find("office"))
    department = _text(p.find("department"))
    subcompany = _text(p.find("subcompany"))
    # description: Personio wraps jobDescriptions > jobDescription > value (HTML)
    desc_parts: list[str] = []
    for jd in p.findall(".//jobDescription"):
        name_el = jd.find("name")
        val_el = jd.find("value")
        name = _text(name_el)
        val = clean_html(_text(val_el))
        if name or val:
            desc_parts.append(f"{name}\n{val}".strip())
    description = "\n\n".join(desc_parts).strip()
    apply_url = _text(p.find("url"))

    loc = short_location([office, department, subcompany])
    return Job(
        source=NAME,
        source_id=pid or apply_url or "",
        title=title,
        company=(subcompany or company).strip(),
        location=loc,
        remote=detect_remote(loc, description),
        description=description,
        apply_url=apply_url,
        posted_at=parse_ts(_text(p.find("createdAt"))),
        raw={"company": company, "employment_type": _text(p.find("employmentType")), "schedule": _text(p.find("schedule"))},
    )
