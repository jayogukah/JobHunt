"""Hacker News 'Who is hiring?' thread via Algolia.

1. Find the latest "Ask HN: Who is hiring?" story (first of each month).
2. Fetch top-level comments via the Algolia search API, filtered by keywords.
3. Each comment becomes a Job — company/location come from the first line,
   description is the comment body.

Endpoints:
  Stories: https://hn.algolia.com/api/v1/search?query=Ask%20HN%3A%20Who%20is%20hiring%3F&tags=story&hitsPerPage=5
  Comments: https://hn.algolia.com/api/v1/search?tags=comment,story_{story_id}&query={kw}&hitsPerPage=50

There is no universal "company" field in HN ads, so we make a best effort
to pull a company name from the first line of the comment.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from src.models import Job
from src.normalize import clean_html, detect_remote, parse_ts

from .base import http_get_json

NAME = "hn_whoishiring"
STORY_SEARCH = "https://hn.algolia.com/api/v1/search"
HN_ITEM_URL = "https://news.ycombinator.com/item?id={id}"

# Patterns like: "Stripe | Remote | Senior Engineer | ..."
_FIRST_LINE_RE = re.compile(r"([^|]+)\s*\|")


def _find_latest_story() -> dict[str, Any] | None:
    data = http_get_json(
        STORY_SEARCH,
        params={
            "query": "Ask HN: Who is hiring?",
            "tags": "story,author_whoishiring",
            "hitsPerPage": "5",
        },
    )
    hits = data.get("hits") or []
    # Pick the most recent
    hits.sort(key=lambda h: h.get("created_at_i") or 0, reverse=True)
    return hits[0] if hits else None


def fetch_comments_for_keyword(story_id: int, keyword: str, limit: int = 50) -> list[Job]:
    data = http_get_json(
        STORY_SEARCH,
        params={
            "tags": f"comment,story_{story_id}",
            "query": keyword,
            "hitsPerPage": str(limit),
        },
    )
    hits = data.get("hits") or []
    out: list[Job] = []
    for h in hits:
        try:
            job = _to_job(story_id, h)
        except Exception:
            continue
        if job.title and job.apply_url:
            out.append(job)
    return out


def fetch(targets: list[str], search: dict[str, Any]) -> list[Job]:  # noqa: ARG001
    """Targets ignored. We find the active thread, then pull comments
    matching each configured keyword, dedup by comment ID.
    """
    story = _find_latest_story()
    if not story:
        return []
    story_id = story.get("objectID") or story.get("story_id")
    if not story_id:
        return []
    out: list[Job] = []
    seen_ids: set[str] = set()
    for kw in search.get("keywords") or []:
        for j in fetch_comments_for_keyword(int(story_id), kw):
            if j.source_id in seen_ids:
                continue
            seen_ids.add(j.source_id)
            out.append(j)
    return out


def _to_job(story_id: int, hit: dict[str, Any]) -> Job:
    body = clean_html(hit.get("comment_text") or "")
    if not body:
        raise ValueError("empty comment body")
    first_line = body.split("\n", 1)[0].strip()
    company = _extract_company(first_line) or "HN Who's Hiring"
    location = _extract_location(first_line)

    comment_id = str(hit.get("objectID") or hit.get("id") or "")
    apply_url = HN_ITEM_URL.format(id=comment_id)
    posted = parse_ts(hit.get("created_at"))
    if posted is None:
        try:
            ts = int(hit.get("created_at_i") or 0)
            posted = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
        except (TypeError, ValueError):
            posted = None

    return Job(
        source=NAME,
        source_id=comment_id,
        title=first_line[:140] or "HN hiring listing",
        company=company,
        location=location,
        remote=detect_remote(location, body),
        description=body,
        apply_url=apply_url,
        posted_at=posted,
        raw={"story_id": story_id, "points": hit.get("points")},
    )


def _extract_company(first_line: str) -> str | None:
    m = _FIRST_LINE_RE.match(first_line)
    if not m:
        return None
    name = m.group(1).strip()
    # Strip trailing markers like "(YC S22)" or leading tags.
    name = re.sub(r"\(.*?\)", "", name).strip()
    return name or None


def _extract_location(first_line: str) -> str | None:
    parts = [p.strip() for p in first_line.split("|") if p.strip()]
    for p in parts[1:4]:
        pl = p.lower()
        if any(
            tok in pl
            for tok in (
                "remote",
                "onsite",
                "hybrid",
                "usa",
                "us,",
                "uk",
                "europe",
                "eu,",
                "germany",
                "uk,",
                "london",
                "berlin",
                "ny",
                "sf",
                "san francisco",
            )
        ):
            return p
    return None
