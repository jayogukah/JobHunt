"""Helpers that turn raw source payloads into unified Job records."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any

from dateutil import parser as dtparser

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")
_NEWLINES_RE = re.compile(r"\n{3,}")


def clean_html(raw: str | None) -> str:
    """Strip tags and normalize whitespace without pulling in a parser."""
    if not raw:
        return ""
    text = _TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    # collapse internal whitespace but keep paragraph breaks
    lines = [_WS_RE.sub(" ", line).strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    text = _NEWLINES_RE.sub("\n\n", text)
    return text.strip()


def parse_ts(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        # seconds or millis since epoch
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    if isinstance(value, str):
        try:
            dt = dtparser.parse(value)
        except (ValueError, TypeError, OverflowError):
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return None


def detect_remote(location: str | None, description: str) -> bool | None:
    """Best-effort remote flag. Returns None if we genuinely can't tell."""
    hay = f"{location or ''} {description[:800]}".lower()
    if "remote" in hay or "work from home" in hay or "work from anywhere" in hay:
        return True
    if "on-site" in hay or "onsite" in hay or "in-office" in hay or "in office" in hay:
        return False
    return None


def short_location(parts: list[str | None]) -> str | None:
    """Join the truthy parts of a location with commas."""
    cleaned = [p.strip() for p in parts if p and p.strip()]
    return ", ".join(cleaned) if cleaned else None
